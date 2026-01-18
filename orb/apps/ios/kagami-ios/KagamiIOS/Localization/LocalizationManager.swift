//
// LocalizationManager.swift — Internationalization for iOS
//
// Currently supports: English (en)
// Infrastructure ready for: ES, AR, ZH, VI, JA, KO, FR, DE, PT
// RTL support prepared for Arabic
//
// To add a new language:
// 1. Add translation JSON to Resources/Locales/{code}.json
// 2. Add case to SupportedLanguage enum
// 3. Run app audit to verify completeness
//

import SwiftUI
import Foundation

// MARK: - Supported Languages

/// Languages with actual translation files available.
/// English is the primary language, Arabic and Hebrew added for RTL support.
enum SupportedLanguage: String, CaseIterable, Identifiable {
    case english = "en"
    case arabic = "ar"
    case hebrew = "he"
    // Future languages (uncomment when translation files are added):
    // case spanish = "es"
    // case chinese = "zh"
    // case vietnamese = "vi"
    // case japanese = "ja"
    // case korean = "ko"
    // case french = "fr"
    // case german = "de"
    // case portuguese = "pt"

    var id: String { rawValue }

    var displayName: String {
        switch self {
        case .english: return "English"
        case .arabic: return "العربية"
        case .hebrew: return "עברית"
        // Future:
        // case .spanish: return "Español"
        // case .chinese: return "中文"
        // case .vietnamese: return "Tiếng Việt"
        // case .japanese: return "日本語"
        // case .korean: return "한국어"
        // case .french: return "Français"
        // case .german: return "Deutsch"
        // case .portuguese: return "Português"
        }
    }

    var isRTL: Bool {
        switch self {
        case .arabic, .hebrew:
            return true
        default:
            return false
        }
    }

    /// Native direction for the language
    var layoutDirection: LayoutDirection {
        isRTL ? .rightToLeft : .leftToRight
    }

    /// Languages that have complete translation files
    static var implementedLanguages: [SupportedLanguage] {
        [.english, .arabic, .hebrew]
    }
}

// MARK: - Localization Manager

@MainActor
class LocalizationManager: ObservableObject {
    static let shared = LocalizationManager()

    @Published var currentLanguage: SupportedLanguage {
        didSet {
            UserDefaults.standard.set(currentLanguage.rawValue, forKey: "appLanguage")
            loadTranslations()
        }
    }

    @Published var isRTL: Bool = false

    private var translations: [String: Any] = [:]

    private init() {
        // Load saved language or use system default
        // Currently only English is implemented
        if let savedCode = UserDefaults.standard.string(forKey: "appLanguage"),
           let language = SupportedLanguage(rawValue: savedCode),
           SupportedLanguage.implementedLanguages.contains(language) {
            self.currentLanguage = language
        } else {
            // Default to English (only implemented language)
            self.currentLanguage = .english
        }

        loadTranslations()
    }

    private func loadTranslations() {
        isRTL = currentLanguage.isRTL

        // Try to load from bundled JSON (if available)
        // Otherwise use hardcoded strings
        guard let url = Bundle.main.url(forResource: currentLanguage.rawValue, withExtension: "json", subdirectory: "Locales"),
              let data = try? Data(contentsOf: url),
              let json = try? JSONSerialization.jsonObject(with: data) as? [String: Any] else {
            // Load fallback translations
            translations = getFallbackTranslations()
            return
        }

        translations = json
    }

    private func getFallbackTranslations() -> [String: Any] {
        // Basic English translations as fallback
        return [
            "common": [
                "ok": "OK",
                "cancel": "Cancel",
                "save": "Save",
                "delete": "Delete",
                "edit": "Edit",
                "close": "Close",
                "back": "Back",
                "next": "Next",
                "done": "Done",
                "loading": "Loading...",
                "error": "Error",
                "success": "Success"
            ],
            "home": [
                "title": "Home",
                "welcome": "Welcome",
                "good_morning": "Good Morning",
                "good_afternoon": "Good Afternoon",
                "good_evening": "Good Evening",
                "good_night": "Good Night",
                "quick_actions": "Quick Actions",
                "rooms": "Rooms",
                "scenes": "Scenes"
            ],
            "devices": [
                "lights": "Lights",
                "shades": "Shades",
                "thermostat": "Thermostat",
                "lock": "Lock",
                "camera": "Camera",
                "fireplace": "Fireplace",
                "turn_on": "Turn On",
                "turn_off": "Turn Off"
            ],
            "scenes": [
                "movie_mode": "Movie Mode",
                "goodnight": "Goodnight",
                "welcome_home": "Welcome Home",
                "away": "Away",
                "morning": "Morning",
                "focus": "Focus"
            ],
            "settings": [
                "title": "Settings",
                "language": "Language",
                "notifications": "Notifications",
                "account": "Account",
                "privacy": "Privacy",
                "about": "About",
                "logout": "Log Out"
            ],
            "errors": [
                "generic": "Something went wrong. Please try again.",
                "network": "Unable to connect. Please check your connection.",
                "unauthorized": "You are not authorized to perform this action."
            ]
        ]
    }

    /// Get a translated string
    func t(_ key: String) -> String {
        let parts = key.split(separator: ".").map(String.init)
        var current: Any = translations

        for part in parts {
            if let dict = current as? [String: Any], let next = dict[part] {
                current = next
            } else {
                return key
            }
        }

        return current as? String ?? key
    }

    /// Get a translated string with interpolation
    func t(_ key: String, args: [String: String]) -> String {
        var result = t(key)
        for (placeholder, value) in args {
            result = result.replacingOccurrences(of: "{\(placeholder)}", with: value)
        }
        return result
    }

    /// Get a pluralized string
    func tp(_ key: String, count: Int) -> String {
        let plural = count == 1 ? "one" : "other"
        let fullKey = "\(key).\(plural)"
        return t(fullKey, args: ["count": "\(count)"])
    }
}

// MARK: - SwiftUI Environment

struct LocalizationEnvironmentKey: EnvironmentKey {
    static let defaultValue: LocalizationManager = LocalizationManager.shared
}

extension EnvironmentValues {
    var localization: LocalizationManager {
        get { self[LocalizationEnvironmentKey.self] }
        set { self[LocalizationEnvironmentKey.self] = newValue }
    }
}

// MARK: - SwiftUI View Extension

extension View {
    /// Apply RTL layout direction if needed
    func localizedLayoutDirection() -> some View {
        self.environment(\.layoutDirection, LocalizationManager.shared.isRTL ? .rightToLeft : .leftToRight)
    }

    /// Apply RTL-aware horizontal padding
    /// For RTL languages, leading becomes trailing and vice versa
    func rtlPadding(_ edge: RTLEdge, _ length: CGFloat) -> some View {
        modifier(RTLPaddingModifier(edge: edge, length: length))
    }

    /// Apply RTL-aware alignment
    func rtlAlignment() -> some View {
        modifier(RTLAlignmentModifier())
    }

    /// Mirror view horizontally for RTL languages
    func rtlMirror() -> some View {
        modifier(RTLMirrorModifier())
    }
}

// MARK: - RTL Edge

enum RTLEdge {
    case leading
    case trailing

    func resolved(for layoutDirection: LayoutDirection) -> Edge.Set {
        let isRTL = layoutDirection == .rightToLeft
        switch self {
        case .leading:
            return isRTL ? .trailing : .leading
        case .trailing:
            return isRTL ? .leading : .trailing
        }
    }
}

// MARK: - RTL Padding Modifier

struct RTLPaddingModifier: ViewModifier {
    let edge: RTLEdge
    let length: CGFloat

    @Environment(\.layoutDirection) var layoutDirection

    func body(content: Content) -> some View {
        let isRTL = layoutDirection == .rightToLeft

        switch edge {
        case .leading:
            return AnyView(content.padding(isRTL ? .trailing : .leading, length))
        case .trailing:
            return AnyView(content.padding(isRTL ? .leading : .trailing, length))
        }
    }
}

// MARK: - RTL Alignment Modifier

struct RTLAlignmentModifier: ViewModifier {
    @Environment(\.layoutDirection) var layoutDirection

    func body(content: Content) -> some View {
        content
            .multilineTextAlignment(layoutDirection == .rightToLeft ? .trailing : .leading)
    }
}

// MARK: - RTL Mirror Modifier

struct RTLMirrorModifier: ViewModifier {
    @Environment(\.layoutDirection) var layoutDirection

    func body(content: Content) -> some View {
        if layoutDirection == .rightToLeft {
            content.scaleEffect(x: -1, y: 1)
        } else {
            content
        }
    }
}

// MARK: - RTL-Aware HStack

/// An HStack that automatically reverses its content order in RTL languages
struct RTLHStack<Content: View>: View {
    let alignment: VerticalAlignment
    let spacing: CGFloat?
    let content: Content

    @Environment(\.layoutDirection) var layoutDirection

    init(
        alignment: VerticalAlignment = .center,
        spacing: CGFloat? = nil,
        @ViewBuilder content: () -> Content
    ) {
        self.alignment = alignment
        self.spacing = spacing
        self.content = content()
    }

    var body: some View {
        HStack(alignment: alignment, spacing: spacing) {
            content
        }
    }
}

// MARK: - RTL-Aware Leading/Trailing

extension HorizontalAlignment {
    /// Returns leading for LTR, trailing for RTL
    static func rtlLeading(for layoutDirection: LayoutDirection) -> HorizontalAlignment {
        layoutDirection == .rightToLeft ? .trailing : .leading
    }

    /// Returns trailing for LTR, leading for RTL
    static func rtlTrailing(for layoutDirection: LayoutDirection) -> HorizontalAlignment {
        layoutDirection == .rightToLeft ? .leading : .trailing
    }
}

// MARK: - RTL Debug View

/// Debug view to preview RTL layout
struct RTLPreviewWrapper<Content: View>: View {
    let content: Content
    @State private var isRTL = false

    init(@ViewBuilder content: () -> Content) {
        self.content = content()
    }

    var body: some View {
        VStack(spacing: 16) {
            Toggle("RTL Mode", isOn: $isRTL)
                .padding()

            content
                .environment(\.layoutDirection, isRTL ? .rightToLeft : .leftToRight)
        }
    }
}

// MARK: - Convenience Functions

@MainActor
func t(_ key: String) -> String {
    LocalizationManager.shared.t(key)
}

@MainActor
func t(_ key: String, args: [String: String]) -> String {
    LocalizationManager.shared.t(key, args: args)
}

@MainActor
func tp(_ key: String, count: Int) -> String {
    LocalizationManager.shared.tp(key, count: count)
}

// MARK: - String Extension for NSLocalizedString

extension String {
    /// Returns a localized version of the string using NSLocalizedString
    /// Use dot-notation keys that match Localizable.strings entries
    /// Example: "common.ok".localized
    var localized: String {
        NSLocalizedString(self, tableName: nil, bundle: .main, value: self, comment: "")
    }

    /// Returns a localized string with format arguments
    /// Example: "accessibility.safetyScore".localized(with: 95)
    func localized(with args: CVarArg...) -> String {
        String(format: localized, arguments: args)
    }
}

// MARK: - Localization Keys

/// Type-safe localization key references
/// Use these for compile-time safety instead of raw strings
enum L {
    enum Common {
        static let ok = "common.ok"
        static let cancel = "common.cancel"
        static let save = "common.save"
        static let delete = "common.delete"
        static let edit = "common.edit"
        static let close = "common.close"
        static let back = "common.back"
        static let next = "common.next"
        static let done = "common.done"
        static let loading = "common.loading"
        static let error = "common.error"
        static let success = "common.success"
        static let retry = "common.retry"
    }

    enum App {
        static let name = "app.name"
        static let tagline = "app.tagline"
    }

    enum Navigation {
        static let home = "navigation.home"
        static let rooms = "navigation.rooms"
        static let scenes = "navigation.scenes"
        static let settings = "navigation.settings"
    }

    enum Safety {
        static let status = "safety.status"
        static let safe = "safety.safe"
        static let caution = "safety.caution"
        static let warning = "safety.warning"
        static let protected = "safety.protected"
        static let score = "safety.score"
        static let allSafe = "safety.allSafe"
    }

    enum Rooms {
        static let title = "rooms.title"
        static let empty = "rooms.empty"
        static let loading = "rooms.loading"
        static let occupied = "rooms.occupied"
        static let lightsOn = "rooms.lightsOn"
        static let lightsDim = "rooms.lightsDim"
        static let lightsOff = "rooms.lightsOff"
        static let bright = "rooms.bright"
    }

    enum Scenes {
        static let title = "scenes.title"
        static let activate = "scenes.activate"
        static let activated = "scenes.activated"
        static let activating = "scenes.activating"
    }

    enum Settings {
        static let title = "settings.title"
        static let connection = "settings.connection"
        static let connected = "settings.connected"
        static let disconnected = "settings.disconnected"
        static let signOut = "settings.signOut"
        static let about = "settings.about"
        static let version = "settings.version"
    }

    enum Widget {
        static let safetyScoreTitle = "widget.safetyScore.title"
        static let safetyScoreDescription = "widget.safetyScore.description"
        static let quickScenesTitle = "widget.quickScenes.title"
        static let homeStatus = "widget.homeStatus"
    }

    enum Error {
        static let generic = "error.generic"
        static let network = "error.network"
        static let loadRooms = "error.loadRooms"
    }
}
