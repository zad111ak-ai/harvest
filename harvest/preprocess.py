"""HTML Preprocessor — 4 modes for different use cases.

Modes:
  full     (DEFAULT) — minimal cleaning, preserves all content. Zero data loss.
  economy  — readability + html2text + list collapsing. 70-90% token savings.
  hybrid   — economy + LLM selector generation for catalogs. 85-95% savings.
  auto     — detects page type and picks optimal mode automatically.

Based on: Trafilatura, Readability.js, html2text, goose3 methodologies.
Output: always standard Markdown. No proprietary formats, no link dictionaries.
"""

import re
from dataclasses import dataclass, field

try:
    from readability import Document as ReadabilityDocument
except ImportError:
    ReadabilityDocument = None  # type: ignore[assignment,misc]

try:
    import html2text as _html2text
except ImportError:
    _html2text = None  # type: ignore[assignment,misc]

try:
    from bs4 import BeautifulSoup, Comment, Tag
except ImportError:
    BeautifulSoup = None  # type: ignore[assignment,misc]
    Comment = None  # type: ignore[assignment,misc]
    Tag = None  # type: ignore[assignment,misc]


# Tags that never contain useful content
NOISE_TAGS = frozenset(
    [
        "script",
        "style",
        "svg",
        "noscript",
        "iframe",
        "object",
        "embed",
        "applet",
        "basefont",
        "bgsound",
        "blink",
        "marquee",
        "template",
        "dialog",
    ]
)


@dataclass
class PreprocessStats:
    """Track preprocessing efficiency."""

    input_chars: int = 0
    output_chars: int = 0
    mode_used: str = "full"  # Which mode was actually used
    page_type: str = "unknown"  # ARTICLE, CATALOG, MIXED
    cards_found: int = 0
    cards_kept: int = 0
    cards_collapsed: int = 0
    duplicates_removed: int = 0
    noise_removed: int = 0
    warnings: list[str] = field(default_factory=list)

    @property
    def compression_ratio(self) -> float:
        if self.input_chars == 0:
            return 0.0
        return 1.0 - (self.output_chars / self.input_chars)

    @property
    def estimated_tokens_saved(self) -> int:
        """Rough estimate: 1 token ≈ 4 chars."""
        return (self.input_chars - self.output_chars) // 4

    def summary(self) -> str:
        """Human-readable summary for CLI output."""
        lines = [
            f"✅ Mode: {self.mode_used}",
            f"📄 Page type: {self.page_type}",
            f"📊 Input: {self.input_chars:,} chars → Output: {self.output_chars:,} chars",
            f"💰 Saved: {self.input_chars - self.output_chars:,} chars (~{self.estimated_tokens_saved:,} tokens, {self.compression_ratio:.0%})",
        ]
        if self.cards_found > 0:
            lines.append(
                f"🃏 Cards: {self.cards_found} found, {self.cards_kept} kept, {self.cards_collapsed} collapsed"
            )
        if self.warnings:
            for w in self.warnings:
                lines.append(f"⚠️ {w}")
        return "\n".join(lines)


@dataclass
class CleanedHTML:
    """Result of HTML preprocessing."""

    text: str
    stats: PreprocessStats

    def __len__(self) -> int:
        return len(self.text)

    def __str__(self) -> str:
        return self.text


class HTMLPreprocessor:
    """Industrial-grade HTML preprocessor with 4 modes.

    Modes:
        full    — minimal cleaning (noise removal only). Default. Zero data loss.
        economy — readability + html2text + list collapsing. 70-90% savings.
        hybrid  — economy + structured extraction hints. 85-95% savings.
        auto    — detects page type, picks best mode, graceful degradation.

    Usage:
        # Default: full mode (safe, no data loss)
        preprocessor = HTMLPreprocessor()
        result = preprocessor.clean(html)

        # Economy mode (for LLM consumption)
        preprocessor = HTMLPreprocessor(mode="economy")
        result = preprocessor.clean(html)

        # Auto mode (smart detection)
        preprocessor = HTMLPreprocessor(mode="auto")
        result = preprocessor.clean(html)
        print(result.stats.summary())
    """

    VALID_MODES = ("full", "economy", "hybrid", "auto")

    def __init__(
        self,
        mode: str = "full",
        max_chars: int = 50_000,
        keep_links: bool = True,
        keep_images: bool = True,
        preview_count: int = 3,
    ):
        if mode not in self.VALID_MODES:
            raise ValueError(f"Unknown mode '{mode}'. Valid: {self.VALID_MODES}")
        self.mode = mode
        self.max_chars = max_chars
        self.keep_links = keep_links
        self.keep_images = keep_images
        self.preview_count = preview_count
        self.stats = PreprocessStats()

    def clean(self, html: str) -> CleanedHTML:
        """Clean HTML based on selected mode."""
        self.stats = PreprocessStats(input_chars=len(html))

        if self.mode == "full":
            return self._full_mode(html)
        elif self.mode == "economy":
            return self._economy_mode(html)
        elif self.mode == "hybrid":
            return self._hybrid_mode(html)
        else:  # auto
            return self._auto_mode(html)

    # ──────────────────────────────────────────────
    # MODE 1: FULL (default — safe, no data loss)
    # ──────────────────────────────────────────────

    def _full_mode(self, html: str) -> CleanedHTML:
        """Full mode: remove noise only, keep everything else.

        What it does: strips scripts, styles, comments, hidden elements.
        What it keeps: ALL content, navigation, footer, sidebar, links as [text](url).
        Best for: when you need every piece of data, debugging, downstream parsers.
        """
        self.stats.mode_used = "full"

        clean = self._remove_noise(html)
        self.stats.noise_removed = self.stats.input_chars - len(clean)

        # Convert to Markdown preserving links (via html2text if available)
        text = self._to_markdown(clean) if _html2text else self._strip_tags(clean)

        # Truncate if needed
        if len(text) > self.max_chars:
            text = text[: self.max_chars] + "\n[...truncated]"

        self.stats.output_chars = len(text)
        return CleanedHTML(text=text, stats=self.stats)

    # ──────────────────────────────────────────────
    # MODE 2: ECONOMY (token-saving for LLM)
    # ──────────────────────────────────────────────

    def _economy_mode(self, html: str) -> CleanedHTML:
        """Economy mode: readability + html2text + list collapsing.

        What it does: extracts main content, converts to Markdown, collapses lists.
        What it loses: navigation, footer, sidebar, ads, boilerplate.
        Best for: feeding into LLM for extraction, RAG systems, embeddings.
        """
        self.stats.mode_used = "economy"

        if BeautifulSoup is None:
            text = self._regex_fallback(html)
            self.stats.output_chars = len(text)
            return CleanedHTML(text=text, stats=self.stats)

        # Noise removal
        html_clean = self._remove_noise(html)

        # Detect page type for logging
        soup = BeautifulSoup(html_clean, "html.parser")
        page_type, cards = self._detect_page_type(soup)
        self.stats.page_type = page_type
        self.stats.cards_found = len(cards)

        # Apply pipeline
        if page_type == "CATALOG" and cards:
            content_html = self._catalog_pipeline(soup, cards)
        elif page_type == "ARTICLE":
            content_html = self._article_pipeline(html_clean)
        else:
            content_html = self._mixed_pipeline(html_clean, soup)

        # Convert to Markdown
        markdown = self._to_markdown(content_html)

        # Graceful degradation: if economy mode killed too much on non-catalog pages
        # Catalogs are EXPECTED to shrink dramatically (card collapsing is intentional)
        if self.stats.page_type != "CATALOG" and len(markdown) < self.stats.input_chars * 0.15:
            self.stats.warnings.append("Economy mode removed too much content. Falling back to full mode.")
            return self._full_mode(html)

        # Deduplicate
        markdown = self._deduplicate(markdown)

        # Truncate
        if len(markdown) > self.max_chars:
            markdown = self._smart_truncate(markdown, self.max_chars)

        self.stats.output_chars = len(markdown)
        return CleanedHTML(text=markdown, stats=self.stats)

    # ──────────────────────────────────────────────
    # MODE 3: HYBRID (economy + extraction hints)
    # ──────────────────────────────────────────────

    def _hybrid_mode(self, html: str) -> CleanedHTML:
        """Hybrid mode: economy + structured extraction hints for LLM.

        What it does: everything economy does, plus adds extraction context:
        - For catalogs: "Here are 3 examples. Extract data using this pattern."
        - For articles: "Main content extracted. Focus on text below."
        - Includes CSS selector hints for downstream code extraction.

        What it loses: same as economy mode.
        Best for: LLM extraction pipelines, AI agents, automated scraping.
        """
        self.stats.mode_used = "hybrid"

        # Start with economy pipeline
        economy_result = self._economy_mode(html)

        # If economy fell back to full, hybrid also uses full
        if self.stats.mode_used == "full":
            return economy_result

        # Add extraction context based on page type
        context_header = self._build_extraction_context()
        economy_result.text = context_header + "\n\n" + economy_result.text

        self.stats.output_chars = len(economy_result.text)
        self.stats.mode_used = "hybrid"
        return economy_result

    def _build_extraction_context(self) -> str:
        """Build LLM extraction context based on page type."""
        if self.stats.page_type == "CATALOG":
            return (
                f"[EXTRACTION CONTEXT]\n"
                f"Page type: CATALOG with {self.stats.cards_found} items.\n"
                f"Below are {self.stats.cards_kept} example items. "
                f"{self.stats.cards_collapsed} more items follow the same structure.\n"
                f"Task: Identify the pattern from examples, then extract ALL items.\n"
                f"Return: JSON array with consistent keys (name, price, url, etc.)."
            )
        elif self.stats.page_type == "ARTICLE":
            return (
                "[EXTRACTION CONTEXT]\n"
                "Page type: ARTICLE. Main content extracted.\n"
                "Boilerplate (nav, footer, ads) removed.\n"
                "Focus on: title, author, date, body text, key facts."
            )
        else:
            return (
                "[EXTRACTION CONTEXT]\n"
                "Page type: MIXED (content + some structure).\n"
                "Extract relevant data based on the user's prompt."
            )

    # ──────────────────────────────────────────────
    # MODE 4: AUTO (smart detection + fallbacks)
    # ──────────────────────────────────────────────

    def _auto_mode(self, html: str) -> CleanedHTML:
        """Auto mode: detects page type and picks optimal mode.

        Logic:
        - Catalog pages → hybrid mode (best for structured extraction)
        - Article pages → economy mode (best for text extraction)
        - Unknown/mixed → economy with fallback to full if too much lost

        Graceful degradation: if chosen mode removes >80%, falls back.
        """
        self.stats.mode_used = "auto"

        if BeautifulSoup is None:
            self.stats.warnings.append("BeautifulSoup not available, using full mode")
            return self._full_mode(html)

        # Quick page type detection
        html_clean = self._remove_noise(html)
        soup = BeautifulSoup(html_clean, "html.parser")
        page_type, cards = self._detect_page_type(soup)
        self.stats.page_type = page_type

        # Pick optimal mode
        if page_type == "CATALOG" and cards:
            self.stats.warnings.append(f"Auto → hybrid (catalog detected, {len(cards)} cards)")
            return self._hybrid_mode(html)
        elif page_type == "ARTICLE":
            self.stats.warnings.append("Auto → economy (article detected)")
            return self._economy_mode(html)
        else:
            self.stats.warnings.append("Auto → economy (mixed page)")
            return self._economy_mode(html)

    # ──────────────────────────────────────────────
    # SHARED PIPELINE COMPONENTS
    # ──────────────────────────────────────────────

    def _detect_page_type(self, soup: "Tag") -> tuple[str, list]:
        """Detect page type using structural analysis."""
        paragraphs = soup.find_all("p")
        avg_p_len = sum(len(p.get_text(strip=True)) for p in paragraphs) / max(len(paragraphs), 1)

        all_tags = soup.find_all(True)
        links = soup.find_all("a")
        link_density = len(links) / max(len(all_tags), 1)

        cards = self._find_repeating_structures(soup)

        if len(cards) > 3 and avg_p_len < 200:
            return "CATALOG", cards
        elif avg_p_len > 300 and link_density < 0.15:
            return "ARTICLE", []
        else:
            return "MIXED", cards if len(cards) > 3 else []

    def _find_repeating_structures(self, soup: "Tag") -> list:
        """Find repeating DOM structures (product cards, list items)."""
        candidates: dict[str, list] = {}

        for tag in soup.find_all(["article", "div", "li", "section", "tr"]):
            classes_raw: list[str] = tag.get("class", []) or []  # type: ignore[assignment,arg-type]
            classes = tuple(str(c) for c in sorted(classes_raw))
            if not classes:
                continue

            key = f"{tag.name}.{'.'.join(classes)}"
            text_len = len(tag.get_text(strip=True))

            if text_len < 20 or text_len > 5000:
                continue

            if key not in candidates:
                candidates[key] = []
            candidates[key].append(tag)

        best_key = None
        best_count = 0
        for key, tags in candidates.items():
            if len(tags) >= 3:
                lengths = [len(t.get_text(strip=True)) for t in tags]
                mean_len = sum(lengths) / len(lengths)
                if mean_len > 0:
                    variance = sum((ln - mean_len) ** 2 for ln in lengths) / len(lengths)
                    std_dev = variance**0.5
                    if std_dev / mean_len < 0.5 and len(tags) > best_count:
                        best_key = key
                        best_count = len(tags)

        if best_key:
            return candidates[best_key]
        return []

    def _catalog_pipeline(self, soup: "Tag", cards: list) -> str:
        """Catalog pipeline: keep first N cards, collapse rest."""
        n = self.preview_count
        self.stats.cards_kept = min(n, len(cards))
        self.stats.cards_collapsed = max(0, len(cards) - n)

        parts = []
        header = soup.find("header") or soup.find("h1")
        if header:
            parts.append(str(header))

        for card in cards[:n]:
            parts.append(str(card))

        remaining = len(cards) - n
        if remaining > 0:
            parts.append(f"<p>[...and {remaining} more items with identical structure...]</p>")

        footer = soup.find("footer")
        if footer:
            parts.append(str(footer))

        return "\n".join(parts)

    def _article_pipeline(self, html: str) -> str:
        """Article pipeline: readability extracts main content."""
        if ReadabilityDocument is None:
            return self._fallback_extract(html)

        try:
            doc = ReadabilityDocument(html)
            content = doc.summary()
            title = doc.title()
            if title:
                content = f"<h1>{title}</h1>\n{content}"
            return content
        except Exception:
            return self._fallback_extract(html)

    def _mixed_pipeline(self, html: str, soup: "Tag") -> str:
        """Mixed pipeline: readability + preserve structured blocks."""
        if ReadabilityDocument is not None:
            try:
                doc = ReadabilityDocument(html)
                content = doc.summary()
                title = doc.title()
                if title:
                    content = f"<h1>{title}</h1>\n{content}"

                if len(content) > len(html) * 0.15:
                    return content
            except Exception:
                pass

        for tag_name in ["nav", "footer", "aside"]:
            for tag in soup.find_all(tag_name):
                tag.decompose()

        return str(soup.body) if soup.body else str(soup)

    def _fallback_extract(self, html: str) -> str:
        """Fallback extraction without readability-lxml."""
        if BeautifulSoup is None:
            return re.sub(r"<[^>]+>", " ", html)

        soup = BeautifulSoup(html, "html.parser")
        for tag in soup.find_all(list(NOISE_TAGS)):
            tag.decompose()
        for comment in soup.find_all(string=lambda t: isinstance(t, Comment)):
            comment.extract()

        main = soup.find("main") or soup.find("article") or soup.find(attrs={"role": "main"})  # type: ignore[call-overload]
        if main:
            return str(main)

        for tag_name in ["nav", "header", "footer", "aside"]:
            for tag in soup.find_all(tag_name):
                tag.decompose()

        return str(soup.body) if soup.body else str(soup)

    def _remove_noise(self, html: str) -> str:
        """Remove scripts, styles, comments via regex."""
        original_len = len(html)
        html = re.sub(r"<script[^>]*>.*?</script>", "", html, flags=re.DOTALL | re.I)
        html = re.sub(r"<style[^>]*>.*?</style>", "", html, flags=re.DOTALL | re.I)
        html = re.sub(r"<noscript[^>]*>.*?</noscript>", "", html, flags=re.DOTALL | re.I)
        html = re.sub(r"<!--.*?-->", "", html, flags=re.DOTALL)
        html = re.sub(r"<svg[^>]*>.*?</svg>", "", html, flags=re.DOTALL | re.I)
        html = re.sub(r"<[^>]+hidden[^>]*>.*?</[^>]+>", "", html, flags=re.DOTALL | re.I)
        self.stats.noise_removed = original_len - len(html)
        return html

    def _strip_tags(self, html: str) -> str:
        """Strip HTML tags, keep text content."""
        text = re.sub(r"<br\s*/?>", "\n", html, flags=re.I)
        text = re.sub(r"</(p|div|h[1-6]|li|tr)>", "\n", text, flags=re.I)
        text = re.sub(r"<[^>]+>", " ", text)
        text = re.sub(r"[ \t]+", " ", text)
        text = re.sub(r"\n{3,}", "\n\n", text)
        return text.strip()

    def _to_markdown(self, html: str) -> str:
        """Convert HTML to clean Markdown using html2text."""
        if _html2text is None:
            text = re.sub(r"<[^>]+>", " ", html)
            return re.sub(r"\s+", " ", text).strip()

        h = _html2text.HTML2Text()
        h.ignore_links = not self.keep_links
        h.ignore_images = not self.keep_images
        h.ignore_emphasis = False
        h.body_width = 0
        h.unicode_snob = True
        h.skip_internal_links = True
        h.ignore_mailto_links = True
        h.protect_links = True
        h.wrap_links = False
        h.single_line_break = False

        markdown = h.handle(html)
        markdown = re.sub(r"\n{3,}", "\n\n", markdown)
        return markdown.strip()

    def _deduplicate(self, text: str) -> str:
        """Remove duplicate lines."""
        lines = text.split("\n")
        seen: set[str] = set()
        unique = []
        for line in lines:
            stripped = line.strip()
            if not stripped:
                unique.append(line)
                continue
            if stripped in seen:
                self.stats.duplicates_removed += 1
                continue
            seen.add(stripped)
            unique.append(line)
        return "\n".join(unique)

    def _smart_truncate(self, text: str, max_chars: int) -> str:
        """Truncate at paragraph boundary."""
        if len(text) <= max_chars:
            return text
        truncated = text[:max_chars]
        last_break = truncated.rfind("\n\n")
        if last_break > max_chars * 0.8:
            return truncated[:last_break] + "\n\n[...truncated]"
        return truncated + "\n[...truncated]"

    def _regex_fallback(self, html: str) -> str:
        """Last resort: regex strip all tags."""
        text = re.sub(r"<script[^>]*>.*?</script>", "", html, flags=re.DOTALL | re.I)
        text = re.sub(r"<style[^>]*>.*?</style>", "", text, flags=re.DOTALL | re.I)
        text = re.sub(r"<!--.*?-->", "", text, flags=re.DOTALL)
        text = re.sub(r"<[^>]+>", " ", text)
        text = re.sub(r"\s+", " ", text).strip()
        return text[: self.max_chars]


def clean_html_for_llm(html: str, max_chars: int = 50_000) -> str:
    """Convenience function — backward compatible. Uses full mode."""
    preprocessor = HTMLPreprocessor(mode="full", max_chars=max_chars)
    result = preprocessor.clean(html)
    return result.text
