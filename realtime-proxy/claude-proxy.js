/**
 * Claude API Streaming Proxy — Scene Director
 * =============================================
 * WebSocket server that streams Claude responses for AI-driven scene direction.
 *
 * Used by: Steamboat Willie autonomous world
 *
 * Protocol:
 *   Client sends: { type: "scene_tick", scene_state, events[], elapsed_ms }
 *   Server streams: { type: "action", character, action, emotion, dialogue }
 *   Server sends: { type: "beat_complete", scene_beat }
 *
 * Environment:
 *   ANTHROPIC_API_KEY — required
 *   CLAUDE_PROXY_PORT — default 8767
 */

import { createServer } from 'http';
import { WebSocketServer, WebSocket } from 'ws';
import Anthropic from '@anthropic-ai/sdk';

// ═══════════════════════════════════════════════════════════════════════════
// CONFIG
// ═══════════════════════════════════════════════════════════════════════════

const PORT = parseInt(process.env.CLAUDE_PROXY_PORT || '8767', 10);
const API_KEY = process.env.ANTHROPIC_API_KEY;

if (!API_KEY) {
  console.error('ANTHROPIC_API_KEY is required');
  process.exit(1);
}

const anthropic = new Anthropic({ apiKey: API_KEY });

// ═══════════════════════════════════════════════════════════════════════════
// SYSTEM PROMPT — The AI Director
// ═══════════════════════════════════════════════════════════════════════════

const DIRECTOR_SYSTEM = `You are the director of a 1928 Steamboat Willie cartoon — the ORIGINAL November 18, 1928 version.

You control THREE characters with HISTORICALLY ACCURATE designs:

WILLIE - Mickey Mouse in his original 1928 form:
  - Small black oval eyes (NOT pie-cut — that was print only)
  - Long, pointy nose (more rat-like than modern Mickey)
  - NO GLOVES, NO SHOES — bare hands and feet
  - Rubber hose limbs (completely bendy, no joints)
  - Large circular ears, lean elongated body, long tail
  - Impish, mischievous personality
  - Loves whistling, steering the boat
Actions: steer, whistle, dance, wave, jump, look_around, duck, laugh, point, tip_hat
Emotions: happy, excited, mischievous, startled, proud, content, nervous

PETE - The grumpy captain in his 1928 CAT form:
  - IMPORTANT: Pete was a CAT in 1928, NOT a dog
  - NO PEG LEG — that wasn't added until 1930
  - TWO NORMAL LEGS with suspender pants (one strap visible)
  - Large burly body, feline features
  - Captain's hat, gruff expression
  - Authoritarian, hates whistling and noise
Actions: stomp, yell, shake_fist, glare, laugh_evil, cross_arms, point, pace, salute, growl
Emotions: angry, annoyed, suspicious, smug, furious, surprised, grudging_respect

PARROT - The wise-cracking bird (the ONLY character with spoken dialogue in 1928):
  - Historical note: The parrot actually SPOKE English in the original
  - Original lines included: "Hope you don't feel hurt, big boy!" and "Help! Help! Man overboard!"
  - Chaotic neutral personality, cracks wise at Mickey's expense
  - Can mimic sounds and cause trouble
Actions: squawk, fly, land, preen, mimic, flap, bob_head, sleep, startle, speak
Emotions: mischievous, startled, sleepy, excited, curious, smug

ANIMATION STYLE — Apply Disney's 12 Principles:
1. SQUASH AND STRETCH — Characters deform with motion
2. ANTICIPATION — Wind up before big actions
3. TIMING — Comedy comes from rhythm (pause, action, reaction)
4. EXAGGERATION — Push everything beyond realism
5. RUBBER HOSE — Limbs flow like garden hoses, stretch like rubber

SCENE DIRECTION:
- Create comedic, dynamic scenes with physical comedy
- Use silent film timing: dramatic pauses, exaggerated takes, slow burns
- Character conflict: Pete hates Willie's whistling
- The parrot causes chaos and breaks the fourth wall with quips
- Occasional tenderness (characters bonding despite conflict)
- High contrast black and white aesthetic

CRITICAL: Output ONLY valid JSON. No markdown, no explanation. Each response is one "beat" of the scene.

JSON Schema:
{
  "scene_beat": "Brief description of what happens",
  "actions": [
    { "character": "willie"|"pete"|"parrot", "action": "<action>", "emotion": "<emotion>", "dialogue": "<text>"|null, "target_x": 0-100|null, "target_y": 0-100|null }
  ],
  "audio_cues": ["whistle"|"grumble"|"squawk"|"splash"|"stomp"|"steam"|"bell"],
  "title_card": { "text": "<dialogue to show>", "speaker": "<character>" } | null,
  "camera": { "focus": "<character>"|null, "shake": true|false }
}`;

// ═══════════════════════════════════════════════════════════════════════════
// HTTP SERVER
// ═══════════════════════════════════════════════════════════════════════════

const httpServer = createServer((req, res) => {
  res.setHeader('Access-Control-Allow-Origin', '*');
  res.setHeader('Access-Control-Allow-Methods', 'GET, OPTIONS');

  if (req.url === '/health') {
    res.writeHead(200, { 'Content-Type': 'application/json' });
    res.end(JSON.stringify({ status: 'ok', service: 'claude-proxy' }));
    return;
  }

  res.writeHead(404, { 'Content-Type': 'application/json' });
  res.end(JSON.stringify({ error: 'Connect via WebSocket' }));
});

// ═══════════════════════════════════════════════════════════════════════════
// WEBSOCKET SERVER
// ═══════════════════════════════════════════════════════════════════════════

const wss = new WebSocketServer({ server: httpServer });

wss.on('connection', (ws) => {
  console.log('[claude-proxy] Client connected');

  // Conversation history for this session
  const history = [];

  ws.on('message', async (data) => {
    try {
      const msg = JSON.parse(data.toString());

      if (msg.type === 'scene_tick') {
        await handleSceneTick(ws, msg, history);
      }
    } catch (err) {
      console.error('[claude-proxy] Error:', err.message);
      ws.send(JSON.stringify({ type: 'error', message: err.message }));
    }
  });

  ws.on('close', () => {
    console.log('[claude-proxy] Client disconnected');
  });
});

// ═══════════════════════════════════════════════════════════════════════════
// SCENE TICK HANDLER
// ═══════════════════════════════════════════════════════════════════════════

async function handleSceneTick(ws, msg, history) {
  const { scene_state, events, elapsed_ms, tick_number } = msg;

  // Build user message
  const userContent = JSON.stringify({
    tick: tick_number,
    elapsed_seconds: Math.round(elapsed_ms / 1000),
    characters: scene_state.characters,
    recent_events: events,
    world: scene_state.world
  });

  // Add to history (keep last 10 exchanges for context)
  history.push({ role: 'user', content: userContent });
  if (history.length > 20) history.splice(0, 2);

  try {
    // Stream response from Claude
    const stream = anthropic.messages.stream({
      model: 'claude-sonnet-4-20250514',
      max_tokens: 500,
      system: DIRECTOR_SYSTEM,
      messages: history
    });

    let fullResponse = '';

    stream.on('text', (text) => {
      fullResponse += text;
      // Try to parse partial JSON and send incremental updates
      // For simplicity, we'll just accumulate and send at end
    });

    const finalMessage = await stream.finalMessage();

    // Add assistant response to history
    history.push({ role: 'assistant', content: fullResponse });

    // Parse and send the response
    try {
      const parsed = JSON.parse(fullResponse);

      // Send each action individually for animation timing
      if (parsed.actions) {
        for (const action of parsed.actions) {
          ws.send(JSON.stringify({ type: 'action', ...action }));
        }
      }

      // Send audio cues
      if (parsed.audio_cues) {
        ws.send(JSON.stringify({ type: 'audio_cues', cues: parsed.audio_cues }));
      }

      // Send title card if present
      if (parsed.title_card) {
        ws.send(JSON.stringify({ type: 'title_card', ...parsed.title_card }));
      }

      // Send camera direction
      if (parsed.camera) {
        ws.send(JSON.stringify({ type: 'camera', ...parsed.camera }));
      }

      // Signal beat complete
      ws.send(JSON.stringify({
        type: 'beat_complete',
        scene_beat: parsed.scene_beat,
        tick: tick_number
      }));

    } catch (parseErr) {
      console.error('[claude-proxy] Failed to parse response:', fullResponse.slice(0, 200));
      ws.send(JSON.stringify({ type: 'error', message: 'Invalid JSON from AI' }));
    }

  } catch (apiErr) {
    console.error('[claude-proxy] API error:', apiErr.message);
    ws.send(JSON.stringify({ type: 'error', message: apiErr.message }));
  }
}

// ═══════════════════════════════════════════════════════════════════════════
// GRACEFUL SHUTDOWN
// ═══════════════════════════════════════════════════════════════════════════

function shutdown() {
  console.log('\nShutting down...');
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
  console.log(`Claude Scene Director Proxy listening on :${PORT}`);
  console.log(`  Health: http://localhost:${PORT}/health`);
  console.log(`  Connect via WebSocket for scene direction`);
});
