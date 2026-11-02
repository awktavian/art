/**
 * ui.js — the DOM around the canvas: legend, hover panel, keyboard-accessible
 * group list, and the runtime HUD.
 *
 * Everything that reaches the screen goes through `el()`/`textContent`, never
 * `innerHTML` with data in it: the strings in cfsg-families.json are Lean
 * source quotes, and a panel that can be injected is a panel that will be.
 *
 * Accessibility is structural, not decorative: the 42 groups are also a real
 * `<ul>` of buttons, so the atlas is operable with a keyboard alone and with a
 * screen reader, and `prefers-reduced-motion` is read once at startup and again
 * on change — under it the piece renders one converged static frame and does
 * not move the camera.
 */

import { describeNode, describeArms, attributionWord, citeOf } from "./describe.js";

const H = (tag, attrs = {}, children = []) => {
  const node = document.createElement(tag);
  for (const [k, v] of Object.entries(attrs)) {
    if (v === null || v === undefined) continue;
    if (k === "text") node.textContent = String(v);
    else if (k === "class") node.className = v;
    else if (k.startsWith("data-") || k === "id" || k === "type" || k === "aria-label" || k === "aria-live" || k === "aria-pressed" || k === "role" || k === "for" || k === "title") node.setAttribute(k, String(v));
    else node[k] = v;
  }
  // Children nest: a helper that returns a <dt>/<dd> pair hands back an array,
  // so flatten all the way down rather than assuming one level.
  const append = (child) => {
    if (child === null || child === undefined || child === false) return;
    if (Array.isArray(child)) {
      for (const inner of child) append(inner);
      return;
    }
    node.appendChild(typeof child === "string" || typeof child === "number"
      ? document.createTextNode(String(child))
      : child);
  };
  append(children);
  return node;
};

export function mountUI(root, { layout, data, prov, api }) {
  root.textContent = "";

  const title = H("h1", { class: "atlas-title", text: "The CFSG Group Atlas" });
  const subtitle = H("p", {
    class: "atlas-sub",
    text: "Path-traced classification of the finite simple groups, drawn from CFSG's own tables.",
  });

  const s = layout.stats;
  const facts = H("dl", { class: "atlas-facts" }, [
    fact("Arms of knownSimpleOrders", `${layout.arms.length}`),
    fact("Lie order formulas", `${s.lieFamilies} (${s.coxeterFolded} with a stated Cartan matrix)`),
    fact("StatedLieTag rows", `${s.lieTagRows}`),
    fact("Sporadics", `${s.sporadics} (${s.sporadicsWithPinnedOrder} with a pinned order)`),
    fact("Root vectors plotted", `${s.rootPoints}`),
    fact("Source commit", s.sourceCommit.slice(0, 12)),
    fact("Provenance pointers", s.provenancePointers === null ? "not loaded" : String(s.provenancePointers)),
    fact("Generator self-checks", `${s.selfChecksPassed} / ${s.selfChecksTotal}`),
  ]);

  const legend = H("section", { class: "atlas-legend", "aria-label": "How to read the atlas" }, [
    H("h2", { text: "Reading it" }),
    H("ul", {}, [
      li("Height", "is Lie rank. The eleven fixed-rank types stand on steps — Tits at rank 0, E8 at rank 8. The five infinite series have rank n, a variable, so they sit on a shelf labelled rather than measured."),
      li("Faceting", "is Coxeter symmetry. A node is carved with m-fold wedges only where CFSG states a Cartan matrix; a smooth node is a family the source gives no root system for, and that is shown as the absence it is."),
      li("Point constellations", "are root systems, orthogonally projected from rank-space onto three of its own dimensions. The densest and brightest is E8's 240 roots, closed under CFSG's reflect rule."),
      li("Colour", "is characteristic: ice for p = 2, gold for p = 3, climbing to rose and white as p grows; groups with no stated characteristic read cool white."),
      li("Filaments", "are real relations: Y443's Nielsen adjacency, the diagram automorphisms of D4 and E6, the cycle structure of each permutation carrier, and the nine 2A suborbits."),
    ]),
  ]);

  const arms = H("section", { class: "atlas-arms", "aria-label": "The four arms" }, [
    H("h2", { text: "knownSimpleOrders = four arms" }),
    H("ol", {}, describeArms(data, prov).map((arm) => H("li", {}, [
      H("span", { class: "arm-name", text: arm.displayName }),
      H("span", { class: "arm-mem", text: arm.membership }),
      H("cite", { class: "arm-cite", text: arm.cite || "" }),
    ]))),
  ]);

  const canvasWrap = H("div", { class: "atlas-stage" }, [
    H("canvas", { id: "atlas-canvas", width: "8", height: "6" }),
    H("p", { class: "atlas-canvas-note", text: "Path-traced WebGL2. If this is blank, the browser has no WebGL2 context." }),
  ]);

  const panel = H("aside", {
    class: "atlas-info",
    "aria-live": "polite",
    "aria-label": "Selected group",
  }, [H("h2", { class: "info-title", text: "Nothing selected" })]);

  const list = H("ul", { class: "atlas-list", "aria-label": "All 42 groups in the atlas" });
  const listButtons = new Map();
  layout.nodes.forEach((node, index) => {
    const button = H("button", {
      type: "button",
      class: "atlas-listitem",
      "data-index": String(index),
      text: node.kind === "lie" ? node.label : node.label,
      title: node.kind === "lie" ? `Lie family, ${node.rankVaries ? "rank n" : `rank ${node.rank}`}` : "sporadic group",
    });
    button.addEventListener("click", () => api.focusNode(index, "list"));
    button.addEventListener("focus", () => api.hoverNode(index));
    listButtons.set(index, button);
    list.appendChild(H("li", {}, [button]));
  });

  const hud = H("div", { class: "atlas-hud", "aria-label": "Runtime" }, [
    span("hud-frames", "samples 0"),
    span("hud-res", "res —"),
    span("hud-dpr", "dpr —"),
    span("hud-buffer", "buffer —"),
    span("hud-adapt", "adaptive —"),
    span("hud-spp", "spp —"),
    span("hud-motion", "motion —"),
  ]);

  const controls = H("div", { class: "atlas-controls" }, [
    H("button", { type: "button", id: "atlas-play", "aria-pressed": "true", text: "Pause flythrough" }),
    H("button", { type: "button", id: "atlas-reset", text: "Reset accumulation" }),
    H("button", { type: "button", id: "atlas-seed", text: "New seed" }),
  ]);

  const selfChecks = H("details", { class: "atlas-checks" }, [
    H("summary", { text: `Generator self-checks (${s.selfChecksPassed}/${s.selfChecksTotal})` }),
    H("ul", {}, (data.meta.selfChecks || []).map((c) => H("li", {}, [
      H("span", { class: c.pass ? "check pass" : "check fail", text: c.pass ? "✓" : "✗" }),
      document.createTextNode(` ${c.name}`),
    ]))),
  ]);

  root.append(
    H("header", { class: "atlas-head" }, [title, subtitle]),
    H("div", { class: "atlas-grid" }, [
      H("div", { class: "atlas-col atlas-col-left" }, [facts, legend, arms, selfChecks]),
      H("div", { class: "atlas-col atlas-col-stage" }, [canvasWrap, controls, hud]),
      H("div", { class: "atlas-col atlas-col-right" }, [panel, H("h2", { class: "list-head", text: "Every node" }), list]),
    ]),
  );

  function fact(term, value) {
    return [H("dt", { text: term }), H("dd", { text: value })];
  }
  function li(term, value) {
    return H("li", {}, [H("b", { text: `${term} — ` }), document.createTextNode(value)]);
  }
  function span(cls, text) {
    return H("span", { class: cls, text });
  }

  function renderInfo(node) {
    panel.textContent = "";
    panel.appendChild(H("h2", { class: "info-title", text: describeNode(node, data, prov).title }));
    const described = describeNode(node, data, prov);
    panel.appendChild(H("p", { class: "info-kicker", text: described.kicker }));
    panel.appendChild(H("dl", { class: "info-rows" }, described.rows.map((r) => [
      H("dt", { text: r.label }),
      H("dd", { class: `row ${r.absent ? "absent" : ""} ${r.tone === "accent" ? "accent" : ""}` }, [
        H("span", { class: "row-value", text: r.value }),
        r.cite ? H("cite", { class: "row-cite", text: r.cite }) : null,
        r.attribution ? H("span", { class: "row-attr", text: attributionWord(r.attribution) }) : null,
      ]),
    ]).flat()));
    panel.appendChild(H("p", {
      class: "info-pointer",
      text: `${described.pointer}${described.provenanceCite ? `  ·  ${described.provenanceCite}` : ""}`,
    }));
  }

  return {
    canvas: canvasWrap.querySelector("#atlas-canvas"),
    playButton: controls.querySelector("#atlas-play"),
    resetButton: controls.querySelector("#atlas-reset"),
    seedButton: controls.querySelector("#atlas-seed"),
    hud: {
      frames: hud.querySelector(".hud-frames"),
      res: hud.querySelector(".hud-res"),
      dpr: hud.querySelector(".hud-dpr"),
      buffer: hud.querySelector(".hud-buffer"),
      adapt: hud.querySelector(".hud-adapt"),
      spp: hud.querySelector(".hud-spp"),
      motion: hud.querySelector(".hud-motion"),
    },
    listButtons,
    showNode(index) {
      for (const [i, button] of listButtons) {
        button.classList.toggle("active", i === index);
      }
      if (index >= 0 && index < layout.nodes.length) renderInfo(layout.nodes[index]);
      else panel.textContent = "";
    },
    setHud(parts) {
      if (parts.frames !== undefined) this.hud.frames.textContent = `samples ${parts.frames}`;
      if (parts.res !== undefined) this.hud.res.textContent = `res ${parts.res}`;
      if (parts.dpr !== undefined) this.hud.dpr.textContent = `dpr ${parts.dpr}`;
      if (parts.buffer !== undefined) this.hud.buffer.textContent = `buffer ${parts.buffer}`;
      if (parts.adapt !== undefined) this.hud.adapt.textContent = `adaptive ${parts.adapt}`;
      // samples per pixel per presented frame, and the buffer's pixel ceiling:
      // the two knobs that decide whether this stays interactive.
      if (parts.spp !== undefined) {
        this.hud.spp.textContent = parts.pixelBudget
          ? `spp ${parts.spp}/frame · budget ${(parts.pixelBudget / 1e6).toFixed(2)} Mpx`
          : `spp ${parts.spp}/frame`;
      }
      if (parts.motion !== undefined) this.hud.motion.textContent = `motion ${parts.motion}`;
    },
    stats: s,
    citeOf,
  };
}
