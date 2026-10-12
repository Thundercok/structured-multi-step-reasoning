"""
Unit tests cho slang dictionary và listing classification.
"""

from slang_dictionary import classify_listing


def test_classify_listing_rolex_rep():
    title = "Cần bán đồng hồ Rô léx Submariner 1:1 Clean Factory"
    description = "Hàng rep 1:1 siêu cấp máy ETA Thụy Sĩ"
    price = 6500000

    result = classify_listing(title, description, price)
    assert result["brand"] == "Rolex"
    assert result["confidence_score"] >= 70
    assert "Clean Factory" in result["matched_slangs"] or "Rep 1:1" in result["matched_slangs"]


def test_classify_listing_genuine_high_price():
    title = "Đồng hồ Hublot Big Bang chính hãng Hàng Chính Hãng Fullbox"
    description = "Cam kết chính hãng 100% mua tại hãng"
    price = 250000000

    result = classify_listing(title, description, price)
    assert result["confidence_score"] < 40
