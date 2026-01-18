//! HTML Agent Support — Distributed Cognitive Substrate
//!
//! Loads, manages, and displays HTML agents from the Kagami agent directory.
//! Agents are high-craft HTML files that participate in Byzantine consensus.
//!
//! Architecture:
//!   ~/.kagami/agents/*.html  →  Tauri Window  →  PBFT Consensus
//!
//! Colony: Grove (Scholar) — Documentation and research
//! h(x) >= 0. Always.

use serde::{Deserialize, Serialize};
use std::fs;
use std::path::PathBuf;
use tauri::{command, AppHandle, Manager, WebviewUrl, WebviewWindowBuilder};
use tracing::{debug, info, warn};

/// Agent metadata extracted from HTML meta tags
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct AgentMetadata {
    /// Agent identifier (filename without .html)
    pub id: String,
    /// Display name from title tag
    pub name: String,
    /// Description from meta description
    pub description: Option<String>,
    /// Colony assignment
    pub colony: Option<String>,
    /// Capabilities (comma-separated)
    pub capabilities: Vec<String>,
    /// Consensus weight
    pub consensus_weight: u32,
    /// Version string
    pub version: Option<String>,
    /// File path
    pub path: PathBuf,
    /// Last modified timestamp
    pub modified: Option<u64>,
}

/// Result of listing agents
#[derive(Debug, Serialize, Deserialize)]
pub struct AgentListResult {
    pub agents: Vec<AgentMetadata>,
    pub count: usize,
    pub directory: String,
}

/// Get the agents directory path
fn get_agents_dir() -> PathBuf {
    let home = dirs::home_dir().unwrap_or_else(|| PathBuf::from("."));
    home.join(".kagami").join("agents")
}

/// Parse agent metadata from HTML content
fn parse_agent_metadata(id: &str, content: &str, path: PathBuf) -> AgentMetadata {
    // Extract title
    let name = extract_tag_content(content, "title")
        .unwrap_or_else(|| id.to_string());

    // Extract meta tags
    let description = extract_meta_content(content, "description");
    let colony = extract_meta_content(content, "kagami:colony");
    let version = extract_meta_content(content, "kagami:version");

    // Parse capabilities
    let capabilities_str = extract_meta_content(content, "kagami:capabilities")
        .unwrap_or_default();
    let capabilities: Vec<String> = capabilities_str
        .split(',')
        .map(|s| s.trim().to_string())
        .filter(|s| !s.is_empty())
        .collect();

    // Parse consensus weight
    let consensus_weight: u32 = extract_meta_content(content, "kagami:consensus-weight")
        .and_then(|s| s.parse().ok())
        .unwrap_or(1);

    // Get file modification time
    let modified = fs::metadata(&path)
        .and_then(|m| m.modified())
        .ok()
        .and_then(|t| t.duration_since(std::time::UNIX_EPOCH).ok())
        .map(|d| d.as_secs());

    AgentMetadata {
        id: id.to_string(),
        name,
        description,
        colony,
        capabilities,
        consensus_weight,
        version,
        path,
        modified,
    }
}

/// Extract content from an HTML tag (e.g., <title>...</title>)
fn extract_tag_content(html: &str, tag: &str) -> Option<String> {
    let open_tag = format!("<{}", tag);
    let close_tag = format!("</{}>", tag);

    let start = html.find(&open_tag)?;
    let content_start = html[start..].find('>')? + start + 1;
    let end = html[content_start..].find(&close_tag)? + content_start;

    Some(html[content_start..end].trim().to_string())
}

/// Extract content from a meta tag
fn extract_meta_content(html: &str, name: &str) -> Option<String> {
    // Look for <meta name="..." content="...">
    let pattern = format!(r#"name="{}""#, name);

    // Find the meta tag
    let pos = html.find(&pattern)?;

    // Find the start of this meta tag
    let tag_start = html[..pos].rfind('<')?;

    // Find the end of this meta tag
    let tag_end = html[pos..].find('>')? + pos;

    // Extract the tag content
    let tag = &html[tag_start..=tag_end];

    // Find content attribute
    let content_start = tag.find(r#"content=""#)? + 9;
    let content_end = tag[content_start..].find('"')? + content_start;

    Some(tag[content_start..content_end].to_string())
}

/// List all available HTML agents
#[command]
pub async fn list_agents() -> Result<AgentListResult, String> {
    let agents_dir = get_agents_dir();

    debug!("Listing agents from: {:?}", agents_dir);

    if !agents_dir.exists() {
        // Create directory if it doesn't exist
        fs::create_dir_all(&agents_dir)
            .map_err(|e| format!("Failed to create agents directory: {}", e))?;

        info!("Created agents directory: {:?}", agents_dir);

        return Ok(AgentListResult {
            agents: vec![],
            count: 0,
            directory: agents_dir.display().to_string(),
        });
    }

    let mut agents = Vec::new();

    // Read directory entries
    let entries = fs::read_dir(&agents_dir)
        .map_err(|e| format!("Failed to read agents directory: {}", e))?;

    for entry in entries.flatten() {
        let path = entry.path();

        // Only process .html files
        if path.extension().and_then(|s| s.to_str()) != Some("html") {
            continue;
        }

        // Check for kagami:agent meta tag
        let content = match fs::read_to_string(&path) {
            Ok(c) => c,
            Err(e) => {
                warn!("Failed to read agent file {:?}: {}", path, e);
                continue;
            }
        };

        // Skip files that aren't Kagami agents
        if !content.contains(r#"kagami:agent"#) {
            debug!("Skipping non-agent file: {:?}", path);
            continue;
        }

        // Extract ID from filename
        let id = path
            .file_stem()
            .and_then(|s| s.to_str())
            .unwrap_or("unknown")
            .to_string();

        let metadata = parse_agent_metadata(&id, &content, path);
        agents.push(metadata);
    }

    // Sort by name
    agents.sort_by(|a, b| a.name.cmp(&b.name));

    let count = agents.len();
    info!("Found {} HTML agents", count);

    Ok(AgentListResult {
        agents,
        count,
        directory: agents_dir.display().to_string(),
    })
}

/// Get metadata for a specific agent
#[command]
pub async fn get_agent(agent_id: String) -> Result<AgentMetadata, String> {
    let agents_dir = get_agents_dir();
    let path = agents_dir.join(format!("{}.html", agent_id));

    if !path.exists() {
        return Err(format!("Agent not found: {}", agent_id));
    }

    let content = fs::read_to_string(&path)
        .map_err(|e| format!("Failed to read agent: {}", e))?;

    Ok(parse_agent_metadata(&agent_id, &content, path))
}

/// Open an agent in a new window
#[command]
pub async fn open_agent(handle: AppHandle, agent_id: String) -> Result<String, String> {
    let agents_dir = get_agents_dir();
    let path = agents_dir.join(format!("{}.html", agent_id));

    if !path.exists() {
        return Err(format!("Agent not found: {}", agent_id));
    }

    // Read agent to get metadata for window config
    let content = fs::read_to_string(&path)
        .map_err(|e| format!("Failed to read agent: {}", e))?;

    let metadata = parse_agent_metadata(&agent_id, &content, path.clone());

    // Check if window already exists
    let window_label = format!("agent-{}", agent_id);
    if let Some(window) = handle.get_webview_window(&window_label) {
        // Focus existing window
        window.set_focus().ok();
        return Ok(format!("Focused existing window: {}", window_label));
    }

    // Convert path to file:// URL
    let url = format!("file://{}", path.display());

    // Create new window
    let _window = WebviewWindowBuilder::new(
        &handle,
        &window_label,
        WebviewUrl::External(url.parse().map_err(|e| format!("Invalid URL: {}", e))?),
    )
    .title(&metadata.name)
    .inner_size(1024.0, 768.0)
    .min_inner_size(400.0, 300.0)
    .resizable(true)
    .build()
    .map_err(|e| format!("Failed to create agent window: {}", e))?;

    info!("Opened agent window: {} -> {}", agent_id, window_label);

    Ok(window_label)
}

/// Close an agent window
#[command]
pub async fn close_agent(handle: AppHandle, agent_id: String) -> Result<(), String> {
    let window_label = format!("agent-{}", agent_id);

    if let Some(window) = handle.get_webview_window(&window_label) {
        window.close()
            .map_err(|e| format!("Failed to close window: {}", e))?;
        info!("Closed agent window: {}", window_label);
    }

    Ok(())
}

/// Get the agents directory path (for opening in file manager)
#[command]
pub async fn get_agents_directory() -> String {
    get_agents_dir().display().to_string()
}

/// Install a default set of agents
#[command]
pub async fn install_default_agents() -> Result<usize, String> {
    let agents_dir = get_agents_dir();

    // Create directory if needed
    fs::create_dir_all(&agents_dir)
        .map_err(|e| format!("Failed to create agents directory: {}", e))?;

    // Default agents to install (these would be bundled with the app in production)
    // For now, we just ensure the directory exists
    info!("Default agents directory ready: {:?}", agents_dir);

    Ok(0) // Number of agents installed
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_extract_tag_content() {
        let html = "<html><title>Test Agent</title></html>";
        assert_eq!(extract_tag_content(html, "title"), Some("Test Agent".to_string()));
    }

    #[test]
    fn test_extract_meta_content() {
        let html = r#"<meta name="description" content="A test description">"#;
        assert_eq!(extract_meta_content(html, "description"), Some("A test description".to_string()));
    }

    #[test]
    fn test_extract_kagami_meta() {
        let html = r#"
            <meta name="kagami:agent" content="true">
            <meta name="kagami:colony" content="grove">
            <meta name="kagami:capabilities" content="display,audit">
        "#;

        assert_eq!(extract_meta_content(html, "kagami:colony"), Some("grove".to_string()));
        assert_eq!(extract_meta_content(html, "kagami:capabilities"), Some("display,audit".to_string()));
    }
}
