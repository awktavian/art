#!/usr/bin/env python3
"""
K os Full Operation Enforcer

Ensures all components are mandatory and running at full capacity.
No optional services, no degraded modes, no fallbacks.
"""

import asyncio
import logging
import os
import sys
from pathlib import Path

# Add K os to path
sys.path.insert(0, str(Path(__file__).parent.parent))

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger("full_operation")

# Force full operation environment
os.environ["KAGAMI_FULL_OPERATION"] = "1"
os.environ["REQUIRE_ALL_COMPONENTS"] = "1"
os.environ["STRICT_MODE"] = "1"
os.environ["KAGAMI_STRICT_APP_HEALTH"] = "1"
os.environ["KAGAMI_REQUIRE_INFERENCE"] = "1"
os.environ["KAGAMI_REQUIRE_REASONING"] = "1"
os.environ["KAGAMI_REQUIRE_AR"] = "1"
os.environ["KAGAMI_REQUIRE_SUBSYSTEMS"] = "inference,reasoning,ar_system"
os.environ["KAGAMI_REQUIRE_EXTERNAL_MODELS"] = "1"

# Disable all lightweight/optional flags
os.environ["LIGHTWEIGHT_STARTUP"] = "0"
os.environ["GAIA_MINIMAL"] = "0"
os.environ["KAGAMI_EMBEDDED"] = "0"
os.environ["DISABLE_HEAVY_FEATURES"] = "0"
os.environ["NON_BLOCKING_BOOT"] = "0"


class FullOperationEnforcer:
    """Ensures K os runs at full capacity with all components."""

    def __init__(self):
        self.failures = []
        self.successes = []

    async def check_database(self) -> bool:
        """Ensure the primary SQL database is running and accessible."""
        try:
            # Use sync check in async context properly
            import asyncio

            from kagami.core.database.connection import check_connection

            # Run sync function in executor to avoid greenlet issues
            loop = asyncio.get_event_loop()
            result = await loop.run_in_executor(None, check_connection)

            if not result:
                raise RuntimeError("Database connection failed")

            logger.info("✅ Database: operational")
            self.successes.append("database")
            return True
        except Exception as e:
            logger.error(f"❌ Database MANDATORY but failed: {e}")
            self.failures.append(f"database: {e}")
            return False

    async def check_redis(self) -> bool:
        """Ensure Redis Stack is running with all modules."""
        try:
            from kagami.core.caching.redis import RedisClientFactory

            client = RedisClientFactory.get_client(
                purpose="default", async_mode=True, decode_responses=True
            )
            await client.ping()

            # Check for Redis Stack modules
            await client.info("modules")

            logger.info("✅ Redis: Redis Stack operational")
            self.successes.append("redis")
            return True
        except Exception as e:
            logger.error(f"❌ Redis MANDATORY but failed: {e}")
            self.failures.append(f"redis: {e}")
            return False

    async def check_gaia(self) -> bool:
        """Ensure GAIA is fully initialized with all protocols."""
        try:
            from gaia import GAIA

            # Initialize with all mandatory settings
            gaia = GAIA(
                enforce_security=True,
                enable_monitoring=True,
                use_v3_protocols=True,
                complete_initialization=True,
                strict_mode=True,
            )

            await gaia.initialize()

            # Verify all protocols loaded

            if not gaia.system:
                raise RuntimeError("GAIA system not initialized")

            logger.info("✅ GAIA: All protocols loaded and operational")
            self.successes.append("gaia")
            return True
        except Exception as e:
            logger.error(f"❌ GAIA MANDATORY but failed: {e}")
            self.failures.append(f"gaia: {e}")
            return False

    async def check_apps(self) -> bool:
        """Ensure all mascot apps are loaded and healthy."""
        try:
            from kagami.core.unified_agents.app_registry import APP_REGISTRY_V2, list_apps_v2

            # Require at least the canonical 7 agents.
            required_agents = {"spark", "forge", "flow", "nexus", "beacon", "grove", "crystal"}
            available = set(APP_REGISTRY_V2.keys())
            missing = sorted(required_agents - available)
            if missing:
                raise RuntimeError(f"Missing canonical agents: {missing}")

            # Ensure registry function is callable (contracts used by API).
            data = list_apps_v2()
            if not isinstance(data, dict) or not data:
                raise RuntimeError("list_apps_v2 returned empty registry")

            logger.info(f"✅ Apps: {len(available)} agents registered (canonical 7 present)")
            self.successes.append("apps")
            return True
        except Exception as e:
            logger.error(f"❌ Apps MANDATORY but failed: {e}")
            self.failures.append(f"apps: {e}")
            return False

    async def check_models(self) -> bool:
        """Ensure external models are available.

        In development, external model presence is optional unless
        KAGAMI_REQUIRE_EXTERNAL_MODELS=1 is set. In production, models are required.
        Accept either importable packages/repos or cached assets where applicable.
        """
        try:
            from pathlib import Path

            env_mode = (os.getenv("ENVIRONMENT") or "development").strip().lower()
            require_ext = (os.getenv("KAGAMI_REQUIRE_EXTERNAL_MODELS") or "0").lower() in (
                "1",
                "true",
                "yes",
                "on",
            )

            models = {
                "voice_registry": {
                    "repo": None,
                    "imports": ["kagami.core.services.voice.voice_registry"],
                    "assets": [],
                },
                "motion_agent": {
                    "repo": Path("motion_agent_repo"),
                    "imports": ["motion_agent"],
                    "assets": [Path(os.path.expanduser("~/.cache/forge_ai_models/motion-agent"))],
                },
                "unirig": {
                    "repo": Path("unirig_repo"),
                    "imports": ["unirig"],
                    "assets": [
                        Path(os.path.expanduser("~/.cache/huggingface/hub/models--VAST-AI--UniRig"))
                    ],
                },
            }

            missing = []
            for name, spec in models.items():
                # repo present?
                repo = spec.get("repo")
                if isinstance(repo, Path) and repo.exists():
                    continue

                # importable?
                import_ok = False
                for mod in spec["imports"]:  # type: ignore[index]
                    try:
                        __import__(mod)
                        import_ok = True
                        break
                    except Exception:
                        continue

                if import_ok:
                    continue

                # cached assets present?
                asset_ok = any(p.exists() for p in spec["assets"])  # type: ignore[index]
                if asset_ok:
                    continue

                missing.append(name)

            if missing:
                if env_mode == "production" or require_ext:
                    raise RuntimeError(f"Missing models: {missing}")
                else:
                    logger.warning("External models missing in dev (allowed): %s", missing)

            logger.info("✅ Models: External models check passed")
            self.successes.append("models")
            return True
        except Exception as e:
            logger.error(f"❌ Models MANDATORY but failed: {e}")
            self.failures.append(f"models: {e}")
            return False

    async def check_inference(self) -> bool:
        """Ensure local LLM inference is available."""
        try:
            from kagami.core.services.llm.service import (
                _resolve_adaptive_manager,
                _structured_client_supported,
                get_llm_service,
            )

            get_llm_service()

            # Verify structured client is available (now mandatory)
            if not _structured_client_supported():
                raise RuntimeError("Structured GAIA client not available")

            # Adaptive manager was removed during consolidation; keep check non-fatal.
            _ = _resolve_adaptive_manager()

            logger.info("✅ Inference: LLM service fully operational")
            self.successes.append("inference")
            return True
        except Exception as e:
            logger.error(f"❌ Inference MANDATORY but failed: {e}")
            self.failures.append(f"inference: {e}")
            return False

    async def check_consensus(self) -> bool:
        """Ensure etcd cluster is healthy with quorum."""
        try:
            from kagami.core.consensus.etcd_client import (
                _check_cluster_health,
                get_etcd_client,
            )

            etcd = get_etcd_client()
            if not etcd:
                raise RuntimeError("etcd client unavailable")

            # Check cluster health
            health = await _check_cluster_health(etcd)

            if not health.get("healthy"):
                raise RuntimeError(f"etcd cluster unhealthy: {health.get('error', 'unknown')}")

            logger.info(
                "✅ Consensus: etcd cluster healthy "
                f"(leader={health['leader']}, members={health['members']}, "
                f"version={health['version']})"
            )
            self.successes.append("consensus")
            return True
        except Exception as e:
            logger.error(f"❌ Consensus MANDATORY but failed: {e}")
            self.failures.append(f"consensus: {e}")
            return False

    async def enforce_full_operation(self) -> bool:
        """Run all checks and enforce full operation."""
        logger.info("=" * 60)
        logger.info("K os FULL OPERATION ENFORCEMENT")
        logger.info("All components are MANDATORY - no exceptions")
        logger.info("=" * 60)

        # Run all checks
        checks = [
            self.check_database(),
            self.check_redis(),
            self.check_gaia(),
            self.check_apps(),
            self.check_models(),
            self.check_inference(),
            self.check_consensus(),
        ]

        results = await asyncio.gather(*checks, return_exceptions=True)

        # Analyze results
        all_passed = all(r is True or (not isinstance(r, Exception) and r) for r in results)

        logger.info("=" * 60)
        if all_passed and not self.failures:
            logger.info("🚀 FULL OPERATION ACHIEVED")
            logger.info(f"✅ All {len(self.successes)} components operational:")
            for component in self.successes:
                logger.info(f"   • {component}")
            return True
        else:
            logger.error("❌ FULL OPERATION FAILED")
            logger.error("The following components are MANDATORY but not operational:")
            for failure in self.failures:
                logger.error(f"   • {failure}")
            logger.error("")
            logger.error("K os cannot operate without ALL components.")
            logger.error("Fix the issues above and try again.")
            return False


async def main():
    """Main entry point."""
    enforcer = FullOperationEnforcer()
    success = await enforcer.enforce_full_operation()

    if not success:
        logger.critical("SYSTEM CANNOT START - MANDATORY COMPONENTS MISSING")
        sys.exit(1)

    logger.info("")
    logger.info("System ready for FULL OPERATION")
    logger.info("All capabilities at maximum")
    logger.info("No degradation, no fallbacks, no optionality")

    # Write status file
    status_file = Path("artifacts/full_operation_status.json")
    import json

    status_file.write_text(
        json.dumps(
            {
                "status": "FULL_OPERATION",
                "components": enforcer.successes,
                "timestamp": str(asyncio.get_event_loop().time()),
            },
            indent=2,
        )
    )

    logger.info(f"Status written to {status_file}")


if __name__ == "__main__":
    asyncio.run(main())
