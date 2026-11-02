/**
 * describe.js — what the hover panel says, computed without a DOM.
 *
 * The panel is a thin projection of two things: the node the layout produced,
 * and the provenance sidecar the generator wrote. A row is only rendered when
 * the datum exists, and each row carries the `file:line` its generator recorded
 * plus the attribution tag it earned — `asserted` (CFSG states it), `derived`
 * (read off a structure CFSG states), or `computed` (calculated here from
 * CFSG's own rules). Where CFSG genuinely does not name something — the order of
 * a sporadic that `sporadicOrderList` carries as an unnamed Finset element — the
 * panel says so in those words instead of inventing a number. That absence is a
 * row like any other, and the tests assert its shape.
 */

const ATTRIBUTION_WORDS = {
  asserted: "stated in CFSG",
  derived: "read off CFSG's structure",
  computed: "computed from CFSG's rules",
};

export function attributionWord(tag) {
  return ATTRIBUTION_WORDS[tag] || tag || "unlabelled";
}

/** `cfsg/CFSG/Open/Defs.lean:12` — the sidecar's own path, verbatim. */
export function citeOf(entry) {
  if (!entry) return null;
  return `${entry.file}:${entry.line}`;
}

function row(label, value, opts = {}) {
  return {
    label,
    value,
    cite: opts.cite || null,
    attribution: opts.attribution || null,
    absent: opts.absent === true,
    tone: opts.tone || "normal",
  };
}

export function makeProvenanceReader(provenance) {
  const pointers = (provenance && provenance.pointers) || {};
  const children = (pointer) => {
    const prefix = `${pointer}/`;
    const out = [];
    for (const key of Object.keys(pointers)) {
      if (key.startsWith(prefix)) out.push({ pointer: key, ...pointers[key] });
    }
    return out.sort((a, b) => (a.pointer < b.pointer ? -1 : 1));
  };
  return {
    loaded: !!provenance,
    has: (pointer) => Object.prototype.hasOwnProperty.call(pointers, pointer),
    at: (pointer) => pointers[pointer] || null,
    cite: (pointer) => citeOf(pointers[pointer]),
    children,
    count: Object.keys(pointers).length,
    source: provenance ? provenance.source : null,
  };
}

function cyclesToString(cycles) {
  return cycles
    .map((perm) => perm
      .filter((c) => c.length > 1)
      .map((c) => `(${c.join(" ")})`)
      .join("") || "identity")
    .join("  ·  ");
}

function factorizationOf(order) {
  return order && order.factorization ? order.factorization : null;
}

function describeLie(node, data, prov) {
  const rows = [];
  const family = data.lieFamilies[node.familyId] || {};
  rows.push(row("Order polynomial", family.formula || node.formula, {
    cite: prov.cite(`/lieFamilies/${node.familyId}/formula`) || prov.cite(`/lieFamilies/${node.familyId}`),
    attribution: "asserted",
  }));
  rows.push(row(
    "Lie rank",
    node.rank === null ? `n — varies (the series is what fixes the group, not the rank)` : String(node.rank),
    {
      cite: prov.cite(`/lieFamilies/${node.familyId}/rankRule`) || prov.cite(`/lieFamilies/${node.familyId}`),
      attribution: node.rank === null ? "derived" : "asserted",
      absent: node.rank === null,
    },
  ));
  if (node.cartan) {
    rows.push(row("Cartan matrix", node.cartan.map((r) => `[${r.join(" ")}]`).join(" "), {
      cite: prov.cite(`/exceptional/${node.type}/cartan`) || node.rankCite,
      attribution: "asserted",
    }));
    rows.push(row(
      "Coxeter residue",
      `4·cos²(π/m) = ${node.coxeter.product} on simple pair (${node.coxeter.pair.join(", ")}) → m = ${node.coxeter.m}, θ = ${node.coxeter.theta.toFixed(4)} rad`,
      { cite: node.rankCite, attribution: "computed", tone: "accent" },
    ));
    rows.push(row("Roots", `${node.rootCount} (${node.positiveCount} positive)`, {
      cite: prov.cite(`/exceptional/${node.type}/rootCount`) || node.isRootCite,
      attribution: "computed",
    }));
    rows.push(row("Root rule", `basis vectors, closed under v − (Σⱼ cartanᵢⱼ vⱼ)·eᵢ`, {
      cite: node.reflectRuleCite,
      attribution: "asserted",
    }));
  } else {
    rows.push(row("Cartan matrix", "not stated in the source for this family — the node is drawn smooth", {
      attribution: "derived",
      absent: true,
    }));
  }
  const params = (family.params || []).join(", ");
  rows.push(row("Parameters", params || "none — q is fixed by the definition", {
    cite: prov.cite(`/lieFamilies/${node.familyId}/params`) || prov.cite(`/lieFamilies/${node.familyId}`),
    attribution: "asserted",
  }));
  const tags = (data.lieFamilies.tags || []).filter((t) => t.orderFormula === node.familyId);
  for (const tag of tags) {
    rows.push(row(`Tag ${tag.tag}`, `admissible: ${tag.admissible}`, {
      cite: prov.cite(`/lieFamilies/tags`) || tag.tagCite,
      attribution: "asserted",
    }));
  }
  (family.sampleOrders || []).forEach((s, i) => {
    const label = s.n === null ? `q = ${s.q}` : `n = ${s.n}, q = ${s.q}`;
    rows.push(row(`|${node.type || node.familyId}|(${label})`, `${s.order}  =  ${s.factorization}`, {
      cite: prov.cite(`/lieFamilies/${node.familyId}/sampleOrders`) || prov.cite(`/lieFamilies/${node.familyId}`),
      attribution: "computed",
    }));
    void i;
  });
  return rows;
}

function describeSporadic(node, data, prov) {
  const rows = [];
  const entry = data.sporadics[node.sporadicName] || {};
  if (node.orderKnown) {
    rows.push(row("Order", `${node.orderValue}  =  ${node.orderFactorization}`, {
      cite: node.orderCite || prov.cite(`/sporadicOrders/named/${node.sporadicName}`),
      attribution: "asserted",
      tone: "accent",
    }));
  } else {
    rows.push(row("Order",
      "in sporadicOrderList but not named there — CFSG carries the 26 orders as an unnamed Finset, so no group is pinned to this value",
      { cite: prov.cite("/sporadicOrders/asWritten"), attribution: "derived", absent: true }));
  }
  rows.push(row("Carrier", entry.model || "not stated", {
    cite: node.cite || prov.cite(`/sporadics/${node.sporadicName}`),
    attribution: "asserted",
    absent: !entry.model,
  }));
  if (typeof entry.characteristic === "number") {
    rows.push(row("Characteristic", `p = ${entry.characteristic}`, {
      cite: prov.cite(`/sporadics/${node.sporadicName}/characteristic`) || node.cite,
      attribution: "asserted",
    }));
  }
  if (typeof entry.representationDegree === "number") {
    rows.push(row("Module degree", String(entry.representationDegree), {
      cite: prov.cite(`/sporadics/${node.sporadicName}/representationDegree`) || node.cite,
      attribution: "asserted",
    }));
  }
  if (Array.isArray(entry.seedFiles)) {
    rows.push(row("Seed file", `${entry.seedFiles.join(", ")}  (mode ${entry.seedMode})`, {
      cite: prov.cite(`/sporadics/${node.sporadicName}/seedFiles`) || entry.seedCite,
      attribution: "asserted",
    }));
  }
  if (typeof entry.degree === "number") {
    rows.push(row("Permutation degree", String(entry.degree), {
      cite: prov.cite(`/sporadics/${node.sporadicName}/degree`) || node.cite,
      attribution: "asserted",
    }));
  }
  if (Array.isArray(entry.generatorCycles)) {
    rows.push(row("Generators", cyclesToString(entry.generatorCycles), {
      cite: node.cite,
      attribution: "asserted",
      tone: "mono",
    }));
  }
  const cert = (data.mathieuCertificates.groups || []).find((g) => g.name === node.sporadicName);
  if (cert) {
    rows.push(row("Schreier certificate", `base ${cert.base.join(", ")} · ${cert.strongGenerators.length} strong generators · ${cert.sylows.length} Sylow blocks`, {
      cite: prov.cite("/mathieuCertificates/groups") || null,
      attribution: "asserted",
    }));
    for (const sylow of cert.sylows) {
      rows.push(row(`Sylow ${sylow.prime}`, `${sylow.generators.length} generators`, {
        cite: sylow.cite || prov.cite("/mathieuCertificates/groups"),
        attribution: "asserted",
      }));
    }
  }
  if (node.sporadicName === "M") {
    const y = data.monsterY443;
    rows.push(row("Presentation", `${y.presentedGroup} — ${y.generatorCount} Nielsen involutions, M = ${y.monster}`, {
      cite: prov.cite("/monsterY443/presentedGroup") || y.adjacencyCite,
      attribution: "asserted",
    }));
    rows.push(row("2A suborbits", `${suborbitText(data)}`, {
      cite: data.monsterSuborbit2A.simpleQuotientCite,
      attribution: "asserted",
    }));
  }
  if (node.sporadicName === "Y443") {
    const y = data.monsterY443;
    rows.push(row("Relations", y.relatorFamilies.map((f) => f.rule).join("  ·  "), {
      cite: prov.cite("/monsterY443/relatorFamilies") || (y.relatorFamilies[0] && y.relatorFamilies[0].cite),
      attribution: "asserted",
    }));
  }
  return rows;
}

function suborbitText(data) {
  const sub = data.monsterSuborbit2A;
  const orders = sub.elementOrders.join(", ");
  const quotients = (sub.simpleQuotients || []).filter(Boolean).join(", ");
  return `nine suborbits, element orders ${orders}${quotients ? `; quotients ${quotients}` : ""}`;
}

/**
 * @returns {object} {title, kicker, rows, pointer, provenanceCite}
 */
export function describeNode(node, data, prov) {
  const rows = node.kind === "lie" ? describeLie(node, data, prov) : describeSporadic(node, data, prov);
  const pointer = node.pointer;
  const own = prov.at(pointer);
  return {
    title: node.kind === "lie" ? node.label : `sporadic ${node.label}`,
    kicker: node.kind === "lie"
      ? `group of Lie type · ${node.rankVaries ? "rank n" : `rank ${node.rank}`}`
      : "sporadic · no infinite family",
    rows,
    pointer,
    provenanceCite: own ? citeOf(own) : null,
    attribution: own ? own.attribution : null,
  };
}

/** The classification banner: the four arms, straight off `knownSimpleOrders`. */
export function describeArms(data, prov) {
  return data.classification.arms.map((arm) => ({
    id: arm.id,
    index: arm.armIndex,
    displayName: arm.displayName,
    membership: arm.membership,
    cite: prov.cite("/classification/arms") || arm.cite,
    attribution: "asserted",
  }));
}

export function describeSelfChecks(data) {
  return (data.meta.selfChecks || []).map((check) => ({ ...check }));
}
