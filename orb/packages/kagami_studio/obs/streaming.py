"""OBS Streaming & Recording — Output configuration.

Provides streaming platform presets and recording settings:
- Platform-specific RTMP URLs
- Optimal bitrate/codec settings
- Recording format options

Usage:
    from kagami_studio.obs import OBSController, StreamSettings

    async with connect_obs() as obs:
        # Start streaming to Twitch
        settings = StreamSettings.twitch("your_stream_key")
        await obs.start_streaming()

        # Record with high quality
        rec_settings = RecordingSettings.high_quality()
        await obs.start_recording()
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum


class StreamingPlatform(str, Enum):
    """Streaming platform identifiers."""

    TWITCH = "twitch"
    YOUTUBE = "youtube"
    FACEBOOK = "facebook"
    INSTAGRAM = "instagram"
    TIKTOK = "tiktok"
    LINKEDIN = "linkedin"
    CUSTOM = "custom"


@dataclass
class StreamSettings:
    """Streaming configuration."""

    platform: StreamingPlatform
    server: str
    key: str

    # Video settings
    video_bitrate: int = 4500  # kbps
    video_encoder: str = "obs_x264"
    video_preset: str = "veryfast"
    keyframe_interval: int = 2  # seconds

    # Audio settings
    audio_bitrate: int = 160  # kbps
    audio_encoder: str = "aac"

    # Quality
    resolution: tuple[int, int] = (1920, 1080)
    fps: int = 30

    @classmethod
    def twitch(
        cls,
        stream_key: str,
        ingest: str = "auto",
        video_bitrate: int = 6000,
    ) -> StreamSettings:
        """Create Twitch streaming settings.

        Args:
            stream_key: Twitch stream key
            ingest: Ingest server ('auto' or specific like 'sea')
            video_bitrate: Video bitrate (Twitch max: 6000 for partners)
        """
        servers = {
            "auto": "rtmp://live.twitch.tv/app/",
            "sea": "rtmp://sea.contribute.live-video.net/app/",  # Seattle
            "sfo": "rtmp://sfo.contribute.live-video.net/app/",
            "lax": "rtmp://lax.contribute.live-video.net/app/",
            "nyc": "rtmp://nyc.contribute.live-video.net/app/",
        }

        return cls(
            platform=StreamingPlatform.TWITCH,
            server=servers.get(ingest, servers["auto"]),
            key=stream_key,
            video_bitrate=min(video_bitrate, 6000),
            keyframe_interval=2,  # Twitch requires 2s
        )

    @classmethod
    def youtube(
        cls,
        stream_key: str,
        resolution: str = "1080p60",
    ) -> StreamSettings:
        """Create YouTube streaming settings.

        Args:
            stream_key: YouTube stream key
            resolution: Target resolution ('720p', '1080p', '1080p60', '1440p', '4k')
        """
        # YouTube recommended settings
        settings = {
            "720p": (1280, 720, 30, 2500),
            "1080p": (1920, 1080, 30, 4500),
            "1080p60": (1920, 1080, 60, 6000),
            "1440p": (2560, 1440, 30, 9000),
            "1440p60": (2560, 1440, 60, 12000),
            "4k": (3840, 2160, 30, 20000),
            "4k60": (3840, 2160, 60, 30000),
        }

        w, h, fps, bitrate = settings.get(resolution, settings["1080p"])

        return cls(
            platform=StreamingPlatform.YOUTUBE,
            server="rtmp://a.rtmp.youtube.com/live2/",
            key=stream_key,
            video_bitrate=bitrate,
            resolution=(w, h),
            fps=fps,
            keyframe_interval=2,
        )

    @classmethod
    def facebook(
        cls,
        stream_key: str,
        resolution: str = "1080p",
    ) -> StreamSettings:
        """Create Facebook Live settings.

        Args:
            stream_key: Facebook stream key
            resolution: '720p' or '1080p'
        """
        w, h = (1920, 1080) if resolution == "1080p" else (1280, 720)
        bitrate = 4000 if resolution == "1080p" else 2500

        return cls(
            platform=StreamingPlatform.FACEBOOK,
            server="rtmps://live-api-s.facebook.com:443/rtmp/",
            key=stream_key,
            video_bitrate=bitrate,
            resolution=(w, h),
            fps=30,
        )

    @classmethod
    def custom_rtmp(
        cls,
        server: str,
        key: str = "",
        video_bitrate: int = 4500,
    ) -> StreamSettings:
        """Create custom RTMP settings.

        Args:
            server: RTMP server URL
            key: Stream key
            video_bitrate: Video bitrate
        """
        return cls(
            platform=StreamingPlatform.CUSTOM,
            server=server,
            key=key,
            video_bitrate=video_bitrate,
        )

    @classmethod
    def srt(
        cls,
        host: str,
        port: int = 9000,
        stream_id: str = "",
        latency: int = 120,
        passphrase: str = "",
    ) -> StreamSettings:
        """Create SRT streaming settings.

        SRT provides lower latency than RTMP.

        Args:
            host: SRT server host
            port: SRT port
            stream_id: Stream ID
            latency: Target latency in ms
            passphrase: Encryption passphrase
        """
        url = f"srt://{host}:{port}?latency={latency * 1000}"
        if stream_id:
            url += f"&streamid={stream_id}"
        if passphrase:
            url += f"&passphrase={passphrase}"

        return cls(
            platform=StreamingPlatform.CUSTOM,
            server=url,
            key="",
        )

    def to_obs_settings(self) -> dict:
        """Convert to OBS output settings."""
        return {
            "server": self.server,
            "key": self.key,
            "bitrate": self.video_bitrate,
            "preset": self.video_preset,
            "keyint_sec": self.keyframe_interval,
        }


class RecordingFormat(str, Enum):
    """Recording format options."""

    MP4 = "mp4"
    MKV = "mkv"
    FLV = "flv"
    MOV = "mov"
    TS = "ts"


@dataclass
class RecordingSettings:
    """Recording configuration."""

    format: RecordingFormat = RecordingFormat.MKV
    path: str = ""  # Empty = use OBS default

    # Video settings
    video_encoder: str = "obs_x264"
    video_bitrate: int = 10000  # kbps (higher than streaming)
    video_preset: str = "medium"
    crf: int = 18  # Quality (0-51, lower = better)
    use_cbr: bool = False  # Use CRF for variable bitrate

    # Audio settings
    audio_encoder: str = "aac"
    audio_bitrate: int = 320  # kbps

    # Quality
    resolution: tuple[int, int] = (1920, 1080)
    fps: int = 60

    @classmethod
    def high_quality(cls, format: RecordingFormat = RecordingFormat.MKV) -> RecordingSettings:
        """High quality recording preset.

        Uses CRF mode for optimal quality/size ratio.
        """
        return cls(
            format=format,
            video_encoder="obs_x264",
            crf=18,
            use_cbr=False,
            video_preset="slow",
            fps=60,
            audio_bitrate=320,
        )

    @classmethod
    def production(cls, format: RecordingFormat = RecordingFormat.MOV) -> RecordingSettings:
        """Production quality (highest quality, large files).

        Uses near-lossless CRF for editing.
        """
        return cls(
            format=format,
            video_encoder="obs_x264",
            crf=12,  # Near lossless
            use_cbr=False,
            video_preset="slow",
            fps=60,
            audio_bitrate=320,
        )

    @classmethod
    def fast(cls, format: RecordingFormat = RecordingFormat.MKV) -> RecordingSettings:
        """Fast recording with good quality.

        Lower CPU usage, slightly larger files.
        """
        return cls(
            format=format,
            video_encoder="obs_x264",
            crf=20,
            use_cbr=False,
            video_preset="ultrafast",
            fps=60,
            audio_bitrate=192,
        )

    @classmethod
    def hardware_nvenc(cls, format: RecordingFormat = RecordingFormat.MKV) -> RecordingSettings:
        """NVIDIA NVENC hardware encoding.

        Very low CPU usage, excellent quality.
        """
        return cls(
            format=format,
            video_encoder="nvenc",
            video_bitrate=25000,  # NVENC uses CBR
            use_cbr=True,
            video_preset="p5",  # Quality preset
            fps=60,
            audio_bitrate=320,
        )

    @classmethod
    def hardware_quicksync(cls, format: RecordingFormat = RecordingFormat.MKV) -> RecordingSettings:
        """Intel QuickSync hardware encoding."""
        return cls(
            format=format,
            video_encoder="qsv",
            video_bitrate=25000,
            use_cbr=True,
            video_preset="quality",
            fps=60,
            audio_bitrate=320,
        )

    @classmethod
    def hardware_videotoolbox(
        cls, format: RecordingFormat = RecordingFormat.MOV
    ) -> RecordingSettings:
        """Apple VideoToolbox hardware encoding (macOS).

        Uses Apple's hardware encoder for excellent efficiency.
        """
        return cls(
            format=format,
            video_encoder="apple_vt_h264_hw",
            video_bitrate=25000,
            use_cbr=True,
            fps=60,
            audio_bitrate=320,
        )

    @classmethod
    def replay_buffer(cls, duration_seconds: int = 30) -> RecordingSettings:
        """Settings for replay buffer.

        Keeps last N seconds in memory for instant replay.
        """
        return cls(
            format=RecordingFormat.MKV,
            video_encoder="obs_x264",
            crf=20,
            use_cbr=False,
            video_preset="veryfast",
            fps=60,
        )

    def to_obs_settings(self) -> dict:
        """Convert to OBS output settings."""
        settings = {
            "RecFormat": self.format.value,
            "VEncoder": self.video_encoder,
            "AEncoder": self.audio_encoder,
            "ABitrate": self.audio_bitrate,
        }

        if self.use_cbr:
            settings["VBitrate"] = self.video_bitrate
            settings["rate_control"] = "CBR"
        else:
            settings["crf"] = self.crf
            settings["rate_control"] = "CRF"

        if self.path:
            settings["RecFilePath"] = self.path

        return settings


@dataclass
class MultiStreamTarget:
    """Target for multi-streaming."""

    platform: StreamingPlatform
    server: str
    key: str
    enabled: bool = True

    @classmethod
    def twitch(cls, key: str) -> MultiStreamTarget:
        """Create Twitch target."""
        return cls(
            platform=StreamingPlatform.TWITCH,
            server="rtmp://live.twitch.tv/app/",
            key=key,
        )

    @classmethod
    def youtube(cls, key: str) -> MultiStreamTarget:
        """Create YouTube target."""
        return cls(
            platform=StreamingPlatform.YOUTUBE,
            server="rtmp://a.rtmp.youtube.com/live2/",
            key=key,
        )

    @classmethod
    def facebook(cls, key: str) -> MultiStreamTarget:
        """Create Facebook target."""
        return cls(
            platform=StreamingPlatform.FACEBOOK,
            server="rtmps://live-api-s.facebook.com:443/rtmp/",
            key=key,
        )


@dataclass
class MultiStreamSettings:
    """Multi-platform streaming configuration."""

    targets: list[MultiStreamTarget]
    video_bitrate: int = 6000
    resolution: tuple[int, int] = (1920, 1080)
    fps: int = 30

    def add_target(
        self,
        platform: StreamingPlatform,
        server: str,
        key: str,
    ) -> None:
        """Add streaming target."""
        self.targets.append(
            MultiStreamTarget(
                platform=platform,
                server=server,
                key=key,
            )
        )

    @classmethod
    def to_twitch_and_youtube(
        cls,
        twitch_key: str,
        youtube_key: str,
    ) -> MultiStreamSettings:
        """Common setup: Twitch + YouTube simultaneously."""
        return cls(
            targets=[
                MultiStreamTarget.twitch(twitch_key),
                MultiStreamTarget.youtube(youtube_key),
            ],
            video_bitrate=6000,  # Stay within Twitch limits
        )
