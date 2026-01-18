package main

import (
	"encoding/json"
	"os"
	"path/filepath"
)

// ════════════════════════════════════════════════════════════════════════════════
// CONFIG
// ════════════════════════════════════════════════════════════════════════════════

// Config holds user preferences
type Config struct {
	DefaultProgram     string `json:"default_program"`
	AutoYes            bool   `json:"auto_yes"`
	DaemonPollInterval int    `json:"daemon_poll_interval"`
	KagamiAPIURL       string `json:"kagami_api_url"`
}

// DefaultConfig returns sensible defaults
func DefaultConfig() *Config {
	return &Config{
		DefaultProgram:     "claude",
		AutoYes:            true,
		DaemonPollInterval: 500,
		KagamiAPIURL:       "http://127.0.0.1:8001",
	}
}

// LoadConfig loads config from disk or returns defaults
func LoadConfig() *Config {
	configDir, err := getConfigDir()
	if err != nil {
		return DefaultConfig()
	}

	configFile := filepath.Join(configDir, "config.json")

	data, err := os.ReadFile(configFile)
	if err != nil {
		return DefaultConfig()
	}

	config := DefaultConfig()
	if err := json.Unmarshal(data, config); err != nil {
		return DefaultConfig()
	}

	return config
}

// Save writes config to disk
func (c *Config) Save() error {
	configDir, err := getConfigDir()
	if err != nil {
		return err
	}

	configFile := filepath.Join(configDir, "config.json")

	data, err := json.MarshalIndent(c, "", "  ")
	if err != nil {
		return err
	}

	return os.WriteFile(configFile, data, 0644)
}

// getConfigDir returns the configuration directory
func getConfigDir() (string, error) {
	home, err := os.UserHomeDir()
	if err != nil {
		return "", err
	}

	configDir := filepath.Join(home, ".kagami", "squad")
	if err := os.MkdirAll(configDir, 0755); err != nil {
		return "", err
	}

	return configDir, nil
}
