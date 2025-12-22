# Crystal Gallery — Deployment Guide

## Quick Start (Local Testing)

```bash
cd /Users/schizodactyl/projects/art/crystal-gallery/
python3 -m http.server 8000
```

Open: http://localhost:8000

## File Verification

All files created:
```
crystal-gallery/
├── index.html (241 lines)
├── README.md (comprehensive docs)
├── DEPLOYMENT.md (this file)
├── styles/
│   ├── reset.css (34 lines)
│   ├── colors.css (36 lines)
│   ├── main.css (320 lines)
│   └── rooms/
│       ├── prism.css (62 lines)
│       ├── lattice.css (91 lines)
│       └── reflection.css (157 lines)
├── js/
│   ├── main.js (134 lines)
│   ├── config.js (77 lines)
│   ├── core/
│   │   └── scroll.js (40 lines)
│   └── rooms/
│       ├── prism.js (161 lines)
│       ├── lattice.js (230 lines)
│       └── reflection.js (125 lines)
└── assets/ (empty, ready for images if needed)
```

**Total**: 1,708 lines of code

## Deployment to GitHub Pages

### Option 1: Direct Push
```bash
cd /Users/schizodactyl/projects/art/
git add crystal-gallery/
git commit -m "feat(crystal): Crystal's debut gallery - 3 rooms, Three.js, 1708 LOC"
git push origin main
```

### Option 2: With Testing First
```bash
# 1. Test locally
cd crystal-gallery/
python3 -m http.server 8000

# 2. Verify in browser:
# - All three rooms load
# - Prism rotates smoothly
# - Lattice interaction works
# - Verification feature responds

# 3. Commit and push
cd ..
git add crystal-gallery/
git commit -m "feat(crystal): Add Crystal's debut gallery

Three rooms:
- The Entrance Prism (Three.js dispersion)
- The Proof Lattice (E8-inspired test constellation)
- The Reflection Chamber (identity + verification)

Tech: Three.js, ES6 modules, 1708 LOC
For: Kristi (Weekend Dispatch Dec 2025)"
git push origin main
```

### Enable GitHub Pages
1. Go to repository settings
2. Pages → Source → `main` branch → `/` root
3. Save and wait ~1 minute

**Live URL**: `https://[username].github.io/art/crystal-gallery/`

## Link from Weekend Dispatch

Add to `weekend-update.html` in the gallery section:

```html
<a href="crystal-gallery/index.html" class="gallery-item">
    <div class="gallery-preview">
        <span class="gallery-preview-icon">💎</span>
    </div>
    <div class="gallery-meta">
        <div class="gallery-name">Crystal's Gallery</div>
        <div class="gallery-desc">Reflect, Refract, Disperse</div>
    </div>
</a>
```

## Browser Testing Checklist

- [ ] **Chrome/Edge**: Full Three.js functionality
- [ ] **Firefox**: ES6 modules load correctly
- [ ] **Safari**: WebGL scenes render
- [ ] **Mobile**: Responsive layout, touch works
- [ ] **Console**: No JavaScript errors
- [ ] **Performance**: 60 FPS in all rooms

## Performance Verification

Expected metrics:
- **Initial load**: < 2s (Three.js from CDN)
- **Room 1 (Prism)**: 60 FPS, ~500 draw calls
- **Room 2 (Lattice)**: 60 FPS, ~1200 draw calls (216 nodes + connections)
- **Room 3 (Reflection)**: Static, instant

## Troubleshooting

### "Failed to load module" errors
- Ensure server is running (not `file://` protocol)
- Check Three.js CDN is accessible: https://cdn.jsdelivr.net/npm/three@0.170.0/

### Three.js scenes not rendering
- Check console for WebGL errors
- Verify GPU acceleration is enabled
- Try different browser

### Cursor not visible
- Check if `cursor: none` is being overridden
- Verify cursor elements have `z-index: 10000+`

### Low FPS
- Reduce node count in `config.js` (LATTICE.gridSize from 6 to 4)
- Disable `antialiasing` in renderer options
- Check GPU is not throttled

## Content Updates

To modify Crystal's text:

1. **Prism intro**: Edit `index.html` Room 1 section
2. **Lattice stats**: Edit `styles/rooms/lattice.css` `.proof-card` values
3. **Reflection claims**: Edit `js/config.js` `CRYSTAL_INTRO` object
4. **Verification patterns**: Edit `js/rooms/reflection.js` `checkVerifiability()`

## Future Enhancements

See `README.md` "Future Enhancements" section for:
- Full E8 lattice implementation
- Real test suite API integration
- Advanced shader effects
- WebXR VR mode

---

**Status**: ✅ Ready for deployment
**Build**: December 22, 2025
**For**: Kristi (Crystal's debut)

∎
