"""Character Identity Bridge.

Loads character profiles from assets/characters/ into the identity system
for real-time face recognition. Characters are the source of truth for
household members with voice, images, and schedules.

This bridges:
- Character profiles (voice, images, schedules in assets/characters/)
- Identity detection (real-time camera recognition)
- Presence system (who's home tracking)

Colony: Nexus (e₄) — Integration
Safety: h(x) ≥ 0 — Privacy-preserving local processing

Usage:
    from kagami.core.integrations.character_identity import (
        load_characters_to_identity_cache,
        get_character_profile,
        CHARACTER_DIR,
    )

    # Load all characters into identity system
    await load_characters_to_identity_cache()

    # Get character profile with all data
    tim = get_character_profile("tim")
"""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass, field
from pathlib import Path

logger = logging.getLogger(__name__)

# Character directory (source of truth)
# Path: packages/kagami/core/integrations/character_identity.py -> assets/characters
CHARACTER_DIR = Path(__file__).parents[4] / "assets" / "characters"


@dataclass
class CharacterProfile:
    """Full character profile loaded from assets/characters/."""

    identity_id: str
    name: str
    role: str  # owner, partner, family, guest

    # Voice
    voice_id: str | None = None
    voice_settings: dict = field(default_factory=dict)

    # Physical description (for identity detection)
    physical_description: dict = field(default_factory=dict)

    # Presence schedule
    presence_schedule: dict = field(default_factory=dict)

    # Reference images
    reference_images: list[Path] = field(default_factory=list)
    camera_footage: list[Path] = field(default_factory=list)

    # Face embedding (computed from images)
    face_embedding: list[float] | None = None
    face_threshold: float = 0.6

    # Full metadata
    metadata: dict = field(default_factory=dict)

    @property
    def display_name(self) -> str:
        return self.name or self.identity_id

    def to_dict(self) -> dict:
        return {
            "identity_id": self.identity_id,
            "name": self.name,
            "role": self.role,
            "voice_id": self.voice_id,
            "physical_description": self.physical_description,
            "presence_schedule": self.presence_schedule,
            "reference_image_count": len(self.reference_images),
            "camera_footage_count": len(self.camera_footage),
            "has_face_embedding": self.face_embedding is not None,
        }


def _load_character_metadata(char_dir: Path) -> dict | None:
    """Load character metadata.json."""
    meta_path = char_dir / "metadata.json"
    if not meta_path.exists():
        return None

    with open(meta_path) as f:
        return json.load(f)


def _find_character_images(char_dir: Path) -> tuple[list[Path], list[Path]]:
    """Find reference images and camera footage for a character."""
    reference_images = []
    camera_footage = []

    # Reference images (high quality portraits)
    for pattern in ["reference_*.png", "reference_*.jpg"]:
        reference_images.extend(char_dir.glob(pattern))

    # Camera footage (real-time detections)
    footage_dir = char_dir / "camera_footage"
    if footage_dir.exists():
        camera_footage.extend(footage_dir.glob("*.jpg"))
        camera_footage.extend(footage_dir.glob("*.png"))

    return sorted(reference_images), sorted(camera_footage)


def load_character_profile(char_name: str) -> CharacterProfile | None:
    """Load a single character profile.

    Args:
        char_name: Character directory name (e.g., "tim", "jill")

    Returns:
        CharacterProfile or None if not found
    """
    char_dir = CHARACTER_DIR / char_name

    if not char_dir.exists():
        return None

    metadata = _load_character_metadata(char_dir)
    if not metadata:
        return None

    reference_images, camera_footage = _find_character_images(char_dir)

    profile = CharacterProfile(
        identity_id=metadata.get("identity_id", char_name),
        name=metadata.get("character_name", char_name.title()),
        role=metadata.get("role", "unknown"),
        voice_id=metadata.get("voice_id"),
        voice_settings=metadata.get("voice_settings", {}),
        physical_description=metadata.get("physical_description", {}),
        presence_schedule=metadata.get("presence_schedule", {}),
        reference_images=reference_images,
        camera_footage=camera_footage,
        face_threshold=metadata.get("face_threshold", 0.6),
        metadata=metadata,
    )

    return profile


def list_characters() -> list[str]:
    """List all available characters.

    Returns:
        List of character directory names
    """
    if not CHARACTER_DIR.exists():
        return []

    characters = []
    for item in CHARACTER_DIR.iterdir():
        if item.is_dir() and not item.name.startswith("."):
            meta_path = item / "metadata.json"
            if meta_path.exists():
                characters.append(item.name)

    return sorted(characters)


def get_character_profile(name: str) -> CharacterProfile | None:
    """Get character profile by name (case-insensitive).

    Args:
        name: Character name or identity_id

    Returns:
        CharacterProfile or None
    """
    # Try exact match first
    profile = load_character_profile(name.lower())
    if profile:
        return profile

    # Search by character_name or identity_id
    for char_name in list_characters():
        profile = load_character_profile(char_name)
        if profile:
            if profile.name.lower() == name.lower():
                return profile
            if profile.identity_id.lower() == name.lower():
                return profile

    return None


async def compute_face_embedding(image_paths: list[Path]) -> list[float] | None:
    """Compute average face embedding from images.

    Uses InsightFace to extract embeddings from multiple images
    and returns the normalized average for robust matching.

    Args:
        image_paths: List of image paths

    Returns:
        512-dim face embedding or None
    """
    if not image_paths:
        return None

    try:
        import cv2
        import numpy as np
        from insightface.app import FaceAnalysis

        # Initialize InsightFace
        app = FaceAnalysis(name="buffalo_l", providers=["CPUExecutionProvider"])
        app.prepare(ctx_id=-1, det_size=(640, 640))

        embeddings = []

        for img_path in image_paths[:10]:  # Use up to 10 images
            try:
                # Read image
                img = cv2.imread(str(img_path))
                if img is None:
                    continue

                # Convert BGR to RGB
                img_rgb = cv2.cvtColor(img, cv2.COLOR_BGR2RGB)

                # Detect faces
                faces = app.get(img_rgb)

                if faces:
                    # Use largest face
                    face = max(faces, key=lambda f: f.bbox[2] - f.bbox[0])
                    embeddings.append(face.embedding)

            except Exception as e:
                logger.debug(f"Failed to process {img_path}: {e}")
                continue

        if not embeddings:
            return None

        # Average and normalize
        avg_embedding = np.mean(embeddings, axis=0)
        norm = np.linalg.norm(avg_embedding)
        if norm > 0:
            avg_embedding = avg_embedding / norm

        return avg_embedding.tolist()

    except ImportError as e:
        logger.warning(f"InsightFace not available: {e}")
        return None
    except Exception as e:
        logger.error(f"Face embedding computation failed: {e}")
        return None


async def load_characters_to_identity_cache(
    force_recompute: bool = False,
) -> dict[str, bool]:
    """Load all characters into the identity cache.

    This:
    1. Loads character profiles from assets/characters/
    2. Computes face embeddings from camera footage
    3. Registers them in the identity cache for real-time matching

    Args:
        force_recompute: Recompute embeddings even if cached

    Returns:
        Dict of character_name -> success
    """
    from kagami.core.caching.identity_cache import get_identity_cache

    cache = await get_identity_cache()
    results = {}

    for char_name in list_characters():
        try:
            profile = load_character_profile(char_name)
            if not profile:
                results[char_name] = False
                continue

            # Skip non-household characters (but include pets!)
            if profile.role not in ("owner", "partner", "family", "resident", "pet"):
                logger.debug(f"Skipping {char_name} (role: {profile.role})")
                continue

            # Check if already in cache
            existing = cache.get_identity(profile.identity_id)
            if existing and not force_recompute:
                logger.debug(f"Character {char_name} already in cache")
                results[char_name] = True
                continue

            # Compute face embedding from images
            all_images = profile.camera_footage + profile.reference_images
            if all_images:
                logger.info(f"Computing face embedding for {profile.name}...")
                embedding = await compute_face_embedding(all_images)

                if embedding:
                    profile.face_embedding = embedding
                    logger.info(
                        f"✓ Computed embedding for {profile.name} from {len(all_images)} images"
                    )

            # Add to cache
            import numpy as np

            face_emb = None
            if profile.face_embedding:
                face_emb = np.array(profile.face_embedding, dtype=np.float32)

            await cache.add_identity(
                identity_id=profile.identity_id,
                name=profile.name,
                face_embedding=face_emb,
                face_threshold=profile.face_threshold,
            )

            logger.info(f"✓ Loaded {profile.name} into identity cache")
            results[char_name] = True

        except Exception as e:
            logger.error(f"Failed to load character {char_name}: {e}")
            results[char_name] = False

    return results


async def sync_character_to_presence(char_name: str) -> bool:
    """Sync character schedule to presence system.

    This ensures the presence system knows about expected
    arrival/departure patterns for household members.

    Args:
        char_name: Character name

    Returns:
        True if synced successfully
    """
    profile = get_character_profile(char_name)
    if not profile:
        return False

    try:
        from kagami_smarthome import get_smart_home

        controller = await get_smart_home()
        if not hasattr(controller, "_presence"):
            return False

        presence = controller._presence

        # Register identity with presence engine
        if hasattr(presence, "register_expected_identity"):
            presence.register_expected_identity(
                identity_id=profile.identity_id,
                name=profile.name,
                schedule=profile.presence_schedule,
                role=profile.role,
            )
            logger.info(f"Synced {profile.name} to presence system")
            return True

    except Exception as e:
        logger.warning(f"Failed to sync {char_name} to presence: {e}")

    return False


# Convenience exports
__all__ = [
    "CHARACTER_DIR",
    "CharacterProfile",
    "compute_face_embedding",
    "get_character_profile",
    "list_characters",
    "load_character_profile",
    "load_characters_to_identity_cache",
    "sync_character_to_presence",
]
