/**
 * Design-token index accessors wrap negative indices (lane ART-RSI-e87513).
 *
 * Defect: getColonyHex / getColonyHexString / getColonyColor used a bare
 * `index % 7`. JS `%` keeps the dividend's sign, so -1 % 7 === -1 and
 * COLONY_ORDER[-1] is undefined — calling getColonyHex(-1) threw
 * "TypeError: Cannot read properties of undefined (reading 'num')".
 * Negative indexing is the natural "previous colony on the Fano cycle"
 * read, so the accessors now wrap through ((index % 7) + 7) % 7.
 *
 * Consumer check: npm run test:unit (this file runs in its glob).
 */
import { test } from "node:test";
import assert from "node:assert/strict";

import {
  COLONY_ORDER, COLONY_COLORS, getColonyHex, getColonyHexString, getColonyColor,
} from "../../lib/design-tokens.js";

test("negative indices wrap onto the Fano cycle instead of throwing", () => {
  for (let i = -14; i < 0; i++) {
    const wrapped = ((i % 7) + 7) % 7;
    assert.equal(getColonyHex(i), COLONY_COLORS[COLONY_ORDER[wrapped]].num,
      `getColonyHex(${i}) should equal colony at wrapped index ${wrapped}`);
    assert.equal(getColonyHexString(i), COLONY_COLORS[COLONY_ORDER[wrapped]].hex,
      `getColonyHexString(${i}) should equal colony at wrapped index ${wrapped}`);
  }
  // -1 is the previous colony before spark: crystal (e7).
  assert.equal(getColonyHex(-1), COLONY_COLORS.crystal.num);
  assert.equal(getColonyHexString(-1), COLONY_COLORS.crystal.hex);
  assert.equal(getColonyHex(-7), COLONY_COLORS.spark.num);
});

test("getColonyColor wraps negative indices through the same cycle", () => {
  const seen = [];
  function Color(n) { seen.push(n); this.value = n; }
  const THREE = { Color };
  getColonyColor(THREE, -1);
  getColonyColor(THREE, -8);
  assert.deepEqual(seen, [COLONY_COLORS.crystal.num, COLONY_COLORS.crystal.num]);
});

test("non-negative behaviour is unchanged (one full cycle + overflow)", () => {
  for (let i = 0; i < 7; i++) {
    assert.equal(getColonyHex(i), COLONY_COLORS[COLONY_ORDER[i]].num);
    assert.equal(getColonyHexString(i), COLONY_COLORS[COLONY_ORDER[i]].hex);
  }
  assert.equal(getColonyHex(7), COLONY_COLORS.spark.num);
  assert.equal(getColonyHex(15), COLONY_COLORS.forge.num);
});
