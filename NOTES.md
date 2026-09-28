# W30-ART-DESC lane notes

Branch: lane/W30-ART-DESC-0928 @ base 13b5755a9058b02ece4c9673985adc51d7b8fa4b (verified, clean).

## Gate
- check-site at base with local /tmp/proof-report.json FAILS (rc=1): the hong row is
  build_status=SKIPPED / soundness=VERIFIER_UNKNOWN (cpu-saturated-skipped mid-sweep on
  Studio). sync-corpus-stats.mjs correctly refuses to publish unverified counts — gate NOT
  defeated, sidecar untouched, no stats edited.
- CI-faithful run per the script's own documented skip path (matches W30-ART receipt):
  `PROOF_REPORT_PATH=/tmp/w30-ART-DESC/no-report.json node scripts/check-site.mjs`
  BEFORE: rc=0, 138 HTML / 690 local refs (gates/pre.log)
  AFTER:  rc=0, 138 HTML / 690 local refs (gates/post.log)

## Counts (final)
- 138 HTML total. Lacking <meta name="description"> at base: 62. Described now: 58 authored.
  Repository coverage: 134/138.
- described: 58 (all ≤160 chars, authored from page h1/h2/p + era/artist evidence;
  live demos/dev tools got honest one-liners: callback, katastrophe, orb/viewer,
  steamboat-willie, brain-freeze, over-9000, slop/*)
- skipped-redirects: 3 — get-a-job.html, home.html, octoni-on.html (pure meta-refresh
  to their index.html siblings; fold-note only per brief)
- skipped-mirror: 1 — patent-portfolio/test.html: in-file PROVENANCE comment declares it
  a byte-identical mirror of ~/projects/awkronos/patents/test.html ("edit there first,
  then port changes here"). Adding a description here would break the mirror invariant;
  canonical owner is the patents repo.
- og-description: NOT added anywhere — zero of the 62 touched pages already carry any
  og:* platform tags, so the brief's precondition ("only where the platform tags already
  exist") is not met. No new meta classes added.

## Resume site
All authored work complete, gates green, commit pending push. If resumed: run
post-gate again, push branch ref, ls-remote verify.
