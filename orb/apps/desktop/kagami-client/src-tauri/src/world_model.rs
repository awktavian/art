//! World Model Inference for Desktop Client.
//!
//! Runs the Base OrganismRSSM model (50M params) via ONNX Runtime
//! for predictive state modeling on desktop platforms.
//!
//! # Features
//!
//! - Real-time observation encoding
//! - Action prediction and evaluation
//! - Trajectory imagination for planning
//! - Seamless Tauri integration
//!
//! # Usage
//!
//! ```rust,ignore
//! use kagami_client::world_model::WorldModel;
//!
//! let model = WorldModel::new("models/organism_rssm_base.onnx")?;
//! let prediction = model.predict(&observation, &action)?;
//! ```
//!
//! Created: January 12, 2026

use std::path::Path;
use std::sync::Arc;
use std::time::Instant;

use anyhow::{anyhow, Context, Result};
use ndarray::{Array2, Array3};
use ort::{Environment, ExecutionProvider, GraphOptimizationLevel, Session, SessionBuilder, Value};
use parking_lot::RwLock;
use serde::{Deserialize, Serialize};
use tauri::State;
use tracing::{debug, info, instrument, warn};

/// World model configuration.
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct WorldModelConfig {
    /// Path to ONNX model file.
    pub model_path: String,

    /// Observation dimension (default: 64).
    pub obs_dim: usize,

    /// Action dimension (default: 8).
    pub action_dim: usize,

    /// Deterministic hidden dimension (default: 384 for Base model).
    pub hidden_dim: usize,

    /// Stochastic latent dimension (default: 32).
    pub stoch_dim: usize,

    /// Use GPU acceleration if available.
    pub use_gpu: bool,

    /// Number of CPU threads for inference.
    pub num_threads: usize,
}

impl Default for WorldModelConfig {
    fn default() -> Self {
        Self {
            model_path: "models/organism_rssm_base.onnx".to_string(),
            obs_dim: 64,
            action_dim: 8,
            hidden_dim: 384,  // Base model
            stoch_dim: 32,
            use_gpu: true,    // Desktop can use GPU
            num_threads: 8,   // Modern desktops have many cores
        }
    }
}

/// World model prediction result.
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct Prediction {
    /// Predicted next observation.
    pub obs_pred: Vec<f32>,

    /// Predicted reward.
    pub reward: f32,

    /// Episode continuation probability.
    pub continue_prob: f32,

    /// Inference latency in milliseconds.
    pub latency_ms: f64,
}

/// World model state for Tauri.
pub struct WorldModelState {
    inner: RwLock<Option<WorldModelInner>>,
}

impl WorldModelState {
    pub fn new() -> Self {
        Self {
            inner: RwLock::new(None),
        }
    }

    pub fn initialize(&self, config: WorldModelConfig) -> Result<()> {
        let inner = WorldModelInner::new(config)?;
        *self.inner.write() = Some(inner);
        Ok(())
    }

    pub fn predict(&self, observation: &[f32], action: &[f32]) -> Result<Prediction> {
        let guard = self.inner.read();
        let inner = guard
            .as_ref()
            .ok_or_else(|| anyhow!("World model not initialized"))?;
        inner.predict(observation, action)
    }

    pub fn reset(&self) {
        if let Some(inner) = self.inner.write().as_mut() {
            inner.reset_state();
        }
    }
}

impl Default for WorldModelState {
    fn default() -> Self {
        Self::new()
    }
}

/// Inner world model implementation.
struct WorldModelInner {
    config: WorldModelConfig,
    session: Session,
    #[allow(dead_code)]
    environment: Arc<Environment>,

    /// Cached hidden state.
    cached_h: Option<Array2<f32>>,

    /// Cached stochastic state.
    cached_z: Option<Array2<f32>>,
}

impl WorldModelInner {
    fn new(config: WorldModelConfig) -> Result<Self> {
        info!("Initializing world model: {}", config.model_path);

        // Create ONNX environment
        let environment = Arc::new(
            Environment::builder()
                .with_name("kagami_desktop_world_model")
                .with_log_level(ort::LoggingLevel::Warning)
                .build()?,
        );

        // Build session
        let mut session_builder = SessionBuilder::new(&environment)?
            .with_optimization_level(GraphOptimizationLevel::Level3)?
            .with_intra_threads(config.num_threads)?;

        // Configure execution providers
        if config.use_gpu {
            // Try Metal (macOS), CUDA, DirectML in order
            session_builder = session_builder.with_execution_providers([
                #[cfg(target_os = "macos")]
                ExecutionProvider::CoreML(Default::default()),
                #[cfg(target_os = "windows")]
                ExecutionProvider::DirectML(Default::default()),
                #[cfg(target_os = "linux")]
                ExecutionProvider::CUDA(Default::default()),
                ExecutionProvider::CPU(Default::default()),
            ])?;
        }

        let session = session_builder.with_model_from_file(&config.model_path)?;

        info!(
            "World model loaded: {} inputs, {} outputs",
            session.inputs.len(),
            session.outputs.len()
        );

        Ok(Self {
            config,
            session,
            environment,
            cached_h: None,
            cached_z: None,
        })
    }

    fn predict(&self, observation: &[f32], action: &[f32]) -> Result<Prediction> {
        let start = Instant::now();

        // Prepare inputs
        let obs_array = Array3::from_shape_vec(
            (1, 1, self.config.obs_dim),
            observation.to_vec(),
        )?;

        let action_array = Array3::from_shape_vec(
            (1, 1, self.config.action_dim),
            action.to_vec(),
        )?;

        let h = self
            .cached_h
            .clone()
            .unwrap_or_else(|| Array2::zeros((1, self.config.hidden_dim)));

        let z = self
            .cached_z
            .clone()
            .unwrap_or_else(|| Array2::zeros((1, self.config.stoch_dim)));

        // Create input tensors
        let inputs = vec![
            Value::from_array(obs_array)?,
            Value::from_array(action_array)?,
            Value::from_array(h)?,
            Value::from_array(z)?,
        ];

        // Run inference
        let outputs = self.session.run(inputs)?;

        // Extract predictions
        let obs_pred: Vec<f32> = outputs[0]
            .try_extract_tensor::<f32>()?
            .view()
            .iter()
            .copied()
            .collect();

        let reward = if outputs.len() > 3 {
            outputs[3]
                .try_extract_tensor::<f32>()?
                .view()
                .iter()
                .next()
                .copied()
                .unwrap_or(0.0)
        } else {
            0.0
        };

        let continue_prob = if outputs.len() > 4 {
            let logit = outputs[4]
                .try_extract_tensor::<f32>()?
                .view()
                .iter()
                .next()
                .copied()
                .unwrap_or(0.0);
            1.0 / (1.0 + (-logit).exp())
        } else {
            1.0
        };

        let latency_ms = start.elapsed().as_secs_f64() * 1000.0;

        Ok(Prediction {
            obs_pred,
            reward,
            continue_prob,
            latency_ms,
        })
    }

    fn reset_state(&mut self) {
        self.cached_h = None;
        self.cached_z = None;
    }
}

// =============================================================================
// TAURI COMMANDS
// =============================================================================

/// Initialize the world model.
#[tauri::command]
pub async fn world_model_init(
    state: State<'_, WorldModelState>,
    model_path: String,
) -> Result<String, String> {
    let config = WorldModelConfig {
        model_path,
        ..Default::default()
    };

    state
        .initialize(config)
        .map_err(|e| format!("Failed to initialize world model: {}", e))?;

    Ok("World model initialized".to_string())
}

/// Run a single prediction.
#[tauri::command]
pub async fn world_model_predict(
    state: State<'_, WorldModelState>,
    observation: Vec<f32>,
    action: Vec<f32>,
) -> Result<Prediction, String> {
    state
        .predict(&observation, &action)
        .map_err(|e| format!("Prediction failed: {}", e))
}

/// Reset model state.
#[tauri::command]
pub async fn world_model_reset(state: State<'_, WorldModelState>) -> Result<(), String> {
    state.reset();
    Ok(())
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_config_default() {
        let config = WorldModelConfig::default();
        assert_eq!(config.obs_dim, 64);
        assert_eq!(config.action_dim, 8);
        assert_eq!(config.hidden_dim, 384);  // Base model
    }
}
