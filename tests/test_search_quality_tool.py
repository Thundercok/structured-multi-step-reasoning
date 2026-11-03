"""The quality score must count files as a person sees them and keep question sources apart."""
import importlib.util
from pathlib import Path

spec = importlib.util.spec_from_file_location(
    'measure_search_quality', Path(__file__).resolve().parents[1] / 'tools/measure_search_quality.py')
tool = importlib.util.module_from_spec(spec)
spec.loader.exec_module(tool)


def rows(*paths):
    return [{'file_path': path} for path in paths]


def test_rank_matches_part_of_the_file_name_ignoring_case_and_folder():
    assert tool.rank_of(['invoice'], ['/a/invoice_dir/note.txt', '/b/Invoice-1.pdf']) == 2
    assert tool.rank_of(['invoice'], ['/a/note.txt']) is None


def test_several_chunks_of_one_file_count_as_one_result():
    assert tool.unique_files(rows('/a.pdf', '/a.pdf', '/b.pdf')) == ['/a.pdf', '/b.pdf']


def test_summary_counts_top_positions_and_misses():
    summary = tool.summarize([1, 2, 4, None])
    assert summary == {'questions': 4, 'top_1': 1, 'top_3': 2, 'not_found': 1,
                       'mean_reciprocal_rank': round((1 + 1 / 2 + 1 / 4) / 4, 3)}


def test_sources_are_scored_apart_and_together():
    results = {'q1': rows('/right.pdf'), 'q2': rows('/wrong.pdf')}
    cases = [{'query': 'q1', 'expect': ['right'], 'source': 'draft'},
             {'query': 'q2', 'expect': ['right'], 'source': 'user'}]
    lines, summary = tool.score(cases, results.__getitem__)
    assert [line['rank'] for line in lines] == [1, None]
    assert summary['draft']['top_1'] == 1 and summary['user']['top_1'] == 0
    assert summary['all']['questions'] == 2


def test_empty_question_set_does_not_divide_by_zero():
    assert tool.summarize([])['mean_reciprocal_rank'] == 0.0
