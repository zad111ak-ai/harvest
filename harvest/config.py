"""
Config — Persistent configuration for Harvest.

Stored in ~/.harvest/config.yaml. Manage via `harvest config` CLI.

All commands read from config by default, CLI flags override.
"""

from pathlib import Path
from typing import Any, Optional

try:
    import yaml
except ImportError:
    yaml = None  # type: ignore


DEFAULT_CONFIG = {
    "version": "0.2.0",
    "defaults": {
        "headless": True,
        "timeout": 30000,
        "delay": 0.5,
        "max_pages": 50,
        "max_concurrent": 5,
        "retries": 3,
        "retry_delay": 2.0,
    },
    "scraper": {
        "backend": "scrapling",  # "scrapling" (default) or "crawl4ai"
    },
    "notify": {
        "telegram_token": "",
        "telegram_chat_id": "",
        "webhook_url": "",
    },
    "proxy": {
        "url": "",
        "rotation_file": "",
        "rotation_interval": 10,  # requests before rotating
    },
    "export": {
        "default_format": "json",
        "csv_delimiter": ",",
    },
    "paths": {
        "data_dir": "~/.harvest/data",
        "snapshots_dir": "~/.harvest/snapshots",
        "logs_dir": "~/.harvest/logs",
    },
    "server": {
        "host": "0.0.0.0",
        "port": 8590,
        "workers": 1,
        "rate_limit": 10,  # requests per minute
    },
}


class Config:
    """Load, save, and access Harvest configuration."""

    def __init__(self, config_path: Optional[str] = None):
        self.config_path = Path(config_path or "~/.harvest/config.yaml").expanduser()
        self._data: dict = {}
        self.load()

    @property
    def data(self) -> dict:
        return self._data

    def load(self):
        """Load config from file or create default."""
        if self.config_path.exists():
            raw = self.config_path.read_text()
            if yaml:
                self._data = yaml.safe_load(raw) or {}
            else:
                # Fallback: basic YAML-like parser for simple configs
                self._data = self._parse_simple_yaml(raw)
        else:
            self._data = self._deep_copy(DEFAULT_CONFIG)
            self.save()

        # Merge any missing default keys
        self._merge_defaults()

    def save(self):
        """Save config to file."""
        self.config_path.parent.mkdir(parents=True, exist_ok=True)
        if yaml:
            self.config_path.write_text(yaml.dump(self._data, default_flow_style=False))
        else:
            self.config_path.write_text(self._format_simple_yaml(self._data))

    def get(self, *keys: str, default: Any = None) -> Any:
        """Get a nested config value: config.get('notify', 'telegram_token')"""
        current = self._data
        for key in keys:
            if isinstance(current, dict):
                current = current.get(key, default)
                if current is None:
                    return default
            else:
                return default
        return current if current is not None else default

    def set(self, *keys: str, value: Any):
        """Set a nested config value: config.set('notify', 'telegram_token', value='abc')"""
        current = self._data
        for key in keys[:-1]:
            if key not in current or not isinstance(current[key], dict):
                current[key] = {}
            current = current[key]
        current[keys[-1]] = value
        self.save()

    def _merge_defaults(self):
        """Merge DEFAULT_CONFIG into loaded data (adds missing keys)."""
        merged = self._deep_copy(DEFAULT_CONFIG)
        self._deep_merge(merged, self._data)
        self._data = merged

    def _deep_merge(self, base: dict, override: dict):
        """Recursively merge override into base."""
        for key, value in override.items():
            if key in base and isinstance(base[key], dict) and isinstance(value, dict):
                self._deep_merge(base[key], value)
            else:
                base[key] = value

    def _deep_copy(self, d: dict) -> dict:
        import copy

        return copy.deepcopy(d)

    def _parse_simple_yaml(self, raw: str) -> dict:
        """Basic YAML parser for simple configs (fallback when PyYAML not installed)."""
        result: dict = {}
        path: list[str] = []

        for line in raw.splitlines():
            stripped = line.strip()
            if not stripped or stripped.startswith("#"):
                continue

            indent = len(line) - len(line.lstrip())
            key_part = stripped.rstrip(":")

            if stripped.endswith(":"):
                # Dict key
                while path and len(path) * 2 >= indent:
                    path.pop()
                path.append(key_part)
            else:
                # Key: value
                if ":" in stripped:
                    key, _, val = stripped.partition(":")
                    key = key.strip()
                    val = val.strip().strip("'\"")
                    # Navigate to correct nesting
                    d = result
                    for p in path:
                        d = d.setdefault(p, {})
                    d[key] = val

        return result

    def _format_simple_yaml(self, d: dict, indent: int = 0) -> str:
        """Format dict as simple YAML."""
        lines = []
        for key, value in d.items():
            prefix = "  " * indent
            if isinstance(value, dict):
                lines.append(f"{prefix}{key}:")
                lines.append(self._format_simple_yaml(value, indent + 1))
            else:
                if isinstance(value, bool):
                    lines.append(f"{prefix}{key}: {str(value).lower()}")
                elif value is None or value == "":
                    lines.append(f'{prefix}{key}: ""')
                else:
                    lines.append(f"{prefix}{key}: {value}")
        return "\n".join(lines)
