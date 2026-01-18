//! World Model Inference for Kagami Hub.
//!
//! Runs the Small OrganismRSSM model (12M params) via ONNX Runtime
//! for real-time state prediction on Raspberry Pi.
//!
//! # Architecture
//!
//! ```text
//! Observations ─┬─► World Model ─► Predicted State ─► Action Selection
//!               │                                     │
//! Actions ──────┘                                     │
//!               ▲                                     │
//!               └─────────────────────────────────────┘
//! ```
//!
//! # Usage
//!
//! ```rust,ignore
//! use kagami_hub::world_model::WorldModelInference;
//!
//! let model = WorldModelInference::new("models/organism_rssm_small.onnx")?;
//! let state = model.predict(&observation, &action)?;
//! ```
//!
//! Created: January 12, 2026

use std::path::Path;
use std::sync::Arc;
use std::time::Instant;

use anyhow::{anyhow, Context, Result};
use ndarray::{Array1, Array2, Array3};
use ort::{Environment, ExecutionProvider, GraphOptimizationLevel, Session, SessionBuilder, Value};
use parking_lot::RwLock;
use tracing::{debug, error, info, instrument, warn};

/// Configuration for world model inference.
#[derive(Debug, Clone)]
pub struct WorldModelConfig {
    /// Path to ONNX model file.
    pub model_path: String,

    /// Observation dimension (default: 64).
    pub obs_dim: usize,

    /// Action dimension (default: 8, matching E8).
    pub action_dim: usize,

    /// Hidden state dimension (default: 256).
    pub hidden_dim: usize,

    /// Stochastic latent dimension (default: 16).
    pub stoch_dim: usize,

    /// Sequence length for inference (default: 1 for single-step).
    pub seq_len: usize,

    /// Whether to use GPU if available.
    pub use_gpu: bool,

    /// Number of inference threads.
    pub num_threads: usize,
}

impl Default for WorldModelConfig {
    fn default() -> Self {
        Self {
            model_path: "models/organism_rssm_small.onnx".to_string(),
            obs_dim: 64,
            action_dim: 8,
            hidden_dim: 256,
            stoch_dim: 16,
            seq_len: 1,
            use_gpu: false,      // RPi doesn't have GPU
            num_threads: 4,       // RPi has 4 cores
        }
    }
}

/// World model prediction output.
#[derive(Debug, Clone)]
pub struct WorldPrediction {
    /// Predicted next observation.
    pub obs_pred: Vec<f32>,

    /// Updated deterministic hidden state.
    pub h: Vec<f32>,

    /// Updated stochastic latent state.
    pub z: Vec<f32>,

    /// Predicted reward (scalar).
    pub reward: f32,

    /// Predicted continuation probability.
    pub continue_prob: f32,

    /// Inference latency in milliseconds.
    pub latency_ms: f64,
}

/// World model inference engine.
///
/// Loads an ONNX model and provides methods for:
/// - Single-step state prediction
/// - Multi-step trajectory imagination
/// - Action evaluation via predicted rewards
pub struct WorldModelInference {
    config: WorldModelConfig,
    session: Session,
    environment: Arc<Environment>,

    /// Cached hidden state for sequential inference.
    cached_h: RwLock<Option<Array2<f32>>>,

    /// Cached stochastic state.
    cached_z: RwLock<Option<Array2<f32>>>,

    /// Inference counter for telemetry.
    inference_count: RwLock<u64>,
}

impl WorldModelInference {
    /// Create a new world model inference engine.
    ///
    /// # Arguments
    ///
    /// * `model_path` - Path to ONNX model file
    ///
    /// # Errors
    ///
    /// Returns error if model file doesn't exist or ONNX Runtime fails to load it.
    pub fn new<P: AsRef<Path>>(model_path: P) -> Result<Self> {
        let config = WorldModelConfig {
            model_path: model_path.as_ref().to_string_lossy().to_string(),
            ..Default::default()
        };
        Self::with_config(config)
    }

    /// Create with custom configuration.
    pub fn with_config(config: WorldModelConfig) -> Result<Self> {
        info!("Initializing world model from {}", config.model_path);

        // Create ONNX Runtime environment
        let environment = Environment::builder()
            .with_name("kagami_world_model")
            .with_log_level(ort::LoggingLevel::Warning)
            .build()?;

        let environment = Arc::new(environment);

        // Build session with optimizations
        let mut session_builder = SessionBuilder::new(&environment)?;

        // Set optimization level
        session_builder = session_builder
            .with_optimization_level(GraphOptimizationLevel::Level3)?
            .with_intra_threads(config.num_threads)?;

        // Add execution providers
        if config.use_gpu {
            // Try CUDA first, fall back to CPU
            session_builder = session_builder
                .with_execution_providers([
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

        // Log input/output shapes
        for input in &session.inputs {
            debug!("  Input: {} {:?}", input.name, input.input_type);
        }
        for output in &session.outputs {
            debug!("  Output: {} {:?}", output.name, output.output_type);
        }

        Ok(Self {
            config,
            session,
            environment,
            cached_h: RwLock::new(None),
            cached_z: RwLock::new(None),
            inference_count: RwLock::new(0),
        })
    }

    /// Predict next state given observation and action.
    ///
    /// # Arguments
    ///
    /// * `observation` - Current observation vector [obs_dim]
    /// * `action` - Action to take [action_dim]
    ///
    /// # Returns
    ///
    /// Predicted next state and updated hidden states.
    #[instrument(skip(self, observation, action))]
    pub fn predict(&self, observation: &[f32], action: &[f32]) -> Result<WorldPrediction> {
        let start = Instant::now();

        // Validate inputs
        if observation.len() != self.config.obs_dim {
            return Err(anyhow!(
                "Observation dimension mismatch: expected {}, got {}",
                self.config.obs_dim,
                observation.len()
            ));
        }

        if action.len() != self.config.action_dim {
            return Err(anyhow!(
                "Action dimension mismatch: expected {}, got {}",
                self.config.action_dim,
                action.len()
            ));
        }

        // Prepare inputs
        let obs_array = Array3::from_shape_vec(
            (1, self.config.seq_len, self.config.obs_dim),
            observation.to_vec(),
        )?;

        let action_array = Array3::from_shape_vec(
            (1, self.config.seq_len, self.config.action_dim),
            action.to_vec(),
        )?;

        // Get or initialize hidden states
        let h = self
            .cached_h
            .read()
            .clone()
            .unwrap_or_else(|| Array2::zeros((1, self.config.hidden_dim)));

        let z = self
            .cached_z
            .read()
            .clone()
            .unwrap_or_else(|| Array2::zeros((1, self.config.stoch_dim)));

        // Create input tensors
        let inputs = vec![
            Value::from_array(obs_array)?,
            Value::from_array(action_array)?,
            Value::from_array(h.clone())?,
            Value::from_array(z.clone())?,
        ];

        // Run inference
        let outputs = self.session.run(inputs)?;

        // Extract outputs
        let obs_pred: Vec<f32> = outputs[0]
            .try_extract_tensor::<f32>()?
            .view()
            .iter()
            .copied()
            .collect();

        let h_out: Array2<f32> = outputs[1]
            .try_extract_tensor::<f32>()?
            .view()
            .to_owned()
            .into_shape((1, self.config.hidden_dim))?;

        let z_out: Array2<f32> = outputs[2]
            .try_extract_tensor::<f32>()?
            .view()
            .to_owned()
            .into_shape((1, self.config.stoch_dim))?;

        // Extract reward and continue predictions if available
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
            1.0 / (1.0 + (-logit).exp()) // Sigmoid
        } else {
            1.0
        };

        // Cache updated states
        *self.cached_h.write() = Some(h_out.clone());
        *self.cached_z.write() = Some(z_out.clone());

        // Update counter
        *self.inference_count.write() += 1;

        let latency_ms = start.elapsed().as_secs_f64() * 1000.0;

        Ok(WorldPrediction {
            obs_pred,
            h: h_out.into_raw_vec(),
            z: z_out.into_raw_vec(),
            reward,
            continue_prob,
            latency_ms,
        })
    }

    /// Imagine a trajectory given initial state and action sequence.
    ///
    /// # Arguments
    ///
    /// * `initial_obs` - Starting observation
    /// * `actions` - Sequence of actions to imagine [horizon, action_dim]
    ///
    /// # Returns
    ///
    /// Sequence of predicted observations [horizon+1, obs_dim]
    pub fn imagine(
        &self,
        initial_obs: &[f32],
        actions: &[Vec<f32>],
    ) -> Result<Vec<WorldPrediction>> {
        let mut trajectory = Vec::with_capacity(actions.len() + 1);

        // Start with initial observation
        let mut current_obs = initial_obs.to_vec();

        // Reset hidden states for imagination
        self.reset_state();

        for action in actions {
            let prediction = self.predict(&current_obs, action)?;
            current_obs = prediction.obs_pred.clone();
            trajectory.push(prediction);
        }

        Ok(trajectory)
    }

    /// Evaluate action by predicting expected reward.
    ///
    /// # Arguments
    ///
    /// * `observation` - Current observation
    /// * `action` - Action to evaluate
    ///
    /// # Returns
    ///
    /// Expected reward for taking the action.
    pub fn evaluate_action(&self, observation: &[f32], action: &[f32]) -> Result<f32> {
        let prediction = self.predict(observation, action)?;
        Ok(prediction.reward)
    }

    /// Reset hidden states (e.g., at episode boundary).
    pub fn reset_state(&self) {
        *self.cached_h.write() = None;
        *self.cached_z.write() = None;
    }

    /// Get inference statistics.
    pub fn get_stats(&self) -> WorldModelStats {
        WorldModelStats {
            inference_count: *self.inference_count.read(),
            model_path: self.config.model_path.clone(),
            obs_dim: self.config.obs_dim,
            action_dim: self.config.action_dim,
        }
    }
}

/// World model statistics.
#[derive(Debug, Clone)]
pub struct WorldModelStats {
    pub inference_count: u64,
    pub model_path: String,
    pub obs_dim: usize,
    pub action_dim: usize,
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_config_default() {
        let config = WorldModelConfig::default();
        assert_eq!(config.obs_dim, 64);
        assert_eq!(config.action_dim, 8);
        assert_eq!(config.hidden_dim, 256);
    }

    // Note: Actual model loading tests require ONNX model file
    // which is generated by the export pipeline.
}
