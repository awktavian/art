# DEBT — design-token source (campaign a10)

**Canonical (public brand):** `projects/awkronos-waddle/packages/design-tokens` (`@awkronos/design-tokens`, `tokens.json` sha prefix `552e08cf`).

**XR adapter (this repo):** `lib/design-tokens.js` at art root — Three.js helpers; colony hexes match waddle `tokens.json` `colors.colony.*`. This match is no longer a prose pin: `tests/unit/identity-coherence.test.mjs` (run by `npm run test:unit`) compares hex/rgb/basis/name and the high-contrast layer against the master field-by-field, and separately pins the Fano geometry to the Kagami genome (`packages/kagami/core/prompts/colonies.py`, "## Fano Lines"). Authority-absent runs SKIP honestly; overrides: `WADDLE_TOKENS_JSON`, `KAGAMI_COLONIES_PY`.

## Residual forks — swept 2026-09-29 (lane DICT-B)

All inline `COLONY_COLORS` literals (plaque, lighting, wayfinding, materials,
typography, artwork-templates, p2-artworks, p3-artworks) and the
`WING_PROFILES` color table now derive from `lib/design-tokens.js`. The
coherence gate rejects any re-declared `COLONY_COLORS = {…}` literal outside
the token owner and requires the swept files to import it.

Sweeps that CHANGED rendered values (retired drifts vs the canonical master;
all others were byte-identical and stay pixel-stable):

| file | colony | old | new (canonical) |
|---|---|---|---|
| patent-portfolio/lib/typography.js | forge | `#F7931E` | `#D4AF37` |
| | flow | `#7ECFC0` | `#4ECDC4` |
| | nexus | `#E8D44D` | `#9B7EBD` |
| | beacon | `#C78FFF` | `#F59E0B` |
| | grove | `#95E17B` | `#7EB77F` |
| patent-portfolio/museum/wayfinding.js | forge | `#FFD700` | `#D4AF37` |
| | beacon | `#45B7D1` | `#F59E0B` |

**MUSEUM VISUAL PASS PENDING** on typography materials + wayfinding signage
(these two files carried the drifted palette; the WebGL museum render itself
was UNMEASURED offline — no headless GPU in `npm run test:unit`/`test:static`).

Single-purpose color uses that merely MEMBER a colony hex
(`SEMANTIC_COLORS`, `PRIORITY_COLORS`, glow accents, fallbacks like
`p3-artworks`' `0x67D4E4`) are vocabulary members, not forks — membership is
not uniqueness; the gate does not scan for hex occurrences.

## Derived CSS surface

`lib/colony-tokens.css` is generated from `lib/design-tokens.js` by
`scripts/generate-colony-css.mjs` (sha-stamped header;
`--check` = drift gate, exit 1 on stale; wired into the unit suite). Pages may
reference `var(--colony-*)` once the inline-hex sweep lands on the web surface
(DICT-C measured ~50 declaration sites blocked on this file).

## Still open

1. `projects/awkronos/patents` mirror still carries its own copy of the old
   table — port the import there after this repo's fold (cross-repo-copy
   cleanup; resolve that repo's own token owner before copying the import path).
2. Museum visual pass on the two changed files above.
3. Root `design-system.css` (typography-only, hand-maintained) has no colony
   hexes; it and the generated `lib/colony-tokens.css` can be merged into one
   linked surface at DICT-C's discretion.
