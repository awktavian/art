# DEBT — design-token source (campaign a10)

**Canonical (public brand):** `projects/awkronos-waddle/packages/design-tokens` (`@awkronos/design-tokens`, `tokens.json` sha prefix `552e08cf`).

**XR adapter (this repo):** `lib/design-tokens.js` at art root — Three.js helpers; colony hexes should match waddle `tokens.json` `colors.colony.*`.

## Residual forks (do not expand)

Inline `COLONY_COLORS` still live in plaque/lighting/artworks/materials/typography (and mirror under `projects/awkronos/patents`). `lib/typography.js` has **drifted** hexes vs canonical colony (e.g. forge/nexus/beacon) — visual risk if force-synced without a museum pass.

## Next move (not done this turn)

1. Re-export numeric colony map from `../../lib/design-tokens.js` in `lib/materials.js`.
2. Delete per-file `const COLONY_COLORS` after a visual smoke.
3. Prefer art `patent-portfolio` as owner; treat `awkronos/patents` as consumer/copy (cross-repo-copy cleanup).
