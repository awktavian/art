//
// OnboardingContainerView.swift — Main Onboarding Container
//
// Colony: Beacon (e5) — Planning
//
// Main container view for the onboarding wizard.
// Coordinates the step views and navigation.
//
// This file is the entry point for onboarding.
// Individual steps are in OnboardingStepViews.swift
// Components are in OnboardingComponents.swift
// State management is in OnboardingStateManager.swift
//
// h(x) >= 0. Always.
//

import SwiftUI

// MARK: - Main Onboarding View

struct OnboardingContainerView: View {
    @Binding var hasCompletedOnboarding: Bool
    @EnvironmentObject var appModel: AppModel
    @StateObject private var stateManager = OnboardingStateManager()

    @Environment(\.accessibilityReduceMotion) var reduceMotion

    var body: some View {
        ZStack {
            // Background
            Color.void
                .ignoresSafeArea()

            VStack(spacing: 0) {
                // Progress indicator
                OnboardingProgressView(
                    currentStep: stateManager.currentStep,
                    completedSteps: stateManager.completedSteps
                )
                .padding(.top, 16)
                .padding(.horizontal, 24)
                .accessibilityIdentifier(AccessibilityIdentifiers.Onboarding.progressIndicator)

                // Skip button (for skippable steps)
                HStack {
                    Spacer()
                    if stateManager.currentStep.isSkippable {
                        Button("Skip") {
                            stateManager.skipStep()
                        }
                        .font(KagamiFont.subheadline())
                        .foregroundColor(.accessibleTextSecondary)
                        .accessibilityLabel("Skip this step")
                        .accessibilityHint("You can configure this later in settings")
                        .accessibilityIdentifier(AccessibilityIdentifiers.Onboarding.skipButton)
                    }
                }
                .frame(height: 44)
                .padding(.horizontal, 24)

                // Step content
                TabView(selection: $stateManager.currentStep) {
                    ForEach(OnboardingStep.allCases) { step in
                        stepContent(for: step)
                            .tag(step)
                    }
                }
                .tabViewStyle(.page(indexDisplayMode: .never))
                .reducedMotionAnimation(KagamiMotion.smooth, value: stateManager.currentStep)

                // Navigation
                OnboardingNavigationView(
                    currentStep: stateManager.currentStep,
                    canProceed: canProceedFromCurrentStep,
                    isLoading: isCurrentStepLoading,
                    onNext: handleNext,
                    onBack: { stateManager.previousStep() }
                )
                .padding(.horizontal, 24)
                .padding(.bottom, 48)
            }
        }
        .preferredColorScheme(.dark)
    }

    // MARK: - Step Content

    @ViewBuilder
    private func stepContent(for step: OnboardingStep) -> some View {
        switch step {
        case .welcome:
            WelcomeStepView()
        case .server:
            ServerStepView(stateManager: stateManager)
        case .integration:
            IntegrationStepView(stateManager: stateManager)
        case .rooms:
            RoomsStepView(stateManager: stateManager)
        case .permissions:
            PermissionsStepView(stateManager: stateManager)
        case .completion:
            CompletionStepView(onComplete: completeOnboarding)
        }
    }

    // MARK: - Navigation Logic

    private var canProceedFromCurrentStep: Bool {
        switch stateManager.currentStep {
        case .welcome:
            return true
        case .server:
            return stateManager.isServerConnected || stateManager.isDemoMode
        case .integration:
            return stateManager.integrationConnected || stateManager.isDemoMode || stateManager.selectedIntegration == nil
        case .rooms:
            return true // Rooms are always optional
        case .permissions:
            return true // Permissions are always optional
        case .completion:
            return true
        }
    }

    private var isCurrentStepLoading: Bool {
        switch stateManager.currentStep {
        case .server:
            return stateManager.isConnecting || stateManager.isDiscovering
        case .integration:
            return stateManager.isTestingIntegration
        case .rooms:
            return stateManager.isLoadingRooms
        default:
            return false
        }
    }

    private func handleNext() {
        switch stateManager.currentStep {
        case .server:
            if !stateManager.isServerConnected && !stateManager.isDemoMode {
                Task {
                    await stateManager.connectToServer()
                    if stateManager.isServerConnected {
                        stateManager.nextStep()
                    }
                }
            } else {
                stateManager.nextStep()
            }

        case .integration:
            if stateManager.selectedIntegration != nil && !stateManager.integrationConnected {
                Task {
                    await stateManager.connectIntegration()
                    if stateManager.integrationConnected {
                        stateManager.nextStep()
                    }
                }
            } else {
                stateManager.nextStep()
            }

        case .completion:
            completeOnboarding()

        default:
            stateManager.nextStep()
        }
    }

    private func completeOnboarding() {
        // Save final state
        stateManager.saveState()

        // Track completion
        KagamiAnalytics.shared.track(.onboardingCompleted, properties: [
            "demo_mode": stateManager.isDemoMode,
            "integration": stateManager.selectedIntegration?.rawValue ?? "none",
            "rooms_configured": stateManager.discoveredRooms.filter { $0.isEnabled }.count
        ])

        // Update app model
        appModel.isDemoMode = stateManager.isDemoMode

        if !stateManager.isDemoMode {
            appModel.apiService.configure(baseURL: stateManager.serverURL)
        }

        // Haptic feedback
        UINotificationFeedbackGenerator().notificationOccurred(.success)

        // Complete onboarding
        withAnimation(KagamiMotion.softSpring) {
            hasCompletedOnboarding = true
        }

        UserDefaults.standard.set(true, forKey: "hasCompletedOnboarding")
    }
}

// MARK: - Type Alias for Backward Compatibility

// Note: OnboardingView is defined in ContentView.swift
// Use OnboardingContainerView for the full flow

// MARK: - Preview

#Preview("Onboarding Container") {
    OnboardingContainerView(hasCompletedOnboarding: .constant(false))
        .environmentObject(AppModel())
}

/*
 * Mirror
 * First impressions matter.
 * The onboarding flow introduces users to Kagami
 * with grace, clarity, and accessibility for all.
 *
 * h(x) >= 0. Always.
 */
