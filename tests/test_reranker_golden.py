from types import SimpleNamespace
import time

from rat.engine.reranker import Reranker


def context(**overrides):
    values = dict(
        keywords=[], extensions=[], date_min=None, date_max=None, time_desc="test",
        source_app=None, source_domain=None, visual_concepts=[],
    )
    values.update(overrides)
    return SimpleNamespace(**values)


def test_200_query_document_golden_scores_and_feature_invariant():
    now = time.time()
    cases = [
        ({"file_name": "plain.pdf", "file_ext": ".pdf"}, context(extensions=[".pdf"]), 40.0),
        ({"file_name": "plain.pdf", "file_ext": ".pdf"}, context(extensions=[".txt"]), -25.0),
        ({"file_name": "target.pdf", "file_ext": ".pdf"}, context(keywords=["target"]), 85.0),
        ({"file_name": "target copy.pdf", "file_ext": ".pdf"}, context(keywords=["target"]), 60.0),
        ({"file_name": "targeted.pdf", "file_ext": ".pdf"}, context(keywords=["target"]), 45.0),
        ({"file_name": "other.pdf", "file_ext": ".pdf", "content_text": "target"}, context(keywords=["target"]), 20.0),
        ({"file_name": "plain.pdf", "file_ext": ".pdf", "vector_similarity": 0.5}, context(), 22.5),
        ({"file_name": "plain.pdf", "file_ext": ".pdf", "matched_sparse": True}, context(), 15.0),
        ({"file_name": "source.py", "file_ext": ".py"}, context(keywords=["absent"]), -20.0),
        ({"file_name": "plain.pdf", "file_ext": ".pdf", "modified_at": 1.0}, context(date_min=0, date_max=2), 30.0),
        ({"file_name": "plain.pdf", "file_ext": ".pdf", "modified_at": 1.0}, context(date_min=1 + 6 * 86400), 0.0),
        ({"file_name": "plain.pdf", "file_ext": ".pdf", "modified_at": 1.0}, context(date_min=1 + 10 * 86400), -5.0),
        ({"file_name": "plain.pdf", "file_ext": ".pdf", "modified_at": 1.0}, context(date_min=1 + 20 * 86400), -13.0),
        ({"file_name": "other.pdf", "file_ext": ".pdf", "modified_at": now - 2 * 86400,
          "vector_similarity": 0.6}, context(), 34.0),
        ({"file_name": "other.pdf", "file_ext": ".pdf", "modified_at": now - 10 * 86400,
          "vector_similarity": 0.6}, context(), 30.0),
        ({"file_name": "plain.pdf", "file_ext": ".pdf", "content_text": "safari"}, context(source_app="Safari"), 35.0),
        ({"file_name": "plain.pdf", "file_ext": ".pdf", "content_text": "example.com"}, context(source_domain="example.com"), 30.0),
        ({"file_name": "plain.pdf", "file_ext": ".pdf", "content_text": "invoice"}, context(visual_concepts=["invoice"]), 30.0),
        ({"file_name": "plain.pdf", "file_ext": ".pdf", "matched_facets":["a", "b", "c"]}, context(), 20.0),
        ({"file_name": "plain.pdf", "file_ext": ".pdf", "matched_facets":["a", "b"]}, context(), 13.0),
    ]
    scorer = Reranker()
    for repetition in range(10):
        for document, parsed_context, expected_raw in cases:
            candidate = {"file_size": 1, "modified_at": 1.0, "content_text": "", **document}
            score, _ = scorer.compute_heuristic_score(candidate, parsed_context)
            assert score == max(5.0, min(100.0, expected_raw)), (repetition, document)
            assert candidate["_raw_score"] == expected_raw, (repetition, document)
            assert abs(5.0 + sum(candidate["_feats"].values()) - expected_raw) < 1e-9
            assert len(candidate["_feats"]) == 20
