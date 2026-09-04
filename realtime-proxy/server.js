/**
 * OpenAI Realtime API — WebSocket Relay Proxy
 * ============================================
 * Proxies client WebSocket connections to wss://api.openai.com/v1/realtime
 *
 * Features:
 *   - Token bucket rate limiting (per-IP, per-session)
 *   - Per-session cost tracking with configurable caps
 *   - Connection pool with max concurrent sessions
 *   - Health / stats HTTP endpoint
 *   - CORS-safe upgrade handling
 *   - Graceful shutdown
 *
 * Environment:
 *   OPENAI_API_KEY       — required
 *   PROXY_PORT           — default 8766
 *   MAX_SESSIONS         — default 5
 *   SESSION_COST_CAP     — default $2.00 per session (in cents: 200)
 *   RATE_TOKENS_PER_SEC  — token bucket refill rate (default 10)
 *   RATE_BUCKET_MAX      — max burst tokens (default 30)
 *   ALLOWED_ORIGINS      — comma-separated origins (default: all)
 *   REALTIME_MODEL       — required; the exact OpenAI Realtime model id
 *   REALTIME_PRICE_*     — required; USD per 1M tokens for that model, four
 *                          values: TEXT_IN, TEXT_OUT, AUDIO_IN, AUDIO_OUT.
 *                          Set from OpenAI's published price for REALTIME_MODEL.
 *
 * Cost accounting is metered from the `usage` block OpenAI returns on
 * `response.done`, never estimated per message. See CostMeter below.
 */

import { createServer } from 'http';
import { WebSocketServer, WebSocket } from 'ws';
import { CostMeter } from './cost-meter.js';

// ═══════════════════════════════════════════════════════════════════════════
// CONFIG
// ═══════════════════════════════════════════════════════════════════════════

const PORT = parseInt(process.env.PROXY_PORT || '8766', 10);
const OPENAI_API_KEY = process.env.OPENAI_API_KEY;
const MAX_SESSIONS = parseInt(process.env.MAX_SESSIONS || '5', 10);
const SESSION_COST_CAP = parseInt(process.env.SESSION_COST_CAP || '200', 10); // cents
const RATE_TOKENS_PER_SEC = parseInt(process.env.RATE_TOKENS_PER_SEC || '10', 10);
const RATE_BUCKET_MAX = parseInt(process.env.RATE_BUCKET_MAX || '30', 10);
const ALLOWED_ORIGINS = process.env.ALLOWED_ORIGINS
  ? process.env.ALLOWED_ORIGINS.split(',').map(s => s.trim())
  : null; // null = allow all
const REALTIME_MODEL = process.env.REALTIME_MODEL;
const OPENAI_REALTIME_URL = `wss://api.openai.com/v1/realtime?model=${REALTIME_MODEL}`;

// Prices are per 1,000,000 tokens, in USD, for REALTIME_MODEL specifically.
// They are deliberately NOT defaulted: a stale built-in price table silently
// mis-meters every session and the cost cap stops meaning what it says. The
// model id and its prices must travel together (see fly.toml [env]).
const PRICE_ENV = {
  textIn: 'REALTIME_PRICE_TEXT_IN_PER_MTOK',
  textOut: 'REALTIME_PRICE_TEXT_OUT_PER_MTOK',
  audioIn: 'REALTIME_PRICE_AUDIO_IN_PER_MTOK',
  audioOut: 'REALTIME_PRICE_AUDIO_OUT_PER_MTOK',
};

function requireConfig() {
  const missing = [];
  if (!OPENAI_API_KEY) missing.push('OPENAI_API_KEY (the upstream credential)');
  if (!REALTIME_MODEL) {
    missing.push(
      'REALTIME_MODEL (the exact OpenAI Realtime model id; no default — a stale ' +
        'built-in name silently pins every session to a retired model)'
    );
  }
  const prices = {};
  for (const [key, envName] of Object.entries(PRICE_ENV)) {
    const raw = process.env[envName];
    const value = Number(raw);
    if (raw === undefined || raw === '' || !Number.isFinite(value) || value < 0) {
      missing.push(`${envName} (USD per 1M tokens for ${REALTIME_MODEL || 'REALTIME_MODEL'})`);
      continue;
    }
    prices[key] = value;
  }
  if (missing.length > 0) {
    console.error('realtime-proxy: refusing to start — missing required configuration:');
    for (const m of missing) console.error(`  - ${m}`);
    process.exit(1);
  }
  return prices;
}

const PRICES = requireConfig();

// ═══════════════════════════════════════════════════════════════════════════
// TOKEN BUCKET RATE LIMITER
// ═══════════════════════════════════════════════════════════════════════════

class TokenBucket {
  constructor(tokensPerSec = RATE_TOKENS_PER_SEC, maxTokens = RATE_BUCKET_MAX) {
    this.tokensPerSec = tokensPerSec;
    this.maxTokens = maxTokens;
    this.tokens = maxTokens;
    this.lastRefill = Date.now();
  }

  consume(n = 1) {
    this._refill();
    if (this.tokens >= n) {
      this.tokens -= n;
      return true;
    }
    return false;
  }

  _refill() {
    const now = Date.now();
    const elapsed = (now - this.lastRefill) / 1000;
    this.tokens = Math.min(this.maxTokens, this.tokens + elapsed * this.tokensPerSec);
    this.lastRefill = now;
  }
}

// ═══════════════════════════════════════════════════════════════════════════
// SESSION TRACKER
// ═══════════════════════════════════════════════════════════════════════════

const sessions = new Map(); // sessionId -> { clientWs, upstreamWs, bucket, cost, created, ip, origin }
let sessionCounter = 0;

function getSessionStats() {
  const active = [];
  const byProject = {};
  const byColony = {};
  let totalCost = 0;

  for (const [id, s] of sessions) {
    const info = {
      id,
      ip: s.ip,
      origin: s.origin,
      project: s.projectId,
      colony: s.colonyId,
      costCents: Math.round(s.meter.cents * 100) / 100,
      // `metered: false` means no response has been billed yet, so costCents 0
      // is "nothing charged", NOT "measured as free". Consumers must not read
      // an unmetered zero as a measurement.
      metered: s.meter.metered,
      billedResponses: s.meter.responses,
      tokens: { ...s.meter.tokens },
      messagesIn: s.messagesIn,
      messagesOut: s.messagesOut,
      created: s.created,
      durationSec: Math.round((Date.now() - s.created) / 1000),
    };
    active.push(info);
    totalCost += s.meter.cents;

    byProject[s.projectId] = (byProject[s.projectId] || 0) + 1;
    byColony[s.colonyId] = (byColony[s.colonyId] || 0) + 1;
  }

  return {
    active,
    total: sessionCounter,
    maxSessions: MAX_SESSIONS,
    model: REALTIME_MODEL,
    pricesUsdPerMTok: PRICES,
    totalCostCents: Math.round(totalCost * 100) / 100,
    byProject,
    byColony,
  };
}

// ═══════════════════════════════════════════════════════════════════════════
// HTTP SERVER (health + stats)
// ═══════════════════════════════════════════════════════════════════════════

const httpServer = createServer((req, res) => {
  // CORS
  const origin = req.headers.origin || '*';
  if (ALLOWED_ORIGINS && !ALLOWED_ORIGINS.includes(origin)) {
    res.writeHead(403, { 'Content-Type': 'application/json' });
    res.end(JSON.stringify({ error: 'Origin not allowed' }));
    return;
  }
  res.setHeader('Access-Control-Allow-Origin', origin);
  res.setHeader('Access-Control-Allow-Methods', 'GET, OPTIONS');
  res.setHeader('Access-Control-Allow-Headers', 'Content-Type');

  if (req.method === 'OPTIONS') {
    res.writeHead(204);
    res.end();
    return;
  }

  if (req.url === '/health') {
    res.writeHead(200, { 'Content-Type': 'application/json' });
    res.end(JSON.stringify({
      status: 'ok',
      sessions: sessions.size,
      maxSessions: MAX_SESSIONS,
      uptime: process.uptime(),
    }));
    return;
  }

  if (req.url === '/stats') {
    res.writeHead(200, { 'Content-Type': 'application/json' });
    res.end(JSON.stringify(getSessionStats()));
    return;
  }

  res.writeHead(404, { 'Content-Type': 'application/json' });
  res.end(JSON.stringify({ error: 'Not found. Use /health or /stats, or connect via WebSocket.' }));
});

// ═══════════════════════════════════════════════════════════════════════════
// WEBSOCKET SERVER
// ═══════════════════════════════════════════════════════════════════════════

const wss = new WebSocketServer({ server: httpServer });

wss.on('connection', (clientWs, req) => {
  // `null`, not the string 'unknown': a session with no Origin header and one
  // from a client that literally sent Origin: unknown must stay distinguishable
  // in /stats. Absent is a value; a stand-in string is not.
  const ip = req.headers['x-forwarded-for']?.split(',')[0]?.trim() || req.socket.remoteAddress || null;
  const origin = req.headers.origin ?? null;

  // Parse project/colony metadata from query params
  // (e.g., ws://localhost:8766?project=robo-skip&colony=forge)
  //
  // These used to default to 'unknown' and 'kagami'. Both are lies in the stats
  // table: 'unknown' is a project name no page ever sends, and 'kagami' silently
  // attributed every unlabelled session to the orchestrator colony, inflating
  // its byColony count with sessions that belong to someone else. The client
  // always has both values (lib/realtime-endpoint.js sets them), so a missing
  // one is a client bug and is reported as such rather than papered over.
  const url = new URL(req.url, `http://${req.headers.host}`);
  const projectId = url.searchParams.get('project');
  const colonyId = url.searchParams.get('colony');
  if (!projectId || !colonyId) {
    const absent = [!projectId && 'project', !colonyId && 'colony'].filter(Boolean).join(' and ');
    console.warn(
      `[reject] ${ip ?? '(no client address)'} (${origin ?? '(no Origin header)'}) ` +
        `omitted required query param(s): ${absent}`
    );
    clientWs.close(4400, `Missing required query parameter(s): ${absent}`);
    return;
  }

  // Origin check
  if (ALLOWED_ORIGINS && !ALLOWED_ORIGINS.includes(origin)) {
    clientWs.close(4003, 'Origin not allowed');
    return;
  }

  // Capacity check
  if (sessions.size >= MAX_SESSIONS) {
    clientWs.close(4029, `Server at capacity (${MAX_SESSIONS} sessions)`);
    return;
  }

  const sessionId = `s-${++sessionCounter}`;
  const bucket = new TokenBucket();
  const meter = new CostMeter(PRICES);

  console.log(
    `[${sessionId}] Client connected from ${ip ?? '(no client address)'} ` +
      `(${origin ?? '(no Origin header)'}) — project:${projectId} colony:${colonyId}`
  );

  // Open upstream connection to OpenAI
  const upstreamWs = new WebSocket(OPENAI_REALTIME_URL, {
    headers: {
      'Authorization': `Bearer ${OPENAI_API_KEY}`,
      'OpenAI-Beta': 'realtime=v1',
    },
  });

  const session = {
    clientWs,
    upstreamWs,
    bucket,
    meter,
    messagesIn: 0,
    messagesOut: 0,
    created: Date.now(),
    ip,
    origin,
    projectId,
    colonyId,
  };
  sessions.set(sessionId, session);

  // ─── Upstream → Client ─────────────────────────────────────────────
  upstreamWs.on('open', () => {
    console.log(`[${sessionId}] Upstream connected to OpenAI Realtime`);
    // Send session ID to client
    clientWs.send(JSON.stringify({
      type: 'proxy.session.created',
      session_id: sessionId,
      model: REALTIME_MODEL,
      project: projectId,
      colony: colonyId,
    }));
  });

  upstreamWs.on('message', (data) => {
    if (clientWs.readyState !== WebSocket.OPEN) return;

    const msg = data.toString();
    session.messagesOut++;

    // Meter from the upstream `response.done` usage block. Messages without
    // usage cost nothing here because nothing has been billed for them yet.
    let parsed = null;
    try { parsed = JSON.parse(msg); } catch { /* non-JSON frame: not billable */ }
    if (parsed && meter.record(parsed)) {
      clientWs.send(JSON.stringify({
        type: 'proxy.session.cost',
        cost_cents: Math.round(meter.cents * 100) / 100,
        limit_cents: SESSION_COST_CAP,
        billed_responses: meter.responses,
        tokens: { ...meter.tokens },
      }));

      // Cost cap check — now against a metered number, not an invented one.
      if (meter.cents >= SESSION_COST_CAP) {
        clientWs.send(JSON.stringify({
          type: 'proxy.session.cost_limit',
          cost_cents: Math.round(meter.cents * 100) / 100,
          limit_cents: SESSION_COST_CAP,
        }));
        cleanup(sessionId, 4028, 'Session cost limit reached');
        return;
      }
    }

    clientWs.send(msg);
  });

  upstreamWs.on('error', (err) => {
    console.error(`[${sessionId}] Upstream error:`, err.message);
    cleanup(sessionId, 4502, 'Upstream error');
  });

  upstreamWs.on('close', (code, reason) => {
    console.log(`[${sessionId}] Upstream closed: ${code} ${reason}`);
    cleanup(sessionId, 4500, 'Upstream closed');
  });

  // ─── Client → Upstream ─────────────────────────────────────────────
  clientWs.on('message', (data) => {
    if (upstreamWs.readyState !== WebSocket.OPEN) return;

    // Rate limit check
    if (!bucket.consume()) {
      clientWs.send(JSON.stringify({
        type: 'proxy.rate_limited',
        retry_after_ms: Math.ceil(1000 / RATE_TOKENS_PER_SEC),
      }));
      return;
    }

    session.messagesIn++;
    // Client frames are not billed here: the upstream `response.done` usage
    // block already accounts for the input tokens they produced.
    upstreamWs.send(data.toString());
  });

  clientWs.on('close', () => {
    console.log(`[${sessionId}] Client disconnected`);
    cleanup(sessionId, 1000, 'Client disconnected');
  });

  clientWs.on('error', (err) => {
    console.error(`[${sessionId}] Client error:`, err.message);
    cleanup(sessionId, 4500, 'Client error');
  });
});

// ═══════════════════════════════════════════════════════════════════════════
// CLEANUP
// ═══════════════════════════════════════════════════════════════════════════

function cleanup(sessionId, code = 1000, reason = 'Session ended') {
  const session = sessions.get(sessionId);
  if (!session) return;

  sessions.delete(sessionId);

  const duration = Math.round((Date.now() - session.created) / 1000);
  const cost = session.meter.metered
    ? `${(Math.round(session.meter.cents * 100) / 100).toFixed(2)}¢ metered over ${session.meter.responses} response(s)`
    : 'nothing billed (no response.done usage received)';
  console.log(`[${sessionId}] Session ended — ${duration}s, ${session.messagesIn}↑ ${session.messagesOut}↓, ${cost}`);

  try {
    if (session.upstreamWs.readyState === WebSocket.OPEN) {
      session.upstreamWs.close(code, reason);
    }
  } catch { /* ignore */ }

  try {
    if (session.clientWs.readyState === WebSocket.OPEN) {
      session.clientWs.close(code, reason);
    }
  } catch { /* ignore */ }
}

// ═══════════════════════════════════════════════════════════════════════════
// GRACEFUL SHUTDOWN
// ═══════════════════════════════════════════════════════════════════════════

function shutdown() {
  console.log('\nShutting down...');
  for (const [id] of sessions) {
    cleanup(id, 1001, 'Server shutting down');
  }
  wss.close();
  httpServer.close(() => process.exit(0));
  setTimeout(() => process.exit(1), 3000);
}

process.on('SIGINT', shutdown);
process.on('SIGTERM', shutdown);

// ═══════════════════════════════════════════════════════════════════════════
// START
// ═══════════════════════════════════════════════════════════════════════════

httpServer.listen(PORT, () => {
  console.log(`OpenAI Realtime Proxy listening on :${PORT}`);
  console.log(`  Model: ${REALTIME_MODEL}`);
  console.log(`  Prices (USD/1M tok): text ${PRICES.textIn}/${PRICES.textOut}, audio ${PRICES.audioIn}/${PRICES.audioOut}`);
  console.log(`  Max sessions: ${MAX_SESSIONS}`);
  console.log(`  Cost cap: ${SESSION_COST_CAP}¢/session`);
  console.log(`  Rate limit: ${RATE_TOKENS_PER_SEC} msg/s (burst: ${RATE_BUCKET_MAX})`);
  console.log(`  Origins: ${ALLOWED_ORIGINS ? ALLOWED_ORIGINS.join(', ') : 'all'}`);
  console.log(`  Health: http://localhost:${PORT}/health`);
  console.log(`  Stats:  http://localhost:${PORT}/stats`);
});
