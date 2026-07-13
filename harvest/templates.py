"""Marketplace Templates — Structured extraction for popular e-commerce sites.

Usage:
    from harvest.templates import get_template
    tmpl = get_template("ozon")
    data = await tmpl.extract(page)
"""

import re
from dataclasses import dataclass
from typing import Optional


@dataclass
class Product:
    name: str
    price: Optional[float] = None
    currency: str = "RUB"
    url: Optional[str] = None
    image: Optional[str] = None
    rating: Optional[float] = None
    reviews: Optional[int] = None
    seller: Optional[str] = None


class MarketplaceTemplate:
    """Base class for marketplace extraction templates."""

    domain: str = ""
    name: str = ""

    async def extract(self, page) -> list[Product]:
        raise NotImplementedError

    @staticmethod
    def parse_price(text: str) -> Optional[float]:
        """Parse price from text like '30 690 ₽' or '1,299.99 $'."""
        if not text:
            return None
        cleaned = re.sub(r"[^\d.,]", "", text)
        if not cleaned:
            return None
        cleaned = cleaned.replace(" ", "").replace("\xa0", "").replace("\u2009", "")
        if "," in cleaned and "." in cleaned:
            cleaned = cleaned.replace(",", "")
        elif "," in cleaned:
            parts = cleaned.split(",")
            if len(parts[-1]) == 3:
                cleaned = cleaned.replace(",", "")
            else:
                cleaned = cleaned.replace(",", ".")
        try:
            return float(cleaned)
        except ValueError:
            return None


class OzonTemplate(MarketplaceTemplate):
    """Ozon.ru product listing extraction via get_all_text() line parsing.

    Matching strategy:
    1. Extract model number from LAST parentheses (e.g. DUAL-RTX5060-O8G)
    2. Normalize to lowercase, strip separators, match against URL path
    3. Fallback: brand + distinctive words from title vs URL
    """

    domain = "ozon.ru"
    name = "Ozon"

    @staticmethod
    def _normalize(s: str) -> str:
        """Normalize for matching: lowercase, strip all non-alphanumeric."""
        return re.sub(r"[^a-z0-9]", "", s.lower())

    async def extract(self, page) -> list[Product]:
        text = page.get_all_text() or ""
        lines = [line.strip() for line in text.split("\n") if line.strip()]

        # Build URL list from links
        links = page.find_all("a")
        href_list: list[str] = []
        for a in links:
            href = a.attrib.get("href", "") if hasattr(a, "attrib") else ""
            if "/product/" in href:
                clean = href.split("?")[0]
                if clean not in href_list:
                    href_list.append(clean)

        # Pre-normalize URLs for fast matching
        href_norm: list[tuple[str, str]] = [(u, self._normalize(u)) for u in href_list]

        products = []
        for i, line in enumerate(lines):
            if "ГБ" not in line:
                continue

            # Forward search for price
            price = None
            for j in range(i + 1, min(len(lines), i + 10)):
                m = re.match(r"^([\d\s\u2009\u00a0]+)\s*₽$", lines[j])
                if m:
                    clean = re.sub(r"[\s\u2009\u00a0]", "", m.group(1))
                    if clean.isdigit() and 1000 <= int(clean) <= 1000000:
                        price = float(clean)
                        break

            # Match URL
            url = None

            # Strategy 1: model number from LAST parentheses
            parens = re.findall(r"\(([^)]+)\)", line)
            model_str = None
            for p in reversed(parens):
                if re.search(r"[A-Z]{2,}|\d{3,}", p):
                    model_str = p.strip()
                    break

            if model_str:
                model_norm = self._normalize(model_str)
                if len(model_norm) >= 4:
                    for u, u_norm in href_norm:
                        if model_norm in u_norm:
                            url = f"https://www.ozon.ru{u}"
                            break

            # Strategy 2: brand + key model words match URL path
            if not url:
                words = line.split()
                if len(words) >= 3:
                    brand = words[0].lower()
                    skip = {
                        "видеокарта",
                        "geforce",
                        "rtx",
                        "5060",
                        "8",
                        "гб",
                        "gb",
                        "oc",
                        "max",
                    }
                    key_words = [w.lower() for w in words if w.lower() not in skip and len(w) > 3][:4]
                    for u, u_norm in href_norm:
                        if brand in u_norm and sum(1 for kw in key_words if kw in u_norm) >= 2:
                            url = f"https://www.ozon.ru{u}"
                            break

            products.append(Product(name=line, price=price, url=url, currency="RUB"))

        return products


class WildberriesTemplate(MarketplaceTemplate):
    """Wildberries product listing extraction."""

    domain = "wildberries.ru"
    name = "Wildberries"

    async def extract(self, page) -> list[Product]:
        text = page.get_all_text() or ""
        lines = [line.strip() for line in text.split("\n") if line.strip()]

        links = page.find_all("a")
        url_map: dict[str, str] = {}
        for a in links:
            href = a.attrib.get("href", "") if hasattr(a, "attrib") else ""
            name = (a.get_all_text() or "").strip()
            if "/catalog/" in href and name:
                if href not in url_map:
                    url_map[href] = name[:80]

        products = []
        for i, line in enumerate(lines):
            price = None
            for j in range(i + 1, min(len(lines), i + 8)):
                m = re.match(r"^([\d\s\u2009\u00a0]+)\s*₽$", lines[j])
                if m:
                    clean = re.sub(r"[\s\u2009\u00a0]", "", m.group(1))
                    if clean.isdigit() and 100 <= int(clean) <= 1000000:
                        price = float(clean)
                        break

            url = None
            for u, n in url_map.items():
                if line[:40] in n:
                    url = u if u.startswith("http") else f"https://www.wildberries.ru{u}"
                    break

            if price:
                products.append(Product(name=line, price=price, url=url, currency="RUB"))

        return products


class AmazonTemplate(MarketplaceTemplate):
    """Amazon product listing extraction."""

    domain = "amazon.com"
    name = "Amazon"

    async def extract(self, page) -> list[Product]:
        items = page.css('[data-component-type="s-search-result"]')
        if not items:
            return []

        products = []
        for item in items:
            name_el = item.css("h2 a span")
            name = name_el[0].text.strip() if name_el else ""
            price_el = item.css(".a-price .a-offscreen")
            price = self.parse_price(price_el[0].text) if price_el else None
            link_el = item.css("h2 a")
            url = ""
            if link_el:
                href = link_el[0].attrib.get("href", "")
                url = f"https://www.amazon.com{href}" if href.startswith("/") else href

            if name:
                products.append(Product(name=name, price=price, url=url, currency="USD"))

        return products


# Registry
TEMPLATES: dict[str, MarketplaceTemplate] = {
    "ozon": OzonTemplate(),
    "wildberries": WildberriesTemplate(),
    "wb": WildberriesTemplate(),
    "amazon": AmazonTemplate(),
}


def get_template(name: str) -> Optional[MarketplaceTemplate]:
    """Get a marketplace template by name or domain."""
    name = name.lower().strip()
    if name in TEMPLATES:
        return TEMPLATES[name]
    for tmpl in TEMPLATES.values():
        if tmpl.domain in name:
            return tmpl
    return None


def list_templates() -> list[str]:
    """List available template names."""
    return list(TEMPLATES.keys())
