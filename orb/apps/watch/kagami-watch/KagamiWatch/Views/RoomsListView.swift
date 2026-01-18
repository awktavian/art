//
// RoomsListView.swift - Compact Room Control for Apple Watch
//
// Colony: Grove (e6) - Spatial Understanding
//
// h(x) >= 0. Always.
//

import SwiftUI
import WatchKit
import KagamiDesign

struct RoomsListView: View {
    @EnvironmentObject var api: KagamiAPIService
    @State private var rooms: [WatchRoomModel] = []
    @State private var isLoading = true
    @State private var errorMessage: String?
    @State private var selectedRoomIndex: Double = 0
    @Namespace private var scrollNamespace

    var body: some View {
        ZStack {
            if isLoading {
                // Skeleton loaders while loading
                ScrollView {
                    LazyVStack(spacing: 8) {
                        ForEach(0..<3, id: \.self) { _ in
                            RoomCardSkeletonView()
                        }
                    }
                    .padding(.horizontal, 4)
                }
            } else if let error = errorMessage {
                ErrorMessageView(.connectionFailed) {
                    Task { await fetchRooms() }
                }
            } else if rooms.isEmpty {
                VStack(spacing: 8) {
                    Image(systemName: "house")
                        .font(.title2)
                        .foregroundColor(.secondary)
                    Text("No rooms")
                        .font(WatchFonts.caption())
                        .foregroundColor(.secondary)
                }
            } else {
                ScrollViewReader { proxy in
                    ScrollView {
                        LazyVStack(spacing: 8) {
                            ForEach(Array(rooms.enumerated()), id: \.element.id) { index, room in
                                WatchRoomCard(
                                    room: room,
                                    isSelected: index == Int(selectedRoomIndex),
                                    onRefresh: { Task { await fetchRooms() } }
                                )
                                .id(room.id)
                                .onTapGesture {
                                    selectedRoomIndex = Double(index)
                                    HapticPattern.success.play()
                                }
                            }
                        }
                        .padding(.horizontal, 4)
                    }
                    .focusable()
                    .digitalCrownRotation(
                        $selectedRoomIndex,
                        from: 0.0,
                        through: Double(rooms.count - 1),
                        by: 1.0,
                        sensitivity: .medium,
                        isContinuous: false,
                        isHapticFeedbackEnabled: true
                    )
                    .onChange(of: selectedRoomIndex) { _, newValue in
                        // Auto-scroll to selected room with animation (Fibonacci timing)
                        let newIndex = Int(newValue)
                        if newIndex >= 0 && newIndex < rooms.count {
                            withAnimation(.easeInOut(duration: WatchMotion.normal)) {
                                proxy.scrollTo(rooms[newIndex].id, anchor: .center)
                            }
                        }
                    }
                }
            }
        }
        .navigationTitle("Rooms")
        .task {
            await fetchRooms()
        }
    }

    private func fetchRooms() async {
        isLoading = true
        errorMessage = nil

        do {
            rooms = try await api.fetchRooms()
        } catch {
            errorMessage = "Failed to load"
        }

        isLoading = false
    }
}

// MARK: - Watch Room Card

struct WatchRoomCard: View {
    let room: WatchRoomModel
    let isSelected: Bool
    let onRefresh: () -> Void

    @EnvironmentObject var api: KagamiAPIService
    @Environment(\.isLuminanceReduced) var isAlwaysOnDisplay

    var body: some View {
        VStack(alignment: .leading, spacing: 6) {
            // Header Row
            HStack {
                // Room name
                VStack(alignment: .leading, spacing: 2) {
                    Text(room.name)
                        .font(WatchFonts.primary(.caption))
                        .lineLimit(1)
                        .alwaysOnText()  // Always-On Display optimization

                    Text(room.floor)
                        .font(WatchFonts.caption(.caption2))
                        .foregroundColor(.secondary)
                }

                Spacer()

                // Status indicators
                HStack(spacing: 4) {
                    if room.occupied {
                        Image(systemName: "person.fill")
                            .font(.system(size: 10))
                            .foregroundColor(.grove)
                            .accessibilityHidden(true)
                    }

                    Circle()
                        .fill(lightStatusColor)
                        .frame(width: 6, height: 6)
                        .accessibilityHidden(true)

                    Text(room.avgLightLevel > 0 ? "\(room.avgLightLevel)%" : "Off")
                        .font(WatchFonts.mono(.caption2))
                        .foregroundColor(.secondary)
                        .alwaysOnOptimized(isEssential: true)
                }
            }
            .accessibilityElement(children: .combine)
            .accessibilityLabel(roomHeaderAccessibilityLabel)

            // Brightness bar
            GeometryReader { geometry in
                ZStack(alignment: .leading) {
                    RoundedRectangle(cornerRadius: 2)
                        .fill(Color.white.opacity(0.1))
                        .frame(height: 3)

                    RoundedRectangle(cornerRadius: 2)
                        .fill(
                            LinearGradient(
                                colors: [.crystal, .forge],
                                startPoint: .leading,
                                endPoint: .trailing
                            )
                        )
                        .frame(width: geometry.size.width * CGFloat(room.avgLightLevel) / 100, height: 3)
                }
            }
            .frame(height: 3)
            .accessibilityHidden(true)

            // Quick action buttons
            HStack(spacing: 4) {
                WatchRoomButton(icon: "lightbulb.fill", label: "Full brightness", color: .crystal, brightnessLevel: 100) {
                    Task {
                        await api.setLights(100, rooms: [room.id])
                        onRefresh()
                    }
                }

                WatchRoomButton(icon: "moon.fill", label: "Dim lights", color: .beacon, brightnessLevel: 30) {
                    Task {
                        await api.setLights(30, rooms: [room.id])
                        onRefresh()
                    }
                }

                WatchRoomButton(icon: "lightbulb.slash", label: "Lights off", color: .textSecondary, brightnessLevel: 0) {
                    Task {
                        await api.setLights(0, rooms: [room.id])
                        onRefresh()
                    }
                }

                if room.hasShades {
                    Divider()
                        .frame(height: 20)
                        .accessibilityHidden(true)

                    WatchRoomButton(icon: "sun.max.fill", label: "Open shades", color: .grove) {
                        Task {
                            await api.controlShades("open", rooms: [room.id])
                            onRefresh()
                        }
                    }

                    WatchRoomButton(icon: "moon.stars.fill", label: "Close shades", color: .flow) {
                        Task {
                            await api.controlShades("close", rooms: [room.id])
                            onRefresh()
                        }
                    }
                }
            }
        }
        .padding(8)
        .watchCard()  // Standardized card styling
        .overlay(
            RoundedRectangle(cornerRadius: 10)
                .stroke(
                    isSelected
                        ? Color.crystal.opacity(0.6)
                        : room.occupied
                            ? Color.grove.opacity(0.4)
                            : Color.clear,
                    lineWidth: isSelected ? 2 : 1
                )
        )
    }

    private var roomHeaderAccessibilityLabel: String {
        var label = "\(room.name), \(room.floor)"
        if room.occupied {
            label += ", occupied"
        }
        if room.avgLightLevel > 0 {
            label += ", lights at \(room.avgLightLevel) percent"
        } else {
            label += ", lights off"
        }
        return label
    }

    private var lightStatusColor: Color {
        switch room.lightState {
        case "On": return .grove
        case "Dim": return .beacon
        default: return .white.opacity(0.5)
        }
    }
}

// MARK: - Watch Room Button (44pt minimum touch target)

struct WatchRoomButton: View {
    let icon: String
    let label: String
    let color: Color
    let brightnessLevel: Int?  // Optional brightness level for checkpoint haptics
    let action: () -> Void

    @State private var isPressed = false
    @Environment(\.accessibilityReduceMotion) var reduceMotion

    init(icon: String, label: String, color: Color, brightnessLevel: Int? = nil, action: @escaping () -> Void) {
        self.icon = icon
        self.label = label
        self.color = color
        self.brightnessLevel = brightnessLevel
        self.action = action
    }

    var body: some View {
        Button(action: {
            isPressed = true
            playCheckpointHaptic()
            action()
            DispatchQueue.main.asyncAfter(deadline: .now() + WatchMotion.fast) {
                isPressed = false
            }
        }) {
            Image(systemName: icon)
                .font(.system(size: 14))
                .foregroundColor(color)
                .frame(width: 32, height: 32)
                .background(
                    RoundedRectangle(cornerRadius: 8)
                        .fill(color.opacity(isPressed ? 0.4 : 0.2))
                )
        }
        .buttonStyle(.plain)
        .frame(minWidth: 44, minHeight: 44)
        .scaleEffect(reduceMotion ? 1.0 : (isPressed ? 0.92 : 1.0))
        .animation(reduceMotion ? nil : WatchMotion.quick, value: isPressed)
        .accessibilityLabel(label)
        .accessibilityHint("Double tap to \(label.lowercased())")
    }

    /// Play checkpoint haptics for brightness levels (every 25%)
    private func playCheckpointHaptic() {
        guard let level = brightnessLevel else {
            HapticPattern.success.play()
            return
        }

        // Checkpoint haptics at 0%, 25%, 50%, 75%, 100%
        let device = WKInterfaceDevice.current()
        switch level {
        case 0:
            // Lights off - subtle click
            device.play(.click)
        case 25:
            // 25% checkpoint
            device.play(.directionDown)
        case 30:
            // Dim (30%) - similar to 25% checkpoint
            device.play(.directionDown)
        case 50:
            // 50% checkpoint
            device.play(.start)
        case 75:
            // 75% checkpoint
            device.play(.directionUp)
        case 100:
            // Full brightness - satisfying success
            device.play(.success)
        default:
            device.play(.click)
        }
    }
}

#Preview {
    NavigationStack {
        RoomsListView()
            .environmentObject(KagamiAPIService())
    }
}

/*
 * 鏡
 * Compact room control from the wrist.
 */
