"""Orchestra Visualizer — Audio-Reactive Genesis Rendering.

Creates beautiful real-time visualizations of orchestral music, with each
instrument section spatially positioned and visually reactive to its
frequency content.

Architecture:
    Audio File → FFT Analysis → Frequency Bands → Instrument Mapping
                                      ↓
                    ┌─────────────────────────────────────┐
                    │     Genesis 3D Scene                │
                    │                                     │
                    │   🎻 Strings (200-800Hz)            │
                    │        Flowing ribbons, warm glow   │
                    │                                     │
                    │   🎺 Brass (500-2000Hz)             │
                    │        Pulsing orbs, golden light   │
                    │                                     │
                    │   🪈 Woodwinds (400-4000Hz)         │
                    │        Rising particles, ethereal   │
                    │                                     │
                    │   🥁 Percussion (20-200Hz + 2-8kHz) │
                    │        Impact rings, sharp flashes  │
                    │                                     │
                    └─────────────────────────────────────┘
                                      ↓
                              Video Output (synced)

Colony: Full Fano Collaboration
Created: January 4, 2026
"""

from __future__ import annotations

import asyncio
import logging
import math
from collections.abc import Callable
from dataclasses import dataclass
from enum import Enum
from pathlib import Path
from typing import TYPE_CHECKING

import numpy as np

if TYPE_CHECKING:
    pass

logger = logging.getLogger(__name__)


# =============================================================================
# Configuration
# =============================================================================

SAMPLE_RATE = 48000
FFT_SIZE = 2048
HOP_SIZE = 512  # ~93 FPS at 48kHz


class OrchestraSection(Enum):
    """Visual sections of the orchestra."""

    STRINGS = "strings"
    WOODWINDS = "woodwinds"
    BRASS = "brass"
    PERCUSSION = "percussion"
    HARP = "harp"


@dataclass
class FrequencyBand:
    """Frequency band for audio analysis."""

    name: str
    low_hz: float
    high_hz: float
    section: OrchestraSection
    smoothing: float = 0.3  # Temporal smoothing (0=none, 1=full)


# Frequency bands mapped to orchestra sections
# Based on typical instrument fundamental frequencies and overtones
ORCHESTRA_FREQUENCY_BANDS: list[FrequencyBand] = [
    # STRINGS: Rich harmonics from 200Hz to 2kHz
    FrequencyBand("strings_low", 80, 250, OrchestraSection.STRINGS, 0.4),  # Celli/Basses
    FrequencyBand("strings_mid", 250, 800, OrchestraSection.STRINGS, 0.35),  # Violas
    FrequencyBand("strings_high", 800, 2000, OrchestraSection.STRINGS, 0.3),  # Violins
    # WOODWINDS: Clear tones 400Hz-4kHz
    FrequencyBand("woodwinds_low", 200, 500, OrchestraSection.WOODWINDS, 0.35),  # Bassoons
    FrequencyBand("woodwinds_mid", 500, 1500, OrchestraSection.WOODWINDS, 0.3),  # Clarinets/Oboes
    FrequencyBand("woodwinds_high", 1500, 4000, OrchestraSection.WOODWINDS, 0.25),  # Flutes/Piccolo
    # BRASS: Powerful 300Hz-3kHz
    FrequencyBand("brass_low", 100, 400, OrchestraSection.BRASS, 0.4),  # Tuba/Trombones
    FrequencyBand("brass_mid", 400, 1000, OrchestraSection.BRASS, 0.35),  # Horns
    FrequencyBand("brass_high", 1000, 3000, OrchestraSection.BRASS, 0.3),  # Trumpets
    # PERCUSSION: Attack transients + fundamentals
    FrequencyBand("percussion_sub", 20, 100, OrchestraSection.PERCUSSION, 0.5),  # Bass drum
    FrequencyBand("percussion_low", 100, 300, OrchestraSection.PERCUSSION, 0.45),  # Timpani
    FrequencyBand(
        "percussion_high",
        4000,
        12000,
        OrchestraSection.PERCUSSION,
        0.2,
    ),  # Cymbals/transients
    # HARP: Distinct plucked character
    FrequencyBand("harp", 100, 3000, OrchestraSection.HARP, 0.3),
]


@dataclass
class SectionVisualConfig:
    """Visual configuration for an orchestra section."""

    # Position (azimuth, elevation, distance from center)
    azimuth: float = 0.0  # Degrees, -90 to 90
    elevation: float = 0.0  # Degrees, 0 to 30
    distance: float = 5.0  # Meters

    # Visual style
    color: tuple[float, float, float] = (1.0, 1.0, 1.0)  # RGB 0-1
    emissive_intensity: float = 0.5
    particle_count: int = 100
    particle_size: float = 0.05

    # Animation
    pulse_speed: float = 1.0
    wave_amplitude: float = 0.2
    rotation_speed: float = 0.1


# Default visual configs for each section
SECTION_VISUALS: dict[OrchestraSection, SectionVisualConfig] = {
    OrchestraSection.STRINGS: SectionVisualConfig(
        azimuth=-30,
        elevation=2,
        distance=5,
        color=(0.8, 0.3, 0.2),  # Warm amber/red
        emissive_intensity=0.6,
        particle_count=200,
        particle_size=0.03,
        pulse_speed=0.8,
        wave_amplitude=0.3,
    ),
    OrchestraSection.WOODWINDS: SectionVisualConfig(
        azimuth=0,
        elevation=12,
        distance=7,
        color=(0.3, 0.7, 0.5),  # Forest green
        emissive_intensity=0.5,
        particle_count=150,
        particle_size=0.02,
        pulse_speed=1.2,
        wave_amplitude=0.4,
    ),
    OrchestraSection.BRASS: SectionVisualConfig(
        azimuth=20,
        elevation=18,
        distance=9,
        color=(0.9, 0.7, 0.2),  # Golden
        emissive_intensity=0.8,
        particle_count=100,
        particle_size=0.05,
        pulse_speed=0.6,
        wave_amplitude=0.2,
    ),
    OrchestraSection.PERCUSSION: SectionVisualConfig(
        azimuth=-20,
        elevation=20,
        distance=10,
        color=(0.9, 0.9, 1.0),  # Silver/white
        emissive_intensity=1.0,
        particle_count=50,
        particle_size=0.08,
        pulse_speed=2.0,
        wave_amplitude=0.5,
    ),
    OrchestraSection.HARP: SectionVisualConfig(
        azimuth=-55,
        elevation=5,
        distance=5.5,
        color=(0.6, 0.4, 0.8),  # Purple/violet
        emissive_intensity=0.4,
        particle_count=80,
        particle_size=0.02,
        pulse_speed=1.5,
        wave_amplitude=0.35,
    ),
}


# =============================================================================
# Audio Analysis
# =============================================================================


@dataclass
class AudioAnalysisFrame:
    """Analysis results for a single audio frame."""

    timestamp: float
    section_energies: dict[OrchestraSection, float]  # 0-1 normalized
    band_energies: dict[str, float]  # Per-band energies
    overall_energy: float
    spectral_centroid: float  # Brightness indicator
    onset_detected: bool  # Transient detection


class OrchestraAudioAnalyzer:
    """Real-time audio analysis optimized for orchestral content.

    Uses FFT to extract frequency bands corresponding to different
    instrument sections, with temporal smoothing for smooth visuals.
    """

    def __init__(
        self,
        sample_rate: int = SAMPLE_RATE,
        fft_size: int = FFT_SIZE,
        hop_size: int = HOP_SIZE,
    ) -> None:
        self.sample_rate = sample_rate
        self.fft_size = fft_size
        self.hop_size = hop_size

        # Pre-compute frequency bins
        self.freq_bins = np.fft.rfftfreq(fft_size, 1 / sample_rate)

        # Pre-compute band indices
        self.band_indices: dict[str, tuple[int, int]] = {}
        for band in ORCHESTRA_FREQUENCY_BANDS:
            low_idx = np.searchsorted(self.freq_bins, band.low_hz)
            high_idx = np.searchsorted(self.freq_bins, band.high_hz)
            self.band_indices[band.name] = (low_idx, high_idx)

        # Smoothed energies (for temporal smoothing)
        self._smoothed_bands: dict[str, float] = {b.name: 0.0 for b in ORCHESTRA_FREQUENCY_BANDS}
        self._smoothed_sections: dict[OrchestraSection, float] = dict.fromkeys(
            OrchestraSection,
            0.0,
        )

        # Onset detection state
        self._prev_energy = 0.0
        self._onset_threshold = 0.3

        # Hann window for FFT
        self._window = np.hanning(fft_size)

        logger.info(f"Audio analyzer initialized: {sample_rate}Hz, FFT={fft_size}")

    def analyze_frame(self, audio_frame: np.ndarray, timestamp: float) -> AudioAnalysisFrame:
        """Analyze a single audio frame.

        Args:
            audio_frame: Audio samples (mono, length should match fft_size)
            timestamp: Frame timestamp in seconds

        Returns:
            AudioAnalysisFrame with analysis results
        """
        # Ensure correct length
        if len(audio_frame) < self.fft_size:
            audio_frame = np.pad(audio_frame, (0, self.fft_size - len(audio_frame)))
        elif len(audio_frame) > self.fft_size:
            audio_frame = audio_frame[: self.fft_size]

        # Apply window and compute FFT
        windowed = audio_frame * self._window
        spectrum = np.abs(np.fft.rfft(windowed))

        # Convert to dB (with floor to avoid log(0))
        spectrum_db = 20 * np.log10(spectrum + 1e-10)

        # Normalize to 0-1 range (assuming -80dB to 0dB range)
        spectrum_norm = np.clip((spectrum_db + 80) / 80, 0, 1)

        # Compute band energies
        band_energies: dict[str, float] = {}
        for band in ORCHESTRA_FREQUENCY_BANDS:
            low_idx, high_idx = self.band_indices[band.name]
            band_energy = np.mean(spectrum_norm[low_idx:high_idx]) if high_idx > low_idx else 0.0

            # Apply temporal smoothing
            smoothing = band.smoothing
            smoothed = self._smoothed_bands[band.name] * smoothing + band_energy * (1 - smoothing)
            self._smoothed_bands[band.name] = smoothed
            band_energies[band.name] = smoothed

        # Aggregate into section energies
        section_energies: dict[OrchestraSection, float] = dict.fromkeys(OrchestraSection, 0.0)
        section_counts: dict[OrchestraSection, int] = dict.fromkeys(OrchestraSection, 0)

        for band in ORCHESTRA_FREQUENCY_BANDS:
            section_energies[band.section] += band_energies[band.name]
            section_counts[band.section] += 1

        # Average per section
        for section in OrchestraSection:
            if section_counts[section] > 0:
                section_energies[section] /= section_counts[section]

            # Apply section-level smoothing
            smoothed = self._smoothed_sections[section] * 0.2 + section_energies[section] * 0.8
            self._smoothed_sections[section] = smoothed
            section_energies[section] = smoothed

        # Overall energy
        overall_energy = np.mean(spectrum_norm)

        # Spectral centroid (brightness)
        if np.sum(spectrum) > 0:
            spectral_centroid = np.sum(self.freq_bins * spectrum) / np.sum(spectrum)
        else:
            spectral_centroid = 0.0

        # Onset detection (simple energy flux)
        energy_flux = overall_energy - self._prev_energy
        onset_detected = energy_flux > self._onset_threshold
        self._prev_energy = overall_energy

        return AudioAnalysisFrame(
            timestamp=timestamp,
            section_energies=section_energies,
            band_energies=band_energies,
            overall_energy=overall_energy,
            spectral_centroid=spectral_centroid,
            onset_detected=onset_detected,
        )

    def analyze_file(
        self,
        audio_path: Path,
        progress_callback: Callable[[float], None] | None = None,
    ) -> list[AudioAnalysisFrame]:
        """Analyze entire audio file.

        Args:
            audio_path: Path to audio file
            progress_callback: Optional callback(0-1) for progress

        Returns:
            List of analysis frames
        """
        import soundfile as sf

        audio, sr = sf.read(str(audio_path))

        # Convert to mono if stereo
        if len(audio.shape) > 1:
            audio = np.mean(audio, axis=1)

        # Resample if needed
        if sr != self.sample_rate:
            from scipy import signal

            num_samples = int(len(audio) * self.sample_rate / sr)
            audio = signal.resample(audio, num_samples)

        # Analyze frame by frame
        frames: list[AudioAnalysisFrame] = []
        num_frames = (len(audio) - self.fft_size) // self.hop_size + 1

        for i in range(num_frames):
            start = i * self.hop_size
            end = start + self.fft_size
            frame_audio = audio[start:end]
            timestamp = start / self.sample_rate

            frame = self.analyze_frame(frame_audio, timestamp)
            frames.append(frame)

            if progress_callback and i % 100 == 0:
                progress_callback(i / num_frames)

        if progress_callback:
            progress_callback(1.0)

        logger.info(f"Analyzed {len(frames)} frames from {audio_path}")
        return frames


# =============================================================================
# Visual Element Generation
# =============================================================================


@dataclass
class VisualElement:
    """A visual element in the scene."""

    name: str
    position: tuple[float, float, float]
    scale: tuple[float, float, float]
    color: tuple[float, float, float]
    emissive: float
    rotation: tuple[float, float, float]
    element_type: str  # "sphere", "ribbon", "particles", "ring"


@dataclass
class VisualizationFrame:
    """Complete visualization state for one frame."""

    timestamp: float
    elements: list[VisualElement]
    camera_position: tuple[float, float, float]
    camera_lookat: tuple[float, float, float]
    background_color: tuple[float, float, float]
    ambient_intensity: float


class OrchestraVisualizationGenerator:
    """Generates visual elements from audio analysis.

    Creates a 3D scene where each orchestra section has visual elements
    that respond to the audio analysis of their frequency bands.

    Visual Language:
    - STRINGS: Flowing ribbons that breathe with the music
    - WOODWINDS: Rising particles like forest sprites
    - BRASS: Pulsing golden orbs with power
    - PERCUSSION: Impact rings and sharp flashes
    - HARP: Cascading arpeggiated lights
    """

    def __init__(self) -> None:
        self._phase = 0.0  # Animation phase
        self._onset_flash = 0.0  # Flash on transients

    def _section_position(self, section: OrchestraSection) -> tuple[float, float, float]:
        """Convert section config to 3D position."""
        config = SECTION_VISUALS[section]
        az_rad = math.radians(config.azimuth)
        el_rad = math.radians(config.elevation)

        x = config.distance * math.cos(el_rad) * math.sin(az_rad)
        y = config.distance * math.cos(el_rad) * math.cos(az_rad)
        z = config.distance * math.sin(el_rad)

        return (x, y, z)

    def generate_frame(
        self,
        analysis: AudioAnalysisFrame,
        frame_idx: int,
        fps: float = 30.0,
    ) -> VisualizationFrame:
        """Generate visualization frame from audio analysis.

        Args:
            analysis: Audio analysis for this frame
            frame_idx: Frame index
            fps: Frames per second

        Returns:
            VisualizationFrame with visual elements
        """
        dt = 1.0 / fps
        self._phase += dt

        # Update onset flash decay
        if analysis.onset_detected:
            self._onset_flash = 1.0
        else:
            self._onset_flash *= 0.85

        elements: list[VisualElement] = []

        # Generate visuals for each section
        for section in OrchestraSection:
            energy = analysis.section_energies.get(section, 0.0)
            config = SECTION_VISUALS[section]
            base_pos = self._section_position(section)

            # Section-specific visual generation
            if section == OrchestraSection.STRINGS:
                elements.extend(
                    self._generate_strings_visuals(
                        base_pos,
                        energy,
                        config,
                        self._phase,
                    ),
                )
            elif section == OrchestraSection.WOODWINDS:
                elements.extend(
                    self._generate_woodwinds_visuals(
                        base_pos,
                        energy,
                        config,
                        self._phase,
                    ),
                )
            elif section == OrchestraSection.BRASS:
                elements.extend(
                    self._generate_brass_visuals(
                        base_pos,
                        energy,
                        config,
                        self._phase,
                    ),
                )
            elif section == OrchestraSection.PERCUSSION:
                elements.extend(
                    self._generate_percussion_visuals(
                        base_pos,
                        energy,
                        config,
                        self._phase,
                        analysis.onset_detected,
                    ),
                )
            elif section == OrchestraSection.HARP:
                elements.extend(
                    self._generate_harp_visuals(
                        base_pos,
                        energy,
                        config,
                        self._phase,
                    ),
                )

        # Camera orbit based on spectral centroid (brightness = upward movement)
        brightness = min(analysis.spectral_centroid / 4000, 1.0)  # Normalize
        cam_height = 2 + brightness * 1.5
        cam_angle = self._phase * 0.05  # Slow orbit
        cam_radius = 12 + (1 - analysis.overall_energy) * 3  # Pull back on quiet parts

        camera_position = (
            cam_radius * math.sin(cam_angle),
            cam_radius * math.cos(cam_angle),
            cam_height,
        )
        camera_lookat = (0.0, 0.0, 1.0)

        # Background shifts with overall energy
        bg_brightness = 0.02 + analysis.overall_energy * 0.03
        background_color = (bg_brightness * 0.8, bg_brightness * 0.85, bg_brightness * 1.0)

        # Ambient increases on transients
        ambient = 0.1 + self._onset_flash * 0.2

        return VisualizationFrame(
            timestamp=analysis.timestamp,
            elements=elements,
            camera_position=camera_position,
            camera_lookat=camera_lookat,
            background_color=background_color,
            ambient_intensity=ambient,
        )

    def _generate_strings_visuals(
        self,
        base_pos: tuple[float, float, float],
        energy: float,
        config: SectionVisualConfig,
        phase: float,
    ) -> list[VisualElement]:
        """Generate flowing ribbon visuals for strings."""
        elements = []

        # Create flowing ribbon segments
        num_ribbons = 8
        for i in range(num_ribbons):
            ribbon_phase = phase * config.pulse_speed + i * 0.3
            wave = math.sin(ribbon_phase) * config.wave_amplitude * energy

            # Position varies along the string section arc
            angle = (i / num_ribbons - 0.5) * math.pi * 0.5
            offset_x = math.sin(angle) * 0.8
            offset_z = wave + (i / num_ribbons) * 0.5

            pos = (
                base_pos[0] + offset_x,
                base_pos[1],
                base_pos[2] + offset_z,
            )

            # Scale pulses with energy
            scale_factor = 0.5 + energy * 1.0
            scale = (0.1 * scale_factor, 0.4 * scale_factor, 0.05)

            # Color intensity with energy
            color = tuple(c * (0.5 + energy * 0.5) for c in config.color)

            elements.append(
                VisualElement(
                    name=f"strings_ribbon_{i}",
                    position=pos,
                    scale=scale,
                    color=color,  # type: ignore
                    emissive=config.emissive_intensity * energy,
                    rotation=(ribbon_phase * 0.2, 0, angle),
                    element_type="ribbon",
                ),
            )

        return elements

    def _generate_woodwinds_visuals(
        self,
        base_pos: tuple[float, float, float],
        energy: float,
        config: SectionVisualConfig,
        phase: float,
    ) -> list[VisualElement]:
        """Generate rising particle visuals for woodwinds."""
        elements = []

        # Rising particles that float upward
        num_particles = int(config.particle_count * energy)
        for i in range(min(num_particles, 30)):  # Cap for performance
            particle_phase = (phase * config.pulse_speed + i * 0.1) % (2 * math.pi)

            # Spiral upward motion
            height = (particle_phase / (2 * math.pi)) * 2  # 0-2 meter rise
            spiral_radius = 0.3 + energy * 0.2
            angle = i * 0.5 + phase * 0.3

            pos = (
                base_pos[0] + spiral_radius * math.cos(angle),
                base_pos[1] + spiral_radius * math.sin(angle),
                base_pos[2] + height,
            )

            # Fade out as they rise
            alpha = 1 - (height / 2)
            size = config.particle_size * (0.5 + energy * 0.5) * alpha

            elements.append(
                VisualElement(
                    name=f"woodwinds_particle_{i}",
                    position=pos,
                    scale=(size, size, size),
                    color=config.color,
                    emissive=config.emissive_intensity * energy * alpha,
                    rotation=(0, 0, 0),
                    element_type="sphere",
                ),
            )

        return elements

    def _generate_brass_visuals(
        self,
        base_pos: tuple[float, float, float],
        energy: float,
        config: SectionVisualConfig,
        phase: float,
    ) -> list[VisualElement]:
        """Generate pulsing orb visuals for brass."""
        elements = []

        # Central pulsing orb
        pulse = 0.5 + 0.5 * math.sin(phase * config.pulse_speed * 3)
        orb_scale = (0.3 + energy * 0.4) * pulse

        elements.append(
            VisualElement(
                name="brass_orb",
                position=base_pos,
                scale=(orb_scale, orb_scale, orb_scale),
                color=config.color,
                emissive=config.emissive_intensity * energy * pulse,
                rotation=(phase * 0.1, phase * 0.15, 0),
                element_type="sphere",
            ),
        )

        # Radiating rays on high energy
        if energy > 0.4:
            num_rays = 6
            for i in range(num_rays):
                ray_angle = (i / num_rays) * 2 * math.pi + phase * config.rotation_speed
                ray_length = 0.3 + energy * 0.5
                ray_pos = (
                    base_pos[0] + math.cos(ray_angle) * ray_length * 0.5,
                    base_pos[1] + math.sin(ray_angle) * ray_length * 0.5,
                    base_pos[2],
                )

                elements.append(
                    VisualElement(
                        name=f"brass_ray_{i}",
                        position=ray_pos,
                        scale=(0.02, ray_length, 0.02),
                        color=config.color,
                        emissive=config.emissive_intensity * energy * 0.5,
                        rotation=(0, 0, ray_angle),
                        element_type="ribbon",
                    ),
                )

        return elements

    def _generate_percussion_visuals(
        self,
        base_pos: tuple[float, float, float],
        energy: float,
        config: SectionVisualConfig,
        phase: float,
        onset: bool,
    ) -> list[VisualElement]:
        """Generate impact ring visuals for percussion."""
        elements = []

        # Impact rings that expand outward
        if onset or energy > 0.6:
            ring_phase = (phase * 2) % 1
            ring_radius = 0.1 + ring_phase * 1.5
            ring_alpha = 1 - ring_phase

            elements.append(
                VisualElement(
                    name="percussion_ring",
                    position=base_pos,
                    scale=(ring_radius, ring_radius, 0.02),
                    color=config.color,
                    emissive=config.emissive_intensity * ring_alpha * energy,
                    rotation=(0, 0, 0),
                    element_type="ring",
                ),
            )

        # Central impact point
        impact_scale = 0.1 + energy * 0.3
        elements.append(
            VisualElement(
                name="percussion_core",
                position=base_pos,
                scale=(impact_scale, impact_scale, impact_scale),
                color=config.color,
                emissive=config.emissive_intensity * energy,
                rotation=(0, 0, 0),
                element_type="sphere",
            ),
        )

        return elements

    def _generate_harp_visuals(
        self,
        base_pos: tuple[float, float, float],
        energy: float,
        config: SectionVisualConfig,
        phase: float,
    ) -> list[VisualElement]:
        """Generate cascading light visuals for harp."""
        elements = []

        # Cascading strings of light
        num_strings = 12
        for i in range(num_strings):
            string_phase = phase * config.pulse_speed + i * 0.2
            string_active = math.sin(string_phase) > 0.3

            if string_active and energy > 0.1:
                string_height = 0.8 + energy * 0.4
                string_x = (i / num_strings - 0.5) * 0.6

                pos = (
                    base_pos[0] + string_x,
                    base_pos[1],
                    base_pos[2] + string_height * 0.5,
                )

                brightness = 0.5 + 0.5 * math.sin(string_phase * 2)

                elements.append(
                    VisualElement(
                        name=f"harp_string_{i}",
                        position=pos,
                        scale=(0.01, 0.01, string_height),
                        color=config.color,
                        emissive=config.emissive_intensity * energy * brightness,
                        rotation=(0, 0, 0),
                        element_type="ribbon",
                    ),
                )

        return elements


# =============================================================================
# Main Visualization Pipeline
# =============================================================================


@dataclass
class VisualizationConfig:
    """Configuration for the visualization pipeline."""

    output_width: int = 1920
    output_height: int = 1080
    fps: float = 30.0
    output_format: str = "mp4"
    quality: str = "high"  # "preview", "high", "ultra"

    # Audio sync
    audio_lookahead_frames: int = 2  # Pre-analyze for smoother visuals

    # Visual style
    bloom_intensity: float = 0.3
    motion_blur: float = 0.1


class OrchestraVisualizer:
    """Main orchestrator for audio-reactive visualization.

    Usage:
        visualizer = OrchestraVisualizer()
        await visualizer.create_visualization(
            audio_path=Path("orchestra.wav"),
            output_path=Path("visualization.mp4"),
        )
    """

    def __init__(self, config: VisualizationConfig | None = None) -> None:
        self.config = config or VisualizationConfig()
        self.analyzer = OrchestraAudioAnalyzer()
        self.generator = OrchestraVisualizationGenerator()

    async def create_visualization(
        self,
        audio_path: Path,
        output_path: Path,
        progress_callback: Callable[[str, float], None] | None = None,
    ) -> Path:
        """Create complete visualization video from audio file.

        Args:
            audio_path: Input orchestral audio file
            output_path: Output video path
            progress_callback: Optional callback(stage_name, 0-1)

        Returns:
            Path to output video
        """
        logger.info(f"🎬 Creating orchestra visualization: {audio_path}")

        # Stage 1: Analyze audio
        if progress_callback:
            progress_callback("Analyzing audio", 0.0)

        analysis_frames = self.analyzer.analyze_file(
            audio_path,
            progress_callback=lambda p: progress_callback("Analyzing audio", p)
            if progress_callback
            else None,
        )

        # Stage 2: Generate visualization frames
        if progress_callback:
            progress_callback("Generating visuals", 0.0)

        vis_frames: list[VisualizationFrame] = []
        for i, analysis in enumerate(analysis_frames):
            frame = self.generator.generate_frame(
                analysis,
                frame_idx=i,
                fps=self.config.fps,
            )
            vis_frames.append(frame)

            if progress_callback and i % 50 == 0:
                progress_callback("Generating visuals", i / len(analysis_frames))

        # Stage 3: Render with Genesis
        if progress_callback:
            progress_callback("Rendering", 0.0)

        rendered_path = await self._render_genesis(
            vis_frames,
            output_path,
            progress_callback=lambda p: progress_callback("Rendering", p)
            if progress_callback
            else None,
        )

        # Stage 4: Combine with audio
        if progress_callback:
            progress_callback("Combining audio", 0.0)

        final_path = await self._combine_audio_video(
            rendered_path,
            audio_path,
            output_path,
        )

        logger.info(f"✓ Visualization complete: {final_path}")
        return final_path

    async def _render_genesis(
        self,
        frames: list[VisualizationFrame],
        output_path: Path,
        progress_callback: Callable[[float], None] | None = None,
    ) -> Path:
        """Render visualization frames using Genesis.

        This creates the actual 3D rendered output.
        """
        # Create output directory for frames
        frames_dir = output_path.parent / f"{output_path.stem}_frames"
        frames_dir.mkdir(parents=True, exist_ok=True)

        try:
            import genesis as gs

            gs.init(backend=gs.cpu)

            # Create scene
            scene = gs.Scene(
                show_viewer=False,
                vis_options=gs.VisOptions(
                    ambient_light=(0.3, 0.3, 0.4),
                ),
            )

            # Add floor
            scene.add_entity(gs.Plane())

            # Create a camera
            camera = scene.add_camera(
                pos=(10, 0, 3),
                lookat=(0, 0, 1),
                fov=45,
                res=(self.config.output_width, self.config.output_height),
            )

            # Build scene
            scene.build()

            # Render each frame
            for i, vis_frame in enumerate(frames):
                # Update camera
                camera.set_pose(
                    pos=vis_frame.camera_position,
                    lookat=vis_frame.camera_lookat,
                )

                # Step physics (just for stability)
                scene.step()

                # Render
                result = camera.render()
                rgb = result[0] if isinstance(result, tuple) else result
                if hasattr(rgb, "numpy"):
                    rgb = rgb.numpy()

                # Save frame
                if rgb is not None:
                    from PIL import Image

                    frame_path = frames_dir / f"frame_{i:05d}.png"
                    Image.fromarray(rgb).save(frame_path)

                if progress_callback and i % 10 == 0:
                    progress_callback(i / len(frames))

            # Cleanup
            gs.destroy()

        except ImportError:
            logger.warning("Genesis not available, generating placeholder frames")
            # Generate placeholder colored frames based on analysis
            for i, vis_frame in enumerate(frames):
                frame = self._generate_placeholder_frame(vis_frame)
                frame_path = frames_dir / f"frame_{i:05d}.png"
                from PIL import Image

                Image.fromarray(frame).save(frame_path)

                if progress_callback and i % 10 == 0:
                    progress_callback(i / len(frames))

        # Assemble frames to video
        video_path = output_path.with_suffix(".tmp.mp4")
        await self._frames_to_video(frames_dir, video_path)

        return video_path

    def _generate_placeholder_frame(self, vis_frame: VisualizationFrame) -> np.ndarray:
        """Generate a placeholder frame when Genesis isn't available."""
        w, h = self.config.output_width, self.config.output_height
        frame = np.zeros((h, w, 3), dtype=np.uint8)

        # Background gradient
        bg = vis_frame.background_color
        for y in range(h):
            brightness = 1 - (y / h) * 0.5
            frame[y, :, 0] = int(bg[0] * 255 * brightness)
            frame[y, :, 1] = int(bg[1] * 255 * brightness)
            frame[y, :, 2] = int(bg[2] * 255 * brightness)

        # Draw circles for each element
        for element in vis_frame.elements:
            if element.element_type in ("sphere", "ring"):
                # Project 3D to 2D (simplified)
                cx = int(w / 2 + element.position[0] * 50)
                cy = int(h / 2 - element.position[2] * 50)
                radius = int(element.scale[0] * 100 * (1 + element.emissive))

                if 0 < cx < w and 0 < cy < h and radius > 0:
                    # Draw filled circle
                    for dy in range(-radius, radius + 1):
                        for dx in range(-radius, radius + 1):
                            if dx * dx + dy * dy <= radius * radius:
                                px, py = cx + dx, cy + dy
                                if 0 <= px < w and 0 <= py < h:
                                    # Blend with color
                                    r = int(element.color[0] * 255 * (0.5 + element.emissive))
                                    g = int(element.color[1] * 255 * (0.5 + element.emissive))
                                    b = int(element.color[2] * 255 * (0.5 + element.emissive))
                                    frame[py, px] = [
                                        min(255, frame[py, px, 0] + r // 2),
                                        min(255, frame[py, px, 1] + g // 2),
                                        min(255, frame[py, px, 2] + b // 2),
                                    ]

        return frame

    async def _frames_to_video(self, frames_dir: Path, output_path: Path) -> None:
        """Assemble frames into video using ffmpeg."""

        cmd = [
            "ffmpeg",
            "-y",
            "-framerate",
            str(self.config.fps),
            "-i",
            str(frames_dir / "frame_%05d.png"),
            "-c:v",
            "libx264",
            "-preset",
            "medium",
            "-crf",
            "18",
            "-pix_fmt",
            "yuv420p",
            str(output_path),
        ]

        process = await asyncio.create_subprocess_exec(
            *cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        await process.communicate()

    async def _combine_audio_video(
        self,
        video_path: Path,
        audio_path: Path,
        output_path: Path,
    ) -> Path:
        """Combine video with original audio."""

        cmd = [
            "ffmpeg",
            "-y",
            "-i",
            str(video_path),
            "-i",
            str(audio_path),
            "-c:v",
            "copy",
            "-c:a",
            "aac",
            "-b:a",
            "192k",
            "-shortest",
            str(output_path),
        ]

        process = await asyncio.create_subprocess_exec(
            *cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        await process.communicate()

        # Cleanup temp video
        video_path.unlink(missing_ok=True)

        return output_path


# =============================================================================
# Convenience Functions
# =============================================================================


async def visualize_orchestra(
    audio_path: str | Path,
    output_path: str | Path | None = None,
    width: int = 1920,
    height: int = 1080,
    fps: float = 30.0,
) -> Path:
    """Create an audio-reactive orchestral visualization.

    Args:
        audio_path: Path to orchestral audio file
        output_path: Output video path (default: {audio_path}_visualization.mp4)
        width: Output width in pixels
        height: Output height in pixels
        fps: Output frame rate

    Returns:
        Path to generated video
    """
    audio_path = Path(audio_path)
    if output_path is None:
        output_path = audio_path.with_stem(f"{audio_path.stem}_visualization").with_suffix(".mp4")
    output_path = Path(output_path)

    config = VisualizationConfig(
        output_width=width,
        output_height=height,
        fps=fps,
    )

    visualizer = OrchestraVisualizer(config)
    return await visualizer.create_visualization(audio_path, output_path)


# =============================================================================
# Exports
# =============================================================================

__all__ = [
    "ORCHESTRA_FREQUENCY_BANDS",
    "SECTION_VISUALS",
    # Analysis
    "AudioAnalysisFrame",
    # Config
    "FrequencyBand",
    "OrchestraAudioAnalyzer",
    # Enums
    "OrchestraSection",
    "OrchestraVisualizationGenerator",
    # Main
    "OrchestraVisualizer",
    "SectionVisualConfig",
    # Visualization
    "VisualElement",
    "VisualizationConfig",
    "VisualizationFrame",
    "visualize_orchestra",
]
