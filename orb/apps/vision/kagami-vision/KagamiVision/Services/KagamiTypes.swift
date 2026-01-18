//
// KagamiTypes.swift — Shared Data Models for Vision Pro
//
// Colony: Nexus (e₄) — Integration
//
// These types match the API schemas from /home/* endpoints.
//

import SwiftUI

// MARK: - Room Model (from GET /home/rooms)

struct Light: Codable, Identifiable {
    let id: Int
    let name: String
    let level: Int  // 0-100

    var isOn: Bool { level > 0 }
}

struct Shade: Codable, Identifiable {
    let id: Int
    let name: String
    let position: Int  // 0=closed, 100=open
}

struct AudioZone: Codable, Identifiable {
    let id: Int
    let name: String
    let isActive: Bool
    let source: String?
    let volume: Int  // 0-100

    enum CodingKeys: String, CodingKey {
        case id, name, source, volume
        case isActive = "is_active"
    }
}

struct HVACState: Codable {
    let currentTemp: Double
    let targetTemp: Double
    let mode: String  // heat, cool, auto, off

    enum CodingKeys: String, CodingKey {
        case currentTemp = "current_temp"
        case targetTemp = "target_temp"
        case mode
    }
}

struct RoomModel: Codable, Identifiable {
    let id: String
    let name: String
    let floor: String
    let lights: [Light]
    let shades: [Shade]
    let audioZone: AudioZone?
    let hvac: HVACState?
    let occupied: Bool

    enum CodingKeys: String, CodingKey {
        case id, name, floor, lights, shades, occupied
        case audioZone = "audio_zone"
        case hvac
    }

    var avgLightLevel: Int {
        guard !lights.isEmpty else { return 0 }
        return lights.reduce(0) { $0 + $1.level } / lights.count
    }

    var lightState: String {
        let avg = avgLightLevel
        if avg == 0 { return "Off" }
        if avg < 50 { return "Dim" }
        return "On"
    }
}

struct RoomsResponse: Codable {
    let rooms: [RoomModel]
    let count: Int
}

// MARK: - Scene Model (from GET /home/scenes)

struct SceneModel: Codable, Identifiable {
    let id: String
    let name: String
    let description: String?
    let icon: String?
    let category: String?
    let isActive: Bool
    let lastActivated: Date?
    let actions: [SceneAction]?

    enum CodingKeys: String, CodingKey {
        case id, name, description, icon, category, actions
        case isActive = "is_active"
        case lastActivated = "last_activated"
    }

    /// SF Symbol icon name, with fallback
    var iconName: String {
        icon ?? SceneIcon.lights
    }
}

struct SceneAction: Codable {
    let type: String          // "light", "shade", "audio", "hvac"
    let deviceId: Int?
    let room: String?
    let action: String        // "set", "on", "off", "open", "close"
    let value: Int?           // Level/position value

    enum CodingKeys: String, CodingKey {
        case type, room, action, value
        case deviceId = "device_id"
    }
}

struct ScenesResponse: Codable {
    let scenes: [SceneModel]
    let count: Int
}

// MARK: - Colony Colors
// Note: Colony colors and init(hex:) are defined in DesignSystem.swift via KagamiDesign
// Do not duplicate here to avoid ambiguous use errors

// MARK: - Scene Icons (SF Symbols for Accessibility)

enum SceneIcon {
    static let movieMode = "tv.fill"
    static let goodnight = "moon.fill"
    static let welcomeHome = "house.fill"
    static let away = "lock.fill"
    static let fireplace = "flame.fill"
    static let lights = "lightbulb.fill"
    static let shades = "blinds.horizontal.closed"
    static let tv = "tv.fill"

    /// Returns true indicating these are all SF Symbol names
    static var usesSystemImages: Bool { true }
}

// MARK: - Privacy Settings

/// Privacy settings for tracking data upload consent.
/// Users can opt-out of gaze/hand tracking data upload while still using tracking locally.
class PrivacySettings: ObservableObject {
    static let shared = PrivacySettings()

    private let handTrackingKey = "kagami.privacy.allowHandTrackingUpload"
    private let gazeTrackingKey = "kagami.privacy.allowGazeTrackingUpload"
    private let analyticsKey = "kagami.privacy.allowAnalytics"

    /// Whether hand tracking data can be uploaded to the server
    @Published var allowHandTrackingUpload: Bool {
        didSet {
            UserDefaults.standard.set(allowHandTrackingUpload, forKey: handTrackingKey)
        }
    }

    /// Whether gaze tracking data can be uploaded to the server
    @Published var allowGazeTrackingUpload: Bool {
        didSet {
            UserDefaults.standard.set(allowGazeTrackingUpload, forKey: gazeTrackingKey)
        }
    }

    /// Whether anonymous analytics can be collected
    @Published var allowAnalytics: Bool {
        didSet {
            UserDefaults.standard.set(allowAnalytics, forKey: analyticsKey)
        }
    }

    /// Whether the user has explicitly provided consent (completed onboarding)
    @Published var hasProvidedConsent: Bool {
        didSet {
            UserDefaults.standard.set(hasProvidedConsent, forKey: "kagami.privacy.hasProvidedConsent")
        }
    }

    private init() {
        // Default to false (opt-in model for privacy)
        self.allowHandTrackingUpload = UserDefaults.standard.object(forKey: handTrackingKey) as? Bool ?? false
        self.allowGazeTrackingUpload = UserDefaults.standard.object(forKey: gazeTrackingKey) as? Bool ?? false
        self.allowAnalytics = UserDefaults.standard.object(forKey: analyticsKey) as? Bool ?? true
        self.hasProvidedConsent = UserDefaults.standard.bool(forKey: "kagami.privacy.hasProvidedConsent")
    }

    /// Resets all privacy settings to defaults
    func resetToDefaults() {
        allowHandTrackingUpload = false
        allowGazeTrackingUpload = false
        allowAnalytics = true
        hasProvidedConsent = false
    }
}

// MARK: - Accessibility Settings
// Note: AccessibilitySettings is defined in DesignSystem.swift
// Do not duplicate here to avoid redeclaration errors

/*
 * Kagami Vision Data Types
 * h(x) >= 0. Always.
 */
