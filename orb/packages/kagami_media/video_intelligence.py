"""
🎬 VIDEO INTELLIGENCE ENGINE
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

Unified video understanding, enhancement, and performance extraction.

Combines:
- Gemini 3 multimodal analysis (scenes, people, emotions)
- Natural VHS enhancement (soft, film-like quality)
- Best moment extraction (peak performances)
- 3D scene understanding (spatial awareness)

Usage:
    from kagami_media.video_intelligence import VideoIntelligence

    vi = VideoIntelligence()
    result = await vi.full_scan("/path/to/video.mp4")

    # Get best performances
    for moment in result.best_performances:
        print(f"{moment.timestamp}s: {moment.description} (score: {moment.score})")

    # Enhance with natural settings
    enhanced = await vi.enhance_natural(video_path)
"""

import asyncio
import json
import os
import subprocess
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Any

# Lazy imports for optional dependencies
HAS_GENAI = False
genai = None


def _ensure_genai():
    """Ensure google.generativeai is available."""
    global HAS_GENAI, genai
    if not HAS_GENAI:
        try:
            import google.generativeai as _genai

            genai = _genai
            HAS_GENAI = True
        except ImportError as e:
            raise ImportError(
                "google-generativeai required. Install: pip install google-generativeai"
            ) from e


class PerformanceType(str, Enum):
    """Types of notable performances/moments."""

    EMOTIONAL = "emotional"  # Strong emotional expression
    FUNNY = "funny"  # Humorous moment
    MILESTONE = "milestone"  # Important life event
    INTERACTION = "interaction"  # Meaningful interaction between people
    ACTIVITY = "activity"  # Engaging activity
    CANDID = "candid"  # Natural, unposed moment
    ARTISTIC = "artistic"  # Visually striking composition


@dataclass
class Performance:
    """A notable performance or moment in the video.

    Attributes:
        timestamp: When the moment occurs (seconds)
        duration: How long it lasts (seconds)
        description: What's happening
        type: Category of moment
        score: Quality score 0-100
        people: Who's involved
        emotion: Dominant emotion
        audio_quality: Audio quality score 0-100
        visual_quality: Visual quality score 0-100
        frame_path: Path to extracted frame (if generated)
    """

    timestamp: float
    duration: float
    description: str
    type: PerformanceType
    score: float  # 0-100
    people: list[str] = field(default_factory=list)
    emotion: str | None = None
    audio_quality: float = 50.0
    visual_quality: float = 50.0
    frame_path: Path | None = None

    @property
    def end_time(self) -> float:
        """End timestamp."""
        return self.timestamp + self.duration


@dataclass
class Person:
    """A person identified in the video.

    Attributes:
        id: Unique identifier (person_1, person_2, etc.)
        description: Physical description
        age_estimate: Child/teen/adult/elderly
        appearances: List of (start, end) timestamps
        speaking_time: Total seconds of speech
        emotions: Emotions displayed and when
        relationships: Inferred relationships to others
    """

    id: str
    description: str
    age_estimate: str | None = None
    appearances: list[tuple[float, float]] = field(default_factory=list)
    speaking_time: float = 0.0
    emotions: dict[str, list[float]] = field(default_factory=dict)
    relationships: dict[str, str] = field(default_factory=dict)


@dataclass
class Scene:
    """A distinct scene in the video.

    Attributes:
        start: Start timestamp
        end: End timestamp
        description: What's happening
        location: Where it takes place
        activity: Main activity
        people: People present
        objects: Notable objects
        mood: Overall mood/atmosphere
        lighting: Lighting conditions
        camera_movement: Static/pan/zoom/etc.
    """

    start: float
    end: float
    description: str
    location: str | None = None
    activity: str | None = None
    people: list[str] = field(default_factory=list)
    objects: list[str] = field(default_factory=list)
    mood: str | None = None
    lighting: str | None = None
    camera_movement: str | None = None


@dataclass
class SpatialUnderstanding:
    """3D spatial understanding of the video.

    Attributes:
        locations: Identified locations/rooms
        layout: Inferred spatial layout
        depth_estimation: Estimated depth zones
        movement_patterns: How people/camera move through space
    """

    locations: list[str] = field(default_factory=list)
    layout: dict[str, Any] = field(default_factory=dict)
    depth_estimation: str | None = None
    movement_patterns: list[str] = field(default_factory=list)


@dataclass
class VideoScan:
    """Complete video intelligence scan result.

    Contains all extracted information about a video including
    scenes, people, performances, and spatial understanding.
    """

    video_path: str
    duration: float
    resolution: tuple[int, int]
    fps: float

    # Core analysis
    summary: str = ""
    scenes: list[Scene] = field(default_factory=list)
    people: list[Person] = field(default_factory=list)
    transcript: list[dict] = field(default_factory=list)

    # Performance extraction
    best_performances: list[Performance] = field(default_factory=list)

    # Spatial understanding
    spatial: SpatialUnderstanding | None = None

    # Metadata
    topics: list[str] = field(default_factory=list)
    era_estimate: str | None = None  # "1980s", "1990s", etc.
    quality_assessment: dict[str, float] = field(default_factory=dict)

    # Raw data
    raw_analysis: dict | None = None

    def to_dict(self) -> dict:
        """Convert to serializable dictionary."""
        return {
            "video_path": self.video_path,
            "duration": self.duration,
            "resolution": self.resolution,
            "fps": self.fps,
            "summary": self.summary,
            "scenes": [
                {
                    "start": s.start,
                    "end": s.end,
                    "description": s.description,
                    "location": s.location,
                    "activity": s.activity,
                    "people": s.people,
                    "objects": s.objects,
                    "mood": s.mood,
                    "lighting": s.lighting,
                    "camera_movement": s.camera_movement,
                }
                for s in self.scenes
            ],
            "people": [
                {
                    "id": p.id,
                    "description": p.description,
                    "age_estimate": p.age_estimate,
                    "appearances": p.appearances,
                    "speaking_time": p.speaking_time,
                    "emotions": p.emotions,
                    "relationships": p.relationships,
                }
                for p in self.people
            ],
            "transcript": self.transcript,
            "best_performances": [
                {
                    "timestamp": p.timestamp,
                    "duration": p.duration,
                    "description": p.description,
                    "type": p.type.value,
                    "score": p.score,
                    "people": p.people,
                    "emotion": p.emotion,
                    "audio_quality": p.audio_quality,
                    "visual_quality": p.visual_quality,
                }
                for p in self.best_performances
            ],
            "spatial": {
                "locations": self.spatial.locations,
                "layout": self.spatial.layout,
                "depth_estimation": self.spatial.depth_estimation,
                "movement_patterns": self.spatial.movement_patterns,
            }
            if self.spatial
            else None,
            "topics": self.topics,
            "era_estimate": self.era_estimate,
            "quality_assessment": self.quality_assessment,
        }

    def save(self, output_path: Path) -> None:
        """Save scan to JSON file."""
        with open(output_path, "w") as f:
            json.dump(self.to_dict(), f, indent=2)

    @classmethod
    def load(cls, input_path: Path) -> "VideoScan":
        """Load scan from JSON file."""
        with open(input_path) as f:
            data = json.load(f)

        scan = cls(
            video_path=data["video_path"],
            duration=data["duration"],
            resolution=tuple(data["resolution"]),
            fps=data["fps"],
            summary=data.get("summary", ""),
            topics=data.get("topics", []),
            era_estimate=data.get("era_estimate"),
            quality_assessment=data.get("quality_assessment", {}),
        )

        # Parse scenes
        for s in data.get("scenes", []):
            scan.scenes.append(
                Scene(
                    start=s["start"],
                    end=s["end"],
                    description=s["description"],
                    location=s.get("location"),
                    activity=s.get("activity"),
                    people=s.get("people", []),
                    objects=s.get("objects", []),
                    mood=s.get("mood"),
                    lighting=s.get("lighting"),
                    camera_movement=s.get("camera_movement"),
                )
            )

        # Parse people
        for p in data.get("people", []):
            scan.people.append(
                Person(
                    id=p["id"],
                    description=p["description"],
                    age_estimate=p.get("age_estimate"),
                    appearances=p.get("appearances", []),
                    speaking_time=p.get("speaking_time", 0),
                    emotions=p.get("emotions", {}),
                    relationships=p.get("relationships", {}),
                )
            )

        # Parse performances
        for p in data.get("best_performances", []):
            scan.best_performances.append(
                Performance(
                    timestamp=p["timestamp"],
                    duration=p["duration"],
                    description=p["description"],
                    type=PerformanceType(p["type"]),
                    score=p["score"],
                    people=p.get("people", []),
                    emotion=p.get("emotion"),
                    audio_quality=p.get("audio_quality", 50),
                    visual_quality=p.get("visual_quality", 50),
                )
            )

        # Parse spatial
        if data.get("spatial"):
            scan.spatial = SpatialUnderstanding(
                locations=data["spatial"].get("locations", []),
                layout=data["spatial"].get("layout", {}),
                depth_estimation=data["spatial"].get("depth_estimation"),
                movement_patterns=data["spatial"].get("movement_patterns", []),
            )

        scan.transcript = data.get("transcript", [])

        return scan


class VideoIntelligence:
    """Unified video intelligence engine.

    Combines multimodal AI analysis with enhancement capabilities
    to provide deep understanding of video content.

    Features:
    - Full video scan with Gemini 3
    - Scene-by-scene breakdown
    - People identification and tracking
    - Best moment/performance extraction
    - 3D spatial understanding
    - Natural VHS enhancement
    """

    # Gemini models in preference order
    MODELS = [
        "gemini-2.0-flash-exp",
        "gemini-2.0-flash",
        "gemini-1.5-pro",
        "gemini-1.5-flash",
    ]

    # Full scan prompt for comprehensive video understanding
    FULL_SCAN_PROMPT = """Analyze this video comprehensively. This appears to be a VHS home video.

Return ONLY valid JSON (no markdown) with this structure:

{
  "summary": "2-3 paragraph summary of the video",

  "era_estimate": "estimated decade (1980s, 1990s, etc.)",

  "scenes": [
    {
      "start": 0.0,
      "end": 30.0,
      "description": "what's happening",
      "location": "living room / outdoor / kitchen / etc",
      "activity": "opening presents / playing / eating / etc",
      "people": ["person_1", "person_2"],
      "objects": ["christmas tree", "couch"],
      "mood": "joyful / tense / calm / chaotic",
      "lighting": "natural / artificial / mixed / dark",
      "camera_movement": "static / pan / zoom / handheld"
    }
  ],

  "people": [
    {
      "id": "person_1",
      "description": "adult man with brown hair, wearing blue sweater",
      "age_estimate": "adult",
      "first_appearance": 0.0,
      "total_screen_time": 120.0,
      "speaking_time": 45.0,
      "dominant_emotions": ["happy", "excited"],
      "relationships": {"person_2": "spouse", "person_3": "child"}
    }
  ],

  "transcript": [
    {
      "start": 0.0,
      "end": 3.0,
      "speaker": "person_1",
      "text": "what they said",
      "emotion": "excited"
    }
  ],

  "best_performances": [
    {
      "timestamp": 45.0,
      "duration": 8.0,
      "description": "Child opens birthday present and screams with joy",
      "type": "emotional",
      "score": 95,
      "people": ["person_3"],
      "emotion": "ecstatic",
      "why_notable": "Genuine moment of pure childhood joy, great audio"
    }
  ],

  "spatial": {
    "locations": ["living room", "kitchen"],
    "layout": {"living room": "main space with couch and TV"},
    "depth_estimation": "typical home interior, 10-20 feet depth",
    "movement_patterns": ["camera follows children", "static tripod shots"]
  },

  "topics": ["birthday party", "family gathering", "children playing"],

  "quality_assessment": {
    "overall": 65,
    "audio_clarity": 50,
    "video_stability": 70,
    "lighting_quality": 60,
    "focus_quality": 75
  }
}

SCORING BEST PERFORMANCES (0-100):
- 90-100: Exceptional moment (genuine emotion, perfect timing, unique)
- 70-89: Great moment (strong emotion, good composition)
- 50-69: Good moment (interesting but not exceptional)
- Below 50: Don't include

Focus on QUALITY over quantity. Include only the best 5-15 moments."""

    def __init__(
        self,
        api_key: str | None = None,
        model: str = "auto",
    ):
        """Initialize video intelligence engine.

        Args:
            api_key: Gemini API key (defaults to env/keychain)
            model: Model name or "auto" for best available
        """
        self.api_key = api_key or self._get_api_key()
        self.model_name = model
        self._model = None

    def _get_api_key(self) -> str:
        """Get API key from environment or keychain."""
        # Try environment first
        key = os.environ.get("GOOGLE_API_KEY") or os.environ.get("GEMINI_API_KEY")
        if key:
            return key

        # Try keychain
        try:
            result = subprocess.run(
                ["security", "find-generic-password", "-s", "kagami", "-a", "gemini_api_key", "-w"],
                capture_output=True,
                text=True,
            )
            if result.returncode == 0:
                return result.stdout.strip()
        except Exception:
            pass

        raise ValueError("Gemini API key not found. Set GOOGLE_API_KEY or add to keychain.")

    def _ensure_model(self) -> None:
        """Ensure model is initialized."""
        if self._model is not None:
            return

        _ensure_genai()
        genai.configure(api_key=self.api_key)

        if self.model_name != "auto":
            self._model = genai.GenerativeModel(self.model_name)
            return

        # Auto-select best available
        for model_name in self.MODELS:
            try:
                self._model = genai.GenerativeModel(model_name)
                print(f"Using model: {model_name}")
                return
            except Exception:
                continue

        self._model = genai.GenerativeModel(self.MODELS[-1])

    def _get_video_info(self, video_path: Path) -> dict:
        """Get video metadata using ffprobe."""
        cmd = [
            "ffprobe",
            "-v",
            "quiet",
            "-print_format",
            "json",
            "-show_format",
            "-show_streams",
            str(video_path),
        ]
        result = subprocess.run(cmd, capture_output=True, text=True)
        data = json.loads(result.stdout)

        video_stream = next(s for s in data["streams"] if s["codec_type"] == "video")

        fps_str = video_stream.get("r_frame_rate", "30/1")
        fps_parts = fps_str.split("/")
        fps = float(fps_parts[0]) / float(fps_parts[1]) if len(fps_parts) == 2 else 30.0

        return {
            "width": int(video_stream["width"]),
            "height": int(video_stream["height"]),
            "fps": fps,
            "duration": float(data["format"].get("duration", 0)),
        }

    async def full_scan(
        self,
        video_path: str | Path,
        extract_frames: bool = False,
        output_dir: Path | None = None,
    ) -> VideoScan:
        """Perform complete video intelligence scan.

        This is the primary method for comprehensive video understanding.
        Uses Gemini 3's multimodal capabilities for:
        - Scene-by-scene analysis
        - People identification and tracking
        - Transcript with speaker/emotion attribution
        - Best performance extraction
        - 3D spatial understanding

        Args:
            video_path: Path to video file
            extract_frames: Extract frames for best performances
            output_dir: Where to save extracted frames

        Returns:
            VideoScan with all extracted intelligence
        """
        self._ensure_model()
        _ensure_genai()

        video_path = Path(video_path)
        if not video_path.exists():
            raise FileNotFoundError(f"Video not found: {video_path}")

        # Get video metadata
        print(f"\n📊 Analyzing: {video_path.name}")
        info = self._get_video_info(video_path)
        print(f"   Resolution: {info['width']}x{info['height']}")
        print(f"   Duration: {info['duration']:.1f}s")
        print(f"   FPS: {info['fps']:.2f}")

        # Upload to Gemini
        print("\n📤 Uploading to Gemini...")
        video_file = genai.upload_file(str(video_path))

        # Wait for processing
        print("⏳ Processing...")
        while video_file.state.name == "PROCESSING":
            await asyncio.sleep(2)
            video_file = genai.get_file(video_file.name)

        if video_file.state.name == "FAILED":
            raise RuntimeError(f"Video processing failed: {video_file.state.name}")

        # Run analysis
        print("🧠 Running full intelligence scan...")
        response = self._model.generate_content(
            [video_file, self.FULL_SCAN_PROMPT],
            generation_config=genai.GenerationConfig(
                temperature=0.2,
                max_output_tokens=65536,
            ),
        )

        # Parse response
        raw_text = response.text.strip() if response.text else ""

        try:
            # Clean JSON
            import re

            text = raw_text
            json_match = re.search(r"```(?:json)?\s*([\s\S]*?)```", text)
            if json_match:
                text = json_match.group(1).strip()
            elif text.startswith("{"):
                pass
            else:
                start = text.find("{")
                if start >= 0:
                    text = text[start:]

            raw_data = json.loads(text)
            print("✓ Parsed analysis")
        except json.JSONDecodeError as e:
            print(f"⚠️  JSON parse error: {e}")
            # Try to salvage
            try:
                fixed = text.rstrip(",\n ")
                fixed += "]" * (text.count("[") - text.count("]"))
                fixed += "}" * (text.count("{") - text.count("}"))
                raw_data = json.loads(fixed)
            except Exception:
                raw_data = {"_error": str(e), "_raw": raw_text[:5000]}

        # Build VideoScan
        scan = VideoScan(
            video_path=str(video_path),
            duration=info["duration"],
            resolution=(info["width"], info["height"]),
            fps=info["fps"],
            summary=raw_data.get("summary", ""),
            era_estimate=raw_data.get("era_estimate"),
            topics=raw_data.get("topics", []),
            quality_assessment=raw_data.get("quality_assessment", {}),
            raw_analysis=raw_data,
        )

        # Parse scenes
        for s in raw_data.get("scenes", []):
            scan.scenes.append(
                Scene(
                    start=float(s.get("start", 0)),
                    end=float(s.get("end", 0)),
                    description=s.get("description", ""),
                    location=s.get("location"),
                    activity=s.get("activity"),
                    people=s.get("people", []),
                    objects=s.get("objects", []),
                    mood=s.get("mood"),
                    lighting=s.get("lighting"),
                    camera_movement=s.get("camera_movement"),
                )
            )

        # Parse people
        for p in raw_data.get("people", []):
            person = Person(
                id=p.get("id", "unknown"),
                description=p.get("description", ""),
                age_estimate=p.get("age_estimate"),
                speaking_time=p.get("speaking_time", 0),
            )
            if "first_appearance" in p:
                person.appearances = [(p["first_appearance"], p.get("total_screen_time", 0))]
            if "dominant_emotions" in p:
                for e in p["dominant_emotions"]:
                    person.emotions[e] = []
            if "relationships" in p:
                person.relationships = p["relationships"]
            scan.people.append(person)

        # Parse transcript
        scan.transcript = raw_data.get("transcript", [])

        # Parse best performances
        for perf in raw_data.get("best_performances", []):
            try:
                perf_type = PerformanceType(perf.get("type", "candid"))
            except ValueError:
                perf_type = PerformanceType.CANDID

            scan.best_performances.append(
                Performance(
                    timestamp=float(perf.get("timestamp", 0)),
                    duration=float(perf.get("duration", 5)),
                    description=perf.get("description", ""),
                    type=perf_type,
                    score=float(perf.get("score", 50)),
                    people=perf.get("people", []),
                    emotion=perf.get("emotion"),
                )
            )

        # Sort performances by score
        scan.best_performances.sort(key=lambda p: p.score, reverse=True)

        # Parse spatial
        if "spatial" in raw_data:
            sp = raw_data["spatial"]
            scan.spatial = SpatialUnderstanding(
                locations=sp.get("locations", []),
                layout=sp.get("layout", {}),
                depth_estimation=sp.get("depth_estimation"),
                movement_patterns=sp.get("movement_patterns", []),
            )

        # Extract frames for best performances if requested
        if extract_frames and scan.best_performances:
            output_dir = output_dir or video_path.parent / "frames"
            await self._extract_performance_frames(video_path, scan, output_dir)

        # Clean up
        try:
            genai.delete_file(video_file.name)
        except Exception:
            pass

        print("\n✅ Scan complete:")
        print(f"   Scenes: {len(scan.scenes)}")
        print(f"   People: {len(scan.people)}")
        print(f"   Best moments: {len(scan.best_performances)}")

        return scan

    async def _extract_performance_frames(
        self,
        video_path: Path,
        scan: VideoScan,
        output_dir: Path,
    ) -> None:
        """Extract frames for best performances."""
        output_dir.mkdir(parents=True, exist_ok=True)

        for i, perf in enumerate(scan.best_performances[:10]):  # Top 10
            frame_path = output_dir / f"perf_{i + 1}_{perf.type.value}_{perf.timestamp:.0f}s.jpg"

            cmd = [
                "ffmpeg",
                "-y",
                "-ss",
                str(perf.timestamp),
                "-i",
                str(video_path),
                "-vframes",
                "1",
                "-q:v",
                "2",
                str(frame_path),
            ]

            subprocess.run(cmd, capture_output=True)

            if frame_path.exists():
                perf.frame_path = frame_path

    async def enhance_natural(
        self,
        video_path: str | Path,
        output_dir: Path | None = None,
        denoise: int = 2,
        grain: int = 12,
        sharpness: float = 0.15,
        scale: int = 2,
        test_mode: bool = False,
    ) -> Path:
        """Enhance video with natural, film-like quality.

        Avoids the sharp/fake AI look by using:
        - Gentle temporal denoising (preserves texture)
        - Lanczos upscaling (soft, organic)
        - Film grain overlay (natural texture)
        - Minimal sharpening

        Args:
            video_path: Path to source video
            output_dir: Where to save enhanced video
            denoise: Denoise strength 1-5 (lower = more natural)
            grain: Film grain intensity 0-100
            sharpness: Edge enhancement 0-1 (lower = softer)
            scale: Upscale factor (2 recommended for VHS)
            test_mode: Only process first 10 seconds

        Returns:
            Path to enhanced video
        """
        video_path = Path(video_path)
        if not video_path.exists():
            raise FileNotFoundError(f"Video not found: {video_path}")

        output_dir = output_dir or video_path.parent / "enhanced_natural"
        output_dir.mkdir(parents=True, exist_ok=True)

        suffix = "_natural_test" if test_mode else "_natural"
        output_path = output_dir / f"{video_path.stem}{suffix}.mp4"

        # Get video info
        info = self._get_video_info(video_path)
        out_w = info["width"] * scale
        out_h = info["height"] * scale

        print(f"\n🎬 Natural Enhancement: {video_path.name}")
        print(f"   {info['width']}x{info['height']} → {out_w}x{out_h}")
        print(f"   Denoise: {denoise}/5, Grain: {grain}%, Sharp: {sharpness}")

        # Build filter chain
        filters = []

        # 1. Gentle temporal denoise
        filters.append(
            f"hqdn3d=luma_spatial={denoise}:chroma_spatial={denoise}:luma_tmp=3:chroma_tmp=3"
        )

        # 2. VHS color correction
        filters.append("eq=saturation=1.1:gamma=1.02")

        # 3. Soft Lanczos upscale
        filters.append(f"scale={out_w}:{out_h}:flags=lanczos")

        # 4. Minimal sharpening
        if sharpness > 0:
            filters.append(f"unsharp=5:5:{sharpness}:5:5:0")

        # 5. Film grain
        if grain > 0:
            filters.append(f"noise=alls={int(grain * 0.5)}:allf=t+u")

        filter_chain = ",".join(filters)

        # Build ffmpeg command
        cmd = [
            "ffmpeg",
            "-y",
            "-i",
            str(video_path),
        ]

        if test_mode:
            cmd.extend(["-t", "10"])

        cmd.extend(
            [
                "-vf",
                filter_chain,
                "-c:v",
                "libx264",
                "-preset",
                "slow",
                "-crf",
                "18",
                "-pix_fmt",
                "yuv420p",
                "-c:a",
                "aac",
                "-b:a",
                "192k",
                str(output_path),
            ]
        )

        print("🎥 Processing...")

        process = subprocess.Popen(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
        )

        for line in process.stdout:
            if "frame=" in line:
                print(f"\r   {line.strip()}", end="", flush=True)

        process.wait()
        print()

        if process.returncode != 0:
            raise RuntimeError(f"Enhancement failed with code {process.returncode}")

        print(f"✅ Saved: {output_path}")
        return output_path

    async def extract_best_clips(
        self,
        video_path: str | Path,
        scan: VideoScan | None = None,
        output_dir: Path | None = None,
        min_score: float = 70,
        max_clips: int = 10,
        padding: float = 2.0,
    ) -> list[Path]:
        """Extract best performance clips from video.

        Args:
            video_path: Path to video
            scan: Pre-computed scan (runs full_scan if None)
            output_dir: Where to save clips
            min_score: Minimum score to extract
            max_clips: Maximum clips to extract
            padding: Seconds before/after performance

        Returns:
            List of paths to extracted clips
        """
        video_path = Path(video_path)

        if scan is None:
            scan = await self.full_scan(video_path)

        output_dir = output_dir or video_path.parent / "best_clips"
        output_dir.mkdir(parents=True, exist_ok=True)

        clips = []

        for i, perf in enumerate(scan.best_performances[:max_clips]):
            if perf.score < min_score:
                continue

            start = max(0, perf.timestamp - padding)
            duration = perf.duration + (2 * padding)

            clip_path = output_dir / f"clip_{i + 1:02d}_{perf.type.value}_{int(perf.score)}.mp4"

            cmd = [
                "ffmpeg",
                "-y",
                "-ss",
                str(start),
                "-i",
                str(video_path),
                "-t",
                str(duration),
                "-c:v",
                "libx264",
                "-preset",
                "fast",
                "-crf",
                "20",
                "-c:a",
                "aac",
                str(clip_path),
            ]

            subprocess.run(cmd, capture_output=True)

            if clip_path.exists():
                clips.append(clip_path)
                print(f"   Extracted: {clip_path.name} ({perf.description[:50]}...)")

        return clips


# Factory function
_instance: VideoIntelligence | None = None


def get_video_intelligence(
    api_key: str | None = None,
    model: str = "auto",
) -> VideoIntelligence:
    """Get or create VideoIntelligence instance.

    Args:
        api_key: Gemini API key (optional)
        model: Model name or "auto"

    Returns:
        VideoIntelligence singleton
    """
    global _instance
    if _instance is None:
        _instance = VideoIntelligence(api_key, model)
    return _instance


# CLI interface
if __name__ == "__main__":
    import sys

    if len(sys.argv) < 2:
        print("Usage: python -m kagami_media.video_intelligence <video_path> [--enhance] [--clips]")
        print()
        print("Options:")
        print("  --enhance    Also enhance video with natural settings")
        print("  --clips      Extract best performance clips")
        print("  --test       Process only first 10 seconds")
        sys.exit(1)

    video_path = Path(sys.argv[1])
    enhance = "--enhance" in sys.argv
    clips = "--clips" in sys.argv
    test = "--test" in sys.argv

    async def main():
        vi = VideoIntelligence()

        # Full scan
        scan = await vi.full_scan(video_path)

        # Save analysis
        output_json = video_path.with_suffix(".intelligence.json")
        scan.save(output_json)
        print(f"📝 Saved analysis: {output_json}")

        # Print best performances
        print("\n🌟 BEST PERFORMANCES:")
        for i, perf in enumerate(scan.best_performances[:5], 1):
            print(f"   {i}. [{perf.timestamp:.1f}s] {perf.description}")
            print(f"      Type: {perf.type.value}, Score: {perf.score:.0f}")

        # Enhance if requested
        if enhance:
            enhanced = await vi.enhance_natural(video_path, test_mode=test)
            print(f"🎬 Enhanced: {enhanced}")

        # Extract clips if requested
        if clips:
            clip_paths = await vi.extract_best_clips(video_path, scan)
            print(f"🎬 Extracted {len(clip_paths)} clips")

    asyncio.run(main())
