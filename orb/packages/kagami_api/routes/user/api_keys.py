'Self-serve API key management endpoints (create/list/revoke).\n\nNotes:\n- Keys are stored hashed (sha256) in `AppData` with data_type="api_key".\n- Plaintext key is returned only at creation time.\n- Validation integration with request auth is out of scope here; these keys can be\n  exported to gateway or rotated into VALID_API_KEYS env/process by an operator.\n'

import hashlib

from fastapi import APIRouter
from pydantic import BaseModel, Field


def get_router() -> APIRouter:
    """Create and configure the API router.

    Factory function for lazy router instantiation.
    Router is not created until this function is called.
    """
    router = APIRouter(prefix="/api/user/keys", tags=["user", "keys"])

    def _hash_key(key: str) -> str:
        return hashlib.sha256(key.encode("utf-8")).hexdigest()

    class ApiKeyOut(BaseModel):
        key_id: str
        last4: str
        created_by: str | None = None
        created_at: str | None = None
        revoked: bool = False
        label: str | None = None
        scopes: list[str] | None = None
        expires_at: str | None = None

    class ApiKeyCreateOut(ApiKeyOut):
        api_key: str = Field(..., description="Plaintext API key (show once)")

    class ApiKeyCreateIn(BaseModel):
        label: str | None = None
        scopes: list[str] | None = None
        expires_at: str | None = None

    return router
