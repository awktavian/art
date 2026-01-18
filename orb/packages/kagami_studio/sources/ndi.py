"""NDI Source — Network Device Interface input.

NDI (Network Device Interface) is a standard for video production
over IP networks. This source allows receiving NDI streams from
professional video equipment, other computers, or applications.

Requirements:
    pip install ndi-python

Usage:
    source = NDISource(source_id="ndi_1", name="Camera A", ndi_name="CAMERA-A")
    await source.start()
    frame = await source.get_frame()
"""

from __future__ import annotations

import asyncio
import logging

import numpy as np

from kagami_studio.sources.base import Source, SourceState, SourceType

logger = logging.getLogger(__name__)


class NDISource(Source):
    """NDI network video source.

    Receives video from NDI-enabled devices and software:
    - NDI cameras (PTZOptics, BirdDog, etc.)
    - OBS Studio, vMix, Wirecast
    - NewTek TriCaster
    - Any NDI-enabled application
    """

    def __init__(
        self,
        source_id: str,
        name: str,
        ndi_name: str | None = None,
        ip_address: str | None = None,
    ):
        """Initialize NDI source.

        Args:
            source_id: Unique source identifier
            name: Display name
            ndi_name: NDI source name to connect to
            ip_address: Specific IP to connect to (optional)
        """
        super().__init__(source_id, name, SourceType.NDI)
        self.ndi_name = ndi_name
        self.ip_address = ip_address
        self._recv = None
        self._finder = None
        self._frame = None
        self._task = None
        self._ndi_lib = None

    async def start(self) -> None:
        """Start receiving NDI stream."""
        self.state = SourceState.STARTING

        try:
            import NDIlib as ndi

            self._ndi_lib = ndi

            # Initialize NDI
            if not ndi.initialize():
                raise RuntimeError("Failed to initialize NDI")

            # Create finder to discover sources
            self._finder = ndi.find_create_v2()
            if not self._finder:
                raise RuntimeError("Failed to create NDI finder")

            # Find sources
            sources = []
            for _ in range(10):  # Wait up to 5 seconds
                ndi.find_wait_for_sources(self._finder, 500)
                sources = ndi.find_get_current_sources(self._finder)
                if sources:
                    break

            if not sources:
                logger.warning("No NDI sources found on network")
                self.state = SourceState.ERROR
                return

            # Find matching source
            target_source = None
            for src in sources:
                if self.ndi_name and self.ndi_name in src.ndi_name:
                    target_source = src
                    break
                if self.ip_address and self.ip_address in src.url_address:
                    target_source = src
                    break

            if not target_source:
                # Use first available
                target_source = sources[0]
                logger.info(f"Using first NDI source: {target_source.ndi_name}")

            # Create receiver
            recv_settings = ndi.RecvCreateV3()
            recv_settings.source_to_connect_to = target_source
            recv_settings.color_format = ndi.RECV_COLOR_FORMAT_BGRX_BGRA

            self._recv = ndi.recv_create_v3(recv_settings)
            if not self._recv:
                raise RuntimeError("Failed to create NDI receiver")

            # Get video format
            self._fps = 30.0  # Will be updated from actual stream
            self._width = 1920
            self._height = 1080

            # Start receive loop
            self._task = asyncio.create_task(self._receive_loop())
            self.state = SourceState.ACTIVE

            logger.info(f"NDI source connected: {target_source.ndi_name}")

        except ImportError:
            logger.error("NDI not available: pip install ndi-python")
            self.state = SourceState.ERROR
        except Exception as e:
            logger.error(f"NDI source failed: {e}")
            self.state = SourceState.ERROR

    async def stop(self) -> None:
        """Stop receiving NDI stream."""
        self.state = SourceState.INACTIVE

        if self._task:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass

        if self._recv and self._ndi_lib:
            self._ndi_lib.recv_destroy(self._recv)
            self._recv = None

        if self._finder and self._ndi_lib:
            self._ndi_lib.find_destroy(self._finder)
            self._finder = None

        logger.info("NDI source stopped")

    async def _receive_loop(self) -> None:
        """Continuous receive loop."""
        ndi = self._ndi_lib

        while self.state == SourceState.ACTIVE:
            try:
                # Receive frame (non-blocking)
                frame_type, video, _audio, _metadata = ndi.recv_capture_v2(
                    self._recv,
                    100,  # 100ms timeout
                )

                if frame_type == ndi.FRAME_TYPE_VIDEO:
                    # Convert to numpy
                    self._frame = np.copy(video.data)
                    self._width = video.xres
                    self._height = video.yres

                    # Free NDI frame
                    ndi.recv_free_video_v2(self._recv, video)

            except Exception as e:
                logger.error(f"NDI receive error: {e}")

            await asyncio.sleep(0.001)

    async def get_frame(self) -> np.ndarray | None:
        """Get current frame."""
        return self._frame

    @staticmethod
    def list_sources() -> list[dict]:
        """List available NDI sources on network.

        Returns:
            List of {name, ip} dicts
        """
        try:
            import NDIlib as ndi

            if not ndi.initialize():
                return []

            finder = ndi.find_create_v2()
            if not finder:
                return []

            # Wait for sources
            ndi.find_wait_for_sources(finder, 2000)
            sources = ndi.find_get_current_sources(finder)

            result = [{"name": src.ndi_name, "ip": src.url_address} for src in sources]

            ndi.find_destroy(finder)
            return result

        except ImportError:
            return []
