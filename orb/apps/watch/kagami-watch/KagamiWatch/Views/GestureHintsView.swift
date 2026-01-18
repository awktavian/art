//
// GestureHintsView.swift — Interactive Gesture Tutorials
//
// Colony: Crystal (e7) — Verification
//
// P1 Core Quality: Teach crown/swipe interactions.
// Implements:
//   - Animated demo on first launch
//   - "Turn crown to select" overlay
//   - 3-second help bubble
//   - Accessibility support
//
// Per audit: Required for 100/100 user score
//
// h(x) >= 0. Always.
//

import SwiftUI
import WatchKit

// MARK: - Gesture Hint Types

enum GestureHintType: String, CaseIterable {
    case doubleTap = "double_tap"
    case crownRotation = "crown_rotation"
    case swipeNavigation = "swipe_navigation"
    case longPress = "long_press"
    case voiceCommand = "voice_command"

    var title: String {
        switch self {
        case .doubleTap: return "Double-Tap"
        case .crownRotation: return "Digital Crown"
        case .swipeNavigation: return "Swipe Navigation"
        case .longPress: return "Long Press"
        case .voiceCommand: return "Voice Command"
        }
    }

    var description: String {
        switch self {
        case .doubleTap: return "Double-tap with two fingers to instantly activate the hero action"
        case .crownRotation: return "Rotate the Digital Crown to adjust light brightness"
        case .swipeNavigation: return "Swipe left or right to navigate between screens"
        case .longPress: return "Long press on a control for more options"
        case .voiceCommand: return "Tap the microphone to speak a command"
        }
    }

    var icon: String {
        switch self {
        case .doubleTap: return "hand.tap"
        case .crownRotation: return "digitalcrown.horizontal.arrow.clockwise.fill"
        case .swipeNavigation: return "hand.draw"
        case .longPress: return "hand.point.up.left.fill"
        case .voiceCommand: return "mic.fill"
        }
    }

    var accentColor: Color {
        switch self {
        case .doubleTap: return .crystal
        case .crownRotation: return .beacon
        case .swipeNavigation: return .flow
        case .longPress: return .nexus
        case .voiceCommand: return .spark
        }
    }
}

// MARK: - Gesture Hint Manager

@MainActor
final class GestureHintManager: ObservableObject {

    // MARK: - Singleton

    static let shared = GestureHintManager()

    // MARK: - Published State

    @Published var currentHint: GestureHintType?
    @Published var hintsShown: Set<GestureHintType> = []
    @Published var isShowingHint: Bool = false

    // MARK: - Configuration

    private let hintDisplayDuration: TimeInterval = 3.0
    private let userDefaultsKey = "shownGestureHints"

    // MARK: - Initialization

    private init() {
        loadShownHints()
    }

    // MARK: - Hint Display

    /// Show a gesture hint if not already shown
    func showHintIfNeeded(_ hint: GestureHintType) {
        guard !hintsShown.contains(hint) else { return }

        currentHint = hint
        isShowingHint = true

        // Auto-dismiss after duration
        DispatchQueue.main.asyncAfter(deadline: .now() + hintDisplayDuration) { [weak self] in
            self?.dismissHint()
        }
    }

    /// Force show a hint (for tutorial/help)
    func forceShowHint(_ hint: GestureHintType) {
        currentHint = hint
        isShowingHint = true

        DispatchQueue.main.asyncAfter(deadline: .now() + hintDisplayDuration) { [weak self] in
            self?.dismissHint()
        }
    }

    /// Dismiss current hint
    func dismissHint() {
        guard let hint = currentHint else { return }

        withAnimation(.easeOut(duration: 0.3)) {
            isShowingHint = false
        }

        // Mark as shown
        hintsShown.insert(hint)
        saveShownHints()

        // Clear current hint after animation
        DispatchQueue.main.asyncAfter(deadline: .now() + 0.3) { [weak self] in
            self?.currentHint = nil
        }
    }

    /// Reset all hints (for testing/debug)
    func resetAllHints() {
        hintsShown.removeAll()
        UserDefaults.standard.removeObject(forKey: userDefaultsKey)
    }

    // MARK: - Persistence

    private func loadShownHints() {
        guard let data = UserDefaults.standard.data(forKey: userDefaultsKey),
              let hints = try? JSONDecoder().decode([String].self, from: data) else {
            return
        }
        hintsShown = Set(hints.compactMap { GestureHintType(rawValue: $0) })
    }

    private func saveShownHints() {
        let hintsArray = hintsShown.map { $0.rawValue }
        guard let data = try? JSONEncoder().encode(hintsArray) else { return }
        UserDefaults.standard.set(data, forKey: userDefaultsKey)
    }
}

// MARK: - Gesture Hint Overlay View

/// Floating hint bubble that appears over content
struct GestureHintOverlay: View {
    @StateObject private var hintManager = GestureHintManager.shared
    @Environment(\.accessibilityReduceMotion) var reduceMotion

    var body: some View {
        ZStack {
            if hintManager.isShowingHint, let hint = hintManager.currentHint {
                GestureHintBubble(hint: hint)
                    .transition(reduceMotion ? .opacity : .scale.combined(with: .opacity))
                    .onTapGesture {
                        hintManager.dismissHint()
                    }
            }
        }
        .animation(reduceMotion ? nil : .spring(response: 0.3, dampingFraction: 0.7), value: hintManager.isShowingHint)
    }
}

/// Individual hint bubble
struct GestureHintBubble: View {
    let hint: GestureHintType
    @State private var isAnimating = false
    @Environment(\.accessibilityReduceMotion) var reduceMotion

    var body: some View {
        VStack(spacing: 8) {
            // Animated icon
            ZStack {
                Circle()
                    .fill(hint.accentColor.opacity(0.2))
                    .frame(width: 50, height: 50)
                    .scaleEffect(reduceMotion ? 1.0 : (isAnimating ? 1.2 : 1.0))
                    .opacity(reduceMotion ? 0.2 : (isAnimating ? 0 : 0.2))

                Image(systemName: hint.icon)
                    .font(.system(size: 24))
                    .foregroundColor(hint.accentColor)
            }

            // Title
            Text(hint.title)
                .font(.system(.headline, design: .rounded))
                .foregroundColor(.white)

            // Description
            Text(hint.description)
                .font(.system(.caption2, design: .rounded))
                .foregroundColor(.secondary)
                .multilineTextAlignment(.center)
                .lineLimit(3)
                .padding(.horizontal, 8)

            // Dismiss hint
            Text("Tap to dismiss")
                .font(.system(.caption2, design: .rounded))
                .foregroundColor(.secondary.opacity(0.85))
                .padding(.top, 4)
        }
        .padding(.vertical, 16)
        .padding(.horizontal, 12)
        .background(
            RoundedRectangle(cornerRadius: 16)
                .fill(.ultraThinMaterial)
                .overlay(
                    RoundedRectangle(cornerRadius: 16)
                        .stroke(hint.accentColor.opacity(0.3), lineWidth: 1)
                )
        )
        .shadow(color: .black.opacity(0.2), radius: 10)
        .accessibilityElement(children: .combine)
        .accessibilityLabel("\(hint.title): \(hint.description)")
        .accessibilityHint("Tap to dismiss")
        .onAppear {
            guard !reduceMotion else { return }
            withAnimation(.easeInOut(duration: 1.0).repeatForever(autoreverses: false)) {
                isAnimating = true
            }
        }
    }
}

// MARK: - Crown Rotation Hint View

/// Inline hint for crown rotation (shows during light adjustment)
struct CrownRotationHint: View {
    @Binding var isVisible: Bool
    @State private var rotationAngle: Double = 0
    @Environment(\.accessibilityReduceMotion) var reduceMotion

    var body: some View {
        if isVisible {
            HStack(spacing: 8) {
                // Animated crown icon
                Image(systemName: "digitalcrown.horizontal.arrow.clockwise.fill")
                    .font(.system(size: 16))
                    .foregroundColor(.beacon)
                    .rotationEffect(.degrees(reduceMotion ? 0 : rotationAngle))

                Text("Turn crown to adjust")
                    .font(.system(.caption2, design: .rounded))
                    .foregroundColor(.secondary)
            }
            .padding(.horizontal, 12)
            .padding(.vertical, 6)
            .background(
                Capsule()
                    .fill(Color.beacon.opacity(0.15))
            )
            .transition(.scale.combined(with: .opacity))
            .onAppear {
                guard !reduceMotion else { return }
                withAnimation(.easeInOut(duration: 1.5).repeatForever(autoreverses: true)) {
                    rotationAngle = 30
                }

                // Auto-hide after 3 seconds
                DispatchQueue.main.asyncAfter(deadline: .now() + 3.0) {
                    withAnimation {
                        isVisible = false
                    }
                }
            }
        }
    }
}

// MARK: - Swipe Navigation Hint

/// Inline hint for swipe navigation
struct SwipeNavigationHint: View {
    @Binding var isVisible: Bool
    @State private var handOffset: CGFloat = 0
    @Environment(\.accessibilityReduceMotion) var reduceMotion

    var body: some View {
        if isVisible {
            HStack(spacing: 8) {
                // Animated hand icon
                Image(systemName: "hand.draw")
                    .font(.system(size: 16))
                    .foregroundColor(.flow)
                    .offset(x: reduceMotion ? 0 : handOffset)

                Text("Swipe to navigate")
                    .font(.system(.caption2, design: .rounded))
                    .foregroundColor(.secondary)
            }
            .padding(.horizontal, 12)
            .padding(.vertical, 6)
            .background(
                Capsule()
                    .fill(Color.flow.opacity(0.15))
            )
            .transition(.scale.combined(with: .opacity))
            .onAppear {
                guard !reduceMotion else { return }
                withAnimation(.easeInOut(duration: 1.0).repeatForever(autoreverses: true)) {
                    handOffset = 10
                }

                // Auto-hide after 3 seconds
                DispatchQueue.main.asyncAfter(deadline: .now() + 3.0) {
                    withAnimation {
                        isVisible = false
                    }
                }
            }
        }
    }
}

// MARK: - Double-Tap Hint

/// Inline hint for double-tap gesture
struct DoubleTapHint: View {
    @Binding var isVisible: Bool
    @State private var tapScale: CGFloat = 1.0
    @Environment(\.accessibilityReduceMotion) var reduceMotion

    var body: some View {
        if isVisible {
            HStack(spacing: 8) {
                // Animated tap icon
                ZStack {
                    Image(systemName: "hand.tap")
                        .font(.system(size: 16))
                        .foregroundColor(.crystal)

                    Circle()
                        .stroke(Color.crystal.opacity(0.5), lineWidth: 1)
                        .frame(width: 24, height: 24)
                        .scaleEffect(reduceMotion ? 1.0 : tapScale)
                        .opacity(reduceMotion ? 0.5 : (tapScale > 1 ? 0 : 0.5))
                }

                Text("Double-tap for quick action")
                    .font(.system(.caption2, design: .rounded))
                    .foregroundColor(.secondary)
            }
            .padding(.horizontal, 12)
            .padding(.vertical, 6)
            .background(
                Capsule()
                    .fill(Color.crystal.opacity(0.15))
            )
            .transition(.scale.combined(with: .opacity))
            .onAppear {
                guard !reduceMotion else { return }
                withAnimation(.easeOut(duration: 0.5).repeatForever(autoreverses: false)) {
                    tapScale = 1.5
                }

                // Auto-hide after specified duration
                DispatchQueue.main.asyncAfter(deadline: .now() + 3.0) {
                    withAnimation {
                        isVisible = false
                    }
                }
            }
        }
    }
}

// MARK: - Gesture Tutorial View (Full Screen)

/// Full-screen gesture tutorial for onboarding
struct GestureTutorialView: View {
    @State private var currentIndex = 0
    @Environment(\.dismiss) private var dismiss

    private let tutorials: [GestureHintType] = [
        .doubleTap,
        .crownRotation,
        .swipeNavigation,
        .voiceCommand
    ]

    var body: some View {
        TabView(selection: $currentIndex) {
            ForEach(Array(tutorials.enumerated()), id: \.element) { index, hint in
                GestureTutorialPage(hint: hint, isLast: index == tutorials.count - 1) {
                    if index < tutorials.count - 1 {
                        withAnimation {
                            currentIndex = index + 1
                        }
                    } else {
                        dismiss()
                    }
                }
                .tag(index)
            }
        }
        .tabViewStyle(.page(indexDisplayMode: .automatic))
        .navigationTitle("Gestures")
        .navigationBarTitleDisplayMode(.inline)
    }
}

/// Single page of gesture tutorial
struct GestureTutorialPage: View {
    let hint: GestureHintType
    let isLast: Bool
    let onContinue: () -> Void

    @State private var isAnimating = false
    @Environment(\.accessibilityReduceMotion) var reduceMotion

    var body: some View {
        ScrollView {
            VStack(spacing: 16) {
                // Animated icon
                ZStack {
                    Circle()
                        .fill(hint.accentColor.opacity(0.2))
                        .frame(width: 80, height: 80)
                        .scaleEffect(reduceMotion ? 1.0 : (isAnimating ? 1.3 : 1.0))
                        .opacity(reduceMotion ? 0.2 : (isAnimating ? 0 : 0.2))

                    Image(systemName: hint.icon)
                        .font(.system(size: 36))
                        .foregroundColor(hint.accentColor)
                }
                .padding(.top, 20)

                // Title
                Text(hint.title)
                    .font(.system(.title3, design: .rounded).weight(.semibold))
                    .foregroundColor(.white)

                // Description
                Text(hint.description)
                    .font(.system(.caption, design: .rounded))
                    .foregroundColor(.secondary)
                    .multilineTextAlignment(.center)
                    .padding(.horizontal, 16)

                // Interactive demo area
                GestureInteractiveDemo(hint: hint)
                    .frame(height: 60)
                    .padding(.vertical, 8)

                // Continue button
                Button {
                    HapticPattern.success.play()
                    onContinue()
                } label: {
                    Text(isLast ? "Get Started" : "Next")
                        .font(.system(.subheadline, design: .rounded).weight(.medium))
                        .foregroundColor(.white)
                        .frame(maxWidth: .infinity)
                        .padding(.vertical, 12)
                        .background(hint.accentColor)
                        .cornerRadius(12)
                }
                .buttonStyle(.plain)
                .padding(.horizontal, 16)
                .padding(.top, 8)
            }
        }
        .onAppear {
            guard !reduceMotion else { return }
            withAnimation(.easeInOut(duration: 1.5).repeatForever(autoreverses: false)) {
                isAnimating = true
            }
        }
    }
}

/// Interactive demonstration area for each gesture
struct GestureInteractiveDemo: View {
    let hint: GestureHintType
    @State private var demoValue: Double = 50
    @State private var demoTapCount = 0

    var body: some View {
        switch hint {
        case .doubleTap:
            // Double-tap demo
            HStack(spacing: 4) {
                Image(systemName: "hand.tap")
                    .foregroundColor(.crystal)
                Image(systemName: "plus")
                    .font(.caption2)
                    .foregroundColor(.secondary)
                Image(systemName: "hand.tap")
                    .foregroundColor(.crystal)
                Image(systemName: "arrow.right")
                    .font(.caption2)
                    .foregroundColor(.secondary)
                Image(systemName: "sparkles")
                    .foregroundColor(.safetyOk)
            }
            .font(.system(size: 18))

        case .crownRotation:
            // Crown rotation demo with slider
            VStack(spacing: 4) {
                Slider(value: $demoValue, in: 0...100)
                    .tint(.beacon)
                Text("\(Int(demoValue))%")
                    .font(.system(.caption2, design: .monospaced))
                    .foregroundColor(.beacon)
            }
            .padding(.horizontal, 16)
            .focusable()
            .digitalCrownRotation($demoValue, from: 0, through: 100, by: 5, sensitivity: .medium, isContinuous: false, isHapticFeedbackEnabled: true)

        case .swipeNavigation:
            // Swipe demo
            HStack(spacing: 12) {
                Image(systemName: "chevron.left")
                    .foregroundColor(.secondary)
                Text("Screen")
                    .font(.system(.caption, design: .rounded))
                    .foregroundColor(.white)
                    .padding(.horizontal, 16)
                    .padding(.vertical, 8)
                    .background(Color.flow.opacity(0.3))
                    .cornerRadius(8)
                Image(systemName: "chevron.right")
                    .foregroundColor(.secondary)
            }

        case .longPress:
            // Long press demo
            Text("Press and hold")
                .font(.system(.caption, design: .rounded))
                .foregroundColor(.secondary)

        case .voiceCommand:
            // Voice demo
            VStack(spacing: 4) {
                Image(systemName: "waveform")
                    .font(.system(size: 24))
                    .foregroundColor(.spark)
                Text("\"Movie mode\"")
                    .font(.system(.caption2, design: .rounded))
                    .foregroundColor(.spark)
            }
        }
    }
}

// MARK: - View Modifier for Gesture Hints

/// View modifier to show gesture hints on first interaction
struct GestureHintModifier: ViewModifier {
    let hint: GestureHintType
    let showOnAppear: Bool

    func body(content: Content) -> some View {
        content
            .onAppear {
                if showOnAppear {
                    GestureHintManager.shared.showHintIfNeeded(hint)
                }
            }
    }
}

extension View {
    /// Show a gesture hint when this view appears
    func showGestureHint(_ hint: GestureHintType, onAppear: Bool = true) -> some View {
        modifier(GestureHintModifier(hint: hint, showOnAppear: onAppear))
    }
}

// MARK: - Preview

#Preview("Gesture Tutorial") {
    NavigationStack {
        GestureTutorialView()
    }
}

#Preview("Hint Bubble") {
    GestureHintBubble(hint: .crownRotation)
}

/*
 * Gesture Hint Architecture:
 *
 * First Launch:
 *   - Show gesture tutorial during onboarding
 *   - Mark each gesture as "learned" when viewed
 *
 * Contextual Hints:
 *   - Show 3-second bubble on first relevant interaction
 *   - Crown hint when focusing slider
 *   - Double-tap hint on hero action
 *   - Swipe hint on first list view
 *
 * Accessibility:
 *   - Respect reduceMotion preference
 *   - VoiceOver labels for all hints
 *   - Tap to dismiss
 *
 * h(x) >= 0. Always.
 */
