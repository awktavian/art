//
// HouseholdTypes.swift -- Household & Accessibility Models
//
// Kagami TV -- Shared types for household management
//
// Colony: Hearth (e5) -- Home and belonging
//
// These types mirror the Rust household.rs definitions to enable
// full accessibility profile support and multi-user household modes.
//
// Design Philosophy:
// - Local-first: Works without internet via mesh networking
// - Culturally adaptive: Respects privacy norms from individualist to collectivist
// - Accessibility-native: WCAG AAA as craft, not compliance
// - Role-aware: Different household members have different needs and permissions
//
// h(x) >= 0. Always.
// Privacy IS safety.
//

import Foundation
import SwiftUI

// MARK: - Member Role

/// Role of a household member determining base permissions
public enum MemberRole: String, Codable, CaseIterable {
    /// Primary household owner with full control
    case owner
    /// Administrator with nearly full control (e.g., spouse, partner)
    case admin
    /// Regular household member (e.g., adult family member)
    case member
    /// Child with restricted permissions
    case child
    /// Guest with minimal, temporary access
    case guest

    /// Returns the default authority level for this role
    public var defaultAuthority: AuthorityLevel {
        switch self {
        case .owner: return .full
        case .admin: return .high
        case .member: return .standard
        case .child: return .limited
        case .guest: return .minimal
        }
    }

    /// Returns true if this role can modify household settings
    public var canModifyHousehold: Bool {
        switch self {
        case .owner, .admin: return true
        default: return false
        }
    }

    /// Returns true if this role can add/remove members
    public var canManageMembers: Bool {
        switch self {
        case .owner, .admin: return true
        default: return false
        }
    }

    /// Returns true if this role can access security features
    public var canAccessSecurity: Bool {
        switch self {
        case .owner, .admin, .member: return true
        default: return false
        }
    }
}

// MARK: - Authority Level

/// Fine-grained authority level for permissions
public enum AuthorityLevel: String, Codable, Comparable, CaseIterable {
    /// No permissions (blocked)
    case none
    /// Minimal permissions (guests, temporary access)
    case minimal
    /// Limited permissions (children, restricted users)
    case limited
    /// Standard permissions (regular household members)
    case standard
    /// High permissions (admins, trusted adults)
    case high
    /// Full permissions (owner only)
    case full

    /// Numeric value for comparison (0-100)
    public var level: Int {
        switch self {
        case .none: return 0
        case .minimal: return 20
        case .limited: return 40
        case .standard: return 60
        case .high: return 80
        case .full: return 100
        }
    }

    /// Check if this authority level can perform an action requiring `required` level
    public func canPerform(_ required: AuthorityLevel) -> Bool {
        self.level >= required.level
    }

    public static func < (lhs: AuthorityLevel, rhs: AuthorityLevel) -> Bool {
        lhs.level < rhs.level
    }
}

// MARK: - Input Method

/// Input method preferences for accessibility
public enum InputMethod: String, Codable, CaseIterable {
    /// Touch screen
    case touch
    /// Physical keyboard
    case keyboard
    /// Mouse/trackpad
    case pointer
    /// Voice commands
    case voice
    /// Eye tracking
    case eyeTracking = "eye_tracking"
    /// Switch control
    case switchControl = "switch_control"
    /// Gesture recognition
    case gesture
}

// MARK: - Accessibility Profile

/// Accessibility requirements and preferences for a household member
public struct AccessibilityProfile: Codable, Equatable {
    /// Minimum font size in pixels (default: 16)
    public var minFontSize: Int

    /// Minimum contrast ratio (WCAG: 4.5 AA, 7.0 AAA)
    public var minContrastRatio: Double

    /// Minimum touch target size in pixels (default: 44)
    public var minTouchTarget: Int

    /// Prefers reduced motion
    public var reducedMotion: Bool

    /// Prefers high contrast mode
    public var highContrast: Bool

    /// Vision impairment level (0 = none, 1 = mild, 2 = moderate, 3 = severe)
    public var visionImpairment: Int

    /// Hearing impairment level (0 = none, 1 = mild, 2 = moderate, 3 = severe)
    public var hearingImpairment: Int

    /// Motor impairment level (0 = none, 1 = mild, 2 = moderate, 3 = severe)
    public var motorImpairment: Int

    /// Cognitive considerations (memory, processing speed, etc.)
    public var cognitiveConsiderations: [String]

    /// Preferred input methods
    public var preferredInputs: [InputMethod]

    /// Screen reader in use
    public var screenReader: Bool

    /// Voice control as primary input
    public var voicePrimary: Bool

    /// Default audio volume (0-100)
    public var defaultVolume: Int

    /// Prefer slow, clear speech
    public var slowSpeech: Bool

    // MARK: - Initializers

    public init(
        minFontSize: Int = 16,
        minContrastRatio: Double = 4.5,
        minTouchTarget: Int = 44,
        reducedMotion: Bool = false,
        highContrast: Bool = false,
        visionImpairment: Int = 0,
        hearingImpairment: Int = 0,
        motorImpairment: Int = 0,
        cognitiveConsiderations: [String] = [],
        preferredInputs: [InputMethod] = [.touch, .voice],
        screenReader: Bool = false,
        voicePrimary: Bool = false,
        defaultVolume: Int = 70,
        slowSpeech: Bool = false
    ) {
        self.minFontSize = minFontSize
        self.minContrastRatio = minContrastRatio
        self.minTouchTarget = minTouchTarget
        self.reducedMotion = reducedMotion
        self.highContrast = highContrast
        self.visionImpairment = visionImpairment
        self.hearingImpairment = hearingImpairment
        self.motorImpairment = motorImpairment
        self.cognitiveConsiderations = cognitiveConsiderations
        self.preferredInputs = preferredInputs
        self.screenReader = screenReader
        self.voicePrimary = voicePrimary
        self.defaultVolume = defaultVolume
        self.slowSpeech = slowSpeech
    }

    /// Create a profile for a senior with common age-related needs
    public static func senior() -> AccessibilityProfile {
        AccessibilityProfile(
            minFontSize: 24,
            minContrastRatio: 7.0,  // WCAG AAA
            minTouchTarget: 48,
            reducedMotion: true,
            highContrast: true,
            visionImpairment: 1,
            hearingImpairment: 1,
            cognitiveConsiderations: ["memory_support"],
            preferredInputs: [.voice, .touch],
            voicePrimary: true,
            defaultVolume: 80,
            slowSpeech: true
        )
    }

    /// Create a profile for someone with visual impairment
    public static func visualImpairment(severity: Int) -> AccessibilityProfile {
        AccessibilityProfile(
            minFontSize: [16, 24, 32, 40][min(severity, 3)],
            minContrastRatio: 7.0,
            minTouchTarget: 48,
            highContrast: severity >= 2,
            visionImpairment: severity,
            preferredInputs: [.voice],
            screenReader: severity >= 2,
            voicePrimary: severity >= 2
        )
    }

    /// Create a profile for someone with motor impairment
    public static func motorImpairment(severity: Int) -> AccessibilityProfile {
        AccessibilityProfile(
            minTouchTarget: [44, 48, 56, 64][min(severity, 3)],
            reducedMotion: true,
            motorImpairment: severity,
            preferredInputs: [.voice, .switchControl],
            voicePrimary: severity >= 2
        )
    }
}

// MARK: - Privacy Orientation

/// Privacy orientation based on cultural norms
public enum PrivacyOrientation: String, Codable {
    /// Strong individual privacy (typical in US, Germany, Netherlands)
    case individualist
    /// Moderate privacy with family sharing (typical in Southern Europe, Latin America)
    case familyOriented = "family_oriented"
    /// Collectivist with shared household awareness (typical in East Asia, Middle East)
    case collectivist
}

// MARK: - Decision Style

/// Decision-making style in household
public enum DecisionStyle: String, Codable {
    /// Individual autonomy
    case individual
    /// Joint decisions between partners
    case partnership
    /// Hierarchical (elders consulted, head decides)
    case hierarchical
    /// Consensus-based (everyone has input)
    case consensus
}

// MARK: - Date Format

/// Date format preference
public enum DateFormat: String, Codable {
    /// MM/DD/YYYY (US)
    case monthDayYear = "month_day_year"
    /// DD/MM/YYYY (Europe, most of world)
    case dayMonthYear = "day_month_year"
    /// YYYY-MM-DD (ISO 8601)
    case yearMonthDay = "year_month_day"
}

// MARK: - Temperature Unit

/// Temperature unit preference
public enum TemperatureUnit: String, Codable {
    case fahrenheit
    case celsius
}

// MARK: - Greeting Style

/// Greeting style preference
public enum GreetingStyle: String, Codable {
    /// Casual greetings ("Hey!", "Hi there!")
    case casual
    /// Formal greetings ("Good morning, Mr. Smith")
    case formal
    /// Warm/friendly ("Good morning! How are you today?")
    case warm
    /// Minimal (just the information, no fluff)
    case minimal
}

// MARK: - Formality Level

/// Formality level in interactions
public enum FormalityLevel: String, Codable {
    /// Very casual, uses nicknames
    case casual
    /// Friendly but respectful
    case friendly
    /// Professional/polite
    case polite
    /// Formal, uses titles
    case formal
}

// MARK: - Cultural Preferences

/// Cultural preferences and norms for a household member
public struct CulturalPreferences: Codable, Equatable {
    /// Primary language (ISO 639-1 code)
    public var primaryLanguage: String

    /// Additional languages
    public var additionalLanguages: [String]

    /// Privacy orientation (individualist vs collectivist)
    public var privacyOrientation: PrivacyOrientation

    /// Decision-making style in household
    public var decisionStyle: DecisionStyle

    /// Religious/spiritual observances (e.g., "ramadan", "shabbat", "sunday_mass")
    public var observances: [String]

    /// Dietary restrictions/preferences
    public var dietary: [String]

    /// Time format preference (12h vs 24h)
    public var timeFormat24h: Bool

    /// Date format preference
    public var dateFormat: DateFormat

    /// Temperature unit preference
    public var tempUnit: TemperatureUnit

    /// Greeting style preference
    public var greetingStyle: GreetingStyle

    /// Formality level in interactions
    public var formality: FormalityLevel

    /// Respect for hierarchy/elders
    public var hierarchicalRespect: Bool

    /// Gender considerations for interactions
    public var genderConsiderations: String?

    // MARK: - Initializers

    public init(
        primaryLanguage: String = "en",
        additionalLanguages: [String] = [],
        privacyOrientation: PrivacyOrientation = .individualist,
        decisionStyle: DecisionStyle = .individual,
        observances: [String] = [],
        dietary: [String] = [],
        timeFormat24h: Bool = false,
        dateFormat: DateFormat = .monthDayYear,
        tempUnit: TemperatureUnit = .fahrenheit,
        greetingStyle: GreetingStyle = .warm,
        formality: FormalityLevel = .friendly,
        hierarchicalRespect: Bool = false,
        genderConsiderations: String? = nil
    ) {
        self.primaryLanguage = primaryLanguage
        self.additionalLanguages = additionalLanguages
        self.privacyOrientation = privacyOrientation
        self.decisionStyle = decisionStyle
        self.observances = observances
        self.dietary = dietary
        self.timeFormat24h = timeFormat24h
        self.dateFormat = dateFormat
        self.tempUnit = tempUnit
        self.greetingStyle = greetingStyle
        self.formality = formality
        self.hierarchicalRespect = hierarchicalRespect
        self.genderConsiderations = genderConsiderations
    }

    /// Create preferences for a US household
    public static func usDefault() -> CulturalPreferences {
        CulturalPreferences()
    }

    /// Create preferences for a European household
    public static func europeDefault() -> CulturalPreferences {
        CulturalPreferences(
            timeFormat24h: true,
            dateFormat: .dayMonthYear,
            tempUnit: .celsius
        )
    }

    /// Create preferences for an East Asian household
    public static func eastAsiaDefault() -> CulturalPreferences {
        CulturalPreferences(
            privacyOrientation: .collectivist,
            decisionStyle: .hierarchical,
            timeFormat24h: true,
            dateFormat: .yearMonthDay,
            tempUnit: .celsius,
            formality: .polite,
            hierarchicalRespect: true
        )
    }

    /// Create preferences for a Middle Eastern household
    public static func middleEastDefault() -> CulturalPreferences {
        CulturalPreferences(
            privacyOrientation: .familyOriented,
            decisionStyle: .hierarchical,
            timeFormat24h: true,
            dateFormat: .dayMonthYear,
            tempUnit: .celsius,
            formality: .formal,
            hierarchicalRespect: true
        )
    }
}

// MARK: - Schedule Profile

/// Meal schedule
public struct MealSchedule: Codable, Equatable {
    public var breakfast: Int?
    public var lunch: Int?
    public var dinner: Int?
    public var snacks: [Int]

    public init(
        breakfast: Int? = 7,
        lunch: Int? = 12,
        dinner: Int? = 18,
        snacks: [Int] = []
    ) {
        self.breakfast = breakfast
        self.lunch = lunch
        self.dinner = dinner
        self.snacks = snacks
    }
}

/// A time period within a day
public struct TimePeriod: Codable, Equatable {
    /// Start hour (0-23)
    public var startHour: Int
    /// End hour (0-23)
    public var endHour: Int
    /// Days this applies (0 = Sunday, 6 = Saturday)
    public var days: [Int]
    /// Label for this period
    public var label: String

    public init(startHour: Int, endHour: Int, days: [Int], label: String) {
        self.startHour = startHour
        self.endHour = endHour
        self.days = days
        self.label = label
    }
}

/// A recurring event or reminder
public struct RecurringEvent: Codable, Equatable {
    /// Event name
    public var name: String
    /// Time (hour, minute)
    public var hour: Int
    public var minute: Int
    /// Days this occurs (0 = Sunday, 6 = Saturday)
    public var days: [Int]
    /// Whether to announce/remind
    public var remind: Bool
    /// Reminder message
    public var message: String?

    public init(name: String, hour: Int, minute: Int, days: [Int], remind: Bool = true, message: String? = nil) {
        self.name = name
        self.hour = hour
        self.minute = minute
        self.days = days
        self.remind = remind
        self.message = message
    }
}

/// Schedule preferences and patterns for a household member
public struct ScheduleProfile: Codable, Equatable {
    /// Typical wake time (hour, 0-23)
    public var wakeHour: Int

    /// Typical sleep time (hour, 0-23)
    public var sleepHour: Int

    /// Work/school start time (hour, 0-23), if applicable
    public var workStart: Int?

    /// Work/school end time (hour, 0-23), if applicable
    public var workEnd: Int?

    /// Days when work/school schedule applies (0 = Sunday, 6 = Saturday)
    public var workDays: [Int]

    /// Meal times
    public var mealTimes: MealSchedule

    /// Quiet hours start and end (hour, 0-23)
    public var quietHoursStart: Int?
    public var quietHoursEnd: Int?

    /// Focus/do-not-disturb periods
    public var focusPeriods: [TimePeriod]

    /// Recurring events/reminders
    public var recurringEvents: [RecurringEvent]

    /// Timezone (IANA timezone string)
    public var timezone: String

    // MARK: - Initializers

    public init(
        wakeHour: Int = 7,
        sleepHour: Int = 22,
        workStart: Int? = 9,
        workEnd: Int? = 17,
        workDays: [Int] = [1, 2, 3, 4, 5],  // Mon-Fri
        mealTimes: MealSchedule = MealSchedule(),
        quietHoursStart: Int? = 22,
        quietHoursEnd: Int? = 7,
        focusPeriods: [TimePeriod] = [],
        recurringEvents: [RecurringEvent] = [],
        timezone: String = "America/Los_Angeles"
    ) {
        self.wakeHour = wakeHour
        self.sleepHour = sleepHour
        self.workStart = workStart
        self.workEnd = workEnd
        self.workDays = workDays
        self.mealTimes = mealTimes
        self.quietHoursStart = quietHoursStart
        self.quietHoursEnd = quietHoursEnd
        self.focusPeriods = focusPeriods
        self.recurringEvents = recurringEvents
        self.timezone = timezone
    }

    /// Create a schedule for a senior
    public static func senior() -> ScheduleProfile {
        ScheduleProfile(
            wakeHour: 6,
            sleepHour: 21,
            workStart: nil,
            workEnd: nil,
            workDays: [],
            mealTimes: MealSchedule(
                breakfast: 7,
                lunch: 12,
                dinner: 17,
                snacks: [10, 15]
            ),
            quietHoursStart: 21,
            quietHoursEnd: 6
        )
    }

    /// Create a schedule for a child (school-age)
    public static func child() -> ScheduleProfile {
        ScheduleProfile(
            wakeHour: 7,
            sleepHour: 20,
            workStart: 8,   // School
            workEnd: 15,    // School
            workDays: [1, 2, 3, 4, 5],
            quietHoursStart: 20,
            quietHoursEnd: 7,
            focusPeriods: [
                TimePeriod(
                    startHour: 16,
                    endHour: 17,
                    days: [1, 2, 3, 4, 5],
                    label: "Homework time"
                )
            ]
        )
    }

    /// Check if current hour is within quiet hours
    public func isQuietHour(_ hour: Int) -> Bool {
        guard let start = quietHoursStart, let end = quietHoursEnd else {
            return false
        }
        if start <= end {
            return hour >= start && hour < end
        } else {
            // Wraps around midnight (e.g., 22:00 - 07:00)
            return hour >= start || hour < end
        }
    }
}

// MARK: - Household Type

/// Type of household, representing diverse living arrangements
public enum HouseholdType: String, Codable, CaseIterable {
    /// Solo senior living independently (e.g., Ingrid in Denmark)
    case soloSenior = "solo_senior"

    /// Multigenerational extended family (e.g., The Patels in Seattle)
    case multigenerationalExtended = "multigenerational_extended"

    /// LGBTQ+ parents with children (e.g., Jordan & Sam in San Francisco)
    case lgbtqParents = "lgbtq_parents"

    /// Roommates/non-family sharing space (e.g., The Apartment in Tokyo)
    case roommates

    /// Single parent with children (e.g., Maria in Mexico City)
    case singleParent = "single_parent"

    /// Accessibility-focused household (e.g., Michael in London)
    case accessibilityFocused = "accessibility_focused"

    /// Student housing/share house (e.g., The Share House in Melbourne)
    case studentHousing = "student_housing"

    /// Empty nesters/retired couple (e.g., The Johannsens in Stockholm)
    case emptyNesters = "empty_nesters"

    /// Home-based business (e.g., Fatima in Dubai)
    case homeBasedBusiness = "home_based_business"

    /// Rural multigenerational (e.g., The O'Briens in County Kerry)
    case ruralMultigenerational = "rural_multigenerational"

    /// Single professional (e.g., Tim)
    case singleProfessional = "single_professional"

    /// Nuclear family (traditional 2 parents + children)
    case nuclearFamily = "nuclear_family"

    /// Couple without children
    case coupleNoChildren = "couple_no_children"

    /// Blended family (step-parents, custody arrangements)
    case blendedFamily = "blended_family"

    /// Other/custom
    case other

    /// Human-readable description
    public var description: String {
        switch self {
        case .soloSenior: return "Solo senior living independently"
        case .multigenerationalExtended: return "Multigenerational extended family"
        case .lgbtqParents: return "LGBTQ+ parents with children"
        case .roommates: return "Roommates or non-family sharing space"
        case .singleParent: return "Single parent with children"
        case .accessibilityFocused: return "Accessibility-focused household"
        case .studentHousing: return "Student housing or share house"
        case .emptyNesters: return "Empty nesters or retired couple"
        case .homeBasedBusiness: return "Home-based business"
        case .ruralMultigenerational: return "Rural multigenerational household"
        case .singleProfessional: return "Single professional"
        case .nuclearFamily: return "Nuclear family"
        case .coupleNoChildren: return "Couple without children"
        case .blendedFamily: return "Blended family"
        case .other: return "Custom household configuration"
        }
    }

    /// Typical privacy orientation for this household type
    public var typicalPrivacy: PrivacyOrientation {
        switch self {
        case .soloSenior, .lgbtqParents, .roommates, .accessibilityFocused,
             .studentHousing, .emptyNesters, .homeBasedBusiness, .singleProfessional,
             .coupleNoChildren:
            return .individualist
        case .multigenerationalExtended, .singleParent, .nuclearFamily, .blendedFamily:
            return .familyOriented
        case .ruralMultigenerational:
            return .collectivist
        case .other:
            return .individualist
        }
    }

    /// Typical decision style for this household type
    public var typicalDecisionStyle: DecisionStyle {
        switch self {
        case .soloSenior, .roommates, .singleParent, .accessibilityFocused,
             .homeBasedBusiness, .singleProfessional:
            return .individual
        case .lgbtqParents, .emptyNesters, .nuclearFamily, .coupleNoChildren:
            return .partnership
        case .multigenerationalExtended, .ruralMultigenerational:
            return .hierarchical
        case .studentHousing, .blendedFamily:
            return .consensus
        case .other:
            return .individual
        }
    }
}

// MARK: - Household Member

/// A member of the household
public struct HouseholdMember: Codable, Identifiable, Equatable {
    /// Unique identifier
    public let id: UUID

    /// Display name
    public var name: String

    /// Pronouns (e.g., "he/him", "she/her", "they/them")
    public var pronouns: String?

    /// Role in the household
    public var role: MemberRole

    /// Authority level for permissions
    public var authorityLevel: AuthorityLevel

    /// Accessibility requirements
    public var accessibilityProfile: AccessibilityProfile

    /// Cultural preferences
    public var culturalPreferences: CulturalPreferences

    /// Schedule profile
    public var scheduleProfile: ScheduleProfile

    /// Email for notifications (optional)
    public var email: String?

    /// Phone for emergency contact (optional)
    public var phone: String?

    /// Associated voice profile ID (for speaker recognition)
    public var voiceProfileId: String?

    /// Associated face profile ID (for face recognition)
    public var faceProfileId: String?

    /// Custom metadata
    public var metadata: [String: String]

    /// When this member was added
    public let createdAt: Date

    /// Last update timestamp
    public var updatedAt: Date

    // MARK: - Initializers

    public init(
        id: UUID = UUID(),
        name: String,
        pronouns: String? = nil,
        role: MemberRole,
        authorityLevel: AuthorityLevel,
        accessibilityProfile: AccessibilityProfile = AccessibilityProfile(),
        culturalPreferences: CulturalPreferences = CulturalPreferences(),
        scheduleProfile: ScheduleProfile = ScheduleProfile(),
        email: String? = nil,
        phone: String? = nil,
        voiceProfileId: String? = nil,
        faceProfileId: String? = nil,
        metadata: [String: String] = [:],
        createdAt: Date = Date(),
        updatedAt: Date = Date()
    ) {
        self.id = id
        self.name = name
        self.pronouns = pronouns
        self.role = role
        self.authorityLevel = authorityLevel
        self.accessibilityProfile = accessibilityProfile
        self.culturalPreferences = culturalPreferences
        self.scheduleProfile = scheduleProfile
        self.email = email
        self.phone = phone
        self.voiceProfileId = voiceProfileId
        self.faceProfileId = faceProfileId
        self.metadata = metadata
        self.createdAt = createdAt
        self.updatedAt = updatedAt
    }

    /// Create a new owner member
    public static func owner(name: String) -> HouseholdMember {
        HouseholdMember(name: name, role: .owner, authorityLevel: .full)
    }

    /// Create a new admin member
    public static func admin(name: String) -> HouseholdMember {
        HouseholdMember(name: name, role: .admin, authorityLevel: .high)
    }

    /// Create a new regular member
    public static func member(name: String) -> HouseholdMember {
        HouseholdMember(name: name, role: .member, authorityLevel: .standard)
    }

    /// Create a new child member
    public static func child(name: String) -> HouseholdMember {
        var member = HouseholdMember(name: name, role: .child, authorityLevel: .limited)
        member.scheduleProfile = .child()
        return member
    }

    /// Create a new guest member
    public static func guest(name: String) -> HouseholdMember {
        HouseholdMember(name: name, role: .guest, authorityLevel: .minimal)
    }

    /// Check if this member can perform an action requiring the given authority
    public func canPerform(_ required: AuthorityLevel) -> Bool {
        authorityLevel.canPerform(required)
    }
}

// MARK: - Emergency Contact

/// Emergency contact information
public struct EmergencyContact: Codable, Equatable {
    public var name: String
    public var phone: String
    public var relationship: String

    public init(name: String, phone: String, relationship: String) {
        self.name = name
        self.phone = phone
        self.relationship = relationship
    }
}

// MARK: - Household Settings

/// Household-level settings
public struct HouseholdSettings: Codable, Equatable {
    /// Guest mode duration (hours before auto-expiry)
    public var guestExpiryHours: Int

    /// Allow voice enrollment for new members
    public var allowVoiceEnrollment: Bool

    /// Allow face enrollment for new members
    public var allowFaceEnrollment: Bool

    /// Default language for household
    public var defaultLanguage: String

    /// Emergency contacts
    public var emergencyContacts: [EmergencyContact]

    /// Address (for emergency services)
    public var address: String?

    /// Security code (for lock/unlock operations)
    public var securityCode: String?

    public init(
        guestExpiryHours: Int = 24,
        allowVoiceEnrollment: Bool = true,
        allowFaceEnrollment: Bool = true,
        defaultLanguage: String = "en",
        emergencyContacts: [EmergencyContact] = [],
        address: String? = nil,
        securityCode: String? = nil
    ) {
        self.guestExpiryHours = guestExpiryHours
        self.allowVoiceEnrollment = allowVoiceEnrollment
        self.allowFaceEnrollment = allowFaceEnrollment
        self.defaultLanguage = defaultLanguage
        self.emergencyContacts = emergencyContacts
        self.address = address
        self.securityCode = securityCode
    }
}

// MARK: - Household

/// A household with members
public struct Household: Codable, Identifiable {
    /// Unique household identifier
    public let id: UUID

    /// Household name
    public var name: String

    /// Type of household
    public var householdType: HouseholdType

    /// All household members
    public var members: [HouseholdMember]

    /// When this household was created
    public let createdAt: Date

    /// Last update timestamp
    public var updatedAt: Date

    /// Household settings
    public var settings: HouseholdSettings

    // MARK: - Initializers

    public init(
        id: UUID = UUID(),
        name: String,
        householdType: HouseholdType,
        owner: HouseholdMember,
        createdAt: Date = Date(),
        updatedAt: Date = Date(),
        settings: HouseholdSettings = HouseholdSettings()
    ) {
        self.id = id
        self.name = name
        self.householdType = householdType
        self.members = [owner]
        self.createdAt = createdAt
        self.updatedAt = updatedAt
        self.settings = settings
    }

    /// Get a member by ID
    public func getMember(id: UUID) -> HouseholdMember? {
        members.first { $0.id == id }
    }

    /// Get a member by name (case-insensitive)
    public func getMemberByName(_ name: String) -> HouseholdMember? {
        let nameLower = name.lowercased()
        return members.first { $0.name.lowercased() == nameLower }
    }

    /// Get members with a specific role
    public func membersWithRole(_ role: MemberRole) -> [HouseholdMember] {
        members.filter { $0.role == role }
    }

    /// Get the primary owner
    public var owner: HouseholdMember? {
        members.first { $0.role == .owner }
    }

    /// Get all admins (including owner)
    public var admins: [HouseholdMember] {
        members.filter { $0.role == .owner || $0.role == .admin }
    }

    /// Add a member
    public mutating func addMember(_ member: HouseholdMember) {
        members.append(member)
        updatedAt = Date()
    }

    /// Remove a member by ID
    @discardableResult
    public mutating func removeMember(id: UUID) -> HouseholdMember? {
        if let index = members.firstIndex(where: { $0.id == id }) {
            updatedAt = Date()
            return members.remove(at: index)
        }
        return nil
    }
}

/*
 * 鏡
 * Every household is unique. Kagami adapts to all of them.
 * Privacy IS safety. h(x) >= 0. Always.
 */
