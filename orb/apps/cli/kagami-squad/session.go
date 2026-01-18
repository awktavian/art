package main

import (
	"encoding/json"
	"fmt"
	"os"
	"os/exec"
	"path/filepath"
	"strings"
	"time"
)

// ════════════════════════════════════════════════════════════════════════════════
// SESSION
// ════════════════════════════════════════════════════════════════════════════════

// Session represents a running agent instance
type Session struct {
	Name     string    `json:"name"`
	Branch   string    `json:"branch"`
	Worktree string    `json:"worktree"`
	TmuxName string    `json:"tmux_name"`
	Program  string    `json:"program"`
	Status   string    `json:"status"`
	AutoYes  bool      `json:"auto_yes"`
	Created  time.Time `json:"created"`
	Updated  time.Time `json:"updated"`
}

// Storage manages session persistence
type Storage struct {
	configDir    string
	sessionsFile string
}

// ════════════════════════════════════════════════════════════════════════════════
// STORAGE
// ════════════════════════════════════════════════════════════════════════════════

func newStorage() *Storage {
	configDir, _ := getConfigDir()
	return &Storage{
		configDir:    configDir,
		sessionsFile: filepath.Join(configDir, "sessions.json"),
	}
}

func (s *Storage) list() []*Session {
	sessions := []*Session{}

	data, err := os.ReadFile(s.sessionsFile)
	if err != nil {
		return sessions
	}

	if err := json.Unmarshal(data, &sessions); err != nil {
		return sessions
	}

	// Update status from tmux
	for _, session := range sessions {
		if tmuxSessionExists(session.TmuxName) {
			session.Status = "running"
		} else {
			session.Status = "stopped"
		}
	}

	return sessions
}

func (s *Storage) save(sessions []*Session) error {
	data, err := json.MarshalIndent(sessions, "", "  ")
	if err != nil {
		return err
	}
	return os.WriteFile(s.sessionsFile, data, 0644)
}

func (s *Storage) add(session *Session) error {
	sessions := s.list()
	sessions = append(sessions, session)
	return s.save(sessions)
}

func (s *Storage) remove(name string) error {
	sessions := s.list()
	filtered := []*Session{}
	for _, session := range sessions {
		if session.Name != name {
			filtered = append(filtered, session)
		}
	}
	return s.save(filtered)
}

// ════════════════════════════════════════════════════════════════════════════════
// SESSION MANAGEMENT
// ════════════════════════════════════════════════════════════════════════════════

func createSession(name, program string) error {
	if name == "" {
		name = fmt.Sprintf("session-%d", time.Now().Unix())
	}

	// Normalize
	name = strings.TrimSpace(name)
	name = strings.ReplaceAll(name, " ", "-")
	name = strings.ToLower(name)

	storage := newStorage()
	for _, s := range storage.list() {
		if s.Name == name {
			return fmt.Errorf("session '%s' already exists", name)
		}
	}

	currentDir, err := os.Getwd()
	if err != nil {
		return err
	}

	repoRoot, err := getRepoRoot(currentDir)
	if err != nil {
		return fmt.Errorf("not in a git repository: %w", err)
	}

	branchName := "ks/" + name
	worktreePath := filepath.Join(repoRoot, ".worktrees", name)

	if err := os.MkdirAll(filepath.Dir(worktreePath), 0755); err != nil {
		return err
	}

	// Create branch if needed
	_ = createGitBranch(repoRoot, branchName)

	// Create worktree (can be slow for large repos)
	fmt.Printf("creating worktree...\n")
	cmd := exec.Command("git", "-C", repoRoot, "worktree", "add", worktreePath, branchName)
	if output, err := cmd.CombinedOutput(); err != nil {
		if !strings.Contains(string(output), "already exists") {
			return fmt.Errorf("git worktree failed: %s", output)
		}
	}

	// Create tmux session
	tmuxName := "ks-" + name
	cmd = exec.Command("tmux", "new-session", "-d", "-s", tmuxName, "-c", worktreePath)
	if err := cmd.Run(); err != nil {
		if !tmuxSessionExists(tmuxName) {
			return fmt.Errorf("tmux session failed: %w", err)
		}
	}

	// Start program
	if program == "" {
		program = "claude"
	}

	cmd = exec.Command("tmux", "send-keys", "-t", tmuxName, program, "Enter")
	if err := cmd.Run(); err != nil {
		return fmt.Errorf("failed to start program: %w", err)
	}

	session := &Session{
		Name:     name,
		Branch:   branchName,
		Worktree: worktreePath,
		TmuxName: tmuxName,
		Program:  program,
		Status:   "running",
		AutoYes:  true,
		Created:  time.Now(),
		Updated:  time.Now(),
	}

	if err := storage.add(session); err != nil {
		return err
	}

	fmt.Printf("created: %s\n", name)
	return nil
}

func killSession(name string) error {
	storage := newStorage()
	sessions := storage.list()

	var session *Session
	for _, s := range sessions {
		if s.Name == name {
			session = s
			break
		}
	}

	if session == nil {
		return fmt.Errorf("session '%s' not found", name)
	}

	if tmuxSessionExists(session.TmuxName) {
		cmd := exec.Command("tmux", "kill-session", "-t", session.TmuxName)
		_ = cmd.Run()
	}

	if session.Worktree != "" {
		cmd := exec.Command("git", "worktree", "remove", "--force", session.Worktree)
		_ = cmd.Run()
	}

	if err := storage.remove(name); err != nil {
		return err
	}

	fmt.Printf("killed: %s\n", name)
	return nil
}

func resetAllSessions() error {
	storage := newStorage()
	sessions := storage.list()

	for _, session := range sessions {
		_ = killSession(session.Name)
	}

	fmt.Println("reset complete")
	return nil
}

func attachToSession(name string) error {
	storage := newStorage()
	sessions := storage.list()

	var session *Session
	for _, s := range sessions {
		if s.Name == name || s.TmuxName == name {
			session = s
			break
		}
	}

	if session == nil {
		return fmt.Errorf("session '%s' not found", name)
	}

	if !tmuxSessionExists(session.TmuxName) {
		return fmt.Errorf("tmux session '%s' not running", session.TmuxName)
	}

	cmd := exec.Command("tmux", "attach-session", "-t", session.TmuxName)
	cmd.Stdin = os.Stdin
	cmd.Stdout = os.Stdout
	cmd.Stderr = os.Stderr
	return cmd.Run()
}

// ════════════════════════════════════════════════════════════════════════════════
// TMUX
// ════════════════════════════════════════════════════════════════════════════════

func tmuxSessionExists(name string) bool {
	cmd := exec.Command("tmux", "has-session", "-t", name)
	return cmd.Run() == nil
}

func captureTmuxPane(sessionName string, lines int) (string, error) {
	tmuxName := sessionName
	if !strings.HasPrefix(sessionName, "ks-") {
		tmuxName = "ks-" + sessionName
	}

	cmd := exec.Command("tmux", "capture-pane", "-t", tmuxName, "-p", "-S", fmt.Sprintf("-%d", lines))
	output, err := cmd.Output()
	if err != nil {
		return "", err
	}
	return strings.TrimSpace(string(output)), nil
}

func sendKeysToSession(sessionName string, keys ...string) error {
	tmuxName := sessionName
	if !strings.HasPrefix(sessionName, "ks-") {
		tmuxName = "ks-" + sessionName
	}

	args := append([]string{"send-keys", "-t", tmuxName}, keys...)
	cmd := exec.Command("tmux", args...)
	return cmd.Run()
}
