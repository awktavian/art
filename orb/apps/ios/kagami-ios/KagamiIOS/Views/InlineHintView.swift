//
// InlineHintView.swift — Contextual Tips Based on User Behavior
//
// Colony: Beacon (e5) — Planning
//
// Features:
//   - Track feature usage patterns
//   - Show contextual hints after behavior thresholds
//   - Progressive disclosure of advanced features
//   - Dismissable and non-intrusive
//
// Examples:
//   - "Try voice commands" after 3 manual taps
//   - "Long-press for quick actions" after 5 scene activations
//   - "Swipe to control brightness" after using light buttons
//
// h(x) >= 0. Always.
//

import SwiftUI
import KagamiDesign

// MARK: - Hint Types

/// Types of hints that can be shown to users
enum HintType: String, CaseIterable, Identifiable {
    case voiceCommands = "voice_commands"
    case longPressScenes = "longpress_scenes"
    case swipeControls = "swipe_controls"
    case searchFeature = "search_feature"
    case widgetSetup = "widget_setup"
    case siriShortcuts = "siri_shortcuts"
    case quickActions = "quick_actions"
    case focusMode = "focus_mode"

    var id: String { rawValue }

    var title: String {
        switch self {
        case .voiceCommands: return "Try Voice Commands"
        case .longPressScenes: return "Quick Scene Actions"
        case .swipeControls: return "Swipe for Brightness"
        case .searchFeature: return "Search Everything"
        case .widgetSetup: return "Add Home Screen Widget"
        case .siriShortcuts: return "Create Siri Shortcuts"
        case .quickActions: return "3D Touch Quick Actions"
        case .focusMode: return "Focus Mode Integration"
        }
    }

    var message: String {
        switch self {
        case .voiceCommands: return "Tap the mic button or say \"Hey Kagami\" for hands-free control"
        case .longPressScenes: return "Long-press any scene card for quick preview and options"
        case .swipeControls: return "Swipe left or right on room cards to adjust brightness"
        case .searchFeature: return "Tap search to quickly find rooms, scenes, and settings"
        case .widgetSetup: return "Add a Kagami widget to your home screen for instant access"
        case .siriShortcuts: return "Create custom Siri shortcuts for your favorite scenes"
        case .quickActions: return "Force press the app icon for quick scene access"
        case .focusMode: return "Connect Kagami to Focus modes for automatic scenes"
        }
    }

    var icon: String {
        switch self {
        case .voiceCommands: return "mic.fill"
        case .longPressScenes: return "hand.tap.fill"
        case .swipeControls: return "hand.draw.fill"
        case .searchFeature: return "magnifyingglass"
        case .widgetSetup: return "apps.iphone"
        case .siriShortcuts: return "waveform"
        case .quickActions: return "hand.point.up.braille.fill"
        case .focusMode: return "moon.fill"
        }
    }

    var color: Color {
        switch self {
        case .voiceCommands: return .nexus
        case .longPressScenes: return .forge
        case .swipeControls: return .beacon
        case .searchFeature: return .crystal
        case .widgetSetup: return .grove
        case .siriShortcuts: return .spark
        case .quickActions: return .flow
        case .focusMode: return .beacon
        }
    }

    /// Threshold of actions before showing hint
    var threshold: Int {
        switch self {
        case .voiceCommands: return 3
        case .longPressScenes: return 5
        case .swipeControls: return 4
        case .searchFeature: return 10
        case .widgetSetup: return 15
        case .siriShortcuts: return 8
        case .quickActions: return 12
        case .focusMode: return 20
        }
    }

    /// Related tracked event
    var triggerEvent: HintTriggerEvent {
        switch self {
        case .voiceCommands: return .manualLightControl
        case .longPressScenes: return .sceneActivation
        case .swipeControls: return .lightButtonTap
        case .searchFeature: return .navigationTap
        case .widgetSetup: return .appOpen
        case .siriShortcuts: return .sceneActivation
        case .quickActions: return .appOpen
        case .focusMode: return .appOpen
        }
    }
}

/// Events that can trigger hints
enum HintTriggerEvent: String {
    case manualLightControl = "manual_light_control"
    case sceneActivation = "scene_activation"
    case lightButtonTap = "light_button_tap"
    case navigationTap = "navigation_tap"
    case appOpen = "app_open"
    case voiceCommandUsed = "voice_command_used"
    case searchUsed = "search_used"
}

// MARK: - Hint Manager

@MainActor
class HintManager: ObservableObject {
    static let shared = HintManager()

    @Published var currentHint: HintType?
    @Published var dismissedHints: Set<String> = []

    private var eventCounts: [String: Int] = [:]
    private let userDefaultsKey = "kagami.hints"

    init() {
        loadState()
    }

    // MARK: - Event Tracking

    /// Track an event that may trigger a hint
    func trackEvent(_ event: HintTriggerEvent) {
        let key = event.rawValue
        eventCounts[key] = (eventCounts[key] ?? 0) + 1
        saveState()

        // Check if any hint should be shown
        checkForHints(triggeredBy: event)
    }

    /// Check if any hints should be shown
    private func checkForHints(triggeredBy event: HintTriggerEvent) {
        // Don't show hints if one is already displayed
        guard currentHint == nil else { return }

        // Find a matching hint
        for hintType in HintType.allCases {
            // Skip if already dismissed
            guard !isDismissed(hintType) else { continue }

            // Check if threshold is met
            if hintType.triggerEvent == event {
                let count = eventCounts[event.rawValue] ?? 0
                if count >= hintType.threshold {
                    showHint(hintType)
                    return
                }
            }
        }
    }

    /// Show a specific hint
    func showHint(_ hint: HintType) {
        withAnimation(KagamiMotion.smooth) {
            currentHint = hint
        }

        // Track hint shown
        KagamiAnalytics.shared.track(.hintShown, properties: [
            "hint_type": hint.rawValue
        ])
    }

    /// Dismiss the current hint
    func dismissCurrentHint() {
        guard let hint = currentHint else { return }

        dismissedHints.insert(hint.rawValue)
        withAnimation(KagamiMotion.smooth) {
            currentHint = nil
        }

        // Track hint dismissed
        KagamiAnalytics.shared.track(.hintDismissed, properties: [
            "hint_type": hint.rawValue
        ])

        saveState()
    }

    /// Check if a hint has been dismissed
    func isDismissed(_ hint: HintType) -> Bool {
        dismissedHints.contains(hint.rawValue)
    }

    /// Reset all hints (for testing)
    func resetAllHints() {
        dismissedHints.removeAll()
        eventCounts.removeAll()
        currentHint = nil
        saveState()
    }

    // MARK: - Persistence

    private func loadState() {
        if let data = UserDefaults.standard.data(forKey: userDefaultsKey),
           let state = try? JSONDecoder().decode(HintState.self, from: data) {
            dismissedHints = state.dismissedHints
            eventCounts = state.eventCounts
        }
    }

    private func saveState() {
        let state = HintState(dismissedHints: dismissedHints, eventCounts: eventCounts)
        if let data = try? JSONEncoder().encode(state) {
            UserDefaults.standard.set(data, forKey: userDefaultsKey)
        }
    }
}

/// Persisted hint state
private struct HintState: Codable {
    var dismissedHints: Set<String>
    var eventCounts: [String: Int]
}

// MARK: - Analytics Events

extension KagamiAnalytics.EventName {
    static let hintShown = KagamiAnalytics.EventName(rawValue: "hint_shown")
    static let hintDismissed = KagamiAnalytics.EventName(rawValue: "hint_dismissed")
    static let hintActioned = KagamiAnalytics.EventName(rawValue: "hint_actioned")
}

// MARK: - Inline Hint View

/// A non-intrusive hint banner that appears contextually
struct InlineHintView: View {
    let hint: HintType
    let onDismiss: () -> Void
    var onAction: (() -> Void)?

    @Environment(\.accessibilityReduceMotion) var reduceMotion
    @State private var isVisible = false

    var body: some View {
        HStack(spacing: KagamiSpacing.md) {
            // Icon
            ZStack {
                Circle()
                    .fill(hint.color.opacity(0.2))
                    .frame(width: 40, height: 40)

                Image(systemName: hint.icon)
                    .font(.system(size: 18))
                    .foregroundColor(hint.color)
            }
            .accessibilityHidden(true)

            // Content
            VStack(alignment: .leading, spacing: 2) {
                Text(hint.title)
                    .font(KagamiFont.subheadline(weight: .medium))
                    .foregroundColor(.accessibleTextPrimary)

                Text(hint.message)
                    .font(KagamiFont.caption())
                    .foregroundColor(.accessibleTextSecondary)
                    .lineLimit(2)
            }

            Spacer()

            // Dismiss button
            Button {
                onDismiss()
            } label: {
                Image(systemName: "xmark")
                    .font(.caption)
                    .foregroundColor(.accessibleTextTertiary)
                    .frame(width: 28, height: 28)
                    .background(Color.voidLight)
                    .clipShape(Circle())
            }
            .accessibilityLabel("Dismiss hint")
        }
        .padding(KagamiSpacing.md)
        .background(
            RoundedRectangle(cornerRadius: KagamiRadius.md)
                .fill(Color.voidLight)
                .overlay(
                    RoundedRectangle(cornerRadius: KagamiRadius.md)
                        .stroke(hint.color.opacity(0.3), lineWidth: 1)
                )
        )
        .opacity(isVisible ? 1 : 0)
        .offset(y: isVisible ? 0 : 10)
        .onAppear {
            if reduceMotion {
                isVisible = true
            } else {
                withAnimation(KagamiMotion.smooth.delay(0.3)) {
                    isVisible = true
                }
            }
        }
        .accessibilityElement(children: .combine)
        .accessibilityLabel("\(hint.title). \(hint.message)")
        .accessibilityHint("Swipe right to dismiss")
        .accessibilityAddTraits(.isButton)
        .onTapGesture {
            if let action = onAction {
                action()
                KagamiAnalytics.shared.track(.hintActioned, properties: [
                    "hint_type": hint.rawValue
                ])
            }
        }
    }
}

// MARK: - Hint Overlay Modifier

/// View modifier to show hints as an overlay
struct HintOverlayModifier: ViewModifier {
    @ObservedObject var hintManager = HintManager.shared

    func body(content: Content) -> some View {
        content
            .overlay(alignment: .bottom) {
                if let hint = hintManager.currentHint {
                    InlineHintView(
                        hint: hint,
                        onDismiss: {
                            hintManager.dismissCurrentHint()
                        }
                    )
                    .padding()
                    .padding(.bottom, KagamiLayout.tabBarHeight)
                    .transition(.move(edge: .bottom).combined(with: .opacity))
                }
            }
            .animation(KagamiMotion.smooth, value: hintManager.currentHint != nil)
    }
}

extension View {
    /// Add hint overlay to view
    func withHintOverlay() -> some View {
        modifier(HintOverlayModifier())
    }
}

// MARK: - Feature Discovery Card

/// A larger discovery card for onboarding or settings
struct FeatureDiscoveryCard: View {
    let hint: HintType
    let onAction: () -> Void
    var onDismiss: (() -> Void)?

    var body: some View {
        VStack(spacing: KagamiSpacing.md) {
            // Icon
            ZStack {
                Circle()
                    .fill(hint.color.opacity(0.2))
                    .frame(width: 64, height: 64)

                Image(systemName: hint.icon)
                    .font(.system(size: 28))
                    .foregroundColor(hint.color)
            }

            // Content
            VStack(spacing: KagamiSpacing.xs) {
                Text(hint.title)
                    .font(KagamiFont.headline())
                    .foregroundColor(.accessibleTextPrimary)

                Text(hint.message)
                    .font(KagamiFont.body())
                    .foregroundColor(.accessibleTextSecondary)
                    .multilineTextAlignment(.center)
            }

            // Action button
            Button {
                onAction()
            } label: {
                Text("Try It")
                    .font(KagamiFont.body(weight: .medium))
                    .foregroundColor(.void)
                    .frame(maxWidth: .infinity)
                    .padding(.vertical, 12)
                    .background(hint.color)
                    .cornerRadius(KagamiRadius.sm)
            }
            .accessibilityLabel("Try \(hint.title)")

            // Dismiss link
            if let onDismiss = onDismiss {
                Button {
                    onDismiss()
                } label: {
                    Text("Maybe Later")
                        .font(KagamiFont.caption())
                        .foregroundColor(.accessibleTextTertiary)
                }
            }
        }
        .padding(KagamiSpacing.lg)
        .background(Color.voidLight)
        .cornerRadius(KagamiRadius.lg)
        .accessibilityElement(children: .contain)
    }
}

// MARK: - Hint Tooltip

/// A small tooltip-style hint
struct HintTooltip: View {
    let text: String
    let color: Color

    var body: some View {
        Text(text)
            .font(KagamiFont.caption())
            .foregroundColor(.void)
            .padding(.horizontal, KagamiSpacing.sm)
            .padding(.vertical, KagamiSpacing.xs)
            .background(color)
            .cornerRadius(KagamiRadius.xs)
            .accessibilityLabel(text)
    }
}

// MARK: - Preview

#Preview("Inline Hint") {
    VStack(spacing: 20) {
        InlineHintView(
            hint: .voiceCommands,
            onDismiss: {}
        )

        InlineHintView(
            hint: .longPressScenes,
            onDismiss: {}
        )

        FeatureDiscoveryCard(
            hint: .searchFeature,
            onAction: {},
            onDismiss: {}
        )
    }
    .padding()
    .background(Color.void)
}

/*
 * Mirror
 * Teach without interrupting.
 * Show, don't tell.
 * h(x) >= 0. Always.
 */
