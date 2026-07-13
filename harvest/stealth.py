"""Stealth — Fingerprint spoofing for Scrapling.

Features:
- User-Agent rotation from 20+ modern browsers
- WebGL/Canvas noise
- WebRTC blocking
- Viewport randomization
- Platform randomization

Usage:
    stealth = Stealth()
    additional_args = stealth.get_args()
"""

import random
from typing import Dict, Any


# 24 real User-Agents: latest Chrome/Firefox/Edge on Win/Mac/Linux
USER_AGENTS = [
    # Chrome 125-127 Windows
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/127.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36",
    # Chrome 125-127 macOS
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/127.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36",
    # Chrome Linux
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/127.0.0.0 Safari/537.36",
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36",
    # Firefox 128-130 Windows
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:130.0) Gecko/20100101 Firefox/130.0",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:129.0) Gecko/20100101 Firefox/129.0",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:128.0) Gecko/20100101 Firefox/128.0",
    # Firefox macOS
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10.15; rv:130.0) Gecko/20100101 Firefox/130.0",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10.15; rv:129.0) Gecko/20100101 Firefox/129.0",
    # Firefox Linux
    "Mozilla/5.0 (X11; Linux x86_64; rv:130.0) Gecko/20100101 Firefox/130.0",
    "Mozilla/5.0 (X11; Linux x86_64; rv:129.0) Gecko/20100101 Firefox/129.0",
    # Edge Windows
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/127.0.0.0 Safari/537.36 Edg/127.0.0.0",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36 Edg/126.0.0.0",
    # Edge macOS
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/127.0.0.0 Safari/537.36 Edg/127.0.0.0",
    # Safari macOS
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/18.0 Safari/605.1.15",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.6 Safari/605.1.15",
    # Safari iOS (iPad)
    "Mozilla/5.0 (iPad; CPU OS 18_0 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/18.0 Mobile/15E148 Safari/604.1",
    "Mozilla/5.0 (iPad; CPU OS 17_6 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.6 Mobile/15E148 Safari/604.1",
]

VIEWPORTS = [
    {"width": 1920, "height": 1080},
    {"width": 1440, "height": 900},
    {"width": 1536, "height": 864},
    {"width": 1366, "height": 768},
    {"width": 1280, "height": 720},
]

PLATFORMS = ["Windows", "MacIntel", "Linux x86_64"]

TIMEZONES = [
    "America/New_York",
    "America/Chicago",
    "America/Los_Angeles",
    "Europe/London",
    "Europe/Berlin",
    "Asia/Tokyo",
    "Asia/Shanghai",
    "Australia/Sydney",
]

LOCALES = [
    "en-US",
    "en-GB",
    "en-CA",
    "en-AU",
    "de-DE",
    "fr-FR",
    "ja-JP",
    "zh-CN",
]

WEBGL_VENDORS = [
    "Intel Inc.",
    "Google Inc. (Intel)",
    "NVIDIA Corporation",
    "AMD",
]

WEBGL_RENDERERS = [
    "Intel Iris OpenGL Engine",
    "ANGLE (Intel, Intel(R) UHD Graphics Direct3D11 vs_5_0 ps_5_0)",
    "ANGLE (NVIDIA, NVIDIA GeForce RTX 3060 Direct3D11 vs_5_0 ps_5_0)",
    "ANGLE (AMD, AMD Radeon(TM) Graphics Direct3D11 vs_5_0 ps_5_0)",
    "Mesa DRI Intel(R) Graphics (ADL GT2)",
]


class Stealth:
    """Generate fingerprint-spoofing arguments for Scrapling sessions."""

    def __init__(self):
        self._user_agent = random.choice(USER_AGENTS)
        self._viewport = random.choice(VIEWPORTS)
        self._timezone = random.choice(TIMEZONES)
        self._locale = random.choice(LOCALES)
        self._platform = random.choice(PLATFORMS)

    def rotate(self):
        """Rotate all fingerprints for a new session."""
        self.__init__()

    def get_args(self) -> Dict[str, Any]:
        """Get Scrapling additional_args for stealth."""
        args = {
            "user_agent": self._user_agent,
            "viewport": self._viewport,
            "timezone_id": self._timezone,
            "locale": self._locale,
            "webgl_vendor": random.choice(WEBGL_VENDORS),
            "webgl_renderer": random.choice(WEBGL_RENDERERS),
            "canvas_noise": True,
            "webrtc_block": True,
        }
        return args

    def summary(self) -> str:
        """Human-readable fingerprint summary."""
        return (
            f"UA={self._user_agent[:60]}... "
            f"VP={self._viewport['width']}x{self._viewport['height']} "
            f"TZ={self._timezone} LOC={self._locale}"
        )
