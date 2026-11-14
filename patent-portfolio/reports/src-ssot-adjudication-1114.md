# src-ssot-adjudication-1114 — two code-map cleanup rows adjudicated (proof-galaxy/SUPERSEDED.md, patent-portfolio/tests/README.md)

**Lane:** ART-SRC-1114 (kind grove, OMNI-SHARPEN-1112 refill wave) · **Base/PIN:** art
origin/main `fca9e10b25455b6d330d1feadf96c22c024db9ea` · **Measured:** 2026-11-14

**Scope law honored:** this lane decides the single source per row and writes this report only.
Nothing was deleted, renamed or edited elsewhere. Per the twin register's own law
(`patent-portfolio/NEAR-DUPLICATE-TWINS.json` → `law.union_not_revert`): divergent content is
recorded with a digest, never silently deleted.

## Instruments used (disclosure)

1. **Byte truth:** `git rev-parse <rev>:<path>` (blob equality), `shasum -a 256` (whole-file
   identity), `cmp -s` (per-file identical/differs census).
2. **Ancestry:** `git log --oneline --follow --reverse -- <path>` and
   `git log -1 --format='%h %ad %s' --date=short -- <path>`.
3. **Reader census (the decisive leg — "which file do tools/tests actually read?"):**
   `git grep -n <token> -- .` over the art tree for `SUPERSEDED`, `proof-galaxy`,
   `tests/README`, `patent-portfolio/tests`, plus direct read of
   `ART-MANIFEST.json`, `apps/manifest.json`, `scripts/twin-register.mjs`,
   `patent-portfolio/NEAR-DUPLICATE-TWINS.json`, `patent-portfolio/tests/package.json` and
   `patent-portfolio/tests/playwright.config.js`.
4. **Cross-repo:** `/usr/bin/diff`-equivalent comparison against
   `~/projects/awkronos/patents/tests/` and `git -C ~/projects/awkronos/patents log -1` for the
   patents-side pin. (Host `diff` is shimmed to `delta`; every identity claim below comes from
   `cmp`/`shasum`, not from the shim — the false-zero class named in
   `nav-twin-adjudication-1102.md` §3.)

---

## Row 1 — `proof-galaxy/SUPERSEDED.md`

### Measured

| leg | measurement | command |
|---|---|---|
| twin exists | `proof/SUPERSEDED.md` and `proof-galaxy/SUPERSEDED.md` are the **same git blob** `ab8fa1763152fdf455153fa20acf63cb7d8e7166` | `git rev-parse HEAD:proof/SUPERSEDED.md HEAD:proof-galaxy/SUPERSEDED.md` |
| identity recipe | whole-file identical (1127 B each), `diff` → IDENTICAL | `diff proof/SUPERSEDED.md proof-galaxy/SUPERSEDED.md` |
| ancestry | **does not discriminate** — both files enter at `3a86109` and were last touched by the same commit `36002cc` (2026-06-17, "Save dirty workspace changes") | `git log --follow --reverse` / `git log -1` per path |
| machine readers | **zero.** No tracked file's *content* contains the string `SUPERSEDED` at all | `git grep -n "SUPERSEDED" -- .` → no output |
| manifest coverage | neither `proof` nor `proof-galaxy` is enumerated | `ART-MANIFEST.json` (`"proof"` count 0), `grep -n proof apps/manifest.json` → 0 hits |
| directory contents | each archived directory holds exactly **1** tracked file — the tombstone; the archived code is not in the repo | `git ls-files proof \| wc -l` → 1, same for `proof-galaxy` |
| successor pointer | the live dashboard it names is a tailnet address (`http://100.92.215.26:8736`), i.e. outside art, no repo-resolvable target | read of the file body |
| archive pointer is **dead on this host** | `~/.kagami/backup-2026-04-26-viz/art-superseded/` does not exist; its parent `~/.kagami/backup-2026-04-26-viz` does not exist either | `ls -d ~/.kagami/backup-2026-04-26-viz/art-superseded/` → No such file or directory |

### Verdict

The two files are not a content conflict — they are an **authority conflict between two
byte-identical copies of the same statement**, and ancestry cannot break the tie because they
were created and last modified in the same commits.

**Canonical: `proof/SUPERSEDED.md`.** Decided on scoping grounds, not age: the body's closing
instruction ("restore from backup if you ever want to refer to its visual language") is about the
`art/proof/` scroll-essay, and that essay is the artifact a reader would actually go looking for,
so the copy that sits in the directory it primarily describes is the one to keep as the statement.
`proof-galaxy/SUPERSEDED.md` becomes a pointer.

**Neither markdown file is the source of truth for the underlying fact.** What actually holds is
the absence of code from both directories plus the successor dashboard living outside art. The
doc's only load-bearing empirical claim — "Original code preserved at
`~/.kagami/backup-2026-04-26-viz/art-superseded/`" — is **false on this host as measured today**.

### Recommended fold (a later write lane, not this one)

1. Rewrite `proof/SUPERSEDED.md` so its body describes *both* archived exhibits at cluster level
   and names where the archive actually lives — or drops the preservation claim and says plainly
   that the archived trees are not in this repo and not on this host.
2. Reduce `proof-galaxy/SUPERSEDED.md` to a two-line stub: superseded, see `../proof/SUPERSEDED.md`.
   Do **not** delete it: an empty-looking directory with no tombstone loses the reason.
3. Do not register this pair in `NEAR-DUPLICATE-TWINS.json` — that register is museum-scoped
   (schema `art-museum-twin-register/1`, role text names the `patent-portfolio/` twin family);
   a same-repo doc pair would widen its declared scope without cause.

---

## Row 2 — `patent-portfolio/tests/README.md`

### Measured

| leg | measurement | command |
|---|---|---|
| cross-repo twin | art copy is **whole-file byte-identical** to `~/projects/awkronos/patents/tests/README.md`: sha256 `5339d1b7e06f34b231a806039c27c7cf4e198bb76c8afd45b6114c495f2ceaf9` on both sides | `shasum -a 256` both paths; `cmp -s` → IDENTICAL |
| declared direction | **both** sides name awkronos as canonical: art's sibling `playwright.config.js` line 1–3 "mirror of `~/projects/awkronos/patents/…`, awkronos/patents is the brand-owned canonical copy — edit there first"; the patents-side file names itself "canonical source … Mirrored at `~/projects/art/patent-portfolio/…`" | read both headers |
| patents-side pin | patents repo toplevel `~/projects/awkronos/patents`; last commit touching `tests/README.md` = `82938387315291cb00f3647b5d3bb7974a55c29f` (2026-02-04, "Initial commit") | `git -C ~/projects/awkronos/patents log -1 -- tests/README.md` |
| art-side pin | art's `patent-portfolio/tests/README.md` last touched by `da76faf` ("Complete design overhaul…") | `git log --oneline -- patent-portfolio/tests/README.md` |
| register coverage | **absent.** The register holds 11 `pairs` + 5 `not_twins`; none is `README.md`, `playwright.config.js` or `package.json` | `grep -nE "SUPERSEDED\|README\|playwright.config" patent-portfolio/NEAR-DUPLICATE-TWINS.json` → no output; path dump of both lists |
| machine readers of the README | **zero** — no tracked file in art references `tests/README` | `git grep -n "tests/README" -- .` → no output |
| what the runner reads instead | `tests/package.json` scripts (`test`, `test:basic`, `test:webgl`, `test:headed`, `test:report`) and `playwright.config.js` `projects` | read both files |
| config twin is drifted at whole-file level | art `playwright.config.js` 2432 B vs patents 2359 B: differ **only** in the 3-line PROVENANCE comment header → identical-below-comment-header (the register's `twin` class, per `law.byte_identity_is_recipe_scoped`) | `cmp -s` DIFFERS; `git diff --no-index` → 1 hunk, header lines only |
| README is stale against the tree it documents | documents 3 groups; the directory has **6** spec files: `basic.spec.js`, `smoke.spec.js`, `exhibit-integrity.spec.js`, `interaction/navigation.spec.js`, `visual-regression/museum.spec.js`, `xr-simulation/vr.spec.js`. `smoke.spec.js` and `exhibit-integrity.spec.js` are never named. README names 2 projects (`chromium`, `chromium-webgl`); config declares 4 (`firefox`, `webkit` also) | `find patent-portfolio/tests -name "*.spec.js"`; `grep -nE "name:" playwright.config.js` |
| art-only file, correctly registered | `exhibit-integrity.spec.js` exists in art and **not** in patents; already listed under `not_twins` | `cmp` census (`MISSING` on patents side) + register dump |

### Verdict

**Single source: `~/projects/awkronos/patents/tests/README.md`.** The art copy
`patent-portfolio/tests/README.md` is an unregistered mirror with no machine reader, and its
own directory's sibling headers state the direction explicitly. So this row is **not** a
generated-vs-handwritten conflict; it is a **documentation-drift conflict**, and the correct
source of truth for *what actually runs* is neither README: it is
`patent-portfolio/tests/package.json` (scripts) + `patent-portfolio/tests/playwright.config.js`
(projects). The README is prose that both repos have let go stale in the same way.

Under the register's recipe law the two README copies are identical at the strongest recipe
(whole file), which is exactly why they are stale together — a divergence check on this pair
would have passed right up to the moment it stopped mattering.

### Recommended fold (a later write lane, not this one)

1. Author the README fix in `awkronos/patents/tests/README.md` first (name all six specs, all four
   projects, and point at the `test:basic` / `test:webgl` / `test:headed` scripts instead of
   re-typing `npx playwright test …`), then port it to art byte-for-byte. Editing art first
   inverts the declared direction and forks the pair.
2. Add three rows to the twin register instrument (`scripts/twin-register.mjs`) so the register
   again matches its own role text: `tests/README.md` (pair, whole-file identical),
   `tests/playwright.config.js` (pair, identical-below-comment-header) and
   `tests/package.json` + `tests/package-lock.json` (measured, not asserted). Without this the
   "ONE art-side statement of the twin family" silently under-covers the tests directory.
3. `exhibit-integrity.spec.js` stays `not_twin` (art-only) — no action, recorded for completeness.

---

## Scope of the numbers in this report

The register's role text is: *"The ONE art-side statement of the museum twin family: which files in
`patent-portfolio/` have a twin in `~/projects/awkronos/patents` … Prose elsewhere
(DEBT-museum-navigation-duplication.md, module headers, commit messages) points here and does not
restate numbers."* This report therefore **does not restate any register pin**. Every digest here
belongs to a file the register does not cover (`README.md`, `playwright.config.js`,
`SUPERSEDED.md`), and every museum-family relationship is cited by pointer to the register. The
register's own `census_provenance.finding` — that the code-map `near_duplicate` row "is scored on
TWO NON-PUBLISHED TREES" — is why all measurements above were taken against the live working trees
and published tips named in the commands column.

Two consequences of that role text, both measured:

1. `README.md` and `playwright.config.js` each **do** have a twin in `~/projects/awkronos/patents`
   (proven by `cmp` above), so by the register's declared scope they belong in it, and they are
   absent from all 16 rows. That is an under-coverage gap in the register, not a scope exemption —
   nothing in `basis` or `law` excludes prose or config files.
2. Row 1 (`SUPERSEDED.md`) is correctly outside the register: its pair is same-repo, not an
   art⟶patents twin. Widening the register for it would break the scope the role text declares.

## Focused check

The twin family is read by two instruments — `tests/unit/museum-twin-register.test.mjs` and
`tests/unit/navigation-twin-invariants.test.mjs` — both run at tip after this report landed
(see the commit line below); `tests/unit/twin-measure.mjs` is the generator, not a reader, and was
not invoked. Neither can go red for this change: my only write is a new file under
`patent-portfolio/reports/`, and the reader census measured **zero** machine readers for both row
files (`git grep` for `SUPERSEDED` and `tests/README` over tracked content → no output). So this
row has **no falsifier by construction**, which is itself the finding: these two rows cannot be
pinned by a test, and can only be decided by the digests recorded above.
