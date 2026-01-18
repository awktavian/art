//
// HouseholdModels.swift — Household Domain Models for Adaptive UX
//
// Models for household members, cultural preferences, and accessibility.
//
// Colony: Symbiote (e3) — Theory of Mind
//
// h(x) >= 0. For EVERYONE.
//

import Foundation
import SwiftUI

// MARK: - Household Member

/// Represents a household member with their preferences and accessibility needs
struct HouseholdMember: Identifiable, Equatable, Sendable {
    let id: String
    let name: String
    let pronouns: Pronouns
    let role: MemberRole
    let authorityLevel: AuthorityLevel
    let accessibilityProfile: AccessibilityProfile
    let culturalPreferences: CulturalPreferences
    let scheduleProfile: ScheduleProfile

    static func == (lhs: HouseholdMember, rhs: HouseholdMember) -> Bool {
        lhs.id == rhs.id
    }
}

// MARK: - Pronouns

/// Pronoun preferences for a household member
struct Pronouns: Equatable, Sendable {
    let subject: String    // he, she, they
    let object: String     // him, her, them
    let possessive: String // his, her, their

    static let heHim = Pronouns(subject: "he", object: "him", possessive: "his")
    static let sheHer = Pronouns(subject: "she", object: "her", possessive: "her")
    static let theyThem = Pronouns(subject: "they", object: "them", possessive: "their")
}

// MARK: - Member Role

/// Role of a member within the household
enum MemberRole: String, CaseIterable, Sendable {
    case owner
    case admin
    case member
    case child
    case guest
    case pet

    var displayName: String {
        switch self {
        case .owner: return "Owner"
        case .admin: return "Admin"
        case .member: return "Member"
        case .child: return "Child"
        case .guest: return "Guest"
        case .pet: return "Pet"
        }
    }
}

// MARK: - Authority Level

/// Level of control authority within the household
enum AuthorityLevel: Int, Comparable, Sendable {
    case minimal = 0   // Can only view
    case limited = 1   // Can control limited devices
    case standard = 2  // Normal member control
    case elevated = 3  // Can manage most settings
    case admin = 4     // Full control

    static func < (lhs: AuthorityLevel, rhs: AuthorityLevel) -> Bool {
        lhs.rawValue < rhs.rawValue
    }
}

// MARK: - Accessibility Profile

/// Accessibility needs and preferences
struct AccessibilityProfile: Equatable, Sendable {
    let visionLevel: VisionLevel
    let motorControl: MotorControl
    let cognitiveNeeds: CognitiveNeeds
    let hearingLevel: HearingLevel

    init(
        visionLevel: VisionLevel = .full,
        motorControl: MotorControl = .full,
        cognitiveNeeds: CognitiveNeeds = .standard,
        hearingLevel: HearingLevel = .full
    ) {
        self.visionLevel = visionLevel
        self.motorControl = motorControl
        self.cognitiveNeeds = cognitiveNeeds
        self.hearingLevel = hearingLevel
    }

    static let standard = AccessibilityProfile()
    static let lowVision = AccessibilityProfile(visionLevel: .lowVision)
    static let blind = AccessibilityProfile(visionLevel: .blind)
    static let hardOfHearing = AccessibilityProfile(hearingLevel: .limited)
    static let deaf = AccessibilityProfile(hearingLevel: .deaf)
    static let motorImpaired = AccessibilityProfile(motorControl: .limited)
    static let cognitiveSupport = AccessibilityProfile(cognitiveNeeds: .simplified)
}

/// Vision capability level
enum VisionLevel: String, Sendable {
    case full
    case lowVision
    case blind
}

/// Motor control capability
enum MotorControl: String, Sendable {
    case full
    case limited
    case voiceOnly
    case switchControl
}

/// Cognitive support needs
enum CognitiveNeeds: String, Sendable {
    case standard
    case simplified
    case detailed
}

/// Hearing capability level
enum HearingLevel: String, Sendable {
    case full
    case limited
    case deaf
}

// MARK: - Cultural Preferences

/// Cultural and localization preferences
struct CulturalPreferences: Equatable, Sendable {
    let primaryLanguage: String
    let privacyOrientation: PrivacyOrientation
    let timeFormat: TimeFormat
    let temperatureUnit: TemperatureUnit

    init(
        primaryLanguage: String = "en",
        privacyOrientation: PrivacyOrientation = .balanced,
        timeFormat: TimeFormat = .system,
        temperatureUnit: TemperatureUnit = .system
    ) {
        self.primaryLanguage = primaryLanguage
        self.privacyOrientation = privacyOrientation
        self.timeFormat = timeFormat
        self.temperatureUnit = temperatureUnit
    }
}

/// Privacy orientation preferences
enum PrivacyOrientation: String, Sendable {
    case individualist  // Prefer private spaces, explicit sharing
    case communalist    // Comfortable with shared spaces, open by default
    case collectivist   // Community-oriented, family-first
    case hierarchical   // Respects hierarchy and formal address
    case balanced       // Context-dependent sharing
}

/// Time format preference
enum TimeFormat: String, Sendable {
    case system         // Use system preference
    case twelveHour     // 12-hour AM/PM
    case twentyFourHour // 24-hour
}

/// Temperature unit preference
enum TemperatureUnit: String, Sendable {
    case system      // Use system preference
    case fahrenheit
    case celsius
}

// MARK: - Schedule Profile

/// Schedule preferences and routines
struct ScheduleProfile: Equatable, Sendable {
    let wakeTime: Date?
    let sleepTime: Date?
    let workStartTime: Date?
    let workEndTime: Date?
    let isNightOwl: Bool

    /// Alias for sleepTime for backward compatibility
    var typicalSleepTime: Date? { sleepTime }

    /// Alias for wakeTime for backward compatibility
    var typicalWakeTime: Date? { wakeTime }

    init(
        wakeTime: Date? = nil,
        sleepTime: Date? = nil,
        workStartTime: Date? = nil,
        workEndTime: Date? = nil,
        isNightOwl: Bool = false
    ) {
        self.wakeTime = wakeTime
        self.sleepTime = sleepTime
        self.workStartTime = workStartTime
        self.workEndTime = workEndTime
        self.isNightOwl = isNightOwl
    }
}

// MARK: - Household

/// Represents a household with its members and type
struct Household: Identifiable, Equatable, Sendable {
    let id: String
    let name: String
    let householdType: HouseholdType
    let members: [HouseholdMember]

    static func == (lhs: Household, rhs: Household) -> Bool {
        lhs.id == rhs.id
    }
}

/// Type of household
enum HouseholdType: String, CaseIterable, Sendable {
    case family         // Traditional family household
    case roommates      // Shared housing
    case couple         // Two-person household
    case multigenerational // Multiple generations
    case single         // Single occupant

    var displayName: String {
        switch self {
        case .family: return "Family"
        case .roommates: return "Roommates"
        case .couple: return "Couple"
        case .multigenerational: return "Multigenerational"
        case .single: return "Single"
        }
    }
}

// MARK: - Content Type

/// Type of content for privacy filtering
enum ContentType: String, Sendable {
    case activity       // Activity logs
    case presence       // Presence information
    case schedule       // Schedule data
    case preferences    // Personal preferences
    case control        // Device control
}

/*
 * 鏡
 * h(x) >= 0. For EVERYONE.
 */
