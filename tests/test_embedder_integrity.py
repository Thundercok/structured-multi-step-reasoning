from types import SimpleNamespace
from unittest.mock import Mock
import sys

import numpy as np
import pytest

from rat.engine.embedder import LocalEmbedder


def test_model_load_failure_raises_without_random_fallback(monkeypatch):
    constructor = Mock(side_effect=OSError("offline model unavailable"))
    monkeypatch.setitem(sys.modules, "fastembed", SimpleNamespace(TextEmbedding=constructor))
    encoder = LocalEmbedder()
    with pytest.raises(RuntimeError, match="embedding|FastEmbed"):
        encoder.embed_query("important query")
    assert not encoder._query_cache
    assert encoder._model is None


def test_missing_model_raises_instead_of_random_vectors(monkeypatch):
    encoder = LocalEmbedder()
    monkeypatch.setattr(encoder, "_load_model", lambda: None)
    with pytest.raises(RuntimeError, match="embedding|model"):
        encoder.embed_texts(["document"])


def test_generation_failure_is_not_zero_fallback_or_cached():
    encoder = LocalEmbedder()
    encoder._model = SimpleNamespace(embed=Mock(side_effect=OSError("broken inference")))
    with pytest.raises(RuntimeError, match="embedding"):
        encoder.embed_query("query")
    assert not encoder._query_cache


@pytest.mark.parametrize("vectors", [
    [[0, 0, 0]], [[float("nan"), 1, 2]], [[float("inf"), 1, 2]],
    [[1, 2, 3], [4, 5, 6]], [[1, 2]], [],
])
def test_invalid_output_is_rejected(vectors):
    encoder = LocalEmbedder()
    encoder._dimension = 3
    encoder._model = SimpleNamespace(embed=Mock(return_value=iter(vectors)))
    with pytest.raises(RuntimeError, match="embedding"):
        encoder.embed_query("query")
    assert not encoder._query_cache


def test_valid_vectors_normalize_and_cache_copies():
    encoder = LocalEmbedder()
    encoder._dimension = 3
    generate = Mock(side_effect=lambda *args, **kwargs: iter([[3, 4, 0]]))
    encoder._model = SimpleNamespace(embed=generate)
    first = encoder.embed_query(" query ")
    np.testing.assert_allclose(first, [0.6, 0.8, 0])
    first[:] = 0
    np.testing.assert_allclose(encoder.embed_query("query"), [0.6, 0.8, 0])
    assert generate.call_count == 1


def test_empty_requests_do_not_load_model(monkeypatch):
    encoder = LocalEmbedder()
    load = Mock(side_effect=AssertionError("must not load"))
    monkeypatch.setattr(encoder, "_load_model", load)
    assert encoder.embed_texts([]).shape == (0, 384)
    assert not encoder.embed_query(" ").any()
    load.assert_not_called()
