"""Unified SOTA Vision Module — December 2025.

Integrates state-of-the-art vision models:
1. Florence-2 — Unified vision foundation (detection + segmentation + grounding)
2. SAM2 — Real-time video segmentation with streaming memory
3. DINOv2 — Self-supervised visual features
4. Jina-VLM — Compact 2.4B multilingual VLM

This module REPLACES the legacy CLIP/DETR stack with SOTA models.

References:
- Florence-2: arxiv.org/abs/2311.06242
- SAM2: segment-anything.com
- DINOv2: arxiv.org/abs/2304.07193
- Jina-VLM: arxiv.org/abs/2512.04032
"""

from __future__ import annotations

import asyncio
import logging
import threading
from dataclasses import dataclass, field
from enum import Enum
from typing import Any

import numpy as np
import torch
from PIL import Image

logger = logging.getLogger(__name__)


# ============================================================================
# Device Detection
# ============================================================================


def get_optimal_device() -> str:
    """Get optimal compute device (single source of truth).

    NOTE: Do not re-implement device selection logic here. Delegate to
    `kagami.core.utils.device`, which is the canonical MPS-first policy.
    """
    from kagami.core.utils.device import get_device_str

    return get_device_str()


# ============================================================================
# Data Classes
# ============================================================================


class TaskType(Enum):
    """Florence-2 supported task types."""

    CAPTION = "<CAPTION>"
    DETAILED_CAPTION = "<DETAILED_CAPTION>"
    MORE_DETAILED_CAPTION = "<MORE_DETAILED_CAPTION>"
    OBJECT_DETECTION = "<OD>"
    DENSE_REGION_CAPTION = "<DENSE_REGION_CAPTION>"
    REGION_PROPOSAL = "<REGION_PROPOSAL>"
    CAPTION_TO_PHRASE_GROUNDING = "<CAPTION_TO_PHRASE_GROUNDING>"
    REFERRING_EXPRESSION_SEGMENTATION = "<REFERRING_EXPRESSION_SEGMENTATION>"
    REGION_TO_SEGMENTATION = "<REGION_TO_SEGMENTATION>"
    OPEN_VOCABULARY_DETECTION = "<OPEN_VOCABULARY_DETECTION>"
    REGION_TO_CATEGORY = "<REGION_TO_CATEGORY>"
    REGION_TO_DESCRIPTION = "<REGION_TO_DESCRIPTION>"
    OCR = "<OCR>"
    OCR_WITH_REGION = "<OCR_WITH_REGION>"


@dataclass
class DetectedObject:
    """Object detection result."""

    id: int
    label: str
    confidence: float
    bbox: list[float]  # [x1, y1, x2, y2] normalized
    mask: np.ndarray[Any, Any] | None = None
    area: float = 0.0


@dataclass
class SceneRelation:
    """Spatial relation between objects."""

    subject_id: int
    object_id: int
    predicate: str
    confidence: float


@dataclass
class SceneGraphResult:
    """Complete scene understanding result."""

    objects: list[DetectedObject]
    relations: list[SceneRelation]
    caption: str
    detailed_caption: str
    ocr_text: str
    processing_time_ms: float
    confidence: float
    metadata: dict[str, Any] = field(default_factory=dict[str, Any])


@dataclass
class VideoSegmentResult:
    """SAM2 video segmentation result."""

    frame_id: int
    masks: list[np.ndarray[Any, Any]]
    object_ids: list[int]
    scores: list[float]
    memory_state: dict[str, Any] = field(default_factory=dict[str, Any])


# ============================================================================
# Florence-2: Unified Vision Foundation Model
# ============================================================================


class Florence2Encoder:
    """Florence-2 unified vision encoder.

    Replaces DETR with a single model that handles:
    - Object detection
    - Image captioning
    - Visual grounding
    - OCR
    - Segmentation

    Model sizes:
    - florence-2-base: 0.23B params
    - florence-2-large: 0.77B params
    """

    # Shared, per-(model_name, device) bundle cache.
    _shared_lock_guard = threading.Lock()
    _shared_locks: dict[tuple[str, str], threading.Lock] = {}
    _shared_bundles: dict[tuple[str, str], tuple[Any, Any]] = {}

    @classmethod
    def _get_lock(cls, key: tuple[str, str]) -> threading.Lock:
        with cls._shared_lock_guard:
            lock = cls._shared_locks.get(key)
            if lock is None:
                lock = threading.Lock()
                cls._shared_locks[key] = lock
            return lock

    def __init__(
        self,
        model_name: str = "microsoft/Florence-2-large",
        device: str | None = None,
    ):
        self.device = device or get_optimal_device()
        self.model_name = model_name
        self.model: Any = None
        self.processor: Any = None
        self._initialized = False
        self._use_native = False

    async def initialize(self) -> None:
        """Load Florence-2 model.

        Note: Florence-2 uses Microsoft's custom code via trust_remote_code.
        We use use_cache=False during generation to avoid cache compatibility issues.
        """
        if self._initialized:
            return

        key = (self.model_name, self.device)
        lock = self._get_lock(key)
        await asyncio.to_thread(lock.acquire)
        try:
            # Re-check after acquiring lock.
            if self._initialized:
                return

            cached = self._shared_bundles.get(key)
            if cached is not None:
                self.processor, self.model = cached
                self._use_native = False
                self._initialized = True
                logger.info(f"✅ Florence-2 reused from cache on {self.device}")
                return

            try:
                from transformers import AutoModelForCausalLM, AutoProcessor

                logger.info(f"Loading Florence-2: {self.model_name}")

                self.processor = AutoProcessor.from_pretrained(
                    self.model_name,
                    trust_remote_code=True,
                )
                # Use float32 for stability across devices (esp. MPS).
                self.model = AutoModelForCausalLM.from_pretrained(
                    self.model_name,
                    trust_remote_code=True,
                    torch_dtype=torch.float32,
                    attn_implementation="eager",
                ).to(self.device)  # type: ignore
                self.model.eval()
                self._use_native = False

                # Publish bundle to shared cache.
                assert self.processor is not None and self.model is not None
                self._shared_bundles[key] = (self.processor, self.model)

                self._initialized = True
                logger.info(f"✅ Florence-2 loaded on {self.device}")

            except Exception as e:
                logger.error(f"Failed to load Florence-2: {e}")
                raise
        finally:
            lock.release()

    def _ensure_initialized(self) -> None:
        """Sync initialization check."""
        if not self._initialized:
            try:
                asyncio.get_running_loop()
            except RuntimeError:
                # No running loop; safe to create our own.
                loop = asyncio.new_event_loop()
                try:
                    loop.run_until_complete(self.initialize())
                finally:
                    loop.close()
            else:
                # Running loop exists; avoid nested loops.
                raise RuntimeError(
                    "_ensure_initialized cannot be called from async context - use await initialize() instead"
                )

    def _run_task(
        self,
        image: Image.Image,
        task: TaskType,
        text_input: str = "",
    ) -> dict[str, Any]:
        """Run Florence-2 task."""
        self._ensure_initialized()

        if self.processor is None or self.model is None:
            raise RuntimeError("Florence-2 not initialized")

        prompt = task.value
        if text_input:
            prompt = f"{task.value}{text_input}"

        inputs = self.processor(
            text=prompt,
            images=image,
            return_tensors="pt",
        )

        # Properly handle dtype for each tensor type
        # Use float32 on MPS to avoid dtype issues
        dtype = (
            torch.float32
            if self.device == "mps"
            else (torch.float16 if self.device != "cpu" else torch.float32)
        )
        for k, v in inputs.items():
            if isinstance(v, torch.Tensor):
                if v.dtype in (torch.float32, torch.float64):
                    inputs[k] = v.to(self.device, dtype=dtype)
                else:
                    inputs[k] = v.to(self.device)

        with torch.no_grad():
            generated_ids = self.model.generate(
                input_ids=inputs["input_ids"],
                pixel_values=inputs["pixel_values"],
                max_new_tokens=1024,
                num_beams=1,
                use_cache=False,  # Disable cache - remote code incompatible with new transformers cache
            )

        generated_text = self.processor.batch_decode(generated_ids, skip_special_tokens=False)[0]

        parsed = self.processor.post_process_generation(
            generated_text,
            task=task.value,
            image_size=(image.width, image.height),
        )

        return parsed

    def detect_objects(self, image: Image.Image) -> list[DetectedObject]:
        """Detect objects in image."""
        result = self._run_task(image, TaskType.OBJECT_DETECTION)

        objects = []
        if TaskType.OBJECT_DETECTION.value in result:
            data = result[TaskType.OBJECT_DETECTION.value]
            bboxes = data.get("bboxes", [])
            labels = data.get("labels", [])

            for i, (bbox, label) in enumerate(zip(bboxes, labels, strict=False)):
                objects.append(
                    DetectedObject(
                        id=i,
                        label=label,
                        confidence=0.9,  # Florence-2 doesn't output confidence
                        bbox=bbox,
                    )
                )

        return objects

    def caption(self, image: Image.Image, detailed: bool = False) -> str:
        """Generate image caption."""
        task = TaskType.DETAILED_CAPTION if detailed else TaskType.CAPTION
        result = self._run_task(image, task)
        return result.get(task.value, "")

    def ground_phrase(
        self,
        image: Image.Image,
        phrase: str,
    ) -> list[DetectedObject]:
        """Ground a phrase to bounding boxes."""
        result = self._run_task(
            image,
            TaskType.CAPTION_TO_PHRASE_GROUNDING,
            text_input=phrase,
        )

        objects = []
        key = TaskType.CAPTION_TO_PHRASE_GROUNDING.value
        if key in result:
            data = result[key]
            bboxes = data.get("bboxes", [])
            labels = data.get("labels", [])

            for i, (bbox, label) in enumerate(zip(bboxes, labels, strict=False)):
                objects.append(
                    DetectedObject(
                        id=i,
                        label=label,
                        confidence=0.9,
                        bbox=bbox,
                    )
                )

        return objects

    def ocr(self, image: Image.Image, with_regions: bool = False) -> str | dict[str, Any]:
        """Extract text from image."""
        task = TaskType.OCR_WITH_REGION if with_regions else TaskType.OCR
        result = self._run_task(image, task)
        return result.get(task.value, "" if not with_regions else {})

    def open_vocabulary_detect(
        self,
        image: Image.Image,
        classes: list[str],
    ) -> list[DetectedObject]:
        """Open vocabulary object detection."""
        text_input = ", ".join(classes)
        result = self._run_task(
            image,
            TaskType.OPEN_VOCABULARY_DETECTION,
            text_input=text_input,
        )

        objects = []
        key = TaskType.OPEN_VOCABULARY_DETECTION.value
        if key in result:
            data = result[key]
            bboxes = data.get("bboxes", [])
            labels = data.get("bboxes_labels", [])

            for i, (bbox, label) in enumerate(zip(bboxes, labels, strict=False)):
                objects.append(
                    DetectedObject(
                        id=i,
                        label=label,
                        confidence=0.85,
                        bbox=bbox,
                    )
                )

        return objects


# ============================================================================
# SAM2: Segment Anything Model 2 for Video
# ============================================================================


class SAM2Segmenter:
    """SAM2 video segmentation with streaming memory.

    Key features:
    - Real-time promptable video segmentation
    - Streaming memory mechanism
    - Supports point/box/mask prompts

    Model sizes:
    - sam2-hiera-tiny: Fastest
    - sam2-hiera-small: Balanced
    - sam2-hiera-base-plus: Better quality
    - sam2-hiera-large: Best quality
    """

    # Shared, per-(model_name, device) bundle cache (model + processor).
    # NOTE: segmentation memory state remains per instance.
    _shared_lock_guard = threading.Lock()
    _shared_locks: dict[tuple[str, str], threading.Lock] = {}
    _shared_bundles: dict[tuple[str, str], tuple[Any, Any]] = {}

    @classmethod
    def _get_lock(cls, key: tuple[str, str]) -> threading.Lock:
        with cls._shared_lock_guard:
            lock = cls._shared_locks.get(key)
            if lock is None:
                lock = threading.Lock()
                cls._shared_locks[key] = lock
            return lock

    def __init__(
        self,
        model_name: str = "facebook/sam2-hiera-large",
        device: str | None = None,
    ):
        self.device = device or get_optimal_device()
        self.model_name = model_name
        self.model: Any = None
        self.processor: Any = None
        self._initialized = False
        self._memory_bank: dict[int, Any] = {}

    async def initialize(self) -> None:
        """Load SAM2 model."""
        if self._initialized:
            return

        key = (self.model_name, self.device)
        lock = self._get_lock(key)
        await asyncio.to_thread(lock.acquire)
        try:
            if self._initialized:
                return

            cached = self._shared_bundles.get(key)
            if cached is not None:
                self.processor, self.model = cached
                self._initialized = True
                logger.info(f"✅ SAM2 reused from cache on {self.device}")
                return

            try:
                from transformers import Sam2Model, Sam2Processor

                logger.info(f"Loading SAM2: {self.model_name}")

                self.processor = Sam2Processor.from_pretrained(self.model_name)
                self.model = Sam2Model.from_pretrained(self.model_name).to(self.device)
                self.model.eval()

                assert self.processor is not None and self.model is not None
                self._shared_bundles[key] = (self.processor, self.model)

                self._initialized = True
                logger.info(f"✅ SAM2 loaded on {self.device}")

            except ImportError as e:
                # Fail fast: no silent fallbacks; callers must install the right deps.
                raise ImportError(
                    "SAM2 requires a transformers version that provides Sam2Model/Sam2Processor. "
                    "Install/upgrade: transformers>=4.40"
                ) from e
            except Exception as e:
                logger.error(f"Failed to load SAM2: {e}")
                raise
        finally:
            lock.release()

    def segment_with_points(
        self,
        image: Image.Image,
        points: list[tuple[int, int]],
        labels: list[int] | None = None,
    ) -> list[np.ndarray[Any, Any]]:
        """Segment using point prompts.

        Args:
            image: Input image
            points: List of (x, y) coordinates
            labels: 1 for foreground, 0 for background
        """
        if not self._initialized or self.processor is None or self.model is None:
            raise RuntimeError("SAM2Segmenter not initialized. Call await initialize() first.")

        if labels is None:
            labels = [1] * len(points)

        # SAM2 expects 4-level nesting: [image, object, point, coords]
        # Format: [[[[x1, y1], [x2, y2], ...]]] for one image, one object
        formatted_points = [[[list(p) for p in points]]]
        formatted_labels = [[labels]]

        inputs = self.processor(
            image,
            input_points=formatted_points,
            input_labels=formatted_labels,
            return_tensors="pt",
        )
        # Move tensors to device
        device_inputs = {
            k: v.to(self.device) if isinstance(v, torch.Tensor) else v for k, v in inputs.items()
        }

        with torch.no_grad():
            outputs = self.model(**device_inputs)

        # Manual post-processing to avoid processor.post_process_masks bug
        # pred_masks shape: [batch, num_objects, num_multimask_outputs, H, W]
        pred_masks = outputs.pred_masks.cpu()
        orig_size = inputs["original_sizes"][0].tolist()

        result_masks = []
        for obj_idx in range(pred_masks.shape[1]):
            # Take best mask (index 0) for each object
            mask = pred_masks[0, obj_idx, 0]  # [H, W]

            # Resize to original size
            resized = torch.nn.functional.interpolate(
                mask.unsqueeze(0).unsqueeze(0).float(),
                size=tuple(orig_size),
                mode="bilinear",
                align_corners=False,
            ).squeeze()

            # Threshold to binary
            binary_mask = (resized > 0.0).numpy()
            result_masks.append(binary_mask)

        return result_masks

    def segment_with_box(
        self,
        image: Image.Image,
        box: list[float],
    ) -> list[np.ndarray[Any, Any]]:
        """Segment using bounding box prompt."""
        if not self._initialized or self.processor is None or self.model is None:
            raise RuntimeError("SAM2Segmenter not initialized. Call await initialize() first.")

        # SAM2 expects boxes with 4-level nesting: [image, object, box]
        formatted_boxes = [[[box]]]

        inputs = self.processor(
            image,
            input_boxes=formatted_boxes,
            return_tensors="pt",
        )
        device_inputs = {
            k: v.to(self.device) if isinstance(v, torch.Tensor) else v for k, v in inputs.items()
        }

        with torch.no_grad():
            outputs = self.model(**device_inputs)

        # Manual post-processing
        pred_masks = outputs.pred_masks.cpu()
        orig_size = inputs["original_sizes"][0].tolist()

        result_masks = []
        for obj_idx in range(pred_masks.shape[1]):
            mask = pred_masks[0, obj_idx, 0]
            resized = torch.nn.functional.interpolate(
                mask.unsqueeze(0).unsqueeze(0).float(),
                size=tuple(orig_size),
                mode="bilinear",
                align_corners=False,
            ).squeeze()
            binary_mask = (resized > 0.0).numpy()
            result_masks.append(binary_mask)

        return result_masks

    def segment_video_frame(
        self,
        frame: Image.Image,
        frame_id: int,
        prompts: dict[str, Any] | None = None,
    ) -> VideoSegmentResult:
        """Segment video frame with memory propagation."""
        if not self._initialized:
            raise RuntimeError("SAM2Segmenter not initialized. Call await initialize() first.")

        # Use prompts if provided, else propagate from memory
        if prompts:
            if "points" in prompts:
                masks = self.segment_with_points(
                    frame,
                    prompts["points"],
                    prompts.get("labels"),
                )
            elif "box" in prompts:
                masks = self.segment_with_box(frame, prompts["box"])
            else:
                masks = []
        else:
            # Propagate from memory (simplified)
            masks = []

        # Update memory bank
        self._memory_bank[frame_id] = {
            "masks": masks,
            "features": None,  # Would store encoder features
        }

        return VideoSegmentResult(
            frame_id=frame_id,
            masks=masks,
            object_ids=list(range(len(masks))),
            scores=[0.9] * len(masks),
            memory_state={"frame_count": len(self._memory_bank)},
        )

    def reset_memory(self) -> None:
        """Clear video memory bank."""
        self._memory_bank.clear()


# ============================================================================
# DINOv2: Self-Supervised Visual Features (Enhanced)
# ============================================================================


class DINOv2Encoder:
    """Enhanced DINOv2 encoder with register tokens.

    Model variants:
    - dinov2_vits14: 22M params, 384D
    - dinov2_vitb14: 86M params, 768D
    - dinov2_vitl14: 300M params, 1024D
    - dinov2_vitg14: 1.1B params, 1536D

    With registers (dinov2_vits14_reg, etc.) for better feature quality.
    """

    # Shared, per-(model_name, device) model cache.
    _shared_lock_guard = threading.Lock()
    _shared_locks: dict[tuple[str, str], threading.Lock] = {}
    _shared_models: dict[tuple[str, str], Any] = {}

    @classmethod
    def _get_lock(cls, key: tuple[str, str]) -> threading.Lock:
        with cls._shared_lock_guard:
            lock = cls._shared_locks.get(key)
            if lock is None:
                lock = threading.Lock()
                cls._shared_locks[key] = lock
            return lock

    def __init__(
        self,
        model_name: str = "dinov2_vitb14_reg",
        device: str | None = None,
    ):
        self.device = device or get_optimal_device()
        self.model_name = model_name
        self.model: Any = None
        self._initialized = False

        # Embedding dimensions
        self._dim_map = {
            "dinov2_vits14": 384,
            "dinov2_vits14_reg": 384,
            "dinov2_vitb14": 768,
            "dinov2_vitb14_reg": 768,
            "dinov2_vitl14": 1024,
            "dinov2_vitl14_reg": 1024,
            "dinov2_vitg14": 1536,
            "dinov2_vitg14_reg": 1536,
        }
        self.embedding_dim = self._dim_map.get(model_name, 768)

    async def initialize(self) -> None:
        """Load DINOv2 model."""
        if self._initialized:
            return

        key = (self.model_name, self.device)
        lock = self._get_lock(key)
        await asyncio.to_thread(lock.acquire)
        try:
            if self._initialized:
                return

            cached = self._shared_models.get(key)
            if cached is not None:
                self.model = cached
                self._initialized = True
                logger.info(
                    f"✅ DINOv2 reused from cache on {self.device}, dim={self.embedding_dim}"
                )
                return

            try:
                logger.info(f"Loading DINOv2: {self.model_name}")

                self.model = torch.hub.load(
                    "facebookresearch/dinov2",
                    self.model_name,
                ).to(self.device)
                self.model.eval()

                assert self.model is not None
                self._shared_models[key] = self.model

                self._initialized = True
                logger.info(f"✅ DINOv2 loaded on {self.device}, dim={self.embedding_dim}")

            except Exception as e:
                logger.error(f"Failed to load DINOv2: {e}")
                raise
        finally:
            lock.release()

    def _ensure_initialized(self) -> None:
        """Ensure the encoder is initialized in sync contexts.

        If you are already in an async context, prefer:
            await encoder.initialize()
        """
        if self._initialized:
            return

        import asyncio

        try:
            asyncio.get_running_loop()
        except RuntimeError:
            # No running loop; safe to create our own.
            loop = asyncio.new_event_loop()
            try:
                loop.run_until_complete(self.initialize())
            finally:
                loop.close()
        else:
            # Running loop exists; avoid nested loops.
            raise RuntimeError(
                "DINOv2Encoder.encode() called before initialization in an async context. "
                "Use: await DINOv2Encoder.initialize()"
            )

        if not self._initialized or self.model is None:
            raise RuntimeError("DINOv2Encoder failed to initialize")

    def _preprocess(self, image: Image.Image | list[Image.Image] | torch.Tensor) -> torch.Tensor:
        """Preprocess image(s) for DINOv2.

        Supports:
        - Single PIL Image
        - List of PIL Images
        - Tensor [C, H, W] or [B, C, H, W]
        """
        import torchvision.transforms as T

        transform = T.Compose(
            [
                T.Resize(256),
                T.CenterCrop(224),
                T.ToTensor(),
                T.Normalize(mean=[0.485, 0.456, 0.406], std=[0.229, 0.224, 0.225]),
            ]
        )

        if isinstance(image, list):
            # Batch of PIL images
            tensors = [transform(img) for img in image]
            return torch.stack(tensors).to(self.device)

        elif isinstance(image, torch.Tensor):
            # Already a tensor - use type: ignore for tensor operations
            tensor = image
            if tensor.ndim == 3:
                tensor = tensor.unsqueeze(0)

            # If not normalized/resized, this might be raw pixels.
            # Assuming callers passing tensors handle their own preprocessing
            # OR we implement a tensor-based transform pipeline.
            # For now, assume tensor is ready or close to ready.
            # Ideally we should use T.Resize on tensors too.

            # Use functional transforms for tensors if needed
            if tensor.shape[-1] > 224 or tensor.shape[-2] > 224:
                tensor = T.functional.resize(tensor, 256)
                tensor = T.functional.center_crop(tensor, 224)

            # Normalize if not already (heuristic: max value > 1 means uint8 or unnormalized)
            if tensor.max() > 5.0:
                tensor = tensor.float() / 255.0
                tensor = T.functional.normalize(
                    tensor, mean=[0.485, 0.456, 0.406], std=[0.229, 0.224, 0.225]
                )

            return tensor.to(self.device)

        # Single PIL image
        return transform(image).unsqueeze(0).to(self.device)

    def encode(self, image: Image.Image | list[Image.Image] | torch.Tensor) -> torch.Tensor:
        """Encode image(s) to embedding.

        Args:
            image: Single PIL Image, List of PIL Images, or Tensor.

        Returns:
            Embeddings tensor [D] or [B, D]
        """
        self._ensure_initialized()
        assert self.model is not None

        tensor = self._preprocess(image)

        with torch.no_grad():
            features = self.model(tensor)

        # Squeeze only if input was single image
        if isinstance(image, Image.Image) or (isinstance(image, torch.Tensor) and image.ndim == 3):
            return features.squeeze(0)

        return features

    def encode_patches(
        self,
        image: Image.Image,
    ) -> tuple[torch.Tensor, torch.Tensor]:
        """Encode with patch-level features.

        Returns:
            (cls_token, patch_tokens)
        """
        self._ensure_initialized()
        assert self.model is not None

        tensor = self._preprocess(image)

        with torch.no_grad():
            features = self.model.forward_features(tensor)
            cls_token = features["x_norm_clstoken"].squeeze(0)
            patch_tokens = features["x_norm_patchtokens"].squeeze(0)

        return cls_token, patch_tokens

    def compute_similarity(
        self,
        image1: Image.Image,
        image2: Image.Image,
    ) -> float:
        """Compute visual similarity between images."""
        emb1 = self.encode(image1)
        emb2 = self.encode(image2)

        similarity = torch.cosine_similarity(
            emb1.unsqueeze(0),
            emb2.unsqueeze(0),
            dim=1,
        ).item()

        return float(similarity)


# ============================================================================
# Jina-VLM: Compact Multilingual Vision-Language Model
# ============================================================================


class JinaVLM:
    """Jina-VLM 2.4B compact multilingual VLM.

    Features:
    - 2.4B parameters
    - SigLIP2 vision encoder + Qwen3 language backbone
    - Excellent multilingual VQA performance
    - Efficient multi-resolution processing
    """

    # Shared, per-(model_name, device) bundle cache (model + processor).
    _shared_lock_guard = threading.Lock()
    _shared_locks: dict[tuple[str, str], threading.Lock] = {}
    _shared_bundles: dict[tuple[str, str], tuple[Any, Any]] = {}

    @classmethod
    def _get_lock(cls, key: tuple[str, str]) -> threading.Lock:
        with cls._shared_lock_guard:
            lock = cls._shared_locks.get(key)
            if lock is None:
                lock = threading.Lock()
                cls._shared_locks[key] = lock
            return lock

    def __init__(
        self,
        model_name: str = "jinaai/Jina-VLM-v1",
        device: str | None = None,
    ):
        self.device = device or get_optimal_device()
        self.model_name = model_name
        self.model: Any = None
        self.processor: Any = None
        self._initialized = False

    async def initialize(self) -> None:
        """Load Jina-VLM model."""
        if self._initialized:
            return

        key = (self.model_name, self.device)
        lock = self._get_lock(key)
        await asyncio.to_thread(lock.acquire)
        try:
            if self._initialized:
                return

            cached = self._shared_bundles.get(key)
            if cached is not None:
                self.processor, self.model = cached
                self._initialized = True
                logger.info(f"✅ Jina-VLM reused from cache on {self.device}")
                return

            try:
                from transformers import AutoModelForVision2Seq, AutoProcessor

                logger.info(f"Loading Jina-VLM: {self.model_name}")

                self.processor = AutoProcessor.from_pretrained(
                    self.model_name,
                    trust_remote_code=True,
                )

                # DType policy: float32 on CPU/MPS for stability; float16 on CUDA for memory.
                torch_dtype = torch.float32 if self.device in {"cpu", "mps"} else torch.float16

                self.model = AutoModelForVision2Seq.from_pretrained(
                    self.model_name,
                    trust_remote_code=True,
                    torch_dtype=torch_dtype,
                ).to(self.device)
                self.model.eval()

                assert self.processor is not None and self.model is not None
                self._shared_bundles[key] = (self.processor, self.model)

                self._initialized = True
                logger.info(f"✅ Jina-VLM loaded on {self.device}")

            except Exception as e:
                logger.error(f"Failed to load Jina-VLM: {e}")
                raise
        finally:
            lock.release()

    def answer(
        self,
        image: Image.Image,
        question: str,
        max_tokens: int = 512,
    ) -> str:
        """Answer a question about the image."""
        if not self._initialized or self.processor is None or self.model is None:
            raise RuntimeError("JinaVLM not initialized. Call await initialize() first.")

        inputs = self.processor(
            images=image,
            text=question,
            return_tensors="pt",
        )

        dtype = torch.float32 if self.device in {"cpu", "mps"} else torch.float16
        for k, v in inputs.items():
            if isinstance(v, torch.Tensor):
                if v.dtype in (torch.float32, torch.float64):
                    inputs[k] = v.to(self.device, dtype=dtype)
                else:
                    inputs[k] = v.to(self.device)

        with torch.no_grad():
            generated_ids = self.model.generate(
                **inputs,
                max_new_tokens=max_tokens,
            )

        answer = self.processor.batch_decode(
            generated_ids,
            skip_special_tokens=True,
        )[0]

        return answer

    def describe(self, image: Image.Image) -> str:
        """Generate detailed image description."""
        return self.answer(image, "Describe this image in detail.")

    def analyze_ui(self, screenshot: Image.Image) -> dict[str, Any]:
        """Analyze UI screenshot."""
        description = self.answer(
            screenshot,
            "What UI elements are visible in this screenshot? List them.",
        )

        issues = self.answer(
            screenshot,
            "Are there any visual issues or bugs in this UI? Be specific.",
        )

        return {
            "elements": description,
            "issues": issues,
            "has_issues": "no issues" not in issues.lower() and "looks fine" not in issues.lower(),
        }


# ============================================================================
# Unified Scene Graph Generator (Florence-2 based)
# ============================================================================


class UnifiedSceneGraphGenerator:
    """SOTA scene graph generator using Florence-2.

    Replaces legacy DETR-based SceneGraphGenerator with:
    - Florence-2 for detection + captioning + grounding
    - Geometric heuristics for relation inference
    - OCR integration
    """

    def __init__(self, device: str | None = None):
        self.device = device or get_optimal_device()
        self.florence = Florence2Encoder(device=self.device)
        self._initialized = False

        # Spatial predicates for relation inference
        self.predicates = [
            "above",
            "below",
            "left_of",
            "right_of",
            "near",
            "inside",
            "overlaps",
            "beside",
            "on",
            "in_front_of",
        ]

    async def initialize(self) -> None:
        """Initialize the generator."""
        if self._initialized:
            return
        await self.florence.initialize()
        self._initialized = True
        logger.info("✅ UnifiedSceneGraphGenerator initialized")

    async def generate(self, image: Image.Image) -> SceneGraphResult:
        """Generate complete scene graph from image."""
        import time

        start = time.time()

        if not self._initialized:
            await self.initialize()

        # 1. Detect objects
        objects = self.florence.detect_objects(image)

        # 2. Generate captions
        caption = self.florence.caption(image, detailed=False)
        detailed_caption = self.florence.caption(image, detailed=True)

        # 3. Extract text (OCR)
        ocr_text = self.florence.ocr(image)
        if isinstance(ocr_text, dict):
            ocr_text = ocr_text.get("text", "")

        # 4. Infer spatial relations
        relations = self._infer_relations(objects)

        # 5. Calculate confidence
        confidence = self._calculate_confidence(objects, relations)

        processing_time = (time.time() - start) * 1000

        return SceneGraphResult(
            objects=objects,
            relations=relations,
            caption=caption,
            detailed_caption=detailed_caption,
            ocr_text=ocr_text,
            processing_time_ms=processing_time,
            confidence=confidence,
            metadata={
                "model": "florence-2-large",
                "device": self.device,
                "image_size": (image.width, image.height),
            },
        )

    def _infer_relations(
        self,
        objects: list[DetectedObject],
    ) -> list[SceneRelation]:
        """Infer spatial relations from bounding boxes."""
        relations = []

        def center(bbox: list[float]) -> tuple[float, float]:
            return ((bbox[0] + bbox[2]) / 2, (bbox[1] + bbox[3]) / 2)

        def iou(a: list[float], b: list[float]) -> float:
            x1 = max(a[0], b[0])
            y1 = max(a[1], b[1])
            x2 = min(a[2], b[2])
            y2 = min(a[3], b[3])
            inter = max(0, x2 - x1) * max(0, y2 - y1)
            area_a = (a[2] - a[0]) * (a[3] - a[1])
            area_b = (b[2] - b[0]) * (b[3] - b[1])
            denom = area_a + area_b - inter
            return inter / denom if denom > 0 else 0

        for i, obj_i in enumerate(objects):
            ci = center(obj_i.bbox)
            for j, obj_j in enumerate(objects):
                if i == j:
                    continue

                cj = center(obj_j.bbox)
                iou_val = iou(obj_i.bbox, obj_j.bbox)

                dx = cj[0] - ci[0]
                dy = cj[1] - ci[1]

                predicate = None
                conf = min(obj_i.confidence, obj_j.confidence)

                # Determine relation
                if iou_val > 0.5:
                    predicate = "overlaps"
                elif iou_val > 0.1:
                    predicate = "near"
                elif abs(dx) < 0.1 and dy < -0.1:
                    predicate = "above"
                elif abs(dx) < 0.1 and dy > 0.1:
                    predicate = "below"
                elif dx < -0.1:
                    predicate = "left_of"
                elif dx > 0.1:
                    predicate = "right_of"
                elif abs(dx) < 0.15 and abs(dy) < 0.15:
                    predicate = "beside"

                if predicate:
                    relations.append(
                        SceneRelation(
                            subject_id=obj_i.id,
                            object_id=obj_j.id,
                            predicate=predicate,
                            confidence=conf,
                        )
                    )

        return relations

    def _calculate_confidence(
        self,
        objects: list[DetectedObject],
        relations: list[SceneRelation],
    ) -> float:
        """Calculate overall scene graph confidence."""
        if not objects:
            return 0.0

        obj_conf = sum(o.confidence for o in objects) / len(objects)

        if relations:
            rel_conf = sum(r.confidence for r in relations) / len(relations)
            return (obj_conf + rel_conf) / 2

        return obj_conf


# ============================================================================
# Unified Vision Module (combines all encoders)
# ============================================================================


class UnifiedVisionModule:
    """Unified vision module combining all SOTA encoders.

    Provides single interface to:
    - Florence-2 (detection, captioning, grounding)
    - SAM2 (segmentation)
    - DINOv2 (visual features)
    - Jina-VLM (VQA)
    """

    def __init__(self, device: str | None = None):
        self.device = device or get_optimal_device()

        # Initialize encoders lazily
        self._florence: Florence2Encoder | None = None
        self._sam2: SAM2Segmenter | None = None
        self._dino: DINOv2Encoder | None = None
        self._jina: JinaVLM | None = None
        self._scene_graph: UnifiedSceneGraphGenerator | None = None

    @property
    def florence(self) -> Florence2Encoder:
        if self._florence is None:
            self._florence = Florence2Encoder(device=self.device)
        return self._florence

    @property
    def sam2(self) -> SAM2Segmenter:
        if self._sam2 is None:
            self._sam2 = SAM2Segmenter(device=self.device)
        return self._sam2

    @property
    def dino(self) -> DINOv2Encoder:
        if self._dino is None:
            self._dino = DINOv2Encoder(device=self.device)
        return self._dino

    @property
    def jina(self) -> JinaVLM:
        if self._jina is None:
            self._jina = JinaVLM(device=self.device)
        return self._jina

    @property
    def scene_graph(self) -> UnifiedSceneGraphGenerator:
        if self._scene_graph is None:
            self._scene_graph = UnifiedSceneGraphGenerator(device=self.device)
        return self._scene_graph

    async def initialize_all(self) -> None:
        """Initialize all encoders."""
        import asyncio

        await asyncio.gather(
            self.florence.initialize(),
            self.sam2.initialize(),
            self.dino.initialize(),
            self.jina.initialize(),
            self.scene_graph.initialize(),
        )
        logger.info("✅ All vision encoders initialized")

    # Convenience methods
    async def detect(self, image: Image.Image) -> list[DetectedObject]:
        """Detect objects in image."""
        await self.florence.initialize()
        return self.florence.detect_objects(image)

    async def caption(self, image: Image.Image, detailed: bool = False) -> str:
        """Generate image caption."""
        await self.florence.initialize()
        return self.florence.caption(image, detailed)

    async def segment(
        self,
        image: Image.Image,
        points: list[tuple[int, int]] | None = None,
        box: list[float] | None = None,
    ) -> list[np.ndarray[Any, Any]]:
        """Segment image with prompts."""
        await self.sam2.initialize()
        if points:
            return self.sam2.segment_with_points(image, points)
        elif box:
            return self.sam2.segment_with_box(image, box)
        return []

    async def encode(self, image: Image.Image) -> torch.Tensor:
        """Encode image to features."""
        await self.dino.initialize()
        return self.dino.encode(image)

    async def answer(self, image: Image.Image, question: str) -> str:
        """Answer question about image."""
        await self.jina.initialize()
        return self.jina.answer(image, question)

    async def analyze(self, image: Image.Image) -> SceneGraphResult:
        """Complete scene analysis."""
        return await self.scene_graph.generate(image)


# ============================================================================
# Module exports
# ============================================================================

__all__ = [
    "DINOv2Encoder",
    "DetectedObject",
    # Core encoders
    "Florence2Encoder",
    "JinaVLM",
    "SAM2Segmenter",
    "SceneGraphResult",
    "SceneRelation",
    # Utilities
    "TaskType",
    # Scene graph
    "UnifiedSceneGraphGenerator",
    # Unified interface
    "UnifiedVisionModule",
    # Video
    "VideoSegmentResult",
    "get_optimal_device",
    "get_unified_vision_module",
]


# ============================================================================
# Global convenience: shared UnifiedVisionModule per device
# ============================================================================

_vision_modules: dict[str, UnifiedVisionModule] = {}
_vision_modules_lock = threading.Lock()


def get_unified_vision_module(device: str | None = None) -> UnifiedVisionModule:
    """Return a shared UnifiedVisionModule for the given device.

    This avoids repeated wrapper/encoder construction in hot call sites
    (e.g., orchestrator handlers). Heavy model weights are still loaded lazily
    via encoder `initialize()` methods.
    """
    dev = device or get_optimal_device()
    with _vision_modules_lock:
        mod = _vision_modules.get(dev)
        if mod is None:
            mod = UnifiedVisionModule(device=dev)
            _vision_modules[dev] = mod
        return mod
