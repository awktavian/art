//! Household Management System
//!
//! Manages household members, roles, and permissions with CRDT-compatible
//! synchronization for mesh networking.
//!
//! # Overview
//!
//! This module provides:
//! - [`HouseholdMember`] - Individual household members with profiles
//! - [`Household`] - The complete household with CRDT sync support
//! - [`HouseholdType`] - 10 diverse household archetypes
//! - [`MemberRole`] / [`AuthorityLevel`] - Permission hierarchies
//! - Profile structs for accessibility, culture, and scheduling
//!
//! # Design Philosophy
//!
//! - **Local-first**: Works without internet via mesh networking
//! - **Culturally adaptive**: Respects privacy norms from individualist to collectivist societies
//! - **Accessibility-native**: WCAG AAA as craft, not compliance
//! - **Role-aware**: Different members have different needs and permissions
//!
//! # Safety
//!
//! ```text
//! h(x) >= 0 always
//! Privacy IS safety.
//! ```
//!
//! Each person owns their own information. Sharing requires explicit consent.
//!
//! # Example
//!
//! ```rust
//! use kagami_hub::household::{
//!     Household, HouseholdMember, HouseholdType, MemberRole, AuthorityLevel,
//!     AccessibilityProfile, CulturalPreferences, ScheduleProfile,
//! };
//! use uuid::Uuid;
//!
//! // Create the primary household member
//! let owner = HouseholdMember::new(
//!     "Tim".to_string(),
//!     MemberRole::Owner,
//!     AuthorityLevel::Full,
//! );
//!
//! // Create the household
//! let household = Household::new(
//!     "Tim's House".to_string(),
//!     HouseholdType::SingleProfessional,
//!     owner,
//! );
//!
//! assert_eq!(household.members().len(), 1);
//! assert!(household.get_member_by_name("Tim").is_some());
//! ```
//!
//! # CRDT Synchronization
//!
//! The household state uses OR-Set semantics for member management,
//! ensuring eventual consistency across mesh-connected hubs.
//!
//! ```text
//! Hub A adds member → syncs to Hub B → both have member
//! Hub A removes member → syncs to Hub B → both remove member
//! Concurrent add/remove → add wins (observed-remove)
//! ```
//!
//! Colony: Hearth (e₅) — Home and belonging
//!
//! η → s → μ → a → η′
//! h(x) ≥ 0. Always.

use serde::{Deserialize, Serialize};
use std::collections::HashMap;
use std::time::{SystemTime, UNIX_EPOCH};

#[cfg(feature = "mesh")]
use uuid::Uuid;

#[cfg(not(feature = "mesh"))]
use std::fmt;

// ============================================================================
// UUID Compatibility (when mesh feature is disabled)
// ============================================================================

#[cfg(not(feature = "mesh"))]
#[derive(Debug, Clone, Copy, PartialEq, Eq, Hash, Serialize, Deserialize)]
pub struct Uuid([u8; 16]);

#[cfg(not(feature = "mesh"))]
impl Uuid {
    /// Create a new random UUID (v4)
    pub fn new_v4() -> Self {
        use std::collections::hash_map::DefaultHasher;
        use std::hash::{Hash, Hasher};

        let mut hasher = DefaultHasher::new();
        SystemTime::now()
            .duration_since(UNIX_EPOCH)
            .unwrap()
            .as_nanos()
            .hash(&mut hasher);
        std::process::id().hash(&mut hasher);

        let hash = hasher.finish();
        let mut bytes = [0u8; 16];
        bytes[0..8].copy_from_slice(&hash.to_le_bytes());
        bytes[8..16].copy_from_slice(&hash.to_be_bytes());

        // Set version (4) and variant (RFC 4122)
        bytes[6] = (bytes[6] & 0x0f) | 0x40;
        bytes[8] = (bytes[8] & 0x3f) | 0x80;

        Self(bytes)
    }
}

#[cfg(not(feature = "mesh"))]
impl fmt::Display for Uuid {
    fn fmt(&self, f: &mut fmt::Formatter<'_>) -> fmt::Result {
        write!(
            f,
            "{:08x}-{:04x}-{:04x}-{:04x}-{:012x}",
            u32::from_be_bytes([self.0[0], self.0[1], self.0[2], self.0[3]]),
            u16::from_be_bytes([self.0[4], self.0[5]]),
            u16::from_be_bytes([self.0[6], self.0[7]]),
            u16::from_be_bytes([self.0[8], self.0[9]]),
            u64::from_be_bytes([
                0, 0, self.0[10], self.0[11], self.0[12], self.0[13], self.0[14], self.0[15]
            ])
        )
    }
}

// ============================================================================
// Member Role
// ============================================================================

/// Role of a household member determining base permissions
#[derive(Debug, Clone, Copy, PartialEq, Eq, Hash, Serialize, Deserialize)]
#[serde(rename_all = "snake_case")]
pub enum MemberRole {
    /// Primary household owner with full control
    Owner,
    /// Administrator with nearly full control (e.g., spouse, partner)
    Admin,
    /// Regular household member (e.g., adult family member)
    Member,
    /// Child with restricted permissions
    Child,
    /// Guest with minimal, temporary access
    Guest,
}

impl MemberRole {
    /// Returns the default authority level for this role
    pub fn default_authority(&self) -> AuthorityLevel {
        match self {
            MemberRole::Owner => AuthorityLevel::Full,
            MemberRole::Admin => AuthorityLevel::High,
            MemberRole::Member => AuthorityLevel::Standard,
            MemberRole::Child => AuthorityLevel::Limited,
            MemberRole::Guest => AuthorityLevel::Minimal,
        }
    }

    /// Returns true if this role can modify household settings
    pub fn can_modify_household(&self) -> bool {
        matches!(self, MemberRole::Owner | MemberRole::Admin)
    }

    /// Returns true if this role can add/remove members
    pub fn can_manage_members(&self) -> bool {
        matches!(self, MemberRole::Owner | MemberRole::Admin)
    }

    /// Returns true if this role can access security features
    pub fn can_access_security(&self) -> bool {
        matches!(
            self,
            MemberRole::Owner | MemberRole::Admin | MemberRole::Member
        )
    }
}

impl Default for MemberRole {
    fn default() -> Self {
        MemberRole::Guest
    }
}

// ============================================================================
// Authority Level
// ============================================================================

/// Fine-grained authority level for permissions
#[derive(Debug, Clone, Copy, PartialEq, Eq, PartialOrd, Ord, Hash, Serialize, Deserialize)]
#[serde(rename_all = "snake_case")]
pub enum AuthorityLevel {
    /// No permissions (blocked)
    None,
    /// Minimal permissions (guests, temporary access)
    Minimal,
    /// Limited permissions (children, restricted users)
    Limited,
    /// Standard permissions (regular household members)
    Standard,
    /// High permissions (admins, trusted adults)
    High,
    /// Full permissions (owner only)
    Full,
}

impl AuthorityLevel {
    /// Returns a numeric value for comparison (0-100)
    pub fn level(&self) -> u8 {
        match self {
            AuthorityLevel::None => 0,
            AuthorityLevel::Minimal => 20,
            AuthorityLevel::Limited => 40,
            AuthorityLevel::Standard => 60,
            AuthorityLevel::High => 80,
            AuthorityLevel::Full => 100,
        }
    }

    /// Check if this authority level can perform an action requiring `required` level
    pub fn can_perform(&self, required: AuthorityLevel) -> bool {
        self >= &required
    }
}

impl Default for AuthorityLevel {
    fn default() -> Self {
        AuthorityLevel::Minimal
    }
}

// ============================================================================
// Accessibility Profile
// ============================================================================

/// Accessibility requirements and preferences for a household member
#[derive(Debug, Clone, PartialEq, Serialize, Deserialize)]
pub struct AccessibilityProfile {
    /// Minimum font size in pixels (default: 16)
    pub min_font_size: u8,

    /// Minimum contrast ratio (WCAG: 4.5 AA, 7.0 AAA)
    pub min_contrast_ratio: f32,

    /// Minimum touch target size in pixels (default: 44)
    pub min_touch_target: u8,

    /// Prefers reduced motion
    pub reduced_motion: bool,

    /// Prefers high contrast mode
    pub high_contrast: bool,

    /// Vision impairment level (0 = none, 1 = mild, 2 = moderate, 3 = severe)
    pub vision_impairment: u8,

    /// Hearing impairment level (0 = none, 1 = mild, 2 = moderate, 3 = severe)
    pub hearing_impairment: u8,

    /// Motor impairment level (0 = none, 1 = mild, 2 = moderate, 3 = severe)
    pub motor_impairment: u8,

    /// Cognitive considerations (memory, processing speed, etc.)
    pub cognitive_considerations: Vec<String>,

    /// Preferred input methods
    pub preferred_inputs: Vec<InputMethod>,

    /// Screen reader in use
    pub screen_reader: bool,

    /// Voice control as primary input
    pub voice_primary: bool,

    /// Default audio volume (0-100)
    pub default_volume: u8,

    /// Prefer slow, clear speech
    pub slow_speech: bool,
}

/// Input method preferences
#[derive(Debug, Clone, PartialEq, Eq, Hash, Serialize, Deserialize)]
#[serde(rename_all = "snake_case")]
pub enum InputMethod {
    /// Touch screen
    Touch,
    /// Physical keyboard
    Keyboard,
    /// Mouse/trackpad
    Pointer,
    /// Voice commands
    Voice,
    /// Eye tracking
    EyeTracking,
    /// Switch control
    SwitchControl,
    /// Gesture recognition
    Gesture,
}

impl Default for AccessibilityProfile {
    fn default() -> Self {
        Self {
            min_font_size: 16,
            min_contrast_ratio: 4.5, // WCAG AA
            min_touch_target: 44,
            reduced_motion: false,
            high_contrast: false,
            vision_impairment: 0,
            hearing_impairment: 0,
            motor_impairment: 0,
            cognitive_considerations: Vec::new(),
            preferred_inputs: vec![InputMethod::Touch, InputMethod::Voice],
            screen_reader: false,
            voice_primary: false,
            default_volume: 70,
            slow_speech: false,
        }
    }
}

impl AccessibilityProfile {
    /// Create a profile for a senior with common age-related needs
    pub fn senior() -> Self {
        Self {
            min_font_size: 24,
            min_contrast_ratio: 7.0, // WCAG AAA
            min_touch_target: 48,
            reduced_motion: true,
            high_contrast: true,
            vision_impairment: 1,
            hearing_impairment: 1,
            motor_impairment: 0,
            cognitive_considerations: vec!["memory_support".to_string()],
            preferred_inputs: vec![InputMethod::Voice, InputMethod::Touch],
            screen_reader: false,
            voice_primary: true,
            default_volume: 80,
            slow_speech: true,
        }
    }

    /// Create a profile for someone with visual impairment
    pub fn visual_impairment(severity: u8) -> Self {
        Self {
            min_font_size: match severity {
                0 => 16,
                1 => 24,
                2 => 32,
                _ => 40,
            },
            min_contrast_ratio: 7.0,
            min_touch_target: 48,
            reduced_motion: false,
            high_contrast: severity >= 2,
            vision_impairment: severity,
            hearing_impairment: 0,
            motor_impairment: 0,
            cognitive_considerations: Vec::new(),
            preferred_inputs: vec![InputMethod::Voice],
            screen_reader: severity >= 2,
            voice_primary: severity >= 2,
            default_volume: 70,
            slow_speech: false,
        }
    }

    /// Create a profile for someone with motor impairment
    pub fn motor_impairment(severity: u8) -> Self {
        Self {
            min_font_size: 16,
            min_contrast_ratio: 4.5,
            min_touch_target: match severity {
                0 => 44,
                1 => 48,
                2 => 56,
                _ => 64,
            },
            reduced_motion: true,
            high_contrast: false,
            vision_impairment: 0,
            hearing_impairment: 0,
            motor_impairment: severity,
            cognitive_considerations: Vec::new(),
            preferred_inputs: vec![InputMethod::Voice, InputMethod::SwitchControl],
            screen_reader: false,
            voice_primary: severity >= 2,
            default_volume: 70,
            slow_speech: false,
        }
    }
}

// ============================================================================
// Cultural Preferences
// ============================================================================

/// Cultural preferences and norms for a household member
#[derive(Debug, Clone, PartialEq, Serialize, Deserialize)]
pub struct CulturalPreferences {
    /// Primary language (ISO 639-1 code)
    pub primary_language: String,

    /// Additional languages
    pub additional_languages: Vec<String>,

    /// Privacy orientation (individualist vs collectivist)
    pub privacy_orientation: PrivacyOrientation,

    /// Decision-making style in household
    pub decision_style: DecisionStyle,

    /// Religious/spiritual observances
    pub observances: Vec<String>,

    /// Dietary restrictions/preferences
    pub dietary: Vec<String>,

    /// Time format preference (12h vs 24h)
    pub time_format_24h: bool,

    /// Date format preference
    pub date_format: DateFormat,

    /// Temperature unit preference
    pub temp_unit: TemperatureUnit,

    /// Greeting style preference
    pub greeting_style: GreetingStyle,

    /// Formality level in interactions
    pub formality: FormalityLevel,

    /// Respect for hierarchy/elders
    pub hierarchical_respect: bool,

    /// Gender considerations for interactions
    pub gender_considerations: Option<String>,
}

/// Privacy orientation based on cultural norms
#[derive(Debug, Clone, Copy, PartialEq, Eq, Hash, Serialize, Deserialize)]
#[serde(rename_all = "snake_case")]
pub enum PrivacyOrientation {
    /// Strong individual privacy (typical in US, Germany, Netherlands)
    Individualist,
    /// Moderate privacy with family sharing (typical in Southern Europe, Latin America)
    FamilyOriented,
    /// Collectivist with shared household awareness (typical in East Asia, Middle East)
    Collectivist,
}

/// Decision-making style in household
#[derive(Debug, Clone, Copy, PartialEq, Eq, Hash, Serialize, Deserialize)]
#[serde(rename_all = "snake_case")]
pub enum DecisionStyle {
    /// Individual autonomy
    Individual,
    /// Joint decisions between partners
    Partnership,
    /// Hierarchical (elders consulted, head decides)
    Hierarchical,
    /// Consensus-based (everyone has input)
    Consensus,
}

/// Date format preference
#[derive(Debug, Clone, Copy, PartialEq, Eq, Hash, Serialize, Deserialize)]
#[serde(rename_all = "snake_case")]
pub enum DateFormat {
    /// MM/DD/YYYY (US)
    MonthDayYear,
    /// DD/MM/YYYY (Europe, most of world)
    DayMonthYear,
    /// YYYY-MM-DD (ISO 8601)
    YearMonthDay,
}

/// Temperature unit preference
#[derive(Debug, Clone, Copy, PartialEq, Eq, Hash, Serialize, Deserialize)]
#[serde(rename_all = "snake_case")]
pub enum TemperatureUnit {
    Fahrenheit,
    Celsius,
}

/// Greeting style preference
#[derive(Debug, Clone, Copy, PartialEq, Eq, Hash, Serialize, Deserialize)]
#[serde(rename_all = "snake_case")]
pub enum GreetingStyle {
    /// Casual greetings ("Hey!", "Hi there!")
    Casual,
    /// Formal greetings ("Good morning, Mr. Smith")
    Formal,
    /// Warm/friendly ("Good morning! How are you today?")
    Warm,
    /// Minimal (just the information, no fluff)
    Minimal,
}

/// Formality level in interactions
#[derive(Debug, Clone, Copy, PartialEq, Eq, Hash, Serialize, Deserialize)]
#[serde(rename_all = "snake_case")]
pub enum FormalityLevel {
    /// Very casual, uses nicknames
    Casual,
    /// Friendly but respectful
    Friendly,
    /// Professional/polite
    Polite,
    /// Formal, uses titles
    Formal,
}

impl Default for CulturalPreferences {
    fn default() -> Self {
        Self {
            primary_language: "en".to_string(),
            additional_languages: Vec::new(),
            privacy_orientation: PrivacyOrientation::Individualist,
            decision_style: DecisionStyle::Individual,
            observances: Vec::new(),
            dietary: Vec::new(),
            time_format_24h: false,
            date_format: DateFormat::MonthDayYear,
            temp_unit: TemperatureUnit::Fahrenheit,
            greeting_style: GreetingStyle::Warm,
            formality: FormalityLevel::Friendly,
            hierarchical_respect: false,
            gender_considerations: None,
        }
    }
}

impl CulturalPreferences {
    /// Create preferences for a US household
    pub fn us_default() -> Self {
        Self::default()
    }

    /// Create preferences for a European household
    pub fn europe_default() -> Self {
        Self {
            time_format_24h: true,
            date_format: DateFormat::DayMonthYear,
            temp_unit: TemperatureUnit::Celsius,
            ..Self::default()
        }
    }

    /// Create preferences for an East Asian household
    pub fn east_asia_default() -> Self {
        Self {
            privacy_orientation: PrivacyOrientation::Collectivist,
            decision_style: DecisionStyle::Hierarchical,
            time_format_24h: true,
            date_format: DateFormat::YearMonthDay,
            temp_unit: TemperatureUnit::Celsius,
            formality: FormalityLevel::Polite,
            hierarchical_respect: true,
            ..Self::default()
        }
    }

    /// Create preferences for a South Asian household
    pub fn south_asia_default() -> Self {
        Self {
            privacy_orientation: PrivacyOrientation::FamilyOriented,
            decision_style: DecisionStyle::Hierarchical,
            time_format_24h: true,
            date_format: DateFormat::DayMonthYear,
            temp_unit: TemperatureUnit::Celsius,
            formality: FormalityLevel::Polite,
            hierarchical_respect: true,
            ..Self::default()
        }
    }

    /// Create preferences for a Middle Eastern household
    pub fn middle_east_default() -> Self {
        Self {
            privacy_orientation: PrivacyOrientation::FamilyOriented,
            decision_style: DecisionStyle::Hierarchical,
            time_format_24h: true,
            date_format: DateFormat::DayMonthYear,
            temp_unit: TemperatureUnit::Celsius,
            formality: FormalityLevel::Formal,
            hierarchical_respect: true,
            ..Self::default()
        }
    }
}

// ============================================================================
// Schedule Profile
// ============================================================================

/// Schedule preferences and patterns for a household member
#[derive(Debug, Clone, PartialEq, Serialize, Deserialize)]
pub struct ScheduleProfile {
    /// Typical wake time (hour, 0-23)
    pub wake_hour: u8,

    /// Typical sleep time (hour, 0-23)
    pub sleep_hour: u8,

    /// Work/school start time (hour, 0-23), if applicable
    pub work_start: Option<u8>,

    /// Work/school end time (hour, 0-23), if applicable
    pub work_end: Option<u8>,

    /// Days when work/school schedule applies (0 = Sunday, 6 = Saturday)
    pub work_days: Vec<u8>,

    /// Meal times (hour, 0-23)
    pub meal_times: MealSchedule,

    /// Quiet hours (no announcements, minimal alerts)
    pub quiet_hours: Option<(u8, u8)>,

    /// Focus/do-not-disturb periods
    pub focus_periods: Vec<TimePeriod>,

    /// Recurring events/reminders
    pub recurring_events: Vec<RecurringEvent>,

    /// Timezone (IANA timezone string)
    pub timezone: String,
}

/// Meal schedule
#[derive(Debug, Clone, PartialEq, Serialize, Deserialize)]
pub struct MealSchedule {
    pub breakfast: Option<u8>,
    pub lunch: Option<u8>,
    pub dinner: Option<u8>,
    pub snacks: Vec<u8>,
}

impl Default for MealSchedule {
    fn default() -> Self {
        Self {
            breakfast: Some(7),
            lunch: Some(12),
            dinner: Some(18),
            snacks: Vec::new(),
        }
    }
}

/// A time period within a day
#[derive(Debug, Clone, PartialEq, Serialize, Deserialize)]
pub struct TimePeriod {
    /// Start hour (0-23)
    pub start_hour: u8,
    /// End hour (0-23)
    pub end_hour: u8,
    /// Days this applies (0 = Sunday, 6 = Saturday)
    pub days: Vec<u8>,
    /// Label for this period
    pub label: String,
}

/// A recurring event or reminder
#[derive(Debug, Clone, PartialEq, Serialize, Deserialize)]
pub struct RecurringEvent {
    /// Event name
    pub name: String,
    /// Time (hour, minute)
    pub time: (u8, u8),
    /// Days this occurs (0 = Sunday, 6 = Saturday)
    pub days: Vec<u8>,
    /// Whether to announce/remind
    pub remind: bool,
    /// Reminder message
    pub message: Option<String>,
}

impl Default for ScheduleProfile {
    fn default() -> Self {
        Self {
            wake_hour: 7,
            sleep_hour: 22,
            work_start: Some(9),
            work_end: Some(17),
            work_days: vec![1, 2, 3, 4, 5], // Mon-Fri
            meal_times: MealSchedule::default(),
            quiet_hours: Some((22, 7)),
            focus_periods: Vec::new(),
            recurring_events: Vec::new(),
            timezone: "America/Los_Angeles".to_string(),
        }
    }
}

impl ScheduleProfile {
    /// Create a schedule for a senior
    pub fn senior() -> Self {
        Self {
            wake_hour: 6,
            sleep_hour: 21,
            work_start: None,
            work_end: None,
            work_days: Vec::new(),
            meal_times: MealSchedule {
                breakfast: Some(7),
                lunch: Some(12),
                dinner: Some(17),
                snacks: vec![10, 15],
            },
            quiet_hours: Some((21, 6)),
            focus_periods: Vec::new(),
            recurring_events: Vec::new(),
            timezone: "America/Los_Angeles".to_string(),
        }
    }

    /// Create a schedule for a child (school-age)
    pub fn child() -> Self {
        Self {
            wake_hour: 7,
            sleep_hour: 20,
            work_start: Some(8),  // School
            work_end: Some(15),   // School
            work_days: vec![1, 2, 3, 4, 5],
            meal_times: MealSchedule::default(),
            quiet_hours: Some((20, 7)),
            focus_periods: vec![TimePeriod {
                start_hour: 16,
                end_hour: 17,
                days: vec![1, 2, 3, 4, 5],
                label: "Homework time".to_string(),
            }],
            recurring_events: Vec::new(),
            timezone: "America/Los_Angeles".to_string(),
        }
    }

    /// Check if current hour is within quiet hours
    pub fn is_quiet_hour(&self, hour: u8) -> bool {
        if let Some((start, end)) = self.quiet_hours {
            if start <= end {
                hour >= start && hour < end
            } else {
                // Wraps around midnight (e.g., 22:00 - 07:00)
                hour >= start || hour < end
            }
        } else {
            false
        }
    }
}

// ============================================================================
// Household Member
// ============================================================================

/// A member of the household
#[derive(Debug, Clone, PartialEq, Serialize, Deserialize)]
pub struct HouseholdMember {
    /// Unique identifier
    pub id: Uuid,

    /// Display name
    pub name: String,

    /// Pronouns (e.g., "he/him", "she/her", "they/them")
    pub pronouns: Option<String>,

    /// Role in the household
    pub role: MemberRole,

    /// Authority level for permissions
    pub authority_level: AuthorityLevel,

    /// Accessibility requirements
    pub accessibility_profile: AccessibilityProfile,

    /// Cultural preferences
    pub cultural_preferences: CulturalPreferences,

    /// Schedule profile
    pub schedule_profile: ScheduleProfile,

    /// Email for notifications (optional)
    pub email: Option<String>,

    /// Phone for emergency contact (optional)
    pub phone: Option<String>,

    /// Associated voice profile ID (for speaker recognition)
    pub voice_profile_id: Option<String>,

    /// Associated face profile ID (for face recognition)
    pub face_profile_id: Option<String>,

    /// Custom metadata
    pub metadata: HashMap<String, String>,

    /// When this member was added
    pub created_at: u64,

    /// Last update timestamp (for CRDT)
    pub updated_at: u64,

    /// Hub that last updated this member (for CRDT)
    pub updated_by: String,
}

impl HouseholdMember {
    /// Create a new household member with default profiles
    pub fn new(name: String, role: MemberRole, authority_level: AuthorityLevel) -> Self {
        let now = current_timestamp();
        Self {
            id: Uuid::new_v4(),
            name,
            pronouns: None,
            role,
            authority_level,
            accessibility_profile: AccessibilityProfile::default(),
            cultural_preferences: CulturalPreferences::default(),
            schedule_profile: ScheduleProfile::default(),
            email: None,
            phone: None,
            voice_profile_id: None,
            face_profile_id: None,
            metadata: HashMap::new(),
            created_at: now,
            updated_at: now,
            updated_by: "local".to_string(),
        }
    }

    /// Create a new owner member
    pub fn owner(name: String) -> Self {
        Self::new(name, MemberRole::Owner, AuthorityLevel::Full)
    }

    /// Create a new admin member
    pub fn admin(name: String) -> Self {
        Self::new(name, MemberRole::Admin, AuthorityLevel::High)
    }

    /// Create a new regular member
    pub fn member(name: String) -> Self {
        Self::new(name, MemberRole::Member, AuthorityLevel::Standard)
    }

    /// Create a new child member
    pub fn child(name: String) -> Self {
        let mut member = Self::new(name, MemberRole::Child, AuthorityLevel::Limited);
        member.schedule_profile = ScheduleProfile::child();
        member
    }

    /// Create a new guest member
    pub fn guest(name: String) -> Self {
        Self::new(name, MemberRole::Guest, AuthorityLevel::Minimal)
    }

    /// Set pronouns
    pub fn with_pronouns(mut self, pronouns: &str) -> Self {
        self.pronouns = Some(pronouns.to_string());
        self
    }

    /// Set accessibility profile
    pub fn with_accessibility(mut self, profile: AccessibilityProfile) -> Self {
        self.accessibility_profile = profile;
        self
    }

    /// Set cultural preferences
    pub fn with_cultural(mut self, prefs: CulturalPreferences) -> Self {
        self.cultural_preferences = prefs;
        self
    }

    /// Set schedule profile
    pub fn with_schedule(mut self, schedule: ScheduleProfile) -> Self {
        self.schedule_profile = schedule;
        self
    }

    /// Check if this member can perform an action requiring the given authority
    pub fn can_perform(&self, required: AuthorityLevel) -> bool {
        self.authority_level.can_perform(required)
    }

    /// Update the member with a new timestamp (for CRDT merge)
    pub fn touch(&mut self, hub_id: &str) {
        self.updated_at = current_timestamp();
        self.updated_by = hub_id.to_string();
    }
}

// ============================================================================
// Household Type
// ============================================================================

/// Type of household, representing diverse living arrangements
///
/// Based on global UX research covering 10 distinct personas.
#[derive(Debug, Clone, Copy, PartialEq, Eq, Hash, Serialize, Deserialize)]
#[serde(rename_all = "snake_case")]
pub enum HouseholdType {
    /// Solo senior living independently (e.g., Ingrid in Denmark)
    SoloSenior,

    /// Multigenerational extended family (e.g., The Patels in Seattle)
    MultigenerationalExtended,

    /// LGBTQ+ parents with children (e.g., Jordan & Sam in San Francisco)
    LgbtqParents,

    /// Roommates/non-family sharing space (e.g., The Apartment in Tokyo)
    Roommates,

    /// Single parent with children (e.g., Maria in Mexico City)
    SingleParent,

    /// Accessibility-focused household (e.g., Michael in London)
    AccessibilityFocused,

    /// Student housing/share house (e.g., The Share House in Melbourne)
    StudentHousing,

    /// Empty nesters/retired couple (e.g., The Johannsens in Stockholm)
    EmptyNesters,

    /// Home-based business (e.g., Fatima in Dubai)
    HomeBasedBusiness,

    /// Rural multigenerational (e.g., The O'Briens in County Kerry)
    RuralMultigenerational,

    /// Single professional (e.g., Tim)
    SingleProfessional,

    /// Nuclear family (traditional 2 parents + children)
    NuclearFamily,

    /// Couple without children
    CoupleNoChildren,

    /// Blended family (step-parents, custody arrangements)
    BlendedFamily,

    /// Other/custom
    Other,
}

impl HouseholdType {
    /// Returns a human-readable description of this household type
    pub fn description(&self) -> &'static str {
        match self {
            HouseholdType::SoloSenior => "Solo senior living independently",
            HouseholdType::MultigenerationalExtended => "Multigenerational extended family",
            HouseholdType::LgbtqParents => "LGBTQ+ parents with children",
            HouseholdType::Roommates => "Roommates or non-family sharing space",
            HouseholdType::SingleParent => "Single parent with children",
            HouseholdType::AccessibilityFocused => "Accessibility-focused household",
            HouseholdType::StudentHousing => "Student housing or share house",
            HouseholdType::EmptyNesters => "Empty nesters or retired couple",
            HouseholdType::HomeBasedBusiness => "Home-based business",
            HouseholdType::RuralMultigenerational => "Rural multigenerational household",
            HouseholdType::SingleProfessional => "Single professional",
            HouseholdType::NuclearFamily => "Nuclear family",
            HouseholdType::CoupleNoChildren => "Couple without children",
            HouseholdType::BlendedFamily => "Blended family with step-parents or custody arrangements",
            HouseholdType::Other => "Custom household configuration",
        }
    }

    /// Returns the typical privacy orientation for this household type
    pub fn typical_privacy(&self) -> PrivacyOrientation {
        match self {
            HouseholdType::SoloSenior => PrivacyOrientation::Individualist,
            HouseholdType::MultigenerationalExtended => PrivacyOrientation::FamilyOriented,
            HouseholdType::LgbtqParents => PrivacyOrientation::Individualist,
            HouseholdType::Roommates => PrivacyOrientation::Individualist,
            HouseholdType::SingleParent => PrivacyOrientation::FamilyOriented,
            HouseholdType::AccessibilityFocused => PrivacyOrientation::Individualist,
            HouseholdType::StudentHousing => PrivacyOrientation::Individualist,
            HouseholdType::EmptyNesters => PrivacyOrientation::Individualist,
            HouseholdType::HomeBasedBusiness => PrivacyOrientation::Individualist,
            HouseholdType::RuralMultigenerational => PrivacyOrientation::Collectivist,
            HouseholdType::SingleProfessional => PrivacyOrientation::Individualist,
            HouseholdType::NuclearFamily => PrivacyOrientation::FamilyOriented,
            HouseholdType::CoupleNoChildren => PrivacyOrientation::Individualist,
            HouseholdType::BlendedFamily => PrivacyOrientation::FamilyOriented,
            HouseholdType::Other => PrivacyOrientation::Individualist,
        }
    }

    /// Returns the typical decision style for this household type
    pub fn typical_decision_style(&self) -> DecisionStyle {
        match self {
            HouseholdType::SoloSenior => DecisionStyle::Individual,
            HouseholdType::MultigenerationalExtended => DecisionStyle::Hierarchical,
            HouseholdType::LgbtqParents => DecisionStyle::Partnership,
            HouseholdType::Roommates => DecisionStyle::Individual,
            HouseholdType::SingleParent => DecisionStyle::Individual,
            HouseholdType::AccessibilityFocused => DecisionStyle::Individual,
            HouseholdType::StudentHousing => DecisionStyle::Consensus,
            HouseholdType::EmptyNesters => DecisionStyle::Partnership,
            HouseholdType::HomeBasedBusiness => DecisionStyle::Individual,
            HouseholdType::RuralMultigenerational => DecisionStyle::Hierarchical,
            HouseholdType::SingleProfessional => DecisionStyle::Individual,
            HouseholdType::NuclearFamily => DecisionStyle::Partnership,
            HouseholdType::CoupleNoChildren => DecisionStyle::Partnership,
            HouseholdType::BlendedFamily => DecisionStyle::Consensus,
            HouseholdType::Other => DecisionStyle::Individual,
        }
    }
}

impl Default for HouseholdType {
    fn default() -> Self {
        HouseholdType::SingleProfessional
    }
}

// ============================================================================
// Household
// ============================================================================

/// OR-Set element for CRDT member management
#[derive(Debug, Clone, Serialize, Deserialize, PartialEq, Eq, Hash)]
pub struct MemberElement {
    /// Member ID
    pub member_id: String,
    /// Unique add tag (hub_id:timestamp)
    pub tag: String,
}

/// A household with members and CRDT-compatible sync
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct Household {
    /// Unique household identifier
    pub id: Uuid,

    /// Household name
    pub name: String,

    /// Type of household
    pub household_type: HouseholdType,

    /// All household members (keyed by ID string for CRDT)
    members: HashMap<String, HouseholdMember>,

    /// OR-Set elements for CRDT (tracks add operations)
    #[serde(default)]
    member_elements: Vec<MemberElement>,

    /// Tombstones for removed members (OR-Set CRDT)
    #[serde(default)]
    tombstones: Vec<String>,

    /// When this household was created
    pub created_at: u64,

    /// Last update timestamp
    pub updated_at: u64,

    /// Hub that last updated (for CRDT)
    pub updated_by: String,

    /// Custom household settings
    pub settings: HouseholdSettings,
}

/// Household-level settings
#[derive(Debug, Clone, PartialEq, Serialize, Deserialize)]
pub struct HouseholdSettings {
    /// Guest mode duration (hours before auto-expiry)
    pub guest_expiry_hours: u32,

    /// Allow voice enrollment for new members
    pub allow_voice_enrollment: bool,

    /// Allow face enrollment for new members
    pub allow_face_enrollment: bool,

    /// Default language for household
    pub default_language: String,

    /// Emergency contacts
    pub emergency_contacts: Vec<EmergencyContact>,

    /// Address (for emergency services)
    pub address: Option<String>,

    /// Security code (for lock/unlock operations)
    pub security_code: Option<String>,
}

impl Default for HouseholdSettings {
    fn default() -> Self {
        Self {
            guest_expiry_hours: 24,
            allow_voice_enrollment: true,
            allow_face_enrollment: true,
            default_language: "en".to_string(),
            emergency_contacts: Vec::new(),
            address: None,
            security_code: None,
        }
    }
}

/// Emergency contact information
#[derive(Debug, Clone, PartialEq, Serialize, Deserialize)]
pub struct EmergencyContact {
    pub name: String,
    pub phone: String,
    pub relationship: String,
}

impl Household {
    /// Create a new household with an initial owner
    pub fn new(name: String, household_type: HouseholdType, owner: HouseholdMember) -> Self {
        let now = current_timestamp();
        let id = Uuid::new_v4();
        let member_id = owner.id.to_string();
        let tag = format!("local:{}", now);

        let mut members = HashMap::new();
        members.insert(member_id.clone(), owner);

        Self {
            id,
            name,
            household_type,
            members,
            member_elements: vec![MemberElement {
                member_id,
                tag,
            }],
            tombstones: Vec::new(),
            created_at: now,
            updated_at: now,
            updated_by: "local".to_string(),
            settings: HouseholdSettings::default(),
        }
    }

    /// Get all current members
    pub fn members(&self) -> Vec<&HouseholdMember> {
        self.members.values().collect()
    }

    /// Get a member by ID
    pub fn get_member(&self, id: &Uuid) -> Option<&HouseholdMember> {
        self.members.get(&id.to_string())
    }

    /// Get a member by name (case-insensitive)
    pub fn get_member_by_name(&self, name: &str) -> Option<&HouseholdMember> {
        let name_lower = name.to_lowercase();
        self.members
            .values()
            .find(|m| m.name.to_lowercase() == name_lower)
    }

    /// Get a mutable reference to a member by ID
    pub fn get_member_mut(&mut self, id: &Uuid) -> Option<&mut HouseholdMember> {
        self.members.get_mut(&id.to_string())
    }

    /// Add a new member to the household (CRDT: OR-Set add)
    pub fn add_member(&mut self, member: HouseholdMember, hub_id: &str) {
        let member_id = member.id.to_string();
        let tag = format!("{}:{}", hub_id, current_timestamp());

        // Add element to OR-Set
        self.member_elements.push(MemberElement {
            member_id: member_id.clone(),
            tag,
        });

        // Add to members map
        self.members.insert(member_id, member);

        self.touch(hub_id);
    }

    /// Remove a member from the household (CRDT: OR-Set remove)
    pub fn remove_member(&mut self, id: &Uuid, hub_id: &str) -> Option<HouseholdMember> {
        let member_id = id.to_string();

        // Find all tags for this member and tombstone them
        let tags_to_remove: Vec<_> = self
            .member_elements
            .iter()
            .filter(|e| e.member_id == member_id)
            .map(|e| e.tag.clone())
            .collect();

        for tag in tags_to_remove {
            self.tombstones.push(tag);
        }

        // Remove elements with tombstoned tags
        self.member_elements
            .retain(|e| !self.tombstones.contains(&e.tag));

        self.touch(hub_id);

        // Remove from members map
        self.members.remove(&member_id)
    }

    /// Get members with a specific role
    pub fn members_with_role(&self, role: MemberRole) -> Vec<&HouseholdMember> {
        self.members.values().filter(|m| m.role == role).collect()
    }

    /// Get the primary owner (first owner found)
    pub fn owner(&self) -> Option<&HouseholdMember> {
        self.members
            .values()
            .find(|m| m.role == MemberRole::Owner)
    }

    /// Get all admins (including owner)
    pub fn admins(&self) -> Vec<&HouseholdMember> {
        self.members
            .values()
            .filter(|m| matches!(m.role, MemberRole::Owner | MemberRole::Admin))
            .collect()
    }

    /// Check if a member can perform an action based on authority
    pub fn can_member_perform(&self, member_id: &Uuid, required: AuthorityLevel) -> bool {
        self.get_member(member_id)
            .map(|m| m.can_perform(required))
            .unwrap_or(false)
    }

    /// Update timestamp (for CRDT)
    pub fn touch(&mut self, hub_id: &str) {
        self.updated_at = current_timestamp();
        self.updated_by = hub_id.to_string();
    }

    // ========================================================================
    // CRDT Merge Operations
    // ========================================================================

    /// Merge another household state into this one (CRDT merge)
    ///
    /// Uses OR-Set semantics for members:
    /// - All adds from both sides are kept
    /// - Tombstones from both sides are merged
    /// - Members with tombstoned tags are removed
    /// - For member data, Last-Writer-Wins based on updated_at
    pub fn merge(&mut self, other: &Household) {
        // Merge tombstones
        for tombstone in &other.tombstones {
            if !self.tombstones.contains(tombstone) {
                self.tombstones.push(tombstone.clone());
            }
        }

        // Merge member elements (OR-Set add)
        for element in &other.member_elements {
            if !self.tombstones.contains(&element.tag)
                && !self.member_elements.contains(element)
            {
                self.member_elements.push(element.clone());
            }
        }

        // Remove tombstoned elements
        self.member_elements
            .retain(|e| !self.tombstones.contains(&e.tag));

        // Merge member data (LWW for each member)
        for (member_id, other_member) in &other.members {
            // Check if member should exist (has non-tombstoned element)
            let should_exist = self
                .member_elements
                .iter()
                .any(|e| &e.member_id == member_id);

            if should_exist {
                match self.members.get_mut(member_id) {
                    Some(existing) => {
                        // LWW: take newer data
                        if other_member.updated_at > existing.updated_at {
                            *existing = other_member.clone();
                        }
                    }
                    None => {
                        // Add member from other
                        self.members
                            .insert(member_id.clone(), other_member.clone());
                    }
                }
            }
        }

        // Remove members that don't have elements
        let valid_member_ids: Vec<_> = self
            .member_elements
            .iter()
            .map(|e| e.member_id.clone())
            .collect();
        self.members
            .retain(|id, _| valid_member_ids.contains(id));

        // Update household metadata (LWW)
        if other.updated_at > self.updated_at {
            self.name = other.name.clone();
            self.household_type = other.household_type;
            self.settings = other.settings.clone();
            self.updated_at = other.updated_at;
            self.updated_by = other.updated_by.clone();
        }
    }

    /// Calculate delta since a given timestamp
    ///
    /// Returns members and elements that changed after the timestamp.
    pub fn delta_since(&self, timestamp: u64) -> HouseholdDelta {
        let changed_members: HashMap<String, HouseholdMember> = self
            .members
            .iter()
            .filter(|(_, m)| m.updated_at > timestamp)
            .map(|(k, v)| (k.clone(), v.clone()))
            .collect();

        HouseholdDelta {
            members: changed_members,
            member_elements: self.member_elements.clone(),
            tombstones: self.tombstones.clone(),
            household_updated_at: self.updated_at,
        }
    }

    /// Apply a delta to this household
    pub fn apply_delta(&mut self, delta: HouseholdDelta) {
        // Merge tombstones
        for tombstone in delta.tombstones {
            if !self.tombstones.contains(&tombstone) {
                self.tombstones.push(tombstone);
            }
        }

        // Merge elements
        for element in delta.member_elements {
            if !self.tombstones.contains(&element.tag)
                && !self.member_elements.contains(&element)
            {
                self.member_elements.push(element);
            }
        }

        // Remove tombstoned elements
        self.member_elements
            .retain(|e| !self.tombstones.contains(&e.tag));

        // Apply member updates (LWW)
        for (member_id, member) in delta.members {
            let should_exist = self
                .member_elements
                .iter()
                .any(|e| e.member_id == member_id);

            if should_exist {
                match self.members.get_mut(&member_id) {
                    Some(existing) => {
                        if member.updated_at > existing.updated_at {
                            *existing = member;
                        }
                    }
                    None => {
                        self.members.insert(member_id, member);
                    }
                }
            }
        }

        // Clean up members without elements
        let valid_member_ids: Vec<_> = self
            .member_elements
            .iter()
            .map(|e| e.member_id.clone())
            .collect();
        self.members
            .retain(|id, _| valid_member_ids.contains(id));
    }
}

/// Delta for efficient sync
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct HouseholdDelta {
    /// Changed members (LWW data)
    pub members: HashMap<String, HouseholdMember>,
    /// All member elements (OR-Set)
    pub member_elements: Vec<MemberElement>,
    /// All tombstones
    pub tombstones: Vec<String>,
    /// Household update timestamp
    pub household_updated_at: u64,
}

// ============================================================================
// Utility Functions
// ============================================================================

/// Get current Unix timestamp
fn current_timestamp() -> u64 {
    SystemTime::now()
        .duration_since(UNIX_EPOCH)
        .unwrap()
        .as_secs()
}

// ============================================================================
// Tests
// ============================================================================

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_create_household() {
        let owner = HouseholdMember::owner("Tim".to_string());
        let household = Household::new(
            "Tim's House".to_string(),
            HouseholdType::SingleProfessional,
            owner,
        );

        assert_eq!(household.name, "Tim's House");
        assert_eq!(household.household_type, HouseholdType::SingleProfessional);
        assert_eq!(household.members().len(), 1);
    }

    #[test]
    fn test_add_member() {
        let owner = HouseholdMember::owner("Tim".to_string());
        let mut household = Household::new(
            "Tim's House".to_string(),
            HouseholdType::SingleProfessional,
            owner,
        );

        let guest = HouseholdMember::guest("Kristi".to_string())
            .with_pronouns("she/her");
        household.add_member(guest, "hub-1");

        assert_eq!(household.members().len(), 2);
        assert!(household.get_member_by_name("Kristi").is_some());
    }

    #[test]
    fn test_remove_member() {
        let owner = HouseholdMember::owner("Tim".to_string());
        let mut household = Household::new(
            "Tim's House".to_string(),
            HouseholdType::SingleProfessional,
            owner,
        );

        let guest = HouseholdMember::guest("Visitor".to_string());
        let guest_id = guest.id;
        household.add_member(guest, "hub-1");

        assert_eq!(household.members().len(), 2);

        household.remove_member(&guest_id, "hub-1");

        assert_eq!(household.members().len(), 1);
        assert!(household.get_member(&guest_id).is_none());
    }

    #[test]
    fn test_authority_levels() {
        assert!(AuthorityLevel::Full > AuthorityLevel::High);
        assert!(AuthorityLevel::High > AuthorityLevel::Standard);
        assert!(AuthorityLevel::Standard > AuthorityLevel::Limited);
        assert!(AuthorityLevel::Limited > AuthorityLevel::Minimal);
        assert!(AuthorityLevel::Minimal > AuthorityLevel::None);

        assert!(AuthorityLevel::Full.can_perform(AuthorityLevel::Standard));
        assert!(!AuthorityLevel::Limited.can_perform(AuthorityLevel::High));
    }

    #[test]
    fn test_role_permissions() {
        assert!(MemberRole::Owner.can_modify_household());
        assert!(MemberRole::Admin.can_modify_household());
        assert!(!MemberRole::Member.can_modify_household());
        assert!(!MemberRole::Child.can_modify_household());
        assert!(!MemberRole::Guest.can_modify_household());

        assert!(MemberRole::Member.can_access_security());
        assert!(!MemberRole::Child.can_access_security());
        assert!(!MemberRole::Guest.can_access_security());
    }

    #[test]
    fn test_household_type_descriptions() {
        assert!(!HouseholdType::SoloSenior.description().is_empty());
        assert!(!HouseholdType::MultigenerationalExtended.description().is_empty());
        assert!(!HouseholdType::LgbtqParents.description().is_empty());
    }

    #[test]
    fn test_accessibility_profiles() {
        let senior = AccessibilityProfile::senior();
        assert!(senior.min_font_size >= 24);
        assert!(senior.voice_primary);
        assert!(senior.slow_speech);

        let visual = AccessibilityProfile::visual_impairment(2);
        assert!(visual.screen_reader);
        assert!(visual.vision_impairment == 2);
    }

    #[test]
    fn test_cultural_preferences() {
        let us = CulturalPreferences::us_default();
        assert!(!us.time_format_24h);
        assert_eq!(us.temp_unit, TemperatureUnit::Fahrenheit);

        let eu = CulturalPreferences::europe_default();
        assert!(eu.time_format_24h);
        assert_eq!(eu.temp_unit, TemperatureUnit::Celsius);
    }

    #[test]
    fn test_schedule_quiet_hours() {
        let schedule = ScheduleProfile::default();
        assert!(schedule.is_quiet_hour(23));
        assert!(schedule.is_quiet_hour(3));
        assert!(!schedule.is_quiet_hour(12));
    }

    #[test]
    fn test_crdt_merge_add() {
        let owner = HouseholdMember::owner("Tim".to_string());
        let mut household1 = Household::new(
            "House".to_string(),
            HouseholdType::SingleProfessional,
            owner.clone(),
        );

        let mut household2 = household1.clone();

        // Add different members on each
        let member1 = HouseholdMember::member("Alice".to_string());
        household1.add_member(member1, "hub-1");

        let member2 = HouseholdMember::member("Bob".to_string());
        household2.add_member(member2, "hub-2");

        // Merge
        household1.merge(&household2);

        // Both members should exist
        assert_eq!(household1.members().len(), 3); // Tim, Alice, Bob
        assert!(household1.get_member_by_name("Alice").is_some());
        assert!(household1.get_member_by_name("Bob").is_some());
    }

    #[test]
    fn test_crdt_merge_remove() {
        let owner = HouseholdMember::owner("Tim".to_string());
        let mut household1 = Household::new(
            "House".to_string(),
            HouseholdType::SingleProfessional,
            owner.clone(),
        );

        let guest = HouseholdMember::guest("Guest".to_string());
        let guest_id = guest.id;
        household1.add_member(guest, "hub-1");

        let mut household2 = household1.clone();

        // Remove on one side
        household1.remove_member(&guest_id, "hub-1");

        // Merge should propagate removal
        household2.merge(&household1);

        assert_eq!(household2.members().len(), 1);
        assert!(household2.get_member(&guest_id).is_none());
    }

    #[test]
    fn test_crdt_delta() {
        let owner = HouseholdMember::owner("Tim".to_string());
        let mut household = Household::new(
            "House".to_string(),
            HouseholdType::SingleProfessional,
            owner,
        );

        // Get timestamp before any changes (subtract 1 to ensure new member is "after")
        let before = household.updated_at.saturating_sub(1);

        let member = HouseholdMember::member("New".to_string());
        household.add_member(member, "hub-1");

        let delta = household.delta_since(before);
        // Delta should include elements and may include members depending on timestamp
        assert!(!delta.member_elements.is_empty());
    }

    #[test]
    fn test_member_builder() {
        let member = HouseholdMember::owner("Tim".to_string())
            .with_pronouns("he/him")
            .with_accessibility(AccessibilityProfile::default())
            .with_cultural(CulturalPreferences::us_default())
            .with_schedule(ScheduleProfile::default());

        assert_eq!(member.name, "Tim");
        assert_eq!(member.pronouns, Some("he/him".to_string()));
        assert_eq!(member.role, MemberRole::Owner);
    }

    #[test]
    fn test_household_type_typical_values() {
        // Test that all household types have sensible defaults
        for household_type in [
            HouseholdType::SoloSenior,
            HouseholdType::MultigenerationalExtended,
            HouseholdType::LgbtqParents,
            HouseholdType::Roommates,
            HouseholdType::SingleParent,
            HouseholdType::AccessibilityFocused,
            HouseholdType::StudentHousing,
            HouseholdType::EmptyNesters,
            HouseholdType::HomeBasedBusiness,
            HouseholdType::RuralMultigenerational,
        ] {
            // Each should have a description
            assert!(!household_type.description().is_empty());

            // Each should have a privacy orientation
            let _privacy = household_type.typical_privacy();

            // Each should have a decision style
            let _decision = household_type.typical_decision_style();
        }
    }
}

/*
 * 鏡
 * Every household is unique. Kagami adapts to all of them.
 * Privacy IS safety. h(x) ≥ 0. Always.
 */
