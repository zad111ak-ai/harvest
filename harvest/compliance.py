"""Compliance checker for legal safety in web scraping.

Checks robots.txt, detects PII, assesses risk scores, and provides
recommendations for GDPR/CCPA compliance.

Usage:
    from harvest.compliance import ComplianceChecker

    checker = ComplianceChecker()
    report = await checker.check("https://example.com")
    print(report["risk_score"])  # 0.0 (safe) to 1.0 (high risk)
"""

import re
import logging
from dataclasses import dataclass, field
from typing import Any, Optional
from urllib.parse import urlparse

import aiohttp

logger = logging.getLogger(__name__)


@dataclass
class ComplianceReport:
    """Result of a compliance check."""

    url: str
    robots_txt: dict[str, Any] = field(default_factory=dict)
    pii_detected: list[dict[str, Any]] = field(default_factory=list)
    risk_score: float = 0.0
    recommendations: list[str] = field(default_factory=list)
    is_compliant: bool = True
    errors: list[str] = field(default_factory=list)


class ComplianceChecker:
    """Check compliance for web scraping operations."""

    # PII patterns (regex)
    PII_PATTERNS: dict[str, dict[str, Any]] = {
        "email": {
            "pattern": r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b",
            "severity": "high",
            "gdpr": True,
            "ccpa": True,
        },
        "phone_us": {
            "pattern": r"\b(?:\+?1[-. ]?)?\(?[0-9]{3}\)?[-. ]?[0-9]{3}[-. ]?[0-9]{4}\b",
            "severity": "medium",
            "gdpr": True,
            "ccpa": True,
        },
        "phone_intl": {
            "pattern": r"\+[0-9]{1,3}[-. ]?[0-9]{4,14}",
            "severity": "medium",
            "gdpr": True,
            "ccpa": True,
        },
        "ssn": {
            "pattern": r"\b[0-9]{3}[-. ]?[0-9]{2}[-. ]?[0-9]{4}\b",
            "severity": "critical",
            "gdpr": True,
            "ccpa": True,
        },
        "credit_card": {
            "pattern": r"\b(?:[0-9]{4}[-. ]?){3}[0-9]{4}\b",
            "severity": "critical",
            "gdpr": True,
            "ccpa": True,
        },
        "ip_address": {
            "pattern": r"\b(?:[0-9]{1,3}\.){3}[0-9]{1,3}\b",
            "severity": "low",
            "gdpr": False,
            "ccpa": False,
        },
        "passport": {
            "pattern": r"\b[A-Z]{1,2}[0-9]{6,9}\b",
            "severity": "high",
            "gdpr": True,
            "ccpa": False,
        },
    }

    # Sensitive data patterns (not PII but risky)
    SENSITIVE_PATTERNS: dict[str, dict[str, Any]] = {
        "date_of_birth": {
            "pattern": r"\b(?:0[1-9]|[12][0-9]|3[01])[/.](?:0[1-9]|1[012])[/.](?:19|20)\d{2}\b",
            "severity": "medium",
        },
        "medical_record": {
            "pattern": r"\b(?:MRN|Patient ID|Medical Record)[:\s]+[A-Z0-9-]+\b",
            "severity": "high",
        },
    }

    def __init__(
        self,
        user_agent: str = "HarvestBot/0.8.0 (+https://github.com/zad111ak-ai/harvest)",
        timeout: int = 10,
    ):
        self.user_agent = user_agent
        self.timeout = timeout
        self._robots_cache: dict[str, dict] = {}

    async def check(
        self,
        url: str,
        data: Optional[str] = None,
        check_robots: bool = True,
        check_pii: bool = True,
    ) -> dict[str, Any]:
        """Run compliance checks on a URL and optional data.

        Args:
            url: URL to check
            data: Optional text content to scan for PII
            check_robots: Whether to check robots.txt
            check_pii: Whether to scan for PII

        Returns:
            ComplianceReport as dict
        """
        report = ComplianceReport(url=url)

        # 1. Check robots.txt
        if check_robots:
            try:
                report.robots_txt = await self._check_robots(url)
                if not report.robots_txt.get("allowed", True):
                    report.recommendations.append("⚠️ robots.txt disallows scraping this URL")
                    report.risk_score += 0.3
            except Exception as e:
                report.errors.append(f"robots.txt check failed: {e}")

        # 2. Scan for PII
        if check_pii and data:
            try:
                report.pii_detected = self._detect_pii(data)
                if report.pii_detected:
                    pii_count = len(report.pii_detected)
                    report.recommendations.append(
                        f"⚠️ Detected {pii_count} potential PII elements. Remove before storage or get user consent."
                    )
                    # High severity = higher risk
                    high_severity = sum(1 for p in report.pii_detected if p.get("severity") in ("high", "critical"))
                    report.risk_score += min(0.5, high_severity * 0.15)
            except Exception as e:
                report.errors.append(f"PII detection failed: {e}")

        # 3. Calculate final risk score
        report.risk_score = min(1.0, report.risk_score)

        # 4. Determine compliance
        report.is_compliant = report.risk_score < 0.7

        # 5. Add recommendations
        if report.risk_score < 0.3:
            report.recommendations.insert(0, "✅ Low risk — safe to proceed")
        elif report.risk_score < 0.7:
            report.recommendations.insert(0, "⚠️ Medium risk — review before proceeding")
        else:
            report.recommendations.insert(0, "🚫 High risk — do not proceed without legal review")

        return {
            "url": report.url,
            "risk_score": report.risk_score,
            "is_compliant": report.is_compliant,
            "robots_txt": report.robots_txt,
            "pii_detected": report.pii_detected,
            "recommendations": report.recommendations,
            "errors": report.errors,
        }

    async def _check_robots(self, url: str) -> dict[str, Any]:
        """Check robots.txt for the URL."""
        parsed = urlparse(url)
        base_url = f"{parsed.scheme}://{parsed.netloc}"
        robots_url = f"{base_url}/robots.txt"

        # Check cache
        if robots_url in self._robots_cache:
            cached = self._robots_cache[robots_url]
            return self._evaluate_robots(cached, url)

        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(
                    robots_url,
                    headers={"User-Agent": self.user_agent},
                    timeout=aiohttp.ClientTimeout(total=self.timeout),
                ) as resp:
                    if resp.status == 200:
                        content = await resp.text()
                        parsed_robots = self._parse_robots(content)
                        self._robots_cache[robots_url] = parsed_robots
                        return self._evaluate_robots(parsed_robots, url)
                    else:
                        # No robots.txt = everything allowed
                        return {"allowed": True, "status": "no_robots_txt"}

        except Exception as e:
            logger.warning(f"Failed to fetch robots.txt: {e}")
            return {"allowed": True, "status": "fetch_error"}

    def _parse_robots(self, content: str) -> dict[str, Any]:
        """Parse robots.txt content."""
        rules: dict[str, Any] = {"user_agents": {}, "sitemaps": []}
        current_agent = None

        for line in content.splitlines():
            line = line.strip()
            if not line or line.startswith("#"):
                continue

            if line.lower().startswith("user-agent:"):
                current_agent = line.split(":", 1)[1].strip()
                if current_agent not in rules["user_agents"]:
                    rules["user_agents"][current_agent] = {
                        "allow": [],
                        "disallow": [],
                    }
            elif line.lower().startswith("allow:") and current_agent:
                path = line.split(":", 1)[1].strip()
                rules["user_agents"][current_agent]["allow"].append(path)
            elif line.lower().startswith("disallow:") and current_agent:
                path = line.split(":", 1)[1].strip()
                rules["user_agents"][current_agent]["disallow"].append(path)
            elif line.lower().startswith("sitemap:"):
                rules["sitemaps"].append(line.split(":", 1)[1].strip())

        return rules

    def _evaluate_robots(self, rules: dict, url: str) -> dict[str, Any]:
        """Evaluate if URL is allowed by robots.txt."""
        parsed = urlparse(url)
        path = parsed.path

        # Check for HarvestBot or wildcard
        for agent, agent_rules in rules.get("user_agents", {}).items():
            if agent in ("*", self.user_agent.split("/")[0]):
                # Check disallow rules
                for disallowed in agent_rules.get("disallow", []):
                    if disallowed and path.startswith(disallowed):
                        return {
                            "allowed": False,
                            "reason": f"Disallowed by robots.txt for {agent}",
                            "rule": disallowed,
                        }

        return {"allowed": True, "status": "allowed"}

    def _detect_pii(self, text: str) -> list[dict[str, Any]]:
        """Detect PII in text."""
        found = []

        for pii_type, pii_config in self.PII_PATTERNS.items():
            pattern = str(pii_config["pattern"])
            matches = re.finditer(pattern, text)

            for match in matches:
                found.append(
                    {
                        "type": pii_type,
                        "value": match.group()[:50],  # Truncate for safety
                        "position": match.span(),
                        "severity": pii_config["severity"],
                        "gdpr_applicable": pii_config.get("gdpr", False),
                        "ccpa_applicable": pii_config.get("ccpa", False),
                    }
                )

        # Also check sensitive patterns
        for sensitive_type, sensitive_config in self.SENSITIVE_PATTERNS.items():
            pattern = sensitive_config["pattern"]
            matches = re.finditer(pattern, text)

            for match in matches:
                found.append(
                    {
                        "type": sensitive_type,
                        "value": match.group()[:50],
                        "position": match.span(),
                        "severity": sensitive_config["severity"],
                        "gdpr_applicable": True,
                        "ccpa_applicable": True,
                    }
                )

        return found

    def check_data(self, data: str, context: Optional[str] = None) -> dict[str, Any]:
        """Check data for compliance without URL check.

        Useful for checking extracted data before storage.
        """
        pii = self._detect_pii(data)

        risk_score = 0.0
        recommendations = []

        if pii:
            high_count = sum(1 for p in pii if p["severity"] in ("high", "critical"))
            risk_score = min(1.0, high_count * 0.2)

            if risk_score >= 0.7:
                recommendations.append("🚫 High PII concentration. Do not store without consent.")
            elif risk_score >= 0.3:
                recommendations.append("⚠️ Some PII detected. Anonymize before storage.")
            else:
                recommendations.append("ℹ️ Minor PII detected. Review before storage.")
        else:
            recommendations.append("✅ No PII detected")

        return {
            "pii_count": len(pii),
            "pii_detected": pii,
            "risk_score": risk_score,
            "recommendations": recommendations,
        }

    def generate_report(self, result: dict[str, Any], format: str = "text") -> str:
        """Generate a human-readable compliance report."""
        if format == "text":
            return self._generate_text_report(result)
        elif format == "json":
            import json

            return json.dumps(result, indent=2)
        else:
            raise ValueError(f"Unknown format: {format}")

    def _generate_text_report(self, result: dict[str, Any]) -> str:
        """Generate text report."""
        lines = [
            "=" * 60,
            "🛡️  COMPLIANCE REPORT",
            "=" * 60,
            f"URL: {result['url']}",
            f"Risk Score: {result['risk_score']:.2f} / 1.00",
            f"Compliant: {'✅ Yes' if result['is_compliant'] else '❌ No'}",
            "",
            "--- robots.txt ---",
        ]

        robots = result.get("robots_txt", {})
        if robots.get("allowed"):
            lines.append("✅ Allowed by robots.txt")
        else:
            lines.append(f"❌ Blocked: {robots.get('reason', 'Unknown')}")

        lines.append("")
        lines.append("--- PII Detection ---")

        pii = result.get("pii_detected", [])
        if pii:
            lines.append(f"⚠️ Found {len(pii)} PII elements:")
            for p in pii[:10]:  # Limit to 10
                lines.append(f"  • {p['type']}: {p['value'][:30]}... (severity: {p['severity']})")
        else:
            lines.append("✅ No PII detected")

        lines.append("")
        lines.append("--- Recommendations ---")
        for rec in result.get("recommendations", []):
            lines.append(f"  {rec}")

        if result.get("errors"):
            lines.append("")
            lines.append("--- Errors ---")
            for err in result["errors"]:
                lines.append(f"  ⚠️ {err}")

        lines.append("=" * 60)
        return "\n".join(lines)
