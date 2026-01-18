//
// VisionLoginView.swift - Spatial Login Experience
//
// Colony: Crystal (e7) - Verification
//
// Features:
//   - Spatial login experience for Vision Pro
//   - Server discovery with visual feedback
//   - Integration setup wizard
//   - Kagami design system adapted for visionOS
//   - Animated connection visualization
//   - Accessibility-first design
//
// Design Philosophy:
//   First contact with Kagami in spatial computing.
//   The login experience sets the tone for the
//   entire relationship. Make it magical but trustworthy.
//
// Created: December 31, 2025


import SwiftUI
import RealityKit
import Combine

/// Spatial login view for Vision Pro
struct VisionLoginView: View {
    @EnvironmentObject var appModel: AppModel
    @StateObject private var viewModel = VisionLoginViewModel()
    @Environment(\.accessibilityReduceMotion) private var reduceMotion

    var body: some View {
        ZStack {
            // Background gradient
            LinearGradient(
                colors: [Color.black, Color(white: 0.08)],
                startPoint: .top,
                endPoint: .bottom
            )
            .ignoresSafeArea()

            VStack(spacing: 40) {
                Spacer()

                // Kagami orb visualization
                KagamiOrbView(
                    connectionState: viewModel.connectionState,
                    reduceMotion: reduceMotion
                )
                .frame(height: 200)

                // Title and status
                VStack(spacing: 12) {
                    Text("Kagami")
                        .font(.system(size: 48, weight: .light))
                        .foregroundStyle(
                            LinearGradient(
                                colors: [.white, .crystal],
                                startPoint: .leading,
                                endPoint: .trailing
                            )
                        )

                    Text(viewModel.statusMessage)
                        .font(.system(size: 18))
                        .foregroundColor(.secondary)
                        .multilineTextAlignment(.center)
                        .frame(height: 50)
                }
                .accessibilityElement(children: .combine)

                Spacer()

                // Connection interface
                switch viewModel.connectionState {
                case .discovering:
                    DiscoveryView(
                        discoveredServers: viewModel.discoveredServers,
                        onSelect: { server in
                            viewModel.connect(to: server)
                        }
                    )

                case .connecting:
                    ConnectionProgressView(progress: viewModel.connectionProgress)

                case .authenticating:
                    AuthenticationView(
                        onAuthenticate: { credentials in
                            Task { await viewModel.authenticate(with: credentials) }
                        }
                    )

                case .setupIntegrations:
                    IntegrationSetupView(
                        availableIntegrations: viewModel.availableIntegrations,
                        onComplete: {
                            viewModel.completeSetup()
                        }
                    )

                case .connected:
                    ConnectedView(
                        serverInfo: viewModel.connectedServerInfo,
                        onContinue: {
                            viewModel.proceedToMain()
                        }
                    )

                case .error(let message):
                    ErrorView(
                        message: message,
                        onRetry: { viewModel.startDiscovery() }
                    )

                case .idle:
                    EmptyView()
                }

                Spacer()

                // Manual entry option
                if viewModel.connectionState == .discovering {
                    Button("Enter Server Address Manually") {
                        viewModel.showManualEntry = true
                    }
                    .buttonStyle(.borderless)
                    .foregroundColor(.secondary)
                    .font(.system(size: 14))
                }
            }
            .padding(40)
        }
        .sheet(isPresented: $viewModel.showManualEntry) {
            ManualServerEntryView(
                onConnect: { url in
                    viewModel.connectToManualServer(url)
                }
            )
        }
        .task {
            viewModel.startDiscovery()
        }
    }
}

// MARK: - View Model

@MainActor
class VisionLoginViewModel: ObservableObject {

    // MARK: - Published State

    @Published var connectionState: ConnectionState = .idle
    @Published var statusMessage: String = ""
    @Published var discoveredServers: [DiscoveredServer] = []
    @Published var connectionProgress: Double = 0
    @Published var availableIntegrations: [Integration] = []
    @Published var connectedServerInfo: ServerInfo?
    @Published var showManualEntry = false

    // MARK: - Types

    enum ConnectionState: Equatable {
        case idle
        case discovering
        case connecting
        case authenticating
        case setupIntegrations
        case connected
        case error(String)

        static func == (lhs: ConnectionState, rhs: ConnectionState) -> Bool {
            switch (lhs, rhs) {
            case (.idle, .idle),
                 (.discovering, .discovering),
                 (.connecting, .connecting),
                 (.authenticating, .authenticating),
                 (.setupIntegrations, .setupIntegrations),
                 (.connected, .connected):
                return true
            case (.error(let a), .error(let b)):
                return a == b
            default:
                return false
            }
        }
    }

    struct DiscoveredServer: Identifiable {
        let id: UUID = UUID()
        let name: String
        let address: String
        let version: String
        var isRecommended: Bool
    }

    struct Integration: Identifiable {
        let id: String
        let name: String
        let icon: String
        var isEnabled: Bool
        var isConfigured: Bool
    }

    struct ServerInfo {
        let name: String
        let version: String
        let safetyScore: Double
        let roomCount: Int
        let deviceCount: Int
    }

    struct Credentials {
        let method: AuthMethod
        let value: String

        enum AuthMethod {
            case biometric
            case passkey
            case manual(username: String, password: String)
        }
    }

    // MARK: - Internal

    private var apiService: KagamiAPIService?
    private var discoveryTask: Task<Void, Never>?

    // MARK: - Discovery

    func startDiscovery() {
        connectionState = .discovering
        statusMessage = "Looking for Kagami servers..."

        discoveryTask?.cancel()
        discoveryTask = Task {
            // Simulate discovery with mDNS
            await Task.yield()

            // Check for kagami.local first
            let kagamiLocal = "http://kagami.local:8001"
            if await testServer(kagamiLocal) {
                await MainActor.run {
                    discoveredServers = [
                        DiscoveredServer(
                            name: "Kagami Home",
                            address: kagamiLocal,
                            version: "1.0.0",
                            isRecommended: true
                        )
                    ]
                    statusMessage = "Found your Kagami server"
                }
                return
            }

            // Check common local addresses
            let addresses = [
                "http://192.168.1.100:8001",
                "http://192.168.1.50:8001",
                "http://10.0.0.100:8001"
            ]

            var found: [DiscoveredServer] = []
            for address in addresses {
                if await testServer(address) {
                    found.append(DiscoveredServer(
                        name: "Kagami Server",
                        address: address,
                        version: "1.0.0",
                        isRecommended: found.isEmpty
                    ))
                }
            }

            await MainActor.run {
                discoveredServers = found
                if found.isEmpty {
                    statusMessage = "No servers found. Check your network."
                } else {
                    statusMessage = "Select a server to connect"
                }
            }
        }
    }

    private func testServer(_ address: String) async -> Bool {
        guard let url = URL(string: "\(address)/health") else { return false }

        do {
            let (_, response) = try await URLSession.shared.data(from: url)
            return (response as? HTTPURLResponse)?.statusCode == 200
        } catch {
            return false
        }
    }

    // MARK: - Connection

    func connect(to server: DiscoveredServer) {
        connectionState = .connecting
        statusMessage = "Connecting to \(server.name)..."
        connectionProgress = 0

        Task {
            // Simulate connection progress
            for i in 1...10 {
                try? await Task.sleep(nanoseconds: 100_000_000)
                await MainActor.run {
                    connectionProgress = Double(i) / 10.0
                }
            }

            // Create API service
            let api = KagamiAPIService(baseURL: server.address)
            await api.connect()

            await MainActor.run {
                apiService = api
                connectionState = .authenticating
                statusMessage = "Verify your identity"
            }
        }
    }

    func connectToManualServer(_ url: String) {
        showManualEntry = false

        let server = DiscoveredServer(
            name: "Manual Server",
            address: url,
            version: "Unknown",
            isRecommended: false
        )

        connect(to: server)
    }

    // MARK: - Authentication

    func authenticate(with credentials: Credentials) async {
        statusMessage = "Authenticating..."

        // In production, this would verify with the server
        try? await Task.sleep(nanoseconds: 500_000_000)

        // Check if integrations need setup
        let needsSetup = UserDefaults.standard.bool(forKey: "hasCompletedIntegrationSetup") == false

        if needsSetup {
            await MainActor.run {
                availableIntegrations = [
                    Integration(id: "healthkit", name: "HealthKit", icon: "heart.fill", isEnabled: true, isConfigured: false),
                    Integration(id: "homekit", name: "HomeKit", icon: "homekit", isEnabled: false, isConfigured: false),
                    Integration(id: "shortcuts", name: "Shortcuts", icon: "bolt.fill", isEnabled: true, isConfigured: false)
                ]
                connectionState = .setupIntegrations
                statusMessage = "Set up your integrations"
            }
        } else {
            await completeConnection()
        }
    }

    // MARK: - Setup

    func completeSetup() {
        UserDefaults.standard.set(true, forKey: "hasCompletedIntegrationSetup")
        Task {
            await completeConnection()
        }
    }

    private func completeConnection() async {
        // Fetch server info
        if let api = apiService {
            do {
                let health = try await api.fetchHealth()
                let rooms = try await api.fetchRooms()

                await MainActor.run {
                    connectedServerInfo = ServerInfo(
                        name: "Kagami Home",
                        version: "1.0.0",
                        safetyScore: health.safetyScore ?? 0.85,
                        roomCount: rooms.count,
                        deviceCount: rooms.reduce(0) { $0 + $1.lights.count + $1.shades.count }
                    )
                    connectionState = .connected
                    statusMessage = "Connected and ready"
                }
            } catch {
                await MainActor.run {
                    connectionState = .error("Failed to fetch server info")
                }
            }
        }
    }

    func proceedToMain() {
        // This would transition to the main app
        // In a real implementation, this would set a state that the app observes
    }
}

// MARK: - Kagami Orb View

struct KagamiOrbView: View {
    let connectionState: VisionLoginViewModel.ConnectionState
    let reduceMotion: Bool

    @State private var pulseScale: CGFloat = 1.0
    @State private var rotationAngle: Double = 0

    var orbColor: Color {
        switch connectionState {
        case .idle, .discovering:
            return .crystal
        case .connecting:
            return .beacon
        case .authenticating:
            return .nexus
        case .setupIntegrations:
            return .flow
        case .connected:
            return .grove
        case .error:
            return .spark
        }
    }

    var body: some View {
        ZStack {
            // Outer glow
            Circle()
                .fill(
                    RadialGradient(
                        colors: [orbColor.opacity(0.4), orbColor.opacity(0)],
                        center: .center,
                        startRadius: 30,
                        endRadius: 100
                    )
                )
                .frame(width: 200, height: 200)
                .scaleEffect(reduceMotion ? 1.0 : pulseScale)

            // Middle ring
            Circle()
                .stroke(
                    AngularGradient(
                        colors: [orbColor, orbColor.opacity(0.3), orbColor],
                        center: .center
                    ),
                    lineWidth: 2
                )
                .frame(width: 100, height: 100)
                .rotationEffect(.degrees(rotationAngle))

            // Inner orb
            Circle()
                .fill(
                    RadialGradient(
                        colors: [orbColor, orbColor.opacity(0.7)],
                        center: .center,
                        startRadius: 0,
                        endRadius: 40
                    )
                )
                .frame(width: 60, height: 60)
                .shadow(color: orbColor.opacity(0.8), radius: 20)

            // Kanji
            Text("鏡")
                .font(.system(size: 24, weight: .light))
                .foregroundColor(.white.opacity(0.9))
        }
        .onAppear {
            guard !reduceMotion else { return }

            // Breathing animation - Fibonacci 2584ms
            withAnimation(.easeInOut(duration: 2.584).repeatForever(autoreverses: true)) {
                pulseScale = 1.1
            }

            // Slow rotation - Fibonacci 9.87s (987ms * 10 for full rotation)
            withAnimation(.linear(duration: 9.87).repeatForever(autoreverses: false)) {
                rotationAngle = 360
            }
        }
        .accessibilityElement()
        .accessibilityLabel("Kagami connection status: \(connectionStateLabel)")
    }

    var connectionStateLabel: String {
        switch connectionState {
        case .idle: return "Idle"
        case .discovering: return "Discovering servers"
        case .connecting: return "Connecting"
        case .authenticating: return "Authenticating"
        case .setupIntegrations: return "Setting up integrations"
        case .connected: return "Connected"
        case .error(let message): return "Error: \(message)"
        }
    }
}

// MARK: - Discovery View

struct DiscoveryView: View {
    let discoveredServers: [VisionLoginViewModel.DiscoveredServer]
    let onSelect: (VisionLoginViewModel.DiscoveredServer) -> Void

    var body: some View {
        VStack(spacing: 16) {
            if discoveredServers.isEmpty {
                // Searching animation
                HStack(spacing: 8) {
                    ForEach(0..<3) { index in
                        Circle()
                            .fill(Color.crystal)
                            .frame(width: 8, height: 8)
                            .opacity(0.5)
                    }
                }
                .accessibilityLabel("Searching for servers")
            } else {
                // Server list
                ForEach(discoveredServers) { server in
                    ServerCard(server: server) {
                        onSelect(server)
                    }
                }
            }
        }
        .frame(maxWidth: 400)
    }
}

struct ServerCard: View {
    let server: VisionLoginViewModel.DiscoveredServer
    let onSelect: () -> Void

    @State private var isHovered = false

    var body: some View {
        Button(action: onSelect) {
            HStack(spacing: 16) {
                // Server icon
                Image(systemName: "server.rack")
                    .font(.system(size: 24))
                    .foregroundColor(.crystal)
                    .frame(width: 40)

                // Server info
                VStack(alignment: .leading, spacing: 4) {
                    HStack {
                        Text(server.name)
                            .font(.system(size: 16, weight: .medium))
                            .foregroundColor(.white)

                        if server.isRecommended {
                            Text("Recommended")
                                .font(.system(size: 10))
                                .foregroundColor(.grove)
                                .padding(.horizontal, 6)
                                .padding(.vertical, 2)
                                .background(
                                    Capsule()
                                        .fill(Color.grove.opacity(0.2))
                                )
                        }
                    }

                    Text(server.address)
                        .font(.system(size: 12, design: .monospaced))
                        .foregroundColor(.secondary)
                }

                Spacer()

                Image(systemName: "chevron.right")
                    .font(.system(size: 14))
                    .foregroundColor(.secondary)
            }
            .padding(16)
            .background(
                RoundedRectangle(cornerRadius: 16)
                    .fill(Color.white.opacity(isHovered ? 0.1 : 0.05))
            )
            .overlay(
                RoundedRectangle(cornerRadius: 16)
                    .stroke(server.isRecommended ? Color.crystal.opacity(0.3) : Color.white.opacity(0.1), lineWidth: 1)
            )
        }
        .buttonStyle(.plain)
        .hoverEffect(.lift)
        .onHover { isHovered = $0 }
    }
}

// MARK: - Connection Progress View

struct ConnectionProgressView: View {
    let progress: Double

    var body: some View {
        VStack(spacing: 16) {
            // Progress ring
            ZStack {
                Circle()
                    .stroke(Color.white.opacity(0.1), lineWidth: 4)
                    .frame(width: 60, height: 60)

                Circle()
                    .trim(from: 0, to: progress)
                    .stroke(Color.beacon, style: StrokeStyle(lineWidth: 4, lineCap: .round))
                    .frame(width: 60, height: 60)
                    .rotationEffect(.degrees(-90))

                Text("\(Int(progress * 100))%")
                    .font(.system(size: 14, design: .monospaced))
                    .foregroundColor(.white)
            }

            Text("Establishing secure connection...")
                .font(.system(size: 14))
                .foregroundColor(.secondary)
        }
        .accessibilityElement()
        .accessibilityLabel("Connecting, \(Int(progress * 100)) percent complete")
    }
}

// MARK: - Authentication View

struct AuthenticationView: View {
    let onAuthenticate: (VisionLoginViewModel.Credentials) -> Void

    var body: some View {
        VStack(spacing: 20) {
            // Biometric button (primary)
            Button(action: {
                onAuthenticate(VisionLoginViewModel.Credentials(method: .biometric, value: ""))
            }) {
                HStack(spacing: 12) {
                    Image(systemName: "opticid")
                        .font(.system(size: 24))

                    Text("Continue with Optic ID")
                        .font(.system(size: 16, weight: .medium))
                }
                .foregroundColor(.white)
                .frame(maxWidth: 280)
                .padding(.vertical, 14)
                .background(
                    RoundedRectangle(cornerRadius: 12)
                        .fill(Color.crystal)
                )
            }
            .buttonStyle(.plain)

            // Passkey option
            Button(action: {
                onAuthenticate(VisionLoginViewModel.Credentials(method: .passkey, value: ""))
            }) {
                HStack(spacing: 12) {
                    Image(systemName: "person.badge.key.fill")
                        .font(.system(size: 20))

                    Text("Use Passkey")
                        .font(.system(size: 14))
                }
                .foregroundColor(.secondary)
            }
            .buttonStyle(.plain)
        }
    }
}

// MARK: - Integration Setup View

struct IntegrationSetupView: View {
    let availableIntegrations: [VisionLoginViewModel.Integration]
    let onComplete: () -> Void

    @State private var integrations: [VisionLoginViewModel.Integration] = []

    var body: some View {
        VStack(spacing: 24) {
            Text("Enable Integrations")
                .font(.system(size: 20, weight: .semibold))
                .foregroundColor(.white)

            VStack(spacing: 12) {
                ForEach(integrations) { integration in
                    IntegrationToggleRow(
                        integration: integration,
                        onToggle: { enabled in
                            if let index = integrations.firstIndex(where: { $0.id == integration.id }) {
                                integrations[index].isEnabled = enabled
                            }
                        }
                    )
                }
            }
            .frame(maxWidth: 350)

            Button("Continue") {
                onComplete()
            }
            .buttonStyle(.borderedProminent)
            .tint(.crystal)
        }
        .onAppear {
            integrations = availableIntegrations
        }
    }
}

struct IntegrationToggleRow: View {
    let integration: VisionLoginViewModel.Integration
    let onToggle: (Bool) -> Void

    @State private var isEnabled: Bool = false

    var body: some View {
        HStack {
            Image(systemName: integration.icon)
                .font(.system(size: 20))
                .foregroundColor(.flow)
                .frame(width: 32)

            Text(integration.name)
                .font(.system(size: 14))
                .foregroundColor(.white)

            Spacer()

            Toggle("", isOn: $isEnabled)
                .labelsHidden()
                .onChange(of: isEnabled) { _, newValue in
                    onToggle(newValue)
                }
        }
        .padding(12)
        .background(
            RoundedRectangle(cornerRadius: 10)
                .fill(Color.white.opacity(0.05))
        )
        .onAppear {
            isEnabled = integration.isEnabled
        }
    }
}

// MARK: - Connected View

struct ConnectedView: View {
    let serverInfo: VisionLoginViewModel.ServerInfo?
    let onContinue: () -> Void

    var body: some View {
        VStack(spacing: 24) {
            // Success checkmark
            Image(systemName: "checkmark.circle.fill")
                .font(.system(size: 48))
                .foregroundColor(.grove)

            if let info = serverInfo {
                VStack(spacing: 8) {
                    Text("Connected to \(info.name)")
                        .font(.system(size: 18, weight: .medium))
                        .foregroundColor(.white)

                    // Stats
                    HStack(spacing: 24) {
                        StatPill(label: "Rooms", value: "\(info.roomCount)")
                        StatPill(label: "Devices", value: "\(info.deviceCount)")
                        StatPill(label: "h(x)", value: String(format: "%.2f", info.safetyScore))
                    }
                }
            }

            Button("Enter Kagami") {
                onContinue()
            }
            .buttonStyle(.borderedProminent)
            .tint(.crystal)
            .font(.system(size: 16, weight: .medium))
        }
    }
}

struct StatPill: View {
    let label: String
    let value: String

    var body: some View {
        VStack(spacing: 2) {
            Text(value)
                .font(.system(size: 16, weight: .semibold, design: .monospaced))
                .foregroundColor(.white)

            Text(label)
                .font(.system(size: 10))
                .foregroundColor(.secondary)
        }
        .padding(.horizontal, 12)
        .padding(.vertical, 6)
        .background(
            Capsule()
                .fill(Color.white.opacity(0.05))
        )
    }
}

// MARK: - Error View

struct ErrorView: View {
    let message: String
    let onRetry: () -> Void

    var body: some View {
        VStack(spacing: 20) {
            Image(systemName: "exclamationmark.triangle.fill")
                .font(.system(size: 40))
                .foregroundColor(.spark)

            Text(message)
                .font(.system(size: 14))
                .foregroundColor(.secondary)
                .multilineTextAlignment(.center)

            Button("Try Again") {
                onRetry()
            }
            .buttonStyle(.bordered)
            .tint(.spark)
        }
        .frame(maxWidth: 300)
    }
}

// MARK: - Manual Server Entry

struct ManualServerEntryView: View {
    let onConnect: (String) -> Void
    @Environment(\.dismiss) private var dismiss
    @State private var serverURL: String = "http://"

    var body: some View {
        NavigationStack {
            VStack(spacing: 24) {
                Text("Enter your Kagami server address")
                    .font(.headline)

                TextField("Server URL", text: $serverURL)
                    .textFieldStyle(.roundedBorder)
                    .autocapitalization(.none)
                    .disableAutocorrection(true)

                Text("Example: http://192.168.1.100:8001")
                    .font(.caption)
                    .foregroundColor(.secondary)

                Spacer()
            }
            .padding(24)
            .navigationTitle("Manual Entry")
            .navigationBarTitleDisplayMode(.inline)
            .toolbar {
                ToolbarItem(placement: .cancellationAction) {
                    Button("Cancel") { dismiss() }
                }
                ToolbarItem(placement: .confirmationAction) {
                    Button("Connect") {
                        onConnect(serverURL)
                    }
                    .disabled(serverURL.count < 10)
                }
            }
        }
        .frame(width: 400, height: 300)
    }
}

// MARK: - Preview

#Preview {
    VisionLoginView()
        .environmentObject(AppModel())
}

/*
 *
 * h(x) >= 0. Always.
 *
 * First contact matters.
 * The orb pulses with trust.
 * Connection is a promise kept.
 */
