import json
import logging
from collections.abc import Iterable
from pathlib import Path
from typing import Any

from kagami.forge.schema import Character

logger = logging.getLogger(__name__)


class PersistenceManager:
    """Filesystem-backed character persistence with in-memory cache.

    Characters are stored as JSON in ~/.kagami/characters/<character_id>.json.
    This provides real persistence for development and production without
    requiring a database. An in-memory cache accelerates repeated reads.
    """

    def __init__(self, storage_dir: Path | None = None) -> None:
        self._characters: dict[str, Character] = {}
        # Use temp storage when KAGAMI_TEST_TEMP_STORAGE is provided (for tests)
        import os

        from kagami.core.utils.paths import get_user_kagami_dir

        test_dir = os.getenv("KAGAMI_TEST_TEMP_STORAGE")
        base_dir = Path(test_dir) if test_dir else (get_user_kagami_dir() / "characters")
        self._storage_dir: Path = storage_dir or base_dir
        try:
            self._storage_dir.mkdir(parents=True, exist_ok=True)
        except Exception as e:
            logger.error(f"Failed to ensure character storage directory: {e}")
        logger.info("PersistenceManager initialized (filesystem-backed)")
        # Best-effort wiring: listen for character feedback events on the unified bus.
        # This enables persistence-backed "growth" updates driven by `character.feedback`.
        try:
            wire_character_feedback_to_bus()
        except Exception:
            pass

    # ------------------------- Index helpers -------------------------
    def _index_path(self) -> Path:
        return self._storage_dir / "index.json"

    def _load_index(self) -> dict[str, Any]:
        path = self._index_path()
        if not path.exists():
            return {"characters": {}}
        try:
            import json as _json

            with path.open("r", encoding="utf-8") as f:
                data = _json.load(f)
            if not isinstance(data, dict):
                return {"characters": {}}
            data.setdefault("characters", {})
            return data
        except Exception:
            return {"characters": {}}

    def _write_index(self, index: dict[str, Any]) -> None:
        try:
            import json as _json

            with self._index_path().open("w", encoding="utf-8") as f:
                _json.dump(index, f, ensure_ascii=False)
        except Exception as e:
            logger.debug(f"Index write failed (non-fatal): {e}")

    def _summarize_personality(self, character: "Character") -> str:
        try:
            pers = getattr(character, "personality", None)
            if isinstance(pers, dict):
                traits = pers.get("traits", [])
            else:
                traits = getattr(pers, "traits", []) if pers else []
            return ", ".join([str(t) for t in traits][:6])
        except Exception:
            return ""

    def _update_index_for(self, character: "Character") -> None:
        try:
            idx = self._load_index()
            c = character
            from datetime import date as _date
            from datetime import datetime as _dt

            _ca = getattr(c, "created_at", None)
            if isinstance(_ca, (_dt, _date)):
                _created_iso: str | None = _ca.isoformat()
            else:
                _created_iso = None
            record = {
                "id": c.character_id,
                "name": c.name,
                "concept": c.concept,
                "created_at": _created_iso,
                "last_updated": __import__("datetime").datetime.utcnow().isoformat(),
                "personality_summary": self._summarize_personality(c),
                "tags": list(getattr(c, "tags", []) or []),
            }
            idx.setdefault("characters", {})[c.character_id] = record
            self._write_index(idx)
        except Exception as e:
            logger.debug(f"Index update skipped: {e}")

    def _path_for(self, character_id: str) -> Path:
        return self._storage_dir / f"{character_id}.json"

    async def save_character(self, character: Character) -> bool:
        """Persist a character to disk and cache.

        Args:
            character: Character object to save

        Returns:
            True on success, False on failure

        Raises:
            ValueError: If character is invalid
        """
        # Input validation
        if not isinstance(character, Character):
            raise ValueError(f"Expected Character object, got {type(character).__name__}")

        if not character.character_id:
            raise ValueError("Character must have a character_id")

        if not character.name or not character.name.strip():
            raise ValueError("Character must have a non-empty name")

        try:
            data = character.to_dict()

            # Ensure datetimes are serialized as ISO strings
            def _default(o: Any) -> Any:
                try:
                    import datetime as _dt

                    if isinstance(o, (_dt.datetime, _dt.date)):
                        return o.isoformat()
                except Exception:
                    pass
                # Support Enum types by serializing to value
                try:
                    from enum import Enum

                    if isinstance(o, Enum):
                        return o.value
                except Exception:
                    pass
                raise TypeError(
                    f"Object of type {type(o).__name__} is not JSON serializable"
                ) from None

            # Avoid dumping large binary arrays directly; rely on dataclass dict[str, Any]
            # representation which should already be JSON-serializable for tests.
            path = self._path_for(character.character_id)
            with path.open("w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False, default=_default)
            self._characters[character.character_id] = character
            logger.info(f"Character {character.character_id} saved to {path}.")
            # Update index (best-effort)
            try:
                self._update_index_for(character)
            except Exception:
                pass
            return True
        except Exception as e:
            logger.error(f"Failed to save character {character.character_id}: {e}")
            return False

    async def load_character(self, character_id: str) -> Character | None:
        """Load a character from disk or cache."""
        try:
            # Always read from disk to avoid stale in-memory cache across processes
            path = self._path_for(character_id)
            if not path.exists():
                logger.warning(f"Character {character_id} not found at {path}.")
                return None
            with path.open("r", encoding="utf-8") as f:
                data = json.load(f)
            character = Character.from_dict(data)
            self._characters[character_id] = character
            logger.info(f"Character {character_id} loaded from {path}.")
            return character
        except Exception as e:
            logger.error(f"Failed to load character {character_id}: {e}")
            return None

    async def list_characters(self, limit: int = 50, offset: int = 0) -> list[Character]:
        """List characters by reading metadata from disk.

        Loads minimal data to construct Character objects and applies pagination.
        """
        try:
            # Only include character JSON files, skip index and other metadata files
            all_ids = [
                p.stem for p in sorted(self._storage_dir.glob("*.json")) if p.name != "index.json"
            ]
            selected_ids = all_ids[offset : offset + limit]

            # Load from cache when available; otherwise read from disk
            def _load_many(ids: Iterable[str]) -> list[Character]:
                out: list[Character] = []
                for cid in ids:
                    if cid in self._characters:
                        out.append(self._characters[cid])
                        continue
                    path = self._path_for(cid)
                    try:
                        with path.open("r", encoding="utf-8") as f:
                            data = json.load(f)
                        ch = Character.from_dict(data)
                        self._characters[cid] = ch
                        out.append(ch)
                    except Exception as e:
                        logger.warning(f"Skipping character {cid}: {e}")
                return out

            return _load_many(selected_ids)
        except Exception as e:
            logger.error(f"Failed to list[Any] characters: {e}")
            return []

    async def save_world_export(
        self,
        *,
        session_id: str,
        export_path: str | None,
        package_path: str | None,
        manifest: dict[str, Any] | None = None,
    ) -> bool:
        """Persist a world export record for creative tool re-use.

        Records a small JSON alongside character artifacts directory so Forge editors
        can discover the last export for a session.
        """
        try:
            base_dir = self._storage_dir / "world_exports"
            base_dir.mkdir(parents=True, exist_ok=True)
            out = base_dir / f"{session_id}.json"
            rec = {
                "session_id": session_id,
                "export_path": export_path,
                "package_path": package_path,
                "manifest": manifest or {},
                "saved_at": __import__("datetime").datetime.utcnow().isoformat(),
            }
            with out.open("w", encoding="utf-8") as f:
                json.dump(rec, f, ensure_ascii=False, indent=2)
            return True
        except Exception as e:
            logger.debug(f"save_world_export failed: {e}")
            return False

    async def delete_character(self, character_id: str) -> bool:
        """Delete a character from disk and cache."""
        try:
            path = self._path_for(character_id)
            if path.exists():
                path.unlink()
            if character_id in self._characters:
                del self._characters[character_id]
            logger.info(f"Character {character_id} deleted.")
            # Remove from index (best-effort)
            try:
                idx = self._load_index()
                chars = idx.get("characters", {})
                if character_id in chars:
                    del chars[character_id]
                    idx["characters"] = chars
                    self._write_index(idx)
            except Exception:
                pass
            return True
        except Exception as e:
            logger.error(f"Failed to delete character {character_id}: {e}")
            return False

    async def search_characters(self, search_term: str) -> list[Character]:
        """Search characters by name or concept across stored records."""
        term = (search_term or "").lower()
        results: list[Character] = []
        try:
            for path in self._storage_dir.glob("*.json"):
                try:
                    with path.open("r", encoding="utf-8") as f:
                        data = json.load(f)
                    name = str(data.get("name", "")).lower()
                    concept = str(data.get("concept", "")).lower()
                    if term in name or term in concept:
                        ch = Character.from_dict(data)
                        results.append(ch)
                except Exception:
                    continue
            logger.info(f"Found {len(results)} characters for search term '{search_term}'.")
            return results
        except Exception as e:
            logger.error(f"Search failed: {e}")
            return []

    # ------------------------- Personality growth -------------------------
    async def update_character_growth(self, character_id: str, feedback: dict[str, Any]) -> bool:
        """Apply growth feedback to a character profile and persist with versioning.

        - Increments metadata.version (stored under metadata['version'])
        - Appends entry to metadata['growth_history'] with timestamp and feedback keys
        - Optionally adjusts traits: add/remove simple strings via feedback
          keys: {"add_traits": [...], "remove_traits": [...]} (best-effort)
        """
        try:
            ch = await self.load_character(character_id)
            if ch is None:
                logger.warning(f"Character {character_id} not found for growth update")
                return False

            # Initialize metadata structures
            meta = getattr(ch, "metadata", {}) or {}
            version = int(meta.get("version", 0)) + 1
            meta["version"] = version
            history = list(meta.get("growth_history", []) or [])
            history.append(
                {
                    "ts": __import__("datetime").datetime.utcnow().isoformat(),
                    "feedback": {k: v for k, v in (feedback or {}).items() if k},
                }
            )
            meta["growth_history"] = history

            # Simple personality adaptation
            try:
                pers = getattr(ch, "personality", None)
                traits = []
                if isinstance(pers, dict):
                    traits = list(pers.get("traits", []) or [])
                else:
                    traits = list(getattr(pers, "traits", []) or [])
                add = list((feedback or {}).get("add_traits", []) or [])
                rem = list((feedback or {}).get("remove_traits", []) or [])
                for t in add:
                    if t not in traits:
                        traits.append(t)
                traits = [t for t in traits if t not in rem]
                if isinstance(pers, dict):
                    pers["traits"] = traits
                    ch.personality = pers
                elif pers is not None:
                    try:
                        pers.traits = traits
                    except Exception:
                        pass
            except Exception:
                pass

            ch.metadata = meta
            saved = await self.save_character(ch)
            if not bool(saved):
                logger.error(
                    f"Growth update save failed for character {character_id}; rolling back in-memory only"
                )
                return False
            return True
        except Exception as e:
            logger.error(f"Growth update failed: {e}")
            return False


# =============================================================================
# UnifiedE8Bus wiring: character feedback → personality growth
# =============================================================================

_CHARACTER_FEEDBACK_WIRED: bool = False
_PERSISTENCE_SINGLETON_KEY: str | None = None
_PERSISTENCE_SINGLETON: PersistenceManager | None = None


def _persistence_key() -> str:
    import os

    return os.getenv("KAGAMI_TEST_TEMP_STORAGE") or "<default>"


def get_persistence_manager() -> PersistenceManager:
    """Get a process-local PersistenceManager singleton.

    This is used by event handlers so background event updates always target the
    active storage root (tests may override via KAGAMI_TEST_TEMP_STORAGE).
    """
    global _PERSISTENCE_SINGLETON, _PERSISTENCE_SINGLETON_KEY
    key = _persistence_key()
    if _PERSISTENCE_SINGLETON is None or key != _PERSISTENCE_SINGLETON_KEY:
        _PERSISTENCE_SINGLETON = PersistenceManager()
        _PERSISTENCE_SINGLETON_KEY = key
    return _PERSISTENCE_SINGLETON


def wire_character_feedback_to_bus() -> bool:
    """Subscribe to `character.feedback` and apply growth updates.

    Event payload shape:
        {"character_id": "...", "feedback": {...}}
    """
    global _CHARACTER_FEEDBACK_WIRED
    if _CHARACTER_FEEDBACK_WIRED:
        return True
    try:
        from kagami.core.events import get_unified_bus

        bus = get_unified_bus()

        async def _on_feedback(event: Any) -> None:
            try:
                payload = getattr(event, "payload", None) or {}
                character_id = payload.get("character_id")
                feedback = payload.get("feedback") or {}
                if not character_id or not isinstance(feedback, dict):
                    return
                pm = get_persistence_manager()
                await pm.update_character_growth(str(character_id), feedback)
            except Exception:
                # Best-effort: feedback updates should never take down the bus.
                return

        bus.subscribe("character.feedback", _on_feedback)
        _CHARACTER_FEEDBACK_WIRED = True
        logger.info("✅ Character feedback wired to UnifiedE8Bus (growth enabled)")
        return True
    except Exception as e:
        logger.debug(f"Character feedback bus wiring skipped: {e}")
        return False
