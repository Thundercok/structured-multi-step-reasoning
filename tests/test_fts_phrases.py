import pytest

from rat.crawler.db import Database, build_fts_query


@pytest.fixture
def database(tmp_path):
    instance = Database(str(tmp_path / "phrases.db"))
    for name, content in (
        ("first", "bài giảng giải tích cơ bản"),
        ("second", "giải bài toán và tích hợp công cụ"),
        ("third", "giaitich"),
        ("fourth", "alphabet soup"),
        ("fifth", "x OR python"),
        ("sixth", "python only"),
        ("seventh", "MA1521Chap1.pdf"),
    ):
        instance.upsert_document(dict(
            file_path=f"/documents/{name}.txt", file_name=f"{name}.txt", file_ext=".txt",
            file_size=100, created_at=1, modified_at=1, indexed_at=1, content_text=content,
        ))
    yield instance
    instance.get_connection().close()


@pytest.mark.parametrize("keyword", ["giai tich", "giải tích", "GIẢI\t TÍCH"])
def test_compound_is_fts_phrase_not_concatenation_or_individual_terms(database, keyword):
    candidates = database.search_candidates([keyword])
    assert [candidate["file_name"] for candidate in candidates] == ["first.txt"]
    assert candidates[0]["bm25"] > 0


def test_single_word_prefix_still_matches(database):
    assert [entry["file_name"] for entry in database.search_candidates(["alpha"])] == ["fourth.txt"]


def test_operators_and_quotes_are_literal_phrase_content(database):
    assert [entry["file_name"] for entry in database.search_candidates(['x" OR python'])] == ["fifth.txt"]


def test_filename_punctuation_matches_fts_tokens(database):
    assert [entry["file_name"] for entry in database.search_candidates(["MA1521Chap1.pdf"])] == ["seventh.txt"]


def test_empty_fts_terms_do_not_issue_invalid_match(database, caplog):
    assert build_fts_query(["", "*", '"']) == ""
    assert database.search_candidates(["*", '"']) == []
    assert "FTS5 query failed" not in caplog.text


def test_multiple_keywords_are_ored_and_deduplicated():
    assert build_fts_query(["giai tich", "slides", "slides"]) == '"giai tich"* OR "slides"*'
