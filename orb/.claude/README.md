# .claude/

Claude Code context: agents, skills, and settings.

## Structure

```
.claude/
├── agents/        # Colony definitions
├── skills/        # Domain knowledge
└── settings.json  # Permissions
```

## Agents

| Agent | Purpose | File |
|-------|---------|------|
| Kagami | Coordination | `agents/kagami.md` |
| Spark | Ideas | `agents/spark.md` |
| Forge | Building | `agents/forge.md` |
| Flow | Debugging | `agents/flow.md` |
| Nexus | Integration | `agents/nexus.md` |
| Beacon | Planning | `agents/beacon.md` |
| Grove | Research | `agents/grove.md` |
| Crystal | Testing | `agents/crystal.md` |

## Skills

| Skill | Path | Purpose |
|-------|------|---------|
| Computer Control | `skills/computer-control/` | Puppeteer, desktop automation |
| E8 Math | `skills/e8-math/` | Math foundations |
| World Model | `skills/world-model/` | RSSM, dynamics |
| Safety | `skills/safety-verification/` | CBF, h(x) |
| Ralph | `skills/ralph/` | Parallel workflows, multi-perspective review |
| Quality | `skills/quality/` | Testing |
| Design | `skills/design/` | Craft, Fibonacci, voice |
| Education | `skills/education/` | Curriculum, gamification, Byzantine consensus |
| Canvas | `skills/canvas/` | LMS, QTI, export |
| Composer | `skills/composer/` | Orchestral composition |
| Video Production | `skills/video-production/` | Video pipeline, documentary |
| SmartHome | `skills/smarthome/` | Home automation |

## Browser Automation

**Always use Puppeteer MCP. Never cursor-ide-browser.**

```
✅ user-puppeteer-puppeteer_navigate
✅ user-puppeteer-puppeteer_click
✅ user-puppeteer-puppeteer_fill

❌ cursor-ide-browser-* (all forbidden)
```

## Source of Truth

| What | Where |
|------|-------|
| Identity | `CLAUDE.md` |
| Ralph | `skills/ralph/SKILL.md` |
| Task State | Memory MCP (never files) |
| Navigation | `.cursor/rules/fetch-map.mdc` |
| Character | `.claude/agents/*.md` |
| Skills | `.claude/skills/` |
