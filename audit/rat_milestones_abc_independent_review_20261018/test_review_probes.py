"""Independent acceptance probes; synthetic files/apps, no live model or launch.

Assertions express the requested behavior. Failures are review evidence, not
changes to the production regression suite.
"""
from datetime import datetime, timedelta, timezone
from pathlib import Path
import plistlib
from tempfile import TemporaryDirectory

import pytest

from rat.crawler.db import Database
from rat.engine.app_resolver import ApplicationCatalog
from rat.engine.finder_intent import is_slide_row, parse_finder_intent
from rat.engine.progressive_search import ProgressiveSearch, SearchRequest
from rat.kernel.capabilities.applications import create_applications_capability
from rat.kernel.contracts import ArtifactStore
from rat.kernel.dispatcher import ActionDispatcher
from rat.kernel.registry import CapabilityRegistry

TZ = timezone(timedelta(hours=7))
NOW = datetime(2026, 10, 18, 12, tzinfo=TZ)


def make_app(root, name, bundle_id='com.fixture.league'):
    path = root / (name + '.app')
    (path / 'Contents/MacOS').mkdir(parents=True)
    (path / 'Contents/Info.plist').write_bytes(plistlib.dumps({
        'CFBundleIdentifier': bundle_id, 'CFBundleName': name,
        'CFBundleExecutable': 'fixture-bin',
    }))
    (path / 'Contents/MacOS/fixture-bin').write_text('Never executed.')
    return path


def dispatcher():
    registry = CapabilityRegistry()
    registry.register_capability(create_applications_capability())
    return ActionDispatcher(registry, ArtifactStore())


def index(db, path, *, content='DSA', summary='', created=1, modified=1):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content)
    db.upsert_document(dict(file_path=str(path), file_name=path.name,
        file_ext=path.suffix, file_size=path.stat().st_size, created_at=created,
        modified_at=modified, indexed_at=1, content_text=content, summary=summary))


@pytest.fixture
def search(tmp_path):
    db = Database(str(tmp_path / 'fixture.db'))
    engine = ProgressiveSearch(db.db_path, now_fn=lambda: NOW)
    yield db, engine
    engine.close_connection()
    db.get_connection().close()


def test_partial_name_requires_selection_before_app_launch(tmp_path):
    make_app(tmp_path, 'League of Legends')
    catalog = ApplicationCatalog.scan([tmp_path])
    launches = []
    result = dispatcher().execute_operation('open_application', {'query': 'mở League'},
        context={'platform': 'darwin', 'catalog': catalog,
                 'app_launcher': lambda app: launches.append(app.path) or (True, None)})
    assert not launches, f'Prefix-only query launched {launches}'
    assert result.status == 'needs_input'


@pytest.mark.parametrize('query,expected', [
    ('slide format', 'format'), ('slide money', 'money'),
    ('báo cáo banking mới nhất', 'banking'),
])
def test_filler_removal_preserves_whole_keyword(query, expected):
    assert parse_finder_intent(query, now=NOW).query_terms == expected


def test_content_matched_report_survives_metadata_projection(search):
    db, engine = search
    # A pytest directory containing the test name would itself contain "report"
    # and mask this bug, because is_report_row searches the whole file_path.
    with TemporaryDirectory(prefix='rat-review-', dir='/tmp') as folder:
        path = Path(folder).resolve() / 'Q3.pdf'
        index(db, path, content='Quarterly report DSA', summary='Quarterly results')
        rows = db.search_metadata('', report_rule=True, sort='modified_desc')
        assert [r['file_path'] for r in rows] == [str(path)]
        snap = engine.initial(SearchRequest(1, 'bản báo cáo mới nhất'))
        assert [h.path for h in snap.hits] == [str(path)]


def test_slide_parent_rule_is_consistent_in_sql(search, tmp_path):
    db, engine = search
    path = tmp_path / 'slides' / 'DSA.pdf'
    index(db, path, content='DSA trees', summary='Trees and graphs')
    row = dict(file_path=str(path), file_name=path.name, file_ext='.pdf',
               summary='Trees and graphs')
    assert is_slide_row(row), 'The documented metadata rule accepts parent folder slides.'
    snap = engine.initial(SearchRequest(1, 'slide DSA'))
    assert [h.path for h in snap.hits] == [str(path)]


def test_creation_time_is_not_silently_replaced_with_modification_time(search, tmp_path):
    db, engine = search
    path = tmp_path / 'DSA.pptx'
    created = datetime(2026, 10, 7, 12, tzinfo=TZ).timestamp()
    index(db, path, created=created, modified=NOW.timestamp())
    snap = engine.initial(SearchRequest(1, 'Slide DSA tạo tuần trước'))
    assert (snap.intent.needs_clarification
            or [h.path for h in snap.hits] == [str(path)])


def test_last_week_half_open_range_includes_fractional_last_second(search, tmp_path):
    db, engine = search
    path = tmp_path / 'DSA.pptx'
    modified = datetime(2026, 10, 11, 23, 59, 59, 500000, tzinfo=TZ).timestamp()
    index(db, path, modified=modified)
    snap = engine.initial(SearchRequest(1, 'Slide DSA sửa tuần trước'))
    assert snap.intent.date_min <= modified < snap.intent.date_max_exclusive
    assert [h.path for h in snap.hits] == [str(path)]
