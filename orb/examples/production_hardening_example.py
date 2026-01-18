#!/usr/bin/env python3
"""
Example demonstrating comprehensive production hardening for 100/100 deployment.

This example shows how to use all the production hardening features:
- Health checks
- Circuit breakers
- Distributed tracing
- Metrics collection
- Automated alerting
- Graceful degradation
- Security scanning
- Deployment validation
- Structured logging
"""

import asyncio
import os
import sys
import time
from typing import Any

# Add the project root to Python path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from kagami.production import (
    ProductionConfig,
    initialize_production,
    start_production,
    stop_production,
    with_circuit_breaker,
    with_graceful_degradation,
    with_tracing,
    with_structured_logging,
    get_logger,
    validate_production_deployment,
)


# Example service class with production hardening
class UserService:
    """Example user service with comprehensive production hardening."""

    def __init__(self):
        self.logger = get_logger("user_service")

    @with_tracing("user_service.get_user")
    @with_circuit_breaker("database", timeout=10.0, failure_threshold=3)
    @with_graceful_degradation("get_user", cache_result=True)
    @with_structured_logging("user_service")
    async def get_user(self, user_id: str) -> dict[str, Any]:
        """Get user with full production hardening."""
        await self.logger.info(f"Fetching user {user_id}")

        # Simulate database call
        await asyncio.sleep(0.1)

        # Simulate occasional errors for demonstration
        if user_id == "error_user":
            raise ValueError("Simulated database error")

        # Simulate slow responses
        if user_id == "slow_user":
            await asyncio.sleep(5)

        user_data = {
            "id": user_id,
            "name": f"User {user_id}",
            "email": f"user{user_id}@example.com",
            "created_at": time.time(),
        }

        await self.logger.info(f"Successfully fetched user {user_id}")
        return user_data

    @with_tracing("user_service.create_user")
    @with_circuit_breaker("database")
    @with_structured_logging("user_service")
    async def create_user(self, user_data: dict[str, Any]) -> str:
        """Create user with validation and hardening."""
        await self.logger.info("Creating new user", user_email=user_data.get("email"))

        # Simulate validation
        if not user_data.get("email"):
            await self.logger.error("User creation failed: missing email")
            raise ValueError("Email is required")

        # Simulate database insert
        await asyncio.sleep(0.2)

        user_id = f"user_{int(time.time())}"
        await self.logger.info("User created successfully", user_id=user_id)

        return user_id


class ApiService:
    """Example API service with security and monitoring."""

    def __init__(self):
        self.logger = get_logger("api_service")
        self.user_service = UserService()

    @with_tracing("api_service.handle_request")
    @with_structured_logging("api_service")
    async def handle_request(self, endpoint: str, request_data: dict[str, Any]) -> dict[str, Any]:
        """Handle API request with comprehensive monitoring."""
        start_time = time.time()

        try:
            await self.logger.info(
                f"Handling request to {endpoint}",
                endpoint=endpoint,
                request_size=len(str(request_data)),
            )

            # Route to appropriate handler
            if endpoint == "/users/{id}":
                user_id = request_data.get("user_id", "123")
                result = await self.user_service.get_user(user_id)
            elif endpoint == "/users":
                result = await self.user_service.create_user(request_data)
            else:
                raise ValueError(f"Unknown endpoint: {endpoint}")

            duration = time.time() - start_time
            await self.logger.info(
                "Request completed successfully", endpoint=endpoint, duration_ms=duration * 1000
            )

            return {"success": True, "data": result}

        except Exception as e:
            duration = time.time() - start_time
            await self.logger.error(
                "Request failed", exception=e, endpoint=endpoint, duration_ms=duration * 1000
            )
            return {"success": False, "error": str(e)}


async def demonstrate_circuit_breaker():
    """Demonstrate circuit breaker functionality."""
    print("\n=== Circuit Breaker Demonstration ===")

    service = UserService()

    print("Testing normal operation...")
    result = await service.get_user("normal_user")
    print(f"✓ Normal request succeeded: {result['name']}")

    print("Testing error conditions (will trigger circuit breaker)...")
    for i in range(5):
        try:
            await service.get_user("error_user")
        except Exception as e:
            print(f"✗ Request {i + 1} failed: {e}")

    print("Circuit breaker should now be open, requests will fail fast...")
    try:
        await service.get_user("normal_user")
        print("✓ Request succeeded (unexpected)")
    except Exception as e:
        print(f"✓ Request failed fast due to circuit breaker: {e}")


async def demonstrate_graceful_degradation():
    """Demonstrate graceful degradation."""
    print("\n=== Graceful Degradation Demonstration ===")

    service = UserService()

    print("Testing slow response (should use cached data on retry)...")

    # First request - will be slow
    start_time = time.time()
    try:
        result = await service.get_user("slow_user")
        duration = time.time() - start_time
        print(f"✓ First request completed in {duration:.2f}s: {result['name']}")
    except Exception as e:
        print(f"✗ First request failed: {e}")

    # Second request - should use cached data if available
    start_time = time.time()
    try:
        result = await service.get_user("slow_user")
        duration = time.time() - start_time
        print(f"✓ Second request completed in {duration:.2f}s (cached): {result['name']}")
    except Exception as e:
        print(f"✗ Second request failed: {e}")


async def demonstrate_security_scanning():
    """Demonstrate security scanning."""
    print("\n=== Security Scanning Demonstration ===")

    from kagami.production.security import get_security_manager

    # Initialize security manager if not already done
    try:
        security_manager = get_security_manager()

        # Test various attack patterns
        test_inputs = [
            {"name": "Normal User", "email": "user@example.com"},
            {"name": "'; DROP TABLE users; --", "email": "hacker@evil.com"},
            {"name": "<script>alert('xss')</script>", "email": "xss@test.com"},
            {"name": "Normal", "email": "user@example.com' UNION SELECT * FROM passwords"},
        ]

        for i, test_input in enumerate(test_inputs, 1):
            print(f"Testing input {i}: {test_input}")

            result = await security_manager.process_request(
                request_data={"body": test_input},
                endpoint="/users",
                user_id="test_user",
                ip_address="127.0.0.1",
            )

            if result["allowed"]:
                print("  ✓ Request allowed")
            else:
                print(f"  ✗ Request blocked: {result['reason']}")
                if result["violations"]:
                    for violation in result["violations"]:
                        print(f"    - {violation.description}")

    except RuntimeError as e:
        print(f"Security manager not initialized: {e}")


async def demonstrate_health_checks():
    """Demonstrate health check system."""
    print("\n=== Health Checks Demonstration ===")

    # Get production manager
    manager = await initialize_production()

    if manager.health_checker:
        print("Running comprehensive health checks...")
        results = await manager.health_checker.run_all_checks()

        for check_name, result in results.items():
            status_icon = "✓" if result.status.value == "healthy" else "✗"
            print(f"  {status_icon} {check_name}: {result.message} ({result.duration_ms:.1f}ms)")

        overall_status = manager.health_checker.get_system_status()
        print(f"\nOverall system status: {overall_status.value.upper()}")
    else:
        print("Health checker not configured (missing database/redis URLs)")


async def demonstrate_metrics_and_alerting():
    """Demonstrate metrics collection and alerting."""
    print("\n=== Metrics and Alerting Demonstration ===")

    from kagami.production.metrics import get_metrics_manager
    from kagami.production.alerting import get_alert_manager, create_system_resource_alert

    try:
        # Get metrics manager
        metrics_manager = get_metrics_manager()
        print("✓ Metrics system active")

        # Collect some metrics
        metrics_manager.business_collector.record_request("GET", "/users/123", 200, 0.15)
        metrics_manager.business_collector.record_request("POST", "/users", 201, 0.25)
        metrics_manager.business_collector.record_request("GET", "/users/456", 500, 0.05)

        print("✓ Recorded sample HTTP requests")

        # Demonstrate alerting
        get_alert_manager()

        # Create a test alert
        test_alert = create_system_resource_alert(
            resource_type="memory",
            usage_percent=95.0,
            threshold_percent=80.0,
            hostname="example-server",
        )

        print(f"✓ Created test alert: {test_alert.title}")

        # Get current metrics as text (Prometheus format)
        metrics_text = metrics_manager.get_metrics_text()
        print(f"✓ Generated metrics export ({len(metrics_text)} characters)")

    except RuntimeError as e:
        print(f"Metrics system not initialized: {e}")


async def run_deployment_validation():
    """Run comprehensive deployment validation."""
    print("\n=== Deployment Validation ===")

    # Use placeholder URLs for demonstration
    database_url = os.getenv("DATABASE_URL", "postgresql://user:pass@localhost/kagami")
    redis_url = os.getenv("REDIS_URL", "redis://localhost:6379")
    service_url = os.getenv("SERVICE_BASE_URL", "http://localhost:8000")

    print("Validating deployment against:")
    print(f"  Database: {database_url}")
    print(f"  Redis: {redis_url}")
    print(f"  Service: {service_url}")

    try:
        is_ready, report = await validate_production_deployment(
            database_url=database_url, redis_url=redis_url, service_url=service_url
        )

        print(f"\nDeployment Status: {'READY' if is_ready else 'NOT READY'}")
        print("\nValidation Report:")
        print(report)

    except Exception as e:
        print(f"Validation failed: {e}")


async def main():
    """Main demonstration function."""
    print("=== Kagami Production Hardening Demo ===")
    print("Demonstrating 100/100 deployment reliability features\n")

    # Configure production system
    config = ProductionConfig(
        environment="demo",
        service_name="kagami-demo",
        database_url=os.getenv("DATABASE_URL", "postgresql://user:pass@localhost/kagami"),
        redis_url=os.getenv("REDIS_URL", "redis://localhost:6379"),
        service_base_url="http://localhost:8000",
        secret_key="demo-secret-key-change-in-production",
        enable_system_metrics=True,
    )

    try:
        # Initialize production systems
        print("Initializing production hardening systems...")
        manager = await initialize_production(config)
        print("✓ Production systems initialized")

        # Start monitoring
        await start_production()
        print("✓ Production monitoring started")

        # Run demonstrations
        await demonstrate_health_checks()
        await demonstrate_security_scanning()
        await demonstrate_circuit_breaker()
        await demonstrate_graceful_degradation()
        await demonstrate_metrics_and_alerting()

        # API service demonstration
        print("\n=== API Service Demonstration ===")
        api_service = ApiService()

        # Test normal requests
        result = await api_service.handle_request("/users/{id}", {"user_id": "123"})
        print(f"✓ GET /users/123: {result}")

        # Test user creation
        result = await api_service.handle_request(
            "/users", {"name": "John Doe", "email": "john@example.com"}
        )
        print(f"✓ POST /users: {result}")

        # Test error handling
        result = await api_service.handle_request("/users", {"name": "No Email"})
        print(f"✗ POST /users (error): {result}")

        # Get system status
        print("\n=== System Status ===")
        status = await manager.get_system_status()
        print(f"System Status: {status}")

        # Run deployment validation
        await run_deployment_validation()

        print("\n=== Demo Complete ===")
        print("All production hardening features demonstrated successfully!")
        print("\nKey capabilities:")
        print("✓ Health checks for all services")
        print("✓ Circuit breakers for external dependencies")
        print("✓ Distributed tracing across service boundaries")
        print("✓ Comprehensive metrics collection")
        print("✓ Automated alerting for SLA violations")
        print("✓ Graceful degradation for service failures")
        print("✓ Security scanning and validation")
        print("✓ Deployment validation suite")
        print("✓ Structured logging and monitoring")

    except Exception as e:
        print(f"Demo failed: {e}")
        import traceback

        traceback.print_exc()

    finally:
        # Clean shutdown
        print("\nShutting down production systems...")
        await stop_production()
        print("✓ Production systems shutdown complete")


if __name__ == "__main__":
    # Set environment variables for demo if not already set
    if not os.getenv("LOG_LEVEL"):
        os.environ["LOG_LEVEL"] = "INFO"

    asyncio.run(main())
