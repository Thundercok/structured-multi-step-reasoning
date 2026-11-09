"""Tests for indexing source code files (.java, .cpp) and .zip archives."""
import zipfile
from pathlib import Path

from rat.config import SUPPORTED_EXTENSIONS
from rat.crawler.db import Database
from rat.crawler.extractors import extract_document_content, extract_text_from_zip
from rat.crawler.indexer import Indexer


def test_supported_extensions_includes_code_and_zip():
    assert ".java" in SUPPORTED_EXTENSIONS
    assert ".cpp" in SUPPORTED_EXTENSIONS
    assert ".c" in SUPPORTED_EXTENSIONS
    assert ".cs" in SUPPORTED_EXTENSIONS
    assert ".zip" in SUPPORTED_EXTENSIONS


def test_extract_java_file(tmp_path: Path):
    java_file = tmp_path / "Graph.java"
    java_file.write_text("public class Graph { private int V; }", encoding="utf-8")
    content = extract_document_content(str(java_file))
    assert "public class Graph" in content


def test_extract_zip_archive(tmp_path: Path):
    zip_path = tmp_path / "Lab9_Test.zip"
    with zipfile.ZipFile(zip_path, "w") as z:
        z.writestr("523C0012/Graph.java", "public class Graph { void bfs() {} }")
        z.writestr("523C0012/AdjacencyMatrix.java", "public class AdjacencyMatrix {}")
        z.writestr("523C0012/matrix.txt", "0 1 1\n1 0 0\n1 0 0")

    content = extract_text_from_zip(str(zip_path))
    assert "Archive: Lab9_Test.zip" in content
    assert "523C0012/Graph.java" in content
    assert "523C0012/AdjacencyMatrix.java" in content
    assert "public class Graph" in content


def test_index_zip_archive_searchable_by_inner_files(tmp_path: Path, monkeypatch):
    db_path = str(tmp_path / "test_rat.db")
    db = Database(db_path)
    indexer = Indexer(db)

    # Mock embedder to keep unit test fast and offline
    import numpy as np
    import rat.crawler.indexer as indexer_module
    monkeypatch.setattr(indexer_module.embedder, "embed_texts", lambda texts: np.zeros((len(texts), 384), dtype=np.float32))

    zip_path = tmp_path / "Student_Lab9.zip"
    with zipfile.ZipFile(zip_path, "w") as z:
        z.writestr("MyGraph.java", "public class MyGraph { int vertices; }")

    indexed = indexer.index_single_file(str(zip_path), force=True)
    assert indexed is True

    # Search candidates using inner file keyword
    candidates = db.search_candidates(keywords=["mygraph"], limit=5)
    assert len(candidates) > 0
    assert candidates[0]["file_name"] == "Student_Lab9.zip"


def test_inspect_archive_listing_and_read(tmp_path: Path):
    from rat.engine.runtime_tools import inspect_archive

    zip_path = tmp_path / "Submissions.zip"
    with zipfile.ZipFile(zip_path, "w") as z:
        z.writestr("lab9/Main.java", "public class Main { public static void main(String[] args) {} }")
        z.writestr("lab9/matrix.txt", "1 0 1")

    # Listing
    listing = inspect_archive(str(zip_path))
    assert listing.get("total_entries") == 2
    entries = [e["filename"] for e in listing.get("entries", [])]
    assert "lab9/Main.java" in entries
    assert "lab9/matrix.txt" in entries

    # Read specific entry
    entry_data = inspect_archive(str(zip_path), target_entry="lab9/Main.java")
    assert entry_data.get("entry_name") == "lab9/Main.java"
    assert "public class Main" in entry_data.get("content", "")

    # Non-existent entry
    err_data = inspect_archive(str(zip_path), target_entry="missing.txt")
    assert err_data.get("error") == "entry_not_found"


def test_documents_capability_operations():
    from rat.kernel.capabilities.documents import create_documents_capability
    cap = create_documents_capability()
    assert "inspect_archive" in cap.operations
    assert "search_filesystem_live" in cap.operations


def test_search_filesystem_live():
    from rat.engine.runtime_tools import search_filesystem_live
    results = search_filesystem_live("Lab9.pdf", max_results=5)
    assert isinstance(results, list)
    if results:
        assert any("Lab9.pdf" in r["filename"] for r in results)

