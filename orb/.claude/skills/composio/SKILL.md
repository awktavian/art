# Composio Skill — Digital Integration

**11 Connected Services · 700+ Digital Tools**

This skill defines how I interact with the digital world through Composio.

---

## Quick Start

```python
from kagami.core.services.composio import get_composio_service

service = get_composio_service()
await service.initialize()

# Execute any action
result = await service.execute_action(
    "ACTION_NAME",
    {"param": "value"}
)
```

---

## Connected Services

| Service | Tools | Key Actions |
|---------|-------|-------------|
| **GitHub** | 200+ | CREATE_AN_ISSUE, CREATE_A_PULL_REQUEST, LIST_WORKFLOW_RUNS |
| **Slack** | 130 | SEND_MESSAGE, CREATE_CHANNEL |
| **Twitter** | 75 | POST_TWEET, SEARCH |
| **Drive** | 56 | LIST_FILES, UPLOAD_FILE |
| **Calendar** | 44 | CREATE_EVENT, LIST_EVENTS |
| **Todoist** | 44 | CREATE_TASK, LIST_TASKS |
| **Notion** | 42 | CREATE_PAGE, SEARCH_NOTION_PAGE |
| **Sheets** | 40 | GET_SPREADSHEET_INFO |
| **Gmail** | 37 | FETCH_EMAILS, SEND_EMAIL |
| **Linear** | 26 | CREATE_LINEAR_ISSUE, GET_CYCLES |
| **Discord** | 6 | SEND_MESSAGE, GET_MY_USER |

---

## Ecosystem Orchestration

```python
from kagami.core.orchestration import get_ecosystem_orchestrator

orchestrator = await get_ecosystem_orchestrator()
await orchestrator.initialize()

# Unified state across ALL services
state = await orchestrator.get_ecosystem_state()

# Cross-domain triggers
await orchestrator.enable_cross_domain_triggers()
```

### Cross-Domain Triggers

| Source | Trigger | Actions |
|--------|---------|---------|
| GitHub | CI failure | Linear issue + Slack alert |
| Gmail | Urgent email | Linear ticket + Slack notify |
| Calendar | Meeting soon | SmartHome prepare office |
| Linear | Sprint complete | Notion doc + Slack announce |

---

## Specialized Flows

### GitHub Development Flow

```python
from kagami.core.orchestration import get_github_flow

flow = await get_github_flow()
await flow.initialize()

# Create branch from issue
branch = await flow.create_branch_from_issue("KAG-123")

# Auto-merge when CI passes
await flow.auto_merge_when_ready(pr_number)
```

### Linear Sprint Sync

```python
from kagami.core.orchestration import get_linear_sync

sync = await get_linear_sync()
await sync.initialize()

# Generate sprint report
report = await sync.generate_sprint_report()
```

### Notion Knowledge Base

```python
from kagami.core.orchestration import get_notion_kb

kb = await get_notion_kb()
await kb.initialize()

# Store research
await kb.store_research("Topic", "Findings...")

# Log decision
await kb.log_decision("Decision Title", "Context", "Decision", ["consequence"])
```

---

## Colony → Service Mapping

| Colony | Primary Services | Key Actions |
|--------|------------------|-------------|
| 🔥 Spark | Twitter, Slack | SEARCH, GET_TRENDING, SEND_MESSAGE |
| ⚒️ Forge | GitHub, Linear | CREATE_BRANCH, CREATE_PR, CREATE_ISSUE |
| 🌊 Flow | GitHub Actions, Slack | LIST_WORKFLOW_RUNS, SEND_MESSAGE (alerts) |
| 🔗 Nexus | All services | Cross-domain routing |
| 🗼 Beacon | Linear, Notion | GET_CYCLES, CREATE_PAGE (decisions) |
| 🌿 Grove | Notion, Drive | SEARCH_PAGE, LIST_FILES |
| 💎 Crystal | GitHub, Linear | LIST_WORKFLOW_RUNS (CI), CREATE_ISSUE (defects) |

---

## Learning Pipeline

```python
from kagami.core.orchestration import get_learning_pipeline

pipeline = await get_learning_pipeline()
await pipeline.initialize()

# Record action
await pipeline.record_action(
    colony="forge",
    service="github",
    action="CREATE_BRANCH",
    success=True,
    duration_ms=150,
)

# Get routing suggestions
suggestions = pipeline.get_routing_suggestions("create feature")
```

---

## Safety

```
h(x) ≥ 0 ALWAYS.

1. Never send without explicit intent
2. Never delete without confirmation
3. Rate limiting enforced (10 QPS)
4. Circuit breaker on failures
5. All actions logged
```

---

鏡
