#!/usr/bin/env python3
"""Comprehensive Production Framework Demo.

This script demonstrates how to use all the comprehensive production-ready
frameworks together: error handling, validation, logging, configuration,
and resource management.
"""

import asyncio
import tempfile
import time
from pathlib import Path

# Import comprehensive frameworks
from kagami.core.production_bootstrap import initialize_production_system
from kagami.core.logging import get_logger, LogContext, log_context
from kagami.core.validation import validate_string, validate_integer, validate_path
from kagami.core.error_handling import error_handler, error_context, RetryStrategy
from kagami.core.resource_management import resource_context, managed_resource, CleanupPriority
from kagami.core.config import get_config_manager, ConfigSchema


class DemoResource:
    """Example resource that needs cleanup."""

    def __init__(self, name: str):
        self.name = name
        self.file_handle: object | None = None
        self.logger = get_logger(f"{__name__}.DemoResource")

        # Create a temporary file as an example resource
        self.temp_file = Path(tempfile.mktemp(suffix=f"_demo_{name}.tmp"))
        self.temp_file.write_text(f"Demo resource: {name}")
        self.logger.info(f"Created demo resource: {self.temp_file}")

    def cleanup(self) -> None:
        """Cleanup method called automatically by resource manager."""
        if self.temp_file and self.temp_file.exists():
            self.temp_file.unlink()
            self.logger.info(f"Cleaned up demo resource: {self.temp_file}")


@managed_resource("demo_service", priority=CleanupPriority.HIGH)
class DemoService:
    """Example service with automatic resource management."""

    def __init__(self, config_value: str):
        self.config_value = config_value
        self.logger = get_logger(f"{__name__}.DemoService")
        self.logger.info(f"Demo service initialized with config: {config_value}")

    def cleanup(self) -> None:
        """Cleanup method."""
        self.logger.info("Demo service cleaned up")


class ProductionFrameworkDemo:
    """Demonstrates comprehensive production framework usage."""

    def __init__(self):
        self.logger = get_logger(__name__)

    @error_handler(
        retry_attempts=3,
        retry_strategy=RetryStrategy.EXPONENTIAL_BACKOFF_WITH_JITTER,
        timeout=10.0,
        log_errors=True,
    )
    async def run_demo(self) -> None:
        """Run the comprehensive demo."""

        # Initialize production system
        self.logger.info("=== Production Framework Demo Starting ===")

        bootstrap = initialize_production_system(
            app_name="demo_app",
            enable_hot_reload=True,
            enable_leak_detection_flag=True,
            cleanup_on_startup=True,
        )

        try:
            await self._demonstrate_frameworks()
        finally:
            # Graceful shutdown
            bootstrap.shutdown()

    async def _demonstrate_frameworks(self) -> None:
        """Demonstrate all frameworks working together."""

        # === Configuration Management Demo ===
        with error_context("configuration_demo"):
            await self._demo_configuration()

        # === Validation Demo ===
        with error_context("validation_demo"):
            await self._demo_validation()

        # === Error Handling Demo ===
        with error_context("error_handling_demo"):
            await self._demo_error_handling()

        # === Resource Management Demo ===
        with error_context("resource_management_demo"):
            await self._demo_resource_management()

        # === Integrated Demo ===
        with error_context("integrated_demo"):
            await self._demo_integrated_workflow()

    async def _demo_configuration(self) -> None:
        """Demonstrate comprehensive configuration management."""
        self.logger.info("--- Configuration Management Demo ---")

        config_manager = get_config_manager("demo_app")

        # Define configuration schemas
        schemas = {
            "demo.service_name": ConfigSchema(
                field_type=str, default="demo_service", description="Name of the demo service"
            ),
            "demo.max_connections": ConfigSchema(
                field_type=int,
                default=100,
                min_value=1,
                max_value=1000,
                description="Maximum number of connections",
            ),
            "demo.enable_features": ConfigSchema(
                field_type=bool, default=True, description="Enable advanced features"
            ),
            "demo.timeout": ConfigSchema(
                field_type=float,
                default=30.0,
                min_value=1.0,
                max_value=300.0,
                description="Operation timeout in seconds",
            ),
        }

        for key, schema in schemas.items():
            config_manager.define_schema(key, schema)

        # Load defaults and validate
        config_manager.load_defaults()
        validation_errors = config_manager.validate_all()

        if validation_errors:
            self.logger.error(f"Configuration validation failed: {validation_errors}")
        else:
            self.logger.info("Configuration validation passed")

        # Demonstrate configuration usage
        service_name = config_manager.get("demo.service_name")
        max_connections = config_manager.get_typed("demo.max_connections", int)
        enable_features = config_manager.get_typed("demo.enable_features", bool)

        self.logger.info(
            "Configuration loaded",
            extra={
                "service_name": service_name,
                "max_connections": max_connections,
                "enable_features": enable_features,
            },
        )

    async def _demo_validation(self) -> None:
        """Demonstrate comprehensive validation."""
        self.logger.info("--- Validation Demo ---")

        # String validation
        string_result = validate_string(
            "demo_value",
            min_length=5,
            max_length=20,
            pattern=r"^demo_\w+$",
            field_name="demo_field",
        )

        if string_result.valid:
            self.logger.info(f"String validation passed: {string_result.sanitized_value}")
        else:
            self.logger.error(f"String validation failed: {string_result.errors}")

        # Integer validation
        integer_result = validate_integer(
            150, min_value=100, max_value=200, field_name="demo_number"
        )

        if integer_result.valid:
            self.logger.info(f"Integer validation passed: {integer_result.sanitized_value}")
        else:
            self.logger.error(f"Integer validation failed: {integer_result.errors}")

        # Path validation
        temp_path = Path(tempfile.mktemp())
        path_result = validate_path(temp_path, must_exist=False, field_name="demo_path")

        if path_result.valid:
            self.logger.info(f"Path validation passed: {path_result.sanitized_value}")
        else:
            self.logger.error(f"Path validation failed: {path_result.errors}")

    async def _demo_error_handling(self) -> None:
        """Demonstrate comprehensive error handling."""
        self.logger.info("--- Error Handling Demo ---")

        @error_handler(
            retry_attempts=2, retry_strategy=RetryStrategy.FIXED, retry_delay=0.1, log_errors=True
        )
        def unreliable_function(should_fail: bool = True) -> str:
            if should_fail:
                raise ConnectionError("Simulated network error")
            return "Success!"

        # Demonstrate retry behavior
        try:
            # This will fail and retry
            result = unreliable_function(should_fail=True)
            self.logger.info(f"Unreliable function result: {result}")
        except Exception as e:
            self.logger.info(f"Function failed after retries: {e}")

        # This will succeed
        try:
            result = unreliable_function(should_fail=False)
            self.logger.info(f"Reliable function result: {result}")
        except Exception as e:
            self.logger.error(f"Unexpected error: {e}")

    async def _demo_resource_management(self) -> None:
        """Demonstrate comprehensive resource management."""
        self.logger.info("--- Resource Management Demo ---")

        # Demonstrate resource context manager
        with resource_context(
            DemoResource("context_managed"), name="demo_resource_1", priority=CleanupPriority.HIGH
        ) as resource:
            self.logger.info(f"Using resource: {resource.name}")
            # Resource will be automatically cleaned up

        # Demonstrate managed resource class
        DemoService("production_config")
        self.logger.info("Service created and will be automatically managed")

        # Resource manager will handle cleanup automatically

    async def _demo_integrated_workflow(self) -> None:
        """Demonstrate all frameworks working together."""
        self.logger.info("--- Integrated Workflow Demo ---")

        # Set up logging context for the workflow
        context = LogContext(
            operation="integrated_demo_workflow",
            component="production_demo",
            metadata={"workflow_id": "demo_001"},
        )

        async with log_context(context):
            # Start performance tracking
            logger = get_logger(__name__)
            tracking_id = logger.start_performance_tracking("integrated_workflow")

            try:
                # Step 1: Validate input parameters
                workflow_config = {
                    "batch_size": 50,
                    "timeout": 30.0,
                    "output_path": "/tmp/demo_output",
                }

                for key, value in workflow_config.items():
                    if key == "batch_size":
                        result = validate_integer(value, min_value=1, max_value=100)
                    elif key == "timeout":
                        result = validate_integer(int(value), min_value=1, max_value=60)
                    else:
                        result = validate_string(str(value), min_length=1)

                    if not result.valid:
                        raise ValueError(f"Invalid {key}: {result.errors}")

                self.logger.info("Input validation passed", extra=workflow_config)

                # Step 2: Initialize resources
                with resource_context(
                    DemoResource("workflow_resource"),
                    name="workflow_resource",
                    priority=CleanupPriority.MEDIUM,
                ) as resource:
                    # Step 3: Perform work with error handling
                    @error_handler(
                        retry_attempts=2, timeout=workflow_config["timeout"], log_errors=True
                    )
                    async def process_batch() -> dict:
                        # Simulate work
                        await asyncio.sleep(0.1)
                        return {
                            "processed": workflow_config["batch_size"],
                            "resource_used": resource.name,
                            "timestamp": time.time(),
                        }

                    result = await process_batch()

                    self.logger.info("Workflow completed successfully", extra=result)

                    # Finish performance tracking
                    logger.finish_performance_tracking(tracking_id, success=True)

            except Exception as e:
                logger.finish_performance_tracking(tracking_id, success=False, error=e)
                raise

        self.logger.info("Integrated workflow demonstration completed")


async def main():
    """Main entry point for the demo."""
    demo = ProductionFrameworkDemo()

    try:
        await demo.run_demo()
        print("\n" + "=" * 60)
        print("🎉 Production Framework Demo Completed Successfully!")
        print("=" * 60)
        print("\nKey features demonstrated:")
        print("✅ Comprehensive error handling with retries and circuit breakers")
        print("✅ Input validation with security scanning and sanitization")
        print("✅ Structured logging with context and performance tracking")
        print("✅ Configuration management with hot-reloading and validation")
        print("✅ Resource management with automatic cleanup and leak detection")
        print("✅ Production-ready bootstrap and graceful shutdown")
        print("\nAll frameworks work together seamlessly for production deployment!")

    except Exception as e:
        print(f"\n❌ Demo failed: {e}")
        raise


if __name__ == "__main__":
    asyncio.run(main())
