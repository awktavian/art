package main

import (
	"context"
	"fmt"
	"os"
	"os/exec"
	"os/signal"
	"path/filepath"
	"strings"
	"syscall"
	"time"

	"github.com/spf13/cobra"
)

// ════════════════════════════════════════════════════════════════════════════════
// KAGAMI SQUAD — Multi-agent orchestration with tmux + git worktrees
// ════════════════════════════════════════════════════════════════════════════════

var (
	version     = "0.1.0"
	programFlag string
	noAutoFlag  bool
	daemonFlag  bool
	apiURLFlag  string

	rootCmd = &cobra.Command{
		Use:   "ks",
		Short: "Kagami Squad — Multi-agent orchestration",
		Long: `Kagami Squad manages multiple AI coding agents in isolated workspaces.

Each session runs in its own git worktree with a dedicated tmux window.
The daemon automatically accepts prompts in the background.

USAGE:
  ks                    Launch TUI (auto-accept mode)
  ks new feature-x      Create new session
  ks list               List sessions
  ks attach feature-x   Attach to session

FLAGS:
  -p, --program         AI program (claude, aider)
  --no-auto             Disable auto-accept
  --api                 Kagami API URL`,
		RunE: func(cmd *cobra.Command, args []string) error {
			ctx := context.Background()

			autoYes := !noAutoFlag

			if daemonFlag {
				return runDaemon(ctx)
			}

			currentDir, err := filepath.Abs(".")
			if err != nil {
				return fmt.Errorf("failed to get current directory: %w", err)
			}

			if !isGitRepo(currentDir) {
				return fmt.Errorf("ks must be run from within a git repository")
			}

			cfg := LoadConfig()

			program := cfg.DefaultProgram
			if programFlag != "" {
				program = programFlag
			}

			apiURL := apiURLFlag
			if apiURL == "" {
				apiURL = cfg.KagamiAPIURL
			}

			if autoYes {
				defer func() {
					if err := launchDaemon(); err != nil {
						fmt.Fprintf(os.Stderr, "warning: daemon failed: %v\n", err)
					}
				}()
			}

			_ = stopDaemon()

			return RunTui(program, autoYes, apiURL)
		},
	}

	newCmd = &cobra.Command{
		Use:   "new [name]",
		Short: "Create a new session",
		Args:  cobra.MaximumNArgs(1),
		RunE: func(cmd *cobra.Command, args []string) error {
			name := ""
			if len(args) > 0 {
				name = args[0]
			}

			cfg := LoadConfig()
			program := cfg.DefaultProgram
			if programFlag != "" {
				program = programFlag
			}

			return createSession(name, program)
		},
	}

	listCmd = &cobra.Command{
		Use:   "list",
		Short: "List all sessions",
		RunE: func(cmd *cobra.Command, args []string) error {
			return printSessionList()
		},
	}

	attachCmd = &cobra.Command{
		Use:   "attach <name>",
		Short: "Attach to a session",
		Args:  cobra.ExactArgs(1),
		RunE: func(cmd *cobra.Command, args []string) error {
			return attachToSession(args[0])
		},
	}

	killCmd = &cobra.Command{
		Use:   "kill <name>",
		Short: "Kill a session",
		Args:  cobra.ExactArgs(1),
		RunE: func(cmd *cobra.Command, args []string) error {
			return killSession(args[0])
		},
	}

	resetCmd = &cobra.Command{
		Use:   "reset",
		Short: "Kill all sessions",
		RunE: func(cmd *cobra.Command, args []string) error {
			return resetAllSessions()
		},
	}

	statusCmd = &cobra.Command{
		Use:   "status",
		Short: "Show system status",
		RunE: func(cmd *cobra.Command, args []string) error {
			return printStatus(apiURLFlag)
		},
	}

	versionCmd = &cobra.Command{
		Use:   "version",
		Short: "Print version",
		Run: func(cmd *cobra.Command, args []string) {
			fmt.Printf("ks v%s\n", version)
		},
	}
)

// ════════════════════════════════════════════════════════════════════════════════
// LIST
// ════════════════════════════════════════════════════════════════════════════════

func printSessionList() error {
	storage := newStorage()
	sessions := storage.list()

	if len(sessions) == 0 {
		fmt.Println("No sessions. Create one with: ks new <name>")
		return nil
	}

	fmt.Printf("Sessions (%d)\n\n", len(sessions))

	for _, s := range sessions {
		status := "○"
		if s.Status == "running" {
			status = "●"
		} else if s.Status == "paused" {
			status = "◆"
		}

		auto := ""
		if s.AutoYes {
			auto = " [auto]"
		}

		fmt.Printf("  %s %s%s\n", status, s.Name, auto)
		fmt.Printf("    branch: %s\n", s.Branch)
	}

	fmt.Println()
	return nil
}

// ════════════════════════════════════════════════════════════════════════════════
// STATUS
// ════════════════════════════════════════════════════════════════════════════════

func printStatus(apiURL string) error {
	fmt.Println("Kagami Squad Status")
	fmt.Println(strings.Repeat("-", 40))

	// Dependencies
	fmt.Println("\nDependencies:")

	deps := []string{"tmux", "git", "claude", "aider"}
	for _, dep := range deps {
		if _, err := exec.LookPath(dep); err != nil {
			fmt.Printf("  ✗ %s (not found)\n", dep)
		} else {
			fmt.Printf("  ✓ %s\n", dep)
		}
	}

	// API
	fmt.Println("\nKagami API:")
	if apiURL == "" {
		apiURL = "http://127.0.0.1:8001"
	}
	api := NewKagamiAPI(apiURL)
	if api.IsReachable() {
		fmt.Printf("  ✓ %s\n", apiURL)
	} else {
		fmt.Printf("  ✗ %s (unreachable)\n", apiURL)
	}

	// Sessions
	storage := newStorage()
	sessions := storage.list()
	fmt.Printf("\nSessions: %d\n", len(sessions))

	// Config
	configDir, _ := getConfigDir()
	fmt.Printf("Config: %s\n", configDir)

	fmt.Println()
	return nil
}

// ════════════════════════════════════════════════════════════════════════════════
// DAEMON
// ════════════════════════════════════════════════════════════════════════════════

func runDaemon(ctx context.Context) error {
	storage := newStorage()
	cfg := LoadConfig()
	pollInterval := time.Duration(cfg.DaemonPollInterval) * time.Millisecond

	sigChan := make(chan os.Signal, 1)
	signal.Notify(sigChan, syscall.SIGINT, syscall.SIGTERM)

	ticker := time.NewTicker(pollInterval)
	defer ticker.Stop()

	for {
		select {
		case <-ctx.Done():
			return nil
		case <-sigChan:
			return nil
		case <-ticker.C:
			sessions := storage.list()
			for _, session := range sessions {
				if session.AutoYes && session.Status == "running" {
					output, err := captureTmuxPane(session.Name, 10)
					if err != nil {
						continue
					}

					if needsInput(output) {
						_ = sendKeysToSession(session.Name, "Enter")
					}
				}
			}
		}
	}
}

func needsInput(output string) bool {
	patterns := []string{
		"[Y/n]",
		"[y/N]",
		"(yes/no)",
		"Press ENTER",
		"Continue?",
		"Do you want to",
		"Apply changes?",
		"Proceed?",
	}

	lower := strings.ToLower(output)
	for _, pattern := range patterns {
		if strings.Contains(lower, strings.ToLower(pattern)) {
			return true
		}
	}
	return false
}

func launchDaemon() error {
	execPath, err := os.Executable()
	if err != nil {
		return fmt.Errorf("failed to get executable: %w", err)
	}

	cmd := exec.Command(execPath, "--daemon")
	cmd.Stdin = nil
	cmd.Stdout = nil
	cmd.Stderr = nil
	cmd.SysProcAttr = &syscall.SysProcAttr{
		Setpgid: true,
	}

	if err := cmd.Start(); err != nil {
		return fmt.Errorf("failed to start daemon: %w", err)
	}

	configDir, err := getConfigDir()
	if err != nil {
		return err
	}

	pidFile := filepath.Join(configDir, "daemon.pid")
	return os.WriteFile(pidFile, []byte(fmt.Sprintf("%d", cmd.Process.Pid)), 0644)
}

func stopDaemon() error {
	configDir, err := getConfigDir()
	if err != nil {
		return err
	}

	pidFile := filepath.Join(configDir, "daemon.pid")
	data, err := os.ReadFile(pidFile)
	if err != nil {
		return nil
	}

	var pid int
	if _, err := fmt.Sscanf(string(data), "%d", &pid); err != nil {
		return err
	}

	proc, err := os.FindProcess(pid)
	if err != nil {
		return err
	}

	_ = proc.Kill()
	_ = os.Remove(pidFile)
	return nil
}

// ════════════════════════════════════════════════════════════════════════════════
// INIT
// ════════════════════════════════════════════════════════════════════════════════

func init() {
	rootCmd.Flags().StringVarP(&programFlag, "program", "p", "",
		"Program to run (claude, aider)")
	rootCmd.Flags().BoolVar(&noAutoFlag, "no-auto", false,
		"Disable auto-accept mode")
	rootCmd.Flags().BoolVar(&daemonFlag, "daemon", false, "Run daemon mode")
	rootCmd.Flags().StringVar(&apiURLFlag, "api", "",
		"Kagami API URL")

	_ = rootCmd.Flags().MarkHidden("daemon")

	rootCmd.AddCommand(newCmd)
	rootCmd.AddCommand(listCmd)
	rootCmd.AddCommand(attachCmd)
	rootCmd.AddCommand(killCmd)
	rootCmd.AddCommand(resetCmd)
	rootCmd.AddCommand(statusCmd)
	rootCmd.AddCommand(versionCmd)

	newCmd.Flags().StringVarP(&programFlag, "program", "p", "",
		"Program to run (claude, aider)")
}

// ════════════════════════════════════════════════════════════════════════════════
// MAIN
// ════════════════════════════════════════════════════════════════════════════════

func main() {
	if err := rootCmd.Execute(); err != nil {
		os.Exit(1)
	}
}
