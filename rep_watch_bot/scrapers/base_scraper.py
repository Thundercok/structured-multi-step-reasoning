"""
Abstract Base Class cho tất cả các Scraper module trong rep_watch_bot.
"""

import logging
from abc import ABC, abstractmethod
from typing import List, Optional
import httpx
from models import WatchListing

logger = logging.getLogger(__name__)


class BaseScraper(ABC):
    """Abstract Base Class định nghĩa giao diện chuẩn cho mọi scraper."""

    def __init__(
        self,
        name: str,
        max_price: int = 15000000,
        min_price: int = 200000,
        proxy: Optional[str] = None
    ):
        self.name = name
        self.max_price = max_price
        self.min_price = min_price
        self.proxy = proxy
        self.headers = {
            "User-Agent": (
                "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/120.0.0.0 Safari/537.36"
            ),
            "Accept": "application/json, text/html, */*",
            "Accept-Language": "vi-VN,vi;q=0.9,en-US;q=0.8,en;q=0.7",
        }

    def get_client(self, timeout: float = 15.0) -> httpx.Client:
        """Tạo httpx Client chuẩn hóa với header và proxy (nếu có)."""
        proxies = self.proxy if self.proxy else None
        return httpx.Client(
            headers=self.headers,
            proxy=proxies,
            timeout=timeout,
            follow_redirects=True
        )

    @abstractmethod
    def fetch_listings(self) -> List[WatchListing]:
        """Phương thức abstract bắt buộc các class con phải triển khai."""
        pass
