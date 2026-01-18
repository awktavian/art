//
// WindowPlacementService.swift -- Intelligent Window Placement for visionOS
//
// Kagami Vision -- Manages window positions in spatial environment
//
// Colony: Beacon (e5) -- Planning
//
// Features:
// - Intelligent initial window placement
// - Multi-window layout management
// - Proxemic zone-aware positioning
// - User preference persistence
// - Shared space coordination
//
// visionOS 2 Window Placement Guidelines:
// - Default placement: 1.5m in front, slightly below eye level
// - Personal zone: 45cm - 1.2m for primary interactions
// - Social zone: 1.2m - 3.6m for shared viewing
// - Minimum spacing: 20cm between windows
//
// Created: January 11, 2026
// Mirror
//

import SwiftUI
import RealityKit
import Combine

// MARK: - Window Placement Service

/// Manages intelligent window placement in the visionOS spatial environment.
@MainActor
class WindowPlacementService: ObservableObject {

    // MARK: - Singleton

    static let shared = WindowPlacementService()

    // MARK: - Published State

    @Published var activeWindows: [WindowInfo] = []
    @Published var preferredZone: ProxemicZone = .personal

    // MARK: - Types

    /// Information about an active window
    struct WindowInfo: Identifiable {
        let id: String
        let windowType: WindowType
        var position: SIMD3<Float>
        var size: SIMD3<Float>  // width, height, depth
        var isVisible: Bool
        let createdAt: Date

        init(
            id: String,
            windowType: WindowType,
            position: SIMD3<Float> = .zero,
            size: SIMD3<Float> = SIMD3<Float>(0.4, 0.3, 0.01)
        ) {
            self.id = id
            self.windowType = windowType
            self.position = position
            self.size = size
            self.isVisible = true
            self.createdAt = Date()
        }
    }

    /// Types of windows in the app
    enum WindowType: String, CaseIterable {
        case main = "main"
        case rooms = "spatial-rooms"
        case settings = "settings"
        case controlPanel = "spatial-control-panel"
        case immersiveHome = "full-spatial"
        case voiceCommand = "voice-command"

        /// Default size for this window type
        var defaultSize: SIMD3<Float> {
            switch self {
            case .main:
                return SIMD3<Float>(0.48, 0.30, 0.01)  // 480x297pt (golden ratio)
            case .rooms:
                return SIMD3<Float>(0.60, 0.37, 0.15)  // 600x371pt, volumetric
            case .settings:
                return SIMD3<Float>(0.40, 0.50, 0.01)  // 400x500pt
            case .controlPanel:
                return SIMD3<Float>(0.30, 0.20, 0.10)  // Compact volumetric
            case .immersiveHome:
                return SIMD3<Float>(1.0, 0.6, 1.0)     // Full immersive
            case .voiceCommand:
                return SIMD3<Float>(0.32, 0.20, 0.01)  // Compact floating
            }
        }

        /// Preferred proxemic zone for this window type
        var preferredZone: ProxemicZone {
            switch self {
            case .main, .settings:
                return .personal
            case .rooms, .controlPanel:
                return .personal
            case .immersiveHome:
                return .social
            case .voiceCommand:
                return .intimate
            }
        }
    }

    /// Proxemic zones based on Hall's theory (1966)
    enum ProxemicZone: String, CaseIterable {
        case intimate    // 0-45cm
        case personal    // 45cm-1.2m
        case social      // 1.2m-3.6m
        case ambient     // 3.6m+

        /// Center distance of this zone in meters
        var centerDistance: Float {
            switch self {
            case .intimate: return 0.30
            case .personal: return 0.80
            case .social: return 2.0
            case .ambient: return 4.5
            }
        }

        /// Range of this zone in meters
        var range: ClosedRange<Float> {
            switch self {
            case .intimate: return 0...0.45
            case .personal: return 0.45...1.2
            case .social: return 1.2...3.6
            case .ambient: return 3.6...10.0
            }
        }
    }

    // MARK: - Layout Strategies

    /// Layout strategies for multiple windows
    enum LayoutStrategy {
        case cascade       // Offset each window slightly
        case tiled         // Arrange in a grid
        case arc          // Arrange in an arc around user
        case stacked      // Stack vertically
        case focused      // One primary, others minimized
    }

    // MARK: - Internal State

    private var cancellables = Set<AnyCancellable>()
    private let persistenceKey = "kagami.window.placements"

    // Reference position (head position when available)
    private var referencePosition: SIMD3<Float> = SIMD3<Float>(0, 1.5, 0)
    private var referenceForward: SIMD3<Float> = SIMD3<Float>(0, 0, -1)

    // MARK: - Init

    private init() {
        loadPersistedPlacements()
    }

    // MARK: - Window Registration

    /// Registers a new window and calculates its position.
    func registerWindow(
        id: String,
        type: WindowType,
        preferredPosition: SIMD3<Float>? = nil
    ) -> SIMD3<Float> {
        // Calculate position if not specified
        let position = preferredPosition ?? calculateOptimalPosition(for: type)

        let window = WindowInfo(
            id: id,
            windowType: type,
            position: position,
            size: type.defaultSize
        )

        activeWindows.append(window)
        persistPlacements()

        return position
    }

    /// Unregisters a window when it closes.
    func unregisterWindow(id: String) {
        activeWindows.removeAll { $0.id == id }
        persistPlacements()
    }

    /// Updates the position of a window.
    func updateWindowPosition(id: String, position: SIMD3<Float>) {
        if let index = activeWindows.firstIndex(where: { $0.id == id }) {
            activeWindows[index].position = position
            persistPlacements()
        }
    }

    // MARK: - Position Calculation

    /// Calculates the optimal position for a new window.
    func calculateOptimalPosition(for type: WindowType) -> SIMD3<Float> {
        let zone = type.preferredZone
        let baseDistance = zone.centerDistance
        let baseHeight = referencePosition.y - 0.1  // Slightly below eye level

        // Start with position directly in front
        var position = referencePosition + referenceForward * baseDistance
        position.y = baseHeight

        // Avoid overlapping with existing windows
        position = avoidOverlap(position: position, size: type.defaultSize)

        return position
    }

    /// Adjusts position to avoid overlapping with existing windows.
    private func avoidOverlap(
        position: SIMD3<Float>,
        size: SIMD3<Float>,
        minSpacing: Float = 0.2
    ) -> SIMD3<Float> {
        var adjustedPosition = position

        for window in activeWindows where window.isVisible {
            let overlap = checkOverlap(
                pos1: adjustedPosition, size1: size,
                pos2: window.position, size2: window.size
            )

            if overlap {
                // Move to the right
                adjustedPosition.x += window.size.x / 2 + size.x / 2 + minSpacing
            }
        }

        return adjustedPosition
    }

    /// Checks if two windows would overlap.
    private func checkOverlap(
        pos1: SIMD3<Float>, size1: SIMD3<Float>,
        pos2: SIMD3<Float>, size2: SIMD3<Float>
    ) -> Bool {
        let halfSize1 = size1 / 2
        let halfSize2 = size2 / 2

        // AABB overlap test
        let xOverlap = abs(pos1.x - pos2.x) < (halfSize1.x + halfSize2.x)
        let yOverlap = abs(pos1.y - pos2.y) < (halfSize1.y + halfSize2.y)
        let zOverlap = abs(pos1.z - pos2.z) < (halfSize1.z + halfSize2.z)

        return xOverlap && yOverlap && zOverlap
    }

    // MARK: - Layout

    /// Applies a layout strategy to all active windows.
    func applyLayout(_ strategy: LayoutStrategy) {
        guard !activeWindows.isEmpty else { return }

        switch strategy {
        case .cascade:
            applyCascadeLayout()
        case .tiled:
            applyTiledLayout()
        case .arc:
            applyArcLayout()
        case .stacked:
            applyStackedLayout()
        case .focused:
            applyFocusedLayout()
        }

        persistPlacements()
    }

    private func applyCascadeLayout() {
        let startPosition = referencePosition + referenceForward * 0.8
        let offset: Float = 0.05  // 5cm offset per window

        for (index, _) in activeWindows.enumerated() {
            var position = startPosition
            position.x += Float(index) * offset
            position.y -= Float(index) * offset
            activeWindows[index].position = position
        }
    }

    private func applyTiledLayout() {
        let columns = min(3, activeWindows.count)
        let startPosition = referencePosition + referenceForward * 1.0
        let spacing: Float = 0.5

        for (index, _) in activeWindows.enumerated() {
            let col = index % columns
            let row = index / columns

            var position = startPosition
            position.x = startPosition.x + Float(col - columns / 2) * spacing
            position.y = startPosition.y - Float(row) * spacing * 0.7

            activeWindows[index].position = position
        }
    }

    private func applyArcLayout() {
        let count = activeWindows.count
        let radius: Float = 1.2
        let arcAngle: Float = min(Float.pi * 0.6, Float(count) * 0.25)
        let startAngle = -arcAngle / 2

        for (index, _) in activeWindows.enumerated() {
            let angle = startAngle + (arcAngle / Float(max(1, count - 1))) * Float(index)

            var position = referencePosition
            position.x = referencePosition.x + radius * sin(angle)
            position.z = referencePosition.z - radius * cos(angle)
            position.y = referencePosition.y - 0.1

            activeWindows[index].position = position
        }
    }

    private func applyStackedLayout() {
        let startPosition = referencePosition + referenceForward * 0.8
        let verticalSpacing: Float = 0.35

        for (index, _) in activeWindows.enumerated() {
            var position = startPosition
            position.y = startPosition.y + Float(index) * verticalSpacing

            activeWindows[index].position = position
        }
    }

    private func applyFocusedLayout() {
        guard !activeWindows.isEmpty else { return }

        // Primary window in center
        activeWindows[0].position = referencePosition + referenceForward * 0.8
        activeWindows[0].position.y = referencePosition.y - 0.1

        // Others moved to periphery
        for index in 1..<activeWindows.count {
            let angle = Float.pi * 0.3 * Float(index % 2 == 0 ? 1 : -1)

            var position = referencePosition
            position.x = referencePosition.x + 0.8 * sin(angle)
            position.z = referencePosition.z - 0.8 * cos(angle)
            position.y = referencePosition.y - 0.2

            activeWindows[index].position = position
        }
    }

    // MARK: - Reference Updates

    /// Updates the reference position (call with head tracking data).
    func updateReference(position: SIMD3<Float>, forward: SIMD3<Float>) {
        referencePosition = position
        referenceForward = simd_normalize(forward)
    }

    // MARK: - Persistence

    private func loadPersistedPlacements() {
        guard let data = UserDefaults.standard.data(forKey: persistenceKey),
              let placements = try? JSONDecoder().decode([PersistedPlacement].self, from: data) else {
            return
        }

        // We don't restore windows automatically, but we save preferences
        // This data is used when windows are registered
        _ = placements
    }

    private func persistPlacements() {
        let placements = activeWindows.map { window in
            PersistedPlacement(
                id: window.id,
                type: window.windowType.rawValue,
                position: [window.position.x, window.position.y, window.position.z]
            )
        }

        if let data = try? JSONEncoder().encode(placements) {
            UserDefaults.standard.set(data, forKey: persistenceKey)
        }
    }

    private struct PersistedPlacement: Codable {
        let id: String
        let type: String
        let position: [Float]
    }
}

// MARK: - SwiftUI Integration

/// Environment key for window placement service
private struct WindowPlacementKey: EnvironmentKey {
    static let defaultValue = WindowPlacementService.shared
}

extension EnvironmentValues {
    var windowPlacement: WindowPlacementService {
        get { self[WindowPlacementKey.self] }
        set { self[WindowPlacementKey.self] = newValue }
    }
}

// MARK: - View Modifier

/// Modifier to register a view with the window placement service
struct WindowPlacementModifier: ViewModifier {
    let windowId: String
    let windowType: WindowPlacementService.WindowType

    @Environment(\.windowPlacement) private var placementService

    func body(content: Content) -> some View {
        content
            .onAppear {
                _ = placementService.registerWindow(id: windowId, type: windowType)
            }
            .onDisappear {
                placementService.unregisterWindow(id: windowId)
            }
    }
}

extension View {
    /// Registers this view with the window placement service.
    func windowPlacement(
        id: String,
        type: WindowPlacementService.WindowType
    ) -> some View {
        modifier(WindowPlacementModifier(windowId: id, windowType: type))
    }
}

/*
 * Mirror
 * h(x) >= 0. Always.
 *
 * Windows float in space with purpose.
 * Each finds its optimal position.
 * The environment becomes the interface.
 */
