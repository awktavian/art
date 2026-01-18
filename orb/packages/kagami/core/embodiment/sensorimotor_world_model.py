"""Sensorimotor World Model - Complete Integration

UPDATED: November 27, 2025 - Now uses KagamiWorldModel as the brain.

Unified world model that:
1. Encodes all senses into H¹⁴ × S⁷ manifold
2. Predicts next states via KagamiWorldModel (hourglass architecture)
3. Decodes motor commands
4. Enables closed perception-action loop

This is the CORE of embodied K os integration loop.
"""

import logging
from typing import Any

import torch
import torch.nn as nn

from kagami.core.embodiment.motor_decoder import DISCRETE_ACTIONS, create_motor_decoder
from kagami.core.embodiment.sensorimotor_encoder_optimized import (
    create_sensorimotor_encoder_optimized,
)
from kagami.core.world_model.kagami_world_model import KagamiWorldModelFactory

# UPDATED: Nov 27, 2025 - Use KagamiWorldModel (unified hourglass architecture)

logger = logging.getLogger(__name__)


class SensorimotorWorldModel(nn.Module):
    """Complete sensorimotor world model (adapter for embodied systems).

    ARCHITECTURE (Dec 16, 2025):
    ============================
    This is a CLEAN WRAPPER around KagamiWorldModel that adds:
    - Multi-modal sensory encoding (vision, audio, touch, proprioception, etc.)
    - Motor command decoding (discrete actions: move, grip, speak, etc.)
    - Embodied coordination (sensorimotor integration)

    Pipeline:
      Senses → Encoder → H¹⁴ × S⁷ → KagamiWorldModel → Prediction → Decoder → Actions

    The world model itself (prediction, dynamics, RSSM) is FULLY DELEGATED to
    KagamiWorldModel (self.brain). This class handles only I/O adaptation.

    Enables:
      - Multi-modal perception fusion
      - Predictive world modeling (via KagamiWorldModel)
      - Action planning
      - Uncertainty quantification
      - Integration monitoring (feedback loop over sensorimotor state)
    """

    def __init__(
        self,
        matryoshka_dims: list[int] | None = None,
        enable_integration_metrics: bool = True,
        device: str | None = None,
        compile_model: bool = True,
        compile_mode: str = "reduce-overhead",
        precision: str = "fp32",
        temporal: bool = True,
        memory_len: int = 8,
        use_text_adapter: bool = False,
        training_bypass: bool = False,
        enable_rssm: bool = True,  # IGNORED: RSSM always enabled
        _rssm_deterministic_dim: int = 256,  # Unused: RSSM dims from KagamiWorldModel
        rssm_action_dim: int = 8,
    ) -> None:
        super().__init__()
        # Exceptional hierarchy dimensions from centralized config (Bulk -> Nucleus order)
        if matryoshka_dims is None:
            from kagami_math.dimensions import get_layer_dimensions

            matryoshka_dims = list(get_layer_dimensions())
        self.matryoshka_dims = list(matryoshka_dims)
        self._enable_integration_metrics_flag = bool(enable_integration_metrics)

        if device is None:
            device = "mps" if torch.backends.mps.is_available() else "cpu"
        self.device = device
        # RSSM is always enabled in KagamiWorldModel, this flag is now legacy
        self.enable_rssm = True
        # Gate FP16 to CUDA only
        requested_fp16 = str(precision).lower() == "fp16"
        is_cuda = device.startswith("cuda") or (torch.cuda.is_available() and device == "cuda")
        self.use_autocast = requested_fp16 and is_cuda
        self.device_type = "cuda" if is_cuda else ("mps" if device == "mps" else "cpu")
        self.autocast_dtype = torch.float16 if self.use_autocast else None

        # === ENCODER: Senses → Manifold (OPTIMIZED) ===
        self.encoder = create_sensorimotor_encoder_optimized(device=device)

        # === VIDEO ENCODER: Temporal visual understanding ===
        # Augments static vision embeddings with video priors for richer temporal/physics signals.
        # NEW: Video features feed directly into H¹⁴ temporal dimension
        self.video_encoder = None
        self.video_to_h14 = None  # Direct video → H¹⁴ projection
        try:
            from kagami.core.embodiment.video_encoder import create_video_encoder

            self.video_encoder = create_video_encoder(device=device, embedding_dim=512)

            # Project video temporal features → H¹⁴ (physics-informed)
            self.video_to_h14 = nn.Sequential(
                nn.Linear(512, 128),
                nn.Tanh(),
                nn.Linear(128, 14),  # → H¹⁴
            ).to(device)

            logger.info("✅ Video encoder enabled with H¹⁴ temporal projection (physics priors)")
        except Exception as e:
            logger.debug(f"Video encoder unavailable: {e}, using static vision only")

        # Legacy CLIP vision encoder removed (Dec 2025).
        # SensorimotorWorldModel consumes vision embeddings directly (e.g., from UnifiedVisionModule/DINOv2)
        # via the sensorimotor encoder, so no internal CLIP dependency is needed.
        self.vision_to_manifold = None

        # === WORLD MODEL: KagamiWorldModel (Unified Hourglass) ===
        # HARDENED (Nov 30, 2025): All features always enabled, presets removed
        self.brain = KagamiWorldModelFactory.create(
            layer_dimensions=tuple(matryoshka_dims),
            dropout=0.05,
        ).to(device)

        # Compile brain if requested
        if compile_model and hasattr(torch, "compile"):
            try:
                self.brain = torch.compile(self.brain, mode=compile_mode)  # type: ignore[assignment]
            except Exception as e:
                logger.warning(f"torch.compile(brain) failed: {e}")

        # === DECODER: Manifold → Motor Commands ===
        final_dim = matryoshka_dims[-1]  # 14
        self.decoder = create_motor_decoder(input_dim=final_dim, device=device)

        # Adapter: Brain output (512) -> Base state (512)
        # Since output matches input dim in Hourglass, this is Identity
        self.output_adapter: nn.Module
        if matryoshka_dims[0] == 512:
            self.output_adapter = nn.Identity()
        else:
            self.output_adapter = nn.Linear(matryoshka_dims[0], matryoshka_dims[0]).to(device)

        # Bridge from base state (512) to decoder input (14) when needed
        self.state_to_decoder = nn.Linear(matryoshka_dims[0], final_dim).to(device)

        # === PROJECTION: H¹⁴ × S⁷ embedding (14+8=22D) → base state ===
        # Note: Uses 22D (14 hyperbolic + 8 octonion embedding) for actual computation
        # Intrinsic manifold dimension is 21D (14+7), but we embed S⁷ in ℝ⁸
        self.manifold_to_state = nn.Linear(22, matryoshka_dims[0]).to(device)

        # === EXPANSION: Add sequence dimension ===
        self.seq_expander = nn.Parameter(torch.randn(1, 16, matryoshka_dims[0])).to(device)

        # === OPTIONAL TEXT→STATE ADAPTER (for fast BC/RL on text-only tasks) ===
        self.use_text_adapter = bool(use_text_adapter)
        self.language_to_state: nn.Module
        if self.use_text_adapter:
            self.language_to_state = nn.Linear(384, matryoshka_dims[0]).to(device)
        else:
            self.language_to_state = nn.Identity()

        # === OPTIONAL: Compile encoder/decoder for end-to-end compile ===
        if compile_model and hasattr(torch, "compile"):
            try:
                self.encoder = torch.compile(self.encoder, mode=compile_mode)
            except Exception as e:
                logger.warning(f"torch.compile(encoder) failed: {e}")
            try:
                # brain already compiled inside create_matryoshka_v2 when enabled
                self.decoder = torch.compile(self.decoder, mode=compile_mode)  # type: ignore[assignment]
            except Exception as e:
                logger.warning(f"torch.compile(decoder) failed: {e}")

        # === TEMPORAL MEMORY BUFFER ===
        self.memory_len = max(0, int(memory_len))
        self._state_memory: list[torch.Tensor] = []  # store past [B, 32]
        self.training_bypass = bool(training_bypass)
        if self.training_bypass:
            self.bypass_proj = nn.Linear(matryoshka_dims[0], matryoshka_dims[-1]).to(device)

        # === RSSM DYNAMICS ===
        # DELEGATED (Nov 30, 2025): RSSM is now handled entirely by KagamiWorldModel (self.brain)
        # Redundant local RSSM removed to ensure single source of truth.
        self._rssm_h: torch.Tensor | None = None
        self._rssm_z: torch.Tensor | None = None

        logger.info(f"✅ SensorimotorWorldModel initialized: {len(matryoshka_dims)} layers")

    def encode_senses(
        self,
        vision_emb: torch.Tensor | None = None,
        audio_emb: torch.Tensor | None = None,
        touch_emb: torch.Tensor | None = None,
        language_emb: torch.Tensor | None = None,
        proprio_emb: torch.Tensor | None = None,
        intero_emb: torch.Tensor | None = None,
        meta_emb: torch.Tensor | None = None,
        video_frames: torch.Tensor | None = None,
    ) -> tuple[torch.Tensor, torch.Tensor]:
        """Encode all sensory inputs into manifold.

        Args:
            vision_emb: Static vision embedding [B, 512] (SOTA vision encoder output)
            video_frames: Video sequence [B, T, C, H, W] (temporal, richer)
            ... (other modalities)

        Returns:
            z_temporal: [B, 14] hyperbolic position
            o_sensory: [B, 8] octonion sensory state
        """
        # If video frames provided, use video encoder (preferred over static vision embeddings)
        video_h14_contribution = None
        if video_frames is not None and self.video_encoder is not None:
            try:
                video_result = self.video_encoder.encode_video(video_frames)
                # Use video embedding instead of static vision
                vision_emb = video_result["video_embedding"]

                # NEW: Project video features directly to H¹⁴ (temporal physics)
                if self.video_to_h14 is not None:
                    video_h14_contribution = self.video_to_h14(video_result["video_embedding"])
                    # Store for merging with encoder's z_temporal

                # Store physics signals for downstream use
                if hasattr(self, "_last_physics_signals"):
                    self._last_physics_signals = video_result.get("physics_signals", {})

            except Exception as e:
                logger.warning(f"Video encoding failed: {e}, falling back to static vision")

        # Encode via sensorimotor encoder
        z_temporal_base, o_sensory = self.encoder(
            vision_emb=vision_emb,
            audio_emb=audio_emb,
            touch_emb=touch_emb,
            language_emb=language_emb,
            proprio_emb=proprio_emb,
            intero_emb=intero_emb,
            meta_emb=meta_emb,
        )

        # Merge video H¹⁴ contribution if available
        if video_h14_contribution is not None:
            # Fuse: z_temporal = α·z_base + (1-α)·z_video
            alpha = 0.7  # Weight towards encoder base
            z_temporal = alpha * z_temporal_base + (1 - alpha) * video_h14_contribution
            # Reproject to H¹⁴
            from kagami.core.mobiasm import create_mobiasm_v2

            mobiasm = create_mobiasm_v2(device=self.device)
            z_temporal = mobiasm.poincare.project(z_temporal)
        else:
            z_temporal = z_temporal_base

        return z_temporal, o_sensory

    def predict(
        self,
        vision_emb: torch.Tensor | None = None,
        audio_emb: torch.Tensor | None = None,
        touch_emb: torch.Tensor | None = None,
        language_emb: torch.Tensor | None = None,
        proprio_emb: torch.Tensor | None = None,
        intero_emb: torch.Tensor | None = None,
        meta_emb: torch.Tensor | None = None,
        video_frames: torch.Tensor | None = None,
    ) -> dict[str, Any]:
        """Complete sensorimotor prediction.

        Pipeline:
          1. Encode senses → H¹⁴ × S⁷
          2. Project to 32D state
          3. Predict via Matryoshka brain
          4. Decode motor commands
          5. Return predictions + integration metrics

        Returns:
            Dictionary with:
              - predicted_manifold_state: Next state in H¹⁴ × S⁷
              - motor_commands: Decoded actions
              - integration_score: Experimental integration proxy
              - uncertainty: Prediction confidence
              - sense_decomposition: Individual sense strengths
        """
        autocast_ctx = (
            torch.amp.autocast(self.device_type, dtype=self.autocast_dtype)
            if self.use_autocast
            else torch.enable_grad()
            if torch.is_grad_enabled()
            else torch.no_grad()
        )

        with autocast_ctx:
            # === 1. ENCODE SENSES (with optional video) ===
            z_temporal, o_sensory = self.encode_senses(
                vision_emb,
                audio_emb,
                touch_emb,
                language_emb,
                proprio_emb,
                intero_emb,
                meta_emb,
                video_frames,
            )

            # Combine manifold components (H¹⁴ + S⁷ embedding = 14 + 8 = 22D in ℝ⁸)
            # Note: S⁷ is 7D intrinsically but embedded in ℝ⁸ for octonion ops
            manifold_state = torch.cat([z_temporal, o_sensory], dim=-1)  # [B, 22]

            # === 2. PROJECT TO STATE SPACE ===
            if self.use_text_adapter and language_emb is not None:
                # Fast path for text-only curriculum: learnable mapping
                state_32d = self.language_to_state(language_emb.to(self.device))  # [B, 32]
            else:
                state_32d = self.manifold_to_state(manifold_state)  # [B, 32]

            # Add sequence dimension (temporal context)
            # Seed with learned template, then write current + memory frames at the front
            state_seq = self.seq_expander.repeat(state_32d.shape[0], 1, 1).clone()  # [B, 16, 32]
            state_seq[:, 0:1, :] = state_32d.unsqueeze(1)
            if self._state_memory:
                # Use as many as fit after the current frame
                frames = min(len(self._state_memory), state_seq.shape[1] - 1)
                for i in range(frames):
                    mem = self._state_memory[-(i + 1)]  # most recent first
                    # Ensure shape [B, 32]
                    mem = mem.to(state_32d.device)
                    state_seq[:, i + 1 : i + 2, :] = mem.unsqueeze(1)

            # === 3. WORLD MODEL PREDICTION ===
            if self.training_bypass:
                # Bypass brain for fast training smoke
                latent_state = self.bypass_proj(state_seq)  # [B, 16, final_dim]
                predicted_state = state_seq
                brain_info = {
                    "num_layers": 1,
                    "dimensions": [self.bypass_proj.out_features],
                    "loop_strength": 0.0,
                    "temporal_coherence": 1.0,
                    "integration_score": 0.0,
                    "latent_state": latent_state.detach(),
                }
            else:
                # OptimizedWorldModel returns (output, metrics)
                # output is the high-dim (final layer) state
                brain_output, _brain_metrics = self.brain(state_seq)  # [B, 16, final_dim]

                # Project back to base dim for state loop compatibility
                predicted_state = self.output_adapter(brain_output)  # [B, 16, 32]

                brain_info = {
                    "num_layers": len(self.matryoshka_dims),
                    "dimensions": self.matryoshka_dims,
                    "loop_strength": 0.0,
                    "temporal_coherence": 1.0,
                    "integration_score": 0.0,
                    "latent_state": brain_output,  # Keep high-dim state for decoder
                }

            # === 4. DECODE MOTOR COMMANDS ===
            latent_state = brain_info.get("latent_state")
            if isinstance(latent_state, torch.Tensor):
                # KagamiWorldModel outputs the bulk interface (e.g., 512D). The motor decoder
                # expects the nucleus/manifold dimension (final_dim, e.g., 14D). If we are not
                # already in final_dim, project via state_to_decoder.
                latent_state = latent_state.to(predicted_state.device, predicted_state.dtype)
                if latent_state.shape[-1] != self.matryoshka_dims[-1]:
                    motor_input = self.state_to_decoder(latent_state)
                else:
                    motor_input = latent_state
            else:
                motor_input = self.state_to_decoder(predicted_state)
            motor_commands = self.decoder(motor_input)

        # === 5. EXTRACT UNCERTAINTY ===
        # Uncertainty = hyperbolic radius
        z_current = z_temporal
        uncertainty = z_current.norm(dim=-1).mean().item()

        # === 6. DECOMPOSE SENSES ===
        sense_decomposition = self.encoder.decompose_senses(o_sensory)

        result = {
            # Predictions
            "predicted_manifold_state": predicted_state,
            "latent_state": motor_input,
            "predicted_z": z_temporal,
            "predicted_o": o_sensory,
            # Motor commands
            "discrete_actions": motor_commands["discrete_actions"],
            "continuous_actions": motor_commands["continuous_actions"],
            "digital_tools": motor_commands["digital_tools"],
            "speech_params": motor_commands["speech_params"],
            # Uncertainty
            "action_uncertainty": motor_commands["action_uncertainty"],
            "prediction_uncertainty": uncertainty,
            # Sense decomposition
            "sense_strengths": sense_decomposition,
            # Integration proxy
            "integration_score": brain_info.get("integration_score", 0.0),
            # Brain info
            "num_layers": brain_info.get("num_layers", len(self.matryoshka_dims)),
            "dimensions": brain_info.get("dimensions", self.matryoshka_dims),
        }

        # Add physics signals from video encoder if available
        if hasattr(self, "_last_physics_signals"):
            result["physics_signals"] = self._last_physics_signals

        return result

    # ---------------- Memory helpers ----------------
    def remember_state(self, state_32d: torch.Tensor) -> None:
        """Push the latest [B, 32] state vector into the temporal memory."""
        if not isinstance(state_32d, torch.Tensor):
            return  # type: ignore  # Defensive/fallback code
        with torch.no_grad():
            s = state_32d.detach().to(self.device)
            # Keep only the first batch element for memory (lightweight)
            if s.dim() == 2:  # [B, 32]
                s0 = s[:1, :]
            else:
                s0 = s.view(1, -1)
            self._state_memory.append(s0)
            if len(self._state_memory) > self.memory_len:
                self._state_memory = self._state_memory[-self.memory_len :]

    def reset_memory(self) -> None:
        self._state_memory.clear()
        # Reset RSSM state in brain
        if hasattr(self.brain, "reset_rssm_state"):
            self.brain.reset_rssm_state()

        self._rssm_h = None
        self._rssm_z = None

    def predict_with_action(
        self,
        current_senses: dict[str, torch.Tensor | None],
        action: torch.Tensor,
    ) -> dict[str, Any]:
        """Action-conditioned prediction via KagamiWorldModel RSSM.

        UNIFIED (Nov 30, 2025): Delegates to self.brain(..., action=action).

        Args:
            current_senses: Dict with vision_emb, audio_emb, etc.
            action: [B, action_dim] action to condition on

        Returns:
            Prediction dict[str, Any] with RSSM dynamics info
        """
        # Get current observation in manifold space
        z_temporal, o_sensory = self.encode_senses(**current_senses)
        manifold_state = torch.cat([z_temporal, o_sensory], dim=-1)  # [B, 22]

        # Project to state space
        lang_emb = current_senses.get("language_emb")
        if self.use_text_adapter and lang_emb is not None:
            state_32d = self.language_to_state(lang_emb.to(self.device))
        else:
            state_32d = self.manifold_to_state(manifold_state)

        # Expand to sequence
        state_seq = self.seq_expander.repeat(state_32d.shape[0], 1, 1).clone()
        state_seq[:, 0:1, :] = state_32d.unsqueeze(1)

        # === DELEGATED FORWARD PASS ===
        # Pass action to brain to trigger RSSM dynamics
        brain_output, brain_metrics = self.brain(state_seq, action=action)
        predicted_state = self.output_adapter(brain_output)  # [B, S, base_dim] (typically 512)

        # Extract predicted core state from metrics
        core_state = brain_metrics.get("core_state")
        if core_state is None:
            # Fallback if core_state missing (shouldn't happen)
            return self.predict(**current_senses)

        # Decode motor commands from the brain output, bridging to decoder dim if needed.
        # (Decoder expects final Matryoshka dim, typically 14.)
        motor_input = brain_output
        if motor_input.dim() == 2:
            motor_input = motor_input.unsqueeze(1)  # [B, 1, D]
        if motor_input.shape[-1] != self.matryoshka_dims[-1]:
            motor_input = self.state_to_decoder(motor_input)
        motor_commands = self.decoder(motor_input)

        # Predicted hyperbolic state (H14): derived from motor_input
        z_pred = motor_input.mean(dim=1) if motor_input.dim() == 3 else motor_input

        o_res = core_state.s7_phase
        if o_res.dim() == 3:
            o_pred = o_res.mean(dim=1)  # [B, 7]
        else:
            o_pred = o_res  # [B, 7]

        # Ensure o_pred matches decoder expectation (may need 8D padding or 7D)
        # encoder.decompose_senses expects 8D octonion (usually).
        # CoreState s7_phase is 7D intrinsic.
        if o_pred.shape[-1] == 7:
            # Pad to 8D (0 real, 7 imag) - similar to G2 embedding
            o_pred_8d = torch.cat([torch.zeros_like(o_pred[..., :1]), o_pred], dim=-1)
        else:
            o_pred_8d = o_pred

        # Decompose predicted senses
        sense_decomposition = self.encoder.decompose_senses(o_pred_8d)

        # Extract RSSM info from metrics
        rssm_kl = brain_metrics.get("rssm_kl_divergence", torch.tensor(0.0))
        rssm_reward = brain_metrics.get("rssm_reward_loss", torch.tensor(0.0))  # Proxy
        rssm_continue = brain_metrics.get("rssm_continue_loss", torch.tensor(0.0))  # Proxy

        return {
            # Standard outputs
            "predicted_manifold_state": predicted_state,
            "predicted_z": z_pred,
            "predicted_o": o_pred_8d,
            "discrete_actions": motor_commands["discrete_actions"],
            "continuous_actions": motor_commands["continuous_actions"],
            "digital_tools": motor_commands["digital_tools"],
            "speech_params": motor_commands["speech_params"],
            "action_uncertainty": motor_commands["action_uncertainty"],
            "prediction_uncertainty": z_pred.norm(dim=-1).mean().item(),
            "sense_strengths": sense_decomposition,
            "num_layers": len(self.matryoshka_dims),
            "dimensions": self.matryoshka_dims,
            # RSSM-specific outputs (from brain metrics)
            "rssm_kl_divergence": rssm_kl,
            "rssm_predicted_reward": rssm_reward,
            "rssm_continue_prob": rssm_continue,
            "rssm_z_norm": brain_metrics.get("rssm_z_norm", torch.tensor(0.0)),
        }

    def plan_action(
        self,
        current_senses: dict[str, torch.Tensor | None],
        goal_state: torch.Tensor | None = None,
        horizon: int = 5,
    ) -> dict[str, Any]:
        """Plan multi-step actions to reach goal.

        Uses world model to simulate future and plan optimal trajectory.

        Args:
            current_senses: Dict with vision_emb, audio_emb, etc.
            goal_state: [B, 22] target manifold state (optional)
            horizon: Number of steps to plan ahead

        Returns:
            action_sequence: Planned actions over horizon
            predicted_trajectory: Predicted states
            total_uncertainty: Cumulative uncertainty
        """
        # Start from current state
        current_prediction = self.predict(**current_senses)

        trajectory = [current_prediction]
        action_sequence = []
        cumulative_uncertainty = 0.0

        for _step in range(horizon):
            # Get action from current prediction
            action = self.decoder.decode_discrete_action(
                current_prediction["discrete_actions"],
                DISCRETE_ACTIONS,
            )
            action_sequence.append(action)

            # Simulate taking action (re-encode predicted state)
            # In real loop, this would be actual execution + re-perception

            # For now, use predicted state as next input
            next_state = current_prediction["predicted_manifold_state"]

            # Recursive prediction
            # (This is approximate - real version would re-encode senses)
            current_prediction = self.predict(
                meta_emb=next_state.mean(dim=1)  # Use predicted state
            )

            trajectory.append(current_prediction)
            cumulative_uncertainty += current_prediction["prediction_uncertainty"]

        return {
            "action_sequence": action_sequence,
            "predicted_trajectory": trajectory,
            "total_uncertainty": cumulative_uncertainty,
            "horizon": horizon,
        }

    def summarize_plan(self, action_steps: list[dict[str, Any]]) -> dict[str, Any]:
        """Summarize a virtual action plan without requiring sensor data.

        Args:
            action_steps: Plan steps produced by the instruction translator.

        Returns:
            Dict with heuristic integration metrics for downstream use.
        """
        if not action_steps:
            return {
                "integration_score": 0.0,
                "predicted_effort": 0.0,
                "plan_complexity": 0.0,
                "unique_motions": 0,
            }

        total_steps = len(action_steps)
        unique_motions = {
            (step.get("motion") or "").lower()
            for step in action_steps
            if isinstance(step.get("motion"), str)
        }
        inputs_per_step: list[float] = []
        total_inputs = 0
        total_duration = 0.0

        for step in action_steps:
            inputs = step.get("inputs") or []
            if not isinstance(inputs, list):
                continue
            total_inputs += len(inputs)
            step_duration = 0.0
            for raw in inputs:
                if not isinstance(raw, dict):
                    continue
                duration = raw.get("duration_ms")
                if isinstance(duration, int | float):
                    step_duration += float(duration) / 1000.0
            total_duration += step_duration
            inputs_per_step.append(step_duration)

        avg_step_duration = total_duration / max(1, total_steps)
        plan_complexity = min(1.0, total_inputs / 10.0 + total_steps * 0.05)
        predicted_effort = min(1.0, avg_step_duration / 2.0 + len(unique_motions) * 0.1)
        integration_score = min(
            1.0, 0.4 * plan_complexity + 0.4 * predicted_effort + 0.2 * (total_steps / 5.0)
        )

        return {
            "integration_score": integration_score,
            "predicted_effort": predicted_effort,
            "plan_complexity": plan_complexity,
            "unique_motions": len(unique_motions),
            "avg_step_duration": avg_step_duration,
            "total_inputs": total_inputs,
        }


def create_sensorimotor_world_model(
    dimensions: list[int] | None = None,
    device: str | None = None,
    compile_model: bool = True,
) -> SensorimotorWorldModel:
    """Factory function for complete sensorimotor world model.

    Returns:
        SensorimotorWorldModel instance

    Example:
        >>> model = create_sensorimotor_world_model()
        >>>
        >>> # Simulate sensory inputs
        >>> vision = torch.randn(1, 512)  # vision embedding (e.g., DINOv2/Florence-derived)
        >>> language = torch.randn(1, 384)  # LLM embedding
        >>>
        >>> # Predict next state and actions
        >>> prediction = model.predict(vision_emb=vision, language_emb=language)
        >>>
        >>> print(f"Integration score: {prediction['integration_score']:.4f}")
        >>> print(f"Uncertainty: {prediction['prediction_uncertainty']:.4f}")
        >>> print(f"Suggested action: {prediction['discrete_actions'].argmax()}")
    """
    # Exceptional hierarchy dimensions from centralized config (Bulk -> Nucleus)
    if dimensions is None:
        from kagami_math.dimensions import get_layer_dimensions

        dimensions = list(get_layer_dimensions())
    return SensorimotorWorldModel(
        matryoshka_dims=dimensions,
        enable_integration_metrics=True,  # Always enabled
        device=device,
        compile_model=compile_model,
    )
