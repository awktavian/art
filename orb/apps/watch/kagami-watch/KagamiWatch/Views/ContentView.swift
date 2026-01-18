//
// ContentView.swift — Main watchOS Content View
//
// Colony: Nexus (e4) — Integration
// Enhanced with: RTL support, accessibility, microinteractions, delight
//
// The primary view for the Kagami watchOS app.
// Shows quick actions and voice command interface.
//
// h(x) >= 0. Always.
//
// 鏡

import SwiftUI
import KagamiDesign

/// Main content view for watchOS
/// Optimized for glanceability and 44pt minimum touch targets
struct ContentView: View {
    @EnvironmentObject var connectivity: WatchConnectivityService
    @State private var showingVoice = false
    @State private var showingRooms = false
    @Environment(\.accessibilityReduceMotion) private var reduceMotion

    var body: some View {
        NavigationStack {
            ScrollView {
                VStack(spacing: 16) {
                    // Status Header
                    statusHeader

                    // Quick Actions
                    quickActions

                    // Safety Footer
                    safetyFooter
                }
                .padding()
            }
            .navigationTitle("Kagami")
            .toolbar {
                ToolbarItem(placement: .topBarTrailing) {
                    Button(action: {
                        WKInterfaceDevice.current().play(.click)
                        showingVoice = true
                    }) {
                        Image(systemName: "mic.fill")
                            .symbolRenderingMode(.hierarchical)
                            .foregroundStyle(Color.crystal)
                    }
                    .accessibilityLabel("Voice command")
                    .accessibilityHint("Double tap to speak a command")
                }
            }
        }
        .sheet(isPresented: $showingVoice) {
            VoiceCommandView()
        }
        .sheet(isPresented: $showingRooms) {
            RoomsListView()
        }
    }

    // MARK: - Status Header

    private var statusHeader: some View {
        VStack(spacing: 10) {
            // Connection status with animated indicator
            HStack(spacing: 8) {
                // Pulsing status dot
                Circle()
                    .fill(connectivity.authState.isAuthenticated ? Color.grove : Color.beacon)
                    .frame(width: 8, height: 8)
                    .overlay(
                        Circle()
                            .stroke(
                                connectivity.authState.isAuthenticated ? Color.grove.opacity(0.4) : Color.beacon.opacity(0.4),
                                lineWidth: 2
                            )
                            .scaleEffect(reduceMotion ? 1.0 : 1.5)
                            .opacity(reduceMotion ? 1.0 : 0)
                            .animation(
                                reduceMotion ? nil : Animation.easeInOut(duration: WatchMotion.slow * 4).repeatForever(autoreverses: false),
                                value: connectivity.authState.isAuthenticated
                            )
                    )

                Text(connectivity.authState.isAuthenticated ? "Connected" : "Connecting...")
                    .font(WatchFonts.caption())
                    .foregroundColor(.secondary)

                Spacer()

                // Mini latency badge
                if connectivity.authState.isAuthenticated {
                    HStack(spacing: 2) {
                        Image(systemName: "bolt.fill")
                            .font(.system(size: 8))
                        Text("OK")
                            .font(WatchFonts.mono(.caption2))
                    }
                    .foregroundColor(.grove.opacity(0.8))
                }
            }

            // User greeting
            if let username = connectivity.authState.username {
                HStack(spacing: 6) {
                    Image(systemName: "person.crop.circle.fill")
                        .font(.headline)
                        .foregroundColor(.nexus)

                    VStack(alignment: .leading, spacing: 1) {
                        Text("Hello,")
                            .font(WatchFonts.caption(.caption2))
                            .foregroundColor(.secondary)
                        Text(username)
                            .font(WatchFonts.primary())
                            .alwaysOnText()
                    }

                    Spacer()
                }
            }
        }
        .padding(12)
        .background(.ultraThinMaterial)
        .cornerRadius(10) // Standardized watchCard corner radius
        .accessibilityElement(children: .combine)
        .accessibilityLabel(connectivity.authState.isAuthenticated
            ? "Connected to Kagami. \(connectivity.authState.username.map { "Hello, \($0)" } ?? "")"
            : "Connecting to Kagami"
        )
    }

    // MARK: - Quick Actions

    private var quickActions: some View {
        VStack(spacing: 10) {
            HStack {
                Text("Quick Actions")
                    .font(WatchFonts.caption())
                    .fontWeight(.medium)
                    .foregroundColor(.secondary)
                Spacer()
            }

            LazyVGrid(columns: [GridItem(.flexible()), GridItem(.flexible())], spacing: 10) {
                QuickActionButton(
                    title: "Goodnight",
                    icon: "moon.stars.fill",
                    color: .flow  // evening/calm scene
                ) {
                    Task {
                        _ = await KagamiAPIService.shared.executeScene("goodnight")
                    }
                }
                .accessibilityLabel("Goodnight")
                .accessibilityHint("Double tap to activate goodnight scene")

                QuickActionButton(
                    title: "Movie",
                    icon: "film.fill",
                    color: .spark  // fire/energy for entertainment
                ) {
                    Task {
                        _ = await KagamiAPIService.shared.executeScene("movie_mode")
                    }
                }
                .accessibilityLabel("Movie mode")
                .accessibilityHint("Double tap to activate movie mode scene")

                QuickActionButton(
                    title: "Rooms",
                    icon: "square.grid.2x2.fill",
                    color: .nexus  // rooms/connection
                ) {
                    showingRooms = true
                }
                .accessibilityLabel("Rooms")
                .accessibilityHint("Double tap to view and control rooms")

                QuickActionButton(
                    title: "Voice",
                    icon: "waveform",
                    color: .crystal  // voice/clarity
                ) {
                    showingVoice = true
                }
                .accessibilityLabel("Voice command")
                .accessibilityHint("Double tap to speak a voice command")
            }
        }
    }

    // MARK: - Safety Footer

    private var safetyFooter: some View {
        HStack(spacing: 4) {
            Image(systemName: "checkmark.shield.fill")
                .font(.system(size: 10))
                .foregroundColor(.safetyOk.opacity(0.5))
            Text("Protected")
                .font(WatchFonts.mono(.caption2))
                .foregroundColor(.safetyOk.opacity(0.6))
        }
        .padding(.top, 8)
        .alwaysOnOptimized(isEssential: true)
        .accessibilityLabel("System is protected and operating safely")
    }
}

// MARK: - Quick Action Button

/// Glanceable button optimized for watchOS
/// Meets 44pt minimum touch target requirement
struct QuickActionButton: View {
    let title: String
    let icon: String
    let color: Color
    let action: () -> Void

    var body: some View {
        Button(action: {
            WKInterfaceDevice.current().play(.click)
            action()
        }) {
            VStack(spacing: 6) {
                Image(systemName: icon)
                    .font(.title3)
                    .foregroundColor(color)
                    .symbolRenderingMode(.hierarchical)

                Text(title)
                    .font(WatchFonts.caption(.caption))
                    .foregroundColor(.primary)
            }
            .frame(maxWidth: .infinity)
            .frame(minHeight: 52)  // Generous touch target
            .background(color.opacity(0.12))
            .cornerRadius(10)  // Standardized watchCard corner radius
            .overlay(
                RoundedRectangle(cornerRadius: 10)
                    .stroke(color.opacity(0.2), lineWidth: 1)
            )
        }
        .buttonStyle(.plain)
        .watchPressEffect()
    }
}

// MARK: - Preview

#Preview {
    ContentView()
        .environmentObject(WatchConnectivityService())
}
