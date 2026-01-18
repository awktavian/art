"""
Hailo-10H NPU Driver for Kagami Orb

Provides high-level interface to the Hailo-10H AI accelerator
for running neural network inference on camera/sensor data.

Reference:
- HailoRT SDK: https://hailo.ai/developer-zone/
- Hailo Model Zoo: https://github.com/hailo-ai/hailo_model_zoo
"""

import asyncio
import time
import logging
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Tuple, Union
import numpy as np
from concurrent.futures import ThreadPoolExecutor

try:
    import pyhailort as hailort
    HAS_HAILORT = True
except ImportError:
    HAS_HAILORT = False

logger = logging.getLogger(__name__)


# =============================================================================
# NPU TYPES AND CONFIGURATIONS
# =============================================================================

class ModelType(Enum):
    """Supported model types for the orb."""
    PERSON_DETECTION = "person_detection"
    FACE_DETECTION = "face_detection"
    FACE_RECOGNITION = "face_recognition"
    POSE_ESTIMATION = "pose_estimation"
    GESTURE_RECOGNITION = "gesture_recognition"
    VOICE_ACTIVITY = "voice_activity"
    WAKE_WORD = "wake_word"
    EMOTION_RECOGNITION = "emotion_recognition"
    GAZE_ESTIMATION = "gaze_estimation"
    DEPTH_ESTIMATION = "depth_estimation"


@dataclass
class ModelConfig:
    """Configuration for a neural network model."""
    model_type: ModelType
    hef_path: Path
    input_shape: Tuple[int, ...]          # NHWC format
    output_shape: Tuple[int, ...]
    input_format: str = "NHWC"            # NHWC or NCHW
    quantization: str = "uint8"           # uint8, int8, float32
    batch_size: int = 1
    preprocess_mean: Tuple[float, ...] = (0.0, 0.0, 0.0)
    preprocess_std: Tuple[float, ...] = (1.0, 1.0, 1.0)


@dataclass
class Detection:
    """Object detection result."""
    class_id: int
    class_name: str
    confidence: float
    bbox: Tuple[float, float, float, float]  # x1, y1, x2, y2 (normalized 0-1)
    
    @property
    def center(self) -> Tuple[float, float]:
        """Get bounding box center."""
        return (
            (self.bbox[0] + self.bbox[2]) / 2,
            (self.bbox[1] + self.bbox[3]) / 2,
        )
    
    @property
    def area(self) -> float:
        """Get bounding box area (normalized)."""
        return (self.bbox[2] - self.bbox[0]) * (self.bbox[3] - self.bbox[1])


@dataclass
class PoseKeypoint:
    """Single pose keypoint."""
    name: str
    x: float          # 0-1 normalized
    y: float          # 0-1 normalized
    confidence: float


@dataclass
class PoseResult:
    """Pose estimation result."""
    keypoints: List[PoseKeypoint]
    confidence: float
    
    KEYPOINT_NAMES = [
        "nose", "left_eye", "right_eye", "left_ear", "right_ear",
        "left_shoulder", "right_shoulder", "left_elbow", "right_elbow",
        "left_wrist", "right_wrist", "left_hip", "right_hip",
        "left_knee", "right_knee", "left_ankle", "right_ankle"
    ]
    
    def get_keypoint(self, name: str) -> Optional[PoseKeypoint]:
        """Get keypoint by name."""
        for kp in self.keypoints:
            if kp.name == name:
                return kp
        return None


@dataclass
class FaceEmbedding:
    """Face recognition embedding."""
    embedding: np.ndarray  # 512-d typically
    bbox: Tuple[float, float, float, float]
    landmarks: Optional[List[Tuple[float, float]]] = None
    
    def similarity(self, other: "FaceEmbedding") -> float:
        """Compute cosine similarity with another embedding."""
        return np.dot(self.embedding, other.embedding) / (
            np.linalg.norm(self.embedding) * np.linalg.norm(other.embedding)
        )


@dataclass
class InferenceResult:
    """Generic inference result container."""
    model_type: ModelType
    latency_ms: float
    timestamp_ms: float
    detections: List[Detection] = field(default_factory=list)
    poses: List[PoseResult] = field(default_factory=list)
    embeddings: List[FaceEmbedding] = field(default_factory=list)
    raw_output: Optional[np.ndarray] = None


# =============================================================================
# HAILO NPU DRIVER
# =============================================================================

class HailoNPUDriver:
    """
    Driver for Hailo-10H Neural Processing Unit.
    
    Features:
    - 40 TOPS AI performance
    - Multiple model support
    - Async inference pipeline
    - Hardware-accelerated preprocessing
    """
    
    # Default model paths (relative to firmware root)
    DEFAULT_MODELS_DIR = Path(__file__).parent.parent / "models"
    
    # Standard model configurations
    BUILTIN_MODELS = {
        ModelType.PERSON_DETECTION: ModelConfig(
            model_type=ModelType.PERSON_DETECTION,
            hef_path=Path("yolov8n_person.hef"),
            input_shape=(1, 640, 640, 3),
            output_shape=(1, 8400, 6),  # boxes + confidence + class
            preprocess_mean=(0.0, 0.0, 0.0),
            preprocess_std=(255.0, 255.0, 255.0),
        ),
        ModelType.FACE_DETECTION: ModelConfig(
            model_type=ModelType.FACE_DETECTION,
            hef_path=Path("retinaface_mobilenet.hef"),
            input_shape=(1, 640, 640, 3),
            output_shape=(1, 16800, 16),
        ),
        ModelType.POSE_ESTIMATION: ModelConfig(
            model_type=ModelType.POSE_ESTIMATION,
            hef_path=Path("yolov8n_pose.hef"),
            input_shape=(1, 640, 640, 3),
            output_shape=(1, 8400, 56),  # 17 keypoints * 3 + bbox + conf
        ),
        ModelType.FACE_RECOGNITION: ModelConfig(
            model_type=ModelType.FACE_RECOGNITION,
            hef_path=Path("arcface_r50.hef"),
            input_shape=(1, 112, 112, 3),
            output_shape=(1, 512),
        ),
    }
    
    def __init__(
        self,
        models_dir: Optional[Path] = None,
        device_id: int = 0,
        simulate: bool = False,
    ):
        """
        Initialize Hailo NPU driver.
        
        Args:
            models_dir: Directory containing .hef model files
            device_id: Hailo device ID (for multi-device systems)
            simulate: Run in simulation mode without hardware
        """
        self.models_dir = models_dir or self.DEFAULT_MODELS_DIR
        self.device_id = device_id
        self.simulate = simulate or not HAS_HAILORT
        
        self._device: Optional[Any] = None
        self._loaded_models: Dict[ModelType, Any] = {}
        self._network_groups: Dict[ModelType, Any] = {}
        self._vstreams: Dict[ModelType, Tuple[Any, Any]] = {}
        self._initialized = False
        
        # Thread pool for async inference
        self._executor = ThreadPoolExecutor(max_workers=2)
        
        self._init_device()
    
    def _init_device(self) -> None:
        """Initialize Hailo device."""
        if self.simulate:
            logger.info("Hailo NPU running in simulation mode")
            self._initialized = True
            return
        
        try:
            # Find and connect to device
            devices = hailort.scan_devices()
            if not devices:
                raise RuntimeError("No Hailo devices found")
            
            if self.device_id >= len(devices):
                raise RuntimeError(f"Device {self.device_id} not found. "
                                   f"Available: {len(devices)} devices")
            
            self._device = hailort.Device(devices[self.device_id])
            
            # Log device info
            info = self._device.identify()
            logger.info(f"Hailo device initialized:")
            logger.info(f"  Board: {info.board_name}")
            logger.info(f"  Serial: {info.serial_number}")
            logger.info(f"  FW Version: {info.fw_version}")
            
            self._initialized = True
            
        except Exception as e:
            logger.error(f"Hailo init failed: {e}")
            logger.info("Falling back to simulation mode")
            self.simulate = True
            self._initialized = True
    
    def is_initialized(self) -> bool:
        """Check if NPU is initialized."""
        return self._initialized
    
    def load_model(self, model_type: ModelType, config: Optional[ModelConfig] = None) -> bool:
        """
        Load a model onto the NPU.
        
        Args:
            model_type: Type of model to load
            config: Optional custom configuration (uses builtin if None)
        
        Returns:
            True if model loaded successfully
        """
        if model_type in self._loaded_models:
            logger.info(f"Model {model_type.value} already loaded")
            return True
        
        config = config or self.BUILTIN_MODELS.get(model_type)
        if not config:
            logger.error(f"No configuration for model type: {model_type}")
            return False
        
        if self.simulate:
            self._loaded_models[model_type] = config
            logger.info(f"Simulated load of {model_type.value}")
            return True
        
        try:
            hef_path = self.models_dir / config.hef_path
            if not hef_path.exists():
                logger.error(f"Model file not found: {hef_path}")
                return False
            
            # Load HEF file
            hef = hailort.Hef(str(hef_path))
            
            # Configure network on device
            network_group = self._device.configure(hef)
            
            # Create virtual streams for input/output
            input_vstreams = network_group.get_input_vstreams()
            output_vstreams = network_group.get_output_vstreams()
            
            self._loaded_models[model_type] = config
            self._network_groups[model_type] = network_group
            self._vstreams[model_type] = (input_vstreams, output_vstreams)
            
            logger.info(f"Loaded model: {model_type.value}")
            logger.info(f"  Input shape: {config.input_shape}")
            logger.info(f"  Output shape: {config.output_shape}")
            
            return True
            
        except Exception as e:
            logger.error(f"Failed to load model {model_type.value}: {e}")
            return False
    
    def unload_model(self, model_type: ModelType) -> None:
        """Unload a model from the NPU."""
        if model_type in self._loaded_models:
            del self._loaded_models[model_type]
        if model_type in self._network_groups:
            del self._network_groups[model_type]
        if model_type in self._vstreams:
            del self._vstreams[model_type]
    
    def _preprocess(
        self,
        image: np.ndarray,
        config: ModelConfig,
    ) -> np.ndarray:
        """
        Preprocess image for inference.
        
        Args:
            image: Input image (HWC, uint8)
            config: Model configuration
        
        Returns:
            Preprocessed tensor ready for NPU
        """
        import cv2
        
        h, w = config.input_shape[1:3]
        
        # Resize
        if image.shape[:2] != (h, w):
            image = cv2.resize(image, (w, h))
        
        # Convert to float and normalize
        image = image.astype(np.float32)
        
        # Apply normalization
        mean = np.array(config.preprocess_mean)
        std = np.array(config.preprocess_std)
        image = (image - mean) / std
        
        # Convert to quantized format if needed
        if config.quantization == "uint8":
            image = np.clip(image * 255, 0, 255).astype(np.uint8)
        elif config.quantization == "int8":
            image = np.clip(image * 127, -128, 127).astype(np.int8)
        
        # Add batch dimension
        image = np.expand_dims(image, axis=0)
        
        return image
    
    def _run_inference_sync(
        self,
        model_type: ModelType,
        input_data: np.ndarray,
    ) -> np.ndarray:
        """Run synchronous inference."""
        if self.simulate:
            return self._simulate_inference(model_type, input_data)
        
        input_vstreams, output_vstreams = self._vstreams[model_type]
        
        # Write input
        for vs in input_vstreams:
            vs.write(input_data)
        
        # Read output
        outputs = []
        for vs in output_vstreams:
            outputs.append(vs.read())
        
        return outputs[0] if len(outputs) == 1 else np.concatenate(outputs)
    
    def _simulate_inference(
        self,
        model_type: ModelType,
        input_data: np.ndarray,
    ) -> np.ndarray:
        """Simulate inference for testing."""
        config = self._loaded_models[model_type]
        
        # Simulate latency
        time.sleep(0.01)  # 10ms
        
        if model_type == ModelType.PERSON_DETECTION:
            # Return fake detection in center
            output = np.zeros((1, 8400, 6), dtype=np.float32)
            output[0, 0, :] = [0.3, 0.3, 0.7, 0.7, 0.95, 0]  # bbox, conf, class
            return output
        
        elif model_type == ModelType.FACE_DETECTION:
            output = np.zeros((1, 16800, 16), dtype=np.float32)
            output[0, 0, :4] = [0.35, 0.25, 0.65, 0.55]  # bbox
            output[0, 0, 4] = 0.92  # confidence
            return output
        
        elif model_type == ModelType.POSE_ESTIMATION:
            output = np.zeros((1, 8400, 56), dtype=np.float32)
            # Fake keypoints
            output[0, 0, :4] = [0.3, 0.2, 0.7, 0.9]  # bbox
            output[0, 0, 4] = 0.88  # confidence
            for i in range(17):
                output[0, 0, 5 + i*3] = 0.5 + (i % 3) * 0.1  # x
                output[0, 0, 6 + i*3] = 0.2 + i * 0.04       # y
                output[0, 0, 7 + i*3] = 0.8                   # conf
            return output
        
        elif model_type == ModelType.FACE_RECOGNITION:
            # Return random embedding
            return np.random.randn(1, 512).astype(np.float32)
        
        return np.zeros(config.output_shape, dtype=np.float32)
    
    def _postprocess_detections(
        self,
        output: np.ndarray,
        model_type: ModelType,
        conf_threshold: float = 0.5,
        nms_threshold: float = 0.45,
    ) -> List[Detection]:
        """
        Post-process detection output.
        
        Args:
            output: Raw model output
            model_type: Model type for class names
            conf_threshold: Confidence threshold
            nms_threshold: NMS IoU threshold
        
        Returns:
            List of Detection objects
        """
        CLASS_NAMES = {
            ModelType.PERSON_DETECTION: ["person"],
            ModelType.FACE_DETECTION: ["face"],
        }
        
        detections = []
        class_names = CLASS_NAMES.get(model_type, ["object"])
        
        # Parse YOLOv8-style output
        output = output[0]  # Remove batch dim
        
        for i in range(output.shape[0]):
            conf = output[i, 4]
            if conf < conf_threshold:
                continue
            
            x1, y1, x2, y2 = output[i, :4]
            class_id = int(output[i, 5]) if output.shape[1] > 5 else 0
            class_name = class_names[class_id] if class_id < len(class_names) else "unknown"
            
            detections.append(Detection(
                class_id=class_id,
                class_name=class_name,
                confidence=float(conf),
                bbox=(float(x1), float(y1), float(x2), float(y2)),
            ))
        
        # TODO: Apply NMS
        return detections
    
    def _postprocess_poses(
        self,
        output: np.ndarray,
        conf_threshold: float = 0.5,
    ) -> List[PoseResult]:
        """Post-process pose estimation output."""
        poses = []
        output = output[0]  # Remove batch dim
        
        for i in range(output.shape[0]):
            conf = output[i, 4]
            if conf < conf_threshold:
                continue
            
            keypoints = []
            for j in range(17):
                base = 5 + j * 3
                kp = PoseKeypoint(
                    name=PoseResult.KEYPOINT_NAMES[j],
                    x=float(output[i, base]),
                    y=float(output[i, base + 1]),
                    confidence=float(output[i, base + 2]),
                )
                keypoints.append(kp)
            
            poses.append(PoseResult(
                keypoints=keypoints,
                confidence=float(conf),
            ))
        
        return poses
    
    def infer(
        self,
        model_type: ModelType,
        image: np.ndarray,
        conf_threshold: float = 0.5,
    ) -> InferenceResult:
        """
        Run inference on an image.
        
        Args:
            model_type: Type of model to use
            image: Input image (HWC, uint8, BGR or RGB)
            conf_threshold: Confidence threshold for detections
        
        Returns:
            InferenceResult with detections/poses/embeddings
        """
        if model_type not in self._loaded_models:
            if not self.load_model(model_type):
                raise RuntimeError(f"Failed to load model: {model_type.value}")
        
        config = self._loaded_models[model_type]
        start_time = time.monotonic()
        
        # Preprocess
        input_tensor = self._preprocess(image, config)
        
        # Run inference
        output = self._run_inference_sync(model_type, input_tensor)
        
        latency_ms = (time.monotonic() - start_time) * 1000
        
        # Post-process based on model type
        result = InferenceResult(
            model_type=model_type,
            latency_ms=latency_ms,
            timestamp_ms=time.monotonic() * 1000,
            raw_output=output,
        )
        
        if model_type in [ModelType.PERSON_DETECTION, ModelType.FACE_DETECTION]:
            result.detections = self._postprocess_detections(
                output, model_type, conf_threshold
            )
        elif model_type == ModelType.POSE_ESTIMATION:
            result.poses = self._postprocess_poses(output, conf_threshold)
        elif model_type == ModelType.FACE_RECOGNITION:
            result.embeddings = [FaceEmbedding(
                embedding=output.flatten(),
                bbox=(0, 0, 1, 1),
            )]
        
        return result
    
    async def infer_async(
        self,
        model_type: ModelType,
        image: np.ndarray,
        conf_threshold: float = 0.5,
    ) -> InferenceResult:
        """Async version of inference."""
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(
            self._executor,
            self.infer,
            model_type,
            image,
            conf_threshold,
        )
    
    def get_loaded_models(self) -> List[ModelType]:
        """Get list of loaded models."""
        return list(self._loaded_models.keys())
    
    def get_device_info(self) -> Dict[str, Any]:
        """Get device information."""
        if self.simulate:
            return {
                "device": "Hailo-10H (simulated)",
                "board": "Simulation",
                "serial": "SIM-0000",
                "fw_version": "0.0.0",
                "tops": 40,
            }
        
        if not self._device:
            return {}
        
        info = self._device.identify()
        return {
            "device": "Hailo-10H",
            "board": info.board_name,
            "serial": info.serial_number,
            "fw_version": info.fw_version,
            "tops": 40,
        }
    
    def close(self) -> None:
        """Clean up resources."""
        self._loaded_models.clear()
        self._network_groups.clear()
        self._vstreams.clear()
        
        if self._device:
            self._device = None
        
        self._executor.shutdown(wait=False)
        self._initialized = False


# =============================================================================
# VISION PIPELINE
# =============================================================================

class OrbVisionPipeline:
    """
    High-level vision pipeline for the Kagami Orb.
    
    Combines camera input with NPU inference for
    real-time person/face/pose detection.
    """
    
    def __init__(
        self,
        npu: Optional[HailoNPUDriver] = None,
        simulate: bool = False,
    ):
        """
        Initialize vision pipeline.
        
        Args:
            npu: NPU driver instance (creates new if None)
            simulate: Run in simulation mode
        """
        self.npu = npu or HailoNPUDriver(simulate=simulate)
        self._callbacks: Dict[ModelType, List[Callable]] = {}
    
    def register_callback(
        self,
        model_type: ModelType,
        callback: Callable[[InferenceResult], None],
    ) -> None:
        """Register a callback for inference results."""
        if model_type not in self._callbacks:
            self._callbacks[model_type] = []
        self._callbacks[model_type].append(callback)
    
    def process_frame(
        self,
        frame: np.ndarray,
        run_person: bool = True,
        run_face: bool = False,
        run_pose: bool = False,
    ) -> Dict[ModelType, InferenceResult]:
        """
        Process a single frame through enabled models.
        
        Args:
            frame: Input frame (HWC, uint8)
            run_person: Run person detection
            run_face: Run face detection
            run_pose: Run pose estimation
        
        Returns:
            Dict mapping model type to inference result
        """
        results = {}
        
        if run_person:
            result = self.npu.infer(ModelType.PERSON_DETECTION, frame)
            results[ModelType.PERSON_DETECTION] = result
            self._dispatch_callbacks(ModelType.PERSON_DETECTION, result)
        
        if run_face:
            result = self.npu.infer(ModelType.FACE_DETECTION, frame)
            results[ModelType.FACE_DETECTION] = result
            self._dispatch_callbacks(ModelType.FACE_DETECTION, result)
        
        if run_pose:
            result = self.npu.infer(ModelType.POSE_ESTIMATION, frame)
            results[ModelType.POSE_ESTIMATION] = result
            self._dispatch_callbacks(ModelType.POSE_ESTIMATION, result)
        
        return results
    
    def _dispatch_callbacks(
        self,
        model_type: ModelType,
        result: InferenceResult,
    ) -> None:
        """Dispatch callbacks for a result."""
        for callback in self._callbacks.get(model_type, []):
            try:
                callback(result)
            except Exception as e:
                logger.error(f"Callback error: {e}")
    
    def close(self) -> None:
        """Clean up resources."""
        self.npu.close()
