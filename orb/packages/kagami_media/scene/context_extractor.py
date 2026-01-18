"""Scene Context Extraction.

Analyzes video scenes for environment data including:
- Background extraction
- Lighting analysis
- Environment classification
- Temporal consistency

Usage:
    analyzer = SceneAnalyzer()
    context = analyzer.analyze_video("video.mp4")
"""

import json
from collections import Counter
from dataclasses import dataclass, field
from pathlib import Path

import cv2
import numpy as np


@dataclass
class LightingInfo:
    """Lighting analysis for a scene."""

    # Color temperature (warm=low, cool=high)
    color_temperature_k: float = 5500.0  # Daylight default

    # Overall brightness (0-255)
    brightness: float = 128.0

    # Contrast level
    contrast: float = 0.5

    # Dominant light direction (estimated)
    light_direction: str = "ambient"  # top, left, right, ambient

    # Color cast
    dominant_color: str = "neutral"  # warm, cool, neutral

    def to_dict(self) -> dict:
        return {
            "color_temperature_k": self.color_temperature_k,
            "brightness": self.brightness,
            "contrast": self.contrast,
            "light_direction": self.light_direction,
            "dominant_color": self.dominant_color,
        }


@dataclass
class SceneContext:
    """Complete scene context for a video."""

    source_video: str
    duration_seconds: float

    # Environment classification
    environment_type: str = "unknown"  # indoor, outdoor
    location_type: str = "unknown"  # home, office, park, etc.

    # Lighting
    lighting: LightingInfo = field(default_factory=LightingInfo)

    # Background
    background_stable: bool = False
    background_complexity: str = "medium"  # simple, medium, complex

    # Temporal info
    time_of_day: str = "unknown"  # morning, afternoon, evening, night

    # Representative frame
    representative_frame_number: int = 0

    # Objects detected
    detected_objects: list[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            "source_video": self.source_video,
            "duration_seconds": self.duration_seconds,
            "environment_type": self.environment_type,
            "location_type": self.location_type,
            "lighting": self.lighting.to_dict(),
            "background_stable": self.background_stable,
            "background_complexity": self.background_complexity,
            "time_of_day": self.time_of_day,
            "representative_frame_number": self.representative_frame_number,
            "detected_objects": self.detected_objects,
        }


class SceneAnalyzer:
    """Analyze video scenes for environment context.

    Extracts lighting, background, and classification data.
    """

    def __init__(
        self,
        sample_count: int = 10,  # Number of frames to analyze
    ):
        """Initialize scene analyzer.

        Args:
            sample_count: Number of frames to sample for analysis
        """
        self.sample_count = sample_count

    def analyze_video(
        self,
        video_path: str,
        output_dir: str | None = None,
    ) -> SceneContext:
        """Analyze scene context from video.

        Args:
            video_path: Path to video file
            output_dir: Optional directory to save analysis

        Returns:
            SceneContext with analysis results
        """
        video_path = Path(video_path)
        cap = cv2.VideoCapture(str(video_path))

        if not cap.isOpened():
            raise RuntimeError(f"Could not open video: {video_path}")

        fps = cap.get(cv2.CAP_PROP_FPS) or 30.0
        total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
        duration = total_frames / fps if fps > 0 else 0

        # Sample frames evenly across video
        frame_indices = np.linspace(0, total_frames - 1, self.sample_count, dtype=int)

        sampled_frames = []
        lighting_samples = []
        environment_votes = []

        for idx in frame_indices:
            cap.set(cv2.CAP_PROP_POS_FRAMES, idx)
            ret, frame = cap.read()

            if ret:
                sampled_frames.append(frame)

                # Analyze lighting
                lighting = self._analyze_lighting(frame)
                lighting_samples.append(lighting)

                # Classify environment
                env_type = self._classify_environment(frame)
                environment_votes.append(env_type)

        cap.release()

        # Aggregate results
        context = SceneContext(
            source_video=video_path.name,
            duration_seconds=duration,
        )

        # Average lighting
        if lighting_samples:
            context.lighting = self._aggregate_lighting(lighting_samples)

        # Majority vote for environment
        if environment_votes:
            context.environment_type = Counter(environment_votes).most_common(1)[0][0]

        # Estimate location type
        context.location_type = self._estimate_location(
            context.environment_type,
            context.lighting,
        )

        # Estimate time of day from lighting
        context.time_of_day = self._estimate_time_of_day(context.lighting)

        # Check background stability
        if len(sampled_frames) >= 2:
            context.background_stable = self._check_background_stability(sampled_frames)

        # Estimate background complexity
        if sampled_frames:
            context.background_complexity = self._estimate_complexity(sampled_frames[0])

        # Select representative frame (middle of video)
        context.representative_frame_number = frame_indices[len(frame_indices) // 2]

        # Save if output_dir specified
        if output_dir:
            self._save_analysis(context, output_dir, sampled_frames)

        return context

    def _analyze_lighting(self, frame: np.ndarray) -> LightingInfo:
        """Analyze lighting in a frame."""
        # Convert to different color spaces
        hsv = cv2.cvtColor(frame, cv2.COLOR_BGR2HSV)
        lab = cv2.cvtColor(frame, cv2.COLOR_BGR2LAB)

        # Brightness from V channel
        brightness = float(np.mean(hsv[:, :, 2]))

        # Contrast from standard deviation
        contrast = float(np.std(hsv[:, :, 2]) / 128.0)

        # Color temperature estimation from a/b channels of LAB
        np.mean(lab[:, :, 1]) - 128  # a: green-red
        b_mean = np.mean(lab[:, :, 2]) - 128  # b: blue-yellow

        # Estimate color temperature (very rough)
        # Positive b = warm, negative b = cool
        if b_mean > 10:
            color_temp = 4000.0  # Warm
            dominant_color = "warm"
        elif b_mean < -10:
            color_temp = 7000.0  # Cool
            dominant_color = "cool"
        else:
            color_temp = 5500.0  # Neutral daylight
            dominant_color = "neutral"

        # Light direction estimation (simplified)
        h, w = frame.shape[:2]
        top_brightness = np.mean(hsv[: h // 3, :, 2])
        np.mean(hsv[2 * h // 3 :, :, 2])
        left_brightness = np.mean(hsv[:, : w // 3, 2])
        right_brightness = np.mean(hsv[:, 2 * w // 3 :, 2])

        brightnesses = {
            "top": top_brightness,
            "left": left_brightness,
            "right": right_brightness,
            "ambient": brightness,
        }

        max_region = max(brightnesses, key=brightnesses.get)
        if brightnesses[max_region] > brightness * 1.2:
            light_direction = max_region
        else:
            light_direction = "ambient"

        return LightingInfo(
            color_temperature_k=color_temp,
            brightness=brightness,
            contrast=contrast,
            light_direction=light_direction,
            dominant_color=dominant_color,
        )

    def _aggregate_lighting(self, samples: list[LightingInfo]) -> LightingInfo:
        """Aggregate lighting info from multiple samples."""
        return LightingInfo(
            color_temperature_k=np.mean([s.color_temperature_k for s in samples]),
            brightness=np.mean([s.brightness for s in samples]),
            contrast=np.mean([s.contrast for s in samples]),
            light_direction=Counter([s.light_direction for s in samples]).most_common(1)[0][0],
            dominant_color=Counter([s.dominant_color for s in samples]).most_common(1)[0][0],
        )

    def _classify_environment(self, frame: np.ndarray) -> str:
        """Classify frame as indoor or outdoor."""
        # Simple heuristic based on color distribution
        hsv = cv2.cvtColor(frame, cv2.COLOR_BGR2HSV)

        # Check for sky colors (blue hues in upper portion)
        upper_third = hsv[: frame.shape[0] // 3, :, :]

        # Sky detection: high saturation blues or bright whites
        blue_mask = (
            (upper_third[:, :, 0] > 90) & (upper_third[:, :, 0] < 130) & (upper_third[:, :, 1] > 30)
        )
        blue_ratio = np.sum(blue_mask) / blue_mask.size

        # Green detection (grass, trees)
        green_mask = (hsv[:, :, 0] > 35) & (hsv[:, :, 0] < 85) & (hsv[:, :, 1] > 30)
        green_ratio = np.sum(green_mask) / green_mask.size

        # Outdoor indicators
        if blue_ratio > 0.15 or green_ratio > 0.2:
            return "outdoor"

        return "indoor"

    def _estimate_location(
        self,
        environment: str,
        lighting: LightingInfo,
    ) -> str:
        """Estimate specific location type."""
        if environment == "outdoor":
            if lighting.brightness > 180:
                return "park_daylight"
            else:
                return "outdoor_evening"
        else:
            if lighting.color_temperature_k < 4500:
                return "home"  # Warm lighting typical of homes
            elif lighting.brightness > 150:
                return "office"
            else:
                return "indoor"

    def _estimate_time_of_day(self, lighting: LightingInfo) -> str:
        """Estimate time of day from lighting."""
        if lighting.brightness < 50:
            return "night"
        elif lighting.brightness < 100:
            return "evening"
        elif lighting.color_temperature_k < 5000:
            return "morning"  # Warm morning light
        else:
            return "afternoon"

    def _check_background_stability(self, frames: list[np.ndarray]) -> bool:
        """Check if background is stable across frames."""
        if len(frames) < 2:
            return True

        # Compare first and last frame
        first = cv2.cvtColor(frames[0], cv2.COLOR_BGR2GRAY)
        last = cv2.cvtColor(frames[-1], cv2.COLOR_BGR2GRAY)

        # Resize for faster comparison
        first = cv2.resize(first, (160, 90))
        last = cv2.resize(last, (160, 90))

        # Calculate structural similarity (simplified)
        diff = np.abs(first.astype(float) - last.astype(float))
        similarity = 1.0 - (np.mean(diff) / 255.0)

        return similarity > 0.7

    def _estimate_complexity(self, frame: np.ndarray) -> str:
        """Estimate visual complexity of frame."""
        # Use edge detection as proxy for complexity
        gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
        edges = cv2.Canny(gray, 50, 150)

        edge_ratio = np.sum(edges > 0) / edges.size

        if edge_ratio < 0.05:
            return "simple"
        elif edge_ratio < 0.15:
            return "medium"
        else:
            return "complex"

    def _save_analysis(
        self,
        context: SceneContext,
        output_dir: str,
        frames: list[np.ndarray],
    ):
        """Save analysis results."""
        output_path = Path(output_dir)
        output_path.mkdir(parents=True, exist_ok=True)

        # Save context JSON
        context_path = output_path / "scene_context.json"
        with open(context_path, "w") as f:
            json.dump(context.to_dict(), f, indent=2)

        # Save representative frame
        if frames:
            mid_idx = len(frames) // 2
            frame_path = output_path / "representative_frame.jpg"
            cv2.imwrite(str(frame_path), frames[mid_idx])


def analyze_scene(
    video_path: str,
    output_dir: str | None = None,
) -> SceneContext:
    """Convenience function to analyze scene context.

    Args:
        video_path: Path to video file
        output_dir: Optional output directory

    Returns:
        SceneContext
    """
    analyzer = SceneAnalyzer()
    return analyzer.analyze_video(video_path, output_dir)
