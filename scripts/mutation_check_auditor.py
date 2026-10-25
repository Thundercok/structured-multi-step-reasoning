"""Mutation harness: every mutant is a deliberate bug; the suite MUST go red on each one.

    python scripts/mutation_check_auditor.py          # exit 1 if any mutant survives (= a behaviour the tests do not pin)

Each mutant is (label, [(old, new), ...]) applied to a temp copy of rat/engine/contradiction_auditor.py.
`old` must occur exactly once, so a refactor that moves the code fails loudly instead of silently passing.
The two strict-xfail "known gap" tests are deselected: a mutant must not count as killed only because an
xfail started passing.
"""
from __future__ import annotations

import pathlib
import shutil
import subprocess
import sys
import tempfile

REPO_ROOT = pathlib.Path(__file__).resolve().parent.parent
ENGINE_SRC = REPO_ROOT / "rat" / "engine" / "contradiction_auditor.py"
TEST1_SRC = REPO_ROOT / "tests" / "test_contradiction_auditor.py"
TEST2_SRC = REPO_ROOT / "tests" / "test_report_and_edges.py"
XFAIL = [
    "test_contradiction_auditor.py::test_gap_exception_clause",
    "test_contradiction_auditor.py::test_gap_semester_unit",
    "test_report_and_edges.py::test_gap_unknown_label_without_he_in_query",
]

MUTANTS = [
    ("M01 '<=' loses its closed upper flag",        [('"<=": (-inf, v, False, True)', '"<=": (-inf, v, False, False)')]),
    ("M02 comma splits inside decimals",            [(r"[,;]\s+|;|", r"[,;]\s*|;|")]),
    ("M03 telemetry gate drops domain guard",       [("and not _DOMAIN.search(s))", ")")]),
    ("M04 FACT ignores asserted/denied outcome",    [('holds == clm.verdict else Res(V.GROUNDING_CONFLICT, "fact_vs_bound")', 'True else Res(V.GROUNDING_CONFLICT, "fact_vs_bound")')]),
    ("M05 every entity governs every entity",       [("return a.id == b.id or (not a.instance and a.id in b.classes)", "return True")]),
    ("M06 query context may relax to SCOPE_ELIDED", [("if q.verdict is V.GROUNDING_CONFLICT", "if False")]),
    ("M07 header block never closes after a list",  [("if block and in_list and not is_b:", "if False:")]),
    ("M08 narrower rule treated as satisfied",      [('return Res(V.GROUNDING_CONFLICT, "looser" if not subset(C, S) else "tighter")', 'return Res(V.SATISFIED_BOUND) if subset(C, S) else Res(V.GROUNDING_CONFLICT, "looser")')]),
    ("M09 unknown-programme canary removed",        [("if m := _CANARY.match(p):", "if False:")]),
    ("M10 bucket: satisfied-first, not pessimistic", [("for want in (V.GROUNDING_CONFLICT, V.SATISFIED_BOUND):", "for want in (V.SATISFIED_BOUND, V.GROUNDING_CONFLICT):")]),
    ("M11 op tie-break picks the generic cue",      [("hits = [(mm.end(), -i, op)", "hits = [(mm.end(), i, op)")]),
    ("M12 spelled-out numbers not normalised",      [('(_NUMW_RE, lambda m: f"{_NUMW[m[1].lower()]} "),', "(_NUMW_RE, lambda m: m[0]),")]),
    ("M13 citation numbers (Điều 15) not stripped", [('(_CITE, " "),', "(_CITE, lambda m: m[0]),")]),
    ("M14 entity carries across sentences",         [("def _sentence_atoms(sent: str, s0: int, block, override) -> list[Atom]:",
                                                      "_LAST = [GENERIC_SV]\ndef _sentence_atoms(sent: str, s0: int, block, override) -> list[Atom]:"),
                                                     ("rows, last, per_carry = [], GENERIC_SV, False", "rows, last, per_carry = [], _LAST[0], False"),
                                                     ("        last = ent or last\n", "        last = ent or last\n        _LAST[0] = last\n")]),
    ("M15 'Được/Không…' accepted as a person name", [("and m[1].lower() not in _NAMED_STOP):", "):")]),
    ("M16 'có' alone makes a FACT (no SV subject)", [("bool(_WEAK.search(a.text) and _SUBJ.search(a.text))", "bool(_WEAK.search(a.text))")]),
    ("M17 negation ignored when reading outcome",   [("return name, bool(_NEG.search(p[:m.start()]))", "return name, False")]),
    ("M18 outcome not inherited inside a sentence", [("shared = next((r[3] for r in rows if r[3]), None) if len(outs) == 1 else None", "shared = None")]),
    ("M19 scoped claim ignores its own bucket",     [("pool = [s for s in cand if s.condition == clm.condition] or [s for s in cand if s.condition is None]", "pool = cand")]),
    ("M20 đạt/đã/tích lũy no longer imply FACT",    [("a.entity.instance or bool(_STRONG.search(a.text))", "a.entity.instance")]),
    ("M21 'phải' no longer a >= cue",               [(r"\bít\s+nhất|\bphải\b", r"\bít\s+nhất")]),
    ("M22 point statement strict, not lenient",     [('return Res(V.SATISFIED_BOUND) if contains(S, clm.value) else Res(V.GROUNDING_CONFLICT, "point_outside")', 'return Res(V.GROUNDING_CONFLICT, "point_outside")')]),
    ("M23 canary stoplist (hệ thống/số/quả) gone",  [(r"(?!thống\b|số\b|quả\b|\d+", r"(?!\d+")]),
    ("M24 header-only line detection removed",      [("if h := _header_scope(line):", "if False:")]),
    ("M25 outcome check disabled",                  [("if not _outcomes_comparable(src.outcome, clm.outcome):", "if False:")]),
    ("M26 sanction compared with anything",         [("    return (a or b) not in _SANCTION", "    return True")]),
    ("M27 unstated consequent never comparable",    [("    return (a or b) not in _SANCTION", "    return False")]),
    ("M28 sanction set empty",                      [('_SANCTION = {"EXPEL"}', "_SANCTION = set()")]),
    ("M29 query_condition=None matches general bucket", [("if query_condition is not None and query_condition in agg:", "if query_condition in agg:")]),
    ("M30 canary needs a lead word again",          [(r"^(?:{_LEAD})?hệ", r"^{_LEAD}hệ")]),
    # ── v2 layer ──
    ("M31 programme extension guard removed",       [("if _AFTER_PROG.match(tail):", "if True:")]),
    ("M32 'hệ 5 năm' read as a grading scale",      [(r"(?![.,]?\d)(?!\s*(?:năm|học\s+kỳ)\b))", r"(?![.,]?\d))")]),
    ("M33 evasion pass disabled",                   [("return _evasion_pass(fs, kb, query_condition), stats", "return fs, stats")]),
    ("M34 evasion ignores that the queried programme is addressed", [("        if any(g.tup and (g.tup.metric", "        if False and any(g.tup and (g.tup.metric")]),
    ("M35 markdown not stripped",                   [('(_MD, ""),', "(_MD, lambda m: m[0]),")]),
    ("M36 restatement parenthetical not stripped",  [('(_RESTATE, " "),', "(_RESTATE, lambda m: m[0]),")]),
    ("M37 grading-scale 'hệ 4' not stripped",       [('(_SCALE, " "),', "(_SCALE, lambda m: m[0]),")]),
    ("M38 per-semester load compared with total",   [('unit = "credit/semester"', "pass")]),
    ("M39 remaining time compared with the cap",    [('unit += "/remaining"', "pass")]),
    ("M40 markdown tables ignored",                 [("    if len(data) < 2:\n        return []", "    return []")]),
    ("M41 offset map collapses",                    [("osp.extend([(sp[m.start()][0], sp[m.end() - 1][1])] * len(r))", "osp.extend([(0, 0)] * len(r))")]),
    ("M42 inline label drops the cue",              [('if f.scope_src == "INLINE" and 0 <= f.scope_span[0] < s0:', "if False:")]),
    ("M43 header label repeated per bullet",        [("if f.scope_span in seen:", "if False:")]),
    ("M44 'rưỡi' ignored",                          [('(_RUOI, lambda m: f"{m[1]}.5 {m[2]}"),', "(_RUOI, lambda m: m[0]),")]),
    ("M45 summary counts unparsed as comparable",   [('"not_comparable": n(V.NOT_COMPARABLE) - unparsed,', '"not_comparable": n(V.NOT_COMPARABLE),')]),
    ("M46 INLINE cue ('Hệ X,') not caught by canary", [('"UNKNOWN:" + re.sub(r"\\s+", " ", m["x"].strip().lower()), m.end()', 'None')]),
    ("M47 NFD text not recomposed",                 [('(_COMBINING, lambda m: unicodedata.normalize("NFC", m[0])),', "(_COMBINING, lambda m: m[0]),")]),
    ("M48 non-breaking space not normalised",       [('(_ODD_SPACE, " "),', "(_ODD_SPACE, lambda m: m[0]),")]),
    ("M49 zero-width characters not removed",       [('(_ZERO_WIDTH, ""),', "(_ZERO_WIDTH, lambda m: m[0]),")]),
    ("M50 query: interrogatives read as part of the name", [("{_PRED}|bao|mấy|nào|", "{_PRED}|")]),
    ("M51 query: extended name of a known programme pins",  [("if nxt and not re.fullmatch(_Q_STOP, nxt, re.I):", "if False:")]),
    ("M52 query: unknown `hệ <label>` does not veto",       [("        if not _Q_ALIAS.match(rest):", "        if False:")]),
    ("M53 query: grading scale vetoes the pin",             [("if _Q_NOT_A_PROGRAMME.match(rest) or _Q_SCALE.match(rest):", "if _Q_NOT_A_PROGRAMME.match(rest):")]),
    ("M54 query: 'hệ thống' vetoes the pin",                [("if _Q_NOT_A_PROGRAMME.match(rest) or _Q_SCALE.match(rest):", "if _Q_SCALE.match(rest):")]),
    ("M55 query: zero-width characters not removed",        [('q = _ODD_SPACE.sub(" ", _ZERO_WIDTH.sub("", q))', "q = q")]),
    ("M56 query: several programmes pin an arbitrary one",  [("return next(iter(ids)) if len(ids) == 1 else None", "return next(iter(ids)) if ids else None")]),
    ("M57 'đăng ký' no longer marks a per-term load",       [("or (_REG.search(text) and not _TOTAL.search(text))", "")]),
    ("M58 total/graduation wording does not cancel 'đăng ký'", [("or (_REG.search(text) and not _TOTAL.search(text))", "or _REG.search(text)")]),
]


def run(label, edits):
    w = pathlib.Path(tempfile.mkdtemp())
    try:
        shutil.copy(ENGINE_SRC, w / "contradiction_auditor.py")
        shutil.copy(TEST1_SRC, w / "test_contradiction_auditor.py")
        shutil.copy(TEST2_SRC, w / "test_report_and_edges.py")
        p = w / "contradiction_auditor.py"
        s = p.read_text(encoding="utf-8")
        for old, new in edits:
            if s.count(old) != 1:
                return label, "INVALID", f"pattern occurs {s.count(old)}x: {old[:50]!r}"
            s = s.replace(old, new)
        p.write_text(s, encoding="utf-8")
        cmd = [sys.executable, "-m", "pytest", "-q", "-p", "no:cacheprovider"] + [a for x in XFAIL for a in ("--deselect", x)]
        out = subprocess.run(cmd, cwd=w, capture_output=True, text=True).stdout.strip().splitlines()
        failed = [l.split("::")[1].split(" ")[0] for l in out if l.startswith("FAILED")]
        return label, ("KILLED" if failed else "SURVIVED"), (failed[0] if failed else (out[-1] if out else "no output"))
    finally:
        shutil.rmtree(w, ignore_errors=True)


if __name__ == "__main__":
    w = pathlib.Path(tempfile.mkdtemp())
    try:
        shutil.copy(ENGINE_SRC, w / "contradiction_auditor.py")
        shutil.copy(TEST1_SRC, w / "test_contradiction_auditor.py")
        shutil.copy(TEST2_SRC, w / "test_report_and_edges.py")
        base = subprocess.run([sys.executable, "-m", "pytest", "-q", "-p", "no:cacheprovider"], cwd=w, capture_output=True, text=True).stdout.strip().splitlines()[-1]
        print("baseline:", base)
    finally:
        shutil.rmtree(w, ignore_errors=True)
    res = []
    for l, e in MUTANTS:
        r = run(l, e)
        res.append(r)
        print(f"{r[1]:9} {r[0]:46} {r[2][:60]}", flush=True)
    bad = [r for r in res if r[1] != "KILLED"]
    print(f"\n{len(res) - len(bad)}/{len(res)} killed")
    sys.exit(1 if bad else 0)
