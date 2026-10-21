"""
rat.crawler — File crawling, extraction, indexing, and watching.
"""

from importlib import import_module

_EXPORTS = {
    "Database": "db", "extract_document_content": "extractors",
    "Indexer": "indexer", "FolderWatcher": "watcher",
}


def __getattr__(name):
    """Loading the database must not also load extraction/indexing models."""
    module = _EXPORTS.get(name)
    if module is None:
        raise AttributeError(name)
    value = getattr(import_module(f"{__name__}.{module}"), name)
    globals()[name] = value
    return value

__all__ = ["Database", "extract_document_content", "Indexer", "FolderWatcher"]
