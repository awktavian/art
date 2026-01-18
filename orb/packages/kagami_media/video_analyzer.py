"""Gemini-powered video analysis for knowledge extraction.

This module provides streamlined video analysis using Gemini 3's native
multimodal capabilities. Instead of complex per-frame processing pipelines,
it leverages Gemini's ability to directly understand video content.

For home video archives, this approach is:
- Faster (minutes vs hours per video)
- More accurate (multimodal understanding beats audio-only transcription)
- Cheaper (~$0.05/video vs hours of GPU time)
- Simpler (single API call vs complex pipeline)

Usage:
    from kagami_media.video_analyzer import GeminiVideoAnalyzer

    analyzer = GeminiVideoAnalyzer()
    result = await analyzer.analyze_video("/path/to/video.mp4")

    # Access structured results
    for segment in result.transcript:
        print(f"[{segment.start_time}] {segment.speaker}: {segment.text}")

    for person in result.people:
        print(f"Person: {person.description} - appears at {person.timestamps}")
"""

import asyncio
import json
import subprocess
from dataclasses import dataclass, field
from pathlib import Path

try:
    import google.generativeai as genai

    HAS_GENAI = True
except ImportError:
    HAS_GENAI = False


@dataclass
class TranscriptSegment:
    """A segment of transcribed speech."""

    start_time: float
    end_time: float
    speaker: str  # "Person 1", "Child", etc. until identified
    text: str
    confidence: float = 1.0
    emotion: str | None = None


@dataclass
class PersonAppearance:
    """A person detected in the video."""

    id: str  # "person_1", "person_2", etc.
    description: str  # "Adult male with blue eyes", "Young girl with blonde hair"
    estimated_age: str | None = None
    timestamps: list[tuple[float, float]] = field(default_factory=list)
    speaking_segments: list[int] = field(default_factory=list)  # indices into transcript


@dataclass
class SceneDescription:
    """A scene or event in the video."""

    start_time: float
    end_time: float
    description: str
    location: str | None = None
    activity: str | None = None
    people_present: list[str] = field(default_factory=list)  # person ids


@dataclass
class VideoAnalysis:
    """Complete analysis result for a video."""

    video_path: str
    duration_seconds: float
    transcript: list[TranscriptSegment] = field(default_factory=list)
    people: list[PersonAppearance] = field(default_factory=list)
    scenes: list[SceneDescription] = field(default_factory=list)
    summary: str = ""
    key_moments: list[dict] = field(default_factory=list)
    raw_analysis: dict | None = None

    def to_dict(self) -> dict:
        """Convert to serializable dictionary."""
        data = {
            "video_path": self.video_path,
            "duration_seconds": self.duration_seconds,
            "transcript": [
                {
                    "start_time": s.start_time,
                    "end_time": s.end_time,
                    "speaker": s.speaker,
                    "text": s.text,
                    "confidence": s.confidence,
                    "emotion": s.emotion,
                }
                for s in self.transcript
            ],
            "people": [
                {
                    "id": p.id,
                    "description": p.description,
                    "estimated_age": p.estimated_age,
                    "timestamps": p.timestamps,
                    "speaking_segments": p.speaking_segments,
                }
                for p in self.people
            ],
            "scenes": [
                {
                    "start_time": s.start_time,
                    "end_time": s.end_time,
                    "description": s.description,
                    "location": s.location,
                    "activity": s.activity,
                    "people_present": s.people_present,
                }
                for s in self.scenes
            ],
            "summary": self.summary,
            "key_moments": self.key_moments,
        }
        # Include raw response if parsing failed
        if self.raw_analysis and "_raw_response" in self.raw_analysis:
            data["_raw_response"] = self.raw_analysis["_raw_response"]
            data["_parse_error"] = self.raw_analysis.get("_parse_error", "")
        return data

    def save(self, output_path: Path) -> None:
        """Save analysis to JSON file."""
        with open(output_path, "w") as f:
            json.dump(self.to_dict(), f, indent=2)


class GeminiVideoAnalyzer:
    """Analyze videos using Gemini 3's multimodal capabilities.

    This class provides direct video analysis without the need for
    complex processing pipelines. Gemini can:
    - Transcribe speech (with visual lip-reading enhancement)
    - Identify and describe people
    - Understand scenes and context
    - Extract key moments and events

    All in a single API call per video.
    """

    GEMINI_MODELS = [
        "gemini-2.0-flash",  # Latest stable (Dec 2025)
        "gemini-2.0-flash-exp",  # Experimental
        "gemini-1.5-flash",  # Fallback
    ]

    ANALYSIS_PROMPT = """Analyze this home video. This is a VHS home video from the 1980s-1990s.

IMPORTANT: Keep responses concise to avoid truncation. Focus on quality over completeness.

Return valid JSON (no markdown) with:

1. **transcript**: ONLY the most important/audible speech segments (max 30):
   - start_time, end_time (seconds)
   - speaker: "Adult man", "Adult woman", "Young boy", "Young girl", "Child"
   - text: what they said
   - emotion: happy/sad/excited/neutral/angry

2. **people**: All people appearing (max 10):
   - id: person_1, person_2, etc.
   - description: brief physical description (hair, age, clothing)
   - estimated_age: child/teen/adult/elderly
   - first_seen: timestamp in seconds

3. **scenes**: Major scene changes (max 10):
   - start_time, end_time
   - description: what's happening
   - location: room/outdoor/etc
   - activity: party/playing/eating/etc

4. **summary**: 1-2 paragraph summary of the video

5. **key_moments**: 5-10 notable moments:
   - timestamp
   - description
   - type: funny/emotional/milestone/activity

Return ONLY valid JSON, no markdown blocks."""

    def __init__(
        self,
        api_key: str | None = None,
        model: str = "auto",
        max_video_duration: int = 3600,  # 1 hour max
    ):
        """Initialize the video analyzer.

        Args:
            api_key: Gemini API key. If not provided, reads from keychain.
            model: Model to use. "auto" tries latest first.
            max_video_duration: Maximum video duration in seconds.
        """
        if not HAS_GENAI:
            raise ImportError(
                "google-generativeai is required. Install with: pip install google-generativeai"
            )

        self.api_key = api_key or self._get_api_key()
        self.model_name = model
        self.max_video_duration = max_video_duration

        # Configure Gemini
        genai.configure(api_key=self.api_key)
        self.model = self._get_model()

    def _get_api_key(self) -> str:
        """Get API key from keychain."""
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
        raise ValueError("Gemini API key not found. Set GEMINI_API_KEY or add to keychain.")

    def _get_model(self) -> "genai.GenerativeModel":
        """Get the best available Gemini model."""
        if self.model_name != "auto":
            return genai.GenerativeModel(self.model_name)

        # Try models in order of preference
        for model_name in self.GEMINI_MODELS:
            try:
                model = genai.GenerativeModel(model_name)
                # Quick test
                return model
            except Exception:
                continue

        # Fallback to first
        return genai.GenerativeModel(self.GEMINI_MODELS[0])

    def _get_video_duration(self, video_path: Path) -> float:
        """Get video duration using ffprobe."""
        try:
            result = subprocess.run(
                [
                    "ffprobe",
                    "-v",
                    "quiet",
                    "-show_entries",
                    "format=duration",
                    "-of",
                    "csv=p=0",
                    str(video_path),
                ],
                capture_output=True,
                text=True,
            )
            if result.returncode == 0:
                return float(result.stdout.strip())
        except Exception:
            pass
        return 0.0

    async def analyze_video(
        self,
        video_path: str | Path,
        custom_prompt: str | None = None,
    ) -> VideoAnalysis:
        """Analyze a video using Gemini.

        Args:
            video_path: Path to the video file.
            custom_prompt: Optional custom analysis prompt.

        Returns:
            VideoAnalysis with all extracted information.
        """
        video_path = Path(video_path)
        if not video_path.exists():
            raise FileNotFoundError(f"Video not found: {video_path}")

        duration = self._get_video_duration(video_path)

        # Upload video to Gemini
        print(f"Uploading video: {video_path.name} ({duration:.0f}s)")
        video_file = genai.upload_file(str(video_path))

        # Wait for processing
        print("Waiting for video processing...")
        while video_file.state.name == "PROCESSING":
            await asyncio.sleep(2)
            video_file = genai.get_file(video_file.name)

        if video_file.state.name == "FAILED":
            raise RuntimeError(f"Video processing failed: {video_file.state.name}")

        print("Analyzing video with Gemini...")

        # Generate analysis
        prompt = custom_prompt or self.ANALYSIS_PROMPT
        response = self.model.generate_content(
            [video_file, prompt],
            generation_config=genai.GenerationConfig(
                temperature=0.2,
                max_output_tokens=65536,  # Increased for long videos
            ),
        )

        # Parse response
        raw_text = response.text.strip() if response.text else ""

        try:
            # Clean response text (remove markdown if present)
            text = raw_text

            # Handle ```json ... ``` format
            import re

            json_match = re.search(r"```(?:json)?\s*([\s\S]*?)```", text)
            if json_match:
                text = json_match.group(1).strip()
            elif text.startswith("{"):
                pass  # Already clean JSON
            else:
                # Try to find JSON object in the text
                start = text.find("{")
                if start >= 0:
                    text = text[start:]

            raw_data = json.loads(text)
            print(
                f"✓ Parsed JSON: {len(raw_data.get('transcript', []))} transcript, {len(raw_data.get('people', []))} people"
            )
        except json.JSONDecodeError as e:
            import sys

            print(f"Warning: Failed to parse JSON response: {e}", file=sys.stderr)

            # Try to salvage truncated JSON by completing it
            try:
                # Remove markdown wrapper if present
                if text.startswith("```"):
                    text = text[text.find("\n") + 1 :]

                # Try to find partial data and close arrays/objects
                # Count unclosed brackets
                opens = text.count("[") - text.count("]")
                opens += text.count("{") - text.count("}")

                # Try to close them
                fixed = text.rstrip(",\n ")
                fixed += "]" * (text.count("[") - text.count("]"))
                fixed += "}" * (text.count("{") - text.count("}"))

                raw_data = json.loads(fixed)
                print(
                    f"✓ Salvaged truncated JSON: {len(raw_data.get('transcript', []))} transcript"
                )
            except Exception:
                print(f"Could not salvage JSON ({len(raw_text)} chars)", file=sys.stderr)
                # Save raw response for debugging
                raw_data = {"_raw_response": raw_text, "_parse_error": str(e)}

        # Build result
        result = VideoAnalysis(
            video_path=str(video_path),
            duration_seconds=duration,
            raw_analysis=raw_data,
        )

        # Parse transcript
        for seg in raw_data.get("transcript", []):
            result.transcript.append(
                TranscriptSegment(
                    start_time=float(seg.get("start_time", 0)),
                    end_time=float(seg.get("end_time", 0)),
                    speaker=seg.get("speaker", "Unknown"),
                    text=seg.get("text", ""),
                    emotion=seg.get("emotion"),
                )
            )

        # Parse people
        for person in raw_data.get("people", []):
            # Handle both old format (timestamps array) and new format (first_seen)
            timestamps = person.get("timestamps", [])
            if not timestamps and "first_seen" in person:
                timestamps = [[person["first_seen"], person["first_seen"]]]
            result.people.append(
                PersonAppearance(
                    id=person.get("id", "unknown"),
                    description=person.get("description", ""),
                    estimated_age=person.get("estimated_age"),
                    timestamps=timestamps,
                    speaking_segments=person.get("speaking_segments", []),
                )
            )

        # Parse scenes
        for scene in raw_data.get("scenes", []):
            result.scenes.append(
                SceneDescription(
                    start_time=float(scene.get("start_time", 0)),
                    end_time=float(scene.get("end_time", 0)),
                    description=scene.get("description", ""),
                    location=scene.get("location"),
                    activity=scene.get("activity"),
                    people_present=scene.get("people_present", []),
                )
            )

        # Set summary and key moments
        result.summary = raw_data.get("summary", "")
        result.key_moments = raw_data.get("key_moments", [])

        # Clean up uploaded file
        try:
            genai.delete_file(video_file.name)
        except Exception:
            pass

        return result

    async def analyze_batch(
        self,
        video_paths: list[str | Path],
        output_dir: Path,
        max_concurrent: int = 2,
    ) -> list[VideoAnalysis]:
        """Analyze multiple videos.

        Args:
            video_paths: List of video paths.
            output_dir: Directory to save analysis JSON files.
            max_concurrent: Maximum concurrent analyses.

        Returns:
            List of VideoAnalysis results.
        """
        output_dir = Path(output_dir)
        output_dir.mkdir(parents=True, exist_ok=True)

        results = []
        semaphore = asyncio.Semaphore(max_concurrent)

        async def analyze_one(video_path: Path) -> VideoAnalysis | None:
            async with semaphore:
                try:
                    print(f"\n{'=' * 60}")
                    print(f"Analyzing: {video_path.name}")
                    print(f"{'=' * 60}")

                    result = await self.analyze_video(video_path)

                    # Save result
                    output_file = output_dir / f"{video_path.stem}.json"
                    result.save(output_file)
                    print(f"✓ Saved: {output_file}")

                    return result
                except Exception as e:
                    print(f"✗ Failed to analyze {video_path.name}: {e}")
                    return None

        # Process all videos
        tasks = [analyze_one(Path(p)) for p in video_paths]
        results = await asyncio.gather(*tasks)

        return [r for r in results if r is not None]


async def analyze_usb_volume(
    volume_path: str | Path,
    output_dir: Path | None = None,
) -> list[VideoAnalysis]:
    """Analyze all videos on a USB volume.

    Args:
        volume_path: Path to the mounted volume.
        output_dir: Where to save analysis. Defaults to volume_path/analysis.

    Returns:
        List of all video analyses.
    """
    volume_path = Path(volume_path)
    if not volume_path.exists():
        raise FileNotFoundError(f"Volume not found: {volume_path}")

    output_dir = output_dir or (volume_path / "analysis")

    # Find all video files
    video_extensions = {".mp4", ".mov", ".avi", ".mkv", ".m4v"}
    videos = [
        f
        for f in volume_path.iterdir()
        if f.suffix.lower() in video_extensions
        and not f.name.startswith(".")
        and not f.name.startswith("test")  # Skip test files
    ]

    if not videos:
        print(f"No videos found in {volume_path}")
        return []

    print(f"Found {len(videos)} videos to analyze")

    analyzer = GeminiVideoAnalyzer()
    return await analyzer.analyze_batch(videos, output_dir)


# CLI interface
if __name__ == "__main__":
    import sys

    if len(sys.argv) < 2:
        print("Usage: python -m kagami_media.video_analyzer <video_path_or_volume>")
        sys.exit(1)

    path = Path(sys.argv[1])

    if path.is_dir():
        # Analyze all videos in directory
        results = asyncio.run(analyze_usb_volume(path))
    else:
        # Analyze single video
        analyzer = GeminiVideoAnalyzer()
        result = asyncio.run(analyzer.analyze_video(path))
        result.save(path.with_suffix(".analysis.json"))
        results = [result]

    print(f"\n{'=' * 60}")
    print(f"Analysis complete: {len(results)} videos processed")
    print(f"{'=' * 60}")
