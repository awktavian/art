//
// KagamiAppIntents.swift
// KagamiVision
//
// App Intents for Siri integration in visionOS 2.
// Enables voice commands like "Hey Siri, movie mode in Kagami"
//
// Features:
//   - Scene activation (movie mode, goodnight, welcome home)
//   - Light control (set brightness, turn on/off)
//   - Shade control (open/close)
//   - Fireplace control
//   - Room-specific commands
//

import AppIntents
import SwiftUI

// MARK: - App Shortcuts Provider

struct KagamiShortcuts: AppShortcutsProvider {
    static var appShortcuts: [AppShortcut] {
        AppShortcut(
            intent: MovieModeIntent(),
            phrases: [
                "Start movie mode in \(.applicationName)",
                "Movie mode with \(.applicationName)",
                "Turn on movie mode in \(.applicationName)"
            ],
            shortTitle: "Movie Mode",
            systemImageName: "film"
        )

        AppShortcut(
            intent: GoodnightIntent(),
            phrases: [
                "Goodnight with \(.applicationName)",
                "Start goodnight in \(.applicationName)",
                "Goodnight scene in \(.applicationName)"
            ],
            shortTitle: "Goodnight",
            systemImageName: "moon.fill"
        )

        AppShortcut(
            intent: WelcomeHomeIntent(),
            phrases: [
                "Welcome home with \(.applicationName)",
                "I'm home with \(.applicationName)"
            ],
            shortTitle: "Welcome Home",
            systemImageName: "house.fill"
        )

        AppShortcut(
            intent: SetLightsIntent(),
            phrases: [
                "Set lights in \(.applicationName)",
                "Adjust lights in \(.applicationName)"
            ],
            shortTitle: "Set Lights",
            systemImageName: "lightbulb.fill"
        )

        AppShortcut(
            intent: LightsOffIntent(),
            phrases: [
                "Turn off all lights in \(.applicationName)",
                "Lights off in \(.applicationName)"
            ],
            shortTitle: "Lights Off",
            systemImageName: "lightbulb.slash"
        )

        AppShortcut(
            intent: ToggleFireplaceIntent(),
            phrases: [
                "Toggle fireplace in \(.applicationName)",
                "Fireplace with \(.applicationName)"
            ],
            shortTitle: "Toggle Fireplace",
            systemImageName: "flame"
        )
    }
}

// MARK: - Movie Mode Intent

struct MovieModeIntent: AppIntent {
    static var title: LocalizedStringResource = "Movie Mode"
    static var description = IntentDescription("Activates movie mode scene")
    static var openAppWhenRun: Bool = false

    @MainActor
    func perform() async throws -> some IntentResult & ProvidesDialog {
        let service = KagamiAPIService.shared
        await service.connect()
        await service.executeScene("movie_mode")

        return .result(dialog: "Movie mode activated. Enjoy your movie!")
    }
}

// MARK: - Goodnight Intent

struct GoodnightIntent: AppIntent {
    static var title: LocalizedStringResource = "Goodnight"
    static var description = IntentDescription("Activates goodnight scene")
    static var openAppWhenRun: Bool = false

    @MainActor
    func perform() async throws -> some IntentResult & ProvidesDialog {
        let service = KagamiAPIService.shared
        await service.connect()
        await service.executeScene("goodnight")

        return .result(dialog: "Goodnight! All lights off and doors locked.")
    }
}

// MARK: - Welcome Home Intent

struct WelcomeHomeIntent: AppIntent {
    static var title: LocalizedStringResource = "Welcome Home"
    static var description = IntentDescription("Activates welcome home scene")
    static var openAppWhenRun: Bool = false

    @MainActor
    func perform() async throws -> some IntentResult & ProvidesDialog {
        let service = KagamiAPIService.shared
        await service.connect()
        await service.executeScene("welcome_home")

        return .result(dialog: "Welcome home! Lights are on and ready for you.")
    }
}

// MARK: - Set Lights Intent

struct SetLightsIntent: AppIntent {
    static var title: LocalizedStringResource = "Set Lights"
    static var description = IntentDescription("Sets light brightness level")
    static var openAppWhenRun: Bool = false

    @Parameter(title: "Brightness", description: "Brightness level from 0 to 100")
    var brightness: Int

    @Parameter(title: "Room", description: "Specific room (optional)")
    var room: String?

    @MainActor
    func perform() async throws -> some IntentResult & ProvidesDialog {
        let level = max(0, min(100, brightness))

        let service = KagamiAPIService.shared
        await service.connect()

        if let roomName = room {
            await service.setLights(level, rooms: [roomName])
            return .result(dialog: "Set \(roomName) lights to \(level) percent.")
        } else {
            await service.setLights(level)
            return .result(dialog: "Set all lights to \(level) percent.")
        }
    }
}

// MARK: - Lights Off Intent

struct LightsOffIntent: AppIntent {
    static var title: LocalizedStringResource = "Lights Off"
    static var description = IntentDescription("Turns off all lights")
    static var openAppWhenRun: Bool = false

    @MainActor
    func perform() async throws -> some IntentResult & ProvidesDialog {
        let service = KagamiAPIService.shared
        await service.connect()
        await service.setLights(0)

        return .result(dialog: "All lights are now off.")
    }
}

// MARK: - Toggle Fireplace Intent

struct ToggleFireplaceIntent: AppIntent {
    static var title: LocalizedStringResource = "Toggle Fireplace"
    static var description = IntentDescription("Toggles the fireplace on or off")
    static var openAppWhenRun: Bool = false

    @MainActor
    func perform() async throws -> some IntentResult & ProvidesDialog {
        let service = KagamiAPIService.shared
        await service.connect()
        await service.toggleFireplace()

        let state = service.fireplaceOn ? "on" : "off"
        return .result(dialog: "Fireplace is now \(state).")
    }
}

// MARK: - Control Shades Intent

struct ControlShadesIntent: AppIntent {
    static var title: LocalizedStringResource = "Control Shades"
    static var description = IntentDescription("Opens or closes window shades")
    static var openAppWhenRun: Bool = false

    @Parameter(title: "Action", description: "Open or close")
    var action: ShadeAction

    @Parameter(title: "Room", description: "Specific room (optional)")
    var room: String?

    enum ShadeAction: String, AppEnum {
        case open
        case close

        static var typeDisplayRepresentation: TypeDisplayRepresentation = "Shade Action"
        static var caseDisplayRepresentations: [ShadeAction: DisplayRepresentation] = [
            .open: "Open",
            .close: "Close"
        ]
    }

    @MainActor
    func perform() async throws -> some IntentResult & ProvidesDialog {
        let service = KagamiAPIService.shared
        await service.connect()

        if let roomName = room {
            await service.controlShades(action.rawValue, rooms: [roomName])
            return .result(dialog: "\(roomName) shades are now \(action.rawValue).")
        } else {
            await service.controlShades(action.rawValue)
            return .result(dialog: "All shades are now \(action.rawValue).")
        }
    }
}

// MARK: - Open Kagami Intent

struct OpenKagamiIntent: AppIntent {
    static var title: LocalizedStringResource = "Open Kagami"
    static var description = IntentDescription("Opens Kagami Vision")
    static var openAppWhenRun: Bool = true

    func perform() async throws -> some IntentResult {
        return .result()
    }
}

// MARK: - Show Room Intent

struct ShowRoomIntent: AppIntent {
    static var title: LocalizedStringResource = "Show Room"
    static var description = IntentDescription("Shows a specific room in Kagami Vision")
    static var openAppWhenRun: Bool = true

    @Parameter(title: "Room Name")
    var roomName: String

    func perform() async throws -> some IntentResult & ProvidesDialog {
        // Opens app and navigates to room
        // Navigation would be handled by the app on launch
        return .result(dialog: "Opening \(roomName) in Kagami Vision.")
    }
}

// MARK: - Start Voice Command Intent (Accessibility Fallback)

/// Intent that provides voice command access for users who cannot use gaze tracking
/// This serves as an accessibility fallback for the GazeMicButton
struct StartVoiceCommandIntent: AppIntent {
    static var title: LocalizedStringResource = "Start Voice Command"
    static var description = IntentDescription("Activates Kagami voice command mode")
    static var openAppWhenRun: Bool = true

    func perform() async throws -> some IntentResult & ProvidesDialog {
        // Posts notification to activate voice command mode in the app
        await MainActor.run {
            NotificationCenter.default.post(
                name: NSNotification.Name("KagamiStartVoiceCommand"),
                object: nil
            )
        }
        return .result(dialog: "Voice command mode activated. Speak your command.")
    }
}

// MARK: - Accessibility Quick Actions

/// Quick action intent for users who need alternative input methods
struct AccessibilityQuickActionIntent: AppIntent {
    static var title: LocalizedStringResource = "Kagami Quick Action"
    static var description = IntentDescription("Perform a quick smart home action")
    static var openAppWhenRun: Bool = false

    @Parameter(title: "Action", description: "The action to perform")
    var action: QuickActionType

    enum QuickActionType: String, AppEnum {
        case toggleLights = "toggle_lights"
        case movieMode = "movie_mode"
        case goodnight = "goodnight"
        case welcomeHome = "welcome_home"
        case allOff = "all_off"

        static var typeDisplayRepresentation: TypeDisplayRepresentation = "Quick Action"
        static var caseDisplayRepresentations: [QuickActionType: DisplayRepresentation] = [
            .toggleLights: "Toggle Lights",
            .movieMode: "Movie Mode",
            .goodnight: "Goodnight",
            .welcomeHome: "Welcome Home",
            .allOff: "All Off"
        ]
    }

    @MainActor
    func perform() async throws -> some IntentResult & ProvidesDialog {
        let service = KagamiAPIService.shared
        await service.connect()

        let response: String
        switch action {
        case .toggleLights:
            await service.setLights(100)
            response = "Lights toggled."
        case .movieMode:
            await service.executeScene("movie_mode")
            response = "Movie mode activated."
        case .goodnight:
            await service.executeScene("goodnight")
            response = "Goodnight scene activated."
        case .welcomeHome:
            await service.executeScene("welcome_home")
            response = "Welcome home!"
        case .allOff:
            await service.setLights(0)
            response = "All lights off."
        }

        return .result(dialog: "\(response)")
    }
}

// MARK: - Extended Shortcuts Provider

extension KagamiShortcuts {
    /// Additional shortcuts for accessibility users
    @AppShortcutsBuilder
    static var accessibilityShortcuts: [AppShortcut] {
        AppShortcut(
            intent: StartVoiceCommandIntent(),
            phrases: [
                "Start voice command in \(.applicationName)",
                "Voice mode in \(.applicationName)",
                "Talk to \(.applicationName)"
            ],
            shortTitle: "Voice Command",
            systemImageName: "mic.fill"
        )

        AppShortcut(
            intent: AccessibilityQuickActionIntent(),
            phrases: [
                "Quick action \(\.$action) in \(.applicationName)",
                "\(\.$action) with \(.applicationName)"
            ],
            shortTitle: "Quick Action",
            systemImageName: "bolt.fill"
        )
    }
}

/*
 * App Intents enable natural voice control via Siri.
 * "Hey Siri, movie mode in Kagami" activates the scene.
 *
 * Accessibility Fallbacks:
 * - StartVoiceCommandIntent: For users who cannot use gaze tracking
 * - AccessibilityQuickActionIntent: For quick voice-activated smart home control
 *
 * These intents ensure the app remains fully accessible to users with
 * eye tracking difficulties or other visual impairments.
 */
