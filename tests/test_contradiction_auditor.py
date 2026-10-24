import pytest
try:
    from contradiction_auditor import (V, Ent, Tup, Role, GENERIC_SV, atoms, extract_all, build_index,
                                       audit, audit_text, match, gate, is_telemetry, iv, subset)
except ImportError:
    from rat.engine.contradiction_auditor import (V, Ent, Tup, Role, GENERIC_SV, atoms, extract_all, build_index,
                                                 audit, audit_text, match, gate, is_telemetry, iv, subset)

TOEIC = build_index("Yêu cầu tối thiểu TOEIC 600.")
DUR = build_index("Thời gian đào tạo tối đa 6 năm.")
SCOPED = build_index("Hệ chính quy: thời gian tối đa 6 năm.\nHệ vừa làm vừa học: thời gian tối đa 8 năm.")
TOEIC2 = build_index("Hệ chính quy: tối thiểu TOEIC 600.\nHệ vừa làm vừa học: tối thiểu TOEIC 600.")


def verdicts(ans, kb, q=None):
    return [f.result.verdict for f in audit_text(ans, kb, q)]


def one(ans, kb, q=None):
    fs = audit_text(ans, kb, q)
    assert len(fs) == 1, [(f.text, f.result) for f in fs]
    return fs[0].result


# ── Case 1: telemetry vs factual claim ──────────────────────────────────────
@pytest.mark.parametrize("s", ["Executed COT: 18 tokens", "[COT] 18 tokens, 230 ms", "Retrieved 3 chunks", "Latency 120 ms"])
def test_telemetry_dropped(s):
    assert is_telemetry(s) and atoms(s) == []


def test_telemetry_does_not_eat_claims():
    assert not is_telemetry("Step 2: SV cần tối thiểu 120 tín chỉ")
    out = atoms("Executed COT: 18 tokens. SV cần tối thiểu 120 tín chỉ.")
    assert len(out) == 1 and "120" in out[0].text


def test_expel_claim_is_atomic_and_keeps_outcome():
    t, un = extract_all("Sinh viên bị buộc thôi học khi tích lũy CPA < 1.2.")
    assert not un and len(t) == 1
    assert (t[0].metric, t[0].op, t[0].value, t[0].outcome) == ("cpa", "<", 1.2, "EXPEL")


def test_outcome_inherited_inside_sentence():
    t, _ = extract_all("SV bị buộc thôi học khi CPA < 1.2 và tích lũy dưới 30 tín chỉ.")
    assert [(x.metric, x.op, x.outcome) for x in t] == [("cpa", "<", "EXPEL"), ("credits", "<", "EXPEL")]


# ── Case 2a: threshold vs achieved value ────────────────────────────────────
def test_a_bound_satisfied():
    assert one("SV đạt TOEIC 650 => Đạt chuẩn.", TOEIC).verdict is V.SATISFIED_BOUND


def test_a_value_below_bound_conflicts():
    assert one("SV đạt TOEIC 550 => Đạt chuẩn.", TOEIC).verdict is V.GROUNDING_CONFLICT


def test_a_denial_below_bound_is_consistent():
    assert one("SV đạt TOEIC 550 nên chưa đạt chuẩn.", TOEIC).verdict is V.SATISFIED_BOUND


def test_a_fact_without_assertion_is_not_a_conflict():
    assert one("SV đạt TOEIC 550.", TOEIC).verdict is V.NOT_COMPARABLE


def test_a_boundary_value_is_closed():
    assert one("SV đạt TOEIC 600 => Đạt chuẩn.", TOEIC).verdict is V.SATISFIED_BOUND


# ── Case 2b: different entities ─────────────────────────────────────────────
def test_b_two_students_disjoint():
    t, _ = extract_all("An đạt TOEIC 650, Bình đạt TOEIC 700.")
    assert [x.entity.id for x in t] == ["an", "bình"]
    assert match(t[0], t[1]).verdict is V.DISJOINT_ENTITIES
    assert match(t[1], t[0]).verdict is V.DISJOINT_ENTITIES


def test_b_each_student_checked_against_norm_separately():
    assert verdicts("An đạt TOEIC 650 nên đạt chuẩn, Bình đạt TOEIC 550 nên đạt chuẩn.", TOEIC) == \
        [V.SATISFIED_BOUND, V.GROUNDING_CONFLICT]


def test_b_entity_does_not_leak_between_sentences():
    t, _ = extract_all("An đạt TOEIC 650. Điểm IELTS tối thiểu 6.")
    assert t[1].entity == GENERIC_SV


# ── Case 2c: real conflict ──────────────────────────────────────────────────
def test_c_looser_cap_conflicts():
    r = one("Được học tối đa 7 năm.", DUR)
    assert (r.verdict, r.reason) == (V.GROUNDING_CONFLICT, "looser")


def test_c_same_cap_ok_and_unit_conversion():
    assert one("Được học tối đa 6 năm.", DUR).verdict is V.SATISFIED_BOUND
    assert one("Được học tối đa 72 tháng.", DUR).verdict is V.SATISFIED_BOUND


def test_c_spelled_out_number():
    assert one("Được học tối đa bảy năm.", DUR).verdict is V.GROUNDING_CONFLICT
    assert one("Được học tối đa sáu năm.", DUR).verdict is V.SATISFIED_BOUND
    assert one("Được học tối đa năm năm.", DUR).reason == "tighter"


@pytest.mark.parametrize("claim,reason", [("dưới 6 năm", "boundary_only"), ("tối đa 5 năm", "tighter"), ("tối đa 7 năm", "looser")])
def test_c_cap_statements_block_both_directions(claim, reason):
    r = one(f"Sinh viên được học {claim}.", DUR)
    assert (r.verdict, r.reason) == (V.GROUNDING_CONFLICT, reason)


def test_c_point_statement_is_lenient_inside_bound_strict_outside():
    assert one("Thời gian đào tạo là 6 năm.", DUR).verdict is V.SATISFIED_BOUND
    assert one("Thời gian đào tạo là 7 năm.", DUR).verdict is V.GROUNDING_CONFLICT


# ── interval algebra ────────────────────────────────────────────────────────
def test_interval_subset_semantics():
    assert subset(iv("<", 6), iv("<=", 6)) and not subset(iv("<=", 6), iv("<", 6))
    assert subset(iv(">=", 130), iv(">=", 120)) and not subset(iv(">=", 100), iv(">=", 120))


# ── operator cues ───────────────────────────────────────────────────────────
@pytest.mark.parametrize("txt,op", [
    ("không vượt quá 6 năm", "<="), ("không quá 6 năm", "<="), ("không dưới 30 tín chỉ", ">="),
    ("không thấp hơn 30 tín chỉ", ">="), ("tối thiểu 120 tín chỉ", ">="), ("120 tín chỉ trở lên", ">="),
    ("6 năm trở xuống", "<="), ("vượt quá 6 năm", ">"), ("dưới 6 năm", "<"), ("trên 120 tín chỉ", ">"),
    ("phải đạt TOEIC 600", ">="), ("phải tích lũy 120 tín chỉ", ">="), ("CPA ≥ 2.0", ">="), ("CPA <= 2.0", "<="),
])
def test_operator_cues(txt, op):
    t, un = extract_all(txt)
    assert not un and t[0].op == op, (t, un)


# ── numeric hygiene ─────────────────────────────────────────────────────────
def test_decimal_comma_not_split():
    t, _ = extract_all("Buộc thôi học khi CPA < 1,2.")
    assert len(t) == 1 and t[0].value == 1.2


def test_citation_numbers_ignored():
    t, un = extract_all("Theo Điều 15, tối đa 6 năm.")
    assert not un and [x.value for x in t] == [6.0]


def test_unparsed_numbers_stay_visible():
    f = audit_text("Học kỳ 2 năm 2025 thì tối đa 6 năm.", DUR)
    assert f[0].result.reason.startswith("unparsed:multi_number")


# ── scope / condition handling ──────────────────────────────────────────────
def conds(text):
    return [(a.condition, a.text) for a in atoms(text)]


def test_scope_distributes_over_one_sentence_and_overrides():
    c = conds("Đối với hệ vừa làm vừa học: tối đa 8 năm, tối thiểu 120 tín chỉ, còn hệ chính quy: tối đa 6 năm.")
    assert [x[0] for x in c] == ["part-time", "part-time", "full-time"]


def test_scope_override_without_punctuation():
    assert [x[0] for x in conds("Hệ vừa làm vừa học tối đa 8 năm còn hệ chính quy tối đa 6 năm.")] == ["part-time", "full-time"]


def test_semicolon_keeps_scope():
    assert [x[0] for x in conds("Đối với hệ vừa làm vừa học: tối đa 8 năm; tối thiểu 120 tín chỉ.")] == ["part-time"] * 2


def test_header_plus_bullets_and_block_closing():
    txt = ("Đối với hệ vừa làm vừa học:\n- Tối đa 8 năm\n- Tối thiểu 120 tín chỉ\n"
           "Quy định chung: tối thiểu 120 tín chỉ.\nCòn hệ chính quy:\n- Tối đa 6 năm")
    assert [x[0] for x in conds(txt)] == ["part-time", "part-time", None, "full-time"]


def test_blank_line_closes_block():
    assert [x[0] for x in conds("Đối với hệ chính quy:\nTối đa 6 năm.\n\nTối đa 8 năm.")] == ["full-time", None]


def test_scope_in_the_middle_of_clause():
    assert conds("Thời gian tối đa của hệ vừa làm vừa học là 8 năm.")[0][0] == "part-time"


def test_scoped_claim_is_checked_inside_its_bucket():
    assert one("Hệ vừa làm vừa học tối đa 8 năm.", SCOPED).verdict is V.SATISFIED_BOUND
    assert one("Hệ chính quy tối đa 8 năm.", SCOPED).verdict is V.GROUNDING_CONFLICT


def test_unscoped_claim_three_outcomes():
    assert one("Tối đa 8 năm.", SCOPED).verdict is V.AMBIGUOUS_SCOPE
    assert one("Tối thiểu TOEIC 600.", TOEIC2).verdict is V.SATISFIED_BOUND
    assert one("Tối đa 10 năm.", SCOPED).verdict is V.GROUNDING_CONFLICT


def test_query_context_may_tighten_but_not_relax():
    assert one("Tối đa 8 năm.", SCOPED, "part-time").verdict is V.SCOPE_ELIDED
    assert one("Tối đa 8 năm.", SCOPED, "full-time").verdict is V.GROUNDING_CONFLICT


def test_out_of_vocabulary_programme_is_unverified_not_conflict():
    assert one("Đối với hệ sau đại học: tối đa 3 năm.", SCOPED).verdict is V.OUT_OF_COVERAGE


def test_unknown_programme_canary():
    for ans in ("Đối với hệ liên kết quốc tế: tối đa 8 năm.", "Đối với hệ liên kết quốc tế, tối đa 8 năm."):
        r = one(ans, SCOPED)
        assert (r.verdict, r.reason) == (V.OUT_OF_COVERAGE, "UNKNOWN:liên kết quốc tế")
    r = one("Đối với hệ liên kết quốc tế:\n- Tối thiểu TOEIC 600", TOEIC2)   # would be a false SAT without the canary
    assert r.verdict is V.OUT_OF_COVERAGE


@pytest.mark.parametrize("s", ["Đối với hệ thống tín chỉ, tối đa 6 năm.", "Với hệ số 2, tối đa 6 năm."])
def test_other_senses_of_he_are_not_programmes(s):
    assert conds(s)[0][0] is None


# ── gate ────────────────────────────────────────────────────────────────────
def test_gate_levels():
    g = lambda a, kb, q=None: gate(audit_text(a, kb, q))
    assert g("Được học tối đa 7 năm.", DUR) == "BLOCK"
    assert g("Tối đa 8 năm.", SCOPED) == "REGENERATE"
    assert g("Đối với hệ sau đại học: tối đa 3 năm.", SCOPED) == "ANNOTATE"
    assert g("Được học tối đa 6 năm.", DUR) == "PASS"


# ── temporal scope ──────────────────────────────────────────────────────────
def test_disjoint_temporal_scopes_not_comparable():
    src = Tup(GENERIC_SV, "duration", "<=", 6, "year", scope=(2020, 2022))
    clm = Tup(GENERIC_SV, "duration", "<=", 7, "year", scope=(2023, 2025))
    assert match(src, clm).verdict is V.NOT_COMPARABLE


# ── known gaps (documented, not hidden) ─────────────────────────────────────
@pytest.mark.xfail(reason="no exception/condition slot: 'trừ trường hợp gia hạn' sits in the same bucket -> pessimistic FP", strict=True)
def test_gap_exception_clause():
    kb = build_index("Thời gian đào tạo tối đa 6 năm, trừ trường hợp được gia hạn thì tối đa 8 năm.")
    assert one("Sinh viên được gia hạn có thể học tối đa 8 năm.", kb).verdict is V.SATISFIED_BOUND


@pytest.mark.xfail(reason="semester vs year not converted (needs school-specific semesters/year)", strict=True)
def test_gap_semester_unit():
    assert one("Được học tối đa 12 học kỳ.", DUR).verdict is V.SATISFIED_BOUND


# ── regressions found by mutation testing / raw-output review ───────────────
@pytest.mark.parametrize("ans", ["Được học 7 năm.", "Đã học 7 năm.", "Không đạt TOEIC 550 nên không đạt chuẩn."])
def test_sentence_initial_function_word_is_not_a_name(ans):
    kb = TOEIC if "TOEIC" in ans else DUR
    assert audit_text(ans, kb)[0].tup.entity == GENERIC_SV


def test_permission_beyond_cap_is_not_masked_as_fact():
    assert one("Được học 7 năm.", DUR).verdict is V.GROUNDING_CONFLICT


def test_denial_with_capitalised_negation_still_checked():
    assert one("Không đạt TOEIC 650 nên không đạt chuẩn.", TOEIC).verdict is V.GROUNDING_CONFLICT
    assert one("Không đạt TOEIC 550 nên không đạt chuẩn.", TOEIC).verdict is V.SATISFIED_BOUND


def test_bucket_is_pessimistic_inside_a_condition():
    kb = build_index("Thời gian tối đa 6 năm. Thời gian tối đa 8 năm.")      # same bucket, conflicting sources
    assert one("Tối đa 8 năm.", kb).verdict is V.GROUNDING_CONFLICT


def test_tie_break_prefers_specific_cue():
    t, _ = extract_all("không dưới 30 tín chỉ")
    assert t[0].op == ">="            # 'không dưới' and 'dưới' end at the same offset


def test_program_subject_with_co_is_a_norm_not_a_fact():
    assert one("Hệ vừa làm vừa học có thời gian đào tạo là 9 năm.", SCOPED).verdict is V.GROUNDING_CONFLICT
    assert one("Hệ vừa làm vừa học có thời gian đào tạo là 8 năm.", SCOPED).verdict is V.SATISFIED_BOUND


def test_student_with_co_is_a_fact():
    kb = build_index("Sinh viên bị buộc thôi học khi CPA < 1.2.")
    assert one("SV có CPA 1.5 bị buộc thôi học.", kb).verdict is V.GROUNDING_CONFLICT
    assert one("SV có CPA 1.0 bị buộc thôi học.", kb).verdict is V.SATISFIED_BOUND


def test_different_consequent_is_not_compared():
    kb = build_index("Sinh viên bị buộc thôi học khi CPA < 1.2.")
    r = one("SV có CPA 1.5 nên đạt chuẩn.", kb)          # PASS claim vs EXPEL rule: unrelated consequents
    assert r.verdict is V.NOT_COMPARABLE


# ── sanction vs requirement (false positives found by reviewing the demo output) ──
@pytest.mark.parametrize("src,claim", [
    ("Sinh viên cần tích lũy tối thiểu 120 tín chỉ.", "SV bị buộc thôi học khi tích lũy dưới 30 tín chỉ."),
    ("Sinh viên bị buộc thôi học khi CPA < 1.2.", "SV cần CPA tối thiểu 2.0."),
])
def test_sanction_and_requirement_are_not_compared(src, claim):
    assert one(claim, build_index(src)).verdict is V.NOT_COMPARABLE


def test_sanction_vs_same_sanction_is_still_compared():
    kb = build_index("Sinh viên bị buộc thôi học khi tích lũy dưới 30 tín chỉ.")
    assert one("SV bị buộc thôi học khi tích lũy dưới 40 tín chỉ.", kb).verdict is V.GROUNDING_CONFLICT
    assert one("SV bị buộc thôi học khi tích lũy dưới 30 tín chỉ.", kb).verdict is V.SATISFIED_BOUND


def test_requirement_with_unstated_consequent_still_compares_to_graduation_claim():
    kb = build_index("Sinh viên cần tích lũy tối thiểu 120 tín chỉ.")
    assert one("SV đủ điều kiện tốt nghiệp khi tích lũy tối thiểu 130 tín chỉ.", kb).verdict is V.GROUNDING_CONFLICT


# ── found by probing a KB that contains a bare unknown-programme header ──────
GENERAL_PLUS = build_index("Thời gian tối đa 9 năm.\nHệ chính quy: tối đa 6 năm.")


def test_no_query_context_is_not_the_general_bucket():
    r = one("Tối đa 6 năm.", GENERAL_PLUS)                       # general bucket CONFLICT, full-time SAT
    assert r.verdict is V.AMBIGUOUS_SCOPE
    assert one("Tối đa 6 năm.", GENERAL_PLUS, "full-time").verdict is V.SCOPE_ELIDED


def test_bare_unknown_programme_header_in_answer():
    r = one("Hệ liên kết quốc tế: tối đa 8 năm.", SCOPED)
    assert (r.verdict, r.reason) == (V.OUT_OF_COVERAGE, "UNKNOWN:liên kết quốc tế")


def test_unknown_programme_in_kb_is_not_filed_as_a_general_rule():
    kb = build_index("Hệ liên kết quốc tế: tối đa 9 năm.\nHệ chính quy: tối đa 6 năm.")
    assert [t.condition for t in kb[("duration", "year")]] == ["UNKNOWN:liên kết quốc tế", "full-time"]
    assert one("Hệ chính quy tối đa 6 năm.", kb).verdict is V.SATISFIED_BOUND
    assert one("Hệ vừa làm vừa học tối đa 6 năm.", kb).verdict is V.OUT_OF_COVERAGE   # other programme's rule must not apply
    assert one("Tối đa 6 năm.", kb).verdict is V.AMBIGUOUS_SCOPE
