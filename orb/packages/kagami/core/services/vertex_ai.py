"""Vertex AI Model Serving Integration.

Provides model deployment, endpoint management, and prediction services
via Google Cloud Vertex AI. Supports both online and batch prediction.

ARCHITECTURE:
=============
    Model Registry (GCS)
          │
          ▼
    ┌─────────────────┐
    │  VertexAIModel  │
    │   Service       │
    └────────┬────────┘
             │
    ┌────────┴────────┐
    │                 │
    ▼                 ▼
┌─────────┐    ┌──────────┐
│ Online  │    │  Batch   │
│Endpoint │    │Prediction│
└─────────┘    └──────────┘

USAGE:
======
    from kagami.core.services.vertex_ai import get_vertex_ai_service

    service = get_vertex_ai_service()
    await service.initialize()

    # Deploy model
    endpoint = await service.deploy_model(
        model_path="gs://kagami-models/rssm/v1",
        endpoint_name="kagami-rssm-prod",
        machine_type="n1-standard-4",
    )

    # Online prediction
    result = await service.predict(endpoint.name, instances=[...])

    # Batch prediction
    job = await service.batch_predict(
        model_name="kagami-rssm",
        input_uri="gs://kagami-data/input/*.jsonl",
        output_uri="gs://kagami-data/output/",
    )

Created: January 4, 2026
"""

from __future__ import annotations

import asyncio
import logging
import os
from dataclasses import dataclass, field
from datetime import UTC, datetime
from enum import Enum
from typing import Any

logger = logging.getLogger(__name__)

# Lazy imports for optional GCP dependencies
_vertex_ai_available = False
_aiplatform = None


def _lazy_import_vertex() -> Any:
    """Lazy import google.cloud.aiplatform."""
    global _vertex_ai_available, _aiplatform
    if _aiplatform is not None:
        return _aiplatform
    try:
        from google.cloud import aiplatform

        _aiplatform = aiplatform
        _vertex_ai_available = True
        return aiplatform
    except ImportError as e:
        _vertex_ai_available = False
        raise ImportError(
            "google-cloud-aiplatform not installed. "
            "Install with: pip install google-cloud-aiplatform"
        ) from e


class ModelState(str, Enum):
    """Model deployment state."""

    PENDING = "pending"
    UPLOADING = "uploading"
    DEPLOYED = "deployed"
    FAILED = "failed"
    UNDEPLOYING = "undeploying"


class PredictionType(str, Enum):
    """Type of prediction request."""

    ONLINE = "online"
    BATCH = "batch"


@dataclass
class EndpointConfig:
    """Configuration for a Vertex AI endpoint.

    Attributes:
        name: Endpoint display name.
        machine_type: Compute machine type (e.g., n1-standard-4).
        min_replicas: Minimum number of replicas.
        max_replicas: Maximum number of replicas for autoscaling.
        accelerator_type: GPU type if needed (e.g., NVIDIA_TESLA_T4).
        accelerator_count: Number of GPUs per replica.
        traffic_split: Traffic percentage to this deployment (0-100).
    """

    name: str
    machine_type: str = "n1-standard-4"
    min_replicas: int = 1
    max_replicas: int = 3
    accelerator_type: str | None = None
    accelerator_count: int = 0
    traffic_split: int = 100


@dataclass
class ModelInfo:
    """Information about a deployed model.

    Attributes:
        model_id: Vertex AI model resource ID.
        display_name: Human-readable model name.
        artifact_uri: GCS path to model artifacts.
        state: Current deployment state.
        endpoint_id: Endpoint ID if deployed.
        created_at: Model creation timestamp.
        deployed_at: Deployment timestamp if deployed.
    """

    model_id: str
    display_name: str
    artifact_uri: str
    state: ModelState = ModelState.PENDING
    endpoint_id: str | None = None
    created_at: datetime = field(default_factory=lambda: datetime.now(UTC))
    deployed_at: datetime | None = None
    labels: dict[str, str] = field(default_factory=dict)


@dataclass
class PredictionResult:
    """Result from a prediction request.

    Attributes:
        predictions: List of prediction outputs.
        deployed_model_id: ID of the model that served the request.
        latency_ms: Request latency in milliseconds.
        model_version: Version of the model used.
    """

    predictions: list[Any]
    deployed_model_id: str
    latency_ms: float
    model_version: str | None = None


@dataclass
class BatchPredictionJob:
    """Batch prediction job information.

    Attributes:
        job_id: Vertex AI batch job ID.
        display_name: Human-readable job name.
        model_name: Model used for predictions.
        input_uri: GCS URI for input data.
        output_uri: GCS URI for output data.
        state: Job state.
        started_at: Job start time.
        completed_at: Job completion time.
        error: Error message if failed.
    """

    job_id: str
    display_name: str
    model_name: str
    input_uri: str
    output_uri: str
    state: str = "PENDING"
    started_at: datetime | None = None
    completed_at: datetime | None = None
    error: str | None = None


@dataclass
class VertexAIConfig:
    """Configuration for Vertex AI service.

    Attributes:
        project_id: GCP project ID.
        region: GCP region for Vertex AI resources.
        staging_bucket: GCS bucket for staging artifacts.
        service_account: Service account email for Vertex AI.
        encryption_key: Cloud KMS key for encryption.
        network: VPC network for private endpoints.
    """

    project_id: str | None = None
    region: str = "us-central1"
    staging_bucket: str | None = None
    service_account: str | None = None
    encryption_key: str | None = None
    network: str | None = None

    @classmethod
    def from_env(cls) -> VertexAIConfig:
        """Create config from environment variables."""
        return cls(
            project_id=os.getenv("GCP_PROJECT_ID") or os.getenv("GOOGLE_CLOUD_PROJECT"),
            region=os.getenv("VERTEX_AI_REGION", "us-central1"),
            staging_bucket=os.getenv("VERTEX_AI_STAGING_BUCKET"),
            service_account=os.getenv("VERTEX_AI_SERVICE_ACCOUNT"),
            encryption_key=os.getenv("VERTEX_AI_ENCRYPTION_KEY"),
            network=os.getenv("VERTEX_AI_NETWORK"),
        )


class VertexAIModelService:
    """Vertex AI model deployment and serving service.

    Provides comprehensive model lifecycle management including:
    - Model upload to Model Registry
    - Endpoint creation and management
    - Online prediction with autoscaling
    - Batch prediction for large datasets
    - Model versioning and traffic splitting

    Thread-safe and async-compatible.

    Example:
        service = VertexAIModelService()
        await service.initialize()

        # Upload and deploy
        model = await service.upload_model(
            artifact_uri="gs://bucket/model",
            display_name="kagami-rssm-v1",
        )
        endpoint = await service.deploy_model(
            model_id=model.model_id,
            endpoint_config=EndpointConfig(name="prod"),
        )

        # Predict
        result = await service.predict(
            endpoint_id=endpoint.endpoint_id,
            instances=[{"input": [1, 2, 3]}],
        )
    """

    # Retry configuration
    MAX_RETRIES = 3
    INITIAL_BACKOFF_SEC = 1.0
    MAX_BACKOFF_SEC = 30.0
    BACKOFF_MULTIPLIER = 2.0

    def __init__(self, config: VertexAIConfig | None = None):
        """Initialize Vertex AI service.

        Args:
            config: Service configuration. If None, loads from environment.
        """
        self.config = config or VertexAIConfig.from_env()
        self._initialized = False
        self._models: dict[str, ModelInfo] = {}
        self._endpoints: dict[str, Any] = {}

    async def initialize(self) -> None:
        """Initialize Vertex AI SDK.

        Must be called before using other methods.

        Raises:
            ImportError: If google-cloud-aiplatform not installed.
            RuntimeError: If project_id not configured.
        """
        if self._initialized:
            return

        aiplatform = _lazy_import_vertex()

        if not self.config.project_id:
            # Try to get from metadata server
            try:
                import httpx

                async with httpx.AsyncClient() as client:
                    resp = await client.get(
                        "http://metadata.google.internal/computeMetadata/v1/project/project-id",
                        headers={"Metadata-Flavor": "Google"},
                        timeout=2.0,
                    )
                    self.config.project_id = resp.text
            except Exception as e:
                raise RuntimeError(
                    "GCP project ID not configured. Set GCP_PROJECT_ID environment variable."
                ) from e

        # Initialize SDK
        init_kwargs = {
            "project": self.config.project_id,
            "location": self.config.region,
        }

        if self.config.staging_bucket:
            init_kwargs["staging_bucket"] = self.config.staging_bucket

        if self.config.encryption_key:
            init_kwargs["encryption_spec_key_name"] = self.config.encryption_key

        aiplatform.init(**init_kwargs)

        self._initialized = True
        logger.info(
            f"Vertex AI initialized: project={self.config.project_id}, region={self.config.region}"
        )

    def _ensure_initialized(self) -> None:
        """Ensure service is initialized."""
        if not self._initialized:
            raise RuntimeError("VertexAIModelService not initialized. Call initialize() first.")

    async def _retry_with_backoff(
        self,
        operation: Any,
        operation_name: str,
    ) -> Any:
        """Execute operation with exponential backoff retry.

        Args:
            operation: Async callable to execute.
            operation_name: Name for logging.

        Returns:
            Operation result.

        Raises:
            Exception: If all retries fail.
        """
        backoff = self.INITIAL_BACKOFF_SEC

        for attempt in range(self.MAX_RETRIES):
            try:
                return await operation()
            except Exception as e:
                if attempt == self.MAX_RETRIES - 1:
                    logger.error(f"{operation_name} failed after {self.MAX_RETRIES} attempts: {e}")
                    raise

                logger.warning(
                    f"{operation_name} attempt {attempt + 1} failed: {e}. "
                    f"Retrying in {backoff:.1f}s..."
                )
                await asyncio.sleep(backoff)
                backoff = min(backoff * self.BACKOFF_MULTIPLIER, self.MAX_BACKOFF_SEC)

        # Should never reach here
        raise RuntimeError(f"{operation_name} failed unexpectedly")

    async def upload_model(
        self,
        artifact_uri: str,
        display_name: str,
        serving_container_image_uri: str | None = None,
        description: str = "",
        labels: dict[str, str] | None = None,
    ) -> ModelInfo:
        """Upload model to Vertex AI Model Registry.

        Args:
            artifact_uri: GCS path to model artifacts.
            display_name: Human-readable model name.
            serving_container_image_uri: Container image for serving.
                Defaults to TensorFlow serving image.
            description: Model description.
            labels: Key-value labels for the model.

        Returns:
            ModelInfo with model details.

        Example:
            model = await service.upload_model(
                artifact_uri="gs://kagami-models/rssm/v1",
                display_name="kagami-rssm-v1",
                labels={"colony": "forge", "version": "1.0"},
            )
        """
        self._ensure_initialized()
        aiplatform = _lazy_import_vertex()

        # Default to TF serving container
        if serving_container_image_uri is None:
            serving_container_image_uri = (
                "us-docker.pkg.dev/vertex-ai/prediction/tf2-cpu.2-12:latest"
            )

        async def _upload() -> Any:
            loop = asyncio.get_running_loop()
            return await loop.run_in_executor(
                None,
                lambda: aiplatform.Model.upload(
                    display_name=display_name,
                    artifact_uri=artifact_uri,
                    serving_container_image_uri=serving_container_image_uri,
                    description=description,
                    labels=labels or {},
                ),
            )

        logger.info(f"Uploading model '{display_name}' from {artifact_uri}")
        model = await self._retry_with_backoff(_upload, f"upload_model({display_name})")

        model_info = ModelInfo(
            model_id=model.name,
            display_name=display_name,
            artifact_uri=artifact_uri,
            state=ModelState.UPLOADED if hasattr(ModelState, "UPLOADED") else ModelState.PENDING,
            labels=labels or {},
        )

        self._models[model.name] = model_info
        logger.info(f"Model uploaded: {model.name}")

        return model_info

    async def create_endpoint(
        self,
        display_name: str,
        description: str = "",
        labels: dict[str, str] | None = None,
        enable_private: bool = False,
    ) -> str:
        """Create a Vertex AI endpoint.

        Args:
            display_name: Endpoint display name.
            description: Endpoint description.
            labels: Key-value labels.
            enable_private: If True, create private endpoint in VPC.

        Returns:
            Endpoint resource name.
        """
        self._ensure_initialized()
        aiplatform = _lazy_import_vertex()

        async def _create() -> Any:
            loop = asyncio.get_running_loop()
            kwargs: dict[str, Any] = {
                "display_name": display_name,
                "description": description,
                "labels": labels or {},
            }

            if enable_private and self.config.network:
                kwargs["network"] = self.config.network

            return await loop.run_in_executor(
                None,
                lambda: aiplatform.Endpoint.create(**kwargs),
            )

        logger.info(f"Creating endpoint '{display_name}'")
        endpoint = await self._retry_with_backoff(_create, f"create_endpoint({display_name})")

        self._endpoints[endpoint.name] = endpoint
        logger.info(f"Endpoint created: {endpoint.name}")

        return endpoint.name

    async def deploy_model(
        self,
        model_id: str,
        endpoint_id: str | None = None,
        endpoint_config: EndpointConfig | None = None,
    ) -> ModelInfo:
        """Deploy model to an endpoint.

        Args:
            model_id: Model resource name from upload_model.
            endpoint_id: Existing endpoint ID. If None, creates new endpoint.
            endpoint_config: Deployment configuration.

        Returns:
            Updated ModelInfo with endpoint details.

        Example:
            model = await service.deploy_model(
                model_id=uploaded_model.model_id,
                endpoint_config=EndpointConfig(
                    name="kagami-prod",
                    machine_type="n1-standard-8",
                    min_replicas=2,
                    max_replicas=10,
                ),
            )
        """
        self._ensure_initialized()
        aiplatform = _lazy_import_vertex()

        config = endpoint_config or EndpointConfig(name="default")

        # Create endpoint if not provided
        if endpoint_id is None:
            endpoint_id = await self.create_endpoint(
                display_name=config.name,
                labels={"managed_by": "kagami"},
            )

        async def _deploy() -> Any:
            loop = asyncio.get_running_loop()

            # Get model and endpoint objects
            model = aiplatform.Model(model_id)
            endpoint = aiplatform.Endpoint(endpoint_id)

            deploy_kwargs: dict[str, Any] = {
                "model": model,
                "deployed_model_display_name": config.name,
                "machine_type": config.machine_type,
                "min_replica_count": config.min_replicas,
                "max_replica_count": config.max_replicas,
                "traffic_split": {"0": config.traffic_split},
            }

            if config.accelerator_type and config.accelerator_count > 0:
                deploy_kwargs["accelerator_type"] = config.accelerator_type
                deploy_kwargs["accelerator_count"] = config.accelerator_count

            if self.config.service_account:
                deploy_kwargs["service_account"] = self.config.service_account

            return await loop.run_in_executor(
                None,
                lambda: endpoint.deploy(**deploy_kwargs),
            )

        logger.info(f"Deploying model {model_id} to endpoint {endpoint_id}")
        await self._retry_with_backoff(_deploy, f"deploy_model({model_id})")

        # Update model info
        if model_id in self._models:
            self._models[model_id].state = ModelState.DEPLOYED
            self._models[model_id].endpoint_id = endpoint_id
            self._models[model_id].deployed_at = datetime.now(UTC)
            return self._models[model_id]

        return ModelInfo(
            model_id=model_id,
            display_name=config.name,
            artifact_uri="",
            state=ModelState.DEPLOYED,
            endpoint_id=endpoint_id,
            deployed_at=datetime.now(UTC),
        )

    async def predict(
        self,
        endpoint_id: str,
        instances: list[dict[str, Any]],
        parameters: dict[str, Any] | None = None,
    ) -> PredictionResult:
        """Make online prediction request.

        Args:
            endpoint_id: Endpoint resource name.
            instances: List of prediction instances.
            parameters: Optional prediction parameters.

        Returns:
            PredictionResult with predictions.

        Example:
            result = await service.predict(
                endpoint_id="projects/.../endpoints/123",
                instances=[
                    {"input": [1.0, 2.0, 3.0]},
                    {"input": [4.0, 5.0, 6.0]},
                ],
            )
            for pred in result.predictions:
                print(pred)
        """
        self._ensure_initialized()
        aiplatform = _lazy_import_vertex()

        import time

        start_time = time.perf_counter()

        async def _predict() -> Any:
            loop = asyncio.get_running_loop()
            endpoint = aiplatform.Endpoint(endpoint_id)

            return await loop.run_in_executor(
                None,
                lambda: endpoint.predict(instances=instances, parameters=parameters or {}),
            )

        response = await self._retry_with_backoff(_predict, f"predict({endpoint_id})")
        latency_ms = (time.perf_counter() - start_time) * 1000

        return PredictionResult(
            predictions=list(response.predictions),
            deployed_model_id=response.deployed_model_id,
            latency_ms=latency_ms,
            model_version=getattr(response, "model_version_id", None),
        )

    async def batch_predict(
        self,
        model_id: str,
        input_uri: str,
        output_uri: str,
        display_name: str | None = None,
        machine_type: str = "n1-standard-4",
        max_replica_count: int = 10,
        starting_replica_count: int = 1,
    ) -> BatchPredictionJob:
        """Start batch prediction job.

        Args:
            model_id: Model resource name.
            input_uri: GCS URI pattern for input (e.g., gs://bucket/*.jsonl).
            output_uri: GCS URI for output directory.
            display_name: Job display name.
            machine_type: Compute machine type.
            max_replica_count: Maximum parallel replicas.
            starting_replica_count: Initial replica count.

        Returns:
            BatchPredictionJob with job details.

        Example:
            job = await service.batch_predict(
                model_id="projects/.../models/123",
                input_uri="gs://kagami-data/batch-input/*.jsonl",
                output_uri="gs://kagami-data/batch-output/",
            )

            # Wait for completion
            while job.state not in ["SUCCEEDED", "FAILED"]:
                job = await service.get_batch_job(job.job_id)
                await asyncio.sleep(30)
        """
        self._ensure_initialized()
        aiplatform = _lazy_import_vertex()

        job_name = display_name or f"kagami-batch-{datetime.now(UTC).strftime('%Y%m%d-%H%M%S')}"

        async def _batch() -> Any:
            loop = asyncio.get_running_loop()
            model = aiplatform.Model(model_id)

            return await loop.run_in_executor(
                None,
                lambda: model.batch_predict(
                    job_display_name=job_name,
                    gcs_source=input_uri,
                    gcs_destination_prefix=output_uri,
                    machine_type=machine_type,
                    max_replica_count=max_replica_count,
                    starting_replica_count=starting_replica_count,
                    sync=False,  # Return immediately
                ),
            )

        logger.info(f"Starting batch prediction job '{job_name}'")
        job = await self._retry_with_backoff(_batch, f"batch_predict({model_id})")

        return BatchPredictionJob(
            job_id=job.name,
            display_name=job_name,
            model_name=model_id,
            input_uri=input_uri,
            output_uri=output_uri,
            state=job.state.name if hasattr(job.state, "name") else str(job.state),
            started_at=datetime.now(UTC),
        )

    async def get_batch_job(self, job_id: str) -> BatchPredictionJob:
        """Get batch prediction job status.

        Args:
            job_id: Batch job resource name.

        Returns:
            Updated BatchPredictionJob.
        """
        self._ensure_initialized()
        aiplatform = _lazy_import_vertex()

        async def _get() -> Any:
            loop = asyncio.get_running_loop()
            return await loop.run_in_executor(
                None,
                lambda: aiplatform.BatchPredictionJob(job_id),
            )

        job = await _get()

        return BatchPredictionJob(
            job_id=job.name,
            display_name=job.display_name,
            model_name=job.model.name if job.model else "",
            input_uri=str(job.input_config) if hasattr(job, "input_config") else "",
            output_uri=str(job.output_config) if hasattr(job, "output_config") else "",
            state=job.state.name if hasattr(job.state, "name") else str(job.state),
            started_at=job.start_time if hasattr(job, "start_time") else None,
            completed_at=job.end_time if hasattr(job, "end_time") else None,
            error=str(job.error) if hasattr(job, "error") and job.error else None,
        )

    async def list_models(
        self,
        filter_expr: str | None = None,
        order_by: str = "create_time desc",
    ) -> list[ModelInfo]:
        """List models in Model Registry.

        Args:
            filter_expr: Optional filter expression.
            order_by: Sort order.

        Returns:
            List of ModelInfo.
        """
        self._ensure_initialized()
        aiplatform = _lazy_import_vertex()

        async def _list() -> list[Any]:
            loop = asyncio.get_running_loop()
            return await loop.run_in_executor(
                None,
                lambda: list(
                    aiplatform.Model.list(
                        filter=filter_expr,
                        order_by=order_by,
                    )
                ),
            )

        models = await _list()

        return [
            ModelInfo(
                model_id=m.name,
                display_name=m.display_name,
                artifact_uri=m.artifact_uri or "",
                state=ModelState.DEPLOYED if m.deployed_models else ModelState.PENDING,
                labels=dict(m.labels) if m.labels else {},
            )
            for m in models
        ]

    async def list_endpoints(self) -> list[dict[str, Any]]:
        """List all endpoints.

        Returns:
            List of endpoint information dicts.
        """
        self._ensure_initialized()
        aiplatform = _lazy_import_vertex()

        async def _list() -> list[Any]:
            loop = asyncio.get_running_loop()
            return await loop.run_in_executor(
                None,
                lambda: list(aiplatform.Endpoint.list()),
            )

        endpoints = await _list()

        return [
            {
                "endpoint_id": e.name,
                "display_name": e.display_name,
                "deployed_models": len(e.deployed_models) if e.deployed_models else 0,
                "create_time": e.create_time,
            }
            for e in endpoints
        ]

    async def undeploy_model(self, endpoint_id: str, deployed_model_id: str) -> None:
        """Undeploy a model from an endpoint.

        Args:
            endpoint_id: Endpoint resource name.
            deployed_model_id: Deployed model ID to undeploy.
        """
        self._ensure_initialized()
        aiplatform = _lazy_import_vertex()

        async def _undeploy() -> None:
            loop = asyncio.get_running_loop()
            endpoint = aiplatform.Endpoint(endpoint_id)

            await loop.run_in_executor(
                None,
                lambda: endpoint.undeploy(deployed_model_id=deployed_model_id),
            )

        logger.info(f"Undeploying model {deployed_model_id} from {endpoint_id}")
        await self._retry_with_backoff(_undeploy, f"undeploy_model({deployed_model_id})")
        logger.info(f"Model undeployed: {deployed_model_id}")

    async def delete_endpoint(self, endpoint_id: str, force: bool = False) -> None:
        """Delete an endpoint.

        Args:
            endpoint_id: Endpoint resource name.
            force: If True, undeploy all models first.
        """
        self._ensure_initialized()
        aiplatform = _lazy_import_vertex()

        async def _delete() -> None:
            loop = asyncio.get_running_loop()
            endpoint = aiplatform.Endpoint(endpoint_id)

            await loop.run_in_executor(
                None,
                lambda: endpoint.delete(force=force),
            )

        logger.info(f"Deleting endpoint {endpoint_id}")
        await self._retry_with_backoff(_delete, f"delete_endpoint({endpoint_id})")

        if endpoint_id in self._endpoints:
            del self._endpoints[endpoint_id]

        logger.info(f"Endpoint deleted: {endpoint_id}")


# Singleton instance
_vertex_service: VertexAIModelService | None = None


def get_vertex_ai_service(config: VertexAIConfig | None = None) -> VertexAIModelService:
    """Get or create singleton Vertex AI service.

    Args:
        config: Optional configuration (only used on first call).

    Returns:
        VertexAIModelService instance.
    """
    global _vertex_service
    if _vertex_service is None:
        _vertex_service = VertexAIModelService(config)
    return _vertex_service


async def initialize_vertex_ai(config: VertexAIConfig | None = None) -> VertexAIModelService:
    """Initialize and return Vertex AI service.

    Convenience function that initializes the service.

    Args:
        config: Optional configuration.

    Returns:
        Initialized VertexAIModelService.
    """
    service = get_vertex_ai_service(config)
    await service.initialize()
    return service


__all__ = [
    "BatchPredictionJob",
    "EndpointConfig",
    "ModelInfo",
    "ModelState",
    "PredictionResult",
    "PredictionType",
    "VertexAIConfig",
    "VertexAIModelService",
    "get_vertex_ai_service",
    "initialize_vertex_ai",
]
