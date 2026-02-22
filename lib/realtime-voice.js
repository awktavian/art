/**
 * Realtime Voice Client — Shared library for voice interaction
 * =============================================================
 * Connects to the local OpenAI Realtime proxy (ws://localhost:8766)
 * and provides a clean API for:
 *   - Push-to-talk microphone capture
 *   - Audio playback of AI responses
 *   - Text transcript callbacks
 *   - Function call routing (for tool integration)
 *
 * Used by: Robo-Skip (voice coaching), Kagami Code Map (voice exploration)
 *
 * Usage:
 *   const voice = new RealtimeVoice({
 *     proxyUrl: 'ws://localhost:8766',
 *     onTranscript: (text, role) => { ... },
 *     onFunctionCall: (name, args) => { ... },
 *     tools: [{ name, description, parameters }],
 *     instructions: 'You are a curling strategy coach...',
 *   });
 *   await voice.connect();
 *   voice.startListening();   // begin mic capture
 *   voice.stopListening();    // commit audio buffer
 *   voice.disconnect();
 */

'use strict';

class RealtimeVoice {
  constructor(opts = {}) {
    this.proxyUrl = opts.proxyUrl || 'ws://localhost:8766';
    this.instructions = opts.instructions || '';
    this.tools = opts.tools || [];
    this.voice = opts.voice || 'alloy';

    // Callbacks
    this.onTranscript = opts.onTranscript || (() => {});
    this.onFunctionCall = opts.onFunctionCall || (() => {});
    this.onStateChange = opts.onStateChange || (() => {});
    this.onError = opts.onError || ((e) => console.error('[RealtimeVoice]', e));
    this.onCostUpdate = opts.onCostUpdate || (() => {});

    // State
    this.ws = null;
    this.audioCtx = null;
    this.mediaStream = null;
    this.processor = null;
    this.state = 'disconnected'; // disconnected | connecting | ready | listening | speaking
    this.sessionId = null;
    this._audioQueue = [];
    this._playing = false;
  }

  // ═══════════════════════════════════════════════════════════════════════
  // CONNECTION
  // ═══════════════════════════════════════════════════════════════════════

  async connect() {
    if (this.ws) return;
    this._setState('connecting');

    return new Promise((resolve, reject) => {
      this.ws = new WebSocket(this.proxyUrl);

      this.ws.onopen = () => {
        console.log('[RealtimeVoice] Connected to proxy');
      };

      this.ws.onmessage = (event) => {
        const msg = JSON.parse(event.data);
        this._handleMessage(msg, resolve);
      };

      this.ws.onclose = (e) => {
        console.log(`[RealtimeVoice] Disconnected: ${e.code} ${e.reason}`);
        this._setState('disconnected');
        this._cleanup();
      };

      this.ws.onerror = (e) => {
        this.onError(e);
        reject(e);
      };

      // Timeout
      setTimeout(() => {
        if (this.state === 'connecting') {
          reject(new Error('Connection timeout'));
          this.disconnect();
        }
      }, 10000);
    });
  }

  disconnect() {
    if (this.ws) {
      this.ws.close(1000, 'Client disconnect');
      this.ws = null;
    }
    this._cleanup();
    this._setState('disconnected');
  }

  // ═══════════════════════════════════════════════════════════════════════
  // MICROPHONE CAPTURE
  // ═══════════════════════════════════════════════════════════════════════

  async startListening() {
    if (this.state !== 'ready') return;

    try {
      this.mediaStream = await navigator.mediaDevices.getUserMedia({
        audio: { sampleRate: 24000, channelCount: 1, echoCancellation: true, noiseSuppression: true },
      });

      this.audioCtx = new (window.AudioContext || window.webkitAudioContext)({ sampleRate: 24000 });
      const source = this.audioCtx.createMediaStreamSource(this.mediaStream);

      // ScriptProcessor for raw PCM (AudioWorklet would be ideal but this is simpler)
      this.processor = this.audioCtx.createScriptProcessor(4096, 1, 1);
      this.processor.onaudioprocess = (e) => {
        if (this.state !== 'listening' || !this.ws) return;
        const float32 = e.inputBuffer.getChannelData(0);
        const int16 = this._float32ToInt16(float32);
        const base64 = this._arrayBufferToBase64(int16.buffer);
        this._send({ type: 'input_audio_buffer.append', audio: base64 });
      };

      source.connect(this.processor);
      this.processor.connect(this.audioCtx.destination);

      this._setState('listening');
    } catch (err) {
      this.onError(err);
    }
  }

  stopListening() {
    if (this.state !== 'listening') return;

    // Stop mic
    if (this.mediaStream) {
      this.mediaStream.getTracks().forEach(t => t.stop());
      this.mediaStream = null;
    }
    if (this.processor) {
      this.processor.disconnect();
      this.processor = null;
    }
    if (this.audioCtx) {
      this.audioCtx.close().catch(() => {});
      this.audioCtx = null;
    }

    // Commit the audio buffer and request a response
    this._send({ type: 'input_audio_buffer.commit' });
    this._send({ type: 'response.create' });

    this._setState('ready');
  }

  // Send a text message instead of audio
  sendText(text) {
    if (!this.ws || this.state === 'disconnected') return;

    this._send({
      type: 'conversation.item.create',
      item: {
        type: 'message',
        role: 'user',
        content: [{ type: 'input_text', text }],
      },
    });
    this._send({ type: 'response.create' });
  }

  // ═══════════════════════════════════════════════════════════════════════
  // MESSAGE HANDLING
  // ═══════════════════════════════════════════════════════════════════════

  _handleMessage(msg, connectResolve) {
    switch (msg.type) {
      // Proxy session created → configure the session
      case 'proxy.session.created':
        this.sessionId = msg.session_id;
        this._configureSession();
        this._setState('ready');
        if (connectResolve) connectResolve();
        break;

      // Rate limited by proxy
      case 'proxy.rate_limited':
        console.warn(`[RealtimeVoice] Rate limited, retry in ${msg.retry_after_ms}ms`);
        break;

      // Cost limit hit
      case 'proxy.session.cost_limit':
        this.onError(new Error(`Session cost limit: ${msg.cost_cents}¢ / ${msg.limit_cents}¢`));
        this.disconnect();
        break;

      // Session created/updated by OpenAI
      case 'session.created':
      case 'session.updated':
        break;

      // Audio response
      case 'response.audio.delta':
        if (msg.delta) {
          this._queueAudio(msg.delta);
        }
        break;

      // Text transcript of AI response
      case 'response.audio_transcript.delta':
        if (msg.delta) {
          this.onTranscript(msg.delta, 'assistant');
        }
        break;

      case 'response.text.delta':
        if (msg.delta) {
          this.onTranscript(msg.delta, 'assistant');
        }
        break;

      // User speech transcript
      case 'conversation.item.input_audio_transcription.completed':
        if (msg.transcript) {
          this.onTranscript(msg.transcript, 'user');
        }
        break;

      // Function call
      case 'response.function_call_arguments.done':
        this._handleFunctionCall(msg);
        break;

      // Response done
      case 'response.done':
        if (this.state === 'speaking') {
          this._setState('ready');
        }
        break;

      // Error from OpenAI
      case 'error':
        this.onError(new Error(msg.error?.message || 'Unknown error'));
        break;
    }
  }

  _configureSession() {
    const config = {
      type: 'session.update',
      session: {
        modalities: ['text', 'audio'],
        voice: this.voice,
        input_audio_format: 'pcm16',
        output_audio_format: 'pcm16',
        input_audio_transcription: { model: 'whisper-1' },
        turn_detection: null, // manual push-to-talk
      },
    };

    if (this.instructions) {
      config.session.instructions = this.instructions;
    }

    if (this.tools.length > 0) {
      config.session.tools = this.tools.map(t => ({
        type: 'function',
        name: t.name,
        description: t.description,
        parameters: t.parameters,
      }));
    }

    this._send(config);
  }

  async _handleFunctionCall(msg) {
    const { call_id, name, arguments: argsStr } = msg;
    let args = {};
    try { args = JSON.parse(argsStr); } catch { /* empty */ }

    const result = await this.onFunctionCall(name, args);

    // Return function result to the conversation
    this._send({
      type: 'conversation.item.create',
      item: {
        type: 'function_call_output',
        call_id,
        output: JSON.stringify(result ?? { ok: true }),
      },
    });
    this._send({ type: 'response.create' });
  }

  // ═══════════════════════════════════════════════════════════════════════
  // AUDIO PLAYBACK
  // ═══════════════════════════════════════════════════════════════════════

  _queueAudio(base64) {
    const binary = atob(base64);
    const bytes = new Uint8Array(binary.length);
    for (let i = 0; i < binary.length; i++) bytes[i] = binary.charCodeAt(i);
    const int16 = new Int16Array(bytes.buffer);
    this._audioQueue.push(int16);
    this._playNext();
  }

  async _playNext() {
    if (this._playing || this._audioQueue.length === 0) return;
    this._playing = true;
    this._setState('speaking');

    const ctx = new (window.AudioContext || window.webkitAudioContext)({ sampleRate: 24000 });

    while (this._audioQueue.length > 0) {
      const int16 = this._audioQueue.shift();
      const float32 = new Float32Array(int16.length);
      for (let i = 0; i < int16.length; i++) float32[i] = int16[i] / 32768;

      const buffer = ctx.createBuffer(1, float32.length, 24000);
      buffer.getChannelData(0).set(float32);

      const source = ctx.createBufferSource();
      source.buffer = buffer;
      source.connect(ctx.destination);
      source.start();

      await new Promise(resolve => { source.onended = resolve; });
    }

    await ctx.close();
    this._playing = false;
    this._setState('ready');
  }

  // ═══════════════════════════════════════════════════════════════════════
  // UTILS
  // ═══════════════════════════════════════════════════════════════════════

  _send(obj) {
    if (this.ws && this.ws.readyState === WebSocket.OPEN) {
      this.ws.send(JSON.stringify(obj));
    }
  }

  _setState(s) {
    if (this.state === s) return;
    this.state = s;
    this.onStateChange(s);
  }

  _cleanup() {
    if (this.mediaStream) {
      this.mediaStream.getTracks().forEach(t => t.stop());
      this.mediaStream = null;
    }
    if (this.processor) {
      this.processor.disconnect();
      this.processor = null;
    }
    if (this.audioCtx) {
      this.audioCtx.close().catch(() => {});
      this.audioCtx = null;
    }
    this._audioQueue = [];
    this._playing = false;
  }

  _float32ToInt16(float32) {
    const int16 = new Int16Array(float32.length);
    for (let i = 0; i < float32.length; i++) {
      const s = Math.max(-1, Math.min(1, float32[i]));
      int16[i] = s < 0 ? s * 0x8000 : s * 0x7FFF;
    }
    return int16;
  }

  _arrayBufferToBase64(buffer) {
    const bytes = new Uint8Array(buffer);
    let binary = '';
    for (let i = 0; i < bytes.length; i++) binary += String.fromCharCode(bytes[i]);
    return btoa(binary);
  }
}

// Export for both module and script contexts
if (typeof window !== 'undefined') {
  window.RealtimeVoice = RealtimeVoice;
}
if (typeof module !== 'undefined' && module.exports) {
  module.exports = { RealtimeVoice };
}
