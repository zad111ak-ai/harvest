"""System commands: doctor, config, serve, memory, checkpoints, pool, shadow."""

import json
import importlib
import sys
from pathlib import Path

from ..config import Config


async def cmd_doctor(args):
    """Check Harvest installation health."""
    checks = []

    # Python version
    py_ver = f"{sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro}"
    checks.append(("Python", py_ver, sys.version_info >= (3, 10)))

    # Core deps
    for mod_name, pkg_name in [
        ("scrapling", "scrapling"),
        ("aiohttp", "aiohttp"),
        ("bs4", "beautifulsoup4"),
        ("fastapi", "fastapi"),
        ("pydantic", "pydantic"),
    ]:
        try:
            mod = importlib.import_module(mod_name)
            ver = getattr(mod, "__version__", "?")
            checks.append((pkg_name, ver, True))
        except ImportError:
            checks.append((pkg_name, "NOT INSTALLED", False))

    # Optional deps
    for mod_name, pkg_name in [
        ("mcp", "mcp"),
        ("yaml", "pyyaml"),
    ]:
        try:
            mod = importlib.import_module(mod_name)
            ver = getattr(mod, "__version__", "?")
            checks.append((pkg_name, ver, True))
        except ImportError:
            checks.append((pkg_name, "NOT INSTALLED", False))

    # Config
    config_path = Path.home() / ".harvest" / "config.yaml"
    checks.append(("config.yaml", str(config_path), config_path.exists()))

    # Print results
    all_ok = True
    for name, ver, ok in checks:
        status = "✅" if ok else "❌"
        if not ok:
            all_ok = False
        print(f"  {status} {name}: {ver}")

    print()
    if all_ok:
        print("✅ All checks passed. Harvest is ready!")
    else:
        print("❌ Some checks failed. Fix the issues above.")


async def cmd_config(args):
    """Manage Harvest configuration."""
    cfg = Config()

    if args.config_cmd == "show":
        print(json.dumps(cfg.data, indent=2, ensure_ascii=False))
    elif args.config_cmd == "get":
        val = cfg.get(*args.keys)
        print(val if val is not None else "(not set)")
    elif args.config_cmd == "set":
        cfg.set(*args.keys, value=args.value)
        path_str = " ".join(args.keys)
        print(f"✓ {path_str} = {args.value}")
    else:
        print("Usage: harvest config [show|get keys...|set keys... value]")


async def cmd_serve(args):
    """Start the HTTP API server with WebSocket streaming."""
    from ..server import run_server
    from ..streaming import get_streamer

    cfg = Config()
    host = args.host or cfg.get("server", "host", default="0.0.0.0")
    port = args.port or cfg.get("server", "port", default=8590)

    get_streamer()  # Initialize global stats collector

    run_server(config=cfg, host=host, port=port)


async def cmd_memory(args):
    """Monitor memory usage."""
    from ..memory_monitor import MemoryMonitor

    monitor = MemoryMonitor(warn_threshold_mb=args.warn, critical_threshold_mb=args.critical)
    monitor.start()
    monitor.snapshot("start")
    print(monitor.report())


async def cmd_checkpoints(args):
    """Manage crawl checkpoints."""
    from ..recovery import CrawlCheckpoint

    if args.ckpt_cmd == "list":
        ckpts = CrawlCheckpoint.list_checkpoints()
        if not ckpts:
            print("No checkpoints found in ~/.harvest/checkpoints/")
            return
        print(f"{'ID':<20} {'Visited':>8} {'Queue':>8} {'Timestamp'}")
        print(f"{'─' * 20} {'─' * 8} {'─' * 8} {'─' * 26}")
        for c in ckpts:
            print(f"{c['crawl_id']:<20} {c['visited_count']:>8} {c['queue_count']:>8} {c['timestamp']}")

    elif args.ckpt_cmd == "show":
        ckpt = CrawlCheckpoint(args.id)
        info = ckpt.get_info()
        if info:
            print(json.dumps(info, indent=2))
        else:
            print(f"No checkpoint found: {args.id}")

    elif args.ckpt_cmd == "delete":
        ckpt = CrawlCheckpoint(args.id)
        if ckpt.exists():
            ckpt.delete()
            print(f"✅ Deleted checkpoint: {args.id}")
        else:
            print(f"No checkpoint found: {args.id}")
    else:
        print("Usage: harvest checkpoints [list|show <id>|delete <id>]")


async def cmd_pool(args):
    """Pre-warm browser pool."""
    from ..browser_pool import BrowserPool

    pool = BrowserPool(warm_count=args.warm, proxy=args.proxy)
    await pool.start()

    if args.stats:
        print(json.dumps(pool.get_stats(), indent=2))
    else:
        print(f"✅ Browser pool warmed: {len(pool._warm)} browsers ready")
        print("   Use: harvest scrape <url> --use-pool")

    await pool.stop()


async def cmd_shadow(args):
    """Extract Shadow DOM content."""
    from ..browser import BrowserSession
    from ..shadow_dom import flatten_shadow_dom, extract_shadow_dom_structured, has_shadow_dom

    async with BrowserSession(proxy=args.proxy) as session:
        await session.fetch(args.url, extraction_type="html")
        page = session.get_playwright_page()

        has_shadow = await has_shadow_dom(page)
        print(f"🔍 Shadow DOM detected: {'Yes' if has_shadow else 'No'}", flush=True)

        if args.structured:
            result = await extract_shadow_dom_structured(page)
            output = json.dumps(result, indent=2, ensure_ascii=False)
        else:
            result = await flatten_shadow_dom(page)
            output = result or ""

    if args.output == "json":
        print(
            json.dumps(
                {"url": args.url, "has_shadow_dom": has_shadow, "content": output[:5000]}, indent=2, ensure_ascii=False
            )
        )
    else:
        print(output)
