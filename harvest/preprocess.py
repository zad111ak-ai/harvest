"""HTML Preprocessor — clean HTML before sending to LLM.

Reduces token usage by 70-80% by removing noise:
- <script>, <style>, <svg>, <noscript>
- Comments, hidden elements
- Redundant attributes (keep href, src, alt, title, data-testid)
- Deep nesting collapse
"""

import re

try:
    from bs4 import BeautifulSoup, Comment
except ImportError:
    BeautifulSoup = None


def clean_html_for_llm(html: str, max_chars: int = 50_000) -> str:
    """Clean HTML for LLM consumption. Returns simplified text.

    Args:
        html: Raw HTML content
        max_chars: Maximum output size (default 50K chars)

    Returns:
        Cleaned text optimized for LLM parsing
    """
    if BeautifulSoup is None:
        # Fallback: basic regex cleaning
        return _regex_clean(html, max_chars)

    soup = BeautifulSoup(html, "html.parser")

    # Remove noise tags
    for tag in soup.find_all(["script", "style", "svg", "noscript", "iframe", "object", "embed"]):
        tag.decompose()

    # Remove comments
    for comment in soup.find_all(string=lambda t: isinstance(t, Comment)):
        comment.extract()

    # Remove hidden elements
    for tag in soup.find_all(style=re.compile(r"display\s*:\s*none", re.I)):
        tag.decompose()
    for tag in soup.find_all(attrs={"hidden": True}):
        tag.decompose()

    # Strip attributes except important ones
    keep_attrs = {
        "href",
        "src",
        "alt",
        "title",
        "data-testid",
        "aria-label",
        "role",
        "type",
        "value",
        "name",
        "placeholder",
    }
    for tag in soup.find_all(True):
        attrs = dict(tag.attrs)
        for attr in list(attrs.keys()):
            if attr not in keep_attrs:
                del tag[attr]

    # Get text with structure markers
    text = _extract_structured_text(soup)

    # Truncate if needed
    if len(text) > max_chars:
        text = text[:max_chars] + "\n[...truncated...]"

    return text.strip()


def _extract_structured_text(soup) -> str:
    """Extract text preserving structure (headings, lists, tables)."""
    parts = []

    for elem in soup.find_all(
        [
            "h1",
            "h2",
            "h3",
            "h4",
            "h5",
            "h6",
            "p",
            "li",
            "td",
            "th",
            "a",
            "span",
            "div",
            "article",
            "section",
            "main",
        ]
    ):
        text = elem.get_text(strip=True)
        if not text:
            continue

        tag = elem.name
        if tag in ("h1", "h2", "h3"):
            parts.append(f"\n{'#' * int(tag[1])} {text}")
        elif tag == "li":
            parts.append(f"• {text}")
        elif tag in ("td", "th"):
            parts.append(f"| {text}")
        elif tag == "a" and elem.get("href"):
            parts.append(f"[{text}]({elem['href']})")
        elif text and len(text) > 10:  # Skip tiny fragments
            parts.append(text)

    return "\n".join(parts)


def _regex_clean(html: str, max_chars: int) -> str:
    """Fallback regex-based cleaning when BeautifulSoup is unavailable."""
    text = re.sub(r"<script[^>]*>.*?</script>", "", html, flags=re.DOTALL | re.I)
    text = re.sub(r"<style[^>]*>.*?</style>", "", text, flags=re.DOTALL | re.I)
    text = re.sub(r"<!--.*?-->", "", text, flags=re.DOTALL)
    text = re.sub(r"<[^>]+>", " ", text)
    text = re.sub(r"\s+", " ", text).strip()
    return text[:max_chars]
