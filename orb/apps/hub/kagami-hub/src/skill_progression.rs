//! Skill Progression System — Grove (e6) Colony
//!
//! Tracks user skill levels as they interact with the hub, awarding badges
//! and progressively unlocking features as users become more proficient.
//!
//! ## Badge Categories
//!
//! - **First Steps**: First command, first scene, first device
//! - **Power User**: 100 commands, custom scenes, automation rules
//! - **Voice Expert**: 1000 commands, multi-step commands, natural phrasing
//! - **Smart Home Master**: Full house control, guest permissions, integrations
//!
//! ## Progressive Unlocking
//!
//! Features unlock as users demonstrate proficiency:
//! - Basic: Lights, scenes (always available)
//! - Intermediate: Automation rules, device groups (after 50 commands)
//! - Advanced: Voice training, custom wake words (after 200 commands)
//! - Expert: API access, developer mode (after 500 commands)
//!
//! Colony: Grove (e6) — Growth, nurturing
//!
//! h(x) >= 0. Always.

use anyhow::Result;
use serde::{Deserialize, Serialize};
use std::collections::{HashMap, HashSet};
use std::sync::Arc;
use std::time::{Duration, SystemTime, UNIX_EPOCH};
use tokio::sync::RwLock;
use tracing::{debug, info, warn};

// ============================================================================
// Skill Levels
// ============================================================================

/// User skill level based on experience
#[derive(Debug, Clone, Copy, PartialEq, Eq, PartialOrd, Ord, Hash, Serialize, Deserialize)]
#[serde(rename_all = "snake_case")]
pub enum SkillLevel {
    /// New user (0-49 commands)
    Beginner,
    /// Learning user (50-199 commands)
    Intermediate,
    /// Proficient user (200-499 commands)
    Advanced,
    /// Expert user (500-999 commands)
    Expert,
    /// Master user (1000+ commands)
    Master,
}

impl SkillLevel {
    /// Get skill level from command count
    pub fn from_command_count(count: u32) -> Self {
        match count {
            0..=49 => SkillLevel::Beginner,
            50..=199 => SkillLevel::Intermediate,
            200..=499 => SkillLevel::Advanced,
            500..=999 => SkillLevel::Expert,
            _ => SkillLevel::Master,
        }
    }

    /// Get minimum command count for this level
    pub fn min_commands(&self) -> u32 {
        match self {
            SkillLevel::Beginner => 0,
            SkillLevel::Intermediate => 50,
            SkillLevel::Advanced => 200,
            SkillLevel::Expert => 500,
            SkillLevel::Master => 1000,
        }
    }

    /// Get display name for the level
    pub fn display_name(&self) -> &'static str {
        match self {
            SkillLevel::Beginner => "Beginner",
            SkillLevel::Intermediate => "Intermediate",
            SkillLevel::Advanced => "Advanced",
            SkillLevel::Expert => "Expert",
            SkillLevel::Master => "Master",
        }
    }

    /// Get description for the level
    pub fn description(&self) -> &'static str {
        match self {
            SkillLevel::Beginner => "Just getting started with voice control",
            SkillLevel::Intermediate => "Learning the ropes of smart home control",
            SkillLevel::Advanced => "Proficient with complex commands",
            SkillLevel::Expert => "Expert voice controller",
            SkillLevel::Master => "Master of the smart home",
        }
    }

    /// Get XP required for next level (0 if at max)
    pub fn xp_to_next_level(&self, current_commands: u32) -> u32 {
        match self.next_level() {
            Some(next) => next.min_commands().saturating_sub(current_commands),
            None => 0,
        }
    }

    /// Get next skill level
    pub fn next_level(&self) -> Option<SkillLevel> {
        match self {
            SkillLevel::Beginner => Some(SkillLevel::Intermediate),
            SkillLevel::Intermediate => Some(SkillLevel::Advanced),
            SkillLevel::Advanced => Some(SkillLevel::Expert),
            SkillLevel::Expert => Some(SkillLevel::Master),
            SkillLevel::Master => None,
        }
    }

    /// Get progress percentage within current level (0.0-1.0)
    pub fn progress_in_level(&self, current_commands: u32) -> f32 {
        let min = self.min_commands();
        let max = self.next_level().map(|l| l.min_commands()).unwrap_or(2000);
        let range = max - min;
        let progress = current_commands.saturating_sub(min);
        (progress as f32 / range as f32).min(1.0)
    }
}

// ============================================================================
// Badges
// ============================================================================

/// Badge identifier
#[derive(Debug, Clone, Copy, PartialEq, Eq, Hash, Serialize, Deserialize)]
#[serde(rename_all = "snake_case")]
pub enum BadgeId {
    // First Steps
    FirstCommand,
    FirstScene,
    FirstLight,
    FirstMusic,
    FirstShade,
    FirstLock,
    FirstThermostat,

    // Milestones
    TenCommands,
    FiftyCommands,
    HundredCommands,
    FiveHundredCommands,
    ThousandCommands,

    // Feature Usage
    AutomationCreator,
    DeviceGroupMaster,
    CustomSceneDesigner,
    MultiRoomController,

    // Voice Proficiency
    NaturalSpeaker,    // Uses natural phrasing
    QuickCommander,    // Fast command sequences
    MultiStepMaster,   // Complex multi-part commands
    ErrorFreeStreak,   // 50 commands without errors

    // Time-based
    EarlyBird,         // First command before 7am
    NightOwl,          // Command after midnight
    WeekendWarrior,    // Heavy weekend usage
    DailyUser,         // Used hub for 7 consecutive days
    MonthlyMaster,     // Used hub for 30 consecutive days

    // Special
    VoiceTrainer,      // Contributed voice samples
    BetaTester,        // Participated in beta features
    PowerUser,         // All intermediate features unlocked
    VoiceExpert,       // All advanced features unlocked
    SmartHomeMaster,   // All features unlocked
}

impl BadgeId {
    /// Get display name for the badge
    pub fn display_name(&self) -> &'static str {
        match self {
            BadgeId::FirstCommand => "First Steps",
            BadgeId::FirstScene => "Scene Setter",
            BadgeId::FirstLight => "Light Controller",
            BadgeId::FirstMusic => "DJ Mode",
            BadgeId::FirstShade => "Shade Operator",
            BadgeId::FirstLock => "Security Expert",
            BadgeId::FirstThermostat => "Climate Controller",
            BadgeId::TenCommands => "Getting Started",
            BadgeId::FiftyCommands => "Regular User",
            BadgeId::HundredCommands => "Century",
            BadgeId::FiveHundredCommands => "Power User",
            BadgeId::ThousandCommands => "Voice Master",
            BadgeId::AutomationCreator => "Automator",
            BadgeId::DeviceGroupMaster => "Group Master",
            BadgeId::CustomSceneDesigner => "Scene Designer",
            BadgeId::MultiRoomController => "Multi-Room Master",
            BadgeId::NaturalSpeaker => "Natural Speaker",
            BadgeId::QuickCommander => "Quick Commander",
            BadgeId::MultiStepMaster => "Multi-Step Master",
            BadgeId::ErrorFreeStreak => "Perfectionist",
            BadgeId::EarlyBird => "Early Bird",
            BadgeId::NightOwl => "Night Owl",
            BadgeId::WeekendWarrior => "Weekend Warrior",
            BadgeId::DailyUser => "Daily User",
            BadgeId::MonthlyMaster => "Monthly Master",
            BadgeId::VoiceTrainer => "Voice Trainer",
            BadgeId::BetaTester => "Beta Tester",
            BadgeId::PowerUser => "Power User",
            BadgeId::VoiceExpert => "Voice Expert",
            BadgeId::SmartHomeMaster => "Smart Home Master",
        }
    }

    /// Get description for the badge
    pub fn description(&self) -> &'static str {
        match self {
            BadgeId::FirstCommand => "Execute your first voice command",
            BadgeId::FirstScene => "Activate your first scene",
            BadgeId::FirstLight => "Control a light for the first time",
            BadgeId::FirstMusic => "Play music with your voice",
            BadgeId::FirstShade => "Control shades or blinds",
            BadgeId::FirstLock => "Lock or unlock a door",
            BadgeId::FirstThermostat => "Adjust the thermostat",
            BadgeId::TenCommands => "Execute 10 voice commands",
            BadgeId::FiftyCommands => "Execute 50 voice commands",
            BadgeId::HundredCommands => "Execute 100 voice commands",
            BadgeId::FiveHundredCommands => "Execute 500 voice commands",
            BadgeId::ThousandCommands => "Execute 1000 voice commands",
            BadgeId::AutomationCreator => "Create your first automation rule",
            BadgeId::DeviceGroupMaster => "Create and use device groups",
            BadgeId::CustomSceneDesigner => "Design a custom scene",
            BadgeId::MultiRoomController => "Control devices in multiple rooms",
            BadgeId::NaturalSpeaker => "Use natural language commands",
            BadgeId::QuickCommander => "Execute 5 commands in under 30 seconds",
            BadgeId::MultiStepMaster => "Execute multi-step voice commands",
            BadgeId::ErrorFreeStreak => "50 successful commands without errors",
            BadgeId::EarlyBird => "Use the hub before 7 AM",
            BadgeId::NightOwl => "Use the hub after midnight",
            BadgeId::WeekendWarrior => "Heavy hub usage on weekends",
            BadgeId::DailyUser => "Use the hub for 7 consecutive days",
            BadgeId::MonthlyMaster => "Use the hub for 30 consecutive days",
            BadgeId::VoiceTrainer => "Contribute voice training samples",
            BadgeId::BetaTester => "Participate in beta testing",
            BadgeId::PowerUser => "Unlock all intermediate features",
            BadgeId::VoiceExpert => "Unlock all advanced features",
            BadgeId::SmartHomeMaster => "Unlock all smart home features",
        }
    }

    /// Get rarity tier (affects LED celebration pattern)
    pub fn rarity(&self) -> BadgeRarity {
        match self {
            BadgeId::FirstCommand | BadgeId::TenCommands => BadgeRarity::Common,
            BadgeId::FirstScene | BadgeId::FirstLight | BadgeId::FirstMusic |
            BadgeId::FirstShade | BadgeId::FirstLock | BadgeId::FirstThermostat |
            BadgeId::FiftyCommands | BadgeId::EarlyBird | BadgeId::NightOwl => BadgeRarity::Uncommon,
            BadgeId::HundredCommands | BadgeId::DailyUser | BadgeId::MultiRoomController |
            BadgeId::NaturalSpeaker | BadgeId::AutomationCreator => BadgeRarity::Rare,
            BadgeId::FiveHundredCommands | BadgeId::MonthlyMaster | BadgeId::QuickCommander |
            BadgeId::MultiStepMaster | BadgeId::ErrorFreeStreak | BadgeId::DeviceGroupMaster |
            BadgeId::CustomSceneDesigner | BadgeId::WeekendWarrior => BadgeRarity::Epic,
            BadgeId::ThousandCommands | BadgeId::VoiceTrainer | BadgeId::BetaTester |
            BadgeId::PowerUser | BadgeId::VoiceExpert | BadgeId::SmartHomeMaster => BadgeRarity::Legendary,
        }
    }

    /// Get LED ring pattern for badge unlock celebration
    pub fn led_pattern(&self) -> &'static str {
        match self.rarity() {
            BadgeRarity::Common => "flash_green",
            BadgeRarity::Uncommon => "pulse_cyan",
            BadgeRarity::Rare => "cascade_purple",
            BadgeRarity::Epic => "rainbow_spin",
            BadgeRarity::Legendary => "spectral_sweep",
        }
    }
}

/// Badge rarity tier
#[derive(Debug, Clone, Copy, PartialEq, Eq, PartialOrd, Ord, Hash, Serialize, Deserialize)]
#[serde(rename_all = "snake_case")]
pub enum BadgeRarity {
    Common,
    Uncommon,
    Rare,
    Epic,
    Legendary,
}

/// Awarded badge with metadata
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct AwardedBadge {
    /// Badge identifier
    pub badge_id: BadgeId,
    /// When the badge was awarded
    pub awarded_at: u64,
    /// Context for the award (e.g., which command triggered it)
    pub context: Option<String>,
}

impl AwardedBadge {
    /// Create a new awarded badge
    pub fn new(badge_id: BadgeId) -> Self {
        let awarded_at = SystemTime::now()
            .duration_since(UNIX_EPOCH)
            .unwrap_or_default()
            .as_secs();

        Self {
            badge_id,
            awarded_at,
            context: None,
        }
    }

    /// Create with context
    pub fn with_context(badge_id: BadgeId, context: &str) -> Self {
        let mut badge = Self::new(badge_id);
        badge.context = Some(context.to_string());
        badge
    }
}

// ============================================================================
// Unlockable Features
// ============================================================================

/// Features that can be unlocked through progression
#[derive(Debug, Clone, Copy, PartialEq, Eq, Hash, Serialize, Deserialize)]
#[serde(rename_all = "snake_case")]
pub enum Feature {
    // Basic (always available)
    LightControl,
    SceneActivation,
    MusicControl,
    BasicStatus,

    // Intermediate (50+ commands)
    AutomationRules,
    DeviceGroups,
    ScheduledCommands,
    MultiRoomControl,

    // Advanced (200+ commands)
    VoiceTraining,
    CustomWakeWords,
    CustomScenes,
    GuestPermissions,

    // Expert (500+ commands)
    ApiAccess,
    DeveloperMode,
    AdvancedAutomation,
    MeshNetworking,

    // Master (1000+ commands)
    BetaFeatures,
    VoiceCloning,
    FullSystemControl,
}

impl Feature {
    /// Get minimum skill level required
    pub fn required_level(&self) -> SkillLevel {
        match self {
            Feature::LightControl | Feature::SceneActivation |
            Feature::MusicControl | Feature::BasicStatus => SkillLevel::Beginner,

            Feature::AutomationRules | Feature::DeviceGroups |
            Feature::ScheduledCommands | Feature::MultiRoomControl => SkillLevel::Intermediate,

            Feature::VoiceTraining | Feature::CustomWakeWords |
            Feature::CustomScenes | Feature::GuestPermissions => SkillLevel::Advanced,

            Feature::ApiAccess | Feature::DeveloperMode |
            Feature::AdvancedAutomation | Feature::MeshNetworking => SkillLevel::Expert,

            Feature::BetaFeatures | Feature::VoiceCloning |
            Feature::FullSystemControl => SkillLevel::Master,
        }
    }

    /// Get display name
    pub fn display_name(&self) -> &'static str {
        match self {
            Feature::LightControl => "Light Control",
            Feature::SceneActivation => "Scene Activation",
            Feature::MusicControl => "Music Control",
            Feature::BasicStatus => "Basic Status",
            Feature::AutomationRules => "Automation Rules",
            Feature::DeviceGroups => "Device Groups",
            Feature::ScheduledCommands => "Scheduled Commands",
            Feature::MultiRoomControl => "Multi-Room Control",
            Feature::VoiceTraining => "Voice Training",
            Feature::CustomWakeWords => "Custom Wake Words",
            Feature::CustomScenes => "Custom Scenes",
            Feature::GuestPermissions => "Guest Permissions",
            Feature::ApiAccess => "API Access",
            Feature::DeveloperMode => "Developer Mode",
            Feature::AdvancedAutomation => "Advanced Automation",
            Feature::MeshNetworking => "Mesh Networking",
            Feature::BetaFeatures => "Beta Features",
            Feature::VoiceCloning => "Voice Cloning",
            Feature::FullSystemControl => "Full System Control",
        }
    }
}

// ============================================================================
// User Profile
// ============================================================================

/// User skill progression profile
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct UserProfile {
    /// User identifier
    pub user_id: String,
    /// Display name
    pub name: String,
    /// Total successful commands
    pub total_commands: u32,
    /// Commands executed today
    pub commands_today: u32,
    /// Current streak (consecutive successful commands)
    pub current_streak: u32,
    /// Best streak ever
    pub best_streak: u32,
    /// Current skill level
    pub skill_level: SkillLevel,
    /// Awarded badges
    pub badges: Vec<AwardedBadge>,
    /// Command types used (for tracking first-time usage)
    pub command_types_used: HashSet<String>,
    /// Rooms controlled (for multi-room tracking)
    pub rooms_controlled: HashSet<String>,
    /// Days active (unix timestamps of unique days)
    pub active_days: HashSet<u64>,
    /// Timestamp of first command
    pub first_command_at: Option<u64>,
    /// Timestamp of last command
    pub last_command_at: Option<u64>,
    /// Profile creation timestamp
    pub created_at: u64,
}

impl UserProfile {
    /// Create a new user profile
    pub fn new(user_id: &str, name: &str) -> Self {
        let created_at = SystemTime::now()
            .duration_since(UNIX_EPOCH)
            .unwrap_or_default()
            .as_secs();

        Self {
            user_id: user_id.to_string(),
            name: name.to_string(),
            total_commands: 0,
            commands_today: 0,
            current_streak: 0,
            best_streak: 0,
            skill_level: SkillLevel::Beginner,
            badges: Vec::new(),
            command_types_used: HashSet::new(),
            rooms_controlled: HashSet::new(),
            active_days: HashSet::new(),
            first_command_at: None,
            last_command_at: None,
            created_at,
        }
    }

    /// Check if user has a specific badge
    pub fn has_badge(&self, badge_id: BadgeId) -> bool {
        self.badges.iter().any(|b| b.badge_id == badge_id)
    }

    /// Award a badge (if not already awarded)
    pub fn award_badge(&mut self, badge_id: BadgeId, context: Option<&str>) -> Option<AwardedBadge> {
        if self.has_badge(badge_id) {
            return None;
        }

        let badge = match context {
            Some(ctx) => AwardedBadge::with_context(badge_id, ctx),
            None => AwardedBadge::new(badge_id),
        };

        self.badges.push(badge.clone());
        info!("User {} earned badge: {:?}", self.name, badge_id);

        Some(badge)
    }

    /// Check if a feature is unlocked
    pub fn is_feature_unlocked(&self, feature: Feature) -> bool {
        self.skill_level >= feature.required_level()
    }

    /// Get all unlocked features
    pub fn unlocked_features(&self) -> Vec<Feature> {
        vec![
            Feature::LightControl,
            Feature::SceneActivation,
            Feature::MusicControl,
            Feature::BasicStatus,
            Feature::AutomationRules,
            Feature::DeviceGroups,
            Feature::ScheduledCommands,
            Feature::MultiRoomControl,
            Feature::VoiceTraining,
            Feature::CustomWakeWords,
            Feature::CustomScenes,
            Feature::GuestPermissions,
            Feature::ApiAccess,
            Feature::DeveloperMode,
            Feature::AdvancedAutomation,
            Feature::MeshNetworking,
            Feature::BetaFeatures,
            Feature::VoiceCloning,
            Feature::FullSystemControl,
        ].into_iter()
        .filter(|f| self.is_feature_unlocked(*f))
        .collect()
    }

    /// Get progress summary
    pub fn progress_summary(&self) -> ProgressSummary {
        ProgressSummary {
            skill_level: self.skill_level,
            total_commands: self.total_commands,
            badges_earned: self.badges.len() as u32,
            features_unlocked: self.unlocked_features().len() as u32,
            progress_to_next_level: self.skill_level.progress_in_level(self.total_commands),
            commands_to_next_level: self.skill_level.xp_to_next_level(self.total_commands),
            current_streak: self.current_streak,
            consecutive_days: self.calculate_consecutive_days(),
        }
    }

    /// Calculate consecutive active days
    fn calculate_consecutive_days(&self) -> u32 {
        if self.active_days.is_empty() {
            return 0;
        }

        let today = SystemTime::now()
            .duration_since(UNIX_EPOCH)
            .unwrap_or_default()
            .as_secs() / 86400;

        let mut days: Vec<u64> = self.active_days.iter().cloned().collect();
        days.sort_by(|a, b| b.cmp(a)); // Most recent first

        let mut consecutive = 0u32;
        let mut expected_day = today;

        for day in days {
            if day == expected_day || day == expected_day - 1 {
                consecutive += 1;
                expected_day = day;
            } else {
                break;
            }
        }

        consecutive
    }
}

/// Progress summary for display
#[derive(Debug, Clone, Serialize)]
pub struct ProgressSummary {
    pub skill_level: SkillLevel,
    pub total_commands: u32,
    pub badges_earned: u32,
    pub features_unlocked: u32,
    pub progress_to_next_level: f32,
    pub commands_to_next_level: u32,
    pub current_streak: u32,
    pub consecutive_days: u32,
}

// ============================================================================
// Skill Progression Manager
// ============================================================================

/// Manages skill progression for all users
pub struct SkillProgressionManager {
    /// User profiles
    profiles: Arc<RwLock<HashMap<String, UserProfile>>>,
    /// Channel for badge notifications
    badge_notification_tx: tokio::sync::broadcast::Sender<BadgeNotification>,
    /// Channel for level-up notifications
    level_up_tx: tokio::sync::broadcast::Sender<LevelUpNotification>,
}

/// Badge unlock notification
#[derive(Debug, Clone)]
pub struct BadgeNotification {
    pub user_id: String,
    pub badge: AwardedBadge,
    pub led_pattern: String,
    pub voice_announcement: String,
}

/// Level-up notification
#[derive(Debug, Clone)]
pub struct LevelUpNotification {
    pub user_id: String,
    pub old_level: SkillLevel,
    pub new_level: SkillLevel,
    pub new_features: Vec<Feature>,
    pub voice_announcement: String,
}

impl SkillProgressionManager {
    /// Create a new skill progression manager
    pub fn new() -> (Self, tokio::sync::broadcast::Receiver<BadgeNotification>, tokio::sync::broadcast::Receiver<LevelUpNotification>) {
        let (badge_tx, badge_rx) = tokio::sync::broadcast::channel(32);
        let (level_tx, level_rx) = tokio::sync::broadcast::channel(32);

        let manager = Self {
            profiles: Arc::new(RwLock::new(HashMap::new())),
            badge_notification_tx: badge_tx,
            level_up_tx: level_tx,
        };

        (manager, badge_rx, level_rx)
    }

    /// Get or create a user profile
    pub async fn get_or_create_profile(&self, user_id: &str, name: &str) -> UserProfile {
        let mut profiles = self.profiles.write().await;

        if let Some(profile) = profiles.get(user_id) {
            return profile.clone();
        }

        let profile = UserProfile::new(user_id, name);
        profiles.insert(user_id.to_string(), profile.clone());
        profile
    }

    /// Record a successful command
    pub async fn record_command(
        &self,
        user_id: &str,
        command_type: &str,
        rooms: Option<&[String]>,
    ) -> Vec<BadgeNotification> {
        let mut profiles = self.profiles.write().await;
        let mut notifications = Vec::new();

        let profile = profiles.entry(user_id.to_string())
            .or_insert_with(|| UserProfile::new(user_id, "User"));

        let now = SystemTime::now()
            .duration_since(UNIX_EPOCH)
            .unwrap_or_default()
            .as_secs();

        let today = now / 86400;
        let hour = (now % 86400) / 3600;

        // Update timestamps
        if profile.first_command_at.is_none() {
            profile.first_command_at = Some(now);
        }
        profile.last_command_at = Some(now);

        // Update command counts
        profile.total_commands += 1;
        profile.commands_today += 1;
        profile.current_streak += 1;
        profile.best_streak = profile.best_streak.max(profile.current_streak);

        // Track active days
        profile.active_days.insert(today);

        // Track command type
        let first_of_type = !profile.command_types_used.contains(command_type);
        profile.command_types_used.insert(command_type.to_string());

        // Track rooms
        if let Some(room_list) = rooms {
            for room in room_list {
                profile.rooms_controlled.insert(room.clone());
            }
        }

        // Check for level up
        let old_level = profile.skill_level;
        let new_level = SkillLevel::from_command_count(profile.total_commands);

        if new_level > old_level {
            profile.skill_level = new_level;

            // Determine newly unlocked features
            let new_features: Vec<Feature> = vec![
                Feature::LightControl,
                Feature::SceneActivation,
                Feature::MusicControl,
                Feature::BasicStatus,
                Feature::AutomationRules,
                Feature::DeviceGroups,
                Feature::ScheduledCommands,
                Feature::MultiRoomControl,
                Feature::VoiceTraining,
                Feature::CustomWakeWords,
                Feature::CustomScenes,
                Feature::GuestPermissions,
                Feature::ApiAccess,
                Feature::DeveloperMode,
                Feature::AdvancedAutomation,
                Feature::MeshNetworking,
                Feature::BetaFeatures,
                Feature::VoiceCloning,
                Feature::FullSystemControl,
            ].into_iter()
            .filter(|f| f.required_level() == new_level)
            .collect();

            let announcement = format!(
                "Congratulations {}! You've reached {} level. {} new features unlocked.",
                profile.name,
                new_level.display_name(),
                new_features.len()
            );

            let level_up = LevelUpNotification {
                user_id: user_id.to_string(),
                old_level,
                new_level,
                new_features,
                voice_announcement: announcement,
            };

            let _ = self.level_up_tx.send(level_up);
            info!("User {} leveled up: {:?} -> {:?}", profile.name, old_level, new_level);
        }

        // Check badge conditions
        notifications.extend(self.check_badges(profile, command_type, first_of_type, hour, today));

        notifications
    }

    /// Record a failed command (resets streak)
    pub async fn record_failure(&self, user_id: &str) {
        let mut profiles = self.profiles.write().await;

        if let Some(profile) = profiles.get_mut(user_id) {
            profile.current_streak = 0;
        }
    }

    /// Check and award applicable badges
    fn check_badges(
        &self,
        profile: &mut UserProfile,
        command_type: &str,
        first_of_type: bool,
        hour: u64,
        _today: u64,
    ) -> Vec<BadgeNotification> {
        let mut notifications = Vec::new();

        // First command badge
        if profile.total_commands == 1 {
            if let Some(badge) = profile.award_badge(BadgeId::FirstCommand, None) {
                notifications.push(self.create_badge_notification(&profile.user_id, badge));
            }
        }

        // Command milestone badges
        let milestones = [
            (10, BadgeId::TenCommands),
            (50, BadgeId::FiftyCommands),
            (100, BadgeId::HundredCommands),
            (500, BadgeId::FiveHundredCommands),
            (1000, BadgeId::ThousandCommands),
        ];

        for (count, badge_id) in milestones {
            if profile.total_commands == count {
                if let Some(badge) = profile.award_badge(badge_id, None) {
                    notifications.push(self.create_badge_notification(&profile.user_id, badge));
                }
            }
        }

        // First-time usage badges
        if first_of_type {
            let type_badges = [
                ("scene", BadgeId::FirstScene),
                ("lights", BadgeId::FirstLight),
                ("music", BadgeId::FirstMusic),
                ("shades", BadgeId::FirstShade),
                ("lock", BadgeId::FirstLock),
                ("thermostat", BadgeId::FirstThermostat),
            ];

            for (cmd_type, badge_id) in type_badges {
                if command_type.contains(cmd_type) {
                    if let Some(badge) = profile.award_badge(badge_id, Some(command_type)) {
                        notifications.push(self.create_badge_notification(&profile.user_id, badge));
                    }
                }
            }
        }

        // Time-based badges
        if hour < 7 && !profile.has_badge(BadgeId::EarlyBird) {
            if let Some(badge) = profile.award_badge(BadgeId::EarlyBird, None) {
                notifications.push(self.create_badge_notification(&profile.user_id, badge));
            }
        }

        if hour >= 24 || hour < 4 {
            if !profile.has_badge(BadgeId::NightOwl) {
                if let Some(badge) = profile.award_badge(BadgeId::NightOwl, None) {
                    notifications.push(self.create_badge_notification(&profile.user_id, badge));
                }
            }
        }

        // Streak badges
        if profile.current_streak >= 50 && !profile.has_badge(BadgeId::ErrorFreeStreak) {
            if let Some(badge) = profile.award_badge(BadgeId::ErrorFreeStreak, None) {
                notifications.push(self.create_badge_notification(&profile.user_id, badge));
            }
        }

        // Consecutive days badges
        let consecutive_days = profile.calculate_consecutive_days();
        if consecutive_days >= 7 && !profile.has_badge(BadgeId::DailyUser) {
            if let Some(badge) = profile.award_badge(BadgeId::DailyUser, None) {
                notifications.push(self.create_badge_notification(&profile.user_id, badge));
            }
        }
        if consecutive_days >= 30 && !profile.has_badge(BadgeId::MonthlyMaster) {
            if let Some(badge) = profile.award_badge(BadgeId::MonthlyMaster, None) {
                notifications.push(self.create_badge_notification(&profile.user_id, badge));
            }
        }

        // Multi-room badge
        if profile.rooms_controlled.len() >= 3 && !profile.has_badge(BadgeId::MultiRoomController) {
            if let Some(badge) = profile.award_badge(BadgeId::MultiRoomController, None) {
                notifications.push(self.create_badge_notification(&profile.user_id, badge));
            }
        }

        // Meta badges
        if profile.skill_level >= SkillLevel::Intermediate && !profile.has_badge(BadgeId::PowerUser) {
            if let Some(badge) = profile.award_badge(BadgeId::PowerUser, None) {
                notifications.push(self.create_badge_notification(&profile.user_id, badge));
            }
        }
        if profile.skill_level >= SkillLevel::Advanced && !profile.has_badge(BadgeId::VoiceExpert) {
            if let Some(badge) = profile.award_badge(BadgeId::VoiceExpert, None) {
                notifications.push(self.create_badge_notification(&profile.user_id, badge));
            }
        }
        if profile.skill_level >= SkillLevel::Master && !profile.has_badge(BadgeId::SmartHomeMaster) {
            if let Some(badge) = profile.award_badge(BadgeId::SmartHomeMaster, None) {
                notifications.push(self.create_badge_notification(&profile.user_id, badge));
            }
        }

        notifications
    }

    /// Create badge notification
    fn create_badge_notification(&self, user_id: &str, badge: AwardedBadge) -> BadgeNotification {
        let display_name = badge.badge_id.display_name();
        let rarity = badge.badge_id.rarity();
        let led_pattern = badge.badge_id.led_pattern().to_string();

        let rarity_prefix = match rarity {
            BadgeRarity::Common => "",
            BadgeRarity::Uncommon => "Nice! ",
            BadgeRarity::Rare => "Excellent! ",
            BadgeRarity::Epic => "Amazing! ",
            BadgeRarity::Legendary => "Legendary! ",
        };

        let voice_announcement = format!(
            "{}You earned the {} badge! {}",
            rarity_prefix,
            display_name,
            badge.badge_id.description()
        );

        let notification = BadgeNotification {
            user_id: user_id.to_string(),
            badge,
            led_pattern,
            voice_announcement,
        };

        let _ = self.badge_notification_tx.send(notification.clone());
        notification
    }

    /// Get user profile
    pub async fn get_profile(&self, user_id: &str) -> Option<UserProfile> {
        let profiles = self.profiles.read().await;
        profiles.get(user_id).cloned()
    }

    /// Get all profiles
    pub async fn get_all_profiles(&self) -> Vec<UserProfile> {
        let profiles = self.profiles.read().await;
        profiles.values().cloned().collect()
    }

    /// Get leaderboard (top users by command count)
    pub async fn get_leaderboard(&self, limit: usize) -> Vec<LeaderboardEntry> {
        let profiles = self.profiles.read().await;
        let mut entries: Vec<_> = profiles.values()
            .map(|p| LeaderboardEntry {
                user_id: p.user_id.clone(),
                name: p.name.clone(),
                total_commands: p.total_commands,
                skill_level: p.skill_level,
                badges_count: p.badges.len() as u32,
            })
            .collect();

        entries.sort_by(|a, b| b.total_commands.cmp(&a.total_commands));
        entries.truncate(limit);
        entries
    }

    /// Check if a feature is unlocked for a user
    pub async fn is_feature_unlocked(&self, user_id: &str, feature: Feature) -> bool {
        let profiles = self.profiles.read().await;
        profiles.get(user_id)
            .map(|p| p.is_feature_unlocked(feature))
            .unwrap_or(feature.required_level() == SkillLevel::Beginner)
    }

    /// Manually award a badge (for special occasions)
    pub async fn award_special_badge(&self, user_id: &str, badge_id: BadgeId, context: &str) -> Option<BadgeNotification> {
        let mut profiles = self.profiles.write().await;

        let profile = profiles.get_mut(user_id)?;

        if let Some(badge) = profile.award_badge(badge_id, Some(context)) {
            return Some(self.create_badge_notification(user_id, badge));
        }

        None
    }
}

impl Default for SkillProgressionManager {
    fn default() -> Self {
        let (manager, _, _) = Self::new();
        manager
    }
}

/// Leaderboard entry
#[derive(Debug, Clone, Serialize)]
pub struct LeaderboardEntry {
    pub user_id: String,
    pub name: String,
    pub total_commands: u32,
    pub skill_level: SkillLevel,
    pub badges_count: u32,
}

// ============================================================================
// Tests
// ============================================================================

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_skill_level_from_commands() {
        assert_eq!(SkillLevel::from_command_count(0), SkillLevel::Beginner);
        assert_eq!(SkillLevel::from_command_count(49), SkillLevel::Beginner);
        assert_eq!(SkillLevel::from_command_count(50), SkillLevel::Intermediate);
        assert_eq!(SkillLevel::from_command_count(199), SkillLevel::Intermediate);
        assert_eq!(SkillLevel::from_command_count(200), SkillLevel::Advanced);
        assert_eq!(SkillLevel::from_command_count(500), SkillLevel::Expert);
        assert_eq!(SkillLevel::from_command_count(1000), SkillLevel::Master);
        assert_eq!(SkillLevel::from_command_count(5000), SkillLevel::Master);
    }

    #[test]
    fn test_skill_level_progress() {
        assert_eq!(SkillLevel::Beginner.progress_in_level(0), 0.0);
        assert_eq!(SkillLevel::Beginner.progress_in_level(25), 0.5);
        assert_eq!(SkillLevel::Beginner.progress_in_level(50), 1.0);
    }

    #[test]
    fn test_user_profile_badges() {
        let mut profile = UserProfile::new("user1", "Test User");

        assert!(!profile.has_badge(BadgeId::FirstCommand));

        let badge = profile.award_badge(BadgeId::FirstCommand, None);
        assert!(badge.is_some());
        assert!(profile.has_badge(BadgeId::FirstCommand));

        // Can't award same badge twice
        let badge2 = profile.award_badge(BadgeId::FirstCommand, None);
        assert!(badge2.is_none());
    }

    #[test]
    fn test_feature_unlocking() {
        let mut profile = UserProfile::new("user1", "Test User");

        // Basic features always unlocked
        assert!(profile.is_feature_unlocked(Feature::LightControl));
        assert!(profile.is_feature_unlocked(Feature::SceneActivation));

        // Intermediate features locked initially
        assert!(!profile.is_feature_unlocked(Feature::AutomationRules));

        // Level up to intermediate
        profile.total_commands = 50;
        profile.skill_level = SkillLevel::from_command_count(50);

        assert!(profile.is_feature_unlocked(Feature::AutomationRules));
        assert!(!profile.is_feature_unlocked(Feature::VoiceTraining));

        // Level up to advanced
        profile.total_commands = 200;
        profile.skill_level = SkillLevel::from_command_count(200);

        assert!(profile.is_feature_unlocked(Feature::VoiceTraining));
    }

    #[test]
    fn test_badge_rarity() {
        assert_eq!(BadgeId::FirstCommand.rarity(), BadgeRarity::Common);
        assert_eq!(BadgeId::FirstScene.rarity(), BadgeRarity::Uncommon);
        assert_eq!(BadgeId::HundredCommands.rarity(), BadgeRarity::Rare);
        assert_eq!(BadgeId::FiveHundredCommands.rarity(), BadgeRarity::Epic);
        assert_eq!(BadgeId::ThousandCommands.rarity(), BadgeRarity::Legendary);
    }

    #[tokio::test]
    async fn test_skill_progression_manager() {
        let (manager, _badge_rx, _level_rx) = SkillProgressionManager::new();

        // Record first command
        let notifications = manager.record_command("user1", "lights", Some(&["Living Room".to_string()])).await;

        // Should get FirstCommand and FirstLight badges
        assert!(notifications.iter().any(|n| n.badge.badge_id == BadgeId::FirstCommand));
        assert!(notifications.iter().any(|n| n.badge.badge_id == BadgeId::FirstLight));

        // Get profile
        let profile = manager.get_profile("user1").await.unwrap();
        assert_eq!(profile.total_commands, 1);
        assert!(profile.has_badge(BadgeId::FirstCommand));
    }

    #[tokio::test]
    async fn test_milestone_badges() {
        let (manager, _badge_rx, _level_rx) = SkillProgressionManager::new();

        // Record 10 commands
        for i in 0..10 {
            manager.record_command("user1", "lights", None).await;
        }

        let profile = manager.get_profile("user1").await.unwrap();
        assert!(profile.has_badge(BadgeId::TenCommands));
    }

    #[tokio::test]
    async fn test_level_up() {
        let (manager, _badge_rx, _level_rx) = SkillProgressionManager::new();

        // Get initial profile
        let profile = manager.get_or_create_profile("user1", "Test User").await;
        assert_eq!(profile.skill_level, SkillLevel::Beginner);

        // Record 50 commands to reach intermediate
        for _ in 0..50 {
            manager.record_command("user1", "lights", None).await;
        }

        let profile = manager.get_profile("user1").await.unwrap();
        assert_eq!(profile.skill_level, SkillLevel::Intermediate);
    }

    #[tokio::test]
    async fn test_leaderboard() {
        let (manager, _badge_rx, _level_rx) = SkillProgressionManager::new();

        // Create users with different command counts
        for _ in 0..100 {
            manager.record_command("user1", "lights", None).await;
        }
        for _ in 0..50 {
            manager.record_command("user2", "lights", None).await;
        }
        for _ in 0..200 {
            manager.record_command("user3", "lights", None).await;
        }

        let leaderboard = manager.get_leaderboard(10).await;
        assert_eq!(leaderboard.len(), 3);
        assert_eq!(leaderboard[0].user_id, "user3");
        assert_eq!(leaderboard[1].user_id, "user1");
        assert_eq!(leaderboard[2].user_id, "user2");
    }
}

/*
 * Grove nurtures growth. Users level up through natural use.
 * Badges celebrate milestones. Features unlock progressively.
 * The system grows with the user.
 *
 * h(x) >= 0. Always.
 */
