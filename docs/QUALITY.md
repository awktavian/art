# Static-site quality gate

The canonical deployment is a GitHub Pages **project site** at
`https://awktavian.github.io/art/`. A URL beginning with `/` therefore escapes
the portfolio and points at `https://awktavian.github.io/`, which is a different
site.

Run the same gate as CI before committing:

```bash
npm test
```

The static half is dependency-free and validates every tracked HTML document
outside the separate `medverify` repository. It rejects:

- root-relative links and assets that escape the `/art/` deployment base;
- local links, scripts, styles, images, posters, and form actions without a
  static target;
- documents without language, title, responsive viewport metadata, or (on the
  directory) a skip link and main landmark;
- directory totals or section badges that disagree with the published cards;
- invalid or out-of-scope PWA manifests and service-worker asset paths;
- service workers whose activation can delete caches owned by sibling apps.

## The corpus-statistics leg, and what its words mean

`wiles/index.html` publishes four generated tiles about the `hong` Lean corpus.
`scripts/sync-corpus-stats.mjs` derives them from the estate proof report
(`PROOF_REPORT_PATH`, default `/tmp/proof-report.json`) and `scripts/check-site.mjs`
runs it as a leg, so a page cannot disagree with the compiler without failing the
build. The leg books one of four states, each with its own cure — read the state,
not just the colour:

| state | rc | what it measured | what clears it |
|---|---|---|---|
| `pass` | 0 | every graded tile matches a verified, in-bounds row | — |
| `drift` | 1 | a verified row disagrees with the page | `node scripts/sync-corpus-stats.mjs` |
| `unverified_source` | 1 | the compiler has not verified that corpus (`build_status` is not `GREEN`), so nothing was compared | a `GREEN` build of that corpus; **no art commit can clear it** |
| `no_verdict` | 0 | no report, or the report — or that corpus's own row — is older than the 24 h bound | a fresh report; deliberately not a pass |

An out-of-bounds row renders no verdict for its own page: a `PASS` earned from
digits the report no longer vouches for is the same false green as a `0 sorry`
earned from a missing count, which is the shape this script was written to
prevent. `scripts/corpus-stats-state.mjs` owns the vocabulary and the sentence
`check-site.mjs` books, so the failure always names the file the leg opened and
never claims a comparison it did not run. On CI and a fresh checkout the report
is absent, so the leg prints `SKIPPED (no verdict)` and the rest of the gate
grades normally; on a Studio host with a red corpus the leg is red for the estate,
and it says which.

The browser half uses one pinned dependency, Playwright, and one Chromium
project. A small Node server mounts the checkout at `/art/`, matching the GitHub
Pages project URL, then checks the directory's keyboard search, accessible names,
live count, and card inventory. It also opens representative interactive routes and
fails on uncaught exceptions or failed same-origin resources. The collapse
film must mount its tracked nine-frame player and remain keyboard operable.

For a fresh checkout, install the browser once before running the full gate:

```bash
npm ci
npx playwright install chromium
npm test
```

GitHub Actions runs both halves on every push and pull request. The branch tree
is still the deployed artifact; this workflow verifies it and does not deploy.
