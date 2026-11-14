/**
 * patent-portfolio/lib/cfsg-proof-graph-bridge.mjs — the certificate→proof-graph
 * mount gate.
 *
 * THE PROPERTY UNDER TEST is that a CFSG certificate census can be mounted into
 * the Hub's declaration-graph schema WITHOUT weakening either side's evidence
 * claim. That splits into three falsifiable obligations, and each one is what a
 * real integration would silently break:
 *
 *   1. IDENTITY. The mounted node ids must be produced by the Hub's own identity
 *      law, not a lookalike. Pinned by recomputing an id that is published, byte
 *      for byte, in `awkronos-waddle/apps/hub/data/proofs-graph.json`.
 *   2. EVIDENCE. Nothing may turn a source-lexical census row into a kernel
 *      claim: `kernelVerified` stays false, a row whose probe exited non-zero is
 *      refused rather than mounted, a relation to something outside the corpus is
 *      refused rather than invented, and an edge kind the layout cannot position
 *      is refused rather than relabelled.
 *   3. CONSUMABILITY. The triple (receipt, graph, layout) must pass every refusal
 *      leg of the two gates the Hub's own read runs — `assertHubReceiptConsistent`
 *      (15 throw sites) and `assertHubMountable` (10) — with a negative control
 *      that proves each leg FIRES. A green gate with no negative control is not a
 *      verified gate; it is an unexercised branch. (This is the exact class of
 *      hole recorded in `apps/hub/lib/proof-artifacts-cache.ts:196-203`: the hub
 *      carried its own literal `schemaVersion !== 2`, the generator bumped to v3,
 *      and no test pinned the copy, so the break surfaced only at runtime.) The
 *      leg list is not kept by hand: `refusalLegs()` counts it out of the bridge
 *      source at test time, so a guard added without a control fails the suite.
 *   4. DRIFT. The port claims fidelity to files that live in another repo. Those
 *      claims were prose: measured 2026-11-14, the five upstream digests appear
 *      ONLY in comment lines and no code recomputed them, so the header's
 *      "drift is detectable, not silent" described an intention rather than a
 *      mechanism. `UPSTREAM_PINS` now carries them as data and the last three
 *      legs below re-derive them, the published node id, the edge/declaration
 *      vocabularies, the `def` floor and the live artifact mount from the real
 *      tree whenever it is on the host — skipping by name when it is not.
 *
 * The census fixture below reproduces, byte for byte, every field of
 * `~/.kagami/solver-certs/GR-FULLSEND-1027-CFSG-AXIOM-CENSUS.json` (sha256
 * 68f0a35d44fbb136713c1adafd8f08c74c12dd6a742e3d815884ab916a27a6e8) that it
 * carries — including all 13 `exec_leg.sample` rows — and drops the fields the
 * mount does not read (the `denominators` census arithmetic, `blob_census`,
 * `hits`, `cone_receipt`, `wall_s`, and the null `output_head`/`reason` keys on
 * the control rows). It is a projection, not a dump. It is inlined rather than
 * read at test time so the suite stays offline and host-independent — the
 * artifact lives on the MacBook, not on the host that runs this suite — exactly
 * like `tests/unit/corpus-stats.test.mjs` keeps its inputs in-process.
 */
import assert from "node:assert/strict";
import { createHash } from "node:crypto";
import { existsSync, readFileSync } from "node:fs";
import test from "node:test";

import {
  CENSUS_SCHEMA,
  CENSUS_VERDICTS,
  CERTIFICATE_NODE_KIND,
  LAYOUT_EDGE_KINDS,
  PRODUCER_EDGE_KINDS,
  RECEIPT_SCHEMA_VERSION,
  EVIDENCE_STATUS,
  UPSTREAM_PINS,
  assertHubMountable,
  assertHubReceiptConsistent,
  buildCertificateGraph,
  buildCompletionReceipt,
  computeFoundationalPageRank,
  encodeIdentityComponent,
  layoutHierarchical,
  nodeIdentityBase,
  normalizeEdgeKind,
  normalizeSourceFile,
  planNodeIds,
  serializeCertificateGraph,
} from "../../patent-portfolio/lib/cfsg-proof-graph-bridge.mjs";

/** All 13 of the artifact's `exec_leg.sample` rows, verbatim. The collision test
 *  appends a 14th row of its own — a duplicate of row 1's identity — which is not
 *  in the artifact. */
const MEMBERS = {
  axioms: ["propext", "Quot.sound"],
  blob: "574ce88589a14c14a93cf33759802dfc36228795",
  decl: "CFSG.CGT.PushingUpLit.A78.LQ4Fin.mem_members",
  name_attempts: [{ name: "CFSG.CGT.PushingUpLit.A78.LQ4Fin.mem_members", reason: null, verdict: "CORE_THREE" }],
  path: "CFSG/CGT/PushingUpLit/A78/LQ4Fin.lean",
  rc: 0,
  verdict: "CORE_THREE",
  wall_s: 44.61,
};
const INVARIANT_B_IFF = {
  axioms: ["propext", "Quot.sound"],
  blob: "574ce88589a14c14a93cf33759802dfc36228795",
  decl: "CFSG.CGT.PushingUpLit.A78.LQ4Fin.invariantB_iff",
  name_attempts: [{ name: "CFSG.CGT.PushingUpLit.A78.LQ4Fin.invariantB_iff", reason: null, verdict: "CORE_THREE" }],
  path: "CFSG/CGT/PushingUpLit/A78/LQ4Fin.lean",
  rc: 0,
  verdict: "CORE_THREE",
  wall_s: 32.2,
};
const FORALL_OF_BLOCKS = {
  axioms: ["propext", "Classical.choice", "Quot.sound"],
  blob: "ca6fafb631458bce0c838356aa70a398c9ccc679",
  decl: "CFSG.KC.ForallBlocks.forall_of_blocks",
  name_attempts: [{ name: "CFSG.KC.ForallBlocks.forall_of_blocks", reason: null, verdict: "CORE_THREE" }],
  path: "CFSG/Certificates/Kernel/Common/ForallBlocks.lean",
  rc: 0,
  verdict: "CORE_THREE",
  wall_s: 0.6,
};
const TAB = {
  axioms: [],
  blob: "2b2a86449986997832f98382c3b62bedaa158549",
  decl: "CFSG.KTabPack.Tab",
  name_attempts: [{ name: "CFSG.KTabPack.Tab", reason: null, verdict: "AXIOM_FREE" }],
  path: "CFSG/Certificates/Kernel/TabPackSound.lean",
  rc: 0,
  verdict: "AXIOM_FREE",
  wall_s: 0.84,
};
const ALL_R_EQ = { ...TAB, decl: "CFSG.KTabPack.allR_eq", wall_s: 0.77, name_attempts: [{ name: "CFSG.KTabPack.allR_eq", reason: null, verdict: "AXIOM_FREE" }] };
const OF_CODE_CODE = {
  axioms: ["propext", "Classical.choice", "Quot.sound"],
  blob: "85494b2e202197c0af239404546866d9c62d6aad",
  decl: "CFSG.ClassicalInvolution.PhanDn.QTwoGammaThree.ofCode_code",
  name_attempts: [{ name: "CFSG.ClassicalInvolution.PhanDn.QTwoGammaThree.ofCode_code", reason: null, verdict: "CORE_THREE" }],
  path: "CFSG/ClassicalInvolution/Phan/PhanDn/QTwoGammaThreeCheck.lean",
  rc: 0,
  verdict: "CORE_THREE",
  wall_s: 36.83,
};
const PTS_CHECK = { ...OF_CODE_CODE, decl: "CFSG.ClassicalInvolution.PhanDn.QTwoGammaThree.ptsCheck_eq_true", wall_s: 65.37, name_attempts: [{ name: "CFSG.ClassicalInvolution.PhanDn.QTwoGammaThree.ptsCheck_eq_true", reason: null, verdict: "CORE_THREE" }] };
const CERT_6P = {
  axioms: ["propext"],
  blob: "26df0d765b1e8c19fc1524e59587fc29f1569e96",
  decl: "CFSG.GF2Type.Smith1980Orth.TwoRankSmall.cert6p",
  name_attempts: [{ name: "CFSG.GF2Type.Smith1980Orth.TwoRankSmall.cert6p", reason: null, verdict: "CORE_THREE" }],
  path: "CFSG/GF2Type/Smith1980Orth/TwoRankSmallData.lean",
  rc: 0,
  verdict: "CORE_THREE",
  wall_s: 62.48,
};
const CERT_6M = { ...CERT_6P, decl: "CFSG.GF2Type.Smith1980Orth.TwoRankSmall.cert6m", wall_s: 78.46, name_attempts: [{ name: "CFSG.GF2Type.Smith1980Orth.TwoRankSmall.cert6m", reason: null, verdict: "CORE_THREE" }] };
// The two rows that carry a verdict AND a non-zero exit code — see the
// probe_rc_nonzero gate. Verbatim from the artifact.
const N_LINES = {
  axioms: [],
  blob: "ba56f8e83aaeb93b80b22762ef05d0be9cce22d6",
  decl: "CFSG.EvenSporadicStandard.G24Model.nLines",
  name_attempts: [{ name: "CFSG.EvenSporadicStandard.G24Model.nLines", reason: null, verdict: "AXIOM_FREE" }],
  path: "CFSG/LocalAnalysis/EvenSporadicStandard/Induction/Rows/G24ModelBase.lean",
  rc: 1,
  verdict: "AXIOM_FREE",
  wall_s: 1.31,
};
const WORD_OFFSET = { ...N_LINES, decl: "CFSG.EvenSporadicStandard.G24Model.wordOffset", wall_s: 0.82, name_attempts: [{ name: "CFSG.EvenSporadicStandard.G24Model.wordOffset", reason: null, verdict: "AXIOM_FREE" }] };
const WORDS_OF = {
  axioms: ["propext"],
  blob: "9f410aefd4e969917b0fbd75bd10c7b69da56ac2",
  decl: "CFSG.EvenSporadicStandard.M12Std.SolomonK.P12.wordsOf",
  name_attempts: [{ name: "CFSG.EvenSporadicStandard.M12Std.SolomonK.P12.wordsOf", reason: null, verdict: "CORE_THREE" }],
  path: "CFSG/LocalAnalysis/EvenSporadicStandard/M12Std/SolomonK/P12Check.lean",
  rc: 0,
  verdict: "CORE_THREE",
  wall_s: 0.8,
};
const CHAIN_DATA = {
  axioms: [],
  blob: "191ac0a1a29f14112d4e850db613cba5a59a2e32",
  decl: "CFSG.EvenSporadicStandard.M12Std.Yosh.ChainData",
  name_attempts: [{ name: "CFSG.EvenSporadicStandard.M12Std.Yosh.ChainData", reason: null, verdict: "AXIOM_FREE" }],
  path: "CFSG/LocalAnalysis/EvenSporadicStandard/M12Std/YoshFusionData.lean",
  rc: 0,
  verdict: "AXIOM_FREE",
  wall_s: 1.66,
};

const CENSUS = {
  schema: CENSUS_SCHEMA,
  lane: "REACTOR-FORGE-2",
  root: "/Users/schizodactyl/projects/cfsg",
  generated_at: "2026-10-28T02:40:42Z",
  tier_law:
    "all rows are source_level/executed_probe about individual declarations; no CFSG statement is machine-checked by this artifact (PC-8: no build receipt)",
  denominators: { commit: "73992122403dbc448c670303cdb66827dca0d597", lean_distinct_blobs: 229002 },
  census_tally: { AXIOM_FREE: 5, CORE_THREE: 8 },
  verdict_words: {
    note: '"does not depend on any axioms" is the PASSING answer; it is not a violation',
    row_verdicts: ["AXIOM_FREE", "CORE_THREE", "DEPENDENT", "UNSOUND", "PROBE_FAILED", "ABSENT"],
    success_line: "does not depend on any axioms",
  },
  controls: {
    holds: true,
    rows: [
      { control: "census_control_rfl", expected: ["AXIOM_FREE"], holds: true, verdict: "AXIOM_FREE", axioms: [] },
      { control: "census_control_sorry", expected: ["UNSOUND"], holds: true, verdict: "UNSOUND", axioms: ["sorryAx"] },
      { control: "census_control_choice", expected: ["CORE_THREE"], holds: true, verdict: "CORE_THREE", axioms: ["propext", "Classical.choice", "Quot.sound"] },
      { control: "unknown_decl_is_loud", expected: ["PROBE_FAILED"], holds: true, verdict: "PROBE_FAILED" },
    ],
  },
  exec_leg: {
    subjects_probed: 8,
    silent_rows: [],
    sample: [
      MEMBERS, INVARIANT_B_IFF, FORALL_OF_BLOCKS, TAB, ALL_R_EQ, OF_CODE_CODE, PTS_CHECK,
      CERT_6P, CERT_6M, N_LINES, WORD_OFFSET, WORDS_OF, CHAIN_DATA,
    ],
  },
};

/** The one declaration-to-declaration reference in the recorded sample that is
 *  real and checkable: `invariantB_iff`'s proof script names `mem_members`.
 *  Verified against the pinned commit, not the working tree —
 *  `git show 73992122403dbc448c670303cdb66827dca0d597:CFSG/CGT/PushingUpLit/A78/LQ4Fin.lean`
 *  line 79 reads `  simp [invariantB, List.all_eq_true, mem_members]`. */
const LEDGER = [
  {
    from: INVARIANT_B_IFF.decl,
    to: MEMBERS.decl,
    file: MEMBERS.path,
    line: 79,
    note: "simp list names mem_members",
  },
];

const mounted = () => buildCertificateGraph(CENSUS, { ledger: LEDGER });

test("identity law: the port reproduces a PUBLISHED hub node id byte for byte", () => {
  // apps/hub/data/proofs-graph.json node[0], read 2026-11-02:
  //   id   "audrey::Audrey_2fCollision_2fMomentum.lean::Audrey.Collision.BinaryCollision"
  //   fqn  "Audrey.Collision.BinaryCollision"
  //   file "Audrey/Collision/Momentum.lean"
  // The published id encodes the file's `/` as `_2f` and leaves the FQN's dots
  // alone — which is only reproducible if the per-character rule is the Hub's.
  assert.equal(
    nodeIdentityBase({
      waddle: "audrey",
      file: "Audrey/Collision/Momentum.lean",
      fqn: "Audrey.Collision.BinaryCollision",
    }),
    "audrey::Audrey_2fCollision_2fMomentum.lean::Audrey.Collision.BinaryCollision",
  );
  assert.equal(encodeIdentityComponent("Audrey/Collision/Momentum.lean"), "Audrey_2fCollision_2fMomentum.lean");
  // Invertibility, which is why `/` cannot be the only escaped character: a
  // literal `_5f` and an encoded `_` must not collide, or two different
  // declarations would mint one node id.
  assert.notEqual(encodeIdentityComponent("_"), encodeIdentityComponent("_5f"));
  assert.equal(encodeIdentityComponent("_"), "_5f");
  assert.notEqual(encodeIdentityComponent("a/b"), encodeIdentityComponent("a_b"));
  // Multi-byte: the law is per UTF-8 BYTE, so one non-ASCII char costs three
  // escapes. A per-char hex would silently produce ids the hub cannot reproduce.
  assert.equal(encodeIdentityComponent("é"), "_c3_a9");
});

test("mount: 13 census rows become 11 nodes and 2 named refusals", () => {
  const { graph, refusals } = mounted();
  assert.equal(graph.nodes.length, 11);
  assert.equal(CENSUS.exec_leg.sample.length, 13);
  assert.equal(refusals.length, 2);
  // The refusal is the point: these two rows carry `verdict: "AXIOM_FREE"`
  // ALONGSIDE `rc: 1`. A consumer that joined on verdict alone would mount two
  // claims the executor itself did not accept.
  assert.deepEqual(
    refusals.map((r) => [r.code, r.subject]).sort(),
    [
      ["probe_rc_nonzero", "CFSG.EvenSporadicStandard.G24Model.nLines"],
      ["probe_rc_nonzero", "CFSG.EvenSporadicStandard.G24Model.wordOffset"],
    ].sort(),
  );
  assert.equal(graph.certification.rowsSeen, 13);
  assert.equal(graph.certification.rowsMounted, 11);
  assert.equal(graph.totals.decls, graph.nodes.length);
  assert.deepEqual(graph.waddles, ["cfsg"]);
  assert.equal(graph.generatedAt, CENSUS.generated_at);
  // Evidence floor: the hub gate refuses a graph that promotes itself.
  assert.equal(graph.kernelVerified, false);
  assert.equal(graph.evidenceClass, EVIDENCE_STATUS);
  assert.match(graph.certification.notClaiming, /no CFSG statement is machine-checked/);
});

test("node shape: every field a DeclRecord must carry, and no invented ones", () => {
  const { graph } = mounted();
  // The published node key set, from the same file (nodes[0] keys):
  const published = ["fqn", "kind", "file", "line", "type", "summary", "docstring", "deps", "axiomsUsed", "sorry", "sha256", "id", "waddle", "importance", "influence"];
  for (const node of graph.nodes) {
    for (const key of published) {
      // `influence` is the ONE field this bridge does not port; it is named in
      // certification.notPorted rather than faked with a 0.
      if (key === "influence") {
        assert.equal(node.influence, undefined, `${node.fqn} must not carry a fabricated influence score`);
        continue;
      }
      assert.ok(key in node, `${node.fqn} is missing published DeclRecord field ${key}`);
    }
    assert.equal(typeof node.id, "string");
    assert.equal(node.waddle, "cfsg");
    assert.equal(node.line, 0);
    assert.match(node.sha256, /^[0-9a-f]{64}$/);
    // The census reports a git BLOB sha1. Relabelling it as the node's `sha256`
    // is the single most tempting lie on this surface, so it is pinned against.
    assert.notEqual(node.sha256, node.certificate.blob_sha1);
    assert.equal(node.certificate.blob_sha1.length, 40);
    assert.equal(node.certificate.commit, CENSUS.denominators.commit);
    assert.ok(Array.isArray(node.axiomsUsed));
    assert.deepEqual(node.axiomsUsed, [...node.axiomsUsed].sort());
    assert.equal(typeof node.importance, "number");
    // A census row has no Lean declaration kind. The floor is a definition, never
    // a theorem — proofs-atlas.ts:228-242 documents exactly this behaviour for an
    // unrecognised kind, and layout.ts:68-89 renders it as "def".
    assert.equal(node.kind, CERTIFICATE_NODE_KIND);
    assert.doesNotMatch(node.summary, /verified|proved|kernel/i);
  }
  assert.ok(graph.certification.notPorted.some((s) => s.startsWith("influence")));
});

test("sorry floor: an executed UNSOUND/sorryAx row is sorry, the recorded 11 are not", () => {
  const { graph } = mounted();
  // Measured, not assumed: all 13 recorded sample rows are AXIOM_FREE or
  // CORE_THREE, and the published hub graph likewise reports `sorry count 0`.
  assert.equal(graph.nodes.filter((n) => n.sorry).length, 0);
  // Positive control, derived from the artifact's OWN control row
  // `census_control_sorry` (controls.rows[1]): axioms ["sorryAx"], verdict
  // "UNSOUND", holds true. Same shape as a sample row, so the mount accepts it —
  // and the sorry flag must light up, or the graph would render a hole as a theorem.
  const withHole = structuredClone(CENSUS);
  withHole.exec_leg.sample.push({
    axioms: ["sorryAx"],
    blob: null,
    decl: "CFSG.Control.sorryHole",
    name_attempts: [],
    path: "CFSG/Control/Scaffold.lean",
    rc: 0,
    verdict: "UNSOUND",
    wall_s: 0.69,
  });
  const second = buildCertificateGraph(withHole, { ledger: LEDGER });
  const hole = second.graph.nodes.find((n) => n.fqn === "CFSG.Control.sorryHole");
  assert.equal(hole.sorry, true);
  assert.deepEqual(hole.axiomsUsed, ["sorryAx"]);
  assert.equal(second.refusals.length, 2); // no new refusal: it mounts, flagged
});

test("edges: only a cited, in-corpus reference becomes an edge", () => {
  const { graph } = mounted();
  assert.equal(graph.edges.length, 1);
  const edge = graph.edges[0];
  assert.equal(edge.kind, "uses");
  assert.equal(edge.resolution, "resolved");
  const fromId = graph.nodes.find((n) => n.fqn === INVARIANT_B_IFF.decl).id;
  const toId = graph.nodes.find((n) => n.fqn === MEMBERS.decl).id;
  assert.equal(edge.from, fromId);
  assert.equal(edge.to, toId);
  assert.match(edge.resolutionReason, /LQ4Fin\.lean:79/);
  assert.equal(graph.nodes.find((n) => n.fqn === INVARIANT_B_IFF.decl).deps.length, 1);
  assert.equal(graph.integrity.dependencies.total, 1);
  assert.equal(graph.integrity.dependencies.resolved, 1);
  // The hub's four harvest legs stay zero: no corpus harvest happened here.
  assert.equal(graph.integrity.dependencies.corpusEdges, 0);
  assert.equal(graph.integrity.dependencies.ledgerCitedEdges, 1);
  for (const node of graph.nodes) {
    if (node.fqn === MEMBERS.decl) continue;
    assert.equal(node.sorry, false);
  }
});

test("refusals: an uncited ref, an out-of-corpus ref, and an unpositionable kind", () => {
  // The fixture legitimately contains two rc=1 rows; they are refused on every
  // build, so the baseline refusals are filtered out to isolate each leg.
  const refCodes = (ledger) =>
    buildCertificateGraph(CENSUS, { ledger })
      .refusals.filter((r) => r.code !== "probe_rc_nonzero")
      .map((r) => r.code);
  // Out of corpus: the Hub records no node for a constant outside its harvested
  // corpora, so this cannot be an edge (generate.mts writeMergeInputs is the
  // producer leg that decides it).
  assert.deepEqual(
    refCodes([{ from: FORALL_OF_BLOCKS.decl, to: "Nat.div_lt_of_lt_mul", file: "x.lean", line: 1 }]),
    ["target_outside_corpus"],
  );
  // No cite: testimony, not evidence.
  assert.deepEqual(
    refCodes([{ from: INVARIANT_B_IFF.decl, to: MEMBERS.decl, file: MEMBERS.path, line: 0 }]),
    ["reference_needs_a_cite"],
  );
  // `imports` is the measured vocabulary split: the PRODUCER type allows it and
  // emits it, the LAYOUT guard throws on it. Refusing by name is the honest leg;
  // silently mapping it to "uses" would misrepresent module structure as a use.
  assert.ok(PRODUCER_EDGE_KINDS.includes("imports"));
  assert.ok(!LAYOUT_EDGE_KINDS.includes("imports"));
  assert.deepEqual(
    refCodes([{ from: TAB.decl, to: ALL_R_EQ.decl, file: TAB.path, line: 12, kind: "imports" }]),
    ["edge_kind_not_positionable"],
  );
  // normalizeEdgeKind is the producer's floor (unknown -> uses) and is NOT used to
  // launder an imports edge: it passes imports through, where the layout guard
  // then refuses it.
  assert.equal(normalizeEdgeKind("imports"), "imports");
  assert.equal(normalizeEdgeKind("proves"), "proves");
  assert.equal(normalizeEdgeKind("nonsense"), "uses");
});

test("verdict vocabulary: an unknown word is refused, never defaulted", () => {
  assert.deepEqual([...CENSUS_VERDICTS], CENSUS.verdict_words.row_verdicts);
  const drifted = structuredClone(CENSUS);
  drifted.exec_leg.sample[3].verdict = "AXIOM_FREEISH";
  const { refusals } = buildCertificateGraph(drifted, { ledger: LEDGER });
  const codes = refusals.map((r) => r.code);
  assert.ok(codes.includes("unknown_verdict_word"), codes.join(","));
  assert.equal(refusals.filter((r) => r.code === "unknown_verdict_word").length, 1);
});

test("identity collision goes loud: two rows, same file and fqn, no line to split them", () => {
  const dup = structuredClone(CENSUS);
  dup.exec_leg.sample.push({ ...MEMBERS });
  assert.throws(
    () => buildCertificateGraph(dup, { ledger: LEDGER }),
    /non-unique declaration identity .*source line cannot disambiguate 0/,
  );
  // And a row that is merely a duplicate of another row's FILE is fine — the file
  // is not what makes an identity here; six of the 13 sample rows share files.
  const { graph } = mounted();
  assert.equal(graph.integrity.identity.duplicateFqns, 0);
  assert.equal(graph.integrity.identity.lineFallbacks, 0);
  const files = new Set(graph.nodes.map((n) => n.file));
  assert.ok(files.size < graph.nodes.length, "the fixture should contain several declarations per file");
});

test("a row with no decl name is refused rather than minted as an anonymous node", () => {
  const nameless = structuredClone(CENSUS);
  // The artifact's own controls.rows have exactly this shape: a verdict and an
  // axiom set, no declaration. They are evidence about the PROBE, not about a
  // declaration, and must not become nodes.
  nameless.exec_leg.sample.push({ ...CENSUS.controls.rows[1], control: "census_control_sorry" });
  const { graph, refusals } = buildCertificateGraph(nameless, { ledger: LEDGER });
  assert.equal(graph.nodes.length, 11);
  const refusal = refusals.find((r) => r.code === "row_has_no_declaration_name");
  assert.ok(refusal, "an anonymous control row must be refused by name");
  assert.match(refusal.reason, /identity needs an FQN/);
});

test("an all-refused census throws instead of publishing an empty graph", () => {
  const failed = structuredClone(CENSUS);
  failed.exec_leg.sample = failed.exec_leg.sample.map((row) => ({ ...row, rc: 1 }));
  assert.throws(() => buildCertificateGraph(failed, { ledger: LEDGER }), /refusing to build an empty certificate graph/);
  // The Hub's own layout guard refuses the same thing (graph-layout/src/index.ts:124-126).
  assert.throws(() => assertHubMountable({ nodes: [], edges: [] }, { positions: {}, pagerank: {} }), /empty proof graph/);
});

test("pagerank port: the depended-on certificate ranks above its consumer", () => {
  const { graph } = mounted();
  const consumer = graph.nodes.find((n) => n.fqn === INVARIANT_B_IFF.decl);
  const dependency = graph.nodes.find((n) => n.fqn === MEMBERS.decl);
  // Foundational direction (edges as stored, consumer -> dep), min-max normalised:
  // with exactly one edge and these two nodes, the dependency is the maximum.
  assert.equal(dependency.importance, 1);
  assert.equal(consumer.importance, 0);
  assert.ok(graph.nodes.every((n) => n.importance >= 0 && n.importance <= 1));
  // Port-level check on an isolated pair, no census involved: 1e-6 convergence,
  // damping 0.85, and the exact normalisation the module documents.
  const nodes = [{ id: "a" }, { id: "b" }];
  const ranks = computeFoundationalPageRank(nodes, [{ from: "a", to: "b" }]);
  assert.equal(ranks.get("b"), 1);
  assert.equal(ranks.get("a"), 0);
  assert.equal(computeFoundationalPageRank([], []).size, 0);
  // A self-loop is skipped, not counted as a dependency (the a === b guard). With
  // no surviving edge every node is dangling, all mass is redistributed uniformly,
  // all ranks are equal, and the min-max normalisation maps the whole set to 0 —
  // degenerate, and pinned as degenerate rather than asserted as meaningful.
  const loop = computeFoundationalPageRank(nodes, [{ from: "a", to: "a" }]);
  assert.equal(loop.get("a"), 0);
  assert.equal(loop.get("b"), 0);
});

test("hierarchical layout port: layer = longest path from a source", () => {
  const { graph, layout } = mounted();
  const consumer = layout.positions[graph.nodes.find((n) => n.fqn === INVARIANT_B_IFF.decl).id];
  const dependency = layout.positions[graph.nodes.find((n) => n.fqn === MEMBERS.decl).id];
  // The dependency is the node with an INCOMING edge, so it lands in layer 1 and
  // is drawn BELOW its consumer. size 1000 over two layers -> layerH 500.
  assert.equal(consumer.y, 250);
  assert.equal(dependency.y, 750);
  assert.ok(Number.isFinite(consumer.x) && Number.isFinite(dependency.x));
  assert.equal(layout.size, 1000);
  // A 3-node chain reaches layer 2, and the ids within a layer are sorted, so a
  // single-node layer sits at colW * 1 = size/2 — exact, not approximate.
  const chain = layoutHierarchical(
    [{ id: "a" }, { id: "b" }, { id: "c" }],
    [{ from: "a", to: "b" }, { from: "b", to: "c" }],
    { size: 300 },
  );
  const at = (id) => chain.positions.find((p) => p.id === id);
  assert.equal(at("a").y, 50);
  assert.equal(at("a").x, 150);
  assert.equal(at("b").y, 150);
  assert.equal(at("c").y, 250);
  assert.ok(chain.positions.every((p) => Number.isFinite(p.x) && Number.isFinite(p.y)));
  // The divergence is part of the contract, not a footnote: the hub publishes a
  // FORCE-directed layout (`graph-layout/src/index.ts:178-182`, seed 0xa1b2c3,
  // 320 iterations). This layout is hierarchical, and says so in its own payload,
  // so no consumer can mistake these coordinates for the hub's.
  assert.equal(layout.algorithm, "hierarchical-longest-path");
  assert.match(layout.algorithmDivergence, /mode:force/);
});

test("layout keys cover the node set exactly, and the mount gate fires when they do not", () => {
  const { graph, layout } = mounted();
  assert.equal(assertHubMountable(graph, layout), true);
  // NEGATIVE controls — the branch that must throw has to be proven to throw.
  const droppedPosition = structuredClone(layout);
  delete droppedPosition.positions[graph.nodes[0].id];
  assert.throws(() => assertHubMountable(graph, droppedPosition), /position keys do not exactly match/);
  const extraRank = structuredClone(layout);
  extraRank.pagerank["not-a-node"] = 0.5;
  assert.throws(() => assertHubMountable(graph, extraRank), /PageRank keys do not exactly match/);
  const unverified = structuredClone(graph);
  unverified.integrity.checks.totalsMatchNodes = false;
  assert.throws(() => assertHubMountable(unverified, layout), /missing successful merge-integrity checks/);
  const danglingEdge = structuredClone(graph);
  danglingEdge.edges[0].to = "ghost::ghost::ghost";
  assert.throws(() => assertHubMountable(danglingEdge, layout), /references a missing node ID/);
  const lyingTotal = structuredClone(graph);
  lyingTotal.totals.decls = 9999;
  assert.throws(() => assertHubMountable(lyingTotal, layout), /total does not match node count/);
  const wrongKind = structuredClone(graph);
  wrongKind.edges[0].kind = "imports";
  assert.throws(() => assertHubMountable(wrongKind, layout), /resolved edge 0 has unsupported kind imports/);
});

test("the hub receipt gate accepts the emitted triple", () => {
  const { graph, layout } = mounted();
  const out = serializeCertificateGraph(graph, layout);
  assert.equal(out.graphSha256.length, 64);
  assert.equal(out.layoutSha256.length, 64);
  const parsedLayout = JSON.parse(out.layoutText);
  assert.equal(parsedLayout.version, 2);
  assert.equal(parsedLayout.sourceGraphSha256, out.graphSha256);
  assert.equal(out.receipt.schemaVersion, RECEIPT_SCHEMA_VERSION);
  assert.equal(out.receipt.status, EVIDENCE_STATUS);
  assert.equal(out.receipt.kernelVerified, false);
  assert.equal(out.receipt.graph.nodes, graph.nodes.length);
  assert.equal(out.receipt.graph.edges, graph.edges.length);
  assert.equal(out.receipt.layout.resolvedEdges, 1);
  assert.equal(out.receipt.payloads["proofs-graph.json"], out.graphSha256);
  assert.equal(assertHubReceiptConsistent(out.receipt, graph, parsedLayout, { graphSha256: out.graphSha256, layoutSha256: out.layoutSha256 }), true);
});

test("the receipt gate FIRES on each of the five historical ways a triple can disagree", () => {
  const { graph, layout } = mounted();
  const out = serializeCertificateGraph(graph, layout);
  const parsedLayout = JSON.parse(out.layoutText);
  const ctx = { graphSha256: out.graphSha256, layoutSha256: out.layoutSha256 };

  // 1. The historical incident: a consumer pinned to the old schema version.
  assert.throws(
    () => assertHubReceiptConsistent({ ...out.receipt, schemaVersion: 2 }, graph, parsedLayout, ctx),
    /schemaVersion 2 != 3/,
  );
  // 2. A receipt whose digest does not describe these bytes.
  assert.throws(
    () => assertHubReceiptConsistent({ ...out.receipt, graph: { ...out.receipt.graph, sha256: "0".repeat(64) } }, graph, parsedLayout, ctx),
    /proof graph hash does not match/,
  );
  // 3. A promoted evidence tier: a graph that claims kernel verification.
  assert.throws(
    () => assertHubReceiptConsistent(out.receipt, { ...graph, kernelVerified: true }, parsedLayout, ctx),
    /unsupported evidence contract/,
  );
  // 4. Timestamps that disagree across the three files — the exact leg that makes
  //    the receipt a statement about THIS graph rather than any graph.
  assert.throws(
    () => assertHubReceiptConsistent(out.receipt, { ...graph, generatedAt: "2020-01-01T00:00:00Z" }, parsedLayout, ctx),
    /generation timestamps do not agree/,
  );
  // 5. A layout derived from a different graph.
  assert.throws(
    () => assertHubReceiptConsistent(out.receipt, graph, { ...parsedLayout, sourceGraphSha256: "1".repeat(64) }, ctx),
    /not derived from the completed graph/,
  );
});

test("determinism: the same census mounts to the same bytes", () => {
  const first = buildCertificateGraph(CENSUS, { ledger: LEDGER });
  const second = buildCertificateGraph(CENSUS, { ledger: LEDGER });
  const a = serializeCertificateGraph(first.graph, first.layout);
  const b = serializeCertificateGraph(second.graph, second.layout);
  assert.equal(a.graphText, b.graphText);
  assert.equal(a.layoutText, b.layoutText);
  assert.equal(a.graphSha256, b.graphSha256);
  assert.equal(a.layoutSha256, b.layoutSha256);
  // And the digests describe the emitted bytes, not some other rendering of them.
  assert.equal(a.receipt.payloads["proofs-graph.json"], a.graphSha256);
});

test("waddle tag: mounting under a different waddle changes every id, not none", () => {
  const asCfsg = mounted();
  const asReactor = buildCertificateGraph(CENSUS, { waddle: "cfsg-reactor", ledger: LEDGER });
  assert.deepEqual(asReactor.graph.waddles, ["cfsg-reactor"]);
  assert.notEqual(asReactor.graph.nodes[0].id, asCfsg.graph.nodes[0].id);
  // `-` is in the law's pass-through set [A-Za-z0-9.-], so a hyphenated waddle
  // tag survives literally — a port that escaped it would mint ids the hub cannot
  // reproduce, which is exactly why this is pinned rather than assumed.
  assert.ok(asReactor.graph.nodes[0].id.startsWith("cfsg-reactor::"));
  assert.ok(asReactor.graph.nodes.every((n) => n.waddle === "cfsg-reactor"));
  // The identity law is what makes two CFSG mounts of different censuses
  // distinguishable instead of colliding — so the tag must reach the id.
  assert.equal(asCfsg.graph.nodes[0].id.startsWith("cfsg::"), true);
});

test("planNodeIds is reusable and reports its own fallback count", () => {
  const plan = planNodeIds([
    { waddle: "cfsg", file: "./A/B.lean", fqn: "A.b", line: 0 },
    { waddle: "cfsg", file: "A/./B.lean", fqn: "A.c", line: 0 },
  ]);
  // Both spellings normalize to the same file, and distinct fqns stay distinct.
  assert.equal(plan.normalizedFiles[0], "A/B.lean");
  assert.equal(plan.normalizedFiles[1], "A/B.lean");
  assert.equal(plan.ids[0], "cfsg::A_2fB.lean::A.b");
  assert.equal(plan.lineFallbacks, 0);
  assert.throws(() => planNodeIds([{ waddle: "cfsg", file: "/abs/B.lean", fqn: "A.b", line: 0 }]), /escapes the project root|project-relative/);
  assert.throws(() => planNodeIds([{ waddle: "", file: "B.lean", fqn: "A.b", line: 0 }]), /no waddle identity/);
});

/* --------------------------------------------------------------------------
 * ONE ISOLATED CONTROL PER REFUSAL LEG
 *
 * The controls above were chosen by hand, and a hand-chosen set is only as strong
 * as the last leg someone remembered. Measured on 2026-11-10 by neutralising one
 * guard condition at a time inside the two gates of a scratch copy of the bridge
 * and re-running this file (unmodified source: 18 pass, 0 fail): 12 of the 26
 * guards turned the suite red, and 14 could be deleted with the suite still
 * green — every count, payload-hash, receipt-status, node-id, layout-check and
 * layout-cover leg of `assertHubReceiptConsistent`, plus the missing-edge-array,
 * duplicate-id and missing-waddle legs of `assertHubMountable`.
 *
 * The tables below close that, and `refusalLegs()` keeps them honest: the leg
 * list is counted out of the bridge source at test time, so a guard added without
 * a control — or a control left naming a guard that is gone — fails the suite
 * instead of going quietly green.
 *
 * Each control perturbs EXACTLY ONE field and is asserted against the WHOLE
 * message, not a substring. Both halves matter. The pre-existing timestamp
 * control moved `graph.generatedAt`, which trips the two layout conjuncts of the
 * same leg as well, so deleting the receipt-vs-graph conjunct left the suite green
 * (measured: `pass 18 fail 0`). Isolation is what makes a control a proof.
 * -------------------------------------------------------------------------- */

/** The bridge's own text, read once through `import.meta.url` so this works from
 *  any cwd and never leaves the repo. */
const BRIDGE_SOURCE = readFileSync(
  new URL("../../patent-portfolio/lib/cfsg-proof-graph-bridge.mjs", import.meta.url),
  "utf8",
);

/** Stand-in inside a leg string for a `${...}` interpolation in the source. */
const ANY = "*";

/** Every `throw new Error(...)` inside one gate function, each `${...}` replaced
 *  by `ANY`, whitespace collapsed. Sites, not distinct messages: two guards can
 *  share a sentence and still be two guards. */
function refusalLegs(fnName) {
  const start = BRIDGE_SOURCE.indexOf(`export function ${fnName}(`);
  assert.notEqual(start, -1, `${fnName} is no longer in the bridge source`);
  const body = BRIDGE_SOURCE.slice(start, BRIDGE_SOURCE.indexOf("\n}", start));
  const legs = [];
  for (const match of body.matchAll(/throw new Error\(\s*(?:`([^`]*)`|"([^"]*)"|'([^']*)')/g)) {
    legs.push((match[1] ?? match[2] ?? match[3]).replace(/\$\{[^}]*\}/g, ANY).replace(/\s+/g, " ").trim());
  }
  return legs;
}

const escapeRe = (text) => text.replace(/[.*+?^${}()|[\]\\]/g, "\\$&");

/** Assert that `run` is refused by exactly this leg. A control that trips a
 *  different leg proves nothing about the leg it names. */
function assertRefusedBy(run, leg, label) {
  const pattern = new RegExp(`^${leg.split(ANY).map(escapeRe).join("[\\s\\S]*?")}$`);
  let seen = "<did not throw>";
  try {
    run();
  } catch (error) {
    seen = error instanceof Error ? error.message : String(error);
  }
  assert.match(seen, pattern, `${label}\n  expected leg: ${leg}`);
}

/** The in-memory pair a consumer would hand the Hub's mount gate. */
const mountCase = () => mounted();

/** The published triple, as the Hub reads it: receipt, graph, layout bytes, ctx. */
const receiptCase = () => {
  const { graph, layout } = mounted();
  const out = serializeCertificateGraph(graph, layout);
  return {
    receipt: out.receipt,
    graph,
    layout: JSON.parse(out.layoutText),
    ctx: { graphSha256: out.graphSha256, layoutSha256: out.layoutSha256 },
  };
};

const withoutKey = (record, key) =>
  Object.fromEntries(Object.entries(record).filter(([name]) => name !== key));
const patchedAt = (items, index, patch) =>
  items.map((item, i) => (i === index ? { ...item, ...patch } : item));
const graphWith = (graph, patch) => ({ ...graph, ...patch });
const integrityOf = (graph, identity, checks) => ({
  ...graph,
  integrity: {
    ...graph.integrity,
    identity: { ...graph.integrity.identity, ...identity },
    checks: { ...graph.integrity.checks, ...checks },
  },
});
const receiptWith = (t, patch) => ({ ...t.receipt, ...patch });
const receiptGraphWith = (t, patch) => receiptWith(t, { graph: { ...t.receipt.graph, ...patch } });
const receiptLayoutWith = (t, patch) => receiptWith(t, { layout: { ...t.receipt.layout, ...patch } });

/** The mount gate's legs. `args` returns `[graph, layout]`. */
const MOUNT_CONTROLS = [
  {
    leg: "refusing to lay out an empty proof graph",
    why: "a graph with no nodes is a refusal, not a page of nothing",
    args: () => [{ nodes: [], edges: [] }, { positions: {}, pagerank: {} }],
  },
  {
    leg: "proof graph has no edge array",
    why: "a missing edge list is a different claim from an empty one",
    args: ({ graph, layout }) => [graphWith(graph, { edges: undefined }), layout],
  },
  {
    leg: "proof graph is missing successful merge-integrity checks",
    why: "identity leg: the graph no longer asserts its own ids are unique",
    args: ({ graph, layout }) => [integrityOf(graph, { uniqueNodeIds: false }, {}), layout],
  },
  {
    leg: "proof graph is missing successful merge-integrity checks",
    why: "the same guard, its endpoint conjunct",
    args: ({ graph, layout }) => [integrityOf(graph, {}, { resolvedEdgeEndpointsExist: false }), layout],
  },
  {
    leg: "proof graph is missing successful merge-integrity checks",
    why: "the same guard, its total conjunct",
    args: ({ graph, layout }) => [integrityOf(graph, {}, { totalsMatchNodes: false }), layout],
  },
  {
    leg: "proof graph declaration total does not match node count",
    why: "a declared total that is not the node count, with the stored flag still true",
    args: ({ graph, layout }) => [graphWith(graph, { totals: { ...graph.totals, decls: 9999 } }), layout],
  },
  {
    leg: "proof graph contains duplicate node IDs",
    why: "two rows minting one id — the thing the identity law exists to prevent",
    args: ({ graph, layout }) => [
      graphWith(graph, { nodes: patchedAt(graph.nodes, 1, { id: graph.nodes[0].id }) }),
      layout,
    ],
  },
  {
    leg: `proof graph node ${ANY} has no waddle`,
    why: "an unattributed node cannot fold into a hub graph keyed on waddle",
    args: ({ graph, layout }) => [
      graphWith(graph, { nodes: patchedAt(graph.nodes, 0, { waddle: "" }) }),
      layout,
    ],
  },
  {
    leg: `resolved edge ${ANY} references a missing node ID`,
    why: "a dangling endpoint",
    args: ({ graph, layout }) => [
      graphWith(graph, { edges: patchedAt(graph.edges, 0, { to: "ghost::ghost::ghost" }) }),
      layout,
    ],
  },
  {
    leg: `resolved edge ${ANY} has unsupported kind ${ANY}`,
    why: "`imports` is emittable by the producer but unpositionable by the layout",
    args: ({ graph, layout }) => [
      graphWith(graph, { edges: patchedAt(graph.edges, 0, { kind: "imports" }) }),
      layout,
    ],
  },
  {
    leg: "layout position keys do not exactly match graph node IDs",
    why: "a node the renderer would silently drop",
    args: ({ graph, layout }) => [graph, { ...layout, positions: withoutKey(layout.positions, graph.nodes[0].id) }],
  },
  {
    leg: "layout PageRank keys do not exactly match graph node IDs",
    why: "a rank for a node that is not in the graph",
    args: ({ graph, layout }) => [graph, { ...layout, pagerank: { ...layout.pagerank, "not-a-node": 0.5 } }],
  },
];

/** The receipt gate's legs. `args` returns the four gate arguments. */
const RECEIPT_CONTROLS = [
  {
    leg: `proof graph receipt has an unsupported evidence contract: schemaVersion ${ANY} != ${ANY}`,
    why: "the 2026-10-22 incident: a consumer left pinned at v2 while the generator bumped",
    args: (t) => [receiptWith(t, { schemaVersion: RECEIPT_SCHEMA_VERSION - 1 }), t.graph, t.layout, t.ctx],
  },
  {
    leg: `proof graph receipt has an unsupported evidence contract: status ${ANY} != ${ANY}`,
    why: "a receipt that renames its own evidence tier",
    args: (t) => [receiptWith(t, { status: "kernel-verified" }), t.graph, t.layout, t.ctx],
  },
  {
    leg: `proof graph receipt has an unsupported evidence contract: kernelVerified ${ANY} != false`,
    why: "a receipt that promotes itself to a kernel claim",
    args: (t) => [receiptWith(t, { kernelVerified: true }), t.graph, t.layout, t.ctx],
  },
  {
    leg: "proof graph payload has an unsupported evidence contract",
    why: "a graph whose evidence class was rewritten, not one that is kernel-verified",
    args: (t) => [t.receipt, graphWith(t.graph, { evidenceClass: "kernel-verified" }), t.layout, t.ctx],
  },
  {
    leg: "proof graph hash does not match its completion receipt",
    why: "a receipt digest that does not describe these graph bytes",
    args: (t) => [receiptGraphWith(t, { sha256: "0".repeat(64) }), t.graph, t.layout, t.ctx],
  },
  {
    leg: "proof layout hash does not match its completion receipt",
    why: "the same lie on the layout side — a separate field, a separate leg",
    args: (t) => [receiptLayoutWith(t, { sha256: "1".repeat(64) }), t.graph, t.layout, t.ctx],
  },
  {
    leg: "proof payload hashes do not match the completion receipt",
    why: "the payloads map disagrees with the digests the gate was handed",
    args: (t) => [
      receiptWith(t, { payloads: { ...t.receipt.payloads, "proofs-layout.json": "2".repeat(64) } }),
      t.graph,
      t.layout,
      t.ctx,
    ],
  },
  {
    leg: "proof layout was not derived from the completed graph",
    why: "the layout payload claims a different parent graph",
    args: (t) => [t.receipt, t.graph, { ...t.layout, sourceGraphSha256: "3".repeat(64) }, t.ctx],
  },
  {
    leg: "proof layout was not derived from the completed graph",
    why: "the receipt's copy of that claim disagrees with the layout's",
    args: (t) => [receiptLayoutWith(t, { sourceGraphSha256: "4".repeat(64) }), t.graph, t.layout, t.ctx],
  },
  {
    leg: "proof graph nodes do not have unique stable IDs",
    why: "ids the hub could not address, checked by recomputation not by the stored flag",
    args: (t) => [
      t.receipt,
      graphWith(t.graph, { nodes: patchedAt(t.graph.nodes, 1, { id: t.graph.nodes[0].id }) }),
      t.layout,
      t.ctx,
    ],
  },
  {
    leg: "proof artifact counts do not match the completion receipt",
    why: "a receipt that counts 999 nodes",
    args: (t) => [receiptGraphWith(t, { nodes: 999 }), t.graph, t.layout, t.ctx],
  },
  {
    leg: "proof artifact counts do not match the completion receipt",
    why: "the same guard on the layout payload's own nodeCount, which is a second copy",
    args: (t) => [t.receipt, t.graph, { ...t.layout, nodeCount: 999 }, t.ctx],
  },
  {
    leg: "proof artifact counts do not match the completion receipt",
    why: "and on the receipt's layout.nodes",
    args: (t) => [receiptLayoutWith(t, { nodes: 999 }), t.graph, t.layout, t.ctx],
  },
  {
    leg: "proof layout resolved-edge count does not match the completed graph",
    why: "a receipt that reports zero resolved edges for a graph with one",
    args: (t) => [receiptLayoutWith(t, { resolvedEdges: 0 }), t.graph, t.layout, t.ctx],
  },
  {
    leg: "proof artifact generation timestamps do not agree",
    why: "RECEIPT-side drift only — graph and layout still agree with each other, so this is the leg that makes the receipt a statement about THIS graph",
    args: (t) => [receiptWith(t, { generatedAt: "2020-01-01T00:00:00Z" }), t.graph, t.layout, t.ctx],
  },
  {
    leg: "proof artifact generation timestamps do not agree",
    why: "layout-side drift only — a layout computed at a different moment than the graph",
    args: (t) => [t.receipt, t.graph, { ...t.layout, computedAt: "2020-01-01T00:00:00Z" }, t.ctx],
  },
  {
    leg: "proof layout integrity checks are not affirmative",
    why: "a layout whose stored self-report was flipped",
    args: (t) => [
      t.receipt,
      t.graph,
      { ...t.layout, checks: { ...t.layout.checks, pagerankKeysMatchNodeIds: false } },
      t.ctx,
    ],
  },
  {
    leg: "proof layout does not cover exactly the completed graph node IDs",
    why: "a position missing while `checks` still says true — the gate recomputes it",
    args: (t) => [
      t.receipt,
      t.graph,
      { ...t.layout, positions: withoutKey(t.layout.positions, t.graph.nodes[0].id) },
      t.ctx,
    ],
  },
  {
    leg: "proof layout does not cover exactly the completed graph node IDs",
    why: "the same sentence from the PageRank side, a separate guard",
    args: (t) => [
      t.receipt,
      t.graph,
      { ...t.layout, pagerank: withoutKey(t.layout.pagerank, t.graph.nodes[0].id) },
      t.ctx,
    ],
  },
];

test("mount gate: every refusal leg has an isolated negative control that fires", () => {
  const base = mountCase();
  for (const control of MOUNT_CONTROLS) {
    assertRefusedBy(() => assertHubMountable(...control.args(base)), control.leg, `mount gate — ${control.why}`);
  }
});

test("receipt gate: every refusal leg has an isolated negative control that fires", () => {
  const base = receiptCase();
  for (const control of RECEIPT_CONTROLS) {
    assertRefusedBy(
      () => assertHubReceiptConsistent(...control.args(base)),
      control.leg,
      `receipt gate — ${control.why}`,
    );
  }
});

test("the control tables cover the gates' real legs, and name no leg that is gone", () => {
  const mount = refusalLegs("assertHubMountable");
  const receipt = refusalLegs("assertHubReceiptConsistent");
  // Site counts, measured from the source on 2026-11-10. A new guard with a new
  // sentence is caught by the set checks below; a new guard that REUSES an
  // existing sentence is caught only here, which is why the counts are pinned.
  assert.equal(mount.length, 10, "assertHubMountable throw sites");
  assert.equal(receipt.length, 15, "assertHubReceiptConsistent throw sites");
  for (const [name, legs, controls] of [
    ["assertHubMountable", mount, MOUNT_CONTROLS],
    ["assertHubReceiptConsistent", receipt, RECEIPT_CONTROLS],
  ]) {
    const real = new Set(legs);
    const covered = new Set(controls.map((control) => control.leg));
    assert.deepEqual(
      [...real].filter((leg) => !covered.has(leg)),
      [],
      `${name}: refusal legs with no negative control`,
    );
    assert.deepEqual(
      [...covered].filter((leg) => !real.has(leg)),
      [],
      `${name}: controls naming a leg the source no longer has`,
    );
  }
});

test("the gates also refuse nothing: an unresolved edge is skipped, not laundered", () => {
  const { graph, layout } = mounted();
  const ghost = {
    from: "ghost::ghost::ghost",
    to: "ghost::ghost::ghost",
    kind: "imports",
    resolution: "unresolved",
  };
  const withGhost = graphWith(graph, { edges: [...graph.edges, ghost] });
  // The mount gate validates RESOLVED edges only. An unresolved one is a real hub
  // state — the producer records refs it has not resolved yet — so refusing it
  // here would be the opposite error from mounting it as resolved.
  assert.equal(assertHubMountable(withGhost, layout), true);
  // And the resolved-edge count is that filter, not `edges.length`: the receipt
  // says one edge was resolved while two were emitted.
  const out = serializeCertificateGraph(withGhost, layout);
  assert.equal(out.receipt.graph.edges, 2);
  assert.equal(out.receipt.layout.resolvedEdges, 1);
  const parsed = JSON.parse(out.layoutText);
  assert.equal(parsed.resolvedEdgeCount, 1);
  assert.equal(
    assertHubReceiptConsistent(out.receipt, withGhost, parsed, {
      graphSha256: out.graphSha256,
      layoutSha256: out.layoutSha256,
    }),
    true,
  );
});

test("normalizeSourceFile: each shape that would mount a wrong path is refused by name", () => {
  // The accept side — spellings the hub's own normaliser collapses.
  assert.equal(normalizeSourceFile("./A/B.lean"), "A/B.lean");
  assert.equal(normalizeSourceFile("A/./B.lean"), "A/B.lean");
  assert.equal(normalizeSourceFile("A//B.lean"), "A/B.lean");
  assert.equal(normalizeSourceFile("A\\B.lean"), "A/B.lean");
  assert.equal(normalizeSourceFile("  A/B.lean  "), "A/B.lean");
  // The refusal side. `/abs/A/B.lean` is the one that matters: a `split("/")`
  // loop drops the leading slash and mounts `/abs/A/B.lean` as `abs/A/B.lean`,
  // which is a DIFFERENT FILE CLAIM, accepted silently.
  for (const bad of ["", "   ", ".", "..", "../A/B.lean", "/abs/A/B.lean", "A/../../B.lean"]) {
    assert.throws(
      () => normalizeSourceFile(bad),
      /no stable project-relative source file/,
      `normalizeSourceFile must refuse ${JSON.stringify(bad)}`,
    );
  }
  assert.throws(() => normalizeSourceFile(undefined), /no stable project-relative source file/);
  assert.throws(() => normalizeSourceFile(null), /no stable project-relative source file/);
  // The identity law's own two name guards, which are not path legs.
  assert.throws(() => nodeIdentityBase({ waddle: "cfsg", file: "A/B.lean", fqn: "  " }), /no FQN identity/);
  assert.throws(() => nodeIdentityBase({ waddle: " ", file: "A/B.lean", fqn: "A.b" }), /no waddle identity/);
});

test("the receipt is built by buildCompletionReceipt, and names the commit it was read at", () => {
  const { graph, layout } = mounted();
  const out = serializeCertificateGraph(graph, layout);
  assert.equal(out.receipt.repositoryCommit, CENSUS.denominators.commit);
  assert.equal(out.receipt.generatedAt, CENSUS.generated_at);
  assert.deepEqual(out.receipt.producer, {
    name: "cfsg-proof-graph-bridge",
    producerFiles: ["patent-portfolio/lib/cfsg-proof-graph-bridge.mjs"],
  });
  const overridden = serializeCertificateGraph(graph, layout, {
    producer: { name: "lane", producerFiles: ["tests/unit/cfsg-proof-graph-bridge.test.mjs"] },
  });
  assert.deepEqual(overridden.receipt.producer, {
    name: "lane",
    producerFiles: ["tests/unit/cfsg-proof-graph-bridge.test.mjs"],
  });
  // serializeCertificateGraph delegates: the exported builder, handed the same
  // digests, must produce an identical receipt. If the two ever diverge, a caller
  // that builds the receipt directly would pass a gate the publisher's own
  // receipt fails.
  const direct = buildCompletionReceipt(
    graph,
    { ...layout, sourceGraphSha256: out.graphSha256 },
    { graphSha256: out.graphSha256, layoutSha256: out.layoutSha256 },
  );
  assert.deepEqual(direct, out.receipt);
});

/* --------------------------------------------------------------------------
 * THE PORT'S OWN DRIFT PIN — six claims moved from prose into a check
 *
 * Every leg above this line measures the bridge against fixtures that live IN
 * this file. That is deliberate — the suite runs offline, on a host with no
 * Kagami checkout — and it is why the fixture census reproduces all 13
 * `exec_leg.sample` rows of the artifact. But the same inlining quietly left the
 * six facts about the world OUTSIDE the repo asserted by comment text only.
 * Measured on 2026-11-14 with
 * `grep -n "e7cf806c\|6ac4e113\|fe852457\|2e906b28\|68f0a35d" <bridge> <test>`:
 * all five digests occur ONLY inside `*` comment lines — no code in this repo
 * recomputed any of them — and the published node id (below, line 229 before
 * this block) and the published key set (line 272) are string literals
 * transcribed by hand on 2026-11-02. So the header's promise "Drift is
 * therefore detectable, not silent" described an intention, not a mechanism: if
 * the Hub had moved, this file would still have printed 24 pass 0 fail, and the
 * integration it certifies would have broken at runtime. That is the same hole
 * the header itself documents at `proof-artifacts-cache.ts:196-203` — a literal
 * `schemaVersion !== 2` copied into a generator, nothing pinning the copy.
 *
 * These legs are the mechanism. Where the producer tree and the census artifact
 * exist, they recompute from the live bytes: the four ported-source digests
 * against the producer receipt AND the files, the receipt's own evidence
 * constants against `EVIDENCE_STATUS`/`RECEIPT_SCHEMA_VERSION`, the layout
 * guard's edge-kind set against `LAYOUT_EDGE_KINDS`, the harvest's edge-kind
 * union against `PRODUCER_EDGE_KINDS`, the `def` floor that `certificate` is
 * claimed to take, the REQUIRED fields of `DeclRecord` against a mounted node,
 * the identity law applied to the graph's OWN node 0 rather than a copied
 * string, and the mount of the real artifact rather than its projection.
 *
 * Absence is not drift, and is not allowed to pass as a check: when the
 * authority is not on this host the leg reports itself SKIPPED with the reason,
 * the convention `tests/unit/identity-coherence.test.mjs:53-58` already uses.
 *
 * `upstreamDrift()` is pure — it takes its inputs, so the control in the last
 * leg below can hand it one doctored digest and prove the disagreement comes
 * back named. A pin that cannot fail is a comment with a call in front of it.
 * -------------------------------------------------------------------------- */

/** Producer-tree authority, overridable for sandboxed or known-positive runs. */
const WADDLE_REPO =
  process.env.WADDLE_REPO || "/Users/schizodactyl/projects/awkronos-waddle";
const CENSUS_ARTIFACT_PATH =
  process.env.CFSG_CENSUS_ARTIFACT ||
  "/Users/schizodactyl/.kagami/solver-certs/GR-FULLSEND-1027-CFSG-AXIOM-CENSUS.json";

const HEX64 = /^[0-9a-f]{64}$/;
const digestFile = (path) => createHash("sha256").update(readFileSync(path)).digest("hex");

/** Members of a `const NAME = new Set<…["kind"]>([ "a", "b" ]);` literal. */
function setOfKinds(source, name) {
  const block = source.match(
    new RegExp(String.raw`const ${name} = new Set<\w+\["kind"\]>\(\[([\s\S]*?)\]\);`),
  );
  if (!block) return null;
  return [...block[1].matchAll(/"([^"]+)"/g)].map((match) => match[1]);
}

/** Members of the harvest's `kind: "uses" | "imports" | …;` union. */
function producerEdgeKinds(source) {
  const union = source.match(/kind:\s*("uses"(?:\s*\|\s*"[^"]+")+);/);
  if (!union) return null;
  return [...union[1].matchAll(/"([^"]+)"/g)].map((match) => match[1]);
}

/** Fields of `export interface DeclRecord { … }` with no `?` — what a consumer
 *  actually requires. `influence` is optional today; if it ever becomes required,
 *  every mounted node is missing it, and that belongs in this file's red. */
function requiredDeclRecordFields(source) {
  const iface = source.match(/export interface DeclRecord \{([\s\S]*?)\n\}/);
  if (!iface) return null;
  return [...iface[1].matchAll(/^ {2}(\w+)(\?)?:/gm)]
    .filter((match) => !match[2])
    .map((match) => match[1]);
}

/** Same-members comparison that refuses to be vacuous: an unparsed shape on
 *  either side is reported, never treated as agreement. */
function sameSet(a, b) {
  if (!Array.isArray(a) || !Array.isArray(b)) return false;
  const na = [...new Set(a)].sort();
  const nb = [...new Set(b)].sort();
  return na.length === nb.length && na.every((value, index) => value === nb[index]);
}

/**
 * @returns {string[]} one line per claim the live surface no longer supports.
 *   Empty means the port's documented assumptions still hold.
 */
function upstreamDrift({ pins, sourceDigests, receipt, layoutSource, harvestSource, hubGraph, census, censusDigest, mounted }) {
  const drift = [];

  for (const [path, pin] of Object.entries(pins.sources)) {
    if (!HEX64.test(pin)) drift.push(`pin for ${path} is not a sha256: ${JSON.stringify(pin)}`);
    const live = sourceDigests[path];
    if (live === undefined) {
      drift.push(`no live digest for ${path} — the port claims to read it`);
    } else if (live !== pin) {
      drift.push(`ported source moved: ${path} is ${live} on disk, the bridge pins ${pin}`);
    }
    const recorded = receipt?.implementation?.[path];
    if (recorded === undefined) {
      drift.push(`producer receipt names no ${path} — the pin lost its authority`);
    } else if (recorded !== pin) {
      drift.push(`pin disagrees with the producer receipt: ${path} pins ${pin}, receipt says ${recorded}`);
    }
  }

  const pinnedCensus = Object.entries(pins.artifacts);
  if (pinnedCensus.length !== 1) drift.push(`expected exactly one pinned artifact, found ${pinnedCensus.length}`);
  for (const [, pin] of pinnedCensus) {
    if (censusDigest !== pin) {
      drift.push(`census artifact moved: ${censusDigest} on disk, the bridge pins ${pin}`);
    }
  }

  // The two constants the Hub's gate compares against, bound to the live gate.
  if (receipt?.schemaVersion !== RECEIPT_SCHEMA_VERSION) {
    drift.push(`receipt schemaVersion ${JSON.stringify(receipt?.schemaVersion)} != ${RECEIPT_SCHEMA_VERSION}`);
  }
  if (receipt?.status !== EVIDENCE_STATUS) {
    drift.push(`receipt status ${JSON.stringify(receipt?.status)} != ${JSON.stringify(EVIDENCE_STATUS)}`);
  }

  // Edge vocabularies: what the layout can position, and what the producer emits.
  if (!sameSet(setOfKinds(layoutSource, "EDGE_KINDS"), LAYOUT_EDGE_KINDS)) {
    drift.push(
      `layout EDGE_KINDS ${JSON.stringify(setOfKinds(layoutSource, "EDGE_KINDS"))} != LAYOUT_EDGE_KINDS ${JSON.stringify(LAYOUT_EDGE_KINDS)}`,
    );
  }
  if (!sameSet(producerEdgeKinds(harvestSource), PRODUCER_EDGE_KINDS)) {
    drift.push(
      `harvest Edge kind union ${JSON.stringify(producerEdgeKinds(harvestSource))} != PRODUCER_EDGE_KINDS ${JSON.stringify(PRODUCER_EDGE_KINDS)}`,
    );
  }

  // The floor `certificate` is claimed to take: an unknown kind must land on
  // "def", and "certificate" must still be unknown. Either half breaking changes
  // how the hub paints these nodes.
  if (!/:\s*"def";/.test(layoutSource)) {
    drift.push("layout no longer floors an unknown declaration kind at \"def\"");
  }
  const declKinds = setOfKinds(layoutSource, "DECL_KINDS");
  if (!Array.isArray(declKinds)) {
    drift.push("could not parse layout DECL_KINDS — the eight-kind claim is unmeasured");
  } else if (declKinds.includes(CERTIFICATE_NODE_KIND)) {
    drift.push(`harvest now publishes kind ${CERTIFICATE_NODE_KIND} — the node is no longer a floor case`);
  }

  // Consumability of a mounted node against the CURRENT required field set.
  const required = requiredDeclRecordFields(harvestSource);
  if (!Array.isArray(required) || required.length === 0) {
    drift.push("could not parse required fields of DeclRecord — consumability is unmeasured");
  } else {
    const nodes = mounted?.graph?.nodes ?? [];
    for (const field of required) {
      const missing = nodes.filter((node) => !node || !(field in node));
      if (missing.length > 0) {
        drift.push(
          `${missing.length}/${nodes.length} mounted nodes lack now-required DeclRecord field ${field} (e.g. ${missing[0]?.fqn})`,
        );
      }
    }
  }

  // The published graph: identity law re-derived from its own row 0, not copied.
  const first = hubGraph?.nodes?.[0];
  if (!first) {
    drift.push("hub graph has no node 0 to check the identity law against");
  } else {
    const recomputed = nodeIdentityBase({ waddle: first.waddle, file: first.file, fqn: first.fqn });
    if (recomputed !== first.id) {
      drift.push(`identity law no longer reproduces the published id: got ${JSON.stringify(recomputed)} want ${JSON.stringify(first.id)}`);
    }
  }
  const counts = [
    ["totals.decls vs node count", hubGraph?.totals?.decls === hubGraph?.nodes?.length],
    ["receipt nodes vs node count", receipt?.graph?.nodes === hubGraph?.nodes?.length],
    ["receipt edges vs edge count", receipt?.graph?.edges === hubGraph?.edges?.length],
  ];
  for (const [label, ok] of counts) if (!ok) drift.push(`hub graph count check failed: ${label}`);
  const edgeKinds = new Set((hubGraph?.edges ?? []).map((edge) => edge.kind));
  if (edgeKinds.size !== 1 || !edgeKinds.has("uses")) {
    drift.push(`published graph edge kinds are ${JSON.stringify([...edgeKinds])}, not the single "uses"`);
  }
  if ((hubGraph?.waddles ?? []).includes("cfsg")) {
    drift.push("the hub graph now carries a cfsg waddle — surface (1) is no longer missing CFSG declarations");
  }

  // The real artifact, mounted through the bridge itself.
  if (census?.schema !== CENSUS_SCHEMA) {
    drift.push(`live census schema ${JSON.stringify(census?.schema)} != ${CENSUS_SCHEMA}`);
  }
  if (!sameSet(census?.verdict_words?.row_verdicts, CENSUS_VERDICTS)) {
    drift.push(
      `census verdict vocabulary ${JSON.stringify(census?.verdict_words?.row_verdicts)} != CENSUS_VERDICTS ${JSON.stringify(CENSUS_VERDICTS)}`,
    );
  }
  if (typeof census?.tier_law !== "string" || !/no CFSG statement is machine-checked/.test(census.tier_law)) {
    drift.push("census tier_law no longer states the limit the bridge carries verbatim");
  }
  if (!Array.isArray(census?.exec_leg?.sample)) {
    drift.push("live census has no exec_leg.sample array — the mount input moved");
  } else if (mounted?.graph?.nodes?.length !== 11 || mounted?.refusals?.length !== 2) {
    drift.push(
      `the live artifact no longer mounts to 11 nodes and 2 refusals: got ${mounted?.graph?.nodes?.length} nodes, ${mounted?.refusals?.length} refusals`,
    );
  } else if (!mounted.refusals.every((r) => r.code === "probe_rc_nonzero")) {
    drift.push(`live artifact refusals are ${JSON.stringify(mounted.refusals.map((r) => r.code))}, expected all probe_rc_nonzero`);
  }

  return drift;
}

/** A whole surface, read once, in the shapes `upstreamDrift` expects. */
function readUpstreamSurface() {
  const sourceDigests = {};
  for (const path of Object.keys(UPSTREAM_PINS.sources)) {
    sourceDigests[path] = digestFile(`${WADDLE_REPO}/${path}`);
  }
  const receipt = JSON.parse(readFileSync(`${WADDLE_REPO}/apps/hub/data/proof-graph-build-receipt.json`, "utf8"));
  const census = JSON.parse(readFileSync(CENSUS_ARTIFACT_PATH, "utf8"));
  return {
    pins: UPSTREAM_PINS,
    sourceDigests,
    receipt,
    layoutSource: readFileSync(`${WADDLE_REPO}/tools/graph-layout/src/index.ts`, "utf8"),
    harvestSource: readFileSync(`${WADDLE_REPO}/packages/lean-build-graph/src/index.ts`, "utf8"),
    hubGraph: JSON.parse(readFileSync(`${WADDLE_REPO}/apps/hub/data/proofs-graph.json`, "utf8")),
    census,
    censusDigest: digestFile(CENSUS_ARTIFACT_PATH),
    mounted: buildCertificateGraph(census, { ledger: [] }),
  };
}

test("the bridge publishes its upstream pins as data, not as prose", () => {
  // This half needs no authority and is the falsifier: at base the export does
  // not exist, so the digests the header cites had no referent anywhere in code.
  assert.equal(typeof UPSTREAM_PINS, "object", "UPSTREAM_PINS must be exported by the bridge");
  assert.deepEqual(
    Object.keys(UPSTREAM_PINS.sources).sort(),
    [
      "packages/graph-engine/src/layout.ts",
      "packages/graph-engine/src/pagerank.ts",
      "tools/graph-layout/src/index.ts",
      "tools/graph-merge/src/index.ts",
    ],
    "the pin table must cover exactly the four sources the port claims",
  );
  for (const [path, digest] of Object.entries(UPSTREAM_PINS.sources)) {
    assert.match(digest, HEX64, `${path} must be pinned by a full sha256, not an 8-char prefix`);
  }
  const artifacts = Object.entries(UPSTREAM_PINS.artifacts);
  assert.equal(artifacts.length, 1);
  assert.match(artifacts[0][1], HEX64);
});

test("the drift check fires: one doctored digest comes back named", () => {
  // The negative control for a pin that would otherwise be unfalsifiable. Same
  // inputs the live leg uses would need the authority, so this builds the
  // smallest surface that is INTERNALLY consistent — every claim true — and then
  // breaks one thing at a time. Each row must produce exactly the one line.
  const base = {
    pins: {
      sources: {
        "tools/graph-merge/src/index.ts": "a".repeat(64),
        "tools/graph-layout/src/index.ts": "b".repeat(64),
        "packages/graph-engine/src/layout.ts": "c".repeat(64),
        "packages/graph-engine/src/pagerank.ts": "d".repeat(64),
      },
      artifacts: { "GR-FULLSEND-1027-CFSG-AXIOM-CENSUS.json": "e".repeat(64) },
    },
    sourceDigests: {
      "tools/graph-merge/src/index.ts": "a".repeat(64),
      "tools/graph-layout/src/index.ts": "b".repeat(64),
      "packages/graph-engine/src/layout.ts": "c".repeat(64),
      "packages/graph-engine/src/pagerank.ts": "d".repeat(64),
    },
    receipt: {
      schemaVersion: RECEIPT_SCHEMA_VERSION,
      status: EVIDENCE_STATUS,
      implementation: {
        "tools/graph-merge/src/index.ts": "a".repeat(64),
        "tools/graph-layout/src/index.ts": "b".repeat(64),
        "packages/graph-engine/src/layout.ts": "c".repeat(64),
        "packages/graph-engine/src/pagerank.ts": "d".repeat(64),
      },
      graph: { nodes: 19916, edges: 45339 },
    },
    layoutSource:
      'const EDGE_KINDS = new Set<GraphEdge["kind"]>([\n  "uses",\n  "instance_of",\n  "extends",\n  "proves",\n]);\n' +
      'const DECL_KINDS = new Set<GraphNode["kind"]>([\n  "theorem",\n  "lemma",\n  "def",\n  "structure",\n  "instance",\n  "inductive",\n  "abbrev",\n  "axiom",\n]);\n' +
      'function normalizeKind(kind) { return kind ? kind : "def"; }',
    harvestSource:
      'kind: "uses" | "imports" | "instance_of" | "extends" | "proves";\n' +
      "export interface DeclRecord {\n  fqn: string;\n  id?: string;\n}\n",
    hubGraph: {
      totals: { decls: 19916 },
      waddles: ["audrey"],
      nodes: [{ id: "audrey::A.lean::A.b", waddle: "audrey", file: "A/B.lean", fqn: "A.b" }],
      edges: [{ kind: "uses" }],
    },
    census: {
      schema: CENSUS_SCHEMA,
      tier_law: "no CFSG statement is machine-checked by this artifact",
      verdict_words: { row_verdicts: [...CENSUS_VERDICTS] },
      exec_leg: { sample: [{}, {}, {}] },
    },
    censusDigest: "e".repeat(64),
    mounted: { graph: { nodes: [] }, refusals: [] },
  };
  // Hand the consistency checks a surface that is INTERNALLY true: the node 0 id
  // must actually be what the law produces, and every mounted node must carry the
  // required fields, or the doctored rows below report two lines instead of one.
  base.hubGraph.nodes[0].id = nodeIdentityBase({
    waddle: "audrey",
    file: "A/B.lean",
    fqn: "A.b",
  });
  base.mounted.graph.nodes = Array.from({ length: 11 }, (_, index) => ({
    ...Object.fromEntries(requiredDeclRecordFields(base.harvestSource).map((field) => [field, 1])),
    fqn: `A.b${index}`,
  }));
  base.mounted.refusals = [
    { code: "probe_rc_nonzero" },
    { code: "probe_rc_nonzero" },
  ];
  base.hubGraph.totals.decls = base.hubGraph.nodes.length;
  base.receipt.graph.nodes = base.hubGraph.nodes.length;
  base.receipt.graph.edges = base.hubGraph.edges.length;

  assert.deepEqual(upstreamDrift(structuredClone(base)), [], "the control surface must be internally consistent");

  const controls = [
    {
      label: "a ported source moved on disk",
      patch: (s) => { s.sourceDigests["tools/graph-merge/src/index.ts"] = "f".repeat(64); },
      expect: /ported source moved: tools\/graph-merge/,
    },
    {
      label: "the bridge pin disagrees with the producer receipt",
      patch: (s) => { s.receipt.implementation["packages/graph-engine/src/pagerank.ts"] = "0".repeat(64); },
      expect: /pin disagrees with the producer receipt: packages\/graph-engine\/src\/pagerank\.ts/,
    },
    {
      label: "the census artifact moved",
      patch: (s) => { s.censusDigest = "1".repeat(64); },
      expect: /census artifact moved/,
    },
    {
      label: "the hub bumped its receipt schemaVersion",
      patch: (s) => { s.receipt.schemaVersion = RECEIPT_SCHEMA_VERSION + 1; },
      expect: /receipt schemaVersion .*!= 3/,
    },
    {
      label: "the layout guard gained an edge kind the mount would refuse",
      patch: (s) => { s.layoutSource = s.layoutSource.replace('"proves",', '"proves",\n  "imports",'); },
      expect: /layout EDGE_KINDS/,
    },
    {
      label: "the harvest dropped a kind from its union",
      patch: (s) => { s.harvestSource = s.harvestSource.replace(' | "extends"', ""); },
      expect: /harvest Edge kind union/,
    },
    {
      label: "an unknown declaration kind no longer floors at def",
      patch: (s) => { s.layoutSource = s.layoutSource.replace(': "def";', ': "theorem";'); },
      expect: /no longer floors an unknown declaration kind/,
    },
    {
      label: "the harvest started publishing kind certificate",
      patch: (s) => { s.layoutSource = s.layoutSource.replace('"axiom",', '"axiom",\n  "certificate",'); },
      expect: /no longer a floor case/,
    },
    {
      label: "DeclRecord made a field this bridge does not carry required",
      patch: (s) => { s.harvestSource = s.harvestSource.replace("  fqn: string;", "  fqn: string;\n  influence: number;"); },
      expect: /lack now-required DeclRecord field influence/,
    },
    {
      label: "the identity law stopped reproducing the published id",
      patch: (s) => { s.hubGraph.nodes[0].file = "A/C.lean"; },
      expect: /identity law no longer reproduces the published id/,
    },
    {
      label: "the published graph edge kinds diversified",
      patch: (s) => { s.hubGraph.edges[0].kind = "proves"; },
      expect: /not the single "uses"/,
    },
    {
      label: "the hub graph gained a cfsg waddle",
      patch: (s) => { s.hubGraph.waddles.push("cfsg"); },
      expect: /no longer missing CFSG declarations/,
    },
    {
      label: "the census verdict vocabulary changed",
      patch: (s) => { s.census.verdict_words.row_verdicts = ["AXIOM_FREE"]; },
      expect: /census verdict vocabulary/,
    },
    {
      label: "the live artifact no longer mounts to 11 nodes and 2 refusals",
      patch: (s) => { s.mounted.refusals.length = 1; },
      expect: /no longer mounts to 11 nodes and 2 refusals/,
    },
    {
      label: "the shape the check parses disappeared",
      patch: (s) => {
        s.harvestSource = s.harvestSource.replace(
          /export interface DeclRecord \{[\s\S]*?\n\}/,
          "export interface DeclarationRecord {}",
        );
      },
      expect: /could not parse required fields of DeclRecord/,
    },
  ];

  for (const control of controls) {
    const doctored = structuredClone(base);
    control.patch(doctored);
    const drift = upstreamDrift(doctored);
    assert.equal(drift.length, 1, `${control.label}: expected exactly one drift line, got ${JSON.stringify(drift)}`);
    assert.match(drift[0], control.expect, `${control.label}: wrong line reported`);
  }
});

/** Every path the live leg reads. Absence of any one of them is UNMEASURED. */
function authorityPaths() {
  return [
    ...Object.keys(UPSTREAM_PINS.sources).map((path) => `${WADDLE_REPO}/${path}`),
    `${WADDLE_REPO}/packages/lean-build-graph/src/index.ts`,
    `${WADDLE_REPO}/apps/hub/data/proof-graph-build-receipt.json`,
    `${WADDLE_REPO}/apps/hub/data/proofs-graph.json`,
    CENSUS_ARTIFACT_PATH,
  ];
}

test("the live proof-graph surface still matches what this bridge claims", (t) => {
  const absent = authorityPaths().filter((path) => !existsSync(path));
  if (absent.length > 0) {
    t.skip(`authority absent: ${absent.join(", ")} — UNMEASURED, not drift`);
    return;
  }
  const surface = readUpstreamSurface();
  const drift = upstreamDrift(surface);
  assert.deepEqual(drift, [], "the bridge's documented upstream surface has moved:\n  " + drift.join("\n  "));
  // Measured receipts, printed so a green run says what it actually checked.
  t.diagnostic(
    `live surface: ${surface.hubGraph.nodes.length} nodes / ${surface.hubGraph.edges.length} edges, ` +
      `node0 ${surface.hubGraph.nodes[0].id}, ` +
      `census mounts ${surface.mounted.graph.nodes.length} nodes + ${surface.mounted.refusals.length} refusals`,
  );
});

