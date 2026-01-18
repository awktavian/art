from __future__ import annotations

"MAML: Model-Agnostic Meta-Learning.\n\nMAML (Finn et al., 2017) enables rapid adaptation to new tasks with only 1-5 examples.\nLearns good initialization that can be quickly fine-tuned.\n\nKey benefits:\n- 10x faster adaptation (1-5 examples vs 100+)\n- Task-agnostic (works for any task)\n- Few-shot learning capability\n- Transfer learning across tasks\n\nAlgorithm:\n    Meta-Training (outer loop):\n        For each batch of tasks:\n            For each task in batch:\n                1. Clone model\n                2. Inner loop: Adapt to task (K gradient steps)\n                3. Evaluate on query set[Any]\n            4. Meta-update: Improve initialization\n\n    Fast Adaptation (deployment):\n        Given new task with 1-5 examples:\n            1. Start from meta-learned initialization\n            2. Few gradient steps on examples\n            3. Ready to use! (was at good starting point)\n\nMathematical formulation:\n    θ* = meta-learned initialization\n\n    For task i:\n        θ'_i = θ* - α∇L_i^support(θ*)  (K inner steps)\n\n    Meta-update:\n        θ* ← θ* - β∇Σ_i L_i^query(θ'_i)\n\nReference: Finn et al. (2017) \"Model-Agnostic Meta-Learning for Fast Adaptation\"\nhttps://arxiv.org/abs/1703.03400\n"
import copy
import logging
from typing import Any

import torch
import torch.nn as nn
import torch.nn.functional as F

logger = logging.getLogger(__name__)


class MAMLMetaLearner:
    """Model-Agnostic Meta-Learning for rapid adaptation.

    Usage:
        maml = MAMLMetaLearner(base_model, inner_lr=0.01, outer_lr=0.001)

        # Meta-training on batch of tasks
        task_batch = [
            {
                'support': [...],  # Few examples for adaptation
                'query': [...]     # Examples for evaluation
            },
            ...
        ]
        meta_loss = await maml.meta_train(task_batch)

        # Fast adaptation to new task
        new_task = {'support': [example1, example2, example3]}  # Just 3 examples!
        adapted_model = await maml.fast_adapt(new_task, n_steps=5)

        # Use adapted model (learned from only 3 examples!)
        result = adapted_model(new_input)
    """

    def __init__(
        self,
        model: nn.Module,
        inner_lr: float = 0.01,
        outer_lr: float = 0.001,
        inner_steps: int = 5,
        device: str | None = None,
    ) -> None:
        """Initialize MAML meta-learner.

        Args:
            model: Base model to meta-learn
            inner_lr: Learning rate for inner loop (task adaptation)
            outer_lr: Learning rate for outer loop (meta-update)
            inner_steps: Number of inner loop gradient steps
        """
        self._model = model
        self._inner_lr = inner_lr
        self._outer_lr = outer_lr
        self._inner_steps = inner_steps

        # Get parameters - handle both nn.Module and custom models
        if hasattr(model, "parameters") and callable(model.parameters):
            params = list(model.parameters())
        else:
            # Custom model - collect parameters from submodules
            params = []
            for attr_name in dir(model):
                attr = getattr(model, attr_name, None)
                if isinstance(attr, nn.Module):
                    params.extend(attr.parameters())

        if not params:
            # This is expected for placeholder models during initialization
            # MAML will work correctly once a real model is provided
            logger.debug("No parameters found in model for MAML optimizer (using placeholder)")
            dummy_param = torch.nn.Parameter(torch.tensor([0.0]))
            params = [dummy_param]  # Dummy parameter

        self._meta_optimizer = torch.optim.Adam(params, lr=outer_lr)
        self._device = device or ("mps" if torch.backends.mps.is_available() else "cpu")

        # Move model to device if supported
        if hasattr(self._model, "to") and callable(self._model.to):
            try:
                self._model.to(self._device)
                logger.info(f"Model moved to {self._device}")
            except Exception as e:
                logger.warning(f"Could not move model to device: {e}")

        self._meta_iterations = 0
        self._tasks_trained = 0
        logger.info(
            f"MAML initialized: inner_lr={inner_lr}, outer_lr={outer_lr}, inner_steps={inner_steps}, device={self._device}"
        )

    async def meta_train(self, task_batch: list[dict[str, Any]], meta_batch_size: int = 4) -> float:
        """Meta-training on batch of tasks.

        Args:
            task_batch: List of tasks, each with 'support' and 'query' sets
            meta_batch_size: Number of tasks to process per meta-batch

        Returns:
            Meta-loss value
        """
        meta_loss_total = 0.0
        meta_batches = 0
        for i in range(0, len(task_batch), meta_batch_size):
            batch = task_batch[i : i + meta_batch_size]
            meta_loss = 0.0
            for task in batch:
                adapted_model = self._clone_model(self._model)
                for _step in range(self._inner_steps):
                    support_loss = self._compute_loss(adapted_model, task["support"])
                    adapted_model = self._manual_gradient_step(
                        adapted_model, support_loss, self._inner_lr
                    )
                query_loss = self._compute_loss(adapted_model, task["query"])
                meta_loss += query_loss  # type: ignore[assignment]
                self._tasks_trained += 1
            meta_loss /= len(batch)
            self._meta_optimizer.zero_grad()
            meta_loss.backward()  # type: ignore[attr-defined]
            self._meta_optimizer.step()
            meta_loss_total += meta_loss.item()  # type: ignore[attr-defined]
            meta_batches += 1
        avg_meta_loss = meta_loss_total / max(1, meta_batches)
        self._meta_iterations += 1
        logger.info(f"MAML meta-iteration {self._meta_iterations}: meta_loss={avg_meta_loss:.4f}")
        return avg_meta_loss

    async def fast_adapt(self, task: dict[str, Any], n_steps: int | None = None) -> nn.Module:
        """Quickly adapt to new task with few examples.

        Args:
            task: Task with 'support' examples (1-5 examples)
            n_steps: Adaptation steps (default: self._inner_steps)

        Returns:
            Adapted model (ready for inference on this task)
        """
        if n_steps is None:
            n_steps = self._inner_steps
        adapted_model = self._clone_model(self._model)
        for _step in range(n_steps):
            loss = self._compute_loss(adapted_model, task["support"])
            adapted_model = self._manual_gradient_step(adapted_model, loss, self._inner_lr)
        logger.debug(
            f"Fast adapted to task with {len(task['support'])} examples in {n_steps} steps"
        )
        return adapted_model

    def _clone_model(self, model: nn.Module) -> nn.Module:
        """Clone model for task-specific adaptation.

        Args:
            model: Model to clone

        Returns:
            Cloned model
        """
        cloned = copy.deepcopy(model)

        # Set to training mode if supported
        if hasattr(cloned, "train") and callable(cloned.train):
            try:
                cloned.train()
            except Exception as e:
                logger.warning(f"Could not set[Any] model to train mode: {e}")

        return cloned

    def _manual_gradient_step(self, model: nn.Module, loss: torch.Tensor, lr: float) -> nn.Module:
        """Manual gradient descent step (for inner loop).

        Args:
            model: Model to update
            loss: Loss tensor
            lr: Learning rate

        Returns:
            Updated model
        """
        grads = torch.autograd.grad(loss, model.parameters(), create_graph=True)  # type: ignore[arg-type]
        updated_params = []
        for param, grad in zip(model.parameters(), grads, strict=False):
            updated_param = param - lr * grad
            updated_params.append(updated_param)
        updated_model = copy.deepcopy(model)
        for param, updated_param in zip(updated_model.parameters(), updated_params, strict=False):
            param.data = updated_param.data
        return updated_model

    def _compute_loss(self, model: nn.Module, dataset: list[dict[str, Any]]) -> torch.Tensor:
        """Compute loss on dataset.

        Args:
            model: Model to evaluate
            dataset: List of {input, label} dicts

        Returns:
            Loss tensor
        """
        if not dataset:
            return torch.tensor(0.0, requires_grad=True)
        inputs = torch.stack(
            [torch.tensor(item["input"], dtype=torch.float32) for item in dataset]
        ).to(self._device)
        labels = torch.stack(
            [torch.tensor(item["label"], dtype=torch.long) for item in dataset]
        ).to(self._device)
        outputs = model(inputs)
        loss = F.cross_entropy(outputs, labels)
        return loss

    def get_model(self) -> nn.Module:
        """Get meta-learned model (good initialization).

        Returns:
            Meta-learned model
        """
        return self._model

    async def save_meta_model(self, path: str) -> None:
        """Save meta-learned model.

        Args:
            path: Save path
        """
        torch.save(
            {
                "model_state": self._model.state_dict(),
                "meta_iterations": self._meta_iterations,
                "tasks_trained": self._tasks_trained,
                "config": {
                    "inner_lr": self._inner_lr,
                    "outer_lr": self._outer_lr,
                    "inner_steps": self._inner_steps,
                },
            },
            path,
        )
        logger.info(f"💾 Meta-learned model saved to {path}")

    async def load_meta_model(self, path: str) -> None:
        """Load meta-learned model.

        Args:
            path: Load path
        """
        # SECURITY FIX (Dec 15, 2025): Use weights_only=True to prevent arbitrary code execution
        # If this fails with pickle errors, the checkpoint must be re-saved with torch.save()
        try:
            checkpoint = torch.load(path, map_location=self._device, weights_only=True)
        except Exception as e:
            logger.error(
                f"Failed to load checkpoint with weights_only=True. "
                f"This checkpoint may contain unsafe pickle data. Error: {e}"
            )
            raise ValueError(
                f"Unsafe checkpoint format at {path}. "
                "Please re-save the checkpoint using torch.save() with only tensor data."
            ) from e

        self._model.load_state_dict(checkpoint["model_state"])
        self._meta_iterations = checkpoint.get("meta_iterations", 0)
        self._tasks_trained = checkpoint.get("tasks_trained", 0)
        logger.info(
            f"📂 Meta-learned model loaded from {path} ({self._tasks_trained} tasks trained)"
        )


_maml: MAMLMetaLearner | None = None
