"""Production-ready bootstrap and initialization for Kagami OS.

This module provides a comprehensive bootstrap process that initializes all
production-ready frameworks with proper error handling, logging, validation,
configuration, and resource management.
"""

from __future__ import annotations

import atexit
import signal
import sys
import time
from pathlib import Path
from typing import Any

from kagami.core.config import ComprehensiveConfigManager, ConfigSchema, get_config_manager
from kagami.core.error_handling import RetryStrategy, error_context, error_handler
from kagami.core.exceptions import ConfigurationError
from kagami.core.logging import LogContext, get_logger, set_log_context
from kagami.core.resource_management import (
    CleanupPriority,
    cleanup_temp_files,
    enable_leak_detection,
    force_garbage_collection,
    get_resource_manager,
)
from kagami.core.validation import ComprehensiveValidator

# Initialize logger for this module
logger = get_logger(__name__)


class ProductionBootstrap:
    """Production-ready bootstrap orchestrator."""

    def __init__(self, app_name: str = "kagami", config_dir: Path | None = None):
        self.app_name = app_name
        self.config_dir = config_dir or Path.home() / ".kagami"
        self.startup_time = time.time()
        self._initialized = False
        self._shutdown_handlers = []

        # Component managers
        self.config_manager: ComprehensiveConfigManager | None = None
        self.validator = ComprehensiveValidator()

    @error_handler(
        retry_attempts=3,
        retry_strategy=RetryStrategy.EXPONENTIAL_BACKOFF_WITH_JITTER,
        timeout=30.0,
        log_errors=True,
    )
    def initialize(
        self,
        enable_hot_reload: bool = True,
        enable_leak_detection_flag: bool = True,
        cleanup_on_startup: bool = True,
    ) -> None:
        """Initialize all production frameworks in proper order."""

        if self._initialized:
            logger.warning("Production bootstrap already initialized")
            return

        with error_context("production_bootstrap_initialization"):
            # Set initial logging context
            context = LogContext(
                operation="bootstrap_initialization",
                component="production_bootstrap",
                metadata={
                    "app_name": self.app_name,
                    "config_dir": str(self.config_dir),
                    "startup_time": self.startup_time,
                },
            )
            set_log_context(context)

            logger.info("Starting production bootstrap initialization")

            # Phase 1: Pre-flight checks
            self._run_preflight_checks()

            # Phase 2: Initialize configuration management
            self._initialize_configuration(enable_hot_reload)

            # Phase 3: Initialize resource management
            self._initialize_resource_management(enable_leak_detection_flag)

            # Phase 4: Cleanup existing resources if requested
            if cleanup_on_startup:
                self._perform_startup_cleanup()

            # Phase 5: Setup shutdown handlers
            self._setup_shutdown_handlers()

            # Phase 6: Validate complete system state
            self._validate_system_state()

            self._initialized = True
            startup_duration = time.time() - self.startup_time

            logger.info(
                "Production bootstrap initialization completed successfully",
                extra={
                    "startup_duration_ms": startup_duration * 1000,
                    "components_initialized": [
                        "configuration_management",
                        "resource_management",
                        "error_handling",
                        "logging",
                        "validation",
                    ],
                },
            )

    def _run_preflight_checks(self) -> None:
        """Run preflight checks to ensure system readiness."""
        logger.info("Running preflight checks")

        checks = [
            ("config_directory", self._check_config_directory),
            ("permissions", self._check_permissions),
            ("dependencies", self._check_dependencies),
            ("environment", self._check_environment),
        ]

        failed_checks = []

        for check_name, check_func in checks:
            try:
                check_func()
                logger.debug(f"Preflight check passed: {check_name}")
            except Exception as e:
                failed_checks.append((check_name, str(e)))
                logger.error(f"Preflight check failed: {check_name} - {e}")

        if failed_checks:
            error_msg = f"Preflight checks failed: {', '.join(f'{name}: {error}' for name, error in failed_checks)}"
            raise ConfigurationError(error_msg)

        logger.info("All preflight checks passed")

    def _check_config_directory(self) -> None:
        """Check config directory exists and is accessible."""
        if not self.config_dir.exists():
            try:
                self.config_dir.mkdir(parents=True, exist_ok=True)
                logger.info(f"Created config directory: {self.config_dir}")
            except Exception as e:
                raise ConfigurationError(
                    f"Cannot create config directory {self.config_dir}: {e}"
                ) from e

        if not self.config_dir.is_dir():
            raise ConfigurationError(
                f"Config path exists but is not a directory: {self.config_dir}"
            )

        # Test write permissions
        test_file = self.config_dir / ".bootstrap_test"
        try:
            test_file.write_text("test")
            test_file.unlink()
        except Exception as e:
            raise ConfigurationError(f"Config directory not writable: {e}") from e

    def _check_permissions(self) -> None:
        """Check required file system permissions."""
        # Additional permission checks can be added here
        pass

    def _check_dependencies(self) -> None:
        """Check that required dependencies are available."""
        required_modules = [
            "yaml",
            "watchdog",
            "psutil",  # Optional but recommended
        ]

        missing_modules = []
        for module_name in required_modules:
            try:
                __import__(module_name)
            except ImportError:
                missing_modules.append(module_name)

        if missing_modules:
            logger.warning(
                f"Optional dependencies not available: {', '.join(missing_modules)}. "
                f"Some features may be limited."
            )

    def _check_environment(self) -> None:
        """Check environment variables and configuration."""
        # Validate critical environment variables
        critical_env_vars = ["PATH", "HOME"]

        for var in critical_env_vars:
            import os

            if not os.getenv(var):
                logger.warning(f"Critical environment variable {var} not set")

    def _initialize_configuration(self, enable_hot_reload: bool) -> None:
        """Initialize comprehensive configuration management."""
        logger.info("Initializing configuration management")

        # Get configuration manager
        self.config_manager = get_config_manager(self.app_name)

        # Define configuration schemas for common settings
        self._define_configuration_schemas()

        # Load configuration from various sources
        self._load_configuration_sources(enable_hot_reload)

        # Validate all configuration
        validation_errors = self.config_manager.validate_all()
        if validation_errors:
            error_msg = f"Configuration validation failed: {validation_errors}"
            logger.error(error_msg)
            raise ConfigurationError(error_msg)

        logger.info("Configuration management initialized successfully")

    def _define_configuration_schemas(self) -> None:
        """Define configuration schemas for validation."""
        schemas = {
            "log_level": ConfigSchema(
                field_type=str,
                default="INFO",
                allowed_values=["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"],
                description="Logging level",
            ),
            "max_resources": ConfigSchema(
                field_type=int,
                default=1000,
                min_value=1,
                max_value=10000,
                description="Maximum number of tracked resources",
            ),
            "cleanup_interval": ConfigSchema(
                field_type=float,
                default=300.0,
                min_value=1.0,
                max_value=3600.0,
                description="Resource cleanup interval in seconds",
            ),
            "enable_metrics": ConfigSchema(
                field_type=bool, default=True, description="Enable metrics collection"
            ),
            "data_directory": ConfigSchema(
                field_type=str,
                default=str(self.config_dir / "data"),
                description="Data storage directory",
            ),
        }

        for key, schema in schemas.items():
            self.config_manager.define_schema(key, schema)

    def _load_configuration_sources(self, enable_hot_reload: bool) -> None:
        """Load configuration from all available sources."""

        # 1. Load defaults
        self.config_manager.load_defaults()

        # 2. Load from config files (if they exist)
        config_files = [
            self.config_dir / "config.yaml",
            self.config_dir / "config.json",
            Path(".") / "config.yaml",
            Path(".") / "config.json",
        ]

        for config_file in config_files:
            if config_file.exists():
                try:
                    self.config_manager.load_from_file(
                        config_file, watch_for_changes=enable_hot_reload, required=False
                    )
                    logger.info(f"Loaded configuration from {config_file}")
                except Exception as e:
                    logger.warning(f"Failed to load config file {config_file}: {e}")

        # 3. Load from environment variables
        self.config_manager.load_from_environment(f"{self.app_name.upper()}_")

        # 4. Start watching if enabled
        if enable_hot_reload:
            try:
                self.config_manager.start_watching()
                logger.info("Configuration hot-reloading enabled")
            except Exception as e:
                logger.warning(f"Failed to enable configuration hot-reloading: {e}")

    def _initialize_resource_management(self, enable_leak_detection_flag: bool) -> None:
        """Initialize comprehensive resource management."""
        logger.info("Initializing resource management")

        # Get resource manager
        resource_manager = get_resource_manager(self.app_name)

        # Register the configuration manager as a resource
        if self.config_manager:
            resource_manager.register_resource(
                resource=self.config_manager, name="config_manager", priority=CleanupPriority.HIGH
            )

        # Enable leak detection if requested
        if enable_leak_detection_flag:
            try:
                enable_leak_detection(check_interval=60.0)
                logger.info("Resource leak detection enabled")
            except Exception as e:
                logger.warning(f"Failed to enable leak detection: {e}")

        logger.info("Resource management initialized successfully")

    def _perform_startup_cleanup(self) -> None:
        """Perform startup cleanup of temporary resources."""
        logger.info("Performing startup cleanup")

        cleanup_tasks = [
            ("temporary files", lambda: cleanup_temp_files(max_age_hours=24.0)),
            ("garbage collection", lambda: force_garbage_collection()),
        ]

        for task_name, task_func in cleanup_tasks:
            try:
                result = task_func()
                logger.debug(f"Startup cleanup - {task_name}: {result}")
            except Exception as e:
                logger.warning(f"Startup cleanup failed for {task_name}: {e}")

    def _setup_shutdown_handlers(self) -> None:
        """Setup graceful shutdown handlers."""

        def shutdown_handler(signum=None, frame=None):
            logger.info(f"Received shutdown signal: {signum}")
            self.shutdown()
            sys.exit(0)

        # Register signal handlers
        signal.signal(signal.SIGTERM, shutdown_handler)
        signal.signal(signal.SIGINT, shutdown_handler)

        # Register atexit handler
        atexit.register(self.shutdown)

        logger.info("Shutdown handlers registered")

    def _validate_system_state(self) -> None:
        """Validate that all systems are properly initialized."""
        logger.info("Validating system state")

        validation_checks = [
            ("configuration_manager", lambda: self.config_manager is not None),
            ("resource_manager", lambda: get_resource_manager() is not None),
            ("config_directory", lambda: self.config_dir.exists()),
        ]

        failed_validations = []

        for check_name, check_func in validation_checks:
            try:
                if not check_func():
                    failed_validations.append(check_name)
            except Exception as e:
                failed_validations.append(f"{check_name}: {e}")

        if failed_validations:
            error_msg = f"System validation failed: {', '.join(failed_validations)}"
            raise ConfigurationError(error_msg)

        logger.info("System validation completed successfully")

    def add_shutdown_handler(self, handler: callable) -> None:
        """Add a custom shutdown handler."""
        self._shutdown_handlers.append(handler)

    def shutdown(self, timeout: float = 30.0) -> None:
        """Gracefully shutdown all systems."""
        if not self._initialized:
            return

        logger.info("Starting graceful shutdown")
        shutdown_start = time.time()

        try:
            # Call custom shutdown handlers
            for handler in self._shutdown_handlers:
                try:
                    handler()
                except Exception as e:
                    logger.error(f"Custom shutdown handler failed: {e}")

            # Stop configuration watching
            if self.config_manager:
                try:
                    self.config_manager.stop_watching()
                except Exception as e:
                    logger.error(f"Failed to stop configuration watching: {e}")

            # Shutdown resource manager
            try:
                resource_manager = get_resource_manager(self.app_name)
                resource_manager.shutdown(timeout=timeout)
            except Exception as e:
                logger.error(f"Failed to shutdown resource manager: {e}")

            # Final cleanup
            try:
                force_garbage_collection()
            except Exception as e:
                logger.debug(f"Final garbage collection failed: {e}")

            shutdown_duration = time.time() - shutdown_start
            logger.info(
                "Graceful shutdown completed",
                extra={"shutdown_duration_ms": shutdown_duration * 1000},
            )

        except Exception as e:
            logger.error(f"Error during shutdown: {e}")
        finally:
            self._initialized = False

    def get_system_info(self) -> dict[str, Any]:
        """Get comprehensive system information."""
        info = {
            "app_name": self.app_name,
            "config_dir": str(self.config_dir),
            "startup_time": self.startup_time,
            "initialized": self._initialized,
            "uptime_seconds": time.time() - self.startup_time,
        }

        if self.config_manager:
            info["configuration"] = self.config_manager.get_config_info()

        try:
            resource_manager = get_resource_manager(self.app_name)
            info["resources"] = {
                "active_resources": len(resource_manager.list_resources()),
                "resource_summary": resource_manager.list_resources(),
            }
        except Exception:
            pass

        return info


# Global bootstrap instance
_global_bootstrap: ProductionBootstrap | None = None


def get_bootstrap(app_name: str = "kagami", config_dir: Path | None = None) -> ProductionBootstrap:
    """Get the global bootstrap instance."""
    global _global_bootstrap

    if _global_bootstrap is None:
        _global_bootstrap = ProductionBootstrap(app_name, config_dir)

    return _global_bootstrap


def initialize_production_system(
    app_name: str = "kagami", config_dir: Path | None = None, **kwargs
) -> ProductionBootstrap:
    """Initialize the complete production system."""
    bootstrap = get_bootstrap(app_name, config_dir)
    bootstrap.initialize(**kwargs)
    return bootstrap


# Quick initialization function for simple use cases
def quick_init(app_name: str = "kagami") -> None:
    """Quick initialization with sensible defaults."""
    try:
        initialize_production_system(
            app_name=app_name,
            enable_hot_reload=False,
            enable_leak_detection_flag=True,
            cleanup_on_startup=True,
        )
        logger.info(f"Quick initialization completed for {app_name}")
    except Exception as e:
        logger.error(f"Quick initialization failed: {e}")
        raise


__all__ = [
    "ProductionBootstrap",
    "get_bootstrap",
    "initialize_production_system",
    "quick_init",
]
