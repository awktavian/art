# Patent Museum: Current State & Remaining Work

Last updated after Ralph audit and full P1/P2/P3 refinement pass.

---

## What Is Done

The museum is substantially complete. The following systems are implemented and working:

**Navigation & Physics**
- 8-ray collision system with wall slide (`navigation.js`)
- Minimap with click-to-teleport, zoom controls, wing progress tracking (`wayfinding.js`)
- Gallery signage: hanging signs, floor markers, return arrows (`wayfinding.js`)
- Proximity trigger system: 3m spark, 5s sustain

**Content & Education**
- Info panel with full patent data, beginner/expert toggle, glossary tooltips (26 terms auto-highlighted) (`info-panel.js`)
- Plaque system (2 draw calls, canvas-baked)
- Journey tracker with localStorage persistence
- Visitor identity system with RDF/Turtle export

**Artworks**
- P1: 6 bespoke, scientifically accurate visualizations — all implemented
- P2: 18 distinct visualizations with interactive demos — all implemented
- P3: 30 unique geometries with 20 animation types — all implemented
- Fano constellation centerpiece — implemented
- 7 wing-specific architectural enhancements — implemented

**Environment**
- Turrell-inspired lighting with diurnal sky disc
- Spatial audio: HRTF, footsteps, wing entrance sounds
- Zone transition tweens (post-processing, lighting)
- Adaptive quality presets (emergency through ultra)
- Loading screen with colony dot animation

**Infrastructure**
- WebXR support (VR + AR modules)
- Accessibility manager (ARIA, voice nav, reduced motion)
- Debug system with URL parameters
- State machine with error recovery
- Achievement toast display

---

## Remaining Work

### Content Gaps

**P2 microdelight dispatches**
Most P2 artworks do not fire achievement events. P1 dispatches correctly. P2 needs the same `dispatchEvent(new CustomEvent('achievement', ...))` calls wired to meaningful milestones in each artwork's demo mode.

**P2 educational content**
`EDUCATIONAL_CONTENT` in `info-panel.js` has entries for P1 patents only. Need 18 entries for P2 patents covering: concept, analogy, significance, application. Same structure as P1.

**Earcon Orchestration artwork plays no audio**
The earcon artwork (`P2-007` or equivalent) is silent. It demonstrates earcon design but produces no sound. This is the most ironic gap in the museum. Wire actual Web Audio API tones to the earcon visualization events.

### Interaction Gaps

**Cross-artwork navigation**
Clicking "Related Patents" in the info panel does nothing. Should teleport camera to the referenced artwork. Requires mapping patent IDs to world positions and calling the teleport function.

**P3 click interaction**
P3 artworks have no demo mode. Clicking does nothing beyond opening the info panel. Add a click handler that triggers a brief animation highlight or parameter change — even a simple one.

**Missing P3 animation cases**
`update()` in P3 artworks has no handler for `wave` and `gossipNode` animation types. These fall through silently. Add the missing cases.

### Performance

**Zone culling for architecture**
All 7 wings render every frame. Zone-based culling was disabled and never re-enabled. Re-enable frustum + distance culling for wing geometry when visitor is not in or near that wing.

### Engineering

**CI pipeline**
No GitHub Actions workflow exists. Need `.github/workflows/test.yml` that runs `npm test` on push/PR.

**Console.log cleanup**
`main.js` has 44+ `console.log` calls that will appear in production. Replace with the debug system (URL param `?debug=true` already gates the debug overlay). Wrap all logs in `if (DEBUG)` or remove them.

**Playwright headless mode**
Test runner has `headless: false` hardcoded. CI cannot run with a display. Change to `headless: !process.env.CI` or equivalent.

### Accessibility

**P1 artwork formula canvases**
Formula rendering uses `<canvas>` elements with no `aria-label` or fallback text. Screen readers see nothing. Add descriptive `aria-label` to each canvas describing the formula it renders.

### UX

**Curated visitor path**
No suggested order for first-time visitors. Add a "Start Here" prompt in the vestibule that offers a Fano-ordered wing sequence (the 7 lines of the Fano plane map naturally to a traversal order).

**Vestibule darkening on wing entry**
When visitor enters a wing, the vestibule should dim slightly to amplify contrast between the active wing and the rotunda. The zone transition system exists — add a vestibule ambient light dimmer to the transition tween.

### Tests

**Visual regression tests**
`tests/visual/` directory exists but is empty. Add baseline screenshots for each wing entrance and at least one P1 artwork. Playwright can capture these; plug into CI.

---

## Priority Order

1. P2 educational content — highest visitor impact, pure content work
2. P2 microdelight dispatches — completes the achievement loop
3. Earcon audio — obvious irony, one-session fix
4. Console.log cleanup + Playwright headless — CI unblocked after these two
5. CI pipeline — everything else benefits from it
6. Cross-artwork navigation — significant UX upgrade
7. P3 click interaction + missing animation cases — completes P3
8. P1 formula canvas accessibility — ARIA labels, quick
9. Zone culling — performance, measure first
10. Curated path + vestibule dimming — polish, post-CI
11. Visual regression tests — last, needs stable baselines

---

`h(x) ≥ 0 always`
