from __future__ import annotations

from typing import Any

"""Local open-weights STT provider using faster-whisper (CTranslate2).

This provider performs batch transcription at finalize() time for simplicity
and reliability in initial integration. It expects client-side buffering of
short utterances (a few seconds). For streaming partials, a future edit can
switch to incremental decode windows.
"""
import asyncio
import logging
import os
import platform
import time

from kagami.core.di.container import register_service
from kagami.core.interfaces import STTProviderProtocol

from .base import BaseSTTProvider, STTSession

logger = logging.getLogger(__name__)


class FasterWhisperProvider(BaseSTTProvider):
    name = "faster_whisper"

    def __init__(
        self,
        model_size: str = "small",
        device: str | None = None,
        compute_type: str | None = None,
    ) -> None:
        # Allow environment overrides for performance tuning and Apple Silicon (Metal)
        # KAGAMI_STT_MODEL: tiny, base, small, medium, large-v2, etc.
        # KAGAMI_STT_DEVICE: cpu|metal|cuda
        # KAGAMI_STT_COMPUTE: int8|int8_float16|float16|float32 (ctranslate2 types)
        env_model = os.getenv("KAGAMI_STT_MODEL")
        # Prefer Metal on macOS when not explicitly set[Any]
        default_device = "metal" if platform.system().lower() == "darwin" else "cpu"
        env_device = os.getenv("KAGAMI_STT_DEVICE", default_device)
        # Favor float16 on GPU/Metal, int8 on CPU for latency/throughput
        default_compute = "float16" if env_device in ("metal", "cuda") else "int8"
        env_compute = os.getenv("KAGAMI_STT_COMPUTE", default_compute)

        self.model_size = env_model or model_size
        self.device = (device or env_device or "cpu").lower()
        self.compute_type = (compute_type or env_compute).lower()

        self._model: Any | None = None
        # Optional upgraded model for low-confidence second pass
        self._upgrade_model: Any | None = None
        try:
            self._upgrade_enabled = os.getenv("KAGAMI_STT_UPGRADE_ENABLED", "0").lower() in (
                "1",
                "true",
                "yes",
                "on",
            )
        except Exception:
            self._upgrade_enabled = False
        try:
            self._upgrade_model_size = str(os.getenv("KAGAMI_STT_UPGRADE_MODEL", "medium")).strip()
        except Exception:
            self._upgrade_model_size = "medium"
        # Heuristic triggers (env-tunable)
        try:
            self._upgrade_min_words = int(os.getenv("KAGAMI_STT_UPGRADE_MIN_WORDS", "0"))
        except Exception:
            self._upgrade_min_words = 0
        try:
            self._upgrade_min_chars = int(os.getenv("KAGAMI_STT_UPGRADE_MIN_CHARS", "0"))
        except Exception:
            self._upgrade_min_chars = 0
        # Streaming/partial decode state
        self._last_partial_emit_at: dict[str, float] = {}
        # Env-tunable partial emission interval (seconds)
        try:
            import os as _os

            self._min_partial_interval_s = float(
                _os.getenv("KAGAMI_STT_PARTIAL_INTERVAL_S", "0.20")
            )
        except Exception:
            self._min_partial_interval_s = 0.20

    async def initialize(self) -> None:
        try:
            pass
        except Exception as e:  # pragma: no cover - import error surfaced at runtime
            logger.error(f"faster-whisper not available: {e}")
            raise

        # Load model in a thread to avoid blocking event loop
        def _load() -> None:
            from faster_whisper import WhisperModel

            self._model = WhisperModel(
                self.model_size, device=self.device, compute_type=self.compute_type
            )

        await asyncio.to_thread(_load)
        logger.info(
            "FasterWhisperProvider initialized: %s (%s/%s)",
            self.model_size,
            self.device,
            self.compute_type,
        )

    async def finalize(self, session: STTSession) -> str:
        if self._model is None:
            await self.initialize()

        # Convert PCM16 bytes to float32 waveform using soundfile
        import io

        raw = bytes(session.buffer)
        if not raw:
            return ""

        # Build WAV header in-memory for simple decode via soundfile
        # 16-bit PCM, mono
        import struct

        num_channels = session.channels
        sample_rate = session.sample_rate
        bits_per_sample = 16
        byte_rate = sample_rate * num_channels * bits_per_sample // 8
        block_align = num_channels * bits_per_sample // 8
        subchunk2_size = len(raw)
        chunk_size = 36 + subchunk2_size

        wav_header = b"RIFF" + struct.pack("<I", chunk_size) + b"WAVE"
        wav_header += b"fmt " + struct.pack(
            "<IHHIIHH",
            16,
            1,
            num_channels,
            sample_rate,
            byte_rate,
            block_align,
            bits_per_sample,
        )
        wav_header += b"data" + struct.pack("<I", subchunk2_size)

        buf = io.BytesIO(wav_header + raw)

        import soundfile as sf

        waveform, sr = sf.read(buf, dtype="float32")
        if sr != sample_rate:
            logger.debug(
                "Resampling not implemented in provider; expected %s got %s",
                sample_rate,
                sr,
            )

        # Transcribe with faster-whisper (single-shot)
        def _transcribe_primary() -> tuple[str, list[Any], dict[str, Any] | None]:
            assert self._model is not None
            segments, info = self._model.transcribe(
                waveform,
                language=session.language,
                beam_size=1,
                vad_filter=True,
                no_speech_threshold=0.5,
                condition_on_previous_text=False,
            )
            text_parts: list[str] = []
            collected_segments = []
            try:
                for seg in segments:
                    collected_segments.append(seg)
                    try:
                        text_parts.append(getattr(seg, "text", ""))
                    except Exception:
                        continue
            except Exception:
                pass
            text = " ".join([t.strip() for t in text_parts if t and t.strip()])
            return text, collected_segments, (info if isinstance(info, dict) else None)

        primary_text, _segs, _info = await asyncio.to_thread(_transcribe_primary)

        # Optional: low-confidence upgrade pass using a larger model
        if self._upgrade_enabled:
            try:
                should_upgrade = False
                if self._upgrade_min_words > 0:
                    try:
                        num_words = len([w for w in primary_text.split() if w.strip()])
                    except Exception:
                        num_words = 0
                    if num_words < self._upgrade_min_words:
                        should_upgrade = True
                if not should_upgrade and self._upgrade_min_chars > 0:
                    if len(primary_text.strip()) < self._upgrade_min_chars:
                        should_upgrade = True

                # Prefer not to re-upgrade if we're already on a large model
                try:
                    base_sz = (self.model_size or "").lower()
                    if base_sz.startswith("large") or base_sz.startswith("medium"):
                        should_upgrade = False
                except Exception:
                    pass

                if should_upgrade:
                    # Load upgrade model lazily
                    def _load_upgrade() -> None:
                        if self._upgrade_model is None:
                            from faster_whisper import WhisperModel

                            self._upgrade_model = WhisperModel(
                                self._upgrade_model_size,
                                device=self.device,
                                compute_type=self.compute_type,
                            )

                    await asyncio.to_thread(_load_upgrade)

                    def _transcribe_upgrade() -> str:
                        assert self._upgrade_model is not None
                        segments2, _info2 = self._upgrade_model.transcribe(
                            waveform,
                            language=session.language,
                            beam_size=1,
                            vad_filter=True,
                            no_speech_threshold=0.5,
                            condition_on_previous_text=False,
                        )
                        parts2: list[str] = []
                        for seg in segments2:
                            try:
                                parts2.append(getattr(seg, "text", ""))
                            except Exception:
                                continue
                        return " ".join([t.strip() for t in parts2 if t and t.strip()])

                    upgraded_text = await asyncio.to_thread(_transcribe_upgrade)
                    # Use upgraded text if it appears strictly more informative
                    if len(upgraded_text.strip()) > len(primary_text.strip()):
                        try:
                            # Record metric (best-effort)
                            from kagami_observability.metrics import REGISTRY
                            from prometheus_client import Counter

                            try:
                                STT_UPGRADES = Counter(
                                    "kagami_stt_upgrades_total",
                                    "Total STT second-pass upgrades due to low-confidence",
                                    ["from", "to"],
                                    registry=REGISTRY,
                                )
                            except ValueError:
                                # Reuse existing collector
                                from typing import cast as _cast

                                STT_UPGRADES = _cast(
                                    Counter,
                                    getattr(
                                        REGISTRY,
                                        "_names_to_collectors",
                                        {},
                                    ).get("kagami_stt_upgrades_total"),
                                )
                            if STT_UPGRADES is not None:
                                STT_UPGRADES.labels(self.model_size, self._upgrade_model_size).inc()
                        except Exception:
                            pass
                        return upgraded_text.strip()
            except Exception:
                # Never fail due to upgrade path
                pass

        return primary_text.strip()

    async def get_partial(self, session: STTSession) -> str | None:
        """Return a best-effort partial transcript using a short trailing window.

        This uses a small decode window and VAD to produce low-latency partials.
        Emission is rate-limited to avoid flooding the client.
        """
        if self._model is None:
            # Defer model load to first finalize; no partials before ready
            return None

        # Rate-limit partial emissions per session
        now = time.time()
        last = self._last_partial_emit_at.get(session.session_id, 0.0)
        if now - last < self._min_partial_interval_s:
            return None

        raw = bytes(session.buffer)
        if not raw:
            return None

        # Use only the last N milliseconds to keep latency low
        # Env-tunable trailing window for partial decode (ms)
        try:
            import os as _os

            trailing_ms = int(_os.getenv("KAGAMI_STT_PARTIAL_WINDOW_MS", "800"))
        except Exception:
            trailing_ms = 800
        bytes_per_sample = 2  # pcm16
        bytes_per_second = session.sample_rate * session.channels * bytes_per_sample
        window_bytes = int(bytes_per_second * trailing_ms / 1000.0)
        window = raw[-window_bytes:]

        # Build minimal WAV header for decode via soundfile
        import io
        import struct

        num_channels = session.channels
        sample_rate = session.sample_rate
        bits_per_sample = 16
        byte_rate = sample_rate * num_channels * bits_per_sample // 8
        block_align = num_channels * bits_per_sample // 8
        subchunk2_size = len(window)
        if subchunk2_size <= 0:
            return None
        chunk_size = 36 + subchunk2_size
        wav_header = b"RIFF" + struct.pack("<I", chunk_size) + b"WAVE"
        wav_header += b"fmt " + struct.pack(
            "<IHHIIHH",
            16,
            1,
            num_channels,
            sample_rate,
            byte_rate,
            block_align,
            bits_per_sample,
        )
        wav_header += b"data" + struct.pack("<I", subchunk2_size)
        buf = io.BytesIO(wav_header + window)

        try:
            import soundfile as sf

            waveform, _sr = sf.read(buf, dtype="float32")
            if waveform is None or len(waveform) == 0:
                return None
        except Exception:
            return None

        # Small decode with vad_filter to get a rough partial.
        def _transcribe_partial() -> str:
            try:
                assert self._model is not None
                segments, _info = self._model.transcribe(
                    waveform,
                    language=session.language,
                    beam_size=1,
                    vad_filter=True,
                    no_speech_threshold=0.6,
                    condition_on_previous_text=False,
                )
                # Take the last non-empty segment as partial
                last_text = None
                for seg in segments:
                    if seg and getattr(seg, "text", None):
                        t = (seg.text or "").strip()
                        if t:
                            last_text = t
                return last_text or ""
            except Exception:
                return ""

        text = await asyncio.to_thread(_transcribe_partial)
        text = (text or "").strip()
        if not text:
            return None
        self._last_partial_emit_at[session.session_id] = now
        return text


# Register default STT provider for DI consumers
try:
    register_service(
        STTProviderProtocol,
        lambda: FasterWhisperProvider(),
        singleton=True,
    )
except ValueError:
    # Already registered elsewhere (tests or alternative provider)
    pass
