"""Character Profile Generator.

Generates character identity profiles from face clusters.
Creates directory structure, metadata, and README files.

Usage:
    generator = ProfileGenerator()
    generator.generate(
        cluster=person_cluster,
        name="Kristi",
        output_dir="assets/characters/kristi"
    )
"""

import json
from datetime import datetime
from pathlib import Path

import cv2

from kagami_media.face_clusterer import PersonCluster


class ProfileGenerator:
    """Generate character identity profiles from face clusters."""

    def __init__(self, base_dir: str = "assets/characters"):
        """Initialize generator.

        Args:
            base_dir: Base directory for character assets
        """
        self.base_dir = Path(base_dir)

    def generate(
        self,
        cluster: PersonCluster,
        name: str,
        age_estimate: str | None = None,
        notes: str | None = None,
    ) -> Path:
        """Generate a character profile from a face cluster.

        Args:
            cluster: PersonCluster containing faces
            name: Character name (e.g., "kristi")
            age_estimate: Optional age estimate
            notes: Optional notes about the character

        Returns:
            Path to generated profile directory
        """
        # Create directory structure
        char_dir = self.base_dir / name.lower().replace(" ", "_")
        (char_dir / "reference_images").mkdir(parents=True, exist_ok=True)
        (char_dir / "frames").mkdir(exist_ok=True)
        (char_dir / "voice_samples").mkdir(exist_ok=True)

        # Save reference images (top quality faces)
        reference_files = []
        for i, face in enumerate(cluster.top_faces[:5]):
            filename = f"{name.lower()}_{i + 1}.jpg"
            filepath = char_dir / "reference_images" / filename
            cv2.imwrite(str(filepath), face.face_image)

            reference_files.append(
                {
                    "file": f"reference_images/{filename}",
                    "source_video": face.source_video,
                    "timestamp_seconds": face.timestamp_seconds,
                    "timestamp_formatted": face.timestamp_formatted,
                    "quality_score": face.quality_score,
                    "face_id": face.face_id,
                }
            )

        # Save all frames
        for face in cluster.faces:
            filename = f"frame_{face.face_id}.jpg"
            filepath = char_dir / "frames" / filename
            cv2.imwrite(str(filepath), face.face_image)

        # Generate source_timestamps.json
        self._generate_timestamps_json(
            char_dir=char_dir,
            cluster=cluster,
            name=name,
            reference_files=reference_files,
        )

        # Generate metadata.json template
        self._generate_metadata_json(
            char_dir=char_dir,
            name=name,
            age_estimate=age_estimate,
            reference_files=reference_files,
        )

        # Generate README.md
        self._generate_readme(
            char_dir=char_dir,
            name=name,
            cluster=cluster,
            age_estimate=age_estimate,
            notes=notes,
        )

        return char_dir

    def _generate_timestamps_json(
        self,
        char_dir: Path,
        cluster: PersonCluster,
        name: str,
        reference_files: list[dict],
    ):
        """Generate source_timestamps.json with provenance tracking."""

        # Get source drive from first face
        source_drive = cluster.faces[0].source_drive if cluster.faces else "unknown"

        timestamps_data = {
            "character": name,
            "source_drive": source_drive,
            "extraction_date": datetime.now().strftime("%Y-%m-%d"),
            "total_faces_found": len(cluster.faces),
            "source_videos": list(cluster.source_videos),
            "references": reference_files,
            "all_timestamps": [
                {
                    "source_video": f.source_video,
                    "timestamp_seconds": f.timestamp_seconds,
                    "timestamp_formatted": f.timestamp_formatted,
                    "quality_score": f.quality_score,
                    "face_id": f.face_id,
                }
                for f in cluster.faces
            ],
        }

        with open(char_dir / "source_timestamps.json", "w") as f:
            json.dump(timestamps_data, f, indent=2)

    def _generate_metadata_json(
        self,
        char_dir: Path,
        name: str,
        age_estimate: str | None,
        reference_files: list[dict],
    ):
        """Generate metadata.json template."""

        metadata = {
            "character_name": name,
            "voice_id": None,  # To be filled in after voice cloning
            "voice_settings": {
                "stability": 0.45,
                "similarity_boost": 0.75,
                "style": 0.35,
                "speed": 1.0,
                "speaker_boost": True,
            },
            "v3_audio_tags": {
                "effective": [],  # To be determined
                "avoid": [],
            },
            "speech_profile": {
                "wpm": None,  # To be analyzed
                "style": None,
                "humor": None,
                "signature_phrases": [],
            },
            "image_generation": {
                "model": "gpt-image-1.5",
                "input_fidelity": "high",
                "quality": "high",
            },
            "age_estimate": age_estimate,
            "images": [
                {
                    "path": ref["file"],
                    "quality": ref["quality_score"],
                    "source_video": ref["source_video"],
                    "timestamp": ref["timestamp_formatted"],
                }
                for ref in reference_files
            ],
        }

        with open(char_dir / "metadata.json", "w") as f:
            json.dump(metadata, f, indent=2)

    def _generate_readme(
        self,
        char_dir: Path,
        name: str,
        cluster: PersonCluster,
        age_estimate: str | None,
        notes: str | None,
    ):
        """Generate README.md for the character."""

        best_face = cluster.best_face

        readme = f"""# {name} - Identity Assets

**Voice ID:** `[NOT YET CLONED]`

## Contents

- `reference_images/` - Best quality face references ({len(cluster.top_faces[:5])} images)
- `frames/` - All extracted face frames ({len(cluster.faces)} images)
- `voice_samples/` - Voice samples for cloning
- `source_timestamps.json` - Full provenance tracking
- `metadata.json` - Character metadata template

## Source Information

| Metric | Value |
|--------|-------|
| **Total Faces Found** | {len(cluster.faces)} |
| **Source Videos** | {", ".join(cluster.source_videos)} |
| **Best Quality Frame** | {best_face.source_video} @ {best_face.timestamp_formatted} |
| **Age Estimate** | {age_estimate or "Unknown"} |

## Reference Images

"""

        for i, face in enumerate(cluster.top_faces[:5]):
            readme += f"""### Reference {i + 1}
- **Source:** `{face.source_video}`
- **Timestamp:** {face.timestamp_formatted} ({face.timestamp_seconds:.1f}s)
- **Quality:** {face.quality_score}
- **Face ID:** `{face.face_id}`

"""

        if notes:
            readme += f"""## Notes

{notes}

"""

        readme += f"""## Usage

```python
from kagami_studio.characters import speak
from kagami_studio.composition import Shot, ShotType, render_shot

# Have character speak
result = await speak("{name.lower()}", "Hello!")

# Or create a shot
shot = Shot(
    type=ShotType.DIALOGUE,
    character="{name.lower()}",
    text="Hello!",
    motion="warm",
)
result = await render_shot(shot)
```

---

*Generated by kagami_media face extraction pipeline*
"""

        with open(char_dir / "README.md", "w") as f:
            f.write(readme)


def generate_character_profile(
    cluster: PersonCluster,
    name: str,
    base_dir: str = "assets/characters",
    age_estimate: str | None = None,
    notes: str | None = None,
) -> Path:
    """Convenience function to generate a character profile.

    Args:
        cluster: PersonCluster containing faces
        name: Character name
        base_dir: Base directory for characters
        age_estimate: Optional age estimate
        notes: Optional notes

    Returns:
        Path to generated profile
    """
    generator = ProfileGenerator(base_dir=base_dir)
    return generator.generate(
        cluster=cluster,
        name=name,
        age_estimate=age_estimate,
        notes=notes,
    )
