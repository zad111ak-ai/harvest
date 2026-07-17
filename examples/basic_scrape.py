#!/usr/bin/env python3
"""
Harvest: Basic Scraping Example

Standalone example — no DenseForge needed.
Demonstrates core Harvest features: scrape, batch, contacts.

Requirements:
    pip install harvest-agent
"""

from __future__ import annotations

from harvest import Harvest, CrawlConfig


def main() -> None:
    config = CrawlConfig(
        max_concurrent=3,
        respect_robots_txt=True,
    )
    h = Harvest(config)

    # ── Single URL scrape ───────────────────────────────────────────
    print("🕷️  Scraping Hacker News...")
    result = h.scrape("https://news.ycombinator.com")

    print(f"   Title: {result.metadata.get('title', 'N/A')}")
    print(f"   Content: {len(result.markdown)} chars")
    print(f"   Links: {len(result.metadata.get('links', []))}")
    print()
    print("   First 300 chars:")
    print(f"   {result.markdown[:300]}...")
    print()

    # ── Batch scrape ────────────────────────────────────────────────
    print("📦 Batch scraping...")
    urls = [
        "https://httpbin.org/html",
        "https://httpbin.org/json",
    ]
    results = h.batch_scrape(urls, max_concurrent=2)
    for r in results:
        print(f"   ✓ {r.url}: {len(r.markdown)} chars")

    # ── Contact extraction ──────────────────────────────────────────
    print("\n📧 Contact extraction...")
    result = h.scrape("https://httpbin.org/html")
    contacts = h.extract_contacts(result)
    print(f"   Emails: {contacts.emails}")
    print(f"   Phones: {contacts.phones}")

    print("\n✅ Done!")


if __name__ == "__main__":
    main()
