/**
 * lib/realtime-endpoint.js — the single proxy-URL authority.
 *
 * The property under test is that there is NO silent default: a service with
 * no endpoint for the current origin throws a named error rather than handing
 * back a localhost guess that a deployed page can never reach.
 */
import assert from "node:assert/strict";
import test from "node:test";
import { loadBrowserLib } from "./load-browser-lib.mjs";

/** `assert.throws` returns undefined; these tests assert on the error itself. */
function caught(fn) {
  try {
    fn();
  } catch (e) {
    return e;
  }
  return assert.fail("expected a throw, got a value — a silent default is exactly the bug under test");
}

function fresh() {
  return loadBrowserLib("lib/realtime-endpoint.js");
}

test("voice resolves to the local relay on a localhost origin", () => {
  const { resolveRealtimeEndpoint } = fresh();
  const url = resolveRealtimeEndpoint("voice", {
    hostname: "localhost",
    params: { project: "clue", colony: "kagami" },
  });
  assert.equal(url, "ws://localhost:8766/?project=clue&colony=kagami");
});

test("voice resolves to the deployed Fly relay on a published origin", () => {
  const { resolveRealtimeEndpoint } = fresh();
  const url = resolveRealtimeEndpoint("voice", {
    hostname: "awktavian.github.io",
    params: { project: "steamboat-willie" },
  });
  assert.equal(url, "wss://kagami-realtime-proxy.fly.dev/?project=steamboat-willie");
});

test("director is local-only and throws a NAMED error when published", () => {
  const { resolveRealtimeEndpoint, RealtimeEndpointUnavailable } = fresh();
  assert.equal(resolveRealtimeEndpoint("director", { hostname: "127.0.0.1" }), "ws://127.0.0.1:8767/");
  const err = caught(() => resolveRealtimeEndpoint("director", { hostname: "awktavian.github.io" }));
  assert.ok(err instanceof RealtimeEndpointUnavailable);
  // The error must name the service, the origin, and the concrete reason.
  assert.match(err.message, /"director"/);
  assert.match(err.message, /awktavian\.github\.io/);
  assert.match(err.message, /claude-proxy\.js/);
  assert.match(err.message, /KAGAMI_REALTIME_ENDPOINTS/);
  assert.equal(err.service, "director");
});

test("an unknown service is a RangeError, never a guessed URL", () => {
  const { resolveRealtimeEndpoint } = fresh();
  // `RangeError` here is the sandbox realm's, so compare by name, not prototype.
  const err = caught(() => resolveRealtimeEndpoint("gpt", { hostname: "localhost" }));
  assert.equal(err.name, "RangeError");
  assert.match(err.message, /known services: voice, director/);
});

test("window.KAGAMI_REALTIME_ENDPOINTS overrides both branches", () => {
  const w = fresh();
  w.KAGAMI_REALTIME_ENDPOINTS = { director: "wss://director.example" };
  assert.equal(
    w.resolveRealtimeEndpoint("director", { hostname: "awktavian.github.io", params: { project: "x" } }),
    "wss://director.example/?project=x",
  );
});

test("empty query params are dropped rather than sent as empty strings", () => {
  const { resolveRealtimeEndpoint } = fresh();
  assert.equal(
    resolveRealtimeEndpoint("voice", {
      hostname: "localhost",
      params: { project: "clue", colony: undefined, extra: "" },
    }),
    "ws://localhost:8766/?project=clue",
  );
});

test("describeRealtimeEndpoint never throws — it returns the reason as text", () => {
  const { describeRealtimeEndpoint } = fresh();
  const text = describeRealtimeEndpoint("director", { hostname: "awktavian.github.io" });
  assert.match(text, /realtime endpoint unavailable/);
});
