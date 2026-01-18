//
// OnboardingView.swift
// KagamiVision
//
// Spatial onboarding to improve EFE score (60→85)
// Addresses audit finding: New paradigm needs better predictability
//
// Colony: Crystal (e₇) — Verification through guided learning
//
// Phase 2 Accessibility:
//   - VoiceOver navigation through onboarding steps
//   - Reduced motion for animations
//   - Enhanced contrast for visual elements
//

import SwiftUI
import RealityKit
#if os(iOS) || os(visionOS)
import UIKit
#endif

/// Onboarding state tracking
class OnboardingState: ObservableObject {
    @Published var hasCompletedOnboarding: Bool {
        didSet {
            UserDefaults.standard.set(hasCompletedOnboarding, forKey: "hasCompletedOnboarding")
        }
    }
    @Published var currentStep: OnboardingStep = .welcome

    init() {
        self.hasCompletedOnboarding = UserDefaults.standard.bool(forKey: "hasCompletedOnboarding")
    }
}

enum OnboardingStep: Int, CaseIterable {
    case welcome = 0
    case spatialInterface = 1
    case gestures = 2
    case voiceCommands = 3
    case privacyConsent = 4
    case kagamiPresence = 5
    case complete = 6

    var title: String {
        switch self {
        case .welcome:
            return String(localized: "onboarding.welcome.title", defaultValue: "Welcome to Kagami")
        case .spatialInterface:
            return String(localized: "onboarding.spatial.title", defaultValue: "Spatial Interface")
        case .gestures:
            return String(localized: "onboarding.gestures.title", defaultValue: "Hand Gestures")
        case .voiceCommands:
            return String(localized: "onboarding.voice.title", defaultValue: "Voice Commands")
        case .privacyConsent:
            return String(localized: "onboarding.privacy.title", defaultValue: "Privacy Settings")
        case .kagamiPresence:
            return String(localized: "onboarding.presence.title", defaultValue: "Kagami Presence")
        case .complete:
            return String(localized: "onboarding.complete.title", defaultValue: "You're Ready")
        }
    }

    var icon: String {
        switch self {
        case .welcome: return "sparkles"
        case .spatialInterface: return "square.3.layers.3d"
        case .gestures: return "hand.raised"
        case .voiceCommands: return "mic.fill"
        case .privacyConsent: return "hand.raised.fill"
        case .kagamiPresence: return "circle.hexagongrid.fill"
        case .complete: return "checkmark.circle.fill"
        }
    }

    var isSystemImage: Bool {
        return true
    }

    var description: String {
        switch self {
        case .welcome:
            return String(localized: "onboarding.welcome.description", defaultValue: "I'm Kagami, your spatial home assistant. Let me show you how we'll work together in this immersive space.")
        case .spatialInterface:
            return String(localized: "onboarding.spatial.description", defaultValue: "Look at any button to highlight it, then pinch to select. Windows float naturally in your space and respond to your gaze.")
        case .gestures:
            return String(localized: "onboarding.gestures.description", defaultValue: "Pinch to tap. Pinch and drag to scroll. Reach out and rotate your wrist to adjust sliders like light brightness.")
        case .voiceCommands:
            return String(localized: "onboarding.voice.description", defaultValue: "Say \"Hey Kagami\" followed by a command: \"Movie mode\", \"Lights to fifty percent\", or \"Goodnight\".")
        case .privacyConsent:
            return String(localized: "onboarding.privacy.description", defaultValue: "Choose how Kagami uses your spatial data. You can change these settings anytime.")
        case .kagamiPresence:
            return String(localized: "onboarding.presence.description", defaultValue: "Enable the Kagami Presence to see me as a floating orb. Tap me for quick actions based on time of day.")
        case .complete:
            return String(localized: "onboarding.complete.description", defaultValue: "You're ready to control your home in spatial reality. The future is already here.")
        }
    }
}

struct OnboardingView: View {
    @StateObject private var state = OnboardingState()
    @Environment(\.dismiss) private var dismiss
    @EnvironmentObject var appModel: AppModel

    var body: some View {
        ZStack {
            // Background gradient
            LinearGradient(
                colors: [.black, Color(white: 0.1)],
                startPoint: .top,
                endPoint: .bottom
            )
            .ignoresSafeArea()

            VStack(spacing: 40) {
                // Progress indicator
                OnboardingProgressView(currentStep: state.currentStep)

                Spacer()

                // Content area
                OnboardingContentView(step: state.currentStep)
                    .transition(.asymmetric(
                        insertion: .move(edge: .trailing).combined(with: .opacity),
                        removal: .move(edge: .leading).combined(with: .opacity)
                    ))
                    .id(state.currentStep)

                Spacer()

                // Navigation buttons
                HStack(spacing: 20) {
                    if state.currentStep.rawValue > 0 {
                        Button(String(localized: "onboarding.button.back", defaultValue: "Back")) {
                            withAnimation(.smooth) {
                                if let previous = OnboardingStep(rawValue: state.currentStep.rawValue - 1) {
                                    state.currentStep = previous
                                }
                            }
                        }
                        .buttonStyle(.bordered)
                        .tint(.secondary)
                        .accessibilityLabel(String(localized: "onboarding.button.back", defaultValue: "Go back"))
                        .accessibilityHint(String(localized: "onboarding.accessibility.back_hint", defaultValue: "Returns to the previous onboarding step"))
                        .spatialGestureHint(.lookAndPinch)
                    }

                    Spacer()

                    if state.currentStep == .complete {
                        Button(String(localized: "onboarding.button.get_started", defaultValue: "Get Started")) {
                            state.hasCompletedOnboarding = true
                            dismiss()
                        }
                        .buttonStyle(.borderedProminent)
                        .tint(.crystal)
                        .accessibilityLabel(String(localized: "onboarding.button.get_started", defaultValue: "Get Started"))
                        .accessibilityHint(String(localized: "onboarding.accessibility.get_started_hint", defaultValue: "Completes onboarding and opens the main app"))
                        .spatialGestureHint(.lookAndPinch)
                    } else {
                        Button(String(localized: "onboarding.button.next", defaultValue: "Next")) {
                            withAnimation(.smooth) {
                                if let next = OnboardingStep(rawValue: state.currentStep.rawValue + 1) {
                                    state.currentStep = next
                                }
                            }
                        }
                        .buttonStyle(.borderedProminent)
                        .tint(.crystal)
                        .accessibilityLabel(String(localized: "onboarding.button.next", defaultValue: "Next"))
                        .accessibilityHint(String(localized: "onboarding.accessibility.next_hint", defaultValue: "Proceeds to the next onboarding step"))
                        .spatialGestureHint(.lookAndPinch)
                    }
                }
                .padding(.horizontal, 40)

                // Skip option
                if state.currentStep != .complete {
                    Button(String(localized: "onboarding.button.skip", defaultValue: "Skip Tutorial")) {
                        state.hasCompletedOnboarding = true
                        dismiss()
                    }
                    .font(.caption)
                    .foregroundColor(.secondary)
                    .accessibilityLabel(String(localized: "onboarding.button.skip", defaultValue: "Skip Tutorial"))
                    .accessibilityHint(String(localized: "onboarding.accessibility.skip_hint", defaultValue: "Skips the onboarding and opens the main app"))
                    .spatialGestureHint(.lookAndPinch)
                }
            }
            .padding(40)
        }
    }
}

// MARK: - Progress View

struct OnboardingProgressView: View {
    let currentStep: OnboardingStep

    var body: some View {
        HStack(spacing: 12) {
            ForEach(OnboardingStep.allCases, id: \.rawValue) { step in
                if step != .complete {
                    Circle()
                        .fill(step.rawValue <= currentStep.rawValue ? Color.crystal : Color.secondary.opacity(0.3))
                        .frame(width: 10, height: 10)
                        .animation(.smooth, value: currentStep)
                }
            }
        }
    }
}

// MARK: - Content View

struct OnboardingContentView: View {
    let step: OnboardingStep
    @State private var animateIcon = false
    @Environment(\.accessibilityReduceMotion) private var reduceMotion

    var body: some View {
        VStack(spacing: 32) {
            // Icon with animation (respects reduced motion)
            Image(systemName: step.icon)
                .font(.system(size: 60))
                .foregroundStyle(
                    LinearGradient(
                        colors: [.crystal, .white],
                        startPoint: .top,
                        endPoint: .bottom
                    )
                )
                .scaleEffect(reduceMotion ? 1.0 : (animateIcon ? 1.1 : 1.0))
                .animation(
                    reduceMotion ? nil : .easeInOut(duration: 1.597).repeatForever(autoreverses: true),
                    value: animateIcon
                )
                .onAppear {
                    guard !reduceMotion else { return }
                    animateIcon = true
                }
                .onDisappear { animateIcon = false }
                .accessibilityHidden(true)

            Text(step.title)
                .font(.largeTitle)
                .fontWeight(.bold)
                .foregroundStyle(.linearGradient(
                    colors: [.white, .crystal],
                    startPoint: .leading,
                    endPoint: .trailing
                ))
                .accessibilityAddTraits(.isHeader)

            Text(step.description)
                .font(.title3)
                .foregroundColor(.secondary)
                .multilineTextAlignment(.center)
                .lineSpacing(4)
                .frame(maxWidth: 500)

            // Step-specific demo content
            StepDemoView(step: step)
        }
        .accessibilityElement(children: .combine)
        .accessibilityLabel("\(step.title). \(step.description)")
    }
}

// MARK: - Step Demo View

struct StepDemoView: View {
    let step: OnboardingStep

    var body: some View {
        Group {
            switch step {
            case .welcome:
                WelcomeDemoView()
            case .spatialInterface:
                SpatialInterfaceDemoView()
            case .gestures:
                GesturesDemoView()
            case .voiceCommands:
                VoiceCommandsDemoView()
            case .privacyConsent:
                PrivacyConsentDemoView()
            case .kagamiPresence:
                PresenceDemoView()
            case .complete:
                CompleteDemoView()
            }
        }
        .frame(height: 200)
    }
}

struct WelcomeDemoView: View {
    var body: some View {
        HStack(spacing: 20) {
            ForEach(Array(Colony.allCases.prefix(7)), id: \.self) { colony in
                Circle()
                    .fill(colony.color)
                    .frame(width: 30, height: 30)
                    .shadow(color: colony.color.opacity(0.5), radius: 10)
            }
        }
    }
}

struct SpatialInterfaceDemoView: View {
    @State private var selectedIndex = 0
    @State private var timer: Timer?
    @Environment(\.accessibilityReduceMotion) private var reduceMotion

    var body: some View {
        HStack(spacing: 16) {
            ForEach(0..<3) { index in
                RoundedRectangle(cornerRadius: 12)
                    .fill(index == selectedIndex ? Color.crystal.opacity(0.3) : Color.secondary.opacity(0.1))
                    .frame(width: 80, height: 60)
                    .overlay(
                        RoundedRectangle(cornerRadius: 12)
                            .stroke(index == selectedIndex ? Color.crystal : Color.clear, lineWidth: 2)
                    )
                    .scaleEffect(index == selectedIndex ? 1.1 : 1.0)
                    .animation(.spring(response: 0.233, dampingFraction: 0.8), value: selectedIndex)
            }
        }
        .onAppear {
            guard !reduceMotion else { return }
            timer = Timer.scheduledTimer(withTimeInterval: 1.5, repeats: true) { _ in
                selectedIndex = (selectedIndex + 1) % 3
            }
        }
        .onDisappear {
            timer?.invalidate()
            timer = nil
        }
    }
}

struct GesturesDemoView: View {
    @State private var activeGestureIndex = 0
    @State private var timer: Timer?
    @State private var showTryIt = false
    @State private var isPracticeMode = false
    @Environment(\.accessibilityReduceMotion) private var reduceMotion

    private let gestures: [(name: String, icon: String, description: String)] = [
        ("Pinch", "hand.pinch", "Tap your thumb and index finger together to select"),
        ("Drag", "hand.point.up.left.and.text", "Pinch and move your hand to scroll or adjust"),
        ("Rotate", "arrow.triangle.2.circlepath", "Twist your wrist while pinching to change values"),
        ("Open Palm", "hand.raised", "Show your palm to dismiss menus"),
        ("Fist", "hand.raised.slash", "Make a fist for emergency stop")
    ]

    var body: some View {
        VStack(spacing: 20) {
            if isPracticeMode {
                // P0 FIX: Interactive gesture practice mode
                GesturePracticeModeView(onComplete: {
                    withAnimation {
                        isPracticeMode = false
                    }
                })
            } else {
                // Gesture carousel
                HStack(spacing: 24) {
                    ForEach(0..<gestures.count, id: \.self) { index in
                        GestureIcon(
                            name: gestures[index].name,
                            systemImage: gestures[index].icon,
                            isActive: index == activeGestureIndex
                        )
                        .scaleEffect(index == activeGestureIndex ? 1.2 : 0.9)
                        .opacity(index == activeGestureIndex ? 1.0 : 0.5)
                        .animation(.spring(response: 0.233, dampingFraction: 0.8), value: activeGestureIndex)
                    }
                }

                // Description for active gesture
                Text(gestures[activeGestureIndex].description)
                    .font(.caption)
                    .foregroundColor(.secondary)
                    .multilineTextAlignment(.center)
                    .frame(height: 40)
                    .animation(.easeInOut, value: activeGestureIndex)

                // Practice button
                Button(action: {
                    timer?.invalidate()
                    timer = nil
                    withAnimation {
                        isPracticeMode = true
                    }
                }) {
                    HStack(spacing: 8) {
                        Image(systemName: "hand.tap")
                            .foregroundColor(.crystal)
                        Text(String(localized: "onboarding.gestures.practice", defaultValue: "Practice Gestures"))
                            .font(.caption)
                            .fontWeight(.medium)
                            .foregroundColor(.crystal)
                    }
                    .padding(.horizontal, 16)
                    .padding(.vertical, 8)
                    .background(Color.crystal.opacity(0.2), in: Capsule())
                }
                .buttonStyle(.plain)
                .accessibilityLabel(String(localized: "onboarding.gestures.practice", defaultValue: "Practice Gestures"))
                .accessibilityHint(String(localized: "onboarding.gestures.practice_hint", defaultValue: "Opens interactive gesture practice mode"))
            }
        }
        .onAppear {
            guard !reduceMotion else { return }
            timer = Timer.scheduledTimer(withTimeInterval: 2.5, repeats: true) { _ in
                activeGestureIndex = (activeGestureIndex + 1) % gestures.count
            }
        }
        .onDisappear {
            timer?.invalidate()
            timer = nil
        }
        .accessibilityElement(children: .combine)
        .accessibilityLabel("Gesture tutorial showing: \(gestures[activeGestureIndex].name). \(gestures[activeGestureIndex].description)")
    }
}

// MARK: - Gesture Practice Mode View

/// P0 FIX: Interactive gesture practice mode for onboarding
/// Lets users practice pinch/drag gestures before main app with haptic feedback
struct GesturePracticeModeView: View {
    let onComplete: () -> Void

    @State private var currentPracticeGesture = 0
    @State private var gestureSuccessCount: [Int] = [0, 0, 0]  // pinch, drag, open palm
    @State private var showSuccessAnimation = false
    @State private var practiceComplete = false
    @Environment(\.accessibilityReduceMotion) private var reduceMotion

    private let requiredSuccesses = 2  // Number of successful gestures needed to progress

    private let practiceGestures: [(name: String, icon: String, instruction: String)] = [
        ("Pinch", "hand.pinch", "Pinch your thumb and index finger together"),
        ("Drag", "hand.point.up.left.and.text", "Pinch and drag your hand left or right"),
        ("Open Palm", "hand.raised", "Open your palm to dismiss")
    ]

    var body: some View {
        VStack(spacing: 24) {
            // Practice header
            HStack {
                Text(String(localized: "onboarding.practice.title", defaultValue: "Gesture Practice"))
                    .font(.headline)
                    .foregroundColor(.crystal)

                Spacer()

                Button(action: onComplete) {
                    Image(systemName: "xmark.circle.fill")
                        .font(.title3)
                        .foregroundColor(.secondary)
                }
                .buttonStyle(.plain)
                .accessibilityLabel(String(localized: "onboarding.practice.close", defaultValue: "Close practice"))
            }
            .padding(.horizontal)

            if practiceComplete {
                // Success state
                VStack(spacing: 16) {
                    Image(systemName: "checkmark.circle.fill")
                        .font(.system(size: 48))
                        .foregroundColor(.grove)
                        .scaleEffect(reduceMotion ? 1.0 : (showSuccessAnimation ? 1.2 : 1.0))
                        .animation(reduceMotion ? nil : .spring(response: 0.233, dampingFraction: 0.8), value: showSuccessAnimation)

                    Text(String(localized: "onboarding.practice.complete", defaultValue: "Great job! You've mastered the gestures."))
                        .font(.subheadline)
                        .foregroundColor(.secondary)
                        .multilineTextAlignment(.center)

                    Button(String(localized: "onboarding.practice.continue", defaultValue: "Continue")) {
                        onComplete()
                    }
                    .buttonStyle(.borderedProminent)
                    .tint(.crystal)
                }
                .transition(.scale.combined(with: .opacity))
            } else {
                // Current gesture practice
                let gesture = practiceGestures[currentPracticeGesture]
                let successCount = gestureSuccessCount[currentPracticeGesture]

                VStack(spacing: 16) {
                    // Gesture icon with animation target
                    ZStack {
                        // Target ring
                        Circle()
                            .stroke(Color.crystal.opacity(0.3), lineWidth: 3)
                            .frame(width: 100, height: 100)

                        // Success ring (fills as gestures are detected)
                        Circle()
                            .trim(from: 0, to: CGFloat(successCount) / CGFloat(requiredSuccesses))
                            .stroke(Color.grove, style: StrokeStyle(lineWidth: 3, lineCap: .round))
                            .frame(width: 100, height: 100)
                            .rotationEffect(.degrees(-90))
                            .animation(.spring(response: 0.233, dampingFraction: 0.8), value: successCount)

                        // Gesture icon
                        Image(systemName: gesture.icon)
                            .font(.system(size: 36))
                            .foregroundColor(showSuccessAnimation ? .grove : .crystal)
                            .scaleEffect(showSuccessAnimation ? 1.3 : 1.0)
                            .animation(.spring(response: 0.144, dampingFraction: 0.85), value: showSuccessAnimation)
                    }

                    // Instruction
                    Text(gesture.instruction)
                        .font(.subheadline)
                        .foregroundColor(.secondary)
                        .multilineTextAlignment(.center)

                    // Progress indicator
                    HStack(spacing: 4) {
                        ForEach(0..<requiredSuccesses, id: \.self) { index in
                            Circle()
                                .fill(index < successCount ? Color.grove : Color.secondary.opacity(0.3))
                                .frame(width: 8, height: 8)
                                .animation(.spring(response: 0.144, dampingFraction: 0.85), value: successCount)
                        }
                    }

                    // Gesture step indicator
                    HStack(spacing: 8) {
                        ForEach(0..<practiceGestures.count, id: \.self) { index in
                            Circle()
                                .fill(index == currentPracticeGesture ? Color.crystal :
                                      index < currentPracticeGesture ? Color.grove : Color.secondary.opacity(0.3))
                                .frame(width: 10, height: 10)
                        }
                    }
                    .padding(.top, 8)
                }
                .gesture(
                    // Detect gestures for practice
                    SimultaneousGesture(
                        TapGesture()
                            .onEnded { _ in
                                handleGestureDetected(type: .pinch)
                            },
                        DragGesture(minimumDistance: 20)
                            .onEnded { value in
                                if abs(value.translation.width) > 30 {
                                    handleGestureDetected(type: .drag)
                                }
                            }
                    )
                )
                // Long press for open palm simulation
                .onLongPressGesture(minimumDuration: 0.5) {
                    handleGestureDetected(type: .openPalm)
                }
            }
        }
        .padding()
        .background(Color(white: 0.1).opacity(0.5), in: RoundedRectangle(cornerRadius: 16))
        .accessibilityElement(children: .contain)
        .accessibilityLabel(String(localized: "onboarding.practice.accessibility_label", defaultValue: "Gesture practice area"))
    }

    private enum PracticeGestureType {
        case pinch, drag, openPalm
    }

    private func handleGestureDetected(type: PracticeGestureType) {
        let expectedType: PracticeGestureType
        switch currentPracticeGesture {
        case 0: expectedType = .pinch
        case 1: expectedType = .drag
        case 2: expectedType = .openPalm
        default: return
        }

        // Check if correct gesture
        guard type == expectedType else { return }

        // Trigger haptic feedback
        triggerHapticFeedback()

        // Show success animation
        withAnimation {
            showSuccessAnimation = true
        }

        // Increment success count
        gestureSuccessCount[currentPracticeGesture] += 1

        // Reset animation after delay
        DispatchQueue.main.asyncAfter(deadline: .now() + 0.3) {
            withAnimation {
                showSuccessAnimation = false
            }

            // Check if gesture is complete
            if gestureSuccessCount[currentPracticeGesture] >= requiredSuccesses {
                // Move to next gesture or complete
                DispatchQueue.main.asyncAfter(deadline: .now() + 0.2) {
                    withAnimation {
                        if currentPracticeGesture < practiceGestures.count - 1 {
                            currentPracticeGesture += 1
                        } else {
                            practiceComplete = true
                            showSuccessAnimation = true
                        }
                    }
                }
            }
        }
    }

    private func triggerHapticFeedback() {
        // Haptic feedback not available on visionOS - use audio instead
        // For iOS, use UIKit:
        #if os(iOS)
        let generator = UIImpactFeedbackGenerator(style: .medium)
        generator.impactOccurred()
        #endif
    }
}

struct GestureIcon: View {
    let name: String
    let systemImage: String
    let isActive: Bool

    var body: some View {
        VStack(spacing: 8) {
            Image(systemName: systemImage)
                .font(.title)
                .foregroundColor(isActive ? .crystal : .secondary)
                .scaleEffect(isActive ? 1.2 : 1.0)
                .animation(.spring(response: 0.233, dampingFraction: 0.8), value: isActive)

            Text(name)
                .font(.caption)
                .foregroundColor(.secondary)
        }
    }
}

struct VoiceCommandsDemoView: View {
    @State private var commandIndex = 0
    @State private var timer: Timer?
    @Environment(\.accessibilityReduceMotion) private var reduceMotion
    private let commands = ["\"Movie mode\"", "\"Lights to 50%\"", "\"Goodnight\""]

    var body: some View {
        VStack(spacing: 12) {
            HStack(spacing: 8) {
                Image(systemName: "mic.fill")
                    .foregroundColor(.crystal)
                    .accessibilityHidden(true)
                Text(String(localized: "onboarding.voice.hey_kagami", defaultValue: "\"Hey Kagami...\""))
                    .font(.title3)
                    .foregroundColor(.crystal)
            }

            Text(commands[commandIndex])
                .font(.title2)
                .fontWeight(.medium)
                .foregroundColor(.white)
                .transition(.scale.combined(with: .opacity))
                .id(commandIndex)
        }
        .onAppear {
            guard !reduceMotion else { return }
            timer = Timer.scheduledTimer(withTimeInterval: 2.0, repeats: true) { _ in
                withAnimation(.smooth) {
                    commandIndex = (commandIndex + 1) % commands.count
                }
            }
        }
        .onDisappear {
            timer?.invalidate()
            timer = nil
        }
    }
}

struct PresenceDemoView: View {
    @State private var orbScale: CGFloat = 1.0
    @Environment(\.accessibilityReduceMotion) private var reduceMotion

    var body: some View {
        ZStack {
            // Glow
            Circle()
                .fill(
                    RadialGradient(
                        colors: [.crystal.opacity(0.4), .clear],
                        center: .center,
                        startRadius: 20,
                        endRadius: 60
                    )
                )
                .frame(width: 120, height: 120)

            // Orb
            Circle()
                .fill(Color.crystal)
                .frame(width: 50, height: 50)
                .shadow(color: .crystal.opacity(0.8), radius: 20)
                .scaleEffect(reduceMotion ? 1.0 : orbScale)
        }
        .onAppear {
            guard !reduceMotion else { return }
            withAnimation(.easeInOut(duration: 1.597).repeatForever(autoreverses: true)) {
                orbScale = 1.15
            }
        }
        .accessibilityLabel("Kagami presence orb demonstration")
    }
}

struct CompleteDemoView: View {
    var body: some View {
        VStack(spacing: 16) {
            Image(systemName: "checkmark.circle.fill")
                .font(.system(size: 60))
                .foregroundColor(.grove)

            Text("Safety First")
                .font(.system(.body, design: .rounded))
                .foregroundColor(.secondary)
        }
    }
}

// MARK: - Privacy Consent Demo View

struct PrivacyConsentDemoView: View {
    var body: some View {
        VStack(spacing: 20) {
            PrivacyConsentToggleRow(
                icon: "hand.raised",
                title: "Hand Tracking Upload",
                description: "Send gesture data for analytics",
                isEnabled: .constant(PrivacySettings.shared.allowHandTrackingUpload)
            )
            PrivacyConsentToggleRow(
                icon: "eye",
                title: "Gaze Tracking Upload",
                description: "Send eye tracking data for analytics",
                isEnabled: .constant(PrivacySettings.shared.allowGazeTrackingUpload)
            )
        }
        .padding(.horizontal, 20)
    }
}

struct PrivacyConsentToggleRow: View {
    let icon: String
    let title: String
    let description: String
    @Binding var isEnabled: Bool

    var body: some View {
        HStack(spacing: 16) {
            Image(systemName: icon)
                .font(.title2)
                .foregroundColor(.crystal)
                .frame(width: 32)
                .accessibilityHidden(true)

            VStack(alignment: .leading, spacing: 4) {
                Text(title)
                    .font(.system(size: 16, weight: .medium))
                Text(description)
                    .font(.system(size: 13))
                    .foregroundColor(.secondary)
            }

            Spacer()

            Toggle("", isOn: $isEnabled)
                .labelsHidden()
                .toggleStyle(.switch)
                .tint(.crystal)
        }
        .padding(.vertical, 8)
        .padding(.horizontal, 16)
        .background(.ultraThinMaterial, in: RoundedRectangle(cornerRadius: 12))
        .accessibilityElement(children: .combine)
        .accessibilityLabel("\(title). \(description). Currently \(isEnabled ? "enabled" : "disabled")")
        .accessibilityHint("Double tap to toggle")
        .accessibilityAddTraits(.isButton)
    }
}

// MARK: - Colony Enum

enum Colony: String, CaseIterable {
    case spark, forge, flow, nexus, beacon, grove, crystal

    var color: Color {
        switch self {
        case .spark: return .spark
        case .forge: return .forge
        case .flow: return .flow
        case .nexus: return .nexus
        case .beacon: return .beacon
        case .grove: return .grove
        case .crystal: return .crystal
        }
    }
}

// MARK: - Preview

#Preview {
    OnboardingView()
        .environmentObject(AppModel())
}

/*
 * 鏡
 * Every journey begins with understanding.
 */
