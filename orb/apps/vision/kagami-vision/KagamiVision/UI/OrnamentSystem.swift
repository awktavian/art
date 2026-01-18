//
// OrnamentSystem.swift -- Ornament-Based UI Patterns for visionOS
//
// Kagami Vision -- Spatial UI ornaments for Apple Vision Pro
//
// Colony: Crystal (e7) -- Verification
//
// Per KAGAMI_REDESIGN_PLAN.md: Add ornament-based UI patterns
//
// Features:
// - Window ornaments for contextual controls
// - Adaptive ornament positioning
// - Room control ornaments
// - Quick action ornaments
// - Status indicator ornaments
// - Animated ornament transitions
// - VoiceOver accessible ornaments
//
// h(x) >= 0. Always.
//

import SwiftUI
import RealityKit

// MARK: - Ornament Position

/// Standard ornament positions per visionOS HIG
enum OrnamentPosition {
    case leading
    case trailing
    case top
    case bottom
    case topLeading
    case topTrailing
    case bottomLeading
    case bottomTrailing

    /// SwiftUI ornament anchor
    var anchor: UnitPoint {
        switch self {
        case .leading: return .leading
        case .trailing: return .trailing
        case .top: return .top
        case .bottom: return .bottom
        case .topLeading: return .topLeading
        case .topTrailing: return .topTrailing
        case .bottomLeading: return .bottomLeading
        case .bottomTrailing: return .bottomTrailing
        }
    }

    /// Ornament alignment
    var alignment: Alignment {
        switch self {
        case .leading: return .leading
        case .trailing: return .trailing
        case .top: return .top
        case .bottom: return .bottom
        case .topLeading: return .topLeading
        case .topTrailing: return .topTrailing
        case .bottomLeading: return .bottomLeading
        case .bottomTrailing: return .bottomTrailing
        }
    }
}

// MARK: - Ornament Visibility

/// Controls when ornaments appear
enum OrnamentVisibility {
    case always
    case onHover
    case onFocus
    case onGaze
    case manual(Bool)

    var showsByDefault: Bool {
        switch self {
        case .always: return true
        case .manual(let visible): return visible
        default: return false
        }
    }
}

// MARK: - Kagami Ornament Style

/// Base style for all Kagami ornaments
struct KagamiOrnamentStyle {
    let backgroundColor: Color
    let borderColor: Color
    let cornerRadius: CGFloat
    let padding: CGFloat
    let shadowRadius: CGFloat

    static let `default` = KagamiOrnamentStyle(
        backgroundColor: .black.opacity(0.7),
        borderColor: .white.opacity(0.2),
        cornerRadius: 20,
        padding: 12,
        shadowRadius: 8
    )

    static let prominent = KagamiOrnamentStyle(
        backgroundColor: .black.opacity(0.85),
        borderColor: .cyan.opacity(0.4),
        cornerRadius: 24,
        padding: 16,
        shadowRadius: 12
    )

    static let minimal = KagamiOrnamentStyle(
        backgroundColor: .clear,
        borderColor: .clear,
        cornerRadius: 12,
        padding: 8,
        shadowRadius: 0
    )

    static let alert = KagamiOrnamentStyle(
        backgroundColor: .red.opacity(0.15),
        borderColor: .red.opacity(0.5),
        cornerRadius: 20,
        padding: 16,
        shadowRadius: 10
    )
}

// MARK: - Ornament Container Modifier

/// Applies Kagami ornament styling to a view
struct KagamiOrnamentModifier: ViewModifier {
    let style: KagamiOrnamentStyle
    @Environment(\.accessibilityReduceTransparency) var reduceTransparency

    func body(content: Content) -> some View {
        content
            .padding(style.padding)
            .background(
                reduceTransparency
                    ? AnyShapeStyle(Color.black)
                    : AnyShapeStyle(.ultraThinMaterial)
            )
            .background(style.backgroundColor)
            .clipShape(RoundedRectangle(cornerRadius: style.cornerRadius))
            .overlay(
                RoundedRectangle(cornerRadius: style.cornerRadius)
                    .stroke(style.borderColor, lineWidth: 1)
            )
            .shadow(color: .black.opacity(0.3), radius: style.shadowRadius)
    }
}

extension View {
    /// Applies Kagami ornament styling
    func kagamiOrnament(style: KagamiOrnamentStyle = .default) -> some View {
        modifier(KagamiOrnamentModifier(style: style))
    }
}

// MARK: - Room Control Ornament

/// Ornament showing room controls for the selected room
struct RoomControlOrnament: View {
    let room: RoomData
    let onLightChange: (Int) -> Void
    let onSceneActivate: (String) -> Void

    @State private var currentLightLevel: Int
    @State private var isExpanded = false

    init(
        room: RoomData,
        onLightChange: @escaping (Int) -> Void,
        onSceneActivate: @escaping (String) -> Void
    ) {
        self.room = room
        self.onLightChange = onLightChange
        self.onSceneActivate = onSceneActivate
        self._currentLightLevel = State(initialValue: room.lightLevel)
    }

    var body: some View {
        VStack(spacing: 16) {
            // Room header
            HStack {
                Text(room.name)
                    .font(.headline)
                    .foregroundColor(.white)

                Spacer()

                Button {
                    withAnimation(.spring(response: 0.233, dampingFraction: 0.8)) {
                        isExpanded.toggle()
                    }
                } label: {
                    Image(systemName: isExpanded ? "chevron.up" : "chevron.down")
                        .foregroundColor(.white.opacity(0.7))
                }
                .buttonStyle(.plain)
            }

            // Light control
            HStack(spacing: 12) {
                Image(systemName: "lightbulb.fill")
                    .foregroundColor(currentLightLevel > 0 ? .yellow : .gray)

                Slider(value: Binding(
                    get: { Double(currentLightLevel) },
                    set: { newValue in
                        currentLightLevel = Int(newValue)
                        onLightChange(currentLightLevel)
                    }
                ), in: 0...100, step: 5)
                .tint(.cyan)

                Text("\(currentLightLevel)%")
                    .font(.caption)
                    .foregroundColor(.white.opacity(0.7))
                    .frame(width: 40)
            }

            // Quick light buttons
            HStack(spacing: 12) {
                QuickLightButton(label: "Off", level: 0, currentLevel: currentLightLevel) {
                    currentLightLevel = 0
                    onLightChange(0)
                }

                QuickLightButton(label: "25%", level: 25, currentLevel: currentLightLevel) {
                    currentLightLevel = 25
                    onLightChange(25)
                }

                QuickLightButton(label: "50%", level: 50, currentLevel: currentLightLevel) {
                    currentLightLevel = 50
                    onLightChange(50)
                }

                QuickLightButton(label: "100%", level: 100, currentLevel: currentLightLevel) {
                    currentLightLevel = 100
                    onLightChange(100)
                }
            }

            // Expanded content - scene buttons
            if isExpanded {
                Divider()
                    .background(Color.white.opacity(0.2))

                VStack(alignment: .leading, spacing: 12) {
                    Text("Scenes")
                        .font(.caption)
                        .foregroundColor(.white.opacity(0.6))

                    HStack(spacing: 12) {
                        SceneButton(name: "Movie", icon: "film.fill", color: .purple) {
                            onSceneActivate("movie_mode")
                        }

                        SceneButton(name: "Relax", icon: "sparkles", color: .orange) {
                            onSceneActivate("relax")
                        }

                        SceneButton(name: "Focus", icon: "brain", color: .blue) {
                            onSceneActivate("focus")
                        }
                    }
                }
                .transition(.opacity.combined(with: .move(edge: .top)))
            }
        }
        .frame(width: 280)
        .kagamiOrnament(style: .prominent)
        .accessibilityElement(children: .contain)
        .accessibilityLabel("Room controls for \(room.name)")
    }
}

// MARK: - Quick Light Button

struct QuickLightButton: View {
    let label: String
    let level: Int
    let currentLevel: Int
    let action: () -> Void

    private var isSelected: Bool {
        currentLevel == level
    }

    var body: some View {
        Button(action: action) {
            Text(label)
                .font(.caption)
                .foregroundColor(isSelected ? .black : .white)
                .padding(.horizontal, 12)
                .padding(.vertical, 8)
                .background(
                    Capsule()
                        .fill(isSelected ? Color.cyan : Color.white.opacity(0.1))
                )
        }
        .buttonStyle(.plain)
        .accessibilityLabel("Set lights to \(label)")
        .accessibilityAddTraits(isSelected ? .isSelected : [])
    }
}

// MARK: - Scene Button

struct SceneButton: View {
    let name: String
    let icon: String
    let color: Color
    let action: () -> Void

    var body: some View {
        Button(action: action) {
            VStack(spacing: 6) {
                Image(systemName: icon)
                    .font(.system(size: 20))
                    .foregroundColor(color)

                Text(name)
                    .font(.caption2)
                    .foregroundColor(.white.opacity(0.8))
            }
            .frame(width: 60, height: 50)
            .background(
                RoundedRectangle(cornerRadius: 12)
                    .fill(color.opacity(0.15))
            )
        }
        .buttonStyle(.plain)
        .accessibilityLabel("Activate \(name) scene")
    }
}

// MARK: - Quick Actions Ornament

/// Ornament with quick action buttons
struct QuickActionsOrnament: View {
    let actions: [QuickAction]

    struct QuickAction: Identifiable {
        let id = UUID()
        let name: String
        let icon: String
        let color: Color
        let action: () -> Void
    }

    var body: some View {
        HStack(spacing: 16) {
            ForEach(actions) { action in
                Button(action: action.action) {
                    VStack(spacing: 8) {
                        ZStack {
                            Circle()
                                .fill(action.color.opacity(0.2))
                                .frame(width: 50, height: 50)

                            Image(systemName: action.icon)
                                .font(.system(size: 22))
                                .foregroundColor(action.color)
                        }

                        Text(action.name)
                            .font(.caption)
                            .foregroundColor(.white.opacity(0.8))
                    }
                }
                .buttonStyle(OrnamentButtonStyle(color: action.color))
                .accessibilityLabel(action.name)
            }
        }
        .kagamiOrnament()
    }
}

// MARK: - Status Ornament

/// Ornament showing connection and safety status
struct StatusOrnament: View {
    let isConnected: Bool
    let safetyScore: Double
    let pendingActions: Int

    private var safetyColor: Color {
        if safetyScore >= 0.9 { return .green }
        if safetyScore >= 0.5 { return .yellow }
        return .red
    }

    var body: some View {
        HStack(spacing: 16) {
            // Connection status
            HStack(spacing: 8) {
                Circle()
                    .fill(isConnected ? Color.green : Color.red)
                    .frame(width: 10, height: 10)

                Text(isConnected ? "Connected" : "Offline")
                    .font(.caption)
                    .foregroundColor(.white.opacity(0.8))
            }

            Divider()
                .frame(height: 20)
                .background(Color.white.opacity(0.2))

            // Safety score
            HStack(spacing: 8) {
                Text("Safe")
                    .font(.caption)
                    .foregroundColor(.white.opacity(0.6))

                Text("\(String(format: "%.0f", safetyScore * 100))%")
                    .font(.caption.bold())
                    .foregroundColor(safetyColor)
            }

            // Pending actions indicator
            if pendingActions > 0 {
                Divider()
                    .frame(height: 20)
                    .background(Color.white.opacity(0.2))

                HStack(spacing: 6) {
                    Image(systemName: "clock.arrow.circlepath")
                        .font(.caption)
                        .foregroundColor(.orange)

                    Text("\(pendingActions)")
                        .font(.caption)
                        .foregroundColor(.orange)
                }
            }
        }
        .kagamiOrnament(style: .minimal)
        .accessibilityElement(children: .combine)
        .accessibilityLabel("Status: \(isConnected ? "Connected" : "Offline"), Safety score \(String(format: "%.0f", safetyScore * 100)) percent")
    }
}

// MARK: - Navigation Ornament

/// Ornament for room/floor navigation
struct NavigationOrnament: View {
    let floors: [String]
    @Binding var selectedFloor: String

    var body: some View {
        HStack(spacing: 8) {
            ForEach(floors, id: \.self) { floor in
                Button {
                    withAnimation(.spring(response: 0.233, dampingFraction: 0.8)) {
                        selectedFloor = floor
                    }
                } label: {
                    Text(floor)
                        .font(.subheadline)
                        .foregroundColor(selectedFloor == floor ? .black : .white)
                        .padding(.horizontal, 16)
                        .padding(.vertical, 10)
                        .background(
                            Capsule()
                                .fill(selectedFloor == floor ? Color.cyan : Color.white.opacity(0.1))
                        )
                }
                .buttonStyle(.plain)
                .accessibilityLabel("\(floor) floor")
                .accessibilityAddTraits(selectedFloor == floor ? .isSelected : [])
            }
        }
        .kagamiOrnament()
    }
}

// MARK: - Voice Command Ornament

/// Ornament showing voice command status
struct VoiceCommandOrnament: View {
    @Binding var isListening: Bool
    let transcript: String
    let confidence: Double

    var body: some View {
        HStack(spacing: 12) {
            // Microphone indicator
            ZStack {
                Circle()
                    .fill(isListening ? Color.red.opacity(0.3) : Color.gray.opacity(0.2))
                    .frame(width: 40, height: 40)

                Image(systemName: isListening ? "mic.fill" : "mic")
                    .font(.system(size: 18))
                    .foregroundColor(isListening ? .red : .white.opacity(0.6))
            }
            .accessibilityLabel(isListening ? "Listening" : "Microphone inactive")

            if isListening || !transcript.isEmpty {
                VStack(alignment: .leading, spacing: 4) {
                    if isListening {
                        Text("Listening...")
                            .font(.caption)
                            .foregroundColor(.white.opacity(0.6))
                    }

                    if !transcript.isEmpty {
                        Text(transcript)
                            .font(.subheadline)
                            .foregroundColor(.white)
                            .lineLimit(2)

                        if confidence > 0 {
                            Text("Confidence: \(String(format: "%.0f%%", confidence * 100))")
                                .font(.caption2)
                                .foregroundColor(.white.opacity(0.5))
                        }
                    }
                }
                .frame(maxWidth: 200)
            }
        }
        .kagamiOrnament(style: isListening ? .prominent : .default)
        .animation(.spring(response: 0.233, dampingFraction: 0.8), value: isListening)
    }
}

// MARK: - Ornament Button Style

/// Button style for ornament controls
struct OrnamentButtonStyle: ButtonStyle {
    let color: Color

    func makeBody(configuration: Configuration) -> some View {
        configuration.label
            .scaleEffect(configuration.isPressed ? 0.95 : 1.0)
            .opacity(configuration.isPressed ? 0.8 : 1.0)
            .animation(.easeOut(duration: 0.144), value: configuration.isPressed)
    }
}

// MARK: - Room Data Model

struct RoomData: Identifiable {
    let id: String
    let name: String
    var lightLevel: Int
    var isOccupied: Bool
    var temperature: Double?
}

// MARK: - Preview

#Preview {
    VStack(spacing: 40) {
        StatusOrnament(
            isConnected: true,
            safetyScore: 0.92,
            pendingActions: 0
        )

        QuickActionsOrnament(actions: [
            .init(name: "Lights Off", icon: "lightbulb.slash.fill", color: .gray) {},
            .init(name: "Lock All", icon: "lock.fill", color: .blue) {},
            .init(name: "Movie", icon: "film.fill", color: .purple) {},
            .init(name: "Goodnight", icon: "moon.fill", color: .indigo) {}
        ])

        RoomControlOrnament(
            room: RoomData(id: "living", name: "Living Room", lightLevel: 75, isOccupied: true),
            onLightChange: { _ in },
            onSceneActivate: { _ in }
        )
    }
    .padding(40)
    .background(Color.black)
}

/*
 * 鏡
 * h(x) >= 0. Always.
 *
 * Ornaments float at the edge of vision.
 * Controls appear when needed.
 * The interface breathes with intent.
 */
