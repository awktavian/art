//! LLM Integration Module for Kagami Hub
//!
//! Provides natural language understanding for complex queries
//! when pattern matching isn't sufficient.
//!
//! Features:
//! - Cloud LLM via Kagami API
//! - Function calling for home automation
//! - Conversation context management
//! - Intent extraction and slot filling
//!
//! Colony: Nexus (e₄) → Beacon (e₅)
//!
//! η → s → μ → a → η′
//! h(x) ≥ 0. Always.

use anyhow::Result;
use std::collections::HashMap;
use std::sync::Arc;
use std::time::{Duration, Instant};
use tokio::sync::RwLock;
use tracing::{debug, info, warn, error};
use serde::{Deserialize, Serialize};

// ============================================================================
// Configuration
// ============================================================================

/// LLM configuration
#[derive(Debug, Clone)]
pub struct LLMConfig {
    /// Kagami API URL
    pub api_url: String,
    /// API key for authentication
    pub api_key: Option<String>,
    /// Model to use (e.g., "kagami-chat", "gpt-4")
    pub model: String,
    /// Maximum tokens to generate
    pub max_tokens: u32,
    /// Temperature for generation
    pub temperature: f32,
    /// Timeout for API calls
    pub timeout_secs: u64,
    /// Enable function calling
    pub enable_functions: bool,
    /// Maximum conversation history
    pub max_history: usize,
}

impl Default for LLMConfig {
    fn default() -> Self {
        Self {
            api_url: "http://localhost:8000".to_string(),
            api_key: None,
            model: "kagami-chat".to_string(),
            max_tokens: 150,
            temperature: 0.7,
            timeout_secs: 30,
            enable_functions: true,
            max_history: 10,
        }
    }
}

// ============================================================================
// LLM Messages
// ============================================================================

/// Role in conversation
#[derive(Debug, Clone, Serialize, Deserialize, PartialEq)]
#[serde(rename_all = "lowercase")]
pub enum Role {
    System,
    User,
    Assistant,
    Function,
}

/// Chat message
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct Message {
    pub role: Role,
    pub content: String,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub name: Option<String>,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub function_call: Option<FunctionCall>,
}

impl Message {
    /// Create a system message
    pub fn system(content: impl Into<String>) -> Self {
        Self {
            role: Role::System,
            content: content.into(),
            name: None,
            function_call: None,
        }
    }

    /// Create a user message
    pub fn user(content: impl Into<String>) -> Self {
        Self {
            role: Role::User,
            content: content.into(),
            name: None,
            function_call: None,
        }
    }

    /// Create an assistant message
    pub fn assistant(content: impl Into<String>) -> Self {
        Self {
            role: Role::Assistant,
            content: content.into(),
            name: None,
            function_call: None,
        }
    }

    /// Create a function result message
    pub fn function_result(name: impl Into<String>, result: impl Into<String>) -> Self {
        Self {
            role: Role::Function,
            content: result.into(),
            name: Some(name.into()),
            function_call: None,
        }
    }
}

/// Function call request from LLM
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct FunctionCall {
    pub name: String,
    pub arguments: String,
}

// ============================================================================
// Function Definitions
// ============================================================================

/// Function definition for LLM
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct FunctionDef {
    pub name: String,
    pub description: String,
    pub parameters: FunctionParameters,
}

/// Function parameters schema
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct FunctionParameters {
    #[serde(rename = "type")]
    pub type_: String,
    pub properties: HashMap<String, ParameterDef>,
    #[serde(default)]
    pub required: Vec<String>,
}

/// Parameter definition
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct ParameterDef {
    #[serde(rename = "type")]
    pub type_: String,
    pub description: String,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub enum_values: Option<Vec<String>>,
}

/// Standard home automation functions
pub fn home_automation_functions() -> Vec<FunctionDef> {
    vec![
        FunctionDef {
            name: "set_lights".to_string(),
            description: "Set the brightness of lights in one or more rooms".to_string(),
            parameters: FunctionParameters {
                type_: "object".to_string(),
                properties: [
                    ("level".to_string(), ParameterDef {
                        type_: "integer".to_string(),
                        description: "Brightness level from 0 (off) to 100 (full brightness)".to_string(),
                        enum_values: None,
                    }),
                    ("rooms".to_string(), ParameterDef {
                        type_: "array".to_string(),
                        description: "List of room names (omit for all rooms)".to_string(),
                        enum_values: None,
                    }),
                ].into_iter().collect(),
                required: vec!["level".to_string()],
            },
        },
        FunctionDef {
            name: "control_shades".to_string(),
            description: "Open or close window shades in one or more rooms".to_string(),
            parameters: FunctionParameters {
                type_: "object".to_string(),
                properties: [
                    ("action".to_string(), ParameterDef {
                        type_: "string".to_string(),
                        description: "Whether to open or close the shades".to_string(),
                        enum_values: Some(vec!["open".to_string(), "close".to_string()]),
                    }),
                    ("rooms".to_string(), ParameterDef {
                        type_: "array".to_string(),
                        description: "List of room names (omit for all rooms)".to_string(),
                        enum_values: None,
                    }),
                ].into_iter().collect(),
                required: vec!["action".to_string()],
            },
        },
        FunctionDef {
            name: "activate_scene".to_string(),
            description: "Activate a pre-defined scene like movie mode or goodnight".to_string(),
            parameters: FunctionParameters {
                type_: "object".to_string(),
                properties: [
                    ("scene".to_string(), ParameterDef {
                        type_: "string".to_string(),
                        description: "Name of the scene to activate".to_string(),
                        enum_values: Some(vec![
                            "movie_mode".to_string(),
                            "goodnight".to_string(),
                            "welcome_home".to_string(),
                            "focus".to_string(),
                        ]),
                    }),
                ].into_iter().collect(),
                required: vec!["scene".to_string()],
            },
        },
        FunctionDef {
            name: "control_fireplace".to_string(),
            description: "Turn the fireplace on or off".to_string(),
            parameters: FunctionParameters {
                type_: "object".to_string(),
                properties: [
                    ("state".to_string(), ParameterDef {
                        type_: "boolean".to_string(),
                        description: "True to turn on, false to turn off".to_string(),
                        enum_values: None,
                    }),
                ].into_iter().collect(),
                required: vec!["state".to_string()],
            },
        },
        FunctionDef {
            name: "control_tesla".to_string(),
            description: "Control Tesla vehicle (climate, lock, trunk, etc.)".to_string(),
            parameters: FunctionParameters {
                type_: "object".to_string(),
                properties: [
                    ("action".to_string(), ParameterDef {
                        type_: "string".to_string(),
                        description: "Action to perform on the vehicle".to_string(),
                        enum_values: Some(vec![
                            "climate_on".to_string(),
                            "climate_off".to_string(),
                            "lock".to_string(),
                            "unlock".to_string(),
                            "open_frunk".to_string(),
                            "open_trunk".to_string(),
                            "honk".to_string(),
                            "flash".to_string(),
                        ]),
                    }),
                    ("temperature".to_string(), ParameterDef {
                        type_: "number".to_string(),
                        description: "Target temperature for climate (if action is climate_on)".to_string(),
                        enum_values: None,
                    }),
                ].into_iter().collect(),
                required: vec!["action".to_string()],
            },
        },
        FunctionDef {
            name: "play_music".to_string(),
            description: "Control music playback via Spotify".to_string(),
            parameters: FunctionParameters {
                type_: "object".to_string(),
                properties: [
                    ("action".to_string(), ParameterDef {
                        type_: "string".to_string(),
                        description: "Music control action".to_string(),
                        enum_values: Some(vec![
                            "play".to_string(),
                            "pause".to_string(),
                            "skip".to_string(),
                            "previous".to_string(),
                        ]),
                    }),
                    ("playlist".to_string(), ParameterDef {
                        type_: "string".to_string(),
                        description: "Playlist name to play (optional)".to_string(),
                        enum_values: None,
                    }),
                    ("volume".to_string(), ParameterDef {
                        type_: "integer".to_string(),
                        description: "Volume level 0-100 (optional)".to_string(),
                        enum_values: None,
                    }),
                ].into_iter().collect(),
                required: vec!["action".to_string()],
            },
        },
        FunctionDef {
            name: "get_status".to_string(),
            description: "Get current status of home systems".to_string(),
            parameters: FunctionParameters {
                type_: "object".to_string(),
                properties: [
                    ("system".to_string(), ParameterDef {
                        type_: "string".to_string(),
                        description: "System to query".to_string(),
                        enum_values: Some(vec![
                            "tesla".to_string(),
                            "weather".to_string(),
                            "lights".to_string(),
                            "security".to_string(),
                            "temperature".to_string(),
                        ]),
                    }),
                    ("room".to_string(), ParameterDef {
                        type_: "string".to_string(),
                        description: "Room to query (optional)".to_string(),
                        enum_values: None,
                    }),
                ].into_iter().collect(),
                required: vec!["system".to_string()],
            },
        },
    ]
}

// ============================================================================
// LLM Response
// ============================================================================

/// LLM completion response
#[derive(Debug, Clone)]
pub struct LLMResponse {
    /// Generated text response
    pub text: String,
    /// Function call if requested
    pub function_call: Option<FunctionCall>,
    /// Finish reason
    pub finish_reason: String,
    /// Token usage
    pub usage: TokenUsage,
    /// Processing time in milliseconds
    pub processing_time_ms: u64,
}

/// Token usage statistics
#[derive(Debug, Clone, Default)]
pub struct TokenUsage {
    pub prompt_tokens: u32,
    pub completion_tokens: u32,
    pub total_tokens: u32,
}

// ============================================================================
// LLM Client
// ============================================================================

/// LLM client for Kagami API
pub struct LLMClient {
    config: LLMConfig,
    http_client: reqwest::Client,
    conversation: RwLock<Vec<Message>>,
    functions: Vec<FunctionDef>,
}

impl LLMClient {
    /// Create a new LLM client
    pub fn new(config: LLMConfig) -> Self {
        let http_client = reqwest::Client::builder()
            .timeout(Duration::from_secs(config.timeout_secs))
            .build()
            .unwrap_or_default();

        let functions = if config.enable_functions {
            home_automation_functions()
        } else {
            vec![]
        };

        Self {
            config,
            http_client,
            conversation: RwLock::new(vec![]),
            functions,
        }
    }

    /// Create with default config
    pub fn default_client() -> Self {
        Self::new(LLMConfig::default())
    }

    /// Initialize with system prompt
    pub async fn initialize(&self, system_prompt: Option<&str>) {
        let prompt = system_prompt.unwrap_or(DEFAULT_SYSTEM_PROMPT);

        let mut conversation = self.conversation.write().await;
        conversation.clear();
        conversation.push(Message::system(prompt));
    }

    /// Send a message and get response
    pub async fn chat(&self, user_message: &str) -> Result<LLMResponse> {
        let start = Instant::now();

        // Add user message to conversation
        {
            let mut conversation = self.conversation.write().await;
            conversation.push(Message::user(user_message));

            // Trim history if needed
            while conversation.len() > self.config.max_history + 1 {
                // Keep system message, remove oldest user/assistant pair
                if conversation.len() > 2 {
                    conversation.remove(1);
                }
            }
        }

        // Build request
        let conversation = self.conversation.read().await;
        let request = ChatRequest {
            model: self.config.model.clone(),
            messages: conversation.clone(),
            max_tokens: self.config.max_tokens,
            temperature: self.config.temperature,
            functions: if self.config.enable_functions { Some(self.functions.clone()) } else { None },
            function_call: if self.config.enable_functions { Some("auto".to_string()) } else { None },
        };
        drop(conversation);

        // Call API
        let response = self.call_api(&request).await?;

        // Add assistant response to conversation
        {
            let mut conversation = self.conversation.write().await;
            if let Some(ref fc) = response.function_call {
                conversation.push(Message {
                    role: Role::Assistant,
                    content: response.text.clone(),
                    name: None,
                    function_call: Some(fc.clone()),
                });
            } else {
                conversation.push(Message::assistant(&response.text));
            }
        }

        let processing_time_ms = start.elapsed().as_millis() as u64;

        Ok(LLMResponse {
            text: response.text,
            function_call: response.function_call,
            finish_reason: response.finish_reason,
            usage: response.usage,
            processing_time_ms,
        })
    }

    /// Add function result to conversation
    pub async fn add_function_result(&self, function_name: &str, result: &str) {
        let mut conversation = self.conversation.write().await;
        conversation.push(Message::function_result(function_name, result));
    }

    /// Clear conversation history
    pub async fn clear_history(&self) {
        let mut conversation = self.conversation.write().await;
        // Keep only system message
        if let Some(first) = conversation.first().cloned() {
            if first.role == Role::System {
                conversation.clear();
                conversation.push(first);
            } else {
                conversation.clear();
            }
        } else {
            conversation.clear();
        }
    }

    /// Call the LLM API
    async fn call_api(&self, request: &ChatRequest) -> Result<LLMResponse> {
        let url = format!("{}/api/v1/chat/completions", self.config.api_url);

        let mut http_request = self.http_client.post(&url);

        if let Some(ref key) = self.config.api_key {
            http_request = http_request.header("Authorization", format!("Bearer {}", key));
        }

        let response = http_request
            .json(request)
            .send()
            .await?;

        if !response.status().is_success() {
            let status = response.status();
            let body = response.text().await.unwrap_or_default();
            return Err(anyhow::anyhow!("LLM API error: {} - {}", status, body));
        }

        let api_response: ChatResponse = response.json().await?;

        // Extract first choice
        let choice = api_response.choices.into_iter().next()
            .ok_or_else(|| anyhow::anyhow!("No response from LLM"))?;

        Ok(LLMResponse {
            text: choice.message.content,
            function_call: choice.message.function_call,
            finish_reason: choice.finish_reason,
            usage: api_response.usage.unwrap_or_default(),
            processing_time_ms: 0,
        })
    }
}

// ============================================================================
// API Request/Response Types
// ============================================================================

#[derive(Debug, Serialize)]
struct ChatRequest {
    model: String,
    messages: Vec<Message>,
    max_tokens: u32,
    temperature: f32,
    #[serde(skip_serializing_if = "Option::is_none")]
    functions: Option<Vec<FunctionDef>>,
    #[serde(skip_serializing_if = "Option::is_none")]
    function_call: Option<String>,
}

#[derive(Debug, Deserialize)]
struct ChatResponse {
    choices: Vec<Choice>,
    usage: Option<TokenUsage>,
}

#[derive(Debug, Deserialize)]
struct Choice {
    message: ChoiceMessage,
    finish_reason: String,
}

#[derive(Debug, Deserialize)]
struct ChoiceMessage {
    #[serde(default)]
    content: String,
    function_call: Option<FunctionCall>,
}

// ============================================================================
// Intent Extraction
// ============================================================================

/// Extracted intent from LLM response
#[derive(Debug, Clone)]
pub struct ExtractedIntent {
    /// Intent category
    pub intent: String,
    /// Confidence score
    pub confidence: f32,
    /// Extracted slots/entities
    pub slots: HashMap<String, serde_json::Value>,
    /// Original text
    pub text: String,
}

/// Extract intent from natural language using LLM
pub async fn extract_intent(
    client: &LLMClient,
    text: &str,
) -> Result<ExtractedIntent> {
    let response = client.chat(text).await?;

    if let Some(fc) = response.function_call {
        // Parse function arguments
        let slots: HashMap<String, serde_json::Value> = serde_json::from_str(&fc.arguments)
            .unwrap_or_default();

        Ok(ExtractedIntent {
            intent: fc.name,
            confidence: 0.9, // High confidence when function call is made
            slots,
            text: text.to_string(),
        })
    } else {
        // No function call - return as conversational response
        Ok(ExtractedIntent {
            intent: "conversation".to_string(),
            confidence: 0.5,
            slots: HashMap::new(),
            text: response.text,
        })
    }
}

// ============================================================================
// Constants
// ============================================================================

const DEFAULT_SYSTEM_PROMPT: &str = r#"You are Kagami, a helpful home assistant. You control a smart home with lights, shades, fireplace, Tesla vehicle, and music.

Be concise and helpful. When the user wants to control something, use the appropriate function. For questions, provide brief answers.

Current context:
- You're installed on a Raspberry Pi hub
- The home has: living room, kitchen, dining, office, bedrooms
- Tesla Model S Plaid is in the garage
- Spotify is available for music

Respond naturally but briefly. Use functions for actions."#;

// ============================================================================
// Tests
// ============================================================================

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_message_creation() {
        let msg = Message::user("Turn on the lights");
        assert_eq!(msg.role, Role::User);
        assert_eq!(msg.content, "Turn on the lights");
    }

    #[test]
    fn test_functions_defined() {
        let functions = home_automation_functions();
        assert!(!functions.is_empty());

        // Check we have the key functions
        let names: Vec<_> = functions.iter().map(|f| f.name.as_str()).collect();
        assert!(names.contains(&"set_lights"));
        assert!(names.contains(&"control_tesla"));
        assert!(names.contains(&"activate_scene"));
    }

    #[test]
    fn test_config_default() {
        let config = LLMConfig::default();
        assert_eq!(config.max_tokens, 150);
        assert!(config.enable_functions);
    }
}

/*
 * 鏡
 * Natural language is the interface to the home.
 * Understanding flows from words to actions.
 */
