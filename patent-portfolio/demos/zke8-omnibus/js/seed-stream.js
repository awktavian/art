/**
 * seed-stream.js — bit-exact port of the estate's deterministic word stream.
 *
 * Source of the law: kagami core `packages/kagami/core/omni/prng.py:63-144`
 * (`SeededWordStream`), whose bit-level contract is stated at prng.py:17-27 and
 * pinned by `packages/kagami/tests/core/omni/test_eth_jit.py`. That module is the
 * ONE repo-owned generator for the omni corpus builders (`eth_jit`, `eth_spool`)
 * and the paired-timing benches, and it exists to remove a specific defect:
 * stdlib `random.Random(seed)` instances (Mersenne Twister) and any `None` seed
 * drawing OS entropy — prng.py:72-73 makes a `None` seed a hard error, "a
 * nondeterministic corpus is the defect".
 *
 * Why port THIS rather than just use the art repo's house PRNG (Xorshift128+ over
 * an FNV-1a hash, `PRNG` in js/e8-core.js, which the art conventions mandate and
 * which stays the default here): the estate stream is the only mechanism in the
 * chain that is *specified to the bit* on both sides of the port. SHA-256 in
 * counter mode with a big-endian counter and big-endian words is the same
 * arithmetic in Python and in JS, so equality is checkable end to end — 64-bit
 * words, 53-bit fractions, rejection-sampled integers, and the eight carrier lane
 * coefficients that come out of them. `tools/gen-estate-seed-vectors.py` runs the
 * REAL estate module at the live kagami checkout and writes what it produced;
 * `tools/determinism-harness.mjs` grades this file against those bytes. That makes
 * "the browser draws the picture Kagami would have seeded" a measured claim rather
 * than a metaphor.
 *
 * Verbatim semantics carried over, each with its Python origin:
 *   _canonical_seed_bytes   prng.py:47-60   (b"int"|width2BE|valueBE, b"str"|utf8,
 *                                            b"bytes"|bytes; bool and negative and
 *                                            None and other types are REFUSALS)
 *   _word                   prng.py:79-88   (sha256(prefix || counter 8-byte BE),
 *                                            words taken big-endian, counter mode)
 *   getrandbits             prng.py:90-101  (k<=64: one word, top k bits;
 *                                            k>64: ceil(k/64) words concatenated
 *                                            then trimmed to k bits)
 *   random                  prng.py:103-104 (53 bits / 2**53, the stdlib float width)
 *   _below                  prng.py:106-114 (rejection over n.bit_length() bits)
 *   randrange/randint       prng.py:116-127
 *   choice                  prng.py:129-132
 *   sample                  prng.py:134-144 (partial Fisher-Yates, in-place swap
 *                                            on a copy of the pool)
 *
 * 64-bit words are BigInt, which is exactly specified and never loses a bit; the
 * only place a Number appears is `random()`, where Python's own contract is a
 * double (53 bits over 2**53), so the two languages land on the same IEEE value.
 */

import { sha256, utf8 } from './sha256.js';
import { fieldFromUniform } from './e8-core.js';

const BLOCK_BYTES = 32;
const WORD_BYTES = 8;
const B64 = 64n;
const MASK64 = (1n << B64) - 1n;

/** bit_length of a non-negative BigInt (Python int.bit_length). */
function bitLength(x) {
  let n = 0;
  let v = x;
  while (v > 0n) { v >>= 1n; n++; }
  return n;
}

function beBytes(value, width) {
  const out = new Uint8Array(width);
  let v = value;
  for (let i = width - 1; i >= 0; i--) { out[i] = Number(v & 255n); v >>= 8n; }
  return out;
}

function concat(a, b) {
  const out = new Uint8Array(a.length + b.length);
  out.set(a); out.set(b, a.length);
  return out;
}

/**
 * prng.py:47-60. Accepts a BigInt (or safe integer) >= 0, a string, or a
 * Uint8Array. Refusals are errors, not fallbacks: bool, negative, `null`/
 * undefined (the OS-entropy case the estate module refuses at prng.py:72-73) and
 * any other type.
 */
export function canonicalSeedBytes(seed) {
  if (typeof seed === 'boolean') throw new Error('seed must be int, str, or bytes (bool is not a seed)');
  if (seed === null || seed === undefined) throw new Error('seed is required: nondeterministic corpora are the defect');
  if (typeof seed === 'bigint' || (typeof seed === 'number' && Number.isSafeInteger(seed))) {
    const v = BigInt(seed);
    if (v < 0n) throw new Error('seed must be non-negative');
    const width = Math.max((bitLength(v) + 7) >> 3, 1);
    return concat(utf8('int'), concat(beBytes(BigInt(width), 2), beBytes(v, width)));
  }
  if (typeof seed === 'string') return concat(utf8('str'), utf8(seed));
  if (seed instanceof Uint8Array) return concat(utf8('bytes'), seed);
  throw new TypeError(`unsupported seed type: ${Object.prototype.toString.call(seed)}`);
}

export class SeededWordStream {
  constructor(seed) {
    this._prefix = canonicalSeedBytes(seed);
    this._counter = 0;
    this._block = new Uint8Array(0);
    this._pos = BLOCK_BYTES; // force a fresh block on the first word (prng.py:77)
  }

  /** prng.py:79-88 — one big-endian 64-bit word, refilling by counter-mode hash. */
  _word() {
    if (this._pos + WORD_BYTES > this._block.length) {
      this._block = sha256(concat(this._prefix, beBytes(BigInt(this._counter), WORD_BYTES)));
      this._counter += 1;
      this._pos = 0;
    }
    let w = 0n;
    for (let i = 0; i < WORD_BYTES; i++) w = (w << 8n) | BigInt(this._block[this._pos + i]);
    this._pos += WORD_BYTES;
    return w;
  }

  /** prng.py:90-101 — top k bits; k>64 concatenates ceil(k/64) words then trims. */
  getrandbits(k) {
    k = Number(k);
    if (k < 0) throw new Error('number of bits must be non-negative');
    if (k === 0) return 0n;
    if (k <= 64) return this._word() >> BigInt(64 - k);
    const words = Math.ceil(k / 64);
    let value = 0n;
    for (let i = 0; i < words; i++) value = (value << B64) | this._word();
    return value >> BigInt(words * 64 - k);
  }

  /** prng.py:103-104 — 53 bits over 2**53: a double, exactly as stdlib. */
  random() {
    return Number(this.getrandbits(53)) * 2 ** -53;
  }

  /** prng.py:106-114 — uniform in [0,n) by rejection over n.bit_length() bits. */
  _below(n) {
    n = BigInt(n);
    if (n <= 0n) throw new Error(`range empty or not positive: ${n}`);
    const k = bitLength(n);
    let value = this.getrandbits(k);
    while (value >= n) value = this.getrandbits(k);
    return Number(value);
  }

  /** prng.py:116-122 — stdlib bounds and error cases, this stream's bits. */
  randrange(start, stop = null, step = 1) {
    if (step <= 0) throw new Error("randrange() argument 'step' must be positive");
    if (stop === null || stop === undefined) { stop = start; start = 0; }
    const n = Math.max(0, Math.ceil((stop - start) / step)); // len(range(...))
    return start + this._below(n) * step;
  }

  /** prng.py:124-127 — inclusive on both ends. */
  randint(a, b) {
    if (b < a) throw new Error(`empty range for randint(${a}, ${b})`);
    return a + this._below(b - a + 1);
  }

  /** prng.py:129-132 */
  choice(seq) {
    if (seq.length === 0) throw new Error('cannot choose from an empty sequence');
    return seq[this._below(seq.length)];
  }

  /** prng.py:134-144 — partial Fisher-Yates over a copy of the pool. */
  sample(population, k) {
    const n = population.length;
    if (k < 0) throw new Error('negative sample size not allowed');
    if (k > n) throw new Error('sample larger than population');
    const pool = Array.from(population);
    for (let i = 0; i < k; i++) {
      const j = i + this._below(n - i);
      const t = pool[i]; pool[i] = pool[j]; pool[j] = t;
    }
    return pool.slice(0, k);
  }
}

/**
 * The estate-law carrier coefficients. The mapping itself is NOT duplicated here:
 * it is e8-core.js:fieldFromUniform, the one copy of the lane law that the house
 * PRNG also uses, so the two laws differ only in the uniform source. Python's echo
 * of that mapping lives in tools/gen-estate-seed-vectors.py and the harness
 * compares the resulting eight lanes by BIT PATTERN, so a lane that differed by
 * one ulp between Python and the browser would be a FAIL, not a rounding note.
 */
export function fieldCoefficientsEstate(seed, opts = {}) {
  const stream = new SeededWordStream(seed);
  return fieldFromUniform(() => stream.random(), { ...opts, law: 'estate' });
}

/** First `n` 64-bit words, decimal strings — the shape the fixture compares. */
export function words(stream, n) {
  const out = [];
  for (let i = 0; i < n; i++) out.push(stream._word().toString());
  return out;
}
