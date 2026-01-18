# Kagami 10x User Journey Matrix

**Comprehensive Cross-Platform User Journeys for Diverse Households**

*Last Updated: January 12, 2026*

---

## Overview

This matrix defines 10 primary user journeys across all Kagami client platforms, mapped to the 13 documented personas. Each journey is designed for Byzantine quality consensus verification across six dimensions:

| Dimension | Target | What It Measures |
|-----------|--------|------------------|
| **Technical** | 90/100 | Correctness, response time, error handling |
| **Aesthetic** | 90/100 | Fibonacci timing, colony colors, visual harmony |
| **Accessibility** | 90/100 | WCAG AAA, screen reader, motor/vision/hearing support |
| **Emotional** | 90/100 | Resonance, connection, trust, delight |
| **Polish** | 90/100 | Attention to detail, edge cases, refinement |
| **Delight** | 90/100 | Joy, surprise, memorable moments |

---

## Platform Reference

| Platform | Primary Interaction | Key Constraints |
|----------|---------------------|-----------------|
| **iOS** | Touch, Siri, Widgets | Battery, network transitions |
| **watchOS** | Digital Crown, Complications | Screen size, glanceable |
| **tvOS** | Siri Remote, Focus navigation | 10-foot UI, lean-back |
| **visionOS** | Hand gestures, Eye tracking | Spatial, proxemic zones |
| **Android** | Touch, Google Assistant, Widgets | Device diversity |
| **WearOS** | Tiles, Complications, Voice | Small screen, battery |
| **AndroidXR** | Hand tracking, Neural input | Spatial, emerging |
| **Desktop** | Keyboard, Menu bar, Tray | Power user, shortcuts |
| **Hub** | Voice pipeline, Wake word | Always-on, ambient |
| **CarPlay** | Siri, Glanceable, Touch | Driving safety critical |

---

## Persona Reference (13 Households)

| ID | Persona | Key Needs |
|----|---------|-----------|
| P1 | Al-Rashid Family | Islamic prayers, Arabic, shift worker, ADHD teen, elderly |
| P2 | Chen-Williams | Deaf couple, blind mother, visual/audio modality split |
| P3 | Sofia Lindqvist | Autistic, shift worker, sensory sensitivities |
| P4 | Rivera-Chen-Park Throuple | Polyamorous, rotating schedules, privacy |
| P5 | Jackson House | College roommates, high turnover, cost splitting |
| P6 | Okonkwo Empty Nesters | Aging in place, fall detection, family dashboard |
| P7 | Mendez-Thompson Birdnesting | Divorced co-parents, custody schedule |
| P8 | Reyes Military Family | Deployment, OPSEC, timezone, presence simulation |
| P9 | Nguyen Immigrant Family | Vietnamese language, lunar calendar, ancestor altar |
| P10 | Haven House | Intentional community, 12 people, consensus |
| P11 | Volkov Caregiver | Dementia care, wandering alerts, shift handoff |
| P12 | O'Connor Widowed | Solo senior, grief sensitivity, isolation alerts |
| P13 | Recovery House | Sober living, curfew, accountability |

---

## Journey 1: Morning Routine Activation

**Platform Focus:** iOS, watchOS, Hub

### Journey Overview

```
User wakes up -> System detects waking -> Activates morning scene
                                       -> Adjusts lights gradually
                                       -> Provides morning briefing
                                       -> Manages household coordination
```

### Persona Mapping

| Persona | Morning Variation | Special Requirements |
|---------|-------------------|---------------------|
| P1 (Al-Rashid) | Fajr prayer wake, Jadda Arabic briefing | Prayer time integration, multi-language |
| P2 (Chen-Williams) | Vibrating bed shaker (Marcus/David), Audio (Helen) | Modality-specific wake |
| P3 (Sofia) | Gradual 20-minute light rise, no audio | Sensory-safe transitions |
| P6 (Okonkwo) | Medication reminder at 7:30am | Health integration |
| P9 (Nguyen) | Vietnamese greeting for Ba Noi, altar lighting | Cultural calendar awareness |
| P11 (Volkov) | Patricia monitored wake, Ana shift start | Dementia care protocol |
| P12 (O'Connor) | Gentle check-in, breakfast reminder | Isolation monitoring |
| P13 (Recovery) | House-wide 6am wake, morning intentions | Accountability structure |

### Platform Interactions

#### iOS (Primary Control)
```
Entry Point: App launch or widget tap
Actions:
  1. Tap "Good Morning" widget (44px+ touch target)
  2. Scene executes with Fibonacci-timed feedback (233ms)
  3. Progress indicators show room-by-room activation
  4. Completion confirmation with colony-colored checkmark

Exit Condition: Morning scene fully executed, confirmation displayed
Duration: 3-8 seconds (scene complexity dependent)
```

#### watchOS (Glanceable)
```
Entry Point: Watch face complication tap or raise to wake
Actions:
  1. Time-aware hero action displayed (5-9 AM = "Start Day")
  2. Digital Crown scroll to customize
  3. Double-tap to execute
  4. Haptic confirmation (success pattern)

Exit Condition: Haptic pulse confirms execution
Duration: 2-4 seconds
```

#### Hub (Voice-First)
```
Entry Point: Wake word "Hey Kagami" or motion detection
Actions:
  1. LED ring pulses Beacon (planning) color
  2. "Good morning. Starting your day."
  3. Scene executes, LED shows Forge (executing)
  4. Completion: "Your morning routine is ready. [briefing]"

Exit Condition: Audio confirmation and briefing complete
Duration: 5-15 seconds (includes briefing)
```

### Critical Checkpoints

| Checkpoint | Validation | Failure Handling |
|------------|------------|------------------|
| Scene initiation | Response < 100ms | Retry with exponential backoff |
| Light transitions | Fibonacci timing (233ms increments) | Graceful degradation |
| Audio output | Clear, appropriate volume | Visual fallback |
| Medication reminder | Confirmation required | Escalation chain |
| Multi-user coordination | No cross-wake interference | Per-user zones |

### Accessibility Requirements

| Need | Implementation |
|------|----------------|
| **Deaf users** | Vibrating bed shaker, visual alerts, no audio-only info |
| **Blind users** | Full VoiceOver, audio wayfinding, no visual-only info |
| **Motor impaired** | Voice control, large touch targets (44px+), switch access |
| **Cognitive** | Simple choices, visual schedules, transition warnings |
| **Autistic** | Gradual transitions, no sudden sounds, predictable patterns |

### Byzantine Quality Mapping

| Dimension | Target Behaviors |
|-----------|------------------|
| **Technical** | < 100ms response, offline-capable, retry logic |
| **Aesthetic** | Fibonacci timing (89, 144, 233ms), colony colors, dark theme |
| **Accessibility** | Multi-modal feedback, screen reader tested, 4.5:1 contrast |
| **Emotional** | Warm greeting, personalized briefing, not robotic |
| **Polish** | No flicker, smooth transitions, consistent state |
| **Delight** | Personalized weather, contextual suggestions |

### Success Criteria

**Visual:**
- Lights rise smoothly over configured duration
- No harsh transitions or flicker
- Colony status indicators animate correctly
- UI state syncs across all devices within 500ms

**Functional:**
- All configured devices respond
- Medication reminders trigger on schedule
- Household members not disturbed unless configured
- Offline queue processes when connectivity restored

---

## Journey 2: Scene Control (Movie Mode)

**Platform Focus:** tvOS, iOS, Desktop, visionOS

### Journey Overview

```
User wants entertainment -> Selects movie mode -> System dims lights
                                               -> Closes shades
                                               -> Optimizes audio
                                               -> Confirms activation
```

### Persona Mapping

| Persona | Movie Mode Variation | Special Requirements |
|---------|----------------------|---------------------|
| P2 (Chen-Williams) | Audio description for Helen, captions for Marcus | Dual accessibility |
| P3 (Sofia) | Sensory-appropriate lighting (not too dark) | Autism accommodation |
| P4 (Throuple) | Privacy mode check before activating | Relationship awareness |
| P5 (Jackson) | Quiet hours check (exam period) | Roommate coordination |
| P6 (Okonkwo) | Grandchildren-safe content filter | Child-safe mode |
| P8 (Reyes) | Presence simulation continues | Security maintenance |

### Platform Interactions

#### tvOS (Primary)
```
Entry Point: Siri Remote navigation or Siri voice command
Actions:
  1. Focus on "Movie Mode" in quick actions grid (D-pad navigation)
  2. Press center button to activate
  3. Confirmation overlay with 3-second countdown
  4. Scene executes with synchronized device control

Exit Condition: All devices confirmed, overlay dismisses
Duration: 4-6 seconds
```

#### iOS (Control)
```
Entry Point: App scene tab or Siri Shortcut
Actions:
  1. Scroll to "Movie Mode" scene card
  2. Tap to preview (optional)
  3. Tap "Activate" button
  4. Progress ring shows completion percentage
  5. Checkmark animation on success

Exit Condition: Checkmark displayed, haptic feedback
Duration: 2-5 seconds
```

#### Desktop (Quick Entry)
```
Entry Point: Option+M keyboard shortcut or command palette
Actions:
  1. Shortcut triggers immediate execution
  2. Toast notification appears (144ms fade-in)
  3. Colony status updates in real-time
  4. Recent actions list shows execution

Exit Condition: Toast confirms, status bar updates
Duration: 1-3 seconds (fastest platform)
```

#### visionOS (Spatial)
```
Entry Point: Gaze at scene panel, pinch to activate
Actions:
  1. Spatial UI presents scene options in arc
  2. Eye tracking highlights "Movie Mode"
  3. Pinch gesture confirms selection
  4. Room darkens with spatial transition
  5. Control panel repositions for viewing

Exit Condition: Spatial transition complete, panel repositioned
Duration: 5-8 seconds (cinematic pacing)
```

### Critical Checkpoints

| Checkpoint | Validation | Failure Handling |
|------------|------------|------------------|
| Shade control | Position confirmation | Manual override prompt |
| Light levels | All zones at target | Per-zone retry |
| Audio routing | Active zone confirmed | Fallback to default |
| TV state | Power on, input selected | Retry or manual |
| Safety check | h(x) >= 0 maintained | Block if unsafe |

### Accessibility Requirements

| Need | Implementation |
|------|----------------|
| **Low vision** | High contrast scene cards, 7:1 ratio |
| **Motor impaired** | Single-action activation, no multi-tap |
| **Deaf** | Visual confirmation only, no audio-only feedback |
| **Blind** | "Movie mode activated. Lights dimming." announcement |
| **Cognitive** | Simple binary choice, clear cancel option |

### Byzantine Quality Mapping

| Dimension | Target Behaviors |
|-----------|------------------|
| **Technical** | All 5+ devices respond within 2s, state consistent |
| **Aesthetic** | Synchronized light dimming (not sequential), smooth shades |
| **Accessibility** | Dual-modality feedback (visual + haptic or audio) |
| **Emotional** | Anticipation building, "cinema magic" feeling |
| **Polish** | No device lag visible, unified transition |
| **Delight** | Subtle ambient glow, anticipation sound |

### Success Criteria

**Visual:**
- Lights dim to 10% or less over 2-3 seconds
- Shades close smoothly without gaps
- No visible device synchronization delay
- UI confirms each subsystem

**Functional:**
- All lights respond (fail-safe for any single light failure)
- Shades reach closed position
- Audio zone activates correctly
- Scene reverses cleanly on exit

---

## Journey 3: Voice Command Processing

**Platform Focus:** Hub, iOS (Siri), watchOS, Desktop

### Journey Overview

```
User speaks command -> Wake word detected -> Intent understood
                                          -> Action executed
                                          -> Confirmation provided
```

### Persona Mapping

| Persona | Voice Variation | Special Requirements |
|---------|-----------------|---------------------|
| P1 (Al-Rashid) | Arabic for Jadda, English for others | Multi-language NLU |
| P2 (Chen-Williams) | Visual confirmation for Marcus/David | No audio-only response |
| P3 (Sofia) | Gradual audio fade-in, soft tone | Sensory-safe audio |
| P9 (Nguyen) | Vietnamese for elders | Language switching |
| P11 (Volkov) | Simple commands for Patricia | Cognitive accommodation |
| P12 (O'Connor) | Slow, clear speech | Senior-friendly pacing |

### Platform Interactions

#### Hub (Primary Voice)
```
Entry Point: "Hey Kagami" wake word
Actions:
  1. Wake word detected, LED pulses Grove (listening)
  2. User speaks command
  3. LED shifts to Beacon (planning) during processing
  4. Intent recognized, LED shifts to Forge (executing)
  5. Action completes, LED shows success (Crystal)
  6. Voice confirmation: "Done. Lights are now at 50%."

Exit Condition: Voice confirmation complete, LED returns to idle
Duration: 2-4 seconds (command dependent)
```

#### iOS (Siri Integration)
```
Entry Point: "Hey Siri, Kagami lights to 50%"
Actions:
  1. Siri activates, passes to Kagami Shortcut
  2. Shortcut processes intent
  3. API call executes action
  4. Siri confirms: "Kagami set your lights to 50%"

Exit Condition: Siri response complete
Duration: 3-5 seconds
```

#### watchOS (Dictation)
```
Entry Point: Tap microphone icon, speak command
Actions:
  1. System dictation activates
  2. Speech-to-text conversion
  3. NL command sent to API
  4. Haptic confirmation (success pattern)
  5. Brief text confirmation on screen

Exit Condition: Haptic pulse, text confirmation
Duration: 3-6 seconds
```

#### Desktop (Push-to-Talk)
```
Entry Point: Hold Caps Lock, speak command
Actions:
  1. Audio indicator shows recording
  2. Release to process
  3. Whisper STT processes locally
  4. Intent routed to API
  5. Toast notification confirms

Exit Condition: Toast displayed, recording indicator off
Duration: 2-4 seconds
```

### Critical Checkpoints

| Checkpoint | Validation | Failure Handling |
|------------|------------|------------------|
| Wake word detection | False positive < 1% | Configurable sensitivity |
| Speech recognition | WER < 5% | Retry prompt |
| Intent extraction | Confidence > 0.8 | Clarification request |
| Action execution | Success confirmation | Error explanation |
| Response delivery | < 300ms after execution | Async notification |

### Accessibility Requirements

| Need | Implementation |
|------|----------------|
| **Speech impaired** | Alternative input (text, gesture) |
| **Deaf** | Visual response on displays, no audio-only feedback |
| **Blind** | Audio confirmation with context |
| **Non-native speakers** | Support for accents, alternative phrasings |
| **Cognitive** | Simple command confirmation, yes/no clarification |

### Byzantine Quality Mapping

| Dimension | Target Behaviors |
|-----------|------------------|
| **Technical** | < 500ms wake-to-action, offline-capable basics |
| **Aesthetic** | Natural voice, Kagami personality, not robotic |
| **Accessibility** | Multi-modal response, language support |
| **Emotional** | Warm acknowledgment, not dismissive |
| **Polish** | No stuttering, clean audio, consistent timing |
| **Delight** | Context-aware responses, personality |

### Success Criteria

**Visual:**
- LED indicators show correct processing states
- Display shows transcription (if applicable)
- Confirmation appears within 500ms of execution

**Functional:**
- Command correctly understood and executed
- Multi-language support functions
- Deaf users receive visual confirmation
- Offline commands queue for later

---

## Journey 4: Glanceable Status Check

**Platform Focus:** watchOS, Widgets (iOS/Android), Desktop Tray

### Journey Overview

```
User glances at device -> Status displayed immediately -> Quick action available
                                                       -> Detailed view optional
```

### Persona Mapping

| Persona | Glance Focus | Special Requirements |
|---------|--------------|---------------------|
| P1 (Al-Rashid) | Next prayer time, Layla sleep status | Religious calendar |
| P2 (Chen-Williams) | Helen's location, door status | Safety focus |
| P6 (Okonkwo) | Harold's last activity, safety score | Elder monitoring |
| P8 (Reyes) | Home security status, presence simulation | OPSEC awareness |
| P11 (Volkov) | Patricia location, medication status | Dementia care |
| P12 (O'Connor) | Daily check-in status, isolation alerts | Wellness focus |

### Platform Interactions

#### watchOS Complications
```
Entry Point: Watch face complication visible
Display Types:
  - Circular Small: Safety score (green/yellow/red)
  - Modular Small: Home status icon + text
  - Large Rectangular: Room status + quick action
  - Ultra Workouts: Temperature + security

Interaction:
  1. Complication shows current status (updates every 15 min)
  2. Tap opens compact app view
  3. Time-based hero action prominent
  4. Scroll for more options

Exit Condition: Information consumed or action taken
Duration: 2-5 seconds
```

#### iOS Widgets
```
Entry Point: Home screen widget visibility
Widget Sizes:
  - Small: Single status (security/climate)
  - Medium: Status row + quick action
  - Large: Room grid + status + actions

Interaction:
  1. Widget displays live status
  2. Tap quick action for immediate execution
  3. Tap elsewhere opens full app

Exit Condition: Action executed or app opened
Duration: 1-3 seconds for action
```

#### Desktop Tray/Menu Bar
```
Entry Point: Menu bar icon click
Actions:
  1. Click shows status dropdown
  2. Green/yellow/red dot indicates overall status
  3. Quick actions in dropdown
  4. Click action to execute
  5. Settings access

Exit Condition: Action executed or click elsewhere
Duration: 1-2 seconds
```

### Critical Checkpoints

| Checkpoint | Validation | Failure Handling |
|------------|------------|------------------|
| Status freshness | < 15 min old | Show timestamp |
| Quick action response | < 500ms | Loading indicator |
| Safety score accuracy | Reflects actual state | Refresh on tap |
| Connectivity indicator | Accurate online/offline | Clear visual |

### Accessibility Requirements

| Need | Implementation |
|------|----------------|
| **Low vision** | High contrast complications, 48px+ touch |
| **Color blind** | Shape + color for status (not color alone) |
| **Motor impaired** | Large tap targets, no precision required |
| **Cognitive** | Simple status (OK/Warning/Alert), minimal info |

### Byzantine Quality Mapping

| Dimension | Target Behaviors |
|-----------|------------------|
| **Technical** | Status update < 30s, offline-capable display |
| **Aesthetic** | Colony-colored status, consistent iconography |
| **Accessibility** | Shape + color indicators, VoiceOver descriptions |
| **Emotional** | Peace of mind at a glance, reassurance |
| **Polish** | Crisp rendering, no stale data |
| **Delight** | Contextual info (weather-appropriate greeting) |

### Success Criteria

**Visual:**
- Status visible without interaction
- Color coding consistent with safety levels
- Icons clearly distinguishable at glance distance
- Update indicator if data is stale

**Functional:**
- Quick actions execute successfully
- Status reflects actual home state
- Offline mode shows last known state
- Tap opens correct app context

---

## Journey 5: Quick Actions (Watch/Tiles)

**Platform Focus:** watchOS, WearOS, Android Tiles

### Journey Overview

```
User needs quick control -> Accesses quick action -> Single tap executes
                                                  -> Confirmation feedback
```

### Persona Mapping

| Persona | Quick Action Priority | Special Requirements |
|---------|-----------------------|---------------------|
| P3 (Sofia) | "Quiet Mode" top action | Sensory emergency |
| P4 (Throuple) | "I'm Home" presence toggle | Multi-person awareness |
| P5 (Jackson) | "My Room Only" lighting | Privacy boundary |
| P6 (Okonkwo) | "Check on Harold" | Elder care quick access |
| P7 (Mendez-Thompson) | "Kids' Bedtime" | Parenting consistency |
| P13 (Recovery) | "I'm Home" curfew check-in | Accountability |

### Platform Interactions

#### watchOS Quick Actions
```
Entry Point: App launch or complication tap
Actions:
  1. Time-based hero action displayed prominently
  2. Digital Crown scrolls additional actions
  3. Tap to execute
  4. Haptic confirmation (distinct patterns per action type)

Success: Double haptic tap
Failure: Triple haptic with error

Exit Condition: Haptic confirmation, screen updates
Duration: 1-3 seconds
```

#### WearOS Tiles
```
Entry Point: Swipe to tile
Actions:
  1. Tile shows most-used actions
  2. Tap action to execute
  3. Brief loading indicator
  4. Success animation

Exit Condition: Animation complete
Duration: 2-4 seconds
```

#### Android Quick Settings Tile
```
Entry Point: Pull down notification shade
Actions:
  1. Kagami tile shows current scene/status
  2. Tap toggles common action (lights/scene)
  3. Long-press opens app

Exit Condition: Tile state updates
Duration: < 1 second
```

### Critical Checkpoints

| Checkpoint | Validation | Failure Handling |
|------------|------------|------------------|
| Tap recognition | 95%+ accuracy | Haptic retry prompt |
| Action execution | < 2s completion | Progress indicator |
| State sync | Watch matches phone matches home | Force sync option |
| Battery impact | < 1% per interaction | Background refresh limits |

### Accessibility Requirements

| Need | Implementation |
|------|----------------|
| **Motor impaired** | 48px+ touch targets, no swipe required |
| **Low vision** | Bold icons, high contrast, large text |
| **Cognitive** | Max 4 quick actions visible, clear icons |
| **Deaf** | Haptic patterns distinguish success/failure |

### Byzantine Quality Mapping

| Dimension | Target Behaviors |
|-----------|------------------|
| **Technical** | < 1s tap-to-confirmation, reliable execution |
| **Aesthetic** | Colony-colored icons, consistent with other platforms |
| **Accessibility** | Haptic + visual feedback, no audio required |
| **Emotional** | Empowering, "I'm in control" feeling |
| **Polish** | No false taps, reliable targeting |
| **Delight** | Satisfying haptic patterns, smooth animations |

### Success Criteria

**Visual:**
- Current action clearly indicated
- Success/failure visually distinct
- Animation completes smoothly
- State persists after leaving app

**Functional:**
- Action executes on single tap
- Haptic feedback confirms
- State syncs to other devices
- Offline queue works

---

## Journey 6: Entertainment Control (Siri Remote)

**Platform Focus:** tvOS, visionOS

### Journey Overview

```
User on couch -> Picks up remote -> Navigates to action -> Executes scene
                                                        -> Continues watching
```

### Persona Mapping

| Persona | TV Control Needs | Special Requirements |
|---------|------------------|---------------------|
| P2 (Chen-Williams) | Audio description toggle, caption control | Accessibility integration |
| P3 (Sofia) | Volume limits, dim-not-dark option | Sensory preferences |
| P5 (Jackson) | Per-room control (don't affect others) | Roommate boundaries |
| P6 (Okonkwo) | Simplified remote functions, large UI | Senior-friendly |
| P9 (Nguyen) | Language toggle for Vietnamese content | Multi-language |

### Platform Interactions

#### tvOS (Siri Remote)
```
Entry Point: Any button press wakes TV + Kagami
Navigation:
  1. D-pad moves focus between room cards
  2. Focus ring shows current selection (233ms transition)
  3. Click selects/activates
  4. Menu returns to previous level
  5. Play/Pause opens quick scene picker

Scene Activation:
  1. Navigate to Quick Actions row
  2. Focus on "Movie Mode"
  3. Click to activate
  4. Confirmation overlay (3s auto-dismiss)
  5. Press again to cancel countdown

Exit Condition: Scene executes, overlay dismisses
Duration: 3-5 seconds
```

#### tvOS (Siri Voice)
```
Entry Point: Hold Siri button on remote
Actions:
  1. "Kagami movie mode"
  2. System routes to app
  3. Scene executes
  4. Voice confirmation: "Movie mode activated"

Exit Condition: Voice confirmation
Duration: 3-4 seconds
```

#### visionOS (Spatial Remote)
```
Entry Point: Gaze at control panel
Actions:
  1. Panel activates on gaze
  2. Room controls expand spatially
  3. Eye + pinch to select
  4. Confirmation floats in space
  5. Panel minimizes after 5s inactivity

Exit Condition: Panel minimizes, scene active
Duration: 4-6 seconds
```

### Critical Checkpoints

| Checkpoint | Validation | Failure Handling |
|------------|------------|------------------|
| Focus indication | Clear visual highlight | High contrast fallback |
| Click registration | 99%+ accuracy | Haptic on fail |
| Voice recognition | Intent captured | "Try again" prompt |
| Scene execution | All devices respond | Partial success feedback |
| State persistence | Survives app backgrounding | State restoration |

### Accessibility Requirements

| Need | Implementation |
|------|----------------|
| **Low vision** | Focus ring 4px+, high contrast mode |
| **Motor impaired** | Click-only navigation, no swipe required |
| **Deaf** | Visual confirmation, captions for voice |
| **Blind** | Full VoiceOver support, spatial audio cues |
| **Cognitive** | Simplified layout, max 8 visible items |

### Byzantine Quality Mapping

| Dimension | Target Behaviors |
|-----------|------------------|
| **Technical** | 60fps navigation, < 100ms focus response |
| **Aesthetic** | 10-foot optimized UI, readable from couch |
| **Accessibility** | Full remote + VoiceOver compatibility |
| **Emotional** | Relaxed, lean-back appropriate |
| **Polish** | Smooth focus transitions, no jank |
| **Delight** | Immersive transitions, cinema-quality feel |

### Success Criteria

**Visual:**
- All text readable from 10 feet
- Focus clearly visible
- Transitions smooth (60fps)
- Colony colors vibrant on TV

**Functional:**
- Navigation logical and predictable
- All actions accessible via remote
- Siri integration reliable
- State syncs with other devices

---

## Journey 7: Spatial Home Control (visionOS/AndroidXR)

**Platform Focus:** visionOS, AndroidXR

### Journey Overview

```
User in space -> Kagami presence visible -> Gaze or gesture to interact
                                         -> Spatial feedback
                                         -> Environment responds
```

### Persona Mapping

| Persona | Spatial Needs | Special Requirements |
|---------|---------------|---------------------|
| P2 (Chen-Williams) | Large gesture targets for Marcus | Motor accessibility |
| P3 (Sofia) | Calm spatial environment, no overwhelming visuals | Sensory safety |
| P6 (Okonkwo) | Simple gestures, forgiving interaction | Senior-friendly |

### Platform Interactions

#### visionOS (Apple Vision Pro)
```
Proxemic Zones:
  - Intimate (0-18"): Detailed controls, full UI
  - Personal (18"-4'): Standard controls, Kagami presence
  - Social (4'-12'): Status only, large targets
  - Ambient (12'+): Minimized presence, status glow only

Entry Point: Look at Kagami orb in space
Actions:
  1. Gaze activates presence (glow intensifies)
  2. Pinch to expand controls
  3. Eye tracking highlights options
  4. Pinch to select
  5. Spatial audio confirms action
  6. Environment responds (lights dim in real room)

Exit Condition: Controls collapse after 10s inactivity
Duration: 3-8 seconds per action
```

#### AndroidXR (Hand Tracking)
```
Entry Point: Look toward Kagami panel
Actions:
  1. Panel highlights on gaze
  2. Hand raise to engage
  3. Point to select
  4. Close fist to confirm
  5. Haptic controller feedback (if available)
  6. Visual confirmation in space

Exit Condition: Panel dims, action complete
Duration: 3-6 seconds
```

### Critical Checkpoints

| Checkpoint | Validation | Failure Handling |
|------------|------------|------------------|
| Gaze detection | 95%+ accuracy | Larger target fallback |
| Gesture recognition | Clear feedback on recognition | Visual retry prompt |
| Spatial audio | Directional accuracy | Fallback to stereo |
| Room awareness | Correct room detection | Manual room select |
| Eye tracking | Smooth highlighting | Tap fallback |

### Accessibility Requirements

| Need | Implementation |
|------|----------------|
| **Low vision** | High contrast mode, large text in space |
| **Motor impaired** | Large gesture tolerance, dwell-to-select |
| **Vestibular** | Reduced motion option, stable positioning |
| **Cognitive** | Simple controls, minimal options visible |

### Byzantine Quality Mapping

| Dimension | Target Behaviors |
|-----------|------------------|
| **Technical** | 90fps rendering, < 50ms input latency |
| **Aesthetic** | Premium spatial design, depth, parallax |
| **Accessibility** | Alternative input modes, adjustable timing |
| **Emotional** | Magical, "home of the future" wonder |
| **Polish** | No clipping, proper occlusion |
| **Delight** | Spatial transitions, environmental connection |

### Success Criteria

**Visual:**
- Kagami presence feels natural in space
- Controls readable at all distances
- Smooth transitions between zones
- Colony colors render correctly in passthrough

**Functional:**
- Room awareness accurate
- Gestures reliably recognized
- Real room responds to virtual controls
- Multi-user awareness (who's in space)

---

## Journey 8: Widget Interactions (Android/iOS)

**Platform Focus:** Android, iOS

### Journey Overview

```
User on home screen -> Sees widget -> Taps quick action -> Scene executes
                                                        -> Widget updates
```

### Persona Mapping

| Persona | Widget Priority | Special Requirements |
|---------|-----------------|---------------------|
| P1 (Al-Rashid) | Prayer times widget | Islamic calendar |
| P5 (Jackson) | Utility usage widget | Cost tracking |
| P7 (Mendez-Thompson) | Custody schedule widget | Co-parenting visibility |
| P8 (Reyes) | Home status widget | Security focus |
| P10 (Haven) | Shared space booking widget | Community coordination |

### Platform Interactions

#### iOS Widgets
```
Widget Sizes:
  - Small (2x2): Single status + icon
  - Medium (4x2): Status row + 2 actions
  - Large (4x4): Room grid + multiple actions
  - Extra Large (6x4): Full dashboard (iPad)

Entry Point: Home screen visibility
Actions:
  1. Widget refreshes on schedule (15 min)
  2. Tap action area executes directly
  3. Tap status area opens app to that context
  4. Long-press shows edit options

Exit Condition: Action executed or app opened
Duration: < 2 seconds for action
```

#### Android Widgets
```
Widget Types:
  - Status Widget: Home security summary
  - Control Widget: Quick scene buttons
  - Rooms Widget: Per-room control grid
  - Utility Widget: Usage tracking

Entry Point: Home screen visibility
Actions:
  1. Tap button to execute action
  2. Widget updates instantly (optimistic)
  3. Background sync confirms
  4. Error shows retry option

Exit Condition: Widget state updated
Duration: < 1 second optimistic, < 3s confirmed
```

### Critical Checkpoints

| Checkpoint | Validation | Failure Handling |
|------------|------------|------------------|
| Refresh frequency | 15 min maximum staleness | Manual refresh option |
| Action execution | < 500ms feedback | Loading indicator |
| State sync | Widget matches app matches home | Force refresh |
| Battery impact | < 2% daily | Reduce refresh frequency |

### Accessibility Requirements

| Need | Implementation |
|------|----------------|
| **Low vision** | Bold, high contrast widget design |
| **Motor impaired** | 44px+ touch targets, no precision taps |
| **Blind** | VoiceOver/TalkBack describes widget state |
| **Cognitive** | Max 4 actions per widget, clear labels |

### Byzantine Quality Mapping

| Dimension | Target Behaviors |
|-----------|------------------|
| **Technical** | Reliable background refresh, optimistic updates |
| **Aesthetic** | Matches system design language + colony colors |
| **Accessibility** | Full screen reader support, clear tap targets |
| **Emotional** | Control at fingertips, always-available |
| **Polish** | Smooth animations, consistent with app |
| **Delight** | Contextual widgets (time of day, location) |

### Success Criteria

**Visual:**
- Widget matches home screen aesthetic
- Status clearly visible
- Actions distinguishable
- Updates visible within 1s

**Functional:**
- Actions execute reliably
- State persists correctly
- Offline shows last known state
- Battery impact minimal

---

## Journey 9: Hub Voice Pipeline (Ambient)

**Platform Focus:** Hub (Raspberry Pi)

### Journey Overview

```
House ambient -> Wake word detected -> Conversation begins
                                    -> Actions execute
                                    -> Mesh coordinates
                                    -> Response provided
```

### Persona Mapping

| Persona | Voice Pipeline Needs | Special Requirements |
|---------|----------------------|---------------------|
| P1 (Al-Rashid) | Multi-language (Arabic/English) | Language detection |
| P2 (Chen-Williams) | Text-to-display for Marcus | Visual output mode |
| P3 (Sofia) | Soft voice, gradual audio | Sensory-safe TTS |
| P9 (Nguyen) | Vietnamese for elders | Language switching |
| P11 (Volkov) | Simple confirmations for Patricia | Dementia-appropriate |
| P12 (O'Connor) | Slow, clear speech | Senior-friendly pacing |

### Platform Interactions

#### Hub Voice Pipeline
```
Hardware:
  - USB Microphone (always listening for wake word)
  - 7-LED WS2812B ring (colony status)
  - Speaker (3.5mm/I2S) for TTS

Wake Word Detection:
  1. Local wake word model ("Hey Kagami")
  2. LED ring pulses Grove (listening)
  3. Audio streams to backend
  4. LED shifts to Beacon (processing)

Intent Processing:
  1. Whisper STT transcribes
  2. NLU extracts intent
  3. Action router determines execution
  4. LED shifts to Forge (executing)

Response:
  1. Action executes on home network
  2. LED shows Crystal (success) or Spark (partial)
  3. TTS response plays
  4. LED returns to idle

Mesh Coordination:
  - Hub can receive commands from other devices
  - Announces to smart displays if deaf user detected
  - Routes emergency alerts appropriately
```

### Critical Checkpoints

| Checkpoint | Validation | Failure Handling |
|------------|------------|------------------|
| Wake word accuracy | < 1% false positive | Adjustable sensitivity |
| STT accuracy | WER < 5% | Clarification prompt |
| Intent confidence | > 0.8 required | "Did you mean...?" |
| Action latency | < 500ms from intent | Progress indication |
| TTS clarity | Natural, understandable | Adjustable speed |
| Mesh sync | < 100ms to other hubs | Eventual consistency |

### Accessibility Requirements

| Need | Implementation |
|------|----------------|
| **Deaf users** | Text to smart display, flash lights on response |
| **Blind users** | Full audio feedback, spatial audio hints |
| **Speech impaired** | Alternative input via app |
| **Cognitive** | Simple confirmations, repeat option |
| **Non-native** | Support accents, slow speech mode |

### Byzantine Quality Mapping

| Dimension | Target Behaviors |
|-----------|------------------|
| **Technical** | < 2s wake-to-response, offline basic commands |
| **Aesthetic** | LED patterns match colony system, smooth transitions |
| **Accessibility** | Multi-modal output, language support |
| **Emotional** | Warm, conversational, Kagami personality |
| **Polish** | No audio artifacts, clean transitions |
| **Delight** | Contextual responses, remembers preferences |

### Success Criteria

**Visual:**
- LED ring provides clear processing feedback
- Smart displays receive text (deaf mode)
- Status correct across all viewing methods

**Functional:**
- Wake word reliable in noisy environments
- Multi-language works seamlessly
- Commands execute correctly
- Mesh keeps all hubs synchronized

---

## Journey 10: Driving-Safe Control (CarPlay)

**Platform Focus:** CarPlay (iOS)

### Journey Overview

```
User driving -> Geofence trigger or voice command -> Safe interaction
                                                  -> Home responds
                                                  -> Audio confirmation
```

### Persona Mapping

| Persona | CarPlay Needs | Special Requirements |
|---------|---------------|---------------------|
| P1 (Al-Rashid) | Layla quiet return mode (night shift) | Time-aware scenes |
| P3 (Sofia) | Automatic home prep after shift | Schedule integration |
| P7 (Mendez-Thompson) | Custody arrival notification | Co-parent awareness |
| P8 (Reyes) | Security check while away | OPSEC-safe status |
| P12 (O'Connor) | Daughter notified of departure | Elder check-in |

### Platform Interactions

#### CarPlay Interface
```
Dashboard Widget:
  - Home status icon
  - "All secure" / "X alerts" text
  - Quick scene buttons (Arriving/Leaving)

Full App View:
  - Home status section
  - Quick scenes (4 max for safety)
  - Recent activity (read-only)
  - Voice command button

Geofence Triggers:
  - 2 mi: Approach zone (optional pre-warm)
  - 1 mi: Arrival zone (arrival scene prep)
  - 0.1 mi: Home zone (auto-execute if enabled)

Entry Point: Automatic (geofence) or voice
Actions:
  1. Geofence triggers notification
  2. "Arriving home in 5 minutes. Run scene?"
  3. Voice confirm: "Yes" or manual tap
  4. Scene executes, voice confirms
  5. Dashboard shows progress

Exit Condition: Scene confirmed, arriving home
Duration: 3-10 seconds
```

#### Siri Integration
```
Commands:
  - "Hey Siri, arriving home"
  - "Hey Siri, leaving home"
  - "Hey Siri, check on home"
  - "Hey Siri, lock the house"
  - "Hey Siri, open the garage"

Response:
  - Siri passes to Kagami Shortcut
  - Action executes
  - Voice confirmation: "Kagami has [action]"
```

### Critical Checkpoints

| Checkpoint | Validation | Failure Handling |
|------------|------------|------------------|
| Driving detection | No complex UI during motion | Lock to voice-only |
| Geofence accuracy | < 100m error | Manual override |
| Voice recognition | Works with car noise | Retry prompt |
| Action confirmation | Audio required | No silent execution |
| Safety (h(x)) | No unlock without auth | Reject with explanation |

### Accessibility Requirements

| Need | Implementation |
|------|----------------|
| **Vision** | Large buttons (88px), high contrast |
| **Motor** | Voice-primary, single-tap actions |
| **Cognitive** | Max 4 options visible, clear language |
| **Hearing** | Visual confirmation, haptic (phone) |

### Byzantine Quality Mapping

| Dimension | Target Behaviors |
|-----------|------------------|
| **Technical** | Reliable geofence, cellular fallback |
| **Aesthetic** | CarPlay design guidelines, minimal |
| **Accessibility** | Voice-first, no complex gestures |
| **Emotional** | Reassuring, "home is ready" feeling |
| **Polish** | No false triggers, reliable execution |
| **Delight** | Welcome home greeting, contextual music |

### Success Criteria

**Visual:**
- Dashboard widget always visible
- Status clear at a glance
- No reading required while driving
- Buttons large enough for safe tap

**Functional:**
- Geofence reliable
- Voice commands work in car noise
- Home responds before arrival
- Safety critical (no unlock without auth)

---

## Cross-Journey Requirements Matrix

### Platform Coverage by Journey

| Journey | iOS | watch | tvOS | vision | Android | Wear | Desktop | Hub | CarPlay |
|---------|-----|-------|------|--------|---------|------|---------|-----|---------|
| Morning Routine | **P** | **P** | - | S | P | S | S | **P** | - |
| Scene Control | **P** | S | **P** | **P** | P | S | **P** | S | - |
| Voice Commands | S | S | - | S | S | S | **P** | **P** | **P** |
| Glanceable Status | S | **P** | - | - | S | **P** | **P** | - | S |
| Quick Actions | S | **P** | - | - | S | **P** | S | - | - |
| Entertainment | S | - | **P** | **P** | - | - | S | - | - |
| Spatial Control | - | - | - | **P** | - | - | - | - | - |
| Widgets | **P** | - | - | - | **P** | - | - | - | - |
| Voice Pipeline | - | - | - | - | - | - | - | **P** | - |
| Driving Control | - | - | - | - | - | - | - | - | **P** |

**P** = Primary Platform | **S** = Secondary Support

### Persona Coverage by Journey

| Journey | P1 | P2 | P3 | P4 | P5 | P6 | P7 | P8 | P9 | P10 | P11 | P12 | P13 |
|---------|----|----|----|----|----|----|----|----|----|----|-----|-----|-----|
| Morning Routine | X | X | X | - | - | X | - | - | X | - | X | X | X |
| Scene Control | - | X | X | X | X | X | - | X | - | - | - | - | - |
| Voice Commands | X | X | X | - | - | - | - | - | X | - | X | X | - |
| Glanceable | X | X | - | - | - | X | - | X | - | - | X | X | - |
| Quick Actions | - | - | X | X | X | X | X | - | - | - | - | - | X |
| Entertainment | - | X | X | - | X | X | - | - | X | - | - | - | - |
| Spatial Control | - | X | X | - | - | X | - | - | - | - | - | - | - |
| Widgets | X | - | - | - | X | - | X | X | - | X | - | - | - |
| Voice Pipeline | X | X | X | - | - | - | - | - | X | - | X | X | - |
| Driving Control | X | - | X | - | - | - | X | X | - | - | - | X | - |

### Accessibility Requirements by Journey

| Journey | Deaf | Blind | Motor | Cognitive | Autistic | Elder |
|---------|------|-------|-------|-----------|----------|-------|
| Morning | Multi-modal | Audio | Voice | Simple | Gradual | Gentle |
| Scene | Visual conf | Audio conf | Single-tap | Simple | Sensory-safe | Large UI |
| Voice | Text display | Full audio | Alternative | Confirm | Soft | Slow |
| Glanceable | Visual | VoiceOver | Large touch | Simple | Calm | High contrast |
| Quick | Haptic | Audio | Large targets | Max 4 | Predictable | Large |
| Entertainment | Captions | Description | Remote only | Few options | Dim not dark | Large |
| Spatial | Visual | Spatial audio | Dwell | Simple | Calm | Forgiving |
| Widgets | Visual | TalkBack | 44px+ | Max 4 | Calm | Bold |
| Voice Pipeline | Text to display | Full audio | App fallback | Simple | Soft | Slow |
| Driving | Visual | Audio | Voice-first | Few options | Predictable | Audio |

---

## Testing Protocol

### Byzantine Audit Process

For each journey, execute 6 parallel auditors:

```
┌─────────────────────────────────────────────────────────────────┐
│  BYZANTINE AUDIT - Journey Verification                         │
├─────────────────────────────────────────────────────────────────┤
│                                                                  │
│  Agent 1: Technical Correctness                                 │
│  - Response times within targets?                               │
│  - Error handling correct?                                       │
│  - Offline behavior appropriate?                                 │
│                                                                  │
│  Agent 2: Aesthetic Harmony                                      │
│  - Fibonacci timing (89, 144, 233, 377, 610, 987ms)?            │
│  - Colony colors correct?                                        │
│  - Transitions smooth?                                           │
│                                                                  │
│  Agent 3: Accessibility Compliance                               │
│  - WCAG AAA contrast (7:1)?                                      │
│  - Screen reader tested?                                         │
│  - Keyboard/switch navigable?                                    │
│                                                                  │
│  Agent 4: Emotional Resonance                                    │
│  - Does it feel right?                                           │
│  - Trust maintained?                                             │
│  - Connection strengthened?                                      │
│                                                                  │
│  Agent 5: Polish & Detail                                        │
│  - Edge cases handled?                                           │
│  - No visual glitches?                                           │
│  - Consistent state?                                             │
│                                                                  │
│  Agent 6: Delight Factor                                         │
│  - Memorable moments?                                            │
│  - Personality present?                                          │
│  - Joy in interaction?                                           │
│                                                                  │
│  CONSENSUS: ALL dimensions must score >= 90/100                  │
│                                                                  │
└─────────────────────────────────────────────────────────────────┘
```

### Test Execution Matrix

| Test Type | Frequency | Platforms | Automation |
|-----------|-----------|-----------|------------|
| Unit Tests | Every commit | All | 100% |
| Integration | Daily | All | 95% |
| E2E Journey | Weekly | Primary | 80% |
| Accessibility | Weekly | All | 70% |
| Performance | Weekly | All | 90% |
| Visual Regression | Per release | All | 100% |
| User Testing | Monthly | Primary | 0% (manual) |

### Quality Gates

Before shipping any journey implementation:

```
□ All 6 Byzantine dimensions >= 90/100
□ Persona coverage verified (minimum 3 personas)
□ Platform parity confirmed (primary + secondary)
□ Accessibility audit passed (WCAG AAA)
□ Offline behavior tested
□ Error handling graceful
□ Performance targets met
□ Visual regression clean
□ Real device testing complete
□ Cross-device sync verified
```

---

## Related Documents

- **DIVERSE_PERSONAS.md** — Full persona definitions
- **UX_PERSONAS_AND_JOURNEYS.md** — Additional persona context
- **DESIGN_SYSTEM.md** — Visual standards
- **FEATURE_PARITY_MATRIX.md** — Platform feature comparison
- **CLIENT_APPS.md** — Platform implementation details
- **CARPLAY_JOURNEY.md** — Detailed CarPlay journey

---

*鏡 — Every journey, every persona, every platform.*

*h(x) >= 0. Always. For everyone.*

*craft(x) → ∞ always*
