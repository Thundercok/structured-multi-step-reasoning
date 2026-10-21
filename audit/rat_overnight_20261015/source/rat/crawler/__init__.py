"""
rat.crawler — File crawling, extraction, indexing, and watching.
"""

from rat.crawler.db import Database
from rat.crawler.extractors import extract_document_content
from rat.crawler.indexer import Indexer
from rat.crawler.watcher import FolderWatcher

__all__ = ["Database", "extract_document_content", "Indexer", "FolderWatcher"]
