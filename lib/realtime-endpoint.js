/**
 * Realtime Endpoint Resolution — one source for every proxy URL
 * ==============================================================
 * Every voice/director surface in this portfolio used to carry its own copy of
 *
 *     isLocal ? 'ws://localhost:8766' : 'wss://kagami-realtime-proxy.fly.dev'
 *
 * Four copies drifted: `steamboat-willie.html` had no local branch at all, and
 * two error strings told the visitor to check ":8766" on a page that had never
 * talked to :8766. This module is the single place a proxy URL is decided.
 *
 * There is no silent default. A service with no reachable endpoint for the
 * current origin throws `RealtimeEndpointUnavailable`, which NAMES the service,
 * the origin it was asked for, and the override that would fix it — the caller
 * is expected to surface that text, not to substitute a guess.
 *
 * Deployment truth (realtime-proxy/fly.toml, verified live):
 *   voice     → app "kagami-realtime-proxy", internal_port 8766 → wss://kagami-realtime-proxy.fly.dev
 *   director  → realtime-proxy/claude-proxy.js, port 8767. NOT DEPLOYED. Local only.
 *
 * Override for a private/self-hosted deployment, before this script loads:
 *   <script>window.KAGAMI_REALTIME_ENDPOINTS = { voice: 'wss://my-proxy.example' };</script>
 */

'use strict';

class RealtimeEndpointUnavailable extends Error {
  constructor(service, origin, detail) {
    super(
      `realtime endpoint unavailable: service "${service}" has no reachable proxy for origin ` +
        `${origin}. ${detail} Set window.KAGAMI_REALTIME_ENDPOINTS[${JSON.stringify(service)}] ` +
        `to a ws:// or wss:// URL to wire one.`
    );
    this.name = 'RealtimeEndpointUnavailable';
    this.service = service;
    this.origin = origin;
  }
}

const REALTIME_SERVICES = {
  // OpenAI Realtime relay — realtime-proxy/server.js, deployed on Fly.io.
  voice: {
    localPort: 8766,
    deployed: 'wss://kagami-realtime-proxy.fly.dev',
    detail: 'The OpenAI Realtime relay (realtime-proxy/server.js) is deployed as the Fly app "kagami-realtime-proxy".',
  },
  // Claude scene director — realtime-proxy/claude-proxy.js. No Fly app exists
  // for it; fly.toml publishes only internal_port 8766. Local only, on purpose.
  director: {
    localPort: 8767,
    deployed: null,
    detail:
      'The Claude scene director (realtime-proxy/claude-proxy.js, port 8767) has no deployed Fly app — ' +
      'realtime-proxy/fly.toml publishes only the voice relay on 8766, so it is reachable from localhost only.',
  },
};

function isLocalOrigin(hostname) {
  return hostname === 'localhost' || hostname === '127.0.0.1' || hostname === '[::1]' || hostname === '::1';
}

/**
 * Resolve the WebSocket URL for a realtime service.
 *
 * @param {'voice'|'director'} service
 * @param {{ params?: Record<string,string|undefined>, hostname?: string, override?: string }} [opts]
 * @returns {string} an absolute ws:// or wss:// URL
 * @throws {RealtimeEndpointUnavailable} when no endpoint exists for this origin
 * @throws {RangeError} when `service` is not a known service
 */
function resolveRealtimeEndpoint(service, opts = {}) {
  const spec = REALTIME_SERVICES[service];
  if (!spec) {
    throw new RangeError(
      `unknown realtime service ${JSON.stringify(service)} — known services: ${Object.keys(REALTIME_SERVICES).join(', ')}`
    );
  }

  const hostname = opts.hostname ?? (typeof location !== 'undefined' ? location.hostname : '');
  const configured =
    opts.override ??
    (typeof window !== 'undefined' ? window.KAGAMI_REALTIME_ENDPOINTS?.[service] : undefined);

  let base = configured;
  if (!base) {
    base = isLocalOrigin(hostname) ? `ws://${hostname || 'localhost'}:${spec.localPort}` : spec.deployed;
  }
  if (!base) {
    throw new RealtimeEndpointUnavailable(service, hostname || '(unknown origin)', spec.detail);
  }

  const url = new URL(base);
  for (const [key, value] of Object.entries(opts.params || {})) {
    if (value !== undefined && value !== null && value !== '') url.searchParams.set(key, String(value));
  }
  return url.toString();
}

/** Human-readable endpoint description, for status/error UI. Never throws. */
function describeRealtimeEndpoint(service, opts = {}) {
  try {
    return resolveRealtimeEndpoint(service, opts);
  } catch (e) {
    return `(${e.message})`;
  }
}

if (typeof window !== 'undefined') {
  window.resolveRealtimeEndpoint = resolveRealtimeEndpoint;
  window.describeRealtimeEndpoint = describeRealtimeEndpoint;
  window.RealtimeEndpointUnavailable = RealtimeEndpointUnavailable;
  window.REALTIME_SERVICES = REALTIME_SERVICES;
}
if (typeof module !== 'undefined' && module.exports) {
  module.exports = {
    resolveRealtimeEndpoint,
    describeRealtimeEndpoint,
    RealtimeEndpointUnavailable,
    REALTIME_SERVICES,
  };
}
