/**
 * lib/realtime-voice.js — the client must not invent an endpoint or a persona.
 *
 * Both defaults removed here were silent substitutions on a product path:
 * `ws://localhost:8766` sent a published page at a developer's laptop, and
 * `alloy` replaced a project's colony voice whenever kagami-voices.js failed
 * to load, making a missing persona indistinguishable from Kagami's own.
 */
import assert from "node:assert/strict";
import test from "node:test";
import { loadBrowserLib } from "./load-browser-lib.mjs";

function RealtimeVoice() {
  return loadBrowserLib("lib/realtime-voice.js", { WebSocket: class {} }).RealtimeVoice;
}

function caught(fn) {
  try {
    fn();
  } catch (e) {
    return e;
  }
  return assert.fail("expected a throw — a silent default is the bug under test");
}

test("a missing proxyUrl throws and names realtime-endpoint.js", () => {
  const err = caught(() => new (RealtimeVoice())({ voice: "echo" }));
  assert.equal(err.name, "TypeError");
  assert.match(err.message, /proxyUrl is required/);
  assert.match(err.message, /resolveRealtimeEndpoint/);
  assert.match(err.message, /8766/);
});

test("a missing voice throws and names kagami-voices.js", () => {
  const err = caught(() => new (RealtimeVoice())({ proxyUrl: "wss://p.example" }));
  assert.equal(err.name, "TypeError");
  assert.match(err.message, /voice is required/);
  assert.match(err.message, /kagami-voices\.js/);
});

test("an empty-string proxyUrl is rejected, not treated as present", () => {
  const err = caught(() => new (RealtimeVoice())({ proxyUrl: "", voice: "echo" }));
  assert.match(err.message, /proxyUrl is required/);
});

test("both supplied constructs and keeps them verbatim", () => {
  const v = new (RealtimeVoice())({ proxyUrl: "wss://p.example/?project=clue", voice: "onyx" });
  assert.equal(v.proxyUrl, "wss://p.example/?project=clue");
  assert.equal(v.voice, "onyx");
  assert.equal(v.state, "disconnected");
});
