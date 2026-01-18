"""Sensorimotor Intent Handler - Stripe Pattern Refactor.

Handles sensorimotor perception-action intents with clean handler registry.
Complexity reduced from CC=76 to CC<10.

Supported actions:
- sensorimotor.perceive / perceive: Encode sensory inputs to manifold
- sensorimotor.predict / predict_action / observe_and_act: Predict next action
- sensorimotor.act / act: Execute motor command via Composio

Created: December 2025 (refactored from IntentOrchestrator._handle_sensorimotor_intent)
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Any

import torch

if TYPE_CHECKING:
    from kagami.core.orchestrator.core import IntentOrchestrator

logger = logging.getLogger(__name__)


# =============================================================================
# SENSORY ENCODING - HELPERS
# =============================================================================


def _load_image(image_data: Any) -> Any:
    """Load image from various formats to PIL Image."""
    import base64
    from io import BytesIO

    from PIL import Image

    if isinstance(image_data, str):
        if image_data.startswith("data:image"):
            b64_data = image_data.split(",")[1]
            return Image.open(BytesIO(base64.b64decode(b64_data)))
        elif image_data.startswith("/") or image_data.startswith("./"):
            return Image.open(image_data)
        else:
            return Image.open(BytesIO(base64.b64decode(image_data)))
    elif hasattr(image_data, "convert"):  # PIL Image
        return image_data
    else:
        raise ValueError(f"Unsupported image format: {type(image_data)}")


def _should_use_sota_vision() -> bool:
    """Check if SOTA vision encoder should be used."""
    import os

    from kagami.core.boot_mode import is_test_mode

    if is_test_mode():
        return False
    if os.getenv("KAGAMI_VISION_USE_SOTA", "1").lower() in ("0", "false", "no"):
        return False
    if "PYTEST_CURRENT_TEST" in os.environ:
        return False
    return True


def _pad_to_512d(feats: torch.Tensor) -> torch.Tensor:
    """Pad or truncate features to 512D."""
    if feats.dim() == 1:
        feats = feats.unsqueeze(0)
    elif feats.dim() != 2:
        raise ValueError(f"Unexpected shape: {tuple(feats.shape)}")

    if feats.shape[-1] > 512:
        return feats[..., :512]
    elif feats.shape[-1] < 512:
        pad = torch.zeros(
            feats.shape[0], 512 - feats.shape[-1], device=feats.device, dtype=feats.dtype
        )
        return torch.cat([feats, pad], dim=-1)
    return feats


async def _encode_vision_sota(img: Any, device: torch.device) -> torch.Tensor:
    """Encode vision with the SOTA unified vision stack (no fallbacks)."""
    from kagami.core.multimodal.vision import get_unified_vision_module

    vision = get_unified_vision_module(device=str(device))
    feats = await vision.encode(img)

    if not isinstance(feats, torch.Tensor):
        raise TypeError(f"Unexpected type: {type(feats)}")

    feats = _pad_to_512d(feats)
    logger.debug(f"Encoded vision (SOTA): {feats.shape}")
    return feats.to(device)


# =============================================================================
# SENSORY ENCODING - PUBLIC API
# =============================================================================


async def _encode_vision(params: dict[str, Any], device: torch.device) -> torch.Tensor | None:
    """Encode vision input to 512D embedding.

    Args:
        params: Intent parameters containing vision/image/screenshot
        device: Target device for tensor

    Returns:
        Vision embedding tensor [1, 512] or None if no vision input
    """
    if not any(k in params for k in ["vision", "image", "screenshot"]):
        return None

    image_data = params.get("vision") or params.get("image") or params.get("screenshot")
    img = _load_image(image_data)

    if not _should_use_sota_vision():
        raise RuntimeError(
            "SOTA vision disabled for sensorimotor handler (enable KAGAMI_VISION_USE_SOTA=1 and avoid test mode)."
        )

    return await _encode_vision_sota(img, device)


async def _encode_text(params: dict[str, Any], device: torch.device) -> torch.Tensor | None:
    """Encode text input to 384D embedding.

    Args:
        params: Intent parameters containing text/instruction/goal
        device: Target device for tensor

    Returns:
        Language embedding tensor [1, 384] or None if no text input
    """
    if not any(k in params for k in ["text", "instruction", "goal"]):
        return None

    text = params.get("text") or params.get("instruction") or params.get("goal")
    if text is None:
        return None
    text_str = str(text)

    try:
        from kagami.core.services.embedding_service import get_embedding_service

        text_encoder = get_embedding_service()
        vec = await text_encoder.embed_text_async(text_str, dimension=384)
        language_emb = torch.from_numpy(vec).unsqueeze(0).to(device)
        logger.debug(f'Encoded text: "{text_str[:50]}..."')
        return language_emb
    except Exception as e:
        raise RuntimeError(f"Text encoding failed: {e}") from e


def _load_video_from_path(video_path: str) -> torch.Tensor:
    """Load video from file path and extract frames."""
    import cv2
    import numpy as np

    cap = cv2.VideoCapture(video_path)
    frames = []
    for _ in range(8):  # Sample 8 frames
        ret, frame = cap.read()
        if not ret:
            break
        frame_rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        frames.append(frame_rgb)
    cap.release()

    if not frames:
        raise ValueError("No frames extracted from video")

    # Convert to tensor [1, T, C, H, W]
    frames_array = np.stack(frames)
    video_frames = torch.from_numpy(frames_array).permute(0, 3, 1, 2).unsqueeze(0).float()
    video_frames = torch.nn.functional.interpolate(
        video_frames.flatten(0, 1), size=(224, 224), mode="bilinear"
    ).view(1, len(frames), 3, 224, 224)
    return video_frames


async def _encode_video(params: dict[str, Any], device: torch.device) -> torch.Tensor | None:
    """Encode video input to tensor [1, T, 3, 224, 224].

    Args:
        params: Intent parameters containing video/frames
        device: Target device for tensor

    Returns:
        Video frames tensor or None if no video input
    """
    if not any(k in params for k in ["video", "frames"]):
        return None

    try:
        video_data = params.get("video") or params.get("frames")

        if isinstance(video_data, str):
            video_frames = _load_video_from_path(video_data)
        elif isinstance(video_data, torch.Tensor):
            video_frames = video_data
        else:
            raise ValueError(f"Unsupported video format: {type(video_data)}")

        video_frames = video_frames.to(device)
        logger.debug(f"Encoded video input: {video_frames.shape}")
        return video_frames

    except Exception as e:
        raise RuntimeError(f"Video encoding failed: {e}") from e


# =============================================================================
# ACTION HANDLERS
# =============================================================================


async def _handle_perceive(
    model: Any,
    vision_emb: torch.Tensor | None,
    language_emb: torch.Tensor | None,
    video_frames: torch.Tensor | None,
) -> dict[str, Any]:
    """Handle sensorimotor.perceive: Encode senses to manifold.

    Args:
        model: Sensorimotor world model
        vision_emb: Vision embedding [1, 512]
        language_emb: Language embedding [1, 384]
        video_frames: Video frames [1, T, 3, H, W]

    Returns:
        Result dict[str, Any] with manifold coordinates and sense strengths
    """
    with torch.no_grad():
        z, o = model.encode_senses(
            vision_emb=vision_emb, language_emb=language_emb, video_frames=video_frames
        )
    senses = model.encoder.decompose_senses(o)

    return {
        "status": "accepted",
        "response": {
            "z_temporal": z[0].tolist(),
            "o_sensory": o[0].tolist(),
            "sense_strengths": {k: float(v[0].item()) for k, v in senses.items()},
            "manifold_dim": 15,
        },
    }


async def _handle_predict(
    model: Any,
    vision_emb: torch.Tensor | None,
    language_emb: torch.Tensor | None,
    video_frames: torch.Tensor | None,
) -> dict[str, Any]:
    """Handle sensorimotor.predict: Predict next action from senses.

    Args:
        model: Sensorimotor world model
        vision_emb: Vision embedding [1, 512]
        language_emb: Language embedding [1, 384]
        video_frames: Video frames [1, T, 3, H, W]

    Returns:
        Result dict[str, Any] with predicted action and confidence
    """
    from kagami.core.embodiment.motor_decoder import DISCRETE_ACTIONS

    with torch.no_grad():
        prediction = model.predict(
            vision_emb=vision_emb, language_emb=language_emb, video_frames=video_frames
        )

    # Decode action
    discrete_action = model.decoder.decode_discrete_action(
        prediction["discrete_actions"], DISCRETE_ACTIONS
    )

    return {
        "status": "accepted",
        "response": {
            "predicted_action": discrete_action["action"],
            "action_confidence": discrete_action["confidence"],
            "uncertainty": float(prediction["prediction_uncertainty"]),
            "sense_strengths": {
                k: float(v[0, 0].item()) for k, v in prediction["sense_strengths"].items()
            },
            "continuous_actions": prediction["continuous_actions"][0].tolist(),
        },
        "sensorimotor": True,
        "num_layers": prediction["num_layers"],
    }


async def _handle_act(params: dict[str, Any]) -> dict[str, Any]:
    """Handle sensorimotor.act: Execute motor command via Composio.

    Args:
        params: Action parameters containing action_name and action_params

    Returns:
        Result dict[str, Any] with execution status
    """
    try:
        from kagami.core.services.composio import get_composio_service

        composio = get_composio_service()
        if not composio.initialized:
            return {
                "status": "error",
                "error": "Composio not initialized (action execution unavailable)",
                "sensorimotor": True,
            }

        # Extract action to execute
        action_name = params.get("action_name") or params.get("tool")
        action_params = params.get("action_params", {})

        if not action_name:
            return {
                "status": "error",
                "error": "No action_name specified for execution",
                "sensorimotor": True,
            }

        # Execute via Composio
        result = await composio.execute_action(action_name, action_params)

        return {
            "status": "accepted",
            "response": result,
            "sensorimotor": True,
            "action_executed": action_name,
        }

    except Exception as e:
        logger.error(f"Sensorimotor action execution failed: {e}")
        return {
            "status": "error",
            "error": f"Action execution failed: {e}",
            "sensorimotor": True,
        }


# =============================================================================
# MAIN HANDLER (CC < 10)
# =============================================================================


async def handle_sensorimotor_intent(
    orchestrator: IntentOrchestrator, intent: dict[str, Any]
) -> dict[str, Any]:
    """Handle sensorimotor perception-action intents.

    Refactored from IntentOrchestrator._handle_sensorimotor_intent (CC=76 → CC<10).

    Args:
        orchestrator: IntentOrchestrator instance
        intent: Intent dict[str, Any] with action and params

    Returns:
        Result dict[str, Any]

    Actions:
        - sensorimotor.perceive / perceive: Encode senses to manifold
        - sensorimotor.predict / predict_action / observe_and_act: Predict action
        - sensorimotor.act / act: Execute motor command
    """
    action = intent.get("action", "")
    params = intent.get("params", {})

    # Ensure model loaded
    if orchestrator._sensorimotor_model is None:
        await orchestrator._load_sensorimotor_model()
    if orchestrator._sensorimotor_model is None:
        return {
            "status": "error",
            "error": "sensorimotor_model_unavailable",
            "sensorimotor": False,
        }

    device = orchestrator._sensorimotor_model.device

    # Encode sensory inputs (no silent fallbacks; fail explicitly).
    try:
        vision_emb = await _encode_vision(params, device)
        language_emb = await _encode_text(params, device)
        video_frames = await _encode_video(params, device)
    except Exception as e:
        logger.warning("Sensorimotor encoding failed: %s", e)
        return {
            "status": "error",
            "error": "sensorimotor_encoding_failed",
            "detail": str(e),
            "sensorimotor": True,
        }

    # Route to action handler
    if action in ["sensorimotor.perceive", "perceive"]:
        return await _handle_perceive(
            orchestrator._sensorimotor_model, vision_emb, language_emb, video_frames
        )

    elif action in ["sensorimotor.predict", "predict_action", "observe_and_act"]:
        return await _handle_predict(
            orchestrator._sensorimotor_model, vision_emb, language_emb, video_frames
        )

    elif action in ["sensorimotor.act", "act"]:
        return await _handle_act(params)

    else:
        return {"status": "error", "error": f"Unknown sensorimotor action: {action}"}
