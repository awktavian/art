//
// SpatialBreadcrumbView.swift — Advanced Spatial Navigation
//
// Colony: Beacon (e5) — Planning
//
// P1 FIX: Spatial breadcrumb indicator for navigation context
// P2 FIX: 3D minimap overlay, voice-guided navigation, haptic waypoints
//
// Features:
//   - World-locked billboard showing current location path
//   - Always visible in spatial views
//   - Adapts to user head position
//   - Accessibility-friendly with VoiceOver support
//   - 3D minimap overlay (P2)
//   - Voice-guided navigation (P2)
//   - Haptic waypoints (P2)
//   - Spatial audio cues (P2)
//
// Design:
//   "Rooms > Kitchen" style persistent indicator
//   Floats at edge of field of view
//   Non-intrusive but always accessible
//   Minimap shows home layout with current position
//
// Created: January 2, 2026
// 鏡

import SwiftUI
import RealityKit
import AVFoundation

// MARK: - Spatial Breadcrumb View

/// P1 FIX: Persistent world-locked breadcrumb indicator
/// Shows current navigation path like "Rooms > Kitchen"
struct SpatialBreadcrumbView: View {
    @EnvironmentObject var spatialServices: SpatialServicesContainer
    @Environment(\.accessibilityReduceMotion) private var reduceMotion

    /// Current navigation path (e.g., ["Rooms", "Kitchen"])
    let path: [String]

    /// Optional current room for contextual display
    var currentRoom: String? { path.last }

    /// Optional callback when breadcrumb is tapped
    var onTap: ((Int) -> Void)?

    @State private var isHovered = false

    var body: some View {
        HStack(spacing: 6) {
            // Home icon
            Image(systemName: "house.fill")
                .font(.system(size: 12))
                .foregroundColor(.crystal.opacity(0.8))
                .accessibilityHidden(true)

            // Path segments
            ForEach(Array(path.enumerated()), id: \.offset) { index, segment in
                if index > 0 {
                    // Separator
                    Image(systemName: "chevron.right")
                        .font(.system(size: 10, weight: .medium))
                        .foregroundColor(.secondary.opacity(0.6))
                        .accessibilityHidden(true)
                }

                // Segment button
                Button(action: {
                    onTap?(index)
                }) {
                    Text(segment)
                        .font(.system(size: 13, weight: index == path.count - 1 ? .semibold : .regular))
                        .foregroundColor(index == path.count - 1 ? .white : .secondary)
                }
                .buttonStyle(.plain)
                .accessibilityLabel("\(segment), level \(index + 1) of \(path.count)")
                .accessibilityHint(index < path.count - 1 ?
                    String(localized: "breadcrumb.hint.navigate", defaultValue: "Double tap to navigate to this level") :
                    String(localized: "breadcrumb.hint.current", defaultValue: "Current location"))
            }

            Spacer(minLength: 0)
        }
        .padding(.horizontal, 12)
        .padding(.vertical, 8)
        .background(
            RoundedRectangle(cornerRadius: 8)
                .fill(.ultraThinMaterial)
                .opacity(isHovered ? 0.9 : 0.7)
        )
        .overlay(
            RoundedRectangle(cornerRadius: 8)
                .stroke(Color.crystal.opacity(isHovered ? 0.4 : 0.2), lineWidth: 1)
        )
        .scaleEffect(reduceMotion ? 1.0 : (isHovered ? 1.02 : 1.0))
        .animation(.easeInOut(duration: 0.233), value: isHovered)  // 233ms Fibonacci fast
        .onHover { hovering in
            isHovered = hovering
        }
        .accessibilityElement(children: .contain)
        .accessibilityLabel(String(localized: "breadcrumb.accessibility.label", defaultValue: "Navigation path"))
        .accessibilityValue(path.joined(separator: ", "))
    }
}

// MARK: - World-Locked Breadcrumb Entity

/// RealityKit entity for world-locked breadcrumb display
/// Billboards to always face the user
struct SpatialBreadcrumbEntity: View {
    let path: [String]

    @EnvironmentObject var spatialServices: SpatialServicesContainer
    @State private var billboardRotation: simd_quatf = simd_quatf(angle: 0, axis: [0, 1, 0])

    var body: some View {
        RealityView { content in
            // Create breadcrumb container entity
            let container = Entity()
            container.name = "spatial-breadcrumb"

            // Position at top-left of user's field of view
            // Offset from head position in social zone distance
            container.position = SIMD3<Float>(-0.4, 0.3, -1.2)

            // Add to content
            content.add(container)

        } update: { content in
            guard let breadcrumb = content.entities.first(where: { $0.name == "spatial-breadcrumb" }) else { return }

            // Update billboard rotation to face user
            if let headForward = spatialServices.anchorService.headForward {
                // Calculate rotation to face user
                let yaw = atan2(headForward.x, -headForward.z)
                breadcrumb.orientation = simd_quatf(angle: yaw, axis: SIMD3<Float>(0, 1, 0))
            }

            // Update position relative to head
            if let headPos = spatialServices.anchorService.headPosition {
                // Keep breadcrumb in consistent position relative to user's view
                let offsetX: Float = -0.35  // Left of center
                let offsetY: Float = 0.15   // Above eye level
                let offsetZ: Float = -0.8   // Personal zone distance

                breadcrumb.position = headPos + SIMD3<Float>(offsetX, offsetY, offsetZ)
            }
        }
        .overlay(alignment: .topLeading) {
            // SwiftUI overlay for the actual breadcrumb content
            SpatialBreadcrumbView(path: path)
                .frame(maxWidth: 250)
                .offset(x: 20, y: 20)
        }
    }
}

// MARK: - Breadcrumb Overlay Modifier

/// View modifier to add spatial breadcrumb to any view
struct SpatialBreadcrumbModifier: ViewModifier {
    let path: [String]
    let isVisible: Bool

    func body(content: Content) -> some View {
        content
            .overlay(alignment: .topLeading) {
                if isVisible && !path.isEmpty {
                    SpatialBreadcrumbView(path: path)
                        .padding(.top, 16)
                        .padding(.leading, 16)
                        .transition(.asymmetric(
                            insertion: .move(edge: .top).combined(with: .opacity),
                            removal: .opacity
                        ))
                }
            }
    }
}

extension View {
    /// Adds a spatial breadcrumb indicator to the view
    /// - Parameters:
    ///   - path: Navigation path segments (e.g., ["Rooms", "Kitchen"])
    ///   - isVisible: Whether the breadcrumb should be visible
    func spatialBreadcrumb(path: [String], isVisible: Bool = true) -> some View {
        modifier(SpatialBreadcrumbModifier(path: path, isVisible: isVisible))
    }
}

// MARK: - Breadcrumb Navigation State

/// Observable state for managing breadcrumb navigation
@MainActor
class BreadcrumbNavigationState: ObservableObject {
    @Published var currentPath: [String] = []
    @Published var isNavigating = false

    /// Pushes a new segment onto the navigation path
    func push(_ segment: String) {
        withAnimation {
            currentPath.append(segment)
        }
    }

    /// Pops back to a specific index in the path
    func popTo(index: Int) {
        guard index >= 0 && index < currentPath.count else { return }
        withAnimation {
            currentPath = Array(currentPath.prefix(index + 1))
        }
    }

    /// Pops the last segment from the path
    func pop() {
        guard !currentPath.isEmpty else { return }
        withAnimation {
            currentPath.removeLast()
        }
    }

    /// Resets the path to root
    func reset() {
        withAnimation {
            currentPath = []
        }
    }

    /// Sets the entire path at once
    func setPath(_ path: [String]) {
        withAnimation {
            currentPath = path
        }
    }

    /// Formatted path string for display
    var formattedPath: String {
        currentPath.joined(separator: " > ")
    }

    /// Accessibility description of current location
    var accessibilityDescription: String {
        if currentPath.isEmpty {
            return String(localized: "breadcrumb.accessibility.home", defaultValue: "Home")
        }
        return String(localized: "breadcrumb.accessibility.location", defaultValue: "Currently at \(currentPath.last ?? "Home"), \(currentPath.count) levels deep")
    }
}

// MARK: - Preview

#Preview {
    VStack(spacing: 20) {
        SpatialBreadcrumbView(path: ["Rooms", "Kitchen"])

        SpatialBreadcrumbView(path: ["Rooms", "Living Room", "Lights"])

        SpatialBreadcrumbView(path: ["Settings"])
    }
    .padding()
    .background(Color.black)
}

// MARK: - P2: 3D Minimap View

/// 3D minimap showing home layout with current position
struct SpatialMinimapView: View {
    @EnvironmentObject var spatialServices: SpatialServicesContainer
    @EnvironmentObject var navigationState: BreadcrumbNavigationState

    @State private var isExpanded = false
    @State private var selectedRoom: String?

    /// Room layout data
    let rooms: [MinimapRoom]

    /// Current user position in the home
    var userPosition: SIMD3<Float>?

    var body: some View {
        ZStack {
            // Minimap container
            if isExpanded {
                expandedMinimap
            } else {
                collapsedMinimap
            }
        }
        .animation(.spring(response: 0.377, dampingFraction: 0.8), value: isExpanded)  // 377ms Fibonacci normal
    }

    // MARK: - Collapsed Minimap

    private var collapsedMinimap: some View {
        Button(action: { isExpanded = true }) {
            ZStack {
                // Background
                Circle()
                    .fill(.ultraThinMaterial)
                    .frame(width: 60, height: 60)

                // Mini floor plan
                MinimapFloorPlanView(rooms: rooms, userPosition: userPosition, isCompact: true)
                    .frame(width: 50, height: 50)
                    .clipShape(Circle())

                // User position dot
                if userPosition != nil {
                    Circle()
                        .fill(Color.crystal)
                        .frame(width: 8, height: 8)
                        .shadow(color: .crystal.opacity(0.5), radius: 4)
                }
            }
        }
        .buttonStyle(.plain)
        .hoverEffect(.lift)
        .accessibilityLabel(String(localized: "minimap.collapsed.label"))
        .accessibilityHint(String(localized: "minimap.collapsed.hint"))
    }

    // MARK: - Expanded Minimap

    private var expandedMinimap: some View {
        VStack(spacing: 12) {
            // Header
            HStack {
                Text(String(localized: "minimap.title"))
                    .font(.headline)
                    .foregroundColor(.white)

                Spacer()

                Button(action: { isExpanded = false }) {
                    Image(systemName: "xmark.circle.fill")
                        .foregroundColor(.secondary)
                }
                .buttonStyle(.plain)
            }

            // Floor plan
            MinimapFloorPlanView(rooms: rooms, userPosition: userPosition, isCompact: false)
                .frame(width: 280, height: 200)
                .overlay(
                    // Room labels
                    ForEach(rooms) { room in
                        Text(room.name)
                            .font(.system(size: 10))
                            .foregroundColor(.white.opacity(0.8))
                            .position(x: CGFloat(room.labelPosition.x * 280),
                                    y: CGFloat(room.labelPosition.y * 200))
                    }
                )

            // Room list
            ScrollView(.horizontal, showsIndicators: false) {
                HStack(spacing: 8) {
                    ForEach(rooms) { room in
                        MinimapRoomButton(
                            room: room,
                            isSelected: selectedRoom == room.id,
                            isCurrent: navigationState.currentPath.last == room.name
                        ) {
                            selectedRoom = room.id
                            navigateToRoom(room)
                        }
                    }
                }
            }

            // Navigation hint
            if let selected = selectedRoom, let room = rooms.first(where: { $0.id == selected }) {
                Text(String(localized: "minimap.navigate.hint \(room.name)"))
                    .font(.caption)
                    .foregroundColor(.secondary)
            }
        }
        .padding(16)
        .frame(width: 320)
        .background(.ultraThinMaterial, in: RoundedRectangle(cornerRadius: 16))
        .overlay(
            RoundedRectangle(cornerRadius: 16)
                .stroke(Color.crystal.opacity(0.3), lineWidth: 1)
        )
    }

    private func navigateToRoom(_ room: MinimapRoom) {
        navigationState.setPath(["Rooms", room.name])
        // Trigger voice navigation
        VoiceNavigator.shared.announceNavigation(to: room.name)
    }
}

// MARK: - Minimap Room Model

struct MinimapRoom: Identifiable {
    let id: String
    let name: String
    let bounds: CGRect  // Normalized 0-1 coordinates
    let labelPosition: CGPoint  // Normalized 0-1 coordinates
    let floor: Int
    let color: Color
    let deviceCount: Int

    init(
        id: String,
        name: String,
        bounds: CGRect,
        floor: Int = 0,
        color: Color = .crystal,
        deviceCount: Int = 0
    ) {
        self.id = id
        self.name = name
        self.bounds = bounds
        self.labelPosition = CGPoint(x: bounds.midX, y: bounds.midY)
        self.floor = floor
        self.color = color
        self.deviceCount = deviceCount
    }
}

// MARK: - Minimap Floor Plan View

struct MinimapFloorPlanView: View {
    let rooms: [MinimapRoom]
    let userPosition: SIMD3<Float>?
    let isCompact: Bool

    var body: some View {
        GeometryReader { geometry in
            ZStack {
                // Room shapes
                ForEach(rooms) { room in
                    RoundedRectangle(cornerRadius: isCompact ? 2 : 4)
                        .fill(room.color.opacity(0.3))
                        .overlay(
                            RoundedRectangle(cornerRadius: isCompact ? 2 : 4)
                                .stroke(room.color.opacity(0.6), lineWidth: 1)
                        )
                        .frame(
                            width: room.bounds.width * geometry.size.width,
                            height: room.bounds.height * geometry.size.height
                        )
                        .position(
                            x: room.bounds.midX * geometry.size.width,
                            y: room.bounds.midY * geometry.size.height
                        )
                }

                // User position
                if let pos = userPosition {
                    // Convert world position to normalized minimap position
                    let normalizedX = CGFloat((pos.x + 10) / 20)  // Assuming -10 to 10 meter range
                    let normalizedY = CGFloat((pos.z + 10) / 20)

                    ZStack {
                        // Glow
                        Circle()
                            .fill(Color.crystal.opacity(0.3))
                            .frame(width: isCompact ? 8 : 16, height: isCompact ? 8 : 16)

                        // Dot
                        Circle()
                            .fill(Color.crystal)
                            .frame(width: isCompact ? 4 : 8, height: isCompact ? 4 : 8)

                        // Direction indicator (if not compact)
                        if !isCompact {
                            Triangle()
                                .fill(Color.crystal)
                                .frame(width: 6, height: 8)
                                .offset(y: -10)
                        }
                    }
                    .position(
                        x: normalizedX * geometry.size.width,
                        y: normalizedY * geometry.size.height
                    )
                }
            }
        }
    }
}

// MARK: - Triangle Shape

struct Triangle: Shape {
    func path(in rect: CGRect) -> Path {
        var path = Path()
        path.move(to: CGPoint(x: rect.midX, y: rect.minY))
        path.addLine(to: CGPoint(x: rect.maxX, y: rect.maxY))
        path.addLine(to: CGPoint(x: rect.minX, y: rect.maxY))
        path.closeSubpath()
        return path
    }
}

// MARK: - Minimap Room Button

struct MinimapRoomButton: View {
    let room: MinimapRoom
    let isSelected: Bool
    let isCurrent: Bool
    let action: () -> Void

    var body: some View {
        Button(action: action) {
            HStack(spacing: 4) {
                Circle()
                    .fill(room.color)
                    .frame(width: 8, height: 8)

                Text(room.name)
                    .font(.caption2)
                    .foregroundColor(isSelected ? .white : .secondary)

                if room.deviceCount > 0 {
                    Text("\(room.deviceCount)")
                        .font(.system(size: 9))
                        .foregroundColor(.secondary)
                        .padding(.horizontal, 4)
                        .background(Color.secondary.opacity(0.2), in: Capsule())
                }

                if isCurrent {
                    Image(systemName: "location.fill")
                        .font(.system(size: 8))
                        .foregroundColor(.crystal)
                }
            }
            .padding(.horizontal, 8)
            .padding(.vertical, 6)
            .background(
                isSelected ? room.color.opacity(0.3) : Color.clear,
                in: Capsule()
            )
            .overlay(
                Capsule()
                    .stroke(isSelected ? room.color : Color.clear, lineWidth: 1)
            )
        }
        .buttonStyle(.plain)
        .accessibilityLabel("\(room.name), \(room.deviceCount) devices")
        .accessibilityHint(isCurrent ? "Current location" : "Navigate to \(room.name)")
    }
}

// MARK: - P2: Voice Navigator

/// Voice-guided navigation for spatial environments
@MainActor
class VoiceNavigator: ObservableObject {
    static let shared = VoiceNavigator()

    @Published var isEnabled = true
    @Published var isSpeaking = false
    @Published var lastAnnouncement: String?

    private let synthesizer = AVSpeechSynthesizer()

    private init() {}

    /// Announces navigation to a destination
    func announceNavigation(to destination: String) {
        guard isEnabled else { return }

        let text = String(localized: "voice.navigate.to \(destination)")
        speak(text)
    }

    /// Announces arrival at a destination
    func announceArrival(at destination: String) {
        guard isEnabled else { return }

        let text = String(localized: "voice.arrived.at \(destination)")
        speak(text)
    }

    /// Announces a waypoint
    func announceWaypoint(_ waypoint: NavigationWaypoint) {
        guard isEnabled else { return }

        let directionText = waypoint.direction.localizedDescription
        let distanceText = String(format: "%.1f meters", waypoint.distance)
        let text = String(localized: "voice.waypoint \(waypoint.name) \(directionText) \(distanceText)")
        speak(text)
    }

    /// Announces turn-by-turn direction
    func announceDirection(_ direction: NavigationDirection, distance: Float) {
        guard isEnabled else { return }

        let directionText = direction.localizedDescription
        let distanceText = String(format: "%.1f meters", distance)
        let text = String(localized: "voice.direction \(directionText) \(distanceText)")
        speak(text)
    }

    /// Speaks text using speech synthesis
    private func speak(_ text: String) {
        // Cancel any ongoing speech
        if synthesizer.isSpeaking {
            synthesizer.stopSpeaking(at: .immediate)
        }

        let utterance = AVSpeechUtterance(string: text)
        utterance.voice = AVSpeechSynthesisVoice(language: Locale.current.language.languageCode?.identifier ?? "en")
        utterance.rate = AVSpeechUtteranceDefaultSpeechRate
        utterance.pitchMultiplier = 1.0
        utterance.volume = 0.8

        isSpeaking = true
        lastAnnouncement = text
        synthesizer.speak(utterance)

        // Reset speaking state after estimated duration
        Task {
            try? await Task.sleep(nanoseconds: UInt64(Double(text.count) * 0.05 * 1_000_000_000))
            isSpeaking = false
        }
    }
}

// MARK: - Navigation Direction

enum NavigationDirection {
    case forward
    case backward
    case left
    case right
    case up
    case down
    case turnLeft
    case turnRight
    case uTurn
    case arrived

    var localizedDescription: String {
        switch self {
        case .forward: return String(localized: "direction.forward")
        case .backward: return String(localized: "direction.backward")
        case .left: return String(localized: "direction.left")
        case .right: return String(localized: "direction.right")
        case .up: return String(localized: "direction.up")
        case .down: return String(localized: "direction.down")
        case .turnLeft: return String(localized: "direction.turn.left")
        case .turnRight: return String(localized: "direction.turn.right")
        case .uTurn: return String(localized: "direction.uturn")
        case .arrived: return String(localized: "direction.arrived")
        }
    }

    var systemImage: String {
        switch self {
        case .forward: return "arrow.up"
        case .backward: return "arrow.down"
        case .left: return "arrow.left"
        case .right: return "arrow.right"
        case .up: return "arrow.up.circle"
        case .down: return "arrow.down.circle"
        case .turnLeft: return "arrow.turn.up.left"
        case .turnRight: return "arrow.turn.up.right"
        case .uTurn: return "arrow.uturn.backward"
        case .arrived: return "checkmark.circle.fill"
        }
    }
}

// MARK: - Navigation Waypoint

struct NavigationWaypoint: Identifiable {
    let id: UUID
    let name: String
    let position: SIMD3<Float>
    let direction: NavigationDirection
    let distance: Float
    let isDestination: Bool

    init(
        name: String,
        position: SIMD3<Float>,
        direction: NavigationDirection,
        distance: Float,
        isDestination: Bool = false
    ) {
        self.id = UUID()
        self.name = name
        self.position = position
        self.direction = direction
        self.distance = distance
        self.isDestination = isDestination
    }
}

// MARK: - P2: Haptic Waypoint Manager

/// Manages haptic feedback for navigation waypoints
@MainActor
class HapticWaypointManager: ObservableObject {
    static let shared = HapticWaypointManager()

    @Published var isEnabled = true
    @Published var activeWaypoints: [NavigationWaypoint] = []

    /// Proximity threshold for haptic feedback (meters)
    private let proximityThreshold: Float = 2.0

    /// Last triggered waypoint to prevent repeated triggers
    private var lastTriggeredWaypointId: UUID?

    private init() {}

    /// Sets active waypoints for navigation
    func setWaypoints(_ waypoints: [NavigationWaypoint]) {
        activeWaypoints = waypoints
        lastTriggeredWaypointId = nil
    }

    /// Clears all waypoints
    func clearWaypoints() {
        activeWaypoints.removeAll()
        lastTriggeredWaypointId = nil
    }

    /// Updates user position and triggers haptics if near waypoint
    func updatePosition(_ position: SIMD3<Float>) {
        guard isEnabled else { return }

        for waypoint in activeWaypoints {
            let distance = simd_length(position - waypoint.position)

            // Check if within proximity and not already triggered
            if distance < proximityThreshold && lastTriggeredWaypointId != waypoint.id {
                triggerHaptic(for: waypoint, distance: distance)
                lastTriggeredWaypointId = waypoint.id
            }
        }
    }

    /// Triggers haptic feedback for a waypoint
    private func triggerHaptic(for waypoint: NavigationWaypoint, distance: Float) {
        // Haptic intensity based on distance (closer = stronger)
        let intensity = 1.0 - (distance / proximityThreshold)

        if waypoint.isDestination {
            // Strong haptic for destination
            playDestinationHaptic()
        } else {
            // Directional haptic for waypoints
            playDirectionalHaptic(direction: waypoint.direction, intensity: Float(intensity))
        }

        // Voice announcement
        VoiceNavigator.shared.announceWaypoint(waypoint)
    }

    private func playDestinationHaptic() {
        // On visionOS, haptics would be triggered through the device
        // This is a placeholder for the actual implementation
        print("Haptic: Destination reached")
    }

    private func playDirectionalHaptic(direction: NavigationDirection, intensity: Float) {
        // Directional haptic pattern
        print("Haptic: \(direction) at intensity \(intensity)")
    }
}

// MARK: - P2: Spatial Audio Navigation Cues

/// Spatial audio cues for navigation
@MainActor
class SpatialNavigationAudio: ObservableObject {
    static let shared = SpatialNavigationAudio()

    @Published var isEnabled = true

    private weak var audioService: SpatialAudioService?

    private init() {}

    /// Sets the audio service for spatial audio
    func setAudioService(_ service: SpatialAudioService) {
        self.audioService = service
    }

    /// Plays a navigation cue at a position
    func playNavigationCue(at position: SIMD3<Float>, type: NavigationCueType) {
        guard isEnabled, let audio = audioService else { return }

        switch type {
        case .waypoint:
            audio.play(.notification, at: position)

        case .turnPoint:
            audio.play(.select, at: position)

        case .destination:
            audio.playSequence([.success, .notification], at: position)

        case .obstacle:
            audio.play(.error, at: position)

        case .boundary:
            audio.play(.tap, at: position)
        }
    }

    /// Plays directional audio guide
    func playDirectionalGuide(direction: NavigationDirection, distance: Float) {
        guard isEnabled, let audio = audioService else { return }

        // Calculate position based on direction
        let position: SIMD3<Float>
        switch direction {
        case .forward:
            position = SIMD3<Float>(0, 0, -distance)
        case .backward:
            position = SIMD3<Float>(0, 0, distance)
        case .left:
            position = SIMD3<Float>(-distance, 0, 0)
        case .right:
            position = SIMD3<Float>(distance, 0, 0)
        case .up:
            position = SIMD3<Float>(0, distance, 0)
        case .down:
            position = SIMD3<Float>(0, -distance, 0)
        default:
            position = SIMD3<Float>(0, 0, -1)
        }

        audio.play(.tap, at: position)
    }

    enum NavigationCueType {
        case waypoint
        case turnPoint
        case destination
        case obstacle
        case boundary
    }
}

// MARK: - Enhanced Breadcrumb with Navigation Features

/// Extended breadcrumb view with minimap toggle and voice navigation
struct EnhancedSpatialBreadcrumbView: View {
    @EnvironmentObject var spatialServices: SpatialServicesContainer
    @StateObject private var voiceNavigator = VoiceNavigator.shared
    @StateObject private var hapticManager = HapticWaypointManager.shared

    let path: [String]
    let rooms: [MinimapRoom]
    var userPosition: SIMD3<Float>?
    var onTap: ((Int) -> Void)?

    @State private var showMinimap = false

    var body: some View {
        HStack(spacing: 12) {
            // Standard breadcrumb
            SpatialBreadcrumbView(path: path, onTap: onTap)

            // Minimap toggle
            Button(action: { showMinimap.toggle() }) {
                Image(systemName: showMinimap ? "map.fill" : "map")
                    .font(.system(size: 14))
                    .foregroundColor(.crystal)
            }
            .buttonStyle(.plain)
            .accessibilityLabel(String(localized: "minimap.toggle"))

            // Voice navigation toggle
            Button(action: { voiceNavigator.isEnabled.toggle() }) {
                Image(systemName: voiceNavigator.isEnabled ? "speaker.wave.2.fill" : "speaker.slash")
                    .font(.system(size: 14))
                    .foregroundColor(voiceNavigator.isEnabled ? .crystal : .secondary)
            }
            .buttonStyle(.plain)
            .accessibilityLabel(String(localized: "voice.navigation.toggle"))
        }
        .sheet(isPresented: $showMinimap) {
            SpatialMinimapView(rooms: rooms, userPosition: userPosition)
                .presentationDetents([.medium])
        }
    }
}

/*
 * 鏡
 * h(x) >= 0. Always.
 *
 * Know where you are.
 * Know where you came from.
 * The path illuminates the destination.
 *
 * Voice guides the way.
 * Haptics confirm arrival.
 * Sound anchors space.
 */
