"""CaptchaSolver — CAPTCHA detection and solving for Harvest.

Supports:
- Cloudflare Turnstile (behavioral click)
- hCaptcha (behavioral click)
- Ozon slider puzzle (screenshot + analysis)
- Generic slider CAPTCHAs

Usage:
    solver = CaptchaSolver()
    await solver.solve(page, "#cf-turnstile")
"""

import asyncio
import random
from loguru import logger

try:
    from playwright.async_api import Page
except ImportError:
    Page = None  # type: ignore[assignment,misc]


class CaptchaSolver:
    def __init__(self):
        self._yolo = None
        self._load_yolo()

    def _load_yolo(self):
        try:
            from ultralytics import YOLO

            self._yolo = YOLO("yolov8n.pt")
            logger.info("YOLOv8 loaded for CAPTCHA solving")
        except (ImportError, Exception) as e:
            logger.debug(f"YOLOv8 not available: {e}")

    async def solve(self, page: Page, selector: str) -> bool:
        """Detect and solve CAPTCHA on the page."""
        try:
            # Check for various CAPTCHA types
            solved = False

            # 1. Cloudflare Turnstile
            if await self._detect(page, "#cf-turnstile, .cf-turnstile"):
                solved = await self._solve_turnstile(page)

            # 2. hCaptcha
            elif await self._detect(page, "[data-hcaptcha-widget-id], .h-captcha"):
                solved = await self._solve_hcaptcha(page)

            # 3. Ozon slider / generic slider
            elif await self._detect(page, "[class*='slider'], [class*='captcha'], [class*='puzzle']"):
                solved = await self._solve_slider(page)

            # 4. Antibot page detection (Ozon style)
            elif await self._detect_antibot(page):
                solved = await self._solve_antibot(page)

            if solved:
                logger.info("CAPTCHA solved successfully")
            return solved

        except Exception as e:
            logger.warning(f"CAPTCHA solve failed: {e}")
            return False

    async def _detect(self, page: Page, selector: str) -> bool:
        try:
            el = await page.query_selector(selector)
            return el is not None
        except Exception:
            return False

    async def _detect_antibot(self, page: Page) -> bool:
        """Detect antibot challenge pages (like Ozon's 'enable JavaScript' page)."""
        try:
            content = await page.content()
            indicators = [
                "Antibot Captcha",
                "enable JavaScript",
                "We need to make sure that you are not a robot",
                "Slide the slider",
                "ab_cp_",
            ]
            return any(ind in content for ind in indicators)
        except Exception:
            return False

    async def _solve_turnstile(self, page: Page) -> bool:
        """Solve Cloudflare Turnstile via behavioral click."""
        try:
            el = await page.query_selector("#cf-turnstile, .cf-turnstile")
            if not el:
                return False
            box = await el.bounding_box()
            if not box:
                return False

            x = box["x"] + box["width"] / 2
            y = box["y"] + box["height"] / 2

            # Human-like approach
            await self._human_move(page, x, y)
            await asyncio.sleep(0.3 + random.random() * 0.5)
            await page.mouse.click(x, y)
            await asyncio.sleep(3)
            return True
        except Exception as e:
            logger.debug(f"Turnstile solve failed: {e}")
            return False

    async def _solve_hcaptcha(self, page: Page) -> bool:
        """Solve hCaptcha via behavioral click."""
        try:
            el = await page.query_selector("[data-hcaptcha-widget-id], .h-captcha iframe")
            if not el:
                return False
            box = await el.bounding_box()
            if not box:
                return False

            x = box["x"] + 30
            y = box["y"] + box["height"] / 2
            await self._human_move(page, x, y)
            await asyncio.sleep(0.2)
            await page.mouse.click(x, y)
            await asyncio.sleep(3)
            return True
        except Exception as e:
            logger.debug(f"hCaptcha solve failed: {e}")
            return False

    async def _solve_slider(self, page: Page) -> bool:
        """Solve slider CAPTCHA by dragging."""
        try:
            slider = await page.query_selector("[class*='slider'], [class*='drag'], [class*='puzzle'] button")
            if not slider:
                return False
            box = await slider.bounding_box()
            if not box:
                return False

            start_x = box["x"] + box["width"] / 2
            start_y = box["y"] + box["height"] / 2
            end_x = start_x + 200 + random.randint(-20, 20)

            await page.mouse.move(start_x, start_y)
            await asyncio.sleep(0.2)
            await page.mouse.down()
            await asyncio.sleep(0.1)

            # Gradual drag with easing
            steps = 20 + random.randint(0, 10)
            for i in range(steps):
                progress = i / steps
                ease = progress * (2 - progress)  # ease-out
                x = start_x + (end_x - start_x) * ease
                y = start_y + random.uniform(-2, 2)
                await page.mouse.move(x, y)
                await asyncio.sleep(0.01 + random.random() * 0.02)

            await page.mouse.up()
            await asyncio.sleep(2)
            return True
        except Exception as e:
            logger.debug(f"Slider solve failed: {e}")
            return False

    async def _solve_antibot(self, page: Page) -> bool:
        """Try to solve antibot challenge pages."""
        try:
            # Wait for page to fully load
            await asyncio.sleep(2)

            # Try to find and interact with slider
            content = await page.content()
            if "Slide the slider" in content:
                return await self._solve_slider(page)

            # Try clicking through if there's a confirm button
            btn = await page.query_selector("button, [type='submit']")
            if btn:
                await btn.click()
                await asyncio.sleep(3)
                return True

            return False
        except Exception as e:
            logger.debug(f"Antibot solve failed: {e}")
            return False

    async def _human_move(self, page: Page, x: float, y: float):
        """Simulate human-like mouse movement to target."""
        # Start from random position
        cur_x = x + random.randint(-100, 100)
        cur_y = y + random.randint(-100, 100)
        await page.mouse.move(cur_x, cur_y)
        await asyncio.sleep(0.1)

        # Move in steps toward target
        steps = 5 + random.randint(0, 5)
        for i in range(steps):
            progress = (i + 1) / steps
            mx = cur_x + (x - cur_x) * progress + random.uniform(-3, 3)
            my = cur_y + (y - cur_y) * progress + random.uniform(-3, 3)
            await page.mouse.move(mx, my)
            await asyncio.sleep(0.02 + random.random() * 0.05)
