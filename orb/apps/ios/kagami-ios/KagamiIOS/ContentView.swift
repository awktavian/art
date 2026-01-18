//
// ContentView.swift — Main App Content
//
// Kagami iOS — Primary navigation hub after authentication
//
// Colony: Crystal (e7) — Verification & Polish
//
// Accessibility (WCAG 2.1 AAA Target):
// - VoiceOver content descriptions for all interactive elements
// - Minimum 44pt touch targets
// - Color contrast ratio >= 7:1 for all text (AAA compliant)
// - Reduced motion support via accessibilityReduceMotion
// - Dynamic Type support (up to 200% scaling)
// - Live regions for status changes
// - Semantic headers for navigation
// - State-based accessibilityValue for interactive elements
// - VoiceOver announcements for async operations
//

import SwiftUI
import KagamiDesign

// MARK: - Content View

struct ContentView: View {
    @EnvironmentObject var appModel: AppModel
    @EnvironmentObject var deepLinkRouter: DeepLinkRouter
    @State private var selectedTab: Tab = .home
    @Environment(\.accessibilityReduceMotion) private var reduceMotion

    var body: some View {
        TabView(selection: $selectedTab) {
            HomeView()
                .tabItem {
                    Label("Home", systemImage: "house.fill")
                }
                .tag(Tab.home)
                .accessibilityIdentifier(AccessibilityIdentifiers.TabBar.home)

            RoomsView()
                .tabItem {
                    Label("Rooms", systemImage: "rectangle.grid.2x2.fill")
                }
                .tag(Tab.rooms)
                .accessibilityIdentifier(AccessibilityIdentifiers.TabBar.rooms)

            ScenesView()
                .tabItem {
                    Label("Scenes", systemImage: "sparkles")
                }
                .tag(Tab.scenes)
                .accessibilityIdentifier(AccessibilityIdentifiers.TabBar.scenes)

            SettingsView()
                .tabItem {
                    Label("Settings", systemImage: "gearshape.fill")
                }
                .tag(Tab.settings)
                .accessibilityIdentifier(AccessibilityIdentifiers.TabBar.settings)
        }
        .tint(.crystal)
        // Easter Egg: Konami Code → Fano Plane visualization
        .konamiCode()
        .onChange(of: deepLinkRouter.activeRoute) { _, route in
            handleDeepLink(route)
        }
        .alert(
            "Connection Error",
            isPresented: $appModel.showErrorAlert,
            presenting: appModel.currentError
        ) { _ in
            Button("Retry") {
                Task { await appModel.retryLastOperation() }
            }
            Button("Dismiss", role: .cancel) {
                appModel.clearError()
            }
        } message: { error in
            Text(error.localizedDescription)
        }
    }

    private func handleDeepLink(_ route: DeepLinkRoute?) {
        guard let route = route else { return }

        switch route {
        case .room:
            selectedTab = .rooms
        case .scene:
            selectedTab = .scenes
        case .settings:
            selectedTab = .settings
        case .hub, .camera, .cameras:
            selectedTab = .home
        case .command, .routine:
            selectedTab = .home
        }

        // Clear route after handling
        DispatchQueue.main.asyncAfter(deadline: .now() + 0.1) {
            deepLinkRouter.clearRoute()
        }
    }
}

// MARK: - Tab Definition

enum Tab: String, CaseIterable {
    case home
    case rooms
    case scenes
    case settings
}

// MARK: - Home View

struct HomeView: View {
    @EnvironmentObject var appModel: AppModel
    @State private var showVoiceCommand = false
    @Environment(\.accessibilityReduceMotion) private var reduceMotion

    var body: some View {
        NavigationStack {
            ScrollView {
                VStack(spacing: KagamiSpacing.lg) {
                    // Connection Status Card
                    ConnectionStatusCard(
                        isConnected: appModel.isConnected,
                        safetyScore: appModel.safetyScore
                    )
                    .slideUpEntrance(delay: 0)
                    .accessibilitySection(name: "Connection Status", id: "home.section.status")

                    // Quick Actions Grid
                    QuickActionsSection()
                        .slideUpEntrance(delay: 0.05)
                        .accessibilitySection(name: "Quick Actions", id: "home.section.quickActions")

                    // Active Scenes Section
                    ActiveScenesSection()
                        .slideUpEntrance(delay: 0.1)
                        .accessibilitySection(name: "Active Scenes", id: "home.section.scenes")

                    // Occupied Rooms Section
                    OccupiedRoomsSection(rooms: appModel.rooms.filter { $0.occupied })
                        .slideUpEntrance(delay: 0.15)
                        .accessibilitySection(name: "Occupied Rooms", id: "home.section.rooms")

                    // Safety Footer
                    SafetyFooter()
                        .slideUpEntrance(delay: 0.2)
                }
                .padding(.horizontal, KagamiSpacing.md)
                .padding(.vertical, KagamiSpacing.lg)
            }
            .background(
                ZStack {
                    Color.void.ignoresSafeArea()
                    CausticBackground()
                        .opacity(0.3)
                        .ignoresSafeArea()
                        .accessibilityHidden(true)
                }
            )
            .navigationTitle("Kagami")
            .toolbar {
                ToolbarItem(placement: .navigationBarTrailing) {
                    Button {
                        showVoiceCommand = true
                    } label: {
                        Image(systemName: "mic.fill")
                            .foregroundColor(.crystal)
                            .frame(minWidth: 44, minHeight: 44)  // Ensure 44pt touch target
                    }
                    .accessibilityLabel("Voice command")
                    .accessibilityHint("Opens voice control to speak commands to your home")
                }
            }
            .sheet(isPresented: $showVoiceCommand) {
                VoiceCommandView()
            }
            .refreshable {
                await appModel.refresh()
                // Announce refresh completion for VoiceOver users
                UIAccessibility.post(notification: .announcement, argument: "Home refreshed")
            }
        }
        .accessibilityIdentifier(AccessibilityIdentifiers.Home.view)
        .accessibilityAnnounceScreenChange("Kagami Home")
    }
}

// MARK: - Connection Status Card

struct ConnectionStatusCard: View {
    let isConnected: Bool
    let safetyScore: Double?

    var statusColor: Color {
        isConnected ? .safetyOk : .safetyViolation
    }

    var safetyColor: Color {
        Color.safetyColor(for: safetyScore)
    }

    private var safetyStatusDescription: String {
        guard let score = safetyScore else { return "unknown" }
        if score >= 0.5 { return "safe" }
        if score >= 0 { return "caution" }
        return "needs attention"
    }

    private var accessibilityDescription: String {
        let connectionPart = "Home Hub \(isConnected ? "connected" : "disconnected")"
        let safetyPart = "Safety status: \(safetyStatusDescription)"
        return "\(connectionPart). \(safetyPart)"
    }

    var body: some View {
        KagamiCard(accentColor: statusColor) {
            HStack(spacing: KagamiSpacing.md) {
                // Connection indicator
                VStack(alignment: .leading, spacing: KagamiSpacing.xs) {
                    HStack(spacing: KagamiSpacing.sm) {
                        Circle()
                            .fill(statusColor)
                            .frame(width: 10, height: 10)
                            .pulseEffect()
                            .accessibilityHidden(true)

                        Text(isConnected ? "Connected" : "Disconnected")
                            .font(KagamiFont.headline())
                            .foregroundColor(.accessibleTextPrimary)
                    }

                    // Jobs: Remove technical detail users don't need
                    Text("Home Hub")
                        .font(KagamiFont.caption())
                        .foregroundColor(.accessibleTextSecondary)
                }

                Spacer()

                // Safety score
                if let score = safetyScore {
                    VStack(alignment: .trailing, spacing: KagamiSpacing.xs) {
                        Text("Safety")
                            .font(KagamiFont.caption())
                            .foregroundColor(.accessibleTextSecondary)
                            .accessibilityHidden(true)

                        Text(String(format: "%.2f", score))
                            .font(KagamiFont.title2())
                            .foregroundColor(safetyColor)
                            .accessibilityHidden(true)
                    }
                }
            }
        }
        .accessibilityElement(children: .ignore)
        .accessibilityLabel(accessibilityDescription)
        .accessibilityValue(isConnected ? "Connected" : "Disconnected")
        .accessibilityAddTraits(.updatesFrequently)
    }
}

// MARK: - Quick Actions Section

struct QuickActionsSection: View {
    var body: some View {
        VStack(alignment: .leading, spacing: KagamiSpacing.sm) {
            Text("Quick Actions")
                .font(KagamiFont.headline())
                .foregroundColor(.accessibleTextSecondary)
                .padding(.horizontal, KagamiSpacing.xs)
                .accessibilityAddTraits(.isHeader)

            LazyVGrid(columns: [
                GridItem(.flexible(), spacing: KagamiSpacing.sm),
                GridItem(.flexible(), spacing: KagamiSpacing.sm)
            ], spacing: KagamiSpacing.sm) {
                QuickActionButton(
                    icon: "film.fill",
                    title: "Movie Mode",
                    color: .forge,
                    accessibilityHintText: "Dims lights, lowers TV, closes shades for movie watching",
                    action: { await KagamiAPIService.shared.executeScene("movie_mode") }
                )

                QuickActionButton(
                    icon: "moon.fill",
                    title: "Goodnight",
                    color: .flow,
                    accessibilityHintText: "Turns off all lights and locks all doors",
                    action: { await KagamiAPIService.shared.executeScene("goodnight") }
                )

                QuickActionButton(
                    icon: "lightbulb.fill",
                    title: "All Lights Off",
                    color: .beacon,
                    accessibilityHintText: "Turns off every light in the house",
                    action: { await KagamiAPIService.shared.setLights(0, rooms: nil) }
                )

                QuickActionButton(
                    icon: "lock.fill",
                    title: "Lock All",
                    color: .crystal,
                    accessibilityHintText: "Locks all exterior doors",
                    action: { await KagamiAPIService.shared.lockAll() }
                )
            }
        }
        .accessibilityElement(children: .contain)
        .accessibilityLabel("Quick Actions")
    }
}

struct QuickActionButton: View {
    let icon: String
    let title: String
    let color: Color
    var accessibilityHintText: String = ""
    let action: () async -> Void

    @State private var isExecuting = false
    @State private var showSuccess = false

    private var accessibilityStateValue: String {
        if isExecuting {
            return "Activating"
        } else if showSuccess {
            return "Activated successfully"
        } else {
            return "Ready"
        }
    }

    var body: some View {
        Button {
            guard !isExecuting else { return }
            // Ive: "Every tap should be an event" — haptic feedback
            let generator = UIImpactFeedbackGenerator(style: .medium)
            generator.impactOccurred()

            isExecuting = true
            // Announce state change for VoiceOver users
            UIAccessibility.post(notification: .announcement, argument: "Activating \(title)")

            Task {
                await action()
                await MainActor.run {
                    // Success haptic
                    let successGenerator = UINotificationFeedbackGenerator()
                    successGenerator.notificationOccurred(.success)
                    showSuccess = true
                    isExecuting = false
                    // Announce completion
                    UIAccessibility.post(notification: .announcement, argument: "\(title) activated")
                }
            }
        } label: {
            VStack(spacing: KagamiSpacing.sm) {
                ZStack {
                    Circle()
                        .fill(color.opacity(0.15))  // Match Android opacity
                        .frame(width: 48, height: 48)

                    if isExecuting {
                        ProgressView()
                            .progressViewStyle(CircularProgressViewStyle(tint: color))
                            .accessibilityHidden(true)
                    } else {
                        Image(systemName: icon)
                            .font(.title2)
                            .foregroundColor(color)
                            .accessibilityHidden(true)
                    }
                }
                .prismGlow(color: color, radius: isExecuting ? 12 : 0, animated: isExecuting)  // Unified glow radius

                Text(title)
                    .font(KagamiFont.caption())
                    .foregroundColor(.accessibleTextPrimary)
                    .lineLimit(1)
            }
            .frame(maxWidth: .infinity)
            .frame(minHeight: 88)
            .padding(KagamiSpacing.sm)
        }
        .buttonStyle(.plain)
        .background(
            RoundedRectangle(cornerRadius: KagamiRadius.md)
                .fill(.ultraThinMaterial)
        )
        .overlay(
            RoundedRectangle(cornerRadius: KagamiRadius.md)
                .stroke(color.opacity(0.2), lineWidth: 1)
        )
        .chromaticPulse(isTriggered: $showSuccess, color: color)
        .pressEffect()  // Ive: Add press feedback
        .accessibilityElement(children: .ignore)
        .accessibilityLabel(title)
        .accessibilityHint(accessibilityHintText.isEmpty ? "Double tap to activate" : accessibilityHintText)
        .accessibilityValue(accessibilityStateValue)
        .accessibilityAddTraits(.isButton)
    }
}

// MARK: - Active Scenes Section

struct ActiveScenesSection: View {
    @State private var movieModeActive = false

    var body: some View {
        VStack(alignment: .leading, spacing: KagamiSpacing.sm) {
            Text("Active Scenes")
                .font(KagamiFont.headline())
                .foregroundColor(.accessibleTextSecondary)
                .padding(.horizontal, KagamiSpacing.xs)
                .accessibilityAddTraits(.isHeader)

            if movieModeActive {
                ActiveSceneCard(
                    icon: "film.fill",
                    title: "Movie Mode",
                    subtitle: "Active since 7:30 PM",
                    color: .forge,
                    onDeactivate: {
                        Task {
                            await KagamiAPIService.shared.executeScene("exit_movie_mode")
                            movieModeActive = false
                            // Announce deactivation
                            UIAccessibility.post(notification: .announcement, argument: "Movie Mode deactivated")
                        }
                    }
                )
            } else {
                KagamiCard(accentColor: .voidLight) {
                    HStack {
                        Image(systemName: "sparkles")
                            .foregroundColor(.accessibleTextTertiary)
                            .accessibilityHidden(true)
                        Text("No active scenes")
                            .font(KagamiFont.body())
                            .foregroundColor(.accessibleTextSecondary)
                        Spacer()
                    }
                }
                .accessibilityElement(children: .ignore)
                .accessibilityLabel("No active scenes")
            }
        }
        .accessibilityElement(children: .contain)
    }
}

struct ActiveSceneCard: View {
    let icon: String
    let title: String
    let subtitle: String
    let color: Color
    let onDeactivate: () -> Void

    var body: some View {
        KagamiCard(accentColor: color) {
            HStack(spacing: KagamiSpacing.md) {
                ZStack {
                    Circle()
                        .fill(color.opacity(0.2))
                        .frame(width: 44, height: 44)

                    Image(systemName: icon)
                        .font(.title3)
                        .foregroundColor(color)
                }
                .prismGlow(color: color, radius: 12, animated: true)
                .accessibilityHidden(true)

                VStack(alignment: .leading, spacing: KagamiSpacing.xs) {
                    Text(title)
                        .font(KagamiFont.headline())
                        .foregroundColor(.accessibleTextPrimary)

                    Text(subtitle)
                        .font(KagamiFont.caption())
                        .foregroundColor(.accessibleTextSecondary)
                }
                .accessibilityElement(children: .combine)

                Spacer()

                Button {
                    onDeactivate()
                } label: {
                    Image(systemName: "xmark.circle.fill")
                        .font(.title2)
                        .foregroundColor(.accessibleTextTertiary)
                        .frame(minWidth: 44, minHeight: 44)  // Ensure 44pt touch target
                }
                .accessibilityLabel("Deactivate \(title)")
                .accessibilityHint("Double tap to turn off \(title)")
            }
        }
        .spectralDiscovery()
        .accessibilityElement(children: .contain)
        .accessibilityLabel("\(title), \(subtitle)")
        .accessibilityValue("Active")
    }
}

// MARK: - Occupied Rooms Section

struct OccupiedRoomsSection: View {
    let rooms: [RoomModel]

    var body: some View {
        VStack(alignment: .leading, spacing: KagamiSpacing.sm) {
            HStack {
                Text("Occupied Rooms")
                    .font(KagamiFont.headline())
                    .foregroundColor(.accessibleTextSecondary)
                    .accessibilityAddTraits(.isHeader)

                Spacer()

                if !rooms.isEmpty {
                    Text("\(rooms.count)")
                        .font(KagamiFont.caption())
                        .foregroundColor(.grove)
                        .padding(.horizontal, KagamiSpacing.sm)
                        .padding(.vertical, KagamiSpacing.xs)
                        .background(Color.grove.opacity(0.2))
                        .cornerRadius(KagamiRadius.full)
                        .accessibilityHidden(true)  // Count is announced in header
                }
            }
            .padding(.horizontal, KagamiSpacing.xs)
            .accessibilityElement(children: .combine)
            .accessibilityLabel("Occupied Rooms, \(rooms.count) \(rooms.count == 1 ? "room" : "rooms")")

            if rooms.isEmpty {
                KagamiCard(accentColor: .voidLight) {
                    HStack {
                        Image(systemName: "person.slash")
                            .foregroundColor(.accessibleTextTertiary)
                            .accessibilityHidden(true)
                        Text("No rooms currently occupied")
                            .font(KagamiFont.body())
                            .foregroundColor(.accessibleTextSecondary)
                        Spacer()
                    }
                }
                .accessibilityElement(children: .ignore)
                .accessibilityLabel("No rooms currently occupied")
            } else {
                ForEach(rooms) { room in
                    OccupiedRoomCard(room: room)
                }
            }
        }
        .accessibilityElement(children: .contain)
    }
}

struct OccupiedRoomCard: View {
    let room: RoomModel

    private var accessibilityDescription: String {
        var parts: [String] = [room.name, room.floor]
        if room.avgLightLevel > 0 {
            parts.append("Lights at \(room.avgLightLevel) percent")
        } else {
            parts.append("Lights off")
        }
        parts.append("Occupied")
        return parts.joined(separator: ", ")
    }

    var body: some View {
        KagamiCard(accentColor: .grove) {
            HStack(spacing: KagamiSpacing.md) {
                // Room icon with presence indicator
                ZStack {
                    Circle()
                        .fill(Color.grove.opacity(0.2))
                        .frame(width: 44, height: 44)

                    Image(systemName: "person.fill")
                        .font(.title3)
                        .foregroundColor(.grove)
                }
                .accessibilityHidden(true)

                VStack(alignment: .leading, spacing: KagamiSpacing.xs) {
                    Text(room.name)
                        .font(KagamiFont.headline())
                        .foregroundColor(.accessibleTextPrimary)

                    HStack(spacing: KagamiSpacing.sm) {
                        // Light status
                        if room.avgLightLevel > 0 {
                            HStack(spacing: KagamiSpacing.xs) {
                                Image(systemName: "lightbulb.fill")
                                    .font(.caption)
                                Text("\(room.avgLightLevel)%")
                                    .font(KagamiFont.caption())
                            }
                            .foregroundColor(.beacon)
                            .accessibilityHidden(true)
                        }

                        Text(room.floor)
                            .font(KagamiFont.caption())
                            .foregroundColor(.accessibleTextSecondary)
                            .accessibilityHidden(true)
                    }
                }

                Spacer()

                // Navigation indicator
                VStack(alignment: .trailing, spacing: KagamiSpacing.xs) {
                    Image(systemName: "chevron.right")
                        .font(.caption)
                        .foregroundColor(.accessibleTextTertiary)
                }
                .accessibilityHidden(true)
            }
        }
        .accessibilityElement(children: .ignore)
        .accessibilityLabel(accessibilityDescription)
        .accessibilityHint("Double tap to view room details")
        .accessibilityAddTraits(.isButton)
    }
}

// MARK: - Safety Footer
// Jobs: "h(x) >= 0 is engineer-speak. Make it beautiful or remove it."

struct SafetyFooter: View {
    var body: some View {
        VStack(spacing: KagamiSpacing.sm) {
            Divider()
                .background(Color.white.opacity(0.08))

            HStack(spacing: KagamiSpacing.xs) {
                Image(systemName: "checkmark.shield.fill")
                    .font(.caption)
                    .foregroundColor(.safetyOk.opacity(0.6))
                Text("Protected")
                    .font(KagamiFont.caption())
                    .foregroundColor(.safetyOk.opacity(0.6))
            }
            .frame(maxWidth: .infinity, alignment: .center)
        }
        .padding(.top, KagamiSpacing.md)
        .accessibilityLabel("System is protected and operating safely")
    }
}

// MARK: - Onboarding View Placeholder

struct OnboardingView: View {
    @Binding var hasCompletedOnboarding: Bool

    var body: some View {
        OnboardingContainerView(hasCompletedOnboarding: $hasCompletedOnboarding)
    }
}

// MARK: - AppModel Extension

extension AppModel {
    /// Number of household members (placeholder for UI)
    var householdMemberCount: Int? {
        // TODO: Fetch from API
        return 2
    }
}

// MARK: - Preview

#Preview("Content View") {
    ContentView()
        .environmentObject(AppModel())
        .environmentObject(DeepLinkRouter())
        .preferredColorScheme(.dark)
}

#Preview("Home View") {
    HomeView()
        .environmentObject(AppModel())
        .preferredColorScheme(.dark)
}

/*
 * 鏡
 * h(x) >= 0. Always.
 */
