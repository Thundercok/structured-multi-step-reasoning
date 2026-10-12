"""
Module Scraper cào dữ liệu từ các trang Web bán Đồng Hồ Rep chuyên biệt tại Việt Nam.
"""

import logging
from typing import List, Optional
from bs4 import BeautifulSoup
from models import WatchListing
from scrapers.base_scraper import BaseScraper
from slang_dictionary import classify_listing

logger = logging.getLogger(__name__)


class WebRepScraper(BaseScraper):
    def __init__(
        self,
        max_price: int = 15000000,
        min_price: int = 200000,
        proxy: Optional[str] = None
    ):
        super().__init__(name="WebRep", max_price=max_price, min_price=min_price, proxy=proxy)
        self.target_sites = [
            {
                "name": "DongHoReplica",
                "url": "https://donghoreplica.com/dong-ho-replica/",
                "product_selector": "li.product",
                "title_selector": ".woocommerce-loop-product__title, h2, h3",
                "price_selector": ".price .amount, .price ins .amount",
                "link_selector": "a.woocommerce-LoopProduct-link, a",
                "img_selector": "img"
            }
        ]

    def _clean_price(self, price_str: str) -> int:
        """Đổi chuỗi giá dạng '1.500.000₫' thành số nguyên 1500000."""
        if not price_str:
            return 0
        digits = "".join(filter(str.isdigit, price_str))
        return int(digits) if digits else 0

    def fetch_listings(self) -> List[WatchListing]:
        """Cào tin đăng từ các web bán đồng hồ rep."""
        results = []

        with self.get_client() as client:
            for site in self.target_sites:
                try:
                    response = client.get(site["url"])
                    if response.status_code != 200:
                        logger.warning(f"[{site['name']}] Lỗi status {response.status_code}")
                        continue

                    soup = BeautifulSoup(response.text, "lxml")
                    products = soup.select(site["product_selector"])

                    for idx, prod in enumerate(products):
                        title_el = prod.select_one(site["title_selector"])
                        title = title_el.get_text(strip=True) if title_el else ""
                        if not title:
                            continue

                        price_el = prod.select_one(site["price_selector"])
                        price_str = price_el.get_text(strip=True) if price_el else ""
                        price = self._clean_price(price_str)

                        if price > 0 and (price < self.min_price or price > self.max_price):
                            continue

                        link_el = prod.select_one(site["link_selector"])
                        url = link_el.get("href", "") if link_el else site["url"]

                        img_el = prod.select_one(site["img_selector"])
                        image_url = img_el.get("src", "") or img_el.get("data-src", "") if img_el else ""

                        analysis = classify_listing(title, f"Sản phẩm {site['name']}", price)

                        listing = WatchListing(
                            id=f"{site['name'].lower()}_{idx}_{hash(title)}",
                            title=title,
                            price=price,
                            source=site["name"],
                            brand=analysis["brand"],
                            description=f"Sản phẩm niêm yết tại {site['name']}",
                            url=url,
                            image_url=image_url,
                            location="Toàn Quốc",
                            seller_name=site["name"],
                            confidence_score=max(80, analysis["confidence_score"]),
                            matched_slangs=analysis["matched_slangs"] or ["Shop Rep"],
                            is_price_anomaly=analysis["is_price_anomaly"]
                        )
                        results.append(listing)

                except Exception as e:
                    logger.error(f"[{site['name']}] Lỗi cào web: {e}")

        logger.info(f"[{self.name}] Cào thành công {len(results)} sản phẩm đồng hồ rep.")
        return results
