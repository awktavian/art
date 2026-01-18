"""Memory bridge between checkpoints and instincts.

Wires episodic/procedural memory from checkpoints into instinct state,
enabling true learning persistence across restarts.
"""

import logging
from typing import Any

logger = logging.getLogger(__name__)


async def restore_instincts_from_checkpoint(coordination: Any, checkpoint: Any) -> dict[str, int]:
    """
    Restore instinct state from checkpoint.

    Args:
        coordination: Coordination instance
        checkpoint: SelfCheckpoint with memory snapshots

    Returns:
        Stats: {prediction_updates, learning_episodes, threat_patterns}
    """
    stats = {"prediction_updates": 0, "learning_episodes": 0, "threat_patterns": 0}

    try:
        # Extract memory from checkpoint
        episodic_memories = checkpoint.memory.episodic
        procedural_patterns = checkpoint.memory.procedural

        # Restore to LearningInstinct (episodic memory)
        if episodic_memories and hasattr(coordination, "learning_instinct"):
            learning = coordination.learning_instinct

            for memory in episodic_memories:
                # Each episodic memory has: context, outcome, valence, timestamp
                try:
                    context = memory.get("context", {})
                    outcome = memory.get("outcome", {})
                    valence = memory.get("valence", 0.0)

                    # Restore to learning instinct
                    await learning.remember(context, outcome, valence)
                    stats["learning_episodes"] += 1

                except Exception as e:
                    logger.debug(f"Failed to restore episodic memory: {e}")

        # Restore to PredictionInstinct (procedural patterns)
        if procedural_patterns and hasattr(coordination, "prediction_instinct"):
            prediction = coordination.prediction_instinct

            for pattern in procedural_patterns:
                # Each procedural pattern has: signature, outcomes, success_rate
                try:
                    signature = pattern.get("signature", "")
                    outcomes = pattern.get("outcomes", [])

                    # Inject past outcomes directly into prediction instinct
                    if signature and outcomes:
                        prediction._experience[signature].extend(outcomes)
                        stats["prediction_updates"] += len(outcomes)

                except Exception as e:
                    logger.debug(f"Failed to restore procedural pattern: {e}")

        # Restore to ThreatInstinct (learned threats)
        if episodic_memories and hasattr(coordination, "threat_instinct"):
            threat = coordination.threat_instinct

            for memory in episodic_memories:
                # Extract high-threat experiences
                if memory.get("valence", 0) < -0.7:  # Strong negative
                    try:
                        pattern = memory.get("pattern", "")
                        if pattern and hasattr(threat, "_learned_threats"):
                            threat._learned_threats.append(pattern)
                            stats["threat_patterns"] += 1
                    except Exception as e:
                        logger.debug(f"Failed to restore threat pattern: {e}")

        logger.info(
            f"🧠 Restored instinct state: {stats['prediction_updates']} predictions, "
            f"{stats['learning_episodes']} episodes, {stats['threat_patterns']} threats"
        )

        return stats

    except Exception as e:
        logger.warning(f"Failed to restore instincts from checkpoint: {e}")
        return stats


async def capture_instincts_to_checkpoint(
    coordination: Any,
) -> dict[str, Any]:
    """
    Capture current instinct state for checkpoint.

    Args:
        coordination: Coordination instance

    Returns:
        Memory snapshot: {episodic: [...], procedural: [...]}
    """
    episodic = []
    procedural = []

    try:
        # Capture from LearningInstinct (episodic memory)
        if hasattr(coordination, "learning_instinct"):
            learning = coordination.learning_instinct

            # Extract recent episodes (top 100 by recency/importance)
            total_captured = 0
            for signature, episodes in learning._episodes.items():
                for episode in list(episodes)[-100:]:  # Last 100 per signature
                    # Handle both Experience objects and dicts
                    if hasattr(episode, "context"):
                        # Experience dataclass
                        episodic.append(
                            {
                                "signature": signature,
                                "context": episode.context,
                                "outcome": episode.outcome,
                                "valence": episode.valence,
                                "timestamp": episode.timestamp,
                                "attention_weight": abs(episode.valence),
                            }
                        )
                        total_captured += 1
                    elif isinstance(episode, dict):
                        # Already a dict[str, Any]
                        episodic.append(
                            {
                                "signature": signature,
                                **episode,
                                "attention_weight": abs(episode.get("valence", 0)),
                            }
                        )
                        total_captured += 1

            logger.debug(f"Captured {total_captured} episodic memories")

        # Capture from PredictionInstinct (procedural patterns)
        if hasattr(coordination, "prediction_instinct"):
            prediction = coordination.prediction_instinct

            # Extract learned patterns with success rates
            for signature, outcomes in prediction._experience.items():
                if len(outcomes) >= 5:  # Only patterns with sufficient data
                    # Compute success rate
                    successes = sum(1 for o in outcomes if o.get("status") == "success")
                    success_rate = successes / len(outcomes)

                    if success_rate > 0.6:  # Only save successful patterns
                        procedural.append(
                            {
                                "signature": signature,
                                "outcomes": outcomes[-50:],  # Last 50 outcomes
                                "success_rate": success_rate,
                                "sample_size": len(outcomes),
                                "attention_weight": success_rate * 0.9,  # Weight by success
                            }
                        )

        # P1-4: Enhanced memory capture - also capture kernel weights & meta-learning
        kernels = []
        meta_learning = {}

        # Capture kernel attention weights
        for instinct_name in [
            "ethical_instinct",
            "prediction_instinct",
            "threat_instinct",
            "learning_instinct",
        ]:
            if hasattr(coordination, instinct_name):
                instinct = getattr(coordination, instinct_name)

                # Capture metrics about this kernel
                kernel_info = {
                    "name": instinct_name,
                    "invocation_count": getattr(instinct, "_invocation_count", 0),
                    "success_count": getattr(instinct, "_success_count", 0),
                }

                # Compute success rate if available
                invocation_count = (
                    int(kernel_info["invocation_count"]) if kernel_info["invocation_count"] else 0
                )
                if invocation_count > 0:
                    kernel_info["success_rate"] = float(kernel_info["success_count"]) / float(
                        invocation_count
                    )
                else:
                    kernel_info["success_rate"] = 1.0

                kernels.append(kernel_info)

        # Capture meta-learning data (cognitive biases, learned strategies)
        if hasattr(coordination, "_cognitive_biases"):
            meta_learning["cognitive_biases"] = coordination._cognitive_biases

        if hasattr(coordination, "_learned_strategies"):
            meta_learning["learned_strategies"] = coordination._learned_strategies

        logger.debug(
            f"Captured instinct state: {len(episodic)} episodes, {len(procedural)} patterns, "
            f"{len(kernels)} kernels"
        )

        return {
            "episodic": episodic,
            "procedural": procedural,
            "kernels": kernels,
            "meta_learning": meta_learning,
        }

    except Exception as e:
        logger.warning(f"Failed to capture instinct state: {e}")
        return {"episodic": [], "procedural": [], "kernels": [], "meta_learning": {}}
