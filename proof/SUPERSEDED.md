# Superseded by daemon visualizer

**This file is the source of truth.** `../proof-galaxy/SUPERSEDED.md` is a
pointer here — read and edit this copy, not that one.

This static visualizer was archived 2026-04-26.

The unified, live, daemon-driven proof dashboard is now at
**http://100.92.215.26:8736** (Studio, tailnet-exposed).

It supersedes two archived static exhibits, as a cluster:

- `art/proof/` — scrollytelling 8-act galaxy of 357 theorems
- `art/proof-galaxy/` — Three.js penguin colony of 24,232 declarations

What's in the new one:

- Live SSE event stream from the daemon
- Kimina Lean Server status (κ glyph, REPL pool, verdicts, latency)
- D3 force-directed galaxy of 129 open sorries (live)
- Closure events fire gold-burst pulse + (optional) audio chime
- Microdelight on every interaction (hover ripples, focus rings,
  copy-on-click, toast feedback, keyboard shortcuts via ?)
- Compiler SSOT integration (/tmp/proof-report.json)

## Where the archived code actually lives

Measured 2026-11-18: **not in this repo, and not on this host.**

`git ls-files proof proof-galaxy` returns two paths, both of them a
`SUPERSEDED.md` tombstone. Neither exhibit's source is in git history under
those directories, so nothing here is retrievable from the repository.

The archive was recorded at:

```text
~/.kagami/backup-2026-04-26-viz/art-superseded/
```

That line is the historical record of where the backup was placed when the
exhibits were archived — it is **not a reachable restore source**. As of
2026-11-18 neither that path nor its parent `~/.kagami/backup-2026-04-26-viz`
exists on this host. Treat the exhibits as gone unless a copy turns up
elsewhere.

The `art/proof` scroll-essay was a *static* exhibit of a single moment
in the proof corpus. It is not a substitute for the live dashboard,
but it remains a beautiful one-time piece — if a copy of the archive is
ever located, read its visual language before designing new proof surfaces.
