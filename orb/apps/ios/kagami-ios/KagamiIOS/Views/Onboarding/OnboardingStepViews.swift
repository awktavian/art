//
// OnboardingStepViews.swift — Individual Step Views
//
// Colony: Beacon (e5) — Planning
//
// Contains the individual step views for onboarding:
//   - WelcomeStepView
//   - ServerStepView
//   - IntegrationStepView
//   - RoomsStepView
//   - PermissionsStepView
//   - CompletionStepView
//
// h(x) >= 0. Always.
//

import SwiftUI
import KagamiDesign

// MARK: - Step 1: Welcome

struct WelcomeStepView: View {
    @State private var showKanji = false
    @State private var showTitle = false
    @State private var showSubtitle = false
    @State private var showFeatures = false

    @Environment(\.accessibilityReduceMotion) var reduceMotion
    @EnvironmentObject var appModel: AppModel

    /// Skip directly to demo mode in 2 taps
    private func skipToDemo() {
        // Set demo mode
        UserDefaults.standard.set(true, forKey: "isDemoMode")
        UserDefaults.standard.set(true, forKey: "hasCompletedOnboarding")

        // Update app model
        appModel.isDemoMode = true

        // Track analytics
        KagamiAnalytics.shared.track(.demoModeActivated, properties: [
            "source": "welcome_skip_button"
        ])

        // Haptic feedback
        UIImpactFeedbackGenerator(style: .medium).impactOccurred()
    }

    var body: some View {
        ScrollView {
            VStack(spacing: 32) {
                Spacer(minLength: 40)

                // Kanji logo with glow
                Text("\u{93E1}")  // Mirror kanji
                    .font(.system(size: 100))
                    .foregroundColor(.crystal.opacity(0.9))
                    .scaleEffect(showKanji || reduceMotion ? 1 : 0.5)
                    .opacity(showKanji || reduceMotion ? 1 : 0)
                    .shadow(color: .crystal.opacity(0.5), radius: 20, x: 0, y: 0)
                    .accessibilityLabel("Kagami, mirror kanji character")
                    .accessibilityIdentifier(AccessibilityIdentifiers.Onboarding.welcomeKanji)

                // Title
                VStack(spacing: 12) {
                    Text("Welcome to Kagami")
                        .font(KagamiFont.largeTitle())
                        .foregroundColor(.accessibleTextPrimary)
                        .opacity(showTitle || reduceMotion ? 1 : 0)
                        .offset(y: showTitle || reduceMotion ? 0 : 20)
                        .accessibilityIdentifier(AccessibilityIdentifiers.Onboarding.welcomeTitle)

                    Text("The Mirror Operating System")
                        .font(KagamiFont.title3())
                        .foregroundColor(.accessibleTextSecondary)
                        .opacity(showSubtitle || reduceMotion ? 1 : 0)
                        .accessibilityIdentifier(AccessibilityIdentifiers.Onboarding.welcomeSubtitle)
                }

                // Features list
                VStack(alignment: .leading, spacing: 16) {
                    WelcomeFeatureRow(
                        icon: "house.fill",
                        title: "Smart Home",
                        description: "Control lights, shades, climate, and more",
                        color: .forge
                    )

                    WelcomeFeatureRow(
                        icon: "mic.fill",
                        title: "Voice Control",
                        description: "Natural language commands like \"Movie mode\"",
                        color: .nexus
                    )

                    WelcomeFeatureRow(
                        icon: "sparkles",
                        title: "Automation",
                        description: "Scenes and routines that adapt to you",
                        color: .crystal
                    )

                    WelcomeFeatureRow(
                        icon: "shield.checkered",
                        title: "Safety First",
                        description: "h(x) >= 0. Every action is safety-checked",
                        color: .safetyOk
                    )
                }
                .padding(.horizontal, 16)
                .opacity(showFeatures || reduceMotion ? 1 : 0)
                .offset(y: showFeatures || reduceMotion ? 0 : 20)
                .accessibilityIdentifier(AccessibilityIdentifiers.Onboarding.welcomeFeatureList)

                // Skip & Demo Button
                Button {
                    skipToDemo()
                } label: {
                    HStack {
                        Image(systemName: "play.circle")
                        Text("Skip & Demo")
                    }
                    .font(KagamiFont.body(weight: .medium))
                    .foregroundColor(.crystal)
                    .padding(.vertical, 12)
                    .padding(.horizontal, 24)
                    .background(Color.crystal.opacity(0.15))
                    .cornerRadius(KagamiRadius.md)
                }
                .accessibilityLabel("Skip to demo mode")
                .accessibilityHint("Skip onboarding and explore with sample data")
                .accessibilityIdentifier(AccessibilityIdentifiers.Onboarding.skipToDemoButton)

                Spacer(minLength: 40)
            }
            .padding(.horizontal, 24)
        }
        .accessibilityIdentifier(AccessibilityIdentifiers.Onboarding.step(0))
        .onAppear {
            KagamiAnalytics.shared.track(.onboardingStarted)
            KagamiAnalytics.shared.trackOnboardingStep(0, name: "welcome")

            guard !reduceMotion else { return }

            withAnimation(.easeOut(duration: KagamiMotion.slow)) {
                showKanji = true
            }
            withAnimation(.easeOut(duration: KagamiMotion.normal).delay(0.2)) {
                showTitle = true
            }
            withAnimation(.easeOut(duration: KagamiMotion.normal).delay(0.3)) {
                showSubtitle = true
            }
            withAnimation(.easeOut(duration: KagamiMotion.normal).delay(0.4)) {
                showFeatures = true
            }
        }
    }
}

struct WelcomeFeatureRow: View {
    let icon: String
    let title: String
    let description: String
    let color: Color

    var body: some View {
        HStack(alignment: .top, spacing: 16) {
            Image(systemName: icon)
                .font(.title2)
                .foregroundColor(color)
                .frame(width: 32)

            VStack(alignment: .leading, spacing: 4) {
                Text(title)
                    .font(KagamiFont.headline())
                    .foregroundColor(.accessibleTextPrimary)

                Text(description)
                    .font(KagamiFont.subheadline())
                    .foregroundColor(.accessibleTextSecondary)
            }
        }
        .accessibilityElement(children: .combine)
        .accessibilityLabel("\(title). \(description)")
    }
}

// MARK: - Step 2: Server Connection

struct ServerStepView: View {
    @ObservedObject var stateManager: OnboardingStateManager
    @State private var showManualEntry = false

    var body: some View {
        ScrollView {
            VStack(spacing: 24) {
                // Header
                VStack(spacing: 8) {
                    Image(systemName: "antenna.radiowaves.left.and.right")
                        .font(.system(size: 48))
                        .foregroundColor(.nexus)

                    Text("Connect to Kagami")
                        .font(KagamiFont.title2())
                        .foregroundColor(.accessibleTextPrimary)

                    Text("Find your Kagami server on the network")
                        .font(KagamiFont.subheadline())
                        .foregroundColor(.accessibleTextSecondary)
                        .multilineTextAlignment(.center)
                }
                .padding(.top, 24)

                // Discovery section
                VStack(spacing: 16) {
                    // Discover button
                    Button {
                        stateManager.startServerDiscovery()
                    } label: {
                        HStack {
                            if stateManager.isDiscovering {
                                ProgressView()
                                    .tint(.accessibleTextPrimary)
                            } else {
                                Image(systemName: "magnifyingglass")
                            }
                            Text(stateManager.isDiscovering ? "Searching..." : "Search Network")
                        }
                        .font(KagamiFont.body(weight: .medium))
                        .frame(maxWidth: .infinity)
                        .padding(.vertical, 14)
                        .background(Color.voidLight)
                        .foregroundColor(.accessibleTextPrimary)
                        .cornerRadius(KagamiRadius.md)
                        .overlay(
                            RoundedRectangle(cornerRadius: KagamiRadius.md)
                                .stroke(Color.nexus.opacity(0.5), lineWidth: 1)
                        )
                    }
                    .disabled(stateManager.isDiscovering)
                    .accessibleButton(
                        label: "Search for servers",
                        hint: "Scans your local network for Kagami servers"
                    )
                    .accessibilityIdentifier(AccessibilityIdentifiers.Onboarding.serverSearchButton)

                    // Discovered servers
                    if !stateManager.discoveredServers.isEmpty {
                        VStack(alignment: .leading, spacing: 12) {
                            Text("Found Servers")
                                .font(KagamiFont.caption())
                                .foregroundColor(.accessibleTextTertiary)

                            ForEach(stateManager.discoveredServers) { server in
                                ServerCard(
                                    server: server,
                                    isSelected: stateManager.selectedServer == server,
                                    onSelect: {
                                        stateManager.selectedServer = server
                                        stateManager.serverURL = server.url
                                    }
                                )
                            }
                        }
                    }

                    // Manual entry toggle
                    Button {
                        withAnimation(KagamiMotion.smooth) {
                            showManualEntry.toggle()
                        }
                    } label: {
                        HStack {
                            Text("Enter manually")
                                .font(KagamiFont.subheadline())
                            Image(systemName: showManualEntry ? "chevron.up" : "chevron.down")
                                .font(.caption)
                        }
                        .foregroundColor(.accessibleTextSecondary)
                    }

                    if showManualEntry {
                        VStack(alignment: .leading, spacing: 8) {
                            Text("Server URL")
                                .font(KagamiFont.caption())
                                .foregroundColor(.accessibleTextTertiary)

                            TextField("https://api.awkronos.com", text: $stateManager.serverURL)
                                .textFieldStyle(KagamiTextFieldStyle())
                                .autocapitalization(.none)
                                .disableAutocorrection(true)
                                .keyboardType(.URL)
                                .accessibilityLabel("Server URL")
                                .accessibilityIdentifier(AccessibilityIdentifiers.Onboarding.serverURLField)
                        }
                    }

                    // Connection status
                    if stateManager.isServerConnected {
                        HStack {
                            Image(systemName: "checkmark.circle.fill")
                                .foregroundColor(.safetyOk)
                            Text("Connected to \(stateManager.serverURL)")
                                .font(KagamiFont.caption())
                                .foregroundColor(.safetyOk)
                        }
                        .padding(.vertical, 8)
                        .accessibilityIdentifier(AccessibilityIdentifiers.Onboarding.serverConnectionStatus)
                    }

                    if let error = stateManager.connectionError {
                        HStack {
                            Image(systemName: "exclamationmark.triangle.fill")
                                .foregroundColor(.safetyViolation)
                            Text(error)
                                .font(KagamiFont.caption())
                                .foregroundColor(.safetyViolation)
                        }
                        .padding(.vertical, 8)
                    }
                }
                .padding(.horizontal, 16)

                // Demo mode option
                VStack(spacing: 12) {
                    HStack {
                        Rectangle()
                            .fill(Color.accessibleTextTertiary.opacity(0.3))
                            .frame(height: 1)
                        Text("or")
                            .font(KagamiFont.caption())
                            .foregroundColor(.accessibleTextTertiary)
                        Rectangle()
                            .fill(Color.accessibleTextTertiary.opacity(0.3))
                            .frame(height: 1)
                    }

                    Button {
                        stateManager.startDemoMode()
                    } label: {
                        HStack {
                            Image(systemName: "play.circle")
                            Text("Try Demo Mode")
                        }
                        .font(KagamiFont.body(weight: .medium))
                        .foregroundColor(.crystal)
                    }
                    .accessibleButton(
                        label: "Try demo mode",
                        hint: "Explore Kagami with sample data, no server required"
                    )
                    .accessibilityIdentifier(AccessibilityIdentifiers.Onboarding.serverDemoButton)

                    Text("Explore with sample data, no server needed")
                        .font(KagamiFont.caption())
                        .foregroundColor(.accessibleTextTertiary)
                }
                .padding(.top, 16)

                Spacer(minLength: 40)
            }
            .padding(.horizontal, 24)
        }
        .onAppear {
            KagamiAnalytics.shared.trackOnboardingStep(1, name: "server")
        }
    }
}

struct ServerCard: View {
    let server: OnboardingServer
    let isSelected: Bool
    let onSelect: () -> Void

    var body: some View {
        Button(action: onSelect) {
            HStack(spacing: 12) {
                Image(systemName: server.isSecure ? "lock.fill" : "antenna.radiowaves.left.and.right")
                    .foregroundColor(isSelected ? .crystal : .accessibleTextSecondary)
                    .frame(width: 24)

                VStack(alignment: .leading, spacing: 2) {
                    Text(server.name)
                        .font(KagamiFont.body(weight: .medium))
                        .foregroundColor(.accessibleTextPrimary)

                    Text(server.url)
                        .font(KagamiFont.caption())
                        .foregroundColor(.accessibleTextSecondary)
                }

                Spacer()

                Image(systemName: isSelected ? "checkmark.circle.fill" : "circle")
                    .foregroundColor(isSelected ? .crystal : .accessibleTextTertiary)
            }
            .padding(12)
            .background(isSelected ? Color.crystal.opacity(0.15) : Color.voidLight)
            .cornerRadius(KagamiRadius.md)
            .overlay(
                RoundedRectangle(cornerRadius: KagamiRadius.md)
                    .stroke(isSelected ? Color.crystal : Color.clear, lineWidth: 1)
            )
        }
        .buttonStyle(.plain)
        .accessibilityLabel("\(server.name) at \(server.url)")
        .accessibilityAddTraits(isSelected ? .isSelected : [])
    }
}

// MARK: - Step 3: Integration Selection

struct IntegrationStepView: View {
    @ObservedObject var stateManager: OnboardingStateManager
    @State private var showCredentialsSheet = false

    private let columns = [
        GridItem(.flexible()),
        GridItem(.flexible())
    ]

    var body: some View {
        ScrollView {
            VStack(spacing: 24) {
                // Header
                VStack(spacing: 8) {
                    Image(systemName: "house.fill")
                        .font(.system(size: 48))
                        .foregroundColor(.forge)

                    Text("Connect Smart Home")
                        .font(KagamiFont.title2())
                        .foregroundColor(.accessibleTextPrimary)

                    Text("Select your smart home system")
                        .font(KagamiFont.subheadline())
                        .foregroundColor(.accessibleTextSecondary)
                }
                .padding(.top, 24)

                // Demo mode notice
                if stateManager.isDemoMode {
                    HStack {
                        Image(systemName: "info.circle")
                            .foregroundColor(.crystal)
                        Text("Demo mode: Skip this step to use sample data")
                            .font(KagamiFont.caption())
                            .foregroundColor(.accessibleTextSecondary)
                    }
                    .padding(12)
                    .background(Color.crystal.opacity(0.1))
                    .cornerRadius(KagamiRadius.sm)
                }

                // Integration grid
                LazyVGrid(columns: columns, spacing: 12) {
                    ForEach(SmartHomeIntegration.allCases) { integration in
                        IntegrationCard(
                            integration: integration,
                            isSelected: stateManager.selectedIntegration == integration,
                            isConnected: stateManager.integrationConnected && stateManager.selectedIntegration == integration,
                            onSelect: {
                                stateManager.selectedIntegration = integration
                                KagamiAnalytics.shared.track(.integrationSelected, properties: [
                                    "integration_type": integration.rawValue
                                ])
                                if integration.requiresCredentials {
                                    showCredentialsSheet = true
                                }
                            }
                        )
                    }
                }

                // Connection status
                if stateManager.integrationConnected {
                    HStack {
                        Image(systemName: "checkmark.circle.fill")
                            .foregroundColor(.safetyOk)
                        Text("Connected to \(stateManager.selectedIntegration?.displayName ?? "integration")")
                            .font(KagamiFont.subheadline())
                            .foregroundColor(.safetyOk)
                    }
                    .padding(.vertical, 8)
                }

                if let error = stateManager.integrationError {
                    HStack {
                        Image(systemName: "exclamationmark.triangle.fill")
                            .foregroundColor(.safetyViolation)
                        Text(error)
                            .font(KagamiFont.caption())
                            .foregroundColor(.safetyViolation)
                    }
                    .padding(.vertical, 8)
                }

                Spacer(minLength: 40)
            }
            .padding(.horizontal, 24)
        }
        .sheet(isPresented: $showCredentialsSheet) {
            if let integration = stateManager.selectedIntegration {
                IntegrationCredentialsSheet(
                    integration: integration,
                    stateManager: stateManager,
                    onDismiss: { showCredentialsSheet = false }
                )
            }
        }
        .onAppear {
            KagamiAnalytics.shared.trackOnboardingStep(2, name: "integration")
        }
    }
}

struct IntegrationCard: View {
    let integration: SmartHomeIntegration
    let isSelected: Bool
    let isConnected: Bool
    let onSelect: () -> Void

    var body: some View {
        Button(action: onSelect) {
            VStack(spacing: 12) {
                ZStack {
                    Image(systemName: integration.icon)
                        .font(.title)
                        .foregroundColor(isSelected ? integration.colonyColor : .accessibleTextSecondary)

                    if isConnected {
                        Image(systemName: "checkmark.circle.fill")
                            .font(.caption)
                            .foregroundColor(.safetyOk)
                            .offset(x: 16, y: -16)
                    }
                }

                Text(integration.displayName)
                    .font(KagamiFont.body(weight: .medium))
                    .foregroundColor(.accessibleTextPrimary)

                Text(integration.description)
                    .font(KagamiFont.caption())
                    .foregroundColor(.accessibleTextSecondary)
                    .lineLimit(1)
            }
            .frame(maxWidth: .infinity)
            .padding(16)
            .background(isSelected ? integration.colonyColor.opacity(0.15) : Color.voidLight)
            .cornerRadius(KagamiRadius.md)
            .overlay(
                RoundedRectangle(cornerRadius: KagamiRadius.md)
                    .stroke(isSelected ? integration.colonyColor : Color.clear, lineWidth: 2)
            )
        }
        .buttonStyle(.plain)
        .accessibilityLabel("\(integration.displayName). \(integration.description)")
        .accessibilityAddTraits(isSelected ? .isSelected : [])
    }
}

// MARK: - Step 4: Rooms

struct RoomsStepView: View {
    @ObservedObject var stateManager: OnboardingStateManager

    var body: some View {
        ScrollView {
            VStack(spacing: 24) {
                // Header
                VStack(spacing: 8) {
                    Image(systemName: "square.grid.2x2")
                        .font(.system(size: 48))
                        .foregroundColor(.grove)

                    Text("Configure Rooms")
                        .font(KagamiFont.title2())
                        .foregroundColor(.accessibleTextPrimary)

                    Text("Select which rooms to control")
                        .font(KagamiFont.subheadline())
                        .foregroundColor(.accessibleTextSecondary)
                }
                .padding(.top, 24)

                // Loading state
                if stateManager.isLoadingRooms {
                    ProgressView()
                        .padding(40)
                }

                // Rooms list
                if !stateManager.discoveredRooms.isEmpty {
                    VStack(spacing: 12) {
                        // Select all toggle
                        Button {
                            let allEnabled = stateManager.discoveredRooms.allSatisfy { $0.isEnabled }
                            for i in stateManager.discoveredRooms.indices {
                                stateManager.discoveredRooms[i].isEnabled = !allEnabled
                            }
                        } label: {
                            HStack {
                                Image(systemName: stateManager.discoveredRooms.allSatisfy { $0.isEnabled } ? "checkmark.square.fill" : "square")
                                    .foregroundColor(.grove)
                                Text("Select All")
                                    .font(KagamiFont.body())
                                    .foregroundColor(.accessibleTextPrimary)
                                Spacer()
                            }
                            .padding(.vertical, 8)
                        }

                        Divider()
                            .background(Color.accessibleTextTertiary.opacity(0.3))

                        // Room cards grouped by floor
                        ForEach(groupedRooms.keys.sorted(), id: \.self) { floor in
                            VStack(alignment: .leading, spacing: 8) {
                                Text(floor)
                                    .font(KagamiFont.caption())
                                    .foregroundColor(.accessibleTextTertiary)
                                    .padding(.top, 8)

                                ForEach(groupedRooms[floor] ?? []) { room in
                                    if let index = stateManager.discoveredRooms.firstIndex(where: { $0.id == room.id }) {
                                        RoomToggleCard(room: $stateManager.discoveredRooms[index])
                                    }
                                }
                            }
                        }
                    }
                } else if !stateManager.isLoadingRooms {
                    // No rooms found
                    VStack(spacing: 16) {
                        Image(systemName: "questionmark.folder")
                            .font(.system(size: 48))
                            .foregroundColor(.accessibleTextTertiary)

                        Text("No rooms discovered")
                            .font(KagamiFont.body())
                            .foregroundColor(.accessibleTextSecondary)

                        if !stateManager.isDemoMode && !stateManager.integrationConnected {
                            Text("Connect a smart home integration first")
                                .font(KagamiFont.caption())
                                .foregroundColor(.accessibleTextTertiary)
                        }

                        Button {
                            Task {
                                await stateManager.loadRooms()
                            }
                        } label: {
                            HStack {
                                Image(systemName: "arrow.clockwise")
                                Text("Refresh")
                            }
                            .font(KagamiFont.body())
                            .foregroundColor(.grove)
                        }
                    }
                    .padding(40)
                }

                Spacer(minLength: 40)
            }
            .padding(.horizontal, 24)
        }
        .onAppear {
            KagamiAnalytics.shared.trackOnboardingStep(3, name: "rooms")
            if stateManager.discoveredRooms.isEmpty {
                Task {
                    await stateManager.loadRooms()
                }
            }
        }
    }

    private var groupedRooms: [String: [OnboardingRoom]] {
        Dictionary(grouping: stateManager.discoveredRooms) { $0.floor ?? "Other" }
    }
}

struct RoomToggleCard: View {
    @Binding var room: OnboardingRoom

    var body: some View {
        HStack(spacing: 12) {
            Button {
                room.isEnabled.toggle()
            } label: {
                Image(systemName: room.isEnabled ? "checkmark.square.fill" : "square")
                    .font(.title3)
                    .foregroundColor(room.isEnabled ? .grove : .accessibleTextTertiary)
            }

            VStack(alignment: .leading, spacing: 4) {
                Text(room.name)
                    .font(KagamiFont.body(weight: .medium))
                    .foregroundColor(.accessibleTextPrimary)

                HStack(spacing: 8) {
                    if room.hasLights {
                        Image(systemName: "lightbulb.fill")
                            .font(.caption2)
                            .foregroundColor(.beacon)
                    }
                    if room.hasShades {
                        Image(systemName: "blinds.vertical.closed")
                            .font(.caption2)
                            .foregroundColor(.flow)
                    }
                    if room.hasClimate {
                        Image(systemName: "thermometer")
                            .font(.caption2)
                            .foregroundColor(.spark)
                    }
                    if room.hasAudio {
                        Image(systemName: "speaker.wave.2.fill")
                            .font(.caption2)
                            .foregroundColor(.nexus)
                    }
                }
            }

            Spacer()
        }
        .padding(12)
        .background(room.isEnabled ? Color.grove.opacity(0.1) : Color.voidLight)
        .cornerRadius(KagamiRadius.sm)
        .accessibilityElement(children: .combine)
        .accessibilityLabel("\(room.name), \(room.isEnabled ? "enabled" : "disabled")")
        .accessibilityHint("Double tap to toggle")
    }
}

// MARK: - Step 5: Permissions

struct PermissionsStepView: View {
    @ObservedObject var stateManager: OnboardingStateManager

    var body: some View {
        ScrollView {
            VStack(spacing: 24) {
                // Header
                VStack(spacing: 8) {
                    Image(systemName: "checkmark.shield")
                        .font(.system(size: 48))
                        .foregroundColor(.beacon)

                    Text("Permissions")
                        .font(KagamiFont.title2())
                        .foregroundColor(.accessibleTextPrimary)

                    Text("Enable features for the best experience")
                        .font(KagamiFont.subheadline())
                        .foregroundColor(.accessibleTextSecondary)
                }
                .padding(.top, 24)

                // Permissions list
                VStack(spacing: 12) {
                    ForEach(stateManager.permissions) { permission in
                        OnboardingPermissionCard(
                            permission: permission,
                            onRequest: {
                                Task {
                                    await stateManager.requestPermission(permission.id)
                                }
                            }
                        )
                    }
                }

                // Request all button
                Button {
                    Task {
                        await stateManager.requestAllPermissions()
                    }
                } label: {
                    HStack {
                        Image(systemName: "checkmark.circle")
                        Text("Enable All")
                    }
                    .font(KagamiFont.body(weight: .medium))
                    .frame(maxWidth: .infinity)
                    .padding(.vertical, 14)
                    .background(Color.beacon.opacity(0.2))
                    .foregroundColor(.beacon)
                    .cornerRadius(KagamiRadius.md)
                }
                .accessibleButton(label: "Enable all permissions", hint: "Request all permissions at once")
                .padding(.top, 8)

                // Privacy note
                VStack(spacing: 8) {
                    Text("h(x) >= 0. Always.")
                        .font(KagamiFont.caption())
                        .foregroundColor(.crystal.opacity(0.7))

                    Text("Your data stays on your server. Kagami never sends personal data to the cloud.")
                        .font(KagamiFont.caption())
                        .foregroundColor(.accessibleTextTertiary)
                        .multilineTextAlignment(.center)
                }
                .padding(.top, 24)

                Spacer(minLength: 40)
            }
            .padding(.horizontal, 24)
        }
        .onAppear {
            KagamiAnalytics.shared.trackOnboardingStep(4, name: "permissions")
        }
    }
}

struct OnboardingPermissionCard: View {
    let permission: PermissionState
    let onRequest: () -> Void

    var body: some View {
        HStack(spacing: 16) {
            Image(systemName: permission.icon)
                .font(.title2)
                .foregroundColor(.beacon)
                .frame(width: 32)

            VStack(alignment: .leading, spacing: 4) {
                HStack {
                    Text(permission.name)
                        .font(KagamiFont.body(weight: .medium))
                        .foregroundColor(.accessibleTextPrimary)

                    if permission.isRequired {
                        Text("Required")
                            .font(KagamiFont.caption2())
                            .foregroundColor(.beacon)
                            .padding(.horizontal, 6)
                            .padding(.vertical, 2)
                            .background(Color.beacon.opacity(0.2))
                            .cornerRadius(4)
                    }
                }

                Text(permission.description)
                    .font(KagamiFont.caption())
                    .foregroundColor(.accessibleTextSecondary)
            }

            Spacer()

            // Status indicator / button
            if permission.status == .authorized {
                Image(systemName: "checkmark.circle.fill")
                    .font(.title2)
                    .foregroundColor(.safetyOk)
            } else if permission.status == .denied {
                Button {
                    // Open settings
                    if let settingsURL = URL(string: UIApplication.openSettingsURLString) {
                        UIApplication.shared.open(settingsURL)
                    }
                } label: {
                    Text("Settings")
                        .font(KagamiFont.caption())
                        .foregroundColor(.beacon)
                }
            } else {
                Button {
                    onRequest()
                } label: {
                    Text("Enable")
                        .font(KagamiFont.caption(weight: .medium))
                        .foregroundColor(.void)
                        .padding(.horizontal, 12)
                        .padding(.vertical, 6)
                        .background(Color.beacon)
                        .cornerRadius(KagamiRadius.xs)
                }
            }
        }
        .padding(16)
        .background(Color.voidLight)
        .cornerRadius(KagamiRadius.md)
        .accessibilityElement(children: .combine)
        .accessibilityLabel("\(permission.name). \(permission.description). Status: \(statusLabel)")
    }

    private var statusLabel: String {
        switch permission.status {
        case .authorized: return "Enabled"
        case .denied: return "Denied. Open settings to enable."
        case .notDetermined: return "Not enabled"
        case .restricted: return "Restricted"
        }
    }
}

// MARK: - Step 6: Completion

struct CompletionStepView: View {
    let onComplete: () -> Void

    @State private var showConfetti = false
    @State private var showContent = false

    @Environment(\.accessibilityReduceMotion) var reduceMotion

    var body: some View {
        ZStack {
            // Confetti (if motion enabled)
            if showConfetti && !reduceMotion {
                ConfettiView()
                    .ignoresSafeArea()
            }

            ScrollView {
                VStack(spacing: 32) {
                    Spacer(minLength: 60)

                    // Success icon
                    ZStack {
                        Circle()
                            .fill(Color.spark.opacity(0.2))
                            .frame(width: 120, height: 120)

                        Image(systemName: "checkmark.circle.fill")
                            .font(.system(size: 72))
                            .foregroundColor(.safetyOk)
                            .scaleEffect(showContent || reduceMotion ? 1 : 0)
                    }
                    .accessibilityIdentifier(AccessibilityIdentifiers.Onboarding.completionCheckmark)

                    VStack(spacing: 12) {
                        Text("You're All Set!")
                            .font(KagamiFont.largeTitle())
                            .foregroundColor(.accessibleTextPrimary)
                            .opacity(showContent || reduceMotion ? 1 : 0)
                            .accessibilityIdentifier(AccessibilityIdentifiers.Onboarding.completionTitle)

                        Text("Kagami is ready to help manage your home")
                            .font(KagamiFont.subheadline())
                            .foregroundColor(.accessibleTextSecondary)
                            .multilineTextAlignment(.center)
                            .opacity(showContent || reduceMotion ? 1 : 0)
                    }

                    // Quick tips
                    VStack(alignment: .leading, spacing: 16) {
                        Text("Quick Tips")
                            .font(KagamiFont.headline())
                            .foregroundColor(.accessibleTextSecondary)

                        CompletionTip(
                            icon: "mic.fill",
                            text: "Say \"Hey Kagami\" to use voice commands",
                            color: .nexus
                        )

                        CompletionTip(
                            icon: "hand.tap.fill",
                            text: "Long-press scenes for quick actions",
                            color: .forge
                        )

                        CompletionTip(
                            icon: "gear",
                            text: "Visit Settings to customize",
                            color: .crystal
                        )
                    }
                    .padding(20)
                    .background(Color.voidLight)
                    .cornerRadius(KagamiRadius.lg)
                    .opacity(showContent || reduceMotion ? 1 : 0)
                    .offset(y: showContent || reduceMotion ? 0 : 20)

                    Spacer(minLength: 60)
                }
                .padding(.horizontal, 24)
            }
        }
        .onAppear {
            KagamiAnalytics.shared.trackOnboardingStep(5, name: "completion")

            guard !reduceMotion else {
                showContent = true
                return
            }

            withAnimation(.spring(response: 0.6, dampingFraction: 0.7).delay(0.2)) {
                showContent = true
            }

            DispatchQueue.main.asyncAfter(deadline: .now() + 0.3) {
                showConfetti = true
                UINotificationFeedbackGenerator().notificationOccurred(.success)
            }
        }
    }
}

struct CompletionTip: View {
    let icon: String
    let text: String
    let color: Color

    var body: some View {
        HStack(spacing: 12) {
            Image(systemName: icon)
                .font(.body)
                .foregroundColor(color)
                .frame(width: 24)

            Text(text)
                .font(KagamiFont.subheadline())
                .foregroundColor(.accessibleTextSecondary)
        }
    }
}

/*
 * Mirror
 * h(x) >= 0. Always.
 */
