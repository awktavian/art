# Static-site quality gate

The canonical deployment is a GitHub Pages **project site** at
`https://awktavian.github.io/art/`. A URL beginning with `/` therefore escapes
the portfolio and points at `https://awktavian.github.io/`, which is a different
site.

Run the same gate as CI before committing:

```bash
npm test
```

The dependency-free checker validates every tracked HTML document outside the
separate `medverify` repository. It rejects:

- root-relative links and assets that escape the `/art/` deployment base;
- local links, scripts, styles, images, posters, and form actions without a
  static target;
- documents without language, title, or responsive viewport metadata.
- directory totals or section badges that disagree with the published cards;
- invalid or out-of-scope PWA manifests and service-worker asset paths;
- service workers whose activation can delete caches owned by sibling apps.

GitHub Actions runs the gate on every push and pull request. The branch tree is
still the deployed artifact; CI verifies it and does not perform a manual
deployment.
