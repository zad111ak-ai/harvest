#!/usr/bin/env python3
"""
Harvest + DenseForge: Scrape → Memory → Search

This example demonstrates the core workflow:
1. Scrape a web page with Harvest
2. Store content in DenseForge semantic memory
3. Search memory later — your AI agent never forgets

Requirements:
    pip install harvest-agent[denseforge]
"""

from __future__ import annotations

import asyncio
import sys


async def main() -> None:
    # ── Step 1: Scrape ──────────────────────────────────────────────
    try:
        from harvest import Harvest, CrawlConfig
    except ImportError:
        print("❌ Install harvest: pip install harvest-agent")
        sys.exit(1)

    print("🕷️  Step 1: Scraping...")
    config = CrawlConfig(max_concurrent=3, respect_robots_txt=True)
    h = Harvest(config)

    urls = [
        "https://docs.python.org/3/tutorial/classes.html",
        "https://docs.python.org/3/tutorial/datastructures.html",
    ]

    scrape_results = []
    for url in urls:
        print(f"   → {url}")
        result = h.scrape(url)
        scrape_results.append(result)
        print(f"   ✓ {len(result.markdown)} chars extracted")

    # ── Step 2: Store in Semantic Memory ─────────────────────────────
    print("\n🧠 Step 2: Storing in semantic memory...")

    try:
        from harvest.integrations.denseforge import DenseForgeBridge
    except ImportError:
        print("⚠️  DenseForge not installed. Run: pip install denseforge")
        print("\n   Showing raw scrape results instead:\n")
        for r in scrape_results:
            print(f"--- {r.url} ---")
            print(r.markdown[:500])
            print("...\n")
        return

    bridge = DenseForgeBridge()

    if not bridge.available:
        print("⚠️  DenseForge daemon not running. Start with: denseforge daemon")
        return

    for result in scrape_results:
        await bridge.ingest(
            url=result.url,
            content=result.markdown,
            metadata={"title": result.url.split("/")[-1]},
        )
        print(f"   ✓ Stored: {result.url}")

    stats = await bridge.stats()
    print(f"   📊 Total documents: {stats.get('total_documents', 'N/A') if stats else 'N/A'}")

    # ── Step 3: Search Memory ───────────────────────────────────────
    print("\n🔍 Step 3: Searching memory...")

    queries = [
        "How do I create a class in Python?",
        "What is a list comprehension?",
        "How to inherit from a base class?",
    ]

    for query in queries:
        print(f'\n   ❓ "{query}"')
        results = await bridge.search(query, top_k=3)
        if results:
            for i, hit in enumerate(results[:3], 1):
                score = hit.get("score", 0)
                text = hit.get("text", "")[:120]
                print(f"   {i}. [score: {score:.2f}] {text}...")
        else:
            print("   (no results)")

    # ── Step 4: Ask Why ─────────────────────────────────────────────
    print("\n\n🤔 Step 4: Causal reasoning (ask_why)...")
    answer = await bridge.ask_why("Why are Python classes useful?")
    if answer:
        print(f"   💡 {str(answer)[:300]}...")
    else:
        print("   (no answer)")

    print("\n✅ Done! Your AI agent now remembers all scraped data.")
    print("   Next time, just search() instead of re-scraping.")


if __name__ == "__main__":
    asyncio.run(main())
