/**
 * cfsg-proof-graph-bridge.mjs — a READ-ONLY bridge from a CFSG certificate
 * census into the Hub proof-graph schema.
 *
 * WHY THIS FILE EXISTS. The estate has four proof-graph surfaces sitting on
 * three different node capacities, and none of them carries a CFSG DECLARATION:
 *
 *   1. Hub `/proofs` atlas  — DECLARATION-level. 19,916 nodes / 45,339 edges,
 *      all of them `kind: "uses"`, sourced from the 10 `gifts/*` Lean repos.
 *      Owner: `packages/lean-build-graph/src/index.ts` (DeclRecord/Edge),
 *      producer `tools/graph-merge/src/index.ts`, layout consumer
 *      `tools/graph-layout/src/index.ts`.
 *   2. Kimina `proof_graph` — PROJECT/FILE-level with a declaration layer that
 *      is currently dark (`/tmp/kagami-kimina-graph.json`: 40 nodes, all
 *      `kind: "project"`, 0 edges, `degraded.is_degraded: true`; and the
 *      declaration layer's own `uses.present: false` says "UNKNOWN, not zero").
 *   3. Kagami code-map — FILE-level (38,898 nodes / 65,640 edges).
 *   4. CFSG reactor cone graph — MODULE-level (`…/CFSG-REACTOR-1030/work/graph/
 *      summary.json`: 230,966 nodes / 1,497,728 import edges).
 *
 * WHAT CFSG HAS TODAY, AND WHAT IT HAS NONE OF. Measured in this lane: the Hub
 * DOES carry a CFSG surface — `apps/hub/data/cfsg/{build-coverage,kernel-shapes,
 * receipt}.json` (schemas `waddle.cfsg.build-coverage.v1`,
 * `waddle.cfsg.kernel-shapes.v1`, `waddle.cfsg.receipt.v1`, written by
 * `apps/hub/scripts/cfsg-waddle-data.mjs`; receipt counts 229,015 lean files /
 * 2,400 certificates / 69 families / 1,582 subfamilies, timingsMs.total 62,280)
 * rendered by `apps/hub/app/cfsg-periodic-table/`. What CFSG has zero of is a
 * NODE in the declaration graph: `grep -c '"cfsg"' apps/hub/data/proofs-graph.json`
 * is 0, and that file's `waddles` array lists the 10 person-waddles only. So the
 * two CFSG facts — "which family/module is built" (module granularity) and "which
 * declaration depends on which axioms" (declaration granularity) — sit on
 * different surfaces with no edge between them. This bridge is the minimal proof
 * that the second fact is mountable as nodes into surface (1), the only surface
 * whose node capacity (one node per declaration) matches what a certificate
 * census row actually is.
 *
 * WHAT IT DOES. It reads the census shape published by
 * `kagami.cfsg-axiom-census.v1` (example artifact:
 * `~/.kagami/solver-certs/GR-FULLSEND-1027-CFSG-AXIOM-CENSUS.json`,
 * sha256 68f0a35d44fbb136713c1adafd8f08c74c12dd6a742e3d815884ab916a27a6e8),
 * turns each executed-probe row into a `DeclRecord` node, and emits a
 * `LayoutPayload` v2 beside it — then refuses, by name, every relation it
 * cannot carry. The refusal list is the deliverable as much as the graph is:
 * it is the measured gap between "certificate" and "proof graph".
 *
 * WHAT IT NEVER CLAIMS. The census's own `tier_law` is carried verbatim into
 * `graph.certification.notClaiming`: "all rows are source_level/executed_probe
 * about individual declarations; no CFSG statement is machine-checked by this
 * artifact (PC-8: no build receipt)". `kernelVerified` is `false`. A node here
 * is a map of what an executed `#print axioms` probe reported for one pinned
 * commit — not a closure certificate. This mirrors the Hub's own evidence band
 * (`apps/hub/lib/proofs-atlas.ts` `evidenceBand()`), which likewise can never
 * report a verified tier.
 *
 * NO NEW DEPENDENCIES AND NO I/O. The module imports two node builtins
 * (`node:crypto` for the digests, `node:path`'s `posix` for the identity law's
 * path normalization) and reads no file: a census is handed to it parsed, and the
 * graph / layout / receipt are returned as plain objects. The layout is a
 * faithful port of the dependency-free halves of
 * `packages/graph-engine/src/pagerank.ts` and `layout.ts` (`layoutHierarchical`
 * only — `layoutForceDirected` needs d3-force, which this repo does not carry).
 * The ports are pinned to the byte digests recorded in the producer's own
 * completion receipt (`proof-graph-build-receipt.json → implementation`), which
 * this lane re-measured against the live files and found unchanged:
 * graph-merge `e7cf806c…`, graph-layout `6ac4e113…`, layout.ts `fe852457…`,
 * pagerank.ts `2e906b28…`. Drift is therefore detectable, not silent.
 *
 * @module
 */

import { createHash } from "node:crypto";
import { posix } from "node:path";

/** The census artifact schema this bridge reads (verified against the file above). */
export const CENSUS_SCHEMA = "kagami.cfsg-axiom-census.v1";

/**
 * The Hub's node-identity law, ported from
 * `tools/graph-merge/src/index.ts:161-174` (`encodeIdentityComponent`) and
 * `:189-196` (`nodeIdentityBase`). Bijective and URL-safe: `[A-Za-z0-9.-]`
 * survives, every other character becomes `_<hex-byte>` per byte — including
 * `_` itself, which is what makes the encoding invertible.
 *
 * `tests/unit/cfsg-proof-graph-bridge.test.mjs` holds the positive control:
 * applying this to the audrey seed reproduces a node id that is published,
 * byte for byte, in `apps/hub/data/proofs-graph.json`.
 */
export function encodeIdentityComponent(value) {
  const encoder = new TextEncoder();
  let encoded = "";
  for (const char of value) {
    if (/^[A-Za-z0-9.-]$/.test(char)) {
      encoded += char;
      continue;
    }
    for (const byte of encoder.encode(char)) {
      encoded += `_${byte.toString(16).padStart(2, "0")}`;
    }
  }
  return encoded;
}

/**
 * Port of `normalizeSourceFile` (`tools/graph-merge/src/index.ts:145-158`):
 * backslashes to slashes, a leading `./` stripped, `path.posix.normalize`d, then
 * a refusal for an empty result, `.`, an absolute path, `..`, or anything reaching
 * above the project root. The absolute leg is why this is the hub's predicate and
 * not a hand-rolled one: a `split("/")` loop silently DROPS the leading slash and
 * mounts `/abs/Foo.lean` as `abs/Foo.lean` — a different claim, accepted silently.
 *
 * The one addition over the TypeScript original is the runtime `typeof` guard: TS
 * enforces it at compile time there, and a census read out of JSON has no compiler.
 */
export function normalizeSourceFile(file) {
  if (typeof file !== "string") {
    throw new Error(`declaration has no stable project-relative source file: ${JSON.stringify(file)}`);
  }
  const slashNormalized = file.trim().replaceAll("\\", "/").replace(/^\.\/+/, "");
  const normalized = posix.normalize(slashNormalized);
  if (
    !slashNormalized ||
    normalized === "." ||
    posix.isAbsolute(normalized) ||
    normalized === ".." ||
    normalized.startsWith("../")
  ) {
    throw new Error(`declaration has no stable project-relative source file: ${JSON.stringify(file)}`);
  }
  return normalized;
}

/** Port of `nodeIdentityBase` — `waddle::file::fqn`, each component encoded. */
export function nodeIdentityBase({ waddle, file, fqn }) {
  if (!String(waddle ?? "").trim()) throw new Error("declaration has no waddle identity");
  if (!String(fqn ?? "").trim()) throw new Error("declaration has no FQN identity");
  return [waddle.trim(), normalizeSourceFile(file), fqn.trim()]
    .map(encodeIdentityComponent)
    .join("::");
}

/**
 * Port of `planNodeIdentities` (`graph-merge/src/index.ts:199-233`): the base id
 * is `waddle::file::fqn`; a source line is appended ONLY on a base collision, and
 * a collision that the line cannot break is a hard refusal.
 *
 * A census row carries no line, so `line` is 0 — "the census did not capture a
 * line". That is safe while ids are unique (the line never enters the id) and
 * loud when they are not (two rows with the same file+fqn both carry line 0, so
 * the documented `lines.has(line)` guard throws instead of minting a duplicate).
 */
export function planNodeIds(seeds) {
  const normalizedFiles = seeds.map((seed) => normalizeSourceFile(seed.file));
  const bases = seeds.map((seed, index) =>
    nodeIdentityBase({ ...seed, file: normalizedFiles[index] }),
  );
  const groups = new Map();
  bases.forEach((base, index) => {
    const list = groups.get(base);
    if (list) list.push(index);
    else groups.set(base, [index]);
  });
  const ids = [...bases];
  let lineFallbacks = 0;
  for (const [base, indices] of groups) {
    if (indices.length === 1) continue;
    const lines = new Set();
    for (const index of indices) {
      const line = seeds[index].line;
      if (!Number.isInteger(line) || line < 0 || lines.has(line)) {
        throw new Error(`non-unique declaration identity ${base}; source line cannot disambiguate ${String(line)}`);
      }
      lines.add(line);
      ids[index] = `${base}::line:${line}`;
      lineFallbacks += 1;
    }
  }
  if (new Set(ids).size !== ids.length) throw new Error("node identity planning produced duplicate IDs");
  return { ids, normalizedFiles, lineFallbacks };
}

/**
 * The edge-kind vocabulary the Hub's layout consumer will position, ported from
 * `tools/graph-layout/src/index.ts:78-83`. It is NOT the same set the producer
 * emits: `packages/lean-build-graph/src/index.ts:48` and
 * `tools/graph-merge/src/index.ts:36` both include `"imports"`, and
 * `graph-merge/src/index.ts:609` produces `imports` edges, while the layout
 * guard at `:165-167` throws on one. Measured today only because the published
 * graph carries `imports: 0` (`proofs-graph.meta.json → integrity.imports`), so
 * the gap is dormant, not absent. This bridge refuses `imports` by name for the
 * same reason the layout does, and says so in `refusals`.
 */
export const LAYOUT_EDGE_KINDS = Object.freeze(["uses", "instance_of", "extends", "proves"]);

/** `graph-merge/src/index.ts:36` / `lean-build-graph/src/index.ts:48`. */
export const PRODUCER_EDGE_KINDS = Object.freeze(["uses", "imports", "instance_of", "extends", "proves"]);

/**
 * The kind floor the layout applies to a kind outside the eight it knows, ported
 * from `tools/graph-layout/src/index.ts:68-89`: an unknown kind positions as
 * `"def"`. `apps/hub/lib/proofs-atlas.ts:228-242` documents the matching rule on
 * the read side — an unrecognised kind takes the tier floor rather than being
 * promoted into a proof tier. A certificate row carries no Lean declaration kind,
 * so this bridge hands one over as `"certificate"` and lets both floors do their
 * documented job: it is rendered as a definition, never as a theorem.
 */
export const CERTIFICATE_NODE_KIND = "certificate";

/** `graph-merge/src/index.ts:369-375` — anything the producer does not name becomes `uses`. */
export function normalizeEdgeKind(kind) {
  return PRODUCER_EDGE_KINDS.includes(kind) ? kind : "uses";
}

function canonicalJson(value) {
  if (value === null || typeof value !== "object") return JSON.stringify(value);
  if (Array.isArray(value)) return `[${value.map(canonicalJson).join(",")}]`;
  const keys = Object.keys(value).sort();
  return `{${keys.map((k) => `${JSON.stringify(k)}:${canonicalJson(value[k])}`).join(",")}}`;
}

function sha256(text) {
  return createHash("sha256").update(text).digest("hex");
}

/** How many times each value is repeated, summed over the repeats (a value seen
 *  three times contributes 3). Matches the denominator the published meta uses:
 *  19,916 nodes, `duplicateFqns: 8`. */
function countDuplicates(values) {
  const seen = new Map();
  for (const value of values) seen.set(value, (seen.get(value) ?? 0) + 1);
  let total = 0;
  for (const count of seen.values()) if (count > 1) total += count;
  return total;
}

/**
 * Port of `packages/graph-engine/src/pagerank.ts:33-99` — foundational direction
 * (edges as stored, consumer → dep), damping 0.85, 100 iterations, tolerance 1e-6,
 * dangling-node mass spread uniformly, then min-max normalised to [0,1].
 * `Float64Array` is kept, because the iteration order of the arithmetic is part
 * of what makes the output byte-stable.
 */
export function computeFoundationalPageRank(nodes, edges, options = {}) {
  const damping = options.damping ?? 0.85;
  const iterations = options.iterations ?? 100;
  const tolerance = options.tolerance ?? 1e-6;
  const n = nodes.length;
  if (n === 0) return new Map();
  const ids = nodes.map((x) => x.id);
  const idx = new Map(ids.map((id, i) => [id, i]));
  const out = Array.from({ length: n }, () => []);
  for (const e of edges) {
    const a = idx.get(e.from);
    const b = idx.get(e.to);
    if (a == null || b == null || a === b) continue;
    out[a].push(b);
  }
  const rank = new Float64Array(n).fill(1 / n);
  const next = new Float64Array(n);
  for (let it = 0; it < iterations; it++) {
    next.fill((1 - damping) / n);
    let dangling = 0;
    for (let i = 0; i < n; i++) {
      const o = out[i];
      if (o.length === 0) {
        dangling += rank[i];
      } else {
        const share = (damping * rank[i]) / o.length;
        for (const j of o) next[j] += share;
      }
    }
    const danglingShare = (damping * dangling) / n;
    for (let i = 0; i < n; i++) next[i] += danglingShare;
    let delta = 0;
    for (let i = 0; i < n; i++) {
      delta += Math.abs(next[i] - rank[i]);
      rank[i] = next[i];
    }
    if (delta < tolerance) break;
  }
  let min = Infinity;
  let max = -Infinity;
  for (let i = 0; i < n; i++) {
    if (rank[i] < min) min = rank[i];
    if (rank[i] > max) max = rank[i];
  }
  const span = Math.max(1e-12, max - min);
  const result = new Map();
  for (let i = 0; i < n; i++) result.set(ids[i], (rank[i] - min) / span);
  return result;
}

/**
 * Port of `layoutHierarchical` (`packages/graph-engine/src/layout.ts:133-191`):
 * layer = longest path from any source, ids sorted within a layer, one row per
 * layer. Dependency-free and deterministic, which is why the bridge ships this
 * and not `layoutForceDirected` (that one needs `d3-force` and monkey-patches
 * `Math.random`).
 */
export function layoutHierarchical(nodes, edges, options = {}) {
  const size = options.size ?? 1000;
  const incoming = new Map();
  const outgoing = new Map();
  for (const node of nodes) {
    incoming.set(node.id, []);
    outgoing.set(node.id, []);
  }
  for (const e of edges) {
    if (!incoming.has(e.to) || !outgoing.has(e.from)) continue;
    incoming.get(e.to).push(e.from);
    outgoing.get(e.from).push(e.to);
  }
  const layer = new Map();
  function depth(id, stack) {
    if (layer.has(id)) return layer.get(id);
    if (stack.has(id)) return 0;
    stack.add(id);
    let d = 0;
    for (const parent of incoming.get(id) ?? []) d = Math.max(d, depth(parent, stack) + 1);
    stack.delete(id);
    layer.set(id, d);
    return d;
  }
  for (const node of nodes) depth(node.id, new Set());
  const layers = new Map();
  for (const [id, l] of layer) {
    if (!layers.has(l)) layers.set(l, []);
    layers.get(l).push(id);
  }
  const maxLayer = Math.max(0, ...layers.keys());
  const layerH = size / Math.max(1, maxLayer + 1);
  const positions = [];
  for (const [l, ids] of layers) {
    ids.sort();
    const colW = size / (ids.length + 1);
    ids.forEach((id, i) => {
      positions.push({ id, x: colW * (i + 1), y: layerH * (l + 0.5) });
    });
  }
  return { positions, energy: 0 };
}

/** Verdicts the census publishes (`census.verdict_words.row_verdicts`). */
export const CENSUS_VERDICTS = Object.freeze([
  "AXIOM_FREE",
  "CORE_THREE",
  "DEPENDENT",
  "UNSOUND",
  "PROBE_FAILED",
  "ABSENT",
]);

const CORE_THREE = new Set(["propext", "Classical.choice", "Quot.sound"]);

/**
 * Mount CFSG certificate rows into the Hub proof-graph schema.
 *
 * @param {object} census   a `kagami.cfsg-axiom-census.v1` artifact (parsed).
 * @param {object} [options]
 * @param {string} [options.waddle="cfsg"]  the identity-law first component.
 * @param {Array<{from:string,to:string,file:string,line:number,note?:string}>} [options.ledger=[]]
 *        declaration-to-declaration references, each with a source citation. This
 *        is the mount's data contract: a reference without a cite is refused.
 * @param {string} [options.generatedAt]  overrides the census stamp.
 * @returns {{graph: object, layout: object, refusals: Array<{code:string,reason:string,subject:string}>}}
 */
export function buildCertificateGraph(census, options = {}) {
  const waddle = options.waddle ?? "cfsg";
  const ledger = options.ledger ?? [];
  const refusals = [];
  const refuse = (code, reason, subject) => refusals.push({ code, reason, subject });

  if (!census || typeof census !== "object") throw new Error("certificate census is missing");
  if (census.schema && census.schema !== CENSUS_SCHEMA) {
    throw new Error(`unrecognized census schema ${JSON.stringify(census.schema)}; this bridge reads ${CENSUS_SCHEMA} only`);
  }
  const rows = census?.exec_leg?.sample;
  if (!Array.isArray(rows)) throw new Error("census has no exec_leg sample array");

  // ── nodes: one per executed probe that actually ran ───────────────────────
  // rc !== 0 is a refusal, not a node. Measured reason to insist on it: in the
  // GR-FULLSEND-1027 artifact two of the 13 rows carry `rc: 1` alongside the
  // verdict `AXIOM_FREE` — the verdict was read off the probe's output text while
  // `lean` itself exited non-zero. A consumer that joins on `verdict` alone
  // mounts a claim the executor never accepted.
  const seeds = [];
  const rowByIndex = [];
  for (const row of rows) {
    if (typeof row?.decl !== "string" || !row.decl.trim()) {
      refuse("row_has_no_declaration_name", "an exec_leg row with no `decl` cannot become a node; identity needs an FQN", JSON.stringify(row?.path ?? null));
      continue;
    }
    if (row.rc !== 0) {
      refuse(
        "probe_rc_nonzero",
        "the probe exited non-zero, so no verdict on this row is executor-accepted; mounting it would inherit a claim the census could not confirm",
        row.decl,
      );
      continue;
    }
    if (typeof row.path !== "string" || !row.path.trim()) {
      refuse("row_has_no_source_path", "an exec_leg row with no `path` has no project-relative source file", row.decl);
      continue;
    }
    if (!CENSUS_VERDICTS.includes(row.verdict)) {
      refuse("unknown_verdict_word", `verdict ${JSON.stringify(row.verdict)} is outside the census's own vocabulary`, row.decl);
      continue;
    }
    seeds.push({ waddle, file: row.path, fqn: row.decl, line: 0 });
    rowByIndex.push(row);
  }
  if (seeds.length === 0) {
    throw new Error("refusing to build an empty certificate graph: no exec_leg row survived the mount gates");
  }
  const { ids, normalizedFiles, lineFallbacks } = planNodeIds(seeds);
  const idByFqn = new Map();
  seeds.forEach((seed, index) => idByFqn.set(seed.fqn, ids[index]));

  const axiomsOf = (row) => (Array.isArray(row.axioms) ? [...row.axioms].sort() : []);
  const isSorry = (row) => row.verdict === "UNSOUND" || axiomsOf(row).includes("sorryAx");

  const nodes = seeds.map((seed, index) => {
    const row = rowByIndex[index];
    const axioms = axiomsOf(row);
    return {
      fqn: seed.fqn,
      // The census reports no Lean declaration kind. `"certificate"` is outside
      // the eight the harvest publishes, so it takes both documented floors
      // (layout → "def", tier → definition) and is never painted as a theorem.
      kind: CERTIFICATE_NODE_KIND,
      file: normalizedFiles[index],
      line: 0,
      type: "",
      statement: null,
      summary: `CFSG certificate probe: ${row.verdict} (${axioms.length === 0 ? "no axioms" : axioms.join(", ")})`,
      docstring: null,
      deps: [],
      axiomsUsed: axioms,
      sorry: isSorry(row),
      // The census carries a git BLOB sha1, which is not a sha256 and must not be
      // relabelled as one. This field is the sha256 of the census row's own
      // canonical JSON — a digest of the receipt record, computed here.
      sha256: sha256(canonicalJson(row)),
      id: ids[index],
      waddle,
      // Overwritten below by foundational PageRank over the mounted edges.
      importance: 0,
      // The published node carries a second centrality, `influence`
      // ("most downstream reach", packages/graph-engine/src/pagerank.ts:20). This
      // bridge does not port it and does not fake it as 0 — the field is simply
      // absent, and `certification.notPorted` names it. Nothing in the Hub's read
      // path asks for it: `apps/hub/lib/proof-artifacts-cache.ts` `RawDecl` does
      // not declare it, and `grep -rn influence apps/hub/lib apps/hub/app/api/proofs`
      // returns no consumer.
      // Carried so the identity of the evidence is never lost on the way in.
      certificate: {
        schema: census.schema ?? CENSUS_SCHEMA,
        verdict: row.verdict,
        rc: row.rc,
        blob_sha1: typeof row.blob === "string" ? row.blob : null,
        wall_s: typeof row.wall_s === "number" ? row.wall_s : null,
        commit: census?.denominators?.commit ?? null,
      },
    };
  });

  // ── edges: only cited, in-corpus declaration references ───────────────────
  const edges = [];
  const outgoing = new Map(nodes.map((n) => [n.fqn, []]));
  for (const ref of ledger) {
    const fromId = idByFqn.get(ref?.from);
    const toId = idByFqn.get(ref?.to);
    if (!fromId || !toId) {
      refuse(
        "target_outside_corpus",
        "the Hub records no node for a constant outside the harvested corpora, so a reference to one is not an edge; see scripts/proof-graph/generate.mts writeMergeInputs",
        `${String(ref?.from)} -> ${String(ref?.to)}`,
      );
      continue;
    }
    if (!(Number.isInteger(ref.line) && ref.line > 0) || typeof ref.file !== "string" || !ref.file) {
      refuse("reference_needs_a_cite", "a ledger reference without a `file` and a positive `line` is testimony, not evidence", `${ref.from} -> ${ref.to}`);
      continue;
    }
    const kind = normalizeEdgeKind(ref.kind ?? "uses");
    if (!LAYOUT_EDGE_KINDS.includes(kind)) {
      refuse(
        "edge_kind_not_positionable",
        `the Hub's layout guard (tools/graph-layout/src/index.ts:165) throws on kind ${JSON.stringify(kind)} even though the producer type allows it; refused here rather than mislabelled as "uses"`,
        `${ref.from} -> ${ref.to}`,
      );
      continue;
    }
    edges.push({
      from: fromId,
      to: toId,
      kind,
      resolution: "resolved",
      rawFrom: ref.from,
      rawTo: ref.to,
      sourceWaddle: waddle,
      targetWaddle: waddle,
      // `evidence` is deliberately empty: the producer's three words ("corpus",
      // "deps", "import") all mean compiler-reported structure, and a hand-cited
      // source ledger is none of them. The cite rides in resolutionReason.
      resolutionReason: `certificate ledger cite ${ref.file}:${ref.line}${ref.note ? ` (${ref.note})` : ""}`,
      evidence: [],
    });
    outgoing.get(ref.from).push(ref.to);
  }
  for (const node of nodes) node.deps = outgoing.get(node.fqn) ?? [];

  // ── ranks + layout, then the payload the Hub's own gates demand ───────────
  const ranks = computeFoundationalPageRank(nodes, edges);
  for (const node of nodes) node.importance = ranks.get(node.id) ?? 0;

  const size = options.size ?? 1000;
  const { positions } = layoutHierarchical(nodes, edges, { size });
  const positionRecord = {};
  for (const p of positions) positionRecord[p.id] = { x: p.x, y: p.y };
  const pagerankRecord = {};
  for (const node of nodes) pagerankRecord[node.id] = ranks.get(node.id) ?? 0;

  const generatedAt = options.generatedAt ?? census.generated_at ?? null;
  const graph = {
    nodes,
    edges,
    waddles: [waddle],
    generatedAt,
    kernelVerified: false,
    evidenceClass: "structural-source-only",
    totals: {
      decls: nodes.length,
      byWaddle: { [waddle]: { decls: nodes.length } },
    },
    integrity: {
      identity: {
        scheme: "waddle+file+fqn;line-on-collision",
        uniqueNodeIds: true,
        // Counted at fqn level here: a repeated FQN across different files is
        // legal in the Hub's law (the file is in the identity) and is exactly the
        // case the published graph reports — `proofs-graph.meta.json →
        // integrity.identity.duplicateFqns: 8` with `lineFallbacks: 0`. This
        // bridge's lineFallbacks is 0 by construction, because a census row
        // carries no line: a duplicate identity here cannot be repaired and
        // therefore throws rather than reporting a fallback count.
        duplicateFqns: countDuplicates(nodes.map((node) => node.fqn)),
        lineFallbacks,
      },
      dependencies: {
        total: edges.length,
        resolved: edges.filter((e) => e.resolution === "resolved").length,
        unresolved: 0,
        ambiguous: 0,
        // The Hub's four legs are all zero, because none of these edges came from
        // its corpus harvest or its deps files: every edge here is a cited
        // certificate-ledger reference. Reporting `corpusEdges: edges.length`
        // would claim a harvest that never happened.
        corpusEdges: 0,
        depsFileEdges: 0,
        depsOnlyEdges: 0,
        corpusEdgesMissingDepsEvidence: 0,
        ledgerCitedEdges: edges.length,
      },
      imports: 0,
      metadataMismatches: [],
      checks: { resolvedEdgeEndpointsExist: true, totalsMatchNodes: true },
    },
    certification: {
      schema: census.schema ?? CENSUS_SCHEMA,
      sourceArtifactSha256: options.sourceArtifactSha256 ?? null,
      root: census.root ?? null,
      commit: census?.denominators?.commit ?? null,
      lane: census.lane ?? null,
      tierLaw: census.tier_law ?? null,
      notClaiming:
        (census.tier_law ?? "") +
        " A certificate row is one executed probe over one declaration at one commit; " +
        "the Hub re-runs nothing, and no node on this surface is a closure certificate.",
      rowsSeen: rows.length,
      rowsMounted: nodes.length,
      rowsRefused: refusals.length,
      censusTally: census.census_tally ?? null,
      censusControls: census.controls?.rows?.length ?? null,
      // Named absences, so a reader never mistakes "the bridge did not produce it"
      // for "the estate reports zero of it".
      notPorted: [
        "influence (the Hub's second centrality)",
        "declaration `type` and `statement` text (a census row is an axiom probe, not a syntactic harvest)",
        "imports edges (the census reports no module imports; see refusals)",
      ],
      typedAbsences: census.typed_absences ?? null,
    },
  };

  const layout = {
    version: 2,
    // THE ALGORITHM IS NOT THE HUB'S. The published `proofs-layout.json` is
    // produced by `tools/graph-layout/src/index.ts:178-182`, which calls
    // `computeLayout(..., { mode: "force", seed: 0xa1b2c3, iterations: 320 })` —
    // force-directed, and dependent on d3-force. The consistency gate in
    // `proof-artifacts-cache.ts` checks key coverage and counts, never the
    // algorithm or a coordinate, so a hierarchical layout is schema-legal here;
    // but these positions are NOT what the hub would draw for the same graph, and
    // no claim of visual parity is made. Hierarchical is chosen because it is
    // dependency-free, deterministic (no seeded RNG), and layer = longest
    // dependency path, which is the relation a certificate cone actually has.
    algorithm: "hierarchical-longest-path",
    algorithmDivergence:
      "the hub's published layout is mode:force with seed 0xa1b2c3 (graph-layout/src/index.ts:178-182); positions differ, the schema does not",
    computedAt: generatedAt,
    graphGeneratedAt: generatedAt,
    sourceGraphSha256: null, // filled by serializeCertificateGraph, over the emitted bytes
    nodeCount: nodes.length,
    resolvedEdgeCount: edges.filter((e) => e.resolution === "resolved").length,
    size,
    positions: positionRecord,
    pagerank: pagerankRecord,
    checks: { positionKeysMatchNodeIds: true, pagerankKeysMatchNodeIds: true },
  };

  return { graph, layout, refusals };
}

/**
 * The preconditions `tools/graph-layout/src/index.ts:124-137` enforces before it
 * will position a graph, run over an object this bridge just built. It is the
 * mount's own acceptance test in public form: anything that would make the Hub
 * refuse is named here instead of discovered at deploy time.
 */
export function assertHubMountable(graph, layout) {
  if (!Array.isArray(graph.nodes) || graph.nodes.length === 0) throw new Error("refusing to lay out an empty proof graph");
  if (!Array.isArray(graph.edges)) throw new Error("proof graph has no edge array");
  if (
    graph.integrity?.identity?.uniqueNodeIds !== true ||
    graph.integrity?.checks?.resolvedEdgeEndpointsExist !== true ||
    graph.integrity?.checks?.totalsMatchNodes !== true
  ) {
    throw new Error("proof graph is missing successful merge-integrity checks");
  }
  if (graph.totals?.decls !== graph.nodes.length) throw new Error("proof graph declaration total does not match node count");
  const ids = graph.nodes.map((n) => n.id);
  if (new Set(ids).size !== ids.length) throw new Error("proof graph contains duplicate node IDs");
  const known = new Set(ids);
  for (const node of graph.nodes) {
    if (typeof node.waddle !== "string" || !node.waddle) throw new Error(`proof graph node ${node.id} has no waddle`);
  }
  for (const [index, edge] of graph.edges.entries()) {
    if (edge.resolution !== "resolved") continue;
    if (!known.has(edge.from) || !known.has(edge.to)) throw new Error(`resolved edge ${index} references a missing node ID`);
    if (!edge.kind || !LAYOUT_EDGE_KINDS.includes(edge.kind)) {
      throw new Error(`resolved edge ${index} has unsupported kind ${String(edge.kind)}`);
    }
  }
  const sameKeys = (record) => {
    const a = Object.keys(record).sort();
    const b = [...ids].sort();
    return a.length === b.length && a.every((k, i) => k === b[i]);
  };
  if (!sameKeys(layout.positions)) throw new Error("layout position keys do not exactly match graph node IDs");
  if (!sameKeys(layout.pagerank)) throw new Error("layout PageRank keys do not exactly match graph node IDs");
  return true;
}

/**
 * The completion-receipt contract constants, transcribed with their source so a
 * reader can check them against the repo that owns them. They are literals here
 * on purpose: this module is dependency-free and cross-repo, and a live import of
 * `scripts/proof-graph/receipt-contract.ts` would make an art-repo test depend on
 * a waddle checkout existing on the host.
 *
 * - `RECEIPT_SCHEMA_VERSION = 3` — `awkronos-waddle/scripts/proof-graph/receipt-contract.ts:33`.
 *   The hub gate demands EXACT equality: a `>=`, a range, or an allow-list would
 *   re-admit the pre-restoration v2 receipt that the 2026-10-22 bump (1ce779be)
 *   exists to refuse by name (`apps/hub/lib/proof-artifacts-cache.ts:204-208` and
 *   the comment at `:196-203`, which records the real incident: the hub carried a
 *   second literal `2`, the generator moved to v3, and the hub agent path threw on
 *   every new receipt at RUNTIME with no test pinning it).
 * - `EVIDENCE_STATUS = "structural-source-only"` — same module, `:44`.
 */
export const RECEIPT_SCHEMA_VERSION = 3;
export const EVIDENCE_STATUS = "structural-source-only";

/**
 * Build the third leg the Hub's read requires. `readConsistentProofArtifacts`
 * (`apps/hub/lib/proof-artifacts-cache.ts:302-331`) reads receipt + graph + layout
 * and digests all three; every one of its 12 refusal legs is reproduced here in
 * `assertHubReceiptConsistent` so the bridge is judged against the gate its target
 * actually runs, not against a weaker local copy.
 */
export function buildCompletionReceipt(graph, layout, { graphSha256, layoutSha256, receiptProducer }) {
  return {
    schemaVersion: RECEIPT_SCHEMA_VERSION,
    status: EVIDENCE_STATUS,
    kernelVerified: false,
    generatedAt: graph.generatedAt,
    repositoryCommit: graph.certification.commit,
    producer: receiptProducer ?? {
      name: "cfsg-proof-graph-bridge",
      producerFiles: ["patent-portfolio/lib/cfsg-proof-graph-bridge.mjs"],
    },
    payloads: {
      "proofs-graph.json": graphSha256,
      "proofs-layout.json": layoutSha256,
    },
    graph: { nodes: graph.nodes.length, edges: graph.edges.length, sha256: graphSha256 },
    layout: {
      nodes: graph.nodes.length,
      resolvedEdges: graph.edges.filter((e) => e.resolution === "resolved").length,
      sourceGraphSha256: graphSha256,
      sha256: layoutSha256,
    },
  };
}

/**
 * The Hub's own consistency gate, ported from
 * `apps/hub/lib/proof-artifacts-cache.ts:184-300` (the 12 `throw` legs of
 * `validateArtifacts`). Names are kept faithful to the source so a divergent
 * message here is greppable against the file it came from.
 */
export function assertHubReceiptConsistent(receipt, graph, layout, { graphSha256, layoutSha256 }) {
  if (receipt.schemaVersion !== RECEIPT_SCHEMA_VERSION) {
    throw new Error(`proof graph receipt has an unsupported evidence contract: schemaVersion ${JSON.stringify(receipt.schemaVersion)} != ${RECEIPT_SCHEMA_VERSION}`);
  }
  if (receipt.status !== EVIDENCE_STATUS) {
    throw new Error(`proof graph receipt has an unsupported evidence contract: status ${JSON.stringify(receipt.status)} != ${JSON.stringify(EVIDENCE_STATUS)}`);
  }
  if (receipt.kernelVerified !== false) {
    throw new Error(`proof graph receipt has an unsupported evidence contract: kernelVerified ${JSON.stringify(receipt.kernelVerified)} != false`);
  }
  if (graph.kernelVerified !== false || graph.evidenceClass !== EVIDENCE_STATUS) {
    throw new Error("proof graph payload has an unsupported evidence contract");
  }
  if (receipt.graph?.sha256 !== graphSha256) throw new Error("proof graph hash does not match its completion receipt");
  if (receipt.layout?.sha256 !== layoutSha256) throw new Error("proof layout hash does not match its completion receipt");
  if (
    receipt.payloads?.["proofs-graph.json"] !== graphSha256 ||
    receipt.payloads?.["proofs-layout.json"] !== layoutSha256
  ) {
    throw new Error("proof payload hashes do not match the completion receipt");
  }
  if (layout.sourceGraphSha256 !== graphSha256 || receipt.layout.sourceGraphSha256 !== graphSha256) {
    throw new Error("proof layout was not derived from the completed graph");
  }
  const nodeIds = graph.nodes.map((node) => node.id);
  if (
    nodeIds.some((id) => typeof id !== "string" || id.length === 0) ||
    new Set(nodeIds).size !== nodeIds.length
  ) {
    throw new Error("proof graph nodes do not have unique stable IDs");
  }
  const nodes = graph.nodes.length;
  const edges = graph.edges.length;
  if (
    nodes === 0 ||
    receipt.graph.nodes !== nodes ||
    receipt.graph.edges !== edges ||
    receipt.layout.nodes !== nodes ||
    layout.nodeCount !== nodes
  ) {
    throw new Error("proof artifact counts do not match the completion receipt");
  }
  const resolvedEdges = graph.edges.filter((edge) => edge.resolution === "resolved").length;
  if (receipt.layout.resolvedEdges !== resolvedEdges || layout.resolvedEdgeCount !== resolvedEdges) {
    throw new Error("proof layout resolved-edge count does not match the completed graph");
  }
  if (
    receipt.generatedAt !== graph.generatedAt ||
    layout.computedAt !== graph.generatedAt ||
    layout.graphGeneratedAt !== graph.generatedAt
  ) {
    throw new Error("proof artifact generation timestamps do not agree");
  }
  if (layout.checks?.positionKeysMatchNodeIds !== true || layout.checks?.pagerankKeysMatchNodeIds !== true) {
    throw new Error("proof layout integrity checks are not affirmative");
  }
  const expectedIds = [...nodeIds].sort();
  if (JSON.stringify(Object.keys(layout.positions ?? {}).sort()) !== JSON.stringify(expectedIds)) {
    throw new Error("proof layout does not cover exactly the completed graph node IDs");
  }
  if (JSON.stringify(Object.keys(layout.pagerank ?? {}).sort()) !== JSON.stringify(expectedIds)) {
    throw new Error("proof layout does not cover exactly the completed graph node IDs");
  }
  return true;
}

/** Serialize the triple the way the Hub publishes it, and digest the graph bytes. */
export function serializeCertificateGraph(graph, layout, options = {}) {
  const graphText = JSON.stringify(graph);
  const graphSha256 = sha256(graphText);
  const layoutWithDigest = { ...layout, sourceGraphSha256: graphSha256 };
  const layoutText = JSON.stringify(layoutWithDigest);
  const receipt = buildCompletionReceipt(graph, layoutWithDigest, {
    graphSha256,
    layoutSha256: sha256(layoutText),
    receiptProducer: options.producer,
  });
  return { graphText, layoutText, receipt, graphSha256, layoutSha256: sha256(layoutText) };
}
