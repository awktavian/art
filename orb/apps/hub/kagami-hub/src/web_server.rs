//! Web server for phone-based configuration and control
//!
//! Enables iOS/Android apps to:
//! - Discover Hub via mDNS
//! - Configure API URL, wake word, LED settings
//! - Control LED ring
//! - Use phone as voice input proxy
//! - Monitor Hub status
//!
//! ## Security
//!
//! This server implements:
//! - CORS headers for cross-origin phone app requests
//! - Input validation on all configuration updates
//! - Request size limits to prevent DoS
//! - Error response standardization
//!
//! Colony: Beacon (e₅) — Signaling and guidance

use anyhow::Result;
use axum::{
    extract::{
        ws::{Message, WebSocket, WebSocketUpgrade},
        State,
    },
    http::{header, Method, StatusCode},
    response::IntoResponse,
    routing::{get, post},
    Json, Router,
};
use serde::{Deserialize, Serialize};
use std::sync::Arc;
use tokio::sync::{broadcast, RwLock};
use tower_http::cors::{AllowOrigin, CorsLayer};
use tower_http::limit::RequestBodyLimitLayer;
use tracing::{debug, error, info, warn};
use url::Url;

/// Maximum request body size (1MB - prevents DoS from large audio uploads)
const MAX_REQUEST_SIZE: usize = 1024 * 1024;

/// Maximum string length for configuration fields
const MAX_CONFIG_STRING_LENGTH: usize = 256;

/// Maximum age for request signatures (5 minutes)
const SIGNATURE_MAX_AGE_SECS: u64 = 300;

// ═══════════════════════════════════════════════════════════════════════════
// Request Signing (HMAC-SHA256)
// ═══════════════════════════════════════════════════════════════════════════

/// Request signature header name
pub const SIGNATURE_HEADER: &str = "X-Kagami-Signature";

/// Request timestamp header name
pub const TIMESTAMP_HEADER: &str = "X-Kagami-Timestamp";

/// Request nonce header name (for replay protection)
pub const NONCE_HEADER: &str = "X-Kagami-Nonce";

/// Signature verification result
#[derive(Debug)]
pub enum SignatureVerification {
    /// Signature is valid
    Valid,
    /// Signature is missing
    Missing,
    /// Signature is invalid (wrong format or mismatch)
    Invalid(String),
    /// Timestamp is too old or in the future
    Expired,
    /// Nonce was already used (replay attack)
    ReplayDetected,
}

/// Compute HMAC-SHA256 signature for a request
///
/// The signature covers: timestamp + nonce + method + path + body
/// This provides:
/// - Integrity: Body cannot be tampered with
/// - Replay protection: Nonce ensures requests can't be replayed
/// - Freshness: Timestamp prevents old requests from being accepted
pub fn compute_request_signature(
    secret: &[u8],
    timestamp: &str,
    nonce: &str,
    method: &str,
    path: &str,
    body: &[u8],
) -> String {
    use hmac::{Hmac, Mac};
    use sha2::Sha256;

    type HmacSha256 = Hmac<Sha256>;

    // Construct the signing payload
    let payload = format!(
        "{}:{}:{}:{}:{}",
        timestamp,
        nonce,
        method.to_uppercase(),
        path,
        base64::Engine::encode(&base64::engine::general_purpose::STANDARD, body)
    );

    let mut mac = HmacSha256::new_from_slice(secret)
        .expect("HMAC can take key of any size");
    mac.update(payload.as_bytes());

    // Return hex-encoded signature
    let result = mac.finalize();
    hex::encode(result.into_bytes())
}

/// Verify a request signature
///
/// Returns SignatureVerification indicating the result of verification.
/// State-changing endpoints should call this before processing the request.
pub fn verify_request_signature(
    secret: &[u8],
    signature: Option<&str>,
    timestamp: Option<&str>,
    nonce: Option<&str>,
    method: &str,
    path: &str,
    body: &[u8],
    used_nonces: &std::collections::HashSet<String>,
) -> SignatureVerification {
    // Check if signature is present
    let signature = match signature {
        Some(s) => s,
        None => return SignatureVerification::Missing,
    };

    // Check if timestamp is present and valid
    let timestamp = match timestamp {
        Some(t) => t,
        None => return SignatureVerification::Invalid("Missing timestamp".to_string()),
    };

    // Parse timestamp and check age
    let ts: u64 = match timestamp.parse() {
        Ok(t) => t,
        Err(_) => return SignatureVerification::Invalid("Invalid timestamp format".to_string()),
    };

    let now = std::time::SystemTime::now()
        .duration_since(std::time::UNIX_EPOCH)
        .map(|d| d.as_secs())
        .unwrap_or(0);

    // Check if timestamp is too old or too far in the future
    if ts + SIGNATURE_MAX_AGE_SECS < now {
        return SignatureVerification::Expired;
    }
    if ts > now + 60 {
        // Allow 60 seconds of clock skew
        return SignatureVerification::Invalid("Timestamp is in the future".to_string());
    }

    // Check nonce
    let nonce = match nonce {
        Some(n) => n,
        None => return SignatureVerification::Invalid("Missing nonce".to_string()),
    };

    // Check for replay attack
    if used_nonces.contains(nonce) {
        return SignatureVerification::ReplayDetected;
    }

    // Compute expected signature
    let expected = compute_request_signature(secret, timestamp, nonce, method, path, body);

    // Constant-time comparison to prevent timing attacks
    if constant_time_eq(signature.as_bytes(), expected.as_bytes()) {
        SignatureVerification::Valid
    } else {
        SignatureVerification::Invalid("Signature mismatch".to_string())
    }
}

/// Constant-time byte comparison to prevent timing attacks
fn constant_time_eq(a: &[u8], b: &[u8]) -> bool {
    if a.len() != b.len() {
        return false;
    }
    let mut result = 0u8;
    for (x, y) in a.iter().zip(b.iter()) {
        result |= x ^ y;
    }
    result == 0
}

// ═══════════════════════════════════════════════════════════════════════════
// Types
// ═══════════════════════════════════════════════════════════════════════════

#[derive(Clone, Serialize)]
pub struct HubStatus {
    pub name: String,
    pub location: String,
    pub api_url: String,
    pub api_connected: bool,
    pub safety_score: Option<f64>,
    pub led_ring_enabled: bool,
    pub led_brightness: f32,
    pub wake_word: String,
    pub is_listening: bool,
    pub current_colony: Option<String>,
    pub uptime_seconds: u64,
    pub version: &'static str,
}

#[derive(Clone, Serialize)]
pub struct HubConfig {
    pub name: String,
    pub location: String,
    pub api_url: String,
    pub wake_word: String,
    pub wake_sensitivity: f32,
    pub led_enabled: bool,
    pub led_brightness: f32,
    pub led_count: u8,
    pub tts_volume: f32,
    pub tts_colony: String,
}

#[derive(Deserialize)]
pub struct UpdateConfigRequest {
    pub name: Option<String>,
    pub location: Option<String>,
    pub api_url: Option<String>,
    pub wake_word: Option<String>,
    pub wake_sensitivity: Option<f32>,
    pub led_enabled: Option<bool>,
    pub led_brightness: Option<f32>,
    pub tts_volume: Option<f32>,
    pub tts_colony: Option<String>,
}

#[derive(Deserialize)]
pub struct LEDControlRequest {
    pub pattern: String, // "idle", "listening", "thinking", "speaking", "error", "colony"
    pub colony: Option<u8>, // 0-6 for specific colony highlight
    pub color: Option<String>, // hex color override
    pub brightness: Option<f32>,
}

#[derive(Deserialize)]
pub struct VoiceProxyRequest {
    pub audio_base64: String,
    pub sample_rate: u32,
    pub channels: u16,
}

#[derive(Serialize)]
pub struct VoiceProxyResponse {
    pub transcription: Option<String>,
    pub action_taken: Option<String>,
    pub response_audio_base64: Option<String>,
}

#[derive(Clone, Serialize)]
pub struct HubEvent {
    pub event_type: String,
    pub data: serde_json::Value,
    pub timestamp: u64,
}

// ═══════════════════════════════════════════════════════════════════════════
// Server State
// ═══════════════════════════════════════════════════════════════════════════

pub struct HubWebServer {
    config: Arc<RwLock<HubConfig>>,
    status: Arc<RwLock<HubStatus>>,
    event_tx: broadcast::Sender<HubEvent>,
    start_time: std::time::Instant,
}

impl HubWebServer {
    pub fn new(config: HubConfig) -> Self {
        let (event_tx, _) = broadcast::channel(100);

        let status = HubStatus {
            name: config.name.clone(),
            location: config.location.clone(),
            api_url: config.api_url.clone(),
            api_connected: false,
            safety_score: None,
            led_ring_enabled: config.led_enabled,
            led_brightness: config.led_brightness,
            wake_word: config.wake_word.clone(),
            is_listening: false,
            current_colony: None,
            uptime_seconds: 0,
            version: env!("CARGO_PKG_VERSION"),
        };

        Self {
            config: Arc::new(RwLock::new(config)),
            status: Arc::new(RwLock::new(status)),
            event_tx,
            start_time: std::time::Instant::now(),
        }
    }

    pub fn from_hub_config(cfg: &crate::config::HubConfig) -> Self {
        Self::new(HubConfig {
            name: cfg.general.name.clone(),
            location: cfg.general.location.clone(),
            api_url: cfg.general.api_url.clone(),
            wake_word: cfg.wake_word.phrase.clone(),
            wake_sensitivity: cfg.wake_word.sensitivity,
            led_enabled: cfg.led_ring.enabled,
            led_brightness: cfg.led_ring.brightness,
            led_count: cfg.led_ring.count,
            tts_volume: cfg.tts.volume,
            tts_colony: cfg.tts.colony.clone(),
        })
    }

    pub async fn run(&self, port: u16) -> Result<()> {
        let app = self.create_router();

        // Start mDNS advertisement
        self.advertise_mdns(port).await;

        let addr = std::net::SocketAddr::from(([0, 0, 0, 0], port));
        info!("📱 Hub web server listening on http://0.0.0.0:{}", port);
        info!("   Discoverable via mDNS as _kagami-hub._tcp");

        let listener = tokio::net::TcpListener::bind(addr).await?;
        axum::serve(listener, app).await?;

        Ok(())
    }

    fn create_router(&self) -> Router {
        // PERFORMANCE FIX (Jan 2026): Create shared HTTP client once instead of per-request
        let http_client = reqwest::Client::builder()
            .timeout(std::time::Duration::from_secs(30))
            .pool_max_idle_per_host(10)
            .build()
            .expect("Failed to create HTTP client");

        // Initialize STT engine (optional - may fail if model not available)
        // Uses default config (base.en model at 16kHz)
        let stt_engine = match crate::stt::STTEngine::new(crate::stt::STTConfig::default()) {
            Ok(engine) => {
                info!("✓ STT engine initialized for voice proxy");
                Some(Arc::new(engine))
            }
            Err(e) => {
                warn!("STT engine not available: {} (voice proxy will return errors)", e);
                None
            }
        };

        let state = AppState {
            config: self.config.clone(),
            status: self.status.clone(),
            event_tx: self.event_tx.clone(),
            start_time: self.start_time,
            http_client,
            stt_engine,
        };

        // CORS layer - allow requests from phone apps and local network
        // Security: Restrict origins to known clients rather than wildcard
        let allowed_origins: Vec<_> = [
            // Local development
            "http://localhost:3000",
            "http://localhost:3001",
            "http://localhost:8080",
            // Local network (mDNS resolved)
            "http://kagami.local:3000",
            "http://kagami.local:8000",
            // Production domains (awkronos.com)
            "https://awkronos.com",
            "https://api.awkronos.com",
            "https://qa.awkronos.com",
            "https://dashboard.awkronos.com",
            // Production domains (kagami.com)
            "https://qa.kagami.com",
            "https://dashboard.kagami.com",
            // iOS/Android apps (capacitor/native)
            "capacitor://localhost",
            "ionic://localhost",
        ]
        .into_iter()
        .filter_map(|s| s.parse().ok())
        .collect();

        let cors = CorsLayer::new()
            .allow_origin(AllowOrigin::list(allowed_origins))
            .allow_methods([Method::GET, Method::POST, Method::OPTIONS])
            .allow_headers([header::CONTENT_TYPE, header::ACCEPT]);

        Router::new()
            // Status endpoints
            .route("/", get(root_handler))
            .route("/status", get(get_status))
            .route("/health", get(health_check))
            // Configuration endpoints
            .route("/config", get(get_config))
            .route("/config", post(update_config))
            // Control endpoints
            .route("/led", post(control_led))
            .route("/led/test", post(test_led))
            .route("/voice/proxy", post(voice_proxy))
            .route("/voice/listen", post(trigger_listen))
            .route("/command", post(execute_command))
            // Observability endpoints
            .route("/metrics", get(get_metrics))
            .route("/diagnostics", get(get_diagnostics))
            // Real-time events
            .route("/ws", get(websocket_handler))
            // Security: Apply request body size limit to prevent DoS
            .layer(RequestBodyLimitLayer::new(MAX_REQUEST_SIZE))
            .layer(cors)
            .with_state(state)
    }

    async fn advertise_mdns(&self, port: u16) {
        // mDNS advertisement for service discovery
        // Phones can find Hub at _kagami-hub._tcp.local
        tokio::spawn(async move {
            #[cfg(feature = "mdns")]
            {
                use mdns_sd::{ServiceDaemon, ServiceInfo};

                let mdns = ServiceDaemon::new().expect("Failed to create mDNS daemon");

                let service_type = "_kagami-hub._tcp.local.";
                let instance_name = "Kagami Hub";

                let mut properties = std::collections::HashMap::new();
                properties.insert("version".to_string(), env!("CARGO_PKG_VERSION").to_string());
                properties.insert("type".to_string(), "hub".to_string());

                let service = ServiceInfo::new(
                    service_type,
                    instance_name,
                    &format!("{}.local.", hostname::get().unwrap().to_string_lossy()),
                    (),
                    port,
                    properties,
                )
                .expect("Failed to create service info");

                mdns.register(service)
                    .expect("Failed to register mDNS service");

                info!("📡 mDNS: Advertising as {}", instance_name);
            }

            #[cfg(not(feature = "mdns"))]
            {
                info!("📡 mDNS: Disabled (compile with --features mdns)");
                info!("   Hub available at http://<ip>:{}", port);
            }
        });
    }

    // Update status from main loop
    pub async fn update_status(&self, update: impl FnOnce(&mut HubStatus)) {
        let mut status = self.status.write().await;
        status.uptime_seconds = self.start_time.elapsed().as_secs();
        update(&mut status);

        // Broadcast update to WebSocket clients
        let event = HubEvent {
            event_type: "status_update".to_string(),
            data: serde_json::to_value(&*status).unwrap_or_default(),
            timestamp: std::time::SystemTime::now()
                .duration_since(std::time::UNIX_EPOCH)
                .map(|d| d.as_millis() as u64)
                .unwrap_or(0),
        };
        let _ = self.event_tx.send(event);
    }

    pub fn subscribe(&self) -> broadcast::Receiver<HubEvent> {
        self.event_tx.subscribe()
    }
}

// ═══════════════════════════════════════════════════════════════════════════
// App State
// ═══════════════════════════════════════════════════════════════════════════

#[derive(Clone)]
struct AppState {
    config: Arc<RwLock<HubConfig>>,
    status: Arc<RwLock<HubStatus>>,
    event_tx: broadcast::Sender<HubEvent>,
    start_time: std::time::Instant,
    /// Shared HTTP client for API calls.
    /// PERFORMANCE FIX (Jan 2026): Reuse client instead of creating new one per request.
    http_client: reqwest::Client,
    /// STT engine for voice transcription (optional - requires whisper feature)
    stt_engine: Option<Arc<crate::stt::STTEngine>>,
}

// ═══════════════════════════════════════════════════════════════════════════
// Route Handlers
// ═══════════════════════════════════════════════════════════════════════════

async fn root_handler() -> impl IntoResponse {
    axum::response::Html(HUB_CONFIG_UI)
}

/// Prismorphism-styled configuration UI for Hub
const HUB_CONFIG_UI: &str = r###"<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Kagami Hub</title>
    <style>
        /* Design Tokens (from config/design-tokens) */
        :root {
            --void: #07060B;
            --obsidian: #12101A;
            --carbon: #252330;

            --spark: #ff6b35;
            --forge: #d4af37;
            --flow: #4ecdc4;
            --nexus: #9b7ebd;
            --beacon: #f59e0b;
            --grove: #7eb77f;
            --crystal: #67d4e4;

            --text-primary: #f5f0e8;
            --text-secondary: rgba(245, 240, 232, 0.65);

            --radius-md: 12px;
            --space-sm: 8px;
            --space-md: 16px;
            --space-lg: 24px;
        }

        * { box-sizing: border-box; margin: 0; padding: 0; }

        body {
            font-family: -apple-system, BlinkMacSystemFont, 'SF Pro', system-ui, sans-serif;
            background: var(--void);
            color: var(--text-primary);
            min-height: 100vh;
            padding: var(--space-lg);
        }

        /* Prismorphism Glass Card */
        .glass-card {
            background: rgba(18, 16, 26, 0.8);
            backdrop-filter: blur(20px);
            -webkit-backdrop-filter: blur(20px);
            border: 1px solid rgba(255, 255, 255, 0.1);
            border-radius: var(--radius-md);
            padding: var(--space-lg);
            margin-bottom: var(--space-md);
            position: relative;
            overflow: hidden;
        }

        /* Spectral border animation */
        .glass-card::before {
            content: '';
            position: absolute;
            top: -1px; left: -1px; right: -1px; bottom: -1px;
            border-radius: var(--radius-md);
            background: conic-gradient(
                from 0deg,
                var(--spark),
                var(--forge),
                var(--flow),
                var(--nexus),
                var(--beacon),
                var(--grove),
                var(--crystal),
                var(--spark)
            );
            z-index: -1;
            animation: spectral-rotate 8s linear infinite;
            opacity: 0.3;
        }

        @keyframes spectral-rotate {
            from { transform: rotate(0deg); }
            to { transform: rotate(360deg); }
        }

        h1 {
            font-size: 1.5rem;
            font-weight: 600;
            margin-bottom: var(--space-md);
            background: linear-gradient(135deg, var(--crystal), var(--nexus));
            -webkit-background-clip: text;
            -webkit-text-fill-color: transparent;
            background-clip: text;
        }

        h2 {
            font-size: 1rem;
            font-weight: 500;
            color: var(--text-secondary);
            margin-bottom: var(--space-sm);
        }

        /* Colony LED Display */
        .led-ring {
            display: flex;
            gap: var(--space-sm);
            justify-content: center;
            padding: var(--space-md);
        }

        .led {
            width: 24px;
            height: 24px;
            border-radius: 50%;
            box-shadow: 0 0 10px currentColor;
            animation: led-pulse 2s ease-in-out infinite;
        }

        .led:nth-child(1) { color: var(--spark); background: var(--spark); animation-delay: 0s; }
        .led:nth-child(2) { color: var(--forge); background: var(--forge); animation-delay: 0.28s; }
        .led:nth-child(3) { color: var(--flow); background: var(--flow); animation-delay: 0.57s; }
        .led:nth-child(4) { color: var(--nexus); background: var(--nexus); animation-delay: 0.85s; }
        .led:nth-child(5) { color: var(--beacon); background: var(--beacon); animation-delay: 1.14s; }
        .led:nth-child(6) { color: var(--grove); background: var(--grove); animation-delay: 1.42s; }
        .led:nth-child(7) { color: var(--crystal); background: var(--crystal); animation-delay: 1.71s; }

        @keyframes led-pulse {
            0%, 100% { opacity: 0.5; transform: scale(1); }
            50% { opacity: 1; transform: scale(1.1); }
        }

        /* Form elements */
        label {
            display: block;
            font-size: 0.875rem;
            color: var(--text-secondary);
            margin-bottom: var(--space-sm);
        }

        input, select {
            width: 100%;
            padding: var(--space-sm) var(--space-md);
            background: rgba(37, 35, 48, 0.5);
            border: 1px solid rgba(255, 255, 255, 0.1);
            border-radius: 8px;
            color: var(--text-primary);
            font-size: 1rem;
            margin-bottom: var(--space-md);
        }

        input:focus, select:focus {
            outline: none;
            border-color: var(--crystal);
            box-shadow: 0 0 0 2px rgba(103, 212, 228, 0.2);
        }

        input[type="range"] {
            -webkit-appearance: none;
            background: var(--carbon);
            height: 4px;
            border-radius: 2px;
        }

        input[type="range"]::-webkit-slider-thumb {
            -webkit-appearance: none;
            width: 20px;
            height: 20px;
            border-radius: 50%;
            background: var(--crystal);
            cursor: pointer;
        }

        button {
            padding: var(--space-sm) var(--space-lg);
            background: linear-gradient(135deg, var(--crystal), var(--nexus));
            border: none;
            border-radius: 8px;
            color: var(--void);
            font-weight: 600;
            cursor: pointer;
            transition: transform 0.2s, box-shadow 0.2s;
        }

        button:hover {
            transform: translateY(-2px);
            box-shadow: 0 4px 20px rgba(103, 212, 228, 0.4);
        }

        button:active {
            transform: translateY(0);
        }

        /* Status badge */
        .status-badge {
            display: inline-flex;
            align-items: center;
            gap: var(--space-sm);
            padding: 4px 12px;
            border-radius: 999px;
            font-size: 0.75rem;
            font-weight: 500;
        }

        .status-badge.connected {
            background: rgba(0, 255, 136, 0.1);
            color: #00ff88;
        }

        .status-badge.disconnected {
            background: rgba(255, 68, 68, 0.1);
            color: #ff4444;
        }

        /* Grid */
        .grid {
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(300px, 1fr));
            gap: var(--space-md);
        }

        /* Logo */
        .logo {
            font-size: 3rem;
            text-align: center;
            margin-bottom: var(--space-sm);
        }
    </style>
</head>
<body>
    <div class="glass-card" style="text-align: center;">
        <div class="logo">鏡</div>
        <h1>Kagami Hub</h1>
        <div class="led-ring">
            <div class="led"></div>
            <div class="led"></div>
            <div class="led"></div>
            <div class="led"></div>
            <div class="led"></div>
            <div class="led"></div>
            <div class="led"></div>
        </div>
        <span class="status-badge connected" id="status">● Connected</span>
    </div>

    <div class="grid">
        <div class="glass-card">
            <h2>Configuration</h2>
            <label>Hub Name</label>
            <input type="text" id="name" placeholder="Living Room Hub">

            <label>Location</label>
            <input type="text" id="location" placeholder="Living Room">

            <label>API URL</label>
            <input type="text" id="api_url" placeholder="http://kagami.local:8000">

            <label>Wake Word</label>
            <input type="text" id="wake_word" placeholder="Hey Kagami">

            <button onclick="saveConfig()">Save Configuration</button>
        </div>

        <div class="glass-card">
            <h2>LED Ring</h2>
            <label>Brightness: <span id="brightness-val">70%</span></label>
            <input type="range" id="brightness" min="0" max="100" value="70"
                   oninput="document.getElementById('brightness-val').textContent = this.value + '%'">

            <label>Pattern</label>
            <select id="pattern">
                <option value="idle">Idle (Colony Colors)</option>
                <option value="breathing">Breathing</option>
                <option value="spectral">Spectral Shimmer</option>
                <option value="fano">Fano Pulse</option>
                <option value="rainbow">Rainbow</option>
                <option value="sparkle">Sparkle</option>
            </select>

            <button onclick="setLED()">Apply LED Settings</button>
        </div>
    </div>

    <div class="glass-card">
        <h2>API Endpoints</h2>
        <pre style="color: var(--text-secondary); font-size: 0.875rem; overflow-x: auto;">
GET  /status      - Hub status
GET  /health      - Health check
GET  /config      - Get configuration
POST /config      - Update configuration
POST /led         - Control LED ring
POST /voice/proxy - Voice proxy from phone
GET  /metrics     - Prometheus metrics
GET  /diagnostics - System diagnostics
WS   /ws          - Real-time events
        </pre>
    </div>

    <script>
        // Load current config on page load
        fetch('/config')
            .then(r => r.json())
            .then(config => {
                document.getElementById('name').value = config.name || '';
                document.getElementById('location').value = config.location || '';
                document.getElementById('api_url').value = config.api_url || '';
                document.getElementById('wake_word').value = config.wake_word || '';
                document.getElementById('brightness').value = (config.led_brightness || 0.7) * 100;
                document.getElementById('brightness-val').textContent = Math.round((config.led_brightness || 0.7) * 100) + '%';
            });

        function saveConfig() {
            fetch('/config', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    name: document.getElementById('name').value,
                    location: document.getElementById('location').value,
                    api_url: document.getElementById('api_url').value,
                    wake_word: document.getElementById('wake_word').value,
                    led_brightness: parseInt(document.getElementById('brightness').value) / 100
                })
            }).then(() => alert('Configuration saved!'));
        }

        function setLED() {
            fetch('/led', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    pattern: document.getElementById('pattern').value,
                    brightness: parseInt(document.getElementById('brightness').value) / 100
                })
            });
        }

        // WebSocket for real-time updates
        const ws = new WebSocket(`ws://${location.host}/ws`);
        ws.onopen = () => {
            document.getElementById('status').className = 'status-badge connected';
            document.getElementById('status').textContent = '● Connected';
        };
        ws.onclose = () => {
            document.getElementById('status').className = 'status-badge disconnected';
            document.getElementById('status').textContent = '● Disconnected';
        };
    </script>
</body>
</html>
"###;

async fn health_check(State(state): State<AppState>) -> impl IntoResponse {
    let status = state.status.read().await;
    Json(serde_json::json!({
        "status": "ok",
        "api_connected": status.api_connected,
        "safety_score": status.safety_score,
        "uptime_seconds": state.start_time.elapsed().as_secs()
    }))
}

/// Prometheus/OpenMetrics endpoint for observability
/// Returns metrics in text/plain format for scraping
async fn get_metrics() -> impl IntoResponse {
    let metrics = crate::telemetry::export();
    (
        [(header::CONTENT_TYPE, "text/plain; version=0.0.4; charset=utf-8")],
        metrics,
    )
}

/// Diagnostics endpoint for detailed health checks
/// Returns comprehensive system diagnostics in JSON format
async fn get_diagnostics() -> impl IntoResponse {
    let diagnostics = crate::diagnostics::Diagnostics::new();
    let report = diagnostics.run_all().await;
    Json(report)
}

async fn get_status(State(state): State<AppState>) -> impl IntoResponse {
    let mut status = state.status.write().await;
    status.uptime_seconds = state.start_time.elapsed().as_secs();
    Json(status.clone())
}

async fn get_config(State(state): State<AppState>) -> impl IntoResponse {
    let config = state.config.read().await;
    Json(config.clone())
}

/// Standardized error response for API endpoints
///
/// In production, error messages are sanitized to avoid leaking internal details.
/// Field names are only included in debug/development builds.
#[derive(Serialize)]
struct ApiError {
    error: String,
    /// Field name (only included in non-release builds)
    #[serde(skip_serializing_if = "Option::is_none")]
    #[cfg_attr(not(debug_assertions), serde(skip_serializing))]
    field: Option<String>,
}

impl ApiError {
    /// Create a new API error with optional field context
    ///
    /// In release builds, the field is stored but not serialized to prevent
    /// information leakage to potential attackers.
    fn new(error: impl Into<String>, field: Option<String>) -> Self {
        Self {
            error: error.into(),
            field,
        }
    }

    /// Create a generic validation error for production
    ///
    /// Returns a sanitized error message that doesn't leak field names
    fn validation_error(detailed_msg: &str, field: Option<&str>) -> Self {
        // In debug mode, include detailed message
        #[cfg(debug_assertions)]
        {
            Self {
                error: detailed_msg.to_string(),
                field: field.map(String::from),
            }
        }
        // In release mode, use generic message
        #[cfg(not(debug_assertions))]
        {
            let _ = detailed_msg; // Suppress unused warning
            let _ = field;
            Self {
                error: "Invalid request data".to_string(),
                field: None,
            }
        }
    }
}

/// Validate a string field against security constraints
fn validate_string(value: &str, field_name: &str) -> Result<(), ApiError> {
    if value.len() > MAX_CONFIG_STRING_LENGTH {
        return Err(ApiError::validation_error(
            &format!("{} too long (max {} chars)", field_name, MAX_CONFIG_STRING_LENGTH),
            Some(field_name),
        ));
    }
    // Reject strings with control characters (except common whitespace)
    if value
        .chars()
        .any(|c| c.is_control() && c != ' ' && c != '\t' && c != '\n')
    {
        return Err(ApiError::validation_error(
            &format!("{} contains invalid characters", field_name),
            Some(field_name),
        ));
    }
    Ok(())
}

/// Validate a URL string
fn validate_url(value: &str, field_name: &str) -> Result<(), ApiError> {
    validate_string(value, field_name)?;
    if !value.is_empty() {
        Url::parse(value).map_err(|_| {
            ApiError::validation_error(
                &format!("{} is not a valid URL", field_name),
                Some(field_name),
            )
        })?;
    }
    Ok(())
}

async fn update_config(
    State(state): State<AppState>,
    Json(req): Json<UpdateConfigRequest>,
) -> Result<Json<HubConfig>, (StatusCode, Json<ApiError>)> {
    // Validate all inputs before applying any changes
    if let Some(ref name) = req.name {
        validate_string(name, "name").map_err(|e| (StatusCode::BAD_REQUEST, Json(e)))?;
        if name.is_empty() {
            return Err((
                StatusCode::BAD_REQUEST,
                Json(ApiError::validation_error("name cannot be empty", Some("name"))),
            ));
        }
    }
    if let Some(ref location) = req.location {
        validate_string(location, "location").map_err(|e| (StatusCode::BAD_REQUEST, Json(e)))?;
    }
    if let Some(ref api_url) = req.api_url {
        validate_url(api_url, "api_url").map_err(|e| (StatusCode::BAD_REQUEST, Json(e)))?;
    }
    if let Some(ref wake_word) = req.wake_word {
        validate_string(wake_word, "wake_word").map_err(|e| (StatusCode::BAD_REQUEST, Json(e)))?;
        if wake_word.is_empty() {
            return Err((
                StatusCode::BAD_REQUEST,
                Json(ApiError::validation_error("wake_word cannot be empty", Some("wake_word"))),
            ));
        }
    }
    if let Some(ref colony) = req.tts_colony {
        validate_string(colony, "tts_colony").map_err(|e| (StatusCode::BAD_REQUEST, Json(e)))?;
    }

    // All validations passed, apply changes
    let mut config = state.config.write().await;

    if let Some(name) = req.name {
        config.name = name;
    }
    if let Some(location) = req.location {
        config.location = location;
    }
    if let Some(api_url) = req.api_url {
        config.api_url = api_url;
    }
    if let Some(wake_word) = req.wake_word {
        config.wake_word = wake_word;
    }
    if let Some(sensitivity) = req.wake_sensitivity {
        config.wake_sensitivity = sensitivity.clamp(0.0, 1.0);
    }
    if let Some(enabled) = req.led_enabled {
        config.led_enabled = enabled;
    }
    if let Some(brightness) = req.led_brightness {
        config.led_brightness = brightness.clamp(0.0, 1.0);
    }
    if let Some(volume) = req.tts_volume {
        config.tts_volume = volume.clamp(0.0, 1.0);
    }
    if let Some(colony) = req.tts_colony {
        config.tts_colony = colony;
    }

    info!("📱 Config updated from phone app");

    // Broadcast config change
    let event = HubEvent {
        event_type: "config_updated".to_string(),
        data: serde_json::to_value(&*config).unwrap_or_default(),
        timestamp: std::time::SystemTime::now()
            .duration_since(std::time::UNIX_EPOCH)
            .map(|d| d.as_millis() as u64)
            .unwrap_or(0),
    };
    let _ = state.event_tx.send(event);

    Ok(Json(config.clone()))
}

/// Valid LED patterns
const VALID_LED_PATTERNS: &[&str] = &[
    "idle",
    "listening",
    "processing",
    "thinking",
    "executing",
    "speaking",
    "error",
    "success",
    "breathing",
    "spectral",
    "fano",
    "fano_pulse",
    "rainbow",
    "sparkle",
    "colony",
];

async fn control_led(
    State(state): State<AppState>,
    Json(req): Json<LEDControlRequest>,
) -> Result<Json<serde_json::Value>, (StatusCode, Json<ApiError>)> {
    // Validate pattern
    if !VALID_LED_PATTERNS.contains(&req.pattern.as_str()) {
        return Err((
            StatusCode::BAD_REQUEST,
            Json(ApiError::validation_error(
                &format!("Invalid pattern '{}'. Valid: {:?}", req.pattern, VALID_LED_PATTERNS),
                Some("pattern"),
            )),
        ));
    }

    // Validate colony index if provided
    if let Some(colony) = req.colony {
        if colony > 6 {
            return Err((
                StatusCode::BAD_REQUEST,
                Json(ApiError::validation_error("Colony index must be 0-6", Some("colony"))),
            ));
        }
    }

    // Validate hex color if provided
    if let Some(ref color) = req.color {
        if !color.starts_with('#')
            || color.len() != 7
            || !color[1..].chars().all(|c| c.is_ascii_hexdigit())
        {
            return Err((
                StatusCode::BAD_REQUEST,
                Json(ApiError::validation_error("Invalid hex color format. Use #RRGGBB", Some("color"))),
            ));
        }
    }

    info!("💡 LED control: pattern={}", req.pattern);

    // Apply LED control
    #[cfg(feature = "rpi")]
    {
        use crate::led_ring;
        match req.pattern.as_str() {
            "idle" => led_ring::show_idle(),
            "listening" => led_ring::show_listening(),
            "processing" | "thinking" => led_ring::show_processing(),
            "executing" => led_ring::show_executing(),
            "speaking" => led_ring::show_speaking(),
            "error" => led_ring::show_error(),
            "success" => led_ring::show_success(),
            "breathing" => {
                // Set breathing pattern via pattern API
            }
            "spectral" => led_ring::show_spectral(),
            "fano" | "fano_pulse" => led_ring::show_fano_pulse(),
            "rainbow" => {
                // Rainbow pattern
            }
            "sparkle" => {
                // Sparkle pattern
            }
            "colony" => {
                if let Some(idx) = req.colony {
                    led_ring::highlight_colony(idx as usize);
                }
            }
            _ => {}
        }
        if let Some(_brightness) = req.brightness {
            // led_ring::set_brightness(brightness);
        }
    }

    // Update status
    let mut status = state.status.write().await;
    if let Some(brightness) = req.brightness {
        status.led_brightness = brightness.clamp(0.0, 1.0);
    }

    Ok(Json(serde_json::json!({"success": true})))
}

async fn test_led(State(_state): State<AppState>) -> impl IntoResponse {
    info!("🧪 LED test pattern");

    #[cfg(feature = "rpi")]
    {
        use crate::led_ring;
        led_ring::test_pattern();
    }

    (
        StatusCode::OK,
        Json(serde_json::json!({"success": true, "message": "LED test running"})),
    )
}

/// Maximum audio payload size (10MB - reasonable for voice recordings)
const MAX_AUDIO_SIZE: usize = 10 * 1024 * 1024;

/// Valid sample rates for audio input
const VALID_AUDIO_SAMPLE_RATES: &[u32] = &[8000, 16000, 22050, 44100, 48000];

async fn voice_proxy(
    State(state): State<AppState>,
    Json(req): Json<VoiceProxyRequest>,
) -> Result<Json<VoiceProxyResponse>, (StatusCode, Json<ApiError>)> {
    // Validate sample rate
    if !VALID_AUDIO_SAMPLE_RATES.contains(&req.sample_rate) {
        return Err((
            StatusCode::BAD_REQUEST,
            Json(ApiError::validation_error(
                &format!("Invalid sample_rate {}. Valid: {:?}", req.sample_rate, VALID_AUDIO_SAMPLE_RATES),
                Some("sample_rate"),
            )),
        ));
    }

    // Validate channels (1 = mono, 2 = stereo)
    if req.channels == 0 || req.channels > 2 {
        return Err((
            StatusCode::BAD_REQUEST,
            Json(ApiError::validation_error(
                "channels must be 1 (mono) or 2 (stereo)",
                Some("channels"),
            )),
        ));
    }

    // Validate audio payload size
    if req.audio_base64.len() > MAX_AUDIO_SIZE {
        return Err((
            StatusCode::PAYLOAD_TOO_LARGE,
            Json(ApiError::validation_error(
                &format!("audio_base64 too large (max {} bytes)", MAX_AUDIO_SIZE),
                Some("audio_base64"),
            )),
        ));
    }

    info!(
        "🎤 Voice proxy: received {} bytes from phone ({}Hz, {} ch)",
        req.audio_base64.len(),
        req.sample_rate,
        req.channels
    );

    // Decode audio
    let audio_data = match base64::Engine::decode(
        &base64::engine::general_purpose::STANDARD,
        &req.audio_base64,
    ) {
        Ok(data) => data,
        Err(e) => {
            warn!("Failed to decode audio: {}", e);
            return Err((
                StatusCode::BAD_REQUEST,
                Json(ApiError::validation_error(
                    &format!("Invalid base64 encoding: {}", e),
                    Some("audio_base64"),
                )),
            ));
        }
    };

    // Show listening state
    #[cfg(feature = "rpi")]
    {
        use crate::led_ring;
        led_ring::show_listening();
    }

    // Check if STT engine is available
    let stt_engine = match &state.stt_engine {
        Some(engine) => engine.clone(),
        None => {
            #[cfg(feature = "rpi")]
            {
                use crate::led_ring;
                led_ring::show_idle();
            }
            return Err((
                StatusCode::SERVICE_UNAVAILABLE,
                Json(ApiError::new(
                    "Speech-to-text engine not available. Ensure whisper model is installed.",
                    None,
                )),
            ));
        }
    };

    // Convert raw bytes to i16 samples (assuming 16-bit PCM little-endian)
    let samples_i16: Vec<i16> = audio_data
        .chunks_exact(2)
        .map(|chunk| i16::from_le_bytes([chunk[0], chunk[1]]))
        .collect();

    // Convert stereo to mono if needed (average channels)
    let mono_samples: Vec<i16> = if req.channels == 2 {
        samples_i16
            .chunks_exact(2)
            .map(|pair| ((pair[0] as i32 + pair[1] as i32) / 2) as i16)
            .collect()
    } else {
        samples_i16
    };

    // Resample to 16kHz if needed (Whisper expects 16kHz)
    let samples_16k: Vec<i16> = if req.sample_rate != 16000 {
        resample_to_16k(&mono_samples, req.sample_rate)
    } else {
        mono_samples
    };

    debug!(
        "Audio processed: {} samples at 16kHz ({:.2}s)",
        samples_16k.len(),
        samples_16k.len() as f32 / 16000.0
    );

    // Run transcription in blocking task (Whisper is CPU-intensive)
    let transcription = tokio::task::spawn_blocking(move || {
        stt_engine.transcribe(&samples_16k)
    })
    .await
    .map_err(|e| {
        error!("Transcription task failed: {}", e);
        (
            StatusCode::INTERNAL_SERVER_ERROR,
            Json(ApiError::new(format!("Transcription task failed: {}", e), None)),
        )
    })?
    .map_err(|e| {
        warn!("Transcription error: {}", e);
        (
            StatusCode::INTERNAL_SERVER_ERROR,
            Json(ApiError::new(format!("Transcription failed: {}", e), None)),
        )
    })?;

    info!("📝 Transcribed: \"{}\"", transcription);

    #[cfg(feature = "rpi")]
    {
        use crate::led_ring;
        led_ring::show_idle();
    }

    let response = VoiceProxyResponse {
        transcription: if transcription.is_empty() {
            None
        } else {
            Some(transcription)
        },
        action_taken: None,
        response_audio_base64: None,
    };

    Ok(Json(response))
}

/// Resample audio from source sample rate to 16kHz
/// Uses linear interpolation for simplicity (good enough for voice)
fn resample_to_16k(samples: &[i16], source_rate: u32) -> Vec<i16> {
    if source_rate == 16000 {
        return samples.to_vec();
    }

    let ratio = source_rate as f64 / 16000.0;
    let output_len = (samples.len() as f64 / ratio).ceil() as usize;
    let mut output = Vec::with_capacity(output_len);

    for i in 0..output_len {
        let src_idx = i as f64 * ratio;
        let idx_floor = src_idx.floor() as usize;
        let idx_ceil = (idx_floor + 1).min(samples.len() - 1);
        let frac = src_idx - idx_floor as f64;

        // Linear interpolation
        let sample = if idx_floor < samples.len() {
            let s0 = samples[idx_floor] as f64;
            let s1 = samples[idx_ceil] as f64;
            (s0 + (s1 - s0) * frac) as i16
        } else {
            0
        };
        output.push(sample);
    }

    output
}

async fn trigger_listen(State(state): State<AppState>) -> impl IntoResponse {
    info!("👂 Listen triggered from phone");

    // Update status
    let mut status = state.status.write().await;
    status.is_listening = true;

    // Show listening LED
    #[cfg(feature = "rpi")]
    {
        use crate::led_ring;
        led_ring::show_listening();
    }

    // Broadcast event
    let event = HubEvent {
        event_type: "listening_started".to_string(),
        data: serde_json::json!({}),
        timestamp: std::time::SystemTime::now()
            .duration_since(std::time::UNIX_EPOCH)
            .map(|d| d.as_millis() as u64)
            .unwrap_or(0),
    };
    let _ = state.event_tx.send(event);

    (StatusCode::OK, Json(serde_json::json!({"success": true})))
}

/// Maximum command length to prevent abuse
const MAX_COMMAND_LENGTH: usize = 1024;

#[derive(Deserialize)]
struct CommandRequest {
    command: String,
    /// Optional parameters for the command (reserved for future use)
    #[allow(dead_code)]
    params: Option<serde_json::Value>,
}

async fn execute_command(
    State(state): State<AppState>,
    Json(req): Json<CommandRequest>,
) -> Result<Json<serde_json::Value>, (StatusCode, Json<ApiError>)> {
    // Validate command
    if req.command.is_empty() {
        return Err((
            StatusCode::BAD_REQUEST,
            Json(ApiError::validation_error("command cannot be empty", Some("command"))),
        ));
    }
    if req.command.len() > MAX_COMMAND_LENGTH {
        return Err((
            StatusCode::BAD_REQUEST,
            Json(ApiError::validation_error(
                &format!("command too long (max {} chars)", MAX_COMMAND_LENGTH),
                Some("command"),
            )),
        ));
    }
    // Reject commands with control characters
    if req.command.chars().any(|c| c.is_control() && c != ' ') {
        return Err((
            StatusCode::BAD_REQUEST,
            Json(ApiError::validation_error("command contains invalid characters", Some("command"))),
        ));
    }

    info!("⚡ Command from phone: {}", req.command);

    // Forward to Kagami API
    let config = state.config.read().await;
    let api_url = config.api_url.clone();
    drop(config);

    // Validate API URL before making request
    if api_url.is_empty() {
        return Err((
            StatusCode::SERVICE_UNAVAILABLE,
            Json(ApiError::new("API URL not configured", None)),
        ));
    }

    // PERFORMANCE FIX (Jan 2026): Use shared client from state instead of creating new one
    let result = state.http_client
        .post(format!("{}/voice/command", api_url))
        .json(&serde_json::json!({
            "text": req.command,
            "source": "hub_phone_proxy"
        }))
        .send()
        .await;

    match result {
        Ok(resp) => {
            let json: serde_json::Value = resp.json().await.unwrap_or_default();
            Ok(Json(json))
        }
        Err(e) => {
            warn!("Failed to forward command: {}", e);
            // Security: Don't leak internal error details in production
            #[cfg(debug_assertions)]
            let error_msg = format!("Failed to reach API: {}", e);
            #[cfg(not(debug_assertions))]
            let error_msg = "Service temporarily unavailable".to_string();
            Err((
                StatusCode::SERVICE_UNAVAILABLE,
                Json(ApiError::new(error_msg, None)),
            ))
        }
    }
}

// ═══════════════════════════════════════════════════════════════════════════
// WebSocket Handler
// ═══════════════════════════════════════════════════════════════════════════

async fn websocket_handler(
    ws: WebSocketUpgrade,
    State(state): State<AppState>,
) -> impl IntoResponse {
    ws.on_upgrade(|socket| handle_websocket(socket, state))
}

async fn handle_websocket(mut socket: WebSocket, state: AppState) {
    info!("📱 Phone connected via WebSocket");

    // Send initial status
    let status = state.status.read().await;
    let initial = serde_json::to_string(&HubEvent {
        event_type: "connected".to_string(),
        data: serde_json::to_value(&*status).unwrap_or_default(),
        timestamp: std::time::SystemTime::now()
            .duration_since(std::time::UNIX_EPOCH)
            .map(|d| d.as_millis() as u64)
            .unwrap_or(0),
    })
    .unwrap_or_default();
    drop(status);

    if socket.send(Message::Text(initial)).await.is_err() {
        return;
    }

    // Subscribe to events
    let mut rx = state.event_tx.subscribe();

    loop {
        tokio::select! {
            // Forward events to phone
            Ok(event) = rx.recv() => {
                let msg = serde_json::to_string(&event).unwrap_or_default();
                if socket.send(Message::Text(msg)).await.is_err() {
                    break;
                }
            }

            // Handle messages from phone
            Some(msg) = socket.recv() => {
                match msg {
                    Ok(Message::Text(text)) => {
                        debug!("📱 Phone message: {}", text);
                        // Handle phone commands via WebSocket
                        if let Ok(cmd) = serde_json::from_str::<serde_json::Value>(&text) {
                            if let Some(cmd_type) = cmd.get("type").and_then(|v| v.as_str()) {
                                match cmd_type {
                                    "ping" => {
                                        let _ = socket.send(Message::Text(r#"{"type":"pong"}"#.to_string())).await;
                                    }
                                    "trigger_listen" => {
                                        let mut status = state.status.write().await;
                                        status.is_listening = true;
                                        #[cfg(feature = "rpi")]
                                        crate::led_ring::show_listening();
                                    }
                                    _ => {}
                                }
                            }
                        }
                    }
                    Ok(Message::Close(_)) => break,
                    Err(_) => break,
                    _ => {}
                }
            }
        }
    }

    info!("📱 Phone disconnected");
}

/*
 * 鏡
 */
