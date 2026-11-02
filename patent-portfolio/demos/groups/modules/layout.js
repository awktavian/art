/**
 * layout.js — the ONE place the CFSG atlas's geometry is decided.
 *
 * Pure data in, pure data out: no DOM, no WebGL, no clocks, no Math.random.
 * The GPU renderer encodes its output into uniform/instance buffers, and the
 * pure-CPU reference rasterizer (tools/reference-raster.mjs) consumes the SAME
 * module — so the pinned determinism artifact and the pixels on screen are
 * projections of one scene description, not two models that can drift.
 *
 * Every coordinate traces back to a datum in data/cfsg-families.json, whose
 * provenance.json sidecar carries `file:line` for each one. This module never
 * invents a number: where CFSG does not pin a quantity (rank for the infinite
 * series, order for the unnamed sporadics) the node carries a typed absence
 * (`rankVaries`, `orderKnown: false`) and the renderer draws that absence
 * instead of hiding it.
 *
 * Semantic encoding — meaning in placement, per the art rules:
 *
 *   height  = Lie rank. CFSG's own rank table (`rankRule`) is a literal
 *             integer for 11 of the 16 order formulas, so those 11 sit on
 *             steps of a ziggurat: Tits at rank 0 on the ground, Suzuki and
 *             Ree at BN-pair rank 1 just above, E8 at rank 8 on top. The five
 *             infinite series have rank "n" — a variable, not a number — so
 *             they get no step: they hover on a shelf labelled "rank varies"
 *             rather than being assigned a fake height.
 *   fold    = Coxeter residue. A node is faceted with m-fold symmetry only
 *             where CFSG states a Cartan matrix; m comes from the largest
 *             off-diagonal product over simple-root pairs, since 4cos²(π/m)
 *             is that product. A twisted type inherits the root system of its
 *             untwisted namesake, so ²G2 folds like G2 and ²F4(2)′ like F4.
 *             Ten of the sixteen do; the rest are smooth, and the legend says
 *             so rather than letting it read as an oversight.
 *   points  = the root system itself, orthogonally projected from rank-space
 *             onto three of its own dimensions by the first three DCT-III
 *             basis vectors. E8's 240 roots are computed by closure under
 *             CFSG's `reflect` rule, so the brightest constellation in the
 *             piece is a measurement, not a decoration.
 *   cluster = the 26 sporadics have no infinite family, so they are the only
 *             territory that is a cluster rather than a ring, with the Monster
 *             at its centre and Y443's twelve Nielsen involutions wired by
 *             CFSG's own adjacency on top of it.
 */

export const LAYOUT_SCHEMA = "v6.cfsg-atlas.layout.1";

/** Scene-space scale: one unit of Lie rank. */
const RANK_STEP = 0.62;
/** Radius of the Lie ziggurat ring around the sporadic cluster. */
const LIE_RING = 8.6;
/** Height of the shelf that carries the five infinite series. */
const SERIES_SHELF = 6.9;
/** Radius of the Fibonacci shell the 25 non-Monster sporadics ride. */
const SPORADIC_SHELL = 3.15;
/** Radius of the two helices carrying the cyclic-prime and alternating arms. */
const ARM_HELIX = 13.2;

const GOLDEN_ANGLE = Math.PI * (3 - Math.sqrt(5));
const FIXED_COLOR = [0.86, 0.90, 1.00];

function clamp(value, lo, hi) {
  return value < lo ? lo : value > hi ? hi : value;
}

/**
 * sRGB triple from a hue in [0,1) and a luminance. Hand-rolled (no THREE, no
 * CSS parse) so the CPU reference rasterizer can call it in node.
 */
function hsv(h, s, v) {
  const hh = (((h % 1) + 1) % 1) * 6;
  const c = v * s;
  const x = c * (1 - Math.abs((hh % 2) - 1));
  const m = v - c;
  let r = 0;
  let g = 0;
  let b = 0;
  if (hh < 1) [r, g, b] = [c, x, 0];
  else if (hh < 2) [r, g, b] = [x, c, 0];
  else if (hh < 3) [r, g, b] = [0, c, x];
  else if (hh < 4) [r, g, b] = [0, x, c];
  else if (hh < 5) [r, g, b] = [x, 0, c];
  else [r, g, b] = [c, 0, x];
  return [r + m, g + m, b + m];
}

/**
 * Characteristic → hue. The small characteristics are the atlas's colour
 * language: p = 2 is ice, p = 3 gold, larger p climbs toward magenta; groups
 * with no stated characteristic (the permutation carriers, the sporadic
 * cluster at large) read as cool white.
 */
export function colorForCharacteristic(p) {
  if (p === 2) return hsv(0.503, 0.85, 0.98);
  if (p === 3) return hsv(0.128, 0.82, 0.96);
  if (p === 5) return hsv(0.02, 0.80, 0.92);
  if (p === 7) return hsv(0.93, 0.72, 0.90);
  if (p === 11) return hsv(0.79, 0.68, 0.88);
  if (typeof p === "number") return hsv(0.66, 0.5, 0.8);
  return hsv(0.58, 0.10, 0.95);
}

/**
 * The manifold's polar fold angle. π/3 is the simply-laced Coxeter angle —
 * c_ij·c_ji = 1 ⇒ 4cos²θ = 1 ⇒ θ = π/3, m = 3 — i.e. the ADE lattice that
 * five of the seven stated Cartan matrices live in. The raymarched lattice
 * folds on it; each carved node then folds again on its own residue.
 */
export const LIE_FOLD_ANGLE = Math.PI / 3;

/** Largest 4*cos^2(pi/m) residue over adjacent simple-root pairs. */
function coxeterResidue(cartan) {
  let best = { product: 0, i: -1, j: -1 };
  for (let i = 0; i < cartan.length; i += 1) {
    for (let j = 0; j < cartan.length; j += 1) {
      if (i === j) continue;
      const product = cartan[i][j] * cartan[j][i];
      if (product > best.product) best = { product, i, j };
    }
  }
  if (best.product <= 0) return null;
  // 4 cos^2(theta) = c_ij * c_ji for the pair, theta = pi/m.
  const cosTheta = clamp(Math.sqrt(best.product) / 2, -1, 1);
  const theta = Math.acos(cosTheta);
  return {
    product: best.product,
    pair: [best.i, best.j],
    theta,
    m: Math.max(2, Math.round(Math.PI / theta)),
  };
}

/**
 * First three DCT-III basis vectors of R^rank: an orthogonal projection of
 * the root lattice onto three of its own dimensions. Deterministic integer/
 * float math, no RNG.
 */
function projectionFrame(rank) {
  const rows = [];
  for (let k = 0; k < 3; k += 1) {
    const row = [];
    let norm = 0;
    for (let j = 0; j < rank; j += 1) {
      const v = Math.cos((Math.PI * (j + 1) * (2 * k + 1)) / (2 * rank + 2));
      row.push(v);
      norm += v * v;
    }
    const inv = 1 / Math.sqrt(norm);
    rows.push(row.map((v) => v * inv));
  }
  return rows;
}

function projectRoot(frame, root) {
  const out = [0, 0, 0];
  for (let k = 0; k < 3; k += 1) {
    let acc = 0;
    for (let j = 0; j < root.length; j += 1) acc += frame[k][j] * root[j];
    out[k] = acc;
  }
  return out;
}

/** Base-10 exponent of a decimal-string order, to three places. */
function log10OfString(value) {
  const s = String(value).trim();
  if (!/^[0-9]+$/.test(s)) return null;
  const n = BigInt(s);
  if (n <= 0n) return null;
  const digits = s.length;
  const lead = Number(s.slice(0, 4));
  return digits - 4 + Math.log10(lead);
}

/** Name→type pairing, matching the data's own `by-name-correspondence` tag. */
function typeByName(displayName, tagEnum) {
  // E6(q), F4(q), G2(q), … — the untwisted types state their root system.
  for (const tag of tagEnum) {
    if (displayName.startsWith(`${tag}(`)) return tag;
  }
  // ^2E6(q), ^2F4(q) and ^3D4(q) carry their untwisted type's root system:
  // the twist acts on the diagram, not on the rank.
  for (const tag of tagEnum) {
    if (displayName.startsWith(`^2${tag}(`) || displayName.startsWith(`^3${tag}(`)) return tag;
  }
  return null;
}

function buildLieNodes(data) {
  const families = data.lieFamilies;
  const exceptional = data.exceptional;
  const tagEnum = exceptional._meta.tagEnum;

  const ids = Object.keys(families).filter(
    (k) => k !== "characteristicRule" && k !== "familySet" && k !== "tags",
  );
  const seriesIds = ids.filter((id) => !/^\d+$/.test(String(families[id].rankRule)));
  const nodes = [];
  ids.forEach((id, index) => {
    const fam = families[id];
    const rankLiteral = /^\d+$/.test(String(fam.rankRule));
    const rank = rankLiteral ? Number(fam.rankRule) : null;
    const type = typeByName(fam.displayName, tagEnum);
    const roots = type ? exceptional[type].roots : null;
    const cartan = type ? exceptional[type].cartan : null;
    const cox = cartan ? coxeterResidue(cartan) : null;
    const samples = fam.sampleOrders || [];

    // Fixed-rank types take a step of the ziggurat; the series share the shelf.
    const angle = (index / ids.length) * Math.PI * 2;
    let pos;
    if (rank === null) {
      const shelfIndex = seriesIds.indexOf(id);
      const spread = ((shelfIndex - (seriesIds.length - 1) / 2) * Math.PI) / 26;
      pos = [
        Math.cos(angle + spread) * (LIE_RING - 1.9),
        SERIES_SHELF,
        Math.sin(angle + spread) * (LIE_RING - 1.9),
      ];
    } else {
      pos = [
        Math.cos(angle) * LIE_RING,
        (rank - 3) * RANK_STEP,
        Math.sin(angle) * LIE_RING,
      ];
    }

    const maxSample = samples.reduce(
      (best, s) => Math.max(best, log10OfString(s.order) ?? 0),
      0,
    );
    nodes.push({
      id,
      kind: "lie",
      label: fam.displayName,
      familyId: id,
      pos,
      radius: 0.44 + 0.16 * clamp(maxSample / 12, 0, 1) + (type ? 0.1 : 0),
      rank,
      rankVaries: rank === null,
      rankRule: fam.rankRule,
      params: fam.params,
      formula: fam.formula,
      type,
      cartan,
      coxeter: cox,
      rootCount: roots ? roots.length : null,
      positiveCount: type ? exceptional[type].positiveCount : null,
      samples,
      colorSeed: null,
      rankCite: type ? exceptional[type].rankCite : null,
      isRootCite: exceptional._meta.isRootCite,
      reflectRuleCite: exceptional._meta.reflectCite,
      pointer: `/lieFamilies/${id}`,
    });
  });
  return nodes;
}

function buildSporadicNodes(data) {
  const sporadics = data.sporadics;
  const orders = data.sporadicOrders;
  const namedOrders = orders.named || {};
  const pinned = orders.theoremPinned || {};
  const enumeration = (sporadics._carrierEnumeration || []).map((row) => row.carrier);
  const names = enumeration.length === 26
    ? enumeration
    : Object.keys(sporadics).filter((k) => k !== "_carrierEnumeration");

  // Sizes are a ratio, so normalise against the largest order CFSG names.
  const maxLog = Math.max(
    ...Object.values(namedOrders).map((row) => log10OfString(row.value) ?? 0),
    ...Object.values(pinned).map((row) => log10OfString(row.value) ?? 0),
    1,
  );

  return names.map((name, index) => {
    const entry = sporadics[name] || {};
    const row = namedOrders[name] || pinned[name] || null;
    const orderValue = row ? row.value : null;
    const orderLog = orderValue === null ? null : log10OfString(orderValue);
    const isMonster = name === "M";
    const size = orderLog === null
      ? 0.34 + 0.1 * clamp(Math.log10(Math.max(1, entry.representationDegree || 1)) / 4, 0, 1)
      : 0.3 + 1.05 * Math.sqrt(clamp(orderLog / maxLog, 0, 1));

    let pos;
    if (isMonster) {
      pos = [0, 0, 0];
    } else {
      // Fibonacci shell: the golden angle makes 25 sites without clustering.
      const y = 1 - 2 * ((index % 25) / 24);
      const r = Math.sqrt(Math.max(0, 1 - y * y));
      const theta = GOLDEN_ANGLE * index;
      pos = [
        Math.cos(theta) * r * SPORADIC_SHELL,
        y * SPORADIC_SHELL * 0.78,
        Math.sin(theta) * r * SPORADIC_SHELL,
      ];
    }

    const cycles = Array.isArray(entry.generatorCycles) ? entry.generatorCycles : null;
    return {
      id: `sp:${name}`,
      kind: "sporadic",
      label: name,
      sporadicName: name,
      // CFSG does not give a sporadic group a Lie rank: record the absence the
      // same way the Lie series do (`null`), not by omitting the key, so every
      // consumer reads one shape.
      rank: null,
      rankVaries: false,
      pos,
      radius: size,
      characteristic: typeof entry.characteristic === "number" ? entry.characteristic : null,
      representationDegree: typeof entry.representationDegree === "number" ? entry.representationDegree : null,
      model: entry.model || null,
      seedMode: typeof entry.seedMode === "number" ? entry.seedMode : null,
      seedFiles: entry.seedFiles || null,
      degree: typeof entry.degree === "number" ? entry.degree : null,
      generatorCycles: cycles,
      generatorImages: entry.generatorImages || null,
      orderValue,
      orderLog,
      orderKnown: orderValue !== null,
      orderFactorization: row ? row.factorization : null,
      orderCite: row ? row.cite : null,
      colorSeed: null,
      pointer: `/sporadics/${name}`,
      cite: entry.cite || entry.definitionCite || null,
    };
  });
}

/** Y443: twelve Nielsen involutions, wired by CFSG's own adjacency list. */
function buildY443(data, monsterNode) {
  const y = data.monsterY443;
  if (!y) return { points: [], filaments: [] };
  const scale = monsterNode.radius * 1.62;
  const points = [];
  for (let i = 0; i < y.generatorCount; i += 1) {
    const theta = GOLDEN_ANGLE * i * 2;
    const y0 = 1 - 2 * (i / (y.generatorCount - 1));
    const r = Math.sqrt(Math.max(0, 1 - y0 * y0));
    points.push({
      pos: [
        monsterNode.pos[0] + Math.cos(theta) * r * scale,
        monsterNode.pos[1] + y0 * scale,
        monsterNode.pos[2] + Math.sin(theta) * r * scale,
      ],
      index: i,
      kind: "y443",
      cite: y.adjacencyCite,
    });
  }
  const filaments = y.adjacency.map(([a, b], i) => ({
    kind: "y443-edge",
    from: points[a].pos,
    to: points[b].pos,
    index: i,
    cite: y.adjacencyCite,
    label: `x${a}-x${b}`,
  }));
  return { points, filaments, relatorFamilies: y.relatorFamilies, presented: y.presentedGroup };
}

/** The root systems, projected: the piece's brightest and most literal data. */
function buildRootPoints(lieNodes) {
  const points = [];
  for (const node of lieNodes) {
    if (!node.type || !node.cartan || !node.rootList) continue;
    const frame = projectionFrame(node.cartan.length);
    const scale = node.radius * 2.35;
    for (let r = 0; r < node.rootList.length; r += 1) {
      const root = node.rootList[r];
      const p = projectRoot(frame, root);
      const len = Math.hypot(p[0], p[1], p[2]) || 1;
      // Height of the root above the simple-root basis, in the source's own
      // integer coordinates: the sphere's radius grows with it, so the shell
      // structure of the root system reads as depth.
      const height = root.reduce((a, b) => a + Math.abs(b), 0) / root.length;
      const shell = 0.55 + 0.45 * clamp(height / 3, 0, 1);
      points.push({
        pos: [
          node.pos[0] + (p[0] / len) * scale * shell,
          node.pos[1] + (p[1] / len) * scale * shell,
          node.pos[2] + (p[2] / len) * scale * shell,
        ],
        kind: "root",
        family: node.id,
        type: node.type,
        root: r,
        height,
        cite: node.rankCite,
      });
    }
  }
  return points;
}

/** Diagram automorphisms as real edges: ^3D4's triality and the ^2E6 fold. */
function buildDiagramEdges(data, lieNodes) {
  const byType = new Map();
  for (const node of lieNodes) if (node.type) byType.set(node.type, node);
  const filaments = [];
  const auto = data.diagramAutomorphisms || {};
  for (const [type, row] of Object.entries(auto)) {
    const anchor = byType.get(type);
    if (!anchor) continue;
    for (const [a, b] of row.swaps) {
      // A swap of simple-root indices becomes a chord across the node's shell.
      const theta = (a / Math.max(1, anchor.cartan.length)) * Math.PI * 2;
      const theta2 = (b / Math.max(1, anchor.cartan.length)) * Math.PI * 2;
      const r = anchor.radius * 2.1;
      filaments.push({
        kind: "diagram-automorphism",
        from: [
          anchor.pos[0] + Math.cos(theta) * r,
          anchor.pos[1] + Math.sin(theta) * r * 0.4,
          anchor.pos[2] + Math.sin(theta) * r,
        ],
        to: [
          anchor.pos[0] + Math.cos(theta2) * r,
          anchor.pos[1] + Math.sin(theta2) * r * 0.4,
          anchor.pos[2] + Math.sin(theta2) * r,
        ],
        type,
        swap: [a, b],
        cite: row.cite,
        label: `${type}: ${a}↔${b}`,
      });
    }
  }
  return filaments;
}

/** Cycle structure drawn literally: each generator's cycles as chords. */
function buildCycleFilaments(sporadicNodes) {
  const filaments = [];
  for (const node of sporadicNodes) {
    if (!node.generatorCycles) continue;
    const d = Math.max(2, node.degree || 1);
    const r = node.radius * 1.5;
    node.generatorCycles.forEach((cycles, gIndex) => {
      for (const cycle of cycles) {
        if (cycle.length < 2) continue;
        for (let k = 0; k < cycle.length; k += 1) {
          const a = cycle[k];
          const b = cycle[(k + 1) % cycle.length];
          const pa = ((a / d) * Math.PI * 2) + gIndex * 0.35;
          const pb = ((b / d) * Math.PI * 2) + gIndex * 0.35;
          filaments.push({
            kind: "cycle",
            from: [
              node.pos[0] + Math.cos(pa) * r,
              node.pos[1] + Math.sin(pa * 2) * r * 0.35,
              node.pos[2] + Math.sin(pa) * r,
            ],
            to: [
              node.pos[0] + Math.cos(pb) * r,
              node.pos[1] + Math.sin(pb * 2) * r * 0.35,
              node.pos[2] + Math.sin(pb) * r,
            ],
            group: node.sporadicName,
            generator: gIndex,
            cite: node.cite,
            label: `(${cycle.join(" ")})`,
          });
        }
      }
    });
  }
  return filaments;
}

/** The other two arms of knownSimpleOrders, as two helices of order points. */
function buildArmHelices(data) {
  const points = [];
  const arms = data.classification;
  arms.cyclicPrimeSeries.forEach((row, i) => {
    const theta = i * GOLDEN_ANGLE * 1.7;
    const rise = (i / arms.cyclicPrimeSeries.length) * 7.5 - 3.4;
    const r = ARM_HELIX + rise * 0.22;
    points.push({
      pos: [Math.cos(theta) * r, rise, Math.sin(theta) * r],
      kind: "arm:cyclicPrime",
      value: row.order,
      factorization: row.factorization,
      p: row.p,
      cite: arms.arms[0].cite,
      label: `C_${row.p}`,
    });
  });
  arms.alternatingSeries.forEach((row, i) => {
    const theta = -i * GOLDEN_ANGLE * 1.7 + 1.1;
    const rise = -(i / arms.alternatingSeries.length) * 7.5 + 3.4;
    const r = ARM_HELIX * 0.86 + rise * 0.22;
    points.push({
      pos: [Math.cos(theta) * r, rise, Math.sin(theta) * r],
      kind: "arm:alternating",
      value: row.order,
      factorization: row.factorization,
      n: row.n,
      cite: arms.arms[1].cite,
      label: `A_${row.n}`,
    });
  });
  return points;
}

/** Sub-orbit ring: the nine 2A suborbits of the Monster, as a real cycle. */
function buildSuborbitRing(data, monsterNode) {
  const sub = data.monsterSuborbit2A;
  if (!sub) return { points: [], filaments: [] };
  const scale = monsterNode.radius * 1.18;
  const points = sub.elementOrders.map((order, i) => {
    const theta = (i / sub.elementOrders.length) * Math.PI * 2;
    return {
      pos: [
        monsterNode.pos[0] + Math.cos(theta) * scale,
        monsterNode.pos[1] - scale * 0.42,
        monsterNode.pos[2] + Math.sin(theta) * scale,
      ],
      kind: "suborbit",
      index: i,
      elementOrder: order,
      quotient: sub.simpleQuotients[i],
      cite: sub.elementOrderCite,
    };
  });
  const filaments = points.slice(0, -1).map((p, i) => ({
    kind: "suborbit-edge",
    from: p.pos,
    to: points[i + 1].pos,
    cite: sub.indexing ? sub.simpleQuotientCite : null,
    label: `2A[${i}]→2A[${i + 1}]`,
  }));
  return { points, filaments };
}

/**
 * Flythrough pose at a phase in [0,1). Pure and closed-form so the browser's
 * camera and the reference rasterizer's camera are the same function: a slow
 * great-circle orbit whose radius breathes on a 3-fold and whose height sweeps
 * the ziggurat's own rank range. One full turn is 610 × 10 ms — Fibonacci
 * timing, per the house convention.
 */
export const CAMERA_PERIOD_MS = 6100;
export function cameraPoseAt(phase, camera) {
  const a = phase * Math.PI * 2;
  const r = camera.radius + Math.cos(a * 3) * camera.breathe;
  return [
    Math.cos(a) * r,
    camera.height * 0.45 + Math.sin(a * 2) * camera.height,
    Math.sin(a) * r,
  ];
}

const CAMERA = {
  radius: 21.5,
  breathe: 2.4,
  height: 3.1,
  target: [0, 0.6, 0],
  fovYDeg: 42,
  periodMs: CAMERA_PERIOD_MS,
};

/**
 * @param {object} data     parsed data/cfsg-families.json
 * @param {object} [prov]   parsed data/provenance.json (for the pointer audit)
 * @returns the scene description the renderer, the picker and the rasterizer
 *          all read, plus a `stats` block the HUD quotes verbatim.
 */
export function buildLayout(data, prov) {
  const lieNodes = buildLieNodes(data);
  for (const node of lieNodes) {
    // Roots travel with their node so the fold geometry and the point
    // constellation come from one source; stripped again below.
    node.rootList = node.type ? data.exceptional[node.type].roots : [];
  }

  const sporadicNodes = buildSporadicNodes(data);
  const monster = sporadicNodes.find((n) => n.sporadicName === "M") || sporadicNodes[0];
  const y443 = buildY443(data, monster);
  const suborbit = buildSuborbitRing(data, monster);

  const rootPoints = buildRootPoints(lieNodes);
  const diagramFilaments = buildDiagramEdges(data, lieNodes);
  const cycleFilaments = buildCycleFilaments(sporadicNodes);

  const nodes = [...lieNodes, ...sporadicNodes];
  for (const node of nodes) {
    if (node.kind === "lie") {
      node.color = node.cartan
        ? hsv(0.5 + 0.055 * node.cartan.length, 0.72, 0.95)
        : FIXED_COLOR;
    } else {
      node.color = colorForCharacteristic(node.characteristic);
    }
    delete node.rootList;
  }

  const points = [...rootPoints, ...y443.points, ...suborbit.points, ...buildArmHelices(data)];
  const filaments = [...diagramFilaments, ...y443.filaments, ...suborbit.filaments, ...cycleFilaments];

  const stats = {
    layoutSchema: LAYOUT_SCHEMA,
    lieFamilies: lieNodes.length,
    lieTagRows: data.lieFamilies.tags.length,
    fixedRankTypes: lieNodes.filter((n) => n.rank !== null).length,
    seriesWithVariableRank: lieNodes.filter((n) => n.rankVaries).length,
    coxeterFolded: lieNodes.filter((n) => n.cartan).length,
    rootPoints: rootPoints.length,
    sporadics: sporadicNodes.length,
    sporadicsWithPinnedOrder: sporadicNodes.filter((n) => n.orderKnown).length,
    y443Edges: y443.filaments.length,
    diagramEdges: diagramFilaments.length,
    cycleEdges: cycleFilaments.length,
    suborbitPoints: suborbit.points.length,
    armPoints: points.filter((p) => p.kind.startsWith("arm:")).length,
    nodes: nodes.length,
    filaments: filaments.length,
    points: points.length,
    selfChecksPassed: (data.meta.selfChecks || []).filter((c) => c.pass).length,
    selfChecksTotal: (data.meta.selfChecks || []).length,
    // `prov` is the reader from describe.js: it knows whether the sidecar was
    // actually loaded, which is not the same as having zero pointers.
    provenancePointers: prov && prov.loaded ? prov.count : null,
    sourceCommit: data.meta.sourceCommit,
    sourceRepo: data.meta.sourceRepo,
  };

  return {
    nodes,
    points,
    filaments,
    camera: CAMERA,
    stats,
    y443: { relatorFamilies: y443.relatorFamilies, presented: y443.presented, adjacencyCite: data.monsterY443.adjacencyCite },
    suborbit,
    arms: data.classification.arms,
    meta: data.meta,
  };
}

/**
 * Node → instance buffer. Fixed stride, little-endian float32; the same
 * function runs in node for the reference rasterizer's pin.
 */
export const NODE_STRIDE = 16;
export function encodeNodes(nodes) {
  const out = new Float32Array(nodes.length * NODE_STRIDE);
  nodes.forEach((n, i) => {
    const o = i * NODE_STRIDE;
    out[o + 0] = n.pos[0];
    out[o + 1] = n.pos[1];
    out[o + 2] = n.pos[2];
    out[o + 3] = n.radius;
    out[o + 4] = n.color[0];
    out[o + 5] = n.color[1];
    out[o + 6] = n.color[2];
    // theta = Coxeter half-angle; 0 marks "no Cartan matrix in the source".
    out[o + 7] = n.coxeter ? n.coxeter.theta : 0;
    out[o + 8] = n.kind === "lie" ? 0 : 1;
    out[o + 9] = n.coxeter ? n.coxeter.m : 0;
    // -1 is the shader's "no rank in the source" sentinel. Written defensively:
    // a sporadic node simply has no `rank` key, and `undefined === null` is
    // false, which turned this slot into NaN for all 26 sporadics (a NaN in an
    // instance attribute is undefined behaviour on the GPU, not a black pixel).
    out[o + 10] = Number.isFinite(n.rank) ? n.rank : -1;
    out[o + 11] = n.orderKnown ? clamp((n.orderLog || 0) / 54, 0, 1) : -1;
    out[o + 12] = n.characteristic || 0;
    out[o + 13] = n.rootCount || 0;
    out[o + 14] = i;
    out[o + 15] = 0;
  });
  return out;
}

export const POINT_STRIDE = 8;
/**
 * Slot order is the attribute order the renderer binds: pos(3) kind(1)
 * size(1) id(1) arm(1) pad(1). `arm` is carried for the shader's benefit and
 * is currently unread by VS_POINTS — it stays in the buffer so an arm glow can
 * be added without repacking.
 */
export function encodePoints(points) {
  const out = new Float32Array(points.length * POINT_STRIDE);
  points.forEach((p, i) => {
    const o = i * POINT_STRIDE;
    out[o + 0] = p.pos[0];
    out[o + 1] = p.pos[1];
    out[o + 2] = p.pos[2];
    out[o + 3] = p.kind === "root" ? 1 : p.kind === "y443" ? 2 : p.kind === "suborbit" ? 3 : 4;
    out[o + 4] = p.kind === "root" ? 0.55 : p.kind.startsWith("arm") ? 0.34 : 0.4;
    out[o + 5] = i;
    out[o + 6] = p.kind.startsWith("arm") ? 1 : 0;
    out[o + 7] = 0;
  });
  return out;
}

/**
 * CPU-side palette for the two additive passes. The reference rasterizer needs
 * an RGB per kind; the GPU gets its tone index through `encodeFilaments` /
 * `encodePoints` and picks the colour in GLSL. This table is a hand mirror of
 * that switch — it exists so the CPU tier can draw the same objects, and it is
 * NOT asserted to be pixel-identical to them.
 */
export const CPU_KIND_RGB = {
  root: [0.62, 0.92, 1.00],
  y443: [1.00, 0.78, 0.28],
  suborbit: [0.86, 0.72, 1.00],
  "arm:cyclicPrime": [0.98, 0.36, 0.44],
  "arm:alternating": [0.98, 0.96, 0.90],
  cycle: [0.55, 0.85, 0.95],
  "y443-edge": [1.00, 0.80, 0.30],
  "diagram-automorphism": [0.72, 0.60, 1.00],
  "suborbit-edge": [0.95, 0.50, 0.60],
};
export function rgbForKind(kind) {
  return CPU_KIND_RGB[kind] || [0.85, 0.85, 0.90];
}

export const FILAMENT_STRIDE = 10;
const FILAMENT_TONE = { cycle: 0, "y443-edge": 1, "diagram-automorphism": 2, "suborbit-edge": 3 };
export function encodeFilaments(filaments) {
  const out = new Float32Array(filaments.length * FILAMENT_STRIDE);
  filaments.forEach((f, i) => {
    const o = i * FILAMENT_STRIDE;
    out[o + 0] = f.from[0];
    out[o + 1] = f.from[1];
    out[o + 2] = f.from[2];
    out[o + 3] = f.to[0];
    out[o + 4] = f.to[1];
    out[o + 5] = f.to[2];
    // Half-widths in VIEW units, deliberately narrow: 162 ribbons cross the
    // middle of the cluster, and a wide ribbon there stops reading as a
    // relation and starts reading as a plate of glass (seen in a render).
    out[o + 6] = f.kind === "diagram-automorphism" ? 0.62 : f.kind === "y443-edge" ? 0.5
      : f.kind === "suborbit-edge" ? 0.38 : 0.2;
    out[o + 7] = FILAMENT_TONE[f.kind] ?? 3;
    out[o + 8] = i;
    out[o + 9] = 0;
  });
  return out;
}

/**
 * Ray/sphere pick — CPU-side, so hover agrees between the browser and the
 * pinned reference implementation without a GPU read-back.
 * @returns the index of the nearest node hit, or -1.
 */
export function pickNode(nodes, origin, direction) {
  const dl = Math.hypot(direction[0], direction[1], direction[2]);
  if (!(dl > 0)) return -1;
  const dx = direction[0] / dl;
  const dy = direction[1] / dl;
  const dz = direction[2] / dl;
  let best = -1;
  let bestT = Infinity;
  for (let i = 0; i < nodes.length; i += 1) {
    const n = nodes[i];
    const ox = origin[0] - n.pos[0];
    const oy = origin[1] - n.pos[1];
    const oz = origin[2] - n.pos[2];
    const b = 2 * (ox * dx + oy * dy + oz * dz);
    const c = ox * ox + oy * oy + oz * oz - n.radius * n.radius;
    const disc = b * b - 4 * c;
    if (disc < 0) continue;
    const t = (-b - Math.sqrt(disc)) / 2;
    if (t > 0.001 && t < bestT) {
      bestT = t;
      best = i;
    }
  }
  return best;
}
