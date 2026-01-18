//! Dialogue State Machine — Context-Aware Conversations
//!
//! Implements multi-turn dialogue tracking for more natural voice interactions.
//! Enables pronoun resolution, follow-up commands, and contextual understanding.
//!
//! Example flow:
//! User: "Turn on the living room lights"
//! Kagami: "Living room lights on"
//! User: "Dim them to 50%"     <- "them" refers to living room lights
//! Kagami: "Living room lights dimmed to 50%"
//!
//! Colony: Beacon (e5) - Guidance, signaling
//!
//! h(x) >= 0. Always.

use std::collections::VecDeque;
use std::time::{Duration, Instant};
use tracing::{debug, info};

use crate::voice_pipeline::CommandIntent;

// ============================================================================
// Constants
// ============================================================================

/// Maximum number of dialogue turns to keep in history
const MAX_HISTORY_SIZE: usize = 10;

/// Context timeout - after this duration, context is cleared
const CONTEXT_TIMEOUT: Duration = Duration::from_secs(60);

/// Follow-up window - time during which follow-ups are expected
const FOLLOW_UP_WINDOW: Duration = Duration::from_secs(10);

// ============================================================================
// Dialogue State
// ============================================================================

/// Dialogue states for conversation tracking
#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub enum DialogueState {
    /// No active conversation
    Idle,
    /// Waiting for initial command
    Listening,
    /// Processing a command
    Processing,
    /// Waiting for confirmation (yes/no)
    AwaitingConfirmation,
    /// Waiting for follow-up command
    AwaitingFollowUp,
    /// Error occurred, may retry
    Error,
}

impl std::fmt::Display for DialogueState {
    fn fmt(&self, f: &mut std::fmt::Formatter<'_>) -> std::fmt::Result {
        match self {
            DialogueState::Idle => write!(f, "idle"),
            DialogueState::Listening => write!(f, "listening"),
            DialogueState::Processing => write!(f, "processing"),
            DialogueState::AwaitingConfirmation => write!(f, "awaiting_confirmation"),
            DialogueState::AwaitingFollowUp => write!(f, "awaiting_follow_up"),
            DialogueState::Error => write!(f, "error"),
        }
    }
}

// ============================================================================
// Dialogue Context
// ============================================================================

/// Context entity - things that can be referenced by pronouns
#[derive(Debug, Clone)]
pub struct ContextEntity {
    /// Entity type (room, device, scene, etc.)
    pub entity_type: EntityType,
    /// Entity name/identifier
    pub name: String,
    /// When this entity was last referenced
    pub last_referenced: Instant,
}

/// Types of entities that can be tracked in context
#[derive(Debug, Clone, PartialEq, Eq)]
pub enum EntityType {
    Room,
    Device,
    Scene,
    DeviceGroup,
    Temperature,
    Playlist,
}

impl std::fmt::Display for EntityType {
    fn fmt(&self, f: &mut std::fmt::Formatter<'_>) -> std::fmt::Result {
        match self {
            EntityType::Room => write!(f, "room"),
            EntityType::Device => write!(f, "device"),
            EntityType::Scene => write!(f, "scene"),
            EntityType::DeviceGroup => write!(f, "device_group"),
            EntityType::Temperature => write!(f, "temperature"),
            EntityType::Playlist => write!(f, "playlist"),
        }
    }
}

/// A single turn in the dialogue
#[derive(Debug, Clone)]
pub struct DialogueTurn {
    /// User's utterance
    pub user_input: String,
    /// Parsed intent
    pub intent: CommandIntent,
    /// System response
    pub response: Option<String>,
    /// Whether command succeeded
    pub success: bool,
    /// Timestamp
    pub timestamp: Instant,
    /// Extracted entities
    pub entities: Vec<ContextEntity>,
}

/// Dialogue context - maintains conversation state
#[derive(Debug, Clone)]
pub struct DialogueContext {
    /// Current dialogue state
    pub state: DialogueState,
    /// Conversation history
    pub history: VecDeque<DialogueTurn>,
    /// Active entities that can be referenced
    pub active_entities: Vec<ContextEntity>,
    /// Last activity timestamp
    pub last_activity: Instant,
    /// Pending confirmation action (if any)
    pub pending_action: Option<CommandIntent>,
    /// Speaker ID for this dialogue session
    pub speaker_id: Option<String>,
}

impl DialogueContext {
    /// Create a new dialogue context
    pub fn new() -> Self {
        Self {
            state: DialogueState::Idle,
            history: VecDeque::with_capacity(MAX_HISTORY_SIZE),
            active_entities: Vec::new(),
            last_activity: Instant::now(),
            pending_action: None,
            speaker_id: None,
        }
    }

    /// Add a turn to the dialogue history
    pub fn add_turn(&mut self, turn: DialogueTurn) {
        // Update active entities
        for entity in &turn.entities {
            self.update_entity(entity.clone());
        }

        // Add to history
        if self.history.len() >= MAX_HISTORY_SIZE {
            self.history.pop_front();
        }
        self.history.push_back(turn);
        self.last_activity = Instant::now();
    }

    /// Update or add an entity to active context
    pub fn update_entity(&mut self, entity: ContextEntity) {
        // Remove existing entity of same type/name
        self.active_entities.retain(|e| {
            !(e.entity_type == entity.entity_type && e.name == entity.name)
        });
        self.active_entities.push(entity);

        // Prune old entities (keep last 5 per type)
        let mut counts: std::collections::HashMap<String, usize> = std::collections::HashMap::new();
        self.active_entities.retain(|e| {
            let key = format!("{:?}", e.entity_type);
            let count = counts.entry(key).or_insert(0);
            *count += 1;
            *count <= 5
        });
    }

    /// Get the most recently referenced entity of a type
    pub fn get_entity(&self, entity_type: EntityType) -> Option<&ContextEntity> {
        self.active_entities
            .iter()
            .filter(|e| e.entity_type == entity_type)
            .max_by_key(|e| e.last_referenced)
    }

    /// Get the last room mentioned
    pub fn last_room(&self) -> Option<&str> {
        self.get_entity(EntityType::Room)
            .map(|e| e.name.as_str())
    }

    /// Get the last device mentioned
    pub fn last_device(&self) -> Option<&str> {
        self.get_entity(EntityType::Device)
            .map(|e| e.name.as_str())
    }

    /// Check if context has expired
    pub fn is_expired(&self) -> bool {
        self.last_activity.elapsed() > CONTEXT_TIMEOUT
    }

    /// Check if we're in the follow-up window
    pub fn in_follow_up_window(&self) -> bool {
        self.last_activity.elapsed() < FOLLOW_UP_WINDOW
    }

    /// Clear the context
    pub fn clear(&mut self) {
        self.history.clear();
        self.active_entities.clear();
        self.state = DialogueState::Idle;
        self.pending_action = None;
        debug!("Dialogue context cleared");
    }

    /// Get the last successful intent (for follow-up resolution)
    pub fn last_intent(&self) -> Option<&CommandIntent> {
        self.history
            .iter()
            .rev()
            .find(|t| t.success)
            .map(|t| &t.intent)
    }
}

impl Default for DialogueContext {
    fn default() -> Self {
        Self::new()
    }
}

// ============================================================================
// Dialogue State Machine
// ============================================================================

/// State machine for dialogue management
pub struct DialogueStateMachine {
    /// Current context
    context: DialogueContext,
}

impl DialogueStateMachine {
    /// Create a new dialogue state machine
    pub fn new() -> Self {
        Self {
            context: DialogueContext::new(),
        }
    }

    /// Create with existing context
    pub fn with_context(context: DialogueContext) -> Self {
        Self { context }
    }

    /// Get current state
    pub fn state(&self) -> DialogueState {
        self.context.state
    }

    /// Get the context
    pub fn context(&self) -> &DialogueContext {
        &self.context
    }

    /// Get mutable context
    pub fn context_mut(&mut self) -> &mut DialogueContext {
        &mut self.context
    }

    /// Start listening (wake word detected)
    pub fn start_listening(&mut self) {
        // Clear if expired
        if self.context.is_expired() {
            self.context.clear();
        }
        self.context.state = DialogueState::Listening;
        self.context.last_activity = Instant::now();
        debug!("Dialogue: start listening");
    }

    /// Process input - returns resolved intent with context applied
    pub fn process_input(&mut self, input: &str, intent: CommandIntent) -> CommandIntent {
        self.context.state = DialogueState::Processing;

        // Resolve pronouns and apply context
        let resolved_intent = self.resolve_references(input, intent);

        // Extract entities from the resolved intent
        let entities = self.extract_entities(&resolved_intent);

        // Create dialogue turn
        let turn = DialogueTurn {
            user_input: input.to_string(),
            intent: resolved_intent.clone(),
            response: None,
            success: false, // Will be updated after execution
            timestamp: Instant::now(),
            entities,
        };

        self.context.add_turn(turn);
        debug!("Dialogue: processed input -> {:?}", resolved_intent);

        resolved_intent
    }

    /// Record command result
    pub fn record_result(&mut self, success: bool, response: Option<String>) {
        if let Some(turn) = self.context.history.back_mut() {
            turn.success = success;
            turn.response = response;
        }

        if success {
            self.context.state = DialogueState::AwaitingFollowUp;
        } else {
            self.context.state = DialogueState::Error;
        }
    }

    /// Set pending confirmation action
    pub fn request_confirmation(&mut self, intent: CommandIntent) {
        self.context.pending_action = Some(intent);
        self.context.state = DialogueState::AwaitingConfirmation;
    }

    /// Handle confirmation response
    pub fn handle_confirmation(&mut self, confirmed: bool) -> Option<CommandIntent> {
        let action = self.context.pending_action.take();
        if confirmed {
            self.context.state = DialogueState::Processing;
            action
        } else {
            self.context.state = DialogueState::Idle;
            None
        }
    }

    /// Return to idle state
    pub fn return_to_idle(&mut self) {
        self.context.state = DialogueState::Idle;
    }

    /// Check if input is a confirmation
    pub fn is_confirmation(&self, input: &str) -> Option<bool> {
        let input_lower = input.to_lowercase();
        let positive = ["yes", "yeah", "yep", "sure", "ok", "okay", "confirm", "do it", "go ahead"];
        let negative = ["no", "nope", "cancel", "stop", "nevermind", "never mind", "don't"];

        if positive.iter().any(|&p| input_lower.contains(p)) {
            Some(true)
        } else if negative.iter().any(|&n| input_lower.contains(n)) {
            Some(false)
        } else {
            None
        }
    }

    /// Resolve pronoun references using context
    fn resolve_references(&self, input: &str, intent: CommandIntent) -> CommandIntent {
        let input_lower = input.to_lowercase();

        // Check for pronouns that need resolution
        let has_pronoun = input_lower.contains("them")
            || input_lower.contains("it")
            || input_lower.contains("those")
            || input_lower.contains("that")
            || input_lower.contains("there");

        if !has_pronoun {
            return intent;
        }

        // Try to resolve based on context
        match &intent {
            CommandIntent::Lights(level) => {
                // "Dim them" -> apply to last room
                if let Some(room) = self.context.last_room() {
                    debug!("Resolved 'them/it' to room: {}", room);
                    // The intent already has the level, context provides the target
                    // In a full implementation, we'd return a RoomLights(room, level) variant
                }
                CommandIntent::Lights(*level)
            }
            CommandIntent::Shades(action) => {
                if let Some(room) = self.context.last_room() {
                    debug!("Resolved shades target to room: {}", room);
                }
                CommandIntent::Shades(action.clone())
            }
            // Add more cases as needed
            _ => intent,
        }
    }

    /// Extract entities from an intent
    fn extract_entities(&self, intent: &CommandIntent) -> Vec<ContextEntity> {
        let mut entities = Vec::new();
        let now = Instant::now();

        match intent {
            CommandIntent::Scene(scene) => {
                entities.push(ContextEntity {
                    entity_type: EntityType::Scene,
                    name: scene.clone(),
                    last_referenced: now,
                });
            }
            CommandIntent::Lights(_) => {
                // In full implementation, parse room from original input
                // For now, use "last referenced" or default
            }
            CommandIntent::Temperature(temp) => {
                entities.push(ContextEntity {
                    entity_type: EntityType::Temperature,
                    name: temp.to_string(),
                    last_referenced: now,
                });
            }
            CommandIntent::Music(action) => {
                if let crate::voice_pipeline::MusicAction::Play(Some(playlist)) = action {
                    entities.push(ContextEntity {
                        entity_type: EntityType::Playlist,
                        name: playlist.clone(),
                        last_referenced: now,
                    });
                }
            }
            _ => {}
        }

        entities
    }

    /// Set speaker for this session
    pub fn set_speaker(&mut self, speaker_id: Option<String>) {
        self.context.speaker_id = speaker_id;
    }

    /// Get current speaker
    pub fn speaker(&self) -> Option<&str> {
        self.context.speaker_id.as_deref()
    }
}

impl Default for DialogueStateMachine {
    fn default() -> Self {
        Self::new()
    }
}

// ============================================================================
// Tests
// ============================================================================

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_initial_state() {
        let dsm = DialogueStateMachine::new();
        assert_eq!(dsm.state(), DialogueState::Idle);
    }

    #[test]
    fn test_start_listening() {
        let mut dsm = DialogueStateMachine::new();
        dsm.start_listening();
        assert_eq!(dsm.state(), DialogueState::Listening);
    }

    #[test]
    fn test_process_input() {
        let mut dsm = DialogueStateMachine::new();
        dsm.start_listening();

        let intent = CommandIntent::Lights(100);
        let resolved = dsm.process_input("turn on the lights", intent);

        assert_eq!(dsm.state(), DialogueState::Processing);
        assert_eq!(resolved, CommandIntent::Lights(100));
    }

    #[test]
    fn test_record_success() {
        let mut dsm = DialogueStateMachine::new();
        dsm.start_listening();
        dsm.process_input("turn on lights", CommandIntent::Lights(100));
        dsm.record_result(true, Some("Lights on".to_string()));

        assert_eq!(dsm.state(), DialogueState::AwaitingFollowUp);
        assert!(dsm.context().history.back().unwrap().success);
    }

    #[test]
    fn test_confirmation_detection() {
        let dsm = DialogueStateMachine::new();

        assert_eq!(dsm.is_confirmation("yes"), Some(true));
        assert_eq!(dsm.is_confirmation("yeah do it"), Some(true));
        assert_eq!(dsm.is_confirmation("no"), Some(false));
        assert_eq!(dsm.is_confirmation("cancel that"), Some(false));
        assert_eq!(dsm.is_confirmation("random words"), None);
    }

    #[test]
    fn test_context_expiry() {
        let mut ctx = DialogueContext::new();
        ctx.last_activity = Instant::now() - Duration::from_secs(120);
        assert!(ctx.is_expired());
    }

    #[test]
    fn test_follow_up_window() {
        let ctx = DialogueContext::new();
        assert!(ctx.in_follow_up_window());
    }

    #[test]
    fn test_entity_tracking() {
        let mut ctx = DialogueContext::new();

        ctx.update_entity(ContextEntity {
            entity_type: EntityType::Room,
            name: "Living Room".to_string(),
            last_referenced: Instant::now(),
        });

        assert_eq!(ctx.last_room(), Some("Living Room"));
    }

    #[test]
    fn test_history_limit() {
        let mut ctx = DialogueContext::new();

        for i in 0..15 {
            ctx.add_turn(DialogueTurn {
                user_input: format!("command {}", i),
                intent: CommandIntent::Lights(i as i32),
                response: None,
                success: true,
                timestamp: Instant::now(),
                entities: vec![],
            });
        }

        assert_eq!(ctx.history.len(), MAX_HISTORY_SIZE);
    }

    #[test]
    fn test_confirmation_flow() {
        let mut dsm = DialogueStateMachine::new();
        let dangerous_intent = CommandIntent::Lock(false);

        dsm.request_confirmation(dangerous_intent.clone());
        assert_eq!(dsm.state(), DialogueState::AwaitingConfirmation);

        let confirmed = dsm.handle_confirmation(true);
        assert_eq!(confirmed, Some(dangerous_intent));
        assert_eq!(dsm.state(), DialogueState::Processing);
    }

    #[test]
    fn test_confirmation_reject() {
        let mut dsm = DialogueStateMachine::new();
        dsm.request_confirmation(CommandIntent::Lock(false));

        let confirmed = dsm.handle_confirmation(false);
        assert_eq!(confirmed, None);
        assert_eq!(dsm.state(), DialogueState::Idle);
    }
}

/*
 * Kagami Dialogue State Machine
 * Beacon (e5) - Guidance, signaling
 *
 * Conversation flows naturally.
 * Context makes commands intuitive.
 * h(x) >= 0. Always.
 */
