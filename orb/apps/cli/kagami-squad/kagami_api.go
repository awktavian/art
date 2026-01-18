package main

import (
	"bytes"
	"encoding/json"
	"fmt"
	"net/http"
	"time"
)

// ════════════════════════════════════════════════════════════════════════════════
// KAGAMI API CLIENT — Real-time integration with Kagami ecosystem
// ════════════════════════════════════════════════════════════════════════════════

// KagamiAPI provides low-latency access to the Kagami backend
type KagamiAPI struct {
	BaseURL string
	client  *http.Client
}

// HealthResponse from /health
type HealthResponse struct {
	Status    string  `json:"status"`
	Safety    float64 `json:"safety,omitempty"` // h(x) value
	Uptime    int64   `json:"uptime,omitempty"`
	Services  int     `json:"services,omitempty"`
}

// StatusResponse from /api/status
type StatusResponse struct {
	Safety       float64           `json:"safety"`        // h(x) >= 0
	Mode         string            `json:"mode"`          // active, dormant, etc
	ActiveColony string            `json:"active_colony"` // current primary colony
	Services     map[string]string `json:"services"`      // service -> status
}

// AnnounceRequest for /api/home/announce
type AnnounceRequest struct {
	Text  string   `json:"text"`
	Rooms []string `json:"rooms,omitempty"`
}

// LightsRequest for /api/home/lights
type LightsRequest struct {
	Level int      `json:"level"`
	Rooms []string `json:"rooms,omitempty"`
}

// SessionEvent for /api/squad/event
type SessionEvent struct {
	Event   string `json:"event"`   // created, killed, attached
	Session string `json:"session"` // session name
	Program string `json:"program"` // claude, aider
}

// NewKagamiAPI creates a new API client with optimized timeouts
func NewKagamiAPI(baseURL string) *KagamiAPI {
	return &KagamiAPI{
		BaseURL: baseURL,
		client: &http.Client{
			Timeout: 2 * time.Second, // Fast timeout for responsiveness
			Transport: &http.Transport{
				MaxIdleConns:        10,
				IdleConnTimeout:     30 * time.Second,
				DisableCompression:  true, // Faster for small payloads
			},
		},
	}
}

// ════════════════════════════════════════════════════════════════════════════════
// HEALTH & STATUS
// ════════════════════════════════════════════════════════════════════════════════

// Health checks basic API availability
func (api *KagamiAPI) Health() (*HealthResponse, error) {
	resp, err := api.client.Get(api.BaseURL + "/health")
	if err != nil {
		return nil, fmt.Errorf("connection failed: %w", err)
	}
	defer resp.Body.Close()

	if resp.StatusCode != http.StatusOK {
		return nil, fmt.Errorf("unhealthy: %d", resp.StatusCode)
	}

	var health HealthResponse
	if err := json.NewDecoder(resp.Body).Decode(&health); err != nil {
		// Fallback: just being reachable is enough
		return &HealthResponse{Status: "ok"}, nil
	}

	return &health, nil
}

// IsReachable returns true if API responds
func (api *KagamiAPI) IsReachable() bool {
	_, err := api.Health()
	return err == nil
}

// Status gets detailed ecosystem status
func (api *KagamiAPI) Status() (*StatusResponse, error) {
	resp, err := api.client.Get(api.BaseURL + "/api/status")
	if err != nil {
		return nil, err
	}
	defer resp.Body.Close()

	if resp.StatusCode != http.StatusOK {
		return nil, fmt.Errorf("status unavailable: %d", resp.StatusCode)
	}

	var status StatusResponse
	if err := json.NewDecoder(resp.Body).Decode(&status); err != nil {
		return nil, err
	}

	return &status, nil
}

// ════════════════════════════════════════════════════════════════════════════════
// SMART HOME
// ════════════════════════════════════════════════════════════════════════════════

// Announce sends TTS announcement (fire and forget)
func (api *KagamiAPI) Announce(text string, rooms ...string) error {
	req := AnnounceRequest{Text: text, Rooms: rooms}
	return api.post("/api/home/announce", req)
}

// SetLights sets light level (fire and forget)
func (api *KagamiAPI) SetLights(level int, rooms ...string) error {
	req := LightsRequest{Level: level, Rooms: rooms}
	return api.post("/api/home/lights", req)
}

// ════════════════════════════════════════════════════════════════════════════════
// SQUAD EVENTS
// ════════════════════════════════════════════════════════════════════════════════

// NotifySessionEvent reports session lifecycle events to Kagami
func (api *KagamiAPI) NotifySessionEvent(event, session, program string) {
	// Fire and forget - don't block on this
	go func() {
		_ = api.post("/api/squad/event", SessionEvent{
			Event:   event,
			Session: session,
			Program: program,
		})
	}()
}

// ════════════════════════════════════════════════════════════════════════════════
// HELPERS
// ════════════════════════════════════════════════════════════════════════════════

func (api *KagamiAPI) post(path string, payload interface{}) error {
	body, err := json.Marshal(payload)
	if err != nil {
		return err
	}

	resp, err := api.client.Post(
		api.BaseURL+path,
		"application/json",
		bytes.NewReader(body),
	)
	if err != nil {
		return nil // Fail silently - these are optional enhancements
	}
	defer resp.Body.Close()

	return nil
}
