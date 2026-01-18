//
// HomeView.swift -- Room Controls Grid for tvOS
//
// Kagami TV -- Primary home control interface
//
// Features:
// - Room grid with large, focusable cards
// - Quick action buttons for common tasks
// - Connection status display
// - Safety score indicator
// - Smooth animations
// - Theme colors for semantic states
//

import SwiftUI
import KagamiDesign

// MARK: - Home View

struct HomeView: View {
    @EnvironmentObject var appModel: TVAppModel

    var body: some View {
        NavigationStack {
            ScrollView {
                VStack(alignment: .leading, spacing: TVDesign.sectionSpacing) {
                    // Connection Status
                    ConnectionStatusSection(
                        isConnected: appModel.isConnected,
                        safetyScore: appModel.safetyScore,
                        pendingActions: appModel.pendingActionsCount
                    )

                    // Quick Actions
                    QuickActionsSection()

                    // Rooms Grid
                    RoomsGridSection(rooms: appModel.rooms)
                }
                .padding(TVDesign.contentPadding)
            }
            .background(Color.black.ignoresSafeArea())
            .navigationTitle("Kagami")
            .refreshable {
                await appModel.refresh()
            }
        }
    }
}

// MARK: - Connection Status Section

struct ConnectionStatusSection: View {
    let isConnected: Bool
    let safetyScore: Double?
    let pendingActions: Int

    var statusColor: Color {
        isConnected ? TVDesign.successColor : TVDesign.errorColor
    }

    var safetyColor: Color {
        guard let score = safetyScore else { return .gray }
        if score >= 0.9 { return TVDesign.successColor }
        if score >= 0.7 { return TVDesign.warningColor }
        return TVDesign.errorColor
    }

    var body: some View {
        HStack(spacing: TVDesign.gridSpacing) {
            // Connection Status Card
            HStack(spacing: 20) {
                Circle()
                    .fill(statusColor)
                    .frame(width: 20, height: 20)
                    .accessibilityHidden(true)

                VStack(alignment: .leading, spacing: 8) {
                    Text(isConnected ? "Connected" : "Offline")
                        .font(.system(size: TVDesign.headlineSize, weight: .semibold))
                        .foregroundColor(.white)

                    Text("kagami.local")
                        .font(.system(size: TVDesign.captionSize))
                        .foregroundColor(.white.opacity(0.7))
                }

                Spacer()
            }
            .padding(TVDesign.cardSpacing)
            .frame(minWidth: 300)
            .background(
                RoundedRectangle(cornerRadius: TVDesign.cardRadius)
                    .fill(TVDesign.cardBackground)
            )
            .overlay(
                RoundedRectangle(cornerRadius: TVDesign.cardRadius)
                    .stroke(statusColor.opacity(0.3), lineWidth: 2)
            )
            .accessibilityElement(children: .combine)
            .accessibilityLabel("Connection status")
            .accessibilityValue(isConnected ? "Connected to kagami.local" : "Offline")

            // Safety Score Card
            if let score = safetyScore {
                HStack(spacing: 20) {
                    VStack(alignment: .leading, spacing: 8) {
                        Text("Safety")
                            .font(.system(size: TVDesign.captionSize))
                            .foregroundColor(.white.opacity(0.7))

                        Text("\(String(format: "%.0f", score * 100))%")
                            .font(.system(size: TVDesign.titleSize, weight: .bold))
                            .foregroundColor(safetyColor)
                    }

                    Spacer()
                }
                .padding(TVDesign.cardSpacing)
                .frame(minWidth: 200)
                .background(
                    RoundedRectangle(cornerRadius: TVDesign.cardRadius)
                        .fill(TVDesign.cardBackground)
                )
                .overlay(
                    RoundedRectangle(cornerRadius: TVDesign.cardRadius)
                        .stroke(safetyColor.opacity(0.3), lineWidth: 2)
                )
                .accessibilityElement(children: .combine)
                .accessibilityLabel("Safety barrier")
                .accessibilityValue(String(format: "%.2f, %@", score, score >= 0.9 ? "Optimal" : score >= 0.7 ? "Caution" : "Warning"))
            }

            // Pending Actions Card (if offline)
            if pendingActions > 0 {
                HStack(spacing: 20) {
                    Image(systemName: "clock.arrow.circlepath")
                        .font(.system(size: TVDesign.iconSize))
                        .foregroundColor(TVDesign.warningColor)

                    VStack(alignment: .leading, spacing: 8) {
                        Text("\(pendingActions) Pending")
                            .font(.system(size: TVDesign.headlineSize, weight: .semibold))
                            .foregroundColor(.white)

                        Text("Will sync when online")
                            .font(.system(size: TVDesign.captionSize))
                            .foregroundColor(.white.opacity(0.7))
                    }

                    Spacer()
                }
                .padding(TVDesign.cardSpacing)
                .frame(minWidth: 300)
                .background(
                    RoundedRectangle(cornerRadius: TVDesign.cardRadius)
                        .fill(TVDesign.cardBackground)
                )
                .overlay(
                    RoundedRectangle(cornerRadius: TVDesign.cardRadius)
                        .stroke(TVDesign.warningColor.opacity(0.3), lineWidth: 2)
                )
            }

            Spacer()
        }
    }
}

// MARK: - Quick Actions Section

struct QuickActionsSection: View {
    var body: some View {
        VStack(alignment: .leading, spacing: 24) {
            Text("Quick Actions")
                .font(.system(size: TVDesign.headlineSize, weight: .semibold))
                .foregroundColor(.white.opacity(0.8))

            HStack(spacing: TVDesign.gridSpacing) {
                QuickActionCard(
                    icon: "lightbulb.fill",
                    title: "All Lights Off",
                    color: TVDesign.primaryColor
                ) {
                    await KagamiAPIService.shared.setLights(0, rooms: nil)
                }

                QuickActionCard(
                    icon: "lock.fill",
                    title: "Lock All",
                    color: TVDesign.secondaryColor
                ) {
                    await KagamiAPIService.shared.lockAll()
                }

                QuickActionCard(
                    icon: "film.fill",
                    title: "Movie Mode",
                    color: TVDesign.warningColor
                ) {
                    await KagamiAPIService.shared.executeScene("movie_mode")
                }

                QuickActionCard(
                    icon: "moon.fill",
                    title: "Goodnight",
                    color: Color.indigo
                ) {
                    await KagamiAPIService.shared.executeScene("goodnight")
                }
            }
        }
    }
}

// MARK: - Quick Action Card

struct QuickActionCard: View {
    let icon: String
    let title: String
    let color: Color
    let action: () async -> Void

    @State private var isExecuting = false
    @FocusState private var isFocused: Bool

    var body: some View {
        Button {
            guard !isExecuting else { return }
            isExecuting = true
            Task {
                await action()
                await MainActor.run {
                    isExecuting = false
                }
            }
        } label: {
            VStack(spacing: 16) {
                ZStack {
                    Circle()
                        .fill(color.opacity(0.2))
                        .frame(width: TVDesign.largeIconSize + 24, height: TVDesign.largeIconSize + 24)

                    if isExecuting {
                        ProgressView()
                            .scaleEffect(1.2)
                    } else {
                        Image(systemName: icon)
                            .font(.system(size: TVDesign.iconSize))
                            .foregroundColor(color)
                    }
                }

                Text(title)
                    .font(.system(size: TVDesign.bodySize, weight: .medium))
                    .foregroundColor(.white)
            }
            .frame(width: 200, height: 180)
            .background(
                RoundedRectangle(cornerRadius: TVDesign.cardRadius)
                    .fill(isFocused ? TVDesign.focusedBackground : TVDesign.cardBackground)
            )
            .overlay(
                RoundedRectangle(cornerRadius: TVDesign.cardRadius)
                    .stroke(color.opacity(isFocused ? 0.8 : 0.3), lineWidth: isFocused ? 4 : 2)
            )
            .scaleEffect(isFocused ? 1.08 : 1.0)
            .animation(TvMotion.card, value: isFocused)
        }
        .buttonStyle(.plain)
        .focused($isFocused)
        .disabled(isExecuting)
        .accessibilityLabel(title)
        .accessibilityHint("Double click to activate")
        .accessibilityAddTraits(.isButton)
        .accessibilityValue(isExecuting ? "Executing" : "Ready")
    }
}

// MARK: - Rooms Grid Section

struct RoomsGridSection: View {
    let rooms: [RoomModel]

    private let columns = [
        GridItem(.flexible(), spacing: TVDesign.gridSpacing),
        GridItem(.flexible(), spacing: TVDesign.gridSpacing),
        GridItem(.flexible(), spacing: TVDesign.gridSpacing),
        GridItem(.flexible(), spacing: TVDesign.gridSpacing)
    ]

    var body: some View {
        VStack(alignment: .leading, spacing: 24) {
            HStack {
                Text("Rooms")
                    .font(.system(size: TVDesign.headlineSize, weight: .semibold))
                    .foregroundColor(.white.opacity(0.8))

                Spacer()

                if !rooms.isEmpty {
                    Text("\(rooms.count) rooms")
                        .font(.system(size: TVDesign.captionSize))
                        .foregroundColor(.white.opacity(0.65))
                }
            }

            if rooms.isEmpty {
                EmptyRoomsView()
            } else {
                LazyVGrid(columns: columns, spacing: TVDesign.gridSpacing) {
                    ForEach(rooms) { room in
                        RoomCard(room: room)
                    }
                }
            }
        }
    }
}

// MARK: - Empty Rooms View

struct EmptyRoomsView: View {
    var body: some View {
        HStack {
            Spacer()
            VStack(spacing: 20) {
                Image(systemName: "house")
                    .font(.system(size: 80))
                    .foregroundColor(.white.opacity(0.3))

                Text("No rooms available")
                    .font(.system(size: TVDesign.bodySize))
                    .foregroundColor(.white.opacity(0.65))

                Text("Connect to Kagami to see your rooms")
                    .font(.system(size: TVDesign.captionSize))
                    .foregroundColor(.white.opacity(0.3))
            }
            .padding(TVDesign.sectionSpacing)
            Spacer()
        }
        .background(
            RoundedRectangle(cornerRadius: TVDesign.cardRadius)
                .fill(TVDesign.cardBackground)
        )
    }
}

// MARK: - Room Card

struct RoomCard: View {
    let room: RoomModel

    @State private var isChangingLights = false
    @FocusState private var isFocused: Bool

    var lightColor: Color {
        if room.avgLightLevel == 0 { return .gray }
        if room.avgLightLevel < 50 { return TVDesign.warningColor }
        return TVDesign.primaryColor
    }

    var body: some View {
        VStack(alignment: .leading, spacing: 16) {
            // Header
            HStack {
                VStack(alignment: .leading, spacing: 8) {
                    Text(room.name)
                        .font(.system(size: TVDesign.headlineSize, weight: .semibold))
                        .foregroundColor(.white)
                        .lineLimit(1)

                    Text(room.floor)
                        .font(.system(size: TVDesign.captionSize))
                        .foregroundColor(.white.opacity(0.7))
                }

                Spacer()

                // Occupancy indicator
                if room.occupied {
                    Circle()
                        .fill(TVDesign.successColor)
                        .frame(width: 12, height: 12)
                }
            }

            // Light Level Bar
            GeometryReader { geometry in
                ZStack(alignment: .leading) {
                    RoundedRectangle(cornerRadius: 4)
                        .fill(Color.white.opacity(0.15))  // Increased from 0.1 for visibility
                        .frame(height: 8)

                    RoundedRectangle(cornerRadius: 4)
                        .fill(
                            LinearGradient(
                                colors: [TVDesign.primaryColor, TVDesign.secondaryColor],
                                startPoint: .leading,
                                endPoint: .trailing
                            )
                        )
                        .frame(width: geometry.size.width * CGFloat(room.avgLightLevel) / 100, height: 8)
                }
            }
            .frame(height: 8)

            // Light Status
            HStack {
                Image(systemName: "lightbulb.fill")
                    .foregroundColor(lightColor)

                Text(room.avgLightLevel > 0 ? "\(room.avgLightLevel)%" : "Off")
                    .font(.system(size: TVDesign.bodySize))
                    .foregroundColor(.white.opacity(0.8))

                Spacer()
            }

            // Control Buttons
            HStack(spacing: 12) {
                RoomControlButton(icon: "lightbulb.max.fill", label: "Full", color: TVDesign.primaryColor) {
                    isChangingLights = true
                    await KagamiAPIService.shared.setLights(100, rooms: [room.id])
                    isChangingLights = false
                }

                RoomControlButton(icon: "lightbulb.min.fill", label: "Dim", color: TVDesign.warningColor) {
                    isChangingLights = true
                    await KagamiAPIService.shared.setLights(30, rooms: [room.id])
                    isChangingLights = false
                }

                RoomControlButton(icon: "lightbulb.slash.fill", label: "Off", color: .gray) {
                    isChangingLights = true
                    await KagamiAPIService.shared.setLights(0, rooms: [room.id])
                    isChangingLights = false
                }
            }
        }
        .padding(TVDesign.cardSpacing)
        .frame(minHeight: 250)
        .background(
            RoundedRectangle(cornerRadius: TVDesign.cardRadius)
                .fill(isFocused ? TVDesign.focusedBackground : TVDesign.cardBackground)
        )
        .overlay(
            RoundedRectangle(cornerRadius: TVDesign.cardRadius)
                .stroke(lightColor.opacity(isFocused ? 0.6 : 0.2), lineWidth: isFocused ? 3 : 1)
        )
        .scaleEffect(isFocused ? 1.03 : 1.0)
        .animation(TvMotion.card, value: isFocused)
        .focused($isFocused)
        .overlay {
            if isChangingLights {
                RoundedRectangle(cornerRadius: TVDesign.cardRadius)
                    .fill(Color.black.opacity(0.5))
                    .overlay {
                        ProgressView()
                            .scaleEffect(1.5)
                    }
            }
        }
        .accessibilityElement(children: .combine)
        .accessibilityLabel("\(room.name), \(room.floor)")
        .accessibilityValue(room.avgLightLevel > 0 ? "Lights at \(room.avgLightLevel) percent" : "Lights off")
        .accessibilityHint(room.occupied ? "Room is occupied" : "Room is empty")
    }
}

// MARK: - Room Control Button

struct RoomControlButton: View {
    let icon: String
    let label: String
    let color: Color
    let action: () async -> Void

    @FocusState private var isFocused: Bool

    var body: some View {
        Button {
            Task { await action() }
        } label: {
            VStack(spacing: 8) {
                Image(systemName: icon)
                    .font(.system(size: 24))
                    .foregroundColor(color)

                Text(label)
                    .font(.system(size: TVDesign.captionSize))
                    .foregroundColor(.white.opacity(0.8))
            }
            .frame(maxWidth: .infinity)
            .frame(height: 70)
            .background(
                RoundedRectangle(cornerRadius: TVDesign.buttonRadius)
                    .fill(isFocused ? color.opacity(0.3) : color.opacity(0.1))
            )
            .overlay(
                RoundedRectangle(cornerRadius: TVDesign.buttonRadius)
                    .stroke(color.opacity(isFocused ? 0.8 : 0.3), lineWidth: isFocused ? 2 : 1)
            )
            .scaleEffect(isFocused ? 1.05 : 1.0)
            .animation(TvMotion.button, value: isFocused)
        }
        .buttonStyle(.plain)
        .focused($isFocused)
        .accessibilityLabel(label)
        .accessibilityHint("Double click to set lights to \(label)")
        .accessibilityAddTraits(.isButton)
    }
}

// MARK: - Preview

#Preview {
    HomeView()
        .environmentObject(TVAppModel())
}

/*
 * Mirror
 * h(x) >= 0. Always.
 */
