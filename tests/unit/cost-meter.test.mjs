/**
 * realtime-proxy/cost-meter.js — the proxy must bill what OpenAI reports.
 *
 * The replaced `estimateCostCents()` charged 0.3¢ per audio delta, 0.1¢ per
 * input chunk and 0.02¢ for anything it did not recognise. Those numbers were
 * published through /stats as `totalCostCents` and used to enforce
 * SESSION_COST_CAP, so the cap was applied to a fabricated quantity.
 */
import assert from "node:assert/strict";
import test from "node:test";
import { CostMeter } from "../../realtime-proxy/cost-meter.js";

// USD per 1M tokens, matching realtime-proxy/fly.toml [env].
const PRICES = { textIn: 4, textOut: 24, audioIn: 32, audioOut: 64 };

const doneWith = (usage) => ({ type: "response.done", response: { usage } });

test("a fresh meter is unmetered — zero means 'nothing billed', not 'measured free'", () => {
  const m = new CostMeter(PRICES);
  assert.equal(m.cents, 0);
  assert.equal(m.metered, false);
  assert.equal(m.responses, 0);
});

test("messages without a usage block are not billed", () => {
  const m = new CostMeter(PRICES);
  for (const type of [
    "response.audio.delta",
    "response.audio_transcript.delta",
    "input_audio_buffer.append",
    "response.text.delta",
    "session.created",
  ]) {
    assert.equal(m.record({ type }), false, `${type} must not be billed`);
  }
  assert.equal(m.cents, 0);
  assert.equal(m.metered, false);
});

test("response.done meters the real token split at the configured prices", () => {
  const m = new CostMeter(PRICES);
  assert.equal(
    m.record(
      doneWith({
        input_tokens: 1_500_000,
        output_tokens: 1_200_000,
        input_token_details: { text_tokens: 1_000_000, audio_tokens: 500_000 },
        output_token_details: { text_tokens: 1_000_000, audio_tokens: 200_000 },
      }),
    ),
    true,
  );
  // 1M*4 + 0.5M*32 + 1M*24 + 0.2M*64 = 4 + 16 + 24 + 12.8 = $56.80 = 5680¢
  assert.equal(Math.round(m.cents * 100) / 100, 5680);
  assert.equal(m.metered, true);
  assert.equal(m.responses, 1);
  assert.deepEqual(m.tokens, {
    textIn: 1_000_000,
    audioIn: 500_000,
    textOut: 1_000_000,
    audioOut: 200_000,
  });
});

test("costs accumulate across responses", () => {
  const m = new CostMeter(PRICES);
  const one = doneWith({
    input_token_details: { text_tokens: 1_000_000, audio_tokens: 0 },
    output_token_details: { text_tokens: 0, audio_tokens: 0 },
  });
  m.record(one);
  m.record(one);
  assert.equal(Math.round(m.cents), 800); // 2 × $4
  assert.equal(m.responses, 2);
});

test("a missing modality split falls back to the aggregate, priced as text", () => {
  const m = new CostMeter(PRICES);
  m.record(doneWith({ input_tokens: 1_000_000, output_tokens: 1_000_000 }));
  assert.equal(Math.round(m.cents), 2800); // $4 + $24
  assert.deepEqual(m.tokens, { textIn: 1_000_000, audioIn: 0, textOut: 1_000_000, audioOut: 0 });
});

test("a usage block on a non-response.done frame is ignored", () => {
  const m = new CostMeter(PRICES);
  assert.equal(m.record({ type: "response.created", usage: { input_tokens: 1_000_000 } }), false);
  assert.equal(m.cents, 0);
});

test("malformed frames are inert rather than charged a default", () => {
  const m = new CostMeter(PRICES);
  for (const frame of [null, undefined, {}, { type: "response.done" }, { type: "response.done", response: {} }]) {
    assert.equal(m.record(frame), false);
  }
  assert.equal(m.cents, 0);
  assert.equal(m.metered, false);
});
