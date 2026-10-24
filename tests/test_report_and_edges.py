"""Tests for the v2 layer: offset-preserving spans, UI annotations, answer-level summary, and the four edge bugs
(extended programme names / inline canary / digit programmes vs grading scales / query-scope evasion)."""
import pytest
try:
    from contradiction_auditor import V, atoms, audit_answer, audit_text, build_index, copy_footer, gate, normalize_map, infer_query_condition
except ImportError:
    from rat.engine.contradiction_auditor import V, atoms, audit_answer, audit_text, build_index, copy_footer, gate, normalize_map, infer_query_condition

KB = build_index("""Điều 12. Thời gian học tập
Hệ chính quy: thời gian tối đa là 6 năm.
Hệ vừa làm vừa học: thời gian tối đa là 8 năm.
Điều kiện tốt nghiệp: SV phải tích lũy tối thiểu 120 tín chỉ, CPA tối thiểu 2.0 và TOEIC tối thiểu 600.
SV có CPA dưới 1,2 bị buộc thôi học.""")
DUR = build_index("Thời gian đào tạo tối đa 6 năm.")


def one(ans, kb=KB, q=None):
    fs = audit_text(ans, kb, q)
    assert len(fs) == 1, [(f.text, f.result) for f in fs]
    return fs[0].result


# ── bug 1: a known programme name followed by an unexpected word is a LONGER (unknown) programme ──────────
def test_extended_programme_name_is_unknown_not_full_time():
    r = one("Đối với hệ chính quy chất lượng cao: tối thiểu TOEIC 600.")
    assert (r.verdict, r.reason) == (V.OUT_OF_COVERAGE, "UNKNOWN:chính quy chất lượng cao")


@pytest.mark.parametrize("s", ["Hệ chính quy có thời gian tối đa 6 năm.", "Hệ chính quy chỉ được học tối đa 6 năm.",
                               "Đối với hệ chính quy, tối đa 6 năm.", "Hệ chính quy: tối đa 6 năm."])
def test_known_programme_followed_by_a_predicate_stays_known(s):
    assert one(s).verdict is V.SATISFIED_BOUND


# ── bug 2: canary also fires on an inline cue with a comma ───────────────────────────────────────────────
def test_inline_unknown_programme_with_comma():
    r = one("Đối với hệ liên kết quốc tế, tối thiểu TOEIC 600.")
    assert (r.verdict, r.reason) == (V.OUT_OF_COVERAGE, "UNKNOWN:liên kết quốc tế")


# ── bug 3: digit programmes vs grading scales vs other senses of "hệ" ────────────────────────────────────
@pytest.mark.parametrize("s,name", [("Đối với hệ 4,5 năm: tối đa 10 năm.", "4,5 năm"),
                                    ("Hệ 5 năm: SV phải tích lũy tối thiểu 150 tín chỉ.", "5 năm")])
def test_digit_programme_names_are_unknown_programmes(s, name):
    r = one(s)
    assert (r.verdict, r.reason) == (V.OUT_OF_COVERAGE, f"UNKNOWN:{name}")


@pytest.mark.parametrize("s", ["SV cần CPA tối thiểu 2.0 theo hệ 4.", "SV cần CPA tối thiểu 2.0 (thang điểm hệ 4).",
                               "Hệ số quy đổi: tối thiểu TOEIC 600.", "Hệ thống quy định tối thiểu TOEIC 600."])
def test_grading_scales_and_other_senses_of_he_are_not_programmes(s):
    assert one(s).verdict is V.SATISFIED_BOUND


# ── bug 4: CONFLICT -> unverified through an unknown label while the query pinned a known programme ─────
FT = "full-time"


def test_query_scope_evasion_blocks_a_wrong_number_hidden_behind_an_unknown_label():
    r = one("Đối với hệ đại trà: tối đa 10 năm.", q=FT)
    assert (r.verdict, r.reason) == (V.GROUNDING_CONFLICT, "query_scope_evasion")


def test_unknown_label_with_a_correct_value_stays_unverified():
    assert one("Đối với hệ đại trà: tối đa 6 năm.", q=FT).verdict is V.OUT_OF_COVERAGE


def test_unknown_label_is_extra_info_when_the_answer_also_addresses_the_queried_programme():
    fs = audit_text("Hệ chính quy: tối đa 6 năm. Đối với hệ đại trà: tối đa 10 năm.", KB, FT)
    assert [f.result.verdict for f in fs] == [V.SATISFIED_BOUND, V.OUT_OF_COVERAGE]


def test_no_query_means_no_evasion_check():
    assert one("Đối với hệ đại trà: tối đa 10 năm.").verdict is V.OUT_OF_COVERAGE


# ── spans: every offset indexes the ORIGINAL answer ──────────────────────────────────────────────────────
def test_spans_survive_markdown_and_number_words():
    t = "**Hệ chính quy:**\n- Tối đa **sáu** năm.\n- Tối thiểu TOEIC 600."
    a = atoms(t)
    assert [t[x.start:x.end] for x in a] == ["Tối đa **sáu** năm.", "Tối thiểu TOEIC 600."]
    assert {t[x.scope_start:x.scope_end] for x in a} == {"Hệ chính quy:"} and {x.scope_src for x in a} == {"HEADER"}


def test_normalize_map_is_length_aligned():
    s, sp = normalize_map("**A**  1,2 năm (tương đương 14 học kỳ) ba năm")
    assert len(s) == len(sp) and all(0 <= a <= b for a, b in sp)


def test_inline_scope_span_is_the_cue():
    t = "Thời gian tối đa là 6 năm, còn hệ vừa làm vừa học: tối đa 8 năm."
    a = atoms(t)
    assert a[-1].scope_src == "INLINE" and t[a[-1].scope_start:a[-1].scope_end].strip() == "còn hệ vừa làm vừa học:"


# ── annotations: 2-tier anchor ────────────────────────────────────────────────────────────────────────────
def test_header_scoped_unverified_gets_ONE_label_on_the_header_line():
    t = "Hệ liên kết quốc tế:\n- Tối đa 8 năm.\n- Tối thiểu TOEIC 600."
    r = audit_answer(t, KB)
    assert [(x.kind, x.anchor, t[x.start:x.end]) for x in r.annotations] == \
        [("OUT_OF_COVERAGE", "HEADER", "Hệ liên kết quốc tế:")]
    assert r.gate == "ANNOTATE"


def test_inline_scoped_label_covers_cue_and_clause():
    t = "Hệ chính quy: tối đa 6 năm. Hệ liên kết quốc tế: tối đa 10 năm."
    r = audit_answer(t, KB)
    assert [(x.kind, x.anchor, t[x.start:x.end]) for x in r.annotations] == \
        [("OUT_OF_COVERAGE", "CLAUSE", "Hệ liên kết quốc tế: tối đa 10 năm.")]


def test_conflict_is_anchored_on_its_clause_even_under_a_header():
    t = "Hệ chính quy:\n- Tối đa 7 năm.\n- Tối thiểu TOEIC 600."
    r = audit_answer(t, KB)
    assert [(x.kind, x.anchor, t[x.start:x.end]) for x in r.annotations] == \
        [("GROUNDING_CONFLICT", "CLAUSE", "Tối đa 7 năm.")]
    assert r.gate == "BLOCK"


def test_satisfied_claims_get_no_label():
    assert audit_answer("Hệ chính quy: tối đa 6 năm.", KB).annotations == []


def test_markdown_table_rows_are_atoms_with_row_spans():
    t = "| Hệ | Thời gian tối đa |\n|---|---|\n| Chính quy | 7 năm |\n| Vừa làm vừa học | 8 năm |"
    r = audit_answer(t, KB)
    assert [f.result.verdict for f in r.findings] == [V.GROUNDING_CONFLICT, V.SATISFIED_BOUND]
    assert [t[x.start:x.end] for x in r.annotations] == ["| Chính quy | 7 năm |"]


# ── answer-level summary: never a green "verified" ───────────────────────────────────────────────────────
def test_summary_counts_and_sentences_without_numbers():
    r = audit_answer("Quy chế khá phức tạp. Thời gian tối đa 6 năm. Bạn nên hỏi phòng đào tạo.", DUR)
    s = r.summary
    assert (s["quantitative_checked"], s["satisfied"], s["conflict"], s["sentences"], s["sentences_without_numbers"]) == (1, 1, 0, 3, 2)
    assert "chưa được tự động kiểm chứng" in s["note"] and "verified" not in s


def test_all_prose_answer_is_not_reported_as_verified():
    r = audit_answer("Bạn nên liên hệ phòng đào tạo để biết thêm chi tiết.", DUR)
    assert r.summary["quantitative_checked"] == 0 and r.summary["sentences_without_numbers"] == 1 and r.gate == "PASS"


def test_report_gate_equals_gate_of_findings():
    t = "Hệ chính quy: tối đa 7 năm."
    r = audit_answer(t, KB)
    assert r.gate == gate(r.findings) == "BLOCK"


def test_copy_footer_only_when_something_is_unverified():
    assert copy_footer(audit_answer("Hệ liên kết quốc tế: tối đa 10 năm.", KB)).startswith("[Lưu ý")
    assert copy_footer(audit_answer("Hệ chính quy: tối đa 6 năm.", KB)) == ""


# ── normalisation features found by the gold set ─────────────────────────────────────────────────────────
def test_ruoi_is_half():
    assert one("Thời gian tối đa 6 năm rưỡi.", DUR).verdict is V.GROUNDING_CONFLICT
    assert one("Thời gian tối đa 5 năm rưỡi.", DUR).verdict is V.GROUNDING_CONFLICT        # '<= 5.5' != '<= 6'
    assert one("Thời gian học là 4 năm rưỡi.", DUR).verdict is V.SATISFIED_BOUND


def test_restatement_parenthetical_does_not_hide_the_claim():
    r = one("Hệ chính quy được học tối đa 7 năm (tương đương 14 học kỳ).")
    assert r.verdict is V.GROUNDING_CONFLICT


def test_paren_scope_and_không_được_học_quá():
    assert one("Sinh viên không được học quá 7 năm (hệ chính quy).").verdict is V.GROUNDING_CONFLICT
    assert one("Sinh viên không được học quá 6 năm (hệ chính quy).").verdict is V.SATISFIED_BOUND


def test_per_semester_load_is_not_the_programme_total():
    assert one("Bạn nên đăng ký khoảng 15 tín chỉ mỗi học kỳ.").verdict is V.NOT_COMPARABLE


def test_remaining_time_is_not_the_cap():
    assert one("Bạn còn tối đa 1 năm để hoàn thành (hệ chính quy).").verdict is V.NOT_COMPARABLE
    assert one("Bạn còn tối đa 1 năm để hoàn thành.", DUR).verdict is V.NOT_COMPARABLE


def test_grading_scale_does_not_pollute_other_claims():
    t = "SV cần CPA tối thiểu 2.0 trên thang điểm hệ 4 và TOEIC tối thiểu 700."
    assert sorted(f.result.verdict.name for f in audit_text(t, KB)) == ["GROUNDING_CONFLICT", "SATISFIED_BOUND"]


def test_summary_separates_unparsed_from_not_comparable():
    r = audit_answer("Bạn nên đăng ký khoảng 15 tín chỉ mỗi học kỳ. Thời gian là từ 2 đến 3 năm.", DUR)
    s = r.summary
    assert (s["not_comparable"], s["unparsed"], s["quantitative_checked"]) == (1, 1, 1)


# ── unicode: NFD text (macOS, PDF extraction) and odd spaces must behave exactly like NFC ─────────────────
import unicodedata  # noqa: E402

NFD = lambda s: unicodedata.normalize("NFD", s)  # noqa: E731


def test_nfd_answer_and_nfd_source_behave_like_nfc():
    ans = "Hệ chính quy được học tối đa 7 năm."
    assert [f.result for f in audit_text(NFD(ans), KB)] == [f.result for f in audit_text(ans, KB)]
    assert audit_answer(ans, build_index(NFD("Hệ chính quy: tối đa 6 năm."))).gate == "BLOCK"


def test_nfd_spans_index_the_original_text():
    t = NFD("Hệ chính quy:\n- Tối đa 7 năm.")
    r = audit_answer(t, KB)
    assert [t[x.start:x.end] for x in r.annotations] == [NFD("Tối đa 7 năm.")]


def test_nbsp_and_zero_width_do_not_split_a_programme_name():
    assert audit_answer("Hệ chính quy được học tối đa 7 năm.", KB).gate == "BLOCK"
    assert audit_answer("Hệ \u200bchính quy được học tối đa 6 năm.", KB).gate == "PASS"


@pytest.mark.parametrize(
    "query,expected",
    [
        ("học phí hệ chính quy là bao nhiêu?", "full-time"),
        ("hệ chính quy bao nhiêu năm?", "full-time"),
        # Nhãn lạ không có từ khoá 'hệ' ("còn đại trà?") là giới hạn đã biết:
        ("hệ chính quy là gì? còn đại trà?", "full-time"),
        ("thời gian tối đa hệ vừa làm vừa học", "part-time"),
        ("thời gian đào tạo bậc thạc sĩ", "postgrad"),
        ("học phí hệ từ xa", "distance"),
        ("sinh viên chính quy được học tối đa mấy năm?", "full-time"),
    ],
)
def test_infer_query_condition_single_programme(query, expected):
    assert infer_query_condition(query) == expected


@pytest.mark.parametrize(
    "query",
    [
        "so sánh thời gian giữa hệ chính quy và hệ vừa làm vừa học",
        "sự khác biệt giữa chính quy và từ xa",
        "hệ chính quy hay vừa làm vừa học học lâu hơn?",
        "hệ chính quy là gì và hệ 4,5 năm là gì?",
    ],
)
def test_infer_query_condition_multiple_programmes(query):
    assert infer_query_condition(query) is None


@pytest.mark.parametrize(
    "query",
    [
        "thời gian học hệ đại trà là bao lâu?",
        "hệ liên kết quốc tế cần bao nhiêu tín chỉ?",
        "điều kiện tốt nghiệp hệ 5 năm",
        "thang điểm hệ 4 là gì?",
        "sinh viên năm 3 cần đạt bao nhiêu tín chỉ?",
        "",
        None,
    ],
)
def test_infer_query_condition_unknown_or_no_programme(query):
    assert infer_query_condition(query) is None
