# Context Theory — Ubiquitous Computing

**Grounding Watch context awareness in ubicomp research.**

## Overview

The Apple Watch is the paradigm of ubiquitous computing — always present, context-aware, and ambient. Kagami Watch's design is grounded in the foundational research of this field.

## Theoretical Foundations

### Dey's Context Definition (2001)

> "Context is any information that can be used to characterize the situation of an entity."

**Entity types for Kagami Watch**:
- **User**: Tim's location, activity, attention
- **Environment**: Home state, time, weather
- **Device**: Watch state, battery, connectivity

### Weiser's Calm Computing (1991)

> "The most profound technologies are those that disappear."

**Watch application**:
- **Glanceable**: Information visible in < 2 seconds
- **Non-intrusive**: Only surfaces when relevant
- **Peripheral**: Available but not attention-demanding

## Context Dimensions

### Primary Context (Dey)

| Dimension | Source | Watch Implementation |
|-----------|--------|---------------------|
| **Location** | GPS, WiFi | Room detection via home integration |
| **Identity** | User profile | Tim's preferences and patterns |
| **Time** | System clock | Time-of-day appropriate actions |
| **Activity** | HealthKit | Exercise, sleep, work detection |

### Secondary Context

| Dimension | Derived From | Use |
|-----------|--------------|-----|
| **Attention** | Wrist raise, glance duration | Determine detail level |
| **Urgency** | Time, calendar, patterns | Prioritize notifications |
| **Social** | Calendar, presence | Adjust formality |

## Context-Aware Features

### Hero Action Selection

The "most relevant action" uses context scoring:

```python
def score_action(action: Action, context: Context) -> float:
    score = 0.0

    # Time relevance
    if action.typical_time_match(context.time):
        score += 0.3

    # Location relevance
    if action.typical_location_match(context.room):
        score += 0.2

    # Activity relevance
    if action.supports_activity(context.activity):
        score += 0.2

    # Recency (user did this recently)
    if action.recently_used(context.user_history):
        score += 0.15

    # Pattern match (learned behavior)
    if action.matches_pattern(context.patterns):
        score += 0.15

    return score
```

### Complication Updates

Complications update based on context:

| Context | Complication Shows |
|---------|-------------------|
| Morning | "Good morning" + suggested action |
| Work hours | Safety score + quick controls |
| Evening | Scene suggestions |
| Bedtime | Goodnight shortcut |
| Away | Home status summary |

## Attention Management

### Glanceable Design

Research shows Watch glances are < 2 seconds. Design accordingly:

```
┌─────────────────┐
│  🏠 Home        │  ← Status at a glance
│  ●●●○○○○        │  ← Colony activity (7 dots)
│                 │
│  [Movie Mode]   │  ← One clear action
│                 │
│  h(x) = 0.87    │  ← Safety always visible
└─────────────────┘
```

### Notification Triage

Only notify when context suggests high relevance:

| Notification | Show When |
|--------------|-----------|
| Urgent (safety) | Always |
| Important (calendar) | Not in meeting, not sleeping |
| Informational | Only when Watch raised |
| Promotional | Never on Watch |

## Haptic Choreography

### Haptic Language

| Pattern | Meaning | Use |
|---------|---------|-----|
| Single tap | Acknowledgment | Command received |
| Double tap | Completion | Action done |
| Long pulse | Attention needed | Safety alert |
| Rising | Positive | Scene activated |
| Falling | Neutral | System change |

### Scene-Specific Haptics

```swift
func hapticForScene(_ scene: Scene) -> HapticPattern {
    switch scene {
    case .movieMode:
        // Cinematic: rising anticipation
        return .sequence([.light, .medium, .heavy])

    case .goodnight:
        // Calming: slow, soft
        return .sequence([.soft, .pause, .softer])

    case .welcomeHome:
        // Warm: friendly tap
        return .single(.success)

    case .awayMode:
        // Secure: firm confirmation
        return .single(.notification)
    }
}
```

## Privacy in Context

### On-Device Processing

Following Apple's privacy principles:
- **Context computed locally** — no server round-trips
- **Patterns stored locally** — encrypted in Watch
- **Minimal data transfer** — only actions, not context

### Context Minimization

Only collect context needed:

```swift
// ✓ Good: Minimal context for decision
if isEvening && isAtHome {
    suggestMovieMode()
}

// ✗ Bad: Excessive context collection
collectDetailedLocationHistory()
trackAllHealthMetrics()
```

## Implementation

### Context Manager

```swift
class ContextManager {
    /// Current aggregated context
    var current: Context {
        Context(
            time: Date(),
            location: locationService.currentRoom,
            activity: healthService.currentActivity,
            attention: attentionLevel,
            patterns: patternStore.relevantPatterns()
        )
    }

    /// Score an action given current context
    func score(_ action: Action) -> Double {
        action.relevanceScore(for: current)
    }

    /// Get the most relevant action
    func heroAction() -> Action? {
        Action.allCases
            .map { ($0, score($0)) }
            .sorted { $0.1 > $1.1 }
            .first?.0
    }
}
```

## References

1. **Dey, A. K. (2001)**
   "Understanding and Using Context"
   *Personal and Ubiquitous Computing*

2. **Weiser, M. (1991)**
   "The Computer for the 21st Century"
   *Scientific American*

3. **Schilit, B., Adams, N., & Want, R. (1994)**
   "Context-Aware Computing Applications"
   *IEEE Workshop on Mobile Computing*

4. **Apple Watch Human Interface Guidelines (2024)**
   *developer.apple.com/design/human-interface-guidelines/watchos*

---

*The best interface is no interface — the best action is the one you didn't have to choose.*

🔗 Nexus Colony
