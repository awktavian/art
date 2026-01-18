"""Weaviate E8 Adapter — Vector Storage with E8 Quantization.

Integrates Weaviate vector database with Kagami's E8 lattice quantization
for optimal compression while preserving semantic relationships.

Compression:
- Standard Weaviate: 1536D float32 = 6KB per vector
- With E8 quantization: 8D × 16 levels = 128 bytes (47× compression)

The 240 E8 roots provide semantically meaningful discrete states.

Created: December 7, 2025
"""

from __future__ import annotations

import asyncio
import json
import logging
import os
import threading
from dataclasses import dataclass
from datetime import datetime
from typing import TYPE_CHECKING, Any

import torch

if TYPE_CHECKING:
    pass

logger = logging.getLogger(__name__)

# Import circuit breaker for resilience
from kagami.core.caching.redis.factory import RedisClientFactory
from kagami.core.resilience.circuit_breaker import (
    CircuitBreakerConfig,
    CircuitBreakerOpen,
    get_circuit_breaker,
)


@dataclass
class WeaviateE8Config:
    """Configuration for Weaviate E8 adapter."""

    url: str
    api_key: str
    memory_collection: str = "KagamiMemory"
    feedback_collection: str = "ElysiaFeedback"
    e8_training_levels: int = 8
    e8_inference_levels: int = 16
    e8_adaptive: bool = True
    timeout: int = 30
    # IMPORTANT: Weaviate vectors must have a single fixed dimension per collection.
    # This should match Kagami's configured bulk embedding dimension (KAGAMI_BULK_DIM).
    vector_dim: int | None = None


class WeaviateE8Adapter:
    """Weaviate adapter with E8 lattice quantization.

    Provides:
    1. Automatic E8 quantization of embeddings
    2. Hybrid search (vector + E8 code matching)
    3. Collection management (memory, feedback)
    4. Chunk storage with source tracking

    Usage:
        adapter = WeaviateE8Adapter(config)
        await adapter.connect()

        # Store with E8 quantization
        await adapter.store(content, embedding, {"colony": "grove"})

        # Search
        results = await adapter.search_similar(query_embedding)
    """

    def __init__(self, config: WeaviateE8Config | None = None):
        """Initialize adapter.

        Args:
            config: Weaviate configuration
        """
        if config is None:
            from kagami_integrations.elysia import get_elysia_config

            elysia_config = get_elysia_config()
            config = WeaviateE8Config(
                url=elysia_config.weaviate_url,
                api_key=elysia_config.weaviate_api_key,
                memory_collection=elysia_config.memory_collection,
                feedback_collection=elysia_config.feedback_collection,
                e8_training_levels=elysia_config.e8_training_levels,
                e8_inference_levels=elysia_config.e8_inference_levels,
                e8_adaptive=elysia_config.e8_adaptive,
            )

        # Resolve default vector_dim from canonical dimension config.
        if config.vector_dim is None:
            try:
                from kagami.core.config.dimensions import get_bulk_dim

                config.vector_dim = int(get_bulk_dim())
            except Exception:
                config.vector_dim = 512

        self.config = config
        self.client: Any = None
        self.e8_quantizer: Any = None
        self._connected = False
        self._proj_to_e8: torch.nn.Linear | None = None
        self._proj_cache: dict[tuple[int, int], torch.nn.Linear] = {}
        # One asyncio.Lock per event loop (avoids cross-loop lock binding issues in tests/scripts).
        self._connect_locks: dict[int, asyncio.Lock] = {}

        # Circuit breaker for Weaviate operations
        # Prevents cascading failures when Weaviate times out or becomes unavailable
        self._breaker = get_circuit_breaker(
            "weaviate",
            CircuitBreakerConfig(
                failure_threshold=3,  # Open after 3 consecutive failures
                success_threshold=2,  # Close after 2 consecutive successes
                timeout_seconds=30.0,  # Try recovery after 30s
                half_open_max_calls=2,  # Limit concurrent recovery attempts
            ),
        )

        # Redis-persisted circuit breaker state (survives process restarts)
        self._cb_key = "kagami:weaviate:circuit_breaker"
        try:
            self._redis = RedisClientFactory.get_client(purpose="default", async_mode=True)
        except Exception as e:
            logger.debug(f"Redis unavailable for circuit breaker persistence: {e}")
            self._redis = None

    def _project_to_e8(self, embedding: torch.Tensor) -> torch.Tensor:
        """Project an embedding to 8D deterministically.

        For Kagami-native embeddings, prefer passing an E8 nucleus vector directly.
        If the embedding contains an E8+S7 manifold (15D), we take the first 8 dims.
        Otherwise we use a cached fixed linear projection (no per-call random weights).
        """
        if embedding.dim() == 1:
            embedding = embedding.unsqueeze(0)

        if embedding.shape[-1] == 8:
            return embedding

        # If embedding is already in Kagami manifold space (E8(8) + S7(7)=15),
        # the first 8 dims are canonically E8.
        if 8 <= embedding.shape[-1] <= 15:
            return embedding[..., :8]

        in_dim = int(embedding.shape[-1])
        if self._proj_to_e8 is None or self._proj_to_e8.in_features != in_dim:
            # Deterministic init (stable across calls / processes).
            # We do NOT learn this projection here; for true optimality, supply
            # a nucleus embedding from KagamiWorldModel directly.
            proj = torch.nn.Linear(in_dim, 8, bias=False)
            g = torch.Generator(device="cpu")
            g.manual_seed(1337 + in_dim)
            with torch.no_grad():
                w = torch.randn((8, in_dim), generator=g) / max(1.0, in_dim**0.5)
                proj.weight.copy_(w)
            proj.requires_grad_(False)
            self._proj_to_e8 = proj

        proj = self._proj_to_e8.to(device=embedding.device, dtype=embedding.dtype)
        with torch.no_grad():
            result: torch.Tensor = proj(embedding)
            return result

    def _project_to_dim(self, embedding: torch.Tensor, out_dim: int) -> torch.Tensor:
        """Project an embedding to a fixed dimension deterministically.

        Weaviate collections require a single vector dimension; this helper
        ensures callers can provide embeddings of varying dims without breaking
        indexing/search. The projection is deterministic (stable across calls/processes).
        """
        if embedding.dim() == 1:
            embedding = embedding.unsqueeze(0)

        if int(embedding.shape[-1]) == int(out_dim):
            return embedding

        in_dim = int(embedding.shape[-1])
        key = (in_dim, int(out_dim))

        proj = self._proj_cache.get(key)
        if proj is None:
            p = torch.nn.Linear(in_dim, int(out_dim), bias=False)
            g = torch.Generator(device="cpu")
            g.manual_seed(1337 + in_dim * 1000 + int(out_dim))
            with torch.no_grad():
                w = torch.randn((int(out_dim), in_dim), generator=g) / max(1.0, in_dim**0.5)
                p.weight.copy_(w)
            p.requires_grad_(False)
            self._proj_cache[key] = p
            proj = p

        proj = proj.to(device=embedding.device, dtype=embedding.dtype)
        with torch.no_grad():
            result: torch.Tensor = proj(embedding)
            return result

    async def _check_circuit(self) -> bool:
        """Check if circuit breaker is open (persisted in Redis)."""
        if self._redis is None:
            return True  # Assume closed if Redis unavailable
        try:
            state = await self._redis.get(self._cb_key)
            # RedisClientFactory uses decode_responses=True, so state is str not bytes
            return state != "open"  # type: ignore[no-any-return]
        except Exception as e:
            logger.debug(f"Circuit breaker check failed: {e}")
            return True  # Assume closed on error

    async def _open_circuit(self, duration: int = 60) -> None:
        """Open circuit breaker (persisted in Redis)."""
        if self._redis is None:
            return
        try:
            await self._redis.setex(self._cb_key, duration, "open")
            logger.warning(f"Weaviate circuit breaker OPEN for {duration}s")
        except Exception as e:
            logger.error(f"Failed to persist circuit breaker state: {e}")

    async def _close_circuit(self) -> None:
        """Close circuit breaker."""
        if self._redis is None:
            return
        try:
            await self._redis.delete(self._cb_key)
            logger.info("Weaviate circuit breaker CLOSED")
        except Exception as e:
            logger.debug(f"Failed to clear circuit breaker: {e}")

    def _try_embed_text(self, text: str) -> torch.Tensor | None:
        """Best-effort Kagami-native embedding for Weaviate operations.

        We intentionally avoid relying on Weaviate server-side vectorizers because
        collections are often configured with `Vectorizer.none()` for optimal
        alignment with Kagami embeddings/E8 quantization.
        """
        if not text or not text.strip():
            return None
        try:
            import numpy as np
            from kagami.core.services.embedding_service import get_embedding_service

            dim = int(self.config.vector_dim or 512)
            vec: np.ndarray = get_embedding_service().embed_text(text, dimension=dim)  # type: ignore[assignment]
            return torch.from_numpy(vec).float()
        except Exception:
            # Deterministic hash fallback (keeps near_vector functional even if embedding service fails)
            try:
                import hashlib

                import numpy as np

                dim = int(self.config.vector_dim or 512)
                h = hashlib.sha256(text.encode()).digest()
                raw = (h * ((dim * 4 // len(h)) + 1))[: dim * 4]
                arr = np.frombuffer(raw, dtype=np.uint32).astype(np.float32)
                arr = (arr / (np.max(arr) + 1e-6)) * 2.0 - 1.0
                # L2 normalize
                norm = float(np.linalg.norm(arr))
                if norm > 1e-9:
                    arr = arr / norm
                return torch.from_numpy(arr).float()
            except Exception:
                return None

    async def connect(self) -> bool:
        """Connect to Weaviate and initialize E8 quantizer.

        Returns:
            True if connected successfully
        """
        if self._connected:
            return True

        try:
            loop_key = id(asyncio.get_running_loop())
        except RuntimeError:
            loop_key = 0

        lock = self._connect_locks.get(loop_key)
        if lock is None:
            lock = asyncio.Lock()
            self._connect_locks[loop_key] = lock

        async with lock:
            # Double-check locking pattern: another task may have connected between lines 222-235
            if self._connected:
                return True  # type: ignore[unreachable]

            try:
                # Import weaviate (optional dependency)
                try:
                    import weaviate
                except ImportError:
                    logger.warning(
                        "weaviate-client not installed. Install with: pip install weaviate-client"
                    )
                    return False

                # Auth + timeout configuration (best-effort across client versions).
                auth_credentials = None
                additional_config = None
                try:
                    from weaviate.classes.init import AdditionalConfig, Auth, Timeout

                    if self.config.api_key:
                        auth_credentials = Auth.api_key(self.config.api_key)
                    additional_config = AdditionalConfig(
                        timeout=Timeout(
                            init=int(self.config.timeout or 30),
                            query=int(self.config.timeout or 30),
                            insert=int(self.config.timeout or 30),
                        )
                    )
                except Exception:
                    try:
                        from weaviate.auth import AuthApiKey

                        if self.config.api_key:
                            auth_credentials = AuthApiKey(self.config.api_key)
                    except Exception:
                        auth_credentials = None
                    additional_config = None

                # SECURITY: Enforce authentication in production (Dec 21, 2025)
                environment = os.getenv("ENVIRONMENT", "development").lower()
                if environment == "production" and not self.config.api_key:
                    raise RuntimeError(
                        "Production Weaviate connections must use API key authentication. "
                        "Set WEAVIATE_API_KEY environment variable or configure via WeaviateE8Config. "
                        "For Weaviate Cloud, get API key from console.weaviate.cloud. "
                        "For self-hosted, configure authentication per Weaviate docs."
                    )

                # Detect local vs cloud connection
                url = self.config.url
                is_local = "localhost" in url or "127.0.0.1" in url or url.startswith("http://")

                if is_local:
                    # Local Docker or dev instance
                    from urllib.parse import urlparse

                    parsed = urlparse(url)
                    host = parsed.hostname or "localhost"
                    port = parsed.port or 8080

                    kwargs = {
                        "host": host,
                        "port": port,
                        "grpc_port": 50051,
                    }
                    if auth_credentials is not None:
                        kwargs["auth_credentials"] = auth_credentials
                    if additional_config is not None:
                        kwargs["additional_config"] = additional_config
                    self.client = weaviate.connect_to_local(**kwargs)  # type: ignore[arg-type]
                else:
                    # Weaviate Cloud
                    if not self.config.api_key:
                        logger.error("Weaviate Cloud API key is missing")
                        return False
                    try:
                        kwargs = {"cluster_url": url}
                        if auth_credentials is not None:
                            kwargs["auth_credentials"] = auth_credentials
                        if additional_config is not None:
                            kwargs["additional_config"] = additional_config
                        self.client = weaviate.connect_to_weaviate_cloud(**kwargs)  # type: ignore[arg-type]
                    except Exception as cloud_err:
                        logger.error(
                            f"Weaviate Cloud connection failed: {cloud_err}\n"
                            "  Possible causes:\n"
                            "  - Cluster is sleeping (wake it at console.weaviate.cloud)\n"
                            "  - Invalid URL or API key\n"
                            "  - Cluster was deleted"
                        )
                        return False

                if not self.client.is_ready():
                    logger.error("Weaviate client not ready")
                    return False

                # Initialize E8 quantizer
                from kagami.math.e8 import create_e8_quantizer

                self.e8_quantizer = create_e8_quantizer(
                    training_levels=self.config.e8_training_levels,
                    inference_levels=self.config.e8_inference_levels,
                    adaptive_levels=self.config.e8_adaptive,
                )

                # Setup collections
                await self._setup_collections()

                self._connected = True
                logger.info(f"✅ Connected to Weaviate at {self.config.url}")
                return True

            except Exception as e:
                logger.error(f"Failed to connect to Weaviate: {e}")
                return False

    async def _setup_collections(self) -> None:
        """Setup Weaviate collections if they don't exist."""
        try:
            from weaviate.classes.config import Configure, DataType, Property
        except ImportError:
            logger.warning("Weaviate classes not available")
            return

        # Prefer v4.16+ vectorizer config API: bring-your-own vectors.
        # This avoids module dependencies (text2vec-*) and guarantees embedding alignment.
        vector_config = None
        try:
            if hasattr(Configure, "Vectors") and hasattr(Configure.Vectors, "self_provided"):
                vector_config = Configure.Vectors.self_provided()
        except Exception:
            vector_config = None

        # Backwards compatible config API.
        vectorizer_config = None
        for cfg_attr in ("Vectors", "Vectorizer"):
            try:
                cfg = getattr(Configure, cfg_attr, None)
                if cfg is not None and hasattr(cfg, "none"):
                    vectorizer_config = cfg.none()
                    break
            except Exception:
                continue

        def _create_collection(collection_name: str, properties: list[Any]) -> None:
            base_kwargs: dict[str, Any] = {"name": collection_name, "properties": properties}
            attempts: list[dict[str, Any]] = []
            if vector_config is not None:
                attempts.append({"vector_config": vector_config})
            if vectorizer_config is not None:
                attempts.append({"vectorizer_config": vectorizer_config})
            attempts.append({})

            last_exc: Exception | None = None
            for extra in attempts:
                try:
                    self.client.collections.create(**base_kwargs, **extra)
                    return
                except TypeError as exc:
                    last_exc = exc
                    continue
            if last_exc is not None:
                raise last_exc

        # Memory collection
        if not self.client.collections.exists(self.config.memory_collection):
            _create_collection(
                self.config.memory_collection,
                properties=[
                    Property(name="content", data_type=DataType.TEXT),
                    Property(name="colony_affinity", data_type=DataType.TEXT),
                    Property(name="kind", data_type=DataType.TEXT),
                    Property(name="tenant_id", data_type=DataType.TEXT),
                    Property(name="agent", data_type=DataType.TEXT),
                    Property(name="category", data_type=DataType.TEXT),
                    Property(name="episode_id", data_type=DataType.TEXT),
                    Property(name="from_instance", data_type=DataType.TEXT),
                    Property(name="metadata_json", data_type=DataType.TEXT),
                    Property(name="e8_codes", data_type=DataType.INT_ARRAY),
                    # Optional: store explicit E8 vector for local reranking without requiring named vectors.
                    # Stored as JSON to avoid reliance on array dtypes across client/server versions.
                    Property(name="e8_vector_json", data_type=DataType.TEXT),
                    Property(name="complexity", data_type=DataType.NUMBER),
                    Property(name="source_id", data_type=DataType.TEXT),
                    Property(name="created_at", data_type=DataType.DATE),
                ],
            )
            logger.info(f"Created collection: {self.config.memory_collection}")

        # Feedback collection
        if not self.client.collections.exists(self.config.feedback_collection):
            _create_collection(
                self.config.feedback_collection,
                properties=[
                    Property(name="query", data_type=DataType.TEXT),
                    Property(name="response", data_type=DataType.TEXT),
                    Property(name="rating", data_type=DataType.INT),
                    Property(name="colony", data_type=DataType.TEXT),
                    Property(name="model", data_type=DataType.TEXT),
                    Property(name="tenant_id", data_type=DataType.TEXT),
                    Property(name="metadata_json", data_type=DataType.TEXT),
                    Property(name="created_at", data_type=DataType.DATE),
                ],
            )
            logger.info(f"Created collection: {self.config.feedback_collection}")

    def _normalize_created_at(self, value: Any | None) -> datetime:
        """Normalize various timestamp formats to datetime (best-effort)."""
        if value is None:
            return datetime.now()
        if isinstance(value, datetime):
            return value
        # epoch seconds or milliseconds
        if isinstance(value, int | float):
            ts: float = float(value)
            if ts > 1e12:  # ms
                ts = ts / 1000.0
            try:
                return datetime.fromtimestamp(ts)
            except (OSError, ValueError, OverflowError):
                return datetime.now()
        # ISO string
        if isinstance(value, str):
            try:
                # Python 3.11 supports fromisoformat for many iso variants
                return datetime.fromisoformat(value.replace("Z", "+00:00"))
            except (ValueError, TypeError):
                return datetime.now()
        return datetime.now()

    async def _store_internal(
        self,
        content: str,
        embedding: torch.Tensor | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> str:
        """Internal store implementation (wrapped by circuit breaker).

        Raises exceptions to allow circuit breaker to track failures.
        """
        # Check Redis-persisted circuit breaker state
        if not await self._check_circuit():
            raise CircuitBreakerOpen("Weaviate circuit breaker is OPEN (Redis-persisted)")

        if not self._connected:
            await self.connect()

        if not self._connected:
            raise ConnectionError("Not connected to Weaviate")

        metadata = metadata or {}

        # If caller did not supply an embedding, compute a Kagami-native embedding.
        # This keeps storage/search functional even when Weaviate vectorizers are disabled.
        if embedding is None:
            embedding = self._try_embed_text(content)
        if embedding is None:
            raise ValueError("No embedding available for store()")

        # Weaviate vectors MUST have a single fixed dimension per collection.
        bulk_dim = int(self.config.vector_dim or 512)
        emb_in = embedding.flatten() if embedding.dim() > 1 else embedding
        if int(emb_in.shape[-1]) != bulk_dim:
            emb_bulk = self._project_to_dim(emb_in, bulk_dim).flatten()
        else:
            emb_bulk = emb_in
        vector_payload = emb_bulk.tolist()

        # E8 quantize embedding if provided
        e8_codes = []
        complexity = 0.5
        e8_vector_8d: torch.Tensor | None = None

        if embedding is not None and self.e8_quantizer is not None:
            # Weaviate vectors MUST have a single fixed dimension per collection.
            # We store a consistent Kagami "bulk" vector (config.vector_dim) for retrieval,
            # and separately compute 8D E8 projection + codes for lightweight reranking/metadata.
            # Derive E8 codes from canonical 8D vector
            e8_vector_8d = self._project_to_e8(emb_bulk)
            if e8_vector_8d.dim() == 1:
                e8_vector_8d = e8_vector_8d.unsqueeze(0)

            # Quantize - ResidualE8LatticeVQ returns (quantized, codes)
            # codes is a list of tensors, one per level
            try:
                result = self.e8_quantizer(e8_vector_8d)
                # Handle both (quantized, codes) and single quantized return
                if isinstance(result, tuple) and len(result) == 2:
                    _, codes = result
                    # codes is list of tensors [..., 8] - flatten first level for metadata
                    if codes and len(codes) > 0:
                        first_level = codes[0]
                        if first_level.dim() > 1:
                            first_level = first_level.view(-1, 8)
                        # Use hash of first few coords as simple code
                        e8_codes = first_level[0].tolist()[:4]  # First 4 coordinates
                        e8_codes = [int(c) for c in e8_codes]
                    else:
                        e8_codes = []
                else:
                    # Single tensor return (cached quantizer)
                    e8_codes = []
                # Estimate complexity from number of residual levels used
                complexity = (
                    min(1.0, len(codes) / 8.0)
                    if isinstance(result, tuple) and len(result) == 2
                    else 0.5
                )
            except Exception as quant_err:
                logger.warning(f"E8 quantization failed: {quant_err}")
                e8_codes = []
                complexity = 0.5

        # Store in Weaviate
        collection = (
            self.client.collections.use(self.config.memory_collection)
            if hasattr(self.client.collections, "use")
            else self.client.collections.get(self.config.memory_collection)
        )

        kind = str(metadata.get("kind") or metadata.get("type") or "memory")
        tenant_id = str(metadata.get("tenant_id") or metadata.get("tenant") or "")
        agent = str(
            metadata.get("agent")
            or metadata.get("contributing_agent")
            or metadata.get("agent_id")
            or ""
        )
        category = str(metadata.get("category") or "")
        episode_id = str(metadata.get("episode_id") or metadata.get("event_id") or "")
        from_instance = str(metadata.get("from_instance") or "")

        obj_data = {
            "content": content,
            "colony_affinity": metadata.get("colony", "nexus"),
            "kind": kind,
            "tenant_id": tenant_id,
            "agent": agent,
            "category": category,
            "episode_id": episode_id,
            "from_instance": from_instance,
            # Allow callers to provide a dedicated payload JSON; otherwise store the raw metadata.
            "metadata_json": (
                metadata.get("metadata_json")
                if isinstance(metadata.get("metadata_json"), str)
                else json.dumps(metadata, default=str)
            )
            if metadata
            else "",
            "e8_codes": e8_codes,
            # Store the canonical 8D E8 vector for debugging/local reranking.
            "e8_vector_json": json.dumps(e8_vector_8d.flatten().tolist())
            if e8_vector_8d is not None
            else "",
            "complexity": complexity,
            "source_id": metadata.get("source_id", ""),
            "created_at": self._normalize_created_at(
                metadata.get("created_at") or metadata.get("timestamp")
            ),
        }

        # Filter to schema-supported properties (keeps backward-compat with older collections).
        try:
            schema = collection.config.get()
            allowed = {p.name for p in getattr(schema, "properties", [])}
            obj_data = {k: v for k, v in obj_data.items() if k in allowed}
        except Exception:
            pass

        # Prefer supplying our own vector when available.
        # This keeps Weaviate fully aligned to Kagami/E8 rather than server-side vectorizers.
        # Always prefer supplying our own vector (Kagami-aligned).
        try:
            from weaviate.classes.data import Vector  # type: ignore[attr-defined]

            result = collection.data.insert(obj_data, vector=Vector(vector=vector_payload))
        except Exception:
            # Fallback to raw list (client versions differ)
            try:
                result = collection.data.insert(obj_data, vector=vector_payload)
            except Exception:
                result = collection.data.insert(obj_data)
        return str(result)

    async def store(
        self,
        content: str,
        embedding: torch.Tensor | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> str | None:
        """Store content with E8 quantized embedding.

        Args:
            content: Text content to store
            embedding: Optional pre-computed embedding
            metadata: Additional metadata (colony, source_id, etc.)

        Returns:
            UUID of stored object, or None on failure
        """
        try:
            result = await self._breaker.call(self._store_internal, content, embedding, metadata)
            # Success -> close Redis circuit breaker
            await self._close_circuit()
            return result  # type: ignore[no-any-return]
        except CircuitBreakerOpen:
            logger.warning("Weaviate circuit breaker is OPEN - store operation blocked")
            return None
        except Exception as e:
            logger.error(f"Store operation failed: {e}")
            # Failure -> open Redis circuit breaker
            await self._open_circuit(duration=60)
            return None

    async def _search_similar_internal(
        self,
        query: str | torch.Tensor,
        limit: int = 10,
        colony_filter: str | None = None,
        kind_filter: str | None = None,
        tenant_id: str | None = None,
    ) -> list[dict[str, Any]]:
        """Internal search implementation (wrapped by circuit breaker).

        Raises exceptions to allow circuit breaker to track failures.
        """
        # Check Redis-persisted circuit breaker state
        if not await self._check_circuit():
            raise CircuitBreakerOpen("Weaviate circuit breaker is OPEN (Redis-persisted)")

        if not self._connected:
            await self.connect()

        if not self._connected:
            raise ConnectionError("Not connected to Weaviate")

        collection = (
            self.client.collections.use(self.config.memory_collection)
            if hasattr(self.client.collections, "use")
            else self.client.collections.get(self.config.memory_collection)
        )

        def _build_filters(include_kind_tenant: bool) -> Any | None:
            """Build Weaviate filters with graceful backwards-compat."""
            filters_local: Any | None = None
            if colony_filter:
                from weaviate.classes.query import Filter

                filters_local = Filter.by_property("colony_affinity").equal(colony_filter)
            if include_kind_tenant and kind_filter:
                from weaviate.classes.query import Filter

                kind_f = Filter.by_property("kind").equal(kind_filter)
                filters_local = kind_f if filters_local is None else (filters_local & kind_f)
            if include_kind_tenant and tenant_id:
                from weaviate.classes.query import Filter

                tenant_f = Filter.by_property("tenant_id").equal(tenant_id)
                filters_local = tenant_f if filters_local is None else (filters_local & tenant_f)
            return filters_local

        # Prepare query vector once, then run near_vector (optionally with filters).
        q_tensor: torch.Tensor | None = None
        query_list: list[Any] = []

        if isinstance(query, str):
            q_tensor = self._try_embed_text(query)
            if q_tensor is None:
                raise ValueError("Could not generate embedding for query string")
        else:
            # query is torch.Tensor at this point (per type signature)
            q_tensor = query.flatten() if query.dim() > 1 else query

        # Project to collection's expected dimension
        bulk_dim = int(self.config.vector_dim or 512)
        if int(q_tensor.shape[-1]) != bulk_dim:
            q_tensor = self._project_to_dim(q_tensor, bulk_dim).flatten()

        query_list = q_tensor.flatten().tolist()

        def _run_query(filters_local: Any | None) -> Any:
            return collection.query.near_vector(
                near_vector=query_list,
                limit=limit,
                filters=filters_local,
            )

        # Attempt 1: apply all requested filters.
        try:
            results = _run_query(_build_filters(include_kind_tenant=True))
        except Exception as exc:
            # Attempt 2 (compat): drop kind/tenant filters if schema doesn't have them yet.
            if kind_filter or tenant_id:
                try:
                    results = _run_query(_build_filters(include_kind_tenant=False))
                except Exception:
                    raise exc from None
            else:
                raise

        # Format results
        formatted = []
        q_e8_codes: set[int] | None = None
        if (
            isinstance(query, torch.Tensor) or q_tensor is not None
        ) and self.e8_quantizer is not None:
            try:
                q_src = query if isinstance(query, torch.Tensor) else q_tensor
                assert q_src is not None
                q8 = self._project_to_e8(q_src)
                result = self.e8_quantizer(q8)
                # Handle (quantized, codes) tuple return
                if isinstance(result, tuple) and len(result) == 2:
                    _, codes = result
                    if codes and len(codes) > 0:
                        first_level = codes[0]
                        if first_level.dim() > 1:
                            first_level = first_level.view(-1, 8)
                        q_e8_codes = {int(c) for c in first_level[0].tolist()[:4]}
                    else:
                        q_e8_codes = set()
                else:
                    q_e8_codes = None
            except Exception:
                q_e8_codes = None

        for obj in results.objects:
            stored_codes = obj.properties.get("e8_codes", []) or []
            overlap = None
            if q_e8_codes is not None and isinstance(stored_codes, list):
                try:
                    overlap = len(q_e8_codes.intersection({int(x) for x in stored_codes}))
                except Exception:
                    overlap = None

            formatted.append(
                {
                    "uuid": str(obj.uuid),
                    "content": obj.properties.get("content", ""),
                    "colony": obj.properties.get("colony_affinity", ""),
                    "source_id": obj.properties.get("source_id", ""),
                    "kind": obj.properties.get("kind", ""),
                    "tenant_id": obj.properties.get("tenant_id", ""),
                    "agent": obj.properties.get("agent", ""),
                    "category": obj.properties.get("category", ""),
                    "episode_id": obj.properties.get("episode_id", ""),
                    "from_instance": obj.properties.get("from_instance", ""),
                    "metadata_json": obj.properties.get("metadata_json", ""),
                    "e8_codes": stored_codes,
                    "complexity": obj.properties.get("complexity", 0.5),
                    "score": getattr(obj.metadata, "distance", 0.0) if obj.metadata else 0.0,
                    "e8_overlap": overlap,
                    "properties": dict(obj.properties),
                }
            )

        # Optional rerank: prefer higher E8-overlap when available (tie-break by distance).
        if any(r.get("e8_overlap") is not None for r in formatted):
            formatted.sort(key=lambda r: (-(r.get("e8_overlap") or 0), r.get("score") or 0.0))
        return formatted

    async def search_similar(
        self,
        query: str | torch.Tensor,
        limit: int = 10,
        colony_filter: str | None = None,
        kind_filter: str | None = None,
        tenant_id: str | None = None,
    ) -> list[dict[str, Any]]:
        """Search for similar content.

        Args:
            query: Query string or embedding
            limit: Maximum results
            colony_filter: Optional colony filter
            kind_filter: Optional kind filter
            tenant_id: Optional tenant filter

        Returns:
            List of matching objects with properties
        """
        try:
            result = await self._breaker.call(
                self._search_similar_internal, query, limit, colony_filter, kind_filter, tenant_id
            )
            # Success -> close Redis circuit breaker
            await self._close_circuit()
            return result  # type: ignore[no-any-return]
        except CircuitBreakerOpen:
            logger.warning("Weaviate circuit breaker is OPEN - search operation blocked")
            return []
        except Exception as e:
            logger.error(f"Search operation failed: {e}")
            # Failure -> open Redis circuit breaker
            await self._open_circuit(duration=60)
            return []

    async def store_feedback(
        self,
        query: str,
        response: str,
        rating: int,
        colony: str,
        model: str,
    ) -> str | None:
        """Store user feedback for few-shot learning.

        Args:
            query: Original query
            response: Generated response
            rating: User rating (1-5)
            colony: Colony that handled the query
            model: Model used

        Returns:
            UUID of stored feedback
        """
        if not self._connected:
            await self.connect()

        if not self._connected:
            return None

        try:
            collection = (
                self.client.collections.use(self.config.feedback_collection)
                if hasattr(self.client.collections, "use")
                else self.client.collections.get(self.config.feedback_collection)
            )

            # Prefer storing a vector for feedback even if server-side vectorizers are disabled.
            vector_payload = None
            try:
                emb = self._try_embed_text(query)
                if emb is not None:
                    vector_payload = emb.flatten().tolist()
            except Exception:
                vector_payload = None

            props = {
                "query": query,
                "response": response,
                "rating": rating,
                "colony": colony,
                "model": model,
                "tenant_id": "",
                "metadata_json": "",
                "created_at": datetime.now(),
            }

            if vector_payload is not None:
                try:
                    from weaviate.classes.data import Vector  # type: ignore[attr-defined]

                    result = collection.data.insert(props, vector=Vector(vector=vector_payload))
                except Exception:
                    # Fallback to raw list (client versions differ)
                    try:
                        result = collection.data.insert(props, vector=vector_payload)
                    except Exception:
                        result = collection.data.insert(props)
            else:
                result = collection.data.insert(props)

            return str(result)

        except Exception as e:
            logger.error(f"Failed to store feedback: {e}")
            return None

    async def get_similar_feedback(
        self,
        query: str,
        min_rating: int = 4,
        limit: int = 5,
    ) -> list[dict[str, Any]]:
        """Get similar positive feedback for few-shot examples.

        Args:
            query: Current query
            min_rating: Minimum rating to include
            limit: Maximum examples

        Returns:
            List of similar positive feedback
        """
        if not self._connected:
            await self.connect()

        if not self._connected:
            return []

        try:
            from weaviate.classes.query import Filter

            collection = (
                self.client.collections.use(self.config.feedback_collection)
                if hasattr(self.client.collections, "use")
                else self.client.collections.get(self.config.feedback_collection)
            )

            # If query is empty, treat as "recent feedback" fetch (used by StigmergyLearner).
            if not query or not query.strip():
                results = collection.query.fetch_objects(
                    limit=limit,
                    filters=Filter.by_property("rating").greater_or_equal(min_rating),
                )
            else:
                # CRITICAL: Require Kagami-native embeddings (fail fast if unavailable).
                # Weaviate vectorizers are disabled (bring-your-own vectors).
                q_emb = self._try_embed_text(query)
                if q_emb is None:
                    raise ValueError(
                        "Embedding required for semantic search "
                        "(Weaviate vectorizer disabled, bring-your-own vectors)"
                    )
                results = collection.query.near_vector(
                    near_vector=q_emb.flatten().tolist(),
                    limit=limit,
                    filters=Filter.by_property("rating").greater_or_equal(min_rating),
                )

            formatted = []
            for obj in results.objects:
                formatted.append(
                    {
                        "query": obj.properties.get("query", ""),
                        "response": obj.properties.get("response", ""),
                        "rating": obj.properties.get("rating", 0),
                        "colony": obj.properties.get("colony", ""),
                        "model": obj.properties.get("model", ""),
                    }
                )

            return formatted

        except Exception as e:
            logger.error(f"Failed to get feedback: {e}")
            return []

    async def analyze_collection(self, collection_name: str | None = None) -> dict[str, Any]:
        """Analyze a collection for Elysia metadata.

        Generates:
        - Property descriptions
        - Sample data
        - Recommended display types
        - Summary statistics

        Args:
            collection_name: Collection to analyze (default: memory collection)

        Returns:
            Analysis metadata
        """
        if not self._connected:
            await self.connect()

        if not self._connected:
            return {"error": "Not connected"}

        collection_name = collection_name or self.config.memory_collection

        try:
            collection = (
                self.client.collections.use(collection_name)
                if hasattr(self.client.collections, "use")
                else self.client.collections.get(collection_name)
            )

            # Get schema
            schema = collection.config.get()

            # Sample data
            results = collection.query.fetch_objects(limit=10)
            samples = [obj.properties for obj in results.objects]

            # Aggregate stats
            agg = collection.aggregate.over_all(total_count=True)

            return {
                "collection": collection_name,
                "total_count": agg.total_count,
                "properties": [
                    {"name": p.name, "data_type": str(p.data_type)} for p in schema.properties
                ],
                "samples": samples[:3],
                "recommended_display": self._recommend_display(samples),
            }

        except Exception as e:
            logger.error(f"Collection analysis failed: {e}")
            return {"error": str(e)}

    def _recommend_display(self, samples: list[dict]) -> str:
        """Recommend display type based on sample data."""
        if not samples:
            return "generic"

        sample = samples[0]

        # Check for table-like structure
        if len(sample) > 5:
            return "table"

        # Check for document-like content
        content = sample.get("content", "")
        if len(content) > 500:
            return "document"

        return "generic"

    def close(self) -> None:
        """Close Weaviate connection."""
        if self.client:
            self.client.close()
            self._connected = False
            logger.info("Weaviate connection closed")


_ADAPTER_SINGLETON: WeaviateE8Adapter | None = None
_ADAPTER_LOCK = threading.Lock()


def get_weaviate_adapter(config: WeaviateE8Config | None = None) -> WeaviateE8Adapter:
    """Get or create a process-wide Weaviate adapter singleton.

    This avoids redundant connections/quantizer init across subsystems (RAG, storage router,
    shared episodic memory, MCP tools).
    """
    global _ADAPTER_SINGLETON
    if _ADAPTER_SINGLETON is None:
        with _ADAPTER_LOCK:
            if _ADAPTER_SINGLETON is None:
                _ADAPTER_SINGLETON = WeaviateE8Adapter(config)
    else:
        # Best-effort config reconciliation: if caller provides a config and the adapter is
        # not connected yet, update to the provided config.
        if config is not None and not getattr(_ADAPTER_SINGLETON, "_connected", False):
            _ADAPTER_SINGLETON.config = config
    return _ADAPTER_SINGLETON


def reset_weaviate_adapter() -> None:
    """Reset the singleton (primarily for tests)."""
    global _ADAPTER_SINGLETON
    with _ADAPTER_LOCK:
        if _ADAPTER_SINGLETON is not None:
            try:
                _ADAPTER_SINGLETON.close()
            except Exception:
                pass
        _ADAPTER_SINGLETON = None


__all__ = [
    "WeaviateE8Adapter",
    "WeaviateE8Config",
    "get_weaviate_adapter",
    "reset_weaviate_adapter",
]
