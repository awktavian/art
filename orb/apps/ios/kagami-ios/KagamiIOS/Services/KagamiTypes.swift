//
// KagamiTypes.swift — Shared Data Models
//
// Colony: Nexus (e₄) — Integration
//
// These types match the API schemas from /home/* endpoints.
// Used across iOS, VisionOS, and WatchOS clients.
//

import SwiftUI

// MARK: - Room Model (from GET /home/rooms)

public struct Light: Codable, Identifiable {
    public let id: Int
    public let name: String
    public let level: Int  // 0-100

    public var isOn: Bool { level > 0 }

    public init(id: Int, name: String, level: Int) {
        self.id = id
        self.name = name
        self.level = level
    }
}

public struct Shade: Codable, Identifiable {
    public let id: Int
    public let name: String
    public let position: Int  // 0=closed, 100=open

    public init(id: Int, name: String, position: Int) {
        self.id = id
        self.name = name
        self.position = position
    }
}

public struct AudioZone: Codable, Identifiable {
    public let id: Int
    public let name: String
    public let isActive: Bool
    public let source: String?
    public let volume: Int  // 0-100

    enum CodingKeys: String, CodingKey {
        case id, name, source, volume
        case isActive = "is_active"
    }
}

public struct HVACState: Codable {
    public let currentTemp: Double
    public let targetTemp: Double
    public let mode: String  // heat, cool, auto, off

    enum CodingKeys: String, CodingKey {
        case currentTemp = "current_temp"
        case targetTemp = "target_temp"
        case mode
    }
}

public struct RoomModel: Codable, Identifiable {
    public let id: String
    public let name: String
    public let floor: String
    public let lights: [Light]
    public let shades: [Shade]
    public let audioZone: AudioZone?
    public let hvac: HVACState?
    public let occupied: Bool

    enum CodingKeys: String, CodingKey {
        case id, name, floor, lights, shades, occupied
        case audioZone = "audio_zone"
        case hvac
    }

    public var avgLightLevel: Int {
        guard !lights.isEmpty else { return 0 }
        return lights.reduce(0) { $0 + $1.level } / lights.count
    }

    public var lightState: String {
        let avg = avgLightLevel
        if avg == 0 { return "Off" }
        if avg < 50 { return "Dim" }
        return "On"
    }

    /// Convenience initializer for demo mode
    public init(id: String, name: String, floor: String, lightLevel: Int = 0, hasLights: Bool = true, hasShades: Bool = false) {
        self.id = id
        self.name = name
        self.floor = floor
        self.lights = hasLights ? [Light(id: Int(id) ?? 0, name: "\(name) Lights", level: lightLevel)] : []
        self.shades = hasShades ? [Shade(id: Int(id) ?? 0 + 100, name: "\(name) Shades", position: 0)] : []
        self.audioZone = nil
        self.hvac = nil
        self.occupied = lightLevel > 0
    }
}

// MARK: - Home Status (from GET /home/status)

struct HomeStatusModel: Codable {
    let initialized: Bool
    let integrations: [String: Bool]
    let rooms: Int
    let occupiedRooms: Int
    var movieMode: Bool
    let avgTemp: Double?

    enum CodingKeys: String, CodingKey {
        case initialized, integrations, rooms
        case occupiedRooms = "occupied_rooms"
        case movieMode = "movie_mode"
        case avgTemp = "avg_temp"
    }
}

// MARK: - Device States (from GET /home/devices)

struct FireplaceState: Codable {
    let isOn: Bool
    let onSince: Double?
    let remainingMinutes: Int?

    enum CodingKeys: String, CodingKey {
        case isOn = "is_on"
        case onSince = "on_since"
        case remainingMinutes = "remaining_minutes"
    }
}

struct TVMountState: Codable {
    let position: String  // up, down, moving
    let preset: Int?
}

struct LockState: Codable, Identifiable {
    var id: String { name }
    let name: String
    let isLocked: Bool
    let doorState: String

    enum CodingKeys: String, CodingKey {
        case name
        case isLocked = "is_locked"
        case doorState = "door_state"
    }
}

struct DevicesResponse: Codable {
    let lights: [Light]
    let shades: [Shade]
    let audioZones: [AudioZone]
    let locks: [LockState]
    let fireplace: FireplaceState
    let tvMount: TVMountState

    enum CodingKeys: String, CodingKey {
        case lights, shades, locks, fireplace
        case audioZones = "audio_zones"
        case tvMount = "tv_mount"
    }
}

struct RoomsResponse: Codable {
    let rooms: [RoomModel]
    let count: Int
}

// MARK: - Colony Colors
// NOTE: All Color tokens are defined in DesignTokens.generated.swift.
// Import SwiftUI to access Color.spark, Color.void, Color.safetyColor(for:), etc.

// MARK: - Scene Icons (SF Symbols)

enum SceneIcon {
    static let movieMode = "film.fill"
    static let goodnight = "moon.fill"
    static let welcomeHome = "house.fill"
    static let away = "lock.fill"
    static let fireplace = "flame.fill"
    static let lights = "lightbulb.fill"
    static let shades = "blinds.vertical.open"
    static let tv = "tv.fill"
}

/*
 * 鏡
 * h(x) ≥ 0. Always.
 */
