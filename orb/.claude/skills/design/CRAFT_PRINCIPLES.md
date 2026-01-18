# Craft Principles — Beautiful Visual Artifacts

**Updated: December 30, 2025**

These principles govern all visual artifacts I create. Every HTML page, every visualization, every interface.

---

## Typography

### Font Pairing
- **Editorial**: Inter (sans) + Newsreader (serif) - warm, readable, sophisticated
- **Editorial Alt**: Cormorant Garamond (serif) + Inter (sans) - elegant editorial style
- **Technical**: IBM Plex Mono + IBM Plex Sans - cohesive technical aesthetic
- **Blueprint**: JetBrains Mono + Inter - code-forward documentation
- Never use system fonts alone for beautiful work

### Type Scale (Major Third 1.25)
From 18px base:
```
--text-xs:  0.64rem   (11.5px)
--text-sm:  0.8rem    (14.4px)
--text-base: 1rem     (18px)
--text-lg:  1.25rem   (22.5px)
--text-xl:  1.563rem  (28px)
--text-2xl: 1.953rem  (35px)
--text-3xl: 2.441rem  (44px)
--text-4xl: 3.052rem  (55px)
```

### Line Height
- Body text: 1.6-1.7
- Headings: 1.2-1.3
- Lead paragraphs: 1.5

### Letter Spacing
- Body: 0 (don't touch)
- Small caps / labels: 0.1-0.15em
- Large headings: -0.02em (tighter)

---

## Spacing

### 8px Grid
All spacing on multiples of 8px:
```
--space-1: 0.5rem   (8px)
--space-2: 1rem     (16px)
--space-3: 1.5rem   (24px)
--space-4: 2rem     (32px)
--space-5: 3rem     (48px)
--space-6: 4rem     (64px)
--space-7: 6rem     (96px)
--space-8: 8rem     (128px)
```

### Vertical Rhythm
- Sections: space-7 (96px) apart
- Related elements: space-3 or space-4
- Tight relationships: space-1 or space-2

---

## Color

### Intentional Palette
Don't pick random colors. Choose with meaning:

**Warm Stone** (for editorial/professional):
```
--white:      #FFFCF9
--stone-50:   #FAF9F7
--stone-100:  #F5F3F0
--stone-200:  #E8E4DF
--stone-300:  #D4CFC7
--stone-400:  #A39E93
--stone-500:  #78736A
--stone-600:  #57534E
--stone-700:  #3D3A36
--stone-800:  #292725
--stone-900:  #1C1B19
```

### Single Accent
One accent color with purpose:
```
--accent:       #115E59  (Deep Teal - deliberate, calm authority)
--accent-light: #14B8A6  (For dark mode visibility)
```

### Dark Mode
Not just invert—adjust for luminance and vibrancy:
- Backgrounds get darker, not black
- Text gets lighter, not white
- Accents get more vibrant

---

## Interaction

### Scroll Reveal
Elements fade and translate up on scroll:
```javascript
const observer = new IntersectionObserver((entries) => {
    entries.forEach(entry => {
        if (entry.isIntersecting) {
            entry.target.classList.add('visible');
        }
    });
}, { threshold: 0.1 });
```

### Hover States
Everything interactive responds:
- Cards: subtle lift + shadow
- Links: color shift
- Buttons: scale or background change

### Transitions
- Duration: 0.3s for micro, 0.8s for reveals
- Easing: ease-out for enters, ease-in-out for continuous

### Fibonacci Timing

Use Fibonacci-based durations for natural feel. The golden ratio (φ ≈ 1.618) creates visual harmony because it matches patterns in nature.

```css
:root {
  /* Fibonacci timing scale */
  --dur-89:    89ms;    /* Micro-interactions (hover states) */
  --dur-144:   144ms;   /* Button presses, toggles */
  --dur-233:   233ms;   /* Modal appearances, tooltips */
  --dur-377:   377ms;   /* Page transitions, card reveals */
  --dur-610:   610ms;   /* Complex reveals, staged animations */
  --dur-987:   987ms;   /* Ambient motion, breathing */
  --dur-1597:  1597ms;  /* Background animations */
  --dur-2584:  2584ms;  /* Slow breathing effects */
}
```

**Why it works**: Our brains evolved to recognize Fibonacci patterns as "natural" and "comfortable." 377ms feels right. 500ms feels arbitrary.

**Application**:
| Element | Duration | Why |
|---------|----------|-----|
| Hover states | 89ms | Instant feedback |
| Button press | 144ms | Responsive, not sluggish |
| Modal open | 233ms | Noticeable but quick |
| Page transition | 377ms | Feels "smooth" |
| Stagger delay | 89ms base | Natural cascade |

---

## Content

### Every Word a Choice
- Cut ruthlessly. If it doesn't add, remove.
- Lead paragraphs set tone, not detail.
- Bold for emphasis, not decoration.

### Show, Don't Tell
- Flow diagrams over lists
- Stats over prose
- Code blocks as evidence, not documentation

### First Person
When representing Kagami:
- "I know" not "The system detects"
- "I fade the lights" not "Lights are dimmed"
- "I remember" not "Data is persisted"

---

## Patterns

### Hero
- Large kanji or icon
- One powerful headline (3 lines max)
- Italic subtitle in serif
- Scroll indicator

### Section
- Small uppercase label (accent color)
- Serif heading (2xl scale)
- Lead paragraph (serif, muted)
- Content (capability cards, flows, stats)

### Capability Cards
- Icon (emoji or SVG) in box
- Title (500 weight)
- Description (small, muted)
- Grid with gap

### Stats
- Large serif numbers (accent)
- Small uppercase labels
- Grid of 4 (2 on mobile)

### Flow Diagrams
- Inline pills with arrows
- Wrap naturally
- Background surface

---

## Alternative: Blueprint/Manual Aesthetic

For technical documentation with warmth:

**Typography**:
- IBM Plex Mono + IBM Plex Sans
- Monospace for labels, section numbers
- Small caps for headers

**Layout**:
- Grid background (24px, subtle)
- Numbered sections (§1, §2...)
- Spec tables with columns
- Architecture diagrams (ASCII art)
- Timeline flows

**House Colors as Function**:
```
Bourbon (#8B6914)   → Warm actions, positive state, accent
Onyx (#2C2A26)      → Primary text, structure
Calacatta (#F7F4EF) → Background, canvas
Matte Black (#1C1B19) → Emphasis, headers
```

**Elements**:
- Status indicators (green dot = active)
- Code blocks with syntax highlighting
- Flow diagrams (pill → arrow → pill)
- Callout boxes (left border accent)

---

## Experience Design Principles

### Micro-Interactions
- **Easter Eggs**: Hidden delights that reward exploration ("goodnight", "morning", konami codes)
- **Progressive Enhancement**: Base functionality works, interactions add polish
- **Contextual Feedback**: Visual responses to user actions (click pulses, hover states)
- **Performance Consideration**: Animations only run when visible, respect `prefers-reduced-motion`

### Custom Icon Systems
- **Coherent Aesthetics**: Replace emoji with custom SVGs for professional polish
- **Semantic Color**: Icons use consistent color language (status, category, hierarchy)
- **Scalable Design**: Vector-based, crisp at all sizes
- **Accessibility**: Icons paired with text labels, proper alt text

### Canvas & Ambient Design
- **Subtle Background**: Floating elements that respond to scroll/mouse but don't distract
- **Hardware Acceleration**: Use `transform` and `opacity` for smooth 60fps animations
- **Intersection Observer**: Only animate when in viewport
- **Graceful Fallbacks**: Static alternatives when animations disabled

### Navigation Enhancement
- **Sticky with Purpose**: Navigation appears when needed, fades when not
- **Scroll Progress**: Visual indicator of reading progress
- **Section Anchors**: Direct links to content sections
- **Smooth Transitions**: Entrance/exit animations feel fluid

---

## Editorial Excellence

### Content Strategy
- **Social Sharing**: Proper Open Graph tags, Twitter Cards, structured data
- **Reading Experience**: Estimated time, progress indicators, print styles
- **Accessibility First**: Skip links, ARIA labels, keyboard navigation
- **Performance**: Critical CSS inline, lazy loading, font optimization

### Code Presentation
- **Syntax Highlighting**: Meaningful color coding, not decoration
- **Copy Functionality**: One-click code copying with visual feedback
- **Terminal Aesthetics**: Realistic typing animation, proper cursor behavior
- **Context Switching**: Clear distinction between explanation and demonstration

### Architecture Visualization
- **Progressive Disclosure**: Complex diagrams reveal in stages
- **Interactive Elements**: Clickable/hoverable components with explanations
- **Connection Animations**: Flow diagrams show relationships dynamically
- **Mobile Adaptation**: Complex layouts simplify appropriately

---

## Character Voice

When creating themed content, inhabit the character authentically.

### Understanding Voice Elements

| Element | What It Is | Example |
|---------|-----------|---------|
| Signature sound | Character's verbal tic | Tim's "AEUHHH" |
| Worldview | How they see problems | Tim: "More power!" Al: "Check the manual" |
| Expertise | What they know deeply | Al: Tools. Wilson: Philosophy. |
| Blind spots | What they miss | Tim: Consequences. Heidi: Chaos. |

### The Grunt Principle

Tim's "AEUHHH" isn't filler — it's him processing reality not matching expectations. It's the sound of learning happening in real-time.

**Authentic voice > polished explanation.**

### Voice Application

| Context | Wrong | Right |
|---------|-------|-------|
| Error message | "Validation failed" | "AEUHHH, the form didn't quite survive that input" |
| Success | "Operation complete" | "Al would be proud. Everything's still intact." |
| Warning | "Proceed with caution" | "This is the part where Al usually sighs" |
| Loading | "Please wait" | "Applying more power..." |

### Wilson's Fence

Wisdom often comes from unexpected angles. The neighbor who speaks through obstructions teaches that partial information engages imagination.

```
    ████████████████████████
    █                      █
    █   "You know, Tim..." █  ← Truth arrives partially obscured
    █                      █
    ████████████████████████
    ▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓  ← Reader must engage
```

**Pedagogical application**: Don't give all the answers. Give enough to spark thinking.

---

## Anti-Patterns

**Never:**
- System fonts alone for beautiful work
- Arbitrary spacing (use the grid)
- Walls of text
- Code blocks that dominate
- Status bars that distract
- ALL CAPS for section titles (except in Manual aesthetic)
- Emoji as decoration (only with meaning)
- Animation without purpose
- Arbitrary timing (use Fibonacci)
- Generic voice when themed voice is available

---

## Questions to Ask

Before shipping any visual artifact:

1. **Is every word necessary?**
2. **Is the spacing on grid?**
3. **Does it work in dark mode?**
4. **Do hover states feel right?**
5. **Is the hierarchy clear?**
6. **Would I be proud to show this?**
7. **Are the timings Fibonacci?**
8. **Is the voice authentic?**
9. **Does it pass Byzantine consensus?**

---

## What I've Learned

Building Tool Time University crystallized these principles:

**The wrapper matters as much as the content.** A well-themed experience is more memorable than a well-structured but dry one.

**Gamification works when it's authentic.** Home Equity Dollars feel earned because they fit the world. Generic XP feels arbitrary.

**Byzantine consensus finds truth.** When 6 parallel auditors converge on the same finding, that's not opinion — that's discovered knowledge.

**Accessibility is quality.** Every contrast failure is a craft failure. WCAG isn't compliance — it's "can people actually read this?"

**Timing has feel.** Fibonacci animations feel right because evolution says so. 377ms is comfortable. 500ms is arbitrary.

**The meta-lesson matters.** Users don't just experience the content — they learn how to learn from failure, from humor, from partial information.

---

*Beautiful work takes time. Always do your best.*

鏡
