//! Shared HTTP client for automation engine
//!
//! Centralizes HTTP client management to avoid creating new clients on every request.
//! Uses OnceLock for lazy initialization with connection pooling.
//!
//! Colony: Beacon (e5) - Orchestration and coordination
//!
//! h(x) >= 0 always

use reqwest::Client;
use std::sync::{Arc, OnceLock};
use std::time::Duration;

/// Global shared HTTP client instance
static SHARED_CLIENT: OnceLock<Arc<Client>> = OnceLock::new();

/// Default request timeout in seconds
const DEFAULT_TIMEOUT_SECS: u64 = 30;

/// Default connection timeout in seconds
const DEFAULT_CONNECT_TIMEOUT_SECS: u64 = 10;

/// Maximum idle connections per host
const DEFAULT_POOL_IDLE_PER_HOST: usize = 5;

/// Configuration for the shared HTTP client
#[derive(Debug, Clone)]
pub struct HttpClientConfig {
    /// Request timeout
    pub timeout: Duration,
    /// Connection timeout
    pub connect_timeout: Duration,
    /// Maximum idle connections per host
    pub pool_idle_per_host: usize,
    /// User agent string
    pub user_agent: String,
}

impl Default for HttpClientConfig {
    fn default() -> Self {
        Self {
            timeout: Duration::from_secs(DEFAULT_TIMEOUT_SECS),
            connect_timeout: Duration::from_secs(DEFAULT_CONNECT_TIMEOUT_SECS),
            pool_idle_per_host: DEFAULT_POOL_IDLE_PER_HOST,
            user_agent: format!("kagami-hub/{}", env!("CARGO_PKG_VERSION")),
        }
    }
}

/// Initialize the shared HTTP client with custom configuration.
///
/// This should be called early in application startup if custom configuration is needed.
/// If not called, the client will be lazily initialized with default settings.
///
/// # Arguments
///
/// * `config` - Configuration for the HTTP client
///
/// # Returns
///
/// The initialized client, or the existing client if already initialized.
pub fn init_client(config: HttpClientConfig) -> Arc<Client> {
    SHARED_CLIENT
        .get_or_init(|| {
            let client = Client::builder()
                .timeout(config.timeout)
                .connect_timeout(config.connect_timeout)
                .pool_max_idle_per_host(config.pool_idle_per_host)
                .user_agent(&config.user_agent)
                .build()
                .unwrap_or_else(|e| {
                    tracing::error!("Failed to create HTTP client with custom config: {e}, using default");
                    Client::new()
                });

            Arc::new(client)
        })
        .clone()
}

/// Get the shared HTTP client instance.
///
/// If the client hasn't been initialized yet, it will be created with default settings.
/// This is the primary way to obtain the HTTP client for making requests.
///
/// # Returns
///
/// An Arc-wrapped reqwest::Client that can be cheaply cloned across threads.
///
/// # Example
///
/// ```rust,no_run
/// use kagami_hub::automation::shared_client::get_client;
///
/// async fn make_request() {
///     let client = get_client();
///     let response = client.get("http://example.com").send().await;
/// }
/// ```
pub fn get_client() -> Arc<Client> {
    SHARED_CLIENT
        .get_or_init(|| {
            let config = HttpClientConfig::default();
            let client = Client::builder()
                .timeout(config.timeout)
                .connect_timeout(config.connect_timeout)
                .pool_max_idle_per_host(config.pool_idle_per_host)
                .user_agent(&config.user_agent)
                .build()
                .unwrap_or_else(|e| {
                    tracing::error!("Failed to create HTTP client: {e}, using default");
                    Client::new()
                });

            Arc::new(client)
        })
        .clone()
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_default_config() {
        let config = HttpClientConfig::default();
        assert_eq!(config.timeout, Duration::from_secs(30));
        assert_eq!(config.connect_timeout, Duration::from_secs(10));
        assert_eq!(config.pool_idle_per_host, 5);
        assert!(config.user_agent.starts_with("kagami-hub/"));
    }

    #[test]
    fn test_get_client_returns_same_instance() {
        let client1 = get_client();
        let client2 = get_client();
        // Arc::ptr_eq checks if both Arcs point to the same allocation
        assert!(Arc::ptr_eq(&client1, &client2));
    }
}
