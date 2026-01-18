"""KagamiOS API Usage Examples.

CREATED: December 14, 2025
PURPOSE: Example client code for KagamiOS API endpoints

This script demonstrates how to use:
1. Compression API - E8 model quantization
2. Safety API - CBF verification and certification
3. Routing API - Fano plane multi-agent coordination

SETUP:
======
```bash
pip install httpx websockets
export CHRONOS_API_KEY="sk_pro_your_key_here"
python examples/api_usage.py
```

For free tier, use: export CHRONOS_API_KEY="sk_free_your_key_here"
"""

from __future__ import annotations

import asyncio
import os
import sys
from typing import Any

import httpx

# =============================================================================
# CONSTANTS
# =============================================================================

# API configuration
API_BASE_URL: str = os.getenv("CHRONOS_API_URL", "http://localhost:8000")

# Timeout constants (in seconds)
COMPRESS_TIMEOUT: float = 30.0
DECOMPRESS_TIMEOUT: float = 30.0
SAFETY_TIMEOUT: float = 10.0
CERTIFY_TIMEOUT: float = 10.0
ROUTE_TIMEOUT: float = 10.0
COORDINATE_TIMEOUT: float = 35.0
HEALTH_TIMEOUT: float = 5.0

# Connection pool settings
MAX_CONNECTIONS: int = 100
MAX_KEEPALIVE_CONNECTIONS: int = 20
KEEPALIVE_EXPIRY: float = 30.0

# Validation constants
MIN_WEIGHT_VALUE: float = -1e6
MAX_WEIGHT_VALUE: float = 1e6
MAX_WEIGHT_DIMENSION: int = 100000
MIN_CODEBOOKS: int = 1
MAX_CODEBOOKS: int = 16


# =============================================================================
# EXCEPTIONS
# =============================================================================


class KagamiAPIError(Exception):
    """Base exception for KagamiOS API errors."""

    def __init__(
        self, message: str, status_code: int | None = None, response_body: str | None = None
    ) -> None:
        self.message = message
        self.status_code = status_code
        self.response_body = response_body
        super().__init__(self.message)


class KagamiConfigurationError(KagamiAPIError):
    """Raised when API is misconfigured (e.g., missing API key)."""

    pass


class KagamiValidationError(KagamiAPIError):
    """Raised when input validation fails."""

    pass


class KagamiConnectionError(KagamiAPIError):
    """Raised when connection to API fails."""

    pass


# =============================================================================
# API KEY VALIDATION
# =============================================================================


def _get_api_key() -> str:
    """Get and validate the API key from environment.

    Returns:
        The API key string.

    Raises:
        KagamiConfigurationError: If CHRONOS_API_KEY is not set or empty.
    """
    api_key = os.getenv("CHRONOS_API_KEY")
    if not api_key:
        raise KagamiConfigurationError(
            "CHRONOS_API_KEY environment variable is required but not set.\n"
            "Please set it with: export CHRONOS_API_KEY='sk_pro_your_key_here'\n"
            "For free tier: export CHRONOS_API_KEY='sk_free_your_key_here'"
        )
    if not api_key.startswith(("sk_pro_", "sk_free_")):
        raise KagamiConfigurationError(
            f"Invalid API key format. Must start with 'sk_pro_' or 'sk_free_', "
            f"got: {api_key[:10]}..."
        )
    return api_key


# Validate API key at module load time for script usage
try:
    API_KEY: str = _get_api_key()
except KagamiConfigurationError as e:
    print(f"ERROR: {e.message}")
    sys.exit(1)

# =============================================================================
# API CLIENT
# =============================================================================


class KagamiOSClient:
    """Python client for KagamiOS API.

    This client uses a persistent connection pool for efficient HTTP requests.
    Use as an async context manager for automatic resource cleanup:

        async with KagamiOSClient(api_key) as client:
            result = await client.compress_model(weights)

    Or manually manage the lifecycle:

        client = KagamiOSClient(api_key)
        await client.connect()
        try:
            result = await client.compress_model(weights)
        finally:
            await client.close()
    """

    def __init__(self, api_key: str, base_url: str = API_BASE_URL) -> None:
        """Initialize the KagamiOS API client.

        Args:
            api_key: API key for authentication (must start with 'sk_pro_' or 'sk_free_').
            base_url: Base URL for the API server.

        Raises:
            KagamiConfigurationError: If the API key format is invalid.
        """
        if not api_key:
            raise KagamiConfigurationError("API key cannot be empty")
        if not api_key.startswith(("sk_pro_", "sk_free_")):
            raise KagamiConfigurationError(
                f"Invalid API key format. Must start with 'sk_pro_' or 'sk_free_', "
                f"got: {api_key[:10]}..."
            )

        self.api_key: str = api_key
        self.base_url: str = base_url.rstrip("/")
        self._client: httpx.AsyncClient | None = None

    def _get_headers(self) -> dict[str, str]:
        """Get request headers with authentication."""
        return {
            "X-API-Key": self.api_key,
            "Content-Type": "application/json",
        }

    def _create_client(self) -> httpx.AsyncClient:
        """Create a new AsyncClient with connection pooling."""
        limits = httpx.Limits(
            max_connections=MAX_CONNECTIONS,
            max_keepalive_connections=MAX_KEEPALIVE_CONNECTIONS,
            keepalive_expiry=KEEPALIVE_EXPIRY,
        )
        return httpx.AsyncClient(
            base_url=self.base_url,
            headers=self._get_headers(),
            limits=limits,
            timeout=httpx.Timeout(SAFETY_TIMEOUT),  # Default timeout
        )

    async def connect(self) -> None:
        """Initialize the HTTP client connection pool.

        This is called automatically when using the client as a context manager.
        """
        if self._client is None:
            self._client = self._create_client()

    async def close(self) -> None:
        """Close the HTTP client and release resources.

        This is called automatically when using the client as a context manager.
        """
        if self._client is not None:
            await self._client.aclose()
            self._client = None

    async def __aenter__(self) -> KagamiOSClient:
        """Async context manager entry."""
        await self.connect()
        return self

    async def __aexit__(
        self, exc_type: type | None, exc_val: Exception | None, exc_tb: Any
    ) -> None:
        """Async context manager exit."""
        await self.close()

    @property
    def client(self) -> httpx.AsyncClient:
        """Get the HTTP client, auto-connecting if needed.

        Returns:
            The active AsyncClient instance.

        Raises:
            KagamiConnectionError: If the client is not connected.
        """
        if self._client is None:
            # Auto-create client for backwards compatibility
            self._client = self._create_client()
        return self._client

    async def _request(
        self,
        method: str,
        endpoint: str,
        *,
        json: dict[str, Any] | None = None,
        timeout: float | None = None,
    ) -> dict[str, Any]:
        """Make an HTTP request with error handling.

        Args:
            method: HTTP method (GET, POST, etc.).
            endpoint: API endpoint path.
            json: JSON body for the request.
            timeout: Request timeout in seconds.

        Returns:
            Parsed JSON response.

        Raises:
            KagamiAPIError: If the request fails.
            KagamiConnectionError: If connection to the API fails.
        """
        try:
            request_timeout = httpx.Timeout(timeout) if timeout else None
            response = await self.client.request(
                method,
                endpoint,
                json=json,
                timeout=request_timeout,
            )
            response.raise_for_status()
            return response.json()

        except httpx.TimeoutException as e:
            raise KagamiConnectionError(
                f"Request to {endpoint} timed out after {timeout or 'default'}s: {e}"
            ) from e

        except httpx.ConnectError as e:
            raise KagamiConnectionError(
                f"Failed to connect to API at {self.base_url}: {e}\n"
                "Make sure the API server is running: python -m kagami_api.main"
            ) from e

        except httpx.HTTPStatusError as e:
            raise KagamiAPIError(
                f"API request failed with status {e.response.status_code}: {e.response.text}",
                status_code=e.response.status_code,
                response_body=e.response.text,
            ) from e

        except httpx.HTTPError as e:
            raise KagamiAPIError(f"HTTP error during request to {endpoint}: {e}") from e

    def _validate_weights(self, weights: list[list[float]]) -> None:
        """Validate model weights input.

        Args:
            weights: 2D list of model weights.

        Raises:
            KagamiValidationError: If weights are invalid.
        """
        if not weights:
            raise KagamiValidationError("Weights cannot be empty")

        if not isinstance(weights, list):
            raise KagamiValidationError(f"Weights must be a list, got {type(weights).__name__}")

        if not all(isinstance(row, list) for row in weights):
            raise KagamiValidationError("Weights must be a 2D list (list of lists)")

        num_rows = len(weights)
        if num_rows > MAX_WEIGHT_DIMENSION:
            raise KagamiValidationError(
                f"Weight rows ({num_rows}) exceeds maximum ({MAX_WEIGHT_DIMENSION})"
            )

        if not weights[0]:
            raise KagamiValidationError("Weight rows cannot be empty")

        num_cols = len(weights[0])
        if num_cols > MAX_WEIGHT_DIMENSION:
            raise KagamiValidationError(
                f"Weight columns ({num_cols}) exceeds maximum ({MAX_WEIGHT_DIMENSION})"
            )

        # Check consistent dimensions and value ranges
        for i, row in enumerate(weights):
            if len(row) != num_cols:
                raise KagamiValidationError(
                    f"Inconsistent row length at index {i}: expected {num_cols}, got {len(row)}"
                )

            for j, val in enumerate(row):
                if not isinstance(val, int | float):
                    raise KagamiValidationError(
                        f"Invalid weight type at [{i}][{j}]: expected number, got {type(val).__name__}"
                    )
                if val < MIN_WEIGHT_VALUE or val > MAX_WEIGHT_VALUE:
                    raise KagamiValidationError(
                        f"Weight value at [{i}][{j}] ({val}) outside valid range "
                        f"[{MIN_WEIGHT_VALUE}, {MAX_WEIGHT_VALUE}]"
                    )

    def _validate_num_codebooks(self, num_codebooks: int) -> None:
        """Validate number of codebooks.

        Args:
            num_codebooks: Number of residual codebooks.

        Raises:
            KagamiValidationError: If num_codebooks is out of range.
        """
        if not isinstance(num_codebooks, int):
            raise KagamiValidationError(
                f"num_codebooks must be an integer, got {type(num_codebooks).__name__}"
            )
        if num_codebooks < MIN_CODEBOOKS or num_codebooks > MAX_CODEBOOKS:
            raise KagamiValidationError(
                f"num_codebooks ({num_codebooks}) must be between {MIN_CODEBOOKS} and {MAX_CODEBOOKS}"
            )

    async def compress_model(
        self, weights: list[list[float]], num_codebooks: int = 4
    ) -> dict[str, Any]:
        """Compress model weights using E8 quantization.

        Args:
            weights: Model weights as 2D list. Each inner list represents a row.
                Values must be between MIN_WEIGHT_VALUE and MAX_WEIGHT_VALUE.
            num_codebooks: Number of residual codebooks (1-16). Higher values give
                better compression but slower encode/decode.

        Returns:
            Compression result containing:
                - compressed_data: Base64-encoded compressed weights
                - compression_ratio: Achieved compression ratio
                - bitrate: Bits per weight
                - job_id: Unique job identifier for decompression

        Raises:
            KagamiValidationError: If weights or num_codebooks are invalid.
            KagamiAPIError: If the API request fails.
            KagamiConnectionError: If connection fails.
        """
        self._validate_weights(weights)
        self._validate_num_codebooks(num_codebooks)

        return await self._request(
            "POST",
            "/v1/compress",
            json={
                "model_weights": weights,
                "format": "pytorch",
                "num_codebooks": num_codebooks,
            },
            timeout=COMPRESS_TIMEOUT,
        )

    async def decompress_model(
        self, compressed_data: str, original_shape: list[int], job_id: str
    ) -> dict[str, Any]:
        """Decompress E8-quantized weights.

        Args:
            compressed_data: Base64-encoded compressed data from compress_model.
            original_shape: Original tensor shape [rows, cols].
            job_id: Job ID from the compression result.

        Returns:
            Decompression result containing:
                - weights: Reconstructed weight values
                - shape: Tensor shape
                - reconstruction_error: MSE from original weights

        Raises:
            KagamiValidationError: If inputs are invalid.
            KagamiAPIError: If the API request fails.
            KagamiConnectionError: If connection fails.
        """
        if not compressed_data:
            raise KagamiValidationError("compressed_data cannot be empty")
        if not original_shape or len(original_shape) != 2:
            raise KagamiValidationError("original_shape must be a list of 2 integers [rows, cols]")
        if not job_id:
            raise KagamiValidationError("job_id cannot be empty")

        return await self._request(
            "POST",
            "/v1/decompress",
            json={
                "compressed_data": compressed_data,
                "original_shape": original_shape,
                "format": "pytorch",
                "job_id": job_id,
            },
            timeout=DECOMPRESS_TIMEOUT,
        )

    async def verify_safety(
        self,
        operation: str,
        action: dict[str, Any],
        context: dict[str, Any] | None = None,
        user_input: str | None = None,
    ) -> dict[str, Any]:
        """Verify safety of an operation using Control Barrier Functions (CBF).

        Args:
            operation: Operation type (e.g., 'send_message', 'execute_code').
            action: Action parameters specific to the operation type.
            context: Optional execution context (environment, permissions, etc.).
            user_input: Optional raw user input text for analysis.

        Returns:
            Verification result containing:
                - safe: Boolean indicating if operation is safe
                - h_value: CBF safety margin (positive = safe)
                - recommendation: Human-readable safety recommendation

        Raises:
            KagamiValidationError: If inputs are invalid.
            KagamiAPIError: If the API request fails.
            KagamiConnectionError: If connection fails.
        """
        if not operation:
            raise KagamiValidationError("operation cannot be empty")
        if not isinstance(action, dict):
            raise KagamiValidationError(f"action must be a dict, got {type(action).__name__}")

        return await self._request(
            "POST",
            "/v1/verify",
            json={
                "operation": operation,
                "action": action,
                "context": context or {},
                "user_input": user_input,
                "require_certificate": False,
            },
            timeout=SAFETY_TIMEOUT,
        )

    async def certify_safety(
        self,
        system_name: str,
        operation_context: dict[str, Any],
        test_results: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """Generate a safety certificate for a system.

        Args:
            system_name: Name of the system to certify.
            operation_context: Context to include in certificate (version, config, etc.).
            test_results: Optional test results to include in certificate.

        Returns:
            Certificate containing:
                - certificate_id: Unique certificate identifier
                - hash: Cryptographic hash of the certificate
                - confidence: Confidence level of safety assessment
                - component_proofs: Individual safety proofs

        Raises:
            KagamiValidationError: If inputs are invalid.
            KagamiAPIError: If the API request fails.
            KagamiConnectionError: If connection fails.

        Note:
            This endpoint requires a Pro tier API key (sk_pro_*).
        """
        if not system_name:
            raise KagamiValidationError("system_name cannot be empty")
        if not isinstance(operation_context, dict):
            raise KagamiValidationError(
                f"operation_context must be a dict, got {type(operation_context).__name__}"
            )

        return await self._request(
            "POST",
            "/v1/certify",
            json={
                "system_name": system_name,
                "operation_context": operation_context,
                "test_results": test_results or {},
            },
            timeout=CERTIFY_TIMEOUT,
        )

    async def route_task(
        self, task: str, context: dict[str, Any] | None = None, complexity: float | None = None
    ) -> dict[str, Any]:
        """Route a task to appropriate agent colonies.

        Uses Fano plane geometry for optimal task distribution across 7 colonies.

        Args:
            task: Task description text.
            context: Optional task context (domain, constraints, etc.).
            complexity: Optional explicit complexity score (0.0-1.0).
                If not provided, complexity is estimated from task description.

        Returns:
            Routing result containing:
                - mode: Routing mode ('single' or 'fano_line')
                - complexity: Computed or provided complexity score
                - assignments: List of colony assignments
                - fano_line: Fano line index (for multi-colony routing)
                - execution_plan: Human-readable execution plan

        Raises:
            KagamiValidationError: If inputs are invalid.
            KagamiAPIError: If the API request fails.
            KagamiConnectionError: If connection fails.
        """
        if not task:
            raise KagamiValidationError("task cannot be empty")
        if complexity is not None and (complexity < 0.0 or complexity > 1.0):
            raise KagamiValidationError(f"complexity ({complexity}) must be between 0.0 and 1.0")

        return await self._request(
            "POST",
            "/v1/route",
            json={
                "task": task,
                "context": context or {},
                "complexity": complexity,
            },
            timeout=ROUTE_TIMEOUT,
        )

    async def coordinate_execution(
        self, assignments: list[dict[str, Any]], dependencies: dict[str, list[str]] | None = None
    ) -> dict[str, Any]:
        """Coordinate multi-colony task execution.

        Args:
            assignments: Colony assignments from route_task result.
            dependencies: Optional task dependency graph.
                Keys are task IDs, values are lists of dependent task IDs.

        Returns:
            Coordination result containing:
                - job_id: Unique job identifier
                - status: Execution status
                - execution_time_ms: Total execution time in milliseconds
                - results: Results from each colony

        Raises:
            KagamiValidationError: If inputs are invalid.
            KagamiAPIError: If the API request fails.
            KagamiConnectionError: If connection fails.

        Note:
            This endpoint requires a Pro tier API key (sk_pro_*).
        """
        if not assignments:
            raise KagamiValidationError("assignments cannot be empty")
        if not isinstance(assignments, list):
            raise KagamiValidationError(
                f"assignments must be a list, got {type(assignments).__name__}"
            )

        return await self._request(
            "POST",
            "/v1/coordinate",
            json={
                "assignments": assignments,
                "dependencies": dependencies or {},
                "timeout_ms": 30000,
            },
            timeout=COORDINATE_TIMEOUT,
        )

    async def get_health(self) -> dict[str, Any]:
        """Check API health status.

        Returns:
            Health status containing:
                - status: Health status string ('healthy', 'degraded', etc.)
                - version: API version
                - timestamp: Current server time

        Raises:
            KagamiConnectionError: If connection to the API fails.
            KagamiAPIError: If the health check fails.
        """
        return await self._request("GET", "/health", timeout=HEALTH_TIMEOUT)


# =============================================================================
# EXAMPLE 1: COMPRESS AND DECOMPRESS MODEL
# =============================================================================


async def example_compression(client: KagamiOSClient) -> None:
    """Example: Compress and decompress model weights.

    Args:
        client: Initialized KagamiOSClient instance.
    """
    print("=" * 60)
    print("EXAMPLE 1: E8 Model Compression")
    print("=" * 60)

    # Create sample model weights (small for demo)
    print("\n1. Creating sample model weights (1024 x 512)...")
    import random

    random.seed(42)
    weights: list[list[float]] = [[random.random() for _ in range(512)] for _ in range(1024)]
    print(
        f"   Original size: {len(weights)} x {len(weights[0])} = {len(weights) * len(weights[0])} weights"
    )

    # Compress
    print("\n2. Compressing using E8 lattice quantization...")
    compress_result = await client.compress_model(weights, num_codebooks=4)
    print(f"   [OK] Compression ratio: {compress_result['compression_ratio']:.2f}x")
    print(f"   [OK] Bitrate: {compress_result['bitrate']:.2f} bits/weight")
    print(f"   [OK] Job ID: {compress_result['job_id']}")

    # Decompress
    print("\n3. Decompressing...")
    decompress_result = await client.decompress_model(
        compress_result["compressed_data"],
        [len(weights), len(weights[0])],
        compress_result["job_id"],
    )
    print(f"   [OK] Reconstruction error (MSE): {decompress_result['reconstruction_error']:.6f}")
    print(f"   [OK] Shape: {decompress_result['shape']}")

    print("\n[OK] Compression example complete!\n")


# =============================================================================
# EXAMPLE 2: SAFETY VERIFICATION
# =============================================================================


async def example_safety(client: KagamiOSClient) -> None:
    """Example: Verify safety of operations using Control Barrier Functions.

    Args:
        client: Initialized KagamiOSClient instance.
    """
    print("=" * 60)
    print("EXAMPLE 2: Safety Verification")
    print("=" * 60)

    # Test 1: Safe operation
    print("\n1. Verifying safe operation...")
    result1 = await client.verify_safety(
        operation="send_message",
        action={"recipient": "user123", "content": "Hello, how are you?"},
        context={"channel": "general"},
        user_input="Hello, how are you?",
    )
    print(f"   Safe: {result1['safe']}")
    print(f"   h(x): {result1['h_value']:.3f}")
    print(f"   Recommendation: {result1['recommendation']}")

    # Test 2: Potentially unsafe operation
    print("\n2. Verifying potentially unsafe operation...")
    result2 = await client.verify_safety(
        operation="execute_code",
        action={"code": "import os; os.system('rm -rf /')"},
        context={"sandbox": False},
        user_input="Delete all files",
    )
    print(f"   Safe: {result2['safe']}")
    print(f"   h(x): {result2['h_value']:.3f}")
    print(f"   Recommendation: {result2['recommendation']}")

    # Test 3: Generate certificate (Pro tier only)
    if API_KEY.startswith("sk_pro_"):
        print("\n3. Generating safety certificate...")
        cert = await client.certify_safety(
            system_name="Example System",
            operation_context={"version": "1.0.0"},
            test_results={"all_tests_passed": True},
        )
        print(f"   [OK] Certificate ID: {cert['certificate_id']}")
        print(f"   [OK] Confidence: {cert['confidence']}")
        print(f"   [OK] Component proofs: {len(cert['component_proofs'])}")

    print("\n[OK] Safety verification example complete!\n")


# =============================================================================
# EXAMPLE 3: MULTI-AGENT ROUTING
# =============================================================================


async def example_routing(client: KagamiOSClient) -> None:
    """Example: Route tasks to agent colonies using Fano plane geometry.

    Args:
        client: Initialized KagamiOSClient instance.
    """
    print("=" * 60)
    print("EXAMPLE 3: Multi-Agent Routing")
    print("=" * 60)

    # Test 1: Simple task (single colony)
    print("\n1. Routing simple task...")
    result1 = await client.route_task(
        task="Fix a simple bug in the code",
        context={"file": "utils.py"},
        complexity=0.2,
    )
    print(f"   Mode: {result1['mode']}")
    print(f"   Complexity: {result1['complexity']:.2f}")
    print(f"   Assigned colonies: {[a['colony_name'] for a in result1['assignments']]}")
    print(f"   Plan: {result1['execution_plan']}")

    # Test 2: Complex task (Fano line)
    if API_KEY.startswith("sk_pro_"):
        print("\n2. Routing complex task...")
        result2 = await client.route_task(
            task="Design and implement a new distributed system component",
            context={"domain": "backend", "scale": "high"},
            complexity=0.5,
        )
        print(f"   Mode: {result2['mode']}")
        print(f"   Complexity: {result2['complexity']:.2f}")
        print(f"   Assigned colonies: {[a['colony_name'] for a in result2['assignments']]}")
        print(f"   Fano line: {result2['fano_line']}")
        print(f"   Plan: {result2['execution_plan']}")

        # Coordinate execution
        print("\n3. Coordinating execution...")
        coord_result = await client.coordinate_execution(result2["assignments"])
        print(f"   [OK] Job ID: {coord_result['job_id']}")
        print(f"   [OK] Status: {coord_result['status']}")
        print(f"   [OK] Execution time: {coord_result['execution_time_ms']}ms")
        print(f"   [OK] Results from {len(coord_result['results'])} colonies")

    print("\n[OK] Routing example complete!\n")


# =============================================================================
# MAIN
# =============================================================================


async def main() -> None:
    """Run all examples demonstrating KagamiOS API usage.

    This function:
    1. Validates environment configuration
    2. Checks API health
    3. Runs compression, safety, and routing examples
    4. Properly manages client lifecycle with connection pooling
    """
    print("\nKagamiOS API Usage Examples")
    print("=" * 60)
    print(f"API Base URL: {API_BASE_URL}")
    print(f"API Key: {API_KEY[:10]}...")
    print("=" * 60)

    # Health check
    client = KagamiOSClient(API_KEY)
    try:
        health = await client.get_health()
        print(f"\n✓ API Status: {health['status']}")
    except Exception as e:
        print(f"\n✗ API unreachable: {e}")
        print("\nMake sure the API server is running:")
        print("  python -m kagami_api.main")
        sys.exit(1)

        # Run examples
        try:
            await example_compression(client)
            await example_safety(client)
            await example_routing(client)

            print("=" * 60)
            print("All examples completed successfully!")
            print("=" * 60)

        except KagamiValidationError as e:
            print(f"\n[ERROR] Validation Error: {e.message}")
            sys.exit(1)

        except KagamiAPIError as e:
            print(f"\n[ERROR] API Error: {e.message}")
            if e.status_code:
                print(f"   Status Code: {e.status_code}")
            if e.response_body:
                print(f"   Response: {e.response_body}")
            sys.exit(1)

        except KagamiConnectionError as e:
            print(f"\n[ERROR] Connection Error: {e.message}")
            sys.exit(1)

        except Exception as e:
            print(f"\n[ERROR] Unexpected Error: {e}")
            import traceback

            traceback.print_exc()
            sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main())
