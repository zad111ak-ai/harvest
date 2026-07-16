"""Scraping commands: scrape, extract, llm-extract, generate, detect-api, screenshot."""

import json
import logging
import sys
from pathlib import Path

from ..core import Scraper
from ..extract import SchemaExtractor, LLMExtractor, load_schema
from ..export import Exporter
from ..config import Config

logger = logging.getLogger(__name__)


async def cmd_scrape(args):
    scraper = Scraper(proxy=args.proxy, headless=not args.no_headless)
    result = await scraper.scrape(args.url, selector=args.selector)

    # Apply preprocessing mode
    mode = getattr(args, "mode", "full")
    if mode != "full" and result.get("content"):
        from harvest.preprocess import HTMLPreprocessor

        preprocessor = HTMLPreprocessor(mode=mode)
        cleaned = preprocessor.clean(result["content"])
        result["content"] = cleaned.text
        result["_preprocess"] = {
            "mode": preprocessor.stats.mode_used,
            "page_type": preprocessor.stats.page_type,
            "compression": f"{preprocessor.stats.compression_ratio:.0%}",
            "tokens_saved": preprocessor.stats.estimated_tokens_saved,
        }
        if preprocessor.stats.warnings:
            result["_preprocess"]["warnings"] = preprocessor.stats.warnings

    if args.output == "csv":
        csv_output = Exporter.to_csv(result)
        print(csv_output)
    elif args.output == "json":
        print(json.dumps(result, indent=2, ensure_ascii=False))
    elif args.output == "md":
        print(f"# {result.get('title', '')}\n")
        print(result.get("content", ""))
    elif args.output == "txt":
        title = result.get("title", "")
        content = result.get("content", "")
        if title:
            print(f"Title: {title}")
        print(content)


async def cmd_extract(args):
    schema = load_schema(args.schema)
    extractor = SchemaExtractor(proxy=args.proxy, headless=not args.no_headless)
    result = await extractor.extract(args.url, schema)
    print(json.dumps(result, indent=2, ensure_ascii=False))


async def cmd_llm_extract(args):
    """Extract structured data using natural language + LLM."""
    cfg = Config()
    base_url = args.base_url or cfg.get("llm", "base_url", default="http://localhost:3000/v1")
    model = args.model or cfg.get("llm", "model", default="auto/best-chat")
    api_key = args.api_key or cfg.get("llm", "api_key", default="sk-omniroute")

    schema = None
    if args.schema:
        schema = load_schema(args.schema)

    mode = getattr(args, "mode", "full")
    use_semantic_cache = getattr(args, "semantic_cache", False)
    use_self_healing = getattr(args, "self_healing", False)

    llm = LLMExtractor(base_url=base_url, model=model, api_key=api_key)

    # Semantic cache check
    if use_semantic_cache:
        from ..semantic_cache import SemanticCache

        _sem_cache = SemanticCache()
        cached = _sem_cache.get(url=args.url, prompt=args.prompt)
        if cached:
            result = {"url": args.url, "cached": True, "extracted": cached}
            print(json.dumps(result, indent=2, ensure_ascii=False))
            await llm.close()
            return

    # Self-healing extraction
    if use_self_healing:
        from ..self_healing import SelfHealingParser

        _sh = SelfHealingParser(url=args.url, llm_base_url=base_url, llm_model=model, llm_api_key=api_key)
        result = await llm.extract(url=args.url, description=args.prompt, schema=schema, preprocess_mode=mode)
        html = result.get("content", "")
        if schema and html:
            heal_result = await _sh.extract(html=html, schema=schema)
            result["self_healing"] = heal_result
        print(json.dumps(result, indent=2, ensure_ascii=False))
        await llm.close()
        return

    # Vision extraction
    use_vision = getattr(args, "vision", False)
    screenshot_path = getattr(args, "screenshot", None)
    if use_vision or mode == "hybrid-vision":
        from ..vision_extractor import VisionExtractor

        _vision = VisionExtractor(base_url=base_url, model=model, api_key=api_key)
        result = await _vision.extract(
            url=args.url,
            prompt=args.prompt,
            screenshot_path=screenshot_path,
        )

        # If hybrid-vision and vision failed, fallback to HTML extraction
        if mode == "hybrid-vision" and (result.get("error") or not result.get("extracted")):
            logger.info("Vision failed, falling back to HTML extraction")
            result = await llm.extract(
                url=args.url,
                description=args.prompt,
                schema=schema,
                preprocess_mode="economy",
            )
            result["vision_fallback"] = True

        print(json.dumps(result, indent=2, ensure_ascii=False))
        await llm.close()
        return

    result = await llm.extract(
        url=args.url,
        description=args.prompt,
        schema=schema,
        preprocess_mode=mode,
    )
    # Store in semantic cache if enabled
    if use_semantic_cache:
        from ..semantic_cache import SemanticCache

        _sem_cache = SemanticCache()
        _sem_cache.set(
            url=args.url,
            prompt=args.prompt,
            html=result.get("content", ""),
            response=result.get("extracted", {}),
        )

    if args.output == "json":
        print(json.dumps(result, indent=2, ensure_ascii=False))
    elif args.output == "md":
        extracted = result.get("extracted", {})
        print(f"# {result.get('title', '')}\n")
        if isinstance(extracted, dict):
            for k, v in extracted.items():
                print(f"**{k}:** {v}")
        else:
            print(extracted)
    elif args.output == "txt":
        extracted = result.get("extracted", {})
        if isinstance(extracted, dict):
            for k, v in extracted.items():
                print(f"{k}: {v}")
        else:
            print(extracted)

    await llm.close()


async def cmd_generate(args):
    """Generate a standalone scraping script from a URL."""
    from ..script_generator import ScriptGenerator

    gen = ScriptGenerator(proxy=args.proxy)

    print(f"🔍 Fetching {args.url}...", file=sys.stderr)
    print(f"🧠 Analyzing with LLM (fields: {', '.join(args.fields)})...", file=sys.stderr)

    try:
        script = await gen.generate(
            url=args.url,
            fields=args.fields,
            output_format=args.format,
            add_delay=not args.no_delay,
        )
    except Exception as e:
        print(f"❌ Error: {e}", file=sys.stderr)
        sys.exit(1)

    gen.save(script, args.output)
    print(f"\n✅ Script saved to {args.output}", file=sys.stderr)
    print(f"   Run: python3 {args.output} <URL>", file=sys.stderr)
    print(f"   Batch: python3 {args.output} urls.txt --csv output.csv", file=sys.stderr)


async def cmd_detect_api(args):
    """Discover hidden APIs from browser traffic."""
    from ..api_detector import APIDetector

    async with APIDetector(
        proxy=args.proxy,
        headless=not args.no_headless,
    ) as detector:
        await detector.visit(
            args.url,
            interact=args.interact,
            scroll_count=args.scroll,
        )

        print(detector.summary())

        apis = detector.get_apis()
        if not apis:
            print("No API endpoints discovered. Try --interact to trigger more requests.\n")
            return

        sep = "=" * 60
        print(f"\n{sep}")
        print("Generated " + args.format + " code for first endpoint:\n")
        print(detector.generate_code(apis[0], style=args.format))

        if args.export:
            data = detector.export(args.export)
            ep_count = data["total_endpoints"]
            print(f"\n✅ Exported {ep_count} endpoints to " + args.export)


async def cmd_screenshot(args):
    """Take a screenshot of a page using Scrapling's browser session."""
    from ..browser import BrowserSession

    headless = not args.no_headless
    async with BrowserSession(proxy=args.proxy, headless=headless) as session:
        _ = await session.fetch(args.url, extraction_type="html")
        output_path = Path(args.output)

    print(
        json.dumps(
            {
                "url": args.url,
                "output": str(output_path) if output_path.exists() else args.output,
                "note": "Screenshot saved. For full browser screenshot, use the Scrapling API directly.",
            },
            indent=2,
            ensure_ascii=False,
        )
    )
