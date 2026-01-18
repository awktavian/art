//
// PersonaAdaptiveModifiers.swift — Adaptive UX for All Household Types
//
// Modifiers that adapt UI based on member accessibility profiles,
// cultural preferences, and household types.
//
// Colony: Symbiote (e3) — Theory of Mind
//
// h(x) >= 0. For EVERYONE.
//

import SwiftUI

// MARK: - Environment Keys

/// Current household member using the app
struct CurrentMemberKey: EnvironmentKey {
    static let defaultValue: HouseholdMember? = nil
}

/// Current household context
struct CurrentHouseholdKey: EnvironmentKey {
    static let defaultValue: Household? = nil
}

extension EnvironmentValues {
    var currentMember: HouseholdMember? {
        get { self[CurrentMemberKey.self] }
        set { self[CurrentMemberKey.self] = newValue }
    }

    var currentHousehold: Household? {
        get { self[CurrentHouseholdKey.self] }
        set { self[CurrentHouseholdKey.self] = newValue }
    }
}

// MARK: - Accessibility-Adaptive Font Modifier

/// Automatically adjusts font size based on member's vision level
struct AdaptiveFontModifier: ViewModifier {
    @Environment(\.currentMember) var member
    @Environment(\.dynamicTypeSize) var systemTypeSize

    let baseSize: CGFloat
    let weight: Font.Weight

    func body(content: Content) -> some View {
        content
            .font(.system(size: adaptedSize, weight: weight))
            .dynamicTypeSize(...DynamicTypeSize.accessibility5) // Allow full range
    }

    private var adaptedSize: CGFloat {
        guard let profile = member?.accessibilityProfile else {
            return baseSize
        }

        switch profile.visionLevel {
        case .full:
            return baseSize
        case .lowVision:
            // 50% larger minimum
            return max(baseSize * 1.5, 18)
        case .blind:
            // Screen reader users - size less relevant but keep large for partial use
            return max(baseSize * 1.5, 18)
        }
    }
}

// MARK: - Contrast-Adaptive Colors

/// Adjusts colors based on member's contrast needs
struct AdaptiveContrastModifier: ViewModifier {
    @Environment(\.currentMember) var member
    @Environment(\.colorScheme) var colorScheme

    let baseColor: Color
    let role: ContrastRole

    enum ContrastRole {
        case foreground
        case background
        case accent
    }

    func body(content: Content) -> some View {
        content
            .foregroundStyle(role == .foreground ? adaptedColor : baseColor)
            .background(role == .background ? adaptedColor : Color.clear)
            .tint(role == .accent ? adaptedColor : baseColor)
    }

    private var adaptedColor: Color {
        guard let profile = member?.accessibilityProfile else {
            return baseColor
        }

        // For low vision/blind users, use maximum contrast
        switch profile.visionLevel {
        case .full:
            return baseColor
        case .lowVision, .blind:
            // Force high contrast colors
            if role == .foreground {
                return colorScheme == .dark ? .white : .black
            } else {
                return colorScheme == .dark ? .black : .white
            }
        }
    }
}

// MARK: - Touch Target Adapter

/// Ensures touch targets meet accessibility requirements based on user profile
struct AdaptiveTouchTargetModifier: ViewModifier {
    @Environment(\.currentMember) var member

    func body(content: Content) -> some View {
        content
            .frame(minWidth: minTouchSize, minHeight: minTouchSize)
            .contentShape(Rectangle())
    }

    private var minTouchSize: CGFloat {
        guard let profile = member?.accessibilityProfile else {
            return 44 // WCAG minimum
        }

        switch profile.motorControl {
        case .full:
            return 44
        case .limited:
            return 56 // Larger for motor impairment
        case .voiceOnly, .switchControl:
            return 64 // Extra large for alternative input
        }
    }
}

// MARK: - Voice Feedback Modifier

/// Adds enhanced VoiceOver support based on member needs
struct AdaptiveVoiceOverModifier: ViewModifier {
    @Environment(\.currentMember) var member

    let label: String
    let hint: String?
    let priority: AccessibilityPriority

    enum AccessibilityPriority {
        case critical
        case high
        case normal
        case low
    }

    func body(content: Content) -> some View {
        content
            .accessibilityLabel(label)
            .accessibilityHint(adaptedHint)
            .accessibilityAddTraits(traits)
    }

    private var adaptedHint: String {
        guard let base = hint else { return "" }

        // For cognitive support, add more detailed hints
        if member?.accessibilityProfile.cognitiveNeeds == .simplified {
            return base + ". Tap to activate."
        }

        return base
    }

    private var traits: AccessibilityTraits {
        switch priority {
        case .critical:
            return [.startsMediaSession, .isHeader]
        case .high:
            return [.isHeader]
        case .normal:
            return []
        case .low:
            return []
        }
    }
}

// MARK: - Cultural Greeting Modifier

/// Adapts greetings and communication based on cultural preferences
struct CulturalGreetingModifier: ViewModifier {
    @Environment(\.currentMember) var member
    @Environment(\.currentHousehold) var household

    let baseName: String

    func body(content: Content) -> some View {
        content
            .accessibilityLabel(greetingText)
    }

    var greetingText: String {
        guard let member = member else {
            return baseName
        }

        // Use appropriate formality based on culture
        switch member.culturalPreferences.privacyOrientation {
        case .hierarchical:
            // More formal address
            return member.name
        case .collectivist, .communalist:
            // May use family terms
            if household?.householdType == .multigenerational {
                return roleName(for: member.role)
            }
            return member.name
        case .individualist, .balanced:
            // First name is fine
            return member.name
        }
    }

    private func roleName(for role: MemberRole) -> String {
        switch role {
        case .owner, .admin:
            return member?.name ?? baseName
        case .member:
            return member?.name ?? baseName
        case .child:
            return member?.name ?? "Little one"
        case .guest:
            return "Guest"
        case .pet:
            return member?.name ?? "Pet"
        }
    }
}

// MARK: - Privacy Zone Modifier

/// Enforces privacy boundaries based on household type
struct PrivacyZoneModifier: ViewModifier {
    @Environment(\.currentMember) var member
    @Environment(\.currentHousehold) var household

    let zoneMember: HouseholdMember
    let contentType: PrivateContentType

    enum PrivateContentType {
        case location
        case activity
        case schedule
        case camera
        case audio
    }

    func body(content: Content) -> some View {
        Group {
            if canAccess {
                content
            } else {
                Text("Private")
                    .foregroundStyle(.secondary)
                    .accessibilityLabel("This information is private")
            }
        }
    }

    private var canAccess: Bool {
        guard let currentMember = member,
              let household = household else {
            return false
        }

        // Same person can always see their own data
        if currentMember.id == zoneMember.id {
            return true
        }

        // Check authority level
        guard currentMember.authorityLevel != .minimal else {
            return false
        }

        // For roommates, privacy is strict
        if household.householdType == .roommates {
            // Only share public info
            return contentType == .activity && zoneMember.role != .guest
        }

        // For individualist households, require explicit sharing
        if currentMember.culturalPreferences.privacyOrientation == .individualist {
            // In individualist cultures, even family respects boundaries
            return currentMember.authorityLevel == .admin
        }

        // For collectivist/hierarchical, more sharing is default
        return true
    }
}

// MARK: - Schedule-Aware Modifier

/// Adapts UI based on member's schedule (quiet hours, sleep, etc.)
struct ScheduleAwareModifier: ViewModifier {
    @Environment(\.currentMember) var member

    func body(content: Content) -> some View {
        content
            .preferredColorScheme(preferredColorScheme)
    }

    private var preferredColorScheme: ColorScheme? {
        guard let schedule = member?.scheduleProfile,
              let sleepTime = schedule.typicalSleepTime,
              let wakeTime = schedule.typicalWakeTime else {
            return nil
        }

        let calendar = Calendar.current
        let sleepHour = calendar.component(.hour, from: sleepTime)
        let wakeHour = calendar.component(.hour, from: wakeTime)
        let currentHour = calendar.component(.hour, from: Date())

        // If near sleep time, prefer dark mode
        if currentHour >= sleepHour || currentHour < wakeHour {
            return .dark
        }

        return nil
    }
}

// MARK: - Household Type Adaptive Container

/// A container that adapts its presentation based on household type
struct AdaptiveHouseholdContainer<Content: View>: View {
    @Environment(\.currentHousehold) var household

    let content: Content

    init(@ViewBuilder content: () -> Content) {
        self.content = content()
    }

    var body: some View {
        Group {
            switch household?.householdType {
            case .single:
                // Maximum accessibility for single-person households
                content
                    .accessibilityElement(children: .contain)
                    .accessibilityAddTraits(.isStaticText)

            case .multigenerational:
                // Show family-wide information
                content

            case .roommates:
                // Emphasize privacy boundaries
                content
                    .privacyOverlay()

            case .family, .couple, .none:
                // Default presentation
                content
            }
        }
    }
}

// MARK: - Helper Modifiers

extension View {
    /// Adds privacy indication overlay for roommate situations
    func privacyOverlay() -> some View {
        self.overlay(alignment: .topTrailing) {
            Image(systemName: "lock.shield")
                .font(.caption2)
                .foregroundStyle(.secondary)
                .padding(4)
        }
    }

    /// Simplifies controls for single parent / high-stress scenarios
    func simplifiedControls() -> some View {
        self.buttonStyle(.bordered)
    }
}

// MARK: - View Extensions

extension View {
    /// Apply font that adapts to member's vision needs
    func adaptiveFont(size: CGFloat, weight: Font.Weight = .regular) -> some View {
        modifier(AdaptiveFontModifier(baseSize: size, weight: weight))
    }

    /// Apply color that adapts to member's contrast needs
    func adaptiveContrast(_ color: Color, role: AdaptiveContrastModifier.ContrastRole = .foreground) -> some View {
        modifier(AdaptiveContrastModifier(baseColor: color, role: role))
    }

    /// Ensure touch target meets member's motor needs
    func adaptiveTouchTarget() -> some View {
        modifier(AdaptiveTouchTargetModifier())
    }

    /// Add VoiceOver support adapted to member's needs
    func adaptiveAccessibility(
        label: String,
        hint: String? = nil,
        priority: AdaptiveVoiceOverModifier.AccessibilityPriority = .normal
    ) -> some View {
        modifier(AdaptiveVoiceOverModifier(label: label, hint: hint, priority: priority))
    }

    /// Adapt greeting to cultural preferences
    func culturalGreeting(_ name: String) -> some View {
        modifier(CulturalGreetingModifier(baseName: name))
    }

    /// Enforce privacy boundaries for content
    func privacyZone(
        for member: HouseholdMember,
        content: PrivacyZoneModifier.PrivateContentType
    ) -> some View {
        modifier(PrivacyZoneModifier(zoneMember: member, contentType: content))
    }

    /// Adapt to member's schedule
    func scheduleAware() -> some View {
        modifier(ScheduleAwareModifier())
    }
}

// MARK: - Persona-Specific View Builders

/// Builds UI optimized for senior users (Ingrid persona)
struct SeniorOptimizedView<Content: View>: View {
    let content: Content

    init(@ViewBuilder content: () -> Content) {
        self.content = content()
    }

    var body: some View {
        content
            .adaptiveFont(size: 20, weight: .medium)
            .adaptiveTouchTarget()
            .padding()
            .background(Color(.systemBackground))
            .clipShape(RoundedRectangle(cornerRadius: 16))
    }
}

/// Builds UI optimized for accessibility (Michael persona)
struct AccessibilityFirstView<Content: View>: View {
    @Environment(\.accessibilityEnabled) var voiceOverRunning

    let content: Content
    let speakLabel: String

    init(speak label: String, @ViewBuilder content: () -> Content) {
        self.speakLabel = label
        self.content = content()
    }

    var body: some View {
        content
            .accessibilityLabel(speakLabel)
            .accessibilityAddTraits(.startsMediaSession)
            .accessibilityInputLabels([speakLabel, "activate", "select"])
    }
}

/// Builds UI optimized for roommate privacy (Tokyo Apartment persona)
struct PrivacyFirstView<Content: View>: View {
    @Environment(\.currentMember) var currentMember

    let content: Content
    let owner: HouseholdMember

    init(ownedBy owner: HouseholdMember, @ViewBuilder content: () -> Content) {
        self.owner = owner
        self.content = content()
    }

    var body: some View {
        if currentMember?.id == owner.id {
            content
        } else {
            VStack {
                Image(systemName: "eye.slash")
                    .font(.largeTitle)
                    .foregroundStyle(.secondary)
                Text("Private")
                    .font(.caption)
            }
            .accessibilityLabel("This content is private to \(owner.name)")
        }
    }
}

// MARK: - Emergency Features for All Personas

/// Emergency button that's ALWAYS accessible regardless of settings
struct UniversalEmergencyButton: View {
    @Environment(\.currentMember) var member
    @Environment(\.currentHousehold) var household

    let action: () -> Void

    var body: some View {
        Button(action: action) {
            HStack(spacing: 12) {
                Image(systemName: "phone.fill")
                Text(emergencyLabel)
            }
            .font(.headline)
            .foregroundStyle(.white)
            .padding()
            .background(Color.red)
            .clipShape(RoundedRectangle(cornerRadius: 12))
        }
        .frame(minWidth: 64, minHeight: 64) // ALWAYS large target
        .accessibilityLabel(emergencyAccessibilityLabel)
        .accessibilityHint("Double-tap to call for help immediately")
        .accessibilityAddTraits(.startsMediaSession)
        .accessibilityInputLabels(["emergency", "help", "call for help", "SOS"])
    }

    private var emergencyLabel: String {
        // Adapt based on language if known
        switch member?.culturalPreferences.primaryLanguage {
        case "es": return "Emergencia"
        case "de": return "Notfall"
        case "ja": return "緊急"
        case "zh": return "紧急"
        case "hi": return "आपातकाल"
        case "ar": return "طوارئ"
        default: return "Emergency"
        }
    }

    private var emergencyAccessibilityLabel: String {
        if let name = member?.name {
            return "Emergency button. Calls for help and alerts \(name)'s emergency contacts."
        }
        return "Emergency button. Calls for help immediately."
    }
}

// MARK: - Preview

#if DEBUG
struct PersonaAdaptiveModifiers_Previews: PreviewProvider {
    static var previews: some View {
        VStack(spacing: 20) {
            Text("Adaptive Text")
                .adaptiveFont(size: 16, weight: .medium)

            Button("Adaptive Button") { }
                .adaptiveTouchTarget()

            UniversalEmergencyButton { }
        }
        .padding()
        .environment(\.currentMember, HouseholdMember(
            id: "preview",
            name: "Preview User",
            pronouns: Pronouns(subject: "they", object: "them", possessive: "their"),
            role: .admin,
            authorityLevel: .admin,
            accessibilityProfile: .lowVision,
            culturalPreferences: CulturalPreferences(primaryLanguage: "en"),
            scheduleProfile: ScheduleProfile()
        ))
    }
}
#endif
