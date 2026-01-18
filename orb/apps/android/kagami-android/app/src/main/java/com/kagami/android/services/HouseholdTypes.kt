/**
 * Household & Accessibility Models for Kagami Android
 *
 * These types mirror the Rust household.rs definitions to enable
 * full accessibility profile support and multi-user household modes.
 *
 * Colony: Hearth (e5) -- Home and belonging
 *
 * Design Philosophy:
 * - Local-first: Works without internet via mesh networking
 * - Culturally adaptive: Respects privacy norms from individualist to collectivist
 * - Accessibility-native: WCAG AAA as craft, not compliance
 * - Role-aware: Different household members have different needs and permissions
 *
 * h(x) >= 0. Always.
 * Privacy IS safety.
 */

package com.kagami.android.services

import java.util.UUID
import java.util.Date

// =============================================================================
// MEMBER ROLE
// =============================================================================

/**
 * Role of a household member determining base permissions
 */
enum class MemberRole {
    /** Primary household owner with full control */
    OWNER,
    /** Administrator with nearly full control (e.g., spouse, partner) */
    ADMIN,
    /** Regular household member (e.g., adult family member) */
    MEMBER,
    /** Child with restricted permissions */
    CHILD,
    /** Guest with minimal, temporary access */
    GUEST;

    /** Returns the default authority level for this role */
    val defaultAuthority: AuthorityLevel
        get() = when (this) {
            OWNER -> AuthorityLevel.FULL
            ADMIN -> AuthorityLevel.HIGH
            MEMBER -> AuthorityLevel.STANDARD
            CHILD -> AuthorityLevel.LIMITED
            GUEST -> AuthorityLevel.MINIMAL
        }

    /** Returns true if this role can modify household settings */
    val canModifyHousehold: Boolean
        get() = this == OWNER || this == ADMIN

    /** Returns true if this role can add/remove members */
    val canManageMembers: Boolean
        get() = this == OWNER || this == ADMIN

    /** Returns true if this role can access security features */
    val canAccessSecurity: Boolean
        get() = this == OWNER || this == ADMIN || this == MEMBER
}

// =============================================================================
// AUTHORITY LEVEL
// =============================================================================

/**
 * Fine-grained authority level for permissions
 */
enum class AuthorityLevel(val level: Int) {
    /** No permissions (blocked) */
    NONE(0),
    /** Minimal permissions (guests, temporary access) */
    MINIMAL(20),
    /** Limited permissions (children, restricted users) */
    LIMITED(40),
    /** Standard permissions (regular household members) */
    STANDARD(60),
    /** High permissions (admins, trusted adults) */
    HIGH(80),
    /** Full permissions (owner only) */
    FULL(100);

    /** Check if this authority level can perform an action requiring [required] level */
    fun canPerform(required: AuthorityLevel): Boolean = level >= required.level
}

// =============================================================================
// INPUT METHOD
// =============================================================================

/**
 * Input method preferences for accessibility
 */
enum class InputMethod {
    /** Touch screen */
    TOUCH,
    /** Physical keyboard */
    KEYBOARD,
    /** Mouse/trackpad */
    POINTER,
    /** Voice commands */
    VOICE,
    /** Eye tracking */
    EYE_TRACKING,
    /** Switch control */
    SWITCH_CONTROL,
    /** Gesture recognition */
    GESTURE
}

// =============================================================================
// ACCESSIBILITY PROFILE
// =============================================================================

/**
 * Accessibility requirements and preferences for a household member
 */
data class AccessibilityProfile(
    /** Minimum font size in pixels (default: 16) */
    val minFontSize: Int = 16,

    /** Minimum contrast ratio (WCAG: 4.5 AA, 7.0 AAA) */
    val minContrastRatio: Double = 4.5,

    /** Minimum touch target size in pixels (default: 44) */
    val minTouchTarget: Int = 44,

    /** Prefers reduced motion */
    val reducedMotion: Boolean = false,

    /** Prefers high contrast mode */
    val highContrast: Boolean = false,

    /** Vision impairment level (0 = none, 1 = mild, 2 = moderate, 3 = severe) */
    val visionImpairment: Int = 0,

    /** Hearing impairment level (0 = none, 1 = mild, 2 = moderate, 3 = severe) */
    val hearingImpairment: Int = 0,

    /** Motor impairment level (0 = none, 1 = mild, 2 = moderate, 3 = severe) */
    val motorImpairment: Int = 0,

    /** Cognitive considerations (memory, processing speed, etc.) */
    val cognitiveConsiderations: List<String> = emptyList(),

    /** Preferred input methods */
    val preferredInputs: List<InputMethod> = listOf(InputMethod.TOUCH, InputMethod.VOICE),

    /** Screen reader in use */
    val screenReader: Boolean = false,

    /** Voice control as primary input */
    val voicePrimary: Boolean = false,

    /** Default audio volume (0-100) */
    val defaultVolume: Int = 70,

    /** Prefer slow, clear speech */
    val slowSpeech: Boolean = false
) {
    companion object {
        /** Create a profile for a senior with common age-related needs */
        fun senior() = AccessibilityProfile(
            minFontSize = 24,
            minContrastRatio = 7.0,  // WCAG AAA
            minTouchTarget = 48,
            reducedMotion = true,
            highContrast = true,
            visionImpairment = 1,
            hearingImpairment = 1,
            cognitiveConsiderations = listOf("memory_support"),
            preferredInputs = listOf(InputMethod.VOICE, InputMethod.TOUCH),
            voicePrimary = true,
            defaultVolume = 80,
            slowSpeech = true
        )

        /** Create a profile for someone with visual impairment */
        fun visualImpairment(severity: Int): AccessibilityProfile {
            val fontSizes = listOf(16, 24, 32, 40)
            return AccessibilityProfile(
                minFontSize = fontSizes[severity.coerceIn(0, 3)],
                minContrastRatio = 7.0,
                minTouchTarget = 48,
                highContrast = severity >= 2,
                visionImpairment = severity,
                preferredInputs = listOf(InputMethod.VOICE),
                screenReader = severity >= 2,
                voicePrimary = severity >= 2
            )
        }

        /** Create a profile for someone with motor impairment */
        fun motorImpairment(severity: Int): AccessibilityProfile {
            val touchTargets = listOf(44, 48, 56, 64)
            return AccessibilityProfile(
                minTouchTarget = touchTargets[severity.coerceIn(0, 3)],
                reducedMotion = true,
                motorImpairment = severity,
                preferredInputs = listOf(InputMethod.VOICE, InputMethod.SWITCH_CONTROL),
                voicePrimary = severity >= 2
            )
        }
    }
}

// =============================================================================
// PRIVACY ORIENTATION
// =============================================================================

/**
 * Privacy orientation based on cultural norms
 */
enum class PrivacyOrientation {
    /** Strong individual privacy (typical in US, Germany, Netherlands) */
    INDIVIDUALIST,
    /** Moderate privacy with family sharing (typical in Southern Europe, Latin America) */
    FAMILY_ORIENTED,
    /** Collectivist with shared household awareness (typical in East Asia, Middle East) */
    COLLECTIVIST
}

// =============================================================================
// DECISION STYLE
// =============================================================================

/**
 * Decision-making style in household
 */
enum class DecisionStyle {
    /** Individual autonomy */
    INDIVIDUAL,
    /** Joint decisions between partners */
    PARTNERSHIP,
    /** Hierarchical (elders consulted, head decides) */
    HIERARCHICAL,
    /** Consensus-based (everyone has input) */
    CONSENSUS
}

// =============================================================================
// DATE FORMAT
// =============================================================================

/**
 * Date format preference
 */
enum class DateFormatPref {
    /** MM/DD/YYYY (US) */
    MONTH_DAY_YEAR,
    /** DD/MM/YYYY (Europe, most of world) */
    DAY_MONTH_YEAR,
    /** YYYY-MM-DD (ISO 8601) */
    YEAR_MONTH_DAY
}

// =============================================================================
// TEMPERATURE UNIT
// =============================================================================

/**
 * Temperature unit preference
 */
enum class TemperatureUnit {
    FAHRENHEIT,
    CELSIUS
}

// =============================================================================
// GREETING STYLE
// =============================================================================

/**
 * Greeting style preference
 */
enum class GreetingStyle {
    /** Casual greetings ("Hey!", "Hi there!") */
    CASUAL,
    /** Formal greetings ("Good morning, Mr. Smith") */
    FORMAL,
    /** Warm/friendly ("Good morning! How are you today?") */
    WARM,
    /** Minimal (just the information, no fluff) */
    MINIMAL
}

// =============================================================================
// FORMALITY LEVEL
// =============================================================================

/**
 * Formality level in interactions
 */
enum class FormalityLevel {
    /** Very casual, uses nicknames */
    CASUAL,
    /** Friendly but respectful */
    FRIENDLY,
    /** Professional/polite */
    POLITE,
    /** Formal, uses titles */
    FORMAL
}

// =============================================================================
// CULTURAL PREFERENCES
// =============================================================================

/**
 * Cultural preferences and norms for a household member
 */
data class CulturalPreferences(
    /** Primary language (ISO 639-1 code) */
    val primaryLanguage: String = "en",

    /** Additional languages */
    val additionalLanguages: List<String> = emptyList(),

    /** Privacy orientation (individualist vs collectivist) */
    val privacyOrientation: PrivacyOrientation = PrivacyOrientation.INDIVIDUALIST,

    /** Decision-making style in household */
    val decisionStyle: DecisionStyle = DecisionStyle.INDIVIDUAL,

    /** Religious/spiritual observances (e.g., "ramadan", "shabbat", "sunday_mass") */
    val observances: List<String> = emptyList(),

    /** Dietary restrictions/preferences */
    val dietary: List<String> = emptyList(),

    /** Time format preference (12h vs 24h) */
    val timeFormat24h: Boolean = false,

    /** Date format preference */
    val dateFormat: DateFormatPref = DateFormatPref.MONTH_DAY_YEAR,

    /** Temperature unit preference */
    val tempUnit: TemperatureUnit = TemperatureUnit.FAHRENHEIT,

    /** Greeting style preference */
    val greetingStyle: GreetingStyle = GreetingStyle.WARM,

    /** Formality level in interactions */
    val formality: FormalityLevel = FormalityLevel.FRIENDLY,

    /** Respect for hierarchy/elders */
    val hierarchicalRespect: Boolean = false,

    /** Gender considerations for interactions */
    val genderConsiderations: String? = null
) {
    companion object {
        /** Create preferences for a US household */
        fun usDefault() = CulturalPreferences()

        /** Create preferences for a European household */
        fun europeDefault() = CulturalPreferences(
            timeFormat24h = true,
            dateFormat = DateFormatPref.DAY_MONTH_YEAR,
            tempUnit = TemperatureUnit.CELSIUS
        )

        /** Create preferences for an East Asian household */
        fun eastAsiaDefault() = CulturalPreferences(
            privacyOrientation = PrivacyOrientation.COLLECTIVIST,
            decisionStyle = DecisionStyle.HIERARCHICAL,
            timeFormat24h = true,
            dateFormat = DateFormatPref.YEAR_MONTH_DAY,
            tempUnit = TemperatureUnit.CELSIUS,
            formality = FormalityLevel.POLITE,
            hierarchicalRespect = true
        )

        /** Create preferences for a Middle Eastern household */
        fun middleEastDefault() = CulturalPreferences(
            privacyOrientation = PrivacyOrientation.FAMILY_ORIENTED,
            decisionStyle = DecisionStyle.HIERARCHICAL,
            timeFormat24h = true,
            dateFormat = DateFormatPref.DAY_MONTH_YEAR,
            tempUnit = TemperatureUnit.CELSIUS,
            formality = FormalityLevel.FORMAL,
            hierarchicalRespect = true
        )
    }
}

// =============================================================================
// SCHEDULE PROFILE
// =============================================================================

/**
 * Meal schedule
 */
data class MealSchedule(
    val breakfast: Int? = 7,
    val lunch: Int? = 12,
    val dinner: Int? = 18,
    val snacks: List<Int> = emptyList()
)

/**
 * A time period within a day
 */
data class TimePeriod(
    /** Start hour (0-23) */
    val startHour: Int,
    /** End hour (0-23) */
    val endHour: Int,
    /** Days this applies (0 = Sunday, 6 = Saturday) */
    val days: List<Int>,
    /** Label for this period */
    val label: String
)

/**
 * A recurring event or reminder
 */
data class RecurringEvent(
    /** Event name */
    val name: String,
    /** Hour (0-23) */
    val hour: Int,
    /** Minute (0-59) */
    val minute: Int,
    /** Days this occurs (0 = Sunday, 6 = Saturday) */
    val days: List<Int>,
    /** Whether to announce/remind */
    val remind: Boolean = true,
    /** Reminder message */
    val message: String? = null
)

/**
 * Schedule preferences and patterns for a household member
 */
data class ScheduleProfile(
    /** Typical wake time (hour, 0-23) */
    val wakeHour: Int = 7,

    /** Typical sleep time (hour, 0-23) */
    val sleepHour: Int = 22,

    /** Work/school start time (hour, 0-23), if applicable */
    val workStart: Int? = 9,

    /** Work/school end time (hour, 0-23), if applicable */
    val workEnd: Int? = 17,

    /** Days when work/school schedule applies (0 = Sunday, 6 = Saturday) */
    val workDays: List<Int> = listOf(1, 2, 3, 4, 5),  // Mon-Fri

    /** Meal times */
    val mealTimes: MealSchedule = MealSchedule(),

    /** Quiet hours start (hour, 0-23) */
    val quietHoursStart: Int? = 22,

    /** Quiet hours end (hour, 0-23) */
    val quietHoursEnd: Int? = 7,

    /** Focus/do-not-disturb periods */
    val focusPeriods: List<TimePeriod> = emptyList(),

    /** Recurring events/reminders */
    val recurringEvents: List<RecurringEvent> = emptyList(),

    /** Timezone (IANA timezone string) */
    val timezone: String = "America/Los_Angeles"
) {
    /** Check if current hour is within quiet hours */
    fun isQuietHour(hour: Int): Boolean {
        val start = quietHoursStart ?: return false
        val end = quietHoursEnd ?: return false

        return if (start <= end) {
            hour >= start && hour < end
        } else {
            // Wraps around midnight (e.g., 22:00 - 07:00)
            hour >= start || hour < end
        }
    }

    companion object {
        /** Create a schedule for a senior */
        fun senior() = ScheduleProfile(
            wakeHour = 6,
            sleepHour = 21,
            workStart = null,
            workEnd = null,
            workDays = emptyList(),
            mealTimes = MealSchedule(
                breakfast = 7,
                lunch = 12,
                dinner = 17,
                snacks = listOf(10, 15)
            ),
            quietHoursStart = 21,
            quietHoursEnd = 6
        )

        /** Create a schedule for a child (school-age) */
        fun child() = ScheduleProfile(
            wakeHour = 7,
            sleepHour = 20,
            workStart = 8,   // School
            workEnd = 15,    // School
            workDays = listOf(1, 2, 3, 4, 5),
            quietHoursStart = 20,
            quietHoursEnd = 7,
            focusPeriods = listOf(
                TimePeriod(
                    startHour = 16,
                    endHour = 17,
                    days = listOf(1, 2, 3, 4, 5),
                    label = "Homework time"
                )
            )
        )
    }
}

// =============================================================================
// HOUSEHOLD TYPE
// =============================================================================

/**
 * Type of household, representing diverse living arrangements
 */
enum class HouseholdType(val description: String) {
    /** Solo senior living independently (e.g., Ingrid in Denmark) */
    SOLO_SENIOR("Solo senior living independently"),

    /** Multigenerational extended family (e.g., The Patels in Seattle) */
    MULTIGENERATIONAL_EXTENDED("Multigenerational extended family"),

    /** LGBTQ+ parents with children (e.g., Jordan & Sam in San Francisco) */
    LGBTQ_PARENTS("LGBTQ+ parents with children"),

    /** Roommates/non-family sharing space (e.g., The Apartment in Tokyo) */
    ROOMMATES("Roommates or non-family sharing space"),

    /** Single parent with children (e.g., Maria in Mexico City) */
    SINGLE_PARENT("Single parent with children"),

    /** Accessibility-focused household (e.g., Michael in London) */
    ACCESSIBILITY_FOCUSED("Accessibility-focused household"),

    /** Student housing/share house (e.g., The Share House in Melbourne) */
    STUDENT_HOUSING("Student housing or share house"),

    /** Empty nesters/retired couple (e.g., The Johannsens in Stockholm) */
    EMPTY_NESTERS("Empty nesters or retired couple"),

    /** Home-based business (e.g., Fatima in Dubai) */
    HOME_BASED_BUSINESS("Home-based business"),

    /** Rural multigenerational (e.g., The O'Briens in County Kerry) */
    RURAL_MULTIGENERATIONAL("Rural multigenerational household"),

    /** Single professional (e.g., Tim) */
    SINGLE_PROFESSIONAL("Single professional"),

    /** Nuclear family (traditional 2 parents + children) */
    NUCLEAR_FAMILY("Nuclear family"),

    /** Couple without children */
    COUPLE_NO_CHILDREN("Couple without children"),

    /** Blended family (step-parents, custody arrangements) */
    BLENDED_FAMILY("Blended family"),

    /** Other/custom */
    OTHER("Custom household configuration");

    /** Typical privacy orientation for this household type */
    val typicalPrivacy: PrivacyOrientation
        get() = when (this) {
            SOLO_SENIOR, LGBTQ_PARENTS, ROOMMATES, ACCESSIBILITY_FOCUSED,
            STUDENT_HOUSING, EMPTY_NESTERS, HOME_BASED_BUSINESS, SINGLE_PROFESSIONAL,
            COUPLE_NO_CHILDREN -> PrivacyOrientation.INDIVIDUALIST
            MULTIGENERATIONAL_EXTENDED, SINGLE_PARENT, NUCLEAR_FAMILY, BLENDED_FAMILY ->
                PrivacyOrientation.FAMILY_ORIENTED
            RURAL_MULTIGENERATIONAL -> PrivacyOrientation.COLLECTIVIST
            OTHER -> PrivacyOrientation.INDIVIDUALIST
        }

    /** Typical decision style for this household type */
    val typicalDecisionStyle: DecisionStyle
        get() = when (this) {
            SOLO_SENIOR, ROOMMATES, SINGLE_PARENT, ACCESSIBILITY_FOCUSED,
            HOME_BASED_BUSINESS, SINGLE_PROFESSIONAL -> DecisionStyle.INDIVIDUAL
            LGBTQ_PARENTS, EMPTY_NESTERS, NUCLEAR_FAMILY, COUPLE_NO_CHILDREN ->
                DecisionStyle.PARTNERSHIP
            MULTIGENERATIONAL_EXTENDED, RURAL_MULTIGENERATIONAL -> DecisionStyle.HIERARCHICAL
            STUDENT_HOUSING, BLENDED_FAMILY -> DecisionStyle.CONSENSUS
            OTHER -> DecisionStyle.INDIVIDUAL
        }
}

// =============================================================================
// HOUSEHOLD MEMBER
// =============================================================================

/**
 * A member of the household
 */
data class HouseholdMember(
    /** Unique identifier */
    val id: UUID = UUID.randomUUID(),

    /** Display name */
    val name: String,

    /** Pronouns (e.g., "he/him", "she/her", "they/them") */
    val pronouns: String? = null,

    /** Role in the household */
    val role: MemberRole,

    /** Authority level for permissions */
    val authorityLevel: AuthorityLevel,

    /** Accessibility requirements */
    val accessibilityProfile: AccessibilityProfile = AccessibilityProfile(),

    /** Cultural preferences */
    val culturalPreferences: CulturalPreferences = CulturalPreferences(),

    /** Schedule profile */
    val scheduleProfile: ScheduleProfile = ScheduleProfile(),

    /** Email for notifications (optional) */
    val email: String? = null,

    /** Phone for emergency contact (optional) */
    val phone: String? = null,

    /** Associated voice profile ID (for speaker recognition) */
    val voiceProfileId: String? = null,

    /** Associated face profile ID (for face recognition) */
    val faceProfileId: String? = null,

    /** Custom metadata */
    val metadata: Map<String, String> = emptyMap(),

    /** When this member was added */
    val createdAt: Date = Date(),

    /** Last update timestamp */
    val updatedAt: Date = Date()
) {
    /** Check if this member can perform an action requiring the given authority */
    fun canPerform(required: AuthorityLevel): Boolean = authorityLevel.canPerform(required)

    companion object {
        /** Create a new owner member */
        fun owner(name: String) = HouseholdMember(
            name = name,
            role = MemberRole.OWNER,
            authorityLevel = AuthorityLevel.FULL
        )

        /** Create a new admin member */
        fun admin(name: String) = HouseholdMember(
            name = name,
            role = MemberRole.ADMIN,
            authorityLevel = AuthorityLevel.HIGH
        )

        /** Create a new regular member */
        fun member(name: String) = HouseholdMember(
            name = name,
            role = MemberRole.MEMBER,
            authorityLevel = AuthorityLevel.STANDARD
        )

        /** Create a new child member */
        fun child(name: String) = HouseholdMember(
            name = name,
            role = MemberRole.CHILD,
            authorityLevel = AuthorityLevel.LIMITED,
            scheduleProfile = ScheduleProfile.child()
        )

        /** Create a new guest member */
        fun guest(name: String) = HouseholdMember(
            name = name,
            role = MemberRole.GUEST,
            authorityLevel = AuthorityLevel.MINIMAL
        )
    }
}

// =============================================================================
// EMERGENCY CONTACT
// =============================================================================

/**
 * Emergency contact information
 */
data class EmergencyContact(
    val name: String,
    val phone: String,
    val relationship: String
)

// =============================================================================
// HOUSEHOLD SETTINGS
// =============================================================================

/**
 * Household-level settings
 */
data class HouseholdSettings(
    /** Guest mode duration (hours before auto-expiry) */
    val guestExpiryHours: Int = 24,

    /** Allow voice enrollment for new members */
    val allowVoiceEnrollment: Boolean = true,

    /** Allow face enrollment for new members */
    val allowFaceEnrollment: Boolean = true,

    /** Default language for household */
    val defaultLanguage: String = "en",

    /** Emergency contacts */
    val emergencyContacts: List<EmergencyContact> = emptyList(),

    /** Address (for emergency services) */
    val address: String? = null,

    /** Security code (for lock/unlock operations) */
    val securityCode: String? = null
)

// =============================================================================
// HOUSEHOLD
// =============================================================================

/**
 * A household with members
 */
data class Household(
    /** Unique household identifier */
    val id: UUID = UUID.randomUUID(),

    /** Household name */
    val name: String,

    /** Type of household */
    val householdType: HouseholdType,

    /** All household members */
    val members: MutableList<HouseholdMember> = mutableListOf(),

    /** When this household was created */
    val createdAt: Date = Date(),

    /** Last update timestamp */
    var updatedAt: Date = Date(),

    /** Household settings */
    val settings: HouseholdSettings = HouseholdSettings()
) {
    /** Get a member by ID */
    fun getMember(id: UUID): HouseholdMember? = members.find { it.id == id }

    /** Get a member by name (case-insensitive) */
    fun getMemberByName(name: String): HouseholdMember? {
        val nameLower = name.lowercase()
        return members.find { it.name.lowercase() == nameLower }
    }

    /** Get members with a specific role */
    fun membersWithRole(role: MemberRole): List<HouseholdMember> =
        members.filter { it.role == role }

    /** Get the primary owner */
    val owner: HouseholdMember?
        get() = members.find { it.role == MemberRole.OWNER }

    /** Get all admins (including owner) */
    val admins: List<HouseholdMember>
        get() = members.filter { it.role == MemberRole.OWNER || it.role == MemberRole.ADMIN }

    /** Add a member */
    fun addMember(member: HouseholdMember) {
        members.add(member)
        updatedAt = Date()
    }

    /** Remove a member by ID */
    fun removeMember(id: UUID): HouseholdMember? {
        val index = members.indexOfFirst { it.id == id }
        return if (index >= 0) {
            updatedAt = Date()
            members.removeAt(index)
        } else null
    }

    companion object {
        /** Create a new household with an owner */
        fun create(name: String, householdType: HouseholdType, owner: HouseholdMember): Household {
            val household = Household(name = name, householdType = householdType)
            household.members.add(owner)
            return household
        }
    }
}

// Kagami (Mirror)
// Every household is unique. Kagami adapts to all of them.
// Privacy IS safety. h(x) >= 0. Always.
