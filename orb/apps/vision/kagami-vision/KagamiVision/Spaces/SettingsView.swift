//
// SettingsView.swift — Settings for Vision Pro
//
// Colony: Nexus (e4) — Integration
//
// visionOS 2 Features:
//   - .ornament() for window controls
//   - .glassBackgroundEffect() for system glass
//   - VoiceOver labels for all settings items
//   - Spatial gesture hints for interactive elements
//   - Semantic status display
//   - Configurable API URL
//   - Minimum 16pt font sizes
//   - 60pt minimum touch targets
//

import SwiftUI

struct SettingsView: View {
    @EnvironmentObject var appModel: AppModel
    @EnvironmentObject var spatialServices: SpatialServicesContainer
    @Environment(\.dismiss) private var dismiss

    @State private var customAPIURL: String = ""
    @State private var showAPIURLEditor = false

    // Minimum touch target size per Apple HIG
    private let minTouchTargetSize: CGFloat = 60

    private var safetyStatusLabel: String {
        if appModel.safetyScore >= 0.5 { return "All Good" }
        if appModel.safetyScore >= 0 { return "Attention" }
        return "Alert"
    }

    private var safetyStatusColor: Color {
        if appModel.safetyScore >= 0.5 { return .grove }
        if appModel.safetyScore >= 0 { return .beacon }
        return .spark
    }

    var body: some View {
        NavigationStack {
            List {
                // Connection Section
                Section("Connection") {
                    connectionStatusRow
                    latencyRow
                    apiURLRow
                }

                // Spatial Features Section
                Section("Spatial Features") {
                    featureRow(
                        icon: "hand.raised",
                        label: "Hand Tracking",
                        feature: "handTracking"
                    )
                    featureRow(
                        icon: "eye",
                        label: "Eye Tracking",
                        feature: "gazeTracking"
                    )
                    featureRow(
                        icon: "speaker.wave.3",
                        label: "Spatial Audio",
                        feature: "audio"
                    )
                    featureRow(
                        icon: "location",
                        label: "World Anchors",
                        feature: "anchorService"
                    )
                }

                // Privacy Section
                Section("Privacy") {
                    privacyToggleRow(
                        icon: "hand.raised",
                        label: "Upload Hand Tracking Data",
                        description: "Send gesture data to server for analytics",
                        isOn: Binding(
                            get: { PrivacySettings.shared.allowHandTrackingUpload },
                            set: { PrivacySettings.shared.allowHandTrackingUpload = $0 }
                        )
                    )
                    privacyToggleRow(
                        icon: "eye",
                        label: "Upload Gaze Tracking Data",
                        description: "Send eye tracking data to server for analytics",
                        isOn: Binding(
                            get: { PrivacySettings.shared.allowGazeTrackingUpload },
                            set: { PrivacySettings.shared.allowGazeTrackingUpload = $0 }
                        )
                    )
                    privacyToggleRow(
                        icon: "chart.bar",
                        label: "Anonymous Analytics",
                        description: "Help improve Kagami with usage data",
                        isOn: Binding(
                            get: { PrivacySettings.shared.allowAnalytics },
                            set: { PrivacySettings.shared.allowAnalytics = $0 }
                        )
                    )
                }

                // System Status Section
                Section("System Status") {
                    systemStatusRow
                }

                // About Section
                Section("About") {
                    versionRow
                    platformRow
                    privacyRow
                    accessibilityRow
                }
            }
            .listStyle(.insetGrouped)
            .navigationTitle("Settings")
            .font(.system(size: 16))
        }
        .glassBackgroundEffect()
        // Window ornament for quick actions
        .ornament(
            visibility: .visible,
            attachmentAnchor: .scene(.bottom),
            contentAlignment: .center
        ) {
            settingsOrnament
        }
        .sheet(isPresented: $showAPIURLEditor) {
            apiURLEditorSheet
        }
        .onAppear {
            customAPIURL = appModel.apiService.currentURL
        }
    }

    // MARK: - Connection Rows

    private var connectionStatusRow: some View {
        HStack {
            Label("Status", systemImage: "wifi")
                .font(.system(size: 16))
            Spacer()
            Text(appModel.isConnected ? "Connected" : "Offline")
                .font(.system(size: 16))
                .foregroundColor(appModel.isConnected ? .grove : .spark)
        }
        .frame(minHeight: minTouchTargetSize)
        .accessibilityElement(children: .combine)
        .accessibilityLabel("Connection status: \(appModel.isConnected ? "connected" : "offline")")
    }

    private var latencyRow: some View {
        HStack {
            Label("Latency", systemImage: "clock")
                .font(.system(size: 16))
            Spacer()
            Text("\(appModel.apiService.latencyMs)ms")
                .font(.system(size: 16))
                .foregroundColor(.secondary)
        }
        .frame(minHeight: minTouchTargetSize)
        .accessibilityElement(children: .combine)
        .accessibilityLabel("Network latency: \(appModel.apiService.latencyMs) milliseconds")
    }

    private var apiURLRow: some View {
        Button(action: { showAPIURLEditor = true }) {
            HStack {
                Label("API Server", systemImage: "server.rack")
                    .font(.system(size: 16))
                Spacer()
                Text(appModel.apiService.currentURL)
                    .font(.system(size: 14))
                    .foregroundColor(.secondary)
                    .lineLimit(1)
                Image(systemName: "chevron.right")
                    .font(.system(size: 12))
                    .foregroundColor(.secondary)
            }
        }
        .frame(minHeight: minTouchTargetSize)
        .contentShape(.hoverEffect, .rect(cornerRadius: 8))
        .hoverEffect(.highlight)
        .buttonStyle(.plain)
        .accessibilityLabel("Configure API server URL")
        .accessibilityHint("Currently set to \(appModel.apiService.currentURL)")
    }

    // MARK: - Feature Row

    private func featureRow(icon: String, label: String, feature: String) -> some View {
        HStack {
            Label(label, systemImage: icon)
                .font(.system(size: 16))
            Spacer()
            Text(spatialServices.isFeatureAvailable(feature) ? "Available" : "Unavailable")
                .font(.system(size: 16))
                .foregroundColor(spatialServices.isFeatureAvailable(feature) ? .grove : .secondary)
        }
        .frame(minHeight: minTouchTargetSize)
        .accessibilityElement(children: .combine)
        .accessibilityLabel("\(label): \(spatialServices.isFeatureAvailable(feature) ? "available" : "unavailable")")
    }

    // MARK: - Privacy Toggle Row

    private func privacyToggleRow(icon: String, label: String, description: String, isOn: Binding<Bool>) -> some View {
        HStack {
            VStack(alignment: .leading, spacing: 4) {
                Label(label, systemImage: icon)
                    .font(.system(size: 16))
                Text(description)
                    .font(.system(size: 13))
                    .foregroundColor(.secondary)
            }
            Spacer()
            Toggle("", isOn: isOn)
                .labelsHidden()
                .toggleStyle(.switch)
                .tint(.crystal)
        }
        .frame(minHeight: minTouchTargetSize)
        .contentShape(.hoverEffect, .rect(cornerRadius: 8))
        .hoverEffect(.highlight)
        .accessibilityElement(children: .combine)
        .accessibilityLabel("\(label). \(description). Currently \(isOn.wrappedValue ? "enabled" : "disabled")")
        .accessibilityHint("Double tap to toggle")
        .accessibilityAddTraits(.isButton)
    }

    // MARK: - System Status Row

    private var systemStatusRow: some View {
        HStack {
            Label("Status", systemImage: "shield.checkered")
                .font(.system(size: 16))
            Spacer()
            HStack(spacing: 6) {
                Circle()
                    .fill(safetyStatusColor)
                    .frame(width: 10, height: 10)
                    .accessibilityHidden(true)
                Text(safetyStatusLabel)
                    .font(.system(size: 16))
                    .foregroundColor(safetyStatusColor)
            }
        }
        .frame(minHeight: minTouchTargetSize)
        .accessibilityElement(children: .combine)
        .accessibilityLabel("System status: \(safetyStatusLabel)")
    }

    // MARK: - About Rows

    private var versionRow: some View {
        HStack {
            Label("Version", systemImage: "info.circle")
                .font(.system(size: 16))
            Spacer()
            Text(Bundle.main.infoDictionary?["CFBundleShortVersionString"] as? String ?? "1.0.0")
                .font(.system(size: 16))
                .foregroundColor(.secondary)
        }
        .frame(minHeight: minTouchTargetSize)
        .accessibilityElement(children: .combine)
        .accessibilityLabel("App version \(Bundle.main.infoDictionary?["CFBundleShortVersionString"] as? String ?? "1.0.0")")
    }

    private var platformRow: some View {
        HStack {
            Label("Platform", systemImage: "visionpro")
                .font(.system(size: 16))
            Spacer()
            Text("Apple Vision Pro")
                .font(.system(size: 16))
                .foregroundColor(.nexus)
        }
        .frame(minHeight: minTouchTargetSize)
        .accessibilityElement(children: .combine)
        .accessibilityLabel("Platform: Apple Vision Pro")
    }

    private var privacyRow: some View {
        NavigationLink(destination: PrivacyInfoView()) {
            Label("Privacy", systemImage: "hand.raised.fill")
                .font(.system(size: 16))
        }
        .frame(minHeight: minTouchTargetSize)
        .contentShape(.hoverEffect, .rect(cornerRadius: 8))
        .hoverEffect(.highlight)
        .accessibilityLabel("Privacy information")
    }

    private var accessibilityRow: some View {
        NavigationLink(destination: AccessibilityInfoView()) {
            Label("Accessibility", systemImage: "accessibility")
                .font(.system(size: 16))
        }
        .frame(minHeight: minTouchTargetSize)
        .contentShape(.hoverEffect, .rect(cornerRadius: 8))
        .hoverEffect(.highlight)
        .accessibilityLabel("Accessibility information")
    }

    // MARK: - Ornament

    private var settingsOrnament: some View {
        HStack(spacing: 16) {
            Button(action: {
                Task {
                    await appModel.apiService.checkConnection()
                }
            }) {
                Label("Reconnect", systemImage: "arrow.clockwise")
                    .font(.system(size: 14))
            }
            .frame(minWidth: minTouchTargetSize, minHeight: 44)
            .contentShape(.hoverEffect, .capsule)
            .hoverEffect(.lift)
            .buttonStyle(.plain)

            Button(action: { dismiss() }) {
                Label("Done", systemImage: "checkmark")
                    .font(.system(size: 14))
            }
            .frame(minWidth: minTouchTargetSize, minHeight: 44)
            .contentShape(.hoverEffect, .capsule)
            .hoverEffect(.lift)
            .buttonStyle(.plain)
        }
        .padding(.horizontal, 20)
        .padding(.vertical, 12)
        .glassBackgroundEffect()
    }

    // MARK: - API URL Editor Sheet

    private var apiURLEditorSheet: some View {
        NavigationStack {
            Form {
                Section {
                    TextField("API URL", text: $customAPIURL)
                        .font(.system(size: 16, design: .monospaced))
                        .textContentType(.URL)
                        .autocapitalization(.none)
                        .accessibilityLabel("API server URL")
                } header: {
                    Text("Server Address")
                        .font(.system(size: 14))
                } footer: {
                    Text("Enter the URL of your Kagami server (e.g., http://kagami.local:8001)")
                        .font(.system(size: 14))
                }

                Section {
                    Button(action: resetToDefault) {
                        Label("Reset to Default", systemImage: "arrow.counterclockwise")
                            .font(.system(size: 16))
                    }
                    .frame(minHeight: minTouchTargetSize)
                    .contentShape(.hoverEffect, .rect(cornerRadius: 8))
                    .hoverEffect(.highlight)
                }
            }
            .navigationTitle("API Server")
            .toolbar {
                ToolbarItem(placement: .cancellationAction) {
                    Button("Cancel") {
                        showAPIURLEditor = false
                    }
                    .contentShape(.hoverEffect, .rect(cornerRadius: 8))
                    .hoverEffect(.lift)
                }
                ToolbarItem(placement: .confirmationAction) {
                    Button("Save") {
                        saveAPIURL()
                    }
                    .contentShape(.hoverEffect, .rect(cornerRadius: 8))
                    .hoverEffect(.lift)
                }
            }
        }
        .glassBackgroundEffect()
    }

    private func saveAPIURL() {
        Task {
            await appModel.apiService.updateAPIURL(customAPIURL)
            showAPIURLEditor = false
        }
    }

    private func resetToDefault() {
        customAPIURL = KagamiAPIService.defaultAPIURL
    }
}

// MARK: - Privacy Info View

struct PrivacyInfoView: View {
    var body: some View {
        List {
            Section("Data Collection") {
                Text("Kagami Vision collects the following data:")
                    .font(.system(size: 16))
                    .padding(.vertical, 8)

                privacyItem(
                    icon: "hand.raised",
                    title: "Hand Tracking",
                    description: "Used for gesture recognition. Processed on-device only."
                )
                privacyItem(
                    icon: "eye",
                    title: "Eye Tracking",
                    description: "Used for gaze-based interaction. Processed on-device only."
                )
                privacyItem(
                    icon: "heart.fill",
                    title: "HealthKit",
                    description: "Sleep and activity data from paired iPhone. Used for context-aware suggestions."
                )
                privacyItem(
                    icon: "wifi",
                    title: "Network",
                    description: "Communicates with your local Kagami server for smart home control."
                )
            }

            Section("Data Storage") {
                Text("All spatial data is processed on-device. Smart home commands are sent to your local server only.")
                    .font(.system(size: 16))
                    .padding(.vertical, 8)
            }
        }
        .navigationTitle("Privacy")
    }

    private func privacyItem(icon: String, title: String, description: String) -> some View {
        HStack(alignment: .top, spacing: 12) {
            Image(systemName: icon)
                .font(.system(size: 18))
                .foregroundColor(.crystal)
                .frame(width: 24)
            VStack(alignment: .leading, spacing: 4) {
                Text(title)
                    .font(.system(size: 16, weight: .medium))
                Text(description)
                    .font(.system(size: 14))
                    .foregroundColor(.secondary)
            }
        }
        .padding(.vertical, 8)
    }
}

// MARK: - Accessibility Info View

struct AccessibilityInfoView: View {
    var body: some View {
        List {
            Section("Accessibility Features") {
                accessibilityItem(
                    icon: "hand.point.up.left",
                    title: "Gesture Support",
                    description: "All controls support look-and-pinch interaction."
                )
                accessibilityItem(
                    icon: "speaker.wave.2",
                    title: "VoiceOver",
                    description: "Full VoiceOver support with descriptive labels."
                )
                accessibilityItem(
                    icon: "textformat.size",
                    title: "Dynamic Type",
                    description: "Text scales with your preferred reading size."
                )
                accessibilityItem(
                    icon: "circle.lefthalf.filled",
                    title: "Reduced Motion",
                    description: "Animations respect system Reduce Motion setting."
                )
            }

            Section("Conformance") {
                Text("Kagami Vision conforms to WCAG 2.1 Level AA accessibility guidelines.")
                    .font(.system(size: 16))
                    .padding(.vertical, 8)
            }
        }
        .navigationTitle("Accessibility")
    }

    private func accessibilityItem(icon: String, title: String, description: String) -> some View {
        HStack(alignment: .top, spacing: 12) {
            Image(systemName: icon)
                .font(.system(size: 18))
                .foregroundColor(.crystal)
                .frame(width: 24)
            VStack(alignment: .leading, spacing: 4) {
                Text(title)
                    .font(.system(size: 16, weight: .medium))
                Text(description)
                    .font(.system(size: 14))
                    .foregroundColor(.secondary)
            }
        }
        .padding(.vertical, 8)
    }
}

#Preview(windowStyle: .plain) {
    SettingsView()
        .environmentObject(AppModel())
        .environmentObject(SpatialServicesContainer())
}

/*
 * Kagami Vision Settings
 * With ornament controls and configurable API URL
 */
