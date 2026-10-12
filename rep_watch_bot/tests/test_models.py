"""
Unit tests cho Pydantic v2 WatchListing model.
"""

from models import WatchListing


def test_watch_listing_formatted_price():
    listing = WatchListing(
        id="test_1",
        title="Đồng hồ Rolex Rep 1:1",
        price=2500000,
        url="https://example.com/item1",
        source="Test"
    )
    assert listing.formatted_price == "2,500,000 VNĐ"

    listing_negotiable = WatchListing(
        id="test_2",
        title="Đồng hồ thỏa thuận",
        price=0,
        url="https://example.com/item2",
        source="Test"
    )
    assert listing_negotiable.formatted_price == "Thỏa thuận / Liên hệ"


def test_watch_listing_to_dict():
    listing = WatchListing(
        id="test_3",
        title="Hublot Clean Factory",
        price=5000000,
        url="https://example.com/item3",
        source="TestSource",
        brand="Hublot",
        matched_slangs=["Clean Factory", "Rep 1:1"],
        confidence_score=90,
        is_price_anomaly=True
    )

    data = listing.to_dict()
    assert data["id"] == "test_3"
    assert data["brand"] == "Hublot"
    assert data["formatted_price"] == "5,000,000 VNĐ"
    assert data["confidence_score"] == "90%"
    assert data["matched_slangs"] == "Clean Factory, Rep 1:1"
    assert data["is_price_anomaly"] == "Có"
