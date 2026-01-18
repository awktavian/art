//
// RoomsView.swift — Room Control
//
// Fetches rooms from API and displays interactive controls.
// Includes RTL support, Dynamic Type, microinteractions, and delight.
//

import SwiftUI
import KagamiDesign

// MARK: - Room Shimmer Loading View

/// Shimmer skeleton for rooms loading state
struct RoomsShimmerView: View {
    var body: some View {
        VStack(spacing: 0) {
            ForEach(0..<5, id: \.self) { index in
                RoomShimmerRow()
                    .padding(.horizontal, KagamiSpacing.md)
                    .padding(.vertical, KagamiSpacing.sm)
                if index < 4 {
                    Divider()
                        .background(Color.voidLight)
                }
            }
        }
        .accessibilityLabel("Loading rooms")
    }
}

/// Single room shimmer row
struct RoomShimmerRow: View {
    var body: some View {
        VStack(alignment: .leading, spacing: KagamiSpacing.sm) {
            // Header row
            HStack {
                VStack(alignment: .leading, spacing: KagamiSpacing.xs) {
                    // Room name placeholder
                    ShimmerPlaceholder(width: 140, height: 18)
                    // Floor placeholder
                    ShimmerPlaceholder(width: 80, height: 14)
                }
                Spacer()
                // Light status placeholder
                ShimmerPlaceholder(width: 50, height: 16)
            }

            // Brightness bar placeholder
            ShimmerPlaceholder(height: 4)

            // Action buttons placeholder
            HStack(spacing: KagamiSpacing.sm) {
                ForEach(0..<3, id: \.self) { _ in
                    RoundedRectangle(cornerRadius: KagamiRadius.sm)
                        .fill(Color.voidLight)
                        .frame(height: 44)
                        .shimmer()
                }
            }
        }
    }
}

// MARK: - Rooms View

struct RoomsView: View {
    @State private var rooms: [RoomModel] = []
    @State private var isLoading = true
    @State private var errorMessage: String?

    var body: some View {
        NavigationStack {
            Group {
                if isLoading {
                    ScrollView {
                        RoomsShimmerView()
                    }
                    .accessibilityIdentifier(AccessibilityIdentifiers.Rooms.loadingIndicator)
                } else if let error = errorMessage {
                    VStack(spacing: 16) {
                        Text(error)
                            .foregroundColor(.secondary)
                            .accessibilityIdentifier(AccessibilityIdentifiers.Rooms.errorMessage)
                        Button("Retry") {
                            Task { await fetchRooms() }
                        }
                        .buttonStyle(.bordered)
                        .accessibilityIdentifier(AccessibilityIdentifiers.Rooms.retryButton)
                    }
                    .frame(maxWidth: .infinity, maxHeight: .infinity)
                } else if rooms.isEmpty {
                    Text("No rooms found")
                        .foregroundColor(.secondary)
                        .frame(maxWidth: .infinity, maxHeight: .infinity)
                        .accessibilityIdentifier(AccessibilityIdentifiers.Rooms.emptyState)
                } else {
                    List(rooms) { room in
                        RoomRow(room: room, onRefresh: { Task { await fetchRooms() } })
                            .accessibilityIdentifier(AccessibilityIdentifiers.Rooms.row(room.id))
                    }
                    .listStyle(.plain)
                    .scrollContentBackground(.hidden)
                    .refreshable {
                        await fetchRooms()
                    }
                    .accessibilityIdentifier(AccessibilityIdentifiers.Rooms.list)
                }
            }
            .background(Color.void)
            .navigationTitle("Rooms")
            .toolbar {
                ToolbarItem(placement: .navigationBarTrailing) {
                    Button(action: { Task { await fetchRooms() } }) {
                        Image(systemName: "arrow.clockwise")
                    }
                    .accessibilityIdentifier(AccessibilityIdentifiers.Rooms.refreshButton)
                }
            }
        }
        .accessibilityIdentifier(AccessibilityIdentifiers.Rooms.view)
        .task {
            await fetchRooms()
        }
    }

    private func fetchRooms() async {
        isLoading = true
        errorMessage = nil

        do {
            rooms = try await KagamiAPIService.shared.fetchRooms()
        } catch {
            errorMessage = "Failed to load rooms"
        }

        isLoading = false
    }
}

struct RoomRow: View {
    let room: RoomModel
    let onRefresh: () -> Void

    @Environment(\.layoutDirection) private var layoutDirection
    @Environment(\.accessibilityReduceMotion) private var reduceMotion
    @State private var isAnimating = false

    var lightStatusDescription: String {
        if room.avgLightLevel > 0 {
            return "\(room.avgLightLevel) percent brightness"
        }
        return "Off"
    }

    var lightStatusColor: Color {
        switch room.lightState {
        case "On": return .grove
        case "Dim": return .beacon
        default: return Color.white.opacity(0.3)
        }
    }

    var body: some View {
        VStack(alignment: .leading, spacing: KagamiSpacing.md) {
            // Header row with name, floor, and status
            HStack(alignment: .center, spacing: KagamiSpacing.md) {
                // Room icon with occupancy indicator
                ZStack {
                    Circle()
                        .fill(room.occupied ? Color.grove.opacity(0.15) : Color.voidLight)
                        .frame(width: 44, height: 44)

                    Image(systemName: roomIcon)
                        .font(.title3)
                        .foregroundColor(room.occupied ? .grove : .accessibleTextSecondary)
                }
                .overlay(
                    // Occupancy pulse
                    Circle()
                        .stroke(Color.grove.opacity(room.occupied && !reduceMotion ? 0.4 : 0), lineWidth: 2)
                        .scaleEffect(room.occupied && isAnimating ? 1.3 : 1.0)
                )

                VStack(alignment: .leading, spacing: 2) {
                    HStack(spacing: KagamiSpacing.xs) {
                        Text(room.name)
                            .font(KagamiFont.headline())
                            .foregroundColor(.accessibleTextPrimary)

                        if room.occupied {
                            Text("•")
                                .foregroundColor(.grove)
                            Text("Occupied")
                                .font(KagamiFont.caption())
                                .foregroundColor(.grove)
                        }
                    }

                    Text(room.floor)
                        .font(KagamiFont.caption())
                        .foregroundColor(.accessibleTextTertiary)
                }

                Spacer()

                // Light level badge
                VStack(alignment: .trailing, spacing: 4) {
                    HStack(spacing: 4) {
                        Circle()
                            .fill(lightStatusColor)
                            .frame(width: 8, height: 8)
                        Text(room.avgLightLevel > 0 ? "\(room.avgLightLevel)%" : "Off")
                            .font(KagamiFont.body(weight: .medium))
                            .foregroundColor(.accessibleTextPrimary)
                    }

                    if room.avgLightLevel > 0 {
                        Text(room.lightState)
                            .font(KagamiFont.caption())
                            .foregroundColor(.accessibleTextTertiary)
                    }
                }
            }
            .accessibilityElement(children: .combine)
            .accessibilityLabel("\(room.name), \(room.floor). \(room.occupied ? "Occupied. " : "")Lights: \(lightStatusDescription)")

            // Brightness bar with smooth animation
            GeometryReader { geometry in
                ZStack(alignment: layoutDirection == .rightToLeft ? .trailing : .leading) {
                    // Track
                    Capsule()
                        .fill(Color.white.opacity(0.08))
                        .frame(height: 6)

                    // Fill
                    Capsule()
                        .fill(
                            LinearGradient(
                                colors: [.crystal, .forge],
                                startPoint: layoutDirection == .rightToLeft ? .trailing : .leading,
                                endPoint: layoutDirection == .rightToLeft ? .leading : .trailing
                            )
                        )
                        .frame(width: geometry.size.width * CGFloat(room.avgLightLevel) / 100, height: 6)
                        .animation(.spring(response: 0.4, dampingFraction: 0.7), value: room.avgLightLevel)
                }
            }
            .frame(height: 6)
            .accessibilityHidden(true)

            // Action buttons with SF Symbols (cleaner than emoji)
            HStack(spacing: KagamiSpacing.sm) {
                RoomButton(
                    icon: "sun.max.fill",
                    label: "Bright",
                    accessibilityLabel: "Full brightness",
                    color: .crystal
                ) {
                    Task {
                        await KagamiAPIService.shared.setLights(100, rooms: [room.id])
                        onRefresh()
                    }
                }

                RoomButton(
                    icon: "moon.fill",
                    label: "Dim",
                    accessibilityLabel: "Dim lights",
                    color: .beacon
                ) {
                    Task {
                        await KagamiAPIService.shared.setLights(30, rooms: [room.id])
                        onRefresh()
                    }
                }

                RoomButton(
                    icon: "power",
                    label: "Off",
                    accessibilityLabel: "Lights off",
                    color: .accessibleTextTertiary
                ) {
                    Task {
                        await KagamiAPIService.shared.setLights(0, rooms: [room.id])
                        onRefresh()
                    }
                }
            }
        }
        .padding(.vertical, KagamiSpacing.sm)
        .listRowBackground(
            RoundedRectangle(cornerRadius: KagamiRadius.sm)
                .fill(room.occupied ? Color.grove.opacity(0.05) : Color.voidLight)
                .overlay(
                    RoundedRectangle(cornerRadius: KagamiRadius.sm)
                        .stroke(room.occupied ? Color.grove.opacity(0.2) : Color.clear, lineWidth: 1)
                )
        )
        .onAppear {
            if room.occupied && !reduceMotion {
                withAnimation(.easeInOut(duration: 1.5).repeatForever(autoreverses: true)) {
                    isAnimating = true
                }
            }
        }
    }

    private var roomIcon: String {
        let name = room.name.lowercased()
        if name.contains("living") { return "sofa.fill" }
        if name.contains("kitchen") { return "refrigerator.fill" }
        if name.contains("bed") || name.contains("primary") { return "bed.double.fill" }
        if name.contains("bath") { return "shower.fill" }
        if name.contains("office") { return "desktopcomputer" }
        if name.contains("dining") { return "fork.knife" }
        if name.contains("garage") { return "car.fill" }
        if name.contains("gym") { return "figure.run" }
        if name.contains("game") { return "gamecontroller.fill" }
        if name.contains("laundry") { return "washer.fill" }
        if name.contains("entry") || name.contains("mud") { return "door.left.hand.open" }
        if name.contains("deck") || name.contains("patio") { return "sun.horizon.fill" }
        return "square.fill"
    }
}

struct RoomButton: View {
    let icon: String
    let label: String
    let accessibilityLabel: String
    let color: Color
    let action: () -> Void

    @State private var isPressed = false
    @Environment(\.accessibilityReduceMotion) private var reduceMotion

    init(
        icon: String,
        label: String,
        accessibilityLabel: String,
        color: Color,
        action: @escaping () -> Void
    ) {
        self.icon = icon
        self.label = label
        self.accessibilityLabel = accessibilityLabel
        self.color = color
        self.action = action
    }

    var body: some View {
        Button(action: {
            UIImpactFeedbackGenerator(style: .medium).impactOccurred()
            action()
        }) {
            VStack(spacing: 4) {
                Image(systemName: icon)
                    .font(.body)
                    .foregroundColor(color)

                Text(label)
                    .font(KagamiFont.caption(weight: .medium))
                    .foregroundColor(.accessibleTextSecondary)
            }
            .frame(maxWidth: .infinity)
            .frame(minHeight: 52) // Generous touch target
            .background(color.opacity(0.12))
            .cornerRadius(KagamiRadius.md)
            .overlay(
                RoundedRectangle(cornerRadius: KagamiRadius.md)
                    .stroke(color.opacity(0.2), lineWidth: 1)
            )
            .scaleEffect(isPressed && !reduceMotion ? 0.95 : 1.0)
            .animation(.spring(response: 0.2, dampingFraction: 0.7), value: isPressed)
        }
        .buttonStyle(.plain)
        .simultaneousGesture(
            DragGesture(minimumDistance: 0)
                .onChanged { _ in isPressed = true }
                .onEnded { _ in isPressed = false }
        )
        .accessibilityLabel(accessibilityLabel)
        .accessibilityHint("Double tap to activate")
    }
}
