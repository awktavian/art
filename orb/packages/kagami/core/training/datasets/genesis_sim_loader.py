"""Genesis puzzle dataset for JEPA-style world-model training.

This module provides an **infinite** stream of "Genesis puzzles" designed to
train progressively harder dynamics + control concepts in a way that aligns with
the repo's curriculum phases (HIERARCHY → ROTATION → DYNAMICS → JOINT → GENERATION).

Key design goals (Dec 2025):
- **Infinite**: do not pre-generate a finite cache of trajectories.
- **Phase-aware**: puzzle distribution + difficulty can be steered by curriculum.
- **Concept-rich**: puzzles emphasize causal structure (collisions, constraints,
  control, safety barriers, invariances), not just noise.
- **Practical**: keep the dataset pickle-safe (DataLoader spawn) and initialize
  the Genesis engine lazily per-process.

IMPORTANT (Dec 2025):
- The analytic simulator has been removed. This dataset **always** uses the real
  `genesis-world` engine via `GenesisPhysicsWrapper`.
"""

from __future__ import annotations

import hashlib
import logging
from typing import Any

import numpy as np
import torch

from kagami.core.training.datasets.causal_dataset import CausalDataset

logger = logging.getLogger(__name__)


class GenesisSimDataset(CausalDataset):
    """Infinite "Genesis puzzle" dataset.

    Samples are JEPA-friendly causal trajectories:
      - `state_t`:        [T, D] float32
      - `action_t`:       [T, A] float32 (may be zeros for passive dynamics)
      - `state_t_plus_1`: [T, D] float32

    When `enable_rendering=True`, also yields:
      - `frames_t`:       [T, 3, H, W] float32 RGB frames (normalized 0-1)
      - `frames_t_plus_1`: [T, 3, H, W] float32 RGB frames

    Notes:
    - The dataset is **infinite** when iterated (`for sample in ds:`).
    - `__getitem__` remains deterministic for tests/debugging.
    - Genesis is **required** (no analytic fallback).
    """

    # Canonical action dimension (aligns with E8 "action space" conventions).
    DEFAULT_ACTION_DIM = 8

    # Canonical goal dimension (xyz goal / waypoint).
    DEFAULT_GOAL_DIM = 3

    # Default render resolution (small for training throughput).
    DEFAULT_RENDER_WIDTH = 128
    DEFAULT_RENDER_HEIGHT = 128

    # Puzzle families (kept as strings to avoid Enum friction in config/YAML).
    PUZZLE_FAMILIES_JEPA = (
        "free_fall_bounce",
        "two_body_collision_1d",
        "spring_mass",
        "damped_motion",
        "impulse_response",
    )
    PUZZLE_FAMILIES_GENERATION = (
        "goal_reach_with_barrier",
        "goal_reach_switching",
    )

    def __init__(
        self,
        split: str = "train",
        seq_len: int = 32,
        embedding_dim: int = 32,
        physics_dt: float = 1.0 / 60.0,
        seed: int | None = None,
        *,
        # Back-compat: callers may still pass this kwarg. It must not be False.
        use_real_genesis: bool | None = True,
        # Puzzle mode controls distribution: "jepa" (dynamics) vs "generation" (goal/control).
        puzzle_mode: str = "jepa",
        action_dim: int = DEFAULT_ACTION_DIM,
        goal_dim: int = DEFAULT_GOAL_DIM,
        # Streaming/throughput knobs (key optimization):
        buffer_steps: int = 8192,
        samples_per_step: int = 256,
        reset_interval_steps: int = 2048,
        # === RENDERING (Neural World Model Video Training) ===
        enable_rendering: bool = False,
        render_width: int = DEFAULT_RENDER_WIDTH,
        render_height: int = DEFAULT_RENDER_HEIGHT,
        render_every_n_steps: int = 1,  # Render every N physics steps (1 = every step)
    ):
        """Initialize GenesisSimDataset.

        Args:
            split: Dataset split ('train', 'val', 'test')
            seq_len: Number of timesteps per sequence
            embedding_dim: Dimension of state embeddings
            physics_dt: Physics timestep in seconds
            seed: Random seed for reproducibility
            use_real_genesis:
                - True / None: require real Genesis engine (always)
                - False: invalid (analytic path removed)
            puzzle_mode: "jepa" or "generation"
            action_dim: action vector dimension (default 8)
            goal_dim: goal vector dimension (default 3)
            buffer_steps: Rolling replay buffer length (in physics steps)
            samples_per_step: How many training windows to sample per new physics step
            reset_interval_steps: Reset puzzle/initial conditions every N physics steps
            enable_rendering: If True, capture RGB frames alongside state vectors
            render_width: Width of rendered frames (default 128)
            render_height: Height of rendered frames (default 128)
            render_every_n_steps: Render every N physics steps (1 = all, 2 = every other)

        Raises:
            RuntimeError: If the Genesis engine is unavailable
        """
        super().__init__()
        self.split = split
        self.seq_len = seq_len
        self.embedding_dim = embedding_dim
        self.physics_dt = physics_dt
        self.action_dim = int(action_dim)
        self.goal_dim = int(goal_dim)
        self.buffer_steps = int(max(buffer_steps, max(64, seq_len * 8)))
        self.samples_per_step = int(max(1, samples_per_step))
        self.reset_interval_steps = int(max(32, reset_interval_steps))

        # Rendering settings
        self.enable_rendering = bool(enable_rendering)
        self.render_width = int(render_width)
        self.render_height = int(render_height)
        self.render_every_n_steps = max(1, int(render_every_n_steps))

        mode = (puzzle_mode or "jepa").strip().lower()
        if mode not in {"jepa", "generation"}:
            raise ValueError(f"puzzle_mode must be 'jepa' or 'generation', got {puzzle_mode!r}")
        self.puzzle_mode = mode

        # Set seed based on split for reproducibility
        if seed is None:
            seed = {"train": 42, "val": 1337, "test": 7777}.get(split, 42)
        self.seed = seed
        self._rng = np.random.default_rng(seed)

        if use_real_genesis is False:
            raise ValueError(
                "GenesisSimDataset no longer supports use_real_genesis=False "
                "(analytic simulator removed)."
            )

        # Real Genesis engine (required). IMPORTANT: do NOT initialize in __init__ because
        # DataLoader spawn workers need the dataset to be pickleable.
        self._genesis = None  # lazy per-process backend
        self._max_objects = max(1, min(32, self.embedding_dim // 10))
        self._scene_ready = False

        # Curriculum-driven difficulty parameters (can be updated dynamically)
        self._difficulty_min: float = 0.1
        self._difficulty_max: float = 0.4
        self._num_objects_min: int = 3
        self._num_objects_max: int = 5

        backend = "real_genesis"
        render_info = f" render={render_width}x{render_height}" if enable_rendering else ""
        logger.info(
            "GenesisSimDataset initialized: split=%s mode=%s seq_len=%d dim=%d backend=%s%s (infinite iterator)",
            split,
            self.puzzle_mode,
            self.seq_len,
            self.embedding_dim,
            backend,
            render_info,
        )

    # ---------------------------------------------------------------------
    # Curriculum difficulty control
    # ---------------------------------------------------------------------

    def update_difficulty_params(
        self,
        difficulty_range: tuple[float, float] | None = None,
        num_objects_range: tuple[int, int] | None = None,
    ) -> None:
        """Update difficulty parameters from curriculum scheduler.

        This method allows the curriculum scheduler to dynamically adjust
        puzzle difficulty as training progresses through phases.

        Args:
            difficulty_range: (min, max) difficulty scalar range (0.0 to 1.0)
            num_objects_range: (min, max) number of objects in scene

        Example:
            >>> dataset.update_difficulty_params(
            ...     difficulty_range=(0.3, 0.5),
            ...     num_objects_range=(6, 8)
            ... )
        """
        if difficulty_range is not None:
            d_min, d_max = difficulty_range
            self._difficulty_min = float(np.clip(d_min, 0.0, 1.0))
            self._difficulty_max = float(np.clip(d_max, 0.0, 1.0))
            logger.info(
                f"Updated difficulty range: [{self._difficulty_min:.2f}, {self._difficulty_max:.2f}]"
            )

        if num_objects_range is not None:
            n_min, n_max = num_objects_range
            self._num_objects_min = int(max(1, n_min))
            self._num_objects_max = int(max(self._num_objects_min, n_max))
            # Update _max_objects to accommodate new range
            self._max_objects = max(self._max_objects, self._num_objects_max)
            logger.info(
                f"Updated object count range: [{self._num_objects_min}, {self._num_objects_max}]"
            )

    # ---------------------------------------------------------------------
    # Backend init (optional)
    # ---------------------------------------------------------------------

    def _try_init_real_genesis(self) -> Any:
        """Best-effort initialization of the real Genesis engine.

        Returns:
            GenesisPhysicsWrapper instance if available, else None.
        """
        try:
            # Import is cheap; actual Genesis init happens inside wrapper.initialize().
            from kagami.forge.modules.genesis_physics_wrapper import (
                GenesisPhysicsWrapper,
            )
        except Exception:
            return None

        # Try to initialize the engine; if it fails, treat as unavailable (unless required).
        try:
            import asyncio
            import os

            from torch.utils.data import get_worker_info

            # Multiprocessing best-practice:
            # - When DataLoader uses multiple processes, initializing GPU-backed Genesis
            #   in each worker can be flaky and contends with model training.
            # - Default workers to CPU unless explicitly overridden.
            env_device = (os.getenv("KAGAMI_GENESIS_DEVICE") or "").strip().lower()
            if env_device:
                device = env_device
            else:
                device = "cpu" if get_worker_info() is not None else "auto"

            wrapper = GenesisPhysicsWrapper(device=device)
            try:
                loop = asyncio.get_running_loop()
            except RuntimeError:
                try:
                    loop = asyncio.get_event_loop()
                except RuntimeError:
                    loop = asyncio.new_event_loop()
                    asyncio.set_event_loop(loop)

            loop.run_until_complete(wrapper.initialize())
            return wrapper
        except Exception:
            return None

    def __getstate__(self) -> dict[str, Any]:
        """Make the dataset pickle-safe for DataLoader spawn workers."""
        state = dict(self.__dict__)
        # Never pickle the live Genesis backend (contains unpicklable module handles).
        state["_genesis"] = None
        return state

    def _ensure_real_genesis(self) -> None:
        """Initialize the real Genesis backend lazily (per-process)."""
        if self._genesis is not None:
            return
        backend = self._try_init_real_genesis()
        if backend is None:
            raise RuntimeError(
                "Genesis backend initialization failed. Install/verify `genesis-world` "
                "and its runtime dependencies."
            )
        self._genesis = backend
        # Build a single physics scene once per process. Rebuilding scenes triggers
        # kernel recompilation and is slow/flaky under pytest timeouts.
        self._ensure_scene()

    def _ensure_scene(self) -> None:
        if self._scene_ready:
            return
        if self._genesis is None:
            raise RuntimeError("Genesis backend not initialized")
        self._run_coro(
            self._genesis.create_physics_scene(
                scene_type="physics_lab",
                gravity=(0.0, 0.0, -9.81),
                dt=float(self.physics_dt),
                show_viewer=False,
                rendering=self.enable_rendering,  # Enable renderer for video training
            )
        )
        self._scene_ready = True

    def _capture_frame(self) -> torch.Tensor:
        """Capture current frame from Genesis renderer.

        Returns:
            [3, H, W] float32 tensor normalized to [0, 1], or zeros if rendering unavailable.
        """
        H, W = self.render_height, self.render_width
        zeros = torch.zeros((3, H, W), dtype=torch.float32)

        if not self.enable_rendering or self._genesis is None:
            return zeros

        try:
            # render() returns [H, W, 3] uint8 numpy array
            rgb = self._genesis.render(width=W, height=H)

            if rgb is None:
                return zeros

            # Convert to tensor [3, H, W] float32 normalized
            frame = torch.from_numpy(rgb).permute(2, 0, 1).float() / 255.0

            # Resize if needed (Genesis may return different resolution)
            if frame.shape[1] != H or frame.shape[2] != W:
                import torch.nn.functional as F

                frame = F.interpolate(
                    frame.unsqueeze(0), size=(H, W), mode="bilinear", align_corners=False
                ).squeeze(0)

            return frame
        except Exception as e:
            logger.debug("Frame capture failed: %s", e)
            return zeros

    def __len__(self) -> int:
        """Nominal length for compatibility only.

        The dataset is fundamentally an **infinite stream**; training iterates via
        `__iter__`. We expose a finite length for legacy callers/tests.
        """
        return self.buffer_steps * max(1, self.samples_per_step)

    # ---------------------------------------------------------------------
    # Infinite iterator (optimized): many samples per physics step
    # ---------------------------------------------------------------------

    def __iter__(self):  # type: ignore[no-untyped-def]
        """Infinite stream of puzzles with amortized simulation cost.

        Core optimization:
        - Step Genesis once
        - Append to rolling buffer
        - Sample MANY training windows from that buffer

        When enable_rendering=True, also yields frames_t and frames_t_plus_1.
        """
        self._ensure_real_genesis()
        self._ensure_scene()

        # Worker-aware seeding (even though we force num_workers=0 in the curriculum loader,
        # we keep this correct for other call sites).
        try:
            from torch.utils.data import get_worker_info

            info = get_worker_info()
        except Exception:
            info = None

        worker_id = int(getattr(info, "id", 0) or 0)
        seed = int(self.seed) + 10_000 * worker_id
        rng = np.random.default_rng(seed)

        buf = int(self.buffer_steps)
        T = int(self.seq_len)
        D = int(self.embedding_dim)
        A = int(self.action_dim)
        H, W = self.render_height, self.render_width

        # Ring buffers (CPU tensors).
        states_buf = torch.zeros((buf, D), dtype=torch.float32)
        actions_buf = torch.zeros((buf, A), dtype=torch.float32)
        episode_buf = torch.zeros((buf,), dtype=torch.int64)
        puzzle_buf = torch.zeros((buf,), dtype=torch.int16)
        difficulty_buf = torch.zeros((buf,), dtype=torch.float32)

        # Frame buffer (only allocated if rendering enabled)
        frames_buf: torch.Tensor | None = None
        if self.enable_rendering:
            frames_buf = torch.zeros((buf, 3, H, W), dtype=torch.float32)

        # Episode state
        episode_id = 0
        step_abs = 0  # absolute state index for s_t (monotonic)

        families = (
            self.PUZZLE_FAMILIES_GENERATION
            if self.puzzle_mode == "generation"
            else self.PUZZLE_FAMILIES_JEPA
        )
        puzzle_types = list(families)
        puzzle_type_to_id = {p: i for i, p in enumerate(puzzle_types)}

        # Goal for generation mode
        goal = torch.zeros((self.goal_dim,), dtype=torch.float32)

        # Reset once to initialize a puzzle.
        puzzle_type = str(rng.choice(puzzle_types))
        puzzle_id = int(puzzle_type_to_id[puzzle_type])
        difficulty = float(rng.uniform(self._difficulty_min, self._difficulty_max))
        self._reset_episode(rng, puzzle_type=puzzle_type, difficulty=difficulty, goal=goal)

        # Prime buffer with initial state.
        s0 = self._read_state(last_action=torch.zeros((A,), dtype=torch.float32), goal=goal)
        states_buf[step_abs % buf] = s0
        episode_buf[step_abs % buf] = episode_id
        puzzle_buf[step_abs % buf] = puzzle_id
        difficulty_buf[step_abs % buf] = float(difficulty)
        if frames_buf is not None:
            frames_buf[step_abs % buf] = self._capture_frame()

        # Warmup: advance until we have enough history to sample windows.
        while step_abs < T + 1:
            a_t = self._compute_action(
                rng, puzzle_type=puzzle_type, difficulty=difficulty, goal=goal
            )
            actions_buf[step_abs % buf] = a_t
            self._apply_action(a_t)
            self._genesis.step(1)  # type: ignore[attr-defined]

            step_abs += 1
            s_t = self._read_state(last_action=a_t, goal=goal)
            states_buf[step_abs % buf] = s_t
            episode_buf[step_abs % buf] = episode_id
            puzzle_buf[step_abs % buf] = puzzle_id
            difficulty_buf[step_abs % buf] = float(difficulty)

            # Capture frame (respecting render_every_n_steps)
            if frames_buf is not None and (step_abs % self.render_every_n_steps) == 0:
                frames_buf[step_abs % buf] = self._capture_frame()

        # Sample queue: list[Any] of absolute start indices.
        queue: list[int] = []
        arange_states = torch.arange(T + 1, dtype=torch.int64)
        arange_actions = torch.arange(T, dtype=torch.int64)

        while True:
            if not queue:
                # Advance physics one step (refresh buffer) then enqueue many samples.
                if self.reset_interval_steps > 0 and (step_abs % self.reset_interval_steps) == 0:
                    episode_id += 1
                    puzzle_type = str(rng.choice(puzzle_types))
                    puzzle_id = int(puzzle_type_to_id[puzzle_type])
                    # Sample from curriculum-specified difficulty range (clamped to range)
                    difficulty = float(
                        np.clip(
                            rng.uniform(self._difficulty_min, self._difficulty_max),
                            self._difficulty_min,
                            self._difficulty_max,
                        )
                    )
                    self._reset_episode(
                        rng, puzzle_type=puzzle_type, difficulty=difficulty, goal=goal
                    )

                a_t = self._compute_action(
                    rng, puzzle_type=puzzle_type, difficulty=difficulty, goal=goal
                )
                actions_buf[step_abs % buf] = a_t
                self._apply_action(a_t)
                self._genesis.step(1)  # type: ignore[attr-defined]

                step_abs += 1
                s_t = self._read_state(last_action=a_t, goal=goal)
                states_buf[step_abs % buf] = s_t
                episode_buf[step_abs % buf] = episode_id
                puzzle_buf[step_abs % buf] = puzzle_id
                difficulty_buf[step_abs % buf] = float(difficulty)

                # Capture frame
                if frames_buf is not None and (step_abs % self.render_every_n_steps) == 0:
                    frames_buf[step_abs % buf] = self._capture_frame()

                # Valid start range in absolute coordinates:
                # - Need state at start..start+T
                # - Must be within last `buf` steps (ring buffer).
                min_abs = max(0, step_abs - buf + 1)
                max_start = step_abs - T
                if max_start < min_abs:
                    continue

                # Enqueue many starts (amortize sim).
                # We allow occasional rejections due to episode boundary.
                target = int(self.samples_per_step)
                for _ in range(target * 2):  # oversample for rejection
                    if len(queue) >= target:
                        break
                    s_abs = int(rng.integers(min_abs, max_start + 1))
                    # Ensure the window stays inside one episode (fast endpoint check).
                    ep0 = int(episode_buf[s_abs % buf].item())
                    ep1 = int(episode_buf[(s_abs + T) % buf].item())
                    if ep0 != ep1:
                        continue
                    queue.append(s_abs)

                if not queue:
                    continue

            start_abs = queue.pop()
            start_idx = int(start_abs % buf)

            # Metadata anchored at start.
            pid = int(puzzle_buf[start_idx].item())
            ptype = puzzle_types[pid] if 0 <= pid < len(puzzle_types) else "unknown"
            diff = float(difficulty_buf[start_idx].item())
            ep = int(episode_buf[start_idx].item())

            state_idxs = (arange_states + start_abs) % buf
            action_idxs = (arange_actions + start_abs) % buf

            window_states = states_buf.index_select(0, state_idxs)
            window_actions = actions_buf.index_select(0, action_idxs)

            state_t = window_states[:-1]
            state_tp1 = window_states[1:]
            action_t = window_actions

            fingerprint = hashlib.md5(
                f"genesis|{self.split}|{self.puzzle_mode}|ep={ep}|start={start_abs}|ptype={ptype}".encode()
            ).hexdigest()[:16]

            # Generate DYNAMIC text caption describing actual physics state
            # This creates unique, semantically meaningful captions for VL-JEPA
            caption = self._generate_dynamic_caption(state_t, state_tp1, action_t, ptype)

            sample = {
                "state_t": state_t,
                "action_t": action_t,
                "state_t_plus_1": state_tp1,
                "horizon": 1,
                "fingerprint": fingerprint,
                "caption": caption,  # Dynamic state-based description
                "metadata": {
                    "puzzle_type": ptype,
                    "difficulty": diff,
                    "episode_id": ep,
                    "physics_dt": float(self.physics_dt),
                    "mode": self.puzzle_mode,
                    "backend": "real_genesis",
                    "max_objects": int(self._max_objects),
                    "has_frames": self.enable_rendering,
                },
            }

            # Add frames if rendering enabled
            if frames_buf is not None:
                window_frames = frames_buf.index_select(0, state_idxs)
                sample["frames_t"] = window_frames[:-1]  # [T, 3, H, W]
                sample["frames_t_plus_1"] = window_frames[1:]  # [T, 3, H, W]

            yield sample

    def __getitem__(self, idx: int) -> dict[str, Any]:
        """Legacy indexed access (not used in training).

        Kept only to satisfy the `CausalDataset` abstract contract. Prefer iterating
        the dataset instead.
        """
        it = iter(self)
        for _ in range(max(0, int(idx))):
            next(it)
        return next(it)

    # ---------------------------------------------------------------------
    # Real Genesis puzzle simulator (no analytic fallback)
    # ---------------------------------------------------------------------

    # ─────────────────────────────────────────────────────────────────────────────
    # DYNAMIC CAPTION GENERATION (VL-JEPA Training - Dec 28, 2025)
    # ─────────────────────────────────────────────────────────────────────────────
    # Generates UNIQUE captions describing actual physics state.
    # Each caption is different based on positions, velocities, and dynamics.
    # This provides semantic diversity required for VL-JEPA training.

    def _generate_dynamic_caption(
        self,
        state_t: torch.Tensor,  # [T, D]
        state_tp1: torch.Tensor,  # [T, D]
        action_t: torch.Tensor,  # [T, A]
        puzzle_type: str,
    ) -> str:
        """Generate a DYNAMIC caption describing actual physics state.

        Unlike static templates, this generates unique captions based on:
        - Actual positions and velocities from the state tensor
        - Motion direction and magnitude
        - State changes between t and t+1

        Args:
            state_t: State at time t [T, D]
            state_tp1: State at time t+1 [T, D]
            action_t: Actions [T, A]
            puzzle_type: Type of physics puzzle

        Returns:
            Unique text description of the actual physics dynamics.
        """
        # Extract physics from state (skip action/goal prefix)
        # State layout: [action(8), goal(3), physics(...)]
        physics_start = self.action_dim + self.goal_dim  # 8 + 3 = 11

        # Get mean state across sequence for summary (move to CPU for numpy)
        s_t = state_t.mean(dim=0).cpu()  # [D]
        s_tp1 = state_tp1.mean(dim=0).cpu()  # [D]

        # Extract position-like values (first 3 physics dims)
        if s_t.shape[0] > physics_start + 3:
            pos = s_t[physics_start : physics_start + 3].numpy()
            pos_next = s_tp1[physics_start : physics_start + 3].numpy()
            velocity = pos_next - pos
        else:
            pos = np.zeros(3)
            velocity = np.zeros(3)

        # Compute motion characteristics
        speed = float(np.linalg.norm(velocity))
        height = float(pos[2]) if len(pos) > 2 else 0.0

        # Direction descriptions
        if abs(velocity[2]) > 0.01:
            v_dir = "upward" if velocity[2] > 0 else "downward"
        elif abs(velocity[0]) > 0.01:
            v_dir = "rightward" if velocity[0] > 0 else "leftward"
        elif abs(velocity[1]) > 0.01:
            v_dir = "forward" if velocity[1] > 0 else "backward"
        else:
            v_dir = "stationary"

        # Speed descriptions
        if speed > 2.0:
            speed_desc = "rapidly"
        elif speed > 0.5:
            speed_desc = "steadily"
        elif speed > 0.1:
            speed_desc = "slowly"
        else:
            speed_desc = "barely"

        # Height descriptions
        if height > 1.0:
            h_desc = "high"
        elif height > 0.3:
            h_desc = "mid-level"
        elif height > 0.0:
            h_desc = "low"
        else:
            h_desc = "ground-level"

        # Action magnitude
        action_mag = float(action_t.cpu().abs().mean())
        has_action = action_mag > 0.1

        # Generate puzzle-specific dynamic caption
        if puzzle_type == "free_fall_bounce":
            if velocity[2] < -0.1:
                return f"Object falling {speed_desc} at {h_desc} height, moving {v_dir}."
            elif velocity[2] > 0.1:
                return f"Object bouncing {speed_desc} upward from {h_desc} position."
            else:
                return f"Object at {h_desc} height, {v_dir}, speed {speed:.2f}."

        elif puzzle_type == "two_body_collision_1d":
            if speed > 0.5:
                return f"Objects approaching {speed_desc}, relative velocity {speed:.2f}."
            else:
                return f"Post-collision state, objects moving {v_dir} at {speed:.2f}."

        elif puzzle_type == "spring_mass":
            if abs(velocity[0]) > abs(velocity[2]):
                return f"Spring oscillation: mass moving {v_dir} {speed_desc}."
            else:
                return f"Harmonic motion at {h_desc} displacement, velocity {speed:.2f}."

        elif puzzle_type == "damped_motion":
            return f"Damped motion: {speed_desc} {v_dir}, decaying speed {speed:.2f}."

        elif puzzle_type == "impulse_response":
            if has_action:
                return f"Impulse applied, object accelerating {v_dir} {speed_desc}."
            else:
                return f"Post-impulse motion: {v_dir} at {speed:.2f} velocity."

        elif puzzle_type == "goal_reach_with_barrier":
            return f"Navigation: moving {v_dir} {speed_desc} toward goal, height {height:.2f}."

        elif puzzle_type == "goal_reach_switching":
            return f"Goal switching: current motion {v_dir}, speed {speed:.2f}."

        else:
            # Generic dynamic caption
            return f"Physics state: position ({pos[0]:.1f}, {pos[1]:.1f}, {pos[2]:.1f}), moving {v_dir} at {speed:.2f}."

    def _run_coro(self, coro) -> Any:  # type: ignore[no-untyped-def]
        """Run an async coroutine in a local event loop (sync context).

        Training / DataLoader iteration is synchronous; we intentionally avoid
        supporting "already-running event loop" scenarios here.
        """
        import asyncio

        try:
            loop = asyncio.get_event_loop()
        except RuntimeError:
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
        return loop.run_until_complete(coro)

    def _get_entity(self, name: str) -> None:
        if self._genesis is None:
            return None
        return getattr(self._genesis, "_entities", {}).get(name)

    def _set_entity_position(self, entity: Any, *, pos: np.ndarray[Any, Any]) -> None:
        p = np.asarray(pos, dtype=np.float32).reshape(-1)[:3]
        if hasattr(entity, "set_pos"):
            try:
                entity.set_pos([float(p[0]), float(p[1]), float(p[2])])
                return
            except Exception:
                pass
        if hasattr(entity, "set_position"):
            try:
                entity.set_position([float(p[0]), float(p[1]), float(p[2])])
            except Exception:
                pass

    def _set_entity_velocity(
        self,
        entity: Any,
        *,
        linear: np.ndarray[Any, Any],
        angular: np.ndarray[Any, Any] | None = None,
    ) -> None:
        ang = (
            np.zeros((3,), dtype=np.float32)
            if angular is None
            else np.asarray(angular, dtype=np.float32)[:3]
        )
        lin = np.asarray(linear, dtype=np.float32)[:3]
        v6 = [
            float(lin[0]),
            float(lin[1]),
            float(lin[2]),
            float(ang[0]),
            float(ang[1]),
            float(ang[2]),
        ]
        if hasattr(entity, "set_dofs_velocity"):
            entity.set_dofs_velocity(v6)

    def _get_entity_pos_vel(self, entity: Any) -> tuple[np.ndarray[Any, Any], np.ndarray[Any, Any]]:
        # Position
        pos = np.zeros((3,), dtype=np.float32)
        try:
            p = entity.get_pos() if hasattr(entity, "get_pos") else None
            if p is not None:
                if hasattr(p, "numpy"):
                    p = p.numpy()
                arr = np.asarray(p, dtype=np.float32).reshape(-1)
                pos[: min(3, arr.shape[0])] = arr[:3]
        except Exception:
            pass

        vel = np.zeros((3,), dtype=np.float32)
        try:
            v = entity.get_vel() if hasattr(entity, "get_vel") else None
            if v is not None:
                if hasattr(v, "numpy"):
                    v = v.numpy()
                arr = np.asarray(v, dtype=np.float32).reshape(-1)
                vel[: min(3, arr.shape[0])] = arr[:3]
        except Exception:
            pass

        return pos, vel

    # ---------------------------------------------------------------------
    # Streaming mechanics
    # ---------------------------------------------------------------------

    def _reset_episode(
        self,
        rng: np.random.Generator,
        *,
        puzzle_type: str,
        difficulty: float,
        goal: torch.Tensor,
    ) -> None:
        """Reset scene state for a new puzzle episode (fast, no scene rebuild)."""
        if self._genesis is None:
            raise RuntimeError("Genesis backend not initialized")

        self._ensure_scene()

        sphere = self._get_entity("sphere")
        box = self._get_entity("box")

        # Spatial reset (keep within a small region).
        if sphere is not None:
            self._set_entity_position(
                sphere,
                pos=np.array(
                    [
                        float(rng.uniform(-0.8, -0.2)),
                        float(rng.uniform(-0.2, 0.2)),
                        float(rng.uniform(1.0, 2.5)),
                    ],
                    dtype=np.float32,
                ),
            )
        if box is not None:
            self._set_entity_position(
                box,
                pos=np.array(
                    [
                        float(rng.uniform(0.2, 0.8)),
                        float(rng.uniform(-0.2, 0.2)),
                        float(rng.uniform(1.0, 2.5)),
                    ],
                    dtype=np.float32,
                ),
            )

        # Velocity reset (difficulty scales magnitude).
        v_scale = float(0.5 + 6.0 * float(difficulty))
        if puzzle_type == "two_body_collision_1d" and sphere is not None and box is not None:
            v = float(rng.uniform(0.8, 1.5) * v_scale)
            self._set_entity_velocity(sphere, linear=np.array([v, 0.0, 0.0], dtype=np.float32))
            self._set_entity_velocity(box, linear=np.array([-v, 0.0, 0.0], dtype=np.float32))
        else:
            if sphere is not None:
                self._set_entity_velocity(
                    sphere,
                    linear=rng.uniform(-v_scale, v_scale, size=(3,)).astype(np.float32),
                    angular=rng.uniform(-v_scale, v_scale, size=(3,)).astype(np.float32) * 0.2,
                )
            if box is not None:
                self._set_entity_velocity(
                    box,
                    linear=rng.uniform(-v_scale, v_scale, size=(3,)).astype(np.float32),
                    angular=rng.uniform(-v_scale, v_scale, size=(3,)).astype(np.float32) * 0.2,
                )

        # Update goal in-place for generation mode (kept in state vector).
        if self.puzzle_mode == "generation":
            g = rng.uniform(-1.0, 1.0, size=(3,)).astype(np.float32)
            g[2] = float(rng.uniform(0.2, 1.0))
            goal[: min(goal.numel(), 3)] = torch.from_numpy(g[: min(3, goal.numel())])
        else:
            goal.zero_()

    def _compute_action(
        self,
        rng: np.random.Generator,
        *,
        puzzle_type: str,
        difficulty: float,
        goal: torch.Tensor,
    ) -> torch.Tensor:
        """Compute an action vector for the next transition."""
        a = torch.zeros((self.action_dim,), dtype=torch.float32)

        sphere = self._get_entity("sphere")  # type: ignore[func-returns-value]
        if self.puzzle_mode == "generation" and sphere is not None:
            # PD controller towards goal (interpreted as desired linear velocity).
            pos, vel = self._get_entity_pos_vel(sphere)
            to_goal = goal.detach().cpu().numpy()[:3] - pos
            kp = float(0.8 + 2.5 * difficulty)
            kd = float(0.1 + 0.5 * difficulty)
            u = kp * to_goal - kd * vel
            u = np.clip(u, -3.0, 3.0).astype(np.float32)
            a[:3] = torch.from_numpy(u[:3])
            return a

        # JEPA mode: sparse impulses (causal interventions).
        impulse_prob = float(0.01 + 0.12 * difficulty)
        if float(rng.random()) < impulse_prob:
            u = rng.normal(0.0, 1.0 + 2.0 * difficulty, size=(3,)).astype(np.float32)
            u = np.clip(u, -3.0, 3.0).astype(np.float32)
            a[:3] = torch.from_numpy(u[:3])
        return a

    def _apply_action(self, a: torch.Tensor) -> None:
        """Apply action to Genesis entities (interpreted as linear velocity command)."""
        sphere = self._get_entity("sphere")  # type: ignore[func-returns-value]
        if sphere is None:
            return
        u = a.detach().cpu().numpy().reshape(-1)
        if u.shape[0] >= 3:
            self._set_entity_velocity(sphere, linear=u[:3])

    def _read_state(self, *, last_action: torch.Tensor, goal: torch.Tensor) -> torch.Tensor:
        """Read and pack current physics state into [D] vector (CPU tensor)."""
        if self._genesis is None:
            raise RuntimeError("Genesis backend not initialized")

        phys = self._genesis.get_differentiable_state(max_objects=int(self._max_objects))

        flat = phys.detach().reshape(-1)

        vec = torch.zeros((self.embedding_dim,), dtype=torch.float32)
        cursor = 0

        a_dim = min(int(self.action_dim), int(vec.shape[0]))
        if a_dim > 0:
            vec[cursor : cursor + a_dim] = last_action[:a_dim].to(dtype=torch.float32)
            cursor += a_dim

        g_dim = min(int(self.goal_dim), max(0, int(vec.shape[0] - cursor)))
        if g_dim > 0:
            vec[cursor : cursor + g_dim] = goal[:g_dim].to(dtype=torch.float32)
            cursor += g_dim

        space = int(vec.shape[0] - cursor)
        if space > 0:
            vec[cursor : cursor + min(space, int(flat.numel()))] = flat[:space].to(
                dtype=torch.float32
            )

        return vec
