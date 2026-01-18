//
// SettingsView.swift -- Settings Screen for tvOS
//
// Kagami TV -- Configuration and status display
//
// Features:
// - Connection status display
// - Server configuration
// - Offline queue status
// - Circuit breaker status
// - About information
//

import SwiftUI
import KagamiCore
import KagamiDesign

// MARK: - Settings View

struct SettingsView: View {
    @EnvironmentObject var appModel: TVAppModel

    var body: some View {
        NavigationStack {
            ScrollView {
                VStack(alignment: .leading, spacing: TVDesign.sectionSpacing) {
                    // Connection Section
                    SettingsSection(title: "Connection") {
                        VStack(spacing: TVDesign.cardSpacing) {
                            SettingsRow(
                                icon: "wifi",
                                title: "Status",
                                value: appModel.isConnected ? "Connected" : "Disconnected",
                                valueColor: appModel.isConnected ? TVDesign.successColor : TVDesign.errorColor
                            )

                            SettingsRow(
                                icon: "server.rack",
                                title: "Server",
                                value: appModel.apiService.currentBaseURL,
                                valueColor: .white.opacity(0.75)
                            )

                            SettingsRow(
                                icon: "clock",
                                title: "Latency",
                                value: "\(appModel.apiService.latencyMs)ms",
                                valueColor: latencyColor(appModel.apiService.latencyMs)
                            )
                        }
                    }

                    // Circuit Breaker Section
                    SettingsSection(title: "Circuit Breaker") {
                        VStack(spacing: TVDesign.cardSpacing) {
                            SettingsRow(
                                icon: circuitBreakerIcon,
                                title: "State",
                                value: circuitBreakerState,
                                valueColor: circuitBreakerColor
                            )

                            if appModel.apiService.circuitBreaker.isOpen {
                                SettingsRow(
                                    icon: "clock.arrow.circlepath",
                                    title: "Retry In",
                                    value: retryTimeString,
                                    valueColor: TVDesign.warningColor
                                )
                            }

                            // Reset Button
                            if appModel.apiService.circuitBreaker.state != .closed {
                                Button {
                                    appModel.apiService.resetCircuitBreaker()
                                } label: {
                                    HStack {
                                        Image(systemName: "arrow.clockwise")
                                            .font(.system(size: TVDesign.iconSize))
                                        Text("Reset Circuit Breaker")
                                            .font(.system(size: TVDesign.bodySize))
                                    }
                                    .foregroundColor(.white)
                                    .frame(maxWidth: .infinity)
                                    .frame(height: TVDesign.buttonHeight)
                                    .background(
                                        RoundedRectangle(cornerRadius: TVDesign.buttonRadius)
                                            .fill(TVDesign.primaryColor.opacity(0.3))
                                    )
                                }
                                .buttonStyle(.plain)
                            }
                        }
                    }

                    // Offline Queue Section
                    SettingsSection(title: "Offline Queue") {
                        VStack(spacing: TVDesign.cardSpacing) {
                            SettingsRow(
                                icon: "tray.full",
                                title: "Pending Actions",
                                value: "\(appModel.pendingActionsCount)",
                                valueColor: appModel.pendingActionsCount > 0 ? TVDesign.warningColor : .white.opacity(0.75)
                            )

                            SettingsRow(
                                icon: "icloud.and.arrow.up",
                                title: "Sync Status",
                                value: appModel.offlineQueue.isSyncing ? "Syncing..." : "Idle",
                                valueColor: appModel.offlineQueue.isSyncing ? TVDesign.primaryColor : .white.opacity(0.75)
                            )

                            if let lastSync = appModel.offlineQueue.lastSyncTime {
                                SettingsRow(
                                    icon: "checkmark.circle",
                                    title: "Last Sync",
                                    value: lastSyncString(lastSync),
                                    valueColor: TVDesign.successColor
                                )
                            }

                            // Sync Now Button
                            if appModel.pendingActionsCount > 0 && appModel.isConnected {
                                Button {
                                    Task {
                                        await appModel.offlineQueue.syncPendingActions()
                                    }
                                } label: {
                                    HStack {
                                        Image(systemName: "arrow.triangle.2.circlepath")
                                            .font(.system(size: TVDesign.iconSize))
                                        Text("Sync Now")
                                            .font(.system(size: TVDesign.bodySize))
                                    }
                                    .foregroundColor(.white)
                                    .frame(maxWidth: .infinity)
                                    .frame(height: TVDesign.buttonHeight)
                                    .background(
                                        RoundedRectangle(cornerRadius: TVDesign.buttonRadius)
                                            .fill(TVDesign.successColor.opacity(0.3))
                                    )
                                }
                                .buttonStyle(.plain)
                            }
                        }
                    }

                    // Mesh Discovery Section
                    SettingsSection(title: "Mesh Discovery") {
                        VStack(spacing: TVDesign.cardSpacing) {
                            SettingsRow(
                                icon: "antenna.radiowaves.left.and.right",
                                title: "Discovery",
                                value: appModel.meshDiscovery.isDiscovering ? "Searching..." : "Idle",
                                valueColor: appModel.meshDiscovery.isDiscovering ? TVDesign.primaryColor : .white.opacity(0.75)
                            )

                            SettingsRow(
                                icon: "point.3.connected.trianglepath.dotted",
                                title: "Discovered Hubs",
                                value: "\(appModel.meshDiscovery.discoveredHubs.count)",
                                valueColor: .white.opacity(0.75)
                            )

                            // Discover Button
                            Button {
                                Task {
                                    await appModel.meshDiscovery.startDiscovery()
                                }
                            } label: {
                                HStack {
                                    Image(systemName: "magnifyingglass")
                                        .font(.system(size: TVDesign.iconSize))
                                    Text("Discover Hubs")
                                        .font(.system(size: TVDesign.bodySize))
                                }
                                .foregroundColor(.white)
                                .frame(maxWidth: .infinity)
                                .frame(height: TVDesign.buttonHeight)
                                .background(
                                    RoundedRectangle(cornerRadius: TVDesign.buttonRadius)
                                        .fill(TVDesign.secondaryColor.opacity(0.3))
                                )
                            }
                            .buttonStyle(.plain)
                        }
                    }

                    // About Section
                    SettingsSection(title: "About") {
                        VStack(spacing: TVDesign.cardSpacing) {
                            SettingsRow(
                                icon: "info.circle",
                                title: "Version",
                                value: appVersion,
                                valueColor: .white.opacity(0.75)
                            )

                            SettingsRow(
                                icon: "shield.checkered",
                                title: "Safety",
                                value: "Always Safe",
                                valueColor: TVDesign.successColor
                            )
                        }
                    }

                    // Refresh Button
                    Button {
                        Task {
                            await appModel.refresh()
                        }
                    } label: {
                        HStack {
                            if appModel.isLoading {
                                ProgressView()
                                    .scaleEffect(1.2)
                            } else {
                                Image(systemName: "arrow.clockwise")
                                    .font(.system(size: TVDesign.iconSize))
                            }
                            Text(appModel.isLoading ? "Refreshing..." : "Refresh Connection")
                                .font(.system(size: TVDesign.bodySize))
                        }
                        .foregroundColor(.white)
                        .frame(maxWidth: .infinity)
                        .frame(height: TVDesign.buttonHeight)
                        .background(
                            RoundedRectangle(cornerRadius: TVDesign.buttonRadius)
                                .fill(TVDesign.primaryColor.opacity(0.3))
                        )
                    }
                    .buttonStyle(.plain)
                    .disabled(appModel.isLoading)

                    // Safety Footer
                    SafetyFooter()
                }
                .padding(TVDesign.contentPadding)
            }
            .background(Color.black.ignoresSafeArea())
            .navigationTitle("Settings")
        }
    }

    // MARK: - Computed Properties

    private var appVersion: String {
        let version = Bundle.main.infoDictionary?["CFBundleShortVersionString"] as? String ?? "1.0.0"
        let build = Bundle.main.infoDictionary?["CFBundleVersion"] as? String ?? "1"
        return "\(version) (\(build))"
    }

    private var circuitBreakerIcon: String {
        switch appModel.apiService.circuitBreaker.state {
        case .closed:
            return "checkmark.shield"
        case .open:
            return "exclamationmark.shield"
        case .halfOpen:
            return "questionmark.diamond"
        }
    }

    private var circuitBreakerState: String {
        switch appModel.apiService.circuitBreaker.state {
        case .closed:
            return "Closed (Normal)"
        case .open:
            return "Open (Rejecting)"
        case .halfOpen:
            return "Half-Open (Testing)"
        }
    }

    private var circuitBreakerColor: Color {
        switch appModel.apiService.circuitBreaker.state {
        case .closed:
            return TVDesign.successColor
        case .open:
            return TVDesign.errorColor
        case .halfOpen:
            return TVDesign.warningColor
        }
    }

    private var retryTimeString: String {
        if let time = appModel.apiService.circuitBreaker.timeUntilRetry {
            return String(format: "%.0fs", time)
        }
        return "Soon"
    }

    private func latencyColor(_ ms: Int) -> Color {
        if ms < 100 { return TVDesign.successColor }
        if ms < 300 { return TVDesign.warningColor }
        return TVDesign.errorColor
    }

    private func lastSyncString(_ date: Date) -> String {
        let formatter = RelativeDateTimeFormatter()
        formatter.unitsStyle = .abbreviated
        return formatter.localizedString(for: date, relativeTo: Date())
    }
}

// MARK: - Settings Section

struct SettingsSection<Content: View>: View {
    let title: String
    let content: Content

    init(title: String, @ViewBuilder content: () -> Content) {
        self.title = title
        self.content = content()
    }

    var body: some View {
        VStack(alignment: .leading, spacing: 24) {
            Text(title)
                .font(.system(size: TVDesign.headlineSize, weight: .semibold))
                .foregroundColor(.white.opacity(0.85))

            content
                .padding(TVDesign.cardSpacing)
                .background(
                    RoundedRectangle(cornerRadius: TVDesign.cardRadius)
                        .fill(TVDesign.cardBackground)
                )
        }
    }
}

// MARK: - Settings Row

struct SettingsRow: View {
    let icon: String
    let title: String
    let value: String
    let valueColor: Color

    @FocusState private var isFocused: Bool

    var body: some View {
        HStack(spacing: 20) {
            Image(systemName: icon)
                .font(.system(size: TVDesign.iconSize))
                .foregroundColor(TVDesign.primaryColor)
                .frame(width: TVDesign.iconSize + 16)

            Text(title)
                .font(.system(size: TVDesign.bodySize))
                .foregroundColor(.white)

            Spacer()

            Text(value)
                .font(.system(size: TVDesign.bodySize))
                .foregroundColor(valueColor)
                .lineLimit(1)
                .truncationMode(.middle)
        }
        .padding(.vertical, 8)
        .background(
            RoundedRectangle(cornerRadius: TVDesign.buttonRadius)
                .fill(isFocused ? TVDesign.focusedBackground : Color.clear)
        )
        .scaleEffect(isFocused ? 1.02 : 1.0)
        .animation(TvMotion.button, value: isFocused)
        .focused($isFocused)
    }
}

// MARK: - Preview

#Preview {
    SettingsView()
        .environmentObject(TVAppModel())
}

/*
 * Mirror
 * h(x) >= 0. Always.
 */
