"""
Harvest ↔ DenseForge Integration Bridge

Optional connector: Harvest can use DenseForge as its "brain"
for semantic storage, RAG queries, and causal reasoning.

Architecture:
    Harvest (standalone)  →  works alone, no DenseForge needed
    Harvest + DenseForge  →  scraped content auto-ingested into DenseForge
                             semantic search, reasoning, knowledge graph

Usage:
    # Auto-detect (if DenseForge installed)
    from harvest.integrations.denseforge import DenseForgeBridge
    bridge = DenseForgeBridge()
    if bridge.available:
        await bridge.ingest("https://example.com", content)
        results = await bridge.search("What products do they sell?")
"""

import logging
from typing import Optional

logger = logging.getLogger(__name__)


class DenseForgeBridge:
    """Bridge between Harvest and DenseForge.

    Detects if DenseForge is installed and provides a clean API
    for Harvest to use DenseForge's capabilities.
    """

    def __init__(self):
        self._forge = None
        self._available = False

        try:
            from denseforge.core.forge import DenseForge

            self._forge = DenseForge()
            self._available = True
            logger.info("DenseForge bridge: connected")
        except ImportError:
            logger.debug("DenseForge not installed — bridge disabled")
        except Exception as e:
            logger.warning(f"DenseForge bridge init failed: {e}")

    @property
    def available(self) -> bool:
        """Check if DenseForge is available."""
        return self._available

    @property
    def forge(self):
        """Get DenseForge instance (raises if not available)."""
        if not self._available:
            raise RuntimeError("DenseForge not installed. Install with: pip install denseforge")
        return self._forge

    # ─── Harvest → DenseForge (ingest scraped content) ──────────────────

    async def ingest(self, url: str, content: str, metadata: Optional[dict] = None) -> Optional[list[int]]:
        """Ingest scraped content into DenseForge knowledge base.

        Args:
            url: Source URL of the scraped content
            content: Scraped text content
            metadata: Optional metadata (title, author, date, etc.)

        Returns:
            List of document IDs or None if unavailable
        """
        if not self._available:
            return None

        try:
            meta = metadata or {}
            meta["source_url"] = url
            meta["source"] = "harvest"

            doc_ids = self.forge.ingest(
                text=content,
                title=meta.get("title", url),
                metadata=meta,
            )
            logger.info(f"Ingested {url} → DenseForge ({len(doc_ids)} chunks)")
            return doc_ids
        except Exception as e:
            logger.error(f"DenseForge ingest failed: {e}")
            return None

    async def ingest_batch(self, items: list[dict]) -> int:
        """Batch ingest multiple scraped items.

        Args:
            items: List of {"url": str, "content": str, "metadata": dict}

        Returns:
            Number of items ingested
        """
        if not self._available:
            return 0

        try:
            docs = []
            for item in items:
                meta = item.get("metadata", {})
                meta["source_url"] = item["url"]
                meta["source"] = "harvest"
                docs.append(
                    {
                        "text": item["content"],
                        "title": meta.get("title", item["url"]),
                        "metadata": meta,
                    }
                )

            count = self.forge.ingest_batch(docs)
            logger.info(f"Batch ingested {count} items → DenseForge")
            return count
        except Exception as e:
            logger.error(f"DenseForge batch ingest failed: {e}")
            return 0

    # ─── DenseForge → Harvest (search and reason) ──────────────────────

    async def search(self, query: str, top_k: int = 5) -> Optional[list[dict]]:
        """Search DenseForge knowledge base.

        Args:
            query: Natural language query
            top_k: Number of results

        Returns:
            List of search results or None if unavailable
        """
        if not self._available:
            return None

        try:
            results = self.forge.search(query, top_k=top_k)
            return results
        except Exception as e:
            logger.error(f"DenseForge search failed: {e}")
            return None

    async def ask_why(self, effect: str, max_depth: int = 5) -> Optional[dict]:
        """Causal reasoning: why did this happen?

        Args:
            effect: The effect to explain
            max_depth: Max reasoning depth

        Returns:
            Causal explanation or None if unavailable
        """
        if not self._available:
            return None

        try:
            return self.forge.ask_why(effect, max_depth=max_depth)
        except Exception as e:
            logger.error(f"DenseForge ask_why failed: {e}")
            return None

    async def ask_what_if(self, intervention: str, target: str) -> Optional[dict]:
        """Counterfactual reasoning: what if we change X?

        Args:
            intervention: What to change
            target: What outcome to predict

        Returns:
            Counterfactual analysis or None if unavailable
        """
        if not self._available:
            return None

        try:
            return self.forge.ask_what_if(intervention, target)
        except Exception as e:
            logger.error(f"DenseForge ask_what_if failed: {e}")
            return None

    async def stats(self) -> Optional[dict]:
        """Get DenseForge statistics.

        Returns:
            Stats dict or None if unavailable
        """
        if not self._available:
            return None

        try:
            return self.forge.stats()
        except Exception as e:
            logger.error(f"DenseForge stats failed: {e}")
            return None

    # ─── Auto-ingest from scrape results ───────────────────────────────

    async def auto_ingest_scrape(self, scrape_result: dict) -> Optional[list[int]]:
        """Automatically ingest scrape result into DenseForge.

        Args:
            scrape_result: Result from Harvest scraper
                (expects "url", "content", and optional "metadata")

        Returns:
            Document IDs or None
        """
        url = scrape_result.get("url", "")
        content = scrape_result.get("content", "")
        metadata = scrape_result.get("metadata", {})

        if not url or not content:
            return None

        return await self.ingest(url, content, metadata)
