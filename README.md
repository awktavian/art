# art

Tim Jacoby's portfolio of interactive web pieces: generative art, 3D
experiences, games, and voice-enabled interfaces. Every project is a static
vanilla-JS page (no build step); shared code lives in `lib/`.

**Live site**: https://awktavian.github.io/art/

## What is where

- One directory per piece; the entry point is always `index.html`.
- `lib/` — shared libraries (design tokens, audio, visuals, voice overlay).
- `realtime-proxy/` — WebSocket relay to the OpenAI Realtime API (Fly.io,
  port 8766). Powers the voice personas in interactive pieces.
- `medverify/` — a separate repository, ignored here and not published.
- `docs/DEPLOY-STATUS.md` — canonical deployment record (GitHub Pages).
- `docs/QUALITY.md` — the static-site quality gate CI runs.
- `AGENTS.md` — full architecture and conventions for agent sessions.

## Build / run / verify

There is no build. Open any `index.html` in a browser, or serve the repo
root statically. Before committing, run the same gate as CI:

```bash
npm ci
npx playwright install chromium   # first time only
npm test
```

The gate checks link/asset targets, metadata, directory totals, PWA
manifests, and service workers, then mounts the tree at `/art/` in Chromium
and exercises representative interactive routes.

## Deploy

Push to `main`; GitHub Pages serves the branch tree as-is (`.nojekyll`, no
custom domain). `vercel.json` remains for incidental previews only.
