//! Automation Rule Engine
//!
//! Defines automation rules with triggers, conditions, and actions.
//! Supports time-based, event-based, and state-based automations.
//!
//! Colony: Beacon (e5) - Orchestration and coordination
//!
//! h(x) >= 0 always

use serde::{Deserialize, Serialize};
use std::collections::HashMap;
use std::time::{Duration, Instant};

// ============================================================================
// Automation Rules
// ============================================================================

/// An automation rule
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct AutomationRule {
    /// Unique rule identifier
    pub id: String,
    /// Human-readable name
    pub name: String,
    /// Description
    pub description: Option<String>,
    /// Trigger conditions
    pub triggers: Vec<Trigger>,
    /// Conditions that must be true
    pub conditions: Vec<Condition>,
    /// Actions to execute
    pub actions: Vec<Action>,
    /// Is rule enabled
    pub enabled: bool,
    /// Priority (higher = executes first)
    pub priority: i32,
    /// Cooldown between executions (seconds)
    pub cooldown_secs: u32,
    /// Last execution timestamp
    #[serde(skip)]
    pub last_triggered: Option<Instant>,
    /// Execution count
    pub execution_count: u64,
    /// Creation timestamp
    pub created_at: u64,
    /// Last modified timestamp
    pub updated_at: u64,
}

impl AutomationRule {
    /// Create a new automation rule
    pub fn new(id: &str, name: &str) -> Self {
        let now = std::time::SystemTime::now()
            .duration_since(std::time::UNIX_EPOCH)
            .unwrap_or_default()
            .as_secs();

        Self {
            id: id.to_string(),
            name: name.to_string(),
            description: None,
            triggers: vec![],
            conditions: vec![],
            actions: vec![],
            enabled: true,
            priority: 0,
            cooldown_secs: 0,
            last_triggered: None,
            execution_count: 0,
            created_at: now,
            updated_at: now,
        }
    }

    /// Check if rule can execute (cooldown check)
    pub fn can_execute(&self) -> bool {
        if !self.enabled {
            return false;
        }

        if self.cooldown_secs == 0 {
            return true;
        }

        match self.last_triggered {
            Some(last) => last.elapsed() >= Duration::from_secs(self.cooldown_secs as u64),
            None => true,
        }
    }

    /// Mark rule as triggered
    pub fn mark_triggered(&mut self) {
        self.last_triggered = Some(Instant::now());
        self.execution_count += 1;
    }

    /// Update modified timestamp
    pub(crate) fn touch(&mut self) {
        self.updated_at = std::time::SystemTime::now()
            .duration_since(std::time::UNIX_EPOCH)
            .unwrap_or_default()
            .as_secs();
    }
}

// ============================================================================
// Triggers
// ============================================================================

/// Trigger that can start an automation
#[derive(Debug, Clone, Serialize, Deserialize)]
#[serde(tag = "type", rename_all = "snake_case")]
pub enum Trigger {
    /// Time-based trigger
    Time(TimeTrigger),
    /// Device state change
    DeviceState(DeviceStateTrigger),
    /// Event trigger
    Event(EventTrigger),
    /// Presence trigger
    Presence(PresenceTrigger),
    /// Voice command trigger
    VoiceCommand(VoiceCommandTrigger),
    /// Sunrise/sunset trigger
    Sun(SunTrigger),
    /// Webhook trigger
    Webhook(WebhookTrigger),
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct TimeTrigger {
    /// Cron-like schedule (HH:MM format for simple)
    pub schedule: String,
    /// Days of week (0 = Sunday)
    pub days: Vec<u8>,
    /// Timezone offset
    pub timezone_offset_hours: i8,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct DeviceStateTrigger {
    /// Device ID to watch
    pub device_id: String,
    /// Attribute to watch
    pub attribute: String,
    /// Trigger condition
    pub condition: StateCondition,
    /// Value to compare
    pub value: serde_json::Value,
    /// Duration the state must be held
    pub for_duration_secs: Option<u32>,
}

#[derive(Debug, Clone, Copy, Serialize, Deserialize)]
#[serde(rename_all = "snake_case")]
pub enum StateCondition {
    Equals,
    NotEquals,
    GreaterThan,
    LessThan,
    GreaterOrEqual,
    LessOrEqual,
    Changes,
    ChangesTo,
    ChangesFrom,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct EventTrigger {
    /// Event type to watch
    pub event_type: String,
    /// Event source filter
    pub source: Option<String>,
    /// Event data filters
    pub filters: HashMap<String, serde_json::Value>,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct PresenceTrigger {
    /// User ID
    pub user_id: Option<String>,
    /// Zone to watch
    pub zone: Option<String>,
    /// Presence state
    pub state: PresenceState,
}

#[derive(Debug, Clone, Copy, Serialize, Deserialize)]
#[serde(rename_all = "snake_case")]
pub enum PresenceState {
    Home,
    Away,
    Arriving,
    Leaving,
    Sleeping,
    Awake,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct VoiceCommandTrigger {
    /// Phrases that trigger this automation
    pub phrases: Vec<String>,
    /// Require exact match
    pub exact_match: bool,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct SunTrigger {
    /// Sun event type
    pub event: SunEvent,
    /// Offset in minutes (negative = before, positive = after)
    pub offset_minutes: i32,
}

#[derive(Debug, Clone, Copy, Serialize, Deserialize)]
#[serde(rename_all = "snake_case")]
pub enum SunEvent {
    Sunrise,
    Sunset,
    Dawn,
    Dusk,
    Noon,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct WebhookTrigger {
    /// Webhook ID
    pub webhook_id: String,
    /// Required payload fields
    pub required_fields: Vec<String>,
}

// ============================================================================
// Conditions
// ============================================================================

/// Condition that must be true for automation to run
#[derive(Debug, Clone, Serialize, Deserialize)]
#[serde(tag = "type", rename_all = "snake_case")]
pub enum Condition {
    /// Time-based condition
    Time(TimeCondition),
    /// Device state condition
    DeviceState(DeviceStateCondition),
    /// Presence condition
    Presence(PresenceCondition),
    /// Logical AND of conditions
    And(Vec<Condition>),
    /// Logical OR of conditions
    Or(Vec<Condition>),
    /// Logical NOT
    Not(Box<Condition>),
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct TimeCondition {
    /// Start time (HH:MM)
    pub after: Option<String>,
    /// End time (HH:MM)
    pub before: Option<String>,
    /// Allowed days
    pub days: Option<Vec<u8>>,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct DeviceStateCondition {
    /// Device ID
    pub device_id: String,
    /// Attribute
    pub attribute: String,
    /// Comparison
    pub condition: StateCondition,
    /// Value
    pub value: serde_json::Value,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct PresenceCondition {
    /// User ID (None = any user)
    pub user_id: Option<String>,
    /// Required state
    pub state: PresenceState,
}

// ============================================================================
// Actions
// ============================================================================

/// Action to execute when automation triggers
#[derive(Debug, Clone, Serialize, Deserialize)]
#[serde(tag = "type", rename_all = "snake_case")]
pub enum Action {
    /// Control a device
    DeviceControl(DeviceControlAction),
    /// Control a group
    GroupControl(GroupControlAction),
    /// Activate a scene
    Scene(SceneAction),
    /// Send notification
    Notification(NotificationAction),
    /// Make announcement
    Announcement(AnnouncementAction),
    /// Delay execution
    Delay(DelayAction),
    /// Run another automation
    RunAutomation(RunAutomationAction),
    /// Call API endpoint
    ApiCall(ApiCallAction),
    /// Execute script
    Script(ScriptAction),
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct DeviceControlAction {
    /// Device ID
    pub device_id: String,
    /// Service to call
    pub service: String,
    /// Service parameters
    pub params: HashMap<String, serde_json::Value>,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct GroupControlAction {
    /// Group ID
    pub group_id: String,
    /// Service to call
    pub service: String,
    /// Service parameters
    pub params: HashMap<String, serde_json::Value>,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct SceneAction {
    /// Scene name
    pub name: String,
    /// Transition time in seconds
    pub transition: Option<f32>,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct NotificationAction {
    /// Notification title
    pub title: String,
    /// Notification message
    pub message: String,
    /// Target users
    pub targets: Vec<String>,
    /// Priority
    pub priority: NotificationPriority,
}

#[derive(Debug, Clone, Copy, Serialize, Deserialize)]
#[serde(rename_all = "snake_case")]
pub enum NotificationPriority {
    Low,
    Normal,
    High,
    Critical,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct AnnouncementAction {
    /// Message to announce
    pub message: String,
    /// Target rooms (empty = all)
    pub rooms: Vec<String>,
    /// Volume (0.0 - 1.0)
    pub volume: Option<f32>,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct DelayAction {
    /// Delay in seconds
    pub seconds: u32,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct RunAutomationAction {
    /// Automation ID to run
    pub automation_id: String,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct ApiCallAction {
    /// HTTP method
    pub method: String,
    /// URL
    pub url: String,
    /// Headers
    pub headers: HashMap<String, String>,
    /// Request body
    pub body: Option<serde_json::Value>,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct ScriptAction {
    /// Script content or path
    pub script: String,
    /// Script type
    pub script_type: ScriptType,
}

#[derive(Debug, Clone, Copy, Serialize, Deserialize)]
#[serde(rename_all = "snake_case")]
pub enum ScriptType {
    Shell,
    Python,
    Inline,
}

// ============================================================================
// Tests
// ============================================================================

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_automation_rule_cooldown() {
        let mut rule = AutomationRule::new("test-rule", "Test Rule");
        rule.cooldown_secs = 60;

        assert!(rule.can_execute());

        rule.mark_triggered();
        assert!(!rule.can_execute());
    }

    #[test]
    fn test_automation_rule_disabled() {
        let mut rule = AutomationRule::new("test-rule", "Test Rule");
        rule.enabled = false;

        assert!(!rule.can_execute());
    }

    #[test]
    fn test_automation_rule_no_cooldown() {
        let mut rule = AutomationRule::new("test-rule", "Test Rule");
        rule.cooldown_secs = 0;

        assert!(rule.can_execute());
        rule.mark_triggered();
        assert!(rule.can_execute()); // No cooldown, can execute again
    }

    #[test]
    fn test_automation_rule_execution_count() {
        let mut rule = AutomationRule::new("test-rule", "Test Rule");
        assert_eq!(rule.execution_count, 0);

        rule.mark_triggered();
        assert_eq!(rule.execution_count, 1);

        rule.mark_triggered();
        assert_eq!(rule.execution_count, 2);
    }
}
