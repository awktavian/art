//
// PrismEffects.swift — Kagami Glass Effects for iOS
//
// Apple glassmorphism with spectral shimmer effects.
// Creates rainbow effects that emerge from glass surfaces like light through a prism.
// Each element gets a unique shimmer phase based on its ID.
//

import SwiftUI
import UIKit
import KagamiDesign

// MARK: - Spectral Colors

/// The seven spectral colors following optical physics wavelength ordering
enum SpectralColor: Int, CaseIterable {
    case spark = 0   // 620nm (Red) — Arrives first
    case forge = 1   // 590nm (Orange)
    case flow = 2    // 570nm (Yellow)
    case nexus = 3   // 510nm (Green)
    case beacon = 4  // 475nm (Cyan)
    case grove = 5   // 445nm (Blue)
    case crystal = 6 // 400nm (Violet) — Arrives last

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

    /// Wavelength in nanometers (for documentation)
    var wavelength: Int {
        switch self {
        case .spark: return 620
        case .forge: return 590
        case .flow: return 570
        case .nexus: return 510
        case .beacon: return 475
        case .grove: return 445
        case .crystal: return 400
        }
    }

    /// Dispersion delay in milliseconds (8ms between adjacent colors)
    /// Red arrives first, violet arrives last
    var dispersionDelay: Double {
        Double(rawValue) * 0.008 // 8ms per step
    }

    /// Get color at a normalized phase (0-1)
    static func at(phase: Double) -> Color {
        let idx = Int((phase * 7).truncatingRemainder(dividingBy: 7))
        return SpectralColor(rawValue: abs(idx) % 7)?.color ?? .crystal
    }
}

// MARK: - Color Line Definitions

/// Seven color line groupings for gradient and visual composition effects
enum FanoLine: Int, CaseIterable {
    case line123 = 0  // Spark-Forge-Flow (warm spectrum)
    case line145 = 1  // Spark-Nexus-Beacon (red-green-cyan diagonal)
    case line176 = 2  // Spark-Crystal-Grove (red-violet-blue harmonic)
    case line246 = 3  // Forge-Nexus-Grove (orange-green-blue triadic)
    case line257 = 4  // Forge-Beacon-Crystal (warm-to-cool transition)
    case line347 = 5  // Flow-Nexus-Crystal (yellow-green-violet path)
    case line365 = 6  // Flow-Grove-Beacon (yellow-blue-cyan arc)

    /// The three colors on this line
    var colonies: (SpectralColor, SpectralColor, SpectralColor) {
        switch self {
        case .line123: return (.spark, .forge, .flow)
        case .line145: return (.spark, .nexus, .beacon)
        case .line176: return (.spark, .crystal, .grove)
        case .line246: return (.forge, .nexus, .grove)
        case .line257: return (.forge, .beacon, .crystal)
        case .line347: return (.flow, .nexus, .crystal)
        case .line365: return (.flow, .grove, .beacon)
        }
    }

    /// The gradient for this Fano line
    var gradient: LinearGradient {
        let (c1, c2, c3) = colonies
        return LinearGradient(
            colors: [c1.color, c2.color, c3.color],
            startPoint: .topLeading,
            endPoint: .bottomTrailing
        )
    }

    /// Angular gradient for circular effects
    var angularGradient: AngularGradient {
        let (c1, c2, c3) = colonies
        return AngularGradient(
            colors: [c1.color, c2.color, c3.color, c1.color],
            center: .center
        )
    }

    /// Find the color line containing two given colors
    static func containing(_ a: SpectralColor, _ b: SpectralColor) -> FanoLine? {
        for line in allCases {
            let (c1, c2, c3) = line.colonies
            let cols = [c1, c2, c3]
            if cols.contains(a) && cols.contains(b) {
                return line
            }
        }
        return nil
    }

    /// Get the third color given two colors on the line
    func product(of a: SpectralColor, and b: SpectralColor) -> SpectralColor? {
        let (c1, c2, c3) = colonies
        let cols = [c1, c2, c3]
        guard cols.contains(a) && cols.contains(b) else { return nil }
        return cols.first { $0 != a && $0 != b }
    }
}

// MARK: - Discovery State

/// Tracks interaction state for progressive reveal of effects
enum DiscoveryState: Comparable {
    case rest         // Default — 0% opacity
    case glance       // Hover < 150ms — 10% opacity, subtle shimmer
    case interest     // Hover 150-500ms — 25% opacity, color cycle begins
    case focus        // Hover > 500ms — 40% opacity, full spectral effect
    case engage       // Click/tap — 60% flash then settle to 30%

    var opacity: Double {
        switch self {
        case .rest: return 0
        case .glance: return 0.10
        case .interest: return 0.25
        case .focus: return 0.40
        case .engage: return 0.60
        }
    }

    var settledOpacity: Double {
        self == .engage ? 0.30 : opacity
    }
}

// MARK: - Dispersion Timing

/// Physics-accurate dispersion timing for chromatic effects
struct DispersionTiming {
    /// Delay offsets for each spectral color (8ms between adjacent)
    static let delays: [SpectralColor: Double] = [
        .spark: 0,      // Red arrives first
        .forge: 0.008,  // 8ms
        .flow: 0.016,   // 16ms
        .nexus: 0.024,  // 24ms
        .beacon: 0.032, // 32ms
        .grove: 0.040,  // 40ms
        .crystal: 0.048 // Violet arrives last
    ]

    /// Total sweep duration
    static let totalSweep: Double = 0.048

    /// Get animation with physics-accurate delay for a color
    static func animation(for color: SpectralColor, baseDuration: Double = 0.377) -> Animation {
        let delay = delays[color] ?? 0
        return Animation.easeOut(duration: baseDuration).delay(delay)
    }
}

// MARK: - Spectral Shimmer View

/// Animated rainbow shimmer overlay using Canvas
struct SpectralShimmer: View {
    let phase: Double // 0-1, determines starting point in spectrum
    let intensity: Double // 0-1, controls opacity

    @Environment(\.accessibilityReduceMotion) private var reduceMotion

    init(phase: Double, intensity: Double = 0.3) {
        self.phase = phase
        self.intensity = intensity
    }

    var body: some View {
        TimelineView(.animation(minimumInterval: 1/30, paused: reduceMotion)) { timeline in
            Canvas { context, size in
                let time = timeline.date.timeIntervalSinceReferenceDate
                let progress = reduceMotion ? phase : ((time / 8) + phase).truncatingRemainder(dividingBy: 1)

                // Create gradient that moves through spectrum
                let colors: [Color] = (0..<7).map { i in
                    let p = (progress + Double(i) / 7).truncatingRemainder(dividingBy: 1)
                    return SpectralColor.at(phase: p)
                }

                let gradient = Gradient(colors: colors + [colors[0]])

                // Draw as a diagonal sweep
                let start = CGPoint(x: 0, y: 0)
                let end = CGPoint(x: size.width, y: size.height)

                context.fill(
                    Path(CGRect(origin: .zero, size: size)),
                    with: .linearGradient(
                        gradient,
                        startPoint: start,
                        endPoint: end
                    )
                )
            }
        }
        .opacity(intensity)
        .blendMode(.overlay)
    }
}

// MARK: - Spectral Border

/// Animated rainbow border effect
struct SpectralBorder: ViewModifier {
    let lineWidth: CGFloat
    let cornerRadius: CGFloat
    let animated: Bool

    @State private var phase: Double = 0
    @Environment(\.accessibilityReduceMotion) private var reduceMotion

    init(lineWidth: CGFloat = 2, cornerRadius: CGFloat = 12, animated: Bool = true) {
        self.lineWidth = lineWidth
        self.cornerRadius = cornerRadius
        self.animated = animated
    }

    func body(content: Content) -> some View {
        content
            .overlay(
                RoundedRectangle(cornerRadius: cornerRadius)
                    .strokeBorder(
                        AngularGradient(
                            gradient: spectralGradient(at: phase),
                            center: .center,
                            startAngle: .degrees(phase * 360),
                            endAngle: .degrees(phase * 360 + 360)
                        ),
                        lineWidth: lineWidth
                    )
            )
            .onAppear {
                guard animated && !reduceMotion else { return }
                withAnimation(.linear(duration: 6).repeatForever(autoreverses: false)) {
                    phase = 1
                }
            }
    }

    private func spectralGradient(at phase: Double) -> Gradient {
        let colors: [Color] = SpectralColor.allCases.map { $0.color }
        return Gradient(colors: colors + [colors[0]])
    }
}

// MARK: - Spectral Discovery

/// ViewModifier that tracks touch duration and intensifies effects progressively
/// Effects are discovered, not forced — rewarding sustained attention
struct SpectralDiscovery: ViewModifier {
    @State private var discoveryState: DiscoveryState = .rest
    @State private var touchStartTime: Date?
    @State private var timer: Timer?
    @State private var isEngaged = false
    @Environment(\.accessibilityReduceMotion) private var reduceMotion

    /// Thresholds for state transitions
    private let glanceThreshold: TimeInterval = 0.150  // 150ms
    private let interestThreshold: TimeInterval = 0.500 // 500ms

    /// Haptic feedback
    private let impactLight = UIImpactFeedbackGenerator(style: .light)
    private let impactMedium = UIImpactFeedbackGenerator(style: .medium)

    func body(content: Content) -> some View {
        content
            .overlay(
                SpectralShimmer(phase: 0, intensity: discoveryState.opacity)
                    .allowsHitTesting(false)
            )
            .animation(reduceMotion ? nil : .easeInOut(duration: 0.233), value: discoveryState)
            .simultaneousGesture(
                DragGesture(minimumDistance: 0)
                    .onChanged { _ in
                        if touchStartTime == nil {
                            touchStartTime = Date()
                            startDiscoveryTimer()
                        }
                    }
                    .onEnded { _ in
                        endInteraction()
                    }
            )
            .onHover { hovering in
                if hovering {
                    touchStartTime = Date()
                    startDiscoveryTimer()
                } else {
                    endInteraction()
                }
            }
    }

    private func startDiscoveryTimer() {
        timer?.invalidate()
        discoveryState = .glance

        timer = Timer.scheduledTimer(withTimeInterval: 0.05, repeats: true) { _ in
            guard let start = touchStartTime else { return }
            let elapsed = Date().timeIntervalSince(start)

            let newState: DiscoveryState
            if elapsed >= interestThreshold {
                newState = .focus
            } else if elapsed >= glanceThreshold {
                newState = .interest
            } else {
                newState = .glance
            }

            if newState != discoveryState {
                // Haptic feedback on state transition
                if !reduceMotion {
                    switch newState {
                    case .interest:
                        impactLight.impactOccurred()
                    case .focus:
                        impactMedium.impactOccurred()
                    default:
                        break
                    }
                }
                discoveryState = newState
            }
        }
    }

    private func endInteraction() {
        timer?.invalidate()
        timer = nil

        // Flash on engage if we reached focus
        if discoveryState >= .focus && !reduceMotion {
            discoveryState = .engage
            impactMedium.impactOccurred()

            // Settle back down
            DispatchQueue.main.asyncAfter(deadline: .now() + 0.233) {
                withAnimation(.easeOut(duration: 0.377)) {
                    discoveryState = .rest
                }
            }
        } else {
            discoveryState = .rest
        }

        touchStartTime = nil
    }
}

// MARK: - Color Line Glow

/// Shows the complementary color when two colors interact
/// Reveals the third color when hovering between two colors on a line
struct FanoLineGlow: View {
    let colony1: SpectralColor
    let colony2: SpectralColor
    let isActive: Bool

    @State private var pulsePhase: Double = 0
    @Environment(\.accessibilityReduceMotion) private var reduceMotion

    private var fanoLine: FanoLine? {
        FanoLine.containing(colony1, colony2)
    }

    private var productColony: SpectralColor? {
        fanoLine?.product(of: colony1, and: colony2)
    }

    var body: some View {
        Group {
            if let product = productColony, isActive {
                ZStack {
                    // Background glow
                    RoundedRectangle(cornerRadius: 12)
                        .fill(
                            RadialGradient(
                                colors: [
                                    product.color.opacity(0.4),
                                    product.color.opacity(0.2),
                                    .clear
                                ],
                                center: .center,
                                startRadius: 0,
                                endRadius: 100
                            )
                        )
                        .blur(radius: 20)

                    // Pulsing inner glow
                    Circle()
                        .fill(product.color)
                        .frame(width: 20, height: 20)
                        .scaleEffect(reduceMotion ? 1 : (1 + pulsePhase * 0.3))
                        .opacity(reduceMotion ? 0.6 : (0.6 - pulsePhase * 0.3))
                        .blur(radius: 8)
                }
                .onAppear {
                    guard !reduceMotion else { return }
                    withAnimation(.easeInOut(duration: 1.5).repeatForever(autoreverses: true)) {
                        pulsePhase = 1
                    }
                    // Haptic on reveal
                    UIImpactFeedbackGenerator(style: .light).impactOccurred()
                }
            }
        }
        .animation(.easeInOut(duration: 0.377), value: isActive)
    }
}

/// ViewModifier version for easier application
struct FanoLineGlowModifier: ViewModifier {
    let colony1: SpectralColor
    let colony2: SpectralColor
    @Binding var isActive: Bool

    func body(content: Content) -> some View {
        content
            .background(
                FanoLineGlow(colony1: colony1, colony2: colony2, isActive: isActive)
            )
    }
}

// MARK: - Chromatic Pulse

/// Success/completion feedback animation with spectral wave
struct ChromaticPulse: ViewModifier {
    @Binding var isTriggered: Bool
    let color: Color

    @State private var pulseOpacity: Double = 0
    @State private var pulseScale: CGFloat = 1
    @State private var hueRotation: Double = 0
    @Environment(\.accessibilityReduceMotion) private var reduceMotion

    /// Haptic feedback
    private let successHaptic = UINotificationFeedbackGenerator()

    func body(content: Content) -> some View {
        content
            .overlay(
                RoundedRectangle(cornerRadius: 12)
                    .fill(color)
                    .hueRotation(.degrees(hueRotation))
                    .opacity(pulseOpacity)
                    .scaleEffect(pulseScale)
                    .allowsHitTesting(false)
            )
            .onChange(of: isTriggered) { _, triggered in
                if triggered {
                    triggerPulse()
                }
            }
    }

    private func triggerPulse() {
        guard !reduceMotion else {
            // Simple opacity flash for reduced motion
            pulseOpacity = 0.3
            DispatchQueue.main.asyncAfter(deadline: .now() + 0.233) {
                pulseOpacity = 0
                isTriggered = false
            }
            successHaptic.notificationOccurred(.success)
            return
        }

        // Reset state
        pulseOpacity = 0.5
        pulseScale = 1
        hueRotation = 0

        // Haptic
        successHaptic.notificationOccurred(.success)

        // Animate the pulse
        withAnimation(.easeOut(duration: 0.610)) {
            pulseOpacity = 0
            pulseScale = 1.1
            hueRotation = 30
        }

        // Reset trigger after animation
        DispatchQueue.main.asyncAfter(deadline: .now() + 0.610) {
            isTriggered = false
        }
    }
}

// MARK: - Chromatic Edge (Dispersion Effect)

/// Creates chromatic aberration at edges — red on warm side, violet on cool side
struct ChromaticEdge: ViewModifier {
    let dispersion: CGFloat
    let refraction: CGFloat
    let isActive: Bool

    @Environment(\.accessibilityReduceMotion) private var reduceMotion

    init(dispersion: CGFloat = 3, refraction: CGFloat = 1.0, isActive: Bool = true) {
        self.dispersion = dispersion
        self.refraction = refraction
        self.isActive = isActive
    }

    func body(content: Content) -> some View {
        content
            .background(
                ZStack {
                    // Red-shifted edge (warm side — light arrives first)
                    warmEdge

                    // Blue-shifted edge (cool side — light arrives last)
                    coolEdge
                }
                .opacity(isActive ? refraction : 0)
                .animation(reduceMotion ? nil : .easeInOut(duration: 0.377), value: isActive)
            )
    }

    @ViewBuilder
    private var warmEdge: some View {
        RoundedRectangle(cornerRadius: 24)
            .fill(
                LinearGradient(
                    colors: [
                        Color.spark.opacity(0.25),   // e1 Red
                        Color.forge.opacity(0.18),   // e2 Orange
                        Color.flow.opacity(0.12),    // e3 Yellow
                        .clear
                    ],
                    startPoint: .topLeading,
                    endPoint: .center
                )
            )
            .blur(radius: 8)
            .offset(x: -dispersion, y: -dispersion)
    }

    @ViewBuilder
    private var coolEdge: some View {
        RoundedRectangle(cornerRadius: 24)
            .fill(
                LinearGradient(
                    colors: [
                        Color.crystal.opacity(0.25), // e7 Violet
                        Color.grove.opacity(0.18),   // e6 Blue
                        Color.beacon.opacity(0.12),  // e5 Cyan
                        .clear
                    ],
                    startPoint: .bottomTrailing,
                    endPoint: .center
                )
            )
            .blur(radius: 8)
            .offset(x: dispersion, y: dispersion)
    }
}

// MARK: - Prism Catch

/// Brief spectral flash when cursor/touch crosses a corner
struct PrismCatch: View {
    let isActive: Bool
    let position: UnitPoint

    @State private var flashOpacity: Double = 0
    @Environment(\.accessibilityReduceMotion) private var reduceMotion

    var body: some View {
        Circle()
            .fill(
                AngularGradient(
                    colors: SpectralColor.allCases.map { $0.color } + [SpectralColor.spark.color],
                    center: .center
                )
            )
            .frame(width: 40, height: 40)
            .blur(radius: 8)
            .opacity(flashOpacity)
            .position(x: position.x * 100, y: position.y * 100)
            .onChange(of: isActive) { _, active in
                guard active, !reduceMotion else { return }
                flashOpacity = 0.4
                withAnimation(.easeOut(duration: 0.233)) {
                    flashOpacity = 0
                }
                UIImpactFeedbackGenerator(style: .soft).impactOccurred()
            }
    }
}

// MARK: - Caustic Background

/// Animated light pattern background (like light through water)
/// Each layer traces a Fano line direction
struct CausticBackground: View {
    @State private var phase1: Double = 0
    @State private var phase2: Double = 0
    @State private var phase3: Double = 0
    @Environment(\.accessibilityReduceMotion) private var reduceMotion

    var body: some View {
        GeometryReader { geo in
            ZStack {
                // Line 123: Warm spectrum arc (Spark-Forge-Flow)
                causticLayer(
                    colors: [.spark.opacity(0.08), .forge.opacity(0.08)],
                    offset: CGSize(width: cos(phase1 * .pi * 2) * 20, height: sin(phase1 * .pi * 2) * 15),
                    scale: 1 + sin(phase1 * .pi) * 0.05
                )

                // Line 145: Red-cyan diagonal (Spark-Nexus-Beacon)
                causticLayer(
                    colors: [.nexus.opacity(0.08), .beacon.opacity(0.08)],
                    offset: CGSize(width: sin(phase2 * .pi * 2) * 15, height: cos(phase2 * .pi * 2) * 20),
                    scale: 1 + cos(phase2 * .pi) * 0.03
                )

                // Line 176: Red-violet harmonic (Spark-Crystal-Grove)
                causticLayer(
                    colors: [.grove.opacity(0.08), .crystal.opacity(0.08)],
                    offset: CGSize(width: cos(phase3 * .pi * 2) * 18, height: sin(phase3 * .pi * 2) * 12),
                    scale: 1 + sin(phase3 * .pi) * 0.04
                )
            }
        }
        .onAppear {
            guard !reduceMotion else { return }
            // Progressive timing: 21s, 34s, 55s
            // This creates organic phase relationships that never quite sync,
            // producing ever-evolving light patterns (like actual caustics)
            withAnimation(.linear(duration: 21).repeatForever(autoreverses: false)) {
                phase1 = 1
            }
            withAnimation(.linear(duration: 34).repeatForever(autoreverses: false).delay(8)) {
                phase2 = 1
            }
            withAnimation(.linear(duration: 55).repeatForever(autoreverses: false).delay(3)) {
                phase3 = 1
            }
        }
    }

    @ViewBuilder
    private func causticLayer(colors: [Color], offset: CGSize, scale: CGFloat) -> some View {
        if reduceMotion {
            // Static version
            EllipticalGradient(colors: colors, center: .center, startRadiusFraction: 0, endRadiusFraction: 0.7)
                .opacity(0.5)
        } else {
            EllipticalGradient(colors: colors, center: .center, startRadiusFraction: 0, endRadiusFraction: 0.7)
                .offset(offset)
                .scaleEffect(scale)
        }
    }
}

// MARK: - Shimmer Text

/// Text with animated rainbow shimmer
struct ShimmerText: View {
    let text: String
    let font: Font
    let animated: Bool

    @State private var phase: Double = 0
    @Environment(\.accessibilityReduceMotion) private var reduceMotion

    init(_ text: String, font: Font = .body, animated: Bool = true) {
        self.text = text
        self.font = font
        self.animated = animated
    }

    var body: some View {
        Text(text)
            .font(font)
            .foregroundStyle(
                LinearGradient(
                    colors: shimmerColors(at: phase),
                    startPoint: .leading,
                    endPoint: .trailing
                )
            )
            .onAppear {
                guard animated && !reduceMotion else { return }
                withAnimation(.linear(duration: 8).repeatForever(autoreverses: false)) {
                    phase = 1
                }
            }
    }

    private func shimmerColors(at phase: Double) -> [Color] {
        let base: [Color] = SpectralColor.allCases.map { $0.color }
        let shift = Int(phase * 7) % 7
        return Array(base[shift...]) + Array(base[..<shift]) + [base[shift]]
    }
}

// MARK: - Glass Card (Glassmorphism + Spectral Shimmer)

/// Card with glassmorphism base and spectral shimmer on hover/active
struct PrismCard<Content: View>: View {
    let elementId: Int
    let content: () -> Content

    @State private var discoveryState: DiscoveryState = .rest
    @State private var touchStartTime: Date?
    @State private var timer: Timer?
    @Environment(\.accessibilityReduceMotion) private var reduceMotion

    /// Phase offset based on element ID (each element starts at different point)
    private var shimmerPhase: Double {
        Double(elementId % 7) / 7.0
    }

    /// Thresholds
    private let glanceThreshold: TimeInterval = 0.150
    private let interestThreshold: TimeInterval = 0.500

    var body: some View {
        content()
            .background(
                ZStack {
                    // Glass base
                    RoundedRectangle(cornerRadius: KagamiRadius.md)
                        .fill(.ultraThinMaterial)

                    // Spectral shimmer with discovery state
                    SpectralShimmer(phase: shimmerPhase, intensity: discoveryState.opacity)
                        .clipShape(RoundedRectangle(cornerRadius: KagamiRadius.md))
                        .animation(reduceMotion ? nil : KagamiMotion.defaultSpring, value: discoveryState)
                }
            )
            .modifier(ChromaticEdge(
                dispersion: discoveryState >= .focus ? 6 : 3,
                refraction: discoveryState >= .interest ? 1.2 : 0.8,
                isActive: discoveryState >= .glance
            ))
            .overlay(
                RoundedRectangle(cornerRadius: KagamiRadius.md)
                    .stroke(Color.white.opacity(0.1 + discoveryState.opacity * 0.2), lineWidth: 1)
            )
            .shadow(color: .black.opacity(0.1), radius: 10, x: 0, y: 2)
            .onHover { hovering in
                if hovering {
                    touchStartTime = Date()
                    startDiscoveryTimer()
                } else {
                    endInteraction()
                }
            }
            .simultaneousGesture(
                DragGesture(minimumDistance: 0)
                    .onChanged { _ in
                        if touchStartTime == nil {
                            touchStartTime = Date()
                            startDiscoveryTimer()
                        }
                    }
                    .onEnded { _ in
                        endInteraction()
                    }
            )
    }

    private func startDiscoveryTimer() {
        timer?.invalidate()
        discoveryState = .glance

        timer = Timer.scheduledTimer(withTimeInterval: 0.05, repeats: true) { _ in
            guard let start = touchStartTime else { return }
            let elapsed = Date().timeIntervalSince(start)

            let newState: DiscoveryState
            if elapsed >= interestThreshold {
                newState = .focus
            } else if elapsed >= glanceThreshold {
                newState = .interest
            } else {
                newState = .glance
            }

            if newState != discoveryState && !reduceMotion {
                // Haptic on state transition
                switch newState {
                case .interest:
                    UIImpactFeedbackGenerator(style: .light).impactOccurred()
                case .focus:
                    UIImpactFeedbackGenerator(style: .medium).impactOccurred()
                default:
                    break
                }
            }
            discoveryState = newState
        }
    }

    private func endInteraction() {
        timer?.invalidate()
        timer = nil

        if discoveryState >= .focus && !reduceMotion {
            discoveryState = .engage
            UIImpactFeedbackGenerator(style: .medium).impactOccurred()
            DispatchQueue.main.asyncAfter(deadline: .now() + 0.233) {
                withAnimation(.easeOut(duration: 0.377)) {
                    discoveryState = .rest
                }
            }
        } else {
            discoveryState = .rest
        }

        touchStartTime = nil
    }
}

// MARK: - Prism Glow

/// Soft colored glow that pulses
struct PrismGlow: ViewModifier {
    let color: Color
    let radius: CGFloat
    let animated: Bool

    @State private var glowOpacity: Double = 0
    @Environment(\.accessibilityReduceMotion) private var reduceMotion

    init(color: Color = .crystal, radius: CGFloat = 20, animated: Bool = true) {
        self.color = color
        self.radius = radius
        self.animated = animated
    }

    func body(content: Content) -> some View {
        content
            .shadow(
                color: color.opacity(reduceMotion ? 0.3 : glowOpacity),
                radius: reduceMotion ? radius : (glowOpacity > 0.2 ? radius : 0)
            )
            .onAppear {
                guard animated && !reduceMotion else { return }
                withAnimation(.easeInOut(duration: 1.5).repeatForever(autoreverses: true)) {
                    glowOpacity = 0.4
                }
            }
    }
}

// MARK: - Chromatic Aberration Text

/// Creates red/cyan offset effect on text (for headers/logos)
struct ChromaticText: View {
    let text: String
    let font: Font
    let offset: CGFloat

    @State private var isActive = false
    @Environment(\.accessibilityReduceMotion) private var reduceMotion

    init(_ text: String, font: Font = .title, offset: CGFloat = 2) {
        self.text = text
        self.font = font
        self.offset = offset
    }

    var body: some View {
        ZStack {
            // Red channel (left offset)
            Text(text)
                .font(font)
                .foregroundColor(.spark)
                .offset(x: isActive ? -offset : 0)
                .opacity(isActive ? 0.5 : 0)

            // Cyan channel (right offset)
            Text(text)
                .font(font)
                .foregroundColor(.crystal)
                .offset(x: isActive ? offset : 0)
                .opacity(isActive ? 0.5 : 0)

            // Main text
            Text(text)
                .font(font)
                .foregroundColor(.textPrimary)
        }
        .onHover { hovering in
            guard !reduceMotion else { return }
            withAnimation(KagamiMotion.fastSpring) {
                isActive = hovering
            }
        }
    }
}

// MARK: - Prism Ripple

/// Rainbow ripple effect on tap with physics-based dispersion
struct PrismRipple: ViewModifier {
    @State private var ripples: [RippleData] = []
    @Environment(\.accessibilityReduceMotion) private var reduceMotion

    struct RippleData: Identifiable {
        let id = UUID()
        let location: CGPoint
        let startColor: SpectralColor
    }

    func body(content: Content) -> some View {
        content
            .overlay(
                GeometryReader { geo in
                    ZStack {
                        ForEach(ripples) { ripple in
                            rippleView(ripple: ripple, size: geo.size)
                        }
                    }
                }
                .allowsHitTesting(false)
            )
            .simultaneousGesture(
                DragGesture(minimumDistance: 0)
                    .onEnded { value in
                        guard !reduceMotion else { return }
                        let ripple = RippleData(
                            location: value.location,
                            startColor: SpectralColor.allCases.randomElement() ?? .spark
                        )

                        // Haptic feedback
                        UIImpactFeedbackGenerator(style: .light).impactOccurred()

                        withAnimation(.easeOut(duration: 0.987)) {
                            ripples.append(ripple)
                        }
                        DispatchQueue.main.asyncAfter(deadline: .now() + 0.987) {
                            ripples.removeAll { $0.id == ripple.id }
                        }
                    }
            )
    }

    @ViewBuilder
    private func rippleView(ripple: RippleData, size: CGSize) -> some View {
        // Create spectrum of circles with dispersion timing
        ZStack {
            ForEach(SpectralColor.allCases, id: \.rawValue) { color in
                Circle()
                    .stroke(color.color.opacity(0.3), lineWidth: 2)
                    .frame(
                        width: max(size.width, size.height) * 2,
                        height: max(size.width, size.height) * 2
                    )
                    .position(ripple.location)
                    .transition(.asymmetric(
                        insertion: .scale(scale: 0).combined(with: .opacity)
                            .animation(DispersionTiming.animation(for: color, baseDuration: 0.8)),
                        removal: .opacity
                    ))
            }
        }
    }
}

// MARK: - View Extensions

extension View {
    /// Add spectral border
    func spectralBorder(lineWidth: CGFloat = 2, cornerRadius: CGFloat = 12, animated: Bool = true) -> some View {
        modifier(SpectralBorder(lineWidth: lineWidth, cornerRadius: cornerRadius, animated: animated))
    }

    /// Add prism glow
    func prismGlow(color: Color = .crystal, radius: CGFloat = 20, animated: Bool = true) -> some View {
        modifier(PrismGlow(color: color, radius: radius, animated: animated))
    }

    /// Add rainbow ripple on tap
    func prismRipple() -> some View {
        modifier(PrismRipple())
    }

    /// Add spectral discovery (effects intensify with sustained touch)
    func spectralDiscovery() -> some View {
        modifier(SpectralDiscovery())
    }

    /// Add chromatic edge dispersion
    func chromaticEdge(dispersion: CGFloat = 3, refraction: CGFloat = 1.0, isActive: Bool = true) -> some View {
        modifier(ChromaticEdge(dispersion: dispersion, refraction: refraction, isActive: isActive))
    }

    /// Add color line glow between two colors
    func fanoLineGlow(colony1: SpectralColor, colony2: SpectralColor, isActive: Binding<Bool>) -> some View {
        modifier(FanoLineGlowModifier(colony1: colony1, colony2: colony2, isActive: isActive))
    }

    /// Add chromatic pulse on success/completion
    func chromaticPulse(isTriggered: Binding<Bool>, color: Color = .statusSuccess) -> some View {
        modifier(ChromaticPulse(isTriggered: isTriggered, color: color))
    }
}

// MARK: - Preview

#Preview("Prism Effects") {
    ScrollView {
        VStack(spacing: 32) {
            // Shimmer Text
            ShimmerText("KAGAMI", font: .largeTitle.bold())

            // Chromatic Text
            ChromaticText("K A G A M I", font: .system(size: 48, weight: .ultraLight))

            // Prism Card with Discovery
            PrismCard(elementId: 1) {
                VStack(alignment: .leading, spacing: 8) {
                    Text("Prism Card")
                        .font(.headline)
                    Text("Touch and hold to discover effects")
                        .font(.caption)
                        .foregroundColor(.textSecondary)
                }
                .padding()
            }

            // Spectral Border Button
            Button("Spectral Button") {}
                .padding()
                .background(Color.obsidian)
                .foregroundColor(.textPrimary)
                .cornerRadius(KagamiRadius.sm)
                .spectralBorder(cornerRadius: KagamiRadius.sm)

            // Glow Effect
            Circle()
                .fill(Color.crystal)
                .frame(width: 40, height: 40)
                .prismGlow()

            // Ripple Demo
            RoundedRectangle(cornerRadius: 12)
                .fill(Color.obsidian)
                .frame(height: 100)
                .overlay(Text("Tap for ripple").foregroundColor(.textSecondary))
                .prismRipple()

            // Discovery Demo
            RoundedRectangle(cornerRadius: 16)
                .fill(Color.voidLight)
                .frame(height: 80)
                .overlay(Text("Hold to discover").foregroundColor(.textSecondary))
                .spectralDiscovery()
                .cornerRadius(16)
        }
        .padding()
    }
    .background(
        ZStack {
            Color.void.ignoresSafeArea()
            CausticBackground()
                .ignoresSafeArea()
        }
    )
    .preferredColorScheme(.dark)
    .environment(\.sizeCategory, .extraLarge)
}

#Preview("Color Lines") {
    VStack(spacing: 20) {
        ForEach(FanoLine.allCases, id: \.rawValue) { line in
            let (c1, c2, c3) = line.colonies
            HStack {
                Circle().fill(c1.color).frame(width: 24, height: 24)
                Image(systemName: "multiply")
                    .foregroundColor(.textSecondary)
                Circle().fill(c2.color).frame(width: 24, height: 24)
                Image(systemName: "equal")
                    .foregroundColor(.textSecondary)
                Circle().fill(c3.color).frame(width: 24, height: 24)

                Spacer()

                RoundedRectangle(cornerRadius: 8)
                    .fill(line.gradient)
                    .frame(width: 100, height: 24)
            }
            .padding(.horizontal)
        }
    }
    .padding()
    .background(Color.void)
    .preferredColorScheme(.dark)
    .environment(\.sizeCategory, .extraLarge)
}
