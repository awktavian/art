//
// ScenesView.swift — Scene Activation
//
// Glass effects with discovery states, chromatic feedback, RTL, and Dynamic Type.
//

import SwiftUI
import KagamiDesign

struct ScenesView: View {
    @Environment(\.layoutDirection) private var layoutDirection
    @Environment(\.dynamicTypeSize) private var dynamicTypeSize

    let scenes = [
        KagamiScene(id: "movie_mode", name: "Movie Mode", icon: "film.fill", description: "Dim lights, lower TV, close shades", color: .forge, shortcut: "\"Hey Siri, movie mode\""),
        KagamiScene(id: "goodnight", name: "Goodnight", icon: "moon.stars.fill", description: "All lights off, lock doors, sweet dreams", color: .flow, shortcut: "\"Hey Siri, goodnight\""),
        KagamiScene(id: "welcome_home", name: "Welcome Home", icon: "house.fill", description: "Warm lights, open shades, you're back!", color: .beacon, shortcut: "\"Hey Siri, I'm home\""),
        KagamiScene(id: "away", name: "Away Mode", icon: "lock.shield.fill", description: "Secure house, reduce energy", color: .crystal, shortcut: "\"Hey Siri, I'm leaving\""),
        KagamiScene(id: "focus", name: "Focus Mode", icon: "scope", description: "Bright lights, no distractions", color: .spark, shortcut: "\"Hey Siri, focus mode\""),
        KagamiScene(id: "relax", name: "Relax", icon: "flame.fill", description: "Dim lights, fireplace on, unwind", color: .grove, shortcut: "\"Hey Siri, relax mode\""),
        KagamiScene(id: "coffee", name: "Coffee Time", icon: "cup.and.saucer.fill", description: "Bright kitchen, start the day right", color: .nexus, shortcut: "\"Hey Siri, coffee time\""),
    ]

    var body: some View {
        NavigationStack {
            ScrollView {
                LazyVStack(spacing: 12) {
                    ForEach(Array(scenes.enumerated()), id: \.element.id) { index, scene in
                        SceneRow(scene: scene, elementId: index)
                            .accessibilityIdentifier(AccessibilityIdentifiers.Scenes.row(scene.id))
                    }
                }
                .padding()
            }
            .background(
                ZStack {
                    Color.void.ignoresSafeArea()
                    CausticBackground()
                        .opacity(0.5)
                        .ignoresSafeArea()
                }
            )
            .navigationTitle("Scenes")
            .accessibilityIdentifier(AccessibilityIdentifiers.Scenes.list)
        }
        .accessibilityIdentifier(AccessibilityIdentifiers.Scenes.view)
    }
}

struct KagamiScene: Identifiable {
    let id: String
    let name: String
    let icon: String  // SF Symbol name
    let description: String
    let color: Color
    let shortcut: String  // Siri shortcut phrase
}

struct SceneRow: View {
    let scene: KagamiScene
    let elementId: Int

    @State private var showSuccess = false
    @State private var isExecuting = false
    @State private var isPressed = false
    @Environment(\.accessibilityReduceMotion) private var reduceMotion
    @Environment(\.layoutDirection) private var layoutDirection

    private let impactFeedback = UIImpactFeedbackGenerator(style: .medium)
    private let successFeedback = UINotificationFeedbackGenerator()

    var body: some View {
        Button {
            guard !isExecuting else { return }
            impactFeedback.impactOccurred()
            isExecuting = true

            Task {
                await KagamiAPIService.shared.executeScene(scene.id)
                await MainActor.run {
                    successFeedback.notificationOccurred(.success)
                    showSuccess = true
                    isExecuting = false
                }
            }
        } label: {
            HStack(spacing: KagamiSpacing.md) {
                // Icon with glow effect
                ZStack {
                    // Glow ring
                    Circle()
                        .fill(scene.color.opacity(0.15))
                        .frame(width: 52, height: 52)

                    // Icon
                    Image(systemName: scene.icon)
                        .font(.title2)
                        .foregroundColor(scene.color)
                        .symbolRenderingMode(.hierarchical)
                }
                .prismGlow(color: scene.color, radius: isExecuting ? 12 : 0, animated: isExecuting)

                VStack(alignment: .leading, spacing: 4) {
                    Text(scene.name)
                        .font(KagamiFont.headline())
                        .foregroundColor(.accessibleTextPrimary)

                    Text(scene.description)
                        .font(KagamiFont.body())
                        .foregroundColor(.accessibleTextSecondary)
                        .lineLimit(2)

                    // Siri shortcut hint
                    Text(scene.shortcut)
                        .font(KagamiFont.caption())
                        .foregroundColor(scene.color.opacity(0.7))
                        .italic()
                }

                Spacer()

                // Status indicator
                if isExecuting {
                    ProgressView()
                        .progressViewStyle(CircularProgressViewStyle(tint: scene.color))
                        .scaleEffect(0.9)
                } else if showSuccess {
                    // Playful easing for scene activation flash (attention-grabbing)
                    Image(systemName: "checkmark.circle.fill")
                        .font(.title3)
                        .foregroundColor(.safetyOk)
                        .transition(.scale.combined(with: .opacity).animation(KagamiMotion.butterfly))
                } else {
                    Image(systemName: layoutDirection == .rightToLeft ? "chevron.left" : "chevron.right")
                        .font(.body)
                        .foregroundColor(.accessibleTextTertiary)
                }
            }
            .frame(minHeight: 80)
            .padding(.horizontal, KagamiSpacing.md)
            .padding(.vertical, KagamiSpacing.sm)
        }
        .buttonStyle(.plain)
        .background(
            RoundedRectangle(cornerRadius: KagamiRadius.lg)
                .fill(.ultraThinMaterial)
                .overlay(
                    RoundedRectangle(cornerRadius: KagamiRadius.lg)
                        .stroke(
                            LinearGradient(
                                colors: [scene.color.opacity(0.3), scene.color.opacity(0.1)],
                                startPoint: .topLeading,
                                endPoint: .bottomTrailing
                            ),
                            lineWidth: 1
                        )
                )
        )
        .scaleEffect(isPressed && !reduceMotion ? 0.97 : 1.0)
        .animation(.spring(response: 0.2, dampingFraction: 0.7), value: isPressed)
        .chromaticEdge(
            dispersion: 2,
            refraction: 0.6,
            isActive: !reduceMotion
        )
        .chromaticPulse(isTriggered: $showSuccess, color: scene.color)
        .spectralDiscovery()
        .simultaneousGesture(
            DragGesture(minimumDistance: 0)
                .onChanged { _ in isPressed = true }
                .onEnded { _ in isPressed = false }
        )
        .accessibilityLabel("\(scene.name) scene")
        .accessibilityHint("\(scene.description). Say \(scene.shortcut) to activate with Siri")
        .onChange(of: showSuccess) { _, newValue in
            if newValue {
                // Reset success state after delay
                DispatchQueue.main.asyncAfter(deadline: .now() + 2) {
                    withAnimation { showSuccess = false }
                }
            }
        }
    }
}
