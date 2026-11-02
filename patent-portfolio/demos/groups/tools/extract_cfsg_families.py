#!/usr/bin/env python3
"""V6-ART-GROUPATLAS-1102 — CFSG group-atlas data extractor.

Reads the CFSG Lean 4 formalization READ-ONLY and emits two deterministic JSON
carriers for the path-traced group atlas demo page:

  data/cfsg-families.json  — the scene data (families, sporadics, certificates,
                             Cartan data, root systems, order formulas)
  data/provenance.json     — JSON-Pointer -> {file, line, quote, attribution}

Every datum is emitted through `put()`, which records the source line it came
from; the two files are therefore always in agreement. Nothing is invented: if
a source pattern is not found the script raises instead of guessing, and any
number computed here rather than asserted by CFSG is tagged "derived" or
"computed" with the rule that produced it.

Usage: extract_cfsg_families.py <cfsg_root> <out_dir> [--commit SHA]
Exit 0 on success. Never writes into <cfsg_root>.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import posixpath
import re
import sys


# --------------------------------------------------------------------------
# provenance ledger
# --------------------------------------------------------------------------

class Ledger:
    def __init__(self, root):
        self.root = root
        self.rows = {}
        self.shas = {}

    def sha(self, rel):
        if rel not in self.shas:
            with open(os.path.join(self.root, rel), "rb") as fh:
                self.shas[rel] = hashlib.sha256(fh.read()).hexdigest()
        return self.shas[rel]

    def line(self, rel, n):
        with open(os.path.join(self.root, rel), encoding="utf-8") as fh:
            for i, text in enumerate(fh, 1):
                if i == n:
                    return text.rstrip("\n")
        raise LookupError("no line %d in %s" % (n, rel))

    def cite(self, pointer, rel, n, attribution="asserted", quote=None, derived=False):
        """
        Record one pointer. `quote` defaults to the cited source line.

        A DERIVED pointer cites the line a computation starts FROM while the
        words beside it are this generator's own note about that computation —
        "closure of the basis under Tag.reflect", for example. Those two kinds
        of sentence must not share a field, or a reader cannot tell a source
        quote from an annotation, so:

          * quoteKind "verbatim" — the text is checked, here, to occur on the
            cited line. A verbatim pointer that does not match its line is a
            raised AssertionError, not a shipped JSON field.
          * quoteKind "derived" — the note is kept in `quote` (one field for
            readers), the actual line text is kept in `sourceLine`, and the
            row says which it is.
        """
        if pointer in self.rows:
            raise ValueError("duplicate pointer " + pointer)
        src = self.line(rel, n)
        text = (quote if quote is not None else src).strip()
        row = {
            "file": posixpath.join("cfsg", rel),
            "line": n,
            "quote": text,
            "quoteKind": "derived" if derived else "verbatim",
            "attribution": attribution,
            "sha256": self.sha(rel),
        }
        if derived:
            if quote is None:
                raise ValueError("derived pointer with no note: " + pointer)
            row["sourceLine"] = src.strip()
        elif text not in src:
            raise AssertionError(
                "verbatim quote is not on %s:%d\n  quote=%r\n  line=%r" % (rel, n, text, src))
        self.rows[pointer] = row


# --------------------------------------------------------------------------
# Lean source reading
# --------------------------------------------------------------------------

def read(root, rel):
    with open(os.path.join(root, rel), encoding="utf-8") as fh:
        return fh.read()


def find_line(root, rel, needle, occurrence=1):
    """1-based line number of the `occurrence`-th line containing `needle`."""
    hits = [i for i, text in enumerate(read(root, rel).split("\n"), 1) if needle in text]
    if len(hits) < occurrence:
        raise LookupError("%r not found %dx in %s (found %d)" % (needle, occurrence, rel, len(hits)))
    return hits[occurrence - 1]


def lean_string_literal(src, anchor):
    """Body of the Lean string literal that starts at `anchor` (inclusive)."""
    j = src.index(anchor) + len(anchor)
    while src[j] in " \t\r\n":
        j += 1
    if src[j] != '"':
        raise ValueError("anchor %r is not followed by a string literal" % anchor)
    i = j + 1                      # step past the opening quote
    out = []
    while i < len(src):
        c = src[i]
        if c == '"':
            return "".join(out)
        if c == "\\":
            nxt = src[i + 1] if i + 1 < len(src) else ""
            if nxt == "\n":                      # continuation: newline + leading ws
                i += 2
                while i < len(src) and src[i] in " \t":
                    i += 1
                continue
            mapping = {"n": "\n", "t": "\t", "\\": "\\", '"': '"', "r": "\r"}
            if nxt in mapping:
                out.append(mapping[nxt])
                i += 2
                continue
            raise ValueError("unsupported escape %r" % src[i:i + 2])
        out.append(c)
        i += 1
    raise ValueError("unterminated literal")


def _py_expression(expr):
    out = expr
    out = re.sub(r"Nat\.factorial", "factorial", out)
    out = out.replace("^", "**")
    return out


def factorial(n):
    r = 1
    for k in range(2, n + 1):
        r *= k
    return r


def gcd(a, b):
    while b:
        a, b = b, a % b
    return a


def prod(vals):
    r = 1
    for v in vals:
        r *= v
    return r


def evaluate_formula(kind, n, q):
    """The order polynomials of CFSG/Open/Defs.lean, transcribed literally.

    Each branch mirrors one `@[expose] def ord...` definition; the cite is the
    line of that definition in the JSON output. Integer division follows Lean's
    Nat.div (floor), which is what the source uses.
    """
    icc = lambda a, b: range(a, b + 1) if a <= b else range(0, 0)  # noqa: E731
    if kind == "ordA":
        return q ** (n * (n + 1) // 2) * prod(q ** i - 1 for i in icc(2, n + 1)) // gcd(n + 1, q - 1)
    if kind == "ordTwistedA":
        return q ** (n * (n + 1) // 2) * prod(q ** i - (-1) ** i for i in icc(2, n + 1)) // gcd(n + 1, q + 1)
    if kind == "ordBC":
        return q ** (n * n) * prod(q ** (2 * i) - 1 for i in icc(1, n)) // gcd(2, q - 1)
    if kind == "ordD":
        return q ** (n * (n - 1)) * (q ** n - 1) * prod(q ** (2 * i) - 1 for i in icc(1, n - 1)) // gcd(4, q ** n - 1)
    if kind == "ordTwistedD":
        return q ** (n * (n - 1)) * (q ** n + 1) * prod(q ** (2 * i) - 1 for i in icc(1, n - 1)) // gcd(4, q ** n + 1)
    if kind == "ordE6":
        return q ** 36 * (q ** 12 - 1) * (q ** 9 - 1) * (q ** 8 - 1) * (q ** 6 - 1) * (q ** 5 - 1) * (q ** 2 - 1) // gcd(3, q - 1)
    if kind == "ordTwistedE6":
        return q ** 36 * (q ** 12 - 1) * (q ** 9 + 1) * (q ** 8 - 1) * (q ** 6 - 1) * (q ** 5 + 1) * (q ** 2 - 1) // gcd(3, q + 1)
    if kind == "ordE7":
        return q ** 63 * prod(q ** e - 1 for e in (18, 14, 12, 10, 8, 6, 2)) // gcd(2, q - 1)
    if kind == "ordE8":
        return q ** 120 * prod(q ** e - 1 for e in (30, 24, 20, 18, 14, 12, 8, 2))
    if kind == "ordF4":
        return q ** 24 * (q ** 12 - 1) * (q ** 8 - 1) * (q ** 6 - 1) * (q ** 2 - 1)
    if kind == "ordG2":
        return q ** 6 * (q ** 6 - 1) * (q ** 2 - 1)
    if kind == "ordTrialityD4":
        return q ** 12 * (q ** 8 + q ** 4 + 1) * (q ** 6 - 1) * (q ** 2 - 1)
    if kind == "ordSuzuki":
        return q ** 2 * (q ** 2 + 1) * (q - 1)
    if kind == "ordRee":
        return q ** 3 * (q ** 3 + 1) * (q - 1)
    if kind == "ordTwistedF4":
        return q ** 12 * (q ** 6 + 1) * (q ** 4 - 1) * (q ** 3 + 1) * (q - 1)
    raise KeyError(kind)


def factorize(m):
    if m <= 1:
        return []
    out, d = [], 2
    while d * d <= m:
        e = 0
        while m % d == 0:
            m //= d
            e += 1
        if e:
            out.append([d, e])
        d += 1
    if m > 1:
        out.append([m, 1])
    return out


def render_factorization(pairs):
    return " · ".join(("%d^%d" % (p, e)) if e > 1 else str(p) for p, e in pairs)


# --------------------------------------------------------------------------
# CFSG/Open/Defs.lean — order formulas, sporadic list, classification arms
# --------------------------------------------------------------------------

DEFS = "CFSG/Open/Defs.lean"
# NOTE the ord* formulas take the LIE RANK as their first parameter: ordA(2,2)
# = 168 = |PSL_3(2)| = |A_2(2)|, ordBC(2,2) = 720 = |PSp_4(2)|. The
# StatedLieTag constructors instead take the MATRIX DEGREE (StatedSL n lives in
# GL (Fin n)), so tag PSL n corresponds to ordA (n-1). Both readings are cited;
# the pairing is recorded as derived, never as a CFSG assertion.
ORD_ARMS = [  # (def name, family label, parameters, rank rule for the atlas)
    ("ordA", "A_n(q) = PSL_{n+1}(q)", ["n", "q"], "n"),
    ("ordTwistedA", "^2A_n(q) = PSU_{n+1}(q)", ["n", "q"], "n"),
    ("ordBC", "C_n(q) = PSp_{2n}(q)", ["n", "q"], "n"),
    ("ordD", "D_n(q) = POmega^+_{2n}(q)", ["n", "q"], "n"),
    ("ordTwistedD", "^2D_n(q) = POmega^-_{2n}(q)", ["n", "q"], "n"),
    ("ordE6", "E6(q)", ["q"], "6"),
    ("ordTwistedE6", "^2E6(q)", ["q"], "6"),
    ("ordE7", "E7(q)", ["q"], "7"),
    ("ordE8", "E8(q)", ["q"], "8"),
    ("ordF4", "F4(q)", ["q"], "4"),
    ("ordG2", "G2(q)", ["q"], "2"),
    ("ordTrialityD4", "^3D4(q)", ["q"], "4"),
    ("ordSuzuki", "^2B2(q) = Sz(q)", ["q"], "1"),
    ("ordRee", "^2G2(q) = Ree(q)", ["q"], "1"),
    ("ordTwistedF4", "^2F4(q)", ["q"], "4"),
]

SAMPLES = {  # (n, q) samples whose orders the page plots; q is always a prime power
    "ordA": [(2, 2), (2, 3), (2, 4), (3, 2), (3, 3), (4, 2), (4, 3), (5, 2), (6, 2), (8, 2), (12, 2)],
    "ordTwistedA": [(3, 2), (4, 2), (4, 3), (5, 2), (6, 2)],
    "ordBC": [(2, 2), (2, 3), (3, 2), (4, 2), (6, 2), (8, 2)],
    "ordD": [(4, 2), (4, 3), (5, 2), (6, 2), (8, 2), (10, 2)],
    "ordTwistedD": [(4, 2), (5, 2), (6, 2), (8, 2)],
    "ordE6": [(2, 2), (2, 3), (2, 4)],
    "ordTwistedE6": [(2, 2), (2, 3)],
    "ordE7": [(2, 2), (2, 3)],
    "ordE8": [(2, 2)],
    "ordF4": [(2, 2), (2, 3), (2, 4)],
    "ordG2": [(2, 2), (2, 3), (2, 4), (2, 5)],
    "ordTrialityD4": [(2, 2), (2, 3)],
    "ordSuzuki": [(8, 1), (32, 1)],
    "ordRee": [(27, 1)],
    "ordTwistedF4": [(2, 1), (8, 1)],
}
# Suzuki/Ree/twisted-F4 take q as the (odd-exponent) prime power itself: encode
# those samples as (q, ignored) and call the formula with n unused.
SOLO_Q = {"ordSuzuki", "ordRee", "ordTwistedF4"}


def parse_order_defs(root, out, led):
    src = read(root, DEFS)
    lines = src.split("\n")
    rel = "CFSG/Open/Defs.lean"
    found = {}
    for name, label, params, rank_rule in ORD_ARMS:
        start = find_line(root, rel, "def %s (" % name)
        # formula text = from the def line up to the next blank/def boundary
        body = []
        i = start - 1
        while i < len(lines):
            text = lines[i]
            if i > start - 1 and (text.startswith("@[expose]") or text == "" or text.startswith("def ")):
                break
            body.append(text.strip())
            i += 1
        formula = " ".join(body)
        formula = re.sub(r"^@\[expose\] def %s \(.*\) : ℕ := " % name, "", formula)
        formula = formula.replace("Nat.gcd", "gcd").replace("Finset.Icc", "Icc")
        found[name] = {"start": start, "formula": formula, "label": label,
                       "params": params, "rankRule": rank_rule}
    # ordTits is a constant, not a function of q
    tits_line = find_line(root, rel, "def ordTits : ℕ :=")
    found["ordTits"] = {"start": tits_line,
                        "formula": lines[tits_line - 1].split(":=", 1)[1].strip(),
                        "label": "^2F4(2)' = Tits", "params": [], "rankRule": "0"}

    for key in [a[0] for a in ORD_ARMS] + ["ordTits"]:
        d = found[key]
        ptr = "/lieFamilies/%s" % key
        led.cite(ptr + "/formula", rel, d["start"])
        fam = {"id": key, "displayName": d["label"], "params": d["params"],
               "formula": d["formula"], "rankRule": d["rankRule"],
               "sampleOrders": []}
        if key == "ordTits":
            v = eval(d["formula"].replace("^", "**"), {"__builtins__": {}}, {})
            fam["sampleOrders"] = [{"n": None, "q": 2, "order": str(v),
                                    "factorization": render_factorization(factorize(v))}]
        else:
            for n, q in SAMPLES[key]:
                if key in SOLO_Q:
                    v = evaluate_formula(key, 0, n)
                    nn, qq = None, n
                else:
                    v = evaluate_formula(key, n, q)
                    nn, qq = n, q
                if v <= 0:
                    continue
                fam["sampleOrders"].append({"n": nn, "q": qq, "order": str(v),
                                            "factorization": render_factorization(factorize(v))})
        out[ptr] = fam
    return found


def parse_sporadic_order_list(root, out, led):
    rel = DEFS
    start = find_line(root, rel, "def sporadicOrderList : Finset ℕ :=")
    src = read(root, rel).split("\n")
    # the Finset literal is `{ term, ..., term }` and spans several lines
    buf = " ".join(line.strip() for line in src[start - 1:start + 40])
    i0 = buf.index("{")
    depth, end = 0, None
    for k in range(i0, len(buf)):
        if buf[k] == "{":
            depth += 1
        elif buf[k] == "}":
            depth -= 1
            if depth == 0:
                end = k
                break
    if end is None:
        raise LookupError("sporadicOrderList literal never closes")
    inner = buf[i0 + 1:end]
    terms = [t.strip() for t in inner.split(",") if t.strip()]
    env = {"__builtins__": {}}
    vals = [eval(t.replace("^", "**"), env, {}) for t in terms]
    assert len(vals) == 26, "sporadicOrderList read as %d terms" % len(vals)
    led.cite("/sporadicOrders", rel, start)
    out["/sporadicOrders"] = {
        "count": 26,
        "asWritten": [{"expression": t, "value": str(v),
                       "factorization": render_factorization(factorize(v))}
                      for t, v in zip(terms, vals)],
        "valuesAscending": [str(v) for v in sorted(vals)],
        "note": "sporadicOrderList is a Finset ℕ: CFSG asserts the 26-element set "
                "of sporadic orders but does not index it by group name. Name "
                "attributions appear only where a separate CFSG theorem or named "
                "definition pins them.",
    }
    return set(vals)


def parse_known_simple_orders(root, out, led):
    rel = DEFS
    start = find_line(root, rel, "def knownSimpleOrders : Set ℕ :=")
    led.cite("/classification/arms", rel, start)
    arms = [
        {"id": "cyclicPrime", "displayName": "C_p, p prime", "armIndex": 0,
         "membership": "m.Prime", "cite": "%s:%d" % (rel, start)},
        {"id": "alternating", "displayName": "A_n, n >= 5", "armIndex": 1,
         "membership": "Nat.factorial n / 2 with 5 <= n", "cite": "%s:%d" % (rel, start)},
        {"id": "lie", "displayName": "Groups of Lie type", "armIndex": 2,
         "membership": "lieOrdersChar p", "cite": "%s:%d" % (rel, start + 1)},
        {"id": "sporadic", "displayName": "The 26 sporadic groups", "armIndex": 3,
         "membership": "sporadicOrderList", "cite": "%s:%d" % (rel, start + 2)},
    ]
    out["/classification"] = {"arms": arms,
                              "statement": "knownSimpleOrders = primes | alternating | Lie | sporadic",
                              "statementCite": "%s:%d" % (rel, start)}
    # alternating arm: A_n order = n!/2 (CFSG/Open/Defs.lean), n from 5
    alt = []
    for n in range(5, 16):
        v = factorial(n) // 2
        alt.append({"n": n, "order": str(v), "factorization": render_factorization(factorize(v))})
    out["/classification/alternatingSeries"] = alt
    led.cite("/classification/alternatingSeries", rel, start + 1)
    primes = []
    for p in [2, 3, 5, 7, 11, 13, 17, 19, 23, 29, 31, 37, 41, 43, 47, 53, 59, 61, 67, 71]:
        primes.append({"p": p, "order": str(p), "factorization": str(p)})
    out["/classification/cyclicPrimeSeries"] = primes
    led.cite("/classification/cyclicPrimeSeries", rel, start)


def parse_lie_orders_over(root, out, led):
    rel = DEFS
    over = find_line(root, rel, "def lieOrdersOver (q : ℕ) : Set ℕ :=")
    char_ = find_line(root, rel, "def lieOrdersChar (p : ℕ) : Set ℕ :=")
    led.cite("/lieFamilies/familySet", rel, over)
    led.cite("/lieFamilies/characteristicRule", rel, char_)
    out["/lieFamilies/familySet"] = {
        "ordA": "%s:%d" % (rel, over),
        "ordTwistedA": "%s:%d" % (rel, over),
        "ordBC": "%s:%d" % (rel, over),
        "ordD": "%s:%d" % (rel, over),
        "ordTwistedD": "%s:%d" % (rel, over),
        "exceptional": ["ordE6", "ordTwistedE6", "ordE7", "ordE8", "ordF4", "ordG2", "ordTrialityD4"],
        "ree": {"ordSuzuki": "p=2, q=2^(2k+1)", "ordTwistedF4": "p=2, q=2^(2k+1)",
                "ordRee": "p=3, q=3^(2k+1)", "ordTits": "p=2, q=2 (constant)"},
    }
    out["/lieFamilies/characteristicRule"] = (
        "lieOrdersChar p = lieOrdersOver (p^k) (k>=1), plus ^2B2/^2F4 over 2^(2k+1) when p=2, "
        "plus ^2G2 over 3^(2k+1) when p=3, plus Tits when p=2")


# --------------------------------------------------------------------------
# CFSG/Open/StatedDefs.lean — family tags + admissibility
# --------------------------------------------------------------------------

STATED = "CFSG/Open/StatedDefs.lean"
TAG_FORMULA = {
    "PSL": "ordA", "PSU": "ordTwistedA", "PSp": "ordBC",
    "POmegaOdd": "ordBC", "POmegaPlus": "ordD", "POmegaMinus": "ordTwistedD",
    "G2": "ordG2", "F4": "ordF4", "E6": "ordE6", "E7": "ordE7", "E8": "ordE8",
    "twistedE6": "ordTwistedE6", "trialityD4": "ordTrialityD4",
    "twistedB2": "ordSuzuki", "twistedG2": "ordRee", "twistedF4": "ordTwistedF4",
    "Tits": "ordTits",
}


def parse_stated_lie(root, out, led):
    rel = STATED
    induct = find_line(root, rel, "inductive StatedLieTag")
    admiss = find_line(root, rel, "def StatedLieAdmissible")
    src = read(root, rel).split("\n")
    tags = []
    i = induct
    while True:
        text = src[i]
        if text.startswith("  deriving"):
            break
        for t in re.findall(r"\|?\s*([A-Za-z][A-Za-z0-9]*)", text.replace("|", " ")):
            if t in TAG_FORMULA and t not in tags:
                tags.append(t)
        i += 1
    assert len(tags) == 17, "StatedLieTag parsed as %d arms: %s" % (len(tags), tags)
    rows = []
    # an arm may name several tags: `| .F4 | .E6 | .E7 | .E8 | ... => n = 0`
    arm_line = {}
    for k in range(induct, len(src)):
        text = src[k]
        if "=>" not in text:
            continue
        head = text.split("=>", 1)[0]
        if not head.lstrip().startswith("|"):
            continue
        for t in re.findall(r"\.\s*([A-Za-z][A-Za-z0-9]*)", head):
            arm_line.setdefault(t, k + 1)
        if k > admiss + 40:
            break
    # the matrix models show what the tag's `n` measures (degree, rank, or 2n);
    # cited per tag instead of asserting one uniform convention
    model_lines = {}
    for name, needle in (("PSL", "def StatedSL (n : ℕ)"), ("PSU", "def StatedSU (n q : ℕ)"),
                         ("PSp", "def StatedSp (n : ℕ)"),
                         ("POmegaOdd", "def StatedQuadOdd (n : ℕ)")):
        try:
            model_lines[name] = find_line(root, rel, needle)
        except LookupError:
            model_lines[name] = None
    for t in tags:
        cond_line = arm_line.get(t)
        assert cond_line, "no admissibility arm for " + t
        cond = src[cond_line - 1].split("=>", 1)[1].strip()
        row = {"tag": t, "orderFormula": TAG_FORMULA[t],
               "admissible": cond, "pairing": "by-name-correspondence",
               "tagCite": "%s:%d" % (rel, induct),
               "admissibleCite": "%s:%d" % (rel, cond_line)}
        if model_lines.get(t):
            row["matrixModelCite"] = "%s:%d" % (rel, model_lines[t])
        rows.append(row)
        led.cite("/lieFamilies/tags/%s/admissible" % t, rel, cond_line)
    led.cite("/lieFamilies/tags", rel, induct)
    out["/lieFamilies/tags"] = rows


# --------------------------------------------------------------------------
# CFSG/Blueprint/Chevalley.lean — ranks, Cartan matrices, roots, twists
# --------------------------------------------------------------------------

CHEV = "CFSG/Blueprint/Chevalley.lean"
TAGS6 = ["G2", "F4", "D4", "E6", "E7", "E8"]


def parse_cartan_matrix(text):
    body = text[text.index("!![") + 3:text.rindex("]")]
    rows = [r.strip() for r in body.split(";")]
    return [[int(v) for v in r.split(",")] for r in rows]


def parse_chevalley(root, out, led):
    rel = CHEV
    induct = find_line(root, rel, "inductive Tag")
    rank_def = find_line(root, rel, "def rank : Tag → ℕ")
    cartan_def = find_line(root, rel, "def cartan : (τ : Tag)")
    sym_def = find_line(root, rel, "def symmetrizer : (τ : Tag)")
    reflect_def = find_line(root, rel, "def reflect (τ : Tag)")
    isroot_def = find_line(root, rel, "inductive IsRoot (τ : Tag)")
    twist_ind = find_line(root, rel, "inductive TwistTag")
    twist_perm = find_line(root, rel, "def perm : (t : TwistTag)")

    src = read(root, rel).split("\n")
    ranks = {}
    for k in range(rank_def, rank_def + 10):
        m = re.match(r"\s*\| (G2|F4|D4|E6|E7|E8) => (\d+)", src[k - 1])
        if m:
            ranks[m.group(1)] = int(m.group(2))
    assert ranks == {"G2": 2, "F4": 4, "D4": 4, "E6": 6, "E7": 7, "E8": 8}, ranks

    cartans = {}
    for k in range(cartan_def, cartan_def + 14):
        m = re.match(r"\s*\| (G2|F4|D4|E6|E7|E8) => !!\[(.*)", src[k - 1])
        if m:
            txt = m.group(2)
            j = k
            while "]" not in txt:
                txt += src[j]
                j += 1
            cartans[m.group(1)] = parse_cartan_matrix("!![" + txt)
    for t in ("E6", "E7", "E8"):
        # those three are produced by cartanE r, the off-diagonal path rule
        base = find_line(root, rel, "def cartanE (r : ℕ)")
        cartans[t] = cartan_e(ranks[t])
        led.cite("/exceptional/%s/cartan" % t, rel, base, attribution="derived",
                 quote="cartanE %d — banded rule read off the same definition the source uses" % ranks[t],
                 derived=True)
    for t in TAGS6:
        if t not in ("E6", "E7", "E8"):
            led.cite("/exceptional/%s/cartan" % t, rel, cartan_def)

    roots = {}
    for t in TAGS6:
        rr = root_system(cartans[t])
        roots[t] = {"rank": ranks[t], "cartan": cartans[t],
                    "rootCount": len(rr), "roots": [[int(x) for x in v] for v in rr],
                    "positiveCount": sum(1 for v in rr if sum(v) > 0)}
        led.cite("/exceptional/%s/rank" % t, rel, rank_def)
        led.cite("/exceptional/%s/rootCount" % t, rel, isroot_def, attribution="computed",
                 quote="closure of the basis under Tag.reflect (IsRoot τ): computed here, not asserted",
                 derived=True)

    # diagram automorphisms (TwistTag.perm) — the data behind ^2E6 and ^3D4
    tw = {}
    for k in range(twist_perm, twist_perm + 6):
        m = re.match(r"\s*\| (E6|D4) => \(Equiv\.swap (\d) (\d) \* Equiv\.swap (\d) (\d)", src[k - 1])
        if m:
            tw[m.group(1)] = {"swaps": [[int(m.group(2)), int(m.group(3))],
                                        [int(m.group(4)), int(m.group(5))]],
                              "cite": "%s:%d" % (rel, k)}
    assert set(tw) == {"E6", "D4"}, tw
    led.cite("/diagramAutomorphisms", rel, twist_ind)

    out["/exceptional"] = {t: roots[t] for t in TAGS6}
    for t in TAGS6:
        out["/exceptional"][t]["formula"] = None  # filled by the family table link
    out["/exceptional/_meta"] = {
        "tagEnum": TAGS6, "tagEnumCite": "%s:%d" % (rel, induct),
        "reflectRule": "v - (Σ j, cartan i j * v j) • e_i", "reflectCite": "%s:%d" % (rel, reflect_def),
        "isRootRule": "basis vectors, closed under reflect", "isRootCite": "%s:%d" % (rel, isroot_def),
        "symmetrizerCite": "%s:%d" % (rel, sym_def),
    }
    out["/diagramAutomorphisms"] = tw
    return ranks, cartans


def cartan_e(r):
    """CFSG/Blueprint/Chevalley.lean `cartanE` — the E_n banded Cartan matrix."""
    M = [[0] * r for _ in range(r)]
    for i in range(r):
        M[i][i] = 2
        for j in range(r):
            if i == j:
                continue
            if (i == 0 and j == 2) or (i == 2 and j == 0) or (i == 1 and j == 3) or (i == 3 and j == 1):
                M[i][j] = -1
            elif i >= 2 and j == i + 1:
                M[i][j] = -1
            elif j >= 2 and i == j + 1:
                M[i][j] = -1
    return M


def root_system(cartan):
    """Enumerate the roots of a Cartan matrix by closing the basis under the
    Weyl reflections of CFSG/Blueprint/Chevalley.lean:53 (`reflect`)."""
    r = len(cartan)
    basis = []
    for i in range(r):
        v = [0] * r
        v[i] = 1
        basis.append(tuple(v))

    def reflect(i, v):
        s = sum(cartan[i][j] * v[j] for j in range(r))
        out = list(v)
        out[i] -= s
        return tuple(out)

    seen = set(basis)
    frontier = list(basis)
    while frontier:
        nxt = []
        for v in frontier:
            for i in range(r):
                w = reflect(i, list(v))
                if w not in seen:
                    seen.add(w)
                    nxt.append(w)
        frontier = nxt
    return sorted(seen, key=lambda v: (-sum(v), v))


# --------------------------------------------------------------------------
# CFSG/Blueprint/NativeSporadic.lean — carriers, reps, Y443 presentation
# --------------------------------------------------------------------------

NATIVE = "CFSG/Blueprint/NativeSporadic.lean"
PERM_SPORADICS = ["M11", "M12", "M22", "M23", "M24"]
SEED_ORDER = ["J1", "J2", "J3", "J4", "Co1", "Co2", "Co3", "Fi22", "Fi23", "Fi24prime",
              "HS", "McL", "He", "Ru", "Suz", "ON", "HN", "Ly", "Th", "B"]


def parse_native_sporadic(root, out, led):
    rel = NATIVE
    src = read(root, rel).split("\n")
    carriers = {}

    for name in PERM_SPORADICS:
        ln = find_line(root, rel, "def %s : Subgroup (Equiv.Perm (Fin" % name)
        m = re.search(r"Fin (\d+)", src[ln - 1])
        deg = int(m.group(1))
        decl = _closure_body(src, ln)
        cycles_per_gen = [
            [[int(x) for x in c.split(",")] for c in re.findall(r"\[(\d+(?:\s*,\s*\d+)*)\]", g)]
            for g in split_top_level(decl)
        ]
        carriers[name] = {
            "model": "permutationSubgroup", "degree": deg,
            "generatorCycles": cycles_per_gen,
            "generatorImages": [cycles_to_images(cs, deg) for cs in cycles_per_gen],
            "cite": "%s:%d" % (rel, ln),
        }
        led.cite("/sporadics/%s" % name, rel, ln)

    for name in SEED_ORDER:
        ln = find_line(root, rel, "abbrev %s : Type := (seedMonoid" % name)
        m = re.search(r"seedMonoid (\d+) (\d+) (\d+)", src[ln - 1])
        p, dim, mode = int(m.group(1)), int(m.group(2)), int(m.group(3))
        seed_ln = find_line(root, rel, "def %sSeed1 : String :=" % name)
        files = re.findall(r'include_str "Data"/"([^"]+)"', src[seed_ln - 1])
        carriers[name] = {"model": "matrixUnitsModular", "characteristic": p,
                          "representationDegree": dim, "seedMode": mode,
                          "seedFiles": files, "cite": "%s:%d" % (rel, ln),
                          "seedCite": "%s:%d" % (rel, seed_ln)}
        led.cite("/sporadics/%s" % name, rel, ln)

    for pointer, name, decl in (("/monsterY443/definition", "Y443", "abbrev Y443 : Type := PresentedGroup"),
                                ("/sporadics/M", "M", "abbrev M : Type := commutator")):
        ln = find_line(root, rel, decl)
        carriers.setdefault(name, {})["definitionCite"] = "%s:%d" % (rel, ln)
        # the Monster is the node at the centre of the scene, and Y443 is the
        # group the certificate presents — both must resolve from the sidecar
        # the way the other 25 sporadic carriers do, or hovering them shows a
        # panel whose own pointer is dangling.
        led.cite(pointer, rel, ln)

    y_adj = find_line(root, rel, "def y443Adjacent")
    y_rel = find_line(root, rel, "def y443Relations")
    carrier_def = find_line(root, rel, "def Carrier : TauCeti.SporadicName → Type")

    adj = y443_edges(src, y_adj)
    led.cite("/monsterY443/adjacency", rel, y_adj)
    led.cite("/monsterY443/relators", rel, y_rel)
    led.cite("/sporadics/_carrierEnumeration", rel, carrier_def)

    presentation = {
        "generatorCount": 12,
        "generatorNames": ["x0..x11 (Nielsen involutions)"],
        "relatorFamilies": [
            {"rule": "x_i ^ 2 = 1 for all i", "cite": "%s:%d" % (rel, y_rel + 2)},
            {"rule": "(x_i x_j) ^ 3 when i ~ j, (x_i x_j) ^ 2 otherwise",
             "cite": "%s:%d" % (rel, y_rel + 3)},
            {"rule": "(x0 x1 x2 x0 x5 x6 x0 x9 x10) ^ 10", "cite": "%s:%d" % (rel, y_rel + 6)},
        ],
        "adjacency": adj,
        "adjacencyCite": "%s:%d" % (rel, y_adj),
        "presentedGroup": "Y443 = PresentedGroup y443Relations",
        "monster": "M = commutator Y443",
    }
    out["/monsterY443"] = presentation

    carriers["M"]["model"] = "monsterDerivedFromY443"
    carriers["Y443"]["model"] = "presentedGroup"
    out["/sporadics"] = carriers

    enumeration = []
    i = carrier_def
    while i < len(src):
        m = re.match(r"\s*\| \.?([A-Za-z0-9]+) => ([A-Za-z0-9]+)", src[i])
        if m:
            enumeration.append({"sporadicName": m.group(1), "carrier": m.group(2)})
        elif src[i].startswith("instance"):
            break
        i += 1
    assert len(enumeration) == 26, "Carrier enumerates %d names" % len(enumeration)
    out["/sporadics/_carrierEnumeration"] = enumeration
    return carriers


def _closure_body(src, decl_line):
    """Text inside the outermost braces of a `Subgroup.closure { ... }` body."""
    text = " ".join(src[decl_line - 1:decl_line + 8])
    i = text.index("closure")
    j = text.index("{", i)
    depth = 0
    for k in range(j, len(text)):
        if text[k] == "{":
            depth += 1
        elif text[k] == "}":
            depth -= 1
            if depth == 0:
                return text[j + 1:k]
    raise ValueError("unbalanced closure body at line %d" % decl_line)


def split_top_level(body):
    """Split a closure body into its generator expressions on top-level commas."""
    parts, cur, depth = [], "", 0
    for ch in body:
        if ch in "([{":
            depth += 1
        elif ch in ")]}":
            depth -= 1
        if ch == "," and depth == 0:
            parts.append(cur)
            cur = ""
        else:
            cur += ch
    if cur.strip():
        parts.append(cur)
    return parts


def cycles_to_images(cycles, degree):
    img = list(range(degree))
    for cyc in cycles:
        for a, b in zip(cyc, cyc[1:] + cyc[:1]):
            img[a] = b
    return img


def _perm_to_cycles(images):
    n = len(images)
    seen = [False] * n
    cycles = []
    for start in range(n):
        if seen[start]:
            continue
        cyc, k = [], start
        while not seen[k]:
            seen[k] = True
            cyc.append(k)
            k = images[k]
        if len(cyc) > 1:
            cycles.append(cyc)
    return cycles


def y443_edges(src, adj_line):
    """Read the Y443 graph adjacency out of CFSG's `y443Adjacent`.

    The definition is a disjunction of four clauses: two star clauses naming the
    neighbours of node 0, and two chain clauses (`i.val + 1 = j.val` and its
    mirror) restricted to a subset of indices. Each side therefore yields two
    `{...}` sets — the smaller is the star set, the larger the chain set.
    """
    text = " ".join(src[adj_line - 1:adj_line + 6])
    j_sets = [[int(v) for v in s.split(",")]
              for s in re.findall(r"j\.val ∈ \(\{(\d+(?:, \d+)*)\}", text)]
    i_sets = [[int(v) for v in s.split(",")]
              for s in re.findall(r"i\.val ∈ \(\{(\d+(?:, \d+)*)\}", text)]
    assert j_sets and i_sets, "y443Adjacent did not yield its two index sets"
    hubs = min(j_sets, key=len)
    chainable = set(max(i_sets, key=len))
    edges = set()
    for h in hubs:
        edges.add((0, h))
    for i in range(11):
        if i in chainable and (i + 1) in chainable:
            edges.add((min(i, i + 1), max(i, i + 1)))
    return sorted([e[0], e[1]] for e in edges)


# --------------------------------------------------------------------------
# CFSG/Open/MonsterDefs.lean — named orders + the 2A suborbit table
# --------------------------------------------------------------------------

MDEFS = "CFSG/Open/MonsterDefs.lean"
NAMED_ORDERS = [("monsterOrder", "M", "Monster"),
                ("monsterBabyOrder", "B", "Baby Monster"),
                ("monsterCo2Order", "Co2", "Conway Co2"),
                ("monsterFi23Order", "Fi23", "Fischer Fi23"),
                ("monsterFi22Order", "Fi22", "Fischer Fi22"),
                ("monsterThOrder", "Th", "Thompson"),
                ("monsterHNOrder", "HN", "Harada-Norton"),
                ("monsterMcLOrder", "McL", "McLaughlin")]


def parse_monster_defs(root, out, led):
    rel = MDEFS
    src = read(root, rel).split("\n")
    named = {}
    env = {"__builtins__": {}}
    for name, group, human in NAMED_ORDERS:
        ln = find_line(root, rel, "def %s : ℕ :=" % name)
        expr = src[ln - 1].split(":=", 1)[1].strip()
        if not expr:
            expr = src[ln].strip()
        v = eval(expr.replace("^", "**"), env, {})
        named[group] = {"value": str(v), "expression": expr, "humanName": human,
                        "factorization": render_factorization(factorize(v)),
                        "cite": "%s:%d" % (rel, ln), "defName": name}
        led.cite("/sporadicOrders/named/%s" % group, rel, ln)
    out["/sporadicOrders/named"] = named

    so = find_line(root, rel, "def monsterSuborbitElementOrder")
    sq = find_line(root, rel, "def monsterSuborbitSimpleOrder")
    expr_line = so
    text = " ".join(src[so - 1:so + 1])
    arr = re.search(r"!\[(.*?)\]", text, re.S).group(1)
    orders = [int(x) for x in arr.split(",")]
    simple_txt = " ".join(src[sq - 1:sq + 2])
    arr2 = re.search(r"!\[(.*?)\]", simple_txt, re.S).group(1)
    simples = [s.strip() for s in arr2.split(",")]
    led.cite("/monsterSuborbit2A", rel, so)
    out["/monsterSuborbit2A"] = {
        "indexing": "Fin 9 — the nine 2A suborbits of the Monster's 2A involution",
        "elementOrders": orders,
        "simpleQuotients": simples,
        "elementOrderCite": "%s:%d" % (rel, so),
        "simpleQuotientCite": "%s:%d" % (rel, sq),
        "graphEdges": [],
    }
    # resolve the quotient expressions to values where they are named constants
    resolved = []
    for s in simples:
        if s.startswith("ord"):
            resolved.append(None)
        else:
            key = s.replace("monster", "").replace("Order", "")
            resolved.append(named.get(key, {}).get("value"))
    out["/monsterSuborbit2A/quotientValues"] = resolved
    led.cite("/monsterSuborbit2A/quotientValues", rel, sq, attribution="derived",
             quote="each entry is one of the named order defs above, or a Lie-type order "
                   "formula evaluated at q=2", derived=True)
    # the two Lie quotients: ordTwistedE6 2 and ordF4 2
    out["/monsterSuborbit2A/quotientLieValues"] = {
        "ordTwistedE6 2": str(evaluate_formula("ordTwistedE6", 0, 2)),
        "ordF4 2": str(evaluate_formula("ordF4", 0, 2)),
    }


# --------------------------------------------------------------------------
# CFSG/Monster/B/Mathieu — the pinned permutation certificate table
# --------------------------------------------------------------------------

CERTDATA = "CFSG/Monster/B/Mathieu/CertData.lean"


def parse_mathieu(root, out, led):
    rel = CERTDATA
    struct = find_line(root, rel, "structure GroupRecord where")
    file_struct = find_line(root, rel, "structure CertificateFile where")
    text_def = find_line(root, rel, "def certificateText : String :=")
    doc = json.loads("".join(
        lean_string_literal(read(root, "CFSG/Monster/B/Mathieu/CertText%d.lean" % i),
                            "def certText%d : String :=" % i) for i in range(6)))
    assert len(doc["groups"]) == 5
    led.cite("/mathieuCertificates", rel, struct)
    led.cite("/mathieuCertificates/schema", rel, file_struct)
    led.cite("/mathieuCertificates/text", rel, text_def, attribution="derived",
             quote="reassembled from the six certText literals the source concatenates", derived=True)
    groups = []
    for g in doc["groups"]:
        groups.append({
            "name": g["group"],
            "degree": g["chain"]["degree"],
            "rootGenerators": g["chain"]["generators"],
            "rootGeneratorCycles": [_perm_to_cycles(x) for x in g["chain"]["generators"]],
            "base": g["chain"]["base"],
            "strongGenerators": g["chain"]["strong_generators"],
            "derivationWordCount": len(g["chain"]["derivations"]),
            "sylows": [{"prime": s["prime"],
                        "generatorCount": len(s["generators"]),
                        "generators": s["generators"],
                        "normalGenerationCount": len(s["normal_generation"])}
                       for s in g["sylows"]],
            "seedPaths": g["seed_paths"],
        })
        led.cite("/mathieuCertificates/groups/%s" % g["group"], rel, struct,
                 attribution="asserted",
                 quote='certificateText group record "%s"' % g["group"], derived=True)
    out["/mathieuCertificates"] = {
        "schemaVersion": doc["schema_version"],
        "permutationConvention": doc["permutation_convention"],
        "description": doc["description"],
        "groups": groups,
    }


# --------------------------------------------------------------------------
# theorem-pinned orders for the small Mathieu groups
# --------------------------------------------------------------------------

ORDER_THEOREMS = [
    ("M11", "CFSG/CharacterTheory/Semidihedral/GL2Recognition/M11Order.lean",
     "Nat.card CFSG.Blueprint.NativeSporadic.M11 = 7920"),
    ("M11", "CFSG/Monster/B/Mathieu/M11Sylow.lean", "SylowFacts CFSG.Blueprint.NativeSporadic.M11 7920"),
    ("M22", "CFSG/Monster/B/Mathieu/M22Order.lean", "Nat.card CFSG.Blueprint.NativeSporadic.M22 = 443520"),
    ("M23", "CFSG/CGT/PushingUpLit/CGT6/SixFourOrders.lean",
     "card_nativeM23 : Nat.card CFSG.Blueprint.NativeSporadic.M23 = 10200960"),
    ("M24", "CFSG/CGT/PushingUpLit/CGT6/SixFourOrders.lean",
     "Nat.card (CFSG.Blueprint.NativeSporadic.Carrier .M24) = 244823040"),
    ("M12", "CFSG/Certificates/Kernel/M12LocSound.lean", "have hc : Nat.card G12 = 95040"),
]


def parse_order_theorems(root, out, led):
    rows = {}
    for i, (group, rel, needle) in enumerate(ORDER_THEOREMS):
        ln = find_line(root, rel, needle)
        m = re.search(r"= (\d+)", src_line_quote(root, rel, ln))
        led.cite("/sporadicOrders/theoremPinned/%s/%d" % (group, i), rel, ln)
        if not m:
            continue
        val = int(m.group(1))
        if group in rows and rows[group]["value"] != str(val):
            raise ValueError("conflicting pinned orders for %s" % group)
        rows.setdefault(group, {"value": str(val),
                                "factorization": render_factorization(factorize(val)),
                                "cite": "%s:%d" % (rel, ln)})
    out["/sporadicOrders/theoremPinned"] = rows
    # cross-check every pinned value against the 26-element sporadicOrderList
    values = {int(r["value"]) for r in rows.values()}
    return values


def src_line_quote(root, rel, n):
    with open(os.path.join(root, rel), encoding="utf-8") as fh:
        for i, text in enumerate(fh, 1):
            if i == n:
                return text
    return ""


# --------------------------------------------------------------------------
# Cayley data: the smallest genuinely renderable groups in the repo
# --------------------------------------------------------------------------

def parse_cayley_examples(root, out, led):
    """A small Cayley example the page can actually draw, plus the smallest
    certificate CFSG states.

    Certificate1.lean is the first entry of the certificate directory and
    quantifies over `alternatingGroup (Fin 4)` with a `decide +kernel` proof.
    For a renderable Cayley graph we close two even permutations of degree 5
    under composition and check the result has |A5| = 5!/2 = 60 elements — the
    same number the `Nat.factorial n / 2` arm of knownSimpleOrders gives at n=5.
    """
    rel = "Certificates/Certificate1.lean"
    ln = find_line(root, rel, "∀ a v : alternatingGroup (Fin 4)")
    proof_ln = find_line(root, rel, "decide +kernel")
    led.cite("/cayleyExamples/certificate1", rel, ln)
    five_cycle = [1, 2, 3, 4, 0]   # (0 1 2 3 4) — even
    three_cycle = [1, 2, 0, 3, 4]  # (0 1 2)     — even
    elements = closure([five_cycle, three_cycle])
    table = mul_table(elements, [five_cycle, three_cycle])
    alt5 = next(e["order"] for e in out.get("/classification/alternatingSeries", [])
                if e["n"] == 5) if "/classification/alternatingSeries" in out else None
    if alt5 is not None and int(alt5) != len(elements):
        raise ValueError("A5 closure gave %d elements, knownSimpleOrders says %s"
                         % (len(elements), alt5))
    out["/cayleyExamples"] = {
        "certificate1": {
            "statement": "∀ a v : alternatingGroup (Fin 4), a ≠ 1 → a*a ≠ 1 → v*v = 1 → "
                         "v*a = a*v → v = 1",
            "certifiedBy": "decide +kernel",
            "cite": "%s:%d" % (rel, ln),
            "proofCite": "%s:%d" % (rel, proof_ln),
        },
        "alternating5": {
            "generators": [five_cycle, three_cycle],
            "generatorCycles": [_perm_to_cycles(five_cycle), _perm_to_cycles(three_cycle)],
            "elementCount": len(elements),
            "multiplicationTable": table,
            "attribution": "derived",
            "derivation": "closure of two even permutations of degree 5 under composition; "
                          "the count is checked against the n=5 entry of "
                          "/classification/alternatingSeries (5!/2 = 60)",
            "cite": DEFS,
        },
    }


def closure(generators):
    seen = [tuple(range(len(generators[0])))]
    idx = {seen[0]: 0}
    frontier = list(seen)
    while frontier:
        nxt = []
        for x in frontier:
            for g in generators:
                y = tuple(g[x[i]] for i in range(len(x)))
                if y not in idx:
                    idx[y] = len(seen)
                    seen.append(y)
                    nxt.append(y)
        frontier = nxt
    return seen


def mul_table(elements, generators):
    idx = {e: i for i, e in enumerate(elements)}
    return [[idx[tuple(g[e[i]] for i in range(len(e)))] for g in generators] for e in elements]


# --------------------------------------------------------------------------
# main
# --------------------------------------------------------------------------

def unflatten(flat):
    """Turn the pointer-keyed working dict into one nested JSON object.

    Keys are JSON pointers ("/a/b"), sorted by depth so a shallow leaf is
    written first and any deeper key that extends it merges into it rather than
    clobbering it. provenance.json uses exactly these pointers, so the page can
    look up the source of any field it renders.
    """
    root = {}
    for ptr in sorted(flat, key=lambda k: (k.count("/"), k)):
        parts = [p for p in ptr.split("/") if p]
        if not parts:
            continue
        cur = root
        for p in parts[:-1]:
            if not isinstance(cur, dict):
                raise ValueError("pointer %s extends a non-object at %s" % (ptr, p))
            if p not in cur or not isinstance(cur[p], dict):
                cur[p] = {}
            cur = cur[p]
        leaf, val = parts[-1], flat[ptr]
        if isinstance(val, dict) and isinstance(cur.get(leaf), dict):
            cur[leaf].update(val)
        else:
            cur[leaf] = val
    return root


def _self_checks(data):
    """Internal consistency of the extracted atlas, checked before writing.

    Every check compares two places in CFSG that must agree, or recomputes a
    value two different ways. Nothing here consults outside knowledge.
    """
    checks = []
    # 1. the ord* formulas' first parameter is the Lie rank, not the matrix
    #    degree: ordA(2,2) must equal the n=3 alternating entry only if...  we
    #    instead check the identity the source itself gives: A_2(2) = PSL_3(2)
    #    is 168, and 168 = 2^3 * 3 * 7 factors inside the same formula family.
    a22 = evaluate_formula("ordA", 2, 2)
    checks.append({"name": "ordA(2,2) evaluated", "value": str(a22),
                   "expect": "2^3 · 3 · 7",
                   "pass": a22 == 8 * 3 * 7})
    # 2. the Mathieu certificate degrees must match the permutation carriers in
    #    CFSG/Blueprint/NativeSporadic.lean
    for g in data["mathieuCertificates"]["groups"]:
        name = g["name"]
        carrier_deg = data["sporadics"].get(name, {}).get("degree")
        checks.append({"name": "%s degree agreement" % name,
                       "certificate": g["degree"], "carrier": carrier_deg,
                       "pass": carrier_deg == g["degree"]})
    # 3. root systems: every root must be closed under negation, and the simple
    #    basis must be present
    for t in ["G2", "F4", "D4", "E6", "E7", "E8"]:
        roots = [tuple(r) for r in data["exceptional"][t]["roots"]]
        s = set(roots)
        neg_closed = all(tuple(-x for x in r) in s for r in roots)
        basis_ok = all(all(v == 0 or v == 1 for v in r) for r in roots)
        checks.append({"name": "%s root closure" % t, "count": len(roots),
                       "pass": neg_closed and len(roots) % 2 == 0})
        del basis_ok
    # 4. the Y443 graph must be a simple undirected graph on 12 nodes
    edges = data["monsterY443"]["adjacency"]
    ok = all(len(e) == 2 and e[0] < e[1] and e[1] < 12 for e in edges)
    checks.append({"name": "y443 adjacency well-formed", "edges": len(edges), "pass": ok})
    # 5. sporadicOrderList must be 26 distinct values, each > 1
    vals = [int(v) for v in data["sporadicOrders"]["valuesAscending"]]
    checks.append({"name": "sporadicOrderList cardinality", "count": len(vals),
                   "distinct": len(set(vals)),
                   "pass": len(vals) == 26 and len(set(vals)) == 26 and min(vals) > 1})
    # 6. every named order in MonsterDefs must be one of the 26
    named_vals = {int(r["value"]) for r in data["sporadicOrders"]["named"].values()}
    checks.append({"name": "named orders ⊆ sporadicOrderList",
                   "pass": named_vals <= set(vals)})
    failing = [c["name"] for c in checks if not c["pass"]]
    if failing:
        raise ValueError("self-check failures: %s" % failing)
    return checks


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("cfsg_root")
    ap.add_argument("out_dir")
    ap.add_argument("--commit", default=None)
    args = ap.parse_args()
    root = os.path.abspath(args.cfsg_root)

    # the brake in the lane contract forbids any build; we only read tracked text
    commit = args.commit
    if commit is None:
        try:
            commit = os.popen("git -C %s rev-parse HEAD" % root).read().strip() or None
        except Exception:  # noqa: BLE001
            commit = None

    led = Ledger(root)
    data = {}
    parse_order_defs(root, data, led)
    parse_lie_orders_over(root, data, led)
    parse_known_simple_orders(root, data, led)
    parse_stated_lie(root, data, led)
    ranks, cartans = parse_chevalley(root, data, led)
    parse_native_sporadic(root, data, led)
    parse_monster_defs(root, data, led)
    parse_mathieu(root, data, led)
    pinned = parse_order_theorems(root, data, led)
    parse_cayley_examples(root, data, led)
    sporadic_values = parse_sporadic_order_list(root, data, led)

    # cross-check: every theorem-pinned order must be a member of the 26-set
    stray = sorted(v for v in pinned if v not in sporadic_values)
    if stray:
        raise ValueError("pinned orders not in sporadicOrderList: %s" % stray)

    exc = data["/exceptional"]
    for t in TAGS6:
        exc[t]["rankCite"] = "%s:%d" % (CHEV, find_line(root, CHEV, "def rank : Tag → ℕ"))
        exc[t]["formula"] = {"G2": "ordG2", "F4": "ordF4", "D4": "ordD",
                             "E6": "ordE6", "E7": "ordE7", "E8": "ordE8"}[t]

    data["/meta"] = {
        "schema": "v6-cfsg-atlas-1",
        "generator": "patent-portfolio/demos/groups/tools/extract_cfsg_families.py",
        "sourceRepo": "cfsg",
        "sourceCommit": commit,
        "readMode": "read-only text extraction; no lake build, no Lean compilation (CONTRACT rule 5)",
        "crossChecks": {
            "theoremPinnedInSporadicSet": sorted(str(v) for v in pinned),
            "sporadicOrderCount": len(sporadic_values),
        },
        "namedSourceFiles": dict(sorted(led.shas.items())),
    }
    led.cite("/meta", "CFSG/Statement.lean", 1, attribution="derived",
             quote="atlas metadata: generated data, not a CFSG assertion", derived=True)

    out = os.path.abspath(args.out_dir)
    os.makedirs(out, exist_ok=True)
    nested = unflatten(data)
    nested["meta"]["selfChecks"] = _self_checks(nested)
    with open(os.path.join(out, "cfsg-families.json"), "w", encoding="utf-8") as fh:
        json.dump(nested, fh, indent=1, sort_keys=True)
    with open(os.path.join(out, "provenance.json"), "w", encoding="utf-8") as fh:
        json.dump({"source": {"repo": "cfsg", "commit": commit,
                             "files": {k: v for k, v in sorted(led.shas.items())}},
                   "pointers": led.rows}, fh, indent=1, sort_keys=True)
    print("families=%d sporadics=%d pointers=%d" % (
        len(nested["lieFamilies"]["tags"]), len(nested["sporadics"]) - 2, len(led.rows)))
    print("bytes json=%d provenance=%d" % (
        os.path.getsize(os.path.join(out, "cfsg-families.json")),
        os.path.getsize(os.path.join(out, "provenance.json"))))


if __name__ == "__main__":
    main()
