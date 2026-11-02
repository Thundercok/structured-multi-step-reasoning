"""Tests for ApplicationCatalog caching and mtime invalidation."""
import json
import os
from pathlib import Path
import time
import pytest

from rat.engine.app_resolver import Application, ApplicationCatalog, revalidate_application_bundle
from tests.test_progressive_search import app_bundle


def test_application_catalog_caching_and_invalidation(tmp_path):
    cache_file = tmp_path / "cache.json"
    app_dir = tmp_path / "apps"
    app_dir.mkdir()
    app1 = app_bundle(app_dir, "AppOne")

    # 1. Initial scan with explicit cache_path
    t0 = time.monotonic()
    cat1 = ApplicationCatalog.scan([app_dir], cache_path=cache_file)
    t1 = time.monotonic()
    assert len(cat1.applications) == 1
    assert cat1.applications[0].name == "AppOne"
    assert cache_file.is_file()

    # 2. Second scan hits cache
    t2 = time.monotonic()
    cat2 = ApplicationCatalog.scan([app_dir], cache_path=cache_file)
    t3 = time.monotonic()
    assert len(cat2.applications) == 1
    assert cat2.applications[0].name == "AppOne"
    assert (t3 - t2) < (t1 - t0) + 0.05

    # 3. Add second app -> changes app_dir mtime
    # Ensure mtime advances
    time.sleep(0.02)
    app2 = app_bundle(app_dir, "AppTwo")
    os.utime(app_dir, None)

    # 4. Third scan detects directory mtime change and rescans
    cat3 = ApplicationCatalog.scan([app_dir], cache_path=cache_file)
    assert len(cat3.applications) == 2
    names = {a.name for a in cat3.applications}
    assert names == {"AppOne", "AppTwo"}

    # 5. use_cache=False bypasses cache
    cat_no_cache = ApplicationCatalog.scan([app_dir], use_cache=False, cache_path=cache_file)
    assert len(cat_no_cache.applications) == 2
