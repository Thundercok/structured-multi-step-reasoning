"""
Module Scraper cào dữ liệu từ Chợ Tốt (chotot.com) qua Chợ Tốt API.
"""

import logging
from typing import List, Optional
from models import WatchListing
from scrapers.base_scraper import BaseScraper
from slang_dictionary import classify_listing

logger = logging.getLogger(__name__)


class ChoTotScraper(BaseScraper):
    def __init__(
        self,
        keywords: Optional[List[str]] = None,
        max_price: int = 15000000,
        min_price: int = 200000,
        proxy: Optional[str] = None
    ):
        super().__init__(name="Chợ Tốt", max_price=max_price, min_price=min_price, proxy=proxy)
        self.keywords = keywords or [
            "đồng hồ rep", "đồng hồ 1:1", "đồng hồ pass", "đồng hồ thanh lý",
            "rô léx", "rô leks", "húp lót", "pa tek", "omg", "clean factory", "vsf"
        ]
        self.base_url = "https://gateway.chotot.com/v1/public/ad-listing"

    def fetch_listings(self) -> List[WatchListing]:
        """Cào tất cả tin đăng đồng hồ từ Chợ Tốt theo các từ khóa cấu hình."""
        results = []
        seen_ids = set()

        with self.get_client() as client:
            for keyword in self.keywords:
                try:
                    params = {"q": keyword, "limit": 30}
                    response = client.get(self.base_url, params=params)
                    if response.status_code != 200:
                        logger.warning(f"[{self.name}] Lỗi status {response.status_code} khi tìm từ khóa: {keyword}")
                        continue

                    data = response.json()
                    ads = data.get("ads", [])

                    for ad in ads:
                        list_id = str(ad.get("list_id", ""))
                        if not list_id or list_id in seen_ids:
                            continue
                        seen_ids.add(list_id)

                        price = ad.get("price", 0)
                        if price < self.min_price or price > self.max_price:
                            continue

                        title = ad.get("subject", "")
                        body = ad.get("body", "")

                        analysis = classify_listing(title, body, price)
                        confidence_score = analysis["confidence_score"]

                        if confidence_score < 30:
                            continue

                        image_url = ad.get("image", "")
                        if not image_url and ad.get("images"):
                            image_url = ad["images"][0]

                        area_name = ad.get("area_name", "Việt Nam")
                        region_name = ad.get("region_name", "")
                        location = f"{area_name}, {region_name}".strip(", ")

                        canonical_url = f"https://www.chotot.com/{list_id}.htm"

                        listing = WatchListing(
                            id=f"chotot_{list_id}",
                            title=title,
                            price=price,
                            source=self.name,
                            brand=analysis["brand"],
                            description=body,
                            url=canonical_url,
                            image_url=image_url,
                            location=location,
                            seller_name=ad.get("account_name", "Người bán Chợ Tốt"),
                            seller_phone=ad.get("phone", ""),
                            confidence_score=confidence_score,
                            matched_slangs=analysis["matched_slangs"],
                            is_price_anomaly=analysis["is_price_anomaly"]
                        )
                        results.append(listing)

                except Exception as e:
                    logger.error(f"[{self.name}] Lỗi khi cào từ khóa '{keyword}': {e}")

        logger.info(f"[{self.name}] Cào thành công {len(results)} tin đăng rep/pass phù hợp.")
        return results
