"""Mutation harness: every mutant is a deliberate bug; the suite MUST go red on each one.

    python scripts/mutation_check_auditor.py     # exit 1 if any mutant survives (= a behaviour the tests do not pin)

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
TEST_SRC = REPO_ROOT / "tests" / "test_contradiction_auditor.py"
XFAIL = ["test_contradiction_auditor.py::test_gap_exception_clause", "test_contradiction_auditor.py::test_gap_semester_unit"]

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
    ("M12 spelled-out numbers not normalised",      [('t = _NUMW_RE.sub(lambda m: f"{_NUMW[m[1].lower()]} ", t)', "t = t")]),
    ("M13 citation numbers (Điều 15) not stripped", [('t = _CITE.sub(" ", t)', "t = t")]),
    ("M14 entity carries across sentences",         [("def _sentence_atoms(sent: str, block: str | None) -> list[Atom]:\n    cond, rows, last = block, [], GENERIC_SV",
                                                      "_LAST = [GENERIC_SV]\ndef _sentence_atoms(sent: str, block: str | None) -> list[Atom]:\n    cond, rows, last = block, [], _LAST[0]"),
                                                     ("        last = ent or last\n", "        last = ent or last\n        _LAST[0] = last\n")]),
    ("M15 'Được/Không…' accepted as a person name", [("and m[1].lower() not in _NOT_A_NAME):", "):")]),
    ("M16 'có' alone makes a FACT (no SV subject)", [("bool(_WEAK.search(a.text) and _SUBJ.search(a.text))", "bool(_WEAK.search(a.text))")]),
    ("M17 negation ignored when reading outcome",   [("return name, bool(_NEG.search(p[:m.start()]))", "return name, False")]),
    ("M18 outcome not inherited inside a sentence", [("shared = next((r[3] for r in rows if r[3]), None) if len(outs) == 1 else None", "shared = None")]),
    ("M19 scoped claim ignores its own bucket",     [("pool = [s for s in cand if s.condition == clm.condition] or [s for s in cand if s.condition is None]", "pool = cand")]),
    ("M20 đạt/đã/tích lũy no longer imply FACT",    [("a.entity.instance or bool(_STRONG.search(a.text))", "a.entity.instance")]),
    ("M21 'phải' no longer a >= cue",               [(r"\bít\s+nhất|\bphải\b", r"\bít\s+nhất")]),
    ("M22 point statement strict, not lenient",     [('return Res(V.SATISFIED_BOUND) if contains(S, clm.value) else Res(V.GROUNDING_CONFLICT, "point_outside")', 'return Res(V.GROUNDING_CONFLICT, "point_outside")')]),
    ("M23 canary stoplist (hệ thống/số/quả) gone",  [(r"(?!thống\b|số\b|quả\b|\d)", r"(?!\d)")]),
    ("M24 header-only line detection removed",      [("if (h := _header_scope(line)):", "if False:")]),
    ("M25 outcome check disabled",                  [("if not _outcomes_comparable(src.outcome, clm.outcome):", "if False:")]),
    ("M26 sanction compared with anything",         [("    return (a or b) not in _SANCTION", "    return True")]),
    ("M27 unstated consequent never comparable",    [("    return (a or b) not in _SANCTION", "    return False")]),
    ("M28 sanction set empty",                      [('_SANCTION = {"EXPEL"}', "_SANCTION = set()")]),
    ("M29 query_condition=None matches general bucket", [("if query_condition is not None and query_condition in agg:", "if query_condition in agg:")]),
    ("M30 canary needs a lead word again",          [(r"^(?:{_LEAD})?hệ", r"^{_LEAD}hệ")]),
]


def run(label, edits):
    w = pathlib.Path(tempfile.mkdtemp())
    try:
        shutil.copy(ENGINE_SRC, w / "contradiction_auditor.py")
        shutil.copy(TEST_SRC, w / "test_contradiction_auditor.py")
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
        shutil.copy(TEST_SRC, w / "test_contradiction_auditor.py")
        base = subprocess.run([sys.executable, "-m", "pytest", "-q", "-p", "no:cacheprovider"], cwd=w, capture_output=True, text=True).stdout.strip().splitlines()[-1]
        print("baseline:", base)
    finally:
        shutil.rmtree(w, ignore_errors=True)
    res = [run(l, e) for l, e in MUTANTS]
    for label, status, detail in res:
        print(f"{status:9} {label:46} {detail[:60]}")
    bad = [r for r in res if r[1] != "KILLED"]
    print(f"\n{len(res) - len(bad)}/{len(res)} killed")
    sys.exit(1 if bad else 0)
