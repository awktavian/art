//! Intelligent Caching Layer
//!
//! High-performance cache for API responses with:
//! - TTL-based expiration
//! - Size-based eviction (LRU)
//! - Cache warming for frequently accessed data
//!
//! Colony: Crystal (e₇) — Verification, efficiency

use moka::future::Cache;
use std::sync::Arc;
use std::time::Duration;
use tokio::sync::RwLock;
use tracing::{debug, info};

/// Cache entry metadata
#[derive(Debug, Clone)]
pub struct CacheEntry<T> {
    pub data: T,
    pub cached_at: std::time::Instant,
    pub hits: u64,
}

/// Cache configuration
#[derive(Debug, Clone)]
pub struct CacheConfig {
    /// Maximum number of entries
    pub max_entries: u64,
    /// Time-to-live for entries
    pub ttl: Duration,
    /// Time-to-idle (evict if not accessed)
    pub tti: Duration,
}

impl Default for CacheConfig {
    fn default() -> Self {
        Self {
            max_entries: 1000,
            ttl: Duration::from_secs(30),
            tti: Duration::from_secs(60),
        }
    }
}

/// High-performance cache for API responses
pub struct ApiCache {
    /// General purpose cache
    general: Cache<String, serde_json::Value>,
    /// Home state cache (longer TTL)
    home: Cache<String, serde_json::Value>,
    /// Colony state cache (short TTL)
    colonies: Cache<String, serde_json::Value>,
    /// Hit statistics
    stats: Arc<RwLock<CacheStats>>,
}

#[derive(Debug, Clone, Default, serde::Serialize)]
pub struct CacheStats {
    pub hits: u64,
    pub misses: u64,
    pub evictions: u64,
}

impl CacheStats {
    pub fn hit_rate(&self) -> f64 {
        let total = self.hits + self.misses;
        if total == 0 {
            0.0
        } else {
            self.hits as f64 / total as f64
        }
    }
}

impl ApiCache {
    pub fn new() -> Self {
        // General cache: 30s TTL, 1min idle
        let general = Cache::builder()
            .max_capacity(1000)
            .time_to_live(Duration::from_secs(30))
            .time_to_idle(Duration::from_secs(60))
            .build();

        // Home state: 5min TTL (state changes less frequently)
        let home = Cache::builder()
            .max_capacity(100)
            .time_to_live(Duration::from_secs(300))
            .time_to_idle(Duration::from_secs(600))
            .build();

        // Colony state: 5s TTL (changes frequently)
        let colonies = Cache::builder()
            .max_capacity(100)
            .time_to_live(Duration::from_secs(5))
            .time_to_idle(Duration::from_secs(10))
            .build();

        Self {
            general,
            home,
            colonies,
            stats: Arc::new(RwLock::new(CacheStats::default())),
        }
    }

    /// Get from general cache
    pub async fn get(&self, key: &str) -> Option<serde_json::Value> {
        let result = self.general.get(key).await;

        let mut stats = self.stats.write().await;
        if result.is_some() {
            stats.hits += 1;
            debug!("Cache hit: {}", key);
        } else {
            stats.misses += 1;
            debug!("Cache miss: {}", key);
        }

        result
    }

    /// Set in general cache
    pub async fn set(&self, key: &str, value: serde_json::Value) {
        self.general.insert(key.to_string(), value).await;
    }

    /// Get from home cache
    pub async fn get_home(&self, key: &str) -> Option<serde_json::Value> {
        let result = self.home.get(key).await;

        let mut stats = self.stats.write().await;
        if result.is_some() {
            stats.hits += 1;
        } else {
            stats.misses += 1;
        }

        result
    }

    /// Set in home cache
    pub async fn set_home(&self, key: &str, value: serde_json::Value) {
        self.home.insert(key.to_string(), value).await;
    }

    /// Get from colony cache
    pub async fn get_colony(&self, key: &str) -> Option<serde_json::Value> {
        let result = self.colonies.get(key).await;

        let mut stats = self.stats.write().await;
        if result.is_some() {
            stats.hits += 1;
        } else {
            stats.misses += 1;
        }

        result
    }

    /// Set in colony cache
    pub async fn set_colony(&self, key: &str, value: serde_json::Value) {
        self.colonies.insert(key.to_string(), value).await;
    }

    /// Get cache statistics
    pub async fn stats(&self) -> CacheStats {
        self.stats.read().await.clone()
    }

    /// Clear all caches
    pub async fn clear(&self) {
        self.general.invalidate_all();
        self.home.invalidate_all();
        self.colonies.invalidate_all();

        let mut stats = self.stats.write().await;
        stats.evictions += 1;

        info!("Cache cleared");
    }

    /// Warm cache with frequently accessed data
    pub async fn warm(&self, api: &crate::api_client::KagamiApi) {
        info!("Warming cache...");

        // Pre-fetch home status
        if let Ok(status) = api.home_status().await {
            self.set_home("home_status", serde_json::to_value(&status).unwrap_or_default()).await;
        }

        // Pre-fetch health
        if let Ok(health) = api.health().await {
            self.set("health", serde_json::to_value(&health).unwrap_or_default()).await;
        }

        info!("Cache warmed");
    }
}

// Global cache instance
static CACHE: std::sync::OnceLock<ApiCache> = std::sync::OnceLock::new();

pub fn get_cache() -> &'static ApiCache {
    CACHE.get_or_init(ApiCache::new)
}

/// Tauri command to get cache stats
#[tauri::command]
pub async fn get_cache_stats() -> Result<CacheStats, String> {
    Ok(get_cache().stats().await)
}

/// Tauri command to clear cache
#[tauri::command]
pub async fn clear_cache() -> Result<(), String> {
    get_cache().clear().await;
    Ok(())
}

/*
 * 鏡
 * Cache is memory. Memory is speed.
 */
