"""Site analysis commands: crawl, map, contacts, search, monitor, diff, snapshot, batch."""

import json
import re
import asyncio
from pathlib import Path
from urllib.parse import urljoin, urlparse

from ..core import Scraper
from ..monitor import ChangeWatcher
from ..contacts import ContactCollector
from ..crawl import SiteCrawler
from ..export import Exporter
from ..notify import Notifier
from ..batch import BatchProcessor


async def cmd_monitor(args):
    watcher = ChangeWatcher()
    result = await watcher.check(args.url, selector=args.selector)
    print(json.dumps(result, indent=2, ensure_ascii=False))

    if result.get("changed"):
        print("\n[!] CHANGE DETECTED")
        print(result.get("diff_text", ""))

        # Send notification
        if args.notify:
            notifier = Notifier.create(
                args.notify,
                token=args.token or "",
                chat_id=args.chat or "",
                url=args.webhook_url or "",
            )
            message = f"🔔 <b>Change detected on:</b> {args.url}\n\n{result.get('diff_text', '')[:1000]}"
            sent = await notifier.send(message)
            if sent:
                print(f"[✓] Notification sent via {args.notify}")
            else:
                print(f"[✗] Failed to send notification via {args.notify}")
    else:
        print("\n✓ No changes (or first snapshot)")


async def cmd_contacts(args):
    collector = ContactCollector()
    result = await collector.collect(args.url, depth=args.depth)

    if args.export:
        csv_output = Exporter.to_csv(result)
        Path(args.export).write_text(csv_output, encoding="utf-8")
        print(f"[✓] Exported to {args.export}")
    else:
        print(json.dumps(result, indent=2, ensure_ascii=False))

    print(f"\nPages checked: {len(result['pages_checked'])}")
    print(f"Emails found: {len(result['emails'])}")
    print(f"Social links: {len(result['social_links'])}")


async def cmd_crawl(args):
    from ..recovery import CrawlCheckpoint

    # Checkpoint/resume support
    ckpt_id = args.resume or args.checkpoint
    checkpoint = CrawlCheckpoint(ckpt_id) if ckpt_id else None

    visited = set()
    queue = []

    if args.resume and checkpoint:
        state = checkpoint.load()
        if state:
            visited = state["visited"]
            queue = state["queue"]
            print(f"🔄 Resuming crawl '{args.resume}': {len(visited)} visited, {len(queue)} queued")
        else:
            print(f"⚠️  No checkpoint found for '{args.resume}', starting fresh")
    elif args.checkpoint:
        print(f"💾 Checkpoint enabled: '{args.checkpoint}' (auto-saves every 10 URLs)")

    crawler = SiteCrawler(
        proxy=args.proxy,
        headless=not args.no_headless,
        delay=args.delay,
    )

    result = await crawler.crawl(
        args.url,
        max_pages=args.max_pages,
        sitemap_only=args.sitemap_only,
    )

    # Save final checkpoint
    if checkpoint and result.get("pages"):
        all_urls = set(p.get("url", "") for p in result.get("pages", []))
        checkpoint.save(
            all_urls,
            [],
            {
                "total_pages": result["total_pages"],
                "start_url": args.url,
            },
        )
        print(f"💾 Checkpoint saved: {len(all_urls)} URLs")

    if args.export:
        csv_output = Exporter.to_csv(result.get("pages", []))
        Path(args.export).write_text(csv_output, encoding="utf-8")
        print(f"[✓] Exported {result['total_pages']} pages to {args.export}")
    else:
        # Print summary, not full pages
        summary = {
            "start_url": result["start_url"],
            "total_pages": result["total_pages"],
            "total_discovered": result["total_discovered"],
            "sitemap_urls": result.get("sitemap_urls", []),
            "timestamp": result["timestamp"],
            "pages": [{"url": p.get("url", ""), "title": p.get("title", "")} for p in result.get("pages", [])],
        }
        print(json.dumps(summary, indent=2, ensure_ascii=False))

    print(f"\n✓ Crawled {result['total_pages']}/{result['total_discovered']} pages")


async def cmd_search(args):
    scraper = Scraper(proxy=args.proxy, headless=not args.no_headless)
    query = args.query.replace(" ", "+")

    results = []
    tasks = []

    if args.source in ("all", "hn"):
        tasks.append(scraper.scrape(f"https://hn.algolia.com/api/v1/search?query={query}&hitsPerPage=10"))

    if args.source in ("all", "reddit"):
        tasks.append(scraper.scrape(f"https://www.reddit.com/search/?q={query}", extraction="html"))

    outputs = await asyncio.gather(*tasks, return_exceptions=True)
    for out in outputs:
        if isinstance(out, Exception):
            continue
        results.append(out)

    print(
        json.dumps(
            {"query": args.query, "source": args.source, "results": results},
            indent=2,
            ensure_ascii=False,
        )
    )


async def cmd_map(args):
    """Discover all URLs on a website instantly (sitemap + links)."""
    parsed = urlparse(args.url)
    domain = parsed.netloc

    urls = set()
    scraper = Scraper(proxy=args.proxy, headless=not args.no_headless)

    # 1. Try sitemap.xml
    sitemap_urls = [
        urljoin(args.url, "/sitemap.xml"),
        urljoin(args.url, "/sitemap_index.xml"),
        urljoin(args.url, "/sitemap.txt"),
    ]

    for surl in sitemap_urls:
        try:
            result = await scraper.scrape(surl, extraction="text")
            content = result.get("content", "")
            found = re.findall(r"https?://[^\s<>\"']+", content)
            for u in found:
                if domain in u:
                    urls.add(u.split("#")[0].split("?")[0])
        except Exception:
            continue

    # 2. Try robots.txt for Sitemap: directives
    try:
        robots = await scraper.scrape(f"{parsed.scheme}://{domain}/robots.txt", extraction="text")
        for line in robots.get("content", "").split("\n"):
            if line.lower().startswith("sitemap:"):
                sm_url = line.split(":", 1)[1].strip()
                try:
                    sm = await scraper.scrape(sm_url, extraction="text")
                    found = re.findall(r"https?://[^\s<>\"']+", sm.get("content", ""))
                    for u in found:
                        if domain in u:
                            urls.add(u.split("#")[0].split("?")[0])
                except Exception:
                    continue
    except Exception:
        pass

    # 3. Scrape homepage for links
    try:
        home = await scraper.scrape(args.url, extraction="html")
        from bs4 import BeautifulSoup

        soup = BeautifulSoup(home.get("content", ""), "html.parser")
        for a in soup.find_all("a", href=True):
            href = urljoin(args.url, str(a["href"])).split("#")[0].split("?")[0]
            if domain in href:
                urls.add(href)
    except Exception:
        pass

    url_list = sorted(urls)[: args.max_urls]

    if args.output == "txt":
        for u in url_list:
            print(u)
    else:
        print(
            json.dumps(
                {
                    "domain": domain,
                    "total": len(url_list),
                    "urls": url_list,
                },
                indent=2,
                ensure_ascii=False,
            )
        )

    print(f"\n✓ Found {len(url_list)} URLs", file=__import__("sys").stderr)


async def cmd_diff(args):
    """Structural diff — detect what changed in page DOM."""
    from ..structural_diff import StructuralDiff

    differ = StructuralDiff()

    if args.html_old and args.html_new:
        old_html = Path(args.html_old).read_text(encoding="utf-8")
        new_html = Path(args.html_new).read_text(encoding="utf-8")
        result = differ.diff(old_html=old_html, new_html=new_html, url=args.url)
    else:
        # Scrape current and compare with saved snapshot
        scraper = Scraper(proxy=args.proxy, headless=not args.no_headless)
        current = await scraper.scrape(args.url, extraction="html")
        new_html = current.get("content", "")
        old_snap = differ.load_snapshot(args.url)
        if old_snap:
            from ..structural_diff import (
                _extract_structure,
                _find_added,
                _find_removed,
                _find_changed,
                _generate_summary,
            )

            old_structure = old_snap
            new_structure = _extract_structure(new_html)
            added = _find_added(old_structure, new_structure)
            removed = _find_removed(old_structure, new_structure)
            changed = _find_changed(old_structure, new_structure)
            result = {
                "url": args.url,
                "added": added[:20],
                "removed": removed[:20],
                "changed": changed[:20],
                "summary": _generate_summary(added, removed, changed),
            }
        else:
            differ.capture(new_html, url=args.url)
            result = {
                "url": args.url,
                "message": "First snapshot captured. Run again to see diff.",
            }

    print(json.dumps(result, indent=2, ensure_ascii=False))


async def cmd_snapshot(args):
    """Capture DOM structure snapshot."""
    from ..structural_diff import StructuralDiff

    differ = StructuralDiff()
    scraper = Scraper(proxy=args.proxy, headless=not args.no_headless)
    result = await scraper.scrape(args.url, extraction="html")
    html = result.get("content", "")
    structure = differ.capture(html, url=args.url)

    if args.output == "txt":
        for elem in structure[:50]:
            attrs = " ".join(f'{k}="{v}"' for k, v in elem.get("attrs", {}).items())
            text = elem.get("text_preview", "")[:60]
            print(f"  <{elem['tag']}> {attrs} → {text}")
    else:
        print(
            json.dumps(
                {
                    "url": args.url,
                    "elements": len(structure),
                    "structure": structure[:50],
                },
                indent=2,
                ensure_ascii=False,
            )
        )

    print(f"\n✓ Snapshot saved for {args.url}", file=__import__("sys").stderr)


async def cmd_batch(args):
    """Process URLs in batch from file or sitemap."""
    processor = BatchProcessor(
        concurrency=args.concurrency,
        delay=args.delay,
        rate_limit=args.rate_limit,
        retries=args.retries,
        proxy=args.proxy,
        headless=not args.no_headless,
    )

    extract_schema = None
    if args.extract:
        from ..extract import load_schema

        extract_schema = load_schema(args.extract)

    if args.sitemap:
        result = await processor.process_sitemap(
            args.sitemap,
            selector=args.selector,
            extract_schema=extract_schema,
        )
    elif args.file:
        result = await processor.process_file(
            args.file,
            selector=args.selector,
            extract_schema=extract_schema,
        )
    else:
        print("Error: provide either a URL file or --sitemap")
        return

    processor.print_summary(result)

    if args.export:
        fmt = "csv" if args.export.endswith(".csv") else "json"
        path = processor.export_results(result, args.export, fmt=fmt)
        print(f"   📁 Exported to {path}")
