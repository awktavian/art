package main

import (
	"fmt"
	"os/exec"
	"strings"
	"time"

	"github.com/charmbracelet/bubbles/spinner"
	"github.com/charmbracelet/bubbles/textinput"
	tea "github.com/charmbracelet/bubbletea"
	"github.com/charmbracelet/lipgloss"
)

// ════════════════════════════════════════════════════════════════════════════════
// DESIGN SYSTEM — Calm palette, minimal visual language
// ════════════════════════════════════════════════════════════════════════════════

var (
	// Core palette - calm grays with subtle warmth
	colorVoid     = lipgloss.Color("#0a0a0a") // deepest background
	colorSurface  = lipgloss.Color("#141414") // raised surface
	colorDim      = lipgloss.Color("#444444") // disabled, borders
	colorMuted    = lipgloss.Color("#666666") // secondary text
	colorSubtle   = lipgloss.Color("#888888") // hints
	colorText     = lipgloss.Color("#b0b0b0") // primary text
	colorBright   = lipgloss.Color("#e0e0e0") // emphasis
	colorFocus    = lipgloss.Color("#ffffff") // maximum emphasis

	// Semantic colors - soft, not harsh
	colorOK      = lipgloss.Color("#5c8a5c") // success - forest green
	colorWarn    = lipgloss.Color("#8a8a5c") // warning - muted gold
	colorError   = lipgloss.Color("#8a5c5c") // error - muted red
	colorInfo    = lipgloss.Color("#5c7a8a") // info - steel blue
	colorAccent  = lipgloss.Color("#7a8a9a") // accent - cool gray-blue

	// Typography styles
	voidStyle    = lipgloss.NewStyle().Foreground(colorVoid)
	dimStyle     = lipgloss.NewStyle().Foreground(colorDim)
	mutedStyle   = lipgloss.NewStyle().Foreground(colorMuted)
	subtleStyle  = lipgloss.NewStyle().Foreground(colorSubtle)
	textStyle    = lipgloss.NewStyle().Foreground(colorText)
	brightStyle  = lipgloss.NewStyle().Foreground(colorBright)
	focusStyle   = lipgloss.NewStyle().Foreground(colorFocus)

	// Semantic styles
	okStyle      = lipgloss.NewStyle().Foreground(colorOK)
	warnStyle    = lipgloss.NewStyle().Foreground(colorWarn)
	errorStyle   = lipgloss.NewStyle().Foreground(colorError)
	infoStyle    = lipgloss.NewStyle().Foreground(colorInfo)
	accentStyle  = lipgloss.NewStyle().Foreground(colorAccent)

	// Interactive styles
	selectedStyle = lipgloss.NewStyle().Foreground(colorFocus).Bold(true)
	cursorStyle   = lipgloss.NewStyle().Foreground(colorAccent)
)

// ════════════════════════════════════════════════════════════════════════════════
// STATE MACHINE — Explicit states and transitions
// ════════════════════════════════════════════════════════════════════════════════

type tuiState int

const (
	// Core states
	stateList    tuiState = iota // Default: show session list
	statePreview                  // Show session output
	stateNew                      // Create new session
	stateConfirm                  // Confirm destructive action

	// Error states
	stateError // Show error with recovery options

	// Loading states
	stateLoading // Async operation in progress
)

func (s tuiState) String() string {
	switch s {
	case stateList:
		return "list"
	case statePreview:
		return "preview"
	case stateNew:
		return "new"
	case stateConfirm:
		return "confirm"
	case stateError:
		return "error"
	case stateLoading:
		return "loading"
	default:
		return "unknown"
	}
}

// ════════════════════════════════════════════════════════════════════════════════
// MODEL — Single source of truth
// ════════════════════════════════════════════════════════════════════════════════

type tuiModel struct {
	// Current state
	state     tuiState
	prevState tuiState // for returning from error/loading

	// Session data
	sessions []*Session
	selected int
	storage  *Storage

	// Configuration
	program string
	autoYes bool
	apiURL  string

	// External connections
	api         *KagamiAPI
	apiStatus   string // "ok", "unreachable", "unknown"
	lastAPIPoll time.Time

	// UI components
	spinner   spinner.Model
	textInput textinput.Model

	// Viewport
	width  int
	height int

	// Tick counter for animations
	tick int

	// Preview content (cached)
	previewContent string
	previewSession string // which session is being previewed

	// Confirm dialog state
	confirmMsg    string
	confirmAction func() error // returns error for feedback
	confirmTarget string       // what we're confirming

	// Error state
	errorMsg   string
	errorHint  string
	errorRetry func() // optional retry action

	// Status message (temporary)
	statusMsg    string
	statusLevel  string // "ok", "warn", "error", "info"
	statusExpiry time.Time

	// Loading state
	loadingMsg string
}

// ════════════════════════════════════════════════════════════════════════════════
// MESSAGES — Typed communication
// ════════════════════════════════════════════════════════════════════════════════

type tickMsg time.Time
type apiStatusMsg string
type sessionCreatedMsg struct{ name string }
type sessionErrorMsg struct{ err error }
type previewUpdateMsg string

// ════════════════════════════════════════════════════════════════════════════════
// INIT
// ════════════════════════════════════════════════════════════════════════════════

func newTuiModel(program string, autoYes bool, apiURL string) tuiModel {
	storage := newStorage()

	// Spinner: simple dot
	s := spinner.New()
	s.Spinner = spinner.Dot
	s.Style = subtleStyle

	// Text input
	ti := textinput.New()
	ti.Placeholder = "session-name"
	ti.CharLimit = 40
	ti.Width = 30
	ti.PromptStyle = mutedStyle
	ti.TextStyle = textStyle
	ti.PlaceholderStyle = dimStyle
	ti.Cursor.Style = accentStyle

	return tuiModel{
		state:       stateList,
		sessions:    storage.list(),
		storage:     storage,
		program:     program,
		autoYes:     autoYes,
		apiURL:      apiURL,
		api:         NewKagamiAPI(apiURL),
		apiStatus:   "unknown",
		spinner:     s,
		textInput:   ti,
	}
}

func (m tuiModel) Init() tea.Cmd {
	return tea.Batch(
		m.spinner.Tick,
		tickCmd(),
		checkAPICmd(m.api),
	)
}

func tickCmd() tea.Cmd {
	// 233ms = Fibonacci tick for smooth updates
	return tea.Tick(233*time.Millisecond, func(t time.Time) tea.Msg {
		return tickMsg(t)
	})
}

func checkAPICmd(api *KagamiAPI) tea.Cmd {
	return func() tea.Msg {
		if api.IsReachable() {
			return apiStatusMsg("ok")
		}
		return apiStatusMsg("unreachable")
	}
}

// ════════════════════════════════════════════════════════════════════════════════
// UPDATE — State machine transitions
// ════════════════════════════════════════════════════════════════════════════════

func (m tuiModel) Update(msg tea.Msg) (tea.Model, tea.Cmd) {
	switch msg := msg.(type) {
	case tea.WindowSizeMsg:
		m.width = msg.Width
		m.height = msg.Height
		return m, nil

	case tickMsg:
		m.tick++

		// Refresh sessions every ~2s (9 ticks * 233ms)
		if m.tick%9 == 0 {
			m.sessions = m.storage.list()
		}

		// Update preview content if viewing
		if m.state == statePreview && m.selected < len(m.sessions) {
			session := m.sessions[m.selected]
			if session.Name != m.previewSession {
				m.previewSession = session.Name
			}
			content, _ := captureTmuxPane(session.Name, m.height-8)
			m.previewContent = content
		}

		// Poll API every ~5s (21 ticks)
		if m.tick%21 == 0 {
			return m, tea.Batch(tickCmd(), checkAPICmd(m.api))
		}

		// Clear expired status
		if m.statusMsg != "" && time.Now().After(m.statusExpiry) {
			m.statusMsg = ""
		}

		return m, tickCmd()

	case apiStatusMsg:
		m.apiStatus = string(msg)
		m.lastAPIPoll = time.Now()
		return m, nil

	case sessionCreatedMsg:
		m.sessions = m.storage.list()
		m.setStatus("ok", "created "+msg.name)
		m.state = stateList
		// Select the new session
		for i, s := range m.sessions {
			if s.Name == msg.name {
				m.selected = i
				break
			}
		}
		return m, nil

	case sessionErrorMsg:
		m.setError(msg.err.Error(), "press any key to continue")
		return m, nil

	case spinner.TickMsg:
		var cmd tea.Cmd
		m.spinner, cmd = m.spinner.Update(msg)
		return m, cmd

	case tea.KeyMsg:
		return m.handleKey(msg)
	}

	return m, nil
}

func (m tuiModel) handleKey(msg tea.KeyMsg) (tea.Model, tea.Cmd) {
	// Global escape hatch
	switch msg.String() {
	case "ctrl+c":
		return m, tea.Quit
	}

	// State-specific handling
	switch m.state {
	case stateError:
		return m.handleErrorKeys(msg)
	case stateLoading:
		// No input during loading
		return m, nil
	case stateNew:
		return m.handleNewKeys(msg)
	case stateConfirm:
		return m.handleConfirmKeys(msg)
	case statePreview:
		return m.handlePreviewKeys(msg)
	default:
		return m.handleListKeys(msg)
	}
}

func (m tuiModel) handleListKeys(msg tea.KeyMsg) (tea.Model, tea.Cmd) {
	switch msg.String() {
	case "q", "esc":
		return m, tea.Quit

	case "up", "k":
		if m.selected > 0 {
			m.selected--
		} else if len(m.sessions) > 0 {
			m.selected = len(m.sessions) - 1 // wrap
		}

	case "down", "j":
		if m.selected < len(m.sessions)-1 {
			m.selected++
		} else if len(m.sessions) > 0 {
			m.selected = 0 // wrap
		}

	case "enter", "l", "right":
		if len(m.sessions) > 0 && m.selected < len(m.sessions) {
			m.state = statePreview
			session := m.sessions[m.selected]
			m.previewSession = session.Name
			content, _ := captureTmuxPane(session.Name, m.height-8)
			m.previewContent = content
		}

	case "o":
		// Open/attach to tmux session
		if len(m.sessions) > 0 && m.selected < len(m.sessions) {
			session := m.sessions[m.selected]
			if tmuxSessionExists(session.TmuxName) {
				c := exec.Command("tmux", "attach-session", "-t", session.TmuxName)
				return m, tea.ExecProcess(c, func(err error) tea.Msg {
					return tickMsg(time.Now())
				})
			} else {
				m.setError("session not running", "start it first or remove it")
			}
		}

	case "n":
		m.prevState = m.state
		m.state = stateNew
		m.textInput.SetValue("")
		m.textInput.Focus()
		return m, textinput.Blink

	case "d", "x":
		if len(m.sessions) > 0 && m.selected < len(m.sessions) {
			session := m.sessions[m.selected]
			m.confirmTarget = session.Name
			m.confirmMsg = fmt.Sprintf("kill '%s'?", session.Name)
			m.confirmAction = func() error {
				return killSession(session.Name)
			}
			m.prevState = m.state
			m.state = stateConfirm
		}

	case "D", "X":
		// Kill all - extra dangerous
		if len(m.sessions) > 0 {
			m.confirmMsg = fmt.Sprintf("kill ALL %d sessions?", len(m.sessions))
			m.confirmTarget = "all"
			m.confirmAction = func() error {
				return resetAllSessions()
			}
			m.prevState = m.state
			m.state = stateConfirm
		}

	case "r":
		m.sessions = m.storage.list()
		m.setStatus("info", "refreshed")

	case "?":
		m.setStatus("info", "n:new o:open d:kill q:quit")
	}

	return m, nil
}

func (m tuiModel) handlePreviewKeys(msg tea.KeyMsg) (tea.Model, tea.Cmd) {
	switch msg.String() {
	case "q", "esc", "h", "left":
		m.state = stateList
		m.previewContent = ""
		m.previewSession = ""

	case "o", "enter":
		if m.selected < len(m.sessions) {
			session := m.sessions[m.selected]
			if tmuxSessionExists(session.TmuxName) {
				c := exec.Command("tmux", "attach-session", "-t", session.TmuxName)
				return m, tea.ExecProcess(c, func(err error) tea.Msg {
					return tickMsg(time.Now())
				})
			} else {
				m.setError("session not running", "tmux session is dead")
			}
		}

	case "up", "k":
		if m.selected > 0 {
			m.selected--
			if m.selected < len(m.sessions) {
				session := m.sessions[m.selected]
				m.previewSession = session.Name
				content, _ := captureTmuxPane(session.Name, m.height-8)
				m.previewContent = content
			}
		}

	case "down", "j":
		if m.selected < len(m.sessions)-1 {
			m.selected++
			session := m.sessions[m.selected]
			m.previewSession = session.Name
			content, _ := captureTmuxPane(session.Name, m.height-8)
			m.previewContent = content
		}

	case "d", "x":
		if m.selected < len(m.sessions) {
			session := m.sessions[m.selected]
			m.confirmTarget = session.Name
			m.confirmMsg = fmt.Sprintf("kill '%s'?", session.Name)
			m.confirmAction = func() error {
				return killSession(session.Name)
			}
			m.prevState = m.state
			m.state = stateConfirm
		}
	}

	return m, nil
}

func (m tuiModel) handleNewKeys(msg tea.KeyMsg) (tea.Model, tea.Cmd) {
	switch msg.String() {
	case "esc":
		m.state = m.prevState
		return m, nil

	case "enter":
		name := strings.TrimSpace(m.textInput.Value())
		if name == "" {
			name = fmt.Sprintf("session-%d", time.Now().Unix()%10000)
		}
		name = strings.ToLower(strings.ReplaceAll(name, " ", "-"))

		// Validate name
		for _, s := range m.sessions {
			if s.Name == name {
				m.setError(fmt.Sprintf("'%s' already exists", name), "use a different name")
				return m, nil
			}
		}

		// Create session (can be slow)
		m.state = stateLoading
		m.loadingMsg = fmt.Sprintf("creating %s...", name)

		return m, func() tea.Msg {
			if err := createSession(name, m.program); err != nil {
				return sessionErrorMsg{err: err}
			}
			return sessionCreatedMsg{name: name}
		}

	default:
		var cmd tea.Cmd
		m.textInput, cmd = m.textInput.Update(msg)
		return m, cmd
	}
}

func (m tuiModel) handleConfirmKeys(msg tea.KeyMsg) (tea.Model, tea.Cmd) {
	switch msg.String() {
	case "y", "Y", "enter":
		if m.confirmAction != nil {
			if err := m.confirmAction(); err != nil {
				m.setError(err.Error(), "")
			} else {
				m.setStatus("ok", fmt.Sprintf("killed %s", m.confirmTarget))
				m.sessions = m.storage.list()
				if m.selected >= len(m.sessions) && m.selected > 0 {
					m.selected--
				}
			}
		}
		m.state = stateList
		m.confirmAction = nil
		m.confirmTarget = ""

	case "n", "N", "esc", "q":
		m.state = m.prevState
		m.confirmAction = nil
		m.confirmTarget = ""
	}

	return m, nil
}

func (m tuiModel) handleErrorKeys(msg tea.KeyMsg) (tea.Model, tea.Cmd) {
	// Any key dismisses error
	m.state = m.prevState
	m.errorMsg = ""
	m.errorHint = ""
	return m, nil
}

// ════════════════════════════════════════════════════════════════════════════════
// STATUS HELPERS
// ════════════════════════════════════════════════════════════════════════════════

func (m *tuiModel) setStatus(level, msg string) {
	m.statusMsg = msg
	m.statusLevel = level
	m.statusExpiry = time.Now().Add(3 * time.Second)
}

func (m *tuiModel) setError(msg, hint string) {
	m.prevState = m.state
	m.state = stateError
	m.errorMsg = msg
	m.errorHint = hint
}

// ════════════════════════════════════════════════════════════════════════════════
// VIEW — Render current state
// ════════════════════════════════════════════════════════════════════════════════

func (m tuiModel) View() string {
	if m.width == 0 {
		return m.spinner.View() + " initializing..."
	}

	var b strings.Builder

	// Header - always visible
	b.WriteString(m.viewHeader())
	b.WriteString("\n")

	// Content based on state
	switch m.state {
	case stateLoading:
		b.WriteString(m.viewLoading())
	case stateError:
		b.WriteString(m.viewError())
	case stateConfirm:
		b.WriteString(m.viewConfirm())
	case stateNew:
		b.WriteString(m.viewNew())
	case statePreview:
		b.WriteString(m.viewPreview())
	default:
		b.WriteString(m.viewList())
	}

	// Footer - always visible
	b.WriteString("\n")
	b.WriteString(m.viewFooter())

	return b.String()
}

func (m tuiModel) viewHeader() string {
	// Left: title
	title := dimStyle.Render("ks")

	// Right: status indicators
	var indicators []string

	// Session count
	if len(m.sessions) > 0 {
		running := 0
		for _, s := range m.sessions {
			if s.Status == "running" {
				running++
			}
		}
		if running > 0 {
			indicators = append(indicators, okStyle.Render(fmt.Sprintf("%d", running)))
		}
		if running < len(m.sessions) {
			stopped := len(m.sessions) - running
			indicators = append(indicators, dimStyle.Render(fmt.Sprintf("+%d", stopped)))
		}
	}

	// API status (subtle)
	switch m.apiStatus {
	case "ok":
		indicators = append(indicators, dimStyle.Render("·"))
	case "unreachable":
		indicators = append(indicators, errorStyle.Render("○"))
	}

	right := strings.Join(indicators, " ")

	// Calculate padding
	padding := m.width - lipgloss.Width(title) - lipgloss.Width(right) - 2
	if padding < 1 {
		padding = 1
	}

	return title + strings.Repeat(" ", padding) + right
}

func (m tuiModel) viewList() string {
	var b strings.Builder

	if len(m.sessions) == 0 {
		b.WriteString("\n")
		b.WriteString(mutedStyle.Render("  no sessions"))
		b.WriteString("\n\n")
		b.WriteString(dimStyle.Render("  n to create"))
		b.WriteString("\n")
		return b.String()
	}

	b.WriteString("\n")

	for i, s := range m.sessions {
		// Status indicator
		var dot string
		switch s.Status {
		case "running":
			// Subtle pulse effect for running sessions
			if m.tick%4 < 2 {
				dot = okStyle.Render("●")
			} else {
				dot = okStyle.Render("○")
			}
		default:
			dot = dimStyle.Render("○")
		}

		// Name
		name := s.Name
		if len(name) > 28 {
			name = name[:25] + "..."
		}

		// Program badge (very subtle)
		prog := ""
		if s.Program != "claude" {
			prog = dimStyle.Render(" [" + s.Program + "]")
		}

		// Selection
		prefix := "  "
		nameStyle := mutedStyle
		if i == m.selected {
			prefix = cursorStyle.Render("> ")
			nameStyle = textStyle
		}

		b.WriteString(fmt.Sprintf("%s%s %s%s\n", prefix, dot, nameStyle.Render(name), prog))
	}

	return b.String()
}

func (m tuiModel) viewPreview() string {
	if m.selected >= len(m.sessions) {
		return ""
	}

	session := m.sessions[m.selected]

	var b strings.Builder

	// Session info header
	var dot string
	if session.Status == "running" {
		dot = okStyle.Render("●")
	} else {
		dot = dimStyle.Render("○")
	}

	b.WriteString(fmt.Sprintf("\n%s %s\n", dot, brightStyle.Render(session.Name)))
	b.WriteString(dimStyle.Render(fmt.Sprintf("  %s", session.Branch)))
	b.WriteString("\n\n")

	// Preview content
	content := m.previewContent
	if content == "" {
		content = mutedStyle.Render("  (no output)")
	} else {
		// Indent and limit lines
		lines := strings.Split(content, "\n")
		maxLines := m.height - 10
		if maxLines < 5 {
			maxLines = 5
		}
		if len(lines) > maxLines {
			lines = lines[len(lines)-maxLines:]
		}

		var contentLines []string
		for _, line := range lines {
			// Subtle indent
			contentLines = append(contentLines, "  "+line)
		}
		content = strings.Join(contentLines, "\n")
	}

	b.WriteString(content)
	b.WriteString("\n")

	return b.String()
}

func (m tuiModel) viewNew() string {
	var b strings.Builder
	b.WriteString("\n")
	b.WriteString(textStyle.Render("  new: "))
	b.WriteString(m.textInput.View())
	b.WriteString("\n\n")
	b.WriteString(dimStyle.Render("  enter to create · esc to cancel"))
	b.WriteString("\n")
	return b.String()
}

func (m tuiModel) viewConfirm() string {
	var b strings.Builder
	b.WriteString("\n")
	b.WriteString(warnStyle.Render("  " + m.confirmMsg))
	b.WriteString("\n\n")
	b.WriteString(dimStyle.Render("  y/n"))
	b.WriteString("\n")
	return b.String()
}

func (m tuiModel) viewError() string {
	var b strings.Builder
	b.WriteString("\n")
	b.WriteString(errorStyle.Render("  error: " + m.errorMsg))
	b.WriteString("\n")
	if m.errorHint != "" {
		b.WriteString(dimStyle.Render("  " + m.errorHint))
		b.WriteString("\n")
	}
	b.WriteString("\n")
	b.WriteString(dimStyle.Render("  press any key"))
	b.WriteString("\n")
	return b.String()
}

func (m tuiModel) viewLoading() string {
	var b strings.Builder
	b.WriteString("\n")
	b.WriteString("  ")
	b.WriteString(m.spinner.View())
	b.WriteString(" ")
	b.WriteString(mutedStyle.Render(m.loadingMsg))
	b.WriteString("\n")
	return b.String()
}

func (m tuiModel) viewFooter() string {
	// Status message takes priority
	if m.statusMsg != "" {
		var style lipgloss.Style
		switch m.statusLevel {
		case "ok":
			style = okStyle
		case "warn":
			style = warnStyle
		case "error":
			style = errorStyle
		default:
			style = subtleStyle
		}
		return style.Render("  " + m.statusMsg)
	}

	// Contextual hints
	switch m.state {
	case statePreview:
		return dimStyle.Render("  o attach · ← back · d kill")
	case stateNew:
		return "" // hints in viewNew
	case stateConfirm:
		return "" // hints in viewConfirm
	case stateError:
		return "" // hints in viewError
	case stateLoading:
		return ""
	default:
		if len(m.sessions) == 0 {
			return dimStyle.Render("  n new · q quit")
		}
		return dimStyle.Render("  n new · o attach · d kill · q quit")
	}
}

// ════════════════════════════════════════════════════════════════════════════════
// ENTRY POINT
// ════════════════════════════════════════════════════════════════════════════════

func RunTui(program string, autoYes bool, apiURL string) error {
	p := tea.NewProgram(
		newTuiModel(program, autoYes, apiURL),
		tea.WithAltScreen(),
		tea.WithMouseCellMotion(), // Enable mouse for future use
	)
	_, err := p.Run()
	return err
}
