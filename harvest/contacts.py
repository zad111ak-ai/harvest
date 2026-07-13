"""
Contacts — Extract emails and contact information from websites.
"""

import re
from urllib.parse import urlparse

from .core import Scraper


class ContactCollector:
    """Find and extract contact information from websites.

    Discovers team pages, about pages, contact pages.
    Extracts emails, social links, phone numbers.
    """

    CONTACT_KEYWORDS = ["contact", "about", "team", "people", "company", "support"]

    def __init__(self):
        self.scraper = Scraper()

    async def collect(self, url: str, depth: int = 2) -> dict:
        """Collect contact info from a website.

        Args:
            url: Website URL to scan
            depth: How many internal pages to check (1=home only)

        Returns:
            dict with emails, social_links, pages_checked
        """
        result = {
            "url": url,
            "emails": [],
            "social_links": [],
            "pages_checked": [],
            "error": None,
        }

        # First, scrape home page to find contact pages
        try:
            home = await self.scraper.scrape(url)
            result["pages_checked"].append(url)

            # Find emails on home page
            emails = self._extract_emails(home["content"])
            if emails:
                result["emails"].extend(emails)

            # Find social links
            socials = self._extract_social_links(home["content"])
            if socials:
                result["social_links"].extend(socials)

            # Discover contact-related pages
            base = self._base_url(url)
            internal_pages = self._find_internal_pages(home["content"], base)

            # Visit contact pages
            contact_pages = [p for p in internal_pages if self._is_contact_page(p)]
            for page_url in contact_pages[:depth]:
                try:
                    page = await self.scraper.scrape(page_url)
                    result["pages_checked"].append(page_url)

                    emails = self._extract_emails(page["content"])
                    result["emails"].extend(e for e in emails if e not in result["emails"])

                    socials = self._extract_social_links(page["content"])
                    result["social_links"].extend(s for s in socials if s not in result["social_links"])
                except Exception:
                    pass

        except Exception as e:
            result["error"] = str(e)

        return result

    def _extract_emails(self, text: str) -> list[str]:
        """Extract email addresses from text."""
        pattern = r"[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}"
        found = re.findall(pattern, text)
        # Filter common false positives
        filtered = []
        for e in found:
            if not any(
                x in e.lower()
                for x in [
                    "noreply",
                    "no-reply",
                    "donotreply",
                    "example.com",
                    "domain.com",
                ]
            ):
                filtered.append(e.lower())
        return list(set(filtered))

    def _extract_social_links(self, text: str) -> list[dict]:
        """Extract social media links from text."""
        domains = {
            "twitter.com": "Twitter/X",
            "x.com": "Twitter/X",
            "linkedin.com": "LinkedIn",
            "github.com": "GitHub",
            "youtube.com": "YouTube",
            "facebook.com": "Facebook",
            "instagram.com": "Instagram",
            "t.me": "Telegram",
            "discord.gg": "Discord",
            "discord.com": "Discord",
            "reddit.com": "Reddit",
            "medium.com": "Medium",
            "tiktok.com": "TikTok",
        }
        pattern = r"https?://(?:www\.)?(" + "|".join(re.escape(d) for d in domains) + r")[^\s\"'<>)]+"
        found = re.findall(pattern, text, re.IGNORECASE)
        links = []
        for match in found:
            domain = re.search(
                r"(https?://(?:www\.)?" + re.escape(match.split("/")[0]) + r"[^\s\"'<>)]+)",
                text,
            )
            if domain:
                links.append(
                    {
                        "url": domain.group(1).rstrip(".)"),
                        "platform": domains.get(match, match),
                    }
                )
        return list({link["url"]: link for link in links}.values())

    def _base_url(self, url: str) -> str:
        parsed = urlparse(url)
        return f"{parsed.scheme}://{parsed.netloc}"

    def _find_internal_pages(self, html: str, base: str) -> list[str]:
        """Find internal links in HTML content."""
        pattern = r'href=["\'](https?://[^"\']+|/[^"\']+)["\']'
        found = re.findall(pattern, html)
        pages = []
        for link in found:
            if link.startswith("/"):
                link = base + link
            if link.startswith(base) and "#" not in link:
                pages.append(link)
        return list(set(pages))

    def _is_contact_page(self, url: str) -> bool:
        path = urlparse(url).path.lower()
        return any(kw in path for kw in self.CONTACT_KEYWORDS)
