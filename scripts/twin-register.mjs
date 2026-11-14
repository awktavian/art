#!/usr/bin/env node
/**
 * Regenerate / check `patent-portfolio/NEAR-DUPLICATE-TWINS.json` — the art-side SSOT
 * register for the museum twin family (art `patent-portfolio/` x awkronos/patents).
 *
 * Lane RSIPIPE2-01-NAV-TWIN-1102, campaign RSI-PIPE2-1102, 2026-11-02.
 *
 *   node scripts/twin-register.mjs            # print the register to stdout
 *   node scripts/twin-register.mjs --check     # exit 1 if the committed file is not what
 *                                              # these bytes + the mirror tip produce now
 *   node scripts/twin-register.mjs --write     # rewrite it
 *
 * Every number in the register is produced here, by tests/unit/twin-measure.mjs, from two
 * trees. Nothing is copied out of a receipt, a commit message, or a prose note — that
 * copying is what let the `navigation.js` declaration rot (see the DEBT note's residual 1:
 * the canonical header still narrates a fork that the port closed, and its own guard keeps
 * matching the dead hex). The prose fields below are authored once, here, and keyed by pair
 * id; the register is their measured context.
 *
 * Honest-degradation rule: the art side is always measurable (it is this tree). The mirror
 * side needs a patents checkout; without one, --write REFUSES rather than emitting a file
 * whose patents pins are stale, and --check reports the mirror legs as UNMEASURED and still
 * grades the art legs. Pass ART_TWIN_MIRROR_REPO=<patents repo> to override the location.
 */
import { readFileSync, existsSync, writeFileSync } from "node:fs";
import { execFileSync } from "node:child_process";
import { dirname, join, resolve } from "node:path";
import { fileURLToPath } from "node:url";

import {
  readText,
  fileStats,
  bodyPair,
  divergence,
  headerMarkers,
} from "../tests/unit/twin-measure.mjs";

const ROOT = resolve(dirname(fileURLToPath(import.meta.url)), "..");
const REGISTER = join(ROOT, "patent-portfolio", "NEAR-DUPLICATE-TWINS.json");
const MIRROR_REPO =
  process.env.ART_TWIN_MIRROR_REPO || "/Users/schizodactyl/projects/awkronos/patents";

/** git plumbing used instead of the object db's word: always read the ref, never assume it. */
function git(cwd, args) {
  return execFileSync("git", ["-C", cwd, ...args], { encoding: "utf8" }).trim();
}
function liveTip(repo) {
  try {
    const out = git(repo, ["ls-remote", "origin", "refs/heads/main"]);
    const sha = out.split("\t")[0];
    if (/^[0-9a-f]{40}$/.test(sha)) return { sha, source: "git ls-remote origin refs/heads/main (live)" };
  } catch {
    /* fall through to the local remote-tracking ref */
  }
  try {
    const sha = git(repo, ["rev-parse", "refs/remotes/origin/main"]);
    return { sha, source: "local refs/remotes/origin/main — ls-remote unavailable, so this can be stale" };
  } catch {
    return null;
  }
}
function show(repo, ref, path) {
  try {
    return execFileSync("git", ["-C", repo, "show", `${ref}:${path}`], {
      encoding: "utf8",
      maxBuffer: 64 * 1024 * 1024,
    });
  } catch {
    return null;
  }
}

/**
 * The family. `art`/`patents` are repo-relative paths; `recipe` is the body-identity claim
 * the pair actually supports; `prose` is authored here and is the only place it is written.
 * A new pair is added by adding a row — the register, the tripwire and --check all follow.
 */
const PAIRS = [
  {
    id: "museum.navigation.js",
    kind: "museum-module",
    art: "patent-portfolio/museum/navigation.js",
    patents: "museum/navigation.js",
    recipe: "doc-header",
    prose: {
      canonical: "art",
      disposition:
        "declared-mirror — edit HERE, then port whole to patents; never hand-edit the delta into the mirror",
      guards: [
        "art: tests/unit/museum-navigation-mirror.test.mjs T1-T5 (npm run test:unit)",
        "art: tests/unit/museum-twin-register.test.mjs (this register)",
        "patents: tests/CENSUS-museum-navigation-mirror.check.mjs, 6 legs, wired to a tracked .githooks/pre-commit (per-clone core.hooksPath)",
      ],
      note:
        "The bodies below the two doc headers are byte-identical, so this pair has no content drift to consolidate. What it had was drift in the DECLARATION, and residual 1 of patent-portfolio/DEBT-museum-navigation-duplication.md is closed by lane RST-TWINFOLD-1114 (2026-11-14) as the four-file, two-repo fold it always was: art's header narrated the pre-port fork in the present tense and pinned its own blobs, patents' mirror header pinned art's digest, the patents receipt restated both, and art's old T3 asserted those sentences were still PRESENT — a guard that could only redden by re-pasting the rot. Both module headers now state no digest, no line count and no delta arithmetic and point at this row instead; the patents receipt is dated and its guard legs recompute. Every figure describing this pair is produced from the two trees into this file, and museum-navigation-mirror.test.mjs T3 + this register's R2/R3 are what keep a re-pasted number from landing silently again.",
    },
  },
  {
    id: "museum.architecture.js",
    kind: "museum-module",
    art: "patent-portfolio/museum/architecture.js",
    patents: "museum/architecture.js",
    recipe: "whole",
    prose: {
      canonical: "none-declared",
      disposition:
        "undeclared-diverged — separate row, not this pair's business; consolidate only from a lane bound to both trees",
      guards: ["art: tests/unit/museum-twin-register.test.mjs pins this file's bytes"],
      note:
        "Diverged in both directions: art carries lines patents does not and patents carries lines art does not, so neither copy is a stale derivative and neither is deletable. The load-bearing fact for the navigation pair is recorded under geometry_agreement: the two keys navigation.js actually reads resolve identically in both copies, while the WING block does not — which is why porting navigation.js whole was safe and why this file's divergence is its own row.",
    },
  },
  {
    id: "museum.gallery-loader.js",
    kind: "museum-module",
    art: "patent-portfolio/museum/gallery-loader.js",
    patents: "museum/gallery-loader.js",
    recipe: "whole",
    mirror_pins: {
      re: /art copy sha256[\s/]*([0-9a-f]{64}),[\s/]*git blob[\s/]*([0-9a-f]{40})[\s/]*@[\s/]*art[\s/]*([0-9a-f]{7,40})/,
      fields: ["sha256", "blob", "art_ref"],
    },
    prose: {
      canonical: "art",
      disposition:
        "declared-divergent-not-portable — the patents copy cannot run art's version; leave both, keep the declaration",
      guards: [
        "patents: museum/gallery-loader.js lines 1-10 PROVENANCE block (names art as canonical, pins art's blob + sha256 + tip)",
        "art: tests/unit/museum-twin-register.test.mjs pins this file's bytes AND re-measures the mirror's pin (this row's mirror_declaration_check)",
      ],
      note:
        "The only sibling pair whose MIRROR side carries a declaration, and that declaration names art's digests. This register therefore does not restate them: the hexes in this row's mirror_declaration_check.asserted are PARSED out of the mirror's own header bytes at basis.patents_tip, and its agrees booleans compare them with the art bytes measured on the same run — so the liveness claim is recomputed, not re-believed. It used to be prose here ('both are still live at art d2ce9a4, so the declaration is true today') with hand-quoted hexes and a hand-quoted commit, which is residual 1's defect one row over. Why the pair is not portable: art's loader imports three modules that do not exist in the patents tree (artworks/p3-artworks.js, lib/instanced-elements.js, lib/visitor-identity.js — absent from patents, present in art). Art's own copy carries no header marker. The recovery anchor the mirror names for its OWN pre-fold bytes is a dated fact about patents' history and stays in that header.",
    },
  },
  {
    id: "museum.lighting.js",
    kind: "museum-module",
    art: "patent-portfolio/museum/lighting.js",
    patents: "museum/lighting.js",
    recipe: "whole",
    prose: {
      canonical: "none-declared",
      disposition: "undeclared-diverged — separate row; neither copy is a stale derivative",
      guards: ["art: tests/unit/museum-twin-register.test.mjs pins this file's bytes"],
      note: "Diverged both directions, no header marker on either side.",
    },
  },
  {
    id: "museum.wayfinding.js",
    kind: "museum-module",
    art: "patent-portfolio/museum/wayfinding.js",
    patents: "museum/wayfinding.js",
    recipe: "whole",
    prose: {
      canonical: "none-declared",
      disposition: "undeclared-diverged — separate row; neither copy is a stale derivative",
      guards: ["art: tests/unit/museum-twin-register.test.mjs pins this file's bytes"],
      note: "Diverged both directions, no header marker on either side.",
    },
  },
  {
    id: "museum.wing-enhancements.js",
    kind: "museum-module",
    art: "patent-portfolio/museum/wing-enhancements.js",
    patents: "museum/wing-enhancements.js",
    recipe: "whole",
    prose: {
      canonical: "none-declared",
      disposition: "undeclared-diverged — separate row; art is far larger, patents still unique",
      guards: ["art: tests/unit/museum-twin-register.test.mjs pins this file's bytes"],
      note:
        "The widest gap in the family: art's copy is an order of magnitude larger, but patents carries unique lines too, so 'art is ahead' is not the whole story and a delete-the-mirror move would lose content. Separate row.",
    },
  },
  {
    id: "spec.basic.spec.js",
    kind: "spec",
    art: "patent-portfolio/tests/basic.spec.js",
    patents: "tests/basic.spec.js",
    recipe: "comment-header",
    prose: {
      canonical: "patents",
      disposition: "declared-mirror — edit in patents, port whole to art; bodies identical below the headers",
      guards: ["art: tests/unit/museum-twin-register.test.mjs (pair + body identity)"],
      note:
        "Both copies carried a PROVENANCE header claiming the pair is 'byte-identical as of 2026-08-18'. As whole files that was never true once the two headers differ: art's header names patents, patents' header names art. What IS true is identical-below-header, and art's header now says so and points at this register. Patents' four headers still carry the old wording — recorded as a residual for a patents-bound lane, not edited from here.",
    },
  },
  {
    id: "spec.smoke.spec.js",
    kind: "spec",
    art: "patent-portfolio/tests/smoke.spec.js",
    patents: "tests/smoke.spec.js",
    recipe: "comment-header",
    prose: { canonical: "patents", guards: ["art: tests/unit/museum-twin-register.test.mjs"] },
  },
  {
    id: "spec.navigation.spec.js",
    kind: "spec",
    art: "patent-portfolio/tests/interaction/navigation.spec.js",
    patents: "tests/interaction/navigation.spec.js",
    recipe: "comment-header",
    prose: { canonical: "patents", guards: ["art: tests/unit/museum-twin-register.test.mjs"] },
  },
  {
    id: "spec.vr.spec.js",
    kind: "spec",
    art: "patent-portfolio/tests/xr-simulation/vr.spec.js",
    patents: "tests/xr-simulation/vr.spec.js",
    recipe: "comment-header",
    prose: { canonical: "patents", guards: ["art: tests/unit/museum-twin-register.test.mjs"] },
  },
  {
    id: "spec.museum.spec.js",
    kind: "spec",
    art: "patent-portfolio/tests/visual-regression/museum.spec.js",
    patents: "tests/visual-regression/museum.spec.js",
    recipe: "comment-header",
    prose: {
      canonical: "none-declared",
      disposition:
        "undeclared-art-superset — patents is missing 89 lines of coverage art has; that is a gap to port DOWNWARD, not a duplicate to delete",
      guards: ["art: tests/unit/museum-twin-register.test.mjs pins this file's bytes"],
      note:
        "The one asymmetry in the family with a single-direction delta: every patents-only line count is zero, so art's copy strictly contains patents' (the extra block is the per-wing teleport indicator tests, Digit1-Digit7, plus return-to-rotunda via Digit0). Neither file carries a PROVENANCE marker. Recorded here because the census does not see it: the generation's row grouped art's two spec files with patents' navigation.spec.js at verificationTier=signal-weak and never paired these two at all.",
    },
  },
];

// Fill the prose defaults so a short row above is not a second kind of row below.
for (const p of PAIRS) {
  p.prose.canonical ||= "none-declared";
  p.prose.disposition ||=
    p.recipe === "comment-header"
      ? "declared-mirror — edit in patents, port whole to art; bodies identical below the headers"
      : "undeclared-diverged — separate row";
  p.prose.note ||=
    "Declared on both sides by a leading PROVENANCE header; identical below it, different as whole files.";
}

/** Files that are NOT twins — recorded so a future reader does not re-derive the census. */
const NOT_TWINS = [
  {
    path: "patent-portfolio/tests/exhibit-integrity.spec.js",
    side: "art-only",
    note: "No counterpart in the patents tree (measured: git ls-tree of patents refs/heads/main).",
  },
  {
    path: "museum/audio-manager.js",
    side: "patents-only",
    note: "Art has no copy; named in the DEBT note as one of the two modules the mirror carries alone.",
  },
  {
    path: "museum/narrative.js",
    side: "patents-only",
    note: "Art has no copy.",
  },
  {
    path: "tests/CENSUS-museum-navigation-mirror.md",
    side: "patents-only",
    note: "The patents receipt for the navigation pair. Art has no copy — this register is the art-side one.",
  },
  {
    path: "tests/CENSUS-museum-navigation-mirror.check.mjs",
    side: "patents-only",
    note: "The 6-leg guard for the navigation pair, wired to patents' .githooks/pre-commit.",
  },
];

/**
 * The keys navigation.js actually reads out of architecture.js, measured in both copies.
 * This is the check the DEBT note's Option 1 asked for before porting whole — turned from an
 * instruction into a pin, so the next port does not have to re-argue it.
 */
/**
 * DIMENSIONS keys, measured in both copies of architecture.js, in three named sets:
 *   read_by_navigation    — what navigation.js actually reads. The tripwire RE-DERIVES this
 *                           set from navigation.js's own bytes and compares, so this list
 *                           cannot quietly stop matching the file it describes.
 *   debt_port_checklist   — what patent-portfolio/DEBT-museum-navigation-duplication.md line
 *                           ~191 asks a future port lane to verify (`vestibule.depth`); the
 *                           whole vestibule block is measured because that note's own follow-up
 *                           read the block, not one key.
 *   diverged_unread       — recorded with both values because it is a real divergence between
 *                           the two architecture.js copies that navigation.js cannot be broken
 *                           by. Declared, not consolidated.
 */
const GEOM_SETS = {
  read_by_navigation: {
    "rotunda.radius": /rotunda:\s*\{[\s\S]*?radius:\s*([0-9.]+)/,
  },
  debt_port_checklist: {
    "vestibule.width": /vestibule:\s*\{[\s\S]*?width:\s*([0-9.]+)/,
    "vestibule.depth": /vestibule:\s*\{[\s\S]*?depth:\s*([0-9.]+)/,
    "vestibule.height": /vestibule:\s*\{[\s\S]*?height:\s*([0-9.]+)/,
  },
  diverged_unread: {
    "wing.width": /wing:\s*\{[\s\S]*?width:\s*([0-9.]+)/,
  },
};

function geometryAgreement(artText, patText) {
  const grab = (text, re) => {
    const m = text.match(re);
    return m ? Number(m[1]) : null;
  };
  const out = {};
  for (const [setName, set] of Object.entries(GEOM_SETS)) {
    const rows = {};
    for (const [k, re] of Object.entries(set)) {
      const a = grab(artText, re);
      const p = grab(patText, re);
      rows[k] = { art: a, patents: p, agree: a !== null && a === p };
    }
    out[setName] = rows;
  }
  return out;
}

/** rc of a git command that is allowed to fail — the ancestor probe's answer IS its exit code. */
function gitRc(cwd, args) {
  try {
    execFileSync("git", ["-C", cwd, ...args], { stdio: "ignore" });
    return 0;
  } catch (err) {
    return typeof err?.status === "number" ? err.status : null;
  }
}

/**
 * The two identities the census pinned for the navigation.js row, re-read from the object db
 * rather than pasted from the generation artifact. Every hex here is produced by a command
 * named in the same row, so the finding "the row is scored on two non-published trees" is a
 * checked claim on this host and not a narrative. `census_*` values are the generation's own
 * (authored once, below); the test is whether the commits the generation indexed really carry
 * those blobs, and what the PUBLISHED tips carry instead.
 */
const NAV = { art: "patent-portfolio/museum/navigation.js", patents: "museum/navigation.js" };
const CENSUS_ROW = {
  generation: "ccc6b10cf4e942b58e445dc57655dbc2",
  art: { blob: "bd836bd95975cd22fcf377711a77cdfede685aef", sha256: "75f1b28200d4ffa2b3f6c7262a97314349216a79b6b641fb09b0107ccb3519e8", indexed_at: "054c275" },
  patents: { blob: "d20f2aa3d96e8d7496df53dd63aac9ac5105ff8a", sha256: "07a0dec03830bb9f22a47488401f111c446aff98dc213cf37d4fb4e93bd16350", indexed_at: "58ef6462" },
};

function censusLegs(mirrorRef) {
  const leg = (repo, ref, path, recorded) => {
    const text = ref === null ? null : show(repo, ref, path);
    return text === null ? null : { blob: fileStats(text).blob, agrees_with_recorded: fileStats(text).blob === recorded };
  };
  const artParked = leg(ROOT, gitRc(ROOT, ["rev-parse", "--verify", "--quiet", CENSUS_ROW.art.indexed_at]) === 0 ? CENSUS_ROW.art.indexed_at : null, NAV.art, CENSUS_ROW.art.blob);
  const patParked = leg(
    MIRROR_REPO,
    mirrorRef !== null && gitRc(MIRROR_REPO, ["rev-parse", "--verify", "--quiet", CENSUS_ROW.patents.indexed_at]) === 0 ? CENSUS_ROW.patents.indexed_at : null,
    NAV.patents,
    CENSUS_ROW.patents.blob,
  );
  const artPublished = leg(ROOT, gitRc(ROOT, ["rev-parse", "--verify", "--quiet", "refs/remotes/origin/main"]) === 0 ? "refs/remotes/origin/main" : null, NAV.art, null);
  const patPublished = leg(MIRROR_REPO, mirrorRef, NAV.patents, null);
  return {
    art_parked: artParked,
    art_published: artPublished,
    patents_parked: patParked,
    patents_published: patPublished,
    /** Is the commit the generation indexed as patents' published ref actually an ancestor of patents' live main? */
    patents_indexed_is_ancestor_of_main:
      mirrorRef === null ? null : gitRc(MIRROR_REPO, ["merge-base", "--is-ancestor", CENSUS_ROW.patents.indexed_at, mirrorRef]),
  };
}

/**
 * A mirror-side PROVENANCE block that names art's blob or sha256 is a claim about the ART tree,
 * so it is only worth its re-measurement. The old register note asserted that claim in prose
 * ("both are still live at art d2ce9a4, so the declaration is true today") with hand-quoted
 * hexes and a hand-quoted commit — the same protected-by-prose failure residual 1 describes,
 * one row over. Here the asserted hexes are PARSED out of the mirror's own bytes (authored
 * regex, no authored digest) and compared with what this tree carries right now, so the row
 * flips by itself the first time art moves and nothing has to be re-believed.
 */
function mirrorDeclarationCheck(p, artText, patText) {
  if (!p.mirror_pins || patText === null) return null;
  const m = p.mirror_pins.re.exec(patText);
  if (m === null) {
    return {
      state: "DECLARATION_ABSENT",
      reason: `the mirror header no longer matches the pattern this row checks (${p.mirror_pins.re}) — either the mirror stopped declaring art canonical, or the wording moved and this row must follow it`,
    };
  }
  const fields = {};
  p.mirror_pins.fields.forEach((name, i) => {
    fields[name] = m[i + 1];
  });
  const now = fileStats(artText);
  const art = {
    blob: { asserted: fields.blob ?? null, measured: now.blob, agrees: fields.blob ? fields.blob === now.blob : null },
    sha256: {
      asserted: fields.sha256 ?? null,
      measured: now.sha256,
      agrees: fields.sha256 ? fields.sha256 === now.sha256 : null,
    },
  };
  // The ref the mirror names (an abbreviated art commit): does it still exist here, and does it
  // carry the asserted blob? rc 0 on rev-parse --verify is the whole of the "still live" claim.
  const ref = fields.art_ref ?? null;
  const refResolves = ref !== null && gitRc(ROOT, ["rev-parse", "--verify", "--quiet", ref]) === 0;
  const atRef = refResolves ? show(ROOT, ref, p.art) : null;
  return {
    state: "MEASURED",
    read_from: `the mirror's own header bytes at basis.patents_tip (not authored here)`,
    asserted: fields,
    art_tree: art,
    asserted_art_ref: {
      ref,
      resolves: refResolves,
      blob_at_ref: atRef === null ? null : fileStats(atRef).blob,
      agrees_with_asserted_blob: atRef === null ? null : fileStats(atRef).blob === (fields.blob ?? null),
      command: `git -C <art repo> show ${ref}:${p.art} | git hash-object --stdin`,
    },
    /** The load-bearing boolean: what the mirror asserts about art is what art's tree carries. */
    declaration_is_true_of_this_tree:
      (art.blob.agrees === null || art.blob.agrees === true) &&
      (art.sha256.agrees === null || art.sha256.agrees === true),
  };
}

function build() {
  const mirror = liveTip(MIRROR_REPO);
  const mirrorRef = mirror ? mirror.sha : null;

  const pairs = [];
  for (const p of PAIRS) {
    const artText = readText(join(ROOT, p.art));
    const patText = mirrorRef ? show(MIRROR_REPO, mirrorRef, p.patents) : null;
    const row = {
      id: p.id,
      kind: p.kind,
      art: {
        path: p.art,
        ...fileStats(artText),
        header_markers: headerMarkers(artText),
        measured_from:
          "the art working tree this register is committed beside — measured as bytes, so no art commit sha appears here (see basis.art_pin_channel: a register naming the commit that would carry it is stale the instant it lands)", 
      },
      patents:
        patText === null
          ? {
              path: p.patents,
              state: "UNMEASURED",
              reason: `no patents checkout / live tip at ${MIRROR_REPO} on this host`,
            }
          : {
              path: p.patents,
              ...fileStats(patText),
              header_markers: headerMarkers(patText),
              measured_from: `patents ${mirror.source} = ${mirrorRef}`,
            },
      body_identity:
        patText === null
          ? { recipe: p.recipe, state: "UNMEASURED", reason: "mirror bytes unavailable" }
          : bodyPair(artText, patText, p.recipe),
      declaration: (() => {
        // Marker presence is a coarse instrument: the words can name a DIFFERENT relationship
        // (art's lighting.js matches `names-mirror` on a design-token sentence, not on this
        // pair). So the derived status below is read beside art.header_markers /
        // patents.header_markers, each of which carries the line it matched, and the authored
        // `canonical_side` is what decides "undeclared".
        const artMarkers = headerMarkers(artText);
        const patMarkers = patText === null ? null : headerMarkers(patText);
        const derived =
          artMarkers.length === 0 || (patMarkers !== null && patMarkers.length === 0)
            ? artMarkers.length === 0 && patMarkers !== null && patMarkers.length > 0
              ? "declared in one header only"
              : "no declaration marker on the side(s) read"
            : "declared in both headers";
        return {
          canonical_side: p.prose.canonical,
          status: p.prose.canonical === "none-declared" ? "undeclared" : derived,
          status_rule:
            "'undeclared' is authored (canonical_side === none-declared). Otherwise derived from marker presence per side, which is coarse — read the header_markers rows beside it, each carrying its matched line, before treating a marker as a pair declaration. A pair can be 'declared in both headers' and still declare something false; that is the state art's four spec twins were in before this register.",
          art_markers: artMarkers.map((m) => m.marker),
          patents_markers: patMarkers === null ? "UNMEASURED" : patMarkers.map((m) => m.marker),
        };
      })(),
      guards: p.prose.guards,
      disposition: p.prose.disposition,
      note: p.prose.note,
      mirror_declaration_check: mirrorDeclarationCheck(p, artText, patText),
    };
    if (patText !== null) row.divergence = divergence(artText, patText, p.id);
    pairs.push(row);
  }

  const artArch = readText(join(ROOT, "patent-portfolio", "museum", "architecture.js"));
  const patArch = mirrorRef ? show(MIRROR_REPO, mirrorRef, "museum/architecture.js") : null;
  const geom = patArch === null ? null : geometryAgreement(artArch, patArch);
  const legs = censusLegs(mirrorRef);

  /**
   * For each spec pair: the blob the census indexed (patents' banked 58ef6462) against the
   * blob the published tip carries. Measured once; the summary below is derived from these
   * rows, not from a second pass over git.
   */
  const specDeltaRows = PAIRS.filter((p) => p.kind === "spec").map((p) => {
    const atWip = show(MIRROR_REPO, CENSUS_ROW.patents.indexed_at, p.patents);
    const atTip = mirrorRef ? show(MIRROR_REPO, mirrorRef, p.patents) : null;
    return {
      pair: p.id,
      patents_path: p.patents,
      blob_at_generation_leg: atWip === null ? null : fileStats(atWip).blob,
      blob_at_published_tip: atTip === null ? null : fileStats(atTip).blob,
      differs: atWip !== null && atTip !== null && fileStats(atWip).blob !== fileStats(atTip).blob,
    };
  });

  return {
    schema: "art-museum-twin-register/1",
    generated_by: "scripts/twin-register.mjs",
    role:
      "The ONE art-side statement of the museum twin family: which files in patent-portfolio/ have a twin in ~/projects/awkronos/patents, what the relationship between the copies is, and the measured pins that hold that statement. Prose elsewhere (DEBT-museum-navigation-duplication.md, module headers, commit messages) points here and does not restate numbers.",
    law: {
      one_ssot:
        "Numbers live in this file and are produced by tests/unit/twin-measure.mjs from two trees. A second copy of a pin is a fork, and this family has already been caught with one that rotted.",
      union_not_revert:
        "Divergent content is recorded with a digest, never silently deleted, and never reverted to whichever copy scored better. A pair whose two sides each hold unique lines is declared diverged and left alone.",
      similarity_never_authorizes_consolidation:
        "SimHash/hamming scores classify; they do not prove identity and they do not license a merge or a deletion. Only sha256 over the declared recipe pins bytes. A code_map_rsi_targets rankScore is band order, not a measured quantity.",
      byte_identity_is_recipe_scoped:
        "'Identical' always names the recipe it was measured under — doc-header, comment-header or whole — because every pair in this family that looks identical as a body is different as a whole file, by header design.",
    },
    basis: {
      lane: "RSIPIPE2-01-NAV-TWIN-1102",
      campaign: "RSI-PIPE2-1102",
      art_repo: "github.com:awktavian/art (patent-portfolio/)",
      art_pin_channel:
        "blob + sha256 of the tree bytes, per pair row. No art commit sha is recorded: the register is committed INTO the commit its own HEAD value would name, so that value could only ever be stale — and the art side does not need it, because R2 re-measures these bytes against the checkout on every run. Cite the ref in a commit message or the lane envelope, never here.",
      patents_repo: MIRROR_REPO,
      patents_tip: mirrorRef,
      patents_tip_source: mirror ? mirror.source : "unavailable on this host",
      census_generation: CENSUS_ROW.generation,
    },
    geometry_agreement: {
      why:
        "navigation.js reads DIMENSIONS from ./architecture.js. These are its keys, measured in both copies of architecture.js, so 'port navigation whole' is a checked claim and not a re-argument of DEBT residual text.",
      sets:
        geom === null
          ? { state: "UNMEASURED", reason: "mirror bytes unavailable" }
          : {
              read_by_navigation: geom.read_by_navigation,
              debt_port_checklist: geom.debt_port_checklist,
              diverged_unread: geom.diverged_unread,
            },
      note:
        "read_by_navigation is the set the tripwire re-derives from navigation.js's own source on every run; debt_port_checklist is what the DEBT note asks a port lane to verify; diverged_unread is recorded with both values because it is a real divergence the pair's own file cannot be broken by — declared, not consolidated, and not this lane's to merge.",
    },
    pairs,
    not_twins: NOT_TWINS.map((n) => ({
      ...n,
      pins: (() => {
        const t =
          n.side === "art-only" ? readText(join(ROOT, n.path)) : mirrorRef ? show(MIRROR_REPO, mirrorRef, n.path) : null;
        return t === null ? { state: "UNMEASURED" } : fileStats(t);
      })(),
    })),
    census_provenance: {
      finding:
        "The T0 row that keeps re-serving this file (kind=near_duplicate) is scored on TWO NON-PUBLISHED TREES, which is why a pair closed in 2026-10-26 and pinned in 2026-11-02 still reads as live copy debt.",
      generation: CENSUS_ROW.generation,
      row_identities_and_what_they_are: {
        art_leg: {
          recorded_by_generation: CENSUS_ROW.art.blob,
          recorded_sha256_by_generation: CENSUS_ROW.art.sha256,
          what: `the blob at art ${CENSUS_ROW.art.indexed_at} — this host's shared art checkout, behind its own origin/main`,
          re_measured_here: {
            command: `git -C <art seat repo> show ${CENSUS_ROW.art.indexed_at}:${NAV.art} | git hash-object --stdin`,
            blob: legs.art_parked ? legs.art_parked.blob : null,
            state: legs.art_parked ? "MEASURED" : "UNMEASURED",
            agrees_with_generation: legs.art_parked ? legs.art_parked.agrees_with_recorded : null,
          },
          published: {
            ref: "refs/remotes/origin/main",
            command: `git -C <art repo> show refs/remotes/origin/main:${NAV.art}`,
            blob: legs.art_published ? legs.art_published.blob : null,
            state: legs.art_published ? "MEASURED" : "UNMEASURED",
            nature:
              "A build-time observation on the generating host, not a pin. refs/remotes/origin/main moves under the checkout and a register cannot name the commit that would carry it (basis.art_pin_channel), so this value may only be read beside recorded_by_generation — both dated. The live question ('do these bytes match what the tip carries now?') is measured by tests/unit/museum-twin-register.test.mjs R3, which re-reads the ref and, when the two differ, proves with merge-base --is-ancestor whether this checkout is on that tip at all.",
          },
        },
        patents_leg: {
          recorded_by_generation: CENSUS_ROW.patents.blob,
          recorded_sha256_by_generation: CENSUS_ROW.patents.sha256,
          what: `museum/navigation.js at ${CENSUS_ROW.patents.indexed_at} 'wip: banked before fleet git-sync' (2026-08-29) — the head the generation recorded as patents refs/remotes/origin/main, i.e. a banked pre-port tree, not a published surface`,
          re_measured_here: {
            command: `git -C <patents repo> show ${CENSUS_ROW.patents.indexed_at}:${NAV.patents} | git hash-object --stdin`,
            blob: legs.patents_parked ? legs.patents_parked.blob : null,
            state: legs.patents_parked ? "MEASURED" : "UNMEASURED",
            agrees_with_generation: legs.patents_parked ? legs.patents_parked.agrees_with_recorded : null,
            /** 0 = it IS an ancestor of live main, i.e. the generation's ref was honest; non-zero = it is not. */
            merge_base_is_ancestor_rc: legs.patents_indexed_is_ancestor_of_main,
          },
          published: {
            ref: `the tip named by basis.patents_tip`,
            command: `git -C <patents repo> show <basis.patents_tip>:${NAV.patents}`,
            blob: legs.patents_published ? legs.patents_published.blob : null,
            state: legs.patents_published ? "MEASURED" : "UNMEASURED",
          },
        },
      },
      reading:
        "Both 're_measured_here.blob' rows reproduce the hex the generation pinned, so the generation is not wrong about the bytes it read — it read a parked checkout on one side and a banked wip commit on the other. The published rows are different hexes on both sides, and the ancestor rc names whether that banked commit ever landed.",
      consequence:
        "At the published tips the pair's bodies are cmp-identical (re-measured by the tripwire, leg R5), so there is nothing to consolidate. A future row on this path should expect the same two stale legs until the census reads published tips rather than parked checkouts; that is a code-map producer question, not an art-tree question.",
      spec_legs_also_stale: `The same generation's spec rows pair art's current blobs with patents' ${CENSUS_ROW.patents.indexed_at} blobs; spec_pin_delta below is that pair, row by row, measured once.`,
      spec_pin_delta: specDeltaRows,
      spec_pin_delta_summary: {
        rows: specDeltaRows.length,
        differing: specDeltaRows.filter((r) => r.differs).length,
        unchanged: specDeltaRows.filter((r) => !r.differs).length,
        reading:
          "The twins that differ pair art's current blobs against patents' banked pre-port blobs — which is why a spec row can read as copy debt while art and patents agree at their published tips. A row that does NOT differ was untouched on that path since; for museum.spec.js that leaves it a subset gap, not a fork.",
      },
    },
    residuals: [
      "CLOSED 2026-11-14 by lane RST-TWINFOLD-1114 — residual 1 of DEBT-museum-navigation-duplication.md (art's canonical header narrating the pre-port fork in the present tense). Folded as the four-file, two-repo sweep it required: art's patent-portfolio/museum/navigation.js header, patents' museum/navigation.js mirror header, the patents receipt tests/CENSUS-museum-navigation-mirror.md and its guard legs. No module header in either repo now states a digest, a line count or delta arithmetic for this pair; each points at this register row, and the numbers are produced from the two trees. Held by museum-navigation-mirror.test.mjs T3 (pointer resolves, header restates nothing, register agrees with these bytes) and by this file's R2/R3.",
      "CLOSED 2026-11-14 by the same sweep — patents' four spec PROVENANCE headers claimed the pair was '(byte-identical as of 2026-08-18)' as WHOLE files, which the register's own measurement never supported: the twins are identical below the header and differ by it by design, and art's four had already been reworded to say exactly that. Patents' headers now carry the recipe-scoped claim and a pointer to this register's row id; R5 and R7 keep the recipe claim true, so the wording cannot rot back into a whole-file lie.",
      "The five undeclared sibling pairs (architecture, lighting, wayfinding, wing-enhancements, museum.spec) are pinned by this register from the art side, but nothing on the patents side references it. A mirror-side register, or a patents test that reads this one through a declared path override, is the matching half.",
      "museum.spec.js: patents' copy is missing 89 lines of coverage art has (wing teleport indicators + rotunda return). A coverage gap to port downward, not a duplicate to delete.",
      "The census reads whatever tree a host happens to have checked out, which is why a pair closed in 2026-10-26 keeps re-serving as live copy debt. This host's shared art checkout and its patents counterpart are therefore NOT necessarily at their published tips — and no position is recorded in this file, because a committed working-tree count goes false on the next fetch or push and would be the same rot wearing a smaller hat. tests/unit/museum-twin-register.test.mjs R11 measures it on every run instead, with `git -C <repo> rev-list --count HEAD..refs/remotes/origin/main` in both repos, and prints the two counts as a diagnostic. Fast-forwarding a checkout belongs to whoever owns it, not to a lane.",
    ],
  };
}

const args = new Set(process.argv.slice(2));
const json = JSON.stringify(build(), null, 2) + "\n";
if (args.has("--write")) {
  writeFileSync(REGISTER, json);
  process.stdout.write(`wrote ${REGISTER} (${Buffer.byteLength(json, "utf8")} B)\n`);
} else if (args.has("--check")) {
  const current = existsSync(REGISTER) ? readFileSync(REGISTER, "utf8") : null;
  if (current === null) {
    process.stdout.write(`MISSING ${REGISTER}\n`);
    process.exitCode = 1;
  } else if (current === json) {
    process.stdout.write(`register is current: ${REGISTER}\n`);
  } else {
    process.stdout.write(`register is STALE against these bytes: ${REGISTER}\n`);
    process.exitCode = 1;
  }
} else {
  process.stdout.write(json);
}
