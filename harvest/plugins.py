"""
Plugins — modular system for custom data sources and processors.
"""

import importlib
import inspect
import logging
from pathlib import Path
from typing import Any, Optional


class PluginBase:
    """Base class for all Harvest plugins."""

    name: str = ""
    description: str = ""
    author: str = ""
    version: str = "0.1.0"

    def __init__(self, config: Optional[dict] = None):
        self.config = config or {}

    def init(self) -> Any:
        """Called after plugin load for async/non-trivial setup."""
        pass

    def can_handle(self, url: str) -> bool:
        """Return True if this plugin should handle the given URL."""
        return False

    async def handle(self, url: str, **kwargs) -> dict:
        """Handle a URL and return extracted data."""
        raise NotImplementedError


class PluginManager:
    """Discovers, loads, and manages Harvest plugins."""

    def __init__(self, plugin_dirs: Optional[list[str]] = None):
        self.plugin_dirs = plugin_dirs or []
        self.plugins: list[PluginBase] = []
        self._loaded = False

    def discover(self) -> list[PluginBase]:
        """Discover available plugins."""
        if self._loaded:
            return self.plugins

        for directory in self.plugin_dirs:
            path = Path(directory)
            if not path.exists():
                continue
            for f in path.glob("*.py"):
                if f.stem.startswith("_"):
                    continue
                try:
                    module = importlib.import_module(f.stem)
                    for name, obj in inspect.getmembers(module):
                        if (
                            inspect.isclass(obj)
                            and issubclass(obj, PluginBase)
                            and obj is not PluginBase
                            and not inspect.isabstract(obj)
                        ):
                            plugin = obj()
                            self.plugins.append(plugin)
                except Exception as e:
                    logging.warning(f"Failed to load plugin {f.stem}: {e}")
        self._loaded = True
        return self.plugins

    def find_plugin(self, url: str) -> Optional[PluginBase]:
        """Find a registered plugin that can handle the given URL."""
        for plugin in self.plugins:
            if plugin.can_handle(url):
                return plugin
        return None
