/**
 * sha256.js — FIPS 180-4 SHA-256 over bytes, synchronous, dependency-free.
 *
 * WHY A HAND-ROLLED ONE. The estate seed law (js/seed-stream.js, a bit-exact port
 * of kagami core `packages/kagami/core/omni/prng.py:63-104`) expands its stream by
 * hashing `prefix || counter8_be` with SHA-256 in COUNTER MODE. The browser's own
 * hash, `crypto.subtle.digest`, is ASYNC; the carrier's coefficient table has to be
 * built synchronously before a frame is drawn, and an await inside the pixel path
 * is not available. Node's `node:crypto` is not a browser module. So the demo
 * carries the primitive.
 *
 * It is graded, not assumed: tools/determinism-harness.mjs compares this file's
 * digests against `node:crypto`'s SHA-256 over 2,000+ inputs (every length
 * 0..300 bytes plus pseudorandom buffers of hundreds of blocks), against the
 * four known-answer vectors in SHA256_SELFTEST — and the in-browser leg
 * compares against WebCrypto in the same page, so this implementation is
 * measured against a different one on BOTH engines, plus against Python's
 * hashlib (a third implementation) for the estate stream's golden words.
 *
 * Everything here is exactly specified by ECMA-262: >>> , ^ & + on int32 via
 * ToInt32/ToUint32, and Math.imul is not needed (SHA-256 has no multiply). No
 * Math.sin, no floating point at all, so the digest is the same bytes in every
 * engine, which is what makes the pinned frames cross-engine identical.
 */

const K = new Uint32Array([
  0x428a2f98, 0x71374491, 0xb5c0fbcf, 0xe9b5dba5, 0x3956c25b, 0x59f111f1, 0x923f82a4, 0xab1c5ed5,
  0xd807aa98, 0x12835b01, 0x243185be, 0x550c7dc3, 0x72be5d74, 0x80deb1fe, 0x9bdc06a7, 0xc19bf174,
  0xe49b69c1, 0xefbe4786, 0x0fc19dc6, 0x240ca1cc, 0x2de92c6f, 0x4a7484aa, 0x5cb0a9dc, 0x76f988da,
  0x983e5152, 0xa831c66d, 0xb00327c8, 0xbf597fc7, 0xc6e00bf3, 0xd5a79147, 0x06ca6351, 0x14292967,
  0x27b70a85, 0x2e1b2138, 0x4d2c6dfc, 0x53380d13, 0x650a7354, 0x766a0abb, 0x81c2c92e, 0x92722c85,
  0xa2bfe8a1, 0xa81a664b, 0xc24b8b70, 0xc76c51a3, 0xd192e819, 0xd6990624, 0xf40e3585, 0x106aa070,
  0x19a4c116, 0x1e376c08, 0x2748774c, 0x34b0bcb5, 0x391c0cb3, 0x4ed8aa4a, 0x5b9cca4f, 0x682e6ff3,
  0x748f82ee, 0x78a5636f, 0x84c87814, 0x8cc70208, 0x90befffa, 0xa4506ceb, 0xbef9a3f7, 0xc67178f2,
]);

// The 64 round constants and the 8 initial words above were not typed from
// memory: they are DERIVED in exact integer arithmetic (floor of the fractional
// part of the cube root / square root of the first 64 / 8 primes, scaled by
// 2^96 and shifted down, with a guard-bit check that none of them sits within
// 2^-56 of a rounding boundary), by the same recipe FIPS 180-4 §4.2.2 states.
// A wrong constant is not silently tolerated either: SHA256_SELFTEST and the
// harness's 2,000-case comparison against node:crypto both fail on it.

const rotr = (x, n) => ((x >>> n) | (x << (32 - n))) >>> 0;

/** SHA-256 of `bytes` (Uint8Array/array of octets). Returns Uint8Array(32). */
export function sha256(bytes) {
  const msg = bytes instanceof Uint8Array ? bytes : Uint8Array.from(bytes);
  const len = msg.length;
  const bitLen = len * 8;
  // padded length: len + 1 + padZeros + 8 ≡ 0 (mod 64), padZeros >= 0, and the
  // result is always a whole number of blocks strictly longer than the message.
  const padded = new Uint8Array(((((len + 8) >> 6) + 1) << 6));
  padded.set(msg);
  padded[len] = 0x80;
  // 64-bit big-endian bit length; JS numbers are exact to 2^53, so the high word
  // is zero for any buffer this demo will ever hash (a frame is 65,536 bytes).
  const hi = Math.floor(bitLen / 0x100000000);
  const lo = bitLen >>> 0;
  const dv = new DataView(padded.buffer);
  dv.setUint32(padded.length - 8, hi, false);
  dv.setUint32(padded.length - 4, lo, false);

  let h0 = 0x6a09e667, h1 = 0xbb67ae85, h2 = 0x3c6ef372, h3 = 0xa54ff53a;
  let h4 = 0x510e527f, h5 = 0x9b05688c, h6 = 0x1f83d9ab, h7 = 0x5be0cd19;
  const w = new Uint32Array(64);

  for (let off = 0; off < padded.length; off += 64) {
    for (let i = 0; i < 16; i++) w[i] = dv.getUint32(off + i * 4, false);
    for (let i = 16; i < 64; i++) {
      const s0 = (rotr(w[i - 15], 7) ^ rotr(w[i - 15], 18) ^ (w[i - 15] >>> 3)) >>> 0;
      const s1 = (rotr(w[i - 2], 17) ^ rotr(w[i - 2], 19) ^ (w[i - 2] >>> 10)) >>> 0;
      w[i] = (w[i - 16] + w[i - 7] + s0 + s1) >>> 0;
    }
    let a = h0, b = h1, c = h2, d = h3, e = h4, f = h5, g = h6, hh = h7;
    for (let i = 0; i < 64; i++) {
      const S1 = (rotr(e, 6) ^ rotr(e, 11) ^ rotr(e, 25)) >>> 0;
      const ch = ((e & f) ^ (~e & g)) >>> 0;
      const t1 = (hh + S1 + ch + K[i] + w[i]) >>> 0;
      const S0 = (rotr(a, 2) ^ rotr(a, 13) ^ rotr(a, 22)) >>> 0;
      const maj = ((a & b) ^ (a & c) ^ (b & c)) >>> 0;
      const t2 = (S0 + maj) >>> 0;
      hh = g; g = f; f = e;
      e = (d + t1) >>> 0;
      d = c; c = b; b = a;
      a = (t1 + t2) >>> 0;
    }
    h0 = (h0 + a) >>> 0; h1 = (h1 + b) >>> 0; h2 = (h2 + c) >>> 0; h3 = (h3 + d) >>> 0;
    h4 = (h4 + e) >>> 0; h5 = (h5 + f) >>> 0; h6 = (h6 + g) >>> 0; h7 = (h7 + hh) >>> 0;
  }

  const out = new Uint8Array(32);
  const odv = new DataView(out.buffer);
  [h0, h1, h2, h3, h4, h5, h6, h7].forEach((x, i) => odv.setUint32(i * 4, x, false));
  return out;
}

/** Lower-case hex digest, the shape both node and the page print. */
export function sha256Hex(bytes) {
  const d = sha256(bytes);
  let s = '';
  for (let i = 0; i < 32; i++) s += (d[i] + 0x100).toString(16).slice(1);
  return s;
}

/** UTF-8 bytes of a string, without TextEncoder (six lines, no ambient API). */
export function utf8(str) {
  const out = [];
  for (let i = 0; i < str.length; i++) {
    let c = str.charCodeAt(i);
    if (c >= 0xd800 && c <= 0xdbff && i + 1 < str.length) {
      const lo = str.charCodeAt(i + 1);
      if (lo >= 0xdc00 && lo <= 0xdfff) { c = 0x10000 + ((c - 0xd800) << 10) + (lo - 0xdc00); i++; }
    }
    if (c < 0x80) out.push(c);
    else if (c < 0x800) out.push(0xc0 | (c >> 6), 0x80 | (c & 63));
    else if (c < 0x10000) out.push(0xe0 | (c >> 12), 0x80 | ((c >> 6) & 63), 0x80 | (c & 63));
    else out.push(0xf0 | (c >> 18), 0x80 | ((c >> 12) & 63), 0x80 | ((c >> 6) & 63), 0x80 | (c & 63));
  }
  return Uint8Array.from(out);
}

/**
 * Known-answer set: the 0-byte, 3-byte, 56-byte and 88-byte messages, so the
 * one-block, the padding-spills-into-a-second-block, and a mid-block cases are
 * all covered. The expected digests below were produced on this host by
 * Python's `hashlib.sha256` (an OpenSSL C implementation, independent of both
 * this file and of node:crypto) rather than recalled: the first two also match
 * the FIPS 180-4 samples. The harness re-grades all four against node:crypto
 * and against 2,000 further inputs.
 */
export const SHA256_SELFTEST = [
  ['', 'e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855'],
  ['abc', 'ba7816bf8f01cfea414140de5dae2223b00361a396177a9cb410ff61f20015ad'],
  ['abcdbcdecdefdefgefghfghighijhijkijkljklmklmnlmnomnopnopq',
    '248d6a61d20638b8e5c026930c3e6039a33ce45964ff2167f6ecedd419db06c1'],
  ['abcdefghbcdefghicdefghijdefghijkefghijklfghijklmghijklmnhijklmnoijklmnopjklmnopqklmnopqr',
    '743fde1b432e6fcd9199f291329c88744ccf3a36f5527898fbb1bcf66ddb1667'],
];

export const K_LEN = K.length;
