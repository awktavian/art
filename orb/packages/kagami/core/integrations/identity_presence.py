"""Identity Presence Integration.

Connects extracted identities to Kagami's presence detection system.
Enables queries like "Is Becky home?" using camera face recognition.

Usage:
    from kagami.core.integrations.identity_presence import IdentityPresenceService

    service = IdentityPresenceService()

    # Register identity for presence detection
    service.register_identity("becky", identity_id="abc123")

    # Check if someone is home
    is_home = await service.is_identity_present("becky")

    # Get current household members
    present = await service.get_present_identities()
"""

import json
from dataclasses import dataclass
from datetime import datetime, timedelta
from pathlib import Path

import numpy as np

# Try to import face recognition for matching
try:
    import importlib.util

    CV2_AVAILABLE = importlib.util.find_spec("cv2") is not None
except ImportError:
    CV2_AVAILABLE = False


@dataclass
class PresenceRecord:
    """Record of identity presence detection."""

    identity_id: str
    name: str

    # Presence state
    is_present: bool = False
    confidence: float = 0.0

    # Location
    last_seen_location: str | None = None  # Room/camera name
    last_seen_timestamp: datetime | None = None

    # Face embedding for matching
    face_embedding: np.ndarray | None = None

    def to_dict(self) -> dict:
        return {
            "identity_id": self.identity_id,
            "name": self.name,
            "is_present": self.is_present,
            "confidence": self.confidence,
            "last_seen_location": self.last_seen_location,
            "last_seen_timestamp": self.last_seen_timestamp.isoformat()
            if self.last_seen_timestamp
            else None,
        }


class IdentityPresenceService:
    """Service for identity-based presence detection.

    Integrates with:
    - UniFi cameras for face detection
    - Identity manager for face embeddings
    - Smart home presence system
    """

    def __init__(
        self,
        identity_dir: str = "assets/identities",
        presence_timeout_minutes: int = 30,
    ):
        """Initialize presence service.

        Args:
            identity_dir: Directory containing identity data
            presence_timeout_minutes: Minutes before marking someone as away
        """
        self.identity_dir = Path(identity_dir)
        self.presence_timeout = timedelta(minutes=presence_timeout_minutes)

        # Registered identities
        self._registered: dict[str, PresenceRecord] = {}

        # Face embeddings for matching
        self._embeddings: dict[str, np.ndarray] = {}

        # Load registered identities
        self._load_registrations()

    def _load_registrations(self):
        """Load identity registrations from disk."""
        registry_path = self.identity_dir / ".presence_registry.json"

        if registry_path.exists():
            with open(registry_path) as f:
                data = json.load(f)

            for name, info in data.get("registered", {}).items():
                identity_id = info.get("identity_id")

                self._registered[name] = PresenceRecord(
                    identity_id=identity_id,
                    name=name,
                )

                # Load face embedding
                self._load_embedding(name, identity_id)

    def _save_registrations(self):
        """Save identity registrations to disk."""
        registry_path = self.identity_dir / ".presence_registry.json"

        data = {
            "registered": {
                name: {
                    "identity_id": record.identity_id,
                    "name": record.name,
                }
                for name, record in self._registered.items()
            },
            "updated_at": datetime.now().isoformat(),
        }

        self.identity_dir.mkdir(parents=True, exist_ok=True)
        with open(registry_path, "w") as f:
            json.dump(data, f, indent=2)

    def _load_embedding(self, name: str, identity_id: str):
        """Load face embedding for identity."""
        embedding_path = self.identity_dir / identity_id / "faces" / "embeddings.npy"

        if embedding_path.exists():
            embeddings = np.load(embedding_path)
            # Use mean embedding
            self._embeddings[name] = np.mean(embeddings, axis=0)

    def register_identity(
        self,
        name: str,
        identity_id: str,
    ) -> bool:
        """Register an identity for presence detection.

        Args:
            name: Human-readable name (e.g., "Becky")
            identity_id: Identity ID from identity manager

        Returns:
            True if registration successful
        """
        # Verify identity exists
        identity_dir = self.identity_dir / identity_id
        if not identity_dir.exists():
            return False

        # Create presence record
        self._registered[name.lower()] = PresenceRecord(
            identity_id=identity_id,
            name=name,
        )

        # Load face embedding
        self._load_embedding(name.lower(), identity_id)

        # Save registrations
        self._save_registrations()

        # Link in identity metadata
        self._update_identity_link(identity_id, name)

        return True

    def unregister_identity(self, name: str) -> bool:
        """Unregister an identity from presence detection.

        Args:
            name: Identity name

        Returns:
            True if unregistration successful
        """
        name_lower = name.lower()

        if name_lower in self._registered:
            del self._registered[name_lower]

            if name_lower in self._embeddings:
                del self._embeddings[name_lower]

            self._save_registrations()
            return True

        return False

    def _update_identity_link(self, identity_id: str, name: str):
        """Update identity metadata with presence link."""
        meta_path = self.identity_dir / identity_id / "metadata.json"

        if meta_path.exists():
            with open(meta_path) as f:
                data = json.load(f)

            if "linked" not in data:
                data["linked"] = {}

            data["linked"]["presence_name"] = name
            data["linked"]["presence_registered"] = True

            with open(meta_path, "w") as f:
                json.dump(data, f, indent=2)

    async def is_identity_present(self, name: str) -> bool:
        """Check if a registered identity is present.

        Args:
            name: Identity name

        Returns:
            True if identity is currently present
        """
        name_lower = name.lower()

        if name_lower not in self._registered:
            return False

        record = self._registered[name_lower]

        # Check if recent enough
        if record.last_seen_timestamp:
            elapsed = datetime.now() - record.last_seen_timestamp
            if elapsed < self.presence_timeout:
                return record.is_present

        return False

    async def get_present_identities(self) -> list[str]:
        """Get list of currently present registered identities.

        Returns:
            List of names of present identities
        """
        present = []
        now = datetime.now()

        for _name, record in self._registered.items():
            if record.is_present and record.last_seen_timestamp:
                elapsed = now - record.last_seen_timestamp
                if elapsed < self.presence_timeout:
                    present.append(record.name)

        return present

    async def get_identity_location(self, name: str) -> str | None:
        """Get last known location of an identity.

        Args:
            name: Identity name

        Returns:
            Location string or None
        """
        name_lower = name.lower()

        if name_lower in self._registered:
            return self._registered[name_lower].last_seen_location

        return None

    async def update_presence(
        self,
        name: str,
        is_present: bool,
        location: str | None = None,
        confidence: float = 1.0,
    ):
        """Update presence state for an identity.

        Args:
            name: Identity name
            is_present: Whether identity is present
            location: Optional location name
            confidence: Detection confidence
        """
        name_lower = name.lower()

        if name_lower in self._registered:
            record = self._registered[name_lower]
            record.is_present = is_present
            record.confidence = confidence
            record.last_seen_timestamp = datetime.now()

            if location:
                record.last_seen_location = location

    def match_face(
        self,
        face_embedding: np.ndarray,
        threshold: float = 0.6,
    ) -> str | None:
        """Match a face embedding against registered identities.

        Args:
            face_embedding: 512-dim face embedding
            threshold: Cosine similarity threshold

        Returns:
            Name of matched identity or None
        """
        if not self._embeddings:
            return None

        best_match = None
        best_similarity = 0.0

        # Normalize query embedding
        query_norm = face_embedding / (np.linalg.norm(face_embedding) + 1e-8)

        for name, ref_embedding in self._embeddings.items():
            # Normalize reference embedding
            ref_norm = ref_embedding / (np.linalg.norm(ref_embedding) + 1e-8)

            # Cosine similarity
            similarity = float(np.dot(query_norm, ref_norm))

            if similarity > best_similarity and similarity > threshold:
                best_similarity = similarity
                best_match = name

        return best_match

    async def process_camera_detection(
        self,
        face_embedding: np.ndarray,
        camera_name: str,
    ) -> str | None:
        """Process a face detection from a camera.

        Args:
            face_embedding: Detected face embedding
            camera_name: Name of camera/location

        Returns:
            Name of matched identity or None
        """
        matched_name = self.match_face(face_embedding)

        if matched_name:
            await self.update_presence(
                name=matched_name,
                is_present=True,
                location=camera_name,
                confidence=0.9,
            )

        return matched_name

    def get_registered_identities(self) -> list[dict]:
        """Get list of all registered identities.

        Returns:
            List of identity info dictionaries
        """
        return [record.to_dict() for record in self._registered.values()]

    async def query_presence(self, query: str) -> dict:
        """Answer natural language presence queries.

        Supports queries like:
        - "Is Becky home?"
        - "Who is home?"
        - "Where is Tim?"

        Args:
            query: Natural language query

        Returns:
            Response dictionary
        """
        query_lower = query.lower()

        # "Who is home?" query
        if "who" in query_lower and ("home" in query_lower or "here" in query_lower):
            present = await self.get_present_identities()

            if present:
                return {
                    "type": "who_home",
                    "present": present,
                    "answer": f"{', '.join(present)} {'is' if len(present) == 1 else 'are'} home",
                }
            else:
                return {
                    "type": "who_home",
                    "present": [],
                    "answer": "No one from the registered identities is currently detected",
                }

        # "Is X home?" query
        for name in self._registered.keys():
            if name in query_lower:
                is_present = await self.is_identity_present(name)
                location = await self.get_identity_location(name)

                record = self._registered[name]

                if is_present:
                    answer = f"Yes, {record.name} is home"
                    if location:
                        answer += f" (last seen in {location})"
                else:
                    answer = f"No, {record.name} has not been detected recently"

                return {
                    "type": "is_home",
                    "name": record.name,
                    "is_present": is_present,
                    "location": location,
                    "answer": answer,
                }

        return {
            "type": "unknown",
            "answer": "I don't recognize that query. Try 'Who is home?' or 'Is [name] home?'",
        }


# Singleton instance
_presence_service: IdentityPresenceService | None = None


def get_identity_presence_service() -> IdentityPresenceService:
    """Get singleton identity presence service."""
    global _presence_service

    if _presence_service is None:
        _presence_service = IdentityPresenceService()

    return _presence_service


async def is_identity_home(name: str) -> bool:
    """Check if an identity is home.

    Args:
        name: Identity name

    Returns:
        True if present
    """
    service = get_identity_presence_service()
    return await service.is_identity_present(name)


async def who_is_home() -> list[str]:
    """Get list of who is currently home.

    Returns:
        List of present identity names
    """
    service = get_identity_presence_service()
    return await service.get_present_identities()
