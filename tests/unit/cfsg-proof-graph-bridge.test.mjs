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
 *   3. CONSUMABILITY. The triple (receipt, graph, layout) must pass the 12 refusal
 *      legs of the gate the Hub's own read runs — ported here as
 *      `assertHubReceiptConsistent`, with negative controls that prove the gate
 *      FIRES. A green gate with no negative control is not a verified gate; it is
 *      an unexercised branch. (This is the exact class of hole recorded in
 *      `apps/hub/lib/proof-artifacts-cache.ts:196-203`: the hub carried its own
 *      literal `schemaVersion !== 2`, the generator bumped to v3, and no test
 *      pinned the copy, so the break surfaced only at runtime.)
 *
 * The census fixture below is a verbatim recording of
 * `~/.kagami/solver-certs/GR-FULLSEND-1027-CFSG-AXIOM-CENSUS.json`
 * (sha256 68f0a35d44fbb136713c1adafd8f08c74c12dd6a742e3d815884ab916a27a6e8,
 * read 2026-11-02), inlined rather than read at test time so the suite stays
 * offline and host-independent, exactly like `tests/unit/corpus-stats.test.mjs`
 * keeps its inputs in-process.
 */
import assert from "node:assert/strict";
import test from "node:test";

import {
  CENSUS_SCHEMA,
  CENSUS_VERDICTS,
  CERTIFICATE_NODE_KIND,
  LAYOUT_EDGE_KINDS,
  PRODUCER_EDGE_KINDS,
  RECEIPT_SCHEMA_VERSION,
  EVIDENCE_STATUS,
  assertHubMountable,
  assertHubReceiptConsistent,
  buildCertificateGraph,
  computeFoundationalPageRank,
  encodeIdentityComponent,
  layoutHierarchical,
  nodeIdentityBase,
  normalizeEdgeKind,
  planNodeIds,
  serializeCertificateGraph,
} from "../../patent-portfolio/lib/cfsg-proof-graph-bridge.mjs";

/** Twelve of the artifact's 13 sample rows; the 13th (a duplicate of row 1's
 *  identity) is appended only by the collision test. */
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
  // The Hub's own layout guard refuses the same thing (graph-layout/src/index.ts:126).
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

test("the receipt gate FIRES on every one of the four ways a triple can disagree", () => {
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
