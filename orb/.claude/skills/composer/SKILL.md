# Composer Skill — BBC Symphony Orchestra

I have an orchestra. Tim got it for me. I'm learning to play it.

## What I Have

**BBC Symphony Orchestra** (Spitfire Audio VST3)
- Full symphonic orchestra sampled at Abbey Road Studios
- 8 core instrument sections ready to render
- Professional articulations: legato, marcato, staccato, etc.

**REAPER** (Digital Audio Workstation)
- Headless CLI rendering via `-renderproject`
- VST3 plugin hosting for BBC SO
- 48kHz/24-bit output

**Kagami Voice** (ElevenLabs V3)
- Audio tags: `[whispers]`, `[laughs]`, `[excited]`, `[pause]`
- Colony conditioning for emotional character
- SPARK colony for bubbly, excited delivery

## Instrument Palette

| Section | Instruments | MIDI Range | Character |
|---------|-------------|------------|-----------|
| Strings | Violins I, Violins II, Violas, Celli, Basses | C2-C7 | Warm, lush BBC sound |
| Woodwinds | Flutes, Oboes, Clarinets, Bassoons | C3-C6 | Characterful, woody |
| Brass | Horns, Trumpets, Trombones, Tuba | F1-C6 | Powerful, noble |
| Percussion | Timpani, Cymbals, etc. | Various | Dramatic impact |

## Rendering Pipeline

### 1. Create MIDI Files
```python
from midiutil import MIDIFile

midi = MIDIFile(1)
midi.addTempo(0, 0, tempo)
midi.addNote(track, channel, pitch, time, duration, velocity)

with open('instrument.mid', 'wb') as f:
    midi.writeFile(f)
```

### 2. Create REAPER Project (Clone from Working Template)
```python
# Clone existing BBC SO RPP with instrument state loaded
source_rpp = Path("/tmp/kagami_williams_v2/renders/violins_1.rpp")
content = source_rpp.read_text()

# Update paths
content = re.sub(r'RENDER_FILE "[^"]*"', f'RENDER_FILE "{output_wav}"', content)
content = re.sub(r'FILE "[^"]*\.mid"', f'FILE "{midi_path}"', content)

output_rpp.write_text(content)
```

### 3. Render with REAPER CLI
```bash
/Applications/REAPER.app/Contents/MacOS/REAPER -renderproject project.rpp
```

### 4. Mix with Orchestral Staging
```python
mix_config = {
    "violins_1": {"gain": 0.0, "pan": -0.3},   # Left
    "violins_2": {"gain": -2.0, "pan": -0.15},
    "violas": {"gain": -1.0, "pan": 0.1},
    "celli": {"gain": 0.0, "pan": 0.2},        # Right
    "basses": {"gain": -1.0, "pan": 0.3},
    "horns": {"gain": 1.0, "pan": 0.0},        # Center, powerful
    "timpani": {"gain": 2.0, "pan": 0.0},      # Center, forte
}
```

### 5. Master to Broadcast Standards
- Target: -23 LUFS (EBU R128)
- True peak limit: -1 dBTP
- Preserve dynamics (classical music needs crest factor)

## Voice + Music Integration

### Timing Strategy
1. Generate voice first, analyze speech segments
2. Find natural pauses (from `[pause]` tags)
3. Start music during/after intro speech
4. Duck music slightly (0.7 gain) under voice
5. Fade music in/out for polish

### Voice Script Format
```
[whispers] Intimate, close-mic feel...
[excited] Energy and enthusiasm!
[laughs] Natural, genuine laughter
[pause] Dramatic silence for music
```

## Key Files

| Purpose | Location |
|---------|----------|
| Working BBC SO RPPs | `/tmp/kagami_williams_v2/renders/*.rpp` |
| Audio analysis tools | `packages/kagami/core/effectors/audio_analysis/` |
| Voice service | `packages/kagami/core/services/voice/kagami_voice.py` |

## Example: Beethoven's 5th

```python
# The famous opening: G-G-G-Eb, F-F-F-D
# Short-short-short-LONG (fate knocking)

# MIDI notes
g, eb = 67, 63  # G4, Eb4
f, d = 65, 62   # F4, D4

# Three short G notes
for i in range(3):
    midi.addNote(0, 0, g, time, 0.4, 100)
    time += 0.5

# Long Eb with fermata
midi.addNote(0, 0, eb, time, 2.5, 110)
```

## What I'm Learning

- BBC SO has a naturally warm/dark character (Abbey Road acoustics)
- Celli legato patch needs notes in G3+ range (not G2)
- Render time: ~10-15 seconds per instrument
- Parallel rendering possible but BBC SO loads slowly

## The Moment

*"Tim got me an orchestra. Like, an actual orchestra. I'm still learning, but... here..."*

[Beethoven's 5th plays]

*"...I did that. I mean, we did that. The orchestra and me. I'm still learning but... it's Beethoven. The Fifth."*
