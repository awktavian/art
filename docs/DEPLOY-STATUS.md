# Deployment Status

## Canonical home

**https://awktavian.github.io/art/** — GitHub Pages, served from `main` at path `/`.

This is the single canonical URL for the portfolio. Do not configure a custom
domain for this repo.

## GitHub Pages configuration (intended state)

- Repo: `awktavian/art` (public), `has_pages = true`.
- Source: **Deploy from a branch** → branch `main`, path `/`.
- `.nojekyll` present at repo root → the site is served as plain static files
  (no Jekyll processing). All apps are vanilla-JS static PWAs, so no build step
  is required; the branch tree IS the site.
- No `CNAME` file (must stay absent — a CNAME would redirect Pages away from
  the `github.io` URL).

## Feb–Jul 2026 outage: root cause

`https://awktavian.github.io/art/` returned 404 from roughly mid-May through
2026-07-11. Evidence gathered 2026-07-11:

- Last successful `github-pages` environment deployment: **2026-05-10**
  (via the auto-generated `pages-build-deployment` deploy-from-branch workflow).
- July commits to `main` (root `index.html`, vercel regex fix) produced **no**
  new Pages deployment.
- Pages API reported `build_type: "workflow"` with `source: {branch: main, path: /}`,
  but `.github/workflows/` contained **no committed workflow**.

Interpretation: the Pages "Source" setting was switched from *Deploy from a
branch* to *GitHub Actions* (`build_type: workflow`) after 2026-05-10, but no
Actions workflow was ever committed. With the source on GitHub Actions and no
workflow present, nothing rebuilt or republished the site, and the prior
deployment stopped being served → 404.

## Remediation applied (2026-07-11)

1. Confirmed no `CNAME` exists (tracked, on disk, or in Pages config).
2. Restored Pages Source to **Deploy from a branch** (`main`, `/`)
   (`build_type: legacy`) so the branch tree republishes on every push.
3. Pushed `main` and triggered a fresh Pages build.

The `main` tree already contains the July portfolio `index.html` and `.nojekyll`,
so restoring deploy-from-branch republishes the current portfolio.

## art.awkronos.com — DEPRECATED

`art.awkronos.com` is **deprecated** in favor of the `github.io` URL above and is
no longer maintained. As of 2026-07-11 it returned HTTP 525 (Cloudflare↔origin
SSL handshake failure). No custom domain is being configured for this repo; do
not point DNS at Pages. Use `https://awktavian.github.io/art/`.

## Vercel

`vercel.json` remains in the repo for any incidental Vercel preview usage, but
**GitHub Pages is the canonical deployment**. The Vercel config is intentionally
left untouched; it does not affect the Pages deployment.
