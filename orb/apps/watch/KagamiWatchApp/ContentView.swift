//
// ContentView.swift — Kagami Watch Interface
//
// Glanceable smart home control with context-aware suggestions.
// Colony: Nexus (e4) — Integration
// h(x) ≥ 0. Always.
//

import SwiftUI

struct ContentView: View {
    @EnvironmentObject var homeState: WatchHomeState

    var body: some View {
        NavigationStack {
            ScrollView {
                VStack(spacing: 12) {
                    // Status
                    HStack {
                        Circle()
                            .fill(homeState.isConnected ? Color.green : Color.red)
                            .frame(width: 8, height: 8)
                        Text(homeState.isConnected ? "Connected" : "Offline")
                            .font(.caption2)
                            .foregroundColor(.secondary)

                        if !homeState.offlineQueue.isEmpty {
                            Text("(\(homeState.offlineQueue.count) queued)")
                                .font(.caption2)
                                .foregroundColor(.orange)
                        }

                        Spacer()
                        if homeState.isLoading {
                            ProgressView()
                                .scaleEffect(0.7)
                        }
                    }
                    .padding(.horizontal, 4)

                    // Last action
                    if let action = homeState.lastAction {
                        Text(action)
                            .font(.caption)
                            .foregroundColor(.orange)
                            .transition(.scale.combined(with: .opacity))
                    }

                    // Suggested Action (Context-Aware)
                    if let suggested = homeState.context.suggestedAction {
                        SuggestedActionCard(
                            title: suggested.title,
                            icon: suggested.icon,
                            color: suggested.color
                        ) {
                            await homeState.executeSuggestedAction()
                        }
                    }

                    Divider()
                        .padding(.vertical, 2)

                    // Scenes
                    VStack(spacing: 8) {
                        WatchButton(
                            title: "Movie Mode",
                            icon: "film.fill",
                            color: .purple
                        ) {
                            await homeState.executeScene("movie-mode/enter")
                        }

                        WatchButton(
                            title: "Goodnight",
                            icon: "moon.fill",
                            color: .indigo
                        ) {
                            await homeState.executeScene("goodnight")
                        }

                        WatchButton(
                            title: "Welcome Home",
                            icon: "house.fill",
                            color: .orange
                        ) {
                            await homeState.executeScene("welcome-home")
                        }

                        WatchButton(
                            title: "Away",
                            icon: "car.fill",
                            color: .blue
                        ) {
                            await homeState.executeScene("away")
                        }
                    }

                    Divider()
                        .padding(.vertical, 4)

                    // Quick Actions
                    HStack(spacing: 8) {
                        QuickButton(icon: "lightbulb.fill", color: .yellow) {
                            await homeState.setLights(100)
                        }
                        QuickButton(icon: "lightbulb.slash.fill", color: .gray) {
                            await homeState.setLights(0)
                        }
                        QuickButton(icon: "flame.fill", color: .orange) {
                            await homeState.toggleFireplace(true)
                        }
                    }
                }
                .padding(.horizontal, 4)
            }
            .navigationTitle("🪞 Kagami")
            .navigationBarTitleDisplayMode(.inline)
        }
    }
}

// MARK: - Suggested Action Card

struct SuggestedActionCard: View {
    let title: String
    let icon: String
    let color: Color
    let action: () async -> Void

    var body: some View {
        Button {
            Task {
                await action()
            }
        } label: {
            VStack(spacing: 6) {
                Image(systemName: icon)
                    .font(.title2)
                    .foregroundColor(color)
                Text(title)
                    .font(.caption.bold())
                    .foregroundColor(.white)
            }
            .frame(maxWidth: .infinity)
            .padding(.vertical, 12)
            .background(
                RoundedRectangle(cornerRadius: 12)
                    .fill(color.opacity(0.3))
                    .overlay(
                        RoundedRectangle(cornerRadius: 12)
                            .stroke(color.opacity(0.6), lineWidth: 2)
                    )
            )
        }
        .buttonStyle(.plain)
    }
}

// MARK: - Watch Button

struct WatchButton: View {
    let title: String
    let icon: String
    let color: Color
    let action: () async -> Void

    var body: some View {
        Button {
            Task {
                await action()
            }
        } label: {
            HStack {
                Image(systemName: icon)
                    .foregroundColor(color)
                Text(title)
                    .font(.footnote)
                Spacer()
                Image(systemName: "chevron.right")
                    .font(.caption2)
                    .foregroundColor(.secondary)
            }
            .padding(.horizontal, 12)
            .padding(.vertical, 10)
            .background(Color.white.opacity(0.08))
            .cornerRadius(12)
        }
        .buttonStyle(.plain)
    }
}

// MARK: - Quick Button

struct QuickButton: View {
    let icon: String
    let color: Color
    let action: () async -> Void

    var body: some View {
        Button {
            Task {
                await action()
            }
        } label: {
            Image(systemName: icon)
                .font(.title3)
                .foregroundColor(color)
                .frame(width: 44, height: 44)
                .background(color.opacity(0.2))
                .cornerRadius(22)
        }
        .buttonStyle(.plain)
    }
}

#Preview {
    ContentView()
        .environmentObject(WatchHomeState())
}
