# kagami_api

FastAPI-based REST API for the Kagami platform.

## Overview

`kagami_api` provides the HTTP interface to Kagami's capabilities:

- **Colony routing** — Route tasks to specialized AI colonies
- **Safety enforcement** — CBF h(x) ≥ 0 validation on all actions
- **Smart home control** — Lights, shades, scenes via REST
- **User authentication** — JWT + API key support
- **Real-time updates** — WebSocket subscriptions

## Quick Start

```bash
# Install dependencies
pip install -e ".[dev]"

# Start server
uvicorn kagami_api.main:app --port 8001 --reload

# Health check
curl http://localhost:8001/health
```

## API Structure

```
/api/v1/
├── /colonies/       # AI colony routing
│   ├── POST /route  # Route task to appropriate colony
│   └── GET /status  # Colony health status
├── /commands/       # Command execution
│   └── POST /execute
├── /smarthome/      # Smart home control
│   ├── /lights/
│   ├── /shades/
│   └── /scenes/
├── /user/           # User management
│   ├── /auth/       # Authentication
│   └── /preferences/
└── /vitals/         # System health
    ├── GET /health
    ├── GET /ready
    └── GET /live
```

## Authentication

### JWT Tokens
```python
# Login
response = requests.post("/api/v1/user/auth/login", json={
    "email": "user@example.com",
    "password": "..."
})
token = response.json()["access_token"]

# Use token
headers = {"Authorization": f"Bearer {token}"}
```

### API Keys
```python
headers = {"X-API-Key": "your-api-key"}
```

## Example: Route a Task

```python
import requests

response = requests.post(
    "http://localhost:8001/api/v1/colonies/route",
    json={
        "task": "Turn on the living room lights",
        "context": {"room": "living_room"}
    },
    headers={"Authorization": f"Bearer {token}"}
)

print(response.json())
# {"colony": "forge", "result": {"success": true, "message": "Lights set to 100%"}}
```

## Configuration

Environment variables:

| Variable | Description | Default |
|----------|-------------|---------|
| `KAGAMI_API_PORT` | Server port | 8001 |
| `KAGAMI_API_HOST` | Server host | 0.0.0.0 |
| `DATABASE_URL` | PostgreSQL connection | Required |
| `REDIS_URL` | Redis connection | Required |
| `JWT_SECRET` | JWT signing secret | Required |

## Development

```bash
# Run tests
pytest tests/unit/api/

# Type checking
mypy packages/kagami_api/

# Linting
ruff check packages/kagami_api/
```

## License

MIT — See [LICENSE](../../LICENSE)
