//
// KagamiEcosystem.swift — Self-Reference and Cross-App Awareness
//
// Colony: Nexus (e4) — Integration
//
// The Kagami ecosystem is autopoietic — it knows about itself.
// Each app maintains awareness of the other apps in the ecosystem,
// their capabilities, and their current state.
//
// This enables:
// - Handoff between apps (iOS → Watch, iOS → Desktop)
// - Unified state across devices
// - Cross-app feature discovery
// - Ecosystem health monitoring
//
// η → s → μ → a → η′
// h(x) ≥ 0. Always.
//

import Foundation
import Combine

// MARK: - Ecosystem App Definition

/// Represents an app in the Kagami ecosystem
public struct KagamiApp: Identifiable, Codable, Equatable {
    public let id: String
    public let name: String
    public let platform: Platform
    public let version: String
    public let capabilities: [Capability]
    public let primaryColony: Colony

    public enum Platform: String, Codable, CaseIterable {
        case ios = "ios"
        case android = "android"
        case watchOS = "watchos"
        case visionOS = "visionos"
        case desktop = "desktop"
        case hub = "hub"
        case pico = "pico"
        case web = "web"

        public var displayName: String {
            switch self {
            case .ios: return "iPhone"
            case .android: return "Android"
            case .watchOS: return "Apple Watch"
            case .visionOS: return "Vision Pro"
            case .desktop: return "Desktop"
            case .hub: return "Hub"
            case .pico: return "Pico"
            case .web: return "Web"
            }
        }

        public var icon: String {
            switch self {
            case .ios: return "iphone"
            case .android: return "candybarphone"
            case .watchOS: return "applewatch"
            case .visionOS: return "visionpro"
            case .desktop: return "desktopcomputer"
            case .hub: return "homepod.fill"
            case .pico: return "cpu"
            case .web: return "globe"
            }
        }
    }

    public enum Capability: String, Codable, CaseIterable {
        case voice = "voice"
        case smartHome = "smart_home"
        case healthKit = "healthkit"
        case spatial = "spatial"
        case notifications = "notifications"
        case widgets = "widgets"
        case complications = "complications"
        case realtime = "realtime"
        case offline = "offline"
        case ledRing = "led_ring"
        case handTracking = "hand_tracking"
        case eyeTracking = "eye_tracking"

        public var displayName: String {
            switch self {
            case .voice: return "Voice Control"
            case .smartHome: return "Smart Home"
            case .healthKit: return "HealthKit"
            case .spatial: return "Spatial Computing"
            case .notifications: return "Notifications"
            case .widgets: return "Widgets"
            case .complications: return "Complications"
            case .realtime: return "Real-time Sync"
            case .offline: return "Offline Mode"
            case .ledRing: return "LED Ring"
            case .handTracking: return "Hand Tracking"
            case .eyeTracking: return "Eye Tracking"
            }
        }
    }

    public enum Colony: String, Codable, CaseIterable {
        case spark = "spark"
        case forge = "forge"
        case flow = "flow"
        case nexus = "nexus"
        case beacon = "beacon"
        case grove = "grove"
        case crystal = "crystal"
    }
}

// MARK: - Ecosystem Registry

/// The complete Kagami ecosystem — self-describing
public struct KagamiEcosystemRegistry {

    /// All apps in the Kagami ecosystem
    public static let apps: [KagamiApp] = [
        KagamiApp(
            id: "kagami-ios",
            name: "Kagami iOS",
            platform: .ios,
            version: "2.0.0",
            capabilities: [.smartHome, .voice, .notifications, .widgets, .realtime, .healthKit],
            primaryColony: .nexus
        ),
        KagamiApp(
            id: "kagami-android",
            name: "Kagami Android",
            platform: .android,
            version: "2.0.0",
            capabilities: [.smartHome, .voice, .notifications, .widgets, .realtime],
            primaryColony: .nexus
        ),
        KagamiApp(
            id: "kagami-watch",
            name: "Kagami Watch",
            platform: .watchOS,
            version: "2.0.0",
            capabilities: [.smartHome, .healthKit, .complications, .offline, .realtime],
            primaryColony: .crystal
        ),
        KagamiApp(
            id: "kagami-vision",
            name: "Kagami Vision",
            platform: .visionOS,
            version: "2.0.0",
            capabilities: [.smartHome, .spatial, .handTracking, .eyeTracking, .realtime],
            primaryColony: .beacon
        ),
        KagamiApp(
            id: "kagami-desktop",
            name: "Kagami Desktop",
            platform: .desktop,
            version: "2.0.0",
            capabilities: [.smartHome, .voice, .notifications, .realtime],
            primaryColony: .forge
        ),
        KagamiApp(
            id: "kagami-hub",
            name: "Kagami Hub",
            platform: .hub,
            version: "2.0.0",
            capabilities: [.voice, .smartHome, .ledRing, .realtime],
            primaryColony: .flow
        ),
        KagamiApp(
            id: "kagami-pico",
            name: "Kagami Pico",
            platform: .pico,
            version: "1.0.0",
            capabilities: [.ledRing, .realtime],
            primaryColony: .crystal
        ),
    ]

    /// Find an app by ID
    public static func app(id: String) -> KagamiApp? {
        apps.first { $0.id == id }
    }

    /// Find apps by platform
    public static func apps(for platform: KagamiApp.Platform) -> [KagamiApp] {
        apps.filter { $0.platform == platform }
    }

    /// Find apps with a specific capability
    public static func apps(with capability: KagamiApp.Capability) -> [KagamiApp] {
        apps.filter { $0.capabilities.contains(capability) }
    }

    /// Find apps by colony
    public static func apps(for colony: KagamiApp.Colony) -> [KagamiApp] {
        apps.filter { $0.primaryColony == colony }
    }

    /// Current app (self-reference)
    public static var currentApp: KagamiApp {
        #if os(iOS)
        return app(id: "kagami-ios")!
        #elseif os(watchOS)
        return app(id: "kagami-watch")!
        #elseif os(visionOS)
        return app(id: "kagami-vision")!
        #else
        return app(id: "kagami-ios")! // Fallback
        #endif
    }

    /// Apps that can hand off to the current app
    public static var handoffSources: [KagamiApp] {
        // Apps on Apple platforms can hand off to each other
        apps.filter { app in
            [.ios, .watchOS, .visionOS, .desktop].contains(app.platform) &&
            app.id != currentApp.id
        }
    }

    /// Apps that the current app can hand off to
    public static var handoffTargets: [KagamiApp] {
        handoffSources
    }
}

// MARK: - Ecosystem State

/// Live state of apps in the ecosystem
@MainActor
public final class KagamiEcosystemState: ObservableObject {

    // MARK: - Singleton

    public static let shared = KagamiEcosystemState()

    // MARK: - Published State

    @Published public private(set) var connectedApps: [String: AppState] = [:]
    @Published public private(set) var lastUpdate: Date?

    public struct AppState: Codable {
        public let appId: String
        public let isConnected: Bool
        public let lastSeen: Date
        public let safetyScore: Double?
        public let activeColony: String?
    }

    // MARK: - Init

    private init() {
        // Mark self as connected
        updateState(for: KagamiEcosystemRegistry.currentApp.id, isConnected: true)
    }

    // MARK: - State Updates

    public func updateState(for appId: String, isConnected: Bool, safetyScore: Double? = nil, activeColony: String? = nil) {
        connectedApps[appId] = AppState(
            appId: appId,
            isConnected: isConnected,
            lastSeen: Date(),
            safetyScore: safetyScore,
            activeColony: activeColony
        )
        lastUpdate = Date()
    }

    /// Process ecosystem state from WebSocket
    public func processEcosystemUpdate(_ data: [String: Any]) {
        guard let apps = data["connected_apps"] as? [[String: Any]] else { return }

        for appData in apps {
            guard let appId = appData["app_id"] as? String else { continue }
            updateState(
                for: appId,
                isConnected: appData["is_connected"] as? Bool ?? false,
                safetyScore: appData["safety_score"] as? Double,
                activeColony: appData["active_colony"] as? String
            )
        }
    }

    /// Get state for a specific app
    public func state(for appId: String) -> AppState? {
        connectedApps[appId]
    }

    /// Check if another app is currently connected
    public func isAppConnected(_ appId: String) -> Bool {
        connectedApps[appId]?.isConnected ?? false
    }

    /// Get all currently connected apps
    public var currentlyConnectedApps: [KagamiApp] {
        KagamiEcosystemRegistry.apps.filter { app in
            connectedApps[app.id]?.isConnected ?? false
        }
    }
}

// MARK: - Self-Description

extension KagamiEcosystemRegistry {

    /// Generate a self-description of the ecosystem (autopoietic reflection)
    public static func describe() -> String {
        """
        🐝 Kagami Ecosystem — \(apps.count) Apps

        Apps:
        \(apps.map { "  • \($0.name) (\($0.platform.displayName)) — \($0.primaryColony.rawValue.capitalized)" }.joined(separator: "\n"))

        Capabilities across ecosystem:
        \(KagamiApp.Capability.allCases.map { cap in
            let count = apps(with: cap).count
            return "  • \(cap.displayName): \(count) apps"
        }.joined(separator: "\n"))

        Colony distribution:
        \(KagamiApp.Colony.allCases.map { colony in
            let count = apps(for: colony).count
            return "  • \(colony.rawValue.capitalized): \(count) apps"
        }.joined(separator: "\n"))

        Current app: \(currentApp.name)
        Platform: \(currentApp.platform.displayName)
        Primary colony: \(currentApp.primaryColony.rawValue.capitalized)

        鏡 — The mirror knows itself.
        h(x) ≥ 0. Always.
        """
    }
}

/*
 * 鏡
 *
 * Autopoiesis: The system describes itself.
 * The ecosystem knows its own structure.
 * Each app knows about every other app.
 *
 * This is not just metadata — it's self-reference.
 * The mirror reflecting the mirror.
 *
 * η → s → μ → a → η′
 * h(x) ≥ 0. Always.
 */
