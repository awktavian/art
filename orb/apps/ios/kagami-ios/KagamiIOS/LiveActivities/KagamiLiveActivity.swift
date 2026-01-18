//
// KagamiLiveActivity.swift — Dynamic Island & Lock Screen Live Activities
//
// Colony: Nexus (e₄) — Integration
//
// Features:
//   - Dynamic Island presence (compact & expanded views)
//   - Lock screen live updates
//   - Real-time status display (safety, room states, scenes)
//   - Quick actions from expanded view
//
// Architecture:
//   KagamiAPIService → LiveActivityManager → ActivityKit → System UI
//
// h(x) ≥ 0. Always.
//

import ActivityKit
import SwiftUI
import WidgetKit

// MARK: - Live Activity Attributes

/// Defines the content that can be displayed in the Live Activity.
/// Attributes are the dynamic content that updates over time.
struct KagamiLiveActivityAttributes: ActivityAttributes {

    /// Static content that doesn't change during the activity lifecycle
    public struct ContentState: Codable, Hashable {
        /// Current safety score (0.0 to 1.0)
        var safetyScore: Double

        /// Current scene name (e.g., "Movie Mode", "Goodnight")
        var activeScene: String?

        /// Current room being controlled
        var activeRoom: String?

        /// Light level percentage (0-100)
        var lightLevel: Int?

        /// Whether someone is home
        var isOccupied: Bool

        /// Number of active devices
        var activeDevices: Int

        /// Last update timestamp
        var lastUpdate: Date

        /// Status message to display
        var statusMessage: String?
    }

    /// Name of the activity type
    var activityName: String = "KagamiStatus"
}

// MARK: - Live Activity Widget

/// The widget that renders in Dynamic Island and Lock Screen
@available(iOS 16.1, *)
struct KagamiLiveActivityWidget: Widget {
    var body: some WidgetConfiguration {
        ActivityConfiguration(for: KagamiLiveActivityAttributes.self) { context in
            // Lock Screen view
            KagamiLockScreenView(context: context)
        } dynamicIsland: { context in
            // Dynamic Island
            DynamicIsland {
                // Expanded regions
                DynamicIslandExpandedRegion(.leading) {
                    KagamiExpandedLeading(context: context)
                }

                DynamicIslandExpandedRegion(.trailing) {
                    KagamiExpandedTrailing(context: context)
                }

                DynamicIslandExpandedRegion(.center) {
                    KagamiExpandedCenter(context: context)
                }

                DynamicIslandExpandedRegion(.bottom) {
                    KagamiExpandedBottom(context: context)
                }
            } compactLeading: {
                // Compact leading (left pill)
                KagamiCompactLeading(context: context)
            } compactTrailing: {
                // Compact trailing (right pill)
                KagamiCompactTrailing(context: context)
            } minimal: {
                // Minimal (single bubble when another activity is running)
                KagamiMinimal(context: context)
            }
        }
    }
}

// MARK: - Lock Screen View

@available(iOS 16.1, *)
struct KagamiLockScreenView: View {
    let context: ActivityViewContext<KagamiLiveActivityAttributes>

    var body: some View {
        HStack(spacing: 12) {
            // Safety indicator
            SafetyIndicator(score: context.state.safetyScore)

            VStack(alignment: .leading, spacing: 4) {
                // Main status
                Text(context.state.activeScene ?? "Kagami Active")
                    .font(.headline)
                    .foregroundStyle(.white)

                // Secondary info
                HStack(spacing: 8) {
                    if let room = context.state.activeRoom {
                        Label(room, systemImage: "house.fill")
                            .font(.caption)
                            .foregroundStyle(.secondary)
                    }

                    if let level = context.state.lightLevel {
                        Label("\(level)%", systemImage: "lightbulb.fill")
                            .font(.caption)
                            .foregroundStyle(.secondary)
                    }

                    if context.state.isOccupied {
                        Label("Home", systemImage: "person.fill")
                            .font(.caption)
                            .foregroundStyle(.secondary)
                    }
                }
            }

            Spacer()

            // Quick action button
            if let url = URL(string: "kagami://scene/goodnight") {
                Link(destination: url) {
                    Image(systemName: "moon.fill")
                        .font(.title2)
                        .foregroundStyle(.purple)
                }
            }
        }
        .padding()
        .background(.ultraThinMaterial)
    }
}

// MARK: - Dynamic Island Views

@available(iOS 16.1, *)
struct KagamiCompactLeading: View {
    let context: ActivityViewContext<KagamiLiveActivityAttributes>

    var body: some View {
        SafetyIndicator(score: context.state.safetyScore, size: 24)
    }
}

@available(iOS 16.1, *)
struct KagamiCompactTrailing: View {
    let context: ActivityViewContext<KagamiLiveActivityAttributes>

    var body: some View {
        if let scene = context.state.activeScene {
            Text(scene)
                .font(.caption2)
                .fontWeight(.medium)
                .foregroundStyle(.white)
        } else {
            Image(systemName: "house.fill")
                .font(.caption)
                .foregroundStyle(.white)
        }
    }
}

@available(iOS 16.1, *)
struct KagamiMinimal: View {
    let context: ActivityViewContext<KagamiLiveActivityAttributes>

    var body: some View {
        SafetyIndicator(score: context.state.safetyScore, size: 20)
    }
}

@available(iOS 16.1, *)
struct KagamiExpandedLeading: View {
    let context: ActivityViewContext<KagamiLiveActivityAttributes>

    var body: some View {
        VStack(alignment: .leading) {
            SafetyIndicator(score: context.state.safetyScore, size: 32)

            Text("Safe")
                .font(.caption2)
                .foregroundStyle(.secondary)
        }
    }
}

@available(iOS 16.1, *)
struct KagamiExpandedTrailing: View {
    let context: ActivityViewContext<KagamiLiveActivityAttributes>

    var body: some View {
        VStack(alignment: .trailing) {
            if let level = context.state.lightLevel {
                HStack(spacing: 4) {
                    Image(systemName: "lightbulb.fill")
                    Text("\(level)%")
                }
                .font(.caption)
                .foregroundStyle(.yellow)
            }

            Text("\(context.state.activeDevices) active")
                .font(.caption2)
                .foregroundStyle(.secondary)
        }
    }
}

@available(iOS 16.1, *)
struct KagamiExpandedCenter: View {
    let context: ActivityViewContext<KagamiLiveActivityAttributes>

    var body: some View {
        VStack(spacing: 4) {
            Text(context.state.activeScene ?? "鏡 Kagami")
                .font(.headline)
                .fontWeight(.semibold)
                .foregroundStyle(.white)

            if let message = context.state.statusMessage {
                Text(message)
                    .font(.caption)
                    .foregroundStyle(.secondary)
            }
        }
    }
}

@available(iOS 16.1, *)
struct KagamiExpandedBottom: View {
    let context: ActivityViewContext<KagamiLiveActivityAttributes>

    private static let quickActions: [(icon: String, label: String, urlString: String, color: Color)] = [
        ("film", "Movie", "kagami://scene/movie", .purple),
        ("moon.fill", "Goodnight", "kagami://scene/goodnight", .indigo),
        ("lightbulb.fill", "Lights", "kagami://lights/toggle", .yellow),
        ("lock.fill", "Lock", "kagami://lock/all", .green)
    ]

    var body: some View {
        HStack(spacing: 16) {
            // Quick action buttons
            ForEach(Self.quickActions, id: \.label) { action in
                if let url = URL(string: action.urlString) {
                    LiveActivityQuickActionButton(
                        icon: action.icon,
                        label: action.label,
                        url: url,
                        color: action.color
                    )
                }
            }
        }
    }
}

// MARK: - Helper Views

struct SafetyIndicator: View {
    let score: Double
    var size: CGFloat = 28

    var color: Color {
        switch score {
        case 0.7...1.0: return .green
        case 0.3..<0.7: return .orange
        default: return .red
        }
    }

    var body: some View {
        ZStack {
            Circle()
                .stroke(color.opacity(0.3), lineWidth: 3)
                .frame(width: size, height: size)

            Circle()
                .trim(from: 0, to: score)
                .stroke(color, style: StrokeStyle(lineWidth: 3, lineCap: .round))
                .frame(width: size, height: size)
                .rotationEffect(.degrees(-90))

            Text(String(format: "%.1f", score))
                .font(.system(size: size * 0.35, weight: .bold, design: .rounded))
                .foregroundStyle(color)
        }
    }
}

struct LiveActivityQuickActionButton: View {
    let icon: String
    let label: String
    let url: URL
    let color: Color

    var body: some View {
        Link(destination: url) {
            VStack(spacing: 4) {
                Image(systemName: icon)
                    .font(.title3)
                    .foregroundStyle(color)

                Text(label)
                    .font(.caption2)
                    .foregroundStyle(.secondary)
            }
        }
    }
}

// MARK: - Live Activity Manager

/// Manages the lifecycle of Kagami's Live Activity
@available(iOS 16.1, *)
@MainActor
class LiveActivityManager: ObservableObject {

    static let shared = LiveActivityManager()

    @Published var currentActivity: Activity<KagamiLiveActivityAttributes>?
    @Published var isActivityActive: Bool = false

    private init() {}

    /// Check if Live Activities are supported and enabled
    var areActivitiesEnabled: Bool {
        ActivityAuthorizationInfo().areActivitiesEnabled
    }

    /// Start a new Live Activity
    func startActivity(
        safetyScore: Double = 1.0,
        activeScene: String? = nil,
        activeRoom: String? = nil,
        lightLevel: Int? = nil,
        isOccupied: Bool = true,
        activeDevices: Int = 0
    ) {
        guard areActivitiesEnabled else {
            print("⚠️ Live Activities not enabled")
            return
        }

        let attributes = KagamiLiveActivityAttributes()
        let initialState = KagamiLiveActivityAttributes.ContentState(
            safetyScore: safetyScore,
            activeScene: activeScene,
            activeRoom: activeRoom,
            lightLevel: lightLevel,
            isOccupied: isOccupied,
            activeDevices: activeDevices,
            lastUpdate: Date(),
            statusMessage: nil
        )

        do {
            let activity = try Activity.request(
                attributes: attributes,
                content: .init(state: initialState, staleDate: nil),
                pushType: .token
            )

            currentActivity = activity
            isActivityActive = true
            print("✅ Live Activity started: \(activity.id)")

            // Listen for push token updates
            Task {
                for await token in activity.pushTokenUpdates {
                    let tokenString = token.map { String(format: "%02x", $0) }.joined()
                    print("📲 Push token: \(tokenString)")
                    // Send token to Kagami backend for push updates
                    await sendPushTokenToBackend(tokenString)
                }
            }

        } catch {
            print("❌ Failed to start Live Activity: \(error)")
        }
    }

    /// Update the current Live Activity
    func updateActivity(
        safetyScore: Double? = nil,
        activeScene: String? = nil,
        activeRoom: String? = nil,
        lightLevel: Int? = nil,
        isOccupied: Bool? = nil,
        activeDevices: Int? = nil,
        statusMessage: String? = nil
    ) async {
        guard let activity = currentActivity else {
            print("⚠️ No active Live Activity to update")
            return
        }

        let currentState = activity.content.state
        let newState = KagamiLiveActivityAttributes.ContentState(
            safetyScore: safetyScore ?? currentState.safetyScore,
            activeScene: activeScene ?? currentState.activeScene,
            activeRoom: activeRoom ?? currentState.activeRoom,
            lightLevel: lightLevel ?? currentState.lightLevel,
            isOccupied: isOccupied ?? currentState.isOccupied,
            activeDevices: activeDevices ?? currentState.activeDevices,
            lastUpdate: Date(),
            statusMessage: statusMessage ?? currentState.statusMessage
        )

        await activity.update(
            ActivityContent(state: newState, staleDate: Date().addingTimeInterval(300))
        )

        print("🔄 Live Activity updated")
    }

    /// End the current Live Activity
    func endActivity(dismissalPolicy: ActivityUIDismissalPolicy = .default) async {
        guard let activity = currentActivity else {
            print("⚠️ No active Live Activity to end")
            return
        }

        let finalState = activity.content.state
        await activity.end(
            ActivityContent(state: finalState, staleDate: nil),
            dismissalPolicy: dismissalPolicy
        )

        currentActivity = nil
        isActivityActive = false
        print("🛑 Live Activity ended")
    }

    /// Send push token to Kagami backend for remote updates
    private func sendPushTokenToBackend(_ token: String) async {
        // Would call KagamiAPIService to register the token
        print("📤 Would send push token to backend: \(token.prefix(20))...")
    }
}

// MARK: - Preview

#if DEBUG
@available(iOS 16.1, *)
struct KagamiLiveActivity_Previews: PreviewProvider {
    static var previews: some View {
        let state = KagamiLiveActivityAttributes.ContentState(
            safetyScore: 0.85,
            activeScene: "Movie Mode",
            activeRoom: "Living Room",
            lightLevel: 20,
            isOccupied: true,
            activeDevices: 12,
            lastUpdate: Date(),
            statusMessage: "Enjoying the show"
        )

        // Would need ActivityKit preview context here
        SafetyIndicator(score: 0.85)
            .padding()
            .background(Color.black)
            .previewLayout(.sizeThatFits)
    }
}
#endif

/*
 * 鏡
 * h(x) ≥ 0. Always.
 *
 * Always present, never intrusive.
 * A gentle reminder of safety and status.
 * One glance away from understanding.
 */
