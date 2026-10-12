"""
tests/test_query_cache.py — Unit tests for In-Memory LRU Query Cache.
"""

import tempfile
import unittest
from pathlib import Path

from rat.crawler.db import Database, QueryCache


class TestQueryCache(unittest.TestCase):

    def test_query_cache_lru_behavior(self) -> None:
        """Verify LRU cache stores, retrieves, and evicts oldest items."""
        cache = QueryCache(maxsize=2)
        key1 = ("kw1",)
        key2 = ("kw2",)
        key3 = ("kw3",)

        cache.set(key1, [{"id": 1, "name": "doc1"}])
        cache.set(key2, [{"id": 2, "name": "doc2"}])

        self.assertIsNotNone(cache.get(key1))
        # Adding key3 should evict key2 (since key1 was accessed last)
        cache.set(key3, [{"id": 3, "name": "doc3"}])

        self.assertIsNotNone(cache.get(key1))
        self.assertIsNone(cache.get(key2))
        self.assertIsNotNone(cache.get(key3))

    def test_database_search_candidates_cached(self) -> None:
        """Verify Database.search_candidates uses QueryCache."""
        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = str(Path(tmpdir) / "test.db")
            db = Database(db_path)
            db.init_db()

            doc = {
                "file_path": "/test/path/test_doc.txt",
                "file_name": "test_doc.txt",
                "file_ext": ".txt",
                "file_size": 1024,
                "created_at": 1700000000.0,
                "modified_at": 1700000000.0,
                "md5_hash": "dummyhash",
                "content_text": "sample document content for cache testing",
                "summary": "",
                "indexed_at": 1700000000.0,
            }
            db.upsert_document(doc)

            # First search: query database
            res1 = db.search_candidates(keywords=["sample"])
            self.assertEqual(len(res1), 1)

            # Verify item is in cache
            cache_key = (
                ("sample",),
                (),
                (),
                None,
                None,
                50,
            )
            cached_val = db.query_cache.get(cache_key)
            self.assertIsNotNone(cached_val)
            self.assertEqual(len(cached_val), 1)

            # Mutate document: cache must be cleared
            db.delete_document(doc["file_path"])
            self.assertIsNone(db.query_cache.get(cache_key))


if __name__ == "__main__":
    unittest.main()
