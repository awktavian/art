//
// HubView.swift — Hub Management Interface
//
// Colony: Nexus (e4) — Integration
//
// Discover, configure, and control Kagami Hub devices
// from iOS. Voice proxy lets you use your phone as the
// Hub's ears when you're away from it.
//

import SwiftUI
import KagamiDesign

struct HubView: View {
    @StateObject private var hubManager = HubManager.shared
    @State private var showingSettings = false
    @State private var showingLEDControl = false

    var body: some View {
        NavigationStack {
            Group {
                if let hub = hubManager.connectedHub {
                    ConnectedHubView(hub: hub)
                } else {
                    HubDiscoveryView()
                }
            }
            .navigationTitle("Kagami Hub")
            .toolbar {
                if hubManager.connectedHub != nil {
                    ToolbarItem(placement: .navigationBarTrailing) {
                        Button {
                            showingSettings = true
                        } label: {
                            Image(systemName: "gear")
                        }
                    }
                }
            }
            .sheet(isPresented: $showingSettings) {
                HubSettingsView()
            }
            .task {
                // Try to reconnect to last hub on launch
                await hubManager.connectToLastHub()
            }
        }
    }
}

// MARK: - Discovery View

struct HubDiscoveryView: View {
    @ObservedObject private var hubManager = HubManager.shared
    @State private var manualHost = ""
    @State private var manualPort = "8080"
    @State private var showingManualEntry = false

    var body: some View {
        List {
            Section {
                if hubManager.isDiscovering {
                    HStack {
                        ProgressView()
                            .padding(.trailing, 8)
                        Text("Searching for Hubs...")
                            .foregroundColor(.secondary)
                    }
                } else {
                    Button {
                        hubManager.startDiscovery()
                    } label: {
                        Label("Scan for Hubs", systemImage: "antenna.radiowaves.left.and.right")
                    }
                }
            }

            if !hubManager.discoveredHubs.isEmpty {
                Section("Discovered Hubs") {
                    ForEach(hubManager.discoveredHubs) { hub in
                        Button {
                            Task {
                                await hubManager.connect(to: hub)
                            }
                        } label: {
                            HubRowView(hub: hub)
                        }
                        .disabled(hubManager.isConnecting)
                    }
                }
            }

            Section {
                Button {
                    showingManualEntry = true
                } label: {
                    Label("Enter Address Manually", systemImage: "keyboard")
                }
            }

            if let error = hubManager.lastError {
                Section {
                    Text(error)
                        .foregroundColor(.red)
                        .font(.caption)
                }
            }
        }
        .sheet(isPresented: $showingManualEntry) {
            ManualHubEntryView()
        }
        .onAppear {
            if hubManager.discoveredHubs.isEmpty {
                hubManager.startDiscovery()
            }
        }
    }
}

struct HubRowView: View {
    let hub: HubDevice

    var body: some View {
        HStack {
            Image(systemName: "hifispeaker.fill")
                .font(.title2)
                .foregroundColor(.accentColor)

            VStack(alignment: .leading) {
                Text(hub.name)
                    .font(.headline)
                Text("\(hub.host):\(hub.port)")
                    .font(.caption)
                    .foregroundColor(.secondary)
            }

            Spacer()

            Image(systemName: "chevron.right")
                .foregroundColor(.secondary)
        }
        .padding(.vertical, 4)
    }
}

struct ManualHubEntryView: View {
    @ObservedObject private var hubManager = HubManager.shared
    @Environment(\.dismiss) private var dismiss

    @State private var host = ""
    @State private var port = "8080"

    var body: some View {
        NavigationStack {
            Form {
                Section("Hub Address") {
                    TextField("Host (e.g., 192.168.1.100)", text: $host)
                        .textContentType(.URL)
                        .autocapitalization(.none)

                    TextField("Port", text: $port)
                        .keyboardType(.numberPad)
                }

                Section {
                    Button("Connect") {
                        guard !host.isEmpty,
                              let portInt = Int(port) else { return }

                        let hub = HubDevice(
                            id: "\(host):\(portInt)",
                            name: "Manual Hub",
                            location: "Manual",
                            host: host,
                            port: portInt,
                            isConnected: false,
                            lastSeen: Date()
                        )

                        Task {
                            await hubManager.connect(to: hub)
                            if hubManager.connectedHub != nil {
                                dismiss()
                            }
                        }
                    }
                    .disabled(host.isEmpty || hubManager.isConnecting)
                }
            }
            .navigationTitle("Manual Entry")
            .navigationBarTitleDisplayMode(.inline)
            .toolbar {
                ToolbarItem(placement: .cancellationAction) {
                    Button("Cancel") { dismiss() }
                }
            }
        }
    }
}

// MARK: - Connected Hub View

struct ConnectedHubView: View {
    let hub: HubDevice
    @ObservedObject private var hubManager = HubManager.shared
    @State private var isRecording = false

    var body: some View {
        ScrollView {
            VStack(spacing: 20) {
                // Status Card
                HubStatusCard()

                // Quick Actions
                HubQuickActionsCard()

                // Voice Proxy
                VoiceProxyCard(isRecording: $isRecording)

                // LED Control
                LEDControlCard()

                // Disconnect
                Button(role: .destructive) {
                    hubManager.disconnect()
                } label: {
                    Label("Disconnect", systemImage: "xmark.circle")
                        .frame(maxWidth: .infinity)
                }
                .buttonStyle(.bordered)
                .padding(.top, 20)
            }
            .padding()
        }
    }
}

struct HubStatusCard: View {
    @ObservedObject private var hubManager = HubManager.shared

    var body: some View {
        VStack(spacing: 12) {
            // Hub icon and name
            HStack {
                ZStack {
                    Circle()
                        .fill(hubManager.hubStatus?.apiConnected == true ? Color.green.opacity(0.2) : Color.orange.opacity(0.2))
                        .frame(width: 60, height: 60)

                    Image(systemName: "hifispeaker.fill")
                        .font(.title)
                        .foregroundColor(hubManager.hubStatus?.apiConnected == true ? .green : .orange)
                }

                VStack(alignment: .leading) {
                    Text(hubManager.hubStatus?.name ?? hub.name)
                        .font(.title2.bold())

                    Text(hubManager.hubStatus?.location ?? "Unknown location")
                        .foregroundColor(.secondary)

                    if let version = hubManager.hubStatus?.version {
                        Text("v\(version)")
                            .font(.caption)
                            .foregroundColor(.secondary)
                    }
                }

                Spacer()
            }

            Divider()

            // Status indicators
            HStack(spacing: 20) {
                StatusIndicator(
                    icon: "wifi",
                    label: "API",
                    isActive: hubManager.hubStatus?.apiConnected ?? false
                )

                StatusIndicator(
                    icon: "ear",
                    label: "Listening",
                    isActive: hubManager.hubStatus?.isListening ?? false
                )

                if let score = hubManager.hubStatus?.safetyScore {
                    StatusIndicator(
                        icon: "shield.checkered",
                        label: String(format: "%.0f%%", score * 100),
                        isActive: score >= 0.3
                    )
                }

                if let colony = hubManager.hubStatus?.currentColony {
                    StatusIndicator(
                        icon: colonyIcon(for: colony),
                        label: colony.capitalized,
                        isActive: true
                    )
                }
            }

            // Uptime
            if let uptime = hubManager.hubStatus?.uptimeSeconds {
                Text("Uptime: \(formatUptime(uptime))")
                    .font(.caption)
                    .foregroundColor(.secondary)
            }
        }
        .padding()
        .background(Color(.systemGray6))
        .cornerRadius(16)
    }

    private var hub: HubDevice {
        hubManager.connectedHub ?? HubDevice(
            id: "unknown",
            name: "Hub",
            location: "",
            host: "",
            port: 0,
            isConnected: false,
            lastSeen: Date()
        )
    }

    private func colonyIcon(for colony: String) -> String {
        switch colony.lowercased() {
        case "spark": return "flame"
        case "forge": return "hammer"
        case "flow": return "water.waves"
        case "nexus": return "link"
        case "beacon": return "building.columns"
        case "grove": return "leaf"
        case "crystal": return "diamond"
        default: return "circle"
        }
    }

    private func formatUptime(_ seconds: Int) -> String {
        let hours = seconds / 3600
        let minutes = (seconds % 3600) / 60
        if hours > 0 {
            return "\(hours)h \(minutes)m"
        } else {
            return "\(minutes)m"
        }
    }
}

struct StatusIndicator: View {
    let icon: String
    let label: String
    let isActive: Bool

    var body: some View {
        VStack(spacing: 4) {
            Image(systemName: icon)
                .font(.title3)
                .foregroundColor(isActive ? .green : .secondary)

            Text(label)
                .font(.caption2)
                .foregroundColor(.secondary)
        }
    }
}

struct HubQuickActionsCard: View {
    @ObservedObject private var hubManager = HubManager.shared

    let actions: [(icon: String, label: String, command: String)] = [
        ("film", "Movie", "movie mode"),
        ("moon.fill", "Goodnight", "goodnight"),
        ("house.fill", "Welcome", "welcome home"),
        ("sun.max.fill", "Lights On", "turn on all lights"),
    ]

    var body: some View {
        VStack(alignment: .leading, spacing: 12) {
            Text("Quick Commands")
                .font(.headline)

            LazyVGrid(columns: [GridItem(.flexible()), GridItem(.flexible())], spacing: 12) {
                ForEach(actions, id: \.command) { action in
                    Button {
                        Task {
                            try? await hubManager.executeCommand(action.command)
                        }
                    } label: {
                        VStack(spacing: 8) {
                            Image(systemName: action.icon)
                                .font(.title2)
                            Text(action.label)
                                .font(.caption)
                        }
                        .frame(maxWidth: .infinity)
                        .padding()
                        .background(Color.accentColor.opacity(0.1))
                        .cornerRadius(12)
                    }
                    .buttonStyle(.plain)
                }
            }
        }
        .padding()
        .background(Color(.systemGray6))
        .cornerRadius(16)
    }
}

struct VoiceProxyCard: View {
    @Binding var isRecording: Bool
    @ObservedObject private var hubManager = HubManager.shared

    var body: some View {
        VStack(alignment: .leading, spacing: 12) {
            HStack {
                Text("Voice Proxy")
                    .font(.headline)

                Spacer()

                Text("Use phone as Hub's ears")
                    .font(.caption)
                    .foregroundColor(.secondary)
            }

            Button {
                if isRecording {
                    // Will stop automatically
                } else {
                    isRecording = true
                    hubManager.startVoiceProxy()

                    // Auto-stop after 5 seconds
                    Task {
                        try? await Task.sleep(nanoseconds: 5_000_000_000)
                        await MainActor.run {
                            isRecording = false
                        }
                    }
                }
            } label: {
                HStack {
                    Image(systemName: isRecording ? "waveform" : "mic.fill")
                        .font(.title)

                    Text(isRecording ? "Recording..." : "Hold to Speak")
                        .font(.headline)
                }
                .frame(maxWidth: .infinity)
                .padding()
                .background(isRecording ? Color.red : Color.accentColor)
                .foregroundColor(.white)
                .cornerRadius(12)
            }
            .buttonStyle(.plain)
        }
        .padding()
        .background(Color(.systemGray6))
        .cornerRadius(16)
    }
}

struct LEDControlCard: View {
    @ObservedObject private var hubManager = HubManager.shared
    @State private var brightness: Float = 0.5

    let patterns: [(name: String, icon: String)] = [
        ("idle", "circle"),
        ("listening", "ear"),
        ("thinking", "brain"),
        ("speaking", "waveform"),
        ("error", "exclamationmark.triangle"),
    ]

    var body: some View {
        VStack(alignment: .leading, spacing: 12) {
            HStack {
                Text("LED Ring")
                    .font(.headline)

                Spacer()

                Button("Test") {
                    Task {
                        try? await hubManager.testLED()
                    }
                }
                .font(.caption)
            }

            // Pattern buttons
            HStack(spacing: 8) {
                ForEach(patterns, id: \.name) { pattern in
                    Button {
                        Task {
                            try? await hubManager.controlLED(pattern: pattern.name)
                        }
                    } label: {
                        Image(systemName: pattern.icon)
                            .font(.title3)
                            .frame(width: 44, height: 44)
                            .background(Color.accentColor.opacity(0.1))
                            .cornerRadius(8)
                    }
                    .buttonStyle(.plain)
                }
            }

            // Brightness slider
            HStack {
                Image(systemName: "sun.min")
                    .foregroundColor(.secondary)

                Slider(value: $brightness, in: 0...1) { editing in
                    if !editing {
                        Task {
                            try? await hubManager.controlLED(pattern: "idle", brightness: brightness)
                        }
                    }
                }

                Image(systemName: "sun.max")
                    .foregroundColor(.secondary)
            }

            // Colony highlights
            Text("Colony Highlight")
                .font(.caption)
                .foregroundColor(.secondary)

            HStack(spacing: 8) {
                ForEach(0..<7) { colony in
                    Button {
                        Task {
                            try? await hubManager.controlLED(pattern: "colony", colony: colony)
                        }
                    } label: {
                        Circle()
                            .fill(colonyColor(colony))
                            .frame(width: 32, height: 32)
                    }
                    .buttonStyle(.plain)
                }
            }
        }
        .padding()
        .background(Color(.systemGray6))
        .cornerRadius(16)
        .onAppear {
            brightness = hubManager.hubStatus?.ledBrightness ?? 0.5
        }
    }

    private func colonyColor(_ index: Int) -> Color {
        // Use design system colony colors
        switch index {
        case 0: return .spark    // Spark (e1)
        case 1: return .forge    // Forge (e2)
        case 2: return .flow     // Flow (e3)
        case 3: return .nexus    // Nexus (e4)
        case 4: return .beacon   // Beacon (e5)
        case 5: return .grove    // Grove (e6)
        case 6: return .crystal  // Crystal (e7)
        default: return .accessibleTextTertiary
        }
    }
}

// MARK: - Settings View

struct HubSettingsView: View {
    @ObservedObject private var hubManager = HubManager.shared
    @Environment(\.dismiss) private var dismiss

    @State private var config: HubConfig?
    @State private var isSaving = false

    var body: some View {
        NavigationStack {
            Form {
                if var config = config {
                    Section("General") {
                        TextField("Name", text: Binding(
                            get: { config.name },
                            set: { config.name = $0; self.config = config }
                        ))

                        TextField("Location", text: Binding(
                            get: { config.location },
                            set: { config.location = $0; self.config = config }
                        ))
                    }

                    Section("Kagami API") {
                        TextField("API URL", text: Binding(
                            get: { config.apiUrl },
                            set: { config.apiUrl = $0; self.config = config }
                        ))
                        .textContentType(.URL)
                        .autocapitalization(.none)
                    }

                    Section("Wake Word") {
                        TextField("Wake Phrase", text: Binding(
                            get: { config.wakeWord },
                            set: { config.wakeWord = $0; self.config = config }
                        ))

                        HStack {
                            Text("Sensitivity")
                            Slider(value: Binding(
                                get: { config.wakeSensitivity },
                                set: { config.wakeSensitivity = $0; self.config = config }
                            ), in: 0...1)
                        }
                    }

                    Section("LED Ring") {
                        Toggle("Enabled", isOn: Binding(
                            get: { config.ledEnabled },
                            set: { config.ledEnabled = $0; self.config = config }
                        ))

                        HStack {
                            Text("Brightness")
                            Slider(value: Binding(
                                get: { config.ledBrightness },
                                set: { config.ledBrightness = $0; self.config = config }
                            ), in: 0...1)
                        }
                    }

                    Section("Voice") {
                        HStack {
                            Text("Volume")
                            Slider(value: Binding(
                                get: { config.ttsVolume },
                                set: { config.ttsVolume = $0; self.config = config }
                            ), in: 0...1)
                        }

                        Picker("Voice Style", selection: Binding(
                            get: { config.ttsColony },
                            set: { config.ttsColony = $0; self.config = config }
                        )) {
                            Text("Spark (Creative)").tag("spark")
                            Text("Forge (Direct)").tag("forge")
                            Text("Flow (Calm)").tag("flow")
                            Text("Nexus (Friendly)").tag("nexus")
                            Text("Beacon (Formal)").tag("beacon")
                            Text("Grove (Curious)").tag("grove")
                            Text("Crystal (Precise)").tag("crystal")
                        }
                    }
                } else {
                    ProgressView()
                }
            }
            .navigationTitle("Hub Settings")
            .navigationBarTitleDisplayMode(.inline)
            .toolbar {
                ToolbarItem(placement: .cancellationAction) {
                    Button("Cancel") { dismiss() }
                }

                ToolbarItem(placement: .confirmationAction) {
                    Button("Save") {
                        saveConfig()
                    }
                    .disabled(isSaving || config == nil)
                }
            }
            .onAppear {
                config = hubManager.hubConfig
            }
        }
    }

    private func saveConfig() {
        guard let config = config else { return }
        isSaving = true

        Task {
            do {
                try await hubManager.updateConfig(config)
                dismiss()
            } catch {
                // Show error
            }
            isSaving = false
        }
    }
}

// MARK: - Preview

#Preview {
    HubView()
}

/*
 * 鏡
 */
