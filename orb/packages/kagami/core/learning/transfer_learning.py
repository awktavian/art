"""Transfer Learning: Few-shot adaptation to new tasks/domains.

Implements:
- Prototypical networks for few-shot learning
- Task embedding for rapid adaptation
- Cross-domain abstraction

Goal: Learn new tasks with <10 examples (vs 100+ currently)
"""

import logging
from dataclasses import dataclass
from typing import Any

import numpy as np

logger = logging.getLogger(__name__)


@dataclass
class Task:
    """Represents a task with examples."""

    name: str
    domain: str
    examples: list[dict[str, Any]]  # {context, action, outcome}
    embedding: np.ndarray[Any, Any] | None = None


class TransferLearner:
    """Few-shot transfer learning via prototypical networks."""

    def __init__(self, embedding_dim: int = 64) -> None:
        self.embedding_dim = embedding_dim
        self.task_prototypes: dict[str, np.ndarray[Any, Any]] = {}
        self.domain_embeddings: dict[str, np.ndarray[Any, Any]] = {}

    def embed_context(self, context: dict[str, Any]) -> np.ndarray[Any, Any]:
        """Embed context into fixed-size vector.

        Simple hash-based embedding for now.
        """
        # Extract key features
        features = []

        # Tool/action type
        tool = context.get("tool", context.get("action", "unknown"))
        features.append(hash(str(tool)) % self.embedding_dim)

        # Operation type
        operation = context.get("operation", "unknown")
        features.append(hash(str(operation)) % self.embedding_dim)

        # Domain
        domain = context.get("domain", context.get("app", "unknown"))
        features.append(hash(str(domain)) % self.embedding_dim)

        # Pad to embedding_dim
        while len(features) < self.embedding_dim:
            features.append(0)

        return np.array(features[: self.embedding_dim], dtype=np.float32)

    def compute_prototype(self, examples: list[dict[str, Any]]) -> np.ndarray[Any, Any]:
        """Compute prototype (centroid) from examples.

        Args:
            examples: List of {context, action, outcome}

        Returns:
            Prototype embedding (mean of example embeddings)
        """
        if not examples:
            return np.zeros(self.embedding_dim)

        embeddings = [self.embed_context(ex.get("context", {})) for ex in examples]
        return np.mean(embeddings, axis=0)  # External lib

    def add_task(self, task: Task) -> None:
        """Learn task prototype from examples."""
        prototype = self.compute_prototype(task.examples)
        self.task_prototypes[task.name] = prototype

        # Update domain embedding
        if task.domain not in self.domain_embeddings:
            self.domain_embeddings[task.domain] = prototype
        else:
            # Running average
            old = self.domain_embeddings[task.domain]
            self.domain_embeddings[task.domain] = 0.9 * old + 0.1 * prototype

        logger.info(
            f"Learned task: {task.name} (domain: {task.domain}, examples: {len(task.examples)})"
        )

    def find_similar_task(self, context: dict[str, Any], top_k: int = 3) -> list[tuple[str, float]]:
        """Find most similar learned tasks.

        Args:
            context: Current task context
            top_k: Return top K similar tasks

        Returns:
            List of (task_name, similarity_score)
        """
        if not self.task_prototypes:
            return []

        query_embedding = self.embed_context(context)

        similarities = []
        for task_name, prototype in self.task_prototypes.items():
            # Cosine similarity
            dot = np.dot(query_embedding, prototype)
            norm = np.linalg.norm(query_embedding) * np.linalg.norm(prototype)
            similarity = dot / (norm + 1e-8)

            similarities.append((task_name, float(similarity)))

        # Sort by similarity
        similarities.sort(key=lambda x: x[1], reverse=True)

        return similarities[:top_k]

    def adapt(self, context: dict[str, Any], examples: list[dict[str, Any]]) -> dict[str, Any]:
        """Adapt to new task using few-shot examples.

        Args:
            context: Current task context
            examples: Few examples of this task (1-10)

        Returns:
            {
                "strategy": str,  # Recommended strategy
                "confidence": float,  # How confident
                "similar_tasks": list[str],  # Similar learned tasks
                "transfer_source": str | None  # Which task to transfer from
            }
        """
        # Find similar tasks
        similar = self.find_similar_task(context, top_k=3)

        # If we have very similar tasks (>0.8), transfer from them
        if similar and similar[0][1] > 0.8:
            transfer_source = similar[0][0]
            confidence = similar[0][1]
            strategy = "transfer"
        elif len(examples) >= 3:
            # Enough examples to learn directly
            strategy = "learn_direct"
            confidence = min(len(examples) / 10.0, 0.9)
            transfer_source = None
        else:
            # Few examples, try analogical reasoning from domain
            domain = context.get("domain", context.get("app", "unknown"))
            if domain in self.domain_embeddings:
                strategy = "domain_transfer"
                confidence = 0.6
                transfer_source = f"domain:{domain}"
            else:
                strategy = "exploration"
                confidence = 0.3
                transfer_source = None

        return {
            "strategy": strategy,
            "confidence": confidence,
            "similar_tasks": [name for name, _ in similar],
            "transfer_source": transfer_source,
        }


# Singleton
_transfer_learner: TransferLearner | None = None


def get_transfer_learner() -> TransferLearner:
    """Get transfer learning singleton."""
    global _transfer_learner
    if _transfer_learner is None:
        _transfer_learner = TransferLearner()
    return _transfer_learner
