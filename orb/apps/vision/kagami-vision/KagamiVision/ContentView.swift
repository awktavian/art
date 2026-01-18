//
// ContentView.swift
// KagamiVision
//
// Main content view for Kagami Vision Pro app.
//

import SwiftUI

struct ContentView: View {
    @EnvironmentObject var appModel: AppModel
    @EnvironmentObject var healthService: HealthKitService
    @Environment(\.accessibilityReduceMotion) private var reduceMotion

    // Staggered entrance animation state
    @State private var cardsAppeared: [Bool] = [false, false, false, false]

    // Quick actions data
    private let quickActions: [(title: String, icon: String, index: Int)] = [
        ("Lights", "lightbulb.fill", 0),
        ("Movie Mode", "film.fill", 1),
        ("Goodnight", "moon.fill", 2),
        ("All Off", "power", 3)
    ]

    var body: some View {
        NavigationStack {
            VStack(spacing: 20) {
                // Kagami logo/header
                Text("Kagami")
                    .font(.largeTitle)
                    .fontWeight(.bold)

                // Quick actions with staggered entrance animations
                LazyVGrid(columns: [GridItem(.flexible()), GridItem(.flexible())], spacing: 16) {
                    ForEach(0..<4, id: \.self) { index in
                        quickActionView(for: index)
                            .opacity(cardsAppeared[index] ? 1 : 0)
                            .offset(y: cardsAppeared[index] ? 0 : 20)
                            .animation(
                                reduceMotion ? nil :
                                    .spring(response: 0.233, dampingFraction: 0.8)
                                    .delay(Double(index) * 0.144),  // 144ms Fibonacci stagger
                                value: cardsAppeared[index]
                            )
                    }
                }
                .padding()

                Spacer()
            }
            .navigationTitle("Home")
            .task {
                // Trigger staggered entrance animation
                for index in 0..<4 {
                    try? await Task.sleep(nanoseconds: UInt64(index) * 144_000_000)  // 144ms Fibonacci
                    withAnimation {
                        cardsAppeared[index] = true
                    }
                }
            }
        }
    }

    @ViewBuilder
    private func quickActionView(for index: Int) -> some View {
        switch index {
        case 0:
            QuickActionCard(title: "Lights", icon: "lightbulb.fill", action: {
                Task { await appModel.apiService.setLights(100) }
            })
        case 1:
            QuickActionCard(title: "Movie Mode", icon: "film.fill", action: {
                Task { try? await appModel.apiService.executeScene("movie_mode") }
            })
        case 2:
            QuickActionCard(title: "Goodnight", icon: "moon.fill", action: {
                Task { try? await appModel.apiService.executeScene("goodnight") }
            })
        case 3:
            QuickActionCard(title: "All Off", icon: "power", action: {
                Task { await appModel.apiService.setLights(0) }
            })
        default:
            EmptyView()
        }
    }
}

struct QuickActionCard: View {
    let title: String
    let icon: String
    let action: () -> Void

    var body: some View {
        Button(action: action) {
            VStack(spacing: 12) {
                Image(systemName: icon)
                    .font(.system(size: 32))
                    .foregroundColor(.crystal)

                Text(title)
                    .font(.headline)
            }
            .frame(maxWidth: .infinity)
            .padding(.vertical, 24)
        }
        .buttonStyle(OrnamentButtonStyle(color: .crystal))
        .background(.regularMaterial, in: RoundedRectangle(cornerRadius: 16))
        .accessibilityLabel(title)
        .accessibilityHint("Activate \(title.lowercased()) control")
    }
}

#Preview {
    ContentView()
        .environmentObject(AppModel())
        .environmentObject(HealthKitService())
}
