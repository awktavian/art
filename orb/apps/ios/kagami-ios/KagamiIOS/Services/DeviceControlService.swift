//
// DeviceControlService.swift — Device Control Service
//
// Colony: Nexus (e4) — Integration
//
// Features:
//   - Light control (level, rooms)
//   - TV mount control (raise, lower, presets)
//   - Fireplace control (on/off with safety)
//   - Shade control (open, close, position)
//   - Room data fetching
//
// Architecture:
//   DeviceControlService -> MeshCommandRouter (primary) -> Hub via Mesh
//                        -> KagamiAPIService (fallback) -> HTTP Backend
//
// Migration Note (Jan 2026):
//   Commands now route through MeshCommandRouter with Ed25519 signatures.
//   HTTP fallback is maintained for backward compatibility during migration.
//
// h(x) >= 0. Always.
//

import Foundation
import Combine

/// Service for controlling home devices
@MainActor
public final class DeviceControlService: ObservableObject {

    // MARK: - Singleton

    public static let shared = DeviceControlService()

    // MARK: - Published State

    @Published public private(set) var isControlling = false
    @Published public private(set) var lastError: DeviceControlError?
    @Published public private(set) var rooms: [RoomModel] = []
    @Published public private(set) var isFireplaceOn = false

    /// Whether mesh routing is active (vs HTTP fallback)
    @Published public private(set) var usingMeshRouting = false

    // MARK: - Dependencies

    /// Primary: Mesh command router with Ed25519 signatures
    private let meshRouter: MeshCommandRouter

    /// Fallback: Legacy HTTP API service (deprecated, used during migration)
    private let apiService: KagamiAPIService

    // MARK: - Init

    /// Initialize the service with default singleton
    public init() {
        self.meshRouter = MeshCommandRouter.shared
        self.apiService = KagamiAPIService.shared
    }

    /// Internal initializer for testing/custom configuration
    init(meshRouter: MeshCommandRouter = .shared, apiService: KagamiAPIService = .shared) {
        self.meshRouter = meshRouter
        self.apiService = apiService
    }

    /// Initialize mesh routing (call on app startup)
    public func initializeMesh() async {
        do {
            try await meshRouter.initialize()
            usingMeshRouting = true
            #if DEBUG
            print("[DeviceControl] Mesh routing initialized")
            #endif
        } catch {
            usingMeshRouting = false
            #if DEBUG
            print("[DeviceControl] Mesh routing unavailable, using HTTP fallback: \(error)")
            #endif
        }
    }

    // MARK: - Light Control

    /// Set light level for all rooms or specific rooms
    @discardableResult
    public func setLights(_ level: Int, rooms: [String]? = nil) async -> Bool {
        isControlling = true
        lastError = nil

        let clampedLevel = max(0, min(100, level))

        // Primary: Mesh routing with Ed25519 signature
        let success = await meshRouter.executeWithFallback(
            .setLights(level: clampedLevel, rooms: rooms)
        ) {
            // Fallback: Legacy HTTP (deprecated)
            let body: [String: Any] = [
                "level": clampedLevel,
                "rooms": rooms as Any
            ]
            return await self.apiService.postRequest(endpoint: "/home/lights/set", body: body)
        }

        if !success {
            lastError = .controlFailed("lights")
        }

        isControlling = false

        #if DEBUG
        let routeType = meshRouter.connectedHubs.isEmpty ? "HTTP" : "Mesh"
        print("[DeviceControl] Set lights to \(clampedLevel)% via \(routeType) - \(success ? "success" : "failed")")
        #endif

        return success
    }

    /// Turn all lights on (100%)
    @discardableResult
    public func lightsOn(rooms: [String]? = nil) async -> Bool {
        return await setLights(100, rooms: rooms)
    }

    /// Turn all lights off (0%)
    @discardableResult
    public func lightsOff(rooms: [String]? = nil) async -> Bool {
        return await setLights(0, rooms: rooms)
    }

    /// Dim lights to 30%
    @discardableResult
    public func dimLights(rooms: [String]? = nil) async -> Bool {
        return await setLights(30, rooms: rooms)
    }

    // MARK: - TV Control

    /// Control TV mount
    @discardableResult
    public func tvControl(_ action: TVAction) async -> Bool {
        isControlling = true
        lastError = nil

        // Primary: Mesh routing with Ed25519 signature
        let success = await meshRouter.executeWithFallback(
            .tvControl(action: action.rawValue, preset: nil)
        ) {
            // Fallback: Legacy HTTP (deprecated)
            return await self.apiService.postRequest(endpoint: "/home/tv/\(action.rawValue)")
        }

        if !success {
            lastError = .controlFailed("TV")
        }

        isControlling = false

        #if DEBUG
        let routeType = meshRouter.connectedHubs.isEmpty ? "HTTP" : "Mesh"
        print("[DeviceControl] TV \(action.rawValue) via \(routeType) - \(success ? "success" : "failed")")
        #endif

        return success
    }

    /// Lower TV to viewing position
    @discardableResult
    public func lowerTV(preset: Int? = nil) async -> Bool {
        isControlling = true
        lastError = nil

        // Primary: Mesh routing with Ed25519 signature
        let success = await meshRouter.executeWithFallback(
            .tvControl(action: "lower", preset: preset)
        ) {
            // Fallback: Legacy HTTP (deprecated)
            if let preset = preset {
                let body: [String: Any] = ["preset": preset]
                return await self.apiService.postRequest(endpoint: "/home/tv/lower", body: body)
            }
            return await self.apiService.postRequest(endpoint: "/home/tv/lower")
        }

        if !success {
            lastError = .controlFailed("TV")
        }

        isControlling = false
        return success
    }

    /// Raise TV to hidden position
    @discardableResult
    public func raiseTV() async -> Bool {
        return await tvControl(.raise)
    }

    /// TV mount actions
    public enum TVAction: String {
        case raise
        case lower
        case stop
    }

    // MARK: - Fireplace Control

    /// Toggle fireplace on/off
    @discardableResult
    public func setFireplace(on: Bool) async -> Bool {
        isControlling = true
        lastError = nil

        // Primary: Mesh routing with Ed25519 signature
        let success = await meshRouter.executeWithFallback(
            .fireplace(on: on)
        ) {
            // Fallback: Legacy HTTP (deprecated)
            let endpoint = on ? "/home/fireplace/on" : "/home/fireplace/off"
            return await self.apiService.postRequest(endpoint: endpoint)
        }

        if success {
            isFireplaceOn = on
        } else {
            lastError = .controlFailed("fireplace")
        }

        isControlling = false

        #if DEBUG
        let routeType = meshRouter.connectedHubs.isEmpty ? "HTTP" : "Mesh"
        print("[DeviceControl] Fireplace \(on ? "on" : "off") via \(routeType) - \(success ? "success" : "failed")")
        #endif

        return success
    }

    /// Turn fireplace on
    @discardableResult
    public func fireplaceOn() async -> Bool {
        return await setFireplace(on: true)
    }

    /// Turn fireplace off
    @discardableResult
    public func fireplaceOff() async -> Bool {
        return await setFireplace(on: false)
    }

    // MARK: - Shade Control

    /// Control shades with action and optional room filter
    @discardableResult
    public func controlShades(_ action: ShadeAction, rooms: [String]? = nil) async -> Bool {
        isControlling = true
        lastError = nil

        // Primary: Mesh routing with Ed25519 signature
        let success = await meshRouter.executeWithFallback(
            .shades(action: action.rawValue, rooms: rooms)
        ) {
            // Fallback: Legacy HTTP (deprecated)
            let body: [String: Any] = ["rooms": rooms as Any]
            return await self.apiService.postRequest(endpoint: "/home/shades/\(action.rawValue)", body: body)
        }

        if !success {
            lastError = .controlFailed("shades")
        }

        isControlling = false

        #if DEBUG
        let routeType = meshRouter.connectedHubs.isEmpty ? "HTTP" : "Mesh"
        print("[DeviceControl] Shades \(action.rawValue) via \(routeType) - \(success ? "success" : "failed")")
        #endif

        return success
    }

    /// Open shades
    @discardableResult
    public func openShades(rooms: [String]? = nil) async -> Bool {
        return await controlShades(.open, rooms: rooms)
    }

    /// Close shades
    @discardableResult
    public func closeShades(rooms: [String]? = nil) async -> Bool {
        return await controlShades(.close, rooms: rooms)
    }

    /// Shade actions
    public enum ShadeAction: String {
        case open
        case close
        case stop
    }

    // MARK: - Room Data

    /// Fetch all rooms from the API
    public func fetchRooms() async throws -> [RoomModel] {
        let fetchedRooms = try await apiService.fetchRooms()
        rooms = fetchedRooms
        return fetchedRooms
    }

    /// Get a specific room by ID
    public func room(by id: String) -> RoomModel? {
        return rooms.first { $0.id == id }
    }

    /// Get rooms on a specific floor
    public func rooms(on floor: String) -> [RoomModel] {
        return rooms.filter { $0.floor == floor }
    }

    // MARK: - Lock Control

    /// Lock all doors
    @discardableResult
    public func lockAll() async -> Bool {
        isControlling = true
        lastError = nil

        let success = await apiService.postRequest(endpoint: "/home/locks/lock-all")

        if !success {
            lastError = .controlFailed("locks")
        }

        isControlling = false
        return success
    }

    /// Unlock specific lock
    @discardableResult
    public func unlock(lockId: String) async -> Bool {
        let body: [String: Any] = ["lock_id": lockId]
        return await apiService.postRequest(endpoint: "/home/locks/unlock", body: body)
    }

    // MARK: - Climate Control

    /// Set room temperature
    @discardableResult
    public func setTemperature(_ temp: Double, room: String) async -> Bool {
        let body: [String: Any] = [
            "temperature": temp,
            "room": room
        ]
        return await apiService.postRequest(endpoint: "/home/climate/set", body: body)
    }
}

// MARK: - Device Control Error

public enum DeviceControlError: LocalizedError {
    case controlFailed(String)
    case deviceNotFound(String)
    case notConnected

    public var errorDescription: String? {
        switch self {
        case .controlFailed(let device):
            return "Failed to control \(device)"
        case .deviceNotFound(let device):
            return "Device not found: \(device)"
        case .notConnected:
            return "Not connected to server"
        }
    }
}

/*
 * Mirror
 * h(x) >= 0. Always.
 */
