//
// SceneService.swift — Scene Execution Service
//
// Colony: Nexus (e4) — Integration
//
// Features:
//   - Execute home scenes (movie mode, goodnight, welcome home, etc.)
//   - Scene status tracking
//   - Scene history
//
// Architecture:
//   SceneService -> MeshCommandRouter (primary) -> Hub via Mesh
//               -> KagamiAPIService (fallback) -> HTTP Backend
//
// Migration Note (Jan 2026):
//   Commands now route through MeshCommandRouter with Ed25519 signatures.
//   HTTP fallback is maintained for backward compatibility during migration.
//
// h(x) >= 0. Always.
//

import Foundation
import Combine

/// Service for executing home automation scenes
@MainActor
public final class SceneService: ObservableObject {

    // MARK: - Singleton

    public static let shared = SceneService()

    // MARK: - Published State

    @Published public private(set) var isExecuting = false
    @Published public private(set) var lastExecutedScene: String?
    @Published public private(set) var lastExecutionTime: Date?
    @Published public private(set) var lastError: SceneError?

    /// Whether mesh routing is active (vs HTTP fallback)
    @Published public private(set) var usingMeshRouting = false

    // MARK: - Dependencies

    /// Primary: Mesh command router with Ed25519 signatures
    private let meshRouter: MeshCommandRouter

    /// Fallback: Legacy HTTP API service (deprecated, used during migration)
    private let apiService: KagamiAPIService

    // MARK: - Scene Definitions

    /// Available scene types
    public enum SceneType: String, CaseIterable {
        case movieMode = "movie_mode"
        case goodnight = "goodnight"
        case welcomeHome = "welcome_home"
        case away = "away"
        case focus = "focus"
        case relax = "relax"
        case goodMorning = "good_morning"

        public var displayName: String {
            switch self {
            case .movieMode: return "Movie Mode"
            case .goodnight: return "Goodnight"
            case .welcomeHome: return "Welcome Home"
            case .away: return "Away"
            case .focus: return "Focus"
            case .relax: return "Relax"
            case .goodMorning: return "Good Morning"
            }
        }

        public var description: String {
            switch self {
            case .movieMode: return "Dim lights, lower TV, close shades"
            case .goodnight: return "All lights off, lock doors"
            case .welcomeHome: return "Warm lights, open shades"
            case .away: return "Secure house, reduce energy"
            case .focus: return "Bright lights, open shades"
            case .relax: return "Dim lights, fireplace on"
            case .goodMorning: return "Open shades, raise lights gradually"
            }
        }

        public var icon: String {
            switch self {
            case .movieMode: return "film.fill"
            case .goodnight: return "moon.fill"
            case .welcomeHome: return "house.fill"
            case .away: return "lock.fill"
            case .focus: return "target"
            case .relax: return "flame.fill"
            case .goodMorning: return "sun.max.fill"
            }
        }

        /// API endpoint for this scene
        var endpoint: String {
            switch self {
            case .movieMode: return "/home/movie-mode/enter"
            case .goodnight: return "/home/goodnight"
            case .welcomeHome: return "/home/welcome-home"
            case .away: return "/home/away"
            case .focus: return "/home/focus"
            case .relax: return "/home/relax"
            case .goodMorning: return "/home/good-morning"
            }
        }
    }

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
            print("[SceneService] Mesh routing initialized")
            #endif
        } catch {
            usingMeshRouting = false
            #if DEBUG
            print("[SceneService] Mesh routing unavailable, using HTTP fallback: \(error)")
            #endif
        }
    }

    // MARK: - Scene Execution

    /// Execute a scene by type
    @discardableResult
    public func execute(_ sceneType: SceneType) async -> Bool {
        return await execute(sceneType.rawValue)
    }

    /// Execute a scene by string identifier
    @discardableResult
    public func execute(_ sceneId: String) async -> Bool {
        guard !isExecuting else {
            lastError = .alreadyExecuting
            return false
        }

        isExecuting = true
        lastError = nil

        let endpoint = sceneEndpoint(for: sceneId)

        guard let endpoint = endpoint else {
            isExecuting = false
            lastError = .unknownScene(sceneId)
            return false
        }

        // Primary: Mesh routing with Ed25519 signature
        let success = await meshRouter.executeWithFallback(
            .executeScene(sceneId: sceneId)
        ) {
            // Fallback: Legacy HTTP (deprecated)
            return await self.apiService.postRequest(endpoint: endpoint)
        }

        if success {
            lastExecutedScene = sceneId
            lastExecutionTime = Date()

            #if DEBUG
            let routeType = meshRouter.connectedHubs.isEmpty ? "HTTP" : "Mesh"
            print("[SceneService] Executed scene '\(sceneId)' via \(routeType)")
            #endif
        } else {
            lastError = .executionFailed(sceneId)

            #if DEBUG
            print("[SceneService] Failed to execute scene: \(sceneId)")
            #endif
        }

        isExecuting = false
        return success
    }

    /// Exit movie mode specifically (has its own endpoint)
    @discardableResult
    public func exitMovieMode() async -> Bool {
        isExecuting = true
        lastError = nil

        // Primary: Mesh routing with Ed25519 signature
        let success = await meshRouter.executeWithFallback(
            .exitMovieMode
        ) {
            // Fallback: Legacy HTTP (deprecated)
            return await self.apiService.postRequest(endpoint: "/home/movie-mode/exit")
        }

        if success {
            lastExecutedScene = "exit_movie_mode"
            lastExecutionTime = Date()
        } else {
            lastError = .executionFailed("exit_movie_mode")
        }

        isExecuting = false
        return success
    }

    // MARK: - Helpers

    private func sceneEndpoint(for sceneId: String) -> String? {
        // Try to match against known scene types
        if let sceneType = SceneType(rawValue: sceneId) {
            return sceneType.endpoint
        }

        // Fallback mappings for legacy or alternative scene names
        switch sceneId {
        case "movie", "theater":
            return SceneType.movieMode.endpoint
        case "sleep", "night":
            return SceneType.goodnight.endpoint
        case "home", "welcome":
            return SceneType.welcomeHome.endpoint
        case "leave", "lock":
            return SceneType.away.endpoint
        case "work":
            return SceneType.focus.endpoint
        case "chill":
            return SceneType.relax.endpoint
        case "morning", "wake":
            return SceneType.goodMorning.endpoint
        default:
            return nil
        }
    }

    /// Get scene type from string identifier
    public func sceneType(for id: String) -> SceneType? {
        return SceneType(rawValue: id)
    }

    /// Get context-aware suggested scene based on time of day
    public var suggestedScene: SceneType {
        let hour = Calendar.current.component(.hour, from: Date())

        switch hour {
        case 6...9:
            return .goodMorning
        case 10...17:
            return .focus
        case 18...21:
            return .movieMode
        default:
            return .goodnight
        }
    }
}

// MARK: - Scene Error

public enum SceneError: LocalizedError {
    case unknownScene(String)
    case executionFailed(String)
    case alreadyExecuting
    case notConnected

    public var errorDescription: String? {
        switch self {
        case .unknownScene(let scene):
            return "Unknown scene: \(scene)"
        case .executionFailed(let scene):
            return "Failed to execute scene: \(scene)"
        case .alreadyExecuting:
            return "A scene is already being executed"
        case .notConnected:
            return "Not connected to server"
        }
    }
}

/*
 * Mirror
 * h(x) >= 0. Always.
 */
