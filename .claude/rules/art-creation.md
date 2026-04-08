# Art Creation Rules

## Philosophy
Tim's art lives at the intersection of mathematics, algorithms, interactive narrative, and craft.
The goal is to 1000x — push boundaries, show off, create things that make people stop and stare.

## Creative Domains

### Generative Art
- Seeded PRNG (Xorshift128+ with FNV-1a hash) for deterministic infinite variations
- Colony-themed algorithms: each of the 7 Fano colonies produces distinct visual signatures
- "Breathing" backgrounds, particle systems, palette swaps
- Every piece should be reproducible from its hash seed

### 3D / WebGL / Three.js
- Museum-quality interactive experiences (see patent-portfolio)
- Instanced rendering for performance
- WebXR-ready where possible
- Semantic spatial layouts (not random — meaning in placement)

### Games & Interactive
- Monte Carlo analysis for strategy games
- Daily puzzle systems with deterministic seeding
- Physics simulations grounded in real mechanics
- LLM integration for dynamic game content

### Voice-AI Interfaces
- Every interactive project should consider PERCEPTION + ACTION tool surfaces
- Voice personas mapped through colony system (catastrophe theory personalities)
- Tools are sensorimotor interfaces for AI — NOT user-facing features

### Galleries & Curation
- Data-driven UIs (JSON manifests, structured metadata)
- Cinematic presentation (choreographed transitions, camera work)
- Fashion, film, architecture as curated experiences

## Technical Standards
- Vanilla JS, ES modules, no build step — zero friction to create
- IBM Plex Sans / IBM Plex Mono typography
- Dark void palette with ice (#00ced1) and gold (#c9a227) accents
- Fibonacci timing curves: 89, 144, 233, 377, 610, 987ms
- WCAG 2.1 AA accessibility mandatory
- `prefers-reduced-motion` always respected
- PWA-ready: service workers, manifests, offline support where appropriate

## When Creating New Art Projects
1. Create directory at project root with descriptive name
2. Entry point is always `index.html` (clean URLs via Vercel)
3. Use shared libs from `/lib/` — never duplicate
4. Add voice tools if interactive (perception + action)
5. Add to the Key Projects table in CLAUDE.md
6. Deploy via `deploy_to_vercel` and verify
7. Consider: does this push boundaries? Would someone screenshot this?

## Available Creative Tools
- **Figma MCP** — pull design references, screenshots, design system tokens
- **HuggingFace MCP** — search models, papers, spaces for inspiration
- **Playwright** — browser automation for testing interactive pieces
- **Algorithmic Art skill** — p5.js with seeded randomness patterns
- **Canvas Design skill** — visual art in PNG/PDF with design philosophy
