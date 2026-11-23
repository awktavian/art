#!/usr/bin/env node
/**
 * The GitHub Pages deploy-tree invariants of `docs/DEPLOY-STATUS.md`, as one
 * runnable check.
 *
 * The Feb–Jul 2026 outage recorded in `docs/DEPLOY-STATUS.md` §"Feb–Jul 2026
 * outage: root cause (verified)" was not caused by a page. A WIP snapshot
 * commit (`a6ad2d9`) tracked the separate `medverify` repository as a **gitlink**
 * (git mode `160000`) with **no `.gitmodules`** entry; the Pages build's
 * `actions/checkout` ran `git submodule update --init --recursive`, aborted with
 * `fatal: No url found for submodule path 'medverify' in .gitmodules` (exit 128),
 * never reached its deploy step, and the published site 404'd for roughly 25
 * days. The remediation (§"Remediation applied (2026-07-11)") removed the
 * gitlink and added `/medverify/` to `.gitignore`.
 *
 * Until this file, no command could tell you any of that still holds. Measured
 * 2026-11-23 in `/Users/schizodactyl/projects/art`: `git grep -n 160000 -- .`
 * finds no text (a gitlink is a mode, not a string), and `git ls-files | grep
 * -E 'CNAME|nojekyll'` returns `.nojekyll` with nothing asserting that the one
 * stays present and the other stays absent. The gate that CI runs
 * (`scripts/check-site.mjs`, `test:static`) walks HTML, manifests and service
 * workers — it never asks git about the *shape of the tree*, which is exactly
 * the surface that broke the deploy.
 *
 * So this module asks git itself. `tests/unit/pages-deploy-invariants.test.mjs`
 * runs it on every `npm run test:unit`, which the `Static site quality` workflow
 * runs as its first step of the `static` job — so the sentence in
 * `docs/DEPLOY-STATUS.md` ("Every later `main` push must pass `Static site
 * quality`") now names a check that reads the shape that caused the outage.
 *
 * Standalone: `node scripts/pages-deploy-invariants.mjs [--repo DIR]`
 *   rc 0 — every invariant holds (one `clean` line on stdout)
 *   rc 1 — one line per violation, prefixed `VIOLATION <code> <path>`
 *   rc 2 — git itself could not be asked (not a verdict about the tree)
 */
import { execFileSync } from "node:child_process";
import { existsSync, readdirSync } from "node:fs";
import { dirname, join, resolve } from "node:path";
import { fileURLToPath, pathToFileURL } from "node:url";

const ROOT = resolve(dirname(fileURLToPath(import.meta.url)), "..");

/** git mode of an embedded repository entry (a "gitlink" / submodule pointer). */
const GITLINK_MODE = "160000";

/**
 * Separate repositories that live inside this tree but are not part of the
 * published site. `AGENTS.md` §"Key Projects" and `docs/DEPLOY-STATUS.md`
 * §"`/medverify` sub-app" both state it; `.gitignore` carries the rule that
 * keeps a `git add -A` from re-introducing the pointer. `inspectPagesRepo`
 * unions this list with what it finds on disk, so a NEW embedded repo is caught
 * even when nobody remembered to add it here.
 */
export const EMBEDDED_REPOS = ["medverify"];

/** Directories a depth-1 scan must not walk into (huge, and never a repo). */
const SCAN_SKIP = new Set(["node_modules", ".git"]);

function git(repoDir, args, { tolerate = [], quiet = false } = {}) {
  try {
    return {
      status: 0,
      stdout: execFileSync("git", ["-C", repoDir, ...args], {
        encoding: "utf8",
        maxBuffer: 64 * 1024 * 1024,
        stdio: quiet ? ["ignore", "pipe", "ignore"] : ["ignore", "pipe", "pipe"],
      }),
    };
  } catch (error) {
    if (typeof error.status === "number" && tolerate.includes(error.status)) {
      return { status: error.status, stdout: typeof error.stdout === "string" ? error.stdout : "" };
    }
    throw error;
  }
}

/** `git ls-tree -r -z` → [{mode, sha, path}]. */
function treeEntriesOf(repoDir, rev) {
  return git(repoDir, ["ls-tree", "-r", "-z", rev])
    .stdout.split("\0")
    .filter(Boolean)
    .map((row) => {
      const [meta, path] = row.split("\t");
      const [mode, , sha] = meta.split(" ");
      return { mode, sha, path };
    });
}

/** `git ls-files -s -z` → [{mode, sha, path}] — the tracked set as the index sees it. */
function indexEntriesOf(repoDir) {
  return git(repoDir, ["ls-files", "-s", "-z"])
    .stdout.split("\0")
    .filter(Boolean)
    .map((row) => {
      const [meta, path] = row.split("\t");
      const [mode, sha] = meta.split(" ");
      return { mode, sha, path };
    });
}

/**
 * Paths `git submodule update` would try to initialise: the `path = …` values of
 * the committed `.gitmodules`, which is the only thing that makes a `160000`
 * entry survivable for a checker-out reader.
 */
function declaredSubmodulePaths(repoDir) {
  let source;
  try {
    source = git(repoDir, ["show", "HEAD:.gitmodules"]).stdout;
  } catch (error) {
    if (error.status === 128) return { declared: new Set(), present: false };
    throw error;
  }
  const declared = new Set();
  for (const match of source.matchAll(/^[ \t]*path[ \t]*=[ \t]*(.+?)[ \t]*$/gim)) {
    declared.add(match[1]);
  }
  return { declared, present: true };
}

/** Repo root, or a directory inside it, that is itself a git working tree. */
export function embeddedPathsOnDisk(repoDir) {
  const found = new Set();
  for (const entry of readdirSync(repoDir, { withFileTypes: true })) {
    if (SCAN_SKIP.has(entry.name)) continue;
    if (!entry.isDirectory() && !entry.isSymbolicLink()) continue;
    if (existsSync(join(repoDir, entry.name, ".git"))) found.add(entry.name);
  }
  return found;
}

/**
 * Every invariant `docs/DEPLOY-STATUS.md` claims about the tree a Pages build
 * checks out. Returns [] when they all hold; otherwise one object per violation
 * with the code, the path and the reason a reader can act on.
 */
export function inspectPagesRepo({ repoDir = ROOT } = {}) {
  const violations = [];
  const add = (code, path, message) => violations.push({ code, path, message });

  const head = git(repoDir, ["rev-parse", "--verify", "--quiet", "HEAD"], { tolerate: [1, 128] });
  const tree = head.status === 0 ? treeEntriesOf(repoDir, "HEAD") : [];
  const index = indexEntriesOf(repoDir);
  const tracked = new Set(index.map((entry) => entry.path));

  if (head.status !== 0) {
    add(
      "head_unreadable",
      "HEAD",
      "no commit to read: the Pages builder deploys a checked-out tree, and this checkout has none to inspect",
    );
  }

  // 1 + 2 — the orphaned gitlink itself. The tree leg is what a Pages build
  // checks out; the index leg catches the same shape one commit earlier, while
  // it is still only staged.
  const gitlinkPaths = new Set();
  for (const entry of index) {
    if (entry.mode !== GITLINK_MODE) continue;
    gitlinkPaths.add(entry.path);
    add(
      "gitlink_in_index",
      entry.path,
      `mode ${GITLINK_MODE} in the index (${entry.sha}) — the embedded repository is one commit away from being published as a pointer`,
    );
  }
  for (const entry of tree) {
    if (entry.mode !== GITLINK_MODE) continue;
    gitlinkPaths.add(entry.path);
    add(
      "gitlink_in_tree",
      entry.path,
      `mode ${GITLINK_MODE} at ${entry.sha} in HEAD: actions/checkout runs 'git submodule update --init --recursive' and aborts on a pointer it cannot resolve (docs/DEPLOY-STATUS.md §Feb–Jul 2026 outage)`,
    );
  }

  // 3 — the exact shape of the outage: a pointer with no .gitmodules entry.
  const { declared, present } = declaredSubmodulePaths(repoDir);
  for (const path of gitlinkPaths) {
    if (!declared.has(path)) {
      add(
        "orphan_gitlink",
        path,
        `no 'path = ${path}' entry in ${present ? ".gitmodules" : "a .gitmodules file (none is committed)"} — this is the shape that 404'd the site for 25 days`,
      );
    }
  }

  // 4 + 5 — the Pages configuration the doc pins: plain static serving, and no
  // custom domain pulled in by a CNAME.
  if (!tracked.has(".nojekyll")) {
    add(
      "missing_nojekyll",
      ".nojekyll",
      "not tracked: without it Pages runs Jekyll over a vanilla-JS tree (docs/DEPLOY-STATUS.md §GitHub Pages configuration)",
    );
  }
  for (const entry of index) {
    if (entry.path === "CNAME" || entry.path.endsWith("/CNAME")) {
      add(
        "cname_tracked",
        entry.path,
        "a CNAME makes Pages serve a custom domain instead of github.io/art, which this repo has deprecated (docs/DEPLOY-STATUS.md §art.awkronos.com)",
      );
    }
  }

  // 6 + 7 — the containment rule, asked of git rather than of the .gitignore
  // text: the embedded repos must be ignored, and must publish nothing here.
  const embedded = new Set([...EMBEDDED_REPOS, ...embeddedPathsOnDisk(repoDir)]);
  for (const path of [...embedded].sort()) {
    // Ask about `path/`, not `path`. The committed rule is `/medverify/`, and a
    // directory-only pattern does NOT match the bare name when that directory
    // is absent from the checkout: measured 2026-11-23, `git check-ignore -v --
    // medverify` answered rc 0 in `/Users/schizodactyl/projects/art` (where the
    // separate repo sits on disk) and rc 1 in this lane's fresh worktree (where
    // it does not), for the same `.gitignore` blob at the same commit. The
    // trailing slash states "this is a directory" instead of leaving it to a
    // stat, so the leg answers the same way in every checkout and in CI.
    const probe = path.endsWith("/") ? path : `${path}/`;
    const ignored = git(repoDir, ["check-ignore", "--no-index", "--verbose", "--", probe], {
      tolerate: [1],
      quiet: true,
    });
    if (ignored.status !== 0) {
      add(
        "embedded_repo_not_ignored",
        path,
        "git check-ignore says no rule covers it, so a 'git add -A' WIP snapshot can re-introduce the pointer (docs/DEPLOY-STATUS.md §Remediation applied, step 2)",
      );
    }
    const shipped = [...tracked].filter((p) => p === path || p.startsWith(`${path}/`));
    if (shipped.length > 0) {
      add(
        "embedded_repo_tracked",
        path,
        `${shipped.length} tracked path(s) under it, first: ${shipped[0]} — a separate repository must not be published from this tree`,
      );
    }
  }

  return violations;
}

function parseArgv(argv) {
  let repoDir = ROOT;
  for (let i = 0; i < argv.length; i += 1) {
    if (argv[i] === "--repo") {
      i += 1;
      repoDir = resolve(argv[i] ?? ROOT);
    }
  }
  return { repoDir };
}

if (process.argv[1] && import.meta.url === pathToFileURL(resolve(process.argv[1])).href) {
  const { repoDir } = parseArgv(process.argv.slice(2));
  let violations;
  try {
    violations = inspectPagesRepo({ repoDir });
  } catch (error) {
    process.stderr.write(`pages-deploy-invariants: UNABLE to ask git about ${repoDir}: ${error.message}\n`);
    process.exit(2);
  }
  if (violations.length === 0) {
    process.stdout.write(`pages-deploy-invariants: clean — ${repoDir} keeps the Pages tree invariants\n`);
    process.exit(0);
  }
  for (const violation of violations) {
    process.stdout.write(`VIOLATION ${violation.code} ${violation.path} — ${violation.message}\n`);
  }
  process.exit(1);
}
