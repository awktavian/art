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
