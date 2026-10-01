import time
from unittest.mock import patch

from rat.crawler.db import Database
from rat.engine.context_parser import ContextParser
from rat.engine.multi_way_rrf import FacetResult, MultiWayRRF
from rat.engine.reranker import Reranker


def test_bm25_survives_name_merge_fusion_and_rerank(tmp_path):
    database = Database(str(tmp_path / "index.db"))
    database.upsert_document(dict(
        file_path="/alpha.pdf", file_name="alpha.pdf", file_ext=".pdf", file_size=10,
        created_at=time.time(), modified_at=time.time(), md5_hash="alpha",
        content_text="alpha beta", summary="", indexed_at=time.time(),
    ))
    candidates = database.search_candidates(["alpha"])
    assert candidates[0]["rank"] == -100
    assert candidates[0]["bm25"] > 0
    assert candidates[0]["bm25"] != 100
    dense = dict(candidates[0], similarity_score=0.8)
    fused = MultiWayRRF().fuse([FacetResult("lexical", candidates),
                              FacetResult("semantic", [dense], 1.2, True)])
    with patch("rat.crawler.dedup.dedup_engine.get_document_version_info", return_value=None):
        results = Reranker().rerank("alpha", ContextParser.parse_query("alpha"), fused)
    assert results[0].raw_scores["bm25"] == candidates[0]["bm25"]
    assert results[0].raw_scores["cosine"] == 0.8
    assert results[0].raw_scores["mrrf"] == 100
    assert abs(5.0 + sum(results[0].raw_scores["feats"].values()) - results[0].raw_scores["raw_score"]) < 1e-9
    assert results[0].to_dict()["raw_scores"] == results[0].raw_scores
    corrected = MultiWayRRF().fuse([FacetResult("existing", fused), FacetResult("temporal_widened", candidates)])
    assert corrected[0]["bm25"] == candidates[0]["bm25"]
    assert corrected[0]["vector_similarity"] == 0.8


def test_name_only_substring_does_not_fabricate_bm25(tmp_path):
    database = Database(str(tmp_path / "index.db"))
    database.upsert_document(dict(
        file_path="/alphabet.pdf", file_name="alphabet.pdf", file_ext=".pdf", file_size=10,
        created_at=time.time(), modified_at=time.time(), md5_hash="alphabet",
        content_text="", summary="", indexed_at=time.time(),
    ))
    candidates = database.search_candidates(["phabet"])
    assert candidates
    assert candidates[0]["bm25"] is None


def test_raw_score_survives_clamp_and_feature_sum_is_exact():
    context = ContextParser.parse_query("alpha pdf")
    document = {
        "file_name": "alpha.pdf", "file_ext": ".pdf", "content_text": "",
        "modified_at": 1.0, "vector_similarity": 0.8,
    }
    score, _ = Reranker().compute_heuristic_score(document, context)
    assert score == 100.0
    assert document["_raw_score"] > score
    assert abs(5.0 + sum(document["_feats"].values()) - document["_raw_score"]) < 1e-9
    assert document["_feats"]["kw_stem"] == 80.0
    assert document["_feats"]["ext_hit"] == 35.0
    assert document["_feats"]["vec_sim"] == 28.0
