
from __future__ import annotations


import os
import uuid

import httpx
import pytest

API_URL = os.getenv("KAGAMI_API", "http://127.0.0.1:8000")


def test_mobiasm_infer_smoke() -> None:
    # Check if MobiASM service is available
    try:
        with httpx.Client(timeout=2.0) as test_client:
            test_client.get(f"{API_URL}/health")
    except (httpx.ConnectError, httpx.TimeoutException):
        pytest.skip(f"K os API not running at {API_URL}")

    idem = uuid.uuid4().hex
    payload = {"input": [[0.0] * 32 for _ in range(2)], "return_all_layers": False}
    with httpx.Client(timeout=30.0) as client:
        r = client.post(
            f"{API_URL}/mobiasm/infer",
            headers={
                "Authorization": f"Bearer {os.getenv('KAGAMI_API_KEY', 'dev')}",
                "Idempotency-Key": idem,
            },
            json=payload,
        )
        assert r.status_code in (200, 403), r.text  # 403 allowed if CBF blocks
        if r.status_code == 200:
            body = r.json()
            assert "output" in body and "processing_time_ms" in body

        # Replay with same idempotency key should be conflict or replayed
        r2 = client.post(
            f"{API_URL}/mobiasm/infer",
            headers={
                "Authorization": f"Bearer {os.getenv('KAGAMI_API_KEY', 'dev')}",
                "Idempotency-Key": idem,
            },
            json=payload,
        )
        assert r2.status_code in (200, 409), r2.text
