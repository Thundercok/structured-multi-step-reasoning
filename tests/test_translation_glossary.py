from rat.engine.translation_glossary import protect, restore


def test_terms_become_placeholders_and_render_back():
    text, mapping = protect('We train the Transformer with self-attention on two datasets.')
    assert 'Transformer' not in text and 'self-attention' not in text
    assert restore(text, mapping) == 'We huấn luyện the Transformer with tự chú ý (self-attention) on two tập dữ liệu.'


def test_longest_term_wins_and_repeats_share_one_placeholder():
    text, mapping = protect('Multi-head self-attention beats attention; attention is cheap.')
    assert list(mapping.values()) == ['tự chú ý đa đầu (multi-head self-attention)', 'cơ chế chú ý (attention)']
    assert text == 'T1 beats T2; T2 is cheap.'


def test_placeholder_letter_avoids_existing_tokens_and_capitalises_sentence_start():
    text, mapping = protect('T1 weighted scans: dropout helps.')
    assert text.startswith('T1 weighted') and 'K1' in text
    assert restore('K1 giúp ích.', {'K1': 'quá khớp (overfitting)'}) == 'Quá khớp (overfitting) giúp ích.'


def test_plain_text_is_untouched():
    assert protect('Students go to the library.') == ('Students go to the library.', {})
