# ks

Manage multiple AI agents in isolated workspaces.

## Install

```bash
brew install go
cd apps/cli/kagami-squad
make install
```

## Usage

```bash
ks              # TUI
ks new feature  # create session
ks list         # show sessions
ks attach name  # attach to session
ks kill name    # kill session
ks reset        # kill all
```

## Sessions

Each session gets:
- isolated git worktree
- dedicated tmux window
- auto-accept daemon (if configured)

## Design

Follows [Aider](https://github.com/paul-gauthier/aider) and [Claude Code](https://github.com/anthropics/claude-code) patterns:
- single pane focus
- gray palette
- minimal indicators
- sparse keybindings

## TUI

```
ks                                3 sessions

> ● refactor-api
  ○ fix-auth-bug
  ○ add-tests

  n new  o attach  d kill  q quit
```

Keys:
- `j/k` or arrows — navigate
- `enter` or `l` — preview
- `o` — attach (opens tmux)
- `n` — new session
- `d` — kill session
- `q` — quit
