from rat.engine.pdf_text import clean_copied_text


def test_joins_wrapped_lines_and_hyphenation_inside_a_paragraph():
    text, joins = clean_copied_text('based on com-\nplex recurrent\nnetworks.\n\nNext paragraph.')
    assert text == 'based on complex recurrent networks.\n\nNext paragraph.'
    assert joins == 2


def test_ligatures_soft_hyphens_and_list_items():
    text, joins = clean_copied_text('signiﬁcantly e­ffective\n1. first item\n2. second item')
    assert text == 'significantly effective\n1. first item\n2. second item'
    assert joins == 0


def test_capitalised_continuation_keeps_its_hyphen():
    assert clean_copied_text('state-of-the-\nArt models')[0] == 'state-of-the- Art models'
