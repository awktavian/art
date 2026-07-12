# Deployment Status

## Canonical home

**https://awktavian.github.io/art/** — GitHub Pages project site.

This is the single canonical URL for the portfolio. Do not configure a custom
domain for this repo.

The Pages source setting is branch `main`, folder `/`. Here `/` means the root
of the repository branch; it does **not** mean the web-origin root. The public
URL prefix is `/art/`, so internal static URLs must be document-relative.

## GitHub Pages configuration (verified 2026-07-11)

- Repo: `awktavian/art` (public), `has_pages = true`.
- Source: **Deploy from a branch** → branch `main`, path `/`.
- `.nojekyll` present at repo root → the site is served as plain static files
  (no Jekyll processing). All apps are vanilla-JS static PWAs, so no build step
  is required; the branch tree IS the site.
- No `CNAME` file (must stay absent — a CNAME would redirect Pages away from
  the `github.io` URL).
- HTTPS enforcement is enabled and the repository is public.

The pre-browser-canary verification baseline was commit `c31c589` via successful
`pages-build-deployment` run `29179038123`. A post-deploy canary read the live
directory, confirmed the corrected 108-work inventory, and received HTTP 200
from the directory, shared accessibility script, `gen/`, `collapse/`, `home/`,
two PWA manifests, and the Exhale service worker.

Every later `main` push must pass `Static site quality`, including the local
`/art/` Chromium canary, before its deployment is treated as healthy.

GitHub's legacy `GET /repos/awktavian/art/pages/builds/latest` record reported
`errored` for the same SHA while the generated Actions deployment completed
successfully and the live files matched that SHA. Treat the completed Actions
deployment plus live canary as operational evidence; do not infer an outage
from that legacy status field alone.

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

## `/medverify` sub-app (separate repo; not published here)

`medverify` is its own ignored repository, not a published directory in this
project site. It was never actually served here: the former gitlink pointed at
a commit the Pages builder could not fetch. The dead MedVerify directory card
was removed from `index.html`; the visible total is now 108 and the site does
not advertise `/medverify`. Re-add it only after the separate app has a verified
public URL, or after tracked static output is intentionally vendored here.

## art.awkronos.com — DEPRECATED

`art.awkronos.com` is **deprecated** in favor of the `github.io` URL above and is
no longer maintained. As of 2026-07-11 it returned HTTP 525 (Cloudflare↔origin
SSL handshake failure). No custom domain is being configured for this repo; do
not point DNS at Pages. Use `https://awktavian.github.io/art/`.

## Vercel

`vercel.json` remains in the repo for any incidental Vercel preview usage, but
**GitHub Pages is the canonical deployment**. The Vercel config is intentionally
left untouched; it does not affect the Pages deployment.
