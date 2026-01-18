"""CatastropheMemory: Continual Learning via Landscape Topology.

Created: December 14, 2025
Purpose: Prevent catastrophic forgetting by maintaining task wells in landscape

This module implements continual learning by:
1. Carving "wells" in the loss landscape for each task
2. Detecting bifurcation points (task boundaries)
3. Replay sampling from high-risk boundaries
4. Maintaining landscape topology across tasks
"""

from __future__ import annotations

from dataclasses import dataclass

import torch
import torch.nn as nn


@dataclass
class TaskWell:
    """Represents a stable attractor well for a task."""

    task_idx: int
    center: torch.Tensor  # [state_dim]
    depth: float
    coefficients: torch.Tensor  # Catastrophe coefficients [num_catastrophes, state_dim, 4]
    boundary_samples: list[torch.Tensor]


@dataclass
class BifurcationSample:
    """Sample from task boundary (bifurcation point)."""

    state: torch.Tensor
    task_idx: int
    risk: float  # Forgetting risk [0, 1]


@dataclass
class Boundary:
    """Boundary between two task wells."""

    from_task: int
    to_task: int
    states: list[torch.Tensor]
    sharpness: float
    importance: float


class CatastropheMemory(nn.Module):
    """Continual learning via catastrophe theory landscape."""

    def __init__(
        self,
        state_dim: int = 256,
        num_catastrophes: int = 7,
        replay_buffer_size: int = 1000,
    ):
        super().__init__()
        self.state_dim = state_dim
        self.num_catastrophes = num_catastrophes
        self.replay_buffer_size = replay_buffer_size

        # Task wells
        self.wells: dict[str, TaskWell] = {}
        self.boundaries: dict[tuple[int, int], Boundary] = {}

        # Replay buffer
        self.replay_buffer: list[BifurcationSample] = []

        # Stats
        self.stats = {
            "tasks_learned": 0,
            "bifurcations_stored": 0,
        }

    def learn_task(self, states: torch.Tensor, task_name: str) -> int:
        """Learn a new task by carving a well.

        Args:
            states: Task states [N, state_dim]
            task_name: Task identifier

        Returns:
            task_idx: Index of learned task
        """
        task_idx = len(self.wells)

        # Compute well center (mean)
        center = states.mean(dim=0)

        # Compute well depth (normalized standard deviation)
        # Divide by sqrt(N * state_dim) to normalize scale
        depth = float((states - center).pow(2).mean().sqrt())

        # Initialize catastrophe coefficients
        coefficients = torch.randn(self.num_catastrophes, self.state_dim, 4) * 0.1

        # Store boundary samples
        boundary_samples = []
        if len(states) > 10:
            # Sample from periphery (high variance points)
            distances = (states - center).norm(dim=1)
            threshold = distances.quantile(0.8)
            boundary_indices = (distances > threshold).nonzero(as_tuple=True)[0]
            if len(boundary_indices) > 0:
                boundary_samples = [states[i] for i in boundary_indices[:10]]

        well = TaskWell(
            task_idx=task_idx,
            center=center,
            depth=depth,
            coefficients=coefficients,
            boundary_samples=boundary_samples,
        )

        # Overwrite if task exists
        self.wells[task_name] = well

        # Create boundaries to existing tasks
        for existing_name, existing_well in self.wells.items():
            if existing_name == task_name:
                continue

            # Bidirectional boundaries
            self._create_boundary(task_idx, existing_well.task_idx)
            self._create_boundary(existing_well.task_idx, task_idx)

        self.stats["tasks_learned"] = len(self.wells)
        return task_idx

    def _create_boundary(self, from_idx: int, to_idx: int) -> None:
        """Create boundary between two tasks."""
        # Find states between tasks
        from_well = None
        to_well = None
        for well in self.wells.values():
            if well.task_idx == from_idx:
                from_well = well
            if well.task_idx == to_idx:
                to_well = well

        if from_well is None or to_well is None:
            return

        # Compute sharpness (distance between centers)
        distance = (from_well.center - to_well.center).norm()
        sharpness = float(1.0 / (distance + 1e-6))

        # Importance based on task order
        importance = 1.0 / (abs(from_idx - to_idx) + 1)

        # Generate boundary states by interpolating between well centers
        boundary_states = []
        num_interpolation_points = 10
        for i in range(1, num_interpolation_points + 1):
            alpha = i / (num_interpolation_points + 1)
            interpolated_state = (1 - alpha) * from_well.center + alpha * to_well.center
            boundary_states.append(interpolated_state)

        boundary = Boundary(
            from_task=from_idx,
            to_task=to_idx,
            states=boundary_states,
            sharpness=sharpness,
            importance=importance,
        )

        self.boundaries[(from_idx, to_idx)] = boundary

    def add_bifurcation(self, state: torch.Tensor, task_idx: int, risk: float) -> None:
        """Add bifurcation sample to replay buffer.

        Args:
            state: State at bifurcation point [state_dim]
            task_idx: Task index
            risk: Forgetting risk [0, 1]
        """
        sample = BifurcationSample(state=state, task_idx=task_idx, risk=risk)

        self.replay_buffer.append(sample)

        # Maintain buffer size
        if len(self.replay_buffer) > self.replay_buffer_size:
            # Remove lowest risk samples
            self.replay_buffer.sort(key=lambda s: s.risk, reverse=True)
            self.replay_buffer = self.replay_buffer[: self.replay_buffer_size]

        self.stats["bifurcations_stored"] = len(self.replay_buffer)

    def sample_bifurcations(self, batch_size: int) -> dict[str, torch.Tensor] | None:
        """Sample bifurcations for replay.

        Args:
            batch_size: Number of samples

        Returns:
            Batch dict[str, Any] with states, task_labels, risks
        """
        if len(self.replay_buffer) == 0:
            return None

        # Importance sampling by risk
        risks = torch.tensor([s.risk for s in self.replay_buffer])
        probs = risks / risks.sum()

        indices = torch.multinomial(probs, batch_size, replacement=True)

        states = []
        task_labels = []
        sampled_risks = []

        for idx in indices:
            sample = self.replay_buffer[int(idx)]
            states.append(sample.state)
            task_labels.append(sample.task_idx)
            sampled_risks.append(sample.risk)

        return {
            "states": torch.stack(states),
            "task_labels": torch.tensor(task_labels, dtype=torch.long),
            "risks": torch.tensor(sampled_risks),
        }

    def replay_loss(self, states: torch.Tensor, task_labels: torch.Tensor) -> torch.Tensor:
        """Compute replay loss to maintain landscape.

        Args:
            states: Batch of states [B, state_dim]
            task_labels: Task indices [B]

        Returns:
            loss: Scalar loss
        """
        loss = torch.tensor(0.0, device=states.device, requires_grad=True)

        for i, state in enumerate(states):
            task_idx = int(task_labels[i])

            # Find corresponding well
            well = None
            for w in self.wells.values():
                if w.task_idx == task_idx:
                    well = w
                    break

            if well is None:
                continue

            # Attraction loss: pull state toward well center
            distance = (state - well.center).norm()
            attraction = distance.pow(2) * well.depth

            loss = loss + attraction

        return loss / len(states)

    def compute_landscape(self, states: torch.Tensor) -> torch.Tensor:
        """Compute potential landscape at states.

        Args:
            states: States [N, state_dim]

        Returns:
            potentials: Potential values [N]
        """
        potentials = []

        for state in states:
            # Sum potentials from all wells
            total_potential = 0.0

            for well in self.wells.values():
                distance = (state - well.center).norm()
                potential = well.depth / (distance + 1e-6)
                total_potential += float(potential)

            potentials.append(total_potential)

        return torch.tensor(potentials, device=states.device)

    def get_well_depth(self, task_name: str) -> float:
        """Get depth of task well.

        Args:
            task_name: Task identifier

        Returns:
            depth: Well depth (0 if task not found)
        """
        well = self.wells.get(task_name)
        if well is None:
            return 0.0
        return well.depth

    def get_stats(self) -> dict[str, int]:
        """Get memory statistics."""
        return {
            "tasks_learned": self.stats["tasks_learned"],
            "num_wells": len(self.wells),
            "bifurcations_stored": self.stats["bifurcations_stored"],
            "buffer_size": len(self.replay_buffer),
        }


__all__ = ["BifurcationSample", "Boundary", "CatastropheMemory", "TaskWell"]
