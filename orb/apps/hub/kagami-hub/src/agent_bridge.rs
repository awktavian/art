//! Agent Bridge — Voice-to-Agent Command Routing
//!
//! Maps voice commands to HTML agent actions, enabling voice control
//! of the entire agent ecosystem from the Hub.
//!
//! Voice Command Flow:
//! ```
//! "Hey Kagami" → Wake Word
//! "Run movie mode" → Voice → NLU → Agent Bridge → Scene Agent → Consensus → Execute
//! ```
//!
//! Colony: Nexus (e4) — Integration
//! h(x) >= 0. Always.

use anyhow::Result;
use serde::{Deserialize, Serialize};
use std::collections::HashMap;
use std::sync::Arc;
use tokio::sync::RwLock;
use tracing::{debug, error, info, warn};

use crate::api_client::KagamiAPI;
use crate::voice_pipeline::CommandIntent;

// ============================================================================
// Agent Info
// ============================================================================

/// Information about a registered agent
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct AgentInfo {
    pub id: String,
    pub name: String,
    pub description: String,
    pub colony: String,
    pub capabilities: Vec<String>,
    pub consensus_weight: u32,
    pub is_online: bool,
}

/// Agent action request
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct AgentAction {
    pub agent_id: String,
    pub action: String,
    pub params: HashMap<String, serde_json::Value>,
    pub source: String,
    pub requires_consensus: bool,
}

/// Agent action result
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct ActionResult {
    pub success: bool,
    pub message: Option<String>,
    pub data: Option<serde_json::Value>,
}

// ============================================================================
// Voice Command Mapping
// ============================================================================

/// Maps voice intents to agent actions
#[derive(Debug)]
pub struct VoiceToAgentMapping {
    /// Intent pattern (supports wildcards with *)
    pub intent_pattern: String,
    /// Target agent ID
    pub agent_id: String,
    /// Action to trigger
    pub action: String,
    /// Parameter extraction function name
    pub param_extractor: Option<String>,
    /// Whether this requires consensus
    pub requires_consensus: bool,
    /// Priority (higher = checked first)
    pub priority: u32,
}

impl Default for VoiceToAgentMapping {
    fn default() -> Self {
        Self {
            intent_pattern: String::new(),
            agent_id: String::new(),
            action: String::new(),
            param_extractor: None,
            requires_consensus: false,
            priority: 0,
        }
    }
}

// ============================================================================
// Agent Bridge
// ============================================================================

/// Hub ID for agent registration
const HUB_AGENT_ID: &str = "kagami-hub";
const HUB_AGENT_NAME: &str = "Kagami Hub";
const HUB_CONSENSUS_WEIGHT: u32 = 2;

/// Bridge between voice commands and agent actions.
///
/// The Hub acts as a PARTICIPANT agent in the ecosystem,
/// routing voice commands to appropriate agents and
/// participating in consensus.
pub struct AgentBridge {
    api: KagamiAPI,
    agents: Arc<RwLock<HashMap<String, AgentInfo>>>,
    mappings: Arc<RwLock<Vec<VoiceToAgentMapping>>>,
    is_registered: Arc<RwLock<bool>>,
}

impl AgentBridge {
    /// Create a new agent bridge
    pub fn new(api: KagamiAPI) -> Self {
        let bridge = Self {
            api,
            agents: Arc::new(RwLock::new(HashMap::new())),
            mappings: Arc::new(RwLock::new(Vec::new())),
            is_registered: Arc::new(RwLock::new(false)),
        };

        // Initialize default mappings
        let mut mappings = Vec::new();

        // Scene mappings (high priority)
        mappings.push(VoiceToAgentMapping {
            intent_pattern: "scene:*".to_string(),
            agent_id: "scenes".to_string(),
            action: "activate".to_string(),
            param_extractor: Some("extract_scene_name".to_string()),
            requires_consensus: true,
            priority: 100,
        });

        mappings.push(VoiceToAgentMapping {
            intent_pattern: "movie_mode".to_string(),
            agent_id: "scenes".to_string(),
            action: "activate".to_string(),
            param_extractor: None,
            requires_consensus: true,
            priority: 100,
        });

        mappings.push(VoiceToAgentMapping {
            intent_pattern: "goodnight".to_string(),
            agent_id: "scenes".to_string(),
            action: "activate".to_string(),
            param_extractor: None,
            requires_consensus: true,
            priority: 100,
        });

        // Light mappings
        mappings.push(VoiceToAgentMapping {
            intent_pattern: "lights:*".to_string(),
            agent_id: "rooms".to_string(),
            action: "setLights".to_string(),
            param_extractor: Some("extract_light_params".to_string()),
            requires_consensus: false,
            priority: 90,
        });

        mappings.push(VoiceToAgentMapping {
            intent_pattern: "dim".to_string(),
            agent_id: "rooms".to_string(),
            action: "setLights".to_string(),
            param_extractor: Some("extract_dim_params".to_string()),
            requires_consensus: false,
            priority: 90,
        });

        mappings.push(VoiceToAgentMapping {
            intent_pattern: "brighten".to_string(),
            agent_id: "rooms".to_string(),
            action: "setLights".to_string(),
            param_extractor: Some("extract_brighten_params".to_string()),
            requires_consensus: false,
            priority: 90,
        });

        // Shade mappings
        mappings.push(VoiceToAgentMapping {
            intent_pattern: "shades:*".to_string(),
            agent_id: "rooms".to_string(),
            action: "setShades".to_string(),
            param_extractor: Some("extract_shade_params".to_string()),
            requires_consensus: false,
            priority: 85,
        });

        // Lock mappings
        mappings.push(VoiceToAgentMapping {
            intent_pattern: "lock:*".to_string(),
            agent_id: "rooms".to_string(),
            action: "setLock".to_string(),
            param_extractor: Some("extract_lock_params".to_string()),
            requires_consensus: true,
            priority: 95,
        });

        // Dashboard query
        mappings.push(VoiceToAgentMapping {
            intent_pattern: "status".to_string(),
            agent_id: "dashboard".to_string(),
            action: "getStatus".to_string(),
            param_extractor: None,
            requires_consensus: false,
            priority: 50,
        });

        // Sort by priority (descending)
        mappings.sort_by(|a, b| b.priority.cmp(&a.priority));

        // Store mappings
        tokio::spawn({
            let mappings_arc = bridge.mappings.clone();
            async move {
                let mut lock = mappings_arc.write().await;
                *lock = mappings;
            }
        });

        bridge
    }

    /// Register the hub as an agent participant
    pub async fn register(&self) -> Result<()> {
        let registration = serde_json::json!({
            "agentId": HUB_AGENT_ID,
            "name": HUB_AGENT_NAME,
            "type": "PARTICIPANT",
            "capabilities": ["voice", "audio", "wake_word", "tts", "stt", "led_ring"],
            "consensusWeight": HUB_CONSENSUS_WEIGHT,
            "platform": "raspberry_pi",
        });

        let result: Result<serde_json::Value> = self
            .api
            .post_json("/api/v1/agents/register", registration)
            .await;
        match result {
            Ok(_) => {
                let mut registered = self.is_registered.write().await;
                *registered = true;
                info!("Hub registered as agent participant");
                Ok(())
            }
            Err(e) => {
                warn!("Failed to register as agent: {}", e);
                Err(e)
            }
        }
    }

    /// Refresh the list of available agents
    pub async fn refresh_agents(&self) -> Result<()> {
        let response: serde_json::Value = self.api.get_json("/api/v1/agents").await?;

        if let Some(agents_array) = response.get("agents").and_then(|v| v.as_array()) {
            let mut agents = self.agents.write().await;
            agents.clear();

            for agent_json in agents_array {
                if let Ok(agent) = serde_json::from_value::<AgentInfo>(agent_json.clone()) {
                    agents.insert(agent.id.clone(), agent);
                }
            }

            info!("Refreshed {} agents", agents.len());
        }

        Ok(())
    }

    /// Route a voice command intent to an agent action
    pub async fn route_voice_command(&self, intent: &CommandIntent) -> Result<ActionResult> {
        // Get intent as string for matching
        let intent_str = intent_to_string(intent);
        debug!("Routing voice intent: {}", intent_str);

        // Find matching mapping
        let mappings = self.mappings.read().await;
        let mapping = mappings
            .iter()
            .find(|m| matches_pattern(&m.intent_pattern, &intent_str));

        let mapping = match mapping {
            Some(m) => m,
            None => {
                warn!("No agent mapping for intent: {}", intent_str);
                return Ok(ActionResult {
                    success: false,
                    message: Some(format!("No agent handler for: {}", intent_str)),
                    data: None,
                });
            }
        };

        // Extract parameters
        let params = extract_params(intent, mapping.param_extractor.as_deref());

        // Create action
        let action = AgentAction {
            agent_id: mapping.agent_id.clone(),
            action: mapping.action.clone(),
            params,
            source: HUB_AGENT_ID.to_string(),
            requires_consensus: mapping.requires_consensus,
        };

        // Execute action
        self.execute_agent_action(action).await
    }

    /// Execute an action on an agent
    pub async fn execute_agent_action(&self, action: AgentAction) -> Result<ActionResult> {
        info!(
            "Executing agent action: {} on {} (consensus: {})",
            action.action, action.agent_id, action.requires_consensus
        );

        // Build request payload
        let payload = serde_json::json!({
            "action": action.action,
            "params": action.params,
            "source": action.source,
            "requiresConsensus": action.requires_consensus,
        });

        // Call agent endpoint
        let endpoint = format!("/api/v1/agents/{}/action", action.agent_id);

        let result: Result<serde_json::Value> = self.api.post_json(&endpoint, payload).await;
        match result {
            Ok(response) => {
                let success = response
                    .get("success")
                    .and_then(|v| v.as_bool())
                    .unwrap_or(false);
                let message = response
                    .get("message")
                    .and_then(|v| v.as_str())
                    .map(|s| s.to_string());

                Ok(ActionResult {
                    success,
                    message,
                    data: Some(response),
                })
            }
            Err(e) => {
                error!("Agent action failed: {}", e);
                Ok(ActionResult {
                    success: false,
                    message: Some(format!("Action failed: {}", e)),
                    data: None,
                })
            }
        }
    }

    /// Vote on a consensus proposal
    pub async fn vote_on_proposal(
        &self,
        proposal_id: &str,
        approve: bool,
        reason: Option<&str>,
    ) -> Result<()> {
        let vote = serde_json::json!({
            "proposalId": proposal_id,
            "agentId": HUB_AGENT_ID,
            "decision": if approve { "approve" } else { "reject" },
            "reason": reason.unwrap_or(""),
            "weight": HUB_CONSENSUS_WEIGHT,
        });

        let _: serde_json::Value = self.api.post_json("/api/v1/consensus/vote", vote).await?;
        info!(
            "Voted {} on proposal {}",
            if approve { "approve" } else { "reject" },
            proposal_id
        );

        Ok(())
    }

    /// Generate a voice response for an action result
    pub fn generate_response(&self, intent: &CommandIntent, result: &ActionResult) -> String {
        if result.success {
            match intent {
                CommandIntent::Scene(scene) => format!("{} activated", humanize(scene)),
                CommandIntent::Lights(level) => format!("Set lights to {}%", level),
                CommandIntent::Lock(locked) => {
                    if *locked {
                        "Locked".to_string()
                    } else {
                        "Unlocked".to_string()
                    }
                }
                CommandIntent::Fireplace(on) => {
                    if *on {
                        "Fireplace on".to_string()
                    } else {
                        "Fireplace off".to_string()
                    }
                }
                CommandIntent::Shades(action) => format!("Shades {}", action),
                _ => "Done".to_string(),
            }
        } else {
            result
                .message
                .clone()
                .unwrap_or_else(|| "Sorry, that didn't work".to_string())
        }
    }

    /// Get list of available agent capabilities for NLU context
    pub async fn get_capability_hints(&self) -> Vec<String> {
        let agents = self.agents.read().await;
        let mut hints = Vec::new();

        for agent in agents.values() {
            for cap in &agent.capabilities {
                hints.push(format!("{}: {}", agent.name, cap));
            }
        }

        hints
    }
}

// ============================================================================
// Helper Functions
// ============================================================================

/// Convert CommandIntent to string for pattern matching
fn intent_to_string(intent: &CommandIntent) -> String {
    match intent {
        CommandIntent::Scene(name) => format!("scene:{}", name),
        CommandIntent::Lights(level) => format!("lights:{}", level),
        CommandIntent::Shades(action) => format!("shades:{}", action),
        CommandIntent::Lock(locked) => format!("lock:{}", locked),
        CommandIntent::Fireplace(on) => format!("fireplace:{}", on),
        CommandIntent::TV(action) => format!("tv:{}", action),
        CommandIntent::Temperature(temp) => format!("temperature:{}", temp),
        CommandIntent::Music(action) => format!("music:{:?}", action),
        CommandIntent::Announce(text) => format!("announce:{}", text),
        CommandIntent::Status => "status".to_string(),
        CommandIntent::Help => "help".to_string(),
        CommandIntent::Cancel => "cancel".to_string(),
        CommandIntent::Tesla(action) => format!("tesla:{:?}", action),
        CommandIntent::Bed(action) => format!("bed:{:?}", action),
        CommandIntent::Outdoor(action) => format!("outdoor:{:?}", action),
        CommandIntent::Security(action) => format!("security:{:?}", action),
        CommandIntent::Presence => "presence".to_string(),
        CommandIntent::Weather => "weather".to_string(),
        CommandIntent::FindDevice(device) => format!("find:{}", device),
        CommandIntent::VacationMode(on) => format!("vacation:{}", on),
        CommandIntent::GuestMode(on) => format!("guest:{}", on),
        CommandIntent::ClimateZone { room, temp } => format!("climate:{}:{}", room, temp),
        CommandIntent::HvacMode { room, mode } => format!("hvac:{:?}:{}", room, mode),
        CommandIntent::Unknown => "unknown".to_string(),
    }
}

/// Check if a string matches a pattern (supports * wildcards)
fn matches_pattern(pattern: &str, text: &str) -> bool {
    if pattern == text {
        return true;
    }

    if pattern.ends_with('*') {
        let prefix = &pattern[..pattern.len() - 1];
        return text.starts_with(prefix);
    }

    if pattern.starts_with('*') {
        let suffix = &pattern[1..];
        return text.ends_with(suffix);
    }

    // Check for special scene names
    if pattern == "movie_mode" && text.contains("movie") {
        return true;
    }

    if pattern == "goodnight" && (text.contains("night") || text.contains("sleep")) {
        return true;
    }

    false
}

/// Extract parameters from intent based on extractor name
fn extract_params(
    intent: &CommandIntent,
    extractor: Option<&str>,
) -> HashMap<String, serde_json::Value> {
    let mut params = HashMap::new();

    match intent {
        CommandIntent::Scene(name) => {
            params.insert("scene".to_string(), serde_json::Value::String(name.clone()));
        }
        CommandIntent::Lights(level) => {
            params.insert(
                "level".to_string(),
                serde_json::Value::Number((*level).into()),
            );
        }
        CommandIntent::Shades(action) => {
            params.insert(
                "action".to_string(),
                serde_json::Value::String(action.clone()),
            );
        }
        CommandIntent::Lock(locked) => {
            params.insert("locked".to_string(), serde_json::Value::Bool(*locked));
        }
        CommandIntent::Fireplace(on) => {
            params.insert("on".to_string(), serde_json::Value::Bool(*on));
        }
        CommandIntent::TV(action) => {
            params.insert(
                "action".to_string(),
                serde_json::Value::String(action.clone()),
            );
        }
        CommandIntent::Temperature(temp) => {
            params.insert(
                "temperature".to_string(),
                serde_json::Value::Number((*temp).into()),
            );
        }
        CommandIntent::Music(action) => {
            params.insert(
                "action".to_string(),
                serde_json::Value::String(format!("{:?}", action)),
            );
        }
        CommandIntent::Announce(text) => {
            params.insert("text".to_string(), serde_json::Value::String(text.clone()));
        }
        CommandIntent::FindDevice(device) => {
            params.insert(
                "device".to_string(),
                serde_json::Value::String(device.clone()),
            );
        }
        CommandIntent::VacationMode(on) | CommandIntent::GuestMode(on) => {
            params.insert("enabled".to_string(), serde_json::Value::Bool(*on));
        }
        CommandIntent::ClimateZone { room, temp } => {
            params.insert("room".to_string(), serde_json::Value::String(room.clone()));
            params.insert(
                "temperature".to_string(),
                serde_json::Value::Number((*temp).into()),
            );
        }
        CommandIntent::HvacMode { room, mode } => {
            if let Some(r) = room {
                params.insert("room".to_string(), serde_json::Value::String(r.clone()));
            }
            params.insert("mode".to_string(), serde_json::Value::String(mode.clone()));
        }
        _ => {}
    }

    // Apply special extractors
    if let Some(extractor_name) = extractor {
        match extractor_name {
            "extract_dim_params" => {
                if !params.contains_key("level") {
                    params.insert("level".to_string(), serde_json::Value::Number(30.into()));
                }
            }
            "extract_brighten_params" => {
                if !params.contains_key("level") {
                    params.insert("level".to_string(), serde_json::Value::Number(100.into()));
                }
            }
            _ => {}
        }
    }

    params
}

/// Convert snake_case to human readable
fn humanize(s: &str) -> String {
    s.replace('_', " ")
        .split_whitespace()
        .map(|word| {
            let mut chars = word.chars();
            match chars.next() {
                None => String::new(),
                Some(first) => first.to_uppercase().chain(chars).collect(),
            }
        })
        .collect::<Vec<_>>()
        .join(" ")
}

/*
 * 鏡
 * h(x) >= 0. Always.
 */
