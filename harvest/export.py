"""
Export — Convert Harvest results to CSV, XLSX, or other formats.

Usage:
    harvest scrape https://site.com --output csv
    harvest contacts https://site.com --export contacts.csv
    harvest crawl https://site.com --export crawl.csv
"""

import csv
import io
import json
from pathlib import Path
from typing import Any, Optional


class Exporter:
    """Export scraped data to various formats."""

    @staticmethod
    def to_csv(data: Any, output: Optional[str] = None) -> str:
        """Convert data to CSV.

        Handles:
        - list[dict] → each dict is a row
        - dict → single row
        - nested dicts → flattened keys
        """
        rows = Exporter._normalize(data)
        if not rows:
            return ""

        # Collect all keys
        all_keys: list[str] = []
        for row in rows:
            for k in row.keys():
                if k not in all_keys:
                    all_keys.append(k)

        if not all_keys:
            return ""

        output_buf = io.StringIO()
        writer = csv.DictWriter(output_buf, fieldnames=all_keys, extrasaction="ignore")
        writer.writeheader()
        for row in rows:
            writer.writerow(row)

        result = output_buf.getvalue()
        output_buf.close()

        if output:
            Path(output).write_text(result, encoding="utf-8")

        return result

    @staticmethod
    def _normalize(data: Any) -> list[dict]:
        """Normalize various data shapes into list[dict]."""
        if isinstance(data, list):
            rows = []
            for item in data:
                if isinstance(item, dict):
                    rows.append(Exporter._flatten(item))
                else:
                    rows.append({"value": str(item)})
            return rows
        elif isinstance(data, dict):
            return [Exporter._flatten(data)]
        elif isinstance(data, str):
            # Try to parse as JSON
            try:
                parsed = json.loads(data)
                return Exporter._normalize(parsed)
            except (json.JSONDecodeError, TypeError):
                return [{"value": data}]
        else:
            return [{"value": str(data)}]

    @staticmethod
    def _flatten(d: dict, parent_key: str = "", sep: str = ".") -> dict:
        """Flatten nested dict into single-level keys."""
        items: dict[str, Any] = {}
        for k, v in d.items():
            new_key = f"{parent_key}{sep}{k}" if parent_key else k
            if isinstance(v, dict):
                items.update(Exporter._flatten(v, new_key, sep=sep))
            elif isinstance(v, list):
                # Join list items as semicolon-separated string
                items[new_key] = "; ".join(
                    Exporter._flatten(item, "", sep) if isinstance(item, dict) else str(item) for item in v
                )
            else:
                items[new_key] = v
        return items
