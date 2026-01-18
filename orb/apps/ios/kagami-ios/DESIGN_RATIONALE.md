# iOS Design Rationale

**UX theory backing every design decision.**

## Overview

Every interaction in Kagami iOS is grounded in established UX research. This document explains the "why" behind the "what."

## Core Principles

### 1. Fitts's Law

**Law**: Time to acquire target = a + b × log₂(2D/W)

Where D = distance to target, W = target width.

**Application**:
- Primary actions (Hero Action) are **large and central**
- Frequently used controls are **easily reachable** (bottom of screen)
- Destructive actions are **smaller and further** (prevent accidents)

```
┌─────────────────────────────────────────┐
│                                         │
│         [ Hero Action ]                 │ ← Large, central
│         Quick access zone               │
│                                         │
├─────────────────────────────────────────┤
│                                         │
│   Secondary content                     │
│   Less frequent access                  │
│                                         │
├─────────────────────────────────────────┤
│  [Tab] [Tab] [Tab] [Tab] [Tab]         │ ← Bottom, reachable
└─────────────────────────────────────────┘
```

### 2. Recognition Over Recall (Nielsen)

**Principle**: Minimize memory load by making options visible.

**Application**:
- **Room list shows current state** — don't make users remember
- **Scene cards show what will change** — preview before commit
- **Recent actions visible** — no need to recall history

```swift
// ✓ Good: Recognition
RoomRow(room: "Living Room", lightLevel: 75, temperature: 72)

// ✗ Bad: Requires recall
RoomRow(room: "Living Room")  // User must remember current state
```

### 3. Hick's Law

**Law**: Decision time = k × log₂(n + 1), where n = number of choices.

**Application**:
- **Hero Action shows ONE primary action** — no decision paralysis
- **Context actions limited to 3-4** — manageable choices
- **Settings organized hierarchically** — progressive disclosure

```
Hero Action:       1 choice  → ~0ms decision
Context Actions:   3 choices → ~300ms decision
Full Scene List:   10+ choices → Progressive disclosure
```

### 4. Miller's Law

**Law**: Working memory holds 7±2 items.

**Application**:
- **Tab bar has 5 items** — within cognitive limit
- **Room groupings chunk information** — floor by floor
- **Scene suggestions max 4** — easy to scan

### 5. Jakob's Law

**Law**: Users spend most time on other apps; prefer familiar patterns.

**Application**:
- **Standard iOS navigation patterns** — tabs, back buttons
- **Familiar gestures** — swipe, pull-to-refresh
- **SF Symbols** — recognizable iconography

## Information Architecture

### Primary Navigation (Tabs)

| Tab | Purpose | Fitts's Position |
|-----|---------|------------------|
| Home | Overview, Hero Action | Center (primary) |
| Rooms | Spatial navigation | Left-center |
| Voice | Natural interaction | Center |
| Scenes | Preset management | Right-center |
| Settings | Configuration | Right (infrequent) |

### Content Hierarchy

```
1. Hero Action (immediate need)
   └── Most likely next action

2. Safety Score (always visible)
   └── h(x) indicator

3. Quick Actions (frequent)
   └── Lights, TV, Shades

4. Rooms (spatial context)
   └── Current state per room

5. Recent Activity (history)
   └── What just happened
```

## Visual Design

### Typography Scale

Based on Apple HIG, optimized for scanning:

| Element | Size | Weight | Use |
|---------|------|--------|-----|
| Hero Action | 24pt | Semibold | Primary CTA |
| Card Title | 17pt | Semibold | Section headers |
| Body | 15pt | Regular | Content |
| Caption | 13pt | Regular | Secondary info |
| Footnote | 11pt | Regular | Timestamps |

### Color System

Grounded in color psychology:

| Color | Hex | Meaning | Use |
|-------|-----|---------|-----|
| Primary | System Blue | Trust, action | CTAs, links |
| Success | #10B981 | Safety, completion | h(x) > 0.5 |
| Caution | #F59E0B | Attention needed | h(x) 0-0.5 |
| Warning | #EF4444 | Urgent, critical | h(x) < 0 |
| Colony Colors | Various | Identity | Colony indicators |

### Spacing

8-point grid system:

```
4pt  - Tight (icon padding)
8pt  - Compact (related items)
16pt - Standard (card padding)
24pt - Loose (section spacing)
32pt - Generous (screen margins)
```

## Accessibility

### WCAG AA Compliance

| Criterion | Implementation |
|-----------|----------------|
| 4.5:1 contrast | All text passes |
| Touch targets | Min 44×44pt |
| Dynamic Type | Scales 50-300% |
| VoiceOver | Full labeling |
| Reduce Motion | Alternative animations |

### VoiceOver Labels

```swift
// ✓ Good: Descriptive, actionable
.accessibilityLabel("Turn on Living Room lights, currently at 75%")
.accessibilityHint("Double tap to turn off")

// ✗ Bad: Vague, unhelpful
.accessibilityLabel("Light button")
```

## Performance

### Perceived Performance

- **Skeleton screens** during load (< 100ms)
- **Optimistic updates** for local state
- **Haptic feedback** confirms action immediately

### Actual Performance

| Metric | Target | Reason |
|--------|--------|--------|
| Launch | < 1s | User patience threshold |
| Tab switch | < 100ms | Feels instantaneous |
| Command response | < 500ms | Conversational pace |

## References

1. **Fitts, P. M. (1954)**
   "The information capacity of the human motor system"
   *Journal of Experimental Psychology*

2. **Nielsen, J. (1994)**
   "10 Usability Heuristics for User Interface Design"
   *Nielsen Norman Group*

3. **Hick, W. E. (1952)**
   "On the rate of gain of information"
   *Quarterly Journal of Experimental Psychology*

4. **Miller, G. A. (1956)**
   "The magical number seven"
   *Psychological Review*

5. **Apple Human Interface Guidelines (2024)**
   *developer.apple.com/design/human-interface-guidelines*

---

*Good design is invisible — users should achieve goals, not appreciate interfaces.*

🗼 Beacon Colony
