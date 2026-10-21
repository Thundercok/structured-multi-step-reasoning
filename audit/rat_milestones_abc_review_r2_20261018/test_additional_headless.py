"""Round-two acceptance probes; synthetic fixtures only, no production changes."""
from datetime import datetime, timedelta, timezone
from pathlib import Path
import plistlib
from tempfile import TemporaryDirectory

import pytest

from rat.crawler.db import Database
from rat.engine.finder_intent import is_slide_row, parse_finder_intent
from rat.engine.progressive_search import ProgressiveSearch, SearchRequest

TZ = timezone(timedelta(hours=7))
NOW = datetime(2026, 10, 18, 12, tzinfo=TZ)


def index(db, path, *, content='DSA trees', summary='Reference material', created=1, modified=1):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content)
    db.upsert_document(dict(file_path=str(path), file_name=path.name, file_ext=path.suffix,
        file_size=path.stat().st_size, created_at=created, modified_at=modified,
        indexed_at=1, content_text=content, summary=summary))


def make_app(root, name='League of Legends'):
    path = root / (name + '.app')
    (path / 'Contents/MacOS').mkdir(parents=True)
    (path / 'Contents/Info.plist').write_bytes(plistlib.dumps(dict(
        CFBundleName=name, CFBundleIdentifier='com.fixture.league', CFBundleExecutable='fixture-bin')))
    (path / 'Contents/MacOS/fixture-bin').write_text('Never executed.')
    return path


def test_ancestor_slide_matches_cannot_consume_limit_before_valid_parent_match():
    # Neutral root avoids accidental indicators from pytest's test directory name.
    with TemporaryDirectory(prefix='rat-r2-', dir='/tmp') as folder:
        root = Path(folder).resolve()
        db = Database(str(root / 'fixture.db'))
        search = ProgressiveSearch(db.db_path)
        try:
            valid = root / 'slides/DSA_actual.pdf'
            index(db, valid, modified=1)
            for n in range(6):
                invalid = root / 'slides/archive/books' / f'DSA_reference_{n}.pdf'
                index(db, invalid, modified=100 + n)
                assert not is_slide_row(dict(file_path=str(invalid), file_name=invalid.name,
                    file_ext='.pdf', summary='Reference material'))
            assert is_slide_row(dict(file_path=str(valid), file_name=valid.name,
                file_ext='.pdf', summary='Reference material'))
            snapshot = search.initial(SearchRequest(1, 'slide DSA mới nhất', limit=1))
            assert [h.path for h in snapshot.hits] == [str(valid)]
        finally:
            search.close_connection()
            db.get_connection().close()


@pytest.mark.parametrize('query', [
    'Slide DSA đã tạo tuần trước',
    'slides DSA created last week',
])
def test_creation_date_phrase_is_consumed_without_changing_its_meaning(query, tmp_path):
    plan = parse_finder_intent(query, now=NOW)
    assert plan.needs_clarification or (plan.date_field == 'created' and plan.query_terms == 'DSA'), plan
    if plan.needs_clarification:
        return
    db = Database(str(tmp_path / 'fixture.db'))
    search = ProgressiveSearch(db.db_path, now_fn=lambda: NOW)
    try:
        path = tmp_path / 'DSA.pptx'
        index(db, path, created=datetime(2026, 10, 7, 12, tzinfo=TZ).timestamp(), modified=NOW.timestamp())
        assert [h.path for h in search.initial(SearchRequest(1, query)).hits] == [str(path)]
    finally:
        search.close_connection()
        db.get_connection().close()
