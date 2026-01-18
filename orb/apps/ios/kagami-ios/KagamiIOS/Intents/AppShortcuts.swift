//
// AppShortcuts.swift — Siri Shortcuts Integration
//
// Colony: Nexus (e4) — Integration
//
// Provides:
//   - AppShortcutsProvider for Shortcuts app integration
//   - SiriTipView for discoverability in the app
//   - Phrase suggestions for natural language activation
//
// h(x) >= 0. Always.
//

import AppIntents
import SwiftUI

// MARK: - App Shortcuts Provider

struct KagamiAppShortcuts: AppShortcutsProvider {

    /// Shortcut phrases that users can say to Siri
    static var appShortcuts: [AppShortcut] {
        // Movie Mode
        AppShortcut(
            intent: MovieModeIntent(),
            phrases: [
                "Start movie mode in \(.applicationName)",
                "Enter movie mode with \(.applicationName)",
                "Movie time with \(.applicationName)",
                "\(.applicationName) movie mode",
                "Dim the lights for a movie in \(.applicationName)"
            ],
            shortTitle: "Movie Mode",
            systemImageName: "film"
        )

        // Goodnight
        AppShortcut(
            intent: GoodnightIntent(),
            phrases: [
                "Goodnight with \(.applicationName)",
                "\(.applicationName) goodnight",
                "Turn everything off with \(.applicationName)",
                "Go to sleep with \(.applicationName)",
                "Bedtime with \(.applicationName)"
            ],
            shortTitle: "Goodnight",
            systemImageName: "moon.fill"
        )

        // Welcome Home
        AppShortcut(
            intent: WelcomeHomeIntent(),
            phrases: [
                "I'm home with \(.applicationName)",
                "Welcome home with \(.applicationName)",
                "\(.applicationName) I'm home",
                "Turn on the lights with \(.applicationName)"
            ],
            shortTitle: "Welcome Home",
            systemImageName: "house.fill"
        )

        // Note: SetLightsIntent removed from shortcuts because Int parameters
        // are not valid for App Shortcuts. Use voice commands with specific levels
        // via Siri without the shortcut phrase system.

        // Fireplace
        AppShortcut(
            intent: ToggleFireplaceIntent(),
            phrases: [
                "Toggle fireplace in \(.applicationName)",
                "Turn on fireplace with \(.applicationName)",
                "Start the fire with \(.applicationName)",
                "\(.applicationName) fireplace"
            ],
            shortTitle: "Fireplace",
            systemImageName: "flame.fill"
        )

        // Lock All
        AppShortcut(
            intent: LockAllIntent(),
            phrases: [
                "Lock all doors with \(.applicationName)",
                "\(.applicationName) lock up",
                "Secure the house with \(.applicationName)"
            ],
            shortTitle: "Lock All",
            systemImageName: "lock.fill"
        )

        // Safety Score
        AppShortcut(
            intent: GetSafetyScoreIntent(),
            phrases: [
                "What's my safety score in \(.applicationName)",
                "\(.applicationName) safety status",
                "Check h x with \(.applicationName)",
                "Is everything safe with \(.applicationName)"
            ],
            shortTitle: "Safety Score",
            systemImageName: "checkmark.shield.fill"
        )

        // Shades
        AppShortcut(
            intent: ControlShadesIntent(),
            phrases: [
                "Open shades with \(.applicationName)",
                "Close shades with \(.applicationName)",
                "\(.applicationName) control shades"
            ],
            shortTitle: "Shades",
            systemImageName: "blinds.horizontal.open"
        )

        // TV Control
        AppShortcut(
            intent: TVControlIntent(),
            phrases: [
                "Lower TV with \(.applicationName)",
                "Raise TV with \(.applicationName)",
                "\(.applicationName) TV control"
            ],
            shortTitle: "TV Control",
            systemImageName: "tv"
        )

        // Focus Mode
        AppShortcut(
            intent: FocusModeIntent(),
            phrases: [
                "Focus mode with \(.applicationName)",
                "\(.applicationName) focus time",
                "Help me focus with \(.applicationName)",
                "Start focus session with \(.applicationName)"
            ],
            shortTitle: "Focus Mode",
            systemImageName: "brain.head.profile"
        )

        // Relax Mode
        AppShortcut(
            intent: RelaxModeIntent(),
            phrases: [
                "Relax mode with \(.applicationName)",
                "\(.applicationName) chill time",
                "Help me relax with \(.applicationName)",
                "Cozy mode with \(.applicationName)"
            ],
            shortTitle: "Relax Mode",
            systemImageName: "leaf.fill"
        )

        // Energy Mode
        AppShortcut(
            intent: EnergyModeIntent(),
            phrases: [
                "Energy mode with \(.applicationName)",
                "\(.applicationName) energize",
                "Bright lights with \(.applicationName)",
                "Wake me up with \(.applicationName)"
            ],
            shortTitle: "Energy Mode",
            systemImageName: "bolt.fill"
        )

        // Reading Mode
        AppShortcut(
            intent: ReadingModeIntent(),
            phrases: [
                "Reading mode with \(.applicationName)",
                "\(.applicationName) reading time",
                "Reading lights with \(.applicationName)"
            ],
            shortTitle: "Reading Mode",
            systemImageName: "book.fill"
        )

        // Morning Routine
        AppShortcut(
            intent: MorningRoutineIntent(),
            phrases: [
                "Good morning with \(.applicationName)",
                "\(.applicationName) morning routine",
                "Start my day with \(.applicationName)"
            ],
            shortTitle: "Morning Routine",
            systemImageName: "sunrise.fill"
        )

        // Away Mode
        AppShortcut(
            intent: AwayModeIntent(),
            phrases: [
                "Away mode with \(.applicationName)",
                "\(.applicationName) I'm leaving",
                "Secure the house with \(.applicationName)",
                "Leaving home with \(.applicationName)"
            ],
            shortTitle: "Away Mode",
            systemImageName: "figure.walk.departure"
        )

        // Quick Dim
        AppShortcut(
            intent: QuickDimIntent(),
            phrases: [
                "Dim lights with \(.applicationName)",
                "Brighten lights with \(.applicationName)",
                "\(.applicationName) dim",
                "\(.applicationName) brighten"
            ],
            shortTitle: "Quick Dim",
            systemImageName: "slider.horizontal.3"
        )

        // Garage Door
        AppShortcut(
            intent: GarageDoorIntent(),
            phrases: [
                "Garage door with \(.applicationName)",
                "Open garage with \(.applicationName)",
                "Close garage with \(.applicationName)",
                "\(.applicationName) garage"
            ],
            shortTitle: "Garage Door",
            systemImageName: "car.top.door.front.left.open"
        )
    }
}

// MARK: - Siri Tip Views

/// A view that displays a Siri tip for discovering voice commands
struct KagamiSiriTip: View {
    let intent: any AppIntent
    let text: String

    var body: some View {
        SiriTipView(intent: intent, isVisible: .constant(true))
            .siriTipViewStyle(.automatic)
    }
}

/// Siri tip for Movie Mode
struct MovieModeSiriTip: View {
    var body: some View {
        SiriTipView(intent: MovieModeIntent(), isVisible: .constant(true))
    }
}

/// Siri tip for Goodnight
struct GoodnightSiriTip: View {
    var body: some View {
        SiriTipView(intent: GoodnightIntent(), isVisible: .constant(true))
    }
}

/// Siri tip for Welcome Home
struct WelcomeHomeSiriTip: View {
    var body: some View {
        SiriTipView(intent: WelcomeHomeIntent(), isVisible: .constant(true))
    }
}

// MARK: - Shortcuts Discovery View

/// A view that showcases available Siri Shortcuts
struct ShortcutsDiscoveryView: View {
    @State private var selectedShortcut: ShortcutItem?

    struct ShortcutItem: Identifiable {
        let id = UUID()
        let title: String
        let phrase: String
        let icon: String
        let color: Color
        let intent: any AppIntent
    }

    private let shortcuts: [ShortcutItem] = [
        ShortcutItem(
            title: "Movie Mode",
            phrase: "\"Hey Siri, movie time with Kagami\"",
            icon: "film",
            color: .purple,
            intent: MovieModeIntent()
        ),
        ShortcutItem(
            title: "Goodnight",
            phrase: "\"Hey Siri, goodnight with Kagami\"",
            icon: "moon.fill",
            color: .cyan,
            intent: GoodnightIntent()
        ),
        ShortcutItem(
            title: "Welcome Home",
            phrase: "\"Hey Siri, I'm home with Kagami\"",
            icon: "house.fill",
            color: .orange,
            intent: WelcomeHomeIntent()
        ),
        ShortcutItem(
            title: "Focus Mode",
            phrase: "\"Hey Siri, focus mode with Kagami\"",
            icon: "brain.head.profile",
            color: .blue,
            intent: FocusModeIntent()
        ),
        ShortcutItem(
            title: "Relax Mode",
            phrase: "\"Hey Siri, relax with Kagami\"",
            icon: "leaf.fill",
            color: .green,
            intent: RelaxModeIntent()
        ),
        ShortcutItem(
            title: "Fireplace",
            phrase: "\"Hey Siri, start fire with Kagami\"",
            icon: "flame.fill",
            color: .red,
            intent: ToggleFireplaceIntent()
        ),
        ShortcutItem(
            title: "Morning",
            phrase: "\"Hey Siri, good morning with Kagami\"",
            icon: "sunrise.fill",
            color: .yellow,
            intent: MorningRoutineIntent()
        ),
        ShortcutItem(
            title: "Safety Score",
            phrase: "\"Hey Siri, check safety with Kagami\"",
            icon: "checkmark.shield.fill",
            color: .mint,
            intent: GetSafetyScoreIntent()
        ),
    ]

    var body: some View {
        VStack(alignment: .leading, spacing: 16) {
            Text("Siri Shortcuts")
                .font(.headline)
                .foregroundStyle(.white)

            Text("Say these phrases to control your home")
                .font(.caption)
                .foregroundStyle(.secondary)

            LazyVGrid(columns: [GridItem(.flexible()), GridItem(.flexible())], spacing: 12) {
                ForEach(shortcuts) { shortcut in
                    ShortcutCard(shortcut: shortcut)
                        .onTapGesture {
                            selectedShortcut = shortcut
                        }
                }
            }
        }
        .padding()
        .sheet(item: $selectedShortcut) { shortcut in
            ShortcutDetailSheet(shortcut: shortcut)
        }
    }
}

struct ShortcutCard: View {
    let shortcut: ShortcutsDiscoveryView.ShortcutItem

    var body: some View {
        VStack(spacing: 8) {
            Image(systemName: shortcut.icon)
                .font(.title2)
                .foregroundStyle(shortcut.color)

            Text(shortcut.title)
                .font(.caption)
                .fontWeight(.medium)
                .foregroundStyle(.white)
        }
        .frame(maxWidth: .infinity)
        .padding(.vertical, 16)
        .background(
            RoundedRectangle(cornerRadius: 12)
                .fill(shortcut.color.opacity(0.1))
        )
        .overlay(
            RoundedRectangle(cornerRadius: 12)
                .stroke(shortcut.color.opacity(0.3), lineWidth: 1)
        )
    }
}

struct ShortcutDetailSheet: View {
    let shortcut: ShortcutsDiscoveryView.ShortcutItem
    @Environment(\.dismiss) private var dismiss

    var body: some View {
        NavigationStack {
            VStack(spacing: 24) {
                // Icon
                ZStack {
                    Circle()
                        .fill(shortcut.color.opacity(0.15))
                        .frame(width: 80, height: 80)

                    Image(systemName: shortcut.icon)
                        .font(.system(size: 32))
                        .foregroundStyle(shortcut.color)
                }

                // Title
                Text(shortcut.title)
                    .font(.title2)
                    .fontWeight(.bold)
                    .foregroundStyle(.white)

                // Phrase
                VStack(spacing: 8) {
                    Text("Say to Siri:")
                        .font(.caption)
                        .foregroundStyle(.secondary)

                    Text(shortcut.phrase)
                        .font(.body)
                        .fontWeight(.medium)
                        .foregroundStyle(shortcut.color)
                        .padding()
                        .background(
                            RoundedRectangle(cornerRadius: 12)
                                .fill(Color.white.opacity(0.05))
                        )
                }

                // Siri Tip
                SiriTipView(intent: shortcut.intent, isVisible: .constant(true))
                    .padding(.horizontal)

                Spacer()

                // Add to Siri button
                ShortcutsLink()
                    .shortcutsLinkStyle(.automaticOutline)
            }
            .padding()
            .background(Color.black)
            .navigationTitle("Shortcut")
            .navigationBarTitleDisplayMode(.inline)
            .toolbar {
                ToolbarItem(placement: .topBarTrailing) {
                    Button("Done") {
                        dismiss()
                    }
                }
            }
        }
        .presentationDetents([.medium])
        .presentationDragIndicator(.visible)
    }
}

// MARK: - Shortcut Quick Actions

/// Quick action buttons that trigger intents directly
struct ShortcutQuickActions: View {
    var body: some View {
        HStack(spacing: 12) {
            QuickActionIntentButton(
                title: "Movie",
                icon: "film",
                color: .purple,
                intent: MovieModeIntent()
            )

            QuickActionIntentButton(
                title: "Goodnight",
                icon: "moon.fill",
                color: .cyan,
                intent: GoodnightIntent()
            )

            QuickActionIntentButton(
                title: "Welcome",
                icon: "house.fill",
                color: .orange,
                intent: WelcomeHomeIntent()
            )
        }
    }
}

struct QuickActionIntentButton<I: AppIntent>: View {
    let title: String
    let icon: String
    let color: Color
    let intent: I

    var body: some View {
        Button(intent: intent) {
            VStack(spacing: 6) {
                Image(systemName: icon)
                    .font(.title3)
                    .foregroundStyle(color)

                Text(title)
                    .font(.caption2)
                    .foregroundStyle(.secondary)
            }
            .frame(maxWidth: .infinity)
            .padding(.vertical, 12)
            .background(
                RoundedRectangle(cornerRadius: 10)
                    .fill(color.opacity(0.1))
            )
        }
        .buttonStyle(.plain)
    }
}

// Color extension removed - use KagamiDesign.Color or SwiftUI predefined colors

// MARK: - Preview

#Preview("Shortcuts Discovery") {
    ShortcutsDiscoveryView()
        .background(Color.black)
        .preferredColorScheme(.dark)
}

#Preview("Quick Actions") {
    ShortcutQuickActions()
        .padding()
        .background(Color.black)
        .preferredColorScheme(.dark)
}

/*
 * Mirror
 * h(x) >= 0. Always.
 */
