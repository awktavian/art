import assert from "node:assert/strict";
import { test } from "node:test";
import { COLONY_COLORS } from "../../lib/design-tokens.js";

test("colony colors agree across CSS hex, RGB channels, and Three.js numbers", () => {
  assert.equal(Object.keys(COLONY_COLORS).length, 7);
  for (const [colony, { hex, rgb, num }] of Object.entries(COLONY_COLORS)) {
    assert.match(hex, /^#[0-9a-f]{6}$/i, `${colony}: CSS hex`);
    assert.equal(num, Number.parseInt(hex.slice(1), 16), `${colony}: Three.js color`);
    const channels = [1, 3, 5].map((offset) => Number.parseInt(hex.slice(offset, offset + 2), 16));
    assert.deepEqual(rgb, channels, `${colony}: RGB channels`);
  }
});
