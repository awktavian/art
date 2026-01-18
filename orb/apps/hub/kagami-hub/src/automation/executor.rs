//! Automation Executor
//!
//! Executes automation actions including device control, scene activation,
//! and API calls. Uses shared HTTP client for connection pooling.
//!
//! Colony: Beacon (e5) - Orchestration and coordination
//!
//! h(x) >= 0 always

use anyhow::{Context, Result};
use reqwest::Client;
use std::collections::HashMap;
use std::sync::Arc;
use std::time::Duration;
use tracing::{debug, info, warn};

use super::rule_engine::{
    Action, AnnouncementAction, ApiCallAction, DeviceControlAction, DelayAction, SceneAction,
};
use super::shared_client::get_client;

// ============================================================================
// Executor
// ============================================================================

/// Executes automation actions against the API
pub struct ActionExecutor {
    /// HTTP client (shared via Arc)
    client: Arc<Client>,
    /// Base API URL
    api_url: String,
}

impl ActionExecutor {
    /// Create a new executor with the shared HTTP client
    pub fn new(api_url: &str) -> Self {
        Self {
            client: get_client(),
            api_url: api_url.to_string(),
        }
    }

    /// Create a new executor with a custom client (for testing or special configurations)
    pub fn with_client(client: Arc<Client>, api_url: &str) -> Self {
        Self {
            client,
            api_url: api_url.to_string(),
        }
    }

    /// Execute a single action
    pub async fn execute(&self, action: &Action) -> Result<()> {
        match action {
            Action::DeviceControl(dc) => self.execute_device_control(dc).await,
            Action::Scene(sa) => self.execute_scene(sa).await,
            Action::Announcement(aa) => self.execute_announcement(aa).await,
            Action::Delay(da) => self.execute_delay(da).await,
            Action::ApiCall(ac) => self.execute_api_call(ac).await,
            Action::GroupControl(gc) => self.execute_group_control(gc).await,
            Action::RunAutomation(_) => {
                // RunAutomation should be handled by the engine, not the executor
                warn!("RunAutomation should be handled by AutomationEngine");
                Ok(())
            }
            Action::Notification(_) | Action::Script(_) => {
                warn!("Action type not yet implemented");
                Ok(())
            }
        }
    }

    /// Execute device control action
    async fn execute_device_control(&self, action: &DeviceControlAction) -> Result<()> {
        info!("Controlling device {}: {}", action.device_id, action.service);
        let url = format!("{}/device/{}/{}", self.api_url, action.device_id, action.service);

        let response = self
            .client
            .post(&url)
            .json(&action.params)
            .send()
            .await
            .context("Device control request failed")?;

        if !response.status().is_success() {
            let status = response.status();
            let body = response.text().await.unwrap_or_default();
            return Err(anyhow::anyhow!(
                "Device control failed: {} - {}",
                status,
                body
            ));
        }

        debug!("Device {} controlled successfully", action.device_id);
        Ok(())
    }

    /// Execute group control action
    async fn execute_group_control(
        &self,
        action: &super::rule_engine::GroupControlAction,
    ) -> Result<()> {
        info!("Controlling group {}: {}", action.group_id, action.service);
        let url = format!("{}/group/{}/{}", self.api_url, action.group_id, action.service);

        let response = self
            .client
            .post(&url)
            .json(&action.params)
            .send()
            .await
            .context("Group control request failed")?;

        if !response.status().is_success() {
            let status = response.status();
            let body = response.text().await.unwrap_or_default();
            return Err(anyhow::anyhow!(
                "Group control failed: {} - {}",
                status,
                body
            ));
        }

        debug!("Group {} controlled successfully", action.group_id);
        Ok(())
    }

    /// Execute scene activation
    async fn execute_scene(&self, action: &SceneAction) -> Result<()> {
        info!("Activating scene: {}", action.name);
        let url = format!("{}/scene/activate", self.api_url);

        let mut body = HashMap::new();
        body.insert("name".to_string(), serde_json::Value::String(action.name.clone()));
        if let Some(t) = action.transition {
            body.insert("transition".to_string(), serde_json::json!(t));
        }

        let response = self
            .client
            .post(&url)
            .json(&body)
            .send()
            .await
            .context("Scene activation request failed")?;

        if !response.status().is_success() {
            let status = response.status();
            let body = response.text().await.unwrap_or_default();
            return Err(anyhow::anyhow!(
                "Scene activation failed: {} - {}",
                status,
                body
            ));
        }

        debug!("Scene {} activated successfully", action.name);
        Ok(())
    }

    /// Execute announcement action
    async fn execute_announcement(&self, action: &AnnouncementAction) -> Result<()> {
        info!("Making announcement: {}", action.message);
        let url = format!("{}/announce", self.api_url);

        let response = self
            .client
            .post(&url)
            .json(&serde_json::json!({
                "message": action.message,
                "rooms": action.rooms,
                "volume": action.volume
            }))
            .send()
            .await
            .context("Announcement request failed")?;

        if !response.status().is_success() {
            let status = response.status();
            let body = response.text().await.unwrap_or_default();
            return Err(anyhow::anyhow!(
                "Announcement failed: {} - {}",
                status,
                body
            ));
        }

        debug!("Announcement made successfully");
        Ok(())
    }

    /// Execute delay action
    async fn execute_delay(&self, action: &DelayAction) -> Result<()> {
        debug!("Delaying {} seconds", action.seconds);
        tokio::time::sleep(Duration::from_secs(action.seconds as u64)).await;
        Ok(())
    }

    /// Execute API call action
    async fn execute_api_call(&self, action: &ApiCallAction) -> Result<()> {
        info!("Calling API: {} {}", action.method, action.url);

        let mut req = match action.method.to_uppercase().as_str() {
            "GET" => self.client.get(&action.url),
            "POST" => self.client.post(&action.url),
            "PUT" => self.client.put(&action.url),
            "DELETE" => self.client.delete(&action.url),
            "PATCH" => self.client.patch(&action.url),
            _ => return Err(anyhow::anyhow!("Unknown HTTP method: {}", action.method)),
        };

        for (key, value) in &action.headers {
            req = req.header(key, value);
        }

        if let Some(ref body) = action.body {
            req = req.json(body);
        }

        let response = req.send().await.context("API call failed")?;

        if !response.status().is_success() {
            let status = response.status();
            let body = response.text().await.unwrap_or_default();
            return Err(anyhow::anyhow!("API call failed: {} - {}", status, body));
        }

        debug!("API call completed successfully");
        Ok(())
    }

    /// Control all devices in a list in parallel
    ///
    /// Returns Ok if all devices were controlled successfully,
    /// or an error with the count of failed devices.
    pub async fn control_devices_parallel(
        &self,
        device_ids: &[String],
        service: &str,
        params: &HashMap<String, serde_json::Value>,
    ) -> Result<()> {
        info!("Controlling {} devices in parallel: {}", device_ids.len(), service);

        let mut handles = vec![];

        for device_id in device_ids {
            let client = self.client.clone();
            let url = format!("{}/device/{}/{}", self.api_url, device_id, service);
            let params = params.clone();
            let device_id = device_id.clone();

            handles.push(tokio::spawn(async move {
                match client.post(&url).json(&params).send().await {
                    Ok(resp) if resp.status().is_success() => {
                        debug!("Device {} controlled successfully", device_id);
                        Ok(())
                    }
                    Ok(resp) => {
                        warn!("Device {} control failed: {}", device_id, resp.status());
                        Err(anyhow::anyhow!("Control failed: {}", resp.status()))
                    }
                    Err(e) => {
                        warn!("Device {} control error: {}", device_id, e);
                        Err(anyhow::anyhow!("Control error: {}", e))
                    }
                }
            }));
        }

        // Wait for all to complete
        let results: Vec<_> = futures_util::future::join_all(handles).await;
        let errors: Vec<_> = results
            .into_iter()
            .filter_map(|r| r.ok().and_then(|r| r.err()))
            .collect();

        if errors.is_empty() {
            Ok(())
        } else {
            Err(anyhow::anyhow!("{} devices failed", errors.len()))
        }
    }
}

// ============================================================================
// Tests
// ============================================================================

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_executor_creation() {
        let executor = ActionExecutor::new("http://localhost:8000");
        assert_eq!(executor.api_url, "http://localhost:8000");
    }

    #[test]
    fn test_executor_with_custom_client() {
        let client = Arc::new(Client::new());
        let executor = ActionExecutor::with_client(client.clone(), "http://localhost:8000");
        assert_eq!(executor.api_url, "http://localhost:8000");
    }

    #[tokio::test]
    async fn test_delay_action() {
        let executor = ActionExecutor::new("http://localhost:8000");
        let delay = DelayAction { seconds: 1 };

        let start = std::time::Instant::now();
        executor.execute_delay(&delay).await.unwrap();
        let elapsed = start.elapsed();

        assert!(elapsed >= Duration::from_secs(1));
        assert!(elapsed < Duration::from_secs(2));
    }
}
