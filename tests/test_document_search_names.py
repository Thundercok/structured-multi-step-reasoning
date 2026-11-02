"""Indexed filename retrieval regressions; no model-quality claims."""
from pathlib import Path

import pytest

from rat.crawler.db import Database
from rat.kernel.capabilities.documents import create_documents_capability


@pytest.fixture
def index(tmp_path):
    db = Database(str(tmp_path / 'index.db'))
    def add(name, *, exists=True, content='An unrelated PDF document.'):
        path = tmp_path / name
        path.parent.mkdir(parents=True, exist_ok=True)
        if exists:
            path.write_text(content)
        db.upsert_document({'file_path': str(path), 'file_name': path.name,
                            'file_ext': path.suffix, 'file_size': 10,
                            'created_at': 1, 'modified_at': 1, 'indexed_at': 1,
                            'content_text': content})
        return path
    for i in range(20):
        add(f'Unrelated {i}.pdf')
    search = create_documents_capability(db).operations['search_documents'].handler
    yield db, add, lambda query: search({'query': query, 'limit': 5})
    db.get_connection().close()


def test_literal_filename_ignores_brackets_but_keeps_assignment_number(index):
    _, add, search = index
    add('[CALCULUS] Assignment 5.pdf')
    target = add('[CALCULUS] Assignment 6.pdf')
    add('old/[CALCULUS] Assignment 6.pdf', exists=False)
    rows = search('CALCULUS Assignment 6.pdf')
    assert [row['path'] for row in rows] == [str(target)]


def test_filename_matching_preserves_accents_case_and_live_path(index):
    _, add, search = index
    target = add('Giáo_trình_Giải_Tích.PDF')
    assert [r['path'] for r in search('giao trinh giai tich.pdf')] == [str(target)]


def test_content_search_still_works_and_never_presents_disappeared_files(index):
    _, add, search = index
    add('missing.txt', exists=False, content='TCP retransmission')
    target = add('Networks.txt', content='TCP retransmission')
    rows = search('TCP retransmission')
    assert rows and str(target) in [r['path'] for r in rows]
    assert all(Path(r['path']).is_file() for r in rows)


def test_absent_literal_filename_does_not_turn_into_unrelated_pdf_results(index):
    _, add, search = index
    add('[CALCULUS] Assignment 9.pdf', exists=False)
    assert search('CALCULUS Assignment 9.pdf') == []
