"""Captcha Solving Service.

Integrates with captcha solving services to bypass anti-bot protection.

Supported Services:
- 2captcha (recommended): https://2captcha.com
- Anti-Captcha: https://anti-captcha.com
- CapSolver: https://capsolver.com

Cost: ~$2-3 per 1000 solves

Usage:
    from kagami.core.services.captcha import get_captcha_service

    captcha = get_captcha_service()
    token = await captcha.solve_hcaptcha(
        site_key="...",
        site_url="https://example.com"
    )
"""

from __future__ import annotations

import asyncio
import logging
import os
from dataclasses import dataclass
from enum import Enum
from typing import Any

import aiohttp

logger = logging.getLogger(__name__)


class CaptchaProvider(str, Enum):
    """Supported captcha solving providers."""

    TWOCAPTCHA = "2captcha"
    ANTICAPTCHA = "anticaptcha"
    CAPSOLVER = "capsolver"


@dataclass
class CaptchaConfig:
    """Captcha service configuration."""

    provider: CaptchaProvider = CaptchaProvider.TWOCAPTCHA
    api_key: str | None = None
    poll_interval: float = 5.0
    max_wait_time: float = 120.0

    def __post_init__(self):
        if not self.api_key:
            # Try to get from environment first
            self.api_key = os.getenv("TWOCAPTCHA_API_KEY") or os.getenv("CAPTCHA_API_KEY")

        if not self.api_key:
            # Try to get from macOS Keychain
            try:
                import subprocess

                result = subprocess.run(
                    [
                        "security",
                        "find-generic-password",
                        "-a",
                        "kagami",
                        "-s",
                        "twocaptcha-api-key",
                        "-w",
                    ],
                    capture_output=True,
                    text=True,
                )
                if result.returncode == 0:
                    self.api_key = result.stdout.strip()
            except Exception:
                pass  # Keychain not available or key not found


class CaptchaService:
    """Unified captcha solving service.

    Supports multiple backends with a common interface.
    """

    # Provider-specific API endpoints
    ENDPOINTS = {
        CaptchaProvider.TWOCAPTCHA: {
            "submit": "https://2captcha.com/in.php",
            "result": "https://2captcha.com/res.php",
        },
        CaptchaProvider.ANTICAPTCHA: {
            "submit": "https://api.anti-captcha.com/createTask",
            "result": "https://api.anti-captcha.com/getTaskResult",
        },
        CaptchaProvider.CAPSOLVER: {
            "submit": "https://api.capsolver.com/createTask",
            "result": "https://api.capsolver.com/getTaskResult",
        },
    }

    def __init__(self, config: CaptchaConfig | None = None):
        self.config = config or CaptchaConfig()
        self._session: aiohttp.ClientSession | None = None

    async def _get_session(self) -> aiohttp.ClientSession:
        if self._session is None:
            self._session = aiohttp.ClientSession()
        return self._session

    async def solve_hcaptcha(
        self,
        site_key: str,
        site_url: str,
        invisible: bool = False,
    ) -> str:
        """Solve an hCaptcha challenge.

        Args:
            site_key: hCaptcha site key
            site_url: URL where captcha appears
            invisible: Whether the hCaptcha is invisible

        Returns:
            Captcha token (P1_...)

        Raises:
            Exception: If solving fails or times out

        Note:
            Some 2captcha accounts may not have hCaptcha enabled.
            If you get ERROR_METHOD_CALL, check your 2captcha dashboard
            or try Anti-Captcha/CapSolver instead.
        """
        if not self.config.api_key:
            raise Exception(
                "No captcha API key configured. "
                "Set TWOCAPTCHA_API_KEY or CAPTCHA_API_KEY environment variable."
            )

        # Try configured provider first, fall back to others if hCaptcha not supported
        providers_to_try = [self.config.provider]
        if self.config.provider == CaptchaProvider.TWOCAPTCHA:
            # 2captcha may not support hCaptcha on all accounts
            providers_to_try.extend([CaptchaProvider.ANTICAPTCHA, CaptchaProvider.CAPSOLVER])

        last_error = None
        for provider in providers_to_try:
            try:
                if provider == CaptchaProvider.TWOCAPTCHA:
                    return await self._solve_2captcha_hcaptcha(site_key, site_url, invisible)
                elif provider == CaptchaProvider.ANTICAPTCHA:
                    return await self._solve_anticaptcha_hcaptcha(site_key, site_url)
                elif provider == CaptchaProvider.CAPSOLVER:
                    return await self._solve_capsolver_hcaptcha(site_key, site_url)
            except Exception as e:
                last_error = e
                if "ERROR_METHOD_CALL" in str(e):
                    logger.warning(f"{provider.value} doesn't support hCaptcha, trying next...")
                    continue
                raise

        raise Exception(
            f"All providers failed to solve hCaptcha. Last error: {last_error}. "
            "Note: hCaptcha may require special account permissions or enterprise support."
        )

    async def _solve_2captcha_hcaptcha(
        self, site_key: str, site_url: str, invisible: bool = False
    ) -> str:
        """Solve hCaptcha using 2captcha JSON API."""
        session = await self._get_session()

        # Use the JSON API endpoint instead of legacy in.php
        submit_url = "https://api.2captcha.com/createTask"

        task: dict[str, Any] = {
            "type": "HCaptchaTaskProxyless",
            "websiteURL": site_url,
            "websiteKey": site_key,
        }
        if invisible:
            task["isInvisible"] = True

        submit_data = {
            "clientKey": self.config.api_key,
            "task": task,
        }

        async with session.post(submit_url, json=submit_data) as resp:
            data = await resp.json()
            if data.get("errorId") != 0:
                # Fall back to legacy API
                logger.debug(f"JSON API failed: {data}, trying legacy API")
                return await self._solve_2captcha_hcaptcha_legacy(site_key, site_url)
            task_id = data["taskId"]

        logger.info(f"2captcha task submitted: {task_id}")

        # Poll for result using JSON API
        result_url = "https://api.2captcha.com/getTaskResult"
        result_data = {
            "clientKey": self.config.api_key,
            "taskId": task_id,
        }

        start_time = asyncio.get_event_loop().time()
        while True:
            elapsed = asyncio.get_event_loop().time() - start_time
            if elapsed > self.config.max_wait_time:
                raise TimeoutError(f"Captcha solving timed out after {elapsed:.0f}s")

            await asyncio.sleep(self.config.poll_interval)

            async with session.post(result_url, json=result_data) as resp:
                data = await resp.json()

                if data.get("status") == "ready":
                    token = data["solution"]["gRecaptchaResponse"]
                    logger.info(f"Captcha solved in {elapsed:.1f}s")
                    return token
                elif data.get("status") == "processing":
                    continue
                elif data.get("errorId") != 0:
                    raise Exception(f"2captcha error: {data}")

    async def _solve_2captcha_hcaptcha_legacy(self, site_key: str, site_url: str) -> str:
        """Legacy 2captcha API for hCaptcha (fallback)."""
        session = await self._get_session()

        # Submit task using legacy GET API
        submit_params = {
            "key": self.config.api_key,
            "method": "hcaptcha",
            "sitekey": site_key,
            "pageurl": site_url,
            "json": "1",
        }

        async with session.get("https://2captcha.com/in.php", params=submit_params) as resp:
            data = await resp.json()
            if data.get("status") != 1:
                raise Exception(f"2captcha legacy submit failed: {data}")
            task_id = data["request"]

        logger.info(f"2captcha legacy task submitted: {task_id}")

        # Poll for result
        result_params = {
            "key": self.config.api_key,
            "action": "get",
            "id": task_id,
            "json": "1",
        }

        start_time = asyncio.get_event_loop().time()
        while True:
            elapsed = asyncio.get_event_loop().time() - start_time
            if elapsed > self.config.max_wait_time:
                raise TimeoutError(f"Captcha solving timed out after {elapsed:.0f}s")

            await asyncio.sleep(self.config.poll_interval)

            async with session.get("https://2captcha.com/res.php", params=result_params) as resp:
                data = await resp.json()

                if data.get("status") == 1:
                    token = data["request"]
                    logger.info(f"Captcha solved in {elapsed:.1f}s (legacy)")
                    return token
                elif data.get("request") == "CAPCHA_NOT_READY":
                    continue
                else:
                    raise Exception(f"2captcha legacy error: {data}")

    async def _solve_anticaptcha_hcaptcha(self, site_key: str, site_url: str) -> str:
        """Solve hCaptcha using Anti-Captcha."""
        session = await self._get_session()
        endpoints = self.ENDPOINTS[CaptchaProvider.ANTICAPTCHA]

        # Submit task
        submit_data = {
            "clientKey": self.config.api_key,
            "task": {
                "type": "HCaptchaTaskProxyless",
                "websiteURL": site_url,
                "websiteKey": site_key,
            },
        }

        async with session.post(endpoints["submit"], json=submit_data) as resp:
            data = await resp.json()
            if data.get("errorId") != 0:
                raise Exception(f"Anti-Captcha submit failed: {data}")
            task_id = data["taskId"]

        logger.info(f"Anti-Captcha task submitted: {task_id}")

        # Poll for result
        result_data = {
            "clientKey": self.config.api_key,
            "taskId": task_id,
        }

        start_time = asyncio.get_event_loop().time()
        while True:
            elapsed = asyncio.get_event_loop().time() - start_time
            if elapsed > self.config.max_wait_time:
                raise TimeoutError(f"Captcha solving timed out after {elapsed:.0f}s")

            await asyncio.sleep(self.config.poll_interval)

            async with session.post(endpoints["result"], json=result_data) as resp:
                data = await resp.json()

                if data.get("status") == "ready":
                    token = data["solution"]["gRecaptchaResponse"]
                    logger.info(f"Captcha solved in {elapsed:.1f}s")
                    return token
                elif data.get("status") == "processing":
                    continue
                elif data.get("errorId") != 0:
                    raise Exception(f"Anti-Captcha error: {data}")

    async def _solve_capsolver_hcaptcha(self, site_key: str, site_url: str) -> str:
        """Solve hCaptcha using CapSolver."""
        session = await self._get_session()
        endpoints = self.ENDPOINTS[CaptchaProvider.CAPSOLVER]

        # Submit task
        submit_data = {
            "clientKey": self.config.api_key,
            "task": {
                "type": "HCaptchaTaskProxyLess",
                "websiteURL": site_url,
                "websiteKey": site_key,
            },
        }

        async with session.post(endpoints["submit"], json=submit_data) as resp:
            data = await resp.json()
            if data.get("errorId") != 0:
                raise Exception(f"CapSolver submit failed: {data}")
            task_id = data["taskId"]

        logger.info(f"CapSolver task submitted: {task_id}")

        # Poll for result
        result_data = {
            "clientKey": self.config.api_key,
            "taskId": task_id,
        }

        start_time = asyncio.get_event_loop().time()
        while True:
            elapsed = asyncio.get_event_loop().time() - start_time
            if elapsed > self.config.max_wait_time:
                raise TimeoutError(f"Captcha solving timed out after {elapsed:.0f}s")

            await asyncio.sleep(self.config.poll_interval)

            async with session.post(endpoints["result"], json=result_data) as resp:
                data = await resp.json()

                if data.get("status") == "ready":
                    token = data["solution"]["gRecaptchaResponse"]
                    logger.info(f"Captcha solved in {elapsed:.1f}s")
                    return token
                elif data.get("status") == "processing":
                    continue
                elif data.get("errorId") != 0:
                    raise Exception(f"CapSolver error: {data}")

    async def get_balance(self) -> float:
        """Get current account balance."""
        if not self.config.api_key:
            return 0.0

        session = await self._get_session()

        if self.config.provider == CaptchaProvider.TWOCAPTCHA:
            params = {
                "key": self.config.api_key,
                "action": "getbalance",
                "json": "1",
            }
            async with session.get(
                self.ENDPOINTS[CaptchaProvider.TWOCAPTCHA]["result"], params=params
            ) as resp:
                data = await resp.json()
                return float(data.get("request", 0))

        elif self.config.provider in (
            CaptchaProvider.ANTICAPTCHA,
            CaptchaProvider.CAPSOLVER,
        ):
            endpoint = (
                "https://api.anti-captcha.com/getBalance"
                if self.config.provider == CaptchaProvider.ANTICAPTCHA
                else "https://api.capsolver.com/getBalance"
            )
            async with session.post(endpoint, json={"clientKey": self.config.api_key}) as resp:
                data = await resp.json()
                return float(data.get("balance", 0))

        return 0.0

    async def close(self):
        """Close the session."""
        if self._session:
            await self._session.close()
            self._session = None


# Singleton
_captcha_service: CaptchaService | None = None


def get_captcha_service() -> CaptchaService:
    """Get the global captcha service singleton."""
    global _captcha_service
    if _captcha_service is None:
        _captcha_service = CaptchaService()
    return _captcha_service


__all__ = [
    "CaptchaConfig",
    "CaptchaProvider",
    "CaptchaService",
    "get_captcha_service",
]
