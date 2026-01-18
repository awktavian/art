//
// ContentView.swift — Kagami Main Interface
//
// Smart home control interface with scene buttons.
// h(x) ≥ 0. Always.
//

import SwiftUI

struct ContentView: View {
    @EnvironmentObject var homeState: HomeState

    var body: some View {
        NavigationStack {
            ScrollView {
                VStack(spacing: 24) {
                    // Status Header
                    statusHeader

                    // Last Action
                    if let action = homeState.lastAction {
                        Text(action)
                            .font(.headline)
                            .foregroundColor(.white)
                            .padding()
                            .background(Color.black.opacity(0.3))
                            .cornerRadius(12)
                            .transition(.scale.combined(with: .opacity))
                    }

                    // Scenes Section
                    sectionHeader("Scenes")
                    LazyVGrid(columns: [GridItem(.flexible()), GridItem(.flexible())], spacing: 16) {
                        SceneButton(title: "Movie Mode", icon: "film.fill", color: .purple) {
                            await homeState.executeScene("movie-mode/enter")
                        }
                        SceneButton(title: "Goodnight", icon: "moon.fill", color: .indigo) {
                            await homeState.executeScene("goodnight")
                        }
                        SceneButton(title: "Welcome Home", icon: "house.fill", color: .orange) {
                            await homeState.executeScene("welcome-home")
                        }
                        SceneButton(title: "Away", icon: "car.fill", color: .blue) {
                            await homeState.executeScene("away")
                        }
                    }
                    .padding(.horizontal)

                    // Lights Section
                    sectionHeader("Lights")
                    VStack(spacing: 12) {
                        HStack(spacing: 12) {
                            LightButton(level: 100, current: homeState.lightsLevel) {
                                await homeState.setLights(100)
                            }
                            LightButton(level: 75, current: homeState.lightsLevel) {
                                await homeState.setLights(75)
                            }
                            LightButton(level: 50, current: homeState.lightsLevel) {
                                await homeState.setLights(50)
                            }
                            LightButton(level: 0, current: homeState.lightsLevel) {
                                await homeState.setLights(0)
                            }
                        }
                    }
                    .padding(.horizontal)

                    // Controls Section
                    sectionHeader("Controls")
                    HStack(spacing: 16) {
                        ControlButton(
                            title: "Fireplace",
                            icon: "flame.fill",
                            isActive: homeState.fireplaceOn,
                            color: .orange
                        ) {
                            await homeState.toggleFireplace(!homeState.fireplaceOn)
                        }

                        ControlButton(
                            title: "Shades",
                            icon: homeState.shadesOpen ? "blinds.horizontal.open" : "blinds.horizontal.closed",
                            isActive: homeState.shadesOpen,
                            color: .cyan
                        ) {
                            await homeState.controlShades(homeState.shadesOpen ? "close" : "open")
                        }
                    }
                    .padding(.horizontal)

                    Spacer(minLength: 40)
                }
                .padding(.top)
            }
            .background(
                LinearGradient(
                    colors: [Color(hex: "0D0D0D"), Color(hex: "1A1A1A")],
                    startPoint: .top,
                    endPoint: .bottom
                )
            )
            .navigationTitle("🪞 Kagami")
            .navigationBarTitleDisplayMode(.large)
            .toolbarColorScheme(.dark, for: .navigationBar)
        }
    }

    // MARK: - Components

    var statusHeader: some View {
        HStack(spacing: 8) {
            // Connection status pill badge
            HStack(spacing: 6) {
                Circle()
                    .fill(homeState.isConnected ? Color.green : Color.red)
                    .frame(width: 8, height: 8)
                Text(homeState.isConnected ? "Connected" : "Offline")
                    .font(.caption.weight(.semibold))
                    .foregroundColor(homeState.isConnected ? .green : .red)
            }
            .padding(.horizontal, 12)
            .padding(.vertical, 6)
            .background(
                Capsule()
                    .fill((homeState.isConnected ? Color.green : Color.red).opacity(0.15))
            )
            .accessibilityElement(children: .combine)
            .accessibilityLabel("Connection status: \(homeState.isConnected ? "Connected" : "Offline")")

            Spacer()

            if homeState.isLoading {
                ProgressView()
                    .scaleEffect(0.8)
                    .tint(.white.opacity(0.6))
            }
        }
        .padding(.horizontal)
    }

    func sectionHeader(_ title: String) -> some View {
        HStack {
            Text(title)
                .font(.title3.weight(.bold))
                .foregroundColor(.white.opacity(0.9))
                .tracking(0.5)
            Spacer()
        }
        .padding(.horizontal)
        .padding(.top, 12)
        .accessibilityAddTraits(.isHeader)
    }
}

// MARK: - Scene Button

struct SceneButton: View {
    let title: String
    let icon: String
    let color: Color
    let action: () async -> Void

    @State private var isPressed = false

    var body: some View {
        Button {
            Task {
                await action()
            }
        } label: {
            VStack(spacing: 12) {
                Image(systemName: icon)
                    .font(.system(size: 30, weight: .medium))
                    .foregroundColor(color)
                    .symbolEffect(.bounce, value: isPressed)

                Text(title)
                    .font(.subheadline.weight(.semibold))
                    .foregroundColor(.white)
                    .lineLimit(1)
                    .minimumScaleFactor(0.8)
            }
            .frame(maxWidth: .infinity)
            .padding(.vertical, 26)
            .background(
                RoundedRectangle(cornerRadius: 18)
                    .fill(Color.white.opacity(0.08))
                    .overlay(
                        RoundedRectangle(cornerRadius: 18)
                            .stroke(color.opacity(0.35), lineWidth: 1.5)
                    )
            )
        }
        .buttonStyle(ScaleButtonStyle())
        .accessibilityLabel("Activate \(title) scene")
        .accessibilityHint("Double tap to activate")
    }
}

// MARK: - Light Button

struct LightButton: View {
    let level: Int
    let current: Int
    let action: () async -> Void

    var isSelected: Bool { current == level }

    var body: some View {
        Button {
            Task {
                await action()
            }
        } label: {
            VStack(spacing: 6) {
                Image(systemName: level == 0 ? "lightbulb.slash.fill" : "lightbulb.fill")
                    .font(.system(size: 22, weight: .medium))
                    .foregroundColor(isSelected ? .yellow : .gray)
                    .symbolEffect(.pulse, options: .repeating, isActive: isSelected && level > 0)

                Text("\(level)%")
                    .font(.footnote.weight(.bold))
                    .foregroundColor(isSelected ? .white : .secondary)
            }
            .frame(maxWidth: .infinity)
            .padding(.vertical, 18)
            .background(
                RoundedRectangle(cornerRadius: 14)
                    .fill(isSelected ? Color.yellow.opacity(0.2) : Color.white.opacity(0.06))
                    .overlay(
                        RoundedRectangle(cornerRadius: 14)
                            .stroke(isSelected ? Color.yellow.opacity(0.4) : Color.clear, lineWidth: 1.5)
                    )
            )
        }
        .buttonStyle(ScaleButtonStyle())
        .accessibilityLabel("Light level \(level) percent")
        .accessibilityValue(isSelected ? "Selected" : "Not selected")
        .accessibilityHint("Double tap to set lights to \(level) percent")
    }
}

// MARK: - Control Button

struct ControlButton: View {
    let title: String
    let icon: String
    let isActive: Bool
    let color: Color
    let action: () async -> Void

    var body: some View {
        Button {
            Task {
                await action()
            }
        } label: {
            VStack(spacing: 10) {
                Image(systemName: icon)
                    .font(.system(size: 34, weight: .medium))
                    .foregroundColor(isActive ? color : .gray)
                    .contentTransition(.symbolEffect(.replace))

                Text(title)
                    .font(.subheadline.weight(.semibold))
                    .foregroundColor(isActive ? .white : .secondary)
            }
            .frame(maxWidth: .infinity)
            .padding(.vertical, 26)
            .background(
                RoundedRectangle(cornerRadius: 18)
                    .fill(isActive ? color.opacity(0.2) : Color.white.opacity(0.06))
                    .overlay(
                        RoundedRectangle(cornerRadius: 18)
                            .stroke(isActive ? color.opacity(0.5) : Color.clear, lineWidth: 2)
                    )
            )
        }
        .buttonStyle(ScaleButtonStyle())
        .accessibilityLabel("\(title), \(isActive ? "on" : "off")")
        .accessibilityHint("Double tap to toggle")
        .accessibilityAddTraits(isActive ? .isSelected : [])
    }
}

// MARK: - Button Style

struct ScaleButtonStyle: ButtonStyle {
    func makeBody(configuration: Configuration) -> some View {
        configuration.label
            .scaleEffect(configuration.isPressed ? 0.96 : 1.0)
            .animation(.spring(response: 0.3, dampingFraction: 0.6), value: configuration.isPressed)
    }
}

// MARK: - Color Extension

extension Color {
    init(hex: String) {
        let hex = hex.trimmingCharacters(in: CharacterSet.alphanumerics.inverted)
        var int: UInt64 = 0
        Scanner(string: hex).scanHexInt64(&int)
        let a, r, g, b: UInt64
        switch hex.count {
        case 3:
            (a, r, g, b) = (255, (int >> 8) * 17, (int >> 4 & 0xF) * 17, (int & 0xF) * 17)
        case 6:
            (a, r, g, b) = (255, int >> 16, int >> 8 & 0xFF, int & 0xFF)
        case 8:
            (a, r, g, b) = (int >> 24, int >> 16 & 0xFF, int >> 8 & 0xFF, int & 0xFF)
        default:
            (a, r, g, b) = (255, 0, 0, 0)
        }
        self.init(
            .sRGB,
            red: Double(r) / 255,
            green: Double(g) / 255,
            blue: Double(b) / 255,
            opacity: Double(a) / 255
        )
    }
}

#Preview {
    ContentView()
        .environmentObject(HomeState())
}
