"""
Module Scraper cào dữ liệu từ Facebook Marketplace & Groups sử dụng Playwright.
"""

import logging
import asyncio
from typing import List, Optional
from models import WatchListing
from scrapers.base_scraper import BaseScraper
from slang_dictionary import classify_listing

logger = logging.getLogger(__name__)


class FacebookScraper(BaseScraper):
    def __init__(
        self,
        cookies_file: str = "facebook_cookies.json",
        max_price: int = 15000000,
        min_price: int = 200000,
        proxy: Optional[str] = None
    ):
        super().__init__(name="Facebook Marketplace", max_price=max_price, min_price=min_price, proxy=proxy)
        self.cookies_file = cookies_file

    def fetch_listings(self) -> List[WatchListing]:
        """Cào listing Facebook Marketplace bằng Playwright."""
        try:
            return asyncio.run(self._async_fetch())
        except Exception as e:
            logger.warning(f"[{self.name}] Không thể khởi chạy Playwright scraper: {e}")
            return []

    async def _async_fetch(self) -> List[WatchListing]:
        results = []
        try:
            from playwright.async_api import async_playwright
        except ImportError:
            logger.info(f"[{self.name}] Thư viện Playwright chưa được cài đặt. Bỏ qua cào Facebook.")
            return []

        async with async_playwright() as p:
            browser = await p.chromium.launch(headless=True)
            context = await browser.new_context(
                user_agent=self.headers["User-Agent"]
            )

            page = await context.new_page()
            url = "https://www.facebook.com/marketplace/category/watches"

            try:
                await page.goto(url, timeout=20000)
                await page.wait_for_timeout(3000)

                items = await page.query_selector_all('div[role="feed"] > div, div[style*="max-width"]')
                for idx, item in enumerate(items[:15]):
                    text = await item.inner_text()
                    if not text or ("VND" not in text and "đ" not in text):
                        continue

                    lines = [line.strip() for line in text.split("\n") if line.strip()]
                    if len(lines) < 2:
                        continue

                    title = lines[0]
                    price_text = lines[1]

                    digits = "".join(filter(str.isdigit, price_text))
                    price = int(digits) if digits else 0

                    if price > 0 and (price < self.min_price or price > self.max_price):
                        continue

                    analysis = classify_listing(title, text, price)
                    if analysis["confidence_score"] < 30:
                        continue

                    link_el = await item.query_selector('a[href*="/marketplace/item/"]')
                    item_url = "https://www.facebook.com" + await link_el.get_attribute("href") if link_el else url

                    listing = WatchListing(
                        id=f"fb_{idx}_{hash(title)}",
                        title=title,
                        price=price,
                        source=self.name,
                        brand=analysis["brand"],
                        description=text[:200],
                        url=item_url,
                        location="Việt Nam",
                        confidence_score=analysis["confidence_score"],
                        matched_slangs=analysis["matched_slangs"],
                        is_price_anomaly=analysis["is_price_anomaly"]
                    )
                    results.append(listing)

            except Exception as e:
                logger.error(f"[{self.name}] Lỗi trong quá trình cào trang: {e}")
            finally:
                await browser.close()

        logger.info(f"[{self.name}] Cào thành công {len(results)} tin đăng từ Facebook Marketplace.")
        return results
