//
// ContentView.swift -- Main App Content for tvOS
//
// Kagami TV -- Tab-based navigation for the 10-foot interface
//
// tvOS Design Principles:
// - Large, TV-friendly buttons (minimum 66pt for focus)
// - Focus-based navigation (Siri Remote)
// - High contrast for visibility from distance (AAA minimum)
// - Smooth, natural animations
// - Theme colors for semantic meaning
//

import SwiftUI
import KagamiDesign

// MARK: - Content View

struct ContentView: View {
    @EnvironmentObject var appModel: TVAppModel
    @State private var selectedTab: Tab = .home

    var body: some View {
        TabView(selection: $selectedTab) {
            HomeView()
                .tabItem {
                    Label("Home", systemImage: "house.fill")
                }
                .tag(Tab.home)

            ScenesView()
                .tabItem {
                    Label("Scenes", systemImage: "sparkles")
                }
                .tag(Tab.scenes)

            SettingsView()
                .tabItem {
                    Label("Settings", systemImage: "gearshape.fill")
                }
                .tag(Tab.settings)
        }
        .alert(
            "Connection Error",
            isPresented: $appModel.showErrorAlert,
            presenting: appModel.currentError
        ) { _ in
            Button("Retry") {
                Task { await appModel.retryLastOperation() }
            }
            Button("Dismiss", role: .cancel) {
                appModel.clearError()
            }
        } message: { error in
            Text(error.localizedDescription)
        }
    }
}

// MARK: - Tab Definition

enum Tab: String, CaseIterable {
    case home
    case scenes
    case settings
}

// MARK: - tvOS Design Constants

/// Design constants optimized for tvOS 10-foot interface
/// Uses KagamiDesign tokens adapted for TV viewing distances
enum TVDesign {
    // MARK: - Spacing (8pt grid, scaled 2x for TV)
    static let gridSpacing: CGFloat = 48       // 24 * 2 for TV
    static let cardSpacing: CGFloat = 32       // 16 * 2 for TV
    static let contentPadding: CGFloat = 80    // 40 * 2 for TV
    static let sectionSpacing: CGFloat = 64    // 32 * 2 for TV

    // MARK: - Sizes (10-foot optimized)
    static let minimumFocusSize: CGFloat = 66  // Apple TV minimum
    static let buttonHeight: CGFloat = 88      // Large touch target
    static let cardMinWidth: CGFloat = 280     // Wide cards
    static let cardMinHeight: CGFloat = 200    // Tall cards
    static let iconSize: CGFloat = 48          // Standard icon
    static let largeIconSize: CGFloat = 72     // Hero icons

    // MARK: - Typography (scaled for 10-foot viewing)
    static let largeTitleSize: CGFloat = 76    // Large titles
    static let titleSize: CGFloat = 48         // Titles
    static let headlineSize: CGFloat = 38      // Headlines
    static let bodySize: CGFloat = 29          // Body text
    static let captionSize: CGFloat = 23       // Captions

    // MARK: - Theme Colors (AAA contrast on black)
    static let primaryColor = Color.crystal
    static let secondaryColor = Color.nexus
    static let successColor = Color.grove
    static let warningColor = Color.beacon
    static let errorColor = Color.spark
    static let cardBackground = Color.obsidian
    static let focusedBackground = Color.carbon

    // MARK: - Corner Radius
    static let cardRadius: CGFloat = 24
    static let buttonRadius: CGFloat = 16
}

// MARK: - TV Motion

/// Animation timing for tvOS
enum TvMotion {
    // Animation durations (seconds)
    static let instant: Double = 0.144
    static let fast: Double = 0.233
    static let normal: Double = 0.377
    static let slow: Double = 0.610
    static let slower: Double = 0.987
    static let slowest: Double = 1.597

    // Pre-built animations
    static let focus = Animation.easeOut(duration: fast)
    static let card = Animation.spring(response: normal, dampingFraction: 0.8)
    static let button = Animation.easeInOut(duration: fast)
    static let cinematic = Animation.easeInOut(duration: slower)
}

// MARK: - TV Card Style

/// Card background for tvOS with focus state support
struct TVCard<Content: View>: View {
    let accentColor: Color
    let content: Content
    @FocusState private var isFocused: Bool

    init(accentColor: Color = TVDesign.primaryColor, @ViewBuilder content: () -> Content) {
        self.accentColor = accentColor
        self.content = content()
    }

    var body: some View {
        content
            .padding(TVDesign.cardSpacing)
            .frame(minWidth: TVDesign.cardMinWidth, minHeight: TVDesign.cardMinHeight)
            .background(
                RoundedRectangle(cornerRadius: TVDesign.cardRadius)
                    .fill(isFocused ? TVDesign.focusedBackground : TVDesign.cardBackground)
            )
            .overlay(
                RoundedRectangle(cornerRadius: TVDesign.cardRadius)
                    .stroke(accentColor.opacity(isFocused ? 0.8 : 0.3), lineWidth: isFocused ? 4 : 2)
            )
            .scaleEffect(isFocused ? 1.05 : 1.0)
            .animation(TvMotion.card, value: isFocused)
            .focused($isFocused)
    }
}

// MARK: - TV Button Style

/// Large, TV-friendly button with focus state
struct TVButtonStyle: ButtonStyle {
    let color: Color

    func makeBody(configuration: Configuration) -> some View {
        configuration.label
            .font(.system(size: TVDesign.bodySize, weight: .semibold))
            .foregroundColor(.white)
            .frame(minHeight: TVDesign.buttonHeight)
            .padding(.horizontal, TVDesign.cardSpacing)
            .background(
                RoundedRectangle(cornerRadius: TVDesign.buttonRadius)
                    .fill(configuration.isPressed ? color.opacity(0.6) : color.opacity(0.4))
            )
            .overlay(
                RoundedRectangle(cornerRadius: TVDesign.buttonRadius)
                    .stroke(color.opacity(0.6), lineWidth: 2)
            )
            .scaleEffect(configuration.isPressed ? 0.95 : 1.0)
    }
}

// MARK: - TV Scene Button

/// Large scene activation button for tvOS
struct TVSceneButton: View {
    let icon: String
    let title: String
    let description: String
    let color: Color
    let action: () async -> Void

    @State private var isExecuting = false
    @FocusState private var isFocused: Bool

    var body: some View {
        Button {
            guard !isExecuting else { return }
            isExecuting = true
            Task {
                await action()
                await MainActor.run {
                    isExecuting = false
                }
            }
        } label: {
            VStack(spacing: 16) {
                ZStack {
                    Circle()
                        .fill(color.opacity(0.2))
                        .frame(width: TVDesign.largeIconSize + 32, height: TVDesign.largeIconSize + 32)

                    if isExecuting {
                        ProgressView()
                            .scaleEffect(1.5)
                    } else {
                        Image(systemName: icon)
                            .font(.system(size: TVDesign.largeIconSize))
                            .foregroundColor(color)
                    }
                }

                Text(title)
                    .font(.system(size: TVDesign.headlineSize, weight: .semibold))
                    .foregroundColor(.white)

                Text(description)
                    .font(.system(size: TVDesign.captionSize))
                    .foregroundColor(.white.opacity(0.7))
                    .multilineTextAlignment(.center)
            }
            .frame(minWidth: TVDesign.cardMinWidth, minHeight: TVDesign.cardMinHeight)
            .padding(TVDesign.cardSpacing)
            .background(
                RoundedRectangle(cornerRadius: TVDesign.cardRadius)
                    .fill(isFocused ? TVDesign.focusedBackground : TVDesign.cardBackground)
            )
            .overlay(
                RoundedRectangle(cornerRadius: TVDesign.cardRadius)
                    .stroke(color.opacity(isFocused ? 0.8 : 0.3), lineWidth: isFocused ? 4 : 2)
            )
            .scaleEffect(isFocused ? 1.05 : 1.0)
            .animation(TvMotion.card, value: isFocused)
        }
        .buttonStyle(.plain)
        .focused($isFocused)
        .disabled(isExecuting)
        .accessibilityLabel(title)
        .accessibilityHint(description)
        .accessibilityAddTraits(.isButton)
        .accessibilityValue(isExecuting ? "Executing" : "Ready")
    }
}

// MARK: - Preview

#Preview {
    ContentView()
        .environmentObject(TVAppModel())
}

/*
 * Mirror
 * h(x) >= 0. Always.
 */
