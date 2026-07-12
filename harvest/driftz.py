"""Driftz — Temporary Email integration for Harvest.

Access disposable inboxes via https://driftz.net public API.
No auth required. No registration.

Usage:
    from harvest.driftz import DriftzMail
    dm = DriftzMail()
    emails = await dm.get_inbox("user@example.com")
    email = await dm.read_email("user@example.com", "email_id")
"""

import asyncio
import re
from typing import Optional
import httpx


class DriftzMail:
    """Temporary email client via api.driftz.net."""

    BASE_URL = "https://api.driftz.net"

    def __init__(self, proxy: Optional[str] = None, timeout: int = 30):
        self.proxy = proxy
        self.timeout = timeout
        self._client: Optional[httpx.AsyncClient] = None

    @property
    def client(self) -> httpx.AsyncClient:
        if self._client is None:
            kwargs = {"timeout": self.timeout, "headers": {"User-Agent": "Harvest/0.4"}}
            if self.proxy:
                kwargs["proxies"] = {"http://": self.proxy, "https://": self.proxy}
            self._client = httpx.AsyncClient(**kwargs)
        return self._client

    async def close(self):
        if self._client:
            await self._client.aclose()
            self._client = None

    async def get_inbox(self, email: str, limit: int = 15) -> list[dict]:
        """Get list of emails in an inbox."""
        resp = await self.client.get(
            f"{self.BASE_URL}/emails/{email}",
            params={"limit": limit},
        )
        data = resp.json()
        if not data.get("success"):
            raise RuntimeError(f"Driftz API error: {data.get('error', 'unknown')}")
        return data.get("result", {}).get("items", [])

    async def read_email(self, email: str, email_id: str) -> dict:
        """Read full content of a specific email."""
        resp = await self.client.get(
            f"{self.BASE_URL}/emails/{email}/{email_id}",
        )
        data = resp.json()
        if not data.get("success"):
            raise RuntimeError(f"Driftz API error: {data.get('error', 'unknown')}")
        return data.get("result", {})

    async def get_attachments(self, email: str, email_id: str, attachment_id: str) -> bytes:
        """Download an attachment from an email."""
        resp = await self.client.get(
            f"{self.BASE_URL}/emails/{email}/{email_id}/attachments/{attachment_id}",
        )
        resp.raise_for_status()
        return resp.content

    def parse_code_from_email(self, email_text: str) -> Optional[str]:
        """Extract verification code from email text."""
        # Common patterns: "CODE: 123456", "code is 123456", "123-456"
        patterns = [
            r"(?:code|verification|otp|pin)[:\s]*([A-Z0-9]{4,10})",
            r"(?<!\w)(\d{4,8})(?!\w)",
            r"([A-Z0-9]{6,8})(?:\s|$)",
        ]
        for pat in patterns:
            m = re.search(pat, email_text, re.IGNORECASE)
            if m:
                return m.group(1)
        return None

    async def wait_for_email(
        self, email: str, subject_filter: str = "", timeout: int = 120, poll: int = 5
    ) -> Optional[dict]:
        """Poll inbox until email matching subject_filter arrives."""

        deadline = asyncio.get_event_loop().time() + timeout
        while asyncio.get_event_loop().time() < deadline:
            emails = await self.get_inbox(email)
            for e in emails:
                if subject_filter and subject_filter.lower() in e.get("subject", "").lower():
                    return e
                if not subject_filter and emails:
                    return emails[0]
            await asyncio.sleep(poll)
        return None
