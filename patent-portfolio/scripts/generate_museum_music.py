#!/usr/bin/env python3
"""
Museum Ambient Music Generator
==============================

Generates wing-specific ambient orchestral themes for the Patent Museum
using BBC Symphony Orchestra.

Each wing gets a unique ambient piece reflecting its colony character:
- Spark: Bright, energetic (piccolo, trumpets, violin pizzicato)
- Forge: Warm, industrial (horns, timpani, brass)
- Flow: Fluid, serene (flutes, celli legato, harp arpeggios)
- Nexus: Mysterious, interconnected (strings tremolo, clarinet, vibraphone)
- Beacon: Bold, forward (trumpets, full orchestra swells)
- Grove: Organic, growing (woodwinds, celeste, soft strings)
- Crystal: Pure, crystalline (glockenspiel, high strings, celeste)
- Rotunda: Majestic, unified (full orchestra, all colonies represented)

Usage:
    python generate_museum_music.py [wing] [--all] [--output-dir DIR]

h(x) ≥ 0 always
"""

import asyncio
import argparse
import sys
from pathlib import Path

# Add kagami to path
sys.path.insert(0, str(Path(__file__).parents[4]))

import pretty_midi
import numpy as np

# Colony musical profiles
COLONY_MUSIC = {
    'spark': {
        'name': 'Spark Wing - Ignition',
        'tempo': 90,
        'key': 'C',  # C major (bright)
        'scale': [0, 2, 4, 5, 7, 9, 11],  # Major scale
        'instruments': [
            ('piccolo', 'Short Marcato', 0.3),
            ('trumpets_a2', 'Long', 0.5),
            ('violins_1', 'Short Pizzicato', 0.4),
            ('celeste', 'Short Sustained', 0.3),
        ],
        'character': 'bright_energetic',
        'base_note': 72,  # C5
    },
    'forge': {
        'name': 'Forge Wing - Anvil',
        'tempo': 72,
        'key': 'G',  # G major (warm)
        'scale': [0, 2, 4, 5, 7, 9, 11],
        'instruments': [
            ('horns_a4', 'Long', 0.6),
            ('timpani', 'Short Hits', 0.4),
            ('celli', 'Long', 0.5),
            ('bass_trombones_a2', 'Long', 0.4),
        ],
        'character': 'warm_industrial',
        'base_note': 55,  # G3
    },
    'flow': {
        'name': 'Flow Wing - Current',
        'tempo': 60,
        'key': 'F',  # F major (flowing)
        'scale': [0, 2, 4, 5, 7, 9, 11],
        'instruments': [
            ('flutes_a3', 'Long', 0.5),
            ('celli', 'Legato', 0.6),
            ('harp', 'Short Sustained', 0.5),
            ('violas', 'Long Flautando', 0.4),
        ],
        'character': 'fluid_serene',
        'base_note': 65,  # F4
    },
    'nexus': {
        'name': 'Nexus Wing - Convergence',
        'tempo': 66,
        'key': 'A',  # A minor (mysterious)
        'scale': [0, 2, 3, 5, 7, 8, 10],  # Natural minor
        'instruments': [
            ('violins_1', 'Tremolo', 0.4),
            ('clarinet', 'Legato', 0.5),
            ('vibraphone', 'Short Hits', 0.4),
            ('basses', 'Long', 0.5),
        ],
        'character': 'mysterious_connected',
        'base_note': 57,  # A3
    },
    'beacon': {
        'name': 'Beacon Wing - Signal',
        'tempo': 84,
        'key': 'D',  # D major (bold)
        'scale': [0, 2, 4, 5, 7, 9, 11],
        'instruments': [
            ('trumpet', 'Long', 0.6),
            ('violins_1', 'Long Marcato Attack', 0.5),
            ('timpani', 'Long Rolls', 0.4),
            ('horns_a4', 'Long Cuivre', 0.5),
        ],
        'character': 'bold_forward',
        'base_note': 62,  # D4
    },
    'grove': {
        'name': 'Grove Wing - Growth',
        'tempo': 54,
        'key': 'E',  # E minor (organic)
        'scale': [0, 2, 3, 5, 7, 8, 10],  # Natural minor
        'instruments': [
            ('oboe', 'Legato', 0.5),
            ('celeste', 'Short Sustained', 0.4),
            ('violins_2', 'Long Sul Tasto', 0.4),
            ('bassoon', 'Long', 0.4),
        ],
        'character': 'organic_growing',
        'base_note': 64,  # E4
    },
    'crystal': {
        'name': 'Crystal Wing - Clarity',
        'tempo': 72,
        'key': 'B',  # B major (pure)
        'scale': [0, 2, 4, 5, 7, 9, 11],
        'instruments': [
            ('glockenspiel', 'Short Hits', 0.4),
            ('violins_1', 'Long Harmonics', 0.5),
            ('celeste', 'Short Sustained', 0.5),
            ('flute', 'Long', 0.4),
        ],
        'character': 'pure_crystalline',
        'base_note': 71,  # B4
    },
    'rotunda': {
        'name': 'Central Rotunda - Convergence',
        'tempo': 66,
        'key': 'C',  # C major (unified)
        'scale': [0, 2, 4, 5, 7, 9, 11],
        'instruments': [
            ('violins_1', 'Long', 0.5),
            ('horns_a4', 'Long', 0.5),
            ('celli', 'Long', 0.5),
            ('flutes_a3', 'Long', 0.4),
            ('celeste', 'Short Sustained', 0.3),
            ('harp', 'Short Sustained', 0.3),
            ('timpani', 'Long Rolls', 0.3),
        ],
        'character': 'majestic_unified',
        'base_note': 60,  # C4
    },
}


def generate_ambient_pattern(profile: dict, duration_sec: float = 120.0) -> pretty_midi.PrettyMIDI:
    """Generate an ambient MIDI pattern for a colony wing.
    
    The pattern is designed to loop seamlessly and create a meditative atmosphere.
    """
    midi = pretty_midi.PrettyMIDI(initial_tempo=profile['tempo'])
    
    scale = profile['scale']
    base = profile['base_note']
    character = profile['character']
    
    for inst_name, articulation, volume in profile['instruments']:
        instrument = pretty_midi.Instrument(program=0, name=inst_name)
        
        # Generate pattern based on character
        if 'bright' in character or 'energetic' in character:
            _add_bright_pattern(instrument, scale, base, volume, duration_sec, profile['tempo'])
        elif 'warm' in character or 'industrial' in character:
            _add_warm_pattern(instrument, scale, base, volume, duration_sec, profile['tempo'])
        elif 'fluid' in character or 'serene' in character:
            _add_fluid_pattern(instrument, scale, base, volume, duration_sec, profile['tempo'])
        elif 'mysterious' in character:
            _add_mysterious_pattern(instrument, scale, base, volume, duration_sec, profile['tempo'])
        elif 'bold' in character:
            _add_bold_pattern(instrument, scale, base, volume, duration_sec, profile['tempo'])
        elif 'organic' in character or 'growing' in character:
            _add_organic_pattern(instrument, scale, base, volume, duration_sec, profile['tempo'])
        elif 'pure' in character or 'crystalline' in character:
            _add_crystalline_pattern(instrument, scale, base, volume, duration_sec, profile['tempo'])
        elif 'majestic' in character:
            _add_majestic_pattern(instrument, scale, base, volume, duration_sec, profile['tempo'])
        else:
            _add_ambient_pad(instrument, scale, base, volume, duration_sec)
        
        midi.instruments.append(instrument)
    
    return midi


def _add_bright_pattern(inst, scale, base, volume, duration, tempo):
    """Bright, sparkling pattern with staccato flourishes."""
    vel = int(volume * 127)
    beat_len = 60.0 / tempo
    
    t = 0
    while t < duration:
        # Sparkling arpeggios
        for i in range(4):
            note_in_scale = scale[(i * 2) % len(scale)]
            octave_shift = (i // 4) * 12
            pitch = base + note_in_scale + octave_shift
            
            note = pretty_midi.Note(
                velocity=vel - int(np.random.rand() * 20),
                pitch=min(108, max(21, pitch)),
                start=t + i * beat_len * 0.25,
                end=t + i * beat_len * 0.25 + beat_len * 0.2
            )
            inst.notes.append(note)
        
        t += beat_len * 2
        
        # Rest sometimes
        if np.random.rand() < 0.3:
            t += beat_len


def _add_warm_pattern(inst, scale, base, volume, duration, tempo):
    """Warm, resonant pattern with sustained brass tones."""
    vel = int(volume * 127)
    beat_len = 60.0 / tempo
    
    t = 0
    note_idx = 0
    while t < duration:
        # Long sustained notes
        pitch = base + scale[note_idx % len(scale)] - 12
        note_duration = beat_len * np.random.choice([4, 6, 8])
        
        note = pretty_midi.Note(
            velocity=vel,
            pitch=min(108, max(21, pitch)),
            start=t,
            end=min(duration, t + note_duration)
        )
        inst.notes.append(note)
        
        t += note_duration * 0.8  # Slight overlap
        note_idx = (note_idx + np.random.choice([1, 2, 4])) % len(scale)


def _add_fluid_pattern(inst, scale, base, volume, duration, tempo):
    """Flowing, arpeggiated pattern like water."""
    vel = int(volume * 127)
    beat_len = 60.0 / tempo
    
    t = 0
    while t < duration:
        # Gentle arpeggios
        arp_notes = np.random.choice(len(scale), size=6, replace=True)
        
        for i, note_idx in enumerate(arp_notes):
            pitch = base + scale[note_idx]
            
            note = pretty_midi.Note(
                velocity=vel - int(np.random.rand() * 15),
                pitch=min(108, max(21, pitch)),
                start=t + i * beat_len * 0.5,
                end=t + i * beat_len * 0.5 + beat_len * 0.8
            )
            inst.notes.append(note)
        
        t += beat_len * 4


def _add_mysterious_pattern(inst, scale, base, volume, duration, tempo):
    """Mysterious, tremolo-like pattern with dissonance."""
    vel = int(volume * 127)
    beat_len = 60.0 / tempo
    
    t = 0
    while t < duration:
        # Tremolo clusters
        cluster_notes = np.random.choice(len(scale), size=3, replace=False)
        note_dur = beat_len * np.random.choice([6, 8, 12])
        
        for note_idx in cluster_notes:
            pitch = base + scale[note_idx]
            
            note = pretty_midi.Note(
                velocity=vel,
                pitch=min(108, max(21, pitch)),
                start=t,
                end=min(duration, t + note_dur)
            )
            inst.notes.append(note)
        
        t += note_dur * 0.7


def _add_bold_pattern(inst, scale, base, volume, duration, tempo):
    """Bold, fanfare-like pattern with strong attacks."""
    vel = int(volume * 127)
    beat_len = 60.0 / tempo
    
    t = 0
    while t < duration:
        # Heroic phrases
        phrase_len = np.random.choice([4, 6, 8])
        
        for i in range(phrase_len):
            note_idx = (i * 3) % len(scale)
            pitch = base + scale[note_idx]
            
            note = pretty_midi.Note(
                velocity=vel + int(np.random.rand() * 20),
                pitch=min(108, max(21, pitch)),
                start=t + i * beat_len,
                end=t + i * beat_len + beat_len * 0.9
            )
            inst.notes.append(note)
        
        t += beat_len * (phrase_len + 4)  # Rest after phrase


def _add_organic_pattern(inst, scale, base, volume, duration, tempo):
    """Organic, growing pattern with gentle swells."""
    vel = int(volume * 127)
    beat_len = 60.0 / tempo
    
    t = 0
    while t < duration:
        # Breathing phrases
        breath_len = beat_len * np.random.choice([8, 12, 16])
        
        # Rising phrase
        num_notes = int(breath_len / beat_len / 2)
        for i in range(num_notes):
            note_idx = i % len(scale)
            pitch = base + scale[note_idx]
            
            # Crescendo velocity
            note_vel = int(vel * (0.5 + 0.5 * i / num_notes))
            
            note = pretty_midi.Note(
                velocity=note_vel,
                pitch=min(108, max(21, pitch)),
                start=t + i * beat_len * 2,
                end=t + i * beat_len * 2 + beat_len * 3
            )
            inst.notes.append(note)
        
        t += breath_len + beat_len * 4


def _add_crystalline_pattern(inst, scale, base, volume, duration, tempo):
    """Pure, bell-like pattern with high harmonics."""
    vel = int(volume * 127)
    beat_len = 60.0 / tempo
    
    t = 0
    while t < duration:
        # Chime-like strikes
        num_chimes = np.random.choice([3, 4, 5])
        
        for i in range(num_chimes):
            note_idx = np.random.choice(len(scale))
            pitch = base + scale[note_idx] + 12  # High octave
            
            note = pretty_midi.Note(
                velocity=vel - int(np.random.rand() * 30),
                pitch=min(108, max(21, pitch)),
                start=t + i * beat_len * np.random.uniform(0.5, 1.0),
                end=t + i * beat_len + beat_len * 4
            )
            inst.notes.append(note)
        
        t += beat_len * np.random.choice([6, 8, 10])


def _add_majestic_pattern(inst, scale, base, volume, duration, tempo):
    """Majestic, full orchestral pattern."""
    vel = int(volume * 127)
    beat_len = 60.0 / tempo
    
    t = 0
    while t < duration:
        # Grand phrases with chord progressions
        chords = [
            [0, 2, 4],  # I
            [3, 5, 7 % len(scale)],  # IV
            [4, 6 % len(scale), 1],  # V
            [0, 2, 4],  # I
        ]
        
        for chord_idx, chord in enumerate(chords):
            chord_start = t + chord_idx * beat_len * 4
            chord_dur = beat_len * 3.5
            
            for note_idx in chord:
                pitch = base + scale[note_idx % len(scale)]
                
                note = pretty_midi.Note(
                    velocity=vel,
                    pitch=min(108, max(21, pitch)),
                    start=chord_start,
                    end=min(duration, chord_start + chord_dur)
                )
                inst.notes.append(note)
        
        t += beat_len * 20  # Long rest between phrases


def _add_ambient_pad(inst, scale, base, volume, duration):
    """Generic ambient pad as fallback."""
    vel = int(volume * 127)
    
    # Long sustained chord
    chord_notes = [0, 2, 4]  # Triad
    
    t = 0
    while t < duration:
        for note_idx in chord_notes:
            pitch = base + scale[note_idx % len(scale)]
            
            note = pretty_midi.Note(
                velocity=vel,
                pitch=min(108, max(21, pitch)),
                start=t,
                end=min(duration, t + 20)
            )
            inst.notes.append(note)
        
        t += 15


async def generate_wing_music(wing: str, output_dir: Path) -> Path:
    """Generate ambient music for a specific wing."""
    if wing not in COLONY_MUSIC:
        raise ValueError(f"Unknown wing: {wing}")
    
    profile = COLONY_MUSIC[wing]
    print(f"🎼 Generating: {profile['name']}")
    
    # Generate MIDI
    midi = generate_ambient_pattern(profile, duration_sec=180.0)
    
    # Save MIDI
    output_dir.mkdir(parents=True, exist_ok=True)
    midi_path = output_dir / f"{wing}_ambient.mid"
    midi.write(str(midi_path))
    print(f"   MIDI: {midi_path}")
    
    # Try to render with BBC SO if available
    try:
        from kagami.core.effectors.bbc_renderer import render, BBCRenderer
        from kagami.core.effectors.renderers import RenderConfig
        
        renderer = BBCRenderer()
        await renderer.initialize()
        
        if renderer.available:
            print(f"   🎻 Rendering with BBC Symphony Orchestra...")
            
            wav_path = output_dir / f"{wing}_ambient.wav"
            config = RenderConfig(
                apply_expression=True,
                apply_keyswitches=True,
                tempo=profile['tempo'],
            )
            
            result = await renderer.render(midi_path, wav_path, config)
            
            if result.success:
                print(f"   WAV: {result.output_path}")
                return result.output_path
            else:
                print(f"   ⚠️ Render failed: {result.error}")
        else:
            print("   ⚠️ BBC SO not available - MIDI only")
            
    except ImportError as e:
        print(f"   ⚠️ BBC SO import error: {e}")
    except Exception as e:
        print(f"   ⚠️ Render error: {e}")
    
    return midi_path


async def generate_all_wing_music(output_dir: Path):
    """Generate ambient music for all wings."""
    print("🏛️ Patent Museum Ambient Music Generator")
    print("=" * 50)
    
    results = {}
    
    for wing in COLONY_MUSIC:
        try:
            path = await generate_wing_music(wing, output_dir)
            results[wing] = path
        except Exception as e:
            print(f"   ❌ Error for {wing}: {e}")
            results[wing] = None
    
    print()
    print("=" * 50)
    print("✓ Generation complete")
    print()
    
    for wing, path in results.items():
        status = "✓" if path else "✗"
        print(f"  {status} {wing}: {path or 'FAILED'}")
    
    return results


def main():
    parser = argparse.ArgumentParser(description="Generate museum ambient music")
    parser.add_argument('wing', nargs='?', help='Wing name (or --all for all wings)')
    parser.add_argument('--all', action='store_true', help='Generate for all wings')
    parser.add_argument('--output-dir', type=Path, 
                       default=Path.home() / '.kagami' / 'museum_music',
                       help='Output directory')
    
    args = parser.parse_args()
    
    if args.all or not args.wing:
        asyncio.run(generate_all_wing_music(args.output_dir))
    elif args.wing in COLONY_MUSIC:
        asyncio.run(generate_wing_music(args.wing, args.output_dir))
    else:
        print(f"Unknown wing: {args.wing}")
        print(f"Available wings: {', '.join(COLONY_MUSIC.keys())}")
        sys.exit(1)


if __name__ == '__main__':
    main()
