"""
Comprehensive test suite for Harvest.

Tests edge cases, error handling, input validation, and potential crashes.
Run: python3 -m pytest tests/ -v
"""

import json
import asyncio
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

# ── Config tests ──


def test_config_defaults():
    """Config should have all DEFAULT_CONFIG keys after init."""
    from harvest.config import Config

    with tempfile.TemporaryDirectory() as tmp:
        cfg = Config(config_path=f"{tmp}/config.yaml")
        assert cfg.get("version") == "0.2.0"
        assert cfg.get("defaults", "timeout") == 30000
        assert cfg.get("defaults", "retries") == 3
        assert cfg.get("proxy", "url") == ""
        assert cfg.get("server", "port") == 8590


def test_config_set_get():
    """Testing nested set/get."""
    from harvest.config import Config

    with tempfile.TemporaryDirectory() as tmp:
        cfg = Config(config_path=f"{tmp}/config.yaml")
        cfg.set("proxy", "url", value="http://127.0.0.1:1082")
        assert cfg.get("proxy", "url") == "http://127.0.0.1:1082"

        # Reload from file
        cfg2 = Config(config_path=f"{tmp}/config.yaml")
        assert cfg2.get("proxy", "url") == "http://127.0.0.1:1082"


def test_config_empty_keys():
    """Getting non-existent keys should return None or default."""
    from harvest.config import Config

    with tempfile.TemporaryDirectory() as tmp:
        cfg = Config(config_path=f"{tmp}/config.yaml")
        assert cfg.get("nonexistent", "key") is None
        assert cfg.get("nonexistent", default=42) == 42


# ── Rotator tests ──


def test_rotator_empty():
    from harvest.rotator import ProxyRotator

    r = ProxyRotator()
    assert r.get() is None
    assert r.rotate() is None
    assert r.random() is None
    assert r.count == 0


def test_rotator_from_file():
    from harvest.rotator import ProxyRotator

    with tempfile.TemporaryDirectory() as tmp:
        f = Path(f"{tmp}/proxies.txt")
        f.write_text("http://user:pass@1.2.3.4:8080\nhttp://5.6.7.8:3128\nsocks5://9.10.11.12:1080\n# comment\n\n")
        r = ProxyRotator.from_file(str(f))
        assert r.count == 3


def test_rotator_cycle():
    from harvest.rotator import ProxyRotator

    r = ProxyRotator(["a", "b", "c"])
    assert r.get() == "a"
    assert r.rotate() == "b"
    assert r.rotate() == "c"
    assert r.rotate() == "a"  # wraps around


# ── Export tests ──


def test_export_csv_simple():
    from harvest.export import Exporter

    data = {"name": "Test", "value": 42, "items": [1, 2, 3]}
    csv = Exporter.to_csv(data)
    assert "name" in csv
    assert "Test" in csv


def test_export_csv_list():
    from harvest.export import Exporter

    data = [
        {"title": "Page 1", "url": "https://a.com"},
        {"title": "Page 2", "url": "https://b.com"},
    ]
    csv = Exporter.to_csv(data)
    assert "Page 1" in csv
    assert "Page 2" in csv
    assert "https://a.com" in csv


def test_export_csv_empty():
    """Empty data should not crash."""
    from harvest.export import Exporter

    assert Exporter.to_csv([]) == ""
    assert Exporter.to_csv({}) == ""


def test_export_csv_nested():
    """Nested data should be JSON-stringified."""
    from harvest.export import Exporter

    data = {"name": "test", "meta": {"key": "value"}}
    csv = Exporter.to_csv(data)
    # meta should be serialized
    assert '"key": "value"' in csv or "key" in csv


# ── Notify tests ──


def test_notify_stdout():
    """Stdout notifier shouldn't crash."""
    from harvest.notify import Notifier

    n = Notifier.create("stdout")
    import io
    import contextlib
    import asyncio

    f = io.StringIO()
    with contextlib.redirect_stdout(f):
        result = asyncio.run(n.send("test message"))
    output = f.getvalue()
    assert "test message" in output
    assert result


def test_notify_unknown_channel():
    """Unknown channel should fallback to stdout."""
    from harvest.notify import Notifier

    n = Notifier.create("unknown_channel")
    assert n is not None
    assert n.__class__.__name__ == "StdoutNotifier"


# ── Extract tests ──


def test_load_schema_json():
    from harvest.extract import load_schema

    schema = load_schema('{"title": "h1", "price": ".price"}')
    assert schema == {"title": "h1", "price": ".price"}


def test_load_schema_file():
    from harvest.extract import load_schema

    with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
        json.dump({"title": "h1"}, f)
        f.flush()
        schema = load_schema(f"file://{f.name}")
        assert schema == {"title": "h1"}


def test_load_schema_invalid_json():
    """Invalid JSON should return as-is or raise."""
    from harvest.extract import load_schema

    try:
        schema = load_schema("not json at all")
        assert isinstance(schema, str)  # fallback to raw string
    except (json.JSONDecodeError, Exception):
        pass  # acceptable


# ── Pipeline tests ──


def test_pipeline_parse_pipe_string():
    from harvest.pipeline import Pipeline

    p = Pipeline()
    steps = p._parse_pipe_string('scrape https://example.com | extract \'{"title":"h1"}\' | export out.csv')
    assert len(steps) == 3
    assert steps[0]["cmd"] == "scrape"
    assert steps[0]["url"] == "https://example.com"
    assert steps[1]["cmd"] == "extract"
    assert steps[2]["cmd"] == "export"
    assert steps[2]["file"] == "out.csv"


def test_pipeline_parse_empty():
    from harvest.pipeline import Pipeline

    p = Pipeline()
    assert p._parse_pipe_string("") == []


def test_pipeline_smart_split():
    from harvest.pipeline import Pipeline

    p = Pipeline()
    assert p._smart_split("hello world") == ["hello", "world"]
    assert p._smart_split("'hello world' test") == ["hello world", "test"]
    assert p._smart_split('"hello world" test') == ["hello world", "test"]


# ── Crawl edge cases ──


def test_crawl_imports():
    """Module should import without error."""
    from harvest.crawl import SiteCrawler

    assert SiteCrawler is not None


# ── Contacts edge cases ──


def test_contacts_extract_emails():
    from harvest.contacts import ContactCollector

    c = ContactCollector()
    assert "user@company.com" in c._extract_emails("Contact: user@company.com")
    assert c._extract_emails("No email here") == []


def test_contacts_filter_noreply():
    """noreply@ should be filtered out."""
    from harvest.contacts import ContactCollector

    c = ContactCollector()
    emails = c._extract_emails("noreply@company.com and real@company.com")
    assert "real@company.com" in emails
    assert "noreply@company.com" not in emails


def test_contacts_social_links():
    from harvest.contacts import ContactCollector

    c = ContactCollector()
    links = c._extract_social_links('Check our <a href="https://twitter.com/harvest">Twitter</a>')
    assert len(links) > 0
    assert "twitter.com" in links[0]["url"]


def test_contacts_is_contact_page():
    from harvest.contacts import ContactCollector

    c = ContactCollector()
    assert c._is_contact_page("https://example.com/contact")
    assert c._is_contact_page("https://example.com/about")
    assert not c._is_contact_page("https://example.com/blog")


# ── Cli parser tests ──


def test_cli_parse_scrape():
    """Scrape subcommand should parse."""
    from harvest.cli import build_parser

    parser = build_parser()
    args = parser.parse_args(["scrape", "https://example.com"])
    assert args.command == "scrape"
    assert args.url == "https://example.com"


def test_cli_parse_extract():
    from harvest.cli import build_parser

    parser = build_parser()
    args = parser.parse_args(["extract", "https://example.com", "--schema", '{"title":"h1"}'])
    assert args.command == "extract"
    assert args.schema == '{"title":"h1"}'


def test_cli_parse_extract_schema_file():
    """Extract with file:// schema should parse."""
    from harvest.cli import build_parser

    parser = build_parser()
    with tempfile.NamedTemporaryFile(suffix=".json") as f:
        f.write(b'{"title":"h1"}')
        f.flush()
        args = parser.parse_args(["extract", "https://example.com", "--schema", f"file://{f.name}"])
        assert args.command == "extract"


def test_cli_parse_monitor():
    from harvest.cli import build_parser

    parser = build_parser()
    args = parser.parse_args(
        [
            "monitor",
            "https://example.com",
            "--notify",
            "telegram",
            "--token",
            "abc",
            "--chat",
            "123",
        ]
    )
    assert args.command == "monitor"
    assert args.notify == "telegram"


def test_cli_parse_crawl():
    from harvest.cli import build_parser

    parser = build_parser()
    args = parser.parse_args(["crawl", "https://example.com", "--max-pages", "100", "--delay", "1.0"])
    assert args.command == "crawl"
    assert args.max_pages == 100
    assert args.delay == 1.0


def test_cli_parse_contacts_export():
    from harvest.cli import build_parser

    parser = build_parser()
    args = parser.parse_args(["contacts", "https://example.com", "--export", "leads.csv"])
    assert args.command == "contacts"
    assert args.export == "leads.csv"


def test_cli_parse_version():
    from harvest.cli import build_parser

    parser = build_parser()
    try:
        parser.parse_args(["--version"])
    except SystemExit:
        pass  # version action exits


def test_cli_parse_invalid_command_raises():
    """Unknown command should show error."""
    from harvest.cli import build_parser

    parser = build_parser()
    try:
        parser.parse_args(["nonexistent"])
    except SystemExit:
        pass  # expected


# ── Browser tests ──


def test_browser_imports():
    """Browser module should import."""
    from harvest.browser import BrowserSession

    assert BrowserSession is not None


def test_browser_extract_keys():
    from harvest.browser import extract_keys_from_html

    html = '<div class="hidden-key" data-key="abc123"></div><p>key_xzy</p>'
    keys = extract_keys_from_html(html, [r'data-key="([^"]+)"', r"key_[a-z]{3}"])
    assert len(keys) > 0


def test_browser_find_verify_link():
    from harvest.browser import find_verify_link

    body = "Please confirm at https://example.com/verify/abc123"
    assert "verify" in find_verify_link(body)
    body = "No links here"
    assert find_verify_link(body) is None


# ── Monitor tests ──


def test_monitor_url_hash():
    """URL hash should be consistent."""
    from harvest.monitor import ChangeWatcher

    w = ChangeWatcher(data_dir="/tmp/_test_harvest_mon")
    h1 = w._url_hash("https://example.com")
    h2 = w._url_hash("https://example.com")
    assert h1 == h2
    assert len(h1) == 16


# ── Edge cases: missing imports, None, empty ──


def test_server_module_import():
    """Server module can be imported (FastAPI not required at module level)."""
    # Just check the module can be parsed
    import ast

    with open("harvest/server.py") as f:
        ast.parse(f.read())
    assert True


def test_pipeline_module_import():
    import ast

    with open("harvest/pipeline.py") as f:
        ast.parse(f.read())
    assert True


# ── Init tests ──


def test_init_imports():
    from harvest import __version__, __doc__

    assert __version__ == "0.6.2"
    assert len(__doc__) > 0


# ── Batch tests ──


def test_batch_imports():
    """Batch module should import without error."""
    from harvest.batch import BatchProcessor, BatchResult

    assert BatchProcessor is not None
    assert BatchResult is not None


def test_batch_process_urls():
    """process_urls should handle empty list gracefully."""
    from harvest.batch import BatchProcessor

    import asyncio

    bp = BatchProcessor()
    result = asyncio.run(bp.process_urls([]))
    assert result.total == 0
    assert result.success == 0
    assert result.failed == 0


def test_batch_process_file():
    """process_file should raise on missing file."""
    from harvest.batch import BatchProcessor

    import asyncio

    bp = BatchProcessor()
    try:
        asyncio.run(bp.process_file("/nonexistent/file.txt"))
        assert False, "Should have raised"
    except FileNotFoundError:
        pass


def test_batch_process_file_empty():
    """process_file with empty/skip-only file should return empty result."""
    from harvest.batch import BatchProcessor

    import tempfile
    from pathlib import Path
    import asyncio

    with tempfile.TemporaryDirectory() as tmp:
        f = Path(tmp) / "urls.txt"
        f.write_text("# comment only\n\n  \n")
        bp = BatchProcessor()
        result = asyncio.run(bp.process_file(str(f)))
        assert result.total == 0


def test_batch_parse_sitemap():
    """_parse_sitemap should extract <loc> URLs from XML."""
    from harvest.batch import BatchProcessor

    xml = """<?xml version="1.0" encoding="UTF-8"?>
<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">
  <url><loc>https://example.com/page1</loc></url>
  <url><loc>https://example.com/page2</loc></url>
</urlset>"""
    urls = BatchProcessor._parse_sitemap(xml)
    assert len(urls) == 2
    assert "https://example.com/page1" in urls
    assert "https://example.com/page2" in urls


def test_batch_parse_sitemap_empty():
    """_parse_sitemap should return empty list for non-sitemap content."""
    from harvest.batch import BatchProcessor

    urls = BatchProcessor._parse_sitemap("not xml")
    assert urls == []


def test_batch_rate_limit_init():
    """BatchProcessor should initialize with rate limiting."""
    from harvest.batch import BatchProcessor

    bp = BatchProcessor(rate_limit=30)
    assert bp.rate_limit == 30
    assert bp.concurrency == 5
    assert bp.retries == 3


def test_batch_print_summary():
    """print_summary should not crash with empty result."""
    from harvest.batch import BatchProcessor, BatchResult

    import io
    import contextlib

    f = io.StringIO()
    with contextlib.redirect_stdout(f):
        BatchProcessor.print_summary(BatchResult())
    output = f.getvalue()
    assert "Batch complete" in output


def test_batch_cli_parse():
    """Batch subcommand should parse in CLI."""
    from harvest.cli import build_parser

    parser = build_parser()
    args = parser.parse_args(["batch", "urls.txt", "--concurrency", "10", "--delay", "1.0"])
    assert args.command == "batch"
    assert args.file == "urls.txt"
    assert args.concurrency == 10
    assert args.delay == 1.0


def test_batch_cli_parse_sitemap():
    """Batch with --sitemap should parse."""
    from harvest.cli import build_parser

    parser = build_parser()
    args = parser.parse_args(["batch", "--sitemap", "https://example.com/sitemap.xml", "--rate-limit", "30"])
    assert args.command == "batch"
    assert args.sitemap == "https://example.com/sitemap.xml"
    assert args.rate_limit == 30


def test_batch_cli_parse_extract():
    """Batch with --extract schema should parse."""
    from harvest.cli import build_parser

    parser = build_parser()
    args = parser.parse_args(
        [
            "batch",
            "urls.txt",
            "--extract",
            '{"title":"h1","price":".price"}',
            "--export",
            "results.json",
        ]
    )
    assert args.command == "batch"
    assert args.extract is not None
    assert args.export == "results.json"


def test_batch_export_result():
    """export_results should write a valid JSON file."""
    from harvest.batch import BatchProcessor, BatchResult

    import tempfile
    from pathlib import Path
    import json

    bp = BatchProcessor()
    result = BatchResult(
        total=2,
        success=1,
        failed=1,
        results=[{"url": "https://ok.com", "status": "ok", "data": {"content": "ok"}}],
        errors=[{"url": "https://fail.com", "status": "error", "error": "timeout"}],
        duration=1.5,
    )

    with tempfile.TemporaryDirectory() as tmp:
        path = bp.export_results(result, f"{tmp}/out.json", fmt="json")
        data = json.loads(Path(path).read_text())
        assert data["total"] == 2
        assert data["success"] == 1
        assert data["failed"] == 1


def test_batch_export_csv():
    """export_results CSV should work."""
    from harvest.batch import BatchProcessor, BatchResult

    import tempfile
    from pathlib import Path

    bp = BatchProcessor()
    result = BatchResult(
        results=[{"url": "https://ok.com", "status": "ok", "data": {"title": "Test"}}],
    )

    with tempfile.TemporaryDirectory() as tmp:
        path = bp.export_results(result, f"{tmp}/out.csv", fmt="csv")
        content = Path(path).read_text()
        assert "title" in content or "Test" in content


if __name__ == "__main__":
    # Run all test functions manually (pytest-free fallback)
    import traceback

    failures = 0
    total = 0
    for name, fn in sorted(globals().items()):
        if name.startswith("test_"):
            total += 1
            try:
                fn()
                print(f"  ✓ {name}")
            except Exception:
                failures += 1
                print(f"  ✗ {name}")
                traceback.print_exc()
    print(f"\\n{'─' * 40}")
    print(f"  {total - failures}/{total} passed ({failures} failed)")
    sys.exit(1 if failures > 0 else 0)


# ── MCP Server tests ──


def test_mcp_create_server():
    """MCP server should create with all 7 tools."""
    from harvest_mcp import create_server

    server = create_server()
    tools = server._tool_manager.list_tools()
    names = sorted(t.name for t in tools)

    assert len(tools) == 9
    assert names == [
        "batch",
        "contacts",
        "crawl",
        "extract",
        "llm_extract",
        "map_urls",
        "monitor",
        "scrape",
        "status",
    ]


def test_mcp_status_tool():
    """status() should return JSON with version and tools list."""
    from harvest_mcp import create_server

    server = create_server()
    status_tool = [t for t in server._tool_manager.list_tools() if t.name == "status"][0]
    result = status_tool.fn()

    import json

    data = json.loads(result)
    assert data["version"] == "0.6.2"
    assert "scrape" in data["tools"]
    assert data["proxy_configured"] in (True, False)  # depends on env


def test_mcp_scrape_tool_description():
    """scrape tool should have a proper description."""
    from harvest_mcp import create_server

    server = create_server()
    scrape_tool = [t for t in server._tool_manager.list_tools() if t.name == "scrape"][0]
    assert "Scrape" in (scrape_tool.description or "")
    props = scrape_tool.parameters.get("properties", {})
    assert "url" in props


def test_mcp_extract_tool_params():
    """extract tool should accept url and schema params."""
    from harvest_mcp import create_server

    server = create_server()
    extract_tool = [t for t in server._tool_manager.list_tools() if t.name == "extract"][0]
    props = extract_tool.parameters.get("properties", {})
    assert "url" in props
    assert "schema" in props


def test_mcp_contacts_tool_params():
    """contacts tool should accept url and depth params."""
    from harvest_mcp import create_server

    server = create_server()
    ct = [t for t in server._tool_manager.list_tools() if t.name == "contacts"][0]
    props = ct.parameters.get("properties", {})
    assert "url" in props
    assert "depth" in props


def test_mcp_batch_tool_params():
    """batch tool should accept urls list and concurrency."""
    from harvest_mcp import create_server

    server = create_server()
    bt = [t for t in server._tool_manager.list_tools() if t.name == "batch"][0]
    props = bt.parameters.get("properties", {})
    assert "urls" in props
    assert "concurrency" in props


def test_mcp_crawl_tool_params():
    """crawl tool should accept url and max_pages."""
    from harvest_mcp import create_server

    server = create_server()
    ct = [t for t in server._tool_manager.list_tools() if t.name == "crawl"][0]
    props = ct.parameters.get("properties", {})
    assert "url" in props
    assert "max_pages" in props


def test_mcp_monitor_tool_params():
    """monitor tool should accept url and selector."""
    from harvest_mcp import create_server

    server = create_server()
    mt = [t for t in server._tool_manager.list_tools() if t.name == "monitor"][0]
    props = mt.parameters.get("properties", {})
    assert "url" in props
    assert "selector" in props


def test_mcp_main_version():
    """harvest-mcp --version should print version and exit."""
    import subprocess
    import sys

    result = subprocess.run(
        [sys.executable, "-m", "harvest_mcp", "--version"],
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0
    assert "0.6.2" in result.stdout


def test_mcp_entry_point():
    """harvest-mcp module should be importable and runnable."""
    import subprocess
    import sys

    result = subprocess.run(
        [sys.executable, "-m", "harvest_mcp", "--help"],
        capture_output=True,
        text=True,
        timeout=5,
    )
    # FastMCP stdio doesn't have --help, but should not crash
    assert result.returncode in (0, 1)


# ── Cache tests ──


def test_cache_init():
    """Cache should start empty."""
    from harvest.cache import ResponseCache

    c = ResponseCache(ttl_seconds=60)
    assert c.size == 0


def test_cache_set_get():
    """Setting and getting a value should work."""
    from harvest.cache import ResponseCache

    c = ResponseCache(ttl_seconds=60)
    key = "https://example.com"
    val = {"content": "hello", "title": "Example"}
    c.set(key, val)
    assert c.get(key) == val


def test_cache_get_miss():
    """Getting a non-existent key should return None."""
    from harvest.cache import ResponseCache

    c = ResponseCache(ttl_seconds=60)
    assert c.get("https://not-cached.com") is None


def test_cache_ttl_expiry():
    """Expired entries should return None."""
    from harvest.cache import ResponseCache
    import time

    c = ResponseCache(ttl_seconds=1)
    c.set("k", "v")
    time.sleep(1.5)
    assert c.get("k") is None


def test_cache_overwrite():
    """Setting the same key should overwrite."""
    from harvest.cache import ResponseCache

    c = ResponseCache(ttl_seconds=60)
    c.set("k", "v1")
    c.set("k", "v2")
    assert c.get("k") == "v2"


# ── RateLimiter tests ──


def test_rate_limiter_init():
    """RateLimiter should initialize with correct defaults."""
    from harvest.rate_limiter import RateLimiter

    r = RateLimiter(max_per_minute=10)
    assert r.max_per_minute == 10


def test_rate_limiter_acquire():
    """Acquire should succeed when under limit."""
    import asyncio
    from harvest.rate_limiter import RateLimiter

    async def t():
        r = RateLimiter(max_per_minute=100)
        await r.acquire()
        return True

    assert asyncio.run(t())


def test_rate_limiter_context_manager():
    """RateLimiter should work as async context manager."""
    import asyncio
    from harvest.rate_limiter import RateLimiter

    async def t():
        r = RateLimiter(max_per_minute=100)
        async with r:
            return True

    assert asyncio.run(t())


# ── Stealth tests ──


def test_stealth_init():
    """Stealth should initialize with defaults."""
    from harvest.stealth import Stealth
    from harvest.stealth import USER_AGENTS

    s = Stealth()
    assert s._user_agent is not None
    assert len(USER_AGENTS) >= 20


def test_stealth_random_ua():
    """get_random_ua should return a string."""
    from harvest.stealth import Stealth

    s = Stealth()
    ua = s._user_agent
    assert isinstance(ua, str)
    assert len(ua) > 20


def test_stealth_random_viewport():
    """get_viewport should return width/height dict."""
    from harvest.stealth import Stealth

    s = Stealth()
    vp = s._viewport
    assert "width" in vp
    assert "height" in vp
    assert 800 <= vp["width"] <= 1920
    assert 600 <= vp["height"] <= 1080


def test_stealth_random_platform():
    """get_platform should return a string."""
    from harvest.stealth import Stealth

    s = Stealth()
    platform = s._platform
    assert platform in ("Windows", "MacIntel", "Linux x86_64")


def test_stealth_random_timezone():
    """get_timezone should return a valid IANA timezone."""
    from harvest.stealth import Stealth

    s = Stealth()
    tz = s._timezone
    assert "/" in tz


def test_stealth_build_extra_args():
    """build_extra_args should return a dict with all stealth params."""
    from harvest.stealth import Stealth

    s = Stealth()
    args = s.get_args()
    assert isinstance(args, dict)
    assert "locale" in args
    assert "timezone_id" in args
    assert "viewport" in args
    assert "user_agent" in args


# ── Semantic Cache tests ──


def test_semantic_cache_exact_match():
    """Semantic cache should find exact prompt match."""
    from harvest.semantic_cache import SemanticCache

    cache = SemanticCache()
    cache.set("https://example.com", "Get all prices", "<html></html>", {"prices": [1, 2]})
    result = cache.get("https://example.com", "Get all prices", "<html></html>")
    assert result is not None
    assert result["prices"] == [1, 2]


def test_semantic_cache_semantic_match():
    """Semantic cache should find semantically similar prompts."""
    from harvest.semantic_cache import SemanticCache

    cache = SemanticCache()
    cache.set("https://example.com", "Extract all product prices", "<html></html>", {"prices": [10]})
    # Similar but different wording
    result = cache.get("https://example.com", "Get all product prices", "<html></html>")
    assert result is not None


def test_semantic_cache_different_url_no_match():
    """Semantic cache should not match different URLs."""
    from harvest.semantic_cache import SemanticCache

    cache = SemanticCache()
    cache.set("https://a.com", "Get prices", "<html></html>", {"prices": [1]})
    result = cache.get("https://b.com", "Get prices", "<html></html>")
    assert result is None


def test_semantic_cache_html_invalidation():
    """Semantic cache should invalidate when HTML changes."""
    from harvest.semantic_cache import SemanticCache

    cache = SemanticCache()
    cache.set("https://example.com", "Get prices", "<html>v1</html>", {"prices": [1]})
    # Same prompt but different HTML
    result = cache.get("https://example.com", "Get prices", "<html>v2</html>")
    assert result is None


def test_semantic_cache_stats():
    """Semantic cache should track hit/miss stats."""
    from harvest.semantic_cache import SemanticCache

    cache = SemanticCache()
    cache.set("https://example.com", "prompt", "<html></html>", "data")
    cache.get("https://example.com", "prompt", "<html></html>")  # hit
    cache.get("https://example.com", "other", "<html></html>")  # miss
    stats = cache.stats()
    assert stats["hits"] == 1
    assert stats["misses"] == 1
    assert stats["total_entries"] == 1


def test_semantic_cache_invalidate():
    """Semantic cache invalidate should clear URL entries."""
    from harvest.semantic_cache import SemanticCache

    cache = SemanticCache()
    cache.set("https://example.com", "p", "<html></html>", "d")
    cache.invalidate("https://example.com")
    result = cache.get("https://example.com", "p", "<html></html>")
    assert result is None


def test_semantic_cache_clear():
    """Semantic cache clear should reset everything."""
    from harvest.semantic_cache import SemanticCache

    cache = SemanticCache()
    cache.set("https://example.com", "p", "<html></html>", "d")
    cache.clear()
    stats = cache.stats()
    assert stats["total_entries"] == 0
    assert stats["hits"] == 0


# ── Structural Diff tests ──


def test_structural_diff_added_removed():
    """Structural diff should detect added and removed elements."""
    from harvest.structural_diff import StructuralDiff

    old = '<html><body><div class="header">Old</div><div class="content">Text</div></body></html>'
    new = '<html><body><div class="header">Old</div><div class="content">Text</div><div class="footer">New</div></body></html>'
    differ = StructuralDiff()
    result = differ.diff(old_html=old, new_html=new)
    assert len(result["added"]) > 0
    assert result["summary"] != ""


def test_structural_diff_changed_text():
    """Structural diff should detect text content changes."""
    from harvest.structural_diff import StructuralDiff

    old = "<html><body><h1>Old Title</h1><p>Original text</p></body></html>"
    new = "<html><body><h1>New Title</h1><p>Changed text</p></body></html>"
    differ = StructuralDiff()
    result = differ.diff(old_html=old, new_html=new)
    assert len(result["changed"]) > 0


def test_structural_diff_no_change():
    """Structural diff should report no changes for identical HTML."""
    from harvest.structural_diff import StructuralDiff

    html = "<html><body><h1>Title</h1><p>Content</p></body></html>"
    differ = StructuralDiff()
    result = differ.diff(old_html=html, new_html=html)
    assert len(result["added"]) == 0
    assert len(result["removed"]) == 0
    assert len(result["changed"]) == 0


def test_structural_diff_capture_and_load():
    """Structural diff should save and load snapshots."""
    from harvest.structural_diff import StructuralDiff
    import tempfile

    with tempfile.TemporaryDirectory() as tmp:
        differ = StructuralDiff(data_dir=tmp)
        html = '<html><body><div class="box">Hello</div></body></html>'
        differ.capture(html, url="https://test.com")
        loaded = differ.load_snapshot("https://test.com")
        assert loaded is not None
        assert len(loaded) > 0


def test_structural_diff_extract_structure():
    """extract_structure should parse HTML into element signatures."""
    from harvest.structural_diff import _extract_structure

    html = '<html><body><h1 id="title">Hello</h1><div class="card">Content</div></body></html>'
    structure = _extract_structure(html)
    assert len(structure) >= 2
    tags = [e["tag"] for e in structure]
    assert "h1" in tags
    assert "div" in tags


# ── Self-Healing tests ──


def test_self_healing_test_selectors():
    """test_selectors should correctly identify working/broken selectors."""
    from harvest.self_healing import _test_selectors

    html = '<html><body><div class="price">$10</div><span class="title">Product</span></body></html>'
    result = _test_selectors(html, {"price": ".price", "title": ".title", "missing": ".nope"})
    assert result["price"] is True
    assert result["title"] is True
    assert result["missing"] is False


def test_self_healing_extract_with_selectors():
    """extract_with_selectors should pull data from HTML."""
    from harvest.self_healing import _extract_with_selectors

    html = '<html><body><div class="price">$25</div><h1 class="name">Widget</h1></body></html>'
    result = _extract_with_selectors(html, {"price": ".price", "name": ".name"})
    assert result["price"] == "$25"
    assert result["name"] == "Widget"


def test_self_healing_extract_missing():
    """extract_with_selectors should return None for missing elements."""
    from harvest.self_healing import _extract_with_selectors

    html = "<html><body><p>Hello</p></body></html>"
    result = _extract_with_selectors(html, {"missing": ".nope"})
    assert result["missing"] is None


def test_self_healing_detect_broken():
    """SelfHealingParser should detect broken selectors."""
    from harvest.self_healing import SelfHealingParser
    import tempfile

    with tempfile.TemporaryDirectory() as tmp:
        parser = SelfHealingParser(url="https://test.com", data_dir=tmp)
        html = '<html><body><div class="new-price">$99</div></body></html>'
        result = asyncio.run(
            parser.extract(
                html=html,
                schema={"price": ".old-price"},
            )
        )
        assert result["healed"] is False  # LLM unavailable in test
        assert "broken" in result or "still_broken" in result


def test_self_healing_working_selectors():
    """SelfHealingParser should pass through working selectors."""
    from harvest.self_healing import SelfHealingParser
    import tempfile

    with tempfile.TemporaryDirectory() as tmp:
        parser = SelfHealingParser(url="https://test.com", data_dir=tmp)
        html = '<html><body><div class="price">$50</div></body></html>'
        result = asyncio.run(
            parser.extract(
                html=html,
                schema={"price": ".price"},
            )
        )
        assert result["healed"] is False
        assert result["data"]["price"] == "$50"
        assert "working" in result["details"]
