"""
rat.engine.contradiction_auditor — Unified Contradiction Auditor & Monotonic Step Integrity Guard.

Integrates:
1. Exact Claude Reference Engine (normalize -> is_telemetry -> atoms -> extract -> match -> audit -> gate)
2. CI Invariant checker & Unknown condition counter
3. query condition inference (infer_query_condition)
4. Full backward-compatibility adapter for ContradictionAuditor, ContradictionType, AuditFinding, ContradictionReport
"""
from __future__ import annotations

import logging
import re
import time
from dataclasses import asdict, dataclass, field
from enum import Enum, auto
from math import inf
from typing import Any, Dict, List, NamedTuple, Optional, Sequence, Set, Tuple

logger = logging.getLogger("rat.engine.contradiction_auditor")


# ───────────────────────── types ─────────────────────────
class V(Enum):
    GROUNDING_CONFLICT = auto()   # claim contradicts the source
    SATISFIED_BOUND = auto()      # claim consistent with the source bound
    DISJOINT_ENTITIES = auto()    # different subjects: no intervention
    NOT_COMPARABLE = auto()       # same subject, different metric/unit/outcome/period, or unparsed
    AMBIGUOUS_SCOPE = auto()      # unscoped claim; scoped sources disagree about it
    OUT_OF_COVERAGE = auto()      # claim's programme is unknown to the KB: unverified
    SCOPE_ELIDED = auto()         # correct only under the query's programme; answer does not say so


class Role(Enum):
    NORM = auto()   # a rule / bound
    FACT = auto()   # an instance value (a student achieved X)


class Res(NamedTuple):
    verdict: V
    reason: str = ""


@dataclass(frozen=True)
class Ent:
    id: str
    instance: bool
    classes: frozenset


GENERIC_SV = Ent("SV", False, frozenset({"SV"}))


@dataclass(frozen=True)
class Tup:
    entity: Ent
    metric: str
    op: str                 # >=, <=, ==, <, >
    value: float            # normalised to the base unit
    unit: str
    scope: tuple = (-inf, inf)          # temporal scope
    role: Role = Role.NORM
    outcome: str | None = None          # consequent: EXPEL / PASS / GRADUATE
    verdict: bool | None = None         # FACT only: answer asserts (True) / denies (False) the outcome
    condition: str | None = None        # programme: full-time / part-time / "UNKNOWN:<x>"
    text: str = ""


@dataclass(frozen=True)
class Atom:
    text: str
    condition: str | None
    entity: Ent
    outcome: str | None
    neg: bool


@dataclass(frozen=True)
class Finding:
    text: str
    tup: Tup | None
    result: Res


# ───────────────────────── lexicons ─────────────────────────
# Domain lexicon: every programme the school has (NOT derived from the KB).
PROGRAM = {
    "chính quy": "full-time", "vừa làm vừa học": "part-time", "vừa học vừa làm": "part-time",
    "vlvh": "part-time", "sau đại học": "postgrad", "thạc sĩ": "postgrad", "tiến sĩ": "postgrad",
    "liên thông": "transfer", "từ xa": "distance",
}
_HE = r"hệ\s+(?:" + "|".join(sorted(map(re.escape, PROGRAM), key=len, reverse=True)) + r")\b"
_LEAD = r"(?:đối\s+với|với|ở|còn|riêng|trong\s+khi)\s+(?:đối\s+với\s+)?"
_CUE = re.compile(rf"^(?:{_LEAD})?(?P<h>{_HE})\s*[,:]?\s*", re.I)
# canary: detection only. 'hệ <unknown>' -> UNKNOWN:<x>. Stoplist = other senses of "hệ" (finite, stable).
_CANARY = re.compile(
    rf"^(?:{_LEAD})?hệ\s+(?!thống\b|số\b|quả\b|\d)(?P<x>[^,:;\n\d]+?)"
    r"(?:\s*:\s*|\s*$|\s+(?=(?:tối|ít|không|phải|cần|được|có|là)\b))", re.I)
_MID = re.compile(rf"(?:của|ở|cho|đối\s+với)\s+(?P<h>{_HE})", re.I)

_KEYMETRIC = [("toeic", re.compile(r"toeic", re.I), "score"),
              ("ielts", re.compile(r"ielts", re.I), "score"),
              ("cpa", re.compile(r"\b(?:cpa|gpa)\b", re.I), "point")]
_UNITMAP = {"năm": ("duration", "year", 1), "tháng": ("duration", "year", 12),
            "học kỳ": ("duration", "semester", 1), "tín chỉ": ("credits", "credit", 1)}

_OUTCOMES = [("EXPEL", re.compile(r"buộc\s+thôi\s+học|thôi\s+học|đình\s+chỉ\s+học", re.I)),
             ("PASS", re.compile(r"đạt\s+chuẩn|đạt\s+yêu\s+cầu|đủ\s+điều\s+kiện|đủ\s+chuẩn|đáp\s+ứng", re.I)),
             ("GRADUATE", re.compile(r"tốt\s+nghiệp", re.I))]
_NEG = re.compile(r"\b(?:không|chưa|chẳng)\b", re.I)
_SUBJ = re.compile(r"\b(?:SV|[Ss]inh viên)\b")
# achievement verbs: STRONG ones imply an individual even when the subject is elided ("Không đạt TOEIC 550…");
# "có" is ambiguous ("Hệ X có thời gian…" vs "SV có CPA…") so it needs an explicit SV subject.
_STRONG = re.compile(r"\b(?:đạt|đã|đang|hoàn thành|tích lũy)\b", re.I)
_WEAK = re.compile(r"\bcó\b", re.I)
_NAMED = re.compile(r"^(?:(?:SV|[Ss]inh viên)\s+)?(\w+)\s+(?:đạt|được|có|bị|đã|học|hoàn thành|tích lũy)\b")

_CUES = [(re.compile(p, re.I), op) for p, op in [
    (r"không\s+(?:thấp|ít)\s+hơn|không\s+dưới|\btối\s+thiểu|\bít\s+nhất|\bphải\b"
     r"|\bcần(?:\s+(?:đạt|có))?\b|yêu\s+cầu(?:\s+(?:đạt|có))?|≥|>=", ">="),
    (r"không\s+(?:quá|vượt\s+quá|cao\s+hơn)|\btối\s+đa|nhiều\s+nhất|≤|<=", "<="),
    (r"\bdưới|thấp\s+hơn|<", "<"),
    (r"\btrên|vượt\s+quá|cao\s+hơn|>", ">"),
]]
_TRAIL = re.compile(r"^\s*(?:\S+\s+)?trở\s+(lên|xuống)", re.I)
_NUM = re.compile(r"(?<![\w.,])(?P<v>\d+(?:[.,]\d+)?)(?:\s*(?P<u>năm|tháng|học kỳ|tín chỉ)\b)?", re.I)

# telemetry
_HEAD = re.compile(r"^\s*(?:\[[A-Z_]+\]|(?:Executed|Running|Retrieved|Latency|Trace|Step\s*\d+)\b)", re.I)
_TUNIT = re.compile(r"\b\d+(?:[.,]\d+)?\s*(?:tokens?|ms|chunks?|docs?)\b", re.I)
_DOMAIN = re.compile(r"CPA|GPA|TOEIC|IELTS|tín chỉ|học kỳ|\bnăm\b|tháng|thôi học|tốt nghiệp|học phí|điểm|đình chỉ", re.I)

# structure
_SENT = re.compile(r"(?<=[.!?])\s+")
# comma splits only before whitespace so decimal commas ("1,2") survive
_COORD = re.compile(r"\s+(?:và|hoặc|đồng thời)\s+|[,;]\s+|;|\s+(?=(?:còn|riêng|trong khi)\s+hệ\b)", re.I)
_BUL = re.compile(r"^\s*(?:[-*•]\s|\d{1,2}[.)]\s)")
_ARROW = re.compile(r"\s*(?:=>|⇒|→|->)\s*")
_CITE = re.compile(r"\b(?:Điều|Khoản|Mục|Chương)\s+\d+\b", re.I)
_STEP_PREFIX = re.compile(r"\b(?:Bước|Step)\s+\d+[:.]?\s*", re.I)
_NUMW = {"một": 1, "hai": 2, "ba": 3, "bốn": 4, "năm": 5, "sáu": 6, "bảy": 7, "tám": 8, "chín": 9, "mười": 10}
_NUMW_RE = re.compile(r"\b(" + "|".join(_NUMW) + r")\s+(?=(?:năm|tháng|học kỳ|tín chỉ)\b)", re.I)


# ───────────────────────── stage 0-1: normalise + telemetry ─────────────────────────
def normalize(t: str) -> str:
    t = _ARROW.sub(" nên ", t)
    t = _CITE.sub(" ", t)
    t = _STEP_PREFIX.sub(" ", t)
    t = re.sub(r"\bchỉ\s+(đạt|được|có)\b", r"\1", t, flags=re.I)
    t = _NUMW_RE.sub(lambda m: f"{_NUMW[m[1].lower()]} ", t)
    return re.sub(r"[ \t]+", " ", t)


def is_telemetry(s: str) -> bool:
    """Operational head/unit AND no domain lexeme. A domain lexeme always keeps the line."""
    return bool((_HEAD.match(s) or _TUNIT.search(s)) and not _DOMAIN.search(s))


# ───────────────────────── stage 2: atoms ─────────────────────────
def _cid(raw: str) -> str:
    return PROGRAM[re.sub(r"\s+", " ", re.sub(r"^hệ\s+", "", raw.strip().lower()))]


def _take_scope(p: str, cond: str | None):
    """Consume a leading programme cue. Returns (condition, remainder)."""
    if m := _CUE.match(p):
        return _cid(m["h"]), p[m.end():].strip()
    if m := _CANARY.match(p):
        return "UNKNOWN:" + re.sub(r"\s+", " ", m["x"].strip().lower()), p[m.end():].strip()
    return cond, p


def _header_scope(line: str) -> str | None:
    c, rest = _take_scope(line.strip(), None)
    return c if c and not rest else None


_NOT_A_NAME = {"được", "bị", "có", "đã", "đang", "học", "đạt", "hoàn", "tích", "không", "chưa", "chẳng",
               "sẽ", "cần", "phải", "nếu", "khi", "thì", "mỗi", "mọi", "các", "những", "một"}


def _named(p: str) -> Ent | None:
    """Capitalised token + achievement verb. Sentence-initial function words ('Được học…', 'Không đạt…') are not names."""
    m = _NAMED.match(p)
    if (m and m[1][0].isupper() and not (m[1].isupper() and len(m[1]) > 1)
            and m[1].lower() not in _NOT_A_NAME):
        return Ent(m[1].lower(), True, frozenset({"SV"}))   # assumption: a named person here is a student
    return None


def _outcome(p: str):
    for name, rx in _OUTCOMES:
        if m := rx.search(p):
            return name, bool(_NEG.search(p[:m.start()]))
    return None


def _sentence_atoms(sent: str, block: str | None) -> list[Atom]:
    cond, rows, last = block, [], GENERIC_SV
    for p in _COORD.split(sent):
        if not p or not p.strip():
            continue
        cond, p = _take_scope(p.strip(), cond)       # inline cue persists for the rest of the sentence
        if not p:
            continue
        local = _cid(mm["h"]) if (mm := _MID.search(p)) else cond
        ent = _named(p)
        last = ent or last
        rows.append((p, local, ent or last, _outcome(p)))
    outs = {r[3][0] for r in rows if r[3]}
    shared = next((r[3] for r in rows if r[3]), None) if len(outs) == 1 else None
    return [Atom(p, c, e, (o or shared)[0] if (o or shared) else None, (o or shared)[1] if (o or shared) else False)
            for p, c, e, o in rows if _NUM.search(p)]


def atoms(text: str) -> list[Atom]:
    out, block, in_list = [], None, False
    for raw in normalize(text).split("\n"):
        if not raw.strip():
            block, in_list = None, False
            continue
        is_b, line = bool(_BUL.match(raw)), _BUL.sub("", raw)
        if block and in_list and not is_b:
            block = None                              # a non-bullet line after a list closes the header block
        if (h := _header_scope(line)):
            block, in_list = h, False
            continue
        in_list = in_list or is_b
        for sent in _SENT.split(line):
            if sent.strip() and not is_telemetry(sent):
                out += _sentence_atoms(sent, block)
    return out


# ───────────────────────── stage 3: slot extraction ─────────────────────────
def _find_op(pre: str, post: str) -> str:
    if m := _TRAIL.match(post):
        return ">=" if m[1].lower() == "lên" else "<="
    hits = [(mm.end(), -i, op) for i, (rx, op) in enumerate(_CUES) for mm in rx.finditer(pre)]
    return max(hits)[2] if hits else "=="             # nearest cue wins; tie -> earlier (more specific) cue


def extract(a: Atom) -> Tup | str:
    nums = list(_NUM.finditer(a.text))
    if len(nums) != 1:
        return "multi_number" if nums else "no_number"
    n = nums[0]
    v, u = float(n["v"].replace(",", ".")), (n["u"] or "").lower()
    metric = unit = None
    for mid, rx, base in _KEYMETRIC:
        if rx.search(a.text):
            metric, unit = mid, base
            break
    if metric is None and u:
        metric, unit, div = _UNITMAP[u]
        v = round(v / div, 6)
    if metric is None:
        return "no_metric"
    op = _find_op(a.text[:n.start()], a.text[n.end():])
    fact = op == "==" and (a.entity.instance or bool(_STRONG.search(a.text))
                           or bool(_WEAK.search(a.text) and _SUBJ.search(a.text)))
    return Tup(a.entity, metric, op, v, unit, role=Role.FACT if fact else Role.NORM, outcome=a.outcome,
               verdict=(not a.neg) if (fact and a.outcome) else None, condition=a.condition, text=a.text)


def extract_all(text: str):
    tups, unparsed = [], []
    for a in atoms(text):
        r = extract(a)
        (unparsed if isinstance(r, str) else tups).append((a.text, r) if isinstance(r, str) else r)
    return tups, unparsed


def build_index(source_text: str) -> dict:
    idx: dict = {}
    for t in extract_all(source_text)[0]:
        idx.setdefault((t.metric, t.unit), []).append(t)
    return idx


# ───────────────────────── stage 4: interval matcher ─────────────────────────
def iv(op: str, v: float):
    return {">=": (v, inf, True, False), ">": (v, inf, False, False), "<=": (-inf, v, False, True),
            "<": (-inf, v, False, False), "==": (v, v, True, True)}[op]


def contains(I, x: float) -> bool:
    lo, hi, lc, hc = I
    return (x > lo or (lc and x == lo)) and (x < hi or (hc and x == hi))


def subset(C, S) -> bool:
    (cl, ch, clc, chc), (sl, sh, slc, shc) = C, S
    return (cl > sl or (cl == sl and (slc or not clc))) and (ch < sh or (ch == sh and (shc or not chc)))


def applies(a: Ent, b: Ent) -> bool:
    """Does a statement about `a` govern `b`? Instances govern only themselves; a class governs its members."""
    return a.id == b.id or (not a.instance and a.id in b.classes)


_SANCTION = {"EXPEL"}


def _outcomes_comparable(a: str | None, b: str | None) -> bool:
    """A sanction (EXPEL) is only comparable with the same sanction. Requirement-type outcomes (PASS/GRADUATE)
    and an unstated consequent (a bare 'yêu cầu tối thiểu …') compare with each other."""
    if a == b:
        return True
    if a and b:
        return False
    return (a or b) not in _SANCTION


def match(src: Tup, clm: Tup) -> Res:
    if not applies(src.entity, clm.entity):
        return Res(V.DISJOINT_ENTITIES)
    if (src.metric, src.unit) != (clm.metric, clm.unit):
        return Res(V.NOT_COMPARABLE, "metric_or_unit")
    if not _outcomes_comparable(src.outcome, clm.outcome):
        return Res(V.NOT_COMPARABLE, "outcome")
    if not (src.scope[0] <= clm.scope[1] and clm.scope[0] <= src.scope[1]):
        return Res(V.NOT_COMPARABLE, "temporal")
    S = iv(src.op, src.value)
    if src.role is Role.FACT:
        if clm.role is Role.FACT:
            return Res(V.SATISFIED_BOUND) if clm.value == src.value else Res(V.GROUNDING_CONFLICT, "fact_value")
        return Res(V.NOT_COMPARABLE, "fact_source")
    if clm.role is Role.FACT:                         # point value vs bound
        holds = contains(S, clm.value)
        if clm.verdict is None:
            return Res(V.SATISFIED_BOUND) if holds else Res(V.NOT_COMPARABLE, "fact_outside_bound_no_outcome")
        return Res(V.SATISFIED_BOUND) if holds == clm.verdict else Res(V.GROUNDING_CONFLICT, "fact_vs_bound")
    C = iv(clm.op, clm.value)                         # rule vs rule
    if C == S:
        return Res(V.SATISFIED_BOUND)
    if clm.op == "==":                                # "thời gian là X năm": lenient, X must lie inside the bound
        return Res(V.SATISFIED_BOUND) if contains(S, clm.value) else Res(V.GROUNDING_CONFLICT, "point_outside")
    if C[:2] == S[:2]:
        return Res(V.GROUNDING_CONFLICT, "boundary_only")
    return Res(V.GROUNDING_CONFLICT, "looser" if not subset(C, S) else "tighter")


# ───────────────────────── stage 5: audit (bucketed by condition) ─────────────────────────
def _bucket(rs: list[Res]) -> Res:
    """Inside one condition bucket: pessimistic."""
    for want in (V.GROUNDING_CONFLICT, V.SATISFIED_BOUND):
        for r in rs:
            if r.verdict is want:
                return r
    if rs and all(r.verdict is V.DISJOINT_ENTITIES for r in rs):
        return Res(V.DISJOINT_ENTITIES)
    return Res(V.NOT_COMPARABLE, "no_comparable_source")


def audit(clm: Tup, kb: dict, query_condition: str | None = None) -> Res:
    cand = kb.get((clm.metric, clm.unit), [])
    if not cand:
        return Res(V.NOT_COMPARABLE, "no_source_for_metric")
    if clm.condition and clm.condition.startswith("UNKNOWN:"):
        return Res(V.OUT_OF_COVERAGE, clm.condition)
    if clm.condition:                                 # scoped claim: specific bucket, else general rules
        pool = [s for s in cand if s.condition == clm.condition] or [s for s in cand if s.condition is None]
        if not pool:
            return Res(V.OUT_OF_COVERAGE, f"kb_has_no:{clm.condition}")
        return _bucket([match(s, clm) for s in pool])
    buckets: dict = {}
    for s in cand:
        buckets.setdefault(s.condition, []).append(match(s, clm))
    agg = {c: _bucket(rs) for c, rs in buckets.items()}
    kinds = {r.verdict for r in agg.values() if r.verdict in (V.SATISFIED_BOUND, V.GROUNDING_CONFLICT)}
    if not kinds:
        return _bucket(list(agg.values()))
    if len(kinds) == 1:
        return next(r for r in agg.values() if r.verdict in kinds)
    if query_condition is not None and query_condition in agg:   # None = "no query context", NOT the general bucket
        # query context may only TIGHTEN, never relax
        q = agg[query_condition]
        return Res(V.GROUNDING_CONFLICT, "query_scope_conflict") if q.verdict is V.GROUNDING_CONFLICT \
            else Res(V.SCOPE_ELIDED, query_condition)
    return Res(V.AMBIGUOUS_SCOPE, ",".join(f"{c}:{r.verdict.name}" for c, r in agg.items() if c))


def audit_text(answer: str, kb: dict, query_condition: str | None = None) -> list[Finding]:
    tups, unparsed = extract_all(answer)
    return ([Finding(t.text, t, audit(t, kb, query_condition)) for t in tups]
            + [Finding(txt, None, Res(V.NOT_COMPARABLE, f"unparsed:{why}")) for txt, why in unparsed])


def gate(findings: list[Finding]) -> str:
    vs = {f.result.verdict for f in findings}
    if V.GROUNDING_CONFLICT in vs:
        return "BLOCK"
    if V.AMBIGUOUS_SCOPE in vs:
        return "REGENERATE"
    if vs & {V.OUT_OF_COVERAGE, V.SCOPE_ELIDED}:
        return "ANNOTATE"
    return "PASS"


# ───────────────────────── Section 6 additions ─────────────────────────
def infer_query_condition(query: str | None) -> str | None:
    """Find programmes matching _HE in query. Returns PROGRAM[...] if exactly one, else None."""
    if not query:
        return None
    matches = set()
    for m in re.finditer(_HE, query, re.I):
        prog_raw = re.sub(r"^hệ\s+", "", m.group(0).strip().lower())
        prog_raw = re.sub(r"\s+", " ", prog_raw)
        if prog_raw in PROGRAM:
            matches.add(PROGRAM[prog_raw])
    return matches.pop() if len(matches) == 1 else None


def check_kb_ci_invariant(kb: dict) -> list[str]:
    """CI check: every condition in KB (except UNKNOWN:<x>) must belong to set(PROGRAM.values())."""
    valid = set(PROGRAM.values())
    violations = set()
    for tups in kb.values():
        for t in tups:
            if t.condition is not None and not t.condition.startswith("UNKNOWN:"):
                if t.condition not in valid:
                    violations.add(t.condition)
    return sorted(violations)


class UnknownConditionCounter:
    """Tracks frequency of UNKNOWN:<x> scopes and routes frequent ones to manual review queue."""
    def __init__(self, threshold: int = 5):
        self.counts: Dict[str, int] = {}
        self.review_queue: List[str] = []
        self.threshold = threshold

    def record(self, condition: str) -> None:
        if not condition.startswith("UNKNOWN:"):
            return
        tag = condition.split(":", 1)[1]
        self.counts[tag] = self.counts.get(tag, 0) + 1
        if self.counts[tag] >= self.threshold and tag not in self.review_queue:
            self.review_queue.append(tag)


# ───────────────────────── Backward-compatibility layer ─────────────────────────
class ContradictionType(str, Enum):
    GROUNDING_CONFLICT = "grounding_conflict"
    PREMISE_INVERSION = "premise_inversion"
    NUMERIC_COLLISION = "numeric_collision"
    POLICY_VIOLATION = "policy_violation"


@dataclass(frozen=True)
class AuditFinding:
    is_contradiction: bool
    conflict_type: ContradictionType
    step_index: int
    claim: str
    basis: str
    conflicting_source_id: Optional[str] = None
    conflicting_step_index: Optional[int] = None
    severity: str = "blocking"  # "blocking" | "warning"
    explanation: str = ""
    claim_origin: str = "step"  # "step" | "answer"

    def to_dict(self) -> Dict[str, Any]:
        return {
            "is_contradiction": self.is_contradiction,
            "conflict_type": self.conflict_type.value,
            "step_index": self.step_index,
            "claim": self.claim,
            "basis": self.basis,
            "conflicting_source_id": self.conflicting_source_id,
            "conflicting_step_index": self.conflicting_step_index,
            "severity": self.severity,
            "explanation": self.explanation,
            "claim_origin": self.claim_origin,
        }


@dataclass
class ContradictionReport:
    passed: bool
    findings: List[AuditFinding] = field(default_factory=list)
    monotonicity_score: float = 1.0
    audited_steps_count: int = 0
    source_evidences_count: int = 0
    duration_ms: float = 0.0
    coverage_status: str = "checked"  # "checked" | "not_evaluated" | "no_evidences"
    claims_checked_count: int = 0
    operational_events_count: int = 0

    def to_dict(self) -> Dict[str, Any]:
        return {
            "passed": self.passed,
            "findings": [f.to_dict() for f in self.findings],
            "monotonicity_score": round(self.monotonicity_score, 3),
            "audited_steps_count": self.audited_steps_count,
            "source_evidences_count": self.source_evidences_count,
            "duration_ms": round(self.duration_ms, 2),
            "coverage_status": self.coverage_status,
            "claims_checked_count": self.claims_checked_count,
            "operational_events_count": self.operational_events_count,
        }


INVERSION_PAIRS: List[Tuple[str, str, str]] = [
    (
        r"\b(?:được phép|có quyền|đủ điều kiện|hợp lệ)\b",
        r"\b(?:không được phép|bị cấm|không đủ điều kiện|không hợp lệ|từ chối)\b",
        "Quyền / Điều kiện thực hiện (Allowed vs Disallowed)",
    ),
    (
        r"\b(?:bắt buộc|phải|tiên quyết)\b",
        r"\b(?:không bắt buộc|tùy chọn|không cần|miễn trừ)\b",
        "Tính bắt buộc (Mandatory vs Optional)",
    ),
    (
        r"\b(?:bị đình chỉ|đình chỉ liên đới|bị hủy kết quả)\b",
        r"\b(?:không làm đình chỉ|không bị đình chỉ|độc lập|không ảnh hưởng)\b",
        "Chế tài đình chỉ (Suspension vs Independence)",
    ),
    (
        r"\b(?:được hoàn|hoàn trả học phí)\b",
        r"\b(?:không được hoàn|không hoàn trả|mất học phí)\b",
        "Hoàn phí học phần (Refund vs Non-refund)",
    ),
    (
        r"\b(?:bị cảnh báo|cảnh báo học vụ)\b",
        r"\b(?:không bị cảnh báo|thoát cảnh báo|an toàn học vụ)\b",
        "Cảnh báo học vụ (Academic probation)",
    ),
]


def extract_topic_polarity(text: str, pos_raw: str, neg_raw: str) -> Optional[str]:
    neg_re = re.compile(neg_raw, re.IGNORECASE)
    if neg_re.search(text):
        return "negative"
    guard = r"(?<!không\s)(?<!chưa\s)(?<!chẳng\s)(?<!không\slàm\s)(?<!không\sbị\s)(?<!không\sđược\s)"
    pos_re = re.compile(f"{guard}{pos_raw}", re.IGNORECASE)
    if pos_re.search(text):
        return "positive"
    return None


def is_operational_event(text: str) -> bool:
    return is_telemetry(text)


def is_operational_step(text: str) -> bool:
    if is_telemetry(text):
        return True
    t = text.strip().lower()
    if re.match(r"^executed\s+(?:cot|planner|strategy|worker|reasoning)", t):
        return True
    if "generated tokens" in t:
        return True
    if "underlying_requests" in t or "dispatched to solver" in t or "dispatched" in t:
        return True
    if t.startswith("telemetry:") or "latency=" in t:
        return True
    return False

class ContradictionAuditor:
    """
    Backward-compatible auditor facade integrating the Interval Tuple Engine
    with reasoning step monotonicity and public answer claims auditing.
    """
    def __init__(self, strict_numeric: bool = True) -> None:
        self.strict_numeric = strict_numeric

    def audit_trace(
        self,
        steps: Sequence[str],
        source_evidences: Optional[Sequence[Any]] = None,
        answer: Optional[str] = None,
        query: Optional[str] = None,
    ) -> ContradictionReport:
        t0 = time.time()
        findings: List[AuditFinding] = []
        evidences = list(source_evidences or [])

        # 1. Build authoritative SourceEvidence text & index
        source_text_parts = []
        ev_id_map: Dict[str, str] = {}
        for ev in evidences:
            ev_id = getattr(ev, "source_id", "") or (ev.get("source_id", "") if isinstance(ev, dict) else "")
            excerpt = getattr(ev, "excerpt", "") or (ev.get("excerpt", "") if isinstance(ev, dict) else "")
            if excerpt:
                source_text_parts.append(excerpt)
                ev_id_map[excerpt] = ev_id

        full_source_text = "\n".join(source_text_parts)
        kb = build_index(full_source_text) if full_source_text else {}
        query_cond = infer_query_condition(query)

        # 2. Filter steps into operational events vs verifiable step claims
        claims_to_audit: List[Tuple[int, str, str]] = []
        operational_events_count = 0
        for s_idx, s in enumerate(steps):
            sc = s.strip()
            if not sc:
                continue
            if is_operational_step(sc):
                operational_events_count += 1
            else:
                claims_to_audit.append((s_idx, sc, "step"))

        if answer:
            # We split answer by sentences while preserving order
            for a_idx, sent in enumerate(re.split(r"(?<=[.!?\n])\s+", answer)):
                sc = sent.strip()
                if sc and not is_telemetry(sc):
                    claims_to_audit.append((len(steps) + a_idx, sc, "answer"))

        claims_checked_count = len(claims_to_audit)

        # 3. Grounding audit via interval engine on answer & claims
        if kb:
            # Audit answer as a cohesive text
            if answer:
                ans_findings = audit_text(answer, kb, query_condition=query_cond)
                for f in ans_findings:
                    if f.result.verdict is V.GROUNDING_CONFLICT:
                        # Find corresponding source_id if possible
                        matched_ev_id = None
                        if f.tup:
                            cand = kb.get((f.tup.metric, f.tup.unit), [])
                            if cand:
                                for exc_text, eid in ev_id_map.items():
                                    if cand[0].text in exc_text:
                                        matched_ev_id = eid
                                        break
                        findings.append(AuditFinding(
                            is_contradiction=True,
                            conflict_type=ContradictionType.NUMERIC_COLLISION if f.tup and f.tup.metric in ("toeic", "cpa", "duration", "credits") else ContradictionType.GROUNDING_CONFLICT,
                            step_index=len(steps),
                            claim=f.text,
                            basis=f.result.reason,
                            conflicting_source_id=matched_ev_id or (evidences[0].source_id if evidences and hasattr(evidences[0], 'source_id') else None),
                            severity="blocking",
                            explanation=f"Mâu thuẫn quy chuẩn [{f.result.reason}]: {f.text}",
                            claim_origin="answer",
                        ))

            # Audit step claims against KB
            for c_idx, c_text, origin in claims_to_audit:
                if origin == "step":
                    step_findings = audit_text(c_text, kb, query_condition=query_cond)
                    for f in step_findings:
                        if f.result.verdict is V.GROUNDING_CONFLICT:
                            findings.append(AuditFinding(
                                is_contradiction=True,
                                conflict_type=ContradictionType.NUMERIC_COLLISION if f.tup and f.tup.metric in ("toeic", "cpa", "duration", "credits") else ContradictionType.GROUNDING_CONFLICT,
                                step_index=c_idx,
                                claim=f.text,
                                basis=f.result.reason,
                                severity="blocking",
                                explanation=f"Bước suy luận {c_idx+1} mâu thuẫn quy chuẩn [{f.result.reason}]: {f.text}",
                                claim_origin="step",
                            ))

        # 4. Inversion / Polarity Grounding check against each evidence excerpt
        for c_idx, claim_text, origin in claims_to_audit:
            for ev in evidences:
                ev_id = getattr(ev, "source_id", "") or (ev.get("source_id", "") if isinstance(ev, dict) else "")
                excerpt = getattr(ev, "excerpt", "") or (ev.get("excerpt", "") if isinstance(ev, dict) else "")
                if not excerpt:
                    continue
                # Non-numeric polarity inversion check
                target_label = "Nội dung câu trả lời" if origin == "answer" else f"Bước suy luận {c_idx + 1}"
                for pos_raw, neg_raw, desc in INVERSION_PAIRS:
                    pol_src = extract_topic_polarity(excerpt, pos_raw, neg_raw)
                    pol_clm = extract_topic_polarity(claim_text, pos_raw, neg_raw)
                    if pol_src and pol_clm and pol_src != pol_clm:
                        findings.append(AuditFinding(
                            is_contradiction=True,
                            conflict_type=ContradictionType.GROUNDING_CONFLICT,
                            step_index=c_idx,
                            claim=claim_text,
                            basis=excerpt,
                            conflicting_source_id=ev_id,
                            severity="blocking",
                            explanation=f"{target_label} trái ngược nguồn [{ev_id}]: {desc}",
                            claim_origin=origin,
                        ))

        # 5. Premise inversion & step-to-step numeric check between reasoning steps
        step_claims = [(idx, text) for idx, text, origin in claims_to_audit if origin == "step"]
        for j in range(len(step_claims)):
            idx_j, text_j = step_claims[j]
            for i in range(j):
                idx_i, text_i = step_claims[i]
                # Polarity inversion between steps
                for pos_raw, neg_raw, desc in INVERSION_PAIRS:
                    pol_i = extract_topic_polarity(text_i, pos_raw, neg_raw)
                    pol_j = extract_topic_polarity(text_j, pos_raw, neg_raw)
                    if pol_i and pol_j and pol_i != pol_j:
                        findings.append(AuditFinding(
                            is_contradiction=True,
                            conflict_type=ContradictionType.PREMISE_INVERSION,
                            step_index=idx_j,
                            claim=text_j,
                            basis=text_i,
                            conflicting_step_index=idx_i,
                            severity="blocking",
                            explanation=f"Bước {idx_j + 1} đảo ngược tiền đề tại Bước {idx_i + 1}: {desc}",
                            claim_origin="step",
                        ))
                # Numeric step vs step collision via interval match
                tups_i, _ = extract_all(text_i)
                tups_j, _ = extract_all(text_j)
                for ti in tups_i:
                    for tj in tups_j:
                        res = match(ti, tj)
                        if res.verdict is V.GROUNDING_CONFLICT:
                            findings.append(AuditFinding(
                                is_contradiction=True,
                                conflict_type=ContradictionType.NUMERIC_COLLISION,
                                step_index=idx_j,
                                claim=text_j,
                                basis=text_i,
                                conflicting_step_index=idx_i,
                                severity="blocking",
                                explanation=f"Bước {idx_j + 1} xung đột số liệu với Bước {idx_i + 1} [{res.reason}]",
                                claim_origin="step",
                            ))

        dur_ms = (time.time() - t0) * 1000.0
        total_items = max(1, len(steps) + (1 if answer else 0))
        score = 1.0 if not findings else max(0.0, 1.0 - (len(findings) / total_items))

        # Determine coverage status
        if not evidences:
            coverage = "no_evidences"
        elif claims_checked_count == 0:
            coverage = "not_evaluated"
        else:
            # Check if any verifiable topic/metric matched between claims and evidences
            any_matched = False
            for _, claim_text, _ in claims_to_audit:
                c_tups, _ = extract_all(claim_text)
                if any((t.metric, t.unit) in kb for t in c_tups):
                    any_matched = True
                    break
                for ev in evidences:
                    exc = getattr(ev, "excerpt", "") or (ev.get("excerpt", "") if isinstance(ev, dict) else "")
                    topics = ["đình chỉ", "thạc sĩ", "song bằng", "đại học", "học vượt",
                              "tín chỉ", "toeic", "tiếng anh", "cảnh báo học vụ", "rút môn",
                              "học phí", "khóa luận", "rèn luyện", "học bổng", "tốt nghiệp", "chuẩn đầu ra"]
                    if any(top in claim_text.lower() and top in exc.lower() for top in topics):
                        any_matched = True
                        break
                if any_matched:
                    break
            coverage = "checked" if any_matched else "not_evaluated"

        return ContradictionReport(
            passed=len(findings) == 0,
            findings=findings,
            monotonicity_score=score,
            audited_steps_count=len(steps),
            source_evidences_count=len(evidences),
            duration_ms=dur_ms,
            coverage_status=coverage,
            claims_checked_count=claims_checked_count,
            operational_events_count=operational_events_count,
        )
