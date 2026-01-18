//! Automation Engine for Kagami Hub
//!
//! Device grouping, automation triggers, and rule-based control.
//! Supports time-based, event-based, and state-based automations.
//!
//! # Module Structure
//!
//! - [`device_group`] - Device grouping and management
//! - [`rule_engine`] - Automation rules, triggers, conditions, and actions
//! - [`executor`] - Action execution with shared HTTP client
//! - [`shared_client`] - Centralized HTTP client management
//!
//! Colony: Beacon (e5) - Orchestration and coordination
//!
//! h(x) >= 0 always

pub mod device_group;
pub mod executor;
pub mod rule_engine;
pub mod shared_client;

// Re-export main types at module level
pub use device_group::{DeviceGroup, GroupType};
pub use executor::ActionExecutor;
pub use rule_engine::{
    Action, AnnouncementAction, ApiCallAction, AutomationRule, Condition, DelayAction,
    DeviceControlAction, DeviceStateCondition, DeviceStateTrigger, EventTrigger, GroupControlAction,
    NotificationAction, NotificationPriority, PresenceCondition, PresenceState, PresenceTrigger,
    RunAutomationAction, SceneAction, ScriptAction, ScriptType, StateCondition, SunEvent,
    SunTrigger, TimeCondition, TimeTrigger, Trigger, VoiceCommandTrigger, WebhookTrigger,
};
pub use shared_client::{get_client, init_client, HttpClientConfig};

use anyhow::Result;
use chrono::Datelike;
use reqwest::Client;
use std::collections::HashMap;
use std::sync::Arc;
use tokio::sync::{broadcast, RwLock};
use tracing::{error, info};

// Re-import Client for with_client constructor
#[allow(unused_imports)]
use reqwest::Client as _;

// ============================================================================
// Automation Events
// ============================================================================

/// Events emitted by the automation engine
#[derive(Debug, Clone)]
pub enum AutomationEvent {
    /// Automation triggered
    Triggered { rule_id: String, trigger_type: String },
    /// Automation executed
    Executed {
        rule_id: String,
        success: bool,
        error: Option<String>,
    },
    /// Automation disabled
    Disabled { rule_id: String },
    /// Automation enabled
    Enabled { rule_id: String },
    /// Group action executed
    GroupAction { group_id: String, action: String },
}

// ============================================================================
// Automation Engine
// ============================================================================

/// Main automation engine
pub struct AutomationEngine {
    /// Device groups (wrapped in Arc for cheap cloning)
    groups: Arc<RwLock<HashMap<String, Arc<RwLock<DeviceGroup>>>>>,
    /// Automation rules (wrapped in Arc for cheap cloning)
    rules: Arc<RwLock<HashMap<String, Arc<RwLock<AutomationRule>>>>>,
    /// Event broadcaster
    event_tx: broadcast::Sender<AutomationEvent>,
    /// Action executor (owns the HTTP client)
    executor: ActionExecutor,
}

impl AutomationEngine {
    /// Create a new automation engine with shared HTTP client
    pub fn new(api_url: &str) -> Self {
        let (event_tx, _) = broadcast::channel(100);
        let executor = ActionExecutor::new(api_url);

        Self {
            groups: Arc::new(RwLock::new(HashMap::new())),
            rules: Arc::new(RwLock::new(HashMap::new())),
            event_tx,
            executor,
        }
    }

    /// Create a new automation engine with a custom HTTP client
    pub fn with_client(client: Arc<Client>, api_url: &str) -> Self {
        let (event_tx, _) = broadcast::channel(100);
        let executor = ActionExecutor::with_client(client, api_url);

        Self {
            groups: Arc::new(RwLock::new(HashMap::new())),
            rules: Arc::new(RwLock::new(HashMap::new())),
            event_tx,
            executor,
        }
    }

    /// Subscribe to automation events
    pub fn subscribe(&self) -> broadcast::Receiver<AutomationEvent> {
        self.event_tx.subscribe()
    }

    // ========================================================================
    // Group Management
    // ========================================================================

    /// Create a new device group
    pub async fn create_group(&self, group: DeviceGroup) -> Result<()> {
        let mut groups = self.groups.write().await;
        info!("Creating device group: {} ({})", group.name, group.id);
        groups.insert(group.id.clone(), Arc::new(RwLock::new(group)));
        Ok(())
    }

    /// Get a device group (returns a clone)
    pub async fn get_group(&self, group_id: &str) -> Option<DeviceGroup> {
        let groups = self.groups.read().await;
        if let Some(group_arc) = groups.get(group_id) {
            let group = group_arc.read().await;
            Some(group.clone())
        } else {
            None
        }
    }

    /// Get all device groups (returns clones)
    pub async fn get_groups(&self) -> Vec<DeviceGroup> {
        let groups = self.groups.read().await;
        let mut result = Vec::with_capacity(groups.len());
        for group_arc in groups.values() {
            let group = group_arc.read().await;
            result.push(group.clone());
        }
        result
    }

    /// Update a device group
    pub async fn update_group(
        &self,
        group_id: &str,
        update: impl FnOnce(&mut DeviceGroup),
    ) -> Result<()> {
        let groups = self.groups.read().await;
        let group_arc = groups
            .get(group_id)
            .ok_or_else(|| anyhow::anyhow!("Group not found: {}", group_id))?
            .clone();
        drop(groups);

        let mut group = group_arc.write().await;
        update(&mut group);
        group.touch();
        Ok(())
    }

    /// Delete a device group
    pub async fn delete_group(&self, group_id: &str) -> Result<()> {
        let mut groups = self.groups.write().await;
        groups.remove(group_id);
        info!("Deleted device group: {}", group_id);
        Ok(())
    }

    /// Add device to group
    pub async fn add_device_to_group(&self, group_id: &str, device_id: &str) -> Result<()> {
        self.update_group(group_id, |g| g.add_device(device_id))
            .await
    }

    /// Remove device from group
    pub async fn remove_device_from_group(&self, group_id: &str, device_id: &str) -> Result<()> {
        self.update_group(group_id, |g| g.remove_device(device_id))
            .await
    }

    /// Get groups containing a device
    pub async fn get_device_groups(&self, device_id: &str) -> Vec<DeviceGroup> {
        let groups = self.groups.read().await;
        let mut result = Vec::new();
        for group_arc in groups.values() {
            let group = group_arc.read().await;
            if group.device_ids.contains(&device_id.to_string()) {
                result.push(group.clone());
            }
        }
        result
    }

    /// Control all devices in a group
    pub async fn control_group(
        &self,
        group_id: &str,
        service: &str,
        params: HashMap<String, serde_json::Value>,
    ) -> Result<()> {
        let groups = self.groups.read().await;
        let group_arc = groups
            .get(group_id)
            .ok_or_else(|| anyhow::anyhow!("Group not found: {}", group_id))?
            .clone();
        drop(groups);

        let group = group_arc.read().await;
        if !group.enabled {
            return Err(anyhow::anyhow!("Group is disabled"));
        }

        info!(
            "Controlling group {} ({} devices): {}",
            group.name,
            group.device_ids.len(),
            service
        );

        let device_ids = group.device_ids.clone();
        drop(group);

        // Execute control on all devices in parallel using the executor
        self.executor
            .control_devices_parallel(&device_ids, service, &params)
            .await?;

        let _ = self.event_tx.send(AutomationEvent::GroupAction {
            group_id: group_id.to_string(),
            action: service.to_string(),
        });

        Ok(())
    }

    // ========================================================================
    // Rule Management
    // ========================================================================

    /// Create a new automation rule
    pub async fn create_rule(&self, rule: AutomationRule) -> Result<()> {
        let mut rules = self.rules.write().await;
        info!("Creating automation rule: {} ({})", rule.name, rule.id);
        rules.insert(rule.id.clone(), Arc::new(RwLock::new(rule)));
        Ok(())
    }

    /// Get an automation rule (returns a clone)
    pub async fn get_rule(&self, rule_id: &str) -> Option<AutomationRule> {
        let rules = self.rules.read().await;
        if let Some(rule_arc) = rules.get(rule_id) {
            let rule = rule_arc.read().await;
            Some(rule.clone())
        } else {
            None
        }
    }

    /// Get all automation rules (returns clones, sorted by priority)
    pub async fn get_rules(&self) -> Vec<AutomationRule> {
        let rules = self.rules.read().await;
        let mut result = Vec::with_capacity(rules.len());
        for rule_arc in rules.values() {
            let rule = rule_arc.read().await;
            result.push(rule.clone());
        }
        result.sort_by(|a, b| b.priority.cmp(&a.priority));
        result
    }

    /// Update an automation rule
    pub async fn update_rule(
        &self,
        rule_id: &str,
        update: impl FnOnce(&mut AutomationRule),
    ) -> Result<()> {
        let rules = self.rules.read().await;
        let rule_arc = rules
            .get(rule_id)
            .ok_or_else(|| anyhow::anyhow!("Rule not found: {}", rule_id))?
            .clone();
        drop(rules);

        let mut rule = rule_arc.write().await;
        update(&mut rule);
        rule.touch();
        Ok(())
    }

    /// Delete an automation rule
    pub async fn delete_rule(&self, rule_id: &str) -> Result<()> {
        let mut rules = self.rules.write().await;
        rules.remove(rule_id);
        info!("Deleted automation rule: {}", rule_id);
        Ok(())
    }

    /// Enable a rule
    pub async fn enable_rule(&self, rule_id: &str) -> Result<()> {
        self.update_rule(rule_id, |r| r.enabled = true).await?;
        let _ = self.event_tx.send(AutomationEvent::Enabled {
            rule_id: rule_id.to_string(),
        });
        Ok(())
    }

    /// Disable a rule
    pub async fn disable_rule(&self, rule_id: &str) -> Result<()> {
        self.update_rule(rule_id, |r| r.enabled = false).await?;
        let _ = self.event_tx.send(AutomationEvent::Disabled {
            rule_id: rule_id.to_string(),
        });
        Ok(())
    }

    // ========================================================================
    // Trigger Processing
    // ========================================================================

    /// Process an incoming event and check for matching triggers
    pub async fn process_event(
        &self,
        event_type: &str,
        event_data: &serde_json::Value,
    ) -> Result<Vec<String>> {
        let rules = self.rules.read().await;
        let mut triggered_rules = vec![];

        for (rule_id, rule_arc) in rules.iter() {
            let rule = rule_arc.read().await;
            if !rule.can_execute() {
                continue;
            }

            for trigger in &rule.triggers {
                if self.matches_trigger(trigger, event_type, event_data) {
                    if self.check_conditions(&rule.conditions, event_data).await {
                        triggered_rules.push(rule_id.clone());
                        break;
                    }
                }
            }
        }

        drop(rules);

        // Execute triggered rules
        for rule_id in &triggered_rules {
            if let Err(e) = self.execute_rule(rule_id).await {
                error!("Failed to execute rule {}: {}", rule_id, e);
            }
        }

        Ok(triggered_rules)
    }

    /// Check if trigger matches event
    fn matches_trigger(
        &self,
        trigger: &Trigger,
        event_type: &str,
        event_data: &serde_json::Value,
    ) -> bool {
        match trigger {
            Trigger::Event(et) => {
                if et.event_type != event_type {
                    return false;
                }
                if let Some(ref source) = et.source {
                    if event_data.get("source").and_then(|v| v.as_str()) != Some(source) {
                        return false;
                    }
                }
                for (key, expected) in &et.filters {
                    if event_data.get(key) != Some(expected) {
                        return false;
                    }
                }
                true
            }
            Trigger::DeviceState(ds) => {
                if event_type != "device_state_changed" {
                    return false;
                }
                if event_data.get("device_id").and_then(|v| v.as_str()) != Some(&ds.device_id) {
                    return false;
                }
                if event_data.get("attribute").and_then(|v| v.as_str()) != Some(&ds.attribute) {
                    return false;
                }
                if let Some(value) = event_data.get("value") {
                    self.compare_values(value, &ds.value, ds.condition)
                } else {
                    false
                }
            }
            Trigger::VoiceCommand(vc) => {
                if event_type != "voice_command" {
                    return false;
                }
                if let Some(text) = event_data.get("text").and_then(|v| v.as_str()) {
                    let text_lower = text.to_lowercase();
                    for phrase in &vc.phrases {
                        let phrase_lower = phrase.to_lowercase();
                        if vc.exact_match {
                            if text_lower == phrase_lower {
                                return true;
                            }
                        } else if text_lower.contains(&phrase_lower) {
                            return true;
                        }
                    }
                }
                false
            }
            _ => false, // Time and Sun triggers are handled by scheduler
        }
    }

    /// Compare values based on condition
    fn compare_values(
        &self,
        actual: &serde_json::Value,
        expected: &serde_json::Value,
        condition: StateCondition,
    ) -> bool {
        match condition {
            StateCondition::Equals => actual == expected,
            StateCondition::NotEquals => actual != expected,
            StateCondition::GreaterThan => {
                if let (Some(a), Some(e)) = (actual.as_f64(), expected.as_f64()) {
                    a > e
                } else {
                    false
                }
            }
            StateCondition::LessThan => {
                if let (Some(a), Some(e)) = (actual.as_f64(), expected.as_f64()) {
                    a < e
                } else {
                    false
                }
            }
            StateCondition::GreaterOrEqual => {
                if let (Some(a), Some(e)) = (actual.as_f64(), expected.as_f64()) {
                    a >= e
                } else {
                    false
                }
            }
            StateCondition::LessOrEqual => {
                if let (Some(a), Some(e)) = (actual.as_f64(), expected.as_f64()) {
                    a <= e
                } else {
                    false
                }
            }
            StateCondition::Changes => true, // Any change
            StateCondition::ChangesTo => actual == expected,
            StateCondition::ChangesFrom => false, // Would need previous value
        }
    }

    /// Check all conditions
    async fn check_conditions(
        &self,
        conditions: &[Condition],
        context: &serde_json::Value,
    ) -> bool {
        for condition in conditions {
            if !self.check_condition(condition, context).await {
                return false;
            }
        }
        true
    }

    /// Check a single condition
    async fn check_condition(&self, condition: &Condition, context: &serde_json::Value) -> bool {
        match condition {
            Condition::Time(tc) => self.check_time_condition(tc),
            Condition::DeviceState(ds) => self.check_device_state_condition(ds).await,
            Condition::Presence(pc) => self.check_presence_condition(pc).await,
            Condition::And(conditions) => {
                for c in conditions {
                    if !Box::pin(self.check_condition(c, context)).await {
                        return false;
                    }
                }
                true
            }
            Condition::Or(conditions) => {
                for c in conditions {
                    if Box::pin(self.check_condition(c, context)).await {
                        return true;
                    }
                }
                false
            }
            Condition::Not(c) => !Box::pin(self.check_condition(c, context)).await,
        }
    }

    /// Check time condition
    fn check_time_condition(&self, condition: &TimeCondition) -> bool {
        let now = chrono::Local::now();
        let current_time = now.format("%H:%M").to_string();

        if let Some(ref after) = condition.after {
            if current_time < *after {
                return false;
            }
        }

        if let Some(ref before) = condition.before {
            if current_time > *before {
                return false;
            }
        }

        if let Some(ref days) = condition.days {
            let today = now.weekday().num_days_from_sunday() as u8;
            if !days.contains(&today) {
                return false;
            }
        }

        true
    }

    /// Check device state condition
    async fn check_device_state_condition(&self, _condition: &DeviceStateCondition) -> bool {
        // Would need to query current device state from API
        // For now, return true (pass through)
        true
    }

    /// Check presence condition
    async fn check_presence_condition(&self, _condition: &PresenceCondition) -> bool {
        // Would need to query presence from API
        // For now, return true (pass through)
        true
    }

    // ========================================================================
    // Action Execution
    // ========================================================================

    /// Execute all actions for a rule
    pub async fn execute_rule(&self, rule_id: &str) -> Result<()> {
        let rules = self.rules.read().await;
        let rule_arc = rules
            .get(rule_id)
            .ok_or_else(|| anyhow::anyhow!("Rule not found: {}", rule_id))?
            .clone();
        drop(rules);

        let mut rule = rule_arc.write().await;
        if !rule.can_execute() {
            return Err(anyhow::anyhow!(
                "Rule cannot execute (disabled or cooling down)"
            ));
        }

        let actions = rule.actions.clone();
        rule.mark_triggered();
        drop(rule);

        info!("Executing automation rule: {}", rule_id);

        let _ = self.event_tx.send(AutomationEvent::Triggered {
            rule_id: rule_id.to_string(),
            trigger_type: "manual".to_string(),
        });

        // Execute actions in sequence
        for action in &actions {
            // Handle RunAutomation specially since it needs access to self
            if let Action::RunAutomation(ra) = action {
                info!("Running automation: {}", ra.automation_id);
                if let Err(e) = Box::pin(self.execute_rule(&ra.automation_id)).await {
                    error!("Sub-automation execution failed: {}", e);
                    let _ = self.event_tx.send(AutomationEvent::Executed {
                        rule_id: rule_id.to_string(),
                        success: false,
                        error: Some(e.to_string()),
                    });
                    return Err(e);
                }
            } else if let Err(e) = self.executor.execute(action).await {
                error!("Action execution failed: {}", e);
                let _ = self.event_tx.send(AutomationEvent::Executed {
                    rule_id: rule_id.to_string(),
                    success: false,
                    error: Some(e.to_string()),
                });
                return Err(e);
            }
        }

        let _ = self.event_tx.send(AutomationEvent::Executed {
            rule_id: rule_id.to_string(),
            success: true,
            error: None,
        });

        Ok(())
    }
}

// ============================================================================
// Tests
// ============================================================================

#[cfg(test)]
mod tests {
    use super::*;

    #[tokio::test]
    async fn test_engine_group_management() {
        let engine = AutomationEngine::new("http://localhost:8000");

        let group = DeviceGroup::new("test-group", "Test Group", GroupType::Lights);
        engine.create_group(group).await.unwrap();

        let retrieved = engine.get_group("test-group").await;
        assert!(retrieved.is_some());
        assert_eq!(retrieved.unwrap().name, "Test Group");

        engine
            .add_device_to_group("test-group", "device-1")
            .await
            .unwrap();

        let groups = engine.get_device_groups("device-1").await;
        assert_eq!(groups.len(), 1);
    }

    #[tokio::test]
    async fn test_engine_rule_management() {
        let engine = AutomationEngine::new("http://localhost:8000");

        let rule = AutomationRule::new("test-rule", "Test Rule");
        engine.create_rule(rule).await.unwrap();

        let retrieved = engine.get_rule("test-rule").await;
        assert!(retrieved.is_some());

        engine.disable_rule("test-rule").await.unwrap();
        let disabled = engine.get_rule("test-rule").await.unwrap();
        assert!(!disabled.enabled);
    }

    #[tokio::test]
    async fn test_engine_multiple_groups() {
        let engine = AutomationEngine::new("http://localhost:8000");

        let group1 = DeviceGroup::new("group-1", "Group 1", GroupType::Lights);
        let group2 = DeviceGroup::new("group-2", "Group 2", GroupType::Climate);

        engine.create_group(group1).await.unwrap();
        engine.create_group(group2).await.unwrap();

        let groups = engine.get_groups().await;
        assert_eq!(groups.len(), 2);
    }

    #[tokio::test]
    async fn test_engine_delete_group() {
        let engine = AutomationEngine::new("http://localhost:8000");

        let group = DeviceGroup::new("test-group", "Test Group", GroupType::Lights);
        engine.create_group(group).await.unwrap();

        engine.delete_group("test-group").await.unwrap();
        let retrieved = engine.get_group("test-group").await;
        assert!(retrieved.is_none());
    }
}

/*
 * Beacon orchestrates. Automations flow.
 * h(x) >= 0 always
 */
