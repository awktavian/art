# DEBT — museum navigation.js cross-repo duplicate (lane E-ARTNAVDEDUP-1026)

**Status:** art side DONE (canonical declaration committed). Patents side **PROPOSED,
NOT APPLIED** — this lane's write authority is the `art` repo only;
`~/projects/awkronos/patents` is another owner's tree. Applying the text below is a
one-file comment insert for whoever owns that repo.

Census row: `projects/art/patent-portfolio/museum/navigation.js` near_duplicate of a
museum-side copy. **The census pointer was wrong** — `/Users/schizodactyl/museum`
contains no `navigation.js` at all, by working tree (`find` + `grep -I` for
`MuseumNavigation`, `PointerLockControls`, `noclipEnabled`, `_headBobPhase`) or by
history (`git log --all -- '*navigation.js'`, control-probed with `'*README.md'` → 9
rows, so the zero is real). The actual second copy is
`~/projects/awkronos/patents/museum/navigation.js`.

## Canonical call: `art` — by descent, by currency, by publication

| | art | patents |
|---|---|---|
| blob (HEAD == worktree, both clean) | `bd836bd95975…` | `d20f2aa3d96e…` |
| size | 1243 lines / 49959 B | 1129 lines / 45083 B |
| commits touching the file | 7 (`5a363a7` 2026-02-02 → `3d4d10d` 2026-02-22) | 1 (`8293838` 2026-02-04, "Initial commit") |
| remote | `github.com:awktavian/art` — published GitHub Pages | `~/.local/git/projects-awkronos-patents.git` — local bare only |
| verification wired | `npm test` (unit + `scripts/check-site.mjs` + playwright) | none observed |

Descent is not inferred, it is object-verified: **the patents blob `d20f2aa3d96e…` is
byte-identical to this file's blob at art commit `da76faf` (2026-02-07)**, and appears
in art's history as an *intermediate* step in the progression
`51fe640` → `d20f2aa` → `2683197` → `7e4a953` → `8ab2977` → `761d98b` → `bd836bd`.
Art's first version of the file (`51fe640`, 2026-02-02, 742 lines) predates the patents
repo's creation (2026-02-04), so the direction is art → patents. The snapshot was taken
from art's working tree before `da76faf` was committed — which is why the patents commit
is dated three days earlier than the art commit that carries the same bytes; the file's
mtime (`2026-02-04 01:22:48`) and its commit (`01:22:54`) agree to within seconds and
nothing touched it after.

Going art → patents the diff is **117 insertions / 231 deletions across 19 hunks**. The
insertions are the *older* form of each art feature, not new work: patents has no
capability art lacks.

## What the fork predates

- `import { DIMENSIONS } from './architecture.js'` — spawn point and wing distance are
  computed from the architecture data instead of literals (`-39` vs hardcoded `-20`;
  `DIMENSIONS.rotunda.radius + 5` vs `25`).
- Sprint + head bob (`sprintMultiplier`, `_headBobPhase/Amplitude/Offset/Smooth`), and the
  Shift-as-sprint binding the fork drops.
- `checkCollisionMultiRay()` — the 8-ray fan that accumulates blocked directions and slides;
  the fork uses a single ray plus a left/right guess at `moveDistance * 0.3`.
- `findGroundHeight()` with a 1 m cell cache and a persistent `_floorObjects` list; the fork
  re-traverses the scene and allocates a new array **every call, in the hot loop**.
- `calculateSlideMovement()` on pre-allocated vectors; the fork allocates 3 clones per call.
- `'galleries-loaded'`-event collision rebuild with a fallback timer, removed in `dispose()`;
  the fork fires a blind `setTimeout(…, 500)`.
- Velocity clamp by magnitude (kills the diagonal-speed exploit); the fork clamps per axis.
- Collidable set extended with `pedestal`/`artwork`/`exhibit`/`kiosk`.

## Two defects the fork still carries (both verified by reading the file, not the diff)

1. **Gravity applied twice** — `museum/navigation.js:725` (`velocity.y -= 20 * deltaTime`)
   and again at `:796` (`velocity.y -= 25 * deltaTime`). art applies it once.
2. **Teleport table collision** — its `Crystal Wing` entry is `(0, 0, -20)`, the same vector
   as `Vestibule`. Inert, because of the next point, but it is a wrong table.

`this.teleportPoints` is **dead data in both copies** — `git grep teleportPoints` in each
repo returns assignments only (`art` 75/446, `patents` 64/422) and no reader anywhere.
Wing teleports go through `teleportToWing()`'s computed angle, so nothing is lost by the
art side holding `[]`.

## Why not a parameterized single source

`art` and `patents` are separate static sites that each ship their own `museum/` directory
(the fork also carries `audio-manager.js` and `narrative.js`, which `art` does not, and the
other five museum modules in the pair have diverged too — measured:
`architecture.js` 206/1071, `gallery-loader.js` 123/244, `lighting.js` 161/258,
`wayfinding.js` 96/290, `wing-enhancements.js` 29/614). A shared source would mean either
the patents site importing across origins from `awktavian.github.io` (CORS + cache lifetime
+ no version pin, and the two trees disagree on `architecture.js` sizes so the import would
change behaviour, not dedupe it) or vendoring a copy under a new path — which is the silent
third copy this lane exists to prevent. The sound options are the two below.

## Options for the patents owner

1. **Port** — replace `museum/navigation.js` with art's current file, then fix the
   `DIMENSIONS` shape mismatch in that repo's own `architecture.js` (its copy is the 1071-line
   deletion away, so the import target is NOT equivalent: verify `DIMENSIONS.rotunda.radius`
   and `vestibule.depth` exist there before taking the file whole).
2. **Retire** — if the patents museum is not a live surface, delete the copy and link to art,
   the way `DEBT-design-tokens.md` item 1 already proposes for the colony table.

Either way, apply this header to whichever copy survives, so the pairing stays declared:

```
 * NEAR-DUPLICATE DECLARATION — this copy is NOT canonical (lane E-ARTNAVDEDUP-1026, measured 2026-10-26)
 *
 * CANONICAL: projects/art/patent-portfolio/museum/navigation.js
 *   origin github.com:awktavian/art, published https://awktavian.github.io/art/patent-portfolio/
 *   this file is a byte-identical snapshot of that file's blob at art commit da76faf
 *   (2026-02-07), frozen since this repo's only commit 8293838; it is 117 insertions /
 *   231 deletions behind across 19 hunks and carries two defects art already fixed:
 *   gravity is applied twice (lines 725 and 796) and the hardcoded teleport table sends
 *   Crystal Wing to the Vestibule position.
 * RULE — never edit both copies. Change navigation in art, then port it here whole.
```

## Note for the census

This row should be re-pointed: `projects/art/patent-portfolio/museum/navigation.js` ↔
`projects/awkronos/patents/museum/navigation.js`, not `/Users/schizodactyl/museum`. The
other five sibling pairs above are separate groups and were not touched by this lane.
