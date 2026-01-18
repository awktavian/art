//
// Motion.swift — Kagami Design System
//
// Animation timing and easing definitions based on Fibonacci sequence
// and catastrophe theory-inspired curves.
// Source: packages/kagami_design_tokens/tokens.json
//
// Colony: Crystal (e7) — Verification & Polish
//

import SwiftUI

// MARK: - Duration Tokens (Fibonacci-based)

/// Animation durations based on Fibonacci ratios for natural timing.
/// Values in seconds, derived from golden ratio relationships.
public enum KagamiDuration {
    /// Instant response (89ms) - micro-interactions
    public static let instant: Double = 0.089

    /// Fast animation (144ms) - button feedback
    public static let fast: Double = 0.144

    /// Normal animation (233ms) - standard transitions
    public static let normal: Double = 0.233

    /// Slow animation (377ms) - modal presentations
    public static let slow: Double = 0.377

    /// Slower animation (610ms) - complex transitions
    public static let slower: Double = 0.610

    /// Slowest animation (987ms) - dramatic effects
    public static let slowest: Double = 0.987
}

// MARK: - Easing Curves (Catastrophe-Inspired)

/// Easing animations based on catastrophe theory manifolds.
/// Each curve corresponds to a different catastrophe type.
public enum KagamiEasing {
    /// Fold (A2) - Simple transition with abrupt start
    /// Use for binary state changes
    public static let fold = Animation.timingCurve(0.7, 0, 0.3, 1, duration: KagamiDuration.normal)

    /// Cusp (A3) - Smooth deceleration
    /// Use for standard UI transitions
    public static let cusp = Animation.timingCurve(0.4, 0, 0.2, 1, duration: KagamiDuration.normal)

    /// Swallowtail (A4) - Overshooting with settling
    /// Use for spring-like effects
    public static let swallowtail = Animation.timingCurve(0.34, 1.2, 0.64, 1, duration: KagamiDuration.slow)

    /// Butterfly (A5) - Complex oscillation
    /// Use for attention-grabbing animations
    public static let butterfly = Animation.timingCurve(0.68, -0.2, 0.32, 1.2, duration: KagamiDuration.slow)

    /// Smooth - Standard ease-out
    /// Use for general purpose animations
    public static let smooth = Animation.timingCurve(0.16, 1, 0.3, 1, duration: KagamiDuration.normal)

    /// Linear - No easing
    /// Use for continuous animations
    public static let linear = Animation.linear(duration: KagamiDuration.normal)
}

// MARK: - Spring Configurations

/// Spring animation configurations for natural motion
public enum KagamiSpring {
    /// Micro spring - very quick, subtle (89ms response)
    public static let micro = Animation.spring(response: KagamiDuration.instant, dampingFraction: 0.8)

    /// Fast spring - quick feedback (144ms response)
    public static let fast = Animation.spring(response: KagamiDuration.fast, dampingFraction: 0.75)

    /// Default spring - standard interactions (233ms response)
    public static let `default` = Animation.spring(response: KagamiDuration.normal, dampingFraction: 0.7)

    /// Soft spring - gentle animations (377ms response)
    public static let soft = Animation.spring(response: KagamiDuration.slow, dampingFraction: 0.65)

    /// Bouncy spring - playful animations
    public static let bouncy = Animation.spring(response: KagamiDuration.normal, dampingFraction: 0.5)
}

// MARK: - Motion System

/// Unified motion system providing access to all animation tokens
public struct KagamiMotion {
    // MARK: Durations (Re-exported for convenience)

    /// Instant response (89ms)
    public static let instant: Double = KagamiDuration.instant

    /// Fast animation (144ms)
    public static let fast: Double = KagamiDuration.fast

    /// Normal animation (233ms)
    public static let normal: Double = KagamiDuration.normal

    /// Slow animation (377ms)
    public static let slow: Double = KagamiDuration.slow

    /// Slower animation (610ms)
    public static let slower: Double = KagamiDuration.slower

    /// Slowest animation (987ms)
    public static let slowest: Double = KagamiDuration.slowest

    // MARK: Spring Configs (Re-exported for convenience)

    /// Micro spring for subtle feedback
    public static let microSpring = KagamiSpring.micro

    /// Fast spring for button feedback
    public static let fastSpring = KagamiSpring.fast

    /// Default spring for standard interactions
    public static let defaultSpring = KagamiSpring.default

    /// Soft spring for gentle animations
    public static let softSpring = KagamiSpring.soft

    // MARK: Catastrophe Easings (Re-exported for convenience)

    /// Fold easing (A2)
    public static let fold = KagamiEasing.fold

    /// Cusp easing (A3)
    public static let cusp = KagamiEasing.cusp

    /// Swallowtail easing (A4)
    public static let swallowtail = KagamiEasing.swallowtail

    /// Butterfly easing (A5)
    public static let butterfly = KagamiEasing.butterfly

    /// Smooth easing (default)
    public static let smooth = KagamiEasing.smooth
}

// MARK: - Watch Motion (Optimized for watchOS)

/// Motion tokens optimized for Apple Watch's shorter attention span
public struct WatchMotion {
    /// Instant response (100ms)
    public static let instant: Double = 0.1

    /// Fast animation (150ms)
    public static let fast: Double = 0.15

    /// Normal animation (250ms)
    public static let normal: Double = 0.25

    /// Slow animation (350ms)
    public static let slow: Double = 0.35

    /// Micro spring - very snappy
    public static let micro = Animation.spring(response: 0.2, dampingFraction: 0.8)

    /// Quick spring - responsive
    public static let quick = Animation.spring(response: 0.25, dampingFraction: 0.75)

    /// Smooth spring - comfortable
    public static let smooth = Animation.spring(response: 0.3, dampingFraction: 0.7)
}

// MARK: - Spatial Motion (Optimized for visionOS)

/// Motion tokens for spatial/immersive experiences
public struct SpatialMotion {
    /// Instant response (150ms) - longer for spatial comfort
    public static let instant: Double = 0.15

    /// Fast animation (250ms)
    public static let fast: Double = 0.25

    /// Normal animation (400ms) - more cinematic
    public static let normal: Double = 0.4

    /// Slow animation (600ms)
    public static let slow: Double = 0.6

    /// Cinematic animation (1000ms)
    public static let cinematic: Double = 1.0

    /// Micro spring - spatial
    public static let micro = Animation.spring(response: 0.25, dampingFraction: 0.85)

    /// Soft spring - spatial
    public static let soft = Animation.spring(response: 0.4, dampingFraction: 0.75)

    /// Cinematic spring - immersive
    public static let cinematicSpring = Animation.spring(response: 0.6, dampingFraction: 0.7)

    /// Float spring - ambient motion
    public static let float = Animation.spring(response: 0.8, dampingFraction: 0.65)
}

// MARK: - TV Motion (Optimized for tvOS 10-foot interface)

/// Motion tokens optimized for Apple TV's 10-foot experience
/// Timing is slightly longer for cinematic feel, easings are more dramatic
public struct TvMotion {
    // MARK: Durations (Fibonacci-based, cinematic feel)

    /// Instant response (144ms) - focus feedback
    public static let instant: Double = 0.144

    /// Fast animation (233ms) - button presses
    public static let fast: Double = 0.233

    /// Normal animation (377ms) - standard transitions
    public static let normal: Double = 0.377

    /// Slow animation (610ms) - scene changes
    public static let slow: Double = 0.610

    /// Slower animation (987ms) - dramatic reveals
    public static let slower: Double = 0.987

    /// Slowest animation (1597ms) - cinematic effects
    public static let slowest: Double = 1.597

    // MARK: Springs

    /// Focus spring - for focus ring animation
    public static let focus = Animation.spring(response: 0.233, dampingFraction: 0.8)

    /// Card spring - for card scale animation
    public static let card = Animation.spring(response: 0.233, dampingFraction: 0.75)

    /// Button spring - for press feedback
    public static let button = Animation.spring(response: 0.144, dampingFraction: 0.85)

    /// Cinematic spring - for dramatic effects
    public static let cinematic = Animation.spring(response: 0.610, dampingFraction: 0.7)

    // MARK: Catastrophe Easings for TV

    /// Swallowtail easing for scene transitions
    public static let sceneTrans = Animation.timingCurve(0.34, 1.2, 0.64, 1, duration: normal)

    /// Butterfly easing for attention-grabbing elements
    public static let attention = Animation.timingCurve(0.68, -0.2, 0.32, 1.2, duration: slow)

    /// Cusp easing for standard UI
    public static let standard = Animation.timingCurve(0.4, 0, 0.2, 1, duration: normal)
}

// MARK: - Reduced Motion Support

extension View {
    /// Applies animation only when reduced motion is not enabled
    public func animationIfAllowed<V: Equatable>(_ animation: Animation?, value: V) -> some View {
        modifier(ReducedMotionAnimationModifier(animation: animation, value: value))
    }
}

/// Modifier that respects reduced motion preferences
private struct ReducedMotionAnimationModifier<V: Equatable>: ViewModifier {
    @Environment(\.accessibilityReduceMotion) private var reduceMotion
    let animation: Animation?
    let value: V

    func body(content: Content) -> some View {
        content
            .animation(reduceMotion ? nil : animation, value: value)
    }
}
