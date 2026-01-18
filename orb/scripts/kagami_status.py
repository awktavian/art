#!/usr/bin/env python3
"""
鏡 Kagami Status Bar — Complete System Monitor

A macOS menu bar app providing real-time visibility into:
- API health and status
- Training progress
- Colony activity
- Smart home state
- System resources

Design Philosophy (Theory of Mind):
- Immediate: Glanceable status without clicking
- Actionable: Common tasks one click away
- Informative: Details on demand, not overwhelm
- Safe: Quick access to emergency controls

Icon States:
    鏡  = Idle (nothing running)
    🔥 = Training active
    🌐 = API running
    ⚡ = Both API + Training
    ⚠️ = Error/alert state
    🏠 = Smart home mode active
"""

from __future__ import annotations

import json
import subprocess
import time
import webbrowser
from dataclasses import dataclass
from pathlib import Path

import psutil
import rumps

# =============================================================================
# CONFIGURATION
# =============================================================================

KAGAMI_ROOT = Path(__file__).parent.parent.resolve()
SATELLITES_API = KAGAMI_ROOT / "satellites" / "api"
LOG_DIR = KAGAMI_ROOT / "logs"
RUN_DIR = KAGAMI_ROOT / "run"
CHECKPOINTS_DIR = KAGAMI_ROOT / "checkpoints"
API_PID_FILE = RUN_DIR / "kagami-api.pid"
LAUNCHER_SCRIPT = KAGAMI_ROOT / "scripts" / "kagami_api_launcher.py"
TRAINING_SCRIPT = KAGAMI_ROOT / "scripts" / "training" / "train_kagami.py"

API_PORT = 8001
API_URL = f"http://localhost:{API_PORT}"


# =============================================================================
# DATA CLASSES
# =============================================================================


@dataclass
class ProcessInfo:
    """Information about a running process."""

    pid: int | None = None
    running: bool = False
    cpu_percent: float = 0.0
    memory_mb: float = 0.0
    uptime_seconds: float = 0.0


@dataclass
class APIHealth:
    """API health information."""

    status: str = "unknown"
    safety_score: float | None = None
    active_colonies: list[str] | None = None
    uptime_ms: float | None = None
    error: str | None = None


@dataclass
class TrainingProgress:
    """Training progress information."""

    epoch: int = 0
    step: int = 0
    loss: float | None = None
    learning_rate: float | None = None
    eta_minutes: float | None = None


# =============================================================================
# STATUS BAR APPLICATION
# =============================================================================


class KagamiStatusApp(rumps.App):
    """
    鏡 Kagami Status Bar Application

    Menu Structure:
    ─────────────────────────────────
    Status: [state]
    ─────────────────────────────────
    🌐 API
      ├─ Status: Running (PID 12345)
      ├─ Health: OK (h(x) = 0.85)
      ├─ Uptime: 2h 15m
      ├─ ──────────────
      ├─ Start API
      ├─ Stop API
      ├─ Open Docs (/docs)
      └─ Open Health (/health)
    ─────────────────────────────────
    🔥 Training
      ├─ Status: Running (PID 12346)
      ├─ Epoch: 15/100 (15%)
      ├─ Loss: 0.0234
      ├─ ETA: ~45 minutes
      ├─ ──────────────
      ├─ Start Training
      ├─ Stop Training
      └─ Open TensorBoard
    ─────────────────────────────────
    🧠 Colonies
      ├─ 🔥 Spark: idle
      ├─ ⚒️ Forge: active
      ├─ 🌊 Flow: idle
      ├─ 🔗 Nexus: idle
      ├─ 🗼 Beacon: idle
      ├─ 🌿 Grove: idle
      └─ 💎 Crystal: idle
    ─────────────────────────────────
    💻 System
      ├─ CPU: 45%
      ├─ Memory: 8.2 GB
      ├─ Python Processes: 3
      └─ GPU: MPS (12.4 GB)
    ─────────────────────────────────
    📂 Quick Access
      ├─ Open Logs
      ├─ Open Checkpoints
      ├─ View Recent Errors
      └─ API Documentation
    ─────────────────────────────────
    ⚠️ Emergency
      ├─ Kill Training
      ├─ Kill API
      └─ Kill All Python
    ─────────────────────────────────
    Quit
    """

    # Status icons for menu bar
    ICONS = {
        "idle": "鏡",
        "api": "🌐",
        "training": "🔥",
        "both": "⚡",
        "error": "⚠️",
        "home": "🏠",
    }

    COLONY_ICONS = {
        "spark": "🔥",
        "forge": "⚒️",
        "flow": "🌊",
        "nexus": "🔗",
        "beacon": "🗼",
        "grove": "🌿",
        "crystal": "💎",
    }

    def __init__(self):
        super().__init__("鏡", quit_button=None)

        # State
        self.api_info = ProcessInfo()
        self.training_info = ProcessInfo()
        self.api_health = APIHealth()
        self.training_progress = TrainingProgress()
        self.last_update = time.time()
        self.error_count = 0

        # Build menu
        self._build_menu()

        # Start update timer (every 3 seconds)
        self.timer = rumps.Timer(self._update_all, 3)
        self.timer.start()

    def _build_menu(self):
        """Build the complete menu structure."""
        # Main status (updated dynamically)
        self.status_item = rumps.MenuItem("Status: Checking...")

        # API Section
        self.api_menu = rumps.MenuItem("🌐 API")
        self.api_status = rumps.MenuItem("Status: Checking...")
        self.api_health_item = rumps.MenuItem("Health: --")
        self.api_uptime = rumps.MenuItem("Uptime: --")
        self.api_menu.add(self.api_status)
        self.api_menu.add(self.api_health_item)
        self.api_menu.add(self.api_uptime)
        self.api_menu.add(rumps.separator)
        self.api_menu.add(rumps.MenuItem("▶ Start API", callback=self._start_api))
        self.api_menu.add(rumps.MenuItem("■ Stop API", callback=self._stop_api))
        self.api_menu.add(rumps.separator)
        self.api_menu.add(rumps.MenuItem("📖 Open Docs", callback=self._open_docs))
        self.api_menu.add(rumps.MenuItem("❤️ Health Check", callback=self._open_health))
        self.api_menu.add(rumps.MenuItem("📊 Metrics", callback=self._open_metrics))

        # Training Section
        self.training_menu = rumps.MenuItem("🔥 Training")
        self.training_status = rumps.MenuItem("Status: Not running")
        self.training_epoch = rumps.MenuItem("Epoch: --")
        self.training_loss = rumps.MenuItem("Loss: --")
        self.training_eta = rumps.MenuItem("ETA: --")
        self.training_menu.add(self.training_status)
        self.training_menu.add(self.training_epoch)
        self.training_menu.add(self.training_loss)
        self.training_menu.add(self.training_eta)
        self.training_menu.add(rumps.separator)
        self.training_menu.add(rumps.MenuItem("▶ Start Training", callback=self._start_training))
        self.training_menu.add(rumps.MenuItem("■ Stop Training", callback=self._stop_training))
        self.training_menu.add(rumps.separator)
        self.training_menu.add(
            rumps.MenuItem("📈 Open TensorBoard", callback=self._open_tensorboard)
        )
        self.training_menu.add(rumps.MenuItem("📂 Checkpoints", callback=self._open_checkpoints))

        # Colonies Section
        self.colonies_menu = rumps.MenuItem("🧠 Colonies")
        self.colony_items = {}
        for colony, icon in self.COLONY_ICONS.items():
            item = rumps.MenuItem(f"{icon} {colony.title()}: idle")
            self.colony_items[colony] = item
            self.colonies_menu.add(item)

        # System Section
        self.system_menu = rumps.MenuItem("💻 System")
        self.system_cpu = rumps.MenuItem("CPU: --")
        self.system_memory = rumps.MenuItem("Memory: --")
        self.system_python = rumps.MenuItem("Python Processes: --")
        self.system_gpu = rumps.MenuItem("GPU: --")
        self.system_menu.add(self.system_cpu)
        self.system_menu.add(self.system_memory)
        self.system_menu.add(self.system_python)
        self.system_menu.add(self.system_gpu)

        # Quick Access Section
        self.quick_menu = rumps.MenuItem("📂 Quick Access")
        self.quick_menu.add(rumps.MenuItem("📋 Open Logs", callback=self._open_logs))
        self.quick_menu.add(rumps.MenuItem("💾 Open Checkpoints", callback=self._open_checkpoints))
        self.quick_menu.add(rumps.MenuItem("📝 View Recent Errors", callback=self._view_errors))
        self.quick_menu.add(rumps.separator)
        self.quick_menu.add(rumps.MenuItem("📚 CLAUDE.md", callback=self._open_claude_md))
        self.quick_menu.add(rumps.MenuItem("🏠 Home Docs", callback=self._open_home_docs))

        # Emergency Section
        self.emergency_menu = rumps.MenuItem("⚠️ Emergency")
        self.emergency_menu.add(rumps.MenuItem("🛑 Kill Training", callback=self._kill_training))
        self.emergency_menu.add(rumps.MenuItem("🛑 Kill API", callback=self._kill_api))
        self.emergency_menu.add(rumps.separator)
        self.emergency_menu.add(rumps.MenuItem("☠️ Kill All Python", callback=self._kill_all_python))

        # Assemble menu
        self.menu = [
            self.status_item,
            rumps.separator,
            self.api_menu,
            self.training_menu,
            rumps.separator,
            self.colonies_menu,
            self.system_menu,
            rumps.separator,
            self.quick_menu,
            self.emergency_menu,
            rumps.separator,
            rumps.MenuItem("Quit", callback=rumps.quit_application),
        ]

    # =========================================================================
    # UPDATE METHODS
    # =========================================================================

    def _update_all(self, _=None):
        """Update all status information."""
        self._update_process_info()
        self._update_api_health()
        self._update_training_progress()
        self._update_system_info()
        self._update_menu_bar_icon()
        self._update_menu_items()

    def _update_process_info(self):
        """Find and update process information."""
        # Reset
        self.api_info = ProcessInfo()
        self.training_info = ProcessInfo()

        for proc in psutil.process_iter(
            ["pid", "name", "cmdline", "cpu_percent", "memory_info", "create_time"]
        ):
            try:
                cmdline = " ".join(proc.info.get("cmdline") or [])

                # Check for API
                if "kagami_api" in cmdline or "kagami_api_launcher" in cmdline:
                    mem_info = proc.info.get("memory_info")
                    create_time = proc.info.get("create_time", time.time())
                    self.api_info = ProcessInfo(
                        pid=proc.info["pid"],
                        running=True,
                        cpu_percent=proc.cpu_percent(interval=0.1),
                        memory_mb=(mem_info.rss / 1024 / 1024) if mem_info else 0,
                        uptime_seconds=time.time() - create_time,
                    )

                # Check for Training
                if "train_kagami" in cmdline:
                    mem_info = proc.info.get("memory_info")
                    create_time = proc.info.get("create_time", time.time())
                    self.training_info = ProcessInfo(
                        pid=proc.info["pid"],
                        running=True,
                        cpu_percent=proc.cpu_percent(interval=0.1),
                        memory_mb=(mem_info.rss / 1024 / 1024) if mem_info else 0,
                        uptime_seconds=time.time() - create_time,
                    )

            except (psutil.NoSuchProcess, psutil.AccessDenied):
                continue

    def _update_api_health(self):
        """Fetch API health from /health endpoint."""
        if not self.api_info.running:
            self.api_health = APIHealth(status="stopped")
            return

        try:
            import urllib.request

            req = urllib.request.Request(f"{API_URL}/health", method="GET")
            req.add_header("Accept", "application/json")

            with urllib.request.urlopen(req, timeout=2) as resp:
                data = json.loads(resp.read().decode())
                self.api_health = APIHealth(
                    status=data.get("status", "unknown"),
                    safety_score=data.get("h_x"),
                    uptime_ms=data.get("uptime_ms"),
                )
        except Exception as e:
            self.api_health = APIHealth(status="error", error=str(e))

    def _update_training_progress(self):
        """Parse training progress from logs."""
        if not self.training_info.running:
            self.training_progress = TrainingProgress()
            return

        # Try to read from wandb or training logs
        try:
            log_file = LOG_DIR / "training.log"
            if log_file.exists():
                # Read last few lines for progress
                with open(log_file) as f:
                    lines = f.readlines()[-20:]

                for line in reversed(lines):
                    if "epoch" in line.lower() and "loss" in line.lower():
                        # Parse epoch and loss from log line
                        # Format varies, try common patterns
                        import re

                        epoch_match = re.search(r"epoch[:\s]+(\d+)", line, re.I)
                        loss_match = re.search(r"loss[:\s]+([\d.]+)", line, re.I)
                        step_match = re.search(r"step[:\s]+(\d+)", line, re.I)

                        self.training_progress = TrainingProgress(
                            epoch=int(epoch_match.group(1)) if epoch_match else 0,
                            step=int(step_match.group(1)) if step_match else 0,
                            loss=float(loss_match.group(1)) if loss_match else None,
                        )
                        break
        except Exception:
            pass

    def _update_system_info(self):
        """Update system resource information."""
        # CPU
        cpu_percent = psutil.cpu_percent(interval=0.1)
        self.system_cpu.title = f"CPU: {cpu_percent:.1f}%"

        # Memory
        mem = psutil.virtual_memory()
        mem_gb = mem.used / (1024**3)
        self.system_memory.title = f"Memory: {mem_gb:.1f} GB ({mem.percent:.0f}%)"

        # Python processes
        python_count = sum(
            1
            for p in psutil.process_iter(["name"])
            if "python" in (p.info.get("name") or "").lower()
        )
        self.system_python.title = f"Python Processes: {python_count}"

        # GPU (MPS on macOS)
        try:
            import torch

            if hasattr(torch.backends, "mps") and torch.backends.mps.is_available():
                # MPS doesn't have memory query, show as available
                self.system_gpu.title = "GPU: MPS (Apple Silicon)"
            elif torch.cuda.is_available():
                mem_used = torch.cuda.memory_allocated() / (1024**3)
                mem_total = torch.cuda.get_device_properties(0).total_memory / (1024**3)
                self.system_gpu.title = f"GPU: {mem_used:.1f}/{mem_total:.1f} GB"
            else:
                self.system_gpu.title = "GPU: CPU only"
        except ImportError:
            self.system_gpu.title = "GPU: Unknown"

    def _update_menu_bar_icon(self):
        """Update the menu bar icon based on current state."""
        if self.api_health.status == "error" or self.error_count > 0:
            self.title = self.ICONS["error"]
        elif self.api_info.running and self.training_info.running:
            self.title = self.ICONS["both"]
        elif self.training_info.running:
            self.title = self.ICONS["training"]
        elif self.api_info.running:
            self.title = self.ICONS["api"]
        else:
            self.title = self.ICONS["idle"]

    def _update_menu_items(self):
        """Update all menu item titles."""
        # Main status
        if self.api_info.running and self.training_info.running:
            self.status_item.title = "Status: API + Training Active"
        elif self.training_info.running:
            self.status_item.title = "Status: Training Active"
        elif self.api_info.running:
            self.status_item.title = "Status: API Running"
        else:
            self.status_item.title = "Status: Idle"

        # API section
        if self.api_info.running:
            self.api_status.title = f"Status: Running (PID {self.api_info.pid})"
            self.api_health_item.title = f"Health: {self.api_health.status}"
            uptime_str = self._format_uptime(self.api_info.uptime_seconds)
            self.api_uptime.title = f"Uptime: {uptime_str}"
        else:
            self.api_status.title = "Status: Stopped"
            self.api_health_item.title = "Health: --"
            self.api_uptime.title = "Uptime: --"

        # Training section
        if self.training_info.running:
            self.training_status.title = f"Status: Running (PID {self.training_info.pid})"
            if self.training_progress.epoch > 0:
                self.training_epoch.title = f"Epoch: {self.training_progress.epoch}"
            if self.training_progress.loss is not None:
                self.training_loss.title = f"Loss: {self.training_progress.loss:.4f}"
            uptime_str = self._format_uptime(self.training_info.uptime_seconds)
            self.training_eta.title = f"Running: {uptime_str}"
        else:
            self.training_status.title = "Status: Not running"
            self.training_epoch.title = "Epoch: --"
            self.training_loss.title = "Loss: --"
            self.training_eta.title = "ETA: --"

    @staticmethod
    def _format_uptime(seconds: float) -> str:
        """Format seconds into human-readable uptime."""
        if seconds < 60:
            return f"{int(seconds)}s"
        elif seconds < 3600:
            return f"{int(seconds // 60)}m {int(seconds % 60)}s"
        else:
            hours = int(seconds // 3600)
            minutes = int((seconds % 3600) // 60)
            return f"{hours}h {minutes}m"

    # =========================================================================
    # ACTION CALLBACKS
    # =========================================================================

    def _start_api(self, _):
        """Start the API server."""
        if self.api_info.running:
            rumps.notification("Kagami", "API already running", f"PID: {self.api_info.pid}")
            return

        subprocess.Popen(
            ["python", str(LAUNCHER_SCRIPT), "--port", str(API_PORT)],
            cwd=str(KAGAMI_ROOT),
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            start_new_session=True,
        )
        rumps.notification("鏡 Kagami", "API Starting...", f"Port {API_PORT}")

    def _stop_api(self, _):
        """Stop the API server gracefully."""
        if not self.api_info.running:
            rumps.notification("Kagami", "API not running", "")
            return

        result = subprocess.run(
            ["python", str(LAUNCHER_SCRIPT), "--stop"], capture_output=True, text=True
        )
        if result.returncode == 0:
            rumps.notification("鏡 Kagami", "API Stopped", "")
        else:
            # Fallback to direct kill
            self._kill_api(None)

    def _start_training(self, _):
        """Start training."""
        if self.training_info.running:
            rumps.notification(
                "Kagami", "Training already running", f"PID: {self.training_info.pid}"
            )
            return

        subprocess.Popen(
            [
                "python",
                str(TRAINING_SCRIPT),
                "--config",
                "config/training_optimal.yaml",
                "--log-dir",
                "checkpoints/kagami_full",
            ],
            cwd=str(KAGAMI_ROOT),
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            start_new_session=True,
        )
        rumps.notification("鏡 Kagami", "Training Started", "🔥")

    def _stop_training(self, _):
        """Stop training gracefully."""
        if not self.training_info.running:
            rumps.notification("Kagami", "Training not running", "")
            return

        try:
            proc = psutil.Process(self.training_info.pid)
            proc.terminate()
            proc.wait(timeout=10)
            rumps.notification("鏡 Kagami", "Training Stopped", "")
        except Exception as e:
            rumps.notification("Kagami", "Failed to stop training", str(e))

    def _open_docs(self, _):
        """Open API documentation."""
        if self.api_info.running:
            webbrowser.open(f"{API_URL}/docs")
        else:
            rumps.notification("Kagami", "API not running", "Start API first")

    def _open_health(self, _):
        """Open health endpoint."""
        if self.api_info.running:
            webbrowser.open(f"{API_URL}/health")
        else:
            rumps.notification("Kagami", "API not running", "Start API first")

    def _open_metrics(self, _):
        """Open metrics endpoint."""
        if self.api_info.running:
            webbrowser.open(f"{API_URL}/metrics")
        else:
            rumps.notification("Kagami", "API not running", "Start API first")

    def _open_tensorboard(self, _):
        """Open TensorBoard (start if needed)."""
        # Check if TensorBoard is running
        tb_running = any(
            "tensorboard" in " ".join(p.info.get("cmdline") or [])
            for p in psutil.process_iter(["cmdline"])
        )

        if not tb_running:
            subprocess.Popen(
                ["tensorboard", "--logdir", str(CHECKPOINTS_DIR), "--port", "6006"],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                start_new_session=True,
            )
            time.sleep(2)

        webbrowser.open("http://localhost:6006")

    def _open_checkpoints(self, _):
        """Open checkpoints folder."""
        CHECKPOINTS_DIR.mkdir(parents=True, exist_ok=True)
        subprocess.run(["open", str(CHECKPOINTS_DIR)])

    def _open_logs(self, _):
        """Open logs folder."""
        LOG_DIR.mkdir(parents=True, exist_ok=True)
        subprocess.run(["open", str(LOG_DIR)])

    def _view_errors(self, _):
        """View recent errors from error log."""
        error_log = LOG_DIR / "kagami-api-error.log"
        if error_log.exists():
            subprocess.run(["open", "-a", "Console", str(error_log)])
        else:
            rumps.notification("Kagami", "No error log found", "")

    def _open_claude_md(self, _):
        """Open CLAUDE.md in editor."""
        claude_md = KAGAMI_ROOT / "CLAUDE.md"
        if claude_md.exists():
            subprocess.run(["open", str(claude_md)])

    def _open_home_docs(self, _):
        """Open home documentation."""
        home_docs = KAGAMI_ROOT / "docs" / "HOME_MENTAL_MODEL.md"
        if home_docs.exists():
            subprocess.run(["open", str(home_docs)])

    def _kill_training(self, _):
        """Force kill training process."""
        if self.training_info.pid:
            subprocess.run(["kill", "-9", str(self.training_info.pid)], capture_output=True)
            rumps.notification("鏡 Kagami", "Training Killed", "🛑")
        else:
            rumps.notification("Kagami", "No training process found", "")

    def _kill_api(self, _):
        """Force kill API process."""
        if self.api_info.pid:
            subprocess.run(["kill", "-9", str(self.api_info.pid)], capture_output=True)
            rumps.notification("鏡 Kagami", "API Killed", "🛑")
        else:
            rumps.notification("Kagami", "No API process found", "")

    def _kill_all_python(self, _):
        """Kill all Python processes (emergency)."""
        result = rumps.alert(
            "☠️ Kill All Python?",
            "This will terminate ALL Python processes.\nThis includes this status bar app.",
            ok="Kill All",
            cancel="Cancel",
        )
        if result == 1:
            subprocess.run(["pkill", "-9", "-f", "python"], capture_output=True)
            # Note: This will kill this app too


# =============================================================================
# MAIN
# =============================================================================

if __name__ == "__main__":
    KagamiStatusApp().run()
