//
// OnboardingComponents.swift — Shared Onboarding Components
//
// Colony: Beacon (e5) — Planning
//
// Reusable components for the onboarding flow:
//   - OnboardingProgressView
//   - OnboardingNavigationView
//   - IntegrationCredentialsSheet
//   - ConfettiView
//
// h(x) >= 0. Always.
//

import SwiftUI
import KagamiDesign

// MARK: - Progress View

struct OnboardingProgressView: View {
    let currentStep: OnboardingStep
    let completedSteps: Set<OnboardingStep>

    var body: some View {
        HStack(spacing: 8) {
            ForEach(OnboardingStep.allCases) { step in
                ProgressDot(
                    step: step,
                    isCurrent: step == currentStep,
                    isCompleted: completedSteps.contains(step)
                )
            }
        }
        .accessibilityElement(children: .combine)
        .accessibilityLabel("Step \(currentStep.rawValue + 1) of \(OnboardingStep.allCases.count): \(currentStep.title)")
    }
}

struct ProgressDot: View {
    let step: OnboardingStep
    let isCurrent: Bool
    let isCompleted: Bool

    @Environment(\.accessibilityReduceMotion) var reduceMotion

    var body: some View {
        ZStack {
            Circle()
                .fill(fillColor)
                .frame(width: isCurrent ? 12 : 8, height: isCurrent ? 12 : 8)

            if isCompleted && !isCurrent {
                Image(systemName: "checkmark")
                    .font(.system(size: 6, weight: .bold))
                    .foregroundColor(.void)
            }
        }
        .animation(reduceMotion ? nil : KagamiMotion.microSpring, value: isCurrent)
    }

    private var fillColor: Color {
        if isCurrent {
            return step.colonyColor
        } else if isCompleted {
            return .safetyOk
        } else {
            return .accessibleTextTertiary.opacity(0.5)
        }
    }
}

// MARK: - Navigation View

struct OnboardingNavigationView: View {
    let currentStep: OnboardingStep
    let canProceed: Bool
    let isLoading: Bool
    let onNext: () -> Void
    let onBack: () -> Void

    var body: some View {
        HStack {
            // Back button
            if currentStep != .welcome {
                Button {
                    onBack()
                } label: {
                    HStack(spacing: 4) {
                        Image(systemName: "chevron.left")
                        Text("Back")
                    }
                    .font(KagamiFont.body())
                    .foregroundColor(.accessibleTextSecondary)
                }
                .accessibleButton(label: "Go back", hint: "Return to previous step")
                .accessibilityIdentifier(AccessibilityIdentifiers.Onboarding.backButton)
            }

            Spacer()

            // Next/Complete button
            Button {
                onNext()
            } label: {
                HStack(spacing: 8) {
                    if isLoading {
                        ProgressView()
                            .tint(.void)
                    } else {
                        Text(currentStep == .completion ? "Get Started" : "Continue")
                            .font(KagamiFont.headline())

                        if currentStep != .completion {
                            Image(systemName: "chevron.right")
                        }
                    }
                }
                .frame(minWidth: 140)
                .padding(.vertical, 14)
                .padding(.horizontal, 24)
                .background(canProceed && !isLoading ? currentStep.colonyColor : currentStep.colonyColor.opacity(0.5))
                .foregroundColor(.void)
                .cornerRadius(KagamiRadius.md)
            }
            .disabled(!canProceed || isLoading)
            .accessibleButton(
                label: currentStep == .completion ? "Get started with Kagami" : "Continue to next step",
                hint: canProceed ? "Double tap to proceed" : "Complete required fields to continue"
            )
            .accessibilityIdentifier(
                currentStep == .completion
                    ? AccessibilityIdentifiers.Onboarding.getStartedButton
                    : AccessibilityIdentifiers.Onboarding.continueButton
            )
        }
    }
}

// MARK: - Integration Credentials Sheet

struct IntegrationCredentialsSheet: View {
    let integration: SmartHomeIntegration
    @ObservedObject var stateManager: OnboardingStateManager
    let onDismiss: () -> Void

    var body: some View {
        NavigationStack {
            ZStack {
                Color.void
                    .ignoresSafeArea()

                ScrollView {
                    VStack(spacing: 24) {
                        // Integration icon
                        Image(systemName: integration.icon)
                            .font(.system(size: 48))
                            .foregroundColor(integration.colonyColor)
                            .padding(.top, 24)

                        Text("Connect \(integration.displayName)")
                            .font(KagamiFont.title3())
                            .foregroundColor(.accessibleTextPrimary)

                        // Credentials form based on integration type
                        credentialsForm

                        // Test button
                        Button {
                            Task {
                                await stateManager.testIntegration()
                            }
                        } label: {
                            HStack {
                                if stateManager.isTestingIntegration {
                                    ProgressView()
                                        .tint(.void)
                                } else {
                                    Image(systemName: "antenna.radiowaves.left.and.right")
                                    Text("Test Connection")
                                }
                            }
                            .font(KagamiFont.body(weight: .medium))
                            .frame(maxWidth: .infinity)
                            .padding(.vertical, 14)
                            .background(integration.colonyColor)
                            .foregroundColor(.void)
                            .cornerRadius(KagamiRadius.md)
                        }
                        .disabled(stateManager.isTestingIntegration || !hasRequiredCredentials)

                        // Status messages
                        if stateManager.integrationConnected {
                            HStack {
                                Image(systemName: "checkmark.circle.fill")
                                    .foregroundColor(.safetyOk)
                                Text("Connection successful!")
                                    .foregroundColor(.safetyOk)
                            }
                        }

                        if let error = stateManager.integrationError {
                            HStack {
                                Image(systemName: "exclamationmark.triangle.fill")
                                    .foregroundColor(.safetyViolation)
                                Text(error)
                                    .foregroundColor(.safetyViolation)
                            }
                            .font(KagamiFont.caption())
                        }

                        Spacer()
                    }
                    .padding(.horizontal, 24)
                }
            }
            .navigationBarTitleDisplayMode(.inline)
            .toolbar {
                ToolbarItem(placement: .cancellationAction) {
                    Button("Cancel") {
                        onDismiss()
                    }
                    .foregroundColor(.crystal)
                }

                ToolbarItem(placement: .confirmationAction) {
                    Button("Done") {
                        onDismiss()
                    }
                    .foregroundColor(.crystal)
                    .disabled(!stateManager.integrationConnected)
                }
            }
        }
        .preferredColorScheme(.dark)
    }

    @ViewBuilder
    private var credentialsForm: some View {
        VStack(spacing: 16) {
            switch integration {
            case .control4:
                CredentialField(label: "Host/IP Address", text: $stateManager.control4Host, placeholder: "192.168.1.100")
                CredentialField(label: "Port", text: $stateManager.control4Port, placeholder: "5020", keyboardType: .numberPad)
                CredentialField(label: "API Key (optional)", text: $stateManager.control4ApiKey, placeholder: "API key", isSecure: true)

            case .lutron:
                CredentialField(label: "Host/IP Address", text: $stateManager.lutronHost, placeholder: "192.168.1.100")
                CredentialField(label: "Telnet Password (optional)", text: $stateManager.lutronPassword, placeholder: "Password", isSecure: true)

            case .smartthings:
                CredentialField(label: "Personal Access Token", text: $stateManager.smartthingsToken, placeholder: "Token", isSecure: true)

            case .homeAssistant:
                CredentialField(label: "Home Assistant URL", text: $stateManager.homeAssistantURL, placeholder: "https://homeassistant.local:8123", keyboardType: .URL)
                CredentialField(label: "Long-Lived Access Token", text: $stateManager.homeAssistantToken, placeholder: "Token", isSecure: true)

            case .hubitat:
                CredentialField(label: "Hub IP Address", text: $stateManager.hubitatHost, placeholder: "192.168.1.100")
                CredentialField(label: "Maker API Token", text: $stateManager.hubitatToken, placeholder: "Token", isSecure: true)

            default:
                Text("This integration uses OAuth. Tap Continue to authorize.")
                    .font(KagamiFont.body())
                    .foregroundColor(.accessibleTextSecondary)
                    .multilineTextAlignment(.center)
            }
        }
    }

    private var hasRequiredCredentials: Bool {
        switch integration {
        case .control4:
            return !stateManager.control4Host.isEmpty
        case .lutron:
            return !stateManager.lutronHost.isEmpty
        case .smartthings:
            return !stateManager.smartthingsToken.isEmpty
        case .homeAssistant:
            return !stateManager.homeAssistantURL.isEmpty && !stateManager.homeAssistantToken.isEmpty
        case .hubitat:
            return !stateManager.hubitatHost.isEmpty && !stateManager.hubitatToken.isEmpty
        default:
            return true
        }
    }
}

struct CredentialField: View {
    let label: String
    @Binding var text: String
    let placeholder: String
    var isSecure: Bool = false
    var keyboardType: UIKeyboardType = .default

    var body: some View {
        VStack(alignment: .leading, spacing: 8) {
            Text(label)
                .font(KagamiFont.caption())
                .foregroundColor(.accessibleTextTertiary)

            if isSecure {
                SecureField(placeholder, text: $text)
                    .textFieldStyle(KagamiTextFieldStyle())
            } else {
                TextField(placeholder, text: $text)
                    .textFieldStyle(KagamiTextFieldStyle())
                    .autocapitalization(.none)
                    .disableAutocorrection(true)
                    .keyboardType(keyboardType)
            }
        }
        .accessibilityElement(children: .combine)
        .accessibilityLabel(label)
    }
}

// MARK: - Confetti View

struct ConfettiView: View {
    @State private var particles: [ConfettiParticle] = []

    var body: some View {
        GeometryReader { geometry in
            ForEach(particles) { particle in
                Circle()
                    .fill(particle.color)
                    .frame(width: particle.size, height: particle.size)
                    .position(particle.position)
                    .opacity(particle.opacity)
            }
        }
        .onAppear {
            generateParticles()
        }
    }

    private func generateParticles() {
        let colors: [Color] = [.spark, .forge, .flow, .nexus, .beacon, .grove, .crystal]

        for _ in 0..<50 {
            let particle = ConfettiParticle(
                color: colors.randomElement()!,
                size: CGFloat.random(in: 4...12),
                position: CGPoint(
                    x: CGFloat.random(in: 0...UIScreen.main.bounds.width),
                    y: CGFloat.random(in: -100...0)
                ),
                opacity: 1.0,
                velocity: CGFloat.random(in: 2...5)
            )
            particles.append(particle)
        }

        // Animate particles falling
        Timer.scheduledTimer(withTimeInterval: 0.016, repeats: true) { timer in
            for i in particles.indices {
                particles[i].position.y += particles[i].velocity
                particles[i].position.x += CGFloat.random(in: -1...1)

                if particles[i].position.y > UIScreen.main.bounds.height + 50 {
                    particles[i].opacity = 0
                }
            }

            // Stop after all particles have fallen
            if particles.allSatisfy({ $0.opacity == 0 }) {
                timer.invalidate()
            }
        }
    }
}

struct ConfettiParticle: Identifiable {
    let id = UUID()
    let color: Color
    let size: CGFloat
    var position: CGPoint
    var opacity: Double
    var velocity: CGFloat
}

// MARK: - Notifications
// Note: kagamiDidLogout is defined in NotificationService.swift

/*
 * Mirror
 * h(x) >= 0. Always.
 */
