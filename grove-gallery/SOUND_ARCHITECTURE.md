# Grove Gallery - Musical Sound Architecture

## Overview

The sound system is now a **musical composition** based on **E minor pentatonic** scale, with spatial audio, reverb, and ADSR envelopes for expressive phrases.

## Musical Foundation

### E Minor Pentatonic Scale (164.81 Hz - 659.25 Hz)

```
E  = 164.81 Hz (root)
G  = 196.00 Hz (minor third)
A  = 220.00 Hz (fourth)
B  = 246.94 Hz (fifth)
D  = 293.66 Hz (minor seventh)
```

**Why E minor pentatonic?**
- Mystical, meditative quality (perfect for Grove)
- Cannot play wrong notes (all notes harmonize)
- Works for tension and resolution

## Core Architecture

### 1. Musical Phrase Engine (`playPhrase`)

All sounds use ADSR envelope:
- **Attack** (10-50ms): Rise to peak volume
- **Decay** (50-200ms): Drop to sustain level
- **Sustain** (0-100%): Held level during event
- **Release** (100-1000ms): Fade to silence

### 2. Spatial Audio

Stereo panning based on element position:
- `-1.0` = full left
- `0.0` = center
- `+1.0` = full right

Example: Particles spawn at cursor position, sound pans accordingly.

### 3. Reverb (Cathedral Space)

2.5 second reverb tail simulating mystical space:
- **Dry** (60%): Direct sound
- **Wet** (40%): Reverb tail

## Gallery Event Mapping

### Entrance
| Event | Musical Element | Notes |
|-------|-----------------|-------|
| Glyph appears | **E minor chord** (E + G + B) | Foundation, invitation |
| Light burst | **Perfect fifth** (E + B) + shimmer | Mystical energy |
| Title cascade | **E minor arpeggio** (E → G → B → D → E) | Ascending revelation |
| Particles | **Random pentatonic notes** | Organic, varied texture |

### Sanctuary
| Event | Musical Element | Notes |
|-------|-----------------|-------|
| Ambient | **E + B drone** (fifth) | Deep meditation, sustained |
| Cursor swarm | Notes rise with tension | E → G → A → B (ascending) |
| Click burst | **Spatial audio** based on cursor | Pan position matches click |
| Typewriter | Random pentatonic per letter | Musical typing rhythm |
| Detail open | **E major resolution** (E + G# + B) | Success, positive |

### Colonies Hall
| Event | Musical Element | Notes |
|-------|-----------------|-------|
| Wave pulse | **Seven colony notes** | E, G, A, B, D, E, G |
| Click colony | That colony's specific note | Musical identity per colony |
| Ripple | Notes along Fano line | Three-note chord |

### Fano 3D
| Event | Musical Element | Notes |
|-------|-----------------|-------|
| Rotation | **E drone** (constant) | Grounding presence |
| Hover line | **Three-note chord** | Simultaneous harmony |
| Pluck line | String vibration + overtones | Rich harmonic texture |

### Workflow
| Event | Musical Element | Notes |
|-------|-----------------|-------|
| PLAN | **E + G** (minor third) | Opening, questioning |
| EXECUTE | **A + D** (tension) | Action, forward motion |
| VERIFY | **E major chord** | Resolution, success |

### Foundations
| Event | Musical Element | Notes |
|-------|-----------------|-------|
| E8 lattice | Full pentatonic arpeggio | Complete scale showcase |
| Catastrophe | **Pitch bend** | Smooth frequency shifts |
| CBF safety | Consonance ↔ dissonance | Safe = harmony, danger = tritone |

### Epilogue
| Event | Musical Element | Notes |
|-------|-----------------|-------|
| Seven orbs | Seven-part ascending harmony | All colonies together |
| Final message | **E major resolution** (4 notes) | Grand finale, 4s decay |

## Musical Principles Applied

### 1. Harmonic Coherence
All sounds exist in the same key. No random frequencies that clash.

### 2. Tension & Resolution
- **Tension**: A + D (no resolution)
- **Resolution**: E major chord (stable, positive)

### 3. Spatial Expression
Sounds originate from visual elements (cursor, particles, colonies).

### 4. Dynamic Range
- Particles: 0.05 volume (subtle)
- Chords: 0.3 volume (prominent)
- Ambient: 0.001 start → fade in (barely audible → present)

### 5. Phrase-Based Expression
Every sound has musical shape (attack, sustain, release), not just on/off.

## Technical Implementation

### File: `js/core/sound.js`

**Key Methods:**
- `playPhrase(freq, pan, duration, envelope, reverb, waveform)` — Core phrase engine
- `playChord(frequencies, pan, duration, reverb)` — Simultaneous notes
- `playArpeggio(frequencies, pan, noteGap)` — Sequential notes
- `createReverb()` — Cathedral impulse response

**Musical Vocabulary:**
```javascript
// Play single note with expression
soundSystem.playPhrase(164.81, 0, 1.0, {
  attack: 0.02,
  decay: 0.1,
  sustain: 0.7,
  release: 0.5
}, true, 'sine');

// Play chord (harmony)
soundSystem.playChord([164.81, 196.00, 246.94], 0, 1.5, true);

// Play arpeggio (melody)
soundSystem.playArpeggio([164.81, 196.00, 246.94], 0, 0.15);
```

## Colony-Specific Frequencies

```javascript
this.colonyNotes = [
  164.81,  // E3 - Spark
  196.00,  // G3 - Forge
  220.00,  // A3 - Flow
  246.94,  // B3 - Nexus
  293.66,  // D4 - Beacon
  329.63,  // E4 - Grove
  392.00,  // G4 - Crystal
];
```

Each colony has its own musical identity within the pentatonic scale.

## Testing

Open `index.html` in browser and verify:

1. **Entrance**: Glyph → chord, burst → fifth + shimmer, title → arpeggio
2. **Sanctuary**: Ambient drone (E + B), particles pan with cursor
3. **Typewriter**: Each letter = random pentatonic note
4. **Harmony**: All sounds blend (no dissonance)
5. **Spatial**: Sounds pan left/right based on position

## Future Enhancements

- [ ] Web MIDI for external synth control
- [ ] Generative ambient layers (slow harmonic shifts)
- [ ] Dynamic reverb size based on room
- [ ] WebAudio Analyzer for visual-audio sync
- [ ] Colony-specific waveforms (Spark=sawtooth, Crystal=square, etc.)

---

**Musical Principle**: The sound IS the story. Every note has meaning, every chord has purpose, every phrase has shape.

Built by Forge (e₂) — December 2025
