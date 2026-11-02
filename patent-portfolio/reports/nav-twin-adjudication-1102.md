# nav-twin-adjudication-1102 — T0 near_duplicate navigation.js (7.40) adjudicated

**Lane:** RSI40-1102 R31 (kind grove) · **Base/PIN:** art origin/main
`0803caac006d5af44c8e1db7aa8b1b6ace1d7163` (V4 visual fold) · **Measured:** 2026-11-02
**Patents side:** `c7b7ac1afdf1adaa7766fda807eac01c77a04281` — re-read live this turn via
`git -C /Users/schizodactyl/projects/awkronos/patents ls-remote origin refs/heads/main`.
(The local patents checkout is at `1921ef6`, 2 behind; every patents measurement below is
against the published tip object, not the checkout.)

**Register adjudicated against:** `patent-portfolio/NEAR-DUPLICATE-TWINS.json`
(located at that path — the roster guessed `patent-portfolio/reports/`; the register is at the
patent-portfolio root, schema `art-museum-twin-register/1`). navigation.js was treated
READ-ONLY per the R2 owner declaration; this file is the lane's only write.

## Instruments used (disclosure, per register law "similarity never authorizes consolidation")

1. **Primary — byte truth, this turn:** `git show <tip>:<path>` → `git hash-object --stdin`
   (blob equality), `shasum -a 256` (whole-file and tail-split body identity), and
   `/usr/bin/diff` normal format (hunk count, `<`-lines pooled = art-only, `>`-lines =
   patents-only). All counts below are from these executions.
2. **Secondary — dense, corroboration only:** `code_map_freshness` first: state
   `encoder_degraded` (`encoder_snapshot_missing` — the jina query encoder snapshot is not on
   this host, tims-macbook-pro-2), but `denseServeAllowed: true` and generation correlation
   `clean` (8ce4d3eaa3de41d3a0d236f7dd1c9416). So `code_map_semantic_search` was NOT usable
   (needs the query encoder); `code_map_neighbors` IS (no query encoder). Over
   `projects/art/patent-portfolio/museum/navigation.js` its #1 neighbor is
   `projects/awkronos/patents/museum/navigation.js` at **anisotropy-corrected cosine 0.7948**
   (corpus anisotropy baseline 0.2422, 896-dim, coverage 1.0 over 38,898 rows). This score
   classifies; it is band order, not a measured quantity, and per the register's law it
   authorizes nothing. The navigation pair is the ONLY pair given a dense score here —
   11 neighbors-calls for a family whose byte truth is already settled would add noise, not
   evidence.
3. **False-zero caught and named:** the host `diff` is shimmed to `delta` (pretty colorized);
   a first pass through it returned hunk=0/aonly=0/ponly=0 on every pair — a wrapper
   false-zero, not file quiet. Re-measured under `/usr/bin/diff`, the instrument the register
   itself names. All numbers below are from that re-run.

## Headline verdict

**The T0 `near_duplicate` row on navigation.js (rankScore 7.40) is a FALSE-POSITIVE at the
published tips, and the register survives the re-measurement 100%:** every one of the 11
pairs' four pin families (art blob, patents blob, whole-file sha256 ×2, /usr/bin/diff
hunk/`<`/`>` counts) and all 5 declared body-identity sha256 values reproduced byte-for-byte
this turn, at both current tips. Nothing in the family is consolidatable; the row re-serves
stale census legs, adjudicated below.

## Pair-by-pair adjudication (11 register pairs, re-measured 2026-11-02 at the pinned tips)

Verdict vocabulary: **twin** = managed duplicate, content identical under a declared header
recipe; **owner-split** = both sides carry unique content, neither deletable;
**false-positive** = detector-flagged duplicate whose real relation is something else.

| # | pair (art ⟶ patents) | art blob | patents blob | exact | hunks | art-only | patents-only | verdict |
|---|---|---|---|---|---|---|---|---|
| 1 | museum.navigation.js | `6567e4f7…` | `66dd3d5d…` | NO | 5 | 23 | 37 | **twin** (declared, identical-below-doc-header) |
| 2 | museum.architecture.js | `77773d49…` | `d22b9b35…` | NO | 85 | 1071 | 206 | **owner-split** |
| 3 | museum.gallery-loader.js | `e1128da0…` | `9cb66f46…` | NO | 39 | 243 | 122 | **owner-split** (declared, not portable) |
| 4 | museum.lighting.js | `7e324fb9…` | `eab7e187…` | NO | 33 | 257 | 160 | **owner-split** (undeclared) |
| 5 | museum.wayfinding.js | `7696aedb…` | `5c864d75…` | NO | 43 | 290 | 96 | **owner-split** (undeclared) |
| 6 | museum.wing-enhancements.js | `427175ae…` | `b45d993c…` | NO | 10 | 614 | 29 | **owner-split** (widest gap, still both-unique) |
| 7 | spec.basic.spec.js | `4d770d1e…` | `2bc67131…` | NO | 1 | 5 | 3 | **twin** (declared, identical-below-comment-header) |
| 8 | spec.smoke.spec.js | `ba450a56…` | `68dd425b…` | NO | 1 | 5 | 3 | **twin** (same) |
| 9 | spec.navigation.spec.js | `aabca638…` | `0cb166c2…` | NO | 1 | 5 | 3 | **twin** (same) |
| 10 | spec.vr.spec.js | `119c0dab…` | `12310f76…` | NO | 1 | 5 | 3 | **twin** (same) |
| 11 | spec.museum.spec.js | `b59fea84…` | `3da0b47b…` | NO | 1 | 89 | **0** | **false-positive** (as twin): strict one-direction superset, port-DOWNWARD gap |

Full 40-hex blobs, whole-file sha256s and body-identity digests: every value measured this
turn equals the register's pin exactly (spot examples — navigation art whole sha256
`aba48a95050f8d94a1f20c40688243d9834a8424c9c00b62ebe74280fb02f9e9`, patents
`ecd1c2c3cd58d39437967aaeff6d53812c1293489ee4b3e81185ccbd86f9b122`; body tails below).

### The twin pairs (1, 7–10): identical below the declared header — reproduced, not trusted

For each declared pair I re-derived the header/body split from the register's own arithmetic
(art header lines = art_total − body_total; e.g. navigation 1270−1234=36, 1284−1234=50;
specs 6/4 except museum.spec) and hashed the tails independently on both sides:

| pair | art tail (from line) | patents tail (from line) | sha256 of BOTH tails, this turn |
|---|---|---|---|
| navigation.js | +37 | +51 | `1e2054a6b765ab682868986813090b392ab191ae01cdfd8a31c37c6130d64c7c` |
| basic.spec.js | +7 | +5 | `07b5dbb66c4f8a15666f695a376670dabbd209f3fbf0d5b95fa9d44a1185082e` |
| smoke.spec.js | +7 | +5 | `0dbce9c8afbb99e15e4d643832a8e71b3770f555f387074978b8c95937e562cc` |
| navigation.spec.js | +7 | +5 | `daeeaedf6b40add45e28b368c21cb3af6a5f97fc26785401d4d4c7cf143a6bae` |
| vr.spec.js | +7 | +5 | `7648cd18b08a288cf41643b9a9c9b8403bee31408e09858cecaab8e1ef4b2a48` |

All five match the register's `body_identity.sha256` exactly, on both sides. Evidence for the
whole-file mismatch is purely the two PROVENANCE/declaration header blocks (spec pairs: 1 diff
hunk, 5 vs 3 header lines; navigation: 5 hunks, all inside the header region — the tails below
line 37/51 hash-equal). **Verdict: no content drift to consolidate on any twin pair.**
Pair 1 (navigation) is a declared mirror — art canonical, patents header says MIRROR — and the
direction rule stands: edit art, port whole; the 23/37 header-line divergence is *by design*
(header asymmetry: art narrates canonicality, patents narrates provenance + @-pins).

### Owner-split pairs (2–6): bidirectional deltas — real forks by content, neither deletable

Measured art-only AND patents-only line counts are nonzero on all five (see table), so by the
register's `union_not_revert` law none is a stale derivative: architecture 1071⟷206,
gallery-loader 243⟷122 (patents copy additionally cannot run art's version — art imports
`artworks/p3-artworks.js`, `lib/instanced-elements.js`, `lib/visitor-identity.js`, which are
absent from the patents tree; the patents side self-declares as the P2-generation copy while
art's own copy carries no marker — a one-header declaration), lighting 257⟷160, wayfinding
290⟷96, wing-enhancements 614⟷29 (widest size gap in the family, yet patents still owns 29
unique lines — "art is ahead" is not the whole story). **Verdict: owner-split; consolidation
would be a content loss, not a dedup win. Leave both.**

### Pair 11, museum.spec.js — the one-directional delta

patents-only lines = **0** (measured this turn), art-only = 89, exactly one diff hunk. Art's
copy strictly contains patents' (the extra block: per-wing teleport indicator tests Digit1–
Digit7 plus return-to-rotunda via Digit0). This is a **false-positive as a duplicate**: the
relation is subsumption — a coverage gap to port DOWNWARD into patents, not a twin and not an
owner-split (patents holds no unique lines). No PROVENANCE marker on either side.

## The T0 row itself (near_duplicate, navigation.js, 7.40): why it is a false-positive

The register's `census_provenance` says the row scores two NON-PUBLISHED trees. I re-ran its
three falsifiable legs this turn:

| leg | register claim | this turn's measurement | agrees |
|---|---|---|---|
| art leg = parked shared checkout `054c275` | blob `bd836bd95975cd22fcf377711a77cdfede685aef` | `git show 054c275:patent-portfolio/museum/navigation.js \| git hash-object --stdin` → `bd836bd9…` | YES |
| patents leg = banked wip `58ef6462` ("wip: banked before fleet git-sync") | blob `d20f2aa3d96e8d7496df53dd63aac9ac5105ff8a` | hash-object → `d20f2aa3…` | YES |
| that banked commit never landed | `merge_base_is_ancestor_rc: 1` | `git merge-base --is-ancestor 58ef6462 c7b7ac1a` → **rc=1** | YES |
| published art tip | `6567e4f7…` | blob at `0803caac` HEAD (and my seat checkout hashes the same) | YES |
| published patents tip | `66dd3d5d…` | blob at live `c7b7ac1a` | YES |

So: the generation's byte readings were never wrong — it read a parked checkout on one side
and a banked pre-port wip commit on the other. At the **published tips** the pair's bodies are
identical below the headers (re-derived above), and even the dense embedding neighbor agrees
on the shape of the relation: navigation.js's #1 nearest file in the whole 38,898-row corpus is
its own twin, cosine 0.7948 vs. a 0.24 corpus baseline. **The 7.40 row describes copy debt that
does not exist at any published surface; it will keep re-serving until the census reads
published tips instead of parked trees — a code-map producer question, not an art-tree one.**

## What the V4 fold (the PIN itself) did to this family

`git diff --stat 0803caac^1 0803caac -- patent-portfolio/` → the 4 changed files are
`components/info-panel.js`, `index.html`, `lib/accessibility.js`, `main.js` (202 insertions,
79 deletions). **None is a twin-family path**; all 11 art-side blobs still match the register
byte-for-byte at the new pin (verified above before writing this file). The register's
art-side pins are live at `0803caac` with zero refresh needed.

## Recommendations (falsification-tested, none executed by this lane)

1. **Do NOT consolidate any pair.** Twins (1, 7–10) have nothing to merge; owner-splits (2–6)
   would lose content in both directions; pair 11 is a port-downward gap.
2. navigation.js T0 row: keep closed. Disposition stays `declared-mirror`; residual 1 (art's
   header still narrates the pre-port fork in present tense) remains a four-file two-repo
   coordinated fold — this adjudication deliberately does not start it (register law: take all
   four files or none).
3. Pair 11 (museum.spec, 89-line wing-teleport + rotunda-return block) is the only actionable
   content move in the family: port DOWNWARD into patents. That is a patents-bound lane.
4. Census-producer fix: a near_duplicate row on this family should gate on published-tip blobs
   (`origin/main` both sides) before scoring; the parked-checkout legs `bd836bd9`/`d20f2aa3`
   reproduce exactly, so detection of stale legs is cheap and deterministic.

---
*All numbers in this file come from tool output read during this lane's session (2026-11-02):
git hash-object / shasum -a 256 / /usr/bin/diff over tip-extracted bytes, one
code_map_neighbors call (dense, served despite encoder_degraded query leg), and
code_map_freshness. Register quoted: `patent-portfolio/NEAR-DUPLICATE-TWINS.json`, blob
`3cd749aa3e836e02f2f0890d19075c1b05f377a9` at `0803caac`. navigation.js read-only: confirmed
untouched (write-set of this lane = this one md).*
