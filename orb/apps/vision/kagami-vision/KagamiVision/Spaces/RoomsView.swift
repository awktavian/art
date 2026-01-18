//
// RoomsView.swift — Spatial Room Control for Vision Pro
//
// Colony: Nexus (e₄) — Integration
//
// Design:
//   - Glass morphism cards for each room
//   - Inline light and shade controls
//   - Brightness visualization bar
//   - Occupied room highlighting
//   - Pull-to-refresh and manual refresh
//
// Phase 2 Accessibility:
//   - VoiceOver support for room cards
//   - Spatial gesture hints
//   - Enhanced contrast for glass panels
//   - Meaningful accessibility labels
//

import SwiftUI

struct RoomsView: View {
    @EnvironmentObject var appModel: AppModel
    @State private var rooms: [RoomModel] = []
    @State private var isLoading = true
    @State private var errorMessage: String?
    @State private var roomsAppeared: Set<String> = []
    @Environment(\.accessibilityReduceMotion) private var reduceMotion

    var body: some View {
        NavigationStack {
            contentView
                .navigationTitle("Rooms")
                .toolbar {
                    ToolbarItem(placement: .navigationBarTrailing) {
                        Button(action: { Task { await fetchRooms() } }) {
                            Image(systemName: "arrow.clockwise")
                        }
                    }
                }
        }
        .task {
            await fetchRooms()
        }
        .glassBackgroundEffect()
    }

    @ViewBuilder
    private var contentView: some View {
        if isLoading {
            loadingView
        } else if let error = errorMessage {
            errorView(error)
        } else if rooms.isEmpty {
            emptyView
        } else {
            roomsGridView
        }
    }

    private var loadingView: some View {
        ProgressView()
            .progressViewStyle(CircularProgressViewStyle())
            .scaleEffect(1.5)
            .frame(maxWidth: .infinity, maxHeight: .infinity)
    }

    private func errorView(_ error: String) -> some View {
        VStack(spacing: 16) {
            Image(systemName: "exclamationmark.triangle.fill")
                .font(.system(size: 48))
                .foregroundColor(.spark)
                .accessibilityHidden(true)
            Text(error)
                .foregroundColor(.secondary)
            Button("Retry") {
                Task { await fetchRooms() }
            }
            .buttonStyle(.bordered)
            .spatialGestureHint(.lookAndPinch)
        }
        .frame(maxWidth: .infinity, maxHeight: .infinity)
        .accessibilityElement(children: .combine)
        .accessibilityLabel("Error: \(error). Retry button available.")
    }

    private var emptyView: some View {
        VStack(spacing: 16) {
            Image(systemName: "house")
                .font(.system(size: 48))
                .foregroundColor(.secondary)
                .accessibilityHidden(true)
            Text("No rooms found")
                .foregroundColor(.secondary)
        }
        .frame(maxWidth: .infinity, maxHeight: .infinity)
        .accessibilityElement(children: .combine)
        .accessibilityLabel("No rooms found")
    }

    private var roomsGridView: some View {
        ScrollView {
            LazyVGrid(columns: [
                GridItem(.adaptive(minimum: 280, maximum: 360), spacing: 16)
            ], spacing: 16) {
                ForEach(Array(rooms.enumerated()), id: \.element.id) { index, room in
                    roomCard(room: room, index: index)
                }
            }
            .padding(24)
        }
    }

    private func roomCard(room: RoomModel, index: Int) -> some View {
        let hasAppeared = roomsAppeared.contains(room.id)
        return SpatialRoomCard(room: room, onRefresh: {
            Task { await fetchRooms() }
        })
        .opacity(hasAppeared ? 1 : 0)
        .offset(y: hasAppeared ? 0 : 20)
        .animation(
            reduceMotion ? nil :
                .spring(response: 0.233, dampingFraction: 0.8)
                .delay(Double(index) * 0.144),
            value: hasAppeared
        )
        .onAppear {
            DispatchQueue.main.asyncAfter(deadline: .now() + Double(index) * 0.144) {
                withAnimation {
                    _ = roomsAppeared.insert(room.id)
                }
            }
        }
    }

    private func fetchRooms() async {
        isLoading = true
        errorMessage = nil

        do {
            rooms = try await appModel.apiService.fetchRooms()
        } catch {
            errorMessage = "Failed to load rooms"
        }

        isLoading = false
    }
}

// MARK: - Spatial Room Card

struct SpatialRoomCard: View {
    let room: RoomModel
    let onRefresh: () -> Void

    @EnvironmentObject var appModel: AppModel
    @State private var isHovered = false
    @Environment(\.accessibilityDifferentiateWithoutColor) private var differentiateWithoutColor

    private var roomAccessibilityLabel: String {
        var label = "\(room.name), \(room.floor)"
        label += room.occupied ? ", occupied" : ""
        label += ", lights \(room.lightState)"
        if room.avgLightLevel > 0 {
            label += " at \(room.avgLightLevel) percent"
        }
        if !room.shades.isEmpty {
            label += ", has shades"
        }
        return label
    }

    var body: some View {
        VStack(alignment: .leading, spacing: 16) {
            // Header
            HStack {
                VStack(alignment: .leading, spacing: 4) {
                    Text(room.name)
                        .font(.title3)
                        .fontWeight(.semibold)
                        .foregroundColor(.white)

                    Text(room.floor)
                        .font(.system(size: 14))
                        .foregroundColor(.secondary)
                }

                Spacer()

                // Occupancy and light status
                HStack(spacing: 8) {
                    if room.occupied {
                        Image(systemName: "person.fill")
                            .font(.system(size: 14))
                            .foregroundColor(.grove)
                            .accessibilityHidden(true)
                    }

                    // Light status indicator with icon for color-blind accessibility
                    ZStack {
                        Circle()
                            .fill(lightStatusColor)
                            .frame(width: 10, height: 10)

                        // Add icon when differentiateWithoutColor is enabled
                        if differentiateWithoutColor {
                            Image(systemName: lightStatusIcon)
                                .font(.system(size: 6, weight: .bold))
                                .foregroundColor(.white)
                        }
                    }
                    .accessibilityHidden(true)

                    Text(room.avgLightLevel > 0 ? "\(room.avgLightLevel)%" : "Off")
                        .font(.system(size: 14, design: .monospaced))
                        .foregroundColor(.secondary)
                }
            }
            .accessibilityElement(children: .combine)
            .accessibilityLabel(roomAccessibilityLabel)
            .accessibilityAddTraits(.isHeader)

            // Brightness bar
            GeometryReader { geometry in
                ZStack(alignment: .leading) {
                    RoundedRectangle(cornerRadius: 3)
                        .fill(Color.white.opacity(AccessibilitySettings.shared.increaseContrast ? 0.2 : 0.1))
                        .frame(height: 6)

                    RoundedRectangle(cornerRadius: 3)
                        .fill(
                            LinearGradient(
                                colors: [.crystal, .forge],
                                startPoint: .leading,
                                endPoint: .trailing
                            )
                        )
                        .frame(width: geometry.size.width * CGFloat(room.avgLightLevel) / 100, height: 6)
                }
            }
            .frame(height: 6)
            .accessibilityLabel("Brightness level")
            .accessibilityValue("\(room.avgLightLevel) percent")

            // Light Controls
            HStack(spacing: 8) {
                SpatialRoomButton(
                    systemIcon: SceneIcon.lights,
                    label: "On",
                    accessibilityLabel: "Lights on",
                    accessibilityHint: "Sets \(room.name) lights to full brightness",
                    color: .crystal
                ) {
                    Task {
                        await appModel.apiService.setLights(100, rooms: [room.id])
                        onRefresh()
                    }
                }

                SpatialRoomButton(
                    systemIcon: "moon.fill",
                    label: "Dim",
                    accessibilityLabel: "Dim lights",
                    accessibilityHint: "Dims \(room.name) lights to 30 percent",
                    color: .beacon
                ) {
                    Task {
                        await appModel.apiService.setLights(30, rooms: [room.id])
                        onRefresh()
                    }
                }

                SpatialRoomButton(
                    systemIcon: "lightbulb.slash",
                    label: "Off",
                    accessibilityLabel: "Lights off",
                    accessibilityHint: "Turns off \(room.name) lights",
                    color: Color(white: 0.15)
                ) {
                    Task {
                        await appModel.apiService.setLights(0, rooms: [room.id])
                        onRefresh()
                    }
                }
            }
            .spatialRegion("\(room.name) light controls")

            // Shade Controls (if room has shades)
            if !room.shades.isEmpty {
                HStack(spacing: 8) {
                    SpatialRoomButton(
                        systemIcon: "blinds.horizontal.open",
                        label: "Open",
                        accessibilityLabel: "Open shades",
                        accessibilityHint: "Opens all shades in \(room.name)",
                        color: .grove
                    ) {
                        Task {
                            await appModel.apiService.controlShades("open", rooms: [room.id])
                            onRefresh()
                        }
                    }

                    SpatialRoomButton(
                        systemIcon: "blinds.horizontal.closed",
                        label: "Close",
                        accessibilityLabel: "Close shades",
                        accessibilityHint: "Closes all shades in \(room.name)",
                        color: .nexus
                    ) {
                        Task {
                            await appModel.apiService.controlShades("close", rooms: [room.id])
                            onRefresh()
                        }
                    }
                }
                .spatialRegion("\(room.name) shade controls")
            }
        }
        .padding(20)
        .background(
            RoundedRectangle(cornerRadius: 20)
                .fill(
                    AccessibilitySettings.shared.increaseContrast
                        ? AnyShapeStyle(.thinMaterial)
                        : AnyShapeStyle(.ultraThinMaterial)
                )
                .overlay(
                    RoundedRectangle(cornerRadius: 20)
                        .stroke(
                            room.occupied
                                ? Color.grove.opacity(AccessibilitySettings.shared.increaseContrast ? 0.7 : 0.5)
                                : Color.adaptiveGlassBorder.opacity(isHovered ? 0.4 : 0.2),
                            lineWidth: AccessibilitySettings.shared.increaseContrast ? 2 : 1
                        )
                )
        )
        .hoverEffect(.lift)
        .onHover { isHovered = $0 }
    }

    private var lightStatusColor: Color {
        switch room.lightState {
        case "On": return .grove
        case "Dim": return .beacon
        default: return .white.opacity(0.3)
        }
    }

    /// Icon for light status when differentiateWithoutColor is enabled
    private var lightStatusIcon: String {
        switch room.lightState {
        case "On": return "sun.max.fill"
        case "Dim": return "moon.fill"
        default: return "moon.zzz"
        }
    }
}

// MARK: - Spatial Room Button

struct SpatialRoomButton: View {
    let systemIcon: String
    let label: String
    var accessibilityLabel: String? = nil
    var accessibilityHint: String? = nil
    let color: Color
    let action: () -> Void

    @Environment(\.accessibilityReduceMotion) private var reduceMotion
    @State private var isPressed = false

    var body: some View {
        Button(action: {
            isPressed = true
            action()
            DispatchQueue.main.asyncAfter(deadline: .now() + 0.2) {
                isPressed = false
            }
        }) {
            VStack(spacing: 4) {
                Image(systemName: systemIcon)
                    .font(.system(size: 20))
                    .foregroundColor(color)
                    .accessibilityHidden(true)
                Text(label)
                    .font(.system(size: 14, design: .rounded))
                    .foregroundColor(.secondary)
            }
            .frame(maxWidth: .infinity)
            .padding(.vertical, 12)
            .background(
                RoundedRectangle(cornerRadius: 12)
                    .fill(color.opacity(isPressed ? 0.4 : 0.2))
            )
            .overlay(
                RoundedRectangle(cornerRadius: 12)
                    .stroke(
                        color.opacity(AccessibilitySettings.shared.increaseContrast ? 0.5 : 0.3),
                        lineWidth: AccessibilitySettings.shared.increaseContrast ? 1.5 : 1
                    )
            )
        }
        .buttonStyle(.plain)
        .scaleEffect(reduceMotion ? 1.0 : (isPressed ? 0.95 : 1.0))
        .reducedMotionAnimation(isPressed, defaultAnimation: .spring(response: 0.2, dampingFraction: 0.6))
        .accessibilityLabel(accessibilityLabel ?? label)
        .accessibilityHint(accessibilityHint ?? "Look at and pinch to activate")
        .spatialGestureHint(.lookAndPinch)
    }
}

#Preview(windowStyle: .plain) {
    RoomsView()
        .environmentObject(AppModel())
}

/*
 * 鏡
 * Spatial presence through room control.
 */
