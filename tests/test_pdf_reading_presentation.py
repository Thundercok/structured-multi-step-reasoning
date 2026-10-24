"""Whitespace presentation/quote contracts, no PDF fixtures or model calls."""
import pytest

from rat.ui.answer_presentation import page_reading_text
from rat.engine.selected_pdf import selected_source_text, SelectedPDFError


def test_prose_wrap_joins_but_next_paragraph_and_bullet_remain():
    raw = ('A long sentence continues naturally across a physical\n'
           'line in the extracted page.\n\n'
           '• Another point\n')
    displayed = page_reading_text(raw)
    assert 'physical line' in displayed
    assert '\n\n• Another point' in displayed
    assert len(displayed) == len(raw)
    assert ''.join(displayed.split()) == ''.join(raw.split())


@pytest.mark.parametrize('raw', [
    'A sufficiently long formula heading with symbols = 2\nand a lower-case continuation\n',
    'A sufficiently long table row with multiple  columns\nand a lower-case continuation\n',
    '    A sufficiently long indented program source line\n    and a continuation\n',
    '```\nA sufficiently long source line for an example\nand a continuation\n```',
])
def test_formulas_tables_and_code_are_not_joined(raw):
    assert page_reading_text(raw) == raw


def test_reading_selection_copies_exact_source_not_display_whitespace():
    raw = 'Queries are assigned to models of varying cost\nand quality to obtain a desired trade-off.'
    displayed = page_reading_text(raw)
    assert '\n' not in displayed
    assert selected_source_text(raw, displayed) == raw
    assert selected_source_text(raw, 'varying cost and quality') == 'varying cost\nand quality'
    with pytest.raises(SelectedPDFError, match='invalid_citation'):
        selected_source_text(raw, 'varying cost and certainty')
    with pytest.raises(SelectedPDFError, match='invalid_citation'):
        selected_source_text(raw, '  ')
