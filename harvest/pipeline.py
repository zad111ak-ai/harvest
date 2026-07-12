"""
Pipeline — Chain multiple harvest operations into one command.

Like Zapier / Make workflows, but local and free.

Usage:
    harvest pipeline "scrape https://shop.com | extract '{\"price\":\".price\"}' | export output.csv | notify telegram"
    harvest pipeline --file pipeline.yaml
"""

import json
from pathlib import Path
from typing import Any, Optional

from .core import Scraper
from .extract import SchemaExtractor, load_schema
from .crawl import SiteCrawler
from .contacts import ContactCollector
from .export import Exporter
from .notify import Notifier
from .config import Config


class Pipeline:
    """Run chained harvest operations.

    Each step feeds its output as input to the next step.
    """

    STEPS = {
        "scrape": "cmd_scrape",
        "extract": "cmd_extract",
        "crawl": "cmd_crawl",
        "contacts": "cmd_contacts",
        "export": "cmd_export",
        "notify": "cmd_notify",
        "filter": "cmd_filter",
        "sleep": "cmd_sleep",
        "loop": "cmd_loop",
    }

    def __init__(self, config: Optional[Config] = None):
        self.config = config or Config()
        self.scraper = Scraper(proxy=self.config.get("proxy", "url") or None)
        self.extractor = SchemaExtractor()
        self.crawler = SiteCrawler()
        self.collector = ContactCollector()
        self._results: list[dict] = []
        self._context: dict = {}

    async def run_pipeline(self, pipeline_def: str | dict | list) -> list[dict]:
        """Execute a pipeline definition.

        Accepts:
        - String: "scrape URL | extract SCHEMA | export FILE.csv"
        - Dict: {"steps": [{"cmd": "scrape", "url": "..."}, ...]}
        - List: [{"cmd": "scrape", "url": "..."}, ...]
        """
        steps = self._parse_pipeline(pipeline_def)

        for i, step in enumerate(steps):
            cmd = step.pop("cmd", step.pop("command", ""))
            fn_name = f"cmd_{cmd}"

            if not hasattr(self, fn_name):
                raise ValueError(f"Unknown pipeline step: {cmd}. Available: {list(self.STEPS.keys())}")

            fn = getattr(self, fn_name)
            result = await fn(**step)

            self._results.append(
                {
                    "step": i,
                    "command": cmd,
                    "result": result,
                }
            )
            self._context["last_result"] = result
            self._context["results"] = self._results

        return self._results

    def _parse_pipeline(self, pipeline_def: str | dict | list) -> list[dict]:
        """Parse pipeline definition into step dicts."""
        if isinstance(pipeline_def, dict):
            return pipeline_def.get("steps", [])
        if isinstance(pipeline_def, list):
            return pipeline_def
        if isinstance(pipeline_def, str):
            return self._parse_pipe_string(pipeline_def)
        return []

    def _parse_pipe_string(self, s: str) -> list[dict]:
        """Parse 'scrape URL | extract SCHEMA' into step dicts."""
        steps = []
        for part in s.split("|"):
            part = part.strip()
            if not part:
                continue

            # cmd arg1 arg2 ...
            tokens = self._smart_split(part)
            if not tokens:
                continue

            cmd = tokens[0]
            args = tokens[1:] if len(tokens) > 1 else []

            step = {"cmd": cmd}

            if cmd == "scrape":
                step["url"] = args[0] if args else self._context.get("url", "")
                if len(args) > 1:
                    step["selector"] = args[1]
            elif cmd == "extract":
                step["url"] = args[0] if args else self._context.get("url", "")
                if len(args) > 1:
                    step["schema"] = args[1]
            elif cmd == "crawl":
                step["url"] = args[0] if args else ""
                for arg in args[1:]:
                    if arg.startswith("--max-pages="):
                        step["max_pages"] = int(arg.split("=")[1])
                    elif arg.startswith("--delay="):
                        step["delay"] = float(arg.split("=")[1])
            elif cmd == "contacts":
                step["url"] = args[0] if args else ""
            elif cmd == "export":
                step["file"] = args[0] if args else "output.json"
                if len(args) > 1:
                    step["format"] = args[1]
            elif cmd == "notify":
                step["channel"] = args[0] if args else "stdout"
            elif cmd == "filter":
                step["expression"] = " ".join(args)
            elif cmd == "sleep":
                step["seconds"] = float(args[0]) if args else 1
            elif cmd == "loop":
                step["count"] = int(args[0]) if args else 3

            steps.append(step)

        return steps

    def _smart_split(self, s: str) -> list[str]:
        """Split string by spaces, respecting quoted strings."""
        parts = []
        current = ""
        in_quote = False
        quote_char = ""
        for ch in s:
            if in_quote:
                if ch == quote_char:
                    in_quote = False
                else:
                    current += ch
            elif ch in ("'", '"'):
                in_quote = True
                quote_char = ch
            elif ch == " ":
                if current:
                    parts.append(current)
                    current = ""
            else:
                current += ch
        if current:
            parts.append(current)
        return parts

    # ── Command handlers ──

    async def cmd_scrape(self, url: str, selector: Optional[str] = None, **kwargs) -> dict:
        return await self.scraper.scrape(url, selector=selector)

    async def cmd_extract(self, url: str, schema: str | dict, **kwargs) -> dict:
        if isinstance(schema, str):
            schema = load_schema(schema)
        return await self.extractor.extract(url, schema)

    async def cmd_crawl(self, url: str, max_pages: int = 50, delay: float = 0.5, **kwargs) -> dict:
        return await self.crawler.crawl(url, max_pages=max_pages, delay=delay)

    async def cmd_contacts(self, url: str, depth: int = 2, **kwargs) -> dict:
        return await self.collector.collect(url, depth=depth)

    async def cmd_export(
        self,
        file: str = "output.json",
        fmt: Optional[str] = None,
        **kwargs,
    ) -> dict:
        data = self._context.get("last_result", {})
        fmt = fmt or file.split(".")[-1] or "json"

        if fmt == "csv":
            output = Exporter.to_csv(data)
        else:
            output = json.dumps(data, indent=2, ensure_ascii=False)

        Path(file).write_text(output, encoding="utf-8")
        return {"file": file, "format": fmt, "size": len(output)}

    async def cmd_notify(
        self,
        channel: str = "stdout",
        token: str = "",
        chat_id: str = "",
        webhook_url: str = "",
        **kwargs,
    ) -> bool:
        token = token or self.config.get("notify", "telegram_token") or ""
        chat_id = chat_id or self.config.get("notify", "telegram_chat_id") or ""
        webhook_url = webhook_url or self.config.get("notify", "webhook_url") or ""

        notifier = Notifier.create(channel, token=token, chat_id=chat_id, url=webhook_url)
        message = json.dumps(self._context.get("last_result", {}), indent=2, ensure_ascii=False)
        return await notifier.send(message[:3000])

    async def cmd_filter(self, expression: str, **kwargs) -> Any:
        """Apply a simple filter expression to the last result.

        Expressions:
            field.subfield     — Get nested value
            field[0]           — Get first item in list
            field.subfield[0]  — Combined
        """
        data = self._context.get("last_result", {})
        parts = expression.split(".")
        current = data
        for part in parts:
            if "[" in part and part.endswith("]"):
                key = part[: part.index("[")]
                idx = int(part[part.index("[") + 1 : -1])
                current = current.get(key, []) if isinstance(current, dict) else current
                current = current[idx] if isinstance(current, list) and len(current) > idx else current
            else:
                current = current.get(part) if isinstance(current, dict) else current
        return current

    async def cmd_sleep(self, seconds: float = 1, **kwargs):
        import asyncio

        await asyncio.sleep(seconds)
        return {"slept": seconds}

    async def cmd_loop(self, count: int = 3, **kwargs):
        """Placeholder loop. For now just returns count info."""
        return {"loop_count": count, "note": "Define inner steps for actual looping"}
