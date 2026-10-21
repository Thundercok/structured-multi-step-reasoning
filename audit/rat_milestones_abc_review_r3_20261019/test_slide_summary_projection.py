"""Independent F2 follow-up: keep SQL predicate evidence through projection."""
from pathlib import Path
from tempfile import TemporaryDirectory

import pytest

from rat.crawler.db import Database
from rat.engine.finder_intent import is_slide_row
from rat.engine.progressive_search import ProgressiveSearch, SearchRequest


@pytest.mark.parametrize('padding', [0, 15], ids=['short-summary-control', 'indicator-after-200'])
def test_sql_slide_match_survives_summary_projection(padding):
    with TemporaryDirectory(prefix='rat-r3-', dir='/tmp') as folder:
        root = Path(folder).resolve()
        path = root / 'books' / 'DSA.pdf'
        path.parent.mkdir()
        path.write_text('DSA trees')
        summary = 'Reference material. ' * padding + ' slide'
        row = dict(file_path=str(path), file_name=path.name, file_ext='.pdf',
            file_size=path.stat().st_size, created_at=1, modified_at=1, indexed_at=1,
            content_text='DSA trees', summary=summary)
        assert is_slide_row(row)
        db = Database(str(root / 'fixture.db'))
        db.upsert_document(row)
        search = ProgressiveSearch(db.db_path)
        try:
            candidates = db.search_metadata('DSA', slide_rule=True)
            assert [r['file_path'] for r in candidates] == [str(path)]
            assert all('content_text' not in r and len(r['summary']) <= 200 for r in candidates)
            snap = search.initial(SearchRequest(1, 'slide DSA'))
            assert [h.path for h in snap.hits] == [str(path)]
        finally:
            search.close_connection()
            db.get_connection().close()
