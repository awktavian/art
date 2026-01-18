from __future__ import annotations

"""K os CLI

Features:
- status: quick API health check
- send: send a command text over WebSocket
- lang: preview Intent LANG over WebSocket
"""
import argparse
import asyncio
import contextlib
import json
import os
import time
import uuid
from typing import Any

try:
    from fastapi import FastAPI as _FastAPI
except (ImportError, ModuleNotFoundError):  # pragma: no cover - import-time fallback
    # FastAPI not installed, provide fallback type
    _FastAPI = object  # type: ignore

import aiohttp
import httpx

# Expose FastAPI app for tests/integrations expecting `from kagami.main import app`
try:  # pragma: no cover - simple import surface
    from kagami_api import create_app as _create_app

    app: _FastAPI | None = _create_app()
except (ImportError, ModuleNotFoundError, AttributeError, RuntimeError) as e:
    # ImportError/ModuleNotFoundError: kagami_api module unavailable
    # AttributeError: create_app function missing
    # RuntimeError: app creation failed
    import logging

    logging.getLogger(__name__).debug(f"FastAPI app creation unavailable: {e}")
    app = None


def http_to_ws(http_url: str) -> str:
    if http_url.startswith("https://"):
        return "wss://" + http_url[len("https://") :].rstrip("/")
    if http_url.startswith("http://"):
        return "ws://" + http_url[len("http://") :].rstrip("/")
    return "ws://" + http_url.rstrip("/")


async def fetch_status(api_base: str) -> dict[str, Any]:
    url = api_base.rstrip("/") + "/health"
    async with httpx.AsyncClient(timeout=5.0) as client:
        r = await client.get(url)
        r.raise_for_status()
        result = r.json()
        return result if isinstance(result, dict) else {}


async def ws_connect_and_auth(
    session: aiohttp.ClientSession, ws_url: str, api_key: str, client_id: str
) -> aiohttp.ClientWebSocketResponse:
    # Use default aiohttp websocket connect timeout behavior. (Some aiohttp versions
    # expose `ClientWSTimeout`, but its stubs can be inconsistent across versions.)
    ws = await session.ws_connect(ws_url)
    await ws.send_json({"type": "auth", "api_key": api_key})
    try:
        msg = await ws.receive(timeout=2.0)
        if msg.type == aiohttp.WSMsgType.TEXT:
            _ = json.loads(msg.data)
    except (TimeoutError, json.JSONDecodeError, KeyError) as e:
        # TimeoutError: auth response not received in time
        # json.JSONDecodeError: invalid JSON in auth response
        # KeyError: msg.data missing
        import logging

        logging.getLogger(__name__).debug(f"WebSocket auth response failed: {e}")
    return ws


async def send_command(api_base: str, api_key: str, text: str) -> int:
    ws_base = http_to_ws(api_base)
    client_id = f"cli-{uuid.uuid4().hex[:8]}"
    ws_url = f"{ws_base}/ws/{client_id}"
    async with aiohttp.ClientSession() as session:
        try:
            ws = await ws_connect_and_auth(session, ws_url, api_key, client_id)
            await ws.send_json({"type": "command", "text": text})
            deadline = time.time() + 8.0
            wanted = {"response", "progress", "error"}
            while time.time() < deadline:
                msg = await ws.receive(timeout=2.0)
                if msg.type == aiohttp.WSMsgType.TEXT:
                    data = json.loads(msg.data)
                    mtype = data.get("type")
                    if mtype == "response":
                        print(json.dumps(data.get("response"), ensure_ascii=False, indent=2))
                        return 0
                    if mtype in wanted:
                        print(json.dumps(data, ensure_ascii=False))
                        continue
            print(json.dumps({"type": "timeout", "message": "No final response in 8s"}))
            return 1
        except Exception as e:
            print(f"send failed: {e}")
            return 2
        finally:
            with contextlib.suppress(Exception):
                await ws.close()


async def send_lang(api_base: str, api_key: str, lang: str) -> int:
    try:
        async with httpx.AsyncClient(timeout=5.0) as client:
            r = await client.post(
                api_base.rstrip("/") + "/api/command/parse",
                json={"lang": lang},
                headers={"Authorization": f"Bearer {api_key}"} if api_key else None,
            )
            r.raise_for_status()
            data = r.json() or {}
            print(json.dumps(data.get("intent") or {}, ensure_ascii=False, indent=2))
            return 0
    except (httpx.HTTPError, httpx.TimeoutException, json.JSONDecodeError) as e:
        # httpx.HTTPError: HTTP request failed (network, status, etc.)
        # httpx.TimeoutException: request timed out
        # json.JSONDecodeError: invalid JSON response
        import logging

        logging.getLogger(__name__).debug(f"HTTP command parse failed: {e}")
    # Fallback to WebSocket if HTTP fails
    ws_base = http_to_ws(api_base)
    client_id = f"cli-{uuid.uuid4().hex[:8]}"
    ws_url = f"{ws_base}/ws/{client_id}"
    async with aiohttp.ClientSession() as session:
        try:
            ws = await ws_connect_and_auth(session, ws_url, api_key, client_id)
            await ws.send_json({"type": "intent_lang", "lang": lang, "text": lang})
            deadline = time.time() + 5.0
            while time.time() < deadline:
                msg = await ws.receive(timeout=2.0)
                if msg.type == aiohttp.WSMsgType.TEXT:
                    data = json.loads(msg.data)
                    if data.get("type") == "intent_preview":
                        print(json.dumps(data.get("intent"), ensure_ascii=False, indent=2))
                        return 0
                    if data.get("type") == "error":
                        print(json.dumps(data, ensure_ascii=False))
                        return 1
        except Exception as e:
            print(f"lang failed: {e}")
            return 2
        finally:
            with contextlib.suppress(Exception):
                await ws.close()
    # If we exit the loop without returning, no result was received
    return 1


def main(argv: list[str] | None = None) -> int:
    parent = argparse.ArgumentParser(add_help=False)
    parent.add_argument(
        "--url",
        default=(
            os.getenv("KAGAMI_API_BASE")
            or os.getenv("KAGAMI_PUBLIC_URL")
            or "http://127.0.0.1:8001"  # FIX: Match safe API default port
        ),
        help="API base URL",
    )
    parent.add_argument("--api-key", default=os.getenv("KAGAMI_API_KEY", ""))

    parser = argparse.ArgumentParser(prog="kagami", description="K os CLI", parents=[parent])
    sub = parser.add_subparsers(dest="cmd", required=False)
    sub.add_parser("status", help="Check API health", parents=[parent])
    p_send = sub.add_parser("send", help="Send command", parents=[parent])
    p_send.add_argument("text")
    p_lang = sub.add_parser("lang", help="Preview LANG", parents=[parent])
    p_lang.add_argument("lang")
    p_rcp = sub.add_parser("receipt", help="Get receipt by correlation id", parents=[parent])
    p_rcp.add_argument("correlation_id")
    p_tail = sub.add_parser(
        "receipts-tail",
        help="Tail recent receipts (server scans JSONL/DB)",
        parents=[parent],
    )
    p_tail.add_argument("--limit", type=int, default=20)

    args = parser.parse_args(argv)
    api_base = (
        str(getattr(args, "url", "")) or "http://127.0.0.1:8001"
    )  # FIX: Match safe API default port
    api_key = str(getattr(args, "api_key", ""))

    if not args.cmd or args.cmd == "help":
        parser.print_help()
        return 0
    if args.cmd == "status":
        try:
            status = asyncio.run(fetch_status(api_base))
            print(json.dumps(status, ensure_ascii=False, indent=2))
            return 0
        except Exception as e:
            print(f"health failed: {e}")
            return 2
    if args.cmd == "send":
        return asyncio.run(send_command(api_base, api_key, args.text))
    if args.cmd == "lang":
        return asyncio.run(send_lang(api_base, api_key, args.lang))
    if args.cmd == "receipt":
        try:
            import httpx

            url = api_base.rstrip("/") + f"/api/receipts/{args.correlation_id}"
            headers = {"Authorization": f"Bearer {api_key}"} if api_key else {}
            r = asyncio.run(httpx.AsyncClient(timeout=5.0).get(url, headers=headers))
            if hasattr(r, "raise_for_status"):
                r.raise_for_status()
            body = r.json()
            print(json.dumps(body, ensure_ascii=False, indent=2))
            return 0
        except Exception as e:
            print(f"receipt fetch failed: {e}")
            return 2
    if args.cmd == "receipts-tail":
        try:
            import httpx

            url = (
                api_base.rstrip("/")
                + f"/api/receipts/search?limit={int(getattr(args, 'limit', 20) or 20)}"
            )
            headers = {"Authorization": f"Bearer {api_key}"} if api_key else {}
            r = asyncio.run(httpx.AsyncClient(timeout=8.0).get(url, headers=headers))
            if hasattr(r, "raise_for_status"):
                r.raise_for_status()
            body = r.json()
            print(json.dumps(body, ensure_ascii=False, indent=2))
            return 0
        except Exception as e:
            print(f"receipts tail failed: {e}")
            return 2
    print("Unknown command")
    return 2


if __name__ == "__main__":
    raise SystemExit(main()) from None
