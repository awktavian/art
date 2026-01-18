"""Audio System Module - Physics-based spatial audio rendering.

Responsibilities:
- Physics-based collision audio synthesis
- Spatial audio positioning (VBAP)
- Real-time audio buffer management
- Acoustic modeling and room acoustics
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import numpy as np

logger = logging.getLogger(__name__)


@dataclass
class PhysicsAudioEvent:
    """Audio event from physics simulation."""

    type: str  # "collision", "friction", "impact"
    position: tuple[float, float, float]
    velocity: tuple[float, float, float]
    mass: float
    material: str
    intensity: float  # 0.0 to 1.0
    timestamp: float


class RealtimeAudioEngine:
    """Real-time spatial audio engine for physics events."""

    def __init__(self, sample_rate: int = 44100, buffer_ms: int = 50) -> None:
        self.sample_rate = sample_rate
        self.buffer_size = int(sample_rate * buffer_ms / 1000)
        self.buffer = np.zeros((self.buffer_size, 2), dtype=np.float32)  # Stereo

        # Audio synthesis parameters
        self.noise_generators = {}
        self.oscillators = {}

        # Spatial audio setup (8-channel surround, downmixed to stereo)
        self.speaker_positions = np.array(
            [
                [1.0, 0.0, 0.0],  # Front Center
                [0.707, 0.707, 0.0],  # Front Right
                [0.0, 1.0, 0.0],  # Right
                [-0.707, 0.707, 0.0],  # Back Right
                [-1.0, 0.0, 0.0],  # Back Center
                [-0.707, -0.707, 0.0],  # Back Left
                [0.0, -1.0, 0.0],  # Left
                [0.707, -0.707, 0.0],  # Front Left
            ],
        )

        # Room acoustics parameters
        self.room_size = (10.0, 8.0, 3.0)  # meters
        self.absorption_coefficient = 0.3
        self.reverb_time = 1.2  # seconds

        logger.info(f"Audio engine initialized: {sample_rate}Hz, {buffer_ms}ms buffer")

    def synthesize_collision(
        self,
        material1: str,
        material2: str,
        impact_velocity: float,
        mass: float,
        position: tuple[float, float, float],
    ) -> np.ndarray:
        """Synthesize collision audio based on materials and physics."""
        # Material-specific parameters
        material_params = self._get_material_audio_params(material1, material2)

        # Calculate impact energy
        kinetic_energy = 0.5 * mass * impact_velocity**2
        amplitude = min(1.0, kinetic_energy / 100.0)  # Normalize to reasonable range

        # Generate base collision sound
        duration_samples = int(material_params["duration"] * self.sample_rate)
        t = np.linspace(0, material_params["duration"], duration_samples)

        # Multiple frequency components for realistic collision
        frequencies = material_params["frequencies"]
        audio = np.zeros(duration_samples)

        for freq, weight in frequencies:
            # Add frequency component with exponential decay
            component = np.sin(2 * np.pi * freq * t) * np.exp(-t * material_params["decay_rate"])
            audio += component * weight

        # Add noise component for texture
        if material_params["noise_amount"] > 0:
            noise = np.random.normal(0, 0.1, duration_samples)
            # Filter noise based on material
            if material_params["noise_filter"] == "lowpass":
                # Simple lowpass filter
                for i in range(1, len(noise)):
                    noise[i] = noise[i] * 0.7 + noise[i - 1] * 0.3

            audio += noise * material_params["noise_amount"]

        # Apply amplitude and velocity-based modulation
        audio *= amplitude
        audio = np.tanh(audio * 2.0) * 0.5  # Soft clipping for realistic saturation

        return audio.astype(np.float32)

    def _get_material_audio_params(self, material1: str, material2: str) -> dict[str, Any]:
        """Get audio synthesis parameters for material combination."""
        # Material library
        materials = {
            "metal": {
                "frequencies": [(800, 0.5), (1600, 0.3), (3200, 0.2)],
                "decay_rate": 3.0,
                "duration": 0.5,
                "noise_amount": 0.1,
                "noise_filter": "highpass",
            },
            "wood": {
                "frequencies": [(200, 0.4), (400, 0.4), (800, 0.2)],
                "decay_rate": 4.0,
                "duration": 0.8,
                "noise_amount": 0.3,
                "noise_filter": "lowpass",
            },
            "glass": {
                "frequencies": [(1000, 0.3), (2000, 0.4), (4000, 0.3)],
                "decay_rate": 8.0,
                "duration": 1.2,
                "noise_amount": 0.05,
                "noise_filter": "highpass",
            },
            "plastic": {
                "frequencies": [(300, 0.4), (600, 0.3), (1200, 0.3)],
                "decay_rate": 5.0,
                "duration": 0.4,
                "noise_amount": 0.2,
                "noise_filter": "lowpass",
            },
            "concrete": {
                "frequencies": [(100, 0.5), (200, 0.3), (400, 0.2)],
                "decay_rate": 2.0,
                "duration": 1.0,
                "noise_amount": 0.4,
                "noise_filter": "lowpass",
            },
        }

        # Get parameters for both materials and blend
        params1 = materials.get(material1.lower(), materials["plastic"])
        params2 = materials.get(material2.lower(), materials["plastic"])

        # Blend parameters
        blended = {
            "frequencies": [],
            "decay_rate": (params1["decay_rate"] + params2["decay_rate"]) / 2,
            "duration": max(params1["duration"], params2["duration"]),
            "noise_amount": (params1["noise_amount"] + params2["noise_amount"]) / 2,
            "noise_filter": params1["noise_filter"],  # Use first material's filter
        }

        # Blend frequencies
        all_freqs = params1["frequencies"] + params2["frequencies"]
        # Remove duplicates and normalize weights
        freq_dict = {}
        for freq, weight in all_freqs:
            freq_dict[freq] = freq_dict.get(freq, 0) + weight

        blended["frequencies"] = [(freq, weight * 0.5) for freq, weight in freq_dict.items()]

        return blended

    def synthesize_friction(
        self,
        material1: str,
        material2: str,
        friction_velocity: float,
        normal_force: float,
        position: tuple[float, float, float],
    ) -> np.ndarray:
        """Synthesize friction/sliding audio."""
        # Friction creates continuous noise-like sounds
        duration_samples = self.buffer_size  # Generate one buffer's worth

        # Material-specific friction parameters
        friction_params = {
            ("metal", "metal"): {"base_freq": 800, "noise_intensity": 0.3},
            ("wood", "wood"): {"base_freq": 200, "noise_intensity": 0.5},
            ("glass", "concrete"): {"base_freq": 1200, "noise_intensity": 0.2},
            # Add more combinations as needed
        }

        material_key = tuple(sorted([material1.lower(), material2.lower()]))
        params = friction_params.get(material_key, {"base_freq": 400, "noise_intensity": 0.4})

        # Generate filtered noise
        audio = np.random.normal(0, params["noise_intensity"], duration_samples)

        # Apply velocity-based modulation
        velocity_factor = min(1.0, friction_velocity / 10.0)  # Normalize to 0-1
        audio *= velocity_factor

        # Apply force-based amplitude
        force_factor = min(1.0, normal_force / 1000.0)  # Normalize to 0-1
        audio *= force_factor

        # Filter based on material combination
        # Simple resonant filter around base frequency
        # This is a placeholder - in practice, you'd use proper DSP filtering
        for i in range(2, len(audio)):
            resonance = 0.1
            cutoff = params["base_freq"] / self.sample_rate
            audio[i] += audio[i - 1] * (1 - cutoff) * resonance

        return audio.astype(np.float32)

    def _position_to_spherical(
        self,
        position: tuple[float, float, float],
        listener_pos: tuple[float, float, float],
    ) -> tuple[float, float, float]:
        """Convert 3D position to spherical coordinates relative to listener."""
        dx = position[0] - listener_pos[0]
        dy = position[1] - listener_pos[1]
        dz = position[2] - listener_pos[2]

        distance = np.sqrt(dx**2 + dy**2 + dz**2)

        # Avoid division by zero
        if distance < 0.001:
            return 0.0, 0.0, 0.001

        azimuth = np.arctan2(dy, dx)
        elevation = np.arcsin(dz / distance)

        return azimuth, elevation, distance

    def _vbap_pan(
        self,
        azimuth: float,
        elevation: float,
        audio: np.ndarray,
    ) -> np.ndarray:
        """Vector Base Amplitude Panning for spatial audio."""
        # Convert spherical to Cartesian
        source_vector = np.array(
            [
                np.cos(elevation) * np.cos(azimuth),
                np.cos(elevation) * np.sin(azimuth),
                np.sin(elevation),
            ],
        )

        # Find the closest speakers and calculate gains
        gains = np.zeros(len(self.speaker_positions))

        for i, speaker_pos in enumerate(self.speaker_positions):
            # Calculate angle between source and speaker
            dot_product = np.dot(source_vector[:2], speaker_pos[:2])  # Only use X,Y for 2D panning
            dot_product = np.clip(dot_product, -1.0, 1.0)
            angle = np.arccos(dot_product)

            # VBAP gain calculation
            if angle < np.pi / 2:  # Speaker is in front hemisphere
                gains[i] = np.cos(angle) ** 2
            else:
                gains[i] = 0.0

        # Normalize gains
        total_gain = np.sum(gains)
        if total_gain > 0:
            gains /= total_gain

        # Apply panning to create 8-channel surround
        multichannel = np.zeros((len(audio), len(self.speaker_positions)))
        for i in range(len(self.speaker_positions)):
            multichannel[:, i] = audio * gains[i]

        return multichannel

    def _apply_room_acoustics(self, audio: np.ndarray, distance: float) -> np.ndarray:
        """Apply simple room acoustics model."""
        # Distance attenuation
        attenuation = 1.0 / (1.0 + distance * 0.1)
        audio_with_distance = audio * attenuation

        # Simple reverb simulation
        reverb_delay_samples = int(0.05 * self.sample_rate)  # 50ms delay
        reverb_gain = 0.3 * (1.0 - self.absorption_coefficient)

        if len(audio_with_distance) > reverb_delay_samples:
            reverb = np.zeros_like(audio_with_distance)
            reverb[reverb_delay_samples:] = (
                audio_with_distance[:-reverb_delay_samples] * reverb_gain
            )
            audio_with_distance += reverb

        # High frequency absorption for distant sounds
        if distance > 5.0:
            # Simple high-cut filter
            for i in range(1, len(audio_with_distance)):
                cutoff = 0.8  # Aggressive high-cut for distant sounds
                audio_with_distance[i] = (
                    audio_with_distance[i] * (1 - cutoff) + audio_with_distance[i - 1] * cutoff
                )

        return audio_with_distance

    def _downmix_stereo(self, multichannel: np.ndarray) -> np.ndarray:
        """Downmix 8-channel surround to stereo."""
        if multichannel.shape[1] != 8:
            return multichannel

        # Standard 8-channel to stereo downmix matrix
        downmix_matrix = np.array(
            [
                [0.5, 0.354, 0.0, -0.354, -0.5, -0.354, 0.0, 0.354],  # Left
                [0.5, 0.354, 0.0, 0.354, -0.5, 0.354, 0.0, -0.354],  # Right
            ],
        )

        return np.dot(multichannel, downmix_matrix.T)

    def add_event(self, event: PhysicsAudioEvent, listener_pos: tuple[float, float, float]) -> None:
        """Add physics audio event to processing queue."""
        try:
            if event.type == "collision":
                audio = self.synthesize_collision(
                    event.material,
                    event.material,
                    np.linalg.norm(event.velocity),
                    event.mass,
                    event.position,
                )
            elif event.type == "friction":
                audio = self.synthesize_friction(
                    event.material,
                    "concrete",  # Assume ground friction
                    np.linalg.norm(event.velocity),
                    event.mass * 9.81,  # Approximate normal force
                    event.position,
                )
            else:
                return  # Unknown event type

            # Apply spatial positioning
            azimuth, elevation, distance = self._position_to_spherical(event.position, listener_pos)
            multichannel = self._vbap_pan(azimuth, elevation, audio)
            spatial_audio = self._apply_room_acoustics(multichannel, distance)
            stereo = self._downmix_stereo(spatial_audio)

            # Mix into buffer (simple addition for now)
            mix_length = min(len(stereo), len(self.buffer))
            self.buffer[:mix_length] += stereo[:mix_length] * event.intensity

            # Prevent clipping
            self.buffer = np.tanh(self.buffer)

        except Exception as e:
            logger.error(f"Error processing audio event: {e}")

    def get_buffer(self) -> np.ndarray:
        """Get current audio buffer and clear it."""
        result = self.buffer.copy()
        self.buffer.fill(0.0)  # Clear for next frame
        return result

    def set_listener_position(self, position: tuple[float, float, float]) -> None:
        """Update listener position for spatial audio."""
        # This would be used to update spatial calculations
        # For now, listener position is passed per-event

    def set_room_parameters(
        self,
        room_size: tuple[float, float, float],
        absorption: float,
    ) -> None:
        """Update room acoustics parameters."""
        self.room_size = room_size
        self.absorption_coefficient = absorption
        # Recalculate reverb time based on room size and absorption
        volume = room_size[0] * room_size[1] * room_size[2]
        surface_area = 2 * (
            room_size[0] * room_size[1] + room_size[0] * room_size[2] + room_size[1] * room_size[2]
        )
        self.reverb_time = 0.16 * volume / (absorption * surface_area)

    def save_audio(self, audio: np.ndarray, path: Path) -> None:
        """Save audio buffer to file (for debugging)."""
        try:
            import wave

            # Convert to 16-bit PCM
            audio_int = (audio * 32767).astype(np.int16)

            with wave.open(str(path), "wb") as wav_file:
                wav_file.setnchannels(2)  # Stereo
                wav_file.setsampwidth(2)  # 16-bit
                wav_file.setframerate(self.sample_rate)
                wav_file.writeframes(audio_int.tobytes())

            logger.info(f"Audio saved to {path}")
        except Exception as e:
            logger.error(f"Failed to save audio: {e}")


class CollisionAudioSystem:
    """System for managing collision audio events in real-time rendering."""

    def __init__(self, audio_engine: RealtimeAudioEngine) -> None:
        self.audio_engine = audio_engine
        self.pending_events: list[PhysicsAudioEvent] = []
        self.listener_position = (0.0, 0.0, 0.0)

        # Event filtering to prevent audio spam
        self.min_event_interval = 0.01  # 10ms minimum between events
        self.last_event_time = 0.0
        self.event_threshold = 0.1  # Minimum intensity to process

    def add_collision(
        self,
        position: tuple[float, float, float],
        velocity: tuple[float, float, float],
        mass: float,
        material: str,
        timestamp: float,
    ) -> None:
        """Add collision event."""
        # Filter out weak or too-frequent events
        intensity = min(1.0, np.linalg.norm(velocity) * mass / 100.0)

        if intensity < self.event_threshold:
            return

        if timestamp - self.last_event_time < self.min_event_interval:
            return

        event = PhysicsAudioEvent(
            type="collision",
            position=position,
            velocity=velocity,
            mass=mass,
            material=material,
            intensity=intensity,
            timestamp=timestamp,
        )

        self.pending_events.append(event)
        self.last_event_time = timestamp

    def add_friction(
        self,
        position: tuple[float, float, float],
        velocity: tuple[float, float, float],
        mass: float,
        material: str,
        timestamp: float,
    ) -> None:
        """Add friction event."""
        # Friction events are continuous but we sample them
        velocity_magnitude = np.linalg.norm(velocity)
        if velocity_magnitude < 0.1:  # Too slow for audible friction
            return

        intensity = min(1.0, velocity_magnitude / 10.0)

        event = PhysicsAudioEvent(
            type="friction",
            position=position,
            velocity=velocity,
            mass=mass,
            material=material,
            intensity=intensity,
            timestamp=timestamp,
        )

        self.pending_events.append(event)

    def update_listener(self, position: tuple[float, float, float]) -> None:
        """Update listener position."""
        self.listener_position = position

    def process_events(self) -> None:
        """Process all pending audio events."""
        for event in self.pending_events:
            self.audio_engine.add_event(event, self.listener_position)

        self.pending_events.clear()

    def get_audio_buffer(self) -> np.ndarray:
        """Get processed audio buffer."""
        return self.audio_engine.get_buffer()
