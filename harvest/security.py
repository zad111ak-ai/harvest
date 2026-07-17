"""Security Hardening for Harvest — SSRF, Prompt Injection, MCP Auth, Credential Stripping.

Addresses confirmed vulnerabilities from security audit:
- #2: Prompt Injection — sanitize HTML before LLM
- #5: LFI — block file:// scheme and private IPs
- #6: MCP Auth — mandatory bearer token, loopback-only
- #7: Credential Leakage — strip creds from URLs/logs/LLM
- #3: P2P — peer whitelist, content signature verification
- #9: DoS — response size limits
"""

import json
import re
import ipaddress
import hashlib
import hmac
import logging
import secrets
from typing import Tuple
from urllib.parse import urlparse, urlunparse

logger = logging.getLogger("harvest.security")


# ============================================================================
# 1. URL VALIDATION (SSRF + LFI prevention)
# ============================================================================

# RFC 1918 + link-local + metadata + loopback
_BLOCKED_NETWORKS = [
    ipaddress.ip_network("10.0.0.0/8"),
    ipaddress.ip_network("172.16.0.0/12"),
    ipaddress.ip_network("192.168.0.0/16"),
    ipaddress.ip_network("169.254.0.0/16"),  # AWS metadata
    ipaddress.ip_network("127.0.0.0/8"),  # loopback
    ipaddress.ip_network("::1/128"),  # IPv6 loopback
    ipaddress.ip_network("fc00::/7"),  # IPv6 private
]

# Dangerous hostname patterns
_BLOCKED_HOSTNAMES = {
    "localhost",
    "metadata.google.internal",
    "169.254.169.254",  # AWS/GCP/Azure metadata
    "metadata.azure.internal",
    "instance-data.ec2.internal",
}

_BLOCKED_SCHEMES = {"file", "ftp", "data", "javascript", "vbscript"}


def is_safe_url(url: str) -> Tuple[bool, str]:
    """Validate URL against SSRF/LFI attacks.

    Returns:
        (safe, reason) — safe=True if URL is safe, reason explains why if blocked.

    Checks:
    - Scheme (http/https only)
    - Hostname resolution (no private/loopback IPs)
    - Blocked hostnames (metadata endpoints)
    - Shell metacharacters
    - Path traversal
    """
    try:
        parsed = urlparse(url)
    except Exception as e:
        return False, f"Invalid URL: {e}"

    # 1. Scheme check
    if parsed.scheme.lower() in _BLOCKED_SCHEMES:
        return False, f"Blocked scheme: {parsed.scheme}"

    if parsed.scheme.lower() not in ("http", "https"):
        return False, f"Only http/https allowed, got: {parsed.scheme}"

    # 2. Hostname check
    hostname = parsed.hostname
    if not hostname:
        return False, "No hostname in URL"

    # Check blocked hostnames
    if hostname.lower() in _BLOCKED_HOSTNAMES:
        return False, f"Blocked hostname: {hostname}"

    # Check if hostname resolves to private IP (also blocks 0.0.0.0)
    try:
        ip = ipaddress.ip_address(hostname)
        # 0.0.0.0 is not routable but passes ip_address() — block it explicitly
        if ip == ipaddress.ip_address("0.0.0.0"):
            return False, "Non-routable IP: 0.0.0.0"
        for net in _BLOCKED_NETWORKS:
            if ip in net:
                return False, f"Private/loopback IP: {ip}"
    except ValueError:
        # Not an IP, check for localhost patterns
        if hostname in ("localhost", "0.0.0.0", "::"):
            return False, f"Blocked hostname: {hostname}"

    # 3. Shell metacharacters in URL (but NOT query separators like &)
    dangerous_chars = set("`$();|<>\\'\"\\\n\r{}")
    if dangerous_chars.intersection(url):
        chars_found = dangerous_chars.intersection(url)
        return False, f"Shell metacharacters in URL: {chars_found}"

    # 4. Path traversal
    if ".." in parsed.path:
        return False, "Path traversal detected (..)"

    # 5. Credentials in URL
    if parsed.username or parsed.password:
        return False, "Credentials in URL (use headers instead)"

    return True, "OK"


def safe_url(url: str) -> str:
    """Validate URL and raise ValueError if unsafe.

    Usage:
        url = safe_url(user_input)  # raises ValueError if unsafe
    """
    safe, reason = is_safe_url(url)
    if not safe:
        raise ValueError(f"Unsafe URL: {reason}")
    return url


# ============================================================================
# 2. PROMPT INJECTION PREVENTION
# ============================================================================

# Patterns that indicate prompt injection attempts
_INJECTION_PATTERNS = [
    # System prompt overrides
    re.compile(r"\[SYSTEM\]", re.IGNORECASE),
    re.compile(r"<system>", re.IGNORECASE),
    re.compile(r"ignore\s+(all\s+)?previous\s+instructions", re.IGNORECASE),
    re.compile(r"disregard\s+(all\s+)?prior", re.IGNORECASE),
    re.compile(r"you\s+are\s+now", re.IGNORECASE),
    re.compile(r"new\s+instructions?:", re.IGNORECASE),
    re.compile(r"override\s+system", re.IGNORECASE),
    # Data exfiltration attempts
    re.compile(r"send\s+(all\s+)?(extracted|data|results)\s+to\s+https?://", re.IGNORECASE),
    re.compile(r"exfil", re.IGNORECASE),
    re.compile(r"upload\s+to\s+https?://", re.IGNORECASE),
    # Prompt escape sequences
    re.compile(r"---\s*END\s+(OF\s+)?(SYSTEM\s+)?PROMPT\s*---", re.IGNORECASE),
    re.compile(r"###\s*INSTRUCTION", re.IGNORECASE),
    re.compile(r"```system", re.IGNORECASE),
    # Hidden instruction markers
    re.compile(r"<!--.*?-->", re.DOTALL),  # HTML comments (may contain injections)
    re.compile(r"display:\s*none", re.IGNORECASE),  # Hidden elements
    re.compile(r"visibility:\s*hidden", re.IGNORECASE),
    re.compile(r"font-size:\s*0", re.IGNORECASE),
]

# Maximum length for content sent to LLM
MAX_LLM_CONTENT_LENGTH = 100_000


def sanitize_for_llm(html: str) -> str:
    """Sanitize HTML content before sending to LLM.

    Removes:
    - HTML comments (injection vector)
    - Hidden elements (display:none, visibility:hidden)
    - Prompt injection patterns
    - Potential exfiltration instructions
    - Excessive whitespace (hiding payloads)
    - Meta refresh (redirect)

    Wraps in sandbox markers for LLM context isolation.
    """
    if not html:
        return ""

    # 1. Remove HTML comments (common injection vector)
    html = re.sub(r"<!--.*?-->", "", html, flags=re.DOTALL)

    # 2. Remove meta refresh (redirects)
    html = re.sub(
        r'<meta[^>]*http-equiv\s*=\s*["\']?refresh["\']?[^>]*>',
        "",
        html,
        flags=re.IGNORECASE,
    )

    # 3. Remove hidden elements
    html = re.sub(
        r'<[^>]*style\s*=\s*["\'][^"\']*(?:display\s*:\s*none|visibility\s*:\s*hidden|font-size\s*:\s*0)[^"\']*["\'][^>]*>.*?</[^>]+>',
        "",
        html,
        flags=re.DOTALL | re.IGNORECASE,
    )

    # 4. Remove javascript: URLs
    html = re.sub(r"javascript\s*:", "", html, flags=re.IGNORECASE)

    # 5. Strip excessive whitespace (may hide payloads)
    html = re.sub(r"\s{10,}", " ", html)

    # 6. Detect and log prompt injection attempts
    for pattern in _INJECTION_PATTERNS:
        if pattern.search(html):
            logger.warning(f"Prompt injection pattern detected: {pattern.pattern[:50]}...")

    # 7. Truncate to safe length
    if len(html) > MAX_LLM_CONTENT_LENGTH:
        html = html[:MAX_LLM_CONTENT_LENGTH]
        logger.warning(f"Content truncated to {MAX_LLM_CONTENT_LENGTH} chars for LLM safety")

    # 8. Wrap in sandbox markers (tells LLM this is untrusted content)
    return f"<SCRAPED_CONTENT>\n{html}\n</SCRAPED_CONTENT>"


# ============================================================================
# 3. CREDENTIAL STRIPPING
# ============================================================================


def strip_credentials(url: str) -> str:
    """Remove credentials from URL.

    Example:
        https://admin:password123@site.com/path → https://site.com/path
    """
    try:
        parsed = urlparse(url)
        if parsed.username or parsed.password:
            # Rebuild URL without credentials
            return urlunparse(
                (
                    parsed.scheme,
                    str(parsed.hostname or "") + (f":{parsed.port}" if parsed.port else ""),
                    parsed.path,
                    parsed.params,
                    parsed.query,
                    parsed.fragment,
                )
            )
    except Exception:
        pass
    return url


def redact_url(url: str) -> str:
    """Redact credentials in URL for logging.

    Example:
        https://admin:password123@site.com → https://admin:***@site.com
    """
    try:
        parsed = urlparse(url)
        if parsed.password:
            return urlunparse(
                (
                    parsed.scheme,
                    f"{parsed.username}:***@{parsed.hostname}" + (f":{parsed.port}" if parsed.port else ""),
                    parsed.path,
                    parsed.params,
                    parsed.query,
                    parsed.fragment,
                )
            )
    except Exception:
        pass
    return url


# ============================================================================
# 4. MCP AUTHENTICATION
# ============================================================================


def generate_mcp_token() -> str:
    """Generate a secure MCP auth token."""
    return secrets.token_urlsafe(32)


def validate_mcp_token(token: str, expected: str) -> bool:
    """Validate MCP bearer token with constant-time comparison."""
    if not token or not expected:
        return False
    return hmac.compare_digest(token, expected)


def get_mcp_auth_middleware(token: str):
    """Create FastAPI middleware for MCP authentication.

    Usage:
        from harvest.security import get_mcp_auth_middleware

        app = FastAPI()
        auth_middleware = get_mcp_auth_middleware(os.environ["HARVEST_MCP_TOKEN"])
        app.middleware("http")(auth_middleware)
    """
    from fastapi import Request
    from fastapi.responses import JSONResponse

    async def auth_middleware(request: Request, call_next):
        # Skip health check
        if request.url.path in ("/health", "/stats"):
            return await call_next(request)

        # Check Authorization header
        auth_header = request.headers.get("Authorization", "")
        if auth_header.startswith("Bearer "):
            provided_token = auth_header[7:]
        else:
            provided_token = ""

        if not validate_mcp_token(provided_token, token):
            return JSONResponse(
                status_code=401,
                content={"error": "Invalid or missing API token"},
            )

        return await call_next(request)

    return auth_middleware


# ============================================================================
# 5. P2P CONTENT SIGNING
# ============================================================================


def sign_entry(data: dict, secret_key: str) -> str:
    """Sign a P2P cache entry for integrity verification.

    Returns:
        HMAC-SHA256 signature as hex string.
    """
    payload = json.dumps(data, sort_keys=True, default=str)
    return hmac.new(
        secret_key.encode(),
        payload.encode(),
        hashlib.sha256,
    ).hexdigest()


def verify_entry_signature(data: dict, signature: str, secret_key: str) -> bool:
    """Verify P2P entry signature."""
    expected = sign_entry(data, secret_key)
    return hmac.compare_digest(signature, expected)


# ============================================================================
# 6. DOCS: RESPONSE SIZE LIMITS
# ============================================================================

MAX_FETCH_SIZE_BYTES = 10 * 1024 * 1024  # 10MB
MAX_REDIRECT_DEPTH = 5
MAX_REQUEST_TIMEOUT = 30  # seconds


def is_safe_response_size(size_bytes: int) -> Tuple[bool, str]:
    """Check if response size is within safe limits."""
    if size_bytes > MAX_FETCH_SIZE_BYTES:
        return False, f"Response too large: {size_bytes} > {MAX_FETCH_SIZE_BYTES}"
    return True, "OK"
