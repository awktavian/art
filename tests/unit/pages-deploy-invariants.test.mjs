/**
 * docs/DEPLOY-STATUS.md — the Pages deploy-tree invariants are machine-pinned.
 *
 * The outage that file records (§"Feb–Jul 2026 outage: root cause (verified)")
 * was a tree shape, not a page: commit `a6ad2d9` tracked the separate
 * `medverify` repository as a gitlink (mode `160000`) with no `.gitmodules`
 * entry, the Pages build's checkout step died on
 * `fatal: No url found for submodule path 'medverify' in .gitmodules` (exit
 * 128), and `https://awktavian.github.io/art/` served 404 for roughly 25 days.
 * The doc's remediation removed the pointer and ignored `/medverify/`; its last
 * line of defense was prose. Measured here on 2026-11-23 before this file
 * existed: `git -C /Users/schizodactyl/projects/art ls-tree -r HEAD | awk
 * '$1=="160000"'` answered empty and stayed answering empty no matter what got
 * committed next, and no file in `tests/unit/` or `scripts/check-site.mjs`
 * asked the question.
 *
 * The property under test is the guard in both directions — it must read the
 * real tree as clean, and it must go red on a fixture that reproduces the
 * outage shape, then green again once the documented remediation is applied. A
 * clean verdict from a check that cannot fail is worth nothing, so the fixture
 * leg is the load-bearing one.
 */
import assert from "node:assert/strict";
import { execFileSync } from "node:child_process";
import { mkdtempSync, readFileSync, rmSync, writeFileSync } from "node:fs";
import test from "node:test";
import { tmpdir } from "node:os";
import { dirname, join, resolve } from "node:path";
import { fileURLToPath } from "node:url";

import { EMBEDDED_REPOS, inspectPagesRepo } from "../../scripts/pages-deploy-invariants.mjs";

const repoRoot = resolve(dirname(fileURLToPath(import.meta.url)), "../..");

/** git in a throwaway fixture: an explicit identity, because the fixture must
 *  not depend on whoever's `~/.gitconfig` runs the suite. */
function fixtureGit(dir, args) {
  return execFileSync(
    "git",
    ["-c", "user.name=pages-fixture", "-c", "user.email=pages-fixture@localhost", "-C", dir, ...args],
    { encoding: "utf8", stdio: ["ignore", "pipe", "pipe"] },
  );
}

function makeFixture(t) {
  const dir = mkdtempSync(join(tmpdir(), "art-pages-deploy-fixture-"));
  t.after(() => rmSync(dir, { recursive: true, force: true }));
  fixtureGit(dir, ["init", "-q"]);
  fixtureGit(dir, ["commit", "-q", "--allow-empty", "-m", "base"]);
  return dir;
}

const codesOf = (violations) => new Set(violations.map((v) => v.code));

test("the shipped Pages tree holds the invariants docs/DEPLOY-STATUS.md claims", () => {
  const violations = inspectPagesRepo({ repoDir: repoRoot });
  assert.deepEqual(
    violations,
    [],
    `Pages deploy-tree invariants broken:\n${violations.map((v) => `  ${v.code} ${v.path} — ${v.message}`).join("\n")}`,
  );
});

test("the guard is not vacuous: the outage shape goes red, the remediation goes green", (t) => {
  const dir = makeFixture(t);

  // Reproduce the recorded defect: an embedded separate repo committed as a
  // pointer with no .gitmodules, no .nojekyll, a CNAME, and no ignore rule.
  writeFileSync(join(dir, "index.html"), "<!doctype html><title>art</title>\n");
  fixtureGit(dir, ["add", "index.html"]);
  const pointerSha = fixtureGit(dir, ["rev-parse", "HEAD"]).trim();
  fixtureGit(dir, ["update-index", "--add", "--cacheinfo", `160000,${pointerSha},medverify`]);
  writeFileSync(join(dir, "CNAME"), "art.awkronos.com\n");
  fixtureGit(dir, ["add", "CNAME"]);
  fixtureGit(dir, ["commit", "-q", "-m", "WIP snapshot (the a6ad2d9 shape)"]);

  const broken = inspectPagesRepo({ repoDir: dir });
  const codes = codesOf(broken);
  for (const expected of [
    "gitlink_in_tree",
    "gitlink_in_index",
    "orphan_gitlink",
    "missing_nojekyll",
    "cname_tracked",
    "embedded_repo_not_ignored",
  ]) {
    assert.ok(codes.has(expected), `the guard missed ${expected}; it reported: ${[...codes].join(", ") || "nothing"}`);
  }
  const gitlink = broken.find((v) => v.code === "gitlink_in_tree");
  assert.equal(gitlink.path, "medverify", "the pointer must be named by path, not just counted");

  // Now the documented remediation (§"Remediation applied (2026-07-11)") and
  // prove the guard releases: same fixture, same code, green.
  writeFileSync(join(dir, ".gitignore"), "# Embedded separate repo - must not be tracked as a gitlink\n/medverify/\n");
  writeFileSync(join(dir, ".nojekyll"), "");
  fixtureGit(dir, ["rm", "-q", "--cached", "medverify"]);
  fixtureGit(dir, ["rm", "-q", "--cached", "CNAME"]);
  fixtureGit(dir, ["add", ".gitignore", ".nojekyll"]);
  fixtureGit(dir, ["commit", "-q", "-m", "remove the gitlink, ignore /medverify/, drop CNAME"]);

  assert.deepEqual(inspectPagesRepo({ repoDir: dir }), [], "the remediated fixture must read clean");
});

test("a declared submodule and an on-disk embedded repo are both seen", (t) => {
  const dir = makeFixture(t);
  writeFileSync(join(dir, ".nojekyll"), "");
  writeFileSync(join(dir, ".gitignore"), "/sandbox-nested/\n");

  // A gitlink WITH its .gitmodules entry is the survivable shape: no
  // orphan_gitlink, even though a `160000` mode is present.
  const pointerSha = fixtureGit(dir, ["rev-parse", "HEAD"]).trim();
  writeFileSync(join(dir, ".gitmodules"), '[submodule "docs-embed"]\n\tpath = docs-embed\n\turl = https://example.invalid/docs-embed\n');
  fixtureGit(dir, ["update-index", "--add", "--cacheinfo", `160000,${pointerSha},docs-embed`]);
  fixtureGit(dir, ["add", ".gitmodules", ".nojekyll", ".gitignore"]);
  fixtureGit(dir, ["commit", "-q", "-m", "a declared submodule"]);

  const declared = inspectPagesRepo({ repoDir: dir });
  assert.ok(!codesOf(declared).has("orphan_gitlink"), "a pointer named in .gitmodules is not the outage shape");

  // An embedded repo nobody listed in EMBEDDED_REPOS is found on disk and must
  // be ignored: `nested` has a .git/ and no rule; `sandbox-nested` has both.
  fixtureGit(dir, ["init", "-q", "nested"]);
  fixtureGit(dir, ["init", "-q", "sandbox-nested"]);
  const found = new Set(
    inspectPagesRepo({ repoDir: dir })
      .filter((v) => v.code === "embedded_repo_not_ignored")
      .map((v) => v.path),
  );
  assert.ok(found.has("nested"), `a newly embedded repo must be named; found ${[...found].join(", ") || "nothing"}`);
  assert.ok(!found.has("sandbox-nested"), "an ignored embedded repo must not be reported");
  for (const listed of EMBEDDED_REPOS) {
    assert.ok(
      readFileSync(join(repoRoot, "docs", "DEPLOY-STATUS.md"), "utf8").includes(listed),
      `EMBEDDED_REPOS names ${listed}, which docs/DEPLOY-STATUS.md no longer justifies`,
    );
  }
});

test("the consumer that runs this pin is the CI job the doc names", () => {
  // docs/DEPLOY-STATUS.md: "Every later `main` push must pass `Static site
  // quality`". This file is only a defense while that workflow's job still runs
  // `npm run test:unit`; pin the wiring so dropping the step is a red, not a
  // silently unprotected trunk.
  const workflow = readFileSync(join(repoRoot, ".github", "workflows", "site-quality.yml"), "utf8");
  assert.match(workflow, /name: Static site quality/);
  assert.match(workflow, /run: npm run test:unit/);
});
