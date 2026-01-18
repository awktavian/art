from __future__ import annotations

import os
from collections import OrderedDict
from pathlib import Path


class LRUFileCache:
    """Filesystem-backed LRU cache for character/world assets.

    Stores entries under a root directory. Keeps an in-memory LRU index of keys -> paths.
    Evicts least-recently-used entries when exceeding max_items or max_bytes.
    """

    def __init__(
        self,
        root_dir: str | Path,
        max_items: int = 128,
        max_bytes: int = 10_000_000_000,
    ) -> None:
        self.root = Path(root_dir)
        self.root.mkdir(parents=True, exist_ok=True)
        self.max_items = max_items
        self.max_bytes = max_bytes
        self.index: OrderedDict[str, Path] = OrderedDict()
        self.total_bytes = 0
        self._load_existing()

    def _load_existing(self) -> None:
        try:
            for p in self.root.glob("**/*"):
                if p.is_file():
                    key = p.relative_to(self.root).as_posix()
                    self.index[key] = p
                    self.total_bytes += p.stat().st_size
            # Order by mtime newest -> oldest; then reverse to LRU
            items = sorted(self.index.items(), key=lambda kv: kv[1].stat().st_mtime, reverse=True)
            self.index = OrderedDict(items)
        except Exception:
            pass

    def _evict_if_needed(self) -> None:
        # Evict by count
        while len(self.index) > self.max_items:
            _k, p = self.index.popitem(last=False)
            self._safe_remove(p)
        # Evict by bytes
        while self.total_bytes > self.max_bytes and self.index:
            _k, p = self.index.popitem(last=False)
            self._safe_remove(p)

    def _safe_remove(self, p: Path) -> None:
        try:
            sz = p.stat().st_size
        except Exception:
            sz = 0
        try:
            p.unlink(missing_ok=True)
        except Exception:
            pass
        self.total_bytes = max(0, self.total_bytes - sz)

    def put_bytes(self, key: str, data: bytes) -> Path:
        path = self.root / key
        path.parent.mkdir(parents=True, exist_ok=True)
        with open(path, "wb") as f:
            f.write(data)
        # Update index
        if key in self.index:
            self.index.move_to_end(key, last=True)
        self.index[key] = path
        self.total_bytes += path.stat().st_size
        self._evict_if_needed()
        return path

    def has(self, key: str) -> bool:
        return key in self.index and self.index[key].exists()

    def get_path(self, key: str) -> Path | None:
        p = self.index.get(key)
        if p and p.exists():
            # Touch for LRU
            self.index.move_to_end(key, last=True)
            try:
                os.utime(p, None)
            except Exception:
                pass
            return p
        return None

    def put_file(self, key: str, src_path: str | Path) -> Path:
        p = Path(src_path)
        data = p.read_bytes()
        return self.put_bytes(key, data)
