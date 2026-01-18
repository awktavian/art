//
// ShortcutsIntegration.swift -- Siri Shortcuts & VoiceControl Integration
//
// Colony: Beacon (e5) -- Communication
//
// Features:
//   - Siri Shortcuts donation for frequently used actions
//   - App Intents for iOS 16+ Shortcuts.app integration
//   - VoiceControl command registration
//   - Shortcut suggestions based on usage patterns
//   - Widget integration for quick actions
//
// Documentation:
//   - Shortcuts.app: Users can create automations using Kagami intents
//   - VoiceControl: "Kagami movie mode", "Kagami goodnight", etc.
//   - Siri: "Hey Siri, activate movie mode with Kagami"
//
// h(x) >= 0. Always.
//

import Foundation
import SwiftUI
import Intents
import IntentsUI
import AppIntents
import CoreSpotlight
import OSLog
import Combine

// MARK: - Shortcut Category

/// Categories for organizing shortcuts
enum ShortcutCategory: String, CaseIterable {
    case scenes = "Scenes"
    case lighting = "Lighting"
    case climate = "Climate"
    case security = "Security"
    case media = "Media"
    case automation = "Automation"

    var icon: String {
        switch self {
        case .scenes: return "sparkles"
        case .lighting: return "lightbulb"
        case .climate: return "thermometer"
        case .security: return "lock.shield"
        case .media: return "tv"
        case .automation: return "gearshape.2"
        }
    }
}

// MARK: - Shortcut Suggestion

/// A suggested shortcut based on user behavior
struct ShortcutSuggestion: Identifiable {
    let id: String
    let title: String
    let subtitle: String
    let category: ShortcutCategory
    let intent: any AppIntent
    let relevanceScore: Double

    /// Suggested phrase for Siri
    var suggestedPhrase: String {
        "Kagami \(title.lowercased())"
    }
}

// MARK: - Voice Control Command

/// VoiceControl command definition
struct VoiceControlCommand {
    let phrase: String
    let alternativePhrases: [String]
    let action: () async -> Bool

    /// All phrases including alternatives
    var allPhrases: [String] {
        [phrase] + alternativePhrases
    }
}

// MARK: - Shortcuts Integration Manager

/// Manages Siri Shortcuts, App Intents, and VoiceControl integration
@MainActor
final class ShortcutsIntegration: ObservableObject {

    // MARK: - Singleton

    static let shared = ShortcutsIntegration()

    // MARK: - Published State

    @Published private(set) var donatedShortcuts: [String: Int] = [:] // ID: donation count
    @Published private(set) var suggestedShortcuts: [ShortcutSuggestion] = []
    @Published private(set) var voiceControlEnabled: Bool = false

    // MARK: - Private

    private let logger = Logger(subsystem: "com.kagami.ios", category: "Shortcuts")
    private var cancellables = Set<AnyCancellable>()

    // Storage keys
    private enum StorageKey {
        static let donatedShortcuts = "kagami.shortcuts.donated"
        static let shortcutUsage = "kagami.shortcuts.usage"
    }

    // Voice control commands
    private var voiceCommands: [VoiceControlCommand] = []

    // MARK: - Init

    private init() {
        loadPersistedData()
        registerVoiceCommands()
        setupUsageTracking()
    }

    // MARK: - Persistence

    private func loadPersistedData() {
        if let data = UserDefaults.standard.dictionary(forKey: StorageKey.donatedShortcuts) as? [String: Int] {
            donatedShortcuts = data
        }

        updateSuggestions()
    }

    private func saveDonatedShortcuts() {
        UserDefaults.standard.set(donatedShortcuts, forKey: StorageKey.donatedShortcuts)
    }

    // MARK: - Usage Tracking

    private func setupUsageTracking() {
        // Listen for shortcut usage to improve suggestions
        NotificationCenter.default.publisher(for: .shortcutUsed)
            .compactMap { $0.userInfo?["shortcutId"] as? String }
            .sink { [weak self] shortcutId in
                self?.recordUsage(shortcutId: shortcutId)
            }
            .store(in: &cancellables)
    }

    private func recordUsage(shortcutId: String) {
        var usage = UserDefaults.standard.dictionary(forKey: StorageKey.shortcutUsage) as? [String: Int] ?? [:]
        usage[shortcutId, default: 0] += 1
        UserDefaults.standard.set(usage, forKey: StorageKey.shortcutUsage)

        updateSuggestions()
    }

    // MARK: - Shortcut Donation

    /// Donate a shortcut for Siri suggestions
    /// - Parameters:
    ///   - intentType: The type of intent to donate
    ///   - parameters: Parameters for the shortcut
    func donateShortcut(
        intentType: ShortcutIntentType,
        parameters: [String: Any] = [:]
    ) {
        let shortcutId = intentType.id

        // Increment donation count
        donatedShortcuts[shortcutId, default: 0] += 1
        saveDonatedShortcuts()

        // Create and donate the intent
        Task {
            await donateIntent(for: intentType, parameters: parameters)
        }

        logger.debug("Donated shortcut: \(intentType.title) (count: \(self.donatedShortcuts[shortcutId] ?? 0))")
    }

    private func donateIntent(for intentType: ShortcutIntentType, parameters: [String: Any]) async {
        // Create INInteraction for donation
        let intent = intentType.createSiriIntent(parameters: parameters)
        let interaction = INInteraction(intent: intent, response: nil)

        interaction.identifier = intentType.id
        interaction.groupIdentifier = intentType.category.rawValue

        do {
            try await interaction.donate()
            logger.info("Successfully donated intent: \(intentType.title)")
        } catch {
            logger.error("Failed to donate intent: \(error.localizedDescription)")
        }
    }

    /// Donate multiple shortcuts at once
    func donateShortcuts(_ types: [ShortcutIntentType]) {
        for type in types {
            donateShortcut(intentType: type)
        }
    }

    // MARK: - Suggestions

    private func updateSuggestions() {
        let usage = UserDefaults.standard.dictionary(forKey: StorageKey.shortcutUsage) as? [String: Int] ?? [:]

        var suggestions: [ShortcutSuggestion] = []

        // Generate suggestions based on usage patterns
        for intentType in ShortcutIntentType.allCases {
            let usageCount = usage[intentType.id] ?? 0
            let donationCount = donatedShortcuts[intentType.id] ?? 0

            // Calculate relevance score
            let relevance = Double(usageCount * 2 + donationCount) / 10.0

            if relevance > 0.1 {
                let suggestion = ShortcutSuggestion(
                    id: intentType.id,
                    title: intentType.title,
                    subtitle: intentType.description,
                    category: intentType.category,
                    intent: intentType.createAppIntent(),
                    relevanceScore: min(1.0, relevance)
                )
                suggestions.append(suggestion)
            }
        }

        // Sort by relevance
        suggestedShortcuts = suggestions.sorted { $0.relevanceScore > $1.relevanceScore }
    }

    // MARK: - Voice Control

    private func registerVoiceCommands() {
        voiceCommands = [
            // Scene commands
            VoiceControlCommand(
                phrase: "Kagami movie mode",
                alternativePhrases: ["movie mode", "start movie", "movie time"],
                action: { await KagamiAPIService.shared.executeScene("movie_mode") }
            ),
            VoiceControlCommand(
                phrase: "Kagami goodnight",
                alternativePhrases: ["goodnight", "go to sleep", "bedtime"],
                action: { await KagamiAPIService.shared.executeScene("goodnight") }
            ),
            VoiceControlCommand(
                phrase: "Kagami welcome home",
                alternativePhrases: ["I'm home", "welcome home", "arriving home"],
                action: { await KagamiAPIService.shared.executeScene("welcome_home") }
            ),

            // Light commands
            VoiceControlCommand(
                phrase: "Kagami lights on",
                alternativePhrases: ["turn on lights", "lights full"],
                action: { await KagamiAPIService.shared.setLights(100) }
            ),
            VoiceControlCommand(
                phrase: "Kagami lights off",
                alternativePhrases: ["turn off lights", "lights out"],
                action: { await KagamiAPIService.shared.setLights(0) }
            ),
            VoiceControlCommand(
                phrase: "Kagami dim lights",
                alternativePhrases: ["dim the lights", "low lights"],
                action: { await KagamiAPIService.shared.setLights(25) }
            ),

            // Security commands
            VoiceControlCommand(
                phrase: "Kagami lock up",
                alternativePhrases: ["lock all doors", "secure the house"],
                action: { await KagamiAPIService.shared.lockAll() }
            ),

            // TV commands
            VoiceControlCommand(
                phrase: "Kagami lower TV",
                alternativePhrases: ["TV down", "bring down TV"],
                action: { await KagamiAPIService.shared.tvControl("lower") }
            ),
            VoiceControlCommand(
                phrase: "Kagami raise TV",
                alternativePhrases: ["TV up", "hide TV"],
                action: { await KagamiAPIService.shared.tvControl("raise") }
            )
        ]

        voiceControlEnabled = true
        logger.info("Registered \(self.voiceCommands.count) voice commands")
    }

    /// Find and execute a voice command
    /// - Parameter phrase: The spoken phrase
    /// - Returns: True if a command was matched and executed
    func executeVoiceCommand(_ phrase: String) async -> Bool {
        let normalizedPhrase = phrase.lowercased().trimmingCharacters(in: .whitespacesAndNewlines)

        for command in voiceCommands {
            if command.allPhrases.contains(where: { normalizedPhrase.contains($0.lowercased()) }) {
                logger.info("Executing voice command: \(command.phrase)")
                return await command.action()
            }
        }

        logger.debug("No voice command matched: \(phrase)")
        return false
    }

    /// Get all registered voice command phrases
    var allVoicePhrases: [String] {
        voiceCommands.flatMap { $0.allPhrases }
    }

    // MARK: - Spotlight Indexing

    /// Index shortcuts in Spotlight for system-wide search
    func indexShortcutsInSpotlight() {
        var searchableItems: [CSSearchableItem] = []

        for intentType in ShortcutIntentType.allCases {
            let attributeSet = CSSearchableItemAttributeSet(contentType: .item)
            attributeSet.title = intentType.title
            attributeSet.contentDescription = intentType.description
            attributeSet.keywords = intentType.keywords

            let item = CSSearchableItem(
                uniqueIdentifier: "shortcut-\(intentType.id)",
                domainIdentifier: "com.kagami.shortcuts",
                attributeSet: attributeSet
            )

            searchableItems.append(item)
        }

        CSSearchableIndex.default().indexSearchableItems(searchableItems) { [weak self] error in
            if let error = error {
                self?.logger.error("Spotlight indexing failed: \(error.localizedDescription)")
            } else {
                self?.logger.info("Indexed \(searchableItems.count) shortcuts in Spotlight")
            }
        }
    }

    // MARK: - Cleanup

    /// Remove all donated shortcuts
    func clearDonatedShortcuts() {
        INInteraction.deleteAll { [weak self] error in
            if let error = error {
                self?.logger.error("Failed to clear shortcuts: \(error.localizedDescription)")
            } else {
                self?.donatedShortcuts.removeAll()
                self?.saveDonatedShortcuts()
                self?.logger.info("Cleared all donated shortcuts")
            }
        }
    }
}

// MARK: - Shortcut Intent Type

/// Defines all available shortcut intent types
enum ShortcutIntentType: String, CaseIterable {
    case movieMode = "movie_mode"
    case goodnight = "goodnight"
    case welcomeHome = "welcome_home"
    case awayMode = "away_mode"
    case focusMode = "focus_mode"
    case lightsOn = "lights_on"
    case lightsOff = "lights_off"
    case dimLights = "dim_lights"
    case openShades = "open_shades"
    case closeShades = "close_shades"
    case lockAll = "lock_all"
    case lowerTV = "lower_tv"
    case raiseTV = "raise_tv"
    case fireplaceOn = "fireplace_on"
    case fireplaceOff = "fireplace_off"
    case safetyStatus = "safety_status"

    var id: String { rawValue }

    var title: String {
        switch self {
        case .movieMode: return "Movie Mode"
        case .goodnight: return "Goodnight"
        case .welcomeHome: return "Welcome Home"
        case .awayMode: return "Away Mode"
        case .focusMode: return "Focus Mode"
        case .lightsOn: return "Lights On"
        case .lightsOff: return "Lights Off"
        case .dimLights: return "Dim Lights"
        case .openShades: return "Open Shades"
        case .closeShades: return "Close Shades"
        case .lockAll: return "Lock All Doors"
        case .lowerTV: return "Lower TV"
        case .raiseTV: return "Raise TV"
        case .fireplaceOn: return "Fireplace On"
        case .fireplaceOff: return "Fireplace Off"
        case .safetyStatus: return "Safety Status"
        }
    }

    var description: String {
        switch self {
        case .movieMode: return "Dim lights, lower TV, close shades"
        case .goodnight: return "All off, lock up, prepare for sleep"
        case .welcomeHome: return "Warm lights, open shades"
        case .awayMode: return "Secure house, reduce energy"
        case .focusMode: return "Bright lights for productivity"
        case .lightsOn: return "Turn all lights to full brightness"
        case .lightsOff: return "Turn all lights off"
        case .dimLights: return "Set lights to 25%"
        case .openShades: return "Open all window shades"
        case .closeShades: return "Close all window shades"
        case .lockAll: return "Lock all smart locks"
        case .lowerTV: return "Lower TV to viewing position"
        case .raiseTV: return "Raise TV to hidden position"
        case .fireplaceOn: return "Turn on the fireplace"
        case .fireplaceOff: return "Turn off the fireplace"
        case .safetyStatus: return "Check home safety score"
        }
    }

    var category: ShortcutCategory {
        switch self {
        case .movieMode, .goodnight, .welcomeHome, .awayMode, .focusMode:
            return .scenes
        case .lightsOn, .lightsOff, .dimLights:
            return .lighting
        case .openShades, .closeShades:
            return .climate
        case .lockAll, .safetyStatus:
            return .security
        case .lowerTV, .raiseTV:
            return .media
        case .fireplaceOn, .fireplaceOff:
            return .climate
        }
    }

    var keywords: [String] {
        var words = title.lowercased().components(separatedBy: " ")
        words.append("kagami")
        words.append("smart home")
        words.append(category.rawValue.lowercased())
        return words
    }

    /// Create a Siri Intent for donation
    func createSiriIntent(parameters: [String: Any] = [:]) -> INIntent {
        // Create a generic intent for Siri donation
        // In production, these would be custom INIntent subclasses
        let intent = INSearchForMediaIntent()
        intent.suggestedInvocationPhrase = "Kagami \(title.lowercased())"
        return intent
    }

    /// Create an App Intent for Shortcuts.app
    func createAppIntent() -> any AppIntent {
        switch self {
        case .movieMode:
            return MovieModeIntent()
        case .goodnight:
            return GoodnightIntent()
        case .welcomeHome:
            return WelcomeHomeIntent()
        case .awayMode:
            return AwayModeIntent()
        case .focusMode:
            return FocusModeAppIntent()
        case .lightsOn:
            return TurnOnLightsIntent()
        case .lightsOff:
            return TurnOffLightsIntent()
        case .dimLights:
            return DimLightsAppIntent()
        case .openShades:
            return OpenShadesIntent()
        case .closeShades:
            return CloseShadesIntent()
        case .lockAll:
            return LockAllDoorsIntent()
        case .lowerTV:
            return LowerTVIntent()
        case .raiseTV:
            return RaiseTVIntent()
        case .fireplaceOn:
            return FireplaceOnAppIntent()
        case .fireplaceOff:
            return FireplaceOffAppIntent()
        case .safetyStatus:
            return SafetyStatusIntent()
        }
    }
}

// MARK: - Additional App Intents

/// Focus Mode Intent
struct FocusModeAppIntent: AppIntent {
    static var title: LocalizedStringResource = "Focus Mode"
    static var description = IntentDescription("Activate focus mode with bright lights")
    static var openAppWhenRun = false

    @MainActor
    func perform() async throws -> some IntentResult & ProvidesDialog {
        let api = KagamiAPIService.shared
        let success = await api.executeScene("focus")
        guard success else {
            throw SiriIntentError.sceneActivationFailed("focus mode")
        }
        return .result(dialog: "Focus mode activated. Lights bright for productivity.")
    }
}

/// Dim Lights Intent
struct DimLightsAppIntent: AppIntent {
    static var title: LocalizedStringResource = "Dim Lights"
    static var description = IntentDescription("Dim all lights to 25%")
    static var openAppWhenRun = false

    @MainActor
    func perform() async throws -> some IntentResult & ProvidesDialog {
        let api = KagamiAPIService.shared
        let success = await api.setLights(25)
        guard success else {
            throw SiriIntentError.lightControlFailed
        }
        return .result(dialog: "Lights dimmed to 25%.")
    }
}

/// Fireplace On Intent
struct FireplaceOnAppIntent: AppIntent {
    static var title: LocalizedStringResource = "Fireplace On"
    static var description = IntentDescription("Turn on the fireplace")
    static var openAppWhenRun = false

    @MainActor
    func perform() async throws -> some IntentResult & ProvidesDialog {
        let api = KagamiAPIService.shared
        let success = await api.toggleFireplace(on: true)
        guard success else {
            throw SiriIntentError.fireplaceControlFailed
        }
        return .result(dialog: "Fireplace is now on.")
    }
}

/// Fireplace Off Intent
struct FireplaceOffAppIntent: AppIntent {
    static var title: LocalizedStringResource = "Fireplace Off"
    static var description = IntentDescription("Turn off the fireplace")
    static var openAppWhenRun = false

    @MainActor
    func perform() async throws -> some IntentResult & ProvidesDialog {
        let api = KagamiAPIService.shared
        let success = await api.toggleFireplace(on: false)
        guard success else {
            throw SiriIntentError.fireplaceControlFailed
        }
        return .result(dialog: "Fireplace is now off.")
    }
}

// MARK: - Notification Names

extension Notification.Name {
    static let shortcutUsed = Notification.Name("kagami.shortcutUsed")
}

// MARK: - Documentation View

/// View showing available shortcuts and voice commands
struct ShortcutsDocumentationView: View {
    @StateObject private var shortcuts = ShortcutsIntegration.shared

    var body: some View {
        NavigationStack {
            List {
                Section("Siri Phrases") {
                    ForEach(ShortcutIntentType.allCases, id: \.id) { type in
                        VStack(alignment: .leading, spacing: 4) {
                            Text(type.title)
                                .font(KagamiFont.headline())
                            Text("\"Hey Siri, \(type.title.lowercased()) with Kagami\"")
                                .font(KagamiFont.caption())
                                .foregroundColor(.accessibleTextSecondary)
                        }
                        .padding(.vertical, 4)
                    }
                }

                Section("Voice Control") {
                    ForEach(shortcuts.allVoicePhrases, id: \.self) { phrase in
                        Text("\"\(phrase)\"")
                            .font(KagamiFont.body())
                    }
                }

                Section("Shortcuts.app") {
                    Text("Open Shortcuts app and search for \"Kagami\" to find all available actions.")
                        .font(KagamiFont.caption())
                        .foregroundColor(.accessibleTextSecondary)
                }
            }
            .navigationTitle("Voice & Shortcuts")
        }
    }
}

/*
 * Mirror
 * Voice is the most natural interface.
 * h(x) >= 0. Always.
 */
