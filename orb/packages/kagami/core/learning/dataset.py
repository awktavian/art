from __future__ import annotations

"""JSONL dataset writer with de-duplication and basic PII redaction.

- Appends records to JSONL files under a base directory
- Maintains a small in-memory fingerprint cache to avoid exact dupes
"""
import json
import os
import re
import threading
from pathlib import Path
from typing import Any

_LOCK = threading.RLock()
_SEEN: set[str] = set()


def _redact_pii(text: str) -> str:
    try:
        t = text
        # Emails
        t = re.sub(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}", "[redacted-email]", t)
        # Phone numbers simple patterns
        t = re.sub(r"\b\+?\d[\d\-\s()]{7,}\b", "[redacted-phone]", t)
        # Credit-card like
        t = re.sub(r"\b(?:\d[ -]*?){13,19}\b", "[redacted-card]", t)
        return t
    except Exception:
        return text


class DatasetWriter:
    def __init__(self, base_dir: str) -> None:
        self.base_dir = base_dir

    def append(self, rel_path: str, record: dict[str, Any]) -> None:
        os.makedirs(self.base_dir, exist_ok=True)
        path = Path(self.base_dir) / rel_path
        os.makedirs(path.parent, exist_ok=True)
        # De-dup by optional 'fingerprint' or reconstruct simple hash
        fp = None
        try:
            fp = str(record.get("fingerprint") or record.get("fp") or "")
        except Exception:
            fp = None
        if not fp:
            try:
                core = json.dumps(record, sort_keys=True)[:2048]
                import hashlib as _h

                fp = _h.sha256(core.encode("utf-8")).hexdigest()
            except Exception:
                fp = None
        line_obj = dict(record)
        # Redact common PII in string fields
        try:
            for k, v in list(line_obj.items()):
                if isinstance(v, str) and v:
                    line_obj[k] = _redact_pii(v)
        except Exception:
            pass
        if fp:
            line_obj.setdefault("fingerprint", fp)
        data = json.dumps(line_obj, ensure_ascii=False)
        with _LOCK:
            if fp and fp in _SEEN:
                return
            with open(path, "a", encoding="utf-8") as f:
                f.write(data + "\n")
            if fp:
                _SEEN.add(fp)


__all__ = ["DatasetWriter"]
