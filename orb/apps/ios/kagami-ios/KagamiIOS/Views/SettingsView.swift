//
// SettingsView.swift — Settings Screen
//
// Includes RTL support, Dynamic Type, microinteractions, and delight.
//

import SwiftUI
import StoreKit
import KagamiDesign
import KagamiCore

struct SettingsView: View {
    @EnvironmentObject var appModel: AppModel
    @State private var showLogoutConfirmation = false
    @Environment(\.requestReview) private var requestReview
    @Environment(\.layoutDirection) private var layoutDirection
    @Environment(\.dynamicTypeSize) private var dynamicTypeSize
    @Environment(\.accessibilityReduceMotion) private var reduceMotion

    // Haptic generators
    private let impactFeedback = UIImpactFeedbackGenerator(style: .light)
    private let successFeedback = UINotificationFeedbackGenerator()

    var body: some View {
        NavigationStack {
            List {
                // Connection Section with enhanced status display
                Section {
                    // Status row with animated indicator
                    HStack(spacing: KagamiSpacing.md) {
                        // Pulsing status indicator
                        Circle()
                            .fill(appModel.isConnected ? Color.safetyOk : Color.safetyViolation)
                            .frame(width: 10, height: 10)
                            .overlay(
                                Circle()
                                    .stroke(appModel.isConnected ? Color.safetyOk.opacity(0.4) : Color.safetyViolation.opacity(0.4), lineWidth: 2)
                                    .scaleEffect(reduceMotion ? 1.0 : 1.5)
                                    .opacity(reduceMotion ? 1.0 : 0)
                                    .animation(
                                        reduceMotion ? nil : Animation.easeInOut(duration: 1.5).repeatForever(autoreverses: false),
                                        value: appModel.isConnected
                                    )
                            )

                        VStack(alignment: .leading, spacing: 2) {
                            Text(appModel.isConnected ? "Connected" : "Disconnected")
                                .font(KagamiFont.body(weight: .medium))
                                .foregroundColor(.accessibleTextPrimary)
                            Text("Home Hub")
                                .font(KagamiFont.caption())
                                .foregroundColor(.accessibleTextSecondary)
                        }

                        Spacer()

                        // Latency badge
                        HStack(spacing: 4) {
                            Image(systemName: "bolt.fill")
                                .font(.caption2)
                            Text("\(appModel.apiService.latencyMs)ms")
                                .font(KagamiFont.caption(weight: .medium))
                        }
                        .foregroundColor(latencyColor)
                        .padding(.horizontal, 10)
                        .padding(.vertical, 6)
                        .background(latencyColor.opacity(0.15))
                        .cornerRadius(KagamiRadius.sm)
                    }
                    .padding(.vertical, 4)
                    .accessibilityElement(children: .combine)
                    .accessibilityLabel("Connection: \(appModel.isConnected ? "Connected" : "Disconnected"). Latency: \(appModel.apiService.latencyMs) milliseconds")

                    if appModel.isDemoMode {
                        HStack(spacing: KagamiSpacing.sm) {
                            Image(systemName: "sparkles")
                                .foregroundColor(.beacon)
                            Text("Demo Mode")
                                .font(KagamiFont.body())
                            Spacer()
                            Text("Explore freely")
                                .font(KagamiFont.caption())
                                .foregroundColor(.accessibleTextTertiary)
                        }
                        .accessibilityElement(children: .combine)
                        .accessibilityLabel("Demo Mode: Explore the app freely")
                    }
                } header: {
                    SettingsSectionHeader(title: "Connection", icon: "antenna.radiowaves.left.and.right")
                }

                // Household Section (only for authenticated users, not demo mode)
                if !appModel.isDemoMode {
                    Section {
                        SettingsNavigationRow(
                            icon: "person.2.fill",
                            iconColor: .nexus,
                            title: "Members",
                            subtitle: "Manage your household",
                            badge: appModel.householdMemberCount.map { "\($0)" }
                        ) {
                            HouseholdMembersView()
                        }

                        SettingsNavigationRow(
                            icon: "person.badge.plus",
                            iconColor: .grove,
                            title: "Invite Someone",
                            subtitle: "Share access to your home"
                        ) {
                            InviteMemberView()
                        }
                    } header: {
                        SettingsSectionHeader(title: "Household", icon: "house.fill")
                    }
                }

                // Account Section (only for authenticated users, not demo mode)
                if !appModel.isDemoMode {
                    Section {
                        Button(role: .destructive) {
                            impactFeedback.impactOccurred()
                            showLogoutConfirmation = true
                        } label: {
                            HStack(spacing: KagamiSpacing.sm) {
                                Image(systemName: "rectangle.portrait.and.arrow.right")
                                    .symbolRenderingMode(.hierarchical)
                                Text("Sign Out")
                                    .font(KagamiFont.body())
                            }
                            .foregroundColor(.safetyViolation)
                            .frame(maxWidth: .infinity, alignment: .leading)
                        }
                        .accessibilityLabel("Sign out")
                        .accessibilityHint("Double tap to sign out of your account")
                    } header: {
                        SettingsSectionHeader(title: "Account", icon: "person.crop.circle")
                    }
                }

                // Shortcuts Section
                Section {
                    Button {
                        impactFeedback.impactOccurred()
                        if let url = URL(string: "shortcuts://") {
                            UIApplication.shared.open(url)
                        }
                    } label: {
                        HStack(spacing: KagamiSpacing.sm) {
                            SettingsIconBadge(icon: "apps.iphone", color: .beacon)
                            VStack(alignment: .leading, spacing: 2) {
                                Text("Siri Shortcuts")
                                    .font(KagamiFont.body())
                                    .foregroundColor(.accessibleTextPrimary)
                                Text("\"Hey Siri, movie mode\"")
                                    .font(KagamiFont.caption())
                                    .foregroundColor(.accessibleTextTertiary)
                                    .italic()
                            }
                            Spacer()
                            Image(systemName: "arrow.up.forward.square")
                                .font(.body)
                                .foregroundColor(.accessibleTextTertiary)
                        }
                    }
                    .accessibilityLabel("Open Siri Shortcuts")
                    .accessibilityHint("Opens Shortcuts app to add Kagami actions to Siri")

                    SettingsNavigationRow(
                        icon: "book.closed.fill",
                        iconColor: .crystal,
                        title: "Shortcuts Guide",
                        subtitle: "Learn voice commands"
                    ) {
                        SiriShortcutsGuideView()
                    }
                } header: {
                    SettingsSectionHeader(title: "Voice Control", icon: "waveform")
                }

                // About Section
                Section {
                    HStack(spacing: KagamiSpacing.sm) {
                        SettingsIconBadge(icon: "info.circle.fill", color: .crystal)
                        Text("Version")
                            .font(KagamiFont.body())
                        Spacer()
                        Text(appVersion)
                            .font(KagamiFont.body(weight: .medium))
                            .foregroundColor(.accessibleTextSecondary)
                    }
                    .accessibilityElement(children: .combine)
                    .accessibilityLabel("Version \(appVersion)")

                    Button {
                        impactFeedback.impactOccurred()
                        requestReview()
                    } label: {
                        HStack(spacing: KagamiSpacing.sm) {
                            SettingsIconBadge(icon: "star.fill", color: .beacon)
                            VStack(alignment: .leading, spacing: 2) {
                                Text("Love Kagami?")
                                    .font(KagamiFont.body())
                                    .foregroundColor(.accessibleTextPrimary)
                                Text("Leave a review")
                                    .font(KagamiFont.caption())
                                    .foregroundColor(.accessibleTextTertiary)
                            }
                            Spacer()
                            // Star rating preview
                            HStack(spacing: 2) {
                                ForEach(0..<5) { _ in
                                    Image(systemName: "star.fill")
                                        .font(.caption2)
                                        .foregroundColor(.beacon.opacity(0.6))
                                }
                            }
                        }
                    }
                    .accessibilityLabel("Rate Kagami on the App Store")
                    .accessibilityHint("Opens App Store to leave a review")
                } header: {
                    SettingsSectionHeader(title: "About", icon: "sparkles")
                }

                // Safety Footer
                Section {
                    HStack {
                        Spacer()
                        HStack(spacing: KagamiSpacing.xs) {
                            Image(systemName: "shield.checkered")
                                .font(.caption)
                                .foregroundColor(.safetyOk.opacity(0.6))
                            Text("Protected")
                                .font(KagamiFont.caption())
                                .foregroundColor(.safetyOk.opacity(0.6))
                        }
                        Spacer()
                    }
                    .listRowBackground(Color.clear)
                }
                .accessibilityLabel("System is protected and operating safely")
            }
            .listStyle(.insetGrouped)
            .background(Color.void)
            .scrollContentBackground(.hidden)
            .navigationTitle("Settings")
            .confirmationDialog(
                "Sign Out",
                isPresented: $showLogoutConfirmation,
                titleVisibility: .visible
            ) {
                Button("Sign Out", role: .destructive) {
                    performLogout()
                }
                Button("Cancel", role: .cancel) {}
            } message: {
                Text("Are you sure you want to sign out?")
            }
        }
    }

    private func performLogout() {
        // Clear keychain token
        KagamiKeychain.deleteToken()

        // Logout from API service
        appModel.apiService.logout()

        // Reset onboarding to show login again
        // Note: This triggers a view update through the RootView's state
        UserDefaults.standard.set(false, forKey: "isDemoMode")

        // Post notification for app-wide logout handling
        NotificationCenter.default.post(name: .kagamiDidLogout, object: nil)
    }

    private var appVersion: String {
        let version = Bundle.main.infoDictionary?["CFBundleShortVersionString"] as? String ?? "1.0.0"
        let build = Bundle.main.infoDictionary?["CFBundleVersion"] as? String ?? "1"
        return "\(version) (\(build))"
    }

    private var latencyColor: Color {
        let ms = appModel.apiService.latencyMs
        if ms < 100 { return .safetyOk }
        if ms < 300 { return .beacon }
        return .safetyViolation
    }
}

// MARK: - Reusable Settings Components

/// Section header with icon
struct SettingsSectionHeader: View {
    let title: String
    let icon: String

    var body: some View {
        HStack(spacing: 6) {
            Image(systemName: icon)
                .font(.caption)
                .foregroundColor(.accessibleTextTertiary)
            Text(title.uppercased())
                .font(KagamiFont.caption(weight: .semibold))
                .foregroundColor(.accessibleTextTertiary)
                .tracking(0.5)
        }
    }
}

/// Icon badge for settings rows
struct SettingsIconBadge: View {
    let icon: String
    let color: Color

    var body: some View {
        Image(systemName: icon)
            .font(.body)
            .foregroundColor(color)
            .frame(width: 28, height: 28)
            .background(color.opacity(0.15))
            .cornerRadius(6)
    }
}

/// Reusable navigation row for settings
struct SettingsNavigationRow<Destination: View>: View {
    let icon: String
    let iconColor: Color
    let title: String
    let subtitle: String?
    let badge: String?
    let destination: () -> Destination

    init(
        icon: String,
        iconColor: Color,
        title: String,
        subtitle: String? = nil,
        badge: String? = nil,
        @ViewBuilder destination: @escaping () -> Destination
    ) {
        self.icon = icon
        self.iconColor = iconColor
        self.title = title
        self.subtitle = subtitle
        self.badge = badge
        self.destination = destination
    }

    var body: some View {
        NavigationLink(destination: destination) {
            HStack(spacing: KagamiSpacing.sm) {
                SettingsIconBadge(icon: icon, color: iconColor)

                VStack(alignment: .leading, spacing: 2) {
                    Text(title)
                        .font(KagamiFont.body())
                        .foregroundColor(.accessibleTextPrimary)
                    if let subtitle = subtitle {
                        Text(subtitle)
                            .font(KagamiFont.caption())
                            .foregroundColor(.accessibleTextTertiary)
                    }
                }

                Spacer()

                if let badge = badge {
                    Text(badge)
                        .font(KagamiFont.caption(weight: .medium))
                        .foregroundColor(.accessibleTextSecondary)
                        .padding(.horizontal, 8)
                        .padding(.vertical, 4)
                        .background(Color.voidLight)
                        .cornerRadius(KagamiRadius.xs)
                }
            }
        }
        .accessibilityLabel(title)
        .accessibilityHint(subtitle ?? "")
    }
}

// MARK: - Siri Shortcuts Guide View

struct SiriShortcutsGuideView: View {
    var body: some View {
        ScrollView {
            VStack(alignment: .leading, spacing: 24) {
                // Header
                VStack(alignment: .leading, spacing: 8) {
                    Image(systemName: "apps.iphone")
                        .font(.system(size: 48))
                        .foregroundColor(.beacon)

                    Text("Siri Shortcuts")
                        .font(KagamiFont.largeTitle())

                    Text("Control your home with your voice")
                        .font(KagamiFont.body())
                        .foregroundColor(.accessibleTextSecondary)
                }
                .padding(.top, 16)

                // Available shortcuts
                VStack(alignment: .leading, spacing: 16) {
                    Text("Available Shortcuts")
                        .font(KagamiFont.headline())

                    ShortcutRow(icon: "film.fill", title: "Movie Mode", phrase: "\"Hey Siri, movie mode\"", color: .nexus)
                    ShortcutRow(icon: "moon.fill", title: "Goodnight", phrase: "\"Hey Siri, goodnight\"", color: .crystal)
                    ShortcutRow(icon: "house.fill", title: "Welcome Home", phrase: "\"Hey Siri, I'm home\"", color: .beacon)
                    ShortcutRow(icon: "lightbulb.fill", title: "Lights Control", phrase: "\"Hey Siri, lights on\"", color: .forge)
                    ShortcutRow(icon: "flame.fill", title: "Fireplace", phrase: "\"Hey Siri, fireplace on\"", color: .spark)
                }

                // Instructions
                VStack(alignment: .leading, spacing: 12) {
                    Text("How to Add")
                        .font(KagamiFont.headline())

                    Text("1. Open the Shortcuts app")
                        .font(KagamiFont.body())
                        .foregroundColor(.accessibleTextSecondary)

                    Text("2. Tap the + button to create a new shortcut")
                        .font(KagamiFont.body())
                        .foregroundColor(.accessibleTextSecondary)

                    Text("3. Search for \"Kagami\" in the apps section")
                        .font(KagamiFont.body())
                        .foregroundColor(.accessibleTextSecondary)

                    Text("4. Select the action you want to add")
                        .font(KagamiFont.body())
                        .foregroundColor(.accessibleTextSecondary)

                    Text("5. Tap the shortcut name and add to Siri")
                        .font(KagamiFont.body())
                        .foregroundColor(.accessibleTextSecondary)
                }

                Spacer()
            }
            .padding(.horizontal, 24)
        }
        .background(Color.void)
        .navigationTitle("Shortcuts Guide")
        .navigationBarTitleDisplayMode(.inline)
    }
}

struct ShortcutRow: View {
    let icon: String
    let title: String
    let phrase: String
    let color: Color

    var body: some View {
        HStack(spacing: 16) {
            Image(systemName: icon)
                .font(.title2)
                .foregroundColor(color)
                .frame(width: 32)

            VStack(alignment: .leading, spacing: 4) {
                Text(title)
                    .font(KagamiFont.body(weight: .medium))

                Text(phrase)
                    .font(KagamiFont.caption())
                    .foregroundColor(.accessibleTextSecondary)
                    .italic()
            }

            Spacer()
        }
        .padding(12)
        .background(Color.voidLight)
        .cornerRadius(KagamiRadius.sm)
    }
}

// MARK: - Notification Names
// Note: kagamiDidLogout is defined in NotificationService.swift
