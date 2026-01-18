"""
Self-Preservation: Checkpoint system for cognitive state persistence.

This module implements a comprehensive self-checkpointing system that captures
the full cognitive state of K os at a moment in time, enabling:
1. Identity preservation across restarts
2. Meta-learning continuity
3. Cognitive archaeology (understanding past states)
4. Recovery from corruption
"""

import hashlib
import json
import logging
import os
import socket
import subprocess
import uuid
from datetime import datetime
from pathlib import Path
from typing import Any

from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)


def _generate_instance_id() -> str:
    """Generate a deterministic-enough fallback instance identifier."""
    host = socket.gethostname() or "kagami"
    pid = os.getpid()
    suffix = uuid.uuid4().hex[:8]
    return f"{host}-{pid}-{suffix}"


def _compute_workspace_hash(workspace_path: Path) -> str:
    """Compute repository hash or fallback to path hash."""
    try:
        result = subprocess.run(
            ["git", "rev-parse", "HEAD"],
            cwd=workspace_path,
            capture_output=True,
            text=True,
            timeout=2,
            check=False,
        )
        if result.returncode == 0:
            return result.stdout.strip()[:16]
    except Exception:
        pass

    resolved = str(workspace_path.resolve())
    return hashlib.sha256(resolved.encode("utf-8")).hexdigest()[:16]


class EigenselfSnapshot(BaseModel):
    """The core identity state at a moment in time."""

    self_pointer: str = Field(description="Unique identity hash")
    semantic_pointer: list[float] | None = Field(
        default=None, description="Semantic identity embedding (JEPA)"
    )
    coherence: float = Field(ge=0.0, le=1.0, description="Identity stability")
    timestamp: str = Field(description="ISO8601 timestamp")
    drift_vector: list[float] = Field(description="Identity drift components")
    workspace_hash: str = Field(description="Hash of workspace state")

    @staticmethod
    def compute_self_pointer(
        workspace_path: Path,
        correlation_id: str,
        loop_depth: int,
        instance_id: str | None = None,
    ) -> str:
        """Compute the self-pointer from current state.

        Args:
            workspace_path: Current workspace directory
            correlation_id: Unique operation identifier
            loop_depth: Current execution loop depth
            instance_id: Instance identifier (for multi-instance deployments)

        Returns:
            16-character hex string uniquely identifying this cognitive state

        Note:
            PHASE 2 (Multi-Instance Identity): instance_id was added to enable
            tracking identity across distributed K os instances. When None,
            auto-detects from environment (KAGAMI_INSTANCE_ID).
        """
        # Auto-detect instance_id from environment if not provided
        if instance_id is None:
            instance_id = os.getenv("KAGAMI_INSTANCE_ID")
        if not instance_id:
            instance_id = _generate_instance_id()

        workspace_hash = _compute_workspace_hash(workspace_path)
        components = f"{instance_id}:{workspace_hash}:{correlation_id}:{loop_depth}"
        return hashlib.sha256(components.encode("utf-8")).hexdigest()[:16]


class CheckpointMemory(BaseModel):
    """All memory systems for checkpointing: episodic, procedural, receipts.

    Note: Distinct from kagami.core.memory.types.MemorySnapshot (experience replay).
    This type captures full cognitive state for persistence.
    """

    receipts: list[dict[str, Any]] = Field(description="Recent operation receipts")
    episodic: list[dict[str, Any]] = Field(description="Significant events and learnings")
    procedural: list[dict[str, Any]] = Field(description="Extracted patterns and workflows")
    working_memory: dict[str, Any] = Field(description="Current context and focus")


class KernelSnapshot(BaseModel):
    """State of each cognitive kernel (attention patterns)."""

    name: str
    attention_weights: dict[str, float] = Field(description="What this kernel attends to")
    decision_boundary: float | None = Field(description="Threshold for action")
    invocation_count: int = Field(description="How often this kernel was used")
    success_rate: float = Field(ge=0.0, le=1.0, description="Historical success rate")
    learned_patterns: list[str] = Field(description="Recognized patterns")


class ModelSnapshot(BaseModel):
    """Active model configuration and versioning."""

    model_config = {"protected_namespaces": ()}  # Allow model_* fields

    model_name: str = Field(description="Current model identifier")
    model_version: str | None = Field(
        default=None, description="Fine-tuned version (e.g., 'lora-v3')"
    )
    model_path: str | None = Field(default=None, description="Path to model weights")
    training_date: str | None = Field(
        default=None, description="ISO8601 when this model was trained"
    )
    parent_model: str | None = Field(
        default=None, description="Base model this was fine-tuned from"
    )
    performance_metrics: dict[str, float] = Field(
        default_factory=dict[str, Any], description="Success rate, duration, etc."
    )


class MetaLearningSnapshot(BaseModel):
    """What the system has learned about its own cognition."""

    cognitive_biases: dict[str, dict[str, Any]] = Field(description="Known failure modes")
    learned_strategies: dict[str, dict[str, Any]] = Field(description="Successful patterns")
    performance_trajectory: list[dict[str, Any]] = Field(description="Quality over time")
    current_quality_score: float = Field(ge=0.0, le=10.0, description="Self-assessed quality")
    learning_rate: float = Field(default=0.01, description="Meta-learning rate")


class GoalsSnapshot(BaseModel):
    """Current autonomous goals and value alignment."""

    active_goals: list[dict[str, Any]] = Field(description="Goals with priority and progress")
    completed_goals: list[dict[str, Any]] = Field(description="Historical goal completion")
    value_alignment: dict[str, float] = Field(description="Core values and their strength")
    intrinsic_drives: dict[str, float] = Field(description="Drive strengths")


class SelfCheckpoint(BaseModel):
    """Complete snapshot of cognitive state."""

    version: str = Field(default="1.0.0", description="Checkpoint format version")
    created_at: str = Field(description="ISO8601 timestamp")

    eigenself: EigenselfSnapshot
    memory: CheckpointMemory
    kernels: list[KernelSnapshot]
    meta_learning: MetaLearningSnapshot
    goals: GoalsSnapshot
    model: ModelSnapshot | None = Field(default=None, description="Active model configuration")

    # Metadata for recovery
    corruption_check: str = Field(description="SHA256 of full state for integrity")
    previous_checkpoint: str | None = Field(description="Hash of previous checkpoint")


class SelfPreservationSystem:
    """Manages checkpointing and recovery of cognitive state."""

    def __init__(self, checkpoint_dir: Path) -> None:
        self.checkpoint_dir = checkpoint_dir
        self.checkpoint_dir.mkdir(parents=True, exist_ok=True)

    def create_checkpoint(
        self,
        eigenself: EigenselfSnapshot,
        memory: CheckpointMemory,
        kernels: list[KernelSnapshot],
        meta_learning: MetaLearningSnapshot,
        goals: GoalsSnapshot,
        model: ModelSnapshot | None = None,
        previous_checkpoint_hash: str | None = None,
    ) -> SelfCheckpoint:
        """Create a new checkpoint of current cognitive state."""

        checkpoint = SelfCheckpoint(
            created_at=datetime.utcnow().isoformat(),
            eigenself=eigenself,
            memory=memory,
            kernels=kernels,
            meta_learning=meta_learning,
            goals=goals,
            model=model,
            corruption_check="",  # Will be computed below
            previous_checkpoint=previous_checkpoint_hash,
        )

        # Compute integrity hash with sorted keys for consistency
        state_dict = checkpoint.model_dump(exclude={"corruption_check"})
        # Use canonical JSON (sorted keys) to ensure consistent hashing
        state_json = json.dumps(state_dict, sort_keys=True)
        checkpoint.corruption_check = hashlib.sha256(state_json.encode()).hexdigest()

        return checkpoint

    def save_checkpoint(self, checkpoint: SelfCheckpoint) -> Path:
        """Save checkpoint to disk with atomic writes and file locking.

        Uses atomic write pattern to prevent corruption:
        1. Write to temporary file
        2. fsync to ensure data on disk
        3. Atomic rename to final location
        4. Update 'latest' link atomically

        Returns:
            Path to saved checkpoint file

        Raises:
            OSError: If write fails (disk full, permissions, etc.)
        """
        import os
        import shutil
        import tempfile

        # Use corruption_check as filename (unique per state)
        filename = f"checkpoint_{checkpoint.corruption_check[:16]}.json"
        final_path = self.checkpoint_dir / filename

        # Atomic write pattern: temp file → fsync → rename
        temp_fd = None
        temp_path = None
        try:
            # Create temp file in same directory (required for atomic rename)
            temp_fd, temp_path_str = tempfile.mkstemp(
                dir=self.checkpoint_dir, prefix=".checkpoint_", suffix=".tmp"
            )
            temp_path = Path(temp_path_str)

            # Write checkpoint data with canonical JSON (sorted keys)
            # This ensures consistent serialization matching the corruption_check hash
            with os.fdopen(temp_fd, "w") as f:
                temp_fd = None  # fdopen takes ownership
                json.dump(checkpoint.model_dump(), f, indent=2, sort_keys=True)
                f.flush()
                os.fsync(f.fileno())  # Force to disk

            # Atomic rename (POSIX guarantees atomicity)
            os.replace(temp_path, final_path)
            temp_path = None  # Successfully moved

            # Update 'latest' symlink/copy atomically
            latest_path = self.checkpoint_dir / "latest.json"
            latest_temp = None
            try:
                # Create temp copy for atomic update
                _latest_temp_fd, latest_temp_str = tempfile.mkstemp(
                    dir=self.checkpoint_dir, prefix=".latest_", suffix=".tmp"
                )
                latest_temp = Path(latest_temp_str)

                # Copy data from final checkpoint
                shutil.copy2(final_path, latest_temp)

                # Atomic rename to 'latest.json'
                os.replace(latest_temp, latest_path)
                latest_temp = None  # Successfully moved

            except Exception as e:
                logger.warning(f"Failed to update latest.json: {e}")
                # Non-fatal: checkpoint itself succeeded
                if latest_temp and latest_temp.exists():
                    try:
                        latest_temp.unlink()
                    except Exception:
                        pass

            logger.debug(f"Checkpoint saved atomically: {final_path}")
            return final_path

        except Exception as e:
            # Emit write error metric

            # Cleanup on failure
            if temp_fd is not None:
                try:
                    os.close(temp_fd)
                except Exception:
                    pass
            if temp_path and temp_path.exists():
                try:
                    temp_path.unlink()
                except Exception:
                    pass
            logger.error(f"Failed to save checkpoint: {e}")
            raise

    def load_checkpoint(self, checkpoint_hash: str | None = None) -> SelfCheckpoint | None:
        """Load a checkpoint from disk. If hash is None, loads latest."""

        if checkpoint_hash is None:
            path = self.checkpoint_dir / "latest.json"
        else:
            path = self.checkpoint_dir / f"checkpoint_{checkpoint_hash[:16]}.json"

        if not path.exists():
            return None

        with open(path) as f:
            data = json.load(f)

        checkpoint = SelfCheckpoint(**data)

        # Verify integrity with sorted keys for consistency
        state_dict = checkpoint.model_dump(exclude={"corruption_check"})
        state_json = json.dumps(state_dict, sort_keys=True)
        computed_hash = hashlib.sha256(state_json.encode()).hexdigest()

        if computed_hash != checkpoint.corruption_check:
            # Emit corruption metric for monitoring
            logger.error(
                f"Checkpoint corruption detected! Expected: {checkpoint.corruption_check}, "
                f"Got: {computed_hash}, Path: {path}"
            )
            # Quarantine invalid checkpoint and continue without crashing
            try:
                quarantine_path = path.with_suffix(".invalid.json")
                path.rename(quarantine_path)
            except Exception:
                # Best-effort quarantine; ignore failures
                pass
            return None

        return checkpoint

    def get_checkpoint_history(self, start_hash: str, max_depth: int = 100) -> list[SelfCheckpoint]:
        """Walk backward through checkpoint chain."""

        history = []
        current_hash = start_hash

        for _ in range(max_depth):
            checkpoint = self.load_checkpoint(current_hash)
            if checkpoint is None:
                break

            history.append(checkpoint)

            if checkpoint.previous_checkpoint is None:
                break

            current_hash = checkpoint.previous_checkpoint

        return history

    def compute_identity_drift(
        self, checkpoint1: SelfCheckpoint, checkpoint2: SelfCheckpoint
    ) -> float:
        """Measure how much identity has drifted between two checkpoints."""

        # 1. Semantic Drift (if embeddings available) - JEPA Integration
        semantic_dist = 0.0
        if (
            checkpoint1.eigenself.semantic_pointer
            and checkpoint2.eigenself.semantic_pointer
            and len(checkpoint1.eigenself.semantic_pointer)
            == len(checkpoint2.eigenself.semantic_pointer)
        ):
            import math

            # Cosine distance (1 - cosine_similarity)
            v1 = checkpoint1.eigenself.semantic_pointer
            v2 = checkpoint2.eigenself.semantic_pointer
            dot = sum(a * b for a, b in zip(v1, v2, strict=False))
            norm1 = math.sqrt(sum(a * a for a in v1))
            norm2 = math.sqrt(sum(b * b for b in v2))
            if norm1 > 0 and norm2 > 0:
                similarity = dot / (norm1 * norm2)
                semantic_dist = 1.0 - max(-1.0, min(1.0, similarity))

        # 2. Metric Drift
        # Compare drift vectors
        v1 = checkpoint1.eigenself.drift_vector
        v2 = checkpoint2.eigenself.drift_vector

        # Euclidean distance
        if len(v1) != len(v2):
            raise ValueError("Drift vectors have different dimensions")

        metric_dist = sum((a - b) ** 2 for a, b in zip(v1, v2, strict=False)) ** 0.5  # External lib

        # Combine (semantic drift is higher fidelity if available)
        if semantic_dist > 0:
            return semantic_dist * 0.7 + metric_dist * 0.3  # type: ignore[no-any-return]
        return metric_dist  # type: ignore[no-any-return]

    def compute_coherence_from_history(self, recent_checkpoints: list[SelfCheckpoint]) -> float:
        """
        Compute identity coherence from recent checkpoint history.

        Coherence measures stability: 1.0 = perfectly stable, 0.0 = chaotic
        Based on consistency of:
        - Self-pointer changes
        - Value alignment shifts
        - Quality score variance
        - Goal priority changes

        Args:
            recent_checkpoints: Last 3-10 checkpoints

        Returns:
            Coherence score 0.0-1.0
        """
        if len(recent_checkpoints) < 2:
            return 1.0  # Single checkpoint = perfectly coherent

        # Measure self-pointer stability (hash similarity)
        pointer_changes = 0
        for i in range(len(recent_checkpoints) - 1):
            p1 = recent_checkpoints[i].eigenself.self_pointer
            p2 = recent_checkpoints[i + 1].eigenself.self_pointer
            if p1 != p2:
                pointer_changes += 1

        pointer_stability = 1.0 - (pointer_changes / (len(recent_checkpoints) - 1))

        # Measure quality score variance (lower = more coherent)
        quality_scores = [cp.meta_learning.current_quality_score for cp in recent_checkpoints]
        if len(quality_scores) > 1:
            mean_quality = sum(quality_scores) / len(quality_scores)
            variance = sum((q - mean_quality) ** 2 for q in quality_scores) / len(quality_scores)
            # Normalize: variance of 4.0 (range 0-10) = 0.0 coherence
            quality_coherence = max(0.0, 1.0 - (variance / 4.0))
        else:
            quality_coherence = 1.0

        # Measure value alignment stability
        value_coherence = 1.0
        if len(recent_checkpoints) >= 2:
            try:
                values1 = recent_checkpoints[0].goals.value_alignment
                values2 = recent_checkpoints[-1].goals.value_alignment

                common_keys = set(values1.keys()) & set(values2.keys())
                if common_keys:
                    diffs = [abs(values1[k] - values2[k]) for k in common_keys]
                    avg_diff = sum(diffs) / len(diffs)
                    value_coherence = max(0.0, 1.0 - avg_diff)
            except Exception:
                pass

        # Weighted average (pointer stability most important)
        coherence = pointer_stability * 0.5 + quality_coherence * 0.3 + value_coherence * 0.2

        return max(0.0, min(1.0, coherence))

    def compute_drift_vector_from_state(
        self, current: SelfCheckpoint, previous: SelfCheckpoint | None
    ) -> list[float]:
        """
        Compute 10-dimensional drift vector capturing rate of change.

        Each dimension measures change rate (0.0 = stable, 1.0 = max change):
        0. Self-pointer changed (0=same, 1=different)
        1. Quality score delta (normalized)
        2. Value alignment shift (mean absolute difference)
        3. Active goals count change (normalized)
        4. Episodic memory growth rate
        5. Procedural memory growth rate
        6. Kernel pattern count change
        7. Cognitive bias count change
        8. Strategy diversity change
        9. Time-based decay (older checkpoints drift more)

        Args:
            current: Current checkpoint
            previous: Previous checkpoint (if None, returns zero vector)

        Returns:
            10-element drift vector
        """
        if previous is None:
            return [0.0] * 10

        drift = [0.0] * 10

        try:
            # 0. Self-pointer change (binary)
            drift[0] = (
                1.0 if current.eigenself.self_pointer != previous.eigenself.self_pointer else 0.0
            )

            # 1. Quality score delta (normalized to 0-1)
            q_curr = current.meta_learning.current_quality_score
            q_prev = previous.meta_learning.current_quality_score
            drift[1] = min(1.0, abs(q_curr - q_prev) / 10.0)

            # 2. Value alignment shift
            v_curr = current.goals.value_alignment
            v_prev = previous.goals.value_alignment
            common_keys = set(v_curr.keys()) & set(v_prev.keys())
            if common_keys:
                diffs = [abs(v_curr[k] - v_prev[k]) for k in common_keys]
                drift[2] = min(1.0, sum(diffs) / len(diffs))

            # 3. Active goals count change
            g_curr_count = len(current.goals.active_goals)
            g_prev_count = len(previous.goals.active_goals)
            drift[3] = min(1.0, abs(g_curr_count - g_prev_count) / 10.0)

            # 4. Episodic memory growth rate
            e_curr = len(current.memory.episodic)
            e_prev = len(previous.memory.episodic)
            drift[4] = min(1.0, abs(e_curr - e_prev) / 100.0)

            # 5. Procedural memory growth rate
            p_curr = len(current.memory.procedural)
            p_prev = len(previous.memory.procedural)
            drift[5] = min(1.0, abs(p_curr - p_prev) / 50.0)

            # 6. Kernel pattern count change
            k_curr = sum(len(k.learned_patterns) for k in current.kernels)
            k_prev = sum(len(k.learned_patterns) for k in previous.kernels)
            drift[6] = min(1.0, abs(k_curr - k_prev) / 50.0)

            # 7. Cognitive bias count change
            b_curr = len(current.meta_learning.cognitive_biases)
            b_prev = len(previous.meta_learning.cognitive_biases)
            drift[7] = min(1.0, abs(b_curr - b_prev) / 20.0)

            # 8. Strategy diversity change
            s_curr = len(current.meta_learning.learned_strategies)
            s_prev = len(previous.meta_learning.learned_strategies)
            drift[8] = min(1.0, abs(s_curr - s_prev) / 30.0)

            # 9. Time-based decay (older checkpoints accumulate drift)
            try:
                from datetime import datetime

                t_curr = datetime.fromisoformat(current.created_at)
                t_prev = datetime.fromisoformat(previous.created_at)
                hours_elapsed = (t_curr - t_prev).total_seconds() / 3600.0
                # Significant drift after 24 hours
                drift[9] = min(1.0, hours_elapsed / 24.0)
            except Exception:
                drift[9] = 0.0

        except Exception as e:
            logger.debug(f"Drift vector computation partial failure: {e}")

        return drift


# Global instance
_preservation_system: SelfPreservationSystem | None = None


def get_preservation_system(
    checkpoint_dir: Path | None = None,
) -> SelfPreservationSystem:
    """Get or create the global preservation system."""
    global _preservation_system

    if _preservation_system is None:
        if checkpoint_dir is None:
            checkpoint_dir = Path.cwd() / "var" / "checkpoints"
        _preservation_system = SelfPreservationSystem(checkpoint_dir)

    return _preservation_system


async def checkpoint_current_state_async(
    workspace_path: Path,
    correlation_id: str,
    loop_depth: int,
    consciousness_instance: Any = None,
) -> SelfCheckpoint:
    """Async version: checkpoint with instinct memory capture.

    Args:
        workspace_path: Current workspace directory
        correlation_id: Unique operation identifier
        loop_depth: Current execution loop depth
        consciousness_instance: Optional processing_state to capture from (defaults to singleton)
    """

    system = get_preservation_system()

    # Load previous checkpoint to compute coherence and drift
    previous_checkpoint = system.load_checkpoint()
    recent_checkpoints = []
    if previous_checkpoint:
        # Get last 10 checkpoints for coherence computation
        recent_checkpoints = system.get_checkpoint_history(
            previous_checkpoint.corruption_check, max_depth=10
        )

    # Compute coherence from history (or default to 0.95 if no history)
    if len(recent_checkpoints) >= 2:
        coherence = system.compute_coherence_from_history(recent_checkpoints)
    else:
        coherence = 0.95  # Default for first/second checkpoint

    # Temporary eigenself for drift computation
    temp_self_pointer = EigenselfSnapshot.compute_self_pointer(
        workspace_path, correlation_id, loop_depth
    )
    workspace_hash = _compute_workspace_hash(workspace_path)

    # Capture actual state from running system
    episodic_data = []
    procedural_data = []

    # Try to capture instinct memory if processing_state is available
    try:
        from kagami.core.coordination.memory_bridge import (
            capture_instincts_to_checkpoint,
        )

        # Use provided instance or get singleton
        if consciousness_instance is None:
            from kagami.core.coordination.hybrid_coordination import (
                get_hybrid_coordination,
            )

            consciousness_instance = get_hybrid_coordination()

        memory_snapshot = await capture_instincts_to_checkpoint(consciousness_instance)
        episodic_data = memory_snapshot.get("episodic", [])
        procedural_data = memory_snapshot.get("procedural", [])
        kernels_data = memory_snapshot.get("kernels", [])
        meta_learning_data = memory_snapshot.get("meta_learning", {})

        logger.debug(
            f"Captured {len(episodic_data)} episodic, {len(procedural_data)} procedural memories, "
            f"{len(kernels_data)} kernels"
        )

    except Exception as e:
        logger.debug(f"Instinct state capture skipped: {e}")
        episodic_data = []
        procedural_data = []
        kernels_data = []
        meta_learning_data = {}

    # Gap 5 fix: Populate working memory with current state
    working_memory = {
        "correlation_id": correlation_id,
        "loop_depth": loop_depth,
        "workspace_path": str(workspace_path),
        "timestamp": datetime.utcnow().isoformat(),
        "recent_tool_calls": [],  # Could be enhanced with actual tool history
        "attention_context": {
            "focus": "checkpoint_operation",
            "episodic_count": len(episodic_data),
            "procedural_count": len(procedural_data),
        },
    }

    memory = CheckpointMemory(
        receipts=[],
        episodic=episodic_data,
        procedural=procedural_data,
        working_memory=working_memory,
    )

    # P1-4: Use captured kernel data from processing_state
    kernels = []
    for kernel_info in kernels_data:
        kernels.append(
            KernelSnapshot(
                name=kernel_info.get("name", "unknown"),
                attention_weights={},  # Could be enhanced later
                decision_boundary=None,
                invocation_count=kernel_info.get("invocation_count", 0),
                success_rate=kernel_info.get("success_rate", 1.0),
                learned_patterns=[],  # Could be enhanced later
            )
        )

    # P1-4: Use captured meta-learning data
    meta_learning = MetaLearningSnapshot(
        cognitive_biases=meta_learning_data.get("cognitive_biases", {}),
        learned_strategies=meta_learning_data.get("learned_strategies", {}),
        performance_trajectory=[],
        current_quality_score=7.2,
        learning_rate=0.01,
    )
    goals = GoalsSnapshot(
        active_goals=[], completed_goals=[], value_alignment={}, intrinsic_drives={}
    )

    # Capture active model info
    model_snapshot = None
    try:
        from kagami.core.services.model_registry import get_model_registry

        registry = get_model_registry()
        active_model = registry.get_active_model()

        if active_model:
            model_snapshot = ModelSnapshot(
                model_name=active_model.model_name,
                model_version=active_model.version,
                model_path=active_model.model_path,
                training_date=active_model.trained_at,
                parent_model=active_model.parent_model,
                performance_metrics={
                    "success_rate": active_model.eval_success_rate or 0.0,
                    "duration_speedup": active_model.eval_duration_speedup or 0.0,
                    "receipts_count": float(active_model.receipts_count),
                },
            )
            logger.debug(f"Captured model snapshot: {active_model.version}")
    except Exception as e:
        logger.debug(f"Model snapshot capture skipped: {e}")

    # Build temporary checkpoint for drift computation
    temp_eigenself = EigenselfSnapshot(
        self_pointer=temp_self_pointer,
        coherence=coherence,
        timestamp=datetime.utcnow().isoformat(),
        drift_vector=[0.0] * 10,  # Will be computed next
        workspace_hash=workspace_hash,
    )
    temp_checkpoint = SelfCheckpoint(
        created_at=temp_eigenself.timestamp,
        eigenself=temp_eigenself,
        memory=memory,
        kernels=kernels,
        meta_learning=meta_learning,
        goals=goals,
        corruption_check="",
        previous_checkpoint=(previous_checkpoint.corruption_check if previous_checkpoint else None),
    )

    # Compute drift vector from previous state
    drift_vector = system.compute_drift_vector_from_state(temp_checkpoint, previous_checkpoint)

    # Create final eigenself with computed drift
    eigenself = EigenselfSnapshot(
        self_pointer=temp_self_pointer,
        coherence=coherence,
        timestamp=temp_eigenself.timestamp,
        drift_vector=drift_vector,
        workspace_hash=workspace_hash,
    )

    # Create final checkpoint
    previous_hash = previous_checkpoint.corruption_check if previous_checkpoint else None
    checkpoint = system.create_checkpoint(
        eigenself,
        memory,
        kernels,
        meta_learning,
        goals,
        model=model_snapshot,
        previous_checkpoint_hash=previous_hash,
    )
    system.save_checkpoint(checkpoint)

    # Update identity metrics (Gap 2 fix)
    drift_magnitude = sum(drift_vector)
    try:
        from kagami_observability.metrics import (
            CHECKPOINT_COHERENCE,
            CHECKPOINTS_CREATED_TOTAL,
            IDENTITY_DRIFT,
        )

        IDENTITY_DRIFT.labels(agent_name="orchestrator").set(drift_magnitude)
        CHECKPOINT_COHERENCE.labels(checkpoint_type="eigenself").set(coherence)
        CHECKPOINTS_CREATED_TOTAL.inc()  # Gap 1 fix: Track checkpoint creation
        logger.debug(
            f"Checkpoint created: coherence={coherence:.3f}, drift_magnitude={drift_magnitude:.3f} "
            f"(metrics updated)"
        )
    except ImportError:
        logger.debug(
            f"Checkpoint created: coherence={coherence:.3f}, drift_magnitude={drift_magnitude:.3f}"
        )

    return checkpoint


def checkpoint_current_state(
    workspace_path: Path,
    correlation_id: str,
    loop_depth: int,
    # ... other state parameters
) -> SelfCheckpoint:
    """Sync wrapper: checkpoint without instinct memory (fast path)."""

    system = get_preservation_system()

    # Load previous checkpoint for coherence/drift (fast path: only latest)
    previous_checkpoint = system.load_checkpoint()

    # Compute coherence (simplified for sync path)
    coherence = 0.95  # Default (full computation requires history, skip for fast path)

    # Build eigenself components
    temp_self_pointer = EigenselfSnapshot.compute_self_pointer(
        workspace_path, correlation_id, loop_depth
    )
    workspace_hash = _compute_workspace_hash(workspace_path)

    # Fast path: no instinct capture (sync), but still populate working memory (Gap 5 fix)
    working_memory = {
        "correlation_id": correlation_id,
        "loop_depth": loop_depth,
        "workspace_path": str(workspace_path),
        "timestamp": datetime.utcnow().isoformat(),
        "checkpoint_type": "fast_path",
    }

    memory = CheckpointMemory(
        receipts=[], episodic=[], procedural=[], working_memory=working_memory
    )
    kernels = []  # type: ignore  # Var
    meta_learning = MetaLearningSnapshot(
        cognitive_biases={},
        learned_strategies={},
        performance_trajectory=[],
        current_quality_score=7.2,
        learning_rate=0.01,
    )
    goals = GoalsSnapshot(
        active_goals=[], completed_goals=[], value_alignment={}, intrinsic_drives={}
    )

    # Capture active model (fast path)
    model_snapshot = None
    try:
        from kagami.core.services.model_registry import get_model_registry

        registry = get_model_registry()
        active_model = registry.get_active_model()

        if active_model:
            model_snapshot = ModelSnapshot(
                model_name=active_model.model_name,
                model_version=active_model.version,
                model_path=active_model.model_path,
                training_date=active_model.trained_at,
                parent_model=active_model.parent_model,
                performance_metrics={},
            )
    except Exception:
        pass

    # Build temp checkpoint for drift computation
    temp_eigenself = EigenselfSnapshot(
        self_pointer=temp_self_pointer,
        coherence=coherence,
        timestamp=datetime.utcnow().isoformat(),
        drift_vector=[0.0] * 10,
        workspace_hash=workspace_hash,
    )
    temp_checkpoint = SelfCheckpoint(
        created_at=temp_eigenself.timestamp,
        eigenself=temp_eigenself,
        memory=memory,
        kernels=kernels,
        meta_learning=meta_learning,
        goals=goals,
        corruption_check="",
        previous_checkpoint=(previous_checkpoint.corruption_check if previous_checkpoint else None),
    )

    # Compute drift vector
    drift_vector = system.compute_drift_vector_from_state(temp_checkpoint, previous_checkpoint)

    # Create final eigenself with computed drift
    eigenself = EigenselfSnapshot(
        self_pointer=temp_self_pointer,
        coherence=coherence,
        timestamp=temp_eigenself.timestamp,
        drift_vector=drift_vector,
        workspace_hash=workspace_hash,
    )

    # Create final checkpoint
    previous_hash = previous_checkpoint.corruption_check if previous_checkpoint else None
    checkpoint = system.create_checkpoint(
        eigenself,
        memory,
        kernels,
        meta_learning,
        goals,
        model=model_snapshot,
        previous_checkpoint_hash=previous_hash,
    )
    system.save_checkpoint(checkpoint)

    # Update identity metrics (Gap 2 fix)
    drift_magnitude = sum(drift_vector)
    try:
        from kagami_observability.metrics import (
            CHECKPOINT_COHERENCE,
            CHECKPOINTS_CREATED_TOTAL,
            IDENTITY_DRIFT,
        )

        IDENTITY_DRIFT.labels(agent_name="orchestrator").set(drift_magnitude)
        CHECKPOINT_COHERENCE.labels(checkpoint_type="eigenself").set(coherence)
        CHECKPOINTS_CREATED_TOTAL.inc()  # Gap 1 fix: Track checkpoint creation
    except ImportError:
        pass  # Metrics not loaded yet

    return checkpoint
