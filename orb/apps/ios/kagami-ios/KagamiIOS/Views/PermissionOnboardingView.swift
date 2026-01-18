//
// PermissionOnboardingView.swift — Unified Permission Onboarding
//
// Colony: Beacon (e₅) — Architecture, Planning
//
// Features:
//   - Explains what Kagami can do with each permission
//   - Shows privacy implications clearly
//   - Allows granular opt-in (not all-or-nothing)
//   - Graceful degradation if denied
//   - Easy path to re-enable later in Settings
//
// h(x) ≥ 0. Always.
//

import SwiftUI
import HealthKit
import KagamiDesign

/// Unified permission onboarding view for Kagami.
/// Presents permissions in a clear, non-pushy way.
struct PermissionOnboardingView: View {
    @StateObject private var viewModel = PermissionOnboardingViewModel()
    @Environment(\.dismiss) private var dismiss

    var body: some View {
        NavigationStack {
            ScrollView {
                VStack(spacing: 24) {
                    // Header
                    headerSection

                    // Permission cards
                    ForEach(viewModel.permissions) { permission in
                        PermissionCard(
                            permission: permission,
                            onToggle: { viewModel.togglePermission(permission) }
                        )
                    }

                    // Continue button
                    continueButton

                    // Skip option
                    skipButton
                }
                .padding()
            }
            .background(Color.void)
            .navigationTitle("Welcome to Kagami")
            .navigationBarTitleDisplayMode(.inline)
        }
        .preferredColorScheme(.dark)
    }

    // MARK: - Sections

    private var headerSection: some View {
        VStack(spacing: 12) {
            // Kagami logo
            Image(systemName: "hexagon.fill")
                .font(.system(size: 60))
                .foregroundStyle(
                    LinearGradient(
                        colors: [Color.nexus, Color.crystal],
                        startPoint: .topLeading,
                        endPoint: .bottomTrailing
                    )
                )

            Text("鏡 Kagami")
                .font(.title)
                .fontWeight(.bold)
                .foregroundStyle(.white)

            Text("To give you the best experience, Kagami needs a few permissions. You can enable or disable these at any time.")
                .font(.subheadline)
                .foregroundStyle(.secondary)
                .multilineTextAlignment(.center)
                .padding(.horizontal)
        }
        .padding(.vertical)
    }

    private var continueButton: some View {
        Button {
            Task {
                await viewModel.requestEnabledPermissions()
                dismiss()
            }
        } label: {
            HStack {
                Text("Continue")
                    .fontWeight(.semibold)

                if viewModel.isRequesting {
                    ProgressView()
                        .tint(.white)
                        .padding(.leading, 4)
                }
            }
            .frame(maxWidth: .infinity)
            .padding()
            .background(
                LinearGradient(
                    colors: [Color.nexus, Color.crystal],
                    startPoint: .leading,
                    endPoint: .trailing
                )
            )
            .foregroundStyle(.white)
            .clipShape(RoundedRectangle(cornerRadius: 12))
        }
        .disabled(viewModel.isRequesting)
        .padding(.top)
    }

    private var skipButton: some View {
        Button {
            dismiss()
        } label: {
            Text("Skip for now")
                .font(.subheadline)
                .foregroundStyle(.secondary)
        }
        .padding(.bottom)
    }
}

// MARK: - Permission Card

struct PermissionCard: View {
    let permission: PermissionItem
    let onToggle: () -> Void

    var body: some View {
        HStack(spacing: 16) {
            // Icon
            ZStack {
                Circle()
                    .fill(permission.color.opacity(0.15))
                    .frame(width: 48, height: 48)

                Image(systemName: permission.icon)
                    .font(.title2)
                    .foregroundStyle(permission.color)
            }

            // Info
            VStack(alignment: .leading, spacing: 4) {
                Text(permission.name)
                    .font(.headline)
                    .foregroundStyle(.white)

                Text(permission.description)
                    .font(.caption)
                    .foregroundStyle(.secondary)
                    .lineLimit(2)
            }

            Spacer()

            // Toggle
            Toggle("", isOn: Binding(
                get: { permission.isEnabled },
                set: { _ in onToggle() }
            ))
            .labelsHidden()
            .tint(permission.color)
        }
        .padding()
        .background(
            RoundedRectangle(cornerRadius: 12)
                .fill(Color.white.opacity(0.05))
        )
        .overlay(
            RoundedRectangle(cornerRadius: 12)
                .stroke(permission.isEnabled ? permission.color.opacity(0.5) : Color.clear, lineWidth: 1)
        )
    }
}

// MARK: - View Model

@MainActor
class PermissionOnboardingViewModel: ObservableObject {
    @Published var permissions: [PermissionItem] = []
    @Published var isRequesting: Bool = false

    init() {
        setupPermissions()
    }

    private func setupPermissions() {
        permissions = [
            PermissionItem(
                id: "health",
                name: "Health Data",
                description: "Monitor heart rate, sleep, and activity to optimize your home environment.",
                icon: "heart.fill",
                color: .spark,  // Red/orange for health
                isEnabled: true,
                isGranted: false
            ),
            PermissionItem(
                id: "focus",
                name: "Focus Status",
                description: "Adapt lighting and announcements based on your current Focus mode.",
                icon: "moon.fill",
                color: .nexus,  // Purple for focus/integration
                isEnabled: true,
                isGranted: false
            ),
            PermissionItem(
                id: "notifications",
                name: "Notifications",
                description: "Receive alerts about your home, security events, and reminders.",
                icon: "bell.fill",
                color: .beacon,  // Yellow/gold for alerts
                isEnabled: true,
                isGranted: false
            ),
            PermissionItem(
                id: "location",
                name: "Location",
                description: "Enable geofencing for automatic 'Welcome Home' and 'Away' scenes.",
                icon: "location.fill",
                color: .crystal,  // Cyan for spatial/location
                isEnabled: false,
                isGranted: false
            ),
            PermissionItem(
                id: "siri",
                name: "Siri & Shortcuts",
                description: "Control your home with voice commands and automation shortcuts.",
                icon: "waveform",
                color: .flow,  // Blue for voice/flow
                isEnabled: true,
                isGranted: false
            ),
            PermissionItem(
                id: "live_activities",
                name: "Live Activities",
                description: "Show home status in Dynamic Island and on Lock Screen.",
                icon: "rectangle.badge.plus",
                color: .grove,  // Green for live/active status
                isEnabled: true,
                isGranted: false
            )
        ]
    }

    func togglePermission(_ permission: PermissionItem) {
        guard let index = permissions.firstIndex(where: { $0.id == permission.id }) else { return }
        permissions[index].isEnabled.toggle()
    }

    func requestEnabledPermissions() async {
        isRequesting = true
        defer { isRequesting = false }

        for permission in permissions where permission.isEnabled {
            await requestPermission(permission)
        }

        // Save onboarding completed
        UserDefaults.standard.set(true, forKey: "permission_onboarding_completed")
    }

    private func requestPermission(_ permission: PermissionItem) async {
        switch permission.id {
        case "health":
            let granted = await HealthKitService.shared.requestAuthorization()
            updatePermissionStatus(id: "health", granted: granted)

        case "focus":
            let granted = await FocusService.shared.requestAuthorization()
            updatePermissionStatus(id: "focus", granted: granted)

        case "notifications":
            let granted = await requestNotificationPermission()
            updatePermissionStatus(id: "notifications", granted: granted)

        case "location":
            // Location permission is requested when needed
            updatePermissionStatus(id: "location", granted: true)

        case "siri":
            // Siri permissions are handled by the system
            updatePermissionStatus(id: "siri", granted: true)

        case "live_activities":
            if #available(iOS 16.1, *) {
                let enabled = LiveActivityManager.shared.areActivitiesEnabled
                updatePermissionStatus(id: "live_activities", granted: enabled)
            }

        default:
            break
        }
    }

    private func requestNotificationPermission() async -> Bool {
        let center = UNUserNotificationCenter.current()

        do {
            let granted = try await center.requestAuthorization(options: [.alert, .sound, .badge])
            return granted
        } catch {
            print("⚠️ Notification permission error: \(error)")
            return false
        }
    }

    private func updatePermissionStatus(id: String, granted: Bool) {
        if let index = permissions.firstIndex(where: { $0.id == id }) {
            permissions[index].isGranted = granted
        }
    }
}

// MARK: - Permission Item

struct PermissionItem: Identifiable {
    let id: String
    let name: String
    let description: String
    let icon: String
    let color: Color
    var isEnabled: Bool
    var isGranted: Bool
}

// MARK: - UNUserNotificationCenter import

import UserNotifications

// MARK: - Preview

#Preview {
    PermissionOnboardingView()
}

/*
 * 鏡
 * h(x) ≥ 0. Always.
 *
 * Permission is trust.
 * Explain clearly. Respect choices.
 * The user is always in control.
 */
