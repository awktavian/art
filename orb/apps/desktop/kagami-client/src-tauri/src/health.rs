//! Health Data Module for Kagami Client
//!
//! Colony: Nexus (e₄) — Integration
//!
//! This module handles health data from platform-specific APIs:
//! - **macOS**: No native health API (relies on iPhone/Watch sync)
//! - **iOS**: HealthKit
//! - **Android**: Health Connect
//!
//! Health data is synced to Kagami API at /home/health/ingest
//!
//! Created: December 30, 2025
//! 鏡

use serde::{Deserialize, Serialize};
use std::sync::Arc;
use tokio::sync::Mutex;

/// Health metrics from any platform
#[derive(Debug, Clone, Serialize, Deserialize, Default)]
pub struct HealthMetrics {
    pub heart_rate: Option<f64>,
    pub resting_heart_rate: Option<f64>,
    pub hrv: Option<f64>,
    pub steps: Option<i32>,
    pub active_calories: Option<i32>,
    pub exercise_minutes: Option<i32>,
    pub blood_oxygen: Option<f64>,
    pub sleep_hours: Option<f64>,
}

/// Health data ingest payload
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct HealthIngestPayload {
    pub source: String,
    pub device: String,
    pub timestamp: String,
    pub metrics: HealthMetrics,
}

/// Health service state
#[derive(Default)]
pub struct HealthState {
    pub metrics: HealthMetrics,
    pub last_sync: Option<String>,
    pub authorized: bool,
}

/// Shared health service
pub type SharedHealthState = Arc<Mutex<HealthState>>;

/// Create a new shared health state
pub fn create_health_state() -> SharedHealthState {
    Arc::new(Mutex::new(HealthState::default()))
}

/// Sync health data to Kagami API
pub async fn sync_to_kagami(
    api_base: &str,
    payload: &HealthIngestPayload,
) -> Result<(), Box<dyn std::error::Error + Send + Sync>> {
    let client = reqwest::Client::new();
    let url = format!("{}/home/health/ingest", api_base);

    let response = client
        .post(&url)
        .json(payload)
        .timeout(std::time::Duration::from_secs(10))
        .send()
        .await?;

    if response.status().is_success() {
        tracing::info!("✅ Health data synced to Kagami");
        Ok(())
    } else {
        let status = response.status();
        let body = response.text().await.unwrap_or_default();
        Err(format!("Health sync failed: {} - {}", status, body).into())
    }
}

/// Fetch current health status from Kagami API
pub async fn fetch_from_kagami(
    api_base: &str,
) -> Result<HealthMetrics, Box<dyn std::error::Error + Send + Sync>> {
    let client = reqwest::Client::new();
    let url = format!("{}/home/health/status", api_base);

    let response = client
        .get(&url)
        .timeout(std::time::Duration::from_secs(10))
        .send()
        .await?;

    if response.status().is_success() {
        let data: serde_json::Value = response.json().await?;

        // Extract metrics from apple_health if available
        let metrics = if let Some(ah) = data.get("apple_health") {
            HealthMetrics {
                heart_rate: ah.get("heart_rate").and_then(|v| v.as_f64()),
                resting_heart_rate: ah.get("resting_heart_rate").and_then(|v| v.as_f64()),
                hrv: ah.get("hrv").and_then(|v| v.as_f64()),
                steps: ah.get("steps").and_then(|v| v.as_i64().map(|x| x as i32)),
                active_calories: ah.get("active_calories").and_then(|v| v.as_i64().map(|x| x as i32)),
                exercise_minutes: ah.get("exercise_minutes").and_then(|v| v.as_i64().map(|x| x as i32)),
                blood_oxygen: ah.get("blood_oxygen").and_then(|v| v.as_f64()),
                sleep_hours: ah.get("sleep_hours").and_then(|v| v.as_f64()),
            }
        } else {
            HealthMetrics::default()
        };

        tracing::debug!("✅ Health data fetched from Kagami");
        Ok(metrics)
    } else {
        let status = response.status();
        Err(format!("Health fetch failed: {}", status).into())
    }
}

// ============================================================================
// PLATFORM-SPECIFIC IMPLEMENTATIONS
// ============================================================================

/// Platform detection for health capabilities
#[derive(Debug, Clone, Copy, PartialEq)]
pub enum HealthPlatform {
    MacOS,    // No native health API
    IOS,      // HealthKit
    Android,  // Health Connect
    Windows,  // No native health API
    Linux,    // No native health API
}

impl HealthPlatform {
    pub fn current() -> Self {
        #[cfg(target_os = "macos")]
        return HealthPlatform::MacOS;

        #[cfg(target_os = "ios")]
        return HealthPlatform::IOS;

        #[cfg(target_os = "android")]
        return HealthPlatform::Android;

        #[cfg(target_os = "windows")]
        return HealthPlatform::Windows;

        #[cfg(target_os = "linux")]
        return HealthPlatform::Linux;
    }

    pub fn has_native_health_api(&self) -> bool {
        matches!(self, HealthPlatform::IOS | HealthPlatform::Android)
    }

    pub fn api_name(&self) -> &'static str {
        match self {
            HealthPlatform::IOS => "HealthKit",
            HealthPlatform::Android => "Health Connect",
            _ => "None",
        }
    }
}

// ============================================================================
// TAURI COMMANDS
// ============================================================================

/// Check if health API is available on this platform
#[tauri::command]
pub fn health_available() -> bool {
    HealthPlatform::current().has_native_health_api()
}

/// Get current platform's health API name
#[tauri::command]
pub fn health_platform_name() -> String {
    HealthPlatform::current().api_name().to_string()
}

/// Get current health metrics (from cached state)
#[tauri::command]
pub async fn get_health_metrics(state: tauri::State<'_, SharedHealthState>) -> Result<HealthMetrics, String> {
    let state = state.lock().await;
    Ok(state.metrics.clone())
}

/// Check if health is authorized
#[tauri::command]
pub async fn is_health_authorized(state: tauri::State<'_, SharedHealthState>) -> Result<bool, String> {
    let state = state.lock().await;
    Ok(state.authorized)
}

/// Get health API endpoints from environment or use defaults
fn get_health_endpoints() -> Vec<String> {
    if let Ok(url) = std::env::var("KAGAMI_API_URL") {
        vec![url]
    } else {
        vec![
            "https://api.awkronos.com".to_string(),
            "http://localhost:8001".to_string(),
            "http://kagami.local:8001".to_string(),
        ]
    }
}

/// Manual sync trigger (for desktop platforms that receive data from phone)
#[tauri::command]
pub async fn sync_health_data(
    state: tauri::State<'_, SharedHealthState>,
    metrics: HealthMetrics,
) -> Result<(), String> {
    // Update local state
    {
        let mut state = state.lock().await;
        state.metrics = metrics.clone();
        state.last_sync = Some(chrono::Utc::now().to_rfc3339());
    }

    // Sync to Kagami API - try configured endpoints
    let endpoints = get_health_endpoints();

    let payload = HealthIngestPayload {
        source: HealthPlatform::current().api_name().to_string(),
        device: "desktop".to_string(),
        timestamp: chrono::Utc::now().to_rfc3339(),
        metrics,
    };

    for endpoint in &endpoints {
        match sync_to_kagami(endpoint, &payload).await {
            Ok(_) => return Ok(()),
            Err(e) => tracing::debug!("Failed to sync to {}: {}", endpoint, e),
        }
    }

    Err("Failed to sync health data to any Kagami endpoint".to_string())
}

/// Fetch health data from Kagami API (aggregated from all sources)
#[tauri::command]
pub async fn fetch_health_status(
    state: tauri::State<'_, SharedHealthState>,
) -> Result<HealthMetrics, String> {
    // Try configured endpoints
    let endpoints = get_health_endpoints();

    for endpoint in &endpoints {
        match fetch_from_kagami(endpoint).await {
            Ok(metrics) => {
                // Update local state
                {
                    let mut state = state.lock().await;
                    state.metrics = metrics.clone();
                    state.last_sync = Some(chrono::Utc::now().to_rfc3339());
                }
                return Ok(metrics);
            }
            Err(e) => tracing::debug!("Failed to fetch from {}: {}", endpoint, e),
        }
    }

    // Return cached data if API is unavailable
    let state = state.lock().await;
    Ok(state.metrics.clone())
}

/*
 * 鏡
 * h(x) ≥ 0. Always.
 */
