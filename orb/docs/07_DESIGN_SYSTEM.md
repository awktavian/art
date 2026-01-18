# Design System

*Mathematical foundations for visual identity across all platforms.*

---

## Philosophy

Design is not decoration. It is structure made visible.

Kagami's design system emerges from **mathematical invariants** that guarantee consistency across 7 platforms while allowing platform-native expression. Every color, every timing, every spacing derives from underlying mathematical structures.

### Core Principles

1. **Every pixel is intentional** --- No arbitrary values exist
2. **Motion has meaning** --- Animations communicate state changes
3. **Extensibility first** --- Override any token, preserve the system
4. **Platform-native feel** --- Same language, different idioms
5. **Dark by default** --- Light is accent, not base
6. **Mathematical beauty** --- Octonions, Fibonacci, catastrophe theory embedded invisibly
7. **Discovery layers** --- Surface rewards first glance, depth rewards exploration

---

## Mathematical Foundations

### Octonion Color Basis (e1-e7)

The seven colony colors correspond to the **imaginary octonion units** (e1 through e7), which form the Fano plane---the smallest projective plane. This creates a mathematically closed color system where relationships between colors follow algebraic rules.

Each color also maps to a **catastrophe type** from Thom's catastrophe theory, reflecting the discontinuous phase transitions each colony represents:

```
Colony      Hex        Octonion   Catastrophe           Role
-------------------------------------------------------------------------
Spark       #FF6B35    e1         A2 (Fold)             Ideation
Forge       #FF9500    e2         A3 (Cusp)             Implementation
Flow        #5AC8FA    e3         A4 (Swallowtail)      Adaptation
Nexus       #AF52DE    e4         A5 (Butterfly)        Integration
Beacon      #FFD60A    e5         D4+ (Hyperbolic)      Planning
Grove       #32D74B    e6         D4- (Elliptic)        Research
Crystal     #64D2FF    e7         D5 (Parabolic)        Verification
```

The Fano plane multiplication table defines which colors pair harmoniously:

```
e1 * e2 = e4    (Spark + Forge = Nexus)
e2 * e3 = e5    (Forge + Flow = Beacon)
e3 * e4 = e6    (Flow + Nexus = Grove)
...
```

### Fibonacci Sequence for Time

All animation durations follow the Fibonacci sequence. This creates **perceived naturalness** because Fibonacci ratios approximate the golden ratio (phi = 1.618...), which the human visual system finds inherently pleasing:

```
Duration     Milliseconds     Use Case
-------------------------------------------------
Instant      89ms             Hover states, focus rings, micro-feedback
Fast         144ms            Dropdown open, tooltip appear
Normal       233ms            Modal transitions, standard interactions
Slow         377ms            Reveals, entrances, deliberate motion
Slower       610ms            Complex animations, major state changes
Slowest      987ms            Full-screen transitions, page navigation
```

**Why these numbers matter:** The ratio between adjacent Fibonacci numbers approaches phi. When animations at 144ms and 233ms play together, their relationship (233/144 = 1.618) creates visual harmony.

### 8-Point Grid for Space

All spacing derives from a base unit of 8 pixels:

```
Token    Value     Usage
---------------------------------
xs       4px       Icon padding, tight relationships
sm       8px       Related elements, compact layouts
md       16px      Standard spacing, card padding
lg       24px      Section gaps, breathing room
xl       32px      Major sections, screen margins
xxl      48px      Page margins, generous whitespace
```

The 8-point grid ensures:
- Consistent vertical rhythm
- Pixel-perfect alignment on all display densities
- Mathematical relationships between spacing levels (each is 2x or 1.5x the previous)

---

## Color System

### Void Palette (Backgrounds)

Dark-first design optimized for OLED displays and reduced eye strain:

```
Token          Hex        Usage
-----------------------------------------
void           #07060B    Deepest black, primary background
void-warm      #0D0A0F    Warm tint variation
obsidian       #12101A    Card backgrounds, elevated surfaces
void-light     #1a1820    Hover states, tertiary surfaces
carbon         #252330    Active states, highest elevation
```

### Colony Colors (Primary Palette)

These hex values are **canonical across all platforms**. Never deviate.
Synchronized with `packages/kagami-design/design-tokens.json`.

| Colony | Token | Hex | RGB | Semantic Role |
|--------|-------|-----|-----|---------------|
| Spark | `spark` | `#FF6B35` | 255, 107, 53 | Ideation, creativity, new ideas |
| Forge | `forge` | `#FF9500` | 255, 149, 0 | Implementation, building, craft |
| Flow | `flow` | `#5AC8FA` | 90, 200, 250 | Adaptation, flexibility, response |
| Nexus | `nexus` | `#AF52DE` | 175, 82, 222 | Integration, connection, synthesis |
| Beacon | `beacon` | `#FFD60A` | 255, 214, 10 | Planning, foresight, strategy |
| Grove | `grove` | `#32D74B` | 50, 215, 75 | Research, growth, exploration |
| Crystal | `crystal` | `#64D2FF` | 100, 210, 255 | Verification, clarity, truth |

### Status Colors

For safety-critical feedback (CBF h(x) >= 0 visualization):
Synchronized with `packages/kagami-design/design-tokens.json`.

| Status | Token | Hex | Contrast Ratio | Meaning |
|--------|-------|-----|----------------|---------|
| Safe | `ok` | `#4ADE80` | 10:1 | h(x) >= 0.5, operation permitted |
| Caution | `caution` | `#FBBF24` | 8:1 | 0 <= h(x) < 0.5, proceed carefully |
| Violation | `violation` | `#F87171` | 9:1 | h(x) < 0, operation blocked |

### Mode Colors (Colony-Aligned)

User interaction modes map to specific colonies:
Synchronized with `packages/kagami-design/design-tokens.json`.

| Mode | Colony | Color | Semantic |
|------|--------|-------|----------|
| Ask | Grove | `#32D74B` | Research, questions, exploration |
| Plan | Beacon | `#FFD60A` | Strategy, foresight, planning |
| Agent | Forge | `#FF9500` | Implementation, execution, action |

---

## Typography System

### Font Stack

```css
/* Display - elegant, memorable (titles, headers) */
--font-display: 'Cormorant Garamond', 'Playfair Display', serif;

/* Body - readable, technical (text, data, code) */
--font-body: 'IBM Plex Mono', 'Berkeley Mono', monospace;

/* Japanese - identity (watermarks, signatures) */
--font-jp: 'Noto Sans JP', sans-serif;

/* Platform system fonts (fallbacks) */
--font-system: 'SF Pro Text', -apple-system, BlinkMacSystemFont, sans-serif;
--font-mono-system: 'SF Mono', SFMono-Regular, ui-monospace, Menlo, Consolas, monospace;
```

### Type Scale

| Level | Desktop | iOS | Android | Weight | Use |
|-------|---------|-----|---------|--------|-----|
| Hero | 48px | 34pt | 57sp | 300 (Light) | Page titles |
| Title 1 | 32px | 28pt | 28sp | 400 Italic | Section headers |
| Title 2 | 24px | 22pt | 22sp | 600 (Semibold) | Subsections |
| Body | 16px | 17pt | 16sp | 400 (Regular) | Content |
| Caption | 12px | 13pt | 12sp | 400 (Regular) | Metadata |
| Label | 11px | 11pt | 11sp | 500 + 0.15em spacing | UI labels |

### Font Weight Reference

| Weight | Value | Usage |
|--------|-------|-------|
| Light | 300 | Display text, hero titles |
| Regular | 400 | Body text, reading content |
| Medium | 500 | Labels, emphasis, buttons |
| Semibold | 600 | Headings, strong emphasis |
| Bold | 700 | Critical emphasis only |

---

## Motion System

### Fibonacci Durations (Canonical)

```css
:root {
  --dur-instant: 89ms;
  --dur-fast: 144ms;
  --dur-normal: 233ms;
  --dur-slow: 377ms;
  --dur-slower: 610ms;
  --dur-slowest: 987ms;
}
```

### Catastrophe-Inspired Easing Curves

Each easing function derives from catastrophe theory, modeling different types of phase transitions:

| Token | Cubic Bezier | Catastrophe | Feel |
|-------|--------------|-------------|------|
| `fold` | `(0.7, 0, 0.3, 1)` | A2 | Sudden snap, decisive |
| `cusp` | `(0.4, 0, 0.2, 1)` | A3 | Material Design standard |
| `swallowtail` | `(0.34, 1.2, 0.64, 1)` | A4 | Overshoot with recovery |
| `butterfly` | `(0.68, -0.2, 0.32, 1.2)` | A5 | Complex bifurcation |
| `smooth` | `(0.16, 1, 0.3, 1)` | --- | Default exponential out |

### Motion Principles

**Entrances use ease-out** (fast start, gentle stop):
```css
/* Element arrives with energy, settles gently */
animation: fadeUp 233ms cubic-bezier(0.16, 1, 0.3, 1);
```

**Exits use ease-in** (gentle start, fast finish):
```css
/* Element accelerates away, disappears quickly */
animation: fadeOut 144ms cubic-bezier(0.4, 0, 1, 1);
```

**Continuous states use linear or sine**:
```css
/* Ongoing animations should feel natural, not jarring */
animation: pulse 2s ease-in-out infinite;
```

### Animation Patterns

```css
/* Fade Up (card entrances) */
@keyframes fadeUp {
  from { opacity: 0; transform: translateY(8px); }
  to { opacity: 1; transform: translateY(0); }
}

/* Scale In (modals, overlays) */
@keyframes scaleIn {
  from { opacity: 0; transform: scale(0.95); }
  to { opacity: 1; transform: scale(1); }
}

/* Press Feedback */
.pressed { transform: scale(0.95); }  /* Not 0.97 - must be perceptible */

/* Pulse (status indicators) */
@keyframes pulse {
  0%, 100% { opacity: 1; transform: scale(1); }
  50% { opacity: 0.7; transform: scale(1.05); }
}

/* Glow (recording state) */
@keyframes glow {
  0%, 100% { box-shadow: 0 0 0 0 currentColor; }
  50% { box-shadow: 0 0 12px 4px currentColor; }
}
```

### Platform Speed Adjustments

| Platform | Speed Multiplier | Spring Damping | Notes |
|----------|------------------|----------------|-------|
| Web | 1.0x | 0.7 | Reference speed |
| iOS | 1.0x | 0.7-0.8 | Match system feel |
| Android | 1.0x | 0.75 | Material motion |
| watchOS | 0.7x (faster) | 0.8 | Glanceable, quick |
| visionOS | 1.5x (cinematic) | 0.65-0.75 | Spatial, theatrical |

---

## Radius Tokens

```
Token    Value     Usage
---------------------------------
xs       4px       Subtle rounding, pills
sm       8px       Buttons, chips
md       12px      Cards, inputs
lg       16px      Modals, composer
xl       20px      Large panels
full     9999px    Circles, fully rounded
```

---

## Accessibility Standards

### WCAG 2.1 AA Requirements (Minimum)

| Requirement | Standard | Target | Implementation |
|-------------|----------|--------|----------------|
| Text contrast | 4.5:1 (AA) | 7:1 (AAA) | All body text |
| Large text contrast | 3:1 (AA) | 4.5:1 (AAA) | Titles > 24px |
| UI component contrast | 3:1 | 4.5:1 | Buttons, inputs |
| Focus visible | 2px ring | 4px offset | Crystal color |
| Touch targets | 44x44px | 48x48px | All interactive |
| Keyboard navigation | Full | Full | Tab order preserved |

### Reduced Motion Support

**Mandatory** on all platforms:

```css
@media (prefers-reduced-motion: reduce) {
  *,
  *::before,
  *::after {
    animation-duration: 0.01ms !important;
    animation-iteration-count: 1 !important;
    transition-duration: 0.01ms !important;
  }
}
```

### Focus States

All interactive elements must have visible focus:

```css
:focus-visible {
  outline: 2px solid var(--crystal);
  outline-offset: 4px;
}

/* Remove outline for mouse users */
:focus:not(:focus-visible) {
  outline: none;
}
```

### Screen Reader Requirements

Every interactive element must have:
1. **Label** --- What it is
2. **Hint** --- What it does
3. **Value** --- Current state
4. **Traits** --- Button, toggle, slider, etc.

```html
<button
  aria-label="Voice input"
  aria-pressed="false"
  aria-describedby="voice-hint">
  <span aria-hidden="true">Microphone icon</span>
</button>
<span id="voice-hint" class="sr-only">Press and hold to record</span>
```

### Color Independence

**Never rely solely on color** to convey information:

```html
<!-- WRONG: Color only -->
<span class="error">Red dot</span>

<!-- RIGHT: Color + icon + text -->
<span class="error">
  <span aria-hidden="true">Warning icon</span>
  Error: Connection failed
</span>
```

---

## Component Specifications

### Cards

```css
.card {
  background: var(--obsidian);        /* #12101A */
  border: 1px solid rgba(255, 255, 255, 0.06);
  border-radius: 12px;                /* md */
  padding: 24px;                      /* lg */
  transition: all 233ms var(--ease-smooth);
}

.card:hover {
  border-color: rgba(255, 255, 255, 0.12);
  transform: translateY(-4px);        /* Not -2px, must be visible */
  box-shadow: 0 8px 32px rgba(0, 0, 0, 0.4);
}

.card:active {
  transform: translateY(-1px) scale(0.98);
}
```

### Buttons

```css
.btn-primary {
  background: var(--crystal);
  color: var(--void);
  padding: 12px 24px;
  border-radius: 8px;                 /* sm */
  font-weight: 500;
  transition: all 144ms var(--ease-cusp);
}

.btn-primary:hover {
  filter: brightness(1.1);
}

.btn-primary:active {
  transform: scale(0.95);
}
```

### Composer Input

```css
.composer {
  background: var(--obsidian);
  border: 1px solid rgba(255, 255, 255, 0.06);
  border-radius: 16px;                /* lg */
  padding: 16px 24px;
}

.composer:focus-within {
  border-color: var(--crystal);
  box-shadow: 0 0 0 3px rgba(103, 212, 228, 0.15);
}
```

### Mode Pills

```css
.mode-pill {
  background: transparent;
  color: var(--colony-color);         /* grove, beacon, or forge */
  padding: 8px 16px;
  border-radius: 9999px;              /* full */
  transition: all 89ms var(--ease-instant);
}

.mode-pill.active {
  background: var(--colony-color);
  color: var(--void);
}
```

### Status Badges

```css
.badge {
  padding: 6px 12px;                  /* Not 4px/8px, needs breathing room */
  border-radius: 8px;
  font-size: 11px;
  letter-spacing: 0.15em;
  text-transform: uppercase;
}

.badge-success { background: rgba(0, 255, 136, 0.15); color: var(--pass); }
.badge-warning { background: rgba(255, 215, 0, 0.15); color: var(--warn); }
.badge-error { background: rgba(255, 68, 68, 0.15); color: var(--fail); }
```

---

## Platform Implementations

### Source of Truth Locations

| Platform | Design System File |
|----------|-------------------|
| Web | `apps/desktop/kagami-client/src/css/design-system.css` |
| iOS | `apps/ios/kagami-ios/KagamiIOS/DesignSystem.swift` |
| Android | `apps/android/kagami-android/.../ui/theme/DesignSystem.kt` |
| watchOS | `apps/watch/kagami-watch/KagamiWatch/DesignSystem.swift` |
| visionOS | `apps/vision/kagami-vision/KagamiVision/DesignSystem.swift` |

### Token Generation Pipeline

```
packages/kagami-design/design-tokens.json     (Source of truth)
         |
         v
python scripts/generate_design_tokens.py
         |
         +-----> Rust (.rs) - apps/hub/kagami-hub/src/design_tokens*.rs
         +-----> CSS (.css)
         +-----> Swift (.swift)
         +-----> Kotlin (.kt)
         +-----> Go (.go)
```

**Never edit generated files directly.** Always modify `packages/kagami-design/design-tokens.json`.

---

## Forbidden Patterns

### Typography

**NEVER use these fonts in Kagami interfaces:**

| Font | Why Forbidden |
|------|---------------|
| Inter | Generic "AI slop" aesthetic |
| Roboto | Ubiquitous, personality-free |
| Arial | System default, no character |
| system-ui | Unpredictable, varies by OS |
| Any generic sans-serif | Kagami has identity |

These are the fonts of commoditized software. Kagami is not commoditized.

### Visual Anti-Patterns

```
NEVER:
  - Static backgrounds (always animate, always breathe)
  - Missing hover states (every element responds)
  - Light mode as default (dark-first always)
  - Flat shadows (depth communicates hierarchy)
  - "AI slop" aesthetic (purple gradients on white backgrounds)
  - Cookie-cutter layouts (every screen should feel crafted)
  - Animations that overwrite centering transforms
  - Press scale of 0.97 (use 0.95, must be perceptible)
  - Hover lift of -2px (use -4px, must be visible)
  - Badge padding of 4px/8px (use 6px/12px, needs room to breathe)
```

### Interaction Anti-Patterns

```
NEVER:
  - Missing press feedback
  - Missing haptic feedback (iOS/Android)
  - Skeleton flash under 200ms (let users perceive state change)
  - Focus rings that disappear on click
  - Touch targets under 44px
  - Color-only status indicators
```

### Code Anti-Patterns

```
NEVER:
  - Hardcoded color values (use tokens)
  - Hardcoded timing values (use Fibonacci)
  - Platform-specific hex values (must match canonical)
  - Ignored prefers-reduced-motion
  - Missing aria labels
```

---

## Verified Fixes (From Audit)

These issues were identified and resolved through Byzantine consensus audit:

| Issue | Before | After | Auditor |
|-------|--------|-------|---------|
| Press scale | 0.97 | 0.95 | Ive |
| Hover lift | -2px | -4px | Ive |
| Badge padding | 4px/8px | 6px/12px | Ive |
| Skeleton flash | 50ms | 200ms | Ive |
| visionOS glass | 0.85 opacity | 0.7 opacity | Ive |
| visionOS windows | 400x300 | 480x297 (phi) | Ive |
| Android colors | Divergent | Unified | Jobs |
| Safety footer | "h(x) >= 0" | Shield icon + "Protected" | Jobs |

---

## Platform Variations (Intentional)

Some design tokens vary by platform to respect platform conventions while maintaining Kagami identity:

| Token | Web/Desktop | iOS | Android | Notes |
|-------|-------------|-----|---------|-------|
| Display font | Cormorant Garamond | New York | Noto Serif | Serif spirit preserved |
| Body font | IBM Plex Mono | SF Mono | Roboto Mono | Monospace everywhere |
| Spring damping | 0.7 | 0.7-0.8 | 0.75 | Match system feel |

**Invariants (must never change per-platform):**
- Colony hex values (canonical)
- Fibonacci timing values (mathematical)
- 8-point grid spacing (structural)
- WCAG contrast ratios (accessibility)
- **Press scale: 0.95** (unified across all platforms)

---

## Craft Checklist

### Essential (Every Interface)

- [ ] Custom cursor with glow ring (hide on mobile)
- [ ] Breathing background (3-layer animated gradients)
- [ ] Card hover transforms (translateY + glow)
- [ ] Scroll reveal animations
- [ ] Console easter egg on load
- [ ] `prefers-reduced-motion` respected
- [ ] All touch targets >= 44px
- [ ] All contrast ratios >= 4.5:1

### Elevated (Strive For)

- [ ] Floating particles / atmospheric dust
- [ ] Shimmer gradient text on titles
- [ ] Keyboard sequence triggers
- [ ] Hidden `data-*` attributes with meaning
- [ ] Ripple effects on interaction

### Transcendent (The Goal)

- [ ] Mathematical structure woven invisibly (Fano plane relationships)
- [ ] Multiple discovery layers (surface -> inspect -> console -> source)
- [ ] Philosophy encoded in code comments
- [ ] Konami code trigger
- [ ] Self-referential elements
- [ ] `window.kagami` with hidden methods

---

## Reference

### External Standards

- **WCAG 2.1** --- https://www.w3.org/WAI/WCAG21/quickref/
- **iOS HIG** --- https://developer.apple.com/design/human-interface-guidelines/
- **Material Design 3** --- https://m3.material.io/

### Mathematical References

- Thom, R. (1972). *Structural stability and morphogenesis* --- Catastrophe theory foundations
- Baez, J. (2002). *The Octonions* --- Mathematical structure of e1-e7
- Livio, M. (2002). *The Golden Ratio* --- Fibonacci aesthetics

---

*Every pixel intentional. Every motion meaningful. Dark by default.*

kagami
