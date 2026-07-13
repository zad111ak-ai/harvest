"""SessionManager — Cookie and session persistence for Harvest.

Saves/loads cookies between requests to maintain login state,
avoid CAPTCHAs, and improve scraping reliability.

Usage:
    sm = SessionManager(data_dir="~/.harvest/sessions")
    await sm.save_cookies(page, "ozon")
    await sm.load_cookies(page, "ozon")
"""

import json
from pathlib import Path
from loguru import logger


class SessionManager:
    def __init__(self, data_dir: str = "~/.harvest/sessions"):
        self.data_dir = Path(data_dir).expanduser()
        self.data_dir.mkdir(parents=True, exist_ok=True)

    def _cookie_path(self, name: str) -> Path:
        safe = name.replace("/", "_").replace(":", "_")
        return self.data_dir / f"{safe}.json"

    async def save_cookies(self, page, name: str) -> bool:
        """Save cookies from a Playwright page."""
        try:
            context = page.context
            cookies = await context.cookies()
            path = self._cookie_path(name)
            with open(path, "w") as f:
                json.dump(cookies, f, indent=2)
            logger.debug(f"Saved {len(cookies)} cookies for {name}")
            return True
        except Exception as e:
            logger.warning(f"Failed to save cookies for {name}: {e}")
            return False

    async def load_cookies(self, page, name: str) -> bool:
        """Load cookies into a Playwright page."""
        path = self._cookie_path(name)
        if not path.exists():
            return False
        try:
            with open(path) as f:
                cookies = json.load(f)
            context = page.context
            await context.add_cookies(cookies)
            logger.debug(f"Loaded {len(cookies)} cookies for {name}")
            return True
        except Exception as e:
            logger.warning(f"Failed to load cookies for {name}: {e}")
            return False

    async def save_storage(self, page, name: str) -> bool:
        """Save localStorage + sessionStorage."""
        try:
            storage = await page.evaluate("""() => {
                const data = {};
                for (let i = 0; i < localStorage.length; i++) {
                    const key = localStorage.key(i);
                    data[key] = localStorage.getItem(key);
                }
                return data;
            }""")
            path = self._cookie_path(f"{name}_storage")
            with open(path, "w") as f:
                json.dump(storage, f, indent=2)
            return True
        except Exception as e:
            logger.warning(f"Failed to save storage for {name}: {e}")
            return False

    def list_sessions(self) -> list[str]:
        """List saved session names."""
        return [p.stem for p in self.data_dir.glob("*.json") if "_storage" not in p.name]

    def delete_session(self, name: str) -> bool:
        """Delete a saved session."""
        path = self._cookie_path(name)
        storage_path = self._cookie_path(f"{name}_storage")
        deleted = False
        for p in [path, storage_path]:
            if p.exists():
                p.unlink()
                deleted = True
        return deleted
