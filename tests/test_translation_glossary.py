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


def test_extended_paper_terms_en_vi():
    text, mapping = protect('We use scaled dot-product attention with positional encoding and feed-forward networks.')
    assert 'scaled dot-product attention' not in text
    assert 'positional encoding' not in text
    assert 'feed-forward networks' not in text
    assert 'chú ý tích vô hướng theo tỉ lệ (scaled dot-product attention)' in mapping.values()
    assert 'mã hóa vị trí (positional encoding)' in mapping.values()
    assert 'mạng truyền thẳng (feed-forward networks)' in mapping.values()


def test_vi_to_en_direction_protects_and_restores():
    text, mapping = protect('Mạng nơ-ron tích chập và mạng nơ-ron hồi quy được huấn luyện bằng lan truyền ngược.',
                            source='vi', target='en')
    assert 'mạng nơ-ron tích chập' not in text.lower()
    assert 'mạng nơ-ron hồi quy' not in text.lower()
    assert 'lan truyền ngược' not in text.lower()
    assert mapping['T1'] == 'convolutional neural network (CNN)'
    assert mapping['T2'] == 'recurrent neural network (RNN)'
    assert mapping['T3'] == 'training'
    assert mapping['T4'] == 'backpropagation'

    # Simulated MT output with placeholders intact
    mt_out = 'T1 and T2 are T3 using T4.'
    restored = restore(mt_out, mapping)
    assert restored == 'Convolutional neural network (CNN) and recurrent neural network (RNN) are training using backpropagation.'


def test_everyday_english_is_not_treated_as_research_terms():
    for sentence in ('The train leaves the station at noon, so please recall your token.',
                     'Please pay attention to the teacher.'):
        assert protect(sentence) == (sentence, {})


def test_ambiguous_terms_still_protected_in_research_text():
    _, mapping = protect('We train the model and report precision and recall.')
    assert set(mapping.values()) >= {'huấn luyện', 'precision', 'recall'}
    _, mapping = protect('The train set feeds a classifier.')
    assert 'huấn luyện' not in mapping.values()
