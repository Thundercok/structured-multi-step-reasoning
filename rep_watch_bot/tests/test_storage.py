"""
Unit tests cho StorageManager và SQLite / Exporter.
"""

import os
from models import WatchListing
from storage import StorageManager


def test_storage_manager_crud_and_export(tmp_path):
    db_file = str(tmp_path / "test_watches.db")
    storage = StorageManager(db_path=db_file)

    listing = WatchListing(
        id="unit_1",
        title="Đồng hồ Rolex Datejust Rep 1:1",
        price=3500000,
        url="https://example.com/rolex",
        source="TestUnit",
        brand="Rolex",
        matched_slangs=["Rep 1:1"],
        confidence_score=85
    )

    # Test saving new listing
    assert storage.is_new(listing.id) is True
    saved = storage.save_listing(listing)
    assert saved is True

    # Test duplicate prevention
    assert storage.is_new(listing.id) is False
    saved_again = storage.save_listing(listing)
    assert saved_again is False

    # Test retrieval
    all_items = storage.get_all_listings()
    assert len(all_items) == 1
    assert all_items[0].id == "unit_1"
    assert all_items[0].brand == "Rolex"

    # Test CSV export
    output_dir = str(tmp_path / "output")
    csv_file = storage.export_data(output_dir=output_dir, format_type="csv")
    assert os.path.exists(csv_file)
    assert csv_file.endswith(".csv")

    # Test JSON export
    json_file = storage.export_data(output_dir=output_dir, format_type="json")
    assert os.path.exists(json_file)
    assert json_file.endswith(".json")
