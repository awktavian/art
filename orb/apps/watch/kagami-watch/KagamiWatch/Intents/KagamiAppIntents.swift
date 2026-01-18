//
// KagamiAppIntents.swift - Siri App Intents
//
// Colony: Beacon (e5) - Communication
//
// Provides Siri integration for voice commands:
//   - "Turn on Movie Mode"
//   - "Goodnight"
//   - "Welcome Home"
//   - "Turn off the lights"
//
// h(x) >= 0. Always.
//

import AppIntents
import SwiftUI

// MARK: - Shared API Service for Intents

/// Shared API service instance for App Intents to avoid creating new instances per intent
@MainActor
enum IntentAPIService {
    private static var _shared: KagamiAPIService?

    static var shared: KagamiAPIService {
        if let existing = _shared {
            return existing
        }
        let service = KagamiAPIService()
        _shared = service
        return service
    }

    static func ensureConnected() async {
        let api = shared
        if !api.isConnected {
            await api.connect()
        }
    }
}

// MARK: - Movie Mode Intent

struct MovieModeIntent: AppIntent {
    static var title: LocalizedStringResource = "Movie Mode"
    static var description = IntentDescription("Activate Movie Mode scene")
    static var openAppWhenRun: Bool = false

    @MainActor
    func perform() async throws -> some IntentResult {
        await IntentAPIService.ensureConnected()
        let success = await IntentAPIService.shared.executeScene("movie_mode")

        if success {
            HapticPattern.sceneActivated.play()
            return .result(dialog: "Movie mode activated")
        } else {
            HapticPattern.error.play()
            throw IntentError.sceneFailed
        }
    }
}

// MARK: - Goodnight Intent

struct GoodnightIntent: AppIntent {
    static var title: LocalizedStringResource = "Goodnight"
    static var description = IntentDescription("Activate Goodnight scene")
    static var openAppWhenRun: Bool = false

    @MainActor
    func perform() async throws -> some IntentResult {
        await IntentAPIService.ensureConnected()
        let success = await IntentAPIService.shared.executeScene("goodnight")

        if success {
            HapticPattern.sceneActivated.play()
            return .result(dialog: "Goodnight scene activated")
        } else {
            HapticPattern.error.play()
            throw IntentError.sceneFailed
        }
    }
}

// MARK: - Welcome Home Intent

struct WelcomeHomeIntent: AppIntent {
    static var title: LocalizedStringResource = "Welcome Home"
    static var description = IntentDescription("Activate Welcome Home scene")
    static var openAppWhenRun: Bool = false

    @MainActor
    func perform() async throws -> some IntentResult {
        await IntentAPIService.ensureConnected()
        let success = await IntentAPIService.shared.executeScene("welcome_home")

        if success {
            HapticPattern.sceneActivated.play()
            return .result(dialog: "Welcome home")
        } else {
            HapticPattern.error.play()
            throw IntentError.sceneFailed
        }
    }
}

// MARK: - Lights Intent

struct SetLightsIntent: AppIntent {
    static var title: LocalizedStringResource = "Set Lights"
    static var description = IntentDescription("Set light brightness level")
    static var openAppWhenRun: Bool = false

    @Parameter(title: "Brightness", default: 50)
    var brightness: Int

    @MainActor
    func perform() async throws -> some IntentResult {
        await IntentAPIService.ensureConnected()
        await IntentAPIService.shared.setLights(brightness)

        HapticPattern.success.play()
        return .result(dialog: "Lights set to \(brightness) percent")
    }
}

struct TurnOffLightsIntent: AppIntent {
    static var title: LocalizedStringResource = "Turn Off Lights"
    static var description = IntentDescription("Turn off all lights")
    static var openAppWhenRun: Bool = false

    @MainActor
    func perform() async throws -> some IntentResult {
        await IntentAPIService.ensureConnected()
        await IntentAPIService.shared.setLights(0)

        HapticPattern.success.play()
        return .result(dialog: "Lights turned off")
    }
}

struct TurnOnLightsIntent: AppIntent {
    static var title: LocalizedStringResource = "Turn On Lights"
    static var description = IntentDescription("Turn on all lights")
    static var openAppWhenRun: Bool = false

    @MainActor
    func perform() async throws -> some IntentResult {
        await IntentAPIService.ensureConnected()
        await IntentAPIService.shared.setLights(80)

        HapticPattern.success.play()
        return .result(dialog: "Lights turned on")
    }
}

// MARK: - Fireplace Intent

struct ToggleFireplaceIntent: AppIntent {
    static var title: LocalizedStringResource = "Toggle Fireplace"
    static var description = IntentDescription("Turn the fireplace on or off")
    static var openAppWhenRun: Bool = false

    @MainActor
    func perform() async throws -> some IntentResult {
        await IntentAPIService.ensureConnected()
        await IntentAPIService.shared.toggleFireplace()

        HapticPattern.success.play()
        return .result(dialog: "Fireplace toggled")
    }
}

// MARK: - TV Control Intents

struct RaiseTVIntent: AppIntent {
    static var title: LocalizedStringResource = "Raise TV"
    static var description = IntentDescription("Raise the TV to storage position")
    static var openAppWhenRun: Bool = false

    @MainActor
    func perform() async throws -> some IntentResult {
        await IntentAPIService.ensureConnected()
        await IntentAPIService.shared.tvControl("raise")

        HapticPattern.success.play()
        return .result(dialog: "TV raising")
    }
}

struct LowerTVIntent: AppIntent {
    static var title: LocalizedStringResource = "Lower TV"
    static var description = IntentDescription("Lower the TV to viewing position")
    static var openAppWhenRun: Bool = false

    @MainActor
    func perform() async throws -> some IntentResult {
        await IntentAPIService.ensureConnected()
        await IntentAPIService.shared.tvControl("lower")

        HapticPattern.success.play()
        return .result(dialog: "TV lowering")
    }
}

// MARK: - Announce Intent

struct AnnounceIntent: AppIntent {
    static var title: LocalizedStringResource = "Announce"
    static var description = IntentDescription("Announce a message through the speakers")
    static var openAppWhenRun: Bool = false

    @Parameter(title: "Message")
    var message: String

    @MainActor
    func perform() async throws -> some IntentResult {
        await IntentAPIService.ensureConnected()
        await IntentAPIService.shared.announce(message)

        HapticPattern.success.play()
        return .result(dialog: "Announced: \(message)")
    }
}

// MARK: - Away Mode Intent

struct AwayModeIntent: AppIntent {
    static var title: LocalizedStringResource = "Away Mode"
    static var description = IntentDescription("Activate Away mode - secure the home")
    static var openAppWhenRun: Bool = false

    @MainActor
    func perform() async throws -> some IntentResult {
        await IntentAPIService.ensureConnected()
        let success = await IntentAPIService.shared.executeScene("away")

        if success {
            HapticPattern.sceneActivated.play()
            return .result(dialog: "Away mode activated")
        } else {
            HapticPattern.error.play()
            throw IntentError.sceneFailed
        }
    }
}

// MARK: - Lock All Intent

struct LockAllIntent: AppIntent {
    static var title: LocalizedStringResource = "Lock All Doors"
    static var description = IntentDescription("Lock all doors in the house")
    static var openAppWhenRun: Bool = false

    @MainActor
    func perform() async throws -> some IntentResult {
        await IntentAPIService.ensureConnected()
        await IntentAPIService.shared.lockAll()

        HapticPattern.success.play()
        return .result(dialog: "All doors locked")
    }
}

// MARK: - Error Types

enum IntentError: Swift.Error, CustomLocalizedStringResourceConvertible {
    case sceneFailed
    case connectionFailed

    var localizedStringResource: LocalizedStringResource {
        switch self {
        case .sceneFailed:
            return "Failed to activate scene. Please try again."
        case .connectionFailed:
            return "Could not connect to Kagami. Check your connection."
        }
    }
}

// MARK: - App Shortcuts Provider

struct KagamiShortcuts: AppShortcutsProvider {
    static var appShortcuts: [AppShortcut] {
        AppShortcut(
            intent: MovieModeIntent(),
            phrases: [
                "Start \(.applicationName) movie mode",
                "Turn on movie mode with \(.applicationName)",
                "Movie time with \(.applicationName)"
            ],
            shortTitle: "Movie Mode",
            systemImageName: "film.fill"
        )

        AppShortcut(
            intent: GoodnightIntent(),
            phrases: [
                "Goodnight with \(.applicationName)",
                "Bedtime with \(.applicationName)",
                "\(.applicationName) goodnight"
            ],
            shortTitle: "Goodnight",
            systemImageName: "moon.fill"
        )

        AppShortcut(
            intent: WelcomeHomeIntent(),
            phrases: [
                "I'm home with \(.applicationName)",
                "Welcome home with \(.applicationName)",
                "\(.applicationName) welcome home"
            ],
            shortTitle: "Welcome Home",
            systemImageName: "house.fill"
        )

        AppShortcut(
            intent: AwayModeIntent(),
            phrases: [
                "I'm leaving with \(.applicationName)",
                "Away mode with \(.applicationName)",
                "\(.applicationName) away"
            ],
            shortTitle: "Away Mode",
            systemImageName: "car.fill"
        )

        AppShortcut(
            intent: TurnOffLightsIntent(),
            phrases: [
                "Turn off lights with \(.applicationName)",
                "Lights off with \(.applicationName)",
                "\(.applicationName) lights off"
            ],
            shortTitle: "Lights Off",
            systemImageName: "lightbulb.slash.fill"
        )

        AppShortcut(
            intent: TurnOnLightsIntent(),
            phrases: [
                "Turn on lights with \(.applicationName)",
                "Lights on with \(.applicationName)",
                "\(.applicationName) lights on"
            ],
            shortTitle: "Lights On",
            systemImageName: "lightbulb.fill"
        )

        AppShortcut(
            intent: ToggleFireplaceIntent(),
            phrases: [
                "Toggle fireplace with \(.applicationName)",
                "Fireplace with \(.applicationName)",
                "\(.applicationName) fire"
            ],
            shortTitle: "Fireplace",
            systemImageName: "flame.fill"
        )

        AppShortcut(
            intent: RaiseTVIntent(),
            phrases: [
                "Raise the TV with \(.applicationName)",
                "TV up with \(.applicationName)",
                "\(.applicationName) raise TV"
            ],
            shortTitle: "Raise TV",
            systemImageName: "tv.fill"
        )

        AppShortcut(
            intent: LowerTVIntent(),
            phrases: [
                "Lower the TV with \(.applicationName)",
                "TV down with \(.applicationName)",
                "\(.applicationName) lower TV"
            ],
            shortTitle: "Lower TV",
            systemImageName: "tv.fill"
        )

        AppShortcut(
            intent: LockAllIntent(),
            phrases: [
                "Lock all doors with \(.applicationName)",
                "Lock up with \(.applicationName)",
                "\(.applicationName) lock doors"
            ],
            shortTitle: "Lock All",
            systemImageName: "lock.fill"
        )
    }
}
