"""
Unit tests cho Scraper base và ChoTotScraper với HTTP Mocks.
"""

from scrapers.base_scraper import BaseScraper
from scrapers.chotot_scraper import ChoTotScraper


class DummyScraper(BaseScraper):
    def fetch_listings(self):
        return []


def test_base_scraper_init():
    scraper = DummyScraper(name="Dummy", max_price=10000000, min_price=100000)
    assert scraper.name == "Dummy"
    assert scraper.max_price == 10000000
    assert scraper.min_price == 100000
    client = scraper.get_client()
    assert client is not None
    client.close()


def test_chotot_scraper_mocked_fetch(monkeypatch):
    class MockResponse:
        status_code = 200

        def json(self):
            return {
                "ads": [
                    {
                        "list_id": 1001,
                        "subject": "Bán đồng hồ Rolex Rep 1:1 Clean Factory",
                        "body": "Đồng hồ replica siêu cấp máy Thụy Sĩ",
                        "price": 4500000,
                        "image": "https://example.com/img.jpg",
                        "area_name": "Quận 1",
                        "region_name": "TP HCM",
                        "account_name": "Shop Watch",
                        "phone": "0901234567"
                    }
                ]
            }

    class MockClient:
        def __init__(self, *args, **kwargs):
            pass

        def __enter__(self):
            return self

        def __exit__(self, *args):
            pass

        def get(self, url, params=None):
            return MockResponse()

    scraper = ChoTotScraper(keywords=["rolex rep"])
    monkeypatch.setattr(scraper, "get_client", lambda: MockClient())

    listings = scraper.fetch_listings()
    assert len(listings) == 1
    assert listings[0].id == "chotot_1001"
    assert listings[0].brand == "Rolex"
    assert listings[0].price == 4500000
