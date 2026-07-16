"""Harvest CLI — modular command dispatcher."""

import asyncio

from .parser import build_parser


def main():
    parser = build_parser()
    args = parser.parse_args()

    # Lazy import of all command modules
    from .scrape import (
        cmd_scrape,
        cmd_extract,
        cmd_llm_extract,
        cmd_generate,
        cmd_detect_api,
        cmd_screenshot,
    )
    from .site import (
        cmd_crawl,
        cmd_map,
        cmd_contacts,
        cmd_search,
        cmd_monitor,
        cmd_diff,
        cmd_snapshot,
        cmd_batch,
    )
    from .system import (
        cmd_doctor,
        cmd_config,
        cmd_serve,
        cmd_memory,
        cmd_checkpoints,
        cmd_pool,
        cmd_shadow,
    )
    from .p2p import (
        cmd_cache_stats,
        cmd_p2p_stats,
        cmd_p2p_peers,
        cmd_p2p_enable,
        cmd_p2p_disable,
    )

    dispatch = {
        "scrape": cmd_scrape,
        "extract": cmd_extract,
        "monitor": cmd_monitor,
        "check": cmd_monitor,
        "watch": cmd_monitor,
        "contacts": cmd_contacts,
        "crawl": cmd_crawl,
        "search": cmd_search,
        "llm-extract": cmd_llm_extract,
        "map": cmd_map,
        "doctor": cmd_doctor,
        "diff": cmd_diff,
        "snapshot": cmd_snapshot,
        "cache-stats": cmd_cache_stats,
        "screenshot": cmd_screenshot,
        "batch": cmd_batch,
        "serve": cmd_serve,
        "config": cmd_config,
        "generate": cmd_generate,
        "pool": cmd_pool,
        "shadow": cmd_shadow,
        "memory": cmd_memory,
        "checkpoints": cmd_checkpoints,
        "detect-api": cmd_detect_api,
        "p2p-stats": cmd_p2p_stats,
        "p2p-peers": cmd_p2p_peers,
        "p2p-enable": cmd_p2p_enable,
        "p2p-disable": cmd_p2p_disable,
    }

    cmd_fn = dispatch.get(args.command)
    if cmd_fn:
        asyncio.run(cmd_fn(args))
    else:
        parser.print_help()
