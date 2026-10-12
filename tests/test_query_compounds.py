import unicodedata

import pytest

from rat.engine.context_parser import ContextParser
from rat.engine.reranker import Reranker


@pytest.mark.parametrize("query", ["slides giải tích", "slides giai tich", "slides GIẢI TÍCH", "slides giải\t  tích", unicodedata.normalize("NFD", "slides giải tích")])
def test_compound_does_not_leak_component_keywords(query):
    assert ContextParser.parse_query(query).keywords == ["giai tich", "slides"]


def test_compound_matching_uses_whole_words_and_preserves_other_occurrences():
    assert "giai tich" not in ContextParser.parse_query("nongiai tich").keywords
    assert ContextParser.parse_query("slides giải tích giải").keywords == ["giai tich", "slides", "giải"]


def test_longest_compound_wins_without_duplicate_subphrases():
    assert ContextParser.parse_query("bài tập lớn calculus").keywords == ["bai tap lon", "calculus"]


def test_exact_filename_is_preserved():
    assert ContextParser.parse_query("MA1521Chap1.pdf").keywords == ["MA1521Chap1.pdf"]


def test_unrelated_compound_components_do_not_gain_topic_points():
    context = ContextParser.parse_query("slides giải tích")
    document = dict(file_name="Trinh Bay Slides VRPTW.pptx", file_ext=".pptx", modified_at=1,
                    content_text="giải bài toán; tích hợp bộ tối ưu", matched_facets=["lexical"])
    score, _ = Reranker().compute_heuristic_score(document, context)
    assert score == 60
    assert document["_feats"]["kw_content"] == 0


def test_semantic_only_candidate_can_still_have_filename_points():
    context = ContextParser.parse_query("slides giải tích")
    document = dict(file_name="slides_ch2.pdf", file_ext=".pdf", modified_at=1,
                    content_text="English calculus lecture", matched_facets=["semantic"])
    Reranker().compute_heuristic_score(document, context)
    assert document["_feats"]["kw_word"] == 55
