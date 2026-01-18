//
// DesignSystem.swift — Kagami iOS Design System
//
// Extensible design foundation for iOS/watchOS/visionOS.
// All values should be semantic and overridable.
//
// NOTE: Color tokens are defined in DesignTokens.generated.swift.
// Do not add Color extensions here - import them from there.
//

import SwiftUI
import KagamiDesign

// MARK: - Motion Tokens

struct KagamiMotion {
    // MARK: - Duration Tokens (in seconds)
    // Based on natural timing progressions for smooth, harmonious animations

    /// 89ms - Micro interactions (instant feedback)
    static let instant: Double = 0.089

    /// 144ms - Fast transitions (button presses, toggles)
    static let fast: Double = 0.144

    /// 233ms - Normal duration (standard animations)
    static let normal: Double = 0.233

    /// 377ms - Slow transitions (page transitions, overlays)
    static let slow: Double = 0.377

    /// 610ms - Slower animations (complex sequences)
    static let slower: Double = 0.610

    /// 987ms - Slowest animations (breathing effects)
    static let slowest: Double = 0.987

    /// 1597ms - Extended animations (ambient effects)
    static let extended: Double = 1.597

    /// 2584ms - Breathing rhythm (meditation/ambient)
    static let breathing: Double = 2.584

    // MARK: - Spring Configurations

    /// Micro spring for instant feedback (89ms response)
    static let microSpring = Animation.spring(response: instant, dampingFraction: 0.8)

    /// Fast spring for quick interactions (144ms response)
    static let fastSpring = Animation.spring(response: fast, dampingFraction: 0.75)

    /// Default spring for standard interactions (233ms response)
    static let defaultSpring = Animation.spring(response: normal, dampingFraction: 0.7)

    /// Soft spring for gentle animations (377ms response)
    static let softSpring = Animation.spring(response: slow, dampingFraction: 0.65)

    /// Bouncy spring for playful feedback
    static let bouncySpring = Animation.spring(response: normal, dampingFraction: 0.5, blendDuration: fast)

    /// Heavy spring for emphasis
    static let heavySpring = Animation.spring(response: slow, dampingFraction: 0.85)

    // MARK: - Easing Curves
    // Custom timing curves for different animation feels

    /// Smooth ease-out transition
    static let fold = Animation.timingCurve(0.7, 0, 0.3, 1, duration: normal)

    /// Sharp ease-in-out with anticipation
    static let cusp = Animation.timingCurve(0.4, 0, 0.2, 1, duration: normal)

    /// Overshoot with settle (elastic feel)
    static let swallowtail = Animation.timingCurve(0.34, 1.2, 0.64, 1, duration: slow)

    /// Complex overshoot both directions (playful)
    static let butterfly = Animation.timingCurve(0.68, -0.2, 0.32, 1.2, duration: slow)

    /// Smooth default easing
    static let smooth = Animation.timingCurve(0.16, 1, 0.3, 1, duration: normal)

    /// Entrance easing - starts slow, accelerates in
    static let entrance = Animation.timingCurve(0.0, 0.0, 0.2, 1, duration: normal)

    /// Exit easing - starts fast, decelerates out
    static let exit = Animation.timingCurve(0.4, 0.0, 1, 1, duration: fast)

    // MARK: - Semantic Animation Helpers

    /// Create a staggered delay for list item animations
    static func staggerDelay(index: Int) -> Double {
        // Progressive delays for natural stagger effect
        let delays: [Double] = [0, 0.055, 0.089, 0.144, 0.233, 0.377, 0.610]
        return index < delays.count ? delays[index] : Double(index) * instant
    }

    /// Create animation with specified style and duration
    static func animation(_ style: AnimationStyle, duration: Double = normal) -> Animation {
        switch style {
        case .spring:
            return .spring(response: duration, dampingFraction: 0.7)
        case .bounce:
            return .spring(response: duration, dampingFraction: 0.5, blendDuration: fast)
        case .smooth:
            return .timingCurve(0.16, 1, 0.3, 1, duration: duration)
        case .sharp:
            return .timingCurve(0.4, 0, 0.2, 1, duration: duration)
        case .fold:
            return .timingCurve(0.7, 0, 0.3, 1, duration: duration)
        case .cusp:
            return .timingCurve(0.4, 0, 0.2, 1, duration: duration)
        }
    }

    /// Animation style enumeration
    enum AnimationStyle {
        case spring
        case bounce
        case smooth
        case sharp
        case fold
        case cusp
    }
}

// MARK: - Verified Animation View Modifiers

/// Fade in animation with natural timing
struct FibonacciFadeIn: ViewModifier {
    @Environment(\.accessibilityReduceMotion) var reduceMotion
    @State private var appeared = false
    let delay: Double
    let duration: Double

    init(delay: Double = 0, duration: Double = KagamiMotion.normal) {
        self.delay = delay
        self.duration = duration
    }

    func body(content: Content) -> some View {
        content
            .opacity(appeared ? 1 : 0)
            .onAppear {
                if reduceMotion {
                    appeared = true
                } else {
                    withAnimation(KagamiMotion.smooth.delay(delay)) {
                        appeared = true
                    }
                }
            }
    }
}

/// Scale bounce animation for emphasis
struct FibonacciScaleBounce: ViewModifier {
    @Environment(\.accessibilityReduceMotion) var reduceMotion
    @State private var bounced = false
    let delay: Double

    func body(content: Content) -> some View {
        content
            .scaleEffect(bounced ? 1 : 0.8)
            .onAppear {
                if reduceMotion {
                    bounced = true
                } else {
                    withAnimation(KagamiMotion.bouncySpring.delay(delay)) {
                        bounced = true
                    }
                }
            }
    }
}

/// Staggered list item entrance with progressive delays
struct StaggeredEntrance: ViewModifier {
    @Environment(\.accessibilityReduceMotion) var reduceMotion
    @State private var appeared = false
    let index: Int

    func body(content: Content) -> some View {
        content
            .opacity(appeared ? 1 : 0)
            .offset(y: appeared || reduceMotion ? 0 : 16)
            .onAppear {
                if reduceMotion {
                    appeared = true
                } else {
                    let delay = KagamiMotion.staggerDelay(index: index)
                    withAnimation(KagamiMotion.smooth.delay(delay)) {
                        appeared = true
                    }
                }
            }
    }
}

/// Breathing scale effect for ambient indicators
struct BreathingEffect: ViewModifier {
    @Environment(\.accessibilityReduceMotion) var reduceMotion
    @State private var isBreathing = false

    let minScale: CGFloat
    let maxScale: CGFloat

    init(minScale: CGFloat = 0.95, maxScale: CGFloat = 1.05) {
        self.minScale = minScale
        self.maxScale = maxScale
    }

    func body(content: Content) -> some View {
        content
            .scaleEffect(isBreathing && !reduceMotion ? maxScale : minScale)
            .onAppear {
                guard !reduceMotion else { return }
                withAnimation(
                    Animation.easeInOut(duration: KagamiMotion.breathing)
                        .repeatForever(autoreverses: true)
                ) {
                    isBreathing = true
                }
            }
    }
}

/// Easing curve transition for dramatic state changes
struct CatastropheTransition: ViewModifier {
    @Environment(\.accessibilityReduceMotion) var reduceMotion
    let isActive: Bool
    let style: CatastropheStyle

    enum CatastropheStyle {
        case fold      // Simple smooth transition
        case cusp      // Sharp with anticipation
        case swallowtail // Elastic overshoot and settle
        case butterfly // Playful oscillation
    }

    func body(content: Content) -> some View {
        content
            .animation(animation, value: isActive)
    }

    private var animation: Animation {
        guard !reduceMotion else { return .none }

        switch style {
        case .fold:
            return KagamiMotion.fold
        case .cusp:
            return KagamiMotion.cusp
        case .swallowtail:
            return KagamiMotion.swallowtail
        case .butterfly:
            return KagamiMotion.butterfly
        }
    }
}

// MARK: - Spacing Tokens
// NOTE: KagamiSpacing is defined in DesignTokens.generated.swift
// This typedef exists for backwards compatibility with existing code.

// MARK: - Radius Tokens
// NOTE: KagamiRadius is defined in DesignTokens.generated.swift
// This typedef exists for backwards compatibility with existing code.

// MARK: - Layout Tokens

enum KagamiLayout {
    /// Standard iOS tab bar height
    static let tabBarHeight: CGFloat = 49
    /// Minimum touch target size (WCAG 2.1 AA)
    static let minTouchTarget: CGFloat = 44
    /// Safe area bottom padding for iPhones with home indicator
    static let homeIndicatorPadding: CGFloat = 34
}

// MARK: - Animation Modifiers

/// Ive: "Press scale of 0.97 is too subtle. Users need to FEEL the press at 0.95."
struct PressEffect: ViewModifier {
    @Environment(\.accessibilityReduceMotion) var reduceMotion
    @State private var isPressed = false

    func body(content: Content) -> some View {
        content
            .scaleEffect(isPressed && !reduceMotion ? 0.95 : 1.0)  // Ive: More satisfying press
            .animation(reduceMotion ? nil : KagamiMotion.microSpring, value: isPressed)
            .simultaneousGesture(
                DragGesture(minimumDistance: 0)
                    .onChanged { _ in isPressed = true }
                    .onEnded { _ in isPressed = false }
            )
    }
}

struct PulseEffect: ViewModifier {
    @Environment(\.accessibilityReduceMotion) var reduceMotion
    @State private var isPulsing = false

    func body(content: Content) -> some View {
        content
            .scaleEffect(isPulsing && !reduceMotion ? 1.05 : 1.0)
            .opacity(isPulsing && !reduceMotion ? 0.7 : 1.0)
            .onAppear {
                guard !reduceMotion else { return }
                withAnimation(Animation.easeInOut(duration: 1).repeatForever(autoreverses: true)) {
                    isPulsing = true
                }
            }
    }
}

struct GlowEffect: ViewModifier {
    @Environment(\.accessibilityReduceMotion) var reduceMotion
    let color: Color
    @State private var isGlowing = false

    func body(content: Content) -> some View {
        content
            .shadow(color: color.opacity(reduceMotion ? 0.3 : (isGlowing ? 0.4 : 0)), radius: reduceMotion ? 8 : (isGlowing ? 12 : 0))
            .onAppear {
                guard !reduceMotion else { return }
                withAnimation(Animation.easeInOut(duration: 1.5).repeatForever(autoreverses: true)) {
                    isGlowing = true
                }
            }
    }
}

struct SlideUpEntrance: ViewModifier {
    @Environment(\.accessibilityReduceMotion) var reduceMotion
    @State private var appeared = false
    let delay: Double

    func body(content: Content) -> some View {
        content
            .opacity(appeared ? 1 : 0)
            .offset(y: appeared || reduceMotion ? 0 : 12)
            .onAppear {
                if reduceMotion {
                    appeared = true
                } else {
                    withAnimation(KagamiMotion.smooth.delay(delay)) {
                        appeared = true
                    }
                }
            }
    }
}

// MARK: - Shimmer Loading Effect

/// Shimmer effect modifier for loading states
struct ShimmerEffect: ViewModifier {
    @Environment(\.accessibilityReduceMotion) var reduceMotion
    @State private var phase: CGFloat = 0

    func body(content: Content) -> some View {
        if reduceMotion {
            content
                .opacity(0.5)
        } else {
            content
                .overlay(
                    GeometryReader { geometry in
                        LinearGradient(
                            colors: [
                                Color.white.opacity(0),
                                Color.white.opacity(0.15),
                                Color.white.opacity(0)
                            ],
                            startPoint: .leading,
                            endPoint: .trailing
                        )
                        .frame(width: geometry.size.width * 0.6)
                        .offset(x: -geometry.size.width * 0.3 + phase * geometry.size.width * 1.6)
                    }
                )
                .mask(content)
                .onAppear {
                    // Extended duration for natural shimmer rhythm
                    withAnimation(
                        Animation.linear(duration: DesignTokens.Motion.Duration.slowest)
                            .repeatForever(autoreverses: false)
                    ) {
                        phase = 1
                    }
                }
        }
    }
}

/// Shimmer placeholder for loading skeleton UIs
struct ShimmerPlaceholder: View {
    let width: CGFloat?
    let height: CGFloat

    init(width: CGFloat? = nil, height: CGFloat = KagamiSpacing.md) {
        self.width = width
        self.height = height
    }

    var body: some View {
        RoundedRectangle(cornerRadius: KagamiRadius.xs)
            .fill(Color.voidLight)
            .frame(width: width, height: height)
            .modifier(ShimmerEffect())
    }
}

/// Shimmer row placeholder for lists
struct ShimmerRow: View {
    var body: some View {
        HStack(spacing: KagamiSpacing.md) {
            // Leading icon placeholder
            RoundedRectangle(cornerRadius: KagamiRadius.sm)
                .fill(Color.voidLight)
                .frame(width: 44, height: 44)
                .modifier(ShimmerEffect())

            VStack(alignment: .leading, spacing: KagamiSpacing.xs) {
                // Title placeholder
                ShimmerPlaceholder(width: 120, height: 16)
                // Subtitle placeholder
                ShimmerPlaceholder(width: 80, height: 12)
            }

            Spacer()
        }
        .padding(.vertical, KagamiSpacing.sm)
    }
}

// MARK: - Reusable KagamiCard Component

/// A reusable card component with consistent styling
struct KagamiCard<Content: View>: View {
    let content: Content
    var accentColor: Color
    var isInteractive: Bool
    var onTap: (() -> Void)?

    init(
        accentColor: Color = .crystal,
        isInteractive: Bool = false,
        onTap: (() -> Void)? = nil,
        @ViewBuilder content: () -> Content
    ) {
        self.content = content()
        self.accentColor = accentColor
        self.isInteractive = isInteractive
        self.onTap = onTap
    }

    var body: some View {
        Group {
            if isInteractive, let onTap = onTap {
                Button(action: onTap) {
                    cardContent
                }
                .buttonStyle(.plain)
                .pressEffect()
                .minimumTouchTarget() // Ensure 44pt minimum for accessibility
            } else {
                cardContent
            }
        }
    }

    private var cardContent: some View {
        content
            .padding(KagamiSpacing.md)
            .background(Color.obsidian)
            .cornerRadius(KagamiRadius.md)
            .overlay(
                RoundedRectangle(cornerRadius: KagamiRadius.md)
                    .stroke(accentColor.opacity(0.1), lineWidth: 1)
            )
    }
}

/// Card variant with header
struct KagamiCardWithHeader<Content: View>: View {
    let title: String
    let subtitle: String?
    let icon: String?
    let accentColor: Color
    let content: Content

    init(
        title: String,
        subtitle: String? = nil,
        icon: String? = nil,
        accentColor: Color = .crystal,
        @ViewBuilder content: () -> Content
    ) {
        self.title = title
        self.subtitle = subtitle
        self.icon = icon
        self.accentColor = accentColor
        self.content = content()
    }

    var body: some View {
        VStack(alignment: .leading, spacing: KagamiSpacing.md) {
            // Header
            HStack(spacing: KagamiSpacing.sm) {
                if let icon = icon {
                    Text(icon)
                        .font(.title2)
                        .accessibilityHidden(true)
                }
                VStack(alignment: .leading, spacing: 2) {
                    Text(title)
                        .font(KagamiFont.headline())
                        .foregroundColor(.accessibleTextPrimary)
                    if let subtitle = subtitle {
                        Text(subtitle)
                            .font(KagamiFont.caption())
                            .foregroundColor(.accessibleTextSecondary)
                    }
                }
                Spacer()
            }

            // Content
            content
        }
        .padding(KagamiSpacing.md)
        .background(Color.obsidian)
        .cornerRadius(KagamiRadius.md)
        .overlay(
            RoundedRectangle(cornerRadius: KagamiRadius.md)
                .stroke(accentColor.opacity(0.1), lineWidth: 1)
        )
    }
}

// MARK: - View Extensions

// MARK: - Touch Target Enforcement

/// Ensures minimum touch target size for accessibility (WCAG 2.1 AA requires 44pt)
struct MinimumTouchTargetModifier: ViewModifier {
    let minSize: CGFloat

    init(minSize: CGFloat = KagamiLayout.minTouchTarget) {
        self.minSize = minSize
    }

    func body(content: Content) -> some View {
        content
            .frame(minWidth: minSize, minHeight: minSize)
            .contentShape(Rectangle()) // Expand hit area to full frame
    }
}

extension View {
    // Note: minimumTouchTarget is defined in AccessibilityModifiers.swift

    func pressEffect() -> some View {
        modifier(PressEffect())
    }

    func pulseEffect() -> some View {
        modifier(PulseEffect())
    }

    func glowEffect(color: Color = .crystal) -> some View {
        modifier(GlowEffect(color: color))
    }

    func slideUpEntrance(delay: Double = 0) -> some View {
        modifier(SlideUpEntrance(delay: delay))
    }

    /// Apply shimmer loading effect
    func shimmer() -> some View {
        modifier(ShimmerEffect())
    }

    func kagamiCard() -> some View {
        self
            .background(Color.obsidian)
            .cornerRadius(KagamiRadius.md)
            .overlay(
                RoundedRectangle(cornerRadius: KagamiRadius.md)
                    .stroke(Color.white.opacity(0.06), lineWidth: 1)
            )
    }

    // MARK: - Animation Extensions

    /// Apply fade in animation with natural timing
    func fibonacciFadeIn(delay: Double = 0, duration: Double = KagamiMotion.normal) -> some View {
        modifier(FibonacciFadeIn(delay: delay, duration: duration))
    }

    /// Apply scale bounce animation with natural timing
    func fibonacciScaleBounce(delay: Double = 0) -> some View {
        modifier(FibonacciScaleBounce(delay: delay))
    }

    /// Apply staggered entrance for list items
    func staggeredEntrance(index: Int) -> some View {
        modifier(StaggeredEntrance(index: index))
    }

    /// Apply breathing scale effect for ambient indicators
    func breathingEffect(minScale: CGFloat = 0.95, maxScale: CGFloat = 1.05) -> some View {
        modifier(BreathingEffect(minScale: minScale, maxScale: maxScale))
    }

    /// Apply easing curve transition
    func catastropheTransition(isActive: Bool, style: CatastropheTransition.CatastropheStyle) -> some View {
        modifier(CatastropheTransition(isActive: isActive, style: style))
    }

    /// Apply animation with style
    func fibonacciAnimation(_ style: KagamiMotion.AnimationStyle, duration: Double = KagamiMotion.normal) -> some View {
        self.animation(KagamiMotion.animation(style, duration: duration), value: UUID())
    }
}

// MARK: - Extensibility: Theme Override

/// Central theme controller for Kagami iOS design system.
///
/// ## Overview
/// `KagamiTheme` provides runtime theming capabilities while maintaining
/// design system consistency. Use it to customize accent colors, mode indicators,
/// animation intensity, and haptic feedback preferences.
///
/// ## Usage
///
/// ### App-Level Setup
/// Inject into environment at app root:
/// ```swift
/// @main
/// struct KagamiIOSApp: App {
///     @StateObject private var theme = KagamiTheme.shared
///
///     var body: some Scene {
///         WindowGroup {
///             ContentView()
///                 .environmentObject(theme)
///         }
///     }
/// }
/// ```
///
/// ### View-Level Access
/// Access theme in any view:
/// ```swift
/// struct MyView: View {
///     @EnvironmentObject var theme: KagamiTheme
///
///     var body: some View {
///         Circle()
///             .fill(theme.accentColor)
///     }
/// }
/// ```
///
/// ### Runtime Customization
/// Modify theme properties to update all observing views:
/// ```swift
/// theme.accentColor = .spark  // Changes accent throughout app
/// theme.animationScale = 0.5  // Reduces animation intensity
/// theme.hapticEnabled = false // Disables haptic feedback
/// ```
///
/// ## Properties
/// - `accentColor`: Primary accent color (default: `.crystal`)
/// - `modeAskColor`: Color for Ask mode (default: `.grove`)
/// - `modePlanColor`: Color for Plan mode (default: `.beacon`)
/// - `modeAgentColor`: Color for Agent mode (default: `.forge`)
/// - `animationScale`: Animation intensity multiplier (0 = none, 1 = normal, 2 = exaggerated)
/// - `hapticEnabled`: Whether haptic feedback is active
///
/// ## Mode Color Mapping
/// Each mode has a distinct color for visual differentiation:
/// - **Ask** → Green tint — Research, curiosity
/// - **Plan** → Amber tint — Planning, foresight
/// - **Agent** → Orange tint — Implementation, execution
///
class KagamiTheme: ObservableObject {
    /// Shared singleton instance for app-wide theming
    static let shared = KagamiTheme()

    /// Primary accent color used throughout the app
    @Published var accentColor: Color = .crystal

    /// Color for Ask mode (research/queries)
    @Published var modeAskColor: Color = .grove

    /// Color for Plan mode (planning/scheduling)
    @Published var modePlanColor: Color = .beacon

    /// Color for Agent mode (autonomous actions)
    @Published var modeAgentColor: Color = .forge

    /// Animation intensity multiplier
    /// - 0: No animations (respects reduce motion)
    /// - 1: Standard animations
    /// - 2: Exaggerated animations (playful mode)
    @Published var animationScale: Double = 1.0

    /// Whether haptic feedback is enabled
    /// Set to false for silent operation or battery saving
    @Published var hapticEnabled: Bool = true

    /// Returns the appropriate color for a given mode
    /// - Parameter mode: The current Kagami mode
    /// - Returns: The color associated with that mode
    func color(for mode: KagamiMode) -> Color {
        switch mode {
        case .ask: return modeAskColor
        case .plan: return modePlanColor
        case .agent: return modeAgentColor
        }
    }
}

// Note: KagamiMode is defined in ModelSelectorView.swift

// MARK: - Contrast Ratio Verification

/// WCAG 2.1 contrast ratio utilities
struct ContrastRatio {

    /// Calculate luminance for a color (sRGB)
    static func luminance(red: CGFloat, green: CGFloat, blue: CGFloat) -> CGFloat {
        func adjust(_ value: CGFloat) -> CGFloat {
            value <= 0.03928 ? value / 12.92 : pow((value + 0.055) / 1.055, 2.4)
        }
        return 0.2126 * adjust(red) + 0.7152 * adjust(green) + 0.0722 * adjust(blue)
    }

    /// Calculate contrast ratio between two luminances
    static func ratio(l1: CGFloat, l2: CGFloat) -> CGFloat {
        let lighter = max(l1, l2)
        let darker = min(l1, l2)
        return (lighter + 0.05) / (darker + 0.05)
    }

    /// WCAG AA minimum for normal text
    static let wcagAANormal: CGFloat = 4.5

    /// WCAG AA minimum for large text (18pt+ or 14pt bold)
    static let wcagAALarge: CGFloat = 3.0

    /// WCAG AAA minimum for normal text
    static let wcagAAANormal: CGFloat = 7.0

    /// WCAG AAA minimum for large text
    static let wcagAAALarge: CGFloat = 4.5
}

/// Extension to verify Color contrast
extension Color {
    /// Check if this color has sufficient contrast against a background
    /// - Parameters:
    ///   - background: The background color (default: .void - the primary background)
    ///   - minimumRatio: Required contrast ratio (default: WCAG AA normal text = 4.5)
    /// - Returns: True if contrast meets or exceeds minimum ratio
    func meetsContrastRequirement(against background: Color = .void, minimumRatio: CGFloat = ContrastRatio.wcagAANormal) -> Bool {
        // Note: This requires UIColor conversion which loses precision
        // In production, store exact RGB values in design tokens
        guard let fgComponents = UIColor(self).cgColor.components,
              let bgComponents = UIColor(background).cgColor.components else {
            return false
        }

        let fgLuminance = ContrastRatio.luminance(
            red: fgComponents[0],
            green: fgComponents[1],
            blue: fgComponents[2]
        )
        let bgLuminance = ContrastRatio.luminance(
            red: bgComponents[0],
            green: bgComponents[1],
            blue: bgComponents[2]
        )

        let ratio = ContrastRatio.ratio(l1: fgLuminance, l2: bgLuminance)
        return ratio >= minimumRatio
    }

    /// Get the contrast ratio against a background color
    func contrastRatio(against background: Color) -> CGFloat? {
        guard let fgComponents = UIColor(self).cgColor.components,
              let bgComponents = UIColor(background).cgColor.components else {
            return nil
        }

        let fgLuminance = ContrastRatio.luminance(
            red: fgComponents[0],
            green: fgComponents[1],
            blue: fgComponents[2]
        )
        let bgLuminance = ContrastRatio.luminance(
            red: bgComponents[0],
            green: bgComponents[1],
            blue: bgComponents[2]
        )

        return ContrastRatio.ratio(l1: fgLuminance, l2: bgLuminance)
    }
}

/// Debug view modifier to check contrast in previews
struct ContrastDebugModifier: ViewModifier {
    let foregroundColor: Color
    let backgroundColor: Color

    func body(content: Content) -> some View {
        #if DEBUG
        content.overlay(alignment: .topTrailing) {
            if let ratio = foregroundColor.contrastRatio(against: backgroundColor) {
                let passes = ratio >= ContrastRatio.wcagAANormal
                Text(String(format: "%.1f:1", ratio))
                    .font(.caption2)
                    .padding(2)
                    .background(passes ? Color.safetyOk.opacity(0.8) : Color.safetyViolation.opacity(0.8))
                    .foregroundColor(.void)
                    .cornerRadius(4)
                    .padding(2)
            }
        }
        #else
        content
        #endif
    }
}

extension View {
    /// Debug modifier to show contrast ratio overlay
    func debugContrast(foreground: Color, background: Color) -> some View {
        modifier(ContrastDebugModifier(foregroundColor: foreground, backgroundColor: background))
    }
}

// MARK: - Preview

#Preview("Design Tokens") {
    ScrollView {
        VStack(spacing: 24) {
            // Colors
            HStack {
                ForEach([Color.spark, .forge, .flow, .nexus, .beacon, .grove, .crystal], id: \.self) { color in
                    Circle()
                        .fill(color)
                        .frame(width: 40, height: 40)
                }
            }

            // Animated Button
            Button("Press Me") {}
                .padding()
                .background(Color.crystal)
                .foregroundColor(.void)
                .cornerRadius(KagamiRadius.sm)
                .pressEffect()

            // Pulsing Status
            Circle()
                .fill(Color.statusSuccess)
                .frame(width: 12, height: 12)
                .pulseEffect()

            // Glowing Card
            Text("Glowing Card")
                .padding()
                .kagamiCard()
                .glowEffect()

            // Touch Target Demo
            Button("Touch Target (44pt min)") {}
                .minimumTouchTarget()
                .background(Color.forge.opacity(0.3))
                .cornerRadius(KagamiRadius.sm)
        }
        .padding()
    }
    .background(Color.void)
    .preferredColorScheme(.dark)
    .environment(\.sizeCategory, .extraLarge)
}
