//! Filesystem Commands
//!
//! File search, directory listing, and preview functionality.
//! Colony: Forge (e2)

use serde::{Deserialize, Serialize};
use std::process::Command;
use tracing::debug;

use super::error::CommandError;

#[derive(Debug, Serialize, Deserialize)]
pub struct FileMatch {
    pub path: String,
    pub name: String,
    pub directory: String,
    pub is_dir: bool,
}

/// Sanitize search query to prevent command injection.
/// Only allows alphanumeric characters, dots, dashes, underscores, and spaces.
fn sanitize_search_query(query: &str) -> Result<String, CommandError> {
    // Limit query length
    if query.len() > 256 {
        return Err(CommandError::ValidationError(
            "Search query too long (max 256 characters)".to_string(),
        ));
    }

    // Check for empty query
    if query.trim().is_empty() {
        return Err(CommandError::ValidationError(
            "Search query cannot be empty".to_string(),
        ));
    }

    // Sanitize: only allow safe characters
    let sanitized: String = query
        .chars()
        .filter(|c| c.is_alphanumeric() || *c == '.' || *c == '-' || *c == '_' || *c == ' ')
        .collect();

    if sanitized.is_empty() {
        return Err(CommandError::ValidationError(
            "Search query contains only invalid characters".to_string(),
        ));
    }

    Ok(sanitized)
}

/// Search for files using fd (fast find).
/// Falls back to basic glob if fd not available.
#[tauri::command]
pub async fn search_files(query: String, limit: usize) -> Result<Vec<FileMatch>, String> {
    // Sanitize query to prevent command injection
    let sanitized_query = sanitize_search_query(&query)?;

    // Clamp limit to reasonable bounds
    let safe_limit = limit.clamp(1, 1000);

    debug!(
        "Searching files: {} (limit: {})",
        sanitized_query, safe_limit
    );

    // Try fd first (much faster)
    let output = Command::new("fd")
        .args([
            "--type",
            "f",
            "--max-results",
            &safe_limit.to_string(),
            "--color",
            "never",
            &sanitized_query,
        ])
        .output();

    match output {
        Ok(out) if out.status.success() => {
            let stdout = String::from_utf8_lossy(&out.stdout);
            let matches: Vec<FileMatch> = stdout
                .lines()
                .filter(|l| !l.is_empty())
                .map(|path| {
                    let path_buf = std::path::Path::new(path);
                    FileMatch {
                        path: path.to_string(),
                        name: path_buf
                            .file_name()
                            .map(|n| n.to_string_lossy().to_string())
                            .unwrap_or_default(),
                        directory: path_buf
                            .parent()
                            .map(|p| p.to_string_lossy().to_string())
                            .unwrap_or_default(),
                        is_dir: false,
                    }
                })
                .collect();
            Ok(matches)
        }
        _ => {
            // Fallback: use basic glob in current directory with sanitized query
            let pattern = format!("*{}*", sanitized_query);
            let mut matches = Vec::new();

            if let Ok(entries) = glob::glob(&pattern) {
                for entry in entries.flatten().take(safe_limit) {
                    let path = entry.to_string_lossy().to_string();
                    let is_dir = entry.is_dir();
                    matches.push(FileMatch {
                        name: entry
                            .file_name()
                            .map(|n| n.to_string_lossy().to_string())
                            .unwrap_or_default(),
                        directory: entry
                            .parent()
                            .map(|p| p.to_string_lossy().to_string())
                            .unwrap_or_default(),
                        path,
                        is_dir,
                    });
                }
            }

            Ok(matches)
        }
    }
}

/// Read first N lines of a file for preview.
#[tauri::command]
pub async fn read_file_preview(path: String, lines: usize) -> Result<String, String> {
    debug!("Reading file preview: {} ({} lines)", path, lines);

    use std::fs::File;
    use std::io::{BufRead, BufReader};

    let file = File::open(&path).map_err(|e| format!("Cannot open file: {}", e))?;
    let reader = BufReader::new(file);

    let preview: Vec<String> = reader.lines().take(lines).filter_map(|l| l.ok()).collect();

    Ok(preview.join("\n"))
}

/// List directory contents.
#[tauri::command]
pub async fn list_directory(path: String) -> Result<Vec<FileMatch>, String> {
    debug!("Listing directory: {}", path);

    let entries =
        std::fs::read_dir(&path).map_err(|e| format!("Cannot read directory: {}", e))?;

    let mut matches: Vec<FileMatch> = entries
        .filter_map(|e| e.ok())
        .map(|entry| {
            let path = entry.path();
            FileMatch {
                path: path.to_string_lossy().to_string(),
                name: entry.file_name().to_string_lossy().to_string(),
                directory: path
                    .parent()
                    .map(|p| p.to_string_lossy().to_string())
                    .unwrap_or_default(),
                is_dir: path.is_dir(),
            }
        })
        .collect();

    // Sort: directories first, then by name
    matches.sort_by(|a, b| match (a.is_dir, b.is_dir) {
        (true, false) => std::cmp::Ordering::Less,
        (false, true) => std::cmp::Ordering::Greater,
        _ => a.name.to_lowercase().cmp(&b.name.to_lowercase()),
    });

    Ok(matches)
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_file_match_creation() {
        let file = FileMatch {
            path: "/test/path/file.txt".to_string(),
            name: "file.txt".to_string(),
            directory: "/test/path".to_string(),
            is_dir: false,
        };
        assert_eq!(file.name, "file.txt");
        assert!(!file.is_dir);
    }

    #[test]
    fn test_file_match_directory() {
        let dir = FileMatch {
            path: "/test/path/subdir".to_string(),
            name: "subdir".to_string(),
            directory: "/test/path".to_string(),
            is_dir: true,
        };
        assert!(dir.is_dir);
        assert_eq!(dir.name, "subdir");
    }

    #[test]
    fn test_sanitize_search_query_valid_alphanumeric() {
        let result = sanitize_search_query("test123");
        assert!(result.is_ok());
        assert_eq!(result.unwrap(), "test123");
    }

    #[test]
    fn test_sanitize_search_query_valid_with_dots() {
        let result = sanitize_search_query("file.txt");
        assert!(result.is_ok());
        assert_eq!(result.unwrap(), "file.txt");
    }

    #[test]
    fn test_sanitize_search_query_valid_with_dashes() {
        let result = sanitize_search_query("my-file-name");
        assert!(result.is_ok());
        assert_eq!(result.unwrap(), "my-file-name");
    }

    #[test]
    fn test_sanitize_search_query_valid_with_underscores() {
        let result = sanitize_search_query("my_file_name");
        assert!(result.is_ok());
        assert_eq!(result.unwrap(), "my_file_name");
    }

    #[test]
    fn test_sanitize_search_query_valid_with_spaces() {
        let result = sanitize_search_query("my file name");
        assert!(result.is_ok());
        assert_eq!(result.unwrap(), "my file name");
    }

    #[test]
    fn test_sanitize_search_query_empty() {
        let result = sanitize_search_query("");
        assert!(result.is_err());
        assert!(result.unwrap_err().to_string().contains("empty"));
    }

    #[test]
    fn test_sanitize_search_query_whitespace_only() {
        let result = sanitize_search_query("   ");
        assert!(result.is_err());
        assert!(result.unwrap_err().to_string().contains("empty"));
    }

    #[test]
    fn test_sanitize_search_query_too_long() {
        let long_query = "a".repeat(300);
        let result = sanitize_search_query(&long_query);
        assert!(result.is_err());
        assert!(result.unwrap_err().to_string().contains("too long"));
    }

    #[test]
    fn test_sanitize_search_query_max_length_boundary() {
        // Exactly 256 characters should pass
        let max_query = "a".repeat(256);
        let result = sanitize_search_query(&max_query);
        assert!(result.is_ok());

        // 257 characters should fail
        let over_query = "a".repeat(257);
        let result = sanitize_search_query(&over_query);
        assert!(result.is_err());
    }

    #[test]
    fn test_sanitize_search_query_strips_dangerous_chars() {
        // Semicolon injection attempt
        let result = sanitize_search_query("test; rm -rf /");
        assert!(result.is_ok());
        let sanitized = result.unwrap();
        assert!(!sanitized.contains(';'));
        assert!(!sanitized.contains('/'));
        assert!(sanitized.contains("test"));
    }

    #[test]
    fn test_sanitize_search_query_strips_pipe() {
        let result = sanitize_search_query("file | cat");
        assert!(result.is_ok());
        let sanitized = result.unwrap();
        assert!(!sanitized.contains('|'));
    }

    #[test]
    fn test_sanitize_search_query_strips_dollar() {
        let result = sanitize_search_query("$(whoami)");
        assert!(result.is_ok());
        let sanitized = result.unwrap();
        assert!(!sanitized.contains('$'));
        assert!(!sanitized.contains('('));
        assert!(!sanitized.contains(')'));
    }

    #[test]
    fn test_sanitize_search_query_strips_backticks() {
        let result = sanitize_search_query("`id`");
        assert!(result.is_ok());
        let sanitized = result.unwrap();
        assert!(!sanitized.contains('`'));
    }

    #[test]
    fn test_sanitize_search_query_only_invalid_chars() {
        let result = sanitize_search_query(";;;|||");
        assert!(result.is_err());
        assert!(result.unwrap_err().to_string().contains("invalid characters"));
    }
}
