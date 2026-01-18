"""Voice Webhook — Unified Voice & MCP Server.

Handles:
- Twilio incoming calls → ElevenLabs ConvAI
- MCP tool execution → Unified command router
- Voice status callbacks

Security:
- Token-based authentication (Bearer / X-MCP-Token / query param)
- Rate limiting (100 requests/minute per IP)
- Request logging with IP tracking
- RBAC via UnifiedCommandRouter

Endpoints:
- POST /voice/incoming — Twilio webhook
- POST /voice/mcp/execute — MCP tool execution (secured)
- GET /voice/mcp/capabilities — List available tools
- GET /voice/mcp/health — Health check

ElevenLabs MCP Configuration:
- URL: https://<ngrok-domain>/voice/mcp/execute
- Secret Name: mcp_auth_token
- Secret stored in Kagami keychain as: elevenlabs_mcp_token
- Header: Authorization: Bearer <token>

Created: January 8, 2026
鏡
"""

from __future__ import annotations

import hmac
import logging
import os
import time
from collections import defaultdict
from datetime import datetime
from typing import Any

from fastapi import APIRouter, Request
from fastapi.responses import Response
from pydantic import BaseModel

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/voice", tags=["voice-webhook"])


# =============================================================================
# Rate Limiting
# =============================================================================

# In-memory rate limiter (per IP)
_rate_limits: dict[str, list[float]] = defaultdict(list)
RATE_LIMIT_WINDOW = 60  # seconds
RATE_LIMIT_MAX = 100  # requests per window


def _check_rate_limit(ip: str) -> bool:
    """Check if IP is within rate limit.

    Returns True if request is allowed, False if rate limited.
    """
    now = time.time()

    # Clean old entries
    _rate_limits[ip] = [t for t in _rate_limits[ip] if now - t < RATE_LIMIT_WINDOW]

    # Check limit
    if len(_rate_limits[ip]) >= RATE_LIMIT_MAX:
        return False

    # Record this request
    _rate_limits[ip].append(now)
    return True


# =============================================================================
# MCP Models
# =============================================================================


class MCPToolCall(BaseModel):
    """MCP tool call from ElevenLabs."""

    tool_name: str = "kagami"
    tool_call_id: str = ""
    parameters: dict[str, Any] = {}
    conversation_id: str | None = None


class MCPToolResult(BaseModel):
    """MCP tool result."""

    tool_call_id: str
    result: str
    is_error: bool = False


# =============================================================================
# MCP Security
# =============================================================================


# Headers that contain sensitive data and must be redacted in logs
_SENSITIVE_HEADERS = frozenset(
    {
        "authorization",
        "x-mcp-token",
        "x-api-key",
        "cookie",
        "set-cookie",
        "x-auth-token",
        "x-access-token",
        "x-refresh-token",
    }
)


def _redact_headers(headers: dict[str, str]) -> dict[str, str]:
    """Redact sensitive headers for safe logging.

    Args:
        headers: Dictionary of header name -> value.

    Returns:
        Copy of headers with sensitive values redacted.
    """
    redacted = {}
    for key, value in headers.items():
        if key.lower() in _SENSITIVE_HEADERS:
            # Show first 8 chars and length for debugging without exposing full token
            if len(value) > 8:
                redacted[key] = f"{value[:8]}...[REDACTED, len={len(value)}]"
            else:
                redacted[key] = "[REDACTED]"
        else:
            redacted[key] = value
    return redacted


def _verify_mcp_token(request: Request) -> bool:
    """Verify MCP request has valid token.

    Checks:
    1. Authorization header (Bearer token)
    2. X-MCP-Token header
    3. Query param ?token=

    Security:
    - Sensitive headers are redacted before logging
    - Token values are never logged in full
    """
    from kagami.core.security import get_secret

    expected_token = get_secret("elevenlabs_mcp_token")
    if not expected_token:
        logger.warning("No MCP token configured - allowing request")
        return True

    # Get all possible token sources
    auth_header = request.headers.get("Authorization", "")
    mcp_token = request.headers.get("X-MCP-Token", "")
    token_param = request.query_params.get("token", "")

    # Log headers with sensitive values redacted
    all_headers = dict(request.headers)
    redacted_headers = _redact_headers(all_headers)
    logger.debug(f"MCP Request Headers (redacted): {redacted_headers}")

    # Normalize expected token (remove Bearer prefix if present)
    expected_raw = expected_token[7:] if expected_token.startswith("Bearer ") else expected_token

    # Check Authorization header
    if auth_header:
        received_token = auth_header

        # Strip "Bearer " prefix (possibly multiple times for double-Bearer bug)
        while received_token.startswith("Bearer "):
            received_token = received_token[7:].strip()

        # Compare normalized tokens using constant-time comparison
        if hmac.compare_digest(received_token, expected_raw):
            logger.info("MCP auth successful")
            return True
        if hmac.compare_digest(received_token, expected_token):
            logger.info("MCP auth successful")
            return True

    # Check X-MCP-Token header
    if mcp_token:
        if hmac.compare_digest(mcp_token, expected_raw) or hmac.compare_digest(
            mcp_token, expected_token
        ):
            logger.info("MCP auth successful via X-MCP-Token")
            return True

    # Check query param
    if token_param:
        if hmac.compare_digest(token_param, expected_raw) or hmac.compare_digest(
            token_param, expected_token
        ):
            logger.info("MCP auth successful via query param")
            return True

    logger.warning("MCP token validation failed")

    return False


# =============================================================================
# MCP Endpoints (for ElevenLabs MCP Server integration)
# =============================================================================


@router.post("/mcp/execute")
async def mcp_execute(request: Request) -> dict:
    """MCP Protocol Handler for ElevenLabs.

    Implements JSON-RPC 2.0 MCP protocol:
    - initialize: Handshake
    - tools/list: List available tools
    - tools/call: Execute a tool

    Security:
    - Token authentication (Bearer / X-MCP-Token / query param)
    - Rate limiting (100 req/min per IP)
    """
    import json

    from kagami.core.services.voice.mcp_server import execute_command

    client_ip = request.client.host if request.client else "unknown"

    # Rate limiting
    if not _check_rate_limit(client_ip):
        logger.warning(f"🚫 Rate limit exceeded for {client_ip}")
        return {
            "jsonrpc": "2.0",
            "error": {"code": -32000, "message": "Rate limit exceeded"},
            "id": None,
        }

    # Verify authentication
    if not _verify_mcp_token(request):
        logger.warning(f"🚫 MCP auth failed from {client_ip}")
        return {
            "jsonrpc": "2.0",
            "error": {"code": -32001, "message": "Authentication failed"},
            "id": None,
        }

    # Parse JSON-RPC request
    body = await request.body()
    body_str = body.decode()
    logger.info(f"🔧 MCP Request: {body_str[:500]}")

    try:
        data = json.loads(body_str)
    except json.JSONDecodeError:
        return {"jsonrpc": "2.0", "error": {"code": -32700, "message": "Parse error"}, "id": None}

    method = data.get("method", "")
    params = data.get("params", {})
    request_id = data.get("id", 0)

    logger.info(f"🔧 MCP Method: {method}")

    # Handle MCP methods
    if method == "initialize":
        # Respond to initialize handshake
        return {
            "jsonrpc": "2.0",
            "id": request_id,
            "result": {
                "protocolVersion": "2025-03-26",
                "capabilities": {"tools": {}},
                "serverInfo": {"name": "kagami", "version": "1.0.0"},
            },
        }

    elif method == "tools/list":
        # Return available tools
        return {
            "jsonrpc": "2.0",
            "id": request_id,
            "result": {
                "tools": [
                    {
                        "name": "kagami",
                        "description": "Execute Kagami smart home and digital commands. Use natural language like 'turn on lights', 'movie mode', 'check email'.",
                        "inputSchema": {
                            "type": "object",
                            "properties": {
                                "command": {
                                    "type": "string",
                                    "description": "Natural language command",
                                }
                            },
                            "required": ["command"],
                        },
                    }
                ]
            },
        }

    elif method == "tools/call":
        # Execute a tool
        tool_name = params.get("name", "")
        arguments = params.get("arguments", {})

        logger.info(f"🔧 Tool call: {tool_name} with {arguments}")

        if tool_name != "kagami":
            return {
                "jsonrpc": "2.0",
                "id": request_id,
                "error": {"code": -32602, "message": f"Unknown tool: {tool_name}"},
            }

        command = arguments.get("command", "")
        if not command:
            return {
                "jsonrpc": "2.0",
                "id": request_id,
                "result": {
                    "content": [{"type": "text", "text": "No command provided"}],
                    "isError": True,
                },
            }

        try:
            result = await execute_command(command)
            logger.info(f"✅ MCP result: {result}")

            return {
                "jsonrpc": "2.0",
                "id": request_id,
                "result": {"content": [{"type": "text", "text": result}], "isError": False},
            }
        except Exception as e:
            logger.error(f"MCP error: {e}")
            return {
                "jsonrpc": "2.0",
                "id": request_id,
                "result": {"content": [{"type": "text", "text": f"Error: {e}"}], "isError": True},
            }

    else:
        # Unknown method
        return {
            "jsonrpc": "2.0",
            "id": request_id,
            "error": {"code": -32601, "message": f"Method not found: {method}"},
        }


@router.get("/mcp/capabilities")
async def mcp_capabilities() -> dict:
    """List MCP capabilities for ElevenLabs configuration."""
    return {
        "name": "kagami",
        "description": "Kagami smart home and digital assistant",
        "version": "1.0.0",
        "tools": [
            {
                "name": "kagami",
                "description": "Execute a Kagami command. Use for ALL smart home control and digital tasks.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "command": {
                            "type": "string",
                            "description": "Natural language command (e.g., 'set lights to 50%', 'movie mode', 'turn on fireplace')",
                        }
                    },
                    "required": ["command"],
                },
            }
        ],
        "examples": [
            "set lights to 50% in living room",
            "turn on fireplace",
            "movie mode",
            "goodnight",
            "open shades",
            "lower TV",
            "play focus playlist",
        ],
    }


@router.get("/mcp/health")
async def mcp_health() -> dict:
    """MCP health check."""
    return {
        "status": "ok",
        "service": "kagami-mcp",
        "timestamp": datetime.now().isoformat(),
    }


@router.get("/mcp/tasks")
async def mcp_tasks() -> dict:
    """Get all running Ralph tasks."""
    from kagami.core.services.voice.mcp_server import get_running_tasks

    return {
        "tasks": get_running_tasks(),
        "timestamp": datetime.now().isoformat(),
    }


@router.get("/mcp/tasks/{task_id}")
async def mcp_task_status(task_id: str) -> dict:
    """Get status of a specific Ralph task."""
    from kagami.core.services.voice.mcp_server import get_task_status

    task = get_task_status(task_id)
    if not task:
        return {"error": "Task not found", "task_id": task_id}

    return {"task": task}


# =============================================================================
# Twilio Endpoints
# =============================================================================


@router.post("/incoming")
async def voice_incoming(request: Request) -> Response:
    """Handle incoming Twilio call.

    Returns TwiML to connect the call to our WebSocket endpoint
    for bidirectional ElevenLabs ConvAI conversation.
    """
    # Get form data from Twilio
    form = await request.form()
    caller = form.get("From", "Unknown")
    to = form.get("To", "Unknown")
    call_sid = form.get("CallSid", "Unknown")

    logger.info(f"📞 Incoming call: {caller} → {to} (SID: {call_sid})")

    # Get the WebSocket URL for Media Streams
    # Use the same host as the incoming request
    host = request.headers.get("host", "localhost:8000")

    # Check for ngrok URL in environment or use host
    ngrok_url = os.environ.get("NGROK_URL", "")
    if ngrok_url:
        ws_host = ngrok_url.replace("https://", "").replace("http://", "")
    else:
        ws_host = host

    ws_url = f"wss://{ws_host}/ws/voice/twilio"

    logger.info(f"🔗 Connecting to WebSocket: {ws_url}")

    # Return TwiML to connect Media Streams
    twiml = f'''<?xml version="1.0" encoding="UTF-8"?>
<Response>
    <Connect>
        <Stream url="{ws_url}">
            <Parameter name="caller" value="{caller}"/>
            <Parameter name="call_sid" value="{call_sid}"/>
        </Stream>
    </Connect>
</Response>'''

    return Response(content=twiml, media_type="application/xml")


@router.post("/status")
async def voice_status(request: Request) -> Response:
    """Handle Twilio call status webhook."""
    form = await request.form()
    call_sid = form.get("CallSid", "Unknown")
    status = form.get("CallStatus", "Unknown")

    logger.info(f"📞 Call status: {call_sid} → {status}")

    return Response(content="OK", media_type="text/plain")


@router.post("/recording-status")
async def recording_status(request: Request) -> Response:
    """Handle Twilio recording status webhook.

    Called when a call recording is complete.
    Downloads and saves the recording.
    """
    from pathlib import Path

    import aiohttp

    form = await request.form()
    recording_url = form.get("RecordingUrl", "")
    recording_sid = form.get("RecordingSid", "Unknown")
    call_sid = form.get("CallSid", "Unknown")
    recording_status = form.get("RecordingStatus", "Unknown")
    duration = form.get("RecordingDuration", "0")

    logger.info(f"🎙️ Recording status: {recording_sid} → {recording_status}")
    logger.info(f"   Call: {call_sid}, Duration: {duration}s")
    logger.info(f"   URL: {recording_url}")

    if recording_status == "completed" and recording_url:
        # Download the recording
        try:
            from kagami.core.security import get_secret

            account_sid = get_secret("twilio_account_sid")
            auth_token = get_secret("twilio_auth_token")

            # Add .mp3 to get MP3 format
            mp3_url = f"{recording_url}.mp3"

            async with aiohttp.ClientSession() as session:
                auth = aiohttp.BasicAuth(account_sid, auth_token)
                async with session.get(mp3_url, auth=auth) as resp:
                    if resp.status == 200:
                        # Save to recordings directory
                        recordings_dir = Path.home() / ".kagami" / "recordings"
                        recordings_dir.mkdir(parents=True, exist_ok=True)

                        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                        filename = f"call_{timestamp}_{recording_sid}.mp3"
                        filepath = recordings_dir / filename

                        audio_data = await resp.read()
                        filepath.write_bytes(audio_data)

                        logger.info(f"✅ Recording saved: {filepath}")
                        logger.info(f"   Size: {len(audio_data) / 1024:.1f} KB")
                    else:
                        logger.error(f"Failed to download recording: HTTP {resp.status}")

        except Exception as e:
            logger.error(f"Error saving recording: {e}")

    return Response(content="OK", media_type="text/plain")
