//
// LoginView.swift — Watch Login Status View
//
// Colony: Nexus (e4) — Integration
//
// Displays authentication status on watch.
// Login is performed via iPhone companion app - watch only shows status.
//
// States:
//   - Unauthenticated: Prompts user to open iPhone app
//   - Authenticating: Shows loading indicator
//   - Authenticated: Shows user info with logout option
//   - Error: Shows error with retry option
//
// Accessibility:
//   - VoiceOver labels for all interactive elements
//   - Dynamic Type support
//   - Reduced motion respect
//
// Created: December 31, 2025
//

import SwiftUI
import WatchKit

struct LoginView: View {
    @EnvironmentObject var connectivity: WatchConnectivityService

    var body: some View {
        ScrollView {
            VStack(spacing: 16) {
                switch connectivity.authState.status {
                case .unauthenticated:
                    UnauthenticatedView()

                case .authenticating:
                    AuthenticatingView()

                case .authenticated:
                    AuthenticatedView()

                case .tokenExpired:
                    TokenExpiredView()

                case .error:
                    ErrorView()
                }
            }
            .padding(.horizontal, 8)
        }
        .background(Color.void)
        .navigationTitle("Account")
    }
}

// MARK: - Unauthenticated State

private struct UnauthenticatedView: View {
    @EnvironmentObject var connectivity: WatchConnectivityService
    @Environment(\.accessibilityReduceMotion) var reduceMotion

    var body: some View {
        VStack(spacing: 16) {
            // Icon
            ZStack {
                Circle()
                    .fill(Color.nexus.opacity(0.2))
                    .frame(width: 80, height: 80)

                Image(systemName: "person.crop.circle.badge.questionmark")
                    .font(.system(size: 36))
                    .foregroundColor(.nexus)
            }
            .accessibilityHidden(true)

            // Title
            Text("Not Signed In")
                .font(WatchFonts.primary(.headline))
                .foregroundColor(.white)

            // Instructions
            Text("Open Kagami on your iPhone to sign in")
                .font(WatchFonts.secondary(.subheadline))
                .foregroundColor(.secondary)
                .multilineTextAlignment(.center)
                .fixedSize(horizontal: false, vertical: true)

            Spacer().frame(height: 8)

            // iPhone Status
            HStack(spacing: 8) {
                Circle()
                    .fill(connectivity.isReachable ? Color.safetyOk : Color.safetyCaution)
                    .frame(width: 8, height: 8)

                Text(connectivity.isReachable ? "iPhone Connected" : "iPhone Not Available")
                    .font(WatchFonts.caption(.caption))
                    .foregroundColor(.secondary)
            }
            .accessibilityElement(children: .combine)
            .accessibilityLabel(connectivity.isReachable ? "iPhone connected" : "iPhone not available")

            // Retry Button (if iPhone is reachable)
            if connectivity.isReachable {
                Button {
                    HapticPattern.listening.play()
                    connectivity.requestAuthFromiPhone()
                } label: {
                    HStack {
                        Image(systemName: "arrow.clockwise")
                        Text("Refresh")
                    }
                    .font(WatchFonts.secondary(.footnote))
                    .frame(maxWidth: .infinity)
                    .padding(.vertical, 12)
                    .background(Color.nexus.opacity(0.2))
                    .cornerRadius(10)
                }
                .buttonStyle(.plain)
                .accessibleButton(label: "Refresh authentication status", hint: "Checks if you're signed in on iPhone")
            }
        }
        .padding(.vertical, 16)
    }
}

// MARK: - Authenticating State

private struct AuthenticatingView: View {
    var body: some View {
        VStack(spacing: 16) {
            // Loading indicator
            ProgressView()
                .progressViewStyle(.circular)
                .scaleEffect(1.5)
                .frame(width: 60, height: 60)
                .accessibilityLabel("Signing in")

            Text("Signing In...")
                .font(WatchFonts.primary(.headline))
                .foregroundColor(.white)

            Text("Connecting to iPhone")
                .font(WatchFonts.caption(.caption))
                .foregroundColor(.secondary)
        }
        .padding(.vertical, 32)
    }
}

// MARK: - Authenticated State

private struct AuthenticatedView: View {
    @EnvironmentObject var connectivity: WatchConnectivityService
    @State private var showingLogoutConfirmation = false

    var body: some View {
        VStack(spacing: 16) {
            // Avatar
            ZStack {
                Circle()
                    .fill(Color.grove.opacity(0.2))
                    .frame(width: 72, height: 72)

                Text(userInitials)
                    .font(.system(size: 28, weight: .semibold, design: .rounded))
                    .foregroundColor(.grove)
            }
            .accessibilityHidden(true)

            // User Info
            VStack(spacing: 4) {
                Text(displayName)
                    .font(WatchFonts.primary(.headline))
                    .foregroundColor(.white)
                    .lineLimit(1)

                if let username = connectivity.authState.username {
                    Text("@\(username)")
                        .font(WatchFonts.caption(.caption))
                        .foregroundColor(.secondary)
                }
            }

            // Connected indicator
            HStack(spacing: 6) {
                Circle()
                    .fill(Color.safetyOk)
                    .frame(width: 8, height: 8)

                Text("Signed In")
                    .font(WatchFonts.caption(.caption2))
                    .foregroundColor(.safetyOk)
            }
            .accessibilityElement(children: .combine)
            .accessibilityLabel("Signed in as \(displayName)")

            // Server info (if available)
            if let serverURL = connectivity.authState.serverURL {
                Text(simplifiedServerURL(serverURL))
                    .font(WatchFonts.mono(.caption2))
                    .foregroundColor(.secondary)
                    .lineLimit(1)
            }

            Spacer().frame(height: 8)

            // Last sync
            if let lastSync = connectivity.lastSyncDate {
                Text("Synced \(lastSync, style: .relative) ago")
                    .font(WatchFonts.caption(.caption2))
                    .foregroundColor(.secondary)
            }

            // Logout Button
            Button {
                showingLogoutConfirmation = true
            } label: {
                HStack {
                    Image(systemName: "rectangle.portrait.and.arrow.right")
                    Text("Sign Out")
                }
                .font(WatchFonts.secondary(.footnote))
                .foregroundColor(.safetyViolation)
                .frame(maxWidth: .infinity)
                .padding(.vertical, 12)
                .background(Color.safetyViolation.opacity(0.15))
                .cornerRadius(10)
            }
            .buttonStyle(.plain)
            .accessibleButton(label: "Sign out", hint: "Signs out of your account on all devices")
            .confirmationDialog("Sign Out?", isPresented: $showingLogoutConfirmation) {
                Button("Sign Out", role: .destructive) {
                    HapticPattern.confirmation.play()
                    connectivity.requestLogout()
                }
                Button("Cancel", role: .cancel) {}
            }
        }
        .padding(.vertical, 12)
    }

    private var displayName: String {
        connectivity.authState.displayName ??
        connectivity.authState.username ??
        "User"
    }

    private var userInitials: String {
        let name = displayName
        let components = name.split(separator: " ")
        if components.count >= 2 {
            return String(components[0].prefix(1) + components[1].prefix(1)).uppercased()
        }
        return String(name.prefix(2)).uppercased()
    }

    private func simplifiedServerURL(_ url: String) -> String {
        // Remove protocol and port for display
        var simplified = url
            .replacingOccurrences(of: "https://", with: "")
            .replacingOccurrences(of: "http://", with: "")

        // Remove common port numbers
        simplified = simplified
            .replacingOccurrences(of: ":8001", with: "")
            .replacingOccurrences(of: ":443", with: "")

        return simplified
    }
}

// MARK: - Token Expired State

private struct TokenExpiredView: View {
    @EnvironmentObject var connectivity: WatchConnectivityService

    var body: some View {
        VStack(spacing: 16) {
            // Icon
            ZStack {
                Circle()
                    .fill(Color.beacon.opacity(0.2))
                    .frame(width: 72, height: 72)

                Image(systemName: "clock.badge.exclamationmark")
                    .font(.system(size: 32))
                    .foregroundColor(.beacon)
            }
            .accessibilityHidden(true)

            Text("Session Expired")
                .font(WatchFonts.primary(.headline))
                .foregroundColor(.white)

            Text("Open iPhone to refresh")
                .font(WatchFonts.secondary(.subheadline))
                .foregroundColor(.secondary)
                .multilineTextAlignment(.center)

            if connectivity.isReachable {
                Button {
                    HapticPattern.listening.play()
                    connectivity.requestTokenRefresh()
                } label: {
                    HStack {
                        Image(systemName: "arrow.clockwise")
                        Text("Refresh Now")
                    }
                    .font(WatchFonts.secondary(.footnote))
                    .frame(maxWidth: .infinity)
                    .padding(.vertical, 12)
                    .background(Color.beacon.opacity(0.2))
                    .cornerRadius(10)
                }
                .buttonStyle(.plain)
                .accessibleButton(label: "Refresh session", hint: "Requests new authentication token from iPhone")
            }
        }
        .padding(.vertical, 16)
    }
}

// MARK: - Error State

private struct ErrorView: View {
    @EnvironmentObject var connectivity: WatchConnectivityService

    var body: some View {
        VStack(spacing: 16) {
            // Icon
            ZStack {
                Circle()
                    .fill(Color.safetyViolation.opacity(0.2))
                    .frame(width: 72, height: 72)

                Image(systemName: "exclamationmark.triangle")
                    .font(.system(size: 32))
                    .foregroundColor(.safetyViolation)
            }
            .accessibilityHidden(true)

            Text("Sign In Error")
                .font(WatchFonts.primary(.headline))
                .foregroundColor(.white)

            if let errorMsg = connectivity.authState.errorMessage {
                Text(errorMsg)
                    .font(WatchFonts.caption(.caption))
                    .foregroundColor(.secondary)
                    .multilineTextAlignment(.center)
                    .lineLimit(3)
            }

            // Retry button
            Button {
                HapticPattern.listening.play()
                connectivity.requestAuthFromiPhone()
            } label: {
                HStack {
                    Image(systemName: "arrow.clockwise")
                    Text("Try Again")
                }
                .font(WatchFonts.secondary(.footnote))
                .frame(maxWidth: .infinity)
                .padding(.vertical, 12)
                .background(Color.nexus.opacity(0.2))
                .cornerRadius(10)
            }
            .buttonStyle(.plain)
            .accessibleButton(label: "Try again", hint: "Attempts to sign in again")
        }
        .padding(.vertical, 16)
    }
}

// MARK: - Compact Login Status (for inline use)

struct LoginStatusBadge: View {
    @EnvironmentObject var connectivity: WatchConnectivityService

    var body: some View {
        NavigationLink {
            LoginView()
        } label: {
            HStack(spacing: 8) {
                Circle()
                    .fill(statusColor)
                    .frame(width: 8, height: 8)

                Text(statusText)
                    .font(WatchFonts.caption(.caption))
                    .foregroundColor(.secondary)

                Spacer()

                Image(systemName: "chevron.right")
                    .font(.system(size: 10))
                    .foregroundColor(.secondary)
            }
            .padding(.horizontal, 12)
            .padding(.vertical, 10)
            .background(
                RoundedRectangle(cornerRadius: 10)
                    .fill(Color.voidLight)
            )
        }
        .buttonStyle(.plain)
        .accessibleButton(
            label: "Account: \(statusText)",
            hint: "Opens account settings"
        )
    }

    private var statusColor: Color {
        switch connectivity.authState.status {
        case .authenticated: return .safetyOk
        case .authenticating: return .beacon
        case .tokenExpired: return .beacon
        case .error: return .safetyViolation
        case .unauthenticated: return .secondary
        }
    }

    private var statusText: String {
        switch connectivity.authState.status {
        case .authenticated:
            return connectivity.authState.displayName ?? connectivity.authState.username ?? "Signed In"
        case .authenticating:
            return "Signing In..."
        case .tokenExpired:
            return "Session Expired"
        case .error:
            return "Sign In Error"
        case .unauthenticated:
            return "Not Signed In"
        }
    }
}

// MARK: - Preview

#Preview("Unauthenticated") {
    let service = WatchConnectivityService()
    service.authState = WatchAuthState(status: .unauthenticated)

    return LoginView()
        .environmentObject(service)
}

#Preview("Authenticated") {
    let service = WatchConnectivityService()
    service.authState = WatchAuthState(
        status: .authenticated,
        accessToken: "mock-token",
        userId: "user-123",
        username: "tim",
        displayName: "Tim Jacoby",
        serverURL: "https://kagami.local:8001"
    )

    return LoginView()
        .environmentObject(service)
}

#Preview("Error") {
    let service = WatchConnectivityService()
    service.authState = WatchAuthState(
        status: .error,
        errorMessage: "iPhone not reachable"
    )

    return LoginView()
        .environmentObject(service)
}

/*
 * Kagami Watch Login
 *
 * Authentication flows through the iPhone companion app.
 * The watch is an extension of presence, not a standalone identity.
 *
 * h(x) >= 0. Always.
 */
