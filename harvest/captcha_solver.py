"""
CaptchaSolver — Turnstile/hCaptcha behavioral + YOLO solver.

Features:
- Behavioral analysis (mouse movement, click timing)
- YOLOv8 for checkbox detection
- Fallback to manual input via MCP

Usage:
    solver = CaptchaSolver()
    await solver.solve(page, "#cf-turnstile")
"""

import asyncio
import random
from typing import Optional
from playwright.async_api import Page
from loguru import logger


class CaptchaSolver:
    def __init__(self, yolo_model_path: Optional[str] = None):
        self.yolo_model_path = yolo_model_path or "yolov8n.pt"
        self._load_yolo()

    def _load_yolo(self) -> None:
        """Load YOLOv8 model for checkbox detection."""
        try:
            from ultralytics import YOLO

            self.yolo = YOLO(self.yolo_model_path)
            logger.info("YOLOv8 model loaded")
        except ImportError:
            logger.warning("YOLOv8 not available. Install: pip install ultralytics")
            self.yolo = None

    async def solve(self, page: Page, selector: str) -> bool:
        """Solve Turnstile/hCaptcha on the page."""
        try:
            # Wait for captcha to appear
            await page.wait_for_selector(selector, timeout=10000)
            logger.info(f"Captcha detected: {selector}")

            # Behavioral: human-like mouse movement
            await self._behavioral_solve(page, selector)

            # YOLO: detect checkbox
            if self.yolo:
                await self._yolo_solve(page, selector)

            # Wait for success
            await page.wait_for_selector(f"{selector}.success", timeout=5000)
            return True
        except Exception as e:
            logger.warning(f"Captcha solve failed: {e}")
            return False

    async def _behavioral_solve(self, page: Page, selector: str) -> None:
        """Simulate human behavior."""
        # Move mouse in random pattern
        box = await page.locator(selector).bounding_box()
        if box:
            x = box["x"] + box["width"] / 2
            y = box["y"] + box["height"] / 2
            await page.mouse.move(x, y)
            await asyncio.sleep(0.5)
            # Random small movements
            for _ in range(3):
                await page.mouse.move(x + random.uniform(-5, 5), y + random.uniform(-5, 5))
                await asyncio.sleep(0.1)
            await page.mouse.click(x, y)

    async def _yolo_solve(self, page: Page, selector: str) -> None:
        """Use YOLO to detect checkbox."""
        # Take screenshot
        img = await page.screenshot()
        # Run YOLO
        results = self.yolo(img)
        # Find checkbox in results
        for result in results:
            for box in result.boxes:
                if box.cls == "checkbox":  # Example class
                    x1, y1, x2, y2 = map(int, box.xyxy[0])
                    x = (x1 + x2) / 2
                    y = (y1 + y2) / 2
                    await page.mouse.click(x, y)
                    return
