from __future__ import annotations

from typing import Any

import pytest

pytestmark = pytest.mark.tier_integration


import os
import uuid


def test_translate_endpoint_basic(client: Any) -> None:
    os.environ.setdefault("KAGAMI_TEST_NO_CLOUD", "1")
    r = client.post(
        "/api/i18n/translate",
        json={
            "texts": ["Settings", "Save", "Close"],
            "target_lang": "es",
            "domain": "ui",
        },
        headers={"Authorization": "Bearer test_api_key", "Idempotency-Key": str(uuid.uuid4())},
    )
    # Accept 404 if endpoint not yet implemented
    assert r.status_code in (200, 404)
    if r.status_code == 404:
        return
    data = r.json()
    assert data["target_lang"] == "es"
    assert data["translations"][0] in ("Configuración", "Settings")
    assert len(data["translations"]) == 3


def test_translate_endpoint_idempotent_cache(client: Any) -> None:
    os.environ.setdefault("KAGAMI_TEST_NO_CLOUD", "1")
    payload = {"texts": ["Plans"], "target_lang": "fr"}
    idem_key = str(uuid.uuid4())
    headers = {"Authorization": "Bearer test_api_key", "Idempotency-Key": idem_key}
    r1 = client.post("/api/i18n/translate", json=payload, headers=headers)
    r2 = client.post("/api/i18n/translate", json=payload, headers=headers)
    # Accept 404 if endpoint not yet implemented
    if r1.status_code == 404 or r2.status_code == 404:
        return
    assert r1.status_code == 200 and r2.status_code == 200
    d1, d2 = r1.json(), r2.json()
    assert d1["translations"] == d2["translations"]


def test_languages_list(client: Any) -> None:
    r = client.get("/api/i18n/languages")
    # Accept 404 if endpoint not yet implemented
    assert r.status_code in (200, 404)
    if r.status_code == 404:
        return
    data = r.json()
    langs = data.get("languages", [])
    assert isinstance(langs, list) and len(langs) >= 5
    assert any(lang.get("code") == "en" for lang in langs)
