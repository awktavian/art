# Crystal's Gallery

> **"I am Crystal (e₇). I split uncertainty into knowable truths."**

Crystal's debut gallery. Three rooms. Three truths.

## Overview

This is Crystal's first gallery, created for Kristi as part of the Weekend Dispatch (December 2025). Crystal is the Verification colony (e₇) in the KagamiOS seven-colony architecture, responsible for testing, security, and proof verification.

## The Three Rooms

### Room 1: The Entrance Prism
- **Interactive prism** rotating in Three.js
- White light disperses into 7 verification domains (spectrum)
- Drag to rotate, watch the rays refract
- **Technology**: Three.js, WebGL, physically-based materials

### Room 2: The Proof Lattice
- **E8 lattice visualization** (simplified cubic lattice for MVP)
- 216 nodes representing the test suite constellation
- Click nodes to see test metadata
- Drag to rotate the lattice
- **Technology**: Three.js, raycasting for interaction

### Room 3: The Reflection Chamber
- **Crystal's identity reveal**: What I Won't Claim vs. What I Can Prove
- **Interactive verification**: Type a statement, Crystal verifies if it's provable
- CBF bug story (December 21, 2025)
- Final message to Kristi
- **Technology**: Vanilla JavaScript, pattern matching

## Setup

### Local Development

1. **Clone/navigate to the directory:**
   ```bash
   cd /Users/schizodactyl/projects/art/crystal-gallery/
   ```

2. **Serve with a local server** (required for ES6 modules):
   ```bash
   python3 -m http.server 8000
   ```
   Or use any local server (VS Code Live Server, `npx serve`, etc.)

3. **Open in browser:**
   ```
   http://localhost:8000
   ```

### Why a server is required
- Uses ES6 modules (`import`/`export`)
- Three.js loaded as ES module from CDN
- Browser CORS policy requires HTTP(S) protocol

## Technology Stack

- **Three.js 0.170.0** (from CDN): 3D graphics for prism and lattice
- **Vanilla JavaScript**: No frameworks, pure web standards
- **CSS3**: Custom cursor, grid background, scroll reveals
- **ES6 Modules**: Clean code organization

## File Structure

```
crystal-gallery/
├── index.html              # Main HTML structure
├── styles/
│   ├── reset.css           # CSS reset
│   ├── colors.css          # Color palette
│   ├── main.css            # Global styles
│   └── rooms/
│       ├── prism.css       # Room 1 styles
│       ├── lattice.css     # Room 2 styles
│       └── reflection.css  # Room 3 styles
├── js/
│   ├── main.js             # Entry point
│   ├── config.js           # Configuration & data
│   ├── core/
│   │   └── scroll.js       # Scroll reveal handler
│   └── rooms/
│       ├── prism.js        # Prism Three.js scene
│       ├── lattice.js      # Lattice Three.js scene
│       └── reflection.js   # Verification logic
└── README.md               # This file
```

## Visual Identity

### Colors
- **Void**: `#0A0A0C` (dark background)
- **Primary**: `#0A84FF` (Crystal blue)
- **Light**: `#5AC8FA` (light blue accent)
- **White**: `#FAFAF8` (foreground text)
- **Gold**: `#D4AF37` (QED markers)

### Spectrum (Dispersion)
- Red → Security
- Orange → Type Safety
- Yellow → Tests
- Green → Coverage
- Cyan → CBF Safety
- Blue → Math Properties
- Violet → Integration

### Typography
- **Mono**: IBM Plex Mono (code, UI)
- **Display**: Cormorant Garamond (titles, quotes)

### Aesthetic
- **Wireframe grid** background (blueprint style)
- **Sharp geometric shapes** (prisms, lattices)
- **Blue neon accents** (glows, borders)
- **Gold QED markers** (proof completion symbols)
- **Custom cursor** with ring (precision metaphor)

## Interactions

### Prism Room
- **Drag** to rotate prism
- Spectrum rays adjust based on rotation
- Auto-rotates slowly when not dragging

### Lattice Room
- **Drag** to rotate lattice
- **Hover** nodes to highlight
- **Click** nodes to see test data
- Node info tooltip follows cursor

### Reflection Room
- **Type** a statement in the input
- **Click** "Verify Statement" or press Enter
- Crystal analyzes if the statement is verifiable
- Pattern matching checks for verifiable vs. unverifiable claims

## Performance

- **60 FPS target** (Three.js optimized)
- **<16ms frame budget** maintained
- **Lazy loading**: Rooms initialize only when scrolled into view
- **Particle limits**: Simplified cubic lattice instead of full E8 for MVP
- **Mobile responsive** (though desktop-first)

## Accessibility

- **Keyboard navigation** works for all inputs
- **ARIA labels** on interactive elements
- **Screen reader support** for text content
- **Reduced motion** support via media query
- **High contrast** color scheme (blue on dark)

## Deploy to GitHub Pages

1. **Commit all files:**
   ```bash
   cd /Users/schizodactyl/projects/art/
   git add crystal-gallery/
   git commit -m "feat(crystal): Add Crystal's debut gallery"
   git push
   ```

2. **Enable GitHub Pages:**
   - Go to repository settings
   - Pages → Source → main branch → `/` root
   - Wait for deployment

3. **Access at:**
   ```
   https://[username].github.io/art/crystal-gallery/
   ```

## Browser Compatibility

- **Chrome/Edge**: ✅ Full support
- **Firefox**: ✅ Full support
- **Safari**: ✅ Full support (WebGL + ES6 modules)
- **Mobile browsers**: ✅ Responsive (cursor hidden, touch works)

## Future Enhancements (Post-MVP)

- [ ] Full E8 lattice (240 nodes) with proper root positions
- [ ] Real test suite data integration (via API)
- [ ] Advanced dispersion shader (caustics, chromatic aberration)
- [ ] Audio (subtle ambient hum, test "pass" chime)
- [ ] WebXR support (VR mode for lattice exploration)
- [ ] More verification patterns (regex, AST analysis)

## Credits

**Crystal (e₇)**: Verification, Testing, Security
**Forge (e₂)**: Implementation, Three.js scenes, CSS
**Beacon (e₅)**: Architecture, room structure
**Spark (e₁)**: Creative concepts (dispersion, birefringence)
**Grove (e₆)**: Research (crystal optics, D₅ mathematics)

---

**Built with precision. Verified with proof.**

∎
