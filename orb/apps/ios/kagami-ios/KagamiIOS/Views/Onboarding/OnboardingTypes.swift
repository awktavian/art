//
// OnboardingTypes.swift — Onboarding Data Types
//
// Colony: Beacon (e5) — Planning
//
// Defines types used throughout the onboarding flow:
//   - OnboardingStep enum
//   - SmartHomeIntegration enum
//   - OnboardingServer struct
//   - OnboardingRoom struct
//   - PermissionState struct
//
// h(x) >= 0. Always.
//

import SwiftUI
import KagamiDesign

// MARK: - Onboarding Step Enum

enum OnboardingStep: Int, CaseIterable, Identifiable {
    case welcome = 0
    case server = 1
    case integration = 2
    case rooms = 3
    case permissions = 4
    case completion = 5

    var id: Int { rawValue }

    var title: String {
        switch self {
        case .welcome: return "Welcome"
        case .server: return "Server"
        case .integration: return "Smart Home"
        case .rooms: return "Rooms"
        case .permissions: return "Permissions"
        case .completion: return "Ready"
        }
    }

    var icon: String {
        switch self {
        case .welcome: return "sparkles"
        case .server: return "antenna.radiowaves.left.and.right"
        case .integration: return "house.fill"
        case .rooms: return "square.grid.2x2"
        case .permissions: return "checkmark.shield"
        case .completion: return "party.popper"
        }
    }

    var isSkippable: Bool {
        switch self {
        case .welcome, .server, .completion: return false
        case .integration, .rooms, .permissions: return true
        }
    }

    var colonyColor: Color {
        switch self {
        case .welcome: return .crystal
        case .server: return .nexus
        case .integration: return .forge
        case .rooms: return .grove
        case .permissions: return .beacon
        case .completion: return .spark
        }
    }
}

// MARK: - Integration Type

enum SmartHomeIntegration: String, CaseIterable, Identifiable {
    case control4 = "control4"
    case lutron = "lutron"
    case homekit = "homekit"
    case smartthings = "smartthings"
    case homeAssistant = "home_assistant"
    case hubitat = "hubitat"
    case googleHome = "google_home"
    case alexa = "alexa"

    var id: String { rawValue }

    var displayName: String {
        switch self {
        case .control4: return "Control4"
        case .lutron: return "Lutron"
        case .homekit: return "HomeKit"
        case .smartthings: return "SmartThings"
        case .homeAssistant: return "Home Assistant"
        case .hubitat: return "Hubitat"
        case .googleHome: return "Google Home"
        case .alexa: return "Amazon Alexa"
        }
    }

    var icon: String {
        switch self {
        case .control4: return "4.square.fill"
        case .lutron: return "lightswitch.on"
        case .homekit: return "homekit"
        case .smartthings: return "app.connected.to.app.below.fill"
        case .homeAssistant: return "house.and.flag"
        case .hubitat: return "globe"
        case .googleHome: return "g.circle.fill"
        case .alexa: return "a.circle.fill"
        }
    }

    var description: String {
        switch self {
        case .control4: return "Professional automation"
        case .lutron: return "Smart lighting & shades"
        case .homekit: return "Apple ecosystem"
        case .smartthings: return "Samsung smart home"
        case .homeAssistant: return "Open source automation"
        case .hubitat: return "Local processing"
        case .googleHome: return "Google ecosystem"
        case .alexa: return "Amazon ecosystem"
        }
    }

    var requiresCredentials: Bool {
        switch self {
        case .control4, .lutron, .smartthings, .homeAssistant, .hubitat:
            return true
        case .homekit, .googleHome, .alexa:
            return false // OAuth flow
        }
    }

    var colonyColor: Color {
        switch self {
        case .control4: return .beacon
        case .lutron: return .forge
        case .homekit: return .crystal
        case .smartthings: return .spark
        case .homeAssistant: return .grove
        case .hubitat: return .flow
        case .googleHome: return .nexus
        case .alexa: return .beacon
        }
    }
}

// MARK: - Discovered Server

struct OnboardingServer: Identifiable, Equatable {
    let id = UUID()
    let name: String
    let url: String
    let host: String
    let port: Int
    let isSecure: Bool

    static func == (lhs: OnboardingServer, rhs: OnboardingServer) -> Bool {
        lhs.url == rhs.url
    }
}

// MARK: - Discovered Room

struct OnboardingRoom: Identifiable {
    let id: String
    let name: String
    let floor: String?
    var isEnabled: Bool
    var hasLights: Bool
    var hasShades: Bool
    var hasClimate: Bool
    var hasAudio: Bool
}

// MARK: - Permission State

struct PermissionState: Identifiable {
    let id: String
    let name: String
    let description: String
    let icon: String
    var status: PermissionStatus
    let isRequired: Bool

    enum PermissionStatus {
        case notDetermined
        case authorized
        case denied
        case restricted

        var color: Color {
            switch self {
            case .authorized: return .safetyOk
            case .denied, .restricted: return .safetyViolation
            case .notDetermined: return .accessibleTextTertiary
            }
        }

        var icon: String {
            switch self {
            case .authorized: return "checkmark.circle.fill"
            case .denied, .restricted: return "xmark.circle.fill"
            case .notDetermined: return "circle"
            }
        }
    }
}

/*
 * Mirror
 * h(x) >= 0. Always.
 */
