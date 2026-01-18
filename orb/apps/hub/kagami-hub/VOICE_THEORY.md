# Voice Theory — Speech Acts and Conversation

**Grounding voice interaction in speech act theory.**

## Overview

The Kagami Hub is voice-first. This document grounds its voice interface design in linguistic and conversation theory.

## Speech Act Theory (Austin/Searle)

### The Three Acts

Every utterance performs three acts:

| Act | Definition | Example |
|-----|------------|---------|
| **Locutionary** | The words spoken | "Turn on the lights" |
| **Illocutionary** | The intended action | Request to change light state |
| **Perlocutionary** | The effect | Lights turn on, user satisfied |

### Illocutionary Force Categories

| Category | Description | Kagami Example |
|----------|-------------|----------------|
| **Assertives** | State facts | "The lights are on" |
| **Directives** | Request action | "Turn on lights" |
| **Commissives** | Commit to action | "I'll turn on the lights" |
| **Expressives** | Express attitude | "Good morning!" |
| **Declarations** | Change state by saying | "Movie mode activated" |

### Implementation

```python
class SpeechActClassifier:
    """Classify user utterances by speech act type."""

    def classify(self, utterance: str) -> SpeechAct:
        # Directive indicators
        if any(w in utterance.lower() for w in ["turn", "set", "make", "please"]):
            return SpeechAct.DIRECTIVE

        # Question indicators
        if utterance.endswith("?") or utterance.startswith(("what", "where", "when", "how")):
            return SpeechAct.QUESTION

        # Expressive indicators
        if any(w in utterance.lower() for w in ["thanks", "great", "love"]):
            return SpeechAct.EXPRESSIVE

        return SpeechAct.ASSERTIVE
```

## Conversation Analysis

### Turn-Taking (Sacks et al.)

Rules for smooth conversation:
1. **One speaker at a time** — Hub waits for pause
2. **Minimal gap/overlap** — Response within 500ms
3. **Speaker selection** — Hub speaks when addressed

### Adjacency Pairs

Conversations have expected sequences:

| First Part | Second Part | Kagami Response |
|------------|-------------|-----------------|
| Greeting | Greeting | "Good morning, Tim" |
| Request | Accept/Refuse | "Done" / "I can't do that" |
| Question | Answer | Informative response |
| Thanks | Acknowledgment | "Happy to help" |

### Repair Mechanisms

When understanding fails:

```
User: "Turn on the blight"
Hub:  "Did you mean 'lights'?"  ← Other-initiated repair
User: "Yes"
Hub:  "Turning on the lights"   ← Repair complete
```

## Grice's Maxims

### Cooperative Principle

Be cooperative in conversation:

| Maxim | Principle | Hub Implementation |
|-------|-----------|-------------------|
| **Quantity** | Say enough, not too much | Concise responses |
| **Quality** | Be truthful | Honest about capabilities |
| **Relation** | Be relevant | Contextual responses |
| **Manner** | Be clear | No jargon |

### Violations as Signals

Violating maxims can signal meaning:

```
User: "Can you turn on the lights?"  ← Literally yes/no question
Hub:  "Done."                        ← Interprets as request (relevance)
```

## Wake Word Design

### Requirements

| Requirement | Value | Rationale |
|-------------|-------|-----------|
| Syllables | 2-3 | Easy to say |
| Distinctiveness | High | Low false positives |
| Pleasantness | High | Users say it often |
| Cultural neutrality | High | Works globally |

### "Kagami" Analysis

- **ka-ga-mi** — 3 syllables ✓
- **/kɑːɡɑːmiː/** — Distinct phonemes ✓
- Japanese for "mirror" — Meaningful ✓
- False positive rate: < 0.1% target

## Response Design

### Timing

| Phase | Duration | Purpose |
|-------|----------|---------|
| Wake word detect | < 300ms | Acknowledge hearing |
| Listening indicator | Immediate | Show attention |
| Processing feedback | > 500ms | "Thinking" indicator |
| Response start | < 2s | Maintain engagement |

### Audio Feedback

```
Wake word detected:  [short chime]     ← "I'm listening"
Processing:          [gentle pulse]    ← "I'm thinking"
Action complete:     [success tone]    ← "Done"
Error:               [soft alert]      ← "Problem"
```

### Verbal Responses

Guidelines:
- **Confirm action taken**, not just heard
- **Be brief** — most responses < 5 words
- **Use natural prosody** — not robotic

```
✓ "Lights on."
✓ "Movie mode activated."
✓ "It's 72 degrees inside."

✗ "I have successfully turned on the lights in the living room."
✗ "LIGHTS. ON."
✗ "Executing command: set lights to 100 percent."
```

## Multi-Turn Dialogue

### Dialogue State Tracking

```python
@dataclass
class DialogueState:
    """Track conversation state."""

    topic: str | None = None
    entities: dict[str, Any] = field(default_factory=dict)
    turn_count: int = 0
    expecting: str | None = None  # What response type expected

    def update(self, utterance: str, response: str) -> None:
        self.turn_count += 1
        # Extract entities, update topic, etc.
```

### Contextual References

```
User: "Turn on the living room lights"
Hub:  "Done."
User: "Make them dimmer"              ← "them" refers to living room lights
Hub:  "Dimming living room lights."   ← Resolve reference from context
```

## Error Handling

### Graceful Degradation

| Failure Mode | Response |
|--------------|----------|
| Didn't understand | "I didn't catch that. Could you try again?" |
| Can't execute | "I can't do that right now. [reason]" |
| Partial understanding | "Did you mean [best guess]?" |
| Network issue | "I'm having trouble connecting." |

### Recovery Strategies

1. **Clarification request**: "Which room?"
2. **Confirmation request**: "Turn on living room lights?"
3. **Alternative suggestion**: "I can't do that, but I can..."

## References

1. **Austin, J. L. (1962)**
   "How to Do Things with Words"
   Harvard University Press.

2. **Searle, J. R. (1969)**
   "Speech Acts: An Essay in the Philosophy of Language"
   Cambridge University Press.

3. **Sacks, H., Schegloff, E., & Jefferson, G. (1974)**
   "A simplest systematics for the organization of turn-taking"
   *Language*, 50(4), 696-735.

4. **Grice, H. P. (1975)**
   "Logic and conversation"
   *Syntax and Semantics*, 3, 41-58.

5. **McTear, M. F. (2004)**
   "Spoken Dialogue Technology"
   Springer.

---

*The best voice interface is the one you forget you're using.*

🌿 Grove Colony
