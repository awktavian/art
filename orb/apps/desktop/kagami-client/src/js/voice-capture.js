/**
 * Voice Capture — Push-to-Talk Interface
 *
 * Captures audio from the browser/device microphone and sends
 * to Whisper for transcription.
 *
 * Focus:
 *
 * Usage:
 *   - Hold Caps Lock or click mic button to record
 *   - Release to transcribe
 *   - Result appears in Quick Entry input
 */

// Check if running in Tauri
const isTauri = window.__TAURI_INTERNALS__ !== undefined;

// Voice capture state
let mediaRecorder = null;
let audioChunks = [];
let isRecording = false;
let stream = null;

// Tauri invoke (loaded dynamically)
let invoke = null;

// UI Elements
let listeningIndicator = null;
let statusText = null;

// Performance tracking
const voiceMetrics = {
    captureStartTime: 0,
    transcriptionStartTime: 0,
    lastLatencyMs: 0,
};

// ═══════════════════════════════════════════════════════════════
// INITIALIZATION
// ═══════════════════════════════════════════════════════════════

export async function initVoiceCapture() {
    console.log('🎤 Initializing voice capture...');

    listeningIndicator = document.getElementById('listening');
    statusText = document.getElementById('status-text');

    // Request microphone permission early
    try {
        stream = await navigator.mediaDevices.getUserMedia({
            audio: {
                echoCancellation: true,
                noiseSuppression: true,
                autoGainControl: true,
            }
        });
        console.log('✓ Microphone access granted');

        // Stop the stream for now, we'll restart when recording
        stream.getTracks().forEach(track => track.stop());
        stream = null;

    } catch (e) {
        console.warn('Microphone access denied:', e);
    }

    // Set up keyboard listener for Caps Lock
    setupKeyboardTrigger();

    return true;
}

// ═══════════════════════════════════════════════════════════════
// KEYBOARD TRIGGER
// Hold Caps Lock to record
// ═══════════════════════════════════════════════════════════════

function setupKeyboardTrigger() {
    // Track Caps Lock key state
    document.addEventListener('keydown', async (e) => {
        if (e.code === 'CapsLock' && !isRecording) {
            e.preventDefault();
            await startRecording();
        }
    });

    document.addEventListener('keyup', async (e) => {
        if (e.code === 'CapsLock' && isRecording) {
            e.preventDefault();
            await stopRecording();
        }
    });
}

// ═══════════════════════════════════════════════════════════════
// RECORDING FUNCTIONS
// ═══════════════════════════════════════════════════════════════

export async function startRecording() {
    if (isRecording) return;

    console.log('🎤 Starting recording...');
    isRecording = true;
    audioChunks = [];
    voiceMetrics.captureStartTime = performance.now();

    // Update UI
    if (listeningIndicator) {
        listeningIndicator.classList.add('active');
    }
    if (statusText) {
        statusText.textContent = 'Listening...';
    }

    // Try Tauri native audio first (lower latency)
    if (isTauri && invoke) {
        try {
            await invoke('start_voice_capture');
            console.log('✓ Using Tauri native audio capture');
            return;
        } catch (e) {
            console.warn('Tauri audio unavailable, falling back to browser:', e);
        }
    }

    try {
        // Get fresh stream
        stream = await navigator.mediaDevices.getUserMedia({
            audio: {
                echoCancellation: true,
                noiseSuppression: true,
                autoGainControl: true,
                sampleRate: 16000,  // Whisper prefers 16kHz
            }
        });

        // Create MediaRecorder
        const options = { mimeType: 'audio/webm;codecs=opus' };
        if (!MediaRecorder.isTypeSupported(options.mimeType)) {
            // Fallback
            mediaRecorder = new MediaRecorder(stream);
        } else {
            mediaRecorder = new MediaRecorder(stream, options);
        }

        mediaRecorder.ondataavailable = (e) => {
            if (e.data.size > 0) {
                audioChunks.push(e.data);
            }
        };

        mediaRecorder.onstop = async () => {
            // Combine chunks into blob
            const audioBlob = new Blob(audioChunks, { type: 'audio/webm' });
            console.log(`📝 Recorded ${audioBlob.size} bytes`);

            // Transcribe
            await transcribeAudio(audioBlob);
        };

        // Start recording
        mediaRecorder.start(100); // Collect data every 100ms

    } catch (e) {
        console.error('Failed to start recording:', e);
        isRecording = false;
        updateUIError('Microphone access denied');
    }
}

export async function stopRecording() {
    if (!isRecording) return;

    console.log('🎤 Stopping recording...');
    isRecording = false;
    voiceMetrics.transcriptionStartTime = performance.now();

    // Update UI
    if (listeningIndicator) {
        listeningIndicator.classList.remove('active');
    }
    if (statusText) {
        statusText.textContent = 'Transcribing...';
    }

    // Try Tauri native audio first
    if (isTauri && invoke) {
        try {
            const text = await invoke('stop_voice_capture');
            voiceMetrics.lastLatencyMs = performance.now() - voiceMetrics.captureStartTime;
            console.log(`✓ Transcription complete in ${voiceMetrics.lastLatencyMs.toFixed(0)}ms`);
            if (text) {
                handleTranscription(text);
            } else {
                updateUIError('No speech detected');
            }
            return;
        } catch (e) {
            console.warn('Tauri transcription failed:', e);
        }
    }

    // Browser fallback
    if (mediaRecorder) {
        mediaRecorder.stop();
    }

    // Stop stream
    if (stream) {
        stream.getTracks().forEach(track => track.stop());
        stream = null;
    }
}

// ═══════════════════════════════════════════════════════════════
// TRANSCRIPTION
// ═══════════════════════════════════════════════════════════════

async function transcribeAudio(audioBlob) {
    try {
        if (isTauri) {
            // In Tauri, we could send to backend for local Whisper
            // For now, we'll use the Kagami API endpoint
            const formData = new FormData();
            formData.append('audio', audioBlob, 'recording.webm');

            const response = await fetch('http://localhost:8001/audio/transcribe', {
                method: 'POST',
                body: formData,
            });

            if (response.ok) {
                const result = await response.json();
                handleTranscription(result.text);
            } else {
                throw new Error('Transcription failed');
            }
        } else {
            // Browser-only fallback: Use Web Speech API
            handleTranscription(await webSpeechTranscribe());
        }
    } catch (e) {
        console.error('Transcription error:', e);
        updateUIError('Transcription failed');

        // Fallback: show that we captured audio
        if (statusText) {
            statusText.textContent = `Captured ${(audioBlob.size / 1024).toFixed(1)}KB audio`;
        }
    }
}

// Web Speech API fallback
function webSpeechTranscribe() {
    return new Promise((resolve, reject) => {
        if (!('webkitSpeechRecognition' in window)) {
            reject(new Error('Speech recognition not supported'));
            return;
        }

        const recognition = new webkitSpeechRecognition();
        recognition.continuous = false;
        recognition.interimResults = false;
        recognition.lang = 'en-US';

        recognition.onresult = (event) => {
            const text = event.results[0][0].transcript;
            resolve(text);
        };

        recognition.onerror = (event) => {
            reject(new Error(event.error));
        };

        recognition.start();
    });
}

// ═══════════════════════════════════════════════════════════════
// HANDLE TRANSCRIPTION RESULT
// ═══════════════════════════════════════════════════════════════

function handleTranscription(text) {
    if (!text || text.trim().length === 0) {
        updateUIError('No speech detected');
        return;
    }

    console.log(`📝 Transcribed: "${text}"`);

    // Update status
    if (statusText) {
        statusText.textContent = 'Ready';
    }

    // Find command input and populate it
    const input = document.getElementById('command-input');
    if (input) {
        input.value = text;
        input.focus();

        // Trigger input event to update suggestions
        input.dispatchEvent(new Event('input', { bubbles: true }));
    }

    // Emit custom event
    window.dispatchEvent(new CustomEvent('voice-transcription', {
        detail: { text }
    }));
}

function updateUIError(message) {
    if (statusText) {
        statusText.textContent = message;
        setTimeout(() => {
            statusText.textContent = 'Ready';
        }, 2000);
    }
}

// ═══════════════════════════════════════════════════════════════
// EXPORTS
// ═══════════════════════════════════════════════════════════════

export const VoiceCapture = {
    init: initVoiceCapture,
    start: startRecording,
    stop: stopRecording,
    isRecording: () => isRecording,
};

// Auto-init if DOM is ready
if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', initVoiceCapture);
} else {
    initVoiceCapture();
}

// Expose globally
window.VoiceCapture = VoiceCapture;

console.log('%c🎤 Voice capture module loaded. Hold Caps Lock to record.', 'color: #4ecdc4;');

/*
 * 鏡
 */
