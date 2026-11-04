"""Chuột's document search finds files by meaning and can read what it found."""
import numpy as np
import pytest

from rat.crawler.db import Database
from rat.engine.semantic_index import SemanticIndex
from rat.kernel.capabilities.documents import create_documents_capability

ROOM = "Hợp đồng thuê phòng trọ. Tiền cọc là 3.000.000 đồng, trả lại khi hết hạn hợp đồng."
RECIPE = "Công thức nấu phở bò: xương bò, quế, hồi, gừng nướng và nước mắm."


class KeywordEmbedder:
    """Places text by shared topic words, so tests can tell which file should win."""
    TOPICS = (("coc", "phong", "tro", "thue", "cọc", "phòng", "trọ"), ("pho", "phở", "nau", "nấu"))

    def _vector(self, text):
        text = text.lower()
        vector = np.zeros(384, dtype=np.float32)
        for index, words in enumerate(self.TOPICS):
            vector[index] = sum(word in text for word in words)
        norm = np.linalg.norm(vector)
        return vector / norm if norm else vector

    def embed_texts(self, texts, batch_size=8):
        return np.vstack([self._vector(text) for text in texts])

    def embed_query(self, query):
        return self._vector(query)

    def evict(self):
        pass


@pytest.fixture
def world(tmp_path):
    root = tmp_path / "docs"
    root.mkdir()
    (root / "giay_to_nha.txt").write_text(ROOM, encoding="utf-8")
    (root / "nau_an.txt").write_text(RECIPE, encoding="utf-8")
    index = SemanticIndex(tmp_path / "semantic.sqlite", embedder=KeywordEmbedder())
    assert index.start([root])
    index._thread.join(timeout=10)
    database = Database(str(tmp_path / "docs.sqlite"))
    capability = create_documents_capability(database, semantic=index)
    operations = {op.name: op for op in capability.operations.values()}
    return root, index, operations


def search(operations, query, **extra):
    return operations["search_documents"].handler({"query": query, **extra})


def test_question_finds_a_file_that_shares_no_filename_words(world):
    root, _, operations = world
    results = search(operations, "tiền cọc phòng trọ là bao nhiêu?")
    assert results[0]["filename"] == "giay_to_nha.txt"
    assert results[0]["path"] == str(root / "giay_to_nha.txt")
    assert "Tiền cọc" in results[0]["snippet"]
    assert results[0]["read"] is False


def test_a_file_found_by_meaning_can_be_read(world):
    root, _, operations = world
    result = operations["read_document"].handler({"file_path": str(root / "giay_to_nha.txt")})
    assert result["found"] is True
    assert "3.000.000" in result["content"]


def test_a_file_outside_every_index_still_cannot_be_read(world, tmp_path):
    _, _, operations = world
    secret = tmp_path / "secret.txt"
    secret.write_text("mật khẩu", encoding="utf-8")
    result = operations["read_document"].handler({"file_path": str(secret)})
    assert result["found"] is False


def test_a_file_changed_after_indexing_is_not_trusted(world):
    root, index, operations = world
    path = root / "giay_to_nha.txt"
    assert index.contains(path)
    path.write_text(ROOM + " Đã sửa thêm.", encoding="utf-8")
    assert not index.contains(path)
    assert operations["read_document"].handler({"file_path": str(path)})["found"] is False


def test_a_deleted_file_is_not_returned_or_trusted(world):
    root, index, operations = world
    path = root / "giay_to_nha.txt"
    path.unlink()
    assert not index.contains(path)
    assert all(row["filename"] != "giay_to_nha.txt" for row in search(operations, "tiền cọc phòng trọ"))


def test_search_survives_a_broken_meaning_index(tmp_path):
    class Broken:
        def search(self, *args, **kwargs):
            raise OSError("model missing")

        def contains(self, path):
            return False

    capability = create_documents_capability(Database(str(tmp_path / "docs.sqlite")), semantic=Broken())
    operations = {op.name: op for op in capability.operations.values()}
    assert search(operations, "tiền cọc") == []


def test_cancellation_still_cancels(tmp_path):
    class Cancelled:
        def search(self, *args, **kwargs):
            raise ValueError("cancelled:semantic")

    capability = create_documents_capability(Database(str(tmp_path / "docs.sqlite")), semantic=Cancelled())
    operations = {op.name: op for op in capability.operations.values()}
    with pytest.raises(ValueError, match="cancelled"):
        search(operations, "tiền cọc")


def test_limit_counts_meaning_and_keyword_results_together(world):
    _, _, operations = world
    assert len(search(operations, "tiền cọc phòng trọ", limit=1)) == 1
