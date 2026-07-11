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

## Feb–Jul 2026 outage: root cause (verified)

`https://awktavian.github.io/art/` returned 404 from roughly mid-June through
2026-07-11. The Pages "pages build and deployment" run failed at the **Checkout**
step with:

```
fatal: No url found for submodule path 'medverify' in .gitmodules
The process '/usr/bin/git' failed with exit code 128
```

Root cause: the WIP snapshot commit `a6ad2d9`
("WIP: snapshot working state (substrate audit bulk cleanup 2026-06-26)")
accidentally committed the embedded, separate `medverify` repo as a **gitlink**
(git mode `160000`) with **no `.gitmodules`** entry. `actions/checkout` on the
Pages deploy runs `git submodule update --init --recursive`, which aborts on the
orphaned gitlink — so the deploy never reached its deploy step, and the previously
published site stopped being served → whole-site 404.

Corroborating evidence (gathered 2026-07-11): last successful `github-pages`
deployment was **2026-05-10** (`af65090`, before the gitlink was introduced);
every deploy after the 06-26 snapshot failed at Checkout.

## Remediation applied (2026-07-11)

1. Confirmed no `CNAME` exists (tracked, on disk, or in Pages config).
2. Removed the orphaned `medverify` gitlink from the index
   (`git rm --cached medverify`; the on-disk `medverify/` working copy is
   untouched) and added `/medverify/` to `.gitignore` so a future
   `git add -A` / WIP snapshot cannot re-introduce the gitlink.
3. Set Pages Source explicitly to **Deploy from a branch** (`main`, `/`).
4. Pushed `main` and triggered a fresh Pages build.

The `main` tree already contains the July portfolio `index.html` and `.nojekyll`,
so once the Checkout step succeeds, deploy-from-branch republishes the current
portfolio.

## `/medverify` sub-app (separate repo — follow-up)

The portfolio `index.html` links `href="/medverify"`. `medverify` is its own
repository (`git@github.com:awktavian/medverify.git`), not part of this repo. It
was never actually served here — the gitlink pointed at a commit the Pages
builder cannot fetch. Restoring the portfolio does **not** serve `/medverify`;
publishing that sub-app is a separate task (deploy `awktavian/medverify` on its
own, or vendor its built static output into this repo as regular files under
`medverify/`). Until then, the `/medverify` link 404s while the rest of the
portfolio serves normally.

## art.awkronos.com — DEPRECATED

`art.awkronos.com` is **deprecated** in favor of the `github.io` URL above and is
no longer maintained. As of 2026-07-11 it returned HTTP 525 (Cloudflare↔origin
SSL handshake failure). No custom domain is being configured for this repo; do
not point DNS at Pages. Use `https://awktavian.github.io/art/`.

## Vercel

`vercel.json` remains in the repo for any incidental Vercel preview usage, but
**GitHub Pages is the canonical deployment**. The Vercel config is intentionally
left untouched; it does not affect the Pages deployment.
