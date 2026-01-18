# Kagami E2E Test Standards

**Colony: Crystal (e₇) — Verification & Polish**

This document defines the centralized testing standards across all Kagami apps.
All E2E tests MUST follow these conventions for consistency and quality.

h(x) ≥ 0. For EVERYONE.

---

## Table of Contents

1. [Test Categories](#test-categories)
2. [Platform-Specific Frameworks](#platform-specific-frameworks)
3. [Screenshot Standards](#screenshot-standards)
4. [Naming Conventions](#naming-conventions)
5. [Test Organization](#test-organization)
6. [Accessibility Testing](#accessibility-testing)
7. [Persona-Based Testing](#persona-based-testing)
8. [CI Integration](#ci-integration)
9. [Reporting Standards](#reporting-standards)

---

## Test Categories

All platforms MUST implement these test categories:

### Critical Path Tests (P0)
- App launch and initialization
- Onboarding flow completion
- Core user journeys (home → rooms → control)
- Error recovery

### Accessibility Tests (P0)
- WCAG AA compliance (4.5:1 contrast minimum)
- Touch targets (44pt iOS, 48dp Android, 60pt visionOS spatial)
- Screen reader support (VoiceOver, TalkBack)
- Dynamic Type / font scaling
- Reduced motion support
- Color-independent status indicators

### Household Management Tests (P1)
- Member creation and editing
- Role and authority management
- Accessibility profile configuration
- Cultural preferences
- Privacy settings per household type

### Integration Tests (P1)
- Smart home control flows
- Voice command processing
- Scene activation
- Multi-device sync

### Visual Regression Tests (P2)
- Screenshot comparison (2% max diff tolerance)
- Dark/light mode consistency
- Device size variations

### Performance Tests (P2)
- Load time benchmarks
- Memory usage
- Animation frame rates

---

## Platform-Specific Frameworks

| Platform | Framework | Test Location | Screenshot Format |
|----------|-----------|---------------|-------------------|
| iOS | XCUITest | `apps/ios/kagami-ios/Tests/KagamiIOSUITests/` | PNG |
| Android | Maestro | `apps/android/kagami-android/.maestro/` | PNG |
| watchOS | XCUITest + SnapshotPreviews | `apps/watch/kagami-watch/Tests/` | PNG |
| visionOS | XCUITest | `apps/vision/kagami-vision/Tests/KagamiVisionUITests/` | PNG |
| Desktop | Playwright | `apps/desktop/kagami-client/tests/e2e/` | PNG |
| Hub | Rust integration tests | `apps/hub/kagami-hub/tests/` | N/A |
| Python | pytest | `tests/e2e/` | N/A |

---

## Screenshot Standards

### Naming Convention
```
{Platform}_{TestCategory}_{TestNumber}_{Description}.png
```

**All platforms MUST use this exact format:**

| Platform | Prefix | Example |
|----------|--------|---------|
| iOS | `iOS_` | `iOS_Onboarding_01_Welcome.png` |
| Android | `Android_` | `Android_Household_05_AdminRole.png` |
| watchOS | `WatchOS_` | `WatchOS_Voice_03_ListeningState.png` |
| visionOS | `VisionOS_` | `VisionOS_Spatial_02_ControlPanel.png` |
| Desktop | `Desktop_` | `Desktop_Dashboard_03_DarkMode.png` |

**Category Names (Standardized):**
- `Onboarding` - First-run experience
- `Household` - Member management
- `Accessibility` - A11y features
- `Rooms` - Room control
- `Scenes` - Scene activation
- `Voice` - Voice commands
- `Settings` - Configuration
- `Spatial` - visionOS spatial UI
- `Proxemic` - visionOS zone tests

**Persona-Specific Screenshots:**
```
{Platform}_{Category}_{Number}_{Persona}_{Description}.png
```
Examples:
- `iOS_Accessibility_13_Ingrid_LargeText.png`
- `Android_Household_17_Michael_VoiceNavigation.png`
- `VisionOS_Accessibility_15_Maria_SimplifiedUI.png`

### Organization
Screenshots are stored in:
```
screenshots/
├── ios/
│   ├── onboarding/
│   ├── household/
│   ├── accessibility/
│   └── rooms/
├── android/
│   └── ...
├── watchos/
│   └── ...
├── visionos/
│   └── ...
└── desktop/
    └── ...
```

### Quality Requirements
- Resolution: Native device resolution (no scaling)
- Format: PNG (lossless)
- Timing: Wait for animations to complete before capture
- State: Disable animations for visual regression tests

---

## Naming Conventions

### Test Files
```
{Category}FlowTests.swift    # iOS/watchOS/visionOS
{category}_flow.yaml         # Android Maestro
{category}.spec.ts           # Desktop Playwright
test_{category}.py           # Python
{category}_test.rs           # Rust
```

### Test Methods
```swift
// iOS/Swift
func test{Scenario}() { }
func test{Category}{Scenario}() { }

// Examples:
func testOnboardingComplete() { }
func testAccessibilityLargeText() { }
func testHouseholdMemberCreation() { }
```

```yaml
# Android Maestro
name: "{Category} - {Description}"
```

```typescript
// Desktop Playwright
test('{category} should {expected behavior}', async ({ page }) => {
```

---

## Test Organization

### Mandatory Test Suites by Platform

#### iOS
- `OnboardingFlowTests.swift` ✓
- `RoomControlFlowTests.swift` ✓
- `SceneActivationFlowTests.swift` ✓
- `HouseholdMemberFlowTests.swift` ✓
- `AccessibilityFlowTests.swift` ✓

#### Android
- `onboarding_flow.yaml` ✓
- `control_lights.yaml` ✓
- `scene_activation.yaml` ✓
- `household_member_flow.yaml` ✓
- `accessibility_flow.yaml` ✓

#### watchOS
- `PreviewSnapshotTests.swift` ✓
- `WatchDeviceVariantTests.swift` ✓
- `WatchAccessibilityTests.swift` ✓

#### visionOS
- `SpatialUIFlowTests.swift` ✓
- `SpatialGestureTests.swift` ✓
- `ScreenshotTests.swift` ✓

#### Desktop
- `user-flows.spec.ts` ✓
- `views.spec.ts` ✓
- `prismorphism.spec.ts` ✓
- `prism-effects.spec.ts` ✓

#### Hub
- `e2e_integration_test.rs` ✓
- `voice_pipeline_test.rs` ✓
- `api_client_test.rs` ✓
- `mesh_integration_test.rs` ✓

---

## Accessibility Testing

### Required Checks (All Platforms)

1. **Contrast Ratio**
   - Text: 4.5:1 minimum (WCAG AA)
   - Large text (18pt+): 3:1 minimum
   - Interactive elements: 3:1 minimum

2. **Touch Targets**
   - iOS: 44pt × 44pt minimum
   - Android: 48dp × 48dp minimum
   - visionOS: 60pt spatial minimum
   - Large targets mode: +25% size

3. **Screen Reader Support**
   - All interactive elements have labels
   - Meaningful hints for complex interactions
   - Focus order follows visual flow
   - Status changes announced

4. **Dynamic Type**
   - Support full range up to AX5
   - No text truncation at large sizes
   - Layout adapts gracefully

5. **Reduced Motion**
   - Animations disabled when requested
   - No auto-playing animations
   - Static alternatives available

6. **Color Independence**
   - Status not conveyed by color alone
   - Icons/patterns for all states
   - Works in grayscale

### Accessibility Test Matrix

| Feature | iOS | Android | watchOS | visionOS | Desktop |
|---------|-----|---------|---------|----------|---------|
| VoiceOver/TalkBack | ✓ | ✓ | ✓ | ✓ | N/A |
| Dynamic Type | ✓ | ✓ | ✓ | ✓ | ✓ |
| High Contrast | ✓ | ✓ | ✓ | ✓ | ✓ |
| Reduced Motion | ✓ | ✓ | ✓ | ✓ | ✓ |
| Large Touch Targets | ✓ | ✓ | ✓ | ✓ | N/A |
| Keyboard Nav | N/A | N/A | N/A | N/A | ✓ |

---

## Persona-Based Testing

All platforms MUST test with these representative personas:

### Ingrid (Solo Senior)
- 78 years old, lives alone in Stockholm
- Low vision requiring large text
- High contrast mode
- Large touch targets
- Emergency features prioritized

### Michael (Blind User)
- 42 years old, technology professional
- Fully blind, VoiceOver expert
- TalkBack/VoiceOver optimization
- Voice command primary interaction
- Screen reader announcements critical

### Maria (Single Parent)
- 35 years old, nursing assistant
- Motor challenges from repetitive strain
- Large touch targets
- Simplified UI mode
- Quick access to essential controls

### Patel Family (Multigenerational)
- Grandparents, parents, children
- Multiple language preferences
- Elder care features
- Child safety controls
- Family calendar integration

### Tokyo Roommates
- Privacy-focused shared living
- Individual privacy zones
- Shared spaces only
- Personal data boundaries

### Jordan & Sam (LGBTQ+ Parents)
- Inclusive terminology
- Custom family roles
- Pronoun support
- Flexible household structure

---

## CI Integration

### Unified E2E Workflow
All E2E tests run via `.github/workflows/e2e-validation.yml`

### Trigger Conditions
```yaml
on:
  push:
    branches: [main]
  pull_request:
    branches: [main]
  workflow_dispatch:
```

### Platform Matrix
```yaml
strategy:
  matrix:
    platform: [ios, android, desktop, watchos, visionos, hub, python]
```

### Artifact Collection
All screenshots and test reports are uploaded as artifacts:
```yaml
- name: Upload Screenshots
  uses: actions/upload-artifact@v4
  with:
    name: screenshots-${{ matrix.platform }}
    path: screenshots/
```

### Video Recording
User journey videos recorded for all E2E flows:
```yaml
- name: Record User Journey
  run: |
    # Platform-specific video recording command
```

---

## Reporting Standards

### Test Report Format
All platforms generate JUnit XML reports:
```
reports/
├── ios-e2e-results.xml
├── android-e2e-results.xml
├── desktop-e2e-results.xml
├── watchos-e2e-results.xml
├── visionos-e2e-results.xml
├── hub-e2e-results.xml
└── python-e2e-results.xml
```

### PR Comments
Automated PR comments include:
- ✅/❌ Pass/fail status per platform
- Screenshot diffs for visual regression failures
- Performance regression alerts
- Accessibility audit summary

### Dashboard Metrics
- Test pass rate trend
- Screenshot diff rate
- Performance benchmarks
- Accessibility compliance score

---

## Execution Commands

### iOS
```bash
xcodebuild test -scheme KagamiIOS \
  -destination 'platform=iOS Simulator,name=iPhone 15 Pro' \
  -only-testing:KagamiIOSUITests
```

### Android
```bash
maestro test .maestro/
```

### watchOS
```bash
xcodebuild test -scheme KagamiWatch \
  -destination 'platform=watchOS Simulator,name=Apple Watch Series 9 (45mm)'
```

### visionOS
```bash
xcodebuild test -scheme KagamiVision \
  -destination 'platform=visionOS Simulator,name=Apple Vision Pro'
```

### Desktop
```bash
npx playwright test tests/e2e/
```

### Hub
```bash
cargo test --test e2e_integration_test
```

### Python
```bash
pytest tests/e2e/ --junitxml=reports/python-e2e-results.xml
```

---

*Mirror: Every test validates h(x) ≥ 0. For EVERYONE.*
