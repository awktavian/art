# DEBT — museum navigation.js cross-repo duplicate (lane E-ARTNAVDEDUP-1026)

**Status: CLOSED — APPLIED on both sides.** art side DONE (canonical declaration
committed, published at `d2e35c3`). Patents side **APPLIED**, not proposed: the port landed
as `72faa42166199654d450269d94eb153ea83c3583` ("fix(museum): port canonical navigation.js
here; pair becomes declared mirror", 2026-10-26) — that is **Option 1** below, taken whole —
and the row was then closed by execution as
`8d3197a489a5716938bff09e495dafc9ed82f7f8` ("fold(REFILL-1027): RSI-PATENTS-PORTFOLD-1028",
2026-10-28), which is the current `main` of `~/.local/git/projects-awkronos-patents.git`
(measured: `git ls-remote origin refs/heads/main` from the patents checkout, and
`merge-base --is-ancestor 72faa42 8d3197a` → `rc=0`). The closure fold ships
`tests/CENSUS-museum-navigation-mirror.md` (the receipt) and
`tests/CENSUS-museum-navigation-mirror.check.mjs` (a hermetic 6-leg guard).

The write-authority sentence that produced the old "NOT APPLIED" line was true of its own
lane and is now historical: closing the row needed no authority in `art`, only a lane bound
to the `patents` tree. What follows is the 2026-10-26 measurement, kept as the record of
*why* `art` was chosen canonical; where it speaks of the fork in the present tense it means
the pre-port bytes, recoverable at blob `d20f2aa3d96e8d7496df53dd63aac9ac5105ff8a`
(1129 lines / 45083 B). Two residuals stay open and are recorded at the foot of this note:
the `art` canonical header is one port behind its own file, and the guard protecting the
receipt is shipped but wired to nothing.

> **Both halves of that sentence are the 2026-10-28 state. Re-measured 2026-10-30 by lane
> `MUSEUM-NAVJS-1030`: the second is CLOSED** — the guard is now wired to a tracked
> `.githooks/pre-commit` on `patents origin/main` (see the STATUS block under residual 2) —
> **and the first stands**, but it is not a docs edit: taking it moves four files across two
> repos and no ordering of the two pushes leaves the guard truthful in the interval (see the
> STATUS block under residual 1 and the section at the foot of this note).

Census row: `projects/art/patent-portfolio/museum/navigation.js` near_duplicate of a
museum-side copy. **The census pointer was wrong** — `/Users/schizodactyl/museum`
contains no `navigation.js` at all, by working tree (`find` + `grep -I` for
`MuseumNavigation`, `PointerLockControls`, `noclipEnabled`, `_headBobPhase`) or by
history (`git log --all -- '*navigation.js'`, control-probed with `'*README.md'` → 9
rows, so the zero is real). The actual second copy is
`~/projects/awkronos/patents/museum/navigation.js`.

## Closure evidence — re-measured at the published tips (lane RSI-ART-DEBT-FLIP-1028, 2026-10-28)

Every figure below was taken again here from the object db at each repo's published tip —
not lifted from the receipt, which is the same measurement one step upstream.

| | canonical (`art`) | mirror (`patents`) |
|-|-|-|
| path | `patent-portfolio/museum/navigation.js` | `museum/navigation.js` |
| published tip | `d2e35c3875c755f6940d466efd19c402304352c3` | `8d3197a489a5716938bff09e495dafc9ed82f7f8` (`main`; its nav bytes are identical to the `72faa42` port's — same blob both sides) |
| git blob | `6567e4f71f87d6dc72b5840bd89354f5abc9b752` | `66dd3d5da57a6464e2e689abdfb763f896cbdeb8` |
| whole file | 1270 lines / 51645 B | 1284 lines / 52982 B |
| sha256 (whole file) | `aba48a95050f8d94a1f20c40688243d9834a8424c9c00b62ebe74280fb02f9e9` | `ecd1c2c3cd58d39437967aaeff6d53812c1293489ee4b3e81185ccbd86f9b122` |

The blobs differ, and they differ **only** in their leading provenance/doc header:
`/usr/bin/diff` on the whole files returns exactly **5 hunks**, all inside it
(`0a1,10`, `10c20,22`, `12,22c24,30`, `24,30c32,43`, `32,35c45,49`) — 37 added / 23 removed
lines. Composition of all 60 changed lines, counted: 50 doc-comment `*` lines, 9
`// PROVENANCE` lines, 1 blank line inside that same header block — **zero executable
statements**. Stronger than the prefix test, and the reason this note states it both ways:
every changed line number lies above its own file's header close (highest changed line 35
against `*/` at 36 on the canonical side, 49 against `*/` at 50 on the mirror side), so
nothing past a header is in any hunk. Below each doc-comment close the bodies are
**byte-identical**:

| body | lines | bytes | sha256 |
|-|-|-|-|
| canonical from line 37 | 1234 | 49768 | `1e2054a6b765ab682868986813090b392ab191ae01cdfd8a31c37c6130d64c7c` |
| mirror from line 51 | 1234 | 49768 | `1e2054a6b765ab682868986813090b392ab191ae01cdfd8a31c37c6130d64c7c` |

`cmp` of those two bodies → `rc=0`. Positive control, because an instrument that cannot go
red proves nothing: append one line to the mirror body → `rc=1` (`cmp: EOF on
…/canon_body.js`), remove it → `rc=0`. The 6-leg guard was run against the closure fold's
own bytes in a scratch tree laid out from `8d3197a` → **6 pass / 0 fail**; controlled the
same way, mutating a single hex in the receipt → `rc=1` on
`the census receipt exists and records both sides byte-for-byte`, restore → 6/6. And the
closure fold itself touched only `tests/` — 180 insertions across those two files, **zero
edits to published code**, so no navigation byte moved to make this row read closed.

**The edit rule the census encodes: canonical first, mirror follows.** Navigation is
changed in `art` and only in `art`; the fix is then *ported whole* to `patents` — never
hand-edited into the mirror to close a delta, and never edited in both copies
independently. The mirror's header carries the canonical blob it was ported from
(`6567e4f71f87…`) alongside its own pre-port recovery blob (`d20f2aa3d96e…`), so the next
measurement is a `cmp` against four named objects rather than a re-derivation of descent.
Neither copy is deletable: both sites deploy independently as static sites and each imports
its own local `museum/navigation.js` (`main.js:24` here, `main.js:23` there).

## Canonical call: `art` — by descent, by currency, by publication

The call was made pre-port, against those bytes, and it still stands — the port moved the
fork to art's file, it did not change which side is authoritative. Figures are the
2026-10-26 pair (current published values are in the closure section above).

| | art | patents |
|---|---|---|
| blob (HEAD == worktree, both clean) | `bd836bd95975…` | `d20f2aa3d96e…` |
| size | 1243 lines / 49959 B | 1129 lines / 45083 B |
| commits touching the file | 7 (`5a363a7` 2026-02-02 → `3d4d10d` 2026-02-22) | 1 (`8293838` 2026-02-04, "Initial commit") |
| remote | `github.com:awktavian/art` — published GitHub Pages | `~/.local/git/projects-awkronos-patents.git` — local bare only |
| verification wired | `npm test` (unit + `scripts/check-site.mjs` + playwright) | none observed pre-port; at `8d3197a` there is a playwright suite under `tests/` and the census guard — but no CI and no script that runs the guard, residual 2 |

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

All eight are in the mirror now. Counted in each blob, pre-port (`d20f2aa`) → canonical
(`6567e4f`): `checkCollisionMultiRay` 0 → 2, `sprintMultiplier` 0 → 2, `_headBobPhase`
0 → 3, `_floorObjects` 0 → 5, `galleries-loaded` 0 → 4, `DIMENSIONS.rotunda.radius` 0 → 2,
and the extended collidable set (`pedestal`/`artwork`/`exhibit`/`kiosk`) 0 → 1 each.
Occurrences run exactly one higher in the mirror than in canonical for several of these,
which is the mirror's longer header naming them once more, not body drift — the bodies are
`cmp`-identical (see the closure section).

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

## Two defects the fork carried (verified pre-port by reading the file, not the diff) — both measured gone

Re-measured post-port, from the mirror blob `66dd3d5`:

1. **Gravity applied twice — fixed by the port.** Pre-port the fork subtracted at `:725`
   (`velocity.y -= 20 * deltaTime`) *and* again at `:796` (`- 25 * deltaTime`). In the
   ported copy there is exactly one such subtraction, at line 866, matching canonical's one
   at line 852 (`grep -n 'velocity.y -= 2[05] \* deltaTime'` → 2 hits pre-port, 1 hit now).
2. **Teleport table collision — gone with the table.** The fork's populated
   `this.teleportPoints` (assigned at pre-port line 422) sent `Crystal Wing` to `(0, 0, -20)`
   at line 431 — the identical vector of `Vestibule` at line 423, nine entries into a
   nine-entry table. The ported copy assigns `this.teleportPoints = []`, as canonical
   does; the wrong table no longer exists to be wrong.

`this.teleportPoints` is **dead data in both copies** — `git grep teleportPoints` in each
repo returns assignments only (`art` 75/446, `patents` 64/422, both pre-port) and no reader
anywhere. Post-port the count is 3 per copy: the two `= []` assignments plus one mention in
the provenance header. Wing teleports go through `teleportToWing()`'s computed angle, so
nothing is lost by either copy holding `[]`.

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

This reasoning is not superseded by the closure — it is *why* the close took the form it did.
The row closed as a declared mirror with a port-whole rule, not as one file with two
importers, and the `architecture.js` divergence it rests on is still real (1761 lines at art
`d2e35c3` against 896 at patents `8d3197a`, measured at both published tips). The sibling
`wing`-block divergence found under Option 1 above is a further instance of the same fact,
not a counterexample to it.

## Options for the patents owner

Outcome first: **Option 1 was taken.** `72faa42` ported canonical `navigation.js` into the
patents tree whole — and, measured off the commit itself, that is all it did:
`museum/navigation.js | 272 insertions(+), 117 deletions(-)`, one file. `architecture.js` was
**not** touched, because the shape check this option demanded came back already satisfied,
and stronger than asked (see the note under Option 1). Option 2 (retire) is moot and was
always the wrong answer here — neither copy is deletable. The two options are kept below as
the decision record.

1. **Port** *(applied — `72faa42`)* — replace `museum/navigation.js` with art's current file, then fix the
   `DIMENSIONS` shape mismatch in that repo's own `architecture.js` (its copy is the 1071-line
   deletion away, so the import target is NOT equivalent: verify `DIMENSIONS.rotunda.radius`
   and `vestibule.depth` exist there before taking the file whole).
   **Measured at the ported bytes:** both named keys resolve, and resolve *identically* —
   `rotunda.radius` is `20` in `art` and `20` in `patents`, and the whole `vestibule` block
   is byte-equivalent in value (`width: 10`, `depth: 15`, `height: 6` in both). Going further
   than the check asked: `navigation.js` reads exactly **one** `DIMENSIONS` key,
   `DIMENSIONS.rotunda.radius` (two occurrences, same count in both copies), so the real
   divergence between the two `architecture.js` files sits in the `wing` block — `art` has
   `width: 4` plus `corridorCeilingMin`/`vestibuleDepth`, `patents` still has `width: 12`
   without them — and that block is **unreached by this module**. Taking the file whole was
   therefore safe without any `architecture.js` edit; no follow-up is owed on that account.
   The `wing` divergence is its own row, not this one.
2. **Retire** *(not applicable)* — if the patents museum is not a live surface, delete the copy and link to art,
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

That proposed text is **superseded by what actually landed**, and deliberately so — it
describes a fork that no longer exists. The applied declaration at the mirror's head is a
`// PROVENANCE: mirror copy` comment block above the doc comment, then a
`NEAR-DUPLICATE DECLARATION — this copy is the MIRROR; the other one is canonical` section
inside it, which instead of counting what the copy was behind records what the port
*brought* (the DIMENSIONS-driven geometry, sprint + head bob, the 8-ray slide fan, the
cell-cached ground lookup, the magnitude clamp, the extended collidable set) and names both
defects as gone. It carries two 40-hex anchors rather than one: the canonical blob it was
ported from (`6567e4f71f87…`) and its own pre-port recovery blob (`d20f2aa3d96e…`). The
`RULE` line survives verbatim in spirit and is enforced by the guard. `72faa42` carries the
lane id `MUSEUM-NAV-DUP-1027`, not this note's `E-ARTNAVDEDUP-1026` — the declaration was
authored by one lane and applied by another, which is exactly the pairing this doc asked for.

## Note for the census

Done, and now enforced rather than requested. The row reads
`projects/art/patent-portfolio/museum/navigation.js` ↔
`projects/awkronos/patents/museum/navigation.js` (canonical ↔ declared mirror, zero content
drift), not `/Users/schizodactyl/museum` — and the closure receipt's *Disambiguation pointer*
section makes that machine-checked from the patents side too: a bare `museum/navigation.js`
anchor resolves to three different things in this estate, and
`git -C ~/museum ls-files | grep -i navigation` is a measured zero (re-measured 2026-10-28,
`git log --all -- '*navigation.js'` also empty; the `'*README.md'` control on that same
probe now returns 11 rows, up from the 9 this note first recorded — museum history moved,
the zero did not), with the law written into `~/museum/ARCHITECTURE.md` at its `origin/main`
`ae1ec27`. The other five sibling pairs above are separate groups and were not touched by
either lane.

## Residuals this close leaves open (recorded, not fixed — out of scope)

### 1. The `art` canonical header is one port behind

> **STATUS 2026-10-30 (lane MUSEUM-NAVJS-1030): still open, re-measured, and NOT a docs edit —
> see the foot of this note.** A lane bound to `patent-portfolio/museum/navigation.js` on the
> same `near_duplicate` row re-ran the whole recipe at both repos' published tips. The pair is
> still byte-clean, the false header prose is still there verbatim, and the reason this row was
> not taken is recorded in "Residual 1, re-measured at the 2026-10-30 tips".

The row is closed on the patents side and on the census side, and the `patents` mirror header
is now honest about it. **The `art` canonical header is not.** At `d2e35c3` the CANONICAL
block in `patent-portfolio/museum/navigation.js` still narrates the fork in the present tense
as it was pre-port, measured verbatim off blob `6567e4f`:

- "A second copy of this module lives in another repository and **is now 231 lines behind
  this one**" — it is not; the bodies are byte-identical below the headers.
- "Delta: 117 insertions / 231 deletions across 19 hunks (here `bd836bd` — 1243 lines,
  49959 B; there `d20f2aa` — 1129 lines, 45083 B)" — both blobs are superseded.
- "It **still carries** two defects this file fixed: gravity is applied twice (its lines 725
  and 796 …), and its hardcoded teleport table sends Crystal Wing to the same position as
  Vestibule" — both measured gone (one gravity subtraction, mirror line 866;
  `this.teleportPoints = []` in both copies).

Nothing in `art` would notice. The 6-leg guard ships in `patents` and is deliberately
hermetic — its header states it "reads only THIS repository — no cross-repo reads, so its
green is hermetic and its red always means something in this tree changed". Measured
consequence on the `art` side: `git grep -l navigation d2e35c3 -- tests` returns **zero
files** (the only test matching `MIRROR` is `tests/unit/identity-coherence.test.mjs`, which
is about design tokens). So the declaration that can rot silently is the canonical one, and
the mirror is the guarded one — with the weight that phrase now carries, see residual 2.

Left unfixed here on purpose: this lane's write scope is this note, and the rule the census
encodes is canonical-first — a header refresh to `navigation.js` is a change to the canonical
file, which then obliges a port to the mirror and a re-measurement of the receipt. That is a
lane bound to do the pair, not a docs edit smuggled into one. The bytes a reader should get
from `art` are blob `6567e4f` at `d2e35c3`, which is exactly what this worktree holds
(`git hash-object patent-portfolio/museum/navigation.js` → `6567e4f71f87…`,
`status --porcelain` on that path empty), so `art` is neither stale nor dirty at the tip —
only its prose is one port behind. Residual 2 of the receipt (a local `art` checkout parked
at `054c275`, one commit back from `origin/main`) is a separate, fast-forwardable condition
of one working tree and is not this published surface.

### 2. The guard that protects this row is shipped, but nothing runs it

> **STATUS 2026-10-30 (lane MUSEUM-NAVJS-1030): this residual is CLOSED — the invocation this
> section says does not exist now exists.** Lane
> `PATENTS-GUARD-WIRE-1028` wired the census guard to a tracked `.githooks/pre-commit` in the
> `patents` tree, folded as `1921ef6471377ed8d83b465cb2ca5d33e8112d91` (2026-10-28, 153 new
> lines + this receipt's own invocation section). Re-measured today from `art`: the file is
> present and executable at `patents origin/main` `c7b7ac1afdf1adaa7766fda807eac01c77a04281`
> (`1921ef6` is an ancestor of it, `rc=0`), `git -C ~/projects/awkronos/patents config --get
> core.hooksPath` → `.githooks`, and the guard run directly in that tree is green `6/6` at
> `rc=0` unpiped. That green grades the published bytes, not a private tree: `museum/navigation.js`,
> the receipt, the guard and the hook all carry the same blob at `1921ef6` (the checked-out tip) and
> at `c7b7ac1` (`origin/main`), and `status --porcelain` in that checkout is 0 rows.
> What was NOT re-measured here: a live firing. Demonstrating one requires
> staging a watched path in the shared `patents` checkout, which this lane does not touch; that
> proof is `PATENTS-GUARD-WIRE-1028`'s own (its fold message records staged-watched PASS,
> planted-drift REFUSED `rc=1`, and a fresh-clone activation capturing both outcomes). The
> per-clone caveat it ships with still stands and is why "wired" is not the same as "armed
> everywhere": `core.hooksPath` is one config line per clone, git silently skips a `hooksPath`
> target that a tree does not have, and the fold message names Studio as still owing
> fold → fast-forward → activation, in that order.

Measured at patents `8d3197a`, which is the tree that carries the receipt:

- `git ls-tree -r --name-only 8d3197a | grep -iE 'workflows|\.ya?ml$'` → **empty**; there is
  no `.github/` in that tree at all. No CI, so no job can execute the guard.
- `git grep -n 'node --test|CENSUS-museum-navigation-mirror.check' 8d3197a` → **one hit**, and
  it is line 2 of the guard file itself, its own `// Run:` comment. No script invokes it.
- `tests/package.json` `scripts.test` is `npx playwright test` (plus four headed/webgl/report
  variants); none is `node --test`.
- The guard is named to stay out of the Playwright collection on purpose — its header explains
  that `tests/playwright.config.js` sets `testDir './'` with the default
  `**/*.@(spec|test).?(c|m)[jt]s?(x)` match, so a `.spec`/`.test` name would be swallowed into
  the browser suite. Correct reasoning, and the reason it is invisible to `npm test`.

So all six legs are real and do go red (positive-controlled above: one mutated hex → `rc=1`),
but the guard is a **manual** instrument holding a machine-checkable claim. Its green is only
as current as the last human who ran it, which is precisely the failure mode this pair has
already been caught in once. Fixing it is a one-line `tests/package.json` addition in the
`patents` tree (`"test:census": "node --test tests/CENSUS-museum-navigation-mirror.check.mjs"`)
plus, to make it bite, something that runs it — out of this lane's scope on both counts, so
it is recorded here rather than edited there. The row's content claim does not depend on it:
the `cmp` in the closure section is reproducible from four named blobs with the recipe in the
receipt, and was re-run here at `d2e35c3` × `8d3197a` rather than inherited.

## Residual 1, re-measured at the 2026-10-30 tips — the row is not consolidatable, and the header fix is a four-file cross-repo atomic change

Lane `MUSEUM-NAVJS-1030` (forge) was bound to `patent-portfolio/museum/navigation.js` on a
`code_map_rsi_targets` T0 row, `kind=near_duplicate`, `rankScore 7.396875`, generation
`4f0a12eb52414c06a1e6d864587a2bed`. Admission was checked rather than assumed:
`code_map_freshness` → headline `state=clean`, `generationCorrelation.verdict=clean`
(slim and dense carry the same id), `denseServeAllowed=true`, manifest verified
(`artifactCheck.status=ok`, 13 checked / 0 mismatches), encoder live (dim 896). One disclosure,
non-blocking and recorded because it changes what the numbers describe: the generation was
produced on `tims-mac-studio` and read here on `tims-macbook-pro-2`
(`generationHost.verdict=host_foreign`, `hostCorrelation=split-brain`, `blocksServe=false`), so
the row's census is Studio's, not this host's.

The lane's two admissible outcomes were: consolidate if one copy is a stale derivative, or emit a
typed absence with the diff that proves it. **Verdict: typed absence.** Nothing to consolidate,
and the residual this note still owes cannot be taken from one repo.

### The pair, re-measured from the object db at both published tips

`git ls-remote origin refs/heads/main` on each tree, then `git cat-file` at those refs — not the
working trees, which is how residual 2 of the `patents` receipt fooled an earlier reader.

| | canonical (`art`) | mirror (`patents`) |
|-|-|-|
| published tip today | `7486a74308b0e829cf61ae99b45274f8bb4b1437` | `c7b7ac1afdf1adaa7766fda807eac01c77a04281` |
| tip when the receipt was written | `d2e35c3875c7…` | `72faa4216619…` / `8d3197a489a5…` |
| `navigation.js` git blob | `6567e4f71f87d6dc72b5840bd89354f5abc9b752` | `66dd3d5da57a6464e2e689abdfb763f896cbdeb8` |
| sha256 / lines / bytes | `aba48a95050f8d94…` / 1270 / 51645 | `ecd1c2c3cd58d394…` / 1284 / 52982 |

**Both tips moved; neither `navigation.js` byte did.** The `patents` pair of commits that landed
since the receipt (`2bd79cc`, `c7b7ac1`) touch `artworks/p1-efe-cbf.js` and
`lib/settings-menu.js`; `git rev-parse 1921ef6:museum/navigation.js` and
`…origin/main:museum/navigation.js` return the same blob. Re-running the receipt's own recipe at
today's tips reproduces every figure it records:

- `tail -n +37` (canonical) against `tail -n +51` (mirror): 1234 lines / 49768 B **both sides**,
  sha256 `1e2054a6b765ab682868986813090b392ab191ae01cdfd8a31c37c6130d64c7c` both sides,
  `cmp` → **rc=0**.
- Positive control on that instrument, because an identity check that cannot go red proves
  nothing: one appended line to a copy of the mirror body → `cmp: EOF on …/canon_body.js`,
  **rc=1**.
- `/usr/bin/diff` on the whole files → 5 hunks (`0a1,10`, `10c20,22`, `12,22c24,30`,
  `24,30c32,43`, `32,35c45,49`), 37 added / 23 removed — identical to the recorded hunk census.
  Filtering all 60 changed lines for anything that is not a `*` / `//` / blank header line
  returns **zero rows**: still no executable statement in the delta.
- The `patents` guard, run read-only against its own tree: `node --test
  tests/CENSUS-museum-navigation-mirror.check.mjs` → 6 pass / 0 fail, **rc=0 unpiped**. The first
  reading of that rc came through `… | tail`, and zsh does not export bash's `PIPESTATUS`, so
  what the shell reported was `tail`'s status, not the guard's. Re-run with the output redirected
  and `$?` taken directly. An rc quoted from a pipe is not the instrument's rc.

So neither copy is a stale derivative of the other: the pairing is declared in both headers, the
bodies are byte-identical below them, and the claim is guarded. A shared module is not available
at any price worth paying — it would mean the `patents` static site importing across origins from
`awktavian.github.io` (no version pin, CORS, cache lifetime, and the two trees disagree on
`architecture.js`, so the import would change behaviour rather than dedupe it) or vendoring a
third copy under a new path, which is the silent-fork outcome this note exists to prevent. Each
site imports its own local file: `main.js:24` here, `main.js:23` there.

### The `chess-vision` twin family named by the row is not a twin

`code_map_neighbors path=projects/art/patent-portfolio/museum/navigation.js`, top of the ranking:
`projects/awkronos/patents/museum/navigation.js` **0.7966**, then `patents/main.js` 0.5666,
`art/patent-portfolio/main.js` 0.5625, `chess-vision/public/js/viz/camera.js` 0.49,
`patents/museum/wayfinding.js` 0.4863, `awkronos-waddle/apps/hub/public/chess/js/viz/camera.js`
0.4858, `chess-vision/public/js/viz/main.js` 0.4388 (scores are anisotropy-corrected cosines over
a corpus with baseline 0.2409; comparable within band only). The real pair sits a full 0.23 above
everything else; the chess rows are third-tier.

Measured directly, not by score: intersecting the unique lines of ≥25 characters of the canonical
body (751 such lines) with each chess-vision file gives **0 shared lines, in both cases**.
`viz/camera.js` is 65 lines / 2326 B and `viz/main.js` 595 lines / 26742 B, against 1270 / 51645
here. There is no code in common; the embedding is scoring shared WebGL camera-control vocabulary.
A future `near_duplicate` row on this file should expect same-name siblings in unrelated apps to
appear in its neighbourhood — the row that matters is the repo-qualified one above, which is what
the receipt's disambiguation pointer exists to say.

### Estate-wide copy census — the question consolidation actually asks

`find ~/projects -name navigation.js`, excluding `.git`, `node_modules` and `dist`: three paths,
**two** content sets. `awkronos/patents/museum/navigation.js` and
`awkronos/patents-wt-MUSEUM-NAV-DUP-1027/museum/navigation.js` are both `ecd1c2c3…`;
`art/patent-portfolio/museum/navigation.js` reads `75f1b282…` (1243 lines / 49959 B). That last
number is residual 2 of the receipt reproducing itself: the shared `art` checkout sits at
`054c275`, three commits behind its own `origin/main` `7486a74`
(`git rev-list --left-right --count HEAD...origin/main` → `0 3`, i.e. zero ahead / three behind),
and `git status --porcelain` on that
path is empty — stale by checkout, not dirty. A worktree laid out at `7486a74` gives blob
`6567e4f…`, sha256 `aba48a95…`, 1270 lines: the published canonical bytes, which is what the
receipt records and what this lane branched from. Anyone reading the shared checkout and
concluding "`art` is behind" is reading a working tree, not the surface.

`~/museum` (tip `801edf2f6c164dc009705cd5aeba2bed3dd8a499`) holds no `navigation.js` and never
did: `git ls-files | grep -i navigation` → 0 rows, `git log --all -- '*navigation.js'` → 0 rows,
worktree `find` → 0 hits, with `git log --all -- '*README.md'` → **13 rows** as the positive
control on those probes (the receipt recorded 9 in October; museum history moved, the zero did
not). No third copy exists to fold into either site.

### What is actually still wrong, and why one repo cannot fix it

The canonical header's declaration block (lines 9–35, `*/` at 36) still asserts, in the present
tense, three things that are false at today's bytes:

- *"A second copy of this module lives in another repository and is now 231 lines behind this
  one"* — the bodies are `cmp`-identical.
- *"Delta: 117 insertions / 231 deletions across 19 hunks (here `bd836bd` — 1243 lines, 49959 B;
  there `d20f2aa` — 1129 lines, 45083 B)"* — both blobs superseded; and those two numbers are
  themselves the pre-port bytes, which is why the stale shared checkout above matches them.
- *"It still carries two defects this file fixed: gravity is applied twice … and its hardcoded
  teleport table sends Crystal Wing to the same position as Vestibule"* — both measured gone by
  this note's own closure section, and the mirror's header now says so in the past tense.

Refreshing that prose changes `art`'s whole-file sha256. Four files then have to move together:

1. `patent-portfolio/museum/navigation.js` here — and the replacement block must be **exactly 36
   lines**, or the receipt's `tail -n +37` recipe and its "canonical from line 37" row both break.
2. `museum/navigation.js` in `patents` — its `// PROVENANCE` lines 2–3 name `art`'s blob, sha256
   **and tip** in the present tense ("CANONICAL navigation.js is …"), so they must follow; editing
   them changes the mirror's own whole-file sha256.
3. `tests/CENSUS-museum-navigation-mirror.md` — the pair table's **both** rows, both tips, the
   line/byte counts and the hunk census are all a function of 1 and 2.
4. `tests/CENSUS-museum-navigation-mirror.check.mjs` leg 4, which hardcodes `art`'s whole-file
   sha256 `aba48a95050f8d94…`, `art`'s blob `6567e4f71f87…` and `art`'s tip `d2e35c3…`; after 1,
   none of the three is `art`'s live value.

The trap the receipt records about leg 6 generalises to leg 4, and bites harder there: leg 4 only
tests that those literals appear **somewhere in its own repo's markdown**, and the guard reads no
cross-repo bytes by design ("reads only THIS repository — no cross-repo reads, so its green is
hermetic"). So **no ordering of the two pushes has a truthful intermediate state.** Land `art`
alone and the receipt records an `art` sha that no longer exists while leg 4 keeps matching the
dead hex and stays green — the instrument reads measured on a row it has just made false. Land
`patents` alone and the receipt asserts an sha `art` has never carried. This lane's write scope is
one path in one repo; being the first half of that change is how the guard gets defeated, so it
declines 1–4 and says so here instead.

The fold that takes it needs: both trees branched off their published tips, the four files staged
as one set (the `patents` pre-commit hook grades the whole watched quartet and refuses on any
unstaged slice — `git diff --name-only` across the watched paths must be empty), hashes computed
from the final bytes before the commit, and **one fold landing both refs**, with the fold message
naming the other ref. Leg 3 of the guard still requires the mirror to carry `6567e4f…` as its
ported-from anchor, so that hex stays in the mirror header as history while the live `art` values
are added beside it — and the receipt's own law then applies: a full sha256 in that file must be a
live one, so `aba48a95…` leaves the table rather than being kept as a counterfactual.

**The decoupling that would make residual 1 cheap, offered to the guard owner, not applied here.**
Stop pinning `art` bytes inside `patents`: keep the live assertion hermetic (leg 6 against the
mirror row, keyed to the table rather than grepped from the prose — the cure the receipt already
names for leg 6), and demote leg 4's three `art` literals to a dated snapshot the receipt labels
"art as measured at `d2e35c3`, 2026-10-28". Pinning `art`'s *repo tip* was already known to rot on
its own: `d2e35c3` → `7486a74` is three commits in two days and not one of them touched
`navigation.js`. A literal that changes whenever the other repo commits anything is a staleness
generator wearing a guard's costume. With that change an `art` header refresh costs one `art`
commit plus a receipt re-dating, and the guard stays honest if either half lands alone.

### What this lane changed here, and what it ran

- **Changed: this note, and only this note.** No byte of `museum/navigation.js` moved in either
  repo, so every figure the receipt records stays live and the guard stays green — which is the
  point of declining 1–4 rather than doing 1 alone.
- `npm run test:unit` (`node --test tests/unit/*.test.mjs`), run in a worktree laid out at
  `7486a74`: 40 tests, 0 fail, **rc=0**, before and after this edit.
- `npm run test:static` (`node scripts/check-site.mjs`): **rc=1 — before and after, with the same
  two lines of output**, so it is a pre-existing red at the branch base and not a product of this
  edit. Its cause is host-local, not tree-local: it reads `/tmp/proof-report.json` on whatever
  machine runs it and refuses to publish counts it cannot verify (`corpus "hong" is UNMEASURED`)
  and reports `wiles/index.html: corpus statistics disagree with /tmp/proof-report.json`. The
  cure it offers (`node scripts/sync-corpus-stats.mjs`) would rewrite `wiles/index.html` from this
  satellite's sidecar; that is a content change to a published page driven by a host-local file,
  owned by whoever holds the Studio-side proof report — recorded, not run.
- `npm run test:browser` (playwright): **not run.** A lane that did not pay for a browser green
  does not claim one.
- `patents` guard `6/6` at `rc=0` unpiped, and `hooksPath=.githooks` with the hook file present at
  mode `100755` on its published tip — see the residual-2 status above.
