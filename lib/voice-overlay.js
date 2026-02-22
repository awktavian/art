/**
 * Voice Overlay — Drop-in voice UI for any art project
 * =====================================================
 * Injects a minimal floating voice toggle + transcript panel.
 * Uses RealtimeVoice + KAGAMI_VOICES for personality.
 *
 * Usage:
 *   <script src="../lib/realtime-voice.js"></script>
 *   <script src="../lib/kagami-voices.js"></script>
 *   <script src="../lib/voice-overlay.js"></script>
 *   <script>
 *     VoiceOverlay.init({
 *       project: 'skippy',         // key from PROJECT_VOICES
 *       tools: [...],              // optional function tools
 *       onFunctionCall: (n,a)=>{}, // tool handler
 *     });
 *   </script>
 */

'use strict';

const VoiceOverlay = (() => {
  let voice = null;
  let connected = false;
  let holding = false;
  let elements = {};
  let opts = {};

  function createUI() {
    const overlay = document.createElement('div');
    overlay.id = 'voice-overlay';
    overlay.setAttribute('aria-label', 'Voice interaction');
    overlay.style.cssText = 'position:fixed;bottom:24px;right:24px;z-index:10000;display:flex;flex-direction:column;align-items:flex-end;gap:8px;pointer-events:none;font-family:system-ui,sans-serif;';

    const btn = document.createElement('button');
    btn.id = 'voice-toggle';
    btn.setAttribute('aria-label', 'Toggle voice (V)');
    btn.style.cssText = 'pointer-events:auto;display:flex;align-items:center;gap:8px;padding:8px 14px;background:rgba(5,5,5,0.85);backdrop-filter:blur(12px);-webkit-backdrop-filter:blur(12px);border:1px solid rgba(255,255,255,0.08);border-radius:999px;color:rgba(255,255,255,0.5);cursor:pointer;font-family:inherit;font-size:12px;transition:all 233ms;';
    btn.innerHTML = '<svg viewBox="0 0 24 24" width="18" height="18" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round"><rect x="9" y="2" width="6" height="11" rx="3"/><path d="M5 10a7 7 0 0014 0"/><line x1="12" y1="17" x2="12" y2="21"/><line x1="8" y1="21" x2="16" y2="21"/></svg><span id="voice-status">Voice</span>';

    const transcript = document.createElement('div');
    transcript.id = 'voice-transcript';
    transcript.style.cssText = 'pointer-events:auto;max-width:340px;max-height:180px;overflow-y:auto;background:rgba(5,5,5,0.9);backdrop-filter:blur(12px);-webkit-backdrop-filter:blur(12px);border:1px solid rgba(255,255,255,0.06);border-radius:8px;padding:8px;display:none;font-size:11px;line-height:1.4;color:rgba(255,255,255,0.5);';

    overlay.appendChild(btn);
    overlay.appendChild(transcript);
    document.body.appendChild(overlay);

    return {
      overlay,
      btn,
      status: btn.querySelector('#voice-status'),
      transcript,
    };
  }

  let transcriptBuffer = '';

  function addLine(text, color) {
    const div = document.createElement('div');
    div.style.cssText = `padding:2px 0;color:${color || 'rgba(255,255,255,0.5)'}`;
    div.textContent = text;
    elements.transcript.appendChild(div);
    elements.transcript.scrollTop = elements.transcript.scrollHeight;
    while (elements.transcript.children.length > 8) elements.transcript.removeChild(elements.transcript.firstChild);
  }

  function updateLast(text) {
    const lines = elements.transcript.querySelectorAll('div');
    const last = lines[lines.length - 1];
    if (last && !last.textContent.startsWith('You:') && !last.textContent.includes('connected')) {
      last.textContent = text;
    } else {
      const div = document.createElement('div');
      div.style.cssText = 'padding:2px 0;color:#ffd878';
      div.textContent = text;
      elements.transcript.appendChild(div);
    }
    elements.transcript.scrollTop = elements.transcript.scrollHeight;
  }

  function onTranscript(text, role) {
    if (role === 'user') { transcriptBuffer = ''; addLine('You: ' + text, '#f0c860'); }
    else { transcriptBuffer += text; updateLast(transcriptBuffer); }
  }

  async function connect() {
    const config = window.buildVoiceConfig ? window.buildVoiceConfig(opts.project) : null;
    const colony = config?.colony;

    // Build proxy URL with project/colony metadata
    const isLocal = location.hostname === 'localhost' || location.hostname === '127.0.0.1';
    const defaultProxy = isLocal ? 'ws://localhost:8766' : 'wss://kagami-realtime-proxy.fly.dev';
    const baseUrl = opts.proxyUrl || defaultProxy;
    const proxyUrl = new URL(baseUrl);
    if (opts.project) proxyUrl.searchParams.set('project', opts.project);
    if (colony) proxyUrl.searchParams.set('colony', colony.colony.toLowerCase());

    voice = new RealtimeVoice({
      proxyUrl: proxyUrl.toString(),
      voice: config?.voice || opts.voice || 'alloy',
      instructions: (config?.instructions || opts.instructions || 'You are a helpful voice assistant.') +
        (opts.extraInstructions ? '\n' + opts.extraInstructions : ''),
      tools: opts.tools || [],
      onTranscript,
      onFunctionCall: opts.onFunctionCall || (() => ({ ok: true })),
      onStateChange: (s) => {
        elements.overlay.dataset.state = s;
        elements.status.textContent = s === 'ready' ? (colony?.colony || 'Ready')
          : s === 'listening' ? 'Listening...' : s === 'speaking' ? 'Speaking' : 'Voice';
        elements.btn.style.borderColor = s === 'listening' ? (colony?.color || '#f0c860')
          : s === 'speaking' ? '#ffd878' : connected ? 'rgba(255,255,255,0.15)' : 'rgba(255,255,255,0.08)';
        elements.btn.style.boxShadow = s === 'listening'
          ? `0 0 16px ${colony?.color || '#f0c860'}40` : 'none';
        elements.transcript.style.display = (s === 'ready' || s === 'listening' || s === 'speaking') ? 'block' : 'none';
      },
      onError: (e) => { addLine('Error: ' + (e.message || e), '#f87171'); },
    });

    await voice.connect();
    connected = true;
    const colony2 = config?.colony;
    addLine(colony2 ? `${colony2.character} (${colony2.colony}) connected. Hold Space to talk.` : 'Connected. Hold Space to talk.', 'rgba(255,255,255,0.35)');
  }

  function disconnect() {
    if (voice) { voice.disconnect(); voice = null; }
    connected = false;
    elements.status.textContent = 'Voice';
    elements.btn.style.borderColor = 'rgba(255,255,255,0.08)';
    elements.transcript.style.display = 'none';
  }

  return {
    init(options = {}) {
      opts = options;
      elements = createUI();

      elements.btn.addEventListener('click', async () => {
        if (connected) { disconnect(); }
        else {
          elements.status.textContent = 'Connecting...';
          try { await connect(); } catch {
            elements.status.textContent = 'Failed';
            addLine('Connection failed. Is the proxy running on :8766?', '#f87171');
          }
        }
      });

      document.addEventListener('keydown', (e) => {
        if (e.key === 'v' && !e.ctrlKey && !e.metaKey && e.target.tagName !== 'INPUT' && e.target.tagName !== 'TEXTAREA') {
          e.preventDefault(); elements.btn.click(); return;
        }
        if (e.key === ' ' && connected && !holding && e.target.tagName !== 'INPUT' && e.target.tagName !== 'TEXTAREA') {
          e.preventDefault(); holding = true; voice.startListening();
        }
      });

      document.addEventListener('keyup', (e) => {
        if (e.key === ' ' && holding) { e.preventDefault(); holding = false; if (voice) voice.stopListening(); }
      });
    },

    get connected() { return connected; },
    get voice() { return voice; },
    sendText(text) { if (voice) voice.sendText(text); },
  };
})();

if (typeof window !== 'undefined') window.VoiceOverlay = VoiceOverlay;
