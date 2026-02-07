# Patent Museum: Virtuoso Experience Plan

**Goal:** Transform the museum from 10% to 100% quality — a fully realized, immersive experience worthy of Exploratorium/Guggenheim standards.

---

## Phase 1: Critical Foundation Fixes (Blocking Issues)

### 1.1 Rendering Pipeline Fixes
- [ ] **Remove duplicate POST_PROCESSING_QUALITY export** in `lib/post-processing.js`
- [ ] **Fix SSRPass/GTAOPass imports** - implement proper CDN fallbacks
- [ ] **Fix splash screen not dismissing** - ensure pointer lock triggers correctly
- [ ] **Fix WebGL context lost handling** - implement proper recovery
- [ ] **Fix state machine transitions** - ensure LOADING→READY works

### 1.2 Core Initialization Fixes  
- [ ] **Fix renderer initialization order** - ensure scene exists before render
- [ ] **Fix post-processing initialization** - handle missing passes gracefully
- [ ] **Fix audio context initialization** - user gesture requirement
- [ ] **Add comprehensive error boundaries** around all init functions

---

## Phase 2: Collision & Physics System (NEW)

### 2.1 Collision Detection Implementation
Location: `museum/navigation.js`

**Current State:** Players walk through walls and artworks. Only floor height and circular boundary exist.

**Implementation:**
- [ ] **Tag collision geometry** - Add `userData.collidable = true` to all walls in `architecture.js`
- [ ] **Implement raycaster collision** in `update()`:
  - Cast rays in movement direction before applying movement
  - Check against tagged collision objects
  - Prevent movement if collision detected
- [ ] **Implement wall sliding** - project movement along wall surface when blocked
- [ ] **Add collision margin** - 0.3m buffer from walls

### 2.2 Artwork Collision
- [ ] **Add bounding boxes to artworks** in `gallery-loader.js`
- [ ] **Create collision group** for efficient raycasting
- [ ] **Implement artwork proximity stopping** - can't walk into art

### 2.3 Spatial Partitioning (Performance)
- [ ] **Implement octree** for collision geometry
- [ ] **Only check nearby objects** - reduce raycast count
- [ ] **Cache collision results** - reuse for multiple rays

---

## Phase 3: Performance Optimization

### 3.1 GPU Particle Migration
Location: `main.js` lines 1470-1481

**Current:** CPU-updated particles (2100+ ops/frame)
**Target:** Full GPU particle system

- [ ] **Replace dustParticles** with `GPUParticleSystem`
- [ ] **Move all particle updates to vertex shader**
- [ ] **Remove CPU fallback code**
- [ ] **Implement particle LOD** - reduce count beyond 30m

### 3.2 Raycasting Optimization
- [ ] **Throttle hover raycasting** - every 2-3 frames or on mousemove only
- [ ] **Cache interactable objects** - don't rebuild every frame
- [ ] **Use spatial partitioning** for intersection tests

### 3.3 Location Update Optimization
Location: `main.js:1327` `updateLocation()`

- [ ] **Cache location calculation** - only update when camera moves >1m
- [ ] **Reduce COLONY_ORDER iteration** - precompute wing positions

### 3.4 Memory Management
- [ ] **Fix particle attribute disposal** in `reduceParticles()`
- [ ] **Add cleanup to artwork dispose()** methods
- [ ] **Remove event listeners on cleanup**
- [ ] **Implement resource pooling** for common geometries/materials

### 3.5 LOD System Implementation
- [ ] **Particle count LOD** - reduce at distance
- [ ] **Artwork detail LOD** - simplify beyond 50m
- [ ] **Shadow LOD** - disable for distant objects

---

## Phase 4: Content Enhancement (Educational Quality)

### 4.1 Introductory Panels (All Artworks)

Each artwork needs a "What You're Looking At" panel:

| Artwork | Introduction Needed |
|---------|---------------------|
| P1-001 EFE-CBF | "What is a Control Barrier Function?" |
| P1-002 Fano | "What is a Fano Plane? What is Byzantine Fault Tolerance?" |
| P1-003 E8 | "What is E8? What is Semantic Routing?" |
| P1-004 S15 Hopf | "What are Octonions? What is a Hopf Fibration?" |
| P1-005 RSSM | "What is a Recurrent State Space Model?" |
| P1-006 Quantum | "What is the Quantum Threat? What is Lattice Cryptography?" |

- [ ] **Create introductory panel component** - consistent design
- [ ] **Add beginner/expert toggle** - switch explanation depth
- [ ] **Add glossary tooltips** - hover definitions for technical terms
- [ ] **Add "Try This" interaction hints** - guide visitor engagement

### 4.2 Real-World Examples
- [ ] **P1-001 EFE-CBF:** "Robot approaching obstacle" scenario
- [ ] **P1-002 Fano:** "Blockchain consensus" example
- [ ] **P1-003 E8:** "How search queries become routes"
- [ ] **P1-004 S15 Hopf:** "Neural state encoding"
- [ ] **P1-005 RSSM:** "Predicting future observations"
- [ ] **P1-006 Quantum:** "Step-by-step key exchange"

### 4.3 Cross-References
- [ ] **Add "Related Patents" links** between artworks
- [ ] **Add "Prerequisites" indicators** - viewing order suggestions
- [ ] **Add "Deep Dive" expandable sections** - for experts

---

## Phase 5: Wayfinding & Navigation

### 5.1 Enhanced Minimap
Location: `museum/navigation.js` minimap code

- [ ] **Add artwork markers** - dots showing artwork locations
- [ ] **Add gallery room boundaries** - visual distinction
- [ ] **Implement click-to-teleport** - click on minimap to navigate
- [ ] **Add zoom levels** - overview/detail
- [ ] **Add legend/key** - explain symbols
- [ ] **Add "You are here" text label**
- [ ] **Add visited/unvisited indicators** - track progress

### 5.2 Gallery Signage
Location: `museum/architecture.js`

- [ ] **Add gallery category labels** at wing entrances
- [ ] **Add artwork count indicators** - "3 exhibits in this gallery"
- [ ] **Add "Return to Rotunda" directional signs**
- [ ] **Add distance markers** - "30m to Crystal Gallery"

### 5.3 Information Kiosk System
- [ ] **Create kiosk mesh** at rotunda entrance
- [ ] **Add "You Are Here" 3D map**
- [ ] **Add recommended tour paths** - beginner/expert routes
- [ ] **Add accessibility information**

---

## Phase 6: Visual Polish & Interactions

### 6.1 Artwork Visual Enhancements

| Artwork | Enhancement |
|---------|-------------|
| P1-001 EFE-CBF | Enhanced landscape colors, particle trails |
| P1-002 Fano | Animated consensus voting, role highlights |
| P1-003 E8 | Root animation smoothing, search result glow |
| P1-004 S15 Hopf | Fiber ride camera work, dimension labels |
| P1-005 RSSM | State trajectory visualization, KL divergence graph |
| P1-006 Quantum | Encryption animation polish, lattice rotation |

### 6.2 Interaction Polish
Location: `lib/interactions.js`

- [ ] **Enhance hover feedback** - more prominent glow
- [ ] **Add click confirmation** - satisfying visual/audio
- [ ] **Implement dwell indicators** - show sustain progress
- [ ] **Add discovery celebration** - reward finding hidden interactions

### 6.3 Lighting Polish
Location: `museum/lighting.js`

- [ ] **Add artwork label task lighting** - illuminate plaques
- [ ] **Implement proximity-activated illumination** - artworks light up as you approach
- [ ] **Add transition polish** - smoother zone changes

---

## Phase 7: Audio Polish

### 7.1 Spatial Audio
- [ ] **Verify HRTF implementation** - binaural positioning
- [ ] **Add artwork-specific soundscapes** - each piece has unique audio
- [ ] **Add footstep sounds** - surface-appropriate
- [ ] **Add ambient museum sounds** - subtle life

### 7.2 Interaction Audio
- [ ] **Add hover sounds** - subtle acknowledgment
- [ ] **Add click sounds** - satisfying confirmation
- [ ] **Add discovery sounds** - reward finding secrets
- [ ] **Add transition sounds** - entering/leaving galleries

---

## Phase 8: Accessibility

### 8.1 Visual Accessibility
- [ ] **Add high-contrast mode**
- [ ] **Ensure colorblind-friendly palette**
- [ ] **Add motion reduction option**

### 8.2 Input Accessibility  
- [ ] **Full keyboard navigation** - Tab through artworks
- [ ] **Add keyboard shortcuts overlay** (press ? for help)
- [ ] **Implement voice navigation** - "Go to Crystal Gallery"

### 8.3 Screen Reader Support
- [ ] **Add ARIA labels to all UI elements**
- [ ] **Add audio descriptions for artworks**
- [ ] **Announce gallery changes**

---

## Phase 9: XR Polish

### 9.1 VR Enhancements
- [ ] **Verify Apple Vision Pro compatibility**
- [ ] **Test hand tracking interactions**
- [ ] **Optimize for 90fps** - disable screen-space effects
- [ ] **Add VR comfort options** - vignette on movement

### 9.2 AR Features
- [ ] **Implement AR viewing** - place artwork in real space
- [ ] **Add AR wayfinding** - arrows in real world

---

## Phase 10: Testing & Verification

### 10.1 Functional Testing
- [ ] Test all artworks render correctly
- [ ] Test all interactions work
- [ ] Test navigation (walking, teleport, menu)
- [ ] Test collision system
- [ ] Test audio system

### 10.2 Performance Testing
- [ ] Profile FPS on low-end device
- [ ] Check memory usage over time
- [ ] Verify no memory leaks
- [ ] Test with all quality presets

### 10.3 XR Testing
- [ ] Test WebXR on Quest
- [ ] Test on Vision Pro simulator
- [ ] Verify hand tracking
- [ ] Test teleportation

### 10.4 Accessibility Testing
- [ ] Screen reader compatibility
- [ ] Keyboard-only navigation
- [ ] Color contrast verification

---

## Implementation Priority

### Immediate (Blocking)
1. Phase 1: Critical Foundation Fixes
2. Phase 2.1-2.2: Basic Collision System

### High Priority (Core Experience)
3. Phase 3.1-3.2: Performance (GPU particles, raycasting)
4. Phase 4.1: Introductory Panels
5. Phase 5.1: Enhanced Minimap

### Medium Priority (Polish)
6. Phase 6: Visual & Interaction Polish
7. Phase 5.2-5.3: Wayfinding
8. Phase 7: Audio Polish

### Lower Priority (Excellence)
9. Phase 8: Accessibility
10. Phase 9: XR Polish
11. Phase 10: Comprehensive Testing

---

## Success Criteria

**Virtuoso Quality Checklist:**
- [ ] No rendering errors or blank screens
- [ ] Can't walk through walls or artworks
- [ ] 60fps on modern hardware, 30fps+ on low-end
- [ ] Every artwork has educational intro panel
- [ ] Minimap shows where you are and where artworks are
- [ ] Click-to-teleport works from minimap
- [ ] All interactions feel satisfying
- [ ] Audio enhances experience (not annoying)
- [ ] Works in VR (Vision Pro simulator passes)
- [ ] Keyboard navigation works
- [ ] No memory leaks after 10 minutes

---

*h(x) ≥ 0 always. craft(x) → ∞ always.*
