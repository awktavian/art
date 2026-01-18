//
// DesignSystem.swift — Kagami visionOS Design Tokens
//
// Spatial design foundation for Apple Vision Pro.
// Optimized for immersive experiences and depth perception.
//
// Phase 2 Accessibility: VoiceOver, reduced motion, enhanced contrast
//

import SwiftUI
import RealityKit

// MARK: - Accessibility Settings

/// Global accessibility preferences for spatial UI
class AccessibilitySettings: ObservableObject {
    static let shared = AccessibilitySettings()

    /// Tracks system reduced motion preference
    @Published var reduceMotion: Bool = false

    /// Tracks system increased contrast preference
    @Published var increaseContrast: Bool = false

    /// Tracks VoiceOver active state
    @Published var voiceOverRunning: Bool = false

    init() {
        updateFromSystem()
        setupNotifications()
    }

    private func updateFromSystem() {
        reduceMotion = UIAccessibility.isReduceMotionEnabled
        increaseContrast = UIAccessibility.isDarkerSystemColorsEnabled
        voiceOverRunning = UIAccessibility.isVoiceOverRunning
    }

    private func setupNotifications() {
        NotificationCenter.default.addObserver(
            forName: UIAccessibility.reduceMotionStatusDidChangeNotification,
            object: nil,
            queue: .main
        ) { [weak self] _ in
            self?.reduceMotion = UIAccessibility.isReduceMotionEnabled
        }

        NotificationCenter.default.addObserver(
            forName: UIAccessibility.darkerSystemColorsStatusDidChangeNotification,
            object: nil,
            queue: .main
        ) { [weak self] _ in
            self?.increaseContrast = UIAccessibility.isDarkerSystemColorsEnabled
        }

        NotificationCenter.default.addObserver(
            forName: UIAccessibility.voiceOverStatusDidChangeNotification,
            object: nil,
            queue: .main
        ) { [weak self] _ in
            self?.voiceOverRunning = UIAccessibility.isVoiceOverRunning
        }
    }
}

// MARK: - Spatial Color Tokens

extension Color {
    // Void Palette (Adapted for glass materials)
    static let voidSpatial = Color(hex: "#0D0A0F").opacity(0.85)
    static let obsidianSpatial = Color(hex: "#12101A").opacity(0.9)

    // Colony Colors (More vibrant for depth)
    static let spark = Color(hex: "#ff7f50")
    static let forge = Color(hex: "#e6c453")
    static let flow = Color(hex: "#5fd4cb")
    static let nexus = Color(hex: "#b08fd4")
    static let beacon = Color(hex: "#ffb84d")
    static let grove = Color(hex: "#8fc98f")
    static let crystal = Color(hex: "#7ddff0")

    // Spatial-specific
    static let glassHighlight = Color.white.opacity(0.15)
    static let glassBorder = Color.white.opacity(0.2)

    // Enhanced contrast variants (Phase 2 Accessibility)
    static let glassHighlightAccessible = Color.white.opacity(0.35)
    static let glassBorderAccessible = Color.white.opacity(0.45)

    /// Returns appropriate glass highlight based on accessibility settings
    static var adaptiveGlassHighlight: Color {
        AccessibilitySettings.shared.increaseContrast ? glassHighlightAccessible : glassHighlight
    }

    /// Returns appropriate glass border based on accessibility settings
    static var adaptiveGlassBorder: Color {
        AccessibilitySettings.shared.increaseContrast ? glassBorderAccessible : glassBorder
    }

    init(hex: String) {
        let hex = hex.trimmingCharacters(in: CharacterSet.alphanumerics.inverted)
        var int: UInt64 = 0
        Scanner(string: hex).scanHexInt64(&int)
        let r, g, b: UInt64
        switch hex.count {
        case 6:
            (r, g, b) = (int >> 16, int >> 8 & 0xFF, int & 0xFF)
        default:
            (r, g, b) = (0, 0, 0)
        }
        self.init(.sRGB, red: Double(r)/255, green: Double(g)/255, blue: Double(b)/255)
    }
}

// MARK: - Spatial Motion Tokens

struct SpatialMotion {
    // Timing durations for immersive space (natural, cinematic feel)
    static let instant: Double = 0.144     // 144ms - micro-interactions
    static let fast: Double = 0.233        // 233ms - quick responses
    static let normal: Double = 0.377      // 377ms - standard transitions
    static let slow: Double = 0.610        // 610ms - deliberate motion
    static let cinematicDuration: Double = 0.987  // 987ms - cinematic reveals

    // Spatial springs (softer for immersive)
    static let micro = Animation.spring(response: 0.233, dampingFraction: 0.85)
    static let soft = Animation.spring(response: 0.377, dampingFraction: 0.75)
    static let cinematic = Animation.spring(response: 0.610, dampingFraction: 0.7)
    static let float = Animation.spring(response: 0.987, dampingFraction: 0.65)

    // Breathing/ambient animations
    static let breathe = Animation.easeInOut(duration: 2.584)
    static let ambient = Animation.easeInOut(duration: 1.597)
}

// MARK: - Spatial Spacing (Meters for 3D space)

struct SpatialSpacing {
    static let near: Float = 0.5      // 50cm
    static let arm: Float = 0.75     // 75cm (arm's reach)
    static let comfort: Float = 1.0  // 1m
    static let room: Float = 2.0     // 2m
    static let ambient: Float = 5.0  // 5m
}

// MARK: - Window Sizes (Optimized for visionOS)

/// Window size configurations for spatial viewing comfort.
/// Optimized per visionOS HIG for comfortable reading distances.
/// Ive: "Golden ratio (φ ≈ 1.618) creates harmony in spatial dimensions."
struct SpatialWindowSize {
    /// Golden ratio for window proportions
    private static let φ: CGFloat = 1.618

    /// Compact window for quick actions and alerts
    static let compact = CGSize(width: 320, height: 320 / φ)  // 320 × 198

    /// Default window size with golden ratio proportions
    static let defaultSize = CGSize(width: 480, height: 480 / φ)  // 480 × 297

    /// Medium window for detail views
    static let medium = CGSize(width: 600, height: 600 / φ)  // 600 × 371

    /// Large window for immersive content
    static let large = CGSize(width: 800, height: 800 / φ)  // 800 × 494

    /// Full detail view
    static let full = CGSize(width: 1000, height: 1000 / φ)  // 1000 × 618
}

// MARK: - Material Tokens

/// Glass material system for visionOS.
/// Uses Apple's material system with semantic naming.
enum SpatialMaterial {
    /// Primary material - used for main content panels
    /// Maps to .thinMaterial for optimal balance of depth and readability
    case primary

    /// Secondary material - used for background elements
    /// Maps to .ultraThinMaterial for maximum depth perception
    case secondary

    /// Prominent material - used for highlighted/focused elements
    /// Maps to .regularMaterial for emphasis
    case prominent

    /// Adaptive material that responds to accessibility settings
    case adaptive

    /// Returns the SwiftUI material for this token
    var material: SwiftUI.Material {
        switch self {
        case .primary:
            return .thinMaterial
        case .secondary:
            return .ultraThinMaterial
        case .prominent:
            return .regularMaterial
        case .adaptive:
            return AccessibilitySettings.shared.increaseContrast ? .regularMaterial : .thinMaterial
        }
    }

    /// Returns any shape style for flexible usage
    var anyStyle: AnyShapeStyle {
        AnyShapeStyle(material)
    }
}

/// View modifier for applying material tokens
struct MaterialTokenModifier: ViewModifier {
    let token: SpatialMaterial
    let cornerRadius: CGFloat

    func body(content: Content) -> some View {
        content
            .background(token.material, in: RoundedRectangle(cornerRadius: cornerRadius))
    }
}

extension View {
    /// Applies a semantic material token
    func spatialMaterial(_ token: SpatialMaterial, cornerRadius: CGFloat = 20) -> some View {
        modifier(MaterialTokenModifier(token: token, cornerRadius: cornerRadius))
    }
}

// MARK: - Spatial Modifiers

struct SpatialHoverEffect: ViewModifier {
    @State private var isHovered = false

    func body(content: Content) -> some View {
        content
            .scaleEffect(isHovered ? 1.02 : 1.0)
            .shadow(color: .crystal.opacity(isHovered ? 0.3 : 0), radius: isHovered ? 20 : 0)
            .animation(SpatialMotion.soft, value: isHovered)
            .onHover { hovering in
                isHovered = hovering
            }
    }
}

struct SpatialPressEffect: ViewModifier {
    @State private var isPressed = false

    func body(content: Content) -> some View {
        content
            .scaleEffect(isPressed ? 0.95 : 1.0)
            .brightness(isPressed ? 0.1 : 0)
            .animation(SpatialMotion.micro, value: isPressed)
            .simultaneousGesture(
                DragGesture(minimumDistance: 0)
                    .onChanged { _ in isPressed = true }
                    .onEnded { _ in isPressed = false }
            )
    }
}

struct SpatialFloatEffect: ViewModifier {
    @State private var offset: CGFloat = 0
    @Environment(\.accessibilityReduceMotion) private var reduceMotion

    func body(content: Content) -> some View {
        content
            .offset(y: reduceMotion ? 0 : offset)
            .onAppear {
                guard !reduceMotion else { return }
                withAnimation(
                    Animation.easeInOut(duration: 2.584)  // Fibonacci 2584ms
                        .repeatForever(autoreverses: true)
                ) {
                    offset = 8
                }
            }
    }
}

struct SpatialGlassCard: ViewModifier {
    @Environment(\.accessibilityDifferentiateWithoutColor) private var differentiateWithoutColor

    func body(content: Content) -> some View {
        content
            .background(
                AccessibilitySettings.shared.increaseContrast
                    ? AnyShapeStyle(.thinMaterial)
                    : AnyShapeStyle(.ultraThinMaterial)
            )
            .clipShape(RoundedRectangle(cornerRadius: 24))
            .overlay(
                RoundedRectangle(cornerRadius: 24)
                    .stroke(
                        Color.adaptiveGlassBorder,
                        lineWidth: AccessibilitySettings.shared.increaseContrast ? 2 : 1
                    )
            )
    }
}

// MARK: - View Extensions

extension View {
    func spatialHover() -> some View {
        modifier(SpatialHoverEffect())
    }

    func spatialPress() -> some View {
        modifier(SpatialPressEffect())
    }

    func spatialFloat() -> some View {
        modifier(SpatialFloatEffect())
    }

    func spatialGlassCard() -> some View {
        modifier(SpatialGlassCard())
    }

    // MARK: - Spatial Accessibility Extensions (Phase 2)

    /// Adds comprehensive spatial accessibility to an interactive element
    func spatialAccessibility(
        label: String,
        hint: String? = nil,
        traits: AccessibilityTraits = .isButton,
        gestureHint: SpatialGestureHint? = nil
    ) -> some View {
        self
            .accessibilityLabel(label)
            .accessibilityHint(hint ?? gestureHint?.hintText ?? "")
            .accessibilityAddTraits(traits)
    }

    /// Adds spatial gesture hints for VoiceOver users
    func spatialGestureHint(_ hint: SpatialGestureHint) -> some View {
        self.accessibilityHint(hint.hintText)
    }

    /// Marks a view as a spatial region for VoiceOver navigation
    func spatialRegion(_ label: String) -> some View {
        self
            .accessibilityElement(children: .contain)
            .accessibilityLabel(label)
            .accessibilityAddTraits(.isHeader)
    }

    /// Adds reduced motion safe animation
    func reducedMotionAnimation<V: Equatable>(_ value: V, defaultAnimation: Animation = .default) -> some View {
        self.modifier(ReducedMotionAnimationModifier(value: value, defaultAnimation: defaultAnimation))
    }
}

// MARK: - Spatial Gesture Hints

/// Standard hints for spatial gestures in visionOS
enum SpatialGestureHint {
    case tapToActivate
    case doubleTapToSelect
    case pinchToAdjust
    case dragToMove
    case rotateToChange
    case longPressForOptions
    case lookAndPinch
    case custom(String)

    var hintText: String {
        switch self {
        case .tapToActivate:
            return "Look at this element and pinch to activate"
        case .doubleTapToSelect:
            return "Double tap to select"
        case .pinchToAdjust:
            return "Pinch and drag to adjust value"
        case .dragToMove:
            return "Pinch and drag to move in space"
        case .rotateToChange:
            return "Rotate your wrist while pinching to change"
        case .longPressForOptions:
            return "Look and hold pinch for more options"
        case .lookAndPinch:
            return "Look at this element and pinch your fingers to interact"
        case .custom(let text):
            return text
        }
    }
}

// MARK: - Reduced Motion Animation Modifier

struct ReducedMotionAnimationModifier<V: Equatable>: ViewModifier {
    @Environment(\.accessibilityReduceMotion) private var reduceMotion
    let value: V
    let defaultAnimation: Animation

    func body(content: Content) -> some View {
        content
            .animation(reduceMotion ? nil : defaultAnimation, value: value)
    }
}

// MARK: - Ornament Styles

/// Ive: "Padding should be uniform or golden ratio — 20h × 12v is neither"
struct OrnamentButtonStyle: ButtonStyle {
    let color: Color

    func makeBody(configuration: Configuration) -> some View {
        configuration.label
            .padding(.horizontal, 18)  // Ive: Unified padding based on 18 base
            .padding(.vertical, 12)    // 18/φ ≈ 11, rounds to 12
            .background(
                Capsule()
                    .fill(color.opacity(configuration.isPressed ? 0.45 : 0.2))
            )
            .overlay(
                Capsule()
                    .stroke(color.opacity(configuration.isPressed ? 0.65 : 0.4), lineWidth: 1.5)  // More visible edge
            )
            .scaleEffect(configuration.isPressed ? 0.95 : 1.0)  // Canonical press scale
            .animation(SpatialMotion.micro, value: configuration.isPressed)
    }
}

// MARK: - Spatial Typography

extension Font {
    static let spatialTitle = Font.system(size: 32, weight: .semibold, design: .rounded)
    static let spatialHeadline = Font.system(size: 24, weight: .medium, design: .rounded)
    static let spatialBody = Font.system(size: 18, weight: .regular)
    static let spatialCaption = Font.system(size: 14, weight: .regular)
    static let spatialMono = Font.system(size: 16, weight: .medium, design: .monospaced)
}

// MARK: - Proxemic Typography

/// Typography scaled for different spatial distances.
/// Based on Hall's proxemic zones adapted for visionOS.
enum ProxemicZone: CaseIterable {
    /// Intimate zone: < 45cm
    /// Largest text for closest interactions
    case intimate

    /// Personal zone: 45cm - 1.2m (arm's reach)
    /// Standard reading distance for most UI
    case personal

    /// Social zone: 1.2m - 3.6m
    /// Medium distance for ambient displays
    case social

    /// Public zone: > 3.6m
    /// Largest text for distant viewing
    case publicZone

    /// Recommended viewing distance in meters
    var distance: Float {
        switch self {
        case .intimate: return 0.4
        case .personal: return 0.8
        case .social: return 2.0
        case .publicZone: return 4.0
        }
    }

    /// Font scale multiplier for this zone
    var fontScale: CGFloat {
        switch self {
        case .intimate: return 0.85
        case .personal: return 1.0
        case .social: return 1.4
        case .publicZone: return 2.0
        }
    }
}

/// Typography system for proxemic zones
struct ProxemicTypography {
    let zone: ProxemicZone

    var title: Font {
        .system(size: 32 * zone.fontScale, weight: .semibold, design: .rounded)
    }

    var headline: Font {
        .system(size: 24 * zone.fontScale, weight: .medium, design: .rounded)
    }

    var body: Font {
        .system(size: 18 * zone.fontScale, weight: .regular)
    }

    var caption: Font {
        .system(size: 14 * zone.fontScale, weight: .regular)
    }

    var label: Font {
        .system(size: 12 * zone.fontScale, weight: .medium)
    }

    /// Minimum recommended contrast ratio for this zone
    var minimumContrastRatio: Double {
        switch zone {
        case .intimate: return 4.5
        case .personal: return 4.5
        case .social: return 7.0
        case .publicZone: return 10.0
        }
    }
}

/// View modifier for proxemic typography
struct ProxemicTypographyModifier: ViewModifier {
    let zone: ProxemicZone

    func body(content: Content) -> some View {
        content
            .environment(\.proxemicZone, zone)
    }
}

/// Environment key for proxemic zone
private struct ProxemicZoneKey: EnvironmentKey {
    static let defaultValue: ProxemicZone = .personal
}

extension EnvironmentValues {
    var proxemicZone: ProxemicZone {
        get { self[ProxemicZoneKey.self] }
        set { self[ProxemicZoneKey.self] = newValue }
    }
}

extension View {
    /// Sets the proxemic zone for typography scaling
    func proxemicZone(_ zone: ProxemicZone) -> some View {
        modifier(ProxemicTypographyModifier(zone: zone))
    }

    /// Applies typography scaled for the current proxemic zone
    func proxemicTitle() -> some View {
        modifier(ProxemicTitleModifier())
    }

    func proxemicHeadline() -> some View {
        modifier(ProxemicHeadlineModifier())
    }

    func proxemicBody() -> some View {
        modifier(ProxemicBodyModifier())
    }
}

private struct ProxemicTitleModifier: ViewModifier {
    @Environment(\.proxemicZone) var zone

    func body(content: Content) -> some View {
        content.font(ProxemicTypography(zone: zone).title)
    }
}

private struct ProxemicHeadlineModifier: ViewModifier {
    @Environment(\.proxemicZone) var zone

    func body(content: Content) -> some View {
        content.font(ProxemicTypography(zone: zone).headline)
    }
}

private struct ProxemicBodyModifier: ViewModifier {
    @Environment(\.proxemicZone) var zone

    func body(content: Content) -> some View {
        content.font(ProxemicTypography(zone: zone).body)
    }
}

// MARK: - Extensibility

/// Ive: "The magic of glass is at 0.7 opacity — you see through without losing presence"
class SpatialTheme: ObservableObject {
    static let shared = SpatialTheme()

    @Published var accentColor: Color = .crystal
    @Published var glassOpacity: Double = 0.7  // Ive: Was 0.85, too opaque
    @Published var floatAmplitude: CGFloat = 6  // Subtler float
    @Published var hapticsEnabled: Bool = true

    // Accessibility-aware computed properties
    var effectiveGlassOpacity: Double {
        AccessibilitySettings.shared.increaseContrast ? 0.9 : glassOpacity
    }

    var effectiveFloatAmplitude: CGFloat {
        AccessibilitySettings.shared.reduceMotion ? 0 : floatAmplitude
    }
}

// MARK: - 3D Entity Accessibility

/// Provides accessibility support for RealityKit entities
struct SpatialEntityAccessibility {
    let label: String
    let hint: String
    let traits: UIAccessibilityTraits
    let customActions: [String]

    init(
        label: String,
        hint: String = "",
        traits: UIAccessibilityTraits = .none,
        customActions: [String] = []
    ) {
        self.label = label
        self.hint = hint
        self.traits = traits
        self.customActions = customActions
    }

    /// Standard accessibility for the Kagami orb
    static let kagamiOrb = SpatialEntityAccessibility(
        label: "Kagami presence orb",
        hint: "Look at and pinch to activate quick actions. The orb changes color based on active system state.",
        traits: .button,
        customActions: ["Activate", "Dismiss"]
    )

    /// Standard accessibility for ambient particles
    static let ambientParticles = SpatialEntityAccessibility(
        label: "Ambient particle effects",
        hint: "Decorative particles surrounding the Kagami orb",
        traits: .none
    )
}

// MARK: - Gaze Dwell Indicator

/// Visual feedback for gaze dwell activation (look-and-wait interaction)
struct GazeDwellIndicator: View {
    /// Progress from 0.0 to 1.0
    let progress: Double
    /// Color of the progress ring
    var color: Color = .crystal
    /// Size of the indicator
    var size: CGFloat = 44

    @Environment(\.accessibilityReduceMotion) private var reduceMotion

    var body: some View {
        ZStack {
            // Background ring
            Circle()
                .stroke(color.opacity(0.2), lineWidth: 3)
                .frame(width: size, height: size)

            // Progress ring
            Circle()
                .trim(from: 0, to: progress)
                .stroke(
                    color,
                    style: StrokeStyle(lineWidth: 3, lineCap: .round)
                )
                .frame(width: size, height: size)
                .rotationEffect(.degrees(-90))
                .animation(reduceMotion ? nil : .linear(duration: 0.089), value: progress)

            // Completion checkmark
            if progress >= 1.0 {
                Image(systemName: "checkmark")
                    .font(.system(size: size * 0.4, weight: .bold))
                    .foregroundColor(color)
                    .transition(.scale.combined(with: .opacity))
            }
        }
        .accessibilityLabel("Gaze activation progress")
        .accessibilityValue("\(Int(progress * 100)) percent")
    }
}

// MARK: - Hand Tracking Feedback

/// Visual indicator showing hand tracking state
struct HandTrackingFeedbackView: View {
    let leftHandDetected: Bool
    let rightHandDetected: Bool
    let currentGesture: String
    let isOutOfReach: Bool

    @Environment(\.accessibilityReduceMotion) private var reduceMotion

    private var handColor: Color {
        if isOutOfReach { return .orange }
        return .crystal
    }

    var body: some View {
        HStack(spacing: 16) {
            // Left hand indicator
            HandIndicator(
                detected: leftHandDetected,
                chirality: .left,
                color: handColor
            )

            // Gesture indicator (center)
            if !currentGesture.isEmpty && currentGesture != "none" {
                GestureIndicator(gesture: currentGesture)
                    .transition(.scale.combined(with: .opacity))
            }

            // Right hand indicator
            HandIndicator(
                detected: rightHandDetected,
                chirality: .right,
                color: handColor
            )
        }
        .padding(.horizontal, 16)
        .padding(.vertical, 12)
        .background(.ultraThinMaterial, in: Capsule())
        .accessibilityElement(children: .combine)
        .accessibilityLabel(accessibilityDescription)
    }

    private var accessibilityDescription: String {
        var parts: [String] = []
        if leftHandDetected { parts.append("Left hand detected") }
        if rightHandDetected { parts.append("Right hand detected") }
        if currentGesture != "none" { parts.append("Gesture: \(currentGesture)") }
        if isOutOfReach { parts.append("Warning: Hand out of reach") }
        return parts.isEmpty ? "No hands detected" : parts.joined(separator: ", ")
    }
}

/// Individual hand indicator with breathing pulse when active
private struct HandIndicator: View {
    let detected: Bool
    let chirality: Chirality
    let color: Color

    @Environment(\.accessibilityReduceMotion) private var reduceMotion
    @State private var breathingScale: CGFloat = 1.0

    enum Chirality {
        case left, right

        var icon: String {
            switch self {
            case .left: return "hand.raised.fill"
            case .right: return "hand.raised.fill"
            }
        }
    }

    var body: some View {
        Image(systemName: chirality.icon)
            .font(.system(size: 20))
            .foregroundColor(detected ? color : .gray.opacity(0.4))
            .scaleEffect(x: chirality == .left ? -1 : 1, y: 1)
            .scaleEffect(detected && !reduceMotion ? breathingScale : 1.0)
            .opacity(detected ? 1.0 : 0.5)
            .animation(.spring(response: 0.233, dampingFraction: 0.8), value: detected)
            .onAppear {
                // Breathing pulse animation - 2.584s Fibonacci cycle when detected
                guard !reduceMotion else { return }
                withAnimation(.easeInOut(duration: 2.584).repeatForever(autoreverses: true)) {
                    breathingScale = 1.1
                }
            }
            .onChange(of: detected) { _, newValue in
                if !newValue {
                    withAnimation(.easeInOut(duration: 0.233)) {
                        breathingScale = 1.0
                    }
                }
            }
    }
}

/// Gesture type indicator
private struct GestureIndicator: View {
    let gesture: String

    private var icon: String {
        switch gesture {
        case "pinch": return "hand.pinch.fill"
        case "point": return "hand.point.up.fill"
        case "open_palm": return "hand.raised.fill"
        case "fist": return "hand.raised.fill"
        case "thumbs_up": return "hand.thumbsup.fill"
        default: return "hand.raised"
        }
    }

    var body: some View {
        Image(systemName: icon)
            .font(.system(size: 16))
            .foregroundColor(.crystal)
            .padding(8)
            .background(Color.crystal.opacity(0.2), in: Circle())
    }
}

// MARK: - Spatial Depth Layer

/// View modifier for consistent depth layering in visionOS
struct SpatialDepthModifier: ViewModifier {
    let layer: DepthLayer

    enum DepthLayer {
        case background  // Furthest from user
        case content     // Default content layer
        case elevated    // Slightly forward
        case overlay     // Closest to user

        var zOffset: CGFloat {
            switch self {
            case .background: return -20
            case .content: return 0
            case .elevated: return 20
            case .overlay: return 50
            }
        }
    }

    func body(content: Content) -> some View {
        content
            .offset(z: layer.zOffset)
    }
}

extension View {
    /// Applies consistent spatial depth layering
    func spatialDepth(_ layer: SpatialDepthModifier.DepthLayer) -> some View {
        modifier(SpatialDepthModifier(layer: layer))
    }
}

/*
 * 鏡
 *
 * In spatial computing, presence is the interface.
 * Every element exists in real space.
 * Design for depth, not flatness.
 */
