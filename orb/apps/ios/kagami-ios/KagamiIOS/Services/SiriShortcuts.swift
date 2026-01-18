//
// SiriShortcuts.swift — Additional Siri Intent Implementations
//
// Colony: Nexus (e₄) — Integration
//
// NOTE: AppShortcutsProvider is defined in AppShortcuts.swift
// This file contains additional intent implementations.
//

import AppIntents
import SwiftUI

// Additional shortcuts and intents - AppShortcutsProvider moved to AppShortcuts.swift

// MARK: - Intent Error Types

enum SiriIntentError: Error, LocalizedError {
    case sceneActivationFailed(String)
    case lightControlFailed
    case shadeControlFailed
    case fireplaceControlFailed
    case tvControlFailed
    case lockControlFailed
    case connectionFailed

    var errorDescription: String? {
        switch self {
        case .sceneActivationFailed(let scene):
            return "Could not activate \(scene)"
        case .lightControlFailed:
            return "Could not control lights"
        case .shadeControlFailed:
            return "Could not control shades"
        case .fireplaceControlFailed:
            return "Could not control fireplace"
        case .tvControlFailed:
            return "Could not control TV"
        case .lockControlFailed:
            return "Could not control locks"
        case .connectionFailed:
            return "Could not connect to Kagami"
        }
    }
}

// MARK: - Scene Intents
// Note: MovieModeIntent, GoodnightIntent, WelcomeHomeIntent defined in KagamiIntents.swift
// to avoid duplicate definitions

struct AwayModeIntent: AppIntent {
    static var title: LocalizedStringResource = "Away Mode"
    static var description = IntentDescription("Locks up, turns off lights, and activates away mode")
    static var openAppWhenRun = false

    @MainActor
    func perform() async throws -> some IntentResult & ProvidesDialog {
        let api = KagamiAPIService.shared
        let success = await api.executeScene("away")
        guard success else {
            throw SiriIntentError.sceneActivationFailed("away mode")
        }
        return .result(dialog: "Away mode activated. Everything is secure.")
    }
}

// MARK: - Light Control Intents
// Note: SetLightsIntent is defined in KagamiIntents.swift

struct TurnOnLightsIntent: AppIntent {
    static var title: LocalizedStringResource = "Turn On Lights"
    static var description = IntentDescription("Turns on all lights to full brightness")
    static var openAppWhenRun = false

    @MainActor
    func perform() async throws -> some IntentResult & ProvidesDialog {
        let api = KagamiAPIService.shared
        let success = await api.setLights(100)
        guard success else {
            throw SiriIntentError.lightControlFailed
        }
        return .result(dialog: "All lights are now on.")
    }
}

struct TurnOffLightsIntent: AppIntent {
    static var title: LocalizedStringResource = "Turn Off Lights"
    static var description = IntentDescription("Turns off all lights")
    static var openAppWhenRun = false

    @MainActor
    func perform() async throws -> some IntentResult & ProvidesDialog {
        let api = KagamiAPIService.shared
        let success = await api.setLights(0)
        guard success else {
            throw SiriIntentError.lightControlFailed
        }
        return .result(dialog: "All lights are now off.")
    }
}

// MARK: - Shade Control Intents

struct OpenShadesIntent: AppIntent {
    static var title: LocalizedStringResource = "Open Shades"
    static var description = IntentDescription("Opens all shades")
    static var openAppWhenRun = false

    @Parameter(title: "Room", description: "Specific room (optional)")
    var room: String?

    @MainActor
    func perform() async throws -> some IntentResult & ProvidesDialog {
        let api = KagamiAPIService.shared
        let rooms = room != nil ? [room!] : nil
        let success = await api.controlShades("open", rooms: rooms)
        guard success else {
            throw SiriIntentError.shadeControlFailed
        }
        return .result(dialog: "Shades are now open.")
    }
}

struct CloseShadesIntent: AppIntent {
    static var title: LocalizedStringResource = "Close Shades"
    static var description = IntentDescription("Closes all shades")
    static var openAppWhenRun = false

    @Parameter(title: "Room", description: "Specific room (optional)")
    var room: String?

    @MainActor
    func perform() async throws -> some IntentResult & ProvidesDialog {
        let api = KagamiAPIService.shared
        let rooms = room != nil ? [room!] : nil
        let success = await api.controlShades("close", rooms: rooms)
        guard success else {
            throw SiriIntentError.shadeControlFailed
        }
        return .result(dialog: "Shades are now closed.")
    }
}

// MARK: - Fireplace Intent
// Note: ToggleFireplaceIntent is defined in KagamiIntents.swift

// MARK: - TV Control Intents

struct LowerTVIntent: AppIntent {
    static var title: LocalizedStringResource = "Lower TV"
    static var description = IntentDescription("Lowers the TV to viewing position")
    static var openAppWhenRun = false

    @MainActor
    func perform() async throws -> some IntentResult & ProvidesDialog {
        let api = KagamiAPIService.shared
        let success = await api.tvControl("lower")
        guard success else {
            throw SiriIntentError.tvControlFailed
        }
        return .result(dialog: "TV is coming down.")
    }
}

struct RaiseTVIntent: AppIntent {
    static var title: LocalizedStringResource = "Raise TV"
    static var description = IntentDescription("Raises the TV to hidden position")
    static var openAppWhenRun = false

    @MainActor
    func perform() async throws -> some IntentResult & ProvidesDialog {
        let api = KagamiAPIService.shared
        let success = await api.tvControl("raise")
        guard success else {
            throw SiriIntentError.tvControlFailed
        }
        return .result(dialog: "TV is going up.")
    }
}

// MARK: - Status Intents

struct SafetyStatusIntent: AppIntent {
    static var title: LocalizedStringResource = "Safety Status"
    static var description = IntentDescription("Gets the current safety score and home status")
    static var openAppWhenRun = false

    @MainActor
    func perform() async throws -> some IntentResult & ProvidesDialog {
        let api = KagamiAPIService.shared

        do {
            let health = try await api.fetchHealth()
            let score = health.safetyScore ?? 0.85
            let percentage = Int(score * 100)

            if score >= 0.5 {
                return .result(dialog: "All systems nominal. Safety score: \(percentage) percent. All safe.")
            } else if score >= 0 {
                return .result(dialog: "Caution. Safety score: \(percentage) percent. Some constraints are near limits.")
            } else {
                return .result(dialog: "Safety warning detected! Score: \(percentage) percent. Please check Kagami app.")
            }
        } catch {
            return .result(dialog: "Unable to reach Kagami. Please check your connection.")
        }
    }
}

// MARK: - Lock Intents

struct LockAllDoorsIntent: AppIntent {
    static var title: LocalizedStringResource = "Lock All Doors"
    static var description = IntentDescription("Locks all smart locks")
    static var openAppWhenRun = false

    @MainActor
    func perform() async throws -> some IntentResult & ProvidesDialog {
        let api = KagamiAPIService.shared
        let success = await api.postRequest(endpoint: "/home/locks/lock-all")
        guard success else {
            throw SiriIntentError.lockControlFailed
        }
        return .result(dialog: "All doors are now locked.")
    }
}

// MARK: - Room Entities (for parameterized shortcuts)

struct KagamiRoom: AppEntity {
    let id: String
    let name: String

    static var typeDisplayRepresentation: TypeDisplayRepresentation {
        TypeDisplayRepresentation(name: "Room")
    }

    var displayRepresentation: DisplayRepresentation {
        DisplayRepresentation(title: "\(name)")
    }

    static var defaultQuery = RoomQuery()
}

struct RoomQuery: EntityQuery {
    func entities(for identifiers: [String]) async throws -> [KagamiRoom] {
        // Return rooms matching the identifiers
        return KagamiRoom.allRooms.filter { identifiers.contains($0.id) }
    }

    func suggestedEntities() async throws -> [KagamiRoom] {
        return KagamiRoom.allRooms
    }
}

extension KagamiRoom {
    static let allRooms: [KagamiRoom] = [
        KagamiRoom(id: "57", name: "Living Room"),
        KagamiRoom(id: "59", name: "Kitchen"),
        KagamiRoom(id: "58", name: "Dining"),
        KagamiRoom(id: "47", name: "Office"),
        KagamiRoom(id: "36", name: "Primary Bedroom"),
        KagamiRoom(id: "39", name: "Game Room"),
        KagamiRoom(id: "41", name: "Gym"),
    ]
}

/*
 * 鏡
 * Siri, meet Kagami.
 * "Hey Siri, movie mode with Kagami"
 */
