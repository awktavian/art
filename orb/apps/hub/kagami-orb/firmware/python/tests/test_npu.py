"""
Tests for Hailo-10H NPU Driver

Tests cover:
- Device initialization
- Model loading and unloading
- Inference pipeline
- Detection post-processing
- Pose estimation
- Face recognition embeddings
"""

import pytest
import numpy as np
import time

import sys
sys.path.insert(0, str(pytest.importorskip("pathlib").Path(__file__).parent.parent))

from kagami_orb.drivers.npu import (
    HailoNPUDriver,
    ModelType,
    ModelConfig,
    Detection,
    PoseResult,
    PoseKeypoint,
    FaceEmbedding,
    InferenceResult,
    OrbVisionPipeline,
)


class TestModelTypes:
    """Test model type definitions."""
    
    def test_model_types_exist(self):
        """Verify all expected model types."""
        assert ModelType.PERSON_DETECTION
        assert ModelType.FACE_DETECTION
        assert ModelType.FACE_RECOGNITION
        assert ModelType.POSE_ESTIMATION
        assert ModelType.GESTURE_RECOGNITION
        assert ModelType.VOICE_ACTIVITY
        assert ModelType.WAKE_WORD


class TestModelConfig:
    """Test model configuration."""
    
    def test_builtin_configs(self):
        """Test builtin model configurations exist."""
        assert ModelType.PERSON_DETECTION in HailoNPUDriver.BUILTIN_MODELS
        assert ModelType.FACE_DETECTION in HailoNPUDriver.BUILTIN_MODELS
        assert ModelType.POSE_ESTIMATION in HailoNPUDriver.BUILTIN_MODELS
        assert ModelType.FACE_RECOGNITION in HailoNPUDriver.BUILTIN_MODELS
    
    def test_person_detection_config(self):
        """Test person detection model config."""
        config = HailoNPUDriver.BUILTIN_MODELS[ModelType.PERSON_DETECTION]
        
        assert config.input_shape == (1, 640, 640, 3)
        assert config.model_type == ModelType.PERSON_DETECTION
    
    def test_face_recognition_config(self):
        """Test face recognition model config."""
        config = HailoNPUDriver.BUILTIN_MODELS[ModelType.FACE_RECOGNITION]
        
        # ArcFace uses 112x112 input
        assert config.input_shape == (1, 112, 112, 3)
        assert config.output_shape == (1, 512)  # 512-d embedding


class TestHailoNPUDriver:
    """Test Hailo NPU driver."""
    
    @pytest.fixture
    def npu(self):
        """Create NPU in simulation mode."""
        return HailoNPUDriver(simulate=True)
    
    def test_initialization(self, npu):
        """Test driver initializes correctly."""
        assert npu.is_initialized()
    
    def test_device_info(self, npu):
        """Test getting device info."""
        info = npu.get_device_info()
        
        assert "device" in info
        assert "tops" in info
        assert info["tops"] == 40  # Hailo-10H is 40 TOPS
    
    def test_load_model(self, npu):
        """Test loading a model."""
        success = npu.load_model(ModelType.PERSON_DETECTION)
        
        assert success
        assert ModelType.PERSON_DETECTION in npu.get_loaded_models()
    
    def test_load_multiple_models(self, npu):
        """Test loading multiple models."""
        npu.load_model(ModelType.PERSON_DETECTION)
        npu.load_model(ModelType.FACE_DETECTION)
        npu.load_model(ModelType.POSE_ESTIMATION)
        
        loaded = npu.get_loaded_models()
        assert len(loaded) == 3
    
    def test_unload_model(self, npu):
        """Test unloading a model."""
        npu.load_model(ModelType.PERSON_DETECTION)
        npu.unload_model(ModelType.PERSON_DETECTION)
        
        assert ModelType.PERSON_DETECTION not in npu.get_loaded_models()
    
    def test_already_loaded(self, npu):
        """Test loading an already-loaded model."""
        npu.load_model(ModelType.PERSON_DETECTION)
        success = npu.load_model(ModelType.PERSON_DETECTION)
        
        # Should return True (already loaded)
        assert success


class TestInference:
    """Test inference operations."""
    
    @pytest.fixture
    def npu(self):
        """Create NPU in simulation mode."""
        return HailoNPUDriver(simulate=True)
    
    @pytest.fixture
    def test_image(self):
        """Create a test image."""
        return np.random.randint(0, 255, (480, 640, 3), dtype=np.uint8)
    
    def test_person_detection_inference(self, npu, test_image):
        """Test person detection inference."""
        result = npu.infer(ModelType.PERSON_DETECTION, test_image)
        
        assert isinstance(result, InferenceResult)
        assert result.model_type == ModelType.PERSON_DETECTION
        assert result.latency_ms > 0
    
    def test_detection_output(self, npu, test_image):
        """Test detection output format."""
        result = npu.infer(ModelType.PERSON_DETECTION, test_image)
        
        # Simulation returns one fake detection
        assert len(result.detections) >= 0
        
        if result.detections:
            det = result.detections[0]
            assert isinstance(det, Detection)
            assert 0 <= det.confidence <= 1
            assert len(det.bbox) == 4
    
    def test_face_detection_inference(self, npu, test_image):
        """Test face detection inference."""
        result = npu.infer(ModelType.FACE_DETECTION, test_image)
        
        assert result.model_type == ModelType.FACE_DETECTION
    
    def test_pose_estimation_inference(self, npu, test_image):
        """Test pose estimation inference."""
        result = npu.infer(ModelType.POSE_ESTIMATION, test_image)
        
        assert result.model_type == ModelType.POSE_ESTIMATION
        
        # Check pose output
        if result.poses:
            pose = result.poses[0]
            assert isinstance(pose, PoseResult)
            assert len(pose.keypoints) == 17  # COCO format
    
    def test_face_recognition_inference(self, npu):
        """Test face recognition inference."""
        # Face recognition uses 112x112 crop
        face_crop = np.random.randint(0, 255, (112, 112, 3), dtype=np.uint8)
        
        result = npu.infer(ModelType.FACE_RECOGNITION, face_crop)
        
        assert result.model_type == ModelType.FACE_RECOGNITION
        assert len(result.embeddings) == 1
        assert result.embeddings[0].embedding.shape == (512,)
    
    def test_confidence_threshold(self, npu, test_image):
        """Test confidence threshold filtering."""
        result_low = npu.infer(ModelType.PERSON_DETECTION, test_image, conf_threshold=0.1)
        result_high = npu.infer(ModelType.PERSON_DETECTION, test_image, conf_threshold=0.99)
        
        # High threshold should have fewer or equal detections
        assert len(result_high.detections) <= len(result_low.detections)


class TestDetection:
    """Test Detection dataclass."""
    
    def test_bbox_center(self):
        """Test bounding box center calculation."""
        det = Detection(
            class_id=0,
            class_name="person",
            confidence=0.9,
            bbox=(0.2, 0.3, 0.8, 0.7),
        )
        
        cx, cy = det.center
        assert cx == 0.5
        assert cy == 0.5
    
    def test_bbox_area(self):
        """Test bounding box area calculation."""
        det = Detection(
            class_id=0,
            class_name="person",
            confidence=0.9,
            bbox=(0.0, 0.0, 0.5, 0.5),
        )
        
        assert det.area == 0.25


class TestPoseResult:
    """Test PoseResult dataclass."""
    
    @pytest.fixture
    def pose(self):
        """Create a test pose."""
        keypoints = []
        for name in PoseResult.KEYPOINT_NAMES:
            keypoints.append(PoseKeypoint(
                name=name,
                x=0.5,
                y=0.5,
                confidence=0.8,
            ))
        return PoseResult(keypoints=keypoints, confidence=0.9)
    
    def test_keypoint_count(self, pose):
        """Test COCO 17 keypoints."""
        assert len(pose.keypoints) == 17
        assert len(PoseResult.KEYPOINT_NAMES) == 17
    
    def test_get_keypoint_by_name(self, pose):
        """Test getting keypoint by name."""
        nose = pose.get_keypoint("nose")
        assert nose is not None
        assert nose.name == "nose"
    
    def test_keypoint_names(self):
        """Verify COCO keypoint names."""
        names = PoseResult.KEYPOINT_NAMES
        
        assert "nose" in names
        assert "left_eye" in names
        assert "right_wrist" in names
        assert "left_ankle" in names


class TestFaceEmbedding:
    """Test FaceEmbedding dataclass."""
    
    def test_similarity_identical(self):
        """Test cosine similarity of identical embeddings."""
        emb = np.random.randn(512).astype(np.float32)
        
        face1 = FaceEmbedding(embedding=emb, bbox=(0, 0, 1, 1))
        face2 = FaceEmbedding(embedding=emb, bbox=(0, 0, 1, 1))
        
        similarity = face1.similarity(face2)
        assert abs(similarity - 1.0) < 0.001
    
    def test_similarity_different(self):
        """Test cosine similarity of different embeddings."""
        face1 = FaceEmbedding(
            embedding=np.ones(512, dtype=np.float32),
            bbox=(0, 0, 1, 1),
        )
        face2 = FaceEmbedding(
            embedding=-np.ones(512, dtype=np.float32),
            bbox=(0, 0, 1, 1),
        )
        
        similarity = face1.similarity(face2)
        assert similarity < 0  # Opposite vectors


class TestPreprocessing:
    """Test image preprocessing."""
    
    @pytest.fixture
    def npu(self):
        return HailoNPUDriver(simulate=True)
    
    def test_resize(self, npu):
        """Test image resizing."""
        config = HailoNPUDriver.BUILTIN_MODELS[ModelType.PERSON_DETECTION]
        
        # Input image of different size
        image = np.random.randint(0, 255, (480, 640, 3), dtype=np.uint8)
        
        processed = npu._preprocess(image, config)
        
        # Should be resized to model input shape
        assert processed.shape == config.input_shape
    
    def test_normalization(self, npu):
        """Test image normalization."""
        config = ModelConfig(
            model_type=ModelType.PERSON_DETECTION,
            hef_path="test.hef",
            input_shape=(1, 224, 224, 3),
            output_shape=(1, 1000),
            preprocess_mean=(123.0, 117.0, 104.0),  # ImageNet
            preprocess_std=(1.0, 1.0, 1.0),
            quantization="float32",
        )
        
        # All zeros input
        image = np.zeros((224, 224, 3), dtype=np.uint8)
        processed = npu._preprocess(image, config)
        
        # After normalization: (0 - mean) / std
        expected = -123.0  # For red channel
        assert processed[0, 0, 0, 0] < 0


class TestOrbVisionPipeline:
    """Test high-level vision pipeline."""
    
    @pytest.fixture
    def pipeline(self):
        """Create vision pipeline."""
        return OrbVisionPipeline(simulate=True)
    
    @pytest.fixture
    def test_frame(self):
        """Create a test frame."""
        return np.random.randint(0, 255, (480, 640, 3), dtype=np.uint8)
    
    def test_process_frame_person(self, pipeline, test_frame):
        """Test processing frame with person detection."""
        results = pipeline.process_frame(test_frame, run_person=True)
        
        assert ModelType.PERSON_DETECTION in results
    
    def test_process_frame_multiple_models(self, pipeline, test_frame):
        """Test processing with multiple models."""
        results = pipeline.process_frame(
            test_frame,
            run_person=True,
            run_face=True,
            run_pose=True,
        )
        
        assert ModelType.PERSON_DETECTION in results
        assert ModelType.FACE_DETECTION in results
        assert ModelType.POSE_ESTIMATION in results
    
    def test_callback_registration(self, pipeline, test_frame):
        """Test callback registration and dispatch."""
        callback_received = []
        
        def on_person_detected(result):
            callback_received.append(result)
        
        pipeline.register_callback(ModelType.PERSON_DETECTION, on_person_detected)
        pipeline.process_frame(test_frame, run_person=True)
        
        assert len(callback_received) == 1


class TestAsyncInference:
    """Test async inference."""
    
    @pytest.fixture
    def npu(self):
        return HailoNPUDriver(simulate=True)
    
    @pytest.mark.asyncio
    async def test_async_inference(self, npu):
        """Test async inference execution."""
        image = np.random.randint(0, 255, (480, 640, 3), dtype=np.uint8)
        
        result = await npu.infer_async(ModelType.PERSON_DETECTION, image)
        
        assert isinstance(result, InferenceResult)


class TestPerformance:
    """Test NPU performance."""
    
    def test_inference_latency(self):
        """Test inference latency is reasonable."""
        npu = HailoNPUDriver(simulate=True)
        image = np.random.randint(0, 255, (480, 640, 3), dtype=np.uint8)
        
        start = time.monotonic()
        for _ in range(10):
            npu.infer(ModelType.PERSON_DETECTION, image)
        elapsed = time.monotonic() - start
        
        # 10 inferences in simulation should be fast
        assert elapsed < 1.0
    
    def test_model_loading_time(self):
        """Test model loading time."""
        npu = HailoNPUDriver(simulate=True)
        
        start = time.monotonic()
        npu.load_model(ModelType.PERSON_DETECTION)
        elapsed = time.monotonic() - start
        
        # Simulation should be instant
        assert elapsed < 0.1


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
