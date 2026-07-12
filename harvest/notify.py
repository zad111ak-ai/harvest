"""
Notifications — Send harvest results to Telegram, email, or webhooks.

The killer feature: monitor changes and get alerted in real-time.
Like Browse AI Pro ($50/mo) — free.

Usage:
    harvest monitor https://site.com --notify telegram --token ... --chat ...
    harvest monitor https://site.com --notify webhook --url https://hook.n8n.io/...
"""
import json
import logging
from typing import Any, Optional

logger = logging.getLogger("harvest.notify")


class Notifier:
    """Send notifications through various channels."""

    @staticmethod
    def create(channel: str, **kwargs) -> "Notifier":
        channel_map = {
            "telegram": TelegramNotifier,
            "webhook": WebhookNotifier,
            "stdout": StdoutNotifier,
        }
        cls = channel_map.get(channel.lower())
        if not cls:
            raise ValueError(f"Unknown channel: {channel}. Options: {list(channel_map.keys())}")
        return cls(**kwargs)

    async def send(self, message: str, **kwargs):
        raise NotImplementedError


class TelegramNotifier(Notifier):
    """Send notifications via Telegram Bot API."""

    def __init__(self, token: str = "", chat_id: str = ""):
        self.token = token
        self.chat_id = chat_id

    async def send(self, message: str, **kwargs):
        """Send a Telegram message."""
        import aiohttp

        if not self.token or not self.chat_id:
            logger.warning("Telegram not configured. Use --token and --chat")
            return False

        # Parse message length (Telegram limit is 4096)
        max_len = 4000
        if len(message) > max_len:
            message = message[:max_len] + "\n\n...(truncated)"

        url = f"https://api.telegram.org/bot{self.token}/sendMessage"
        payload = {
            "chat_id": self.chat_id,
            "text": message,
            "parse_mode": "HTML",
            "disable_web_page_preview": True,
        }

        try:
            async with aiohttp.ClientSession() as session:
                async with session.post(url, json=payload, timeout=15) as resp:
                    if resp.status != 200:
                        logger.error(f"Telegram API error: {resp.status}")
                        # Try without parse_mode
                        payload["parse_mode"] = ""
                        async with session.post(url, json=payload, timeout=15) as resp2:
                            return resp2.status == 200
                    return True
        except Exception as e:
            logger.error(f"Telegram send failed: {e}")
            return False


class WebhookNotifier(Notifier):
    """Send notifications to an HTTP webhook (n8n, Make, Zapier)."""

    def __init__(self, url: str = ""):
        self.url = url

    async def send(self, message: str, payload: Optional[dict] = None, **kwargs):
        """POST to webhook URL."""
        import aiohttp

        if not self.url:
            logger.warning("Webhook URL not configured")
            return False

        data = {
            "message": message,
            "payload": payload or {},
        }

        try:
            async with aiohttp.ClientSession() as session:
                async with session.post(self.url, json=data, timeout=15) as resp:
                    return resp.status < 400
        except Exception as e:
            logger.error(f"Webhook failed: {e}")
            return False


class StdoutNotifier(Notifier):
    """Print notification to stdout (default)."""

    async def send(self, message: str, **kwargs):
        print(message)
        return True
