"""Legacy VGC uses the same arithmetic gate and only certifies source excerpts."""
import pytest

from rat.engine.vgc import VGCCertificate, VGCCascadeEngine, VGCVerificationStatus, VGCVerifier


def test_program_output_matching_itself_cannot_verify_wrong_expression():
    result = VGCVerifier.verify_calculation(VGCCertificate('999', '999', raw_code='print(999)'), '2 + 2')
    assert result.status == VGCVerificationStatus.INVALID
    assert result.scope == 'calculation'


def test_witness_and_final_claim_are_both_checked():
    result = VGCVerifier.verify_calculation(VGCCertificate('999', '4'), '2 + 2')
    assert result.status == VGCVerificationStatus.INVALID


def test_number_in_source_does_not_verify_wrong_entity_relation():
    source = 'Alice scored 100 points. Bob scored 20 points.'
    claim = 'Bob scored 100 points.'
    result = VGCVerifier.verify_document_fact(VGCCertificate(claim, claim, source_snippet=source), source)
    assert result.status == VGCVerificationStatus.UNVERIFIABLE


def test_exact_excerpt_has_explicit_limited_scope():
    source = 'Alice scored 100 points. Bob scored 20 points.'
    result = VGCVerifier.verify_document_fact(VGCCertificate('Bob scored 20 points.', '', source_snippet='Bob scored 20 points.'), source)
    assert result.status == VGCVerificationStatus.VALID
    assert result.scope == 'source_excerpt'
    assert 'authenticity are unchecked' in result.reason


def test_entire_snippet_is_checked_not_only_its_prefix():
    source = 'Alice scored 100 points. Bob scored 20 points. The semester ended.'
    result = VGCVerifier.verify_document_fact(VGCCertificate(source, '', source_snippet=source + ' Invented ending.'), source)
    assert result.status == VGCVerificationStatus.INVALID


def test_cascade_rechecks_correction_and_does_not_claim_model_inference():
    result = VGCCascadeEngine().solve_quantitative('2 + 2', '2 + 2', python_code='print(999)')
    assert result.verification.status == VGCVerificationStatus.VALID
    assert result.verification.certificate.witness == '4'
    assert not result.escalated and result.tokens == 0 and result.confidence is None
    assert '4' in result.answer and '999' not in result.answer


def test_unsupported_rounding_does_not_gain_a_verified_label():
    result = VGCVerifier.verify_calculation(VGCCertificate('7.4', '7.4'), 'round(7.399, 1)')
    assert result.status == VGCVerificationStatus.UNVERIFIABLE


def test_rounded_witness_is_not_accepted_as_an_exact_division():
    result = VGCVerifier.verify_calculation(VGCCertificate('3.3333', '3.3333'), '10 / 3')
    assert result.status == VGCVerificationStatus.INVALID


@pytest.mark.parametrize('query', [
    'CPA 9.1 với 100 tín chỉ, thêm một môn thì bao nhiêu?',
    'Tính học phí cho 7 tín chỉ',
    'Tính học phí 999 tín chỉ giá 12345 mỗi tín chỉ và giảm 10%',
])
def test_legacy_word_problems_do_not_invent_inputs_or_numeric_certificates(query):
    from rat.engine.meta_reasoner import MetaReasonerEngine
    result = MetaReasonerEngine().solve(query)
    assert result.verification_status == 'unverifiable'
    assert result.witness_proof is None
    assert result.tokens == 0
    assert result.confidence_kind == 'not_estimated'
    assert 'không tự điền' in result.answer


def test_meta_reasoner_returns_verified_literal_answer_with_zero_model_tokens():
    from rat.engine.meta_reasoner import MetaReasonerEngine
    result = MetaReasonerEngine().solve('tính (123 + 45) * 2')
    assert result.verification_status == 'valid'
    assert result.witness_proof == '336'
    assert '336' in result.answer
    assert result.tokens == 0 and result.confidence_kind == 'not_estimated'
