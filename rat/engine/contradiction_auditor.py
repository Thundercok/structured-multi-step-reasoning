"""Contradiction auditor: CPU-only, no LLM verifier.

normalize (offset-preserving) -> telemetry gate -> atoms (condition / entity / outcome / spans)
-> extract (Tup) -> audit (per-condition buckets over interval semantics) -> report (annotations + coverage).
"""
from __future__ import annotations

import re
import time
import unicodedata
from dataclasses import dataclass, replace
from enum import Enum, auto
from math import inf
from typing import NamedTuple


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
    start: int = -1                     # clause span in the ORIGINAL answer text
    end: int = -1
    scope_src: str | None = None        # HEADER (line above) | INLINE (cue inside the clause) | None
    scope_start: int = -1               # span of the header line / the inline cue
    scope_end: int = -1
    per_semester: bool = False


@dataclass(frozen=True)
class Finding:
    text: str
    tup: Tup | None
    result: Res
    span: tuple = (-1, -1)
    scope_src: str | None = None
    scope_span: tuple = (-1, -1)


@dataclass(frozen=True)
class Annotation:
    kind: str            # verdict name
    reason: str
    start: int
    end: int
    anchor: str          # HEADER: one label on the header line / CLAUSE: label on the clause


@dataclass(frozen=True)
class AuditReport:
    findings: list
    annotations: list
    summary: dict
    gate: str


# ───────────────────────── lexicons ─────────────────────────
# Domain lexicon: every programme the school has (NOT derived from the KB).
PROGRAM = {
    "chính quy": "full-time", "vừa làm vừa học": "part-time", "vừa học vừa làm": "part-time",
    "vlvh": "part-time", "sau đại học": "postgrad", "thạc sĩ": "postgrad", "tiến sĩ": "postgrad",
    "liên thông": "transfer", "từ xa": "distance",
}
_PROG_ALT = "|".join(sorted(map(re.escape, PROGRAM), key=len, reverse=True))
_HE = rf"hệ\s+(?:{_PROG_ALT})\b"
_LEAD = r"(?:đối\s+với|với|ở|còn|riêng|trong\s+khi)\s+(?:đối\s+với\s+)?"
# words that may legitimately follow a programme name; anything else means the name is longer than the lexicon knows
_PRED = (r"(?:học|đào\s+tạo|có|được|phải|cần|yêu\s+cầu|tối|ít|không|là|thì|sẽ|bắt\s+buộc|tốt\s+nghiệp|thời\s+gian"
         r"|quy\s+định|cho\s+phép|kéo\s+dài|hoàn\s+thành|đạt|tích\s+lũy|sinh\s+viên|SV|chỉ|mới|vẫn|đã|nếu|khi|bị|xét"
         r"|nợ|bảo\s+lưu|dưới|trên|từ|đủ|chuẩn|cpa|gpa|toeic|ielts|mức|điểm|số|tín\s+chỉ|năm|tháng|học\s+kỳ)")
_CUE = re.compile(rf"^(?:{_LEAD})?(?P<h>{_HE})\s*[,:]?\s*", re.I)
_AFTER_PROG = re.compile(rf"^\s*(?:$|[,:;)]|\d|[<>≤≥=]|{_PRED}\b)", re.I)
_EXT = re.compile(rf"(?P<w>(?:(?!{_PRED}\b)[^\s,:;()\d]+\s+){{0,3}}(?!{_PRED}\b)[^\s,:;()\d]+)", re.I)
# canary: detection only. 'hệ <unknown>' -> UNKNOWN:<x>. Stoplist = other senses of \"hệ\" (finite, stable);
# a digit is a programme name only when followed by năm/học kỳ (\"hệ 5 năm\"), else it is a grading scale (\"hệ 4\").
_CANARY = re.compile(
    rf"^(?:{_LEAD})?hệ\s+(?!thống\b|số\b|quả\b|\d+(?:[.,]\d+)?(?![.,]?\d)(?!\s*(?:năm|học\s+kỳ)\b))"
    r"(?P<x>\d+(?:[.,]\d+)?\s*(?:năm|học\s+kỳ)\b[^,:;\n\d]*?|[^,:;\n\d]+?)"
    r"(?:\s*:\s*|\s*$|\s+(?=(?:tối|ít|không|phải|cần|được|có|là)\b))", re.I)
_MID = re.compile(rf"(?:của|ở|cho|đối\s+với|\()\s*(?P<h>{_HE})", re.I)

_KEYMETRIC = [("toeic", re.compile(r"toeic", re.I), "score"),
              ("ielts", re.compile(r"ielts", re.I), "score"),
              ("cpa", re.compile(r"\b(?:cpa|gpa)\b", re.I), "point")]
_UNITMAP = {"năm": ("duration", "year", 1), "tháng": ("duration", "year", 12),
            "học kỳ": ("duration", "semester", 1), "tín chỉ": ("credits", "credit", 1)}
_PER = re.compile(r"(?:mỗi|một|/)\s*(?:học\s+kỳ|kỳ)\b", re.I)                       # \"15 tín chỉ mỗi học kỳ\"
# \"phải đăng ký tối thiểu 14 tín chỉ\" is a per-term load even when \"mỗi học kỳ\" is dropped; applied to source AND claim,
# so the two stay comparable. Any total/graduation/exam wording in the same clause cancels it.
_REG = re.compile(r"\bđăng\s+ký\b", re.I)
_TOTAL = re.compile(r"\b(?:tổng|tích\s+lũy|toàn\s+khóa|tốt\s+nghiệp|xét|dự\s+thi|bảo\s+vệ|đồ\s+án|luận)\b", re.I)
_REMAIN = re.compile(r"\bcòn(?:\s+lại)?(?:\s+(?:tối\s+đa|ít\s+nhất|khoảng))?\s*$", re.I)   # \"còn tối đa 1 năm\"

_OUTCOMES = [("EXPEL", re.compile(r"buộc\s+thôi\s+học|thôi\s+học|đình\s+chỉ\s+học", re.I)),
             ("PASS", re.compile(r"đạt\s+chuẩn|đạt\s+yêu\s+cầu|đủ\s+điều\s+kiện|đủ\s+chuẩn|đáp\s+ứng", re.I)),
             ("GRADUATE", re.compile(r"tốt\s+nghiệp", re.I))]
_NEG = re.compile(r"\b(?:không|chưa|chẳng)\b", re.I)
_SUBJ = re.compile(r"\b(?:SV|[Ss]inh viên)\b")
# achievement verbs: STRONG ones imply an individual even when the subject is elided (\"Không đạt TOEIC 550…\");
# \"có\" is ambiguous (\"Hệ X có thời gian…\" vs \"SV có CPA…\") so it needs an explicit SV subject.
_STRONG = re.compile(r"\b(?:đạt|đã|đang|hoàn thành|tích lũy)\b", re.I)
_WEAK = re.compile(r"\bcó\b", re.I)
_NAMED = re.compile(r"^(?:(?:SV|[Ss]inh viên)\s+)?(\w+)\s+(?:đạt|được|có|bị|đã|học|hoàn thành|tích lũy)\b")
_NOT_A_NAME = {"được", "bị", "có", "đã", "đang", "học", "đạt", "hoàn", "tích", "không", "chưa", "chẳng",
               "sẽ", "cần", "phải", "nếu", "khi", "thì", "mỗi", "mọi", "các", "những", "một"}

_CUES = [(re.compile(p, re.I), op) for p, op in [
    (r"không\s+(?:thấp|ít)\s+hơn|không\s+dưới|\btối\s+thiểu|\bít\s+nhất|\bphải\b"
     r"|\bcần(?:\s+(?:đạt|có))?\b|yêu\s+cầu(?:\s+(?:đạt|có))?|≥|>=", ">="),
    (r"không\s+(?:được\s+)?(?:\w+\s+){0,2}?(?:quá|vượt\s+quá|cao\s+hơn)|\btối\s+đa|nhiều\s+nhất|≤|<=", "<="),
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
# comma splits only before whitespace so decimal commas (\"1,2\") survive
_COORD = re.compile(r"\s+(?:và|hoặc|đồng thời)\s+|[,;]\s+|;|\s+(?=(?:còn|riêng|trong khi)\s+hệ\b)", re.I)
_BUL = re.compile(r"^\s*(?:[-*•]\s|\d{1,2}[.)]\s)")

# normalisation steps (each is length-tracked so spans map back to the original answer)
_MD = re.compile(r"\*\*|__|`|^[ \t]*#{1,6}[ \t]*|^[ \t]*>[ \t]?", re.M)
_ARROW = re.compile(r"\s*(?:=>|⇒|→|->)\s*")
_CITE = re.compile(r"\b(?:Điều|Khoản|Mục|Chương)\s+\d+\b", re.I)
_NUMW = {"một": 1, "hai": 2, "ba": 3, "bốn": 4, "năm": 5, "sáu": 6, "bảy": 7, "tám": 8, "chín": 9, "mười": 10}
_NUMW_RE = re.compile(r"\b(" + "|".join(_NUMW) + r")\s+(?=(?:năm|tháng|học kỳ|tín chỉ)\b)", re.I)
_RUOI = re.compile(r"\b(\d+)\s+(năm|tháng)\s+rưỡi\b", re.I)                                  # \"4 năm rưỡi\" -> 4.5 năm
_SCALE = re.compile(r"\b(?:thang\s+(?:điểm\s+)?|hệ\s+)(?:4|10|100)\b(?!\s*(?:năm|học\s+kỳ)\b)(?![.,]\d)", re.I)
_RESTATE = re.compile(r"\(\s*(?:tương\s+đương|tức(?:\s+là)?|khoảng|xấp\s+xỉ|nghĩa\s+là|≈|~)[^)]*\)", re.I)
_WS = re.compile(r"[ \t]+")
_COMBINING = re.compile(r".[̀-ͯ]+", re.S)             # NFD (macOS file names, PDF extraction) -> NFC
_ODD_SPACE = re.compile(r"[    ]")
_ZERO_WIDTH = re.compile(r"[​‌‍﻿]")
_NORM_STEPS = [
    (_COMBINING, lambda m: unicodedata.normalize("NFC", m[0])),
    (_ODD_SPACE, " "),
    (_ZERO_WIDTH, ""),
    (_MD, ""),
    (_ARROW, " nên "),
    (_CITE, " "),
    (_NUMW_RE, lambda m: f"{_NUMW[m[1].lower()]} "),
    (_RUOI, lambda m: f"{m[1]}.5 {m[2]}"),
    (_SCALE, " "),
    (_RESTATE, " "),
    (_WS, " "),
]


# ───────────────────────── stage 0-1: normalise (offset-preserving) + telemetry ─────────────────────────
def _sub(rx, repl, s, sp):
    out, osp, last = [], [], 0
    for m in rx.finditer(s):
        out.append(s[last:m.start()])
        osp.extend(sp[last:m.start()])
        r = repl(m) if callable(repl) else repl
        out.append(r)
        if r:
            osp.extend([(sp[m.start()][0], sp[m.end() - 1][1])] * len(r))
        last = m.end()
    out.append(s[last:])
    osp.extend(sp[last:])
    return "".join(out), osp


def normalize_map(t: str):
    """Returns (normalised text, spans) where spans[i] = (start, end) of normalised char i in the ORIGINAL text."""
    s, sp = t, [(i, i + 1) for i in range(len(t))]
    for rx, repl in _NORM_STEPS:
        s, sp = _sub(rx, repl, s, sp)
    return s, sp


def normalize(t: str) -> str:
    return normalize_map(t)[0]


def is_telemetry(s: str) -> bool:
    """Operational head/unit AND no domain lexeme. A domain lexeme always keeps the line."""
    return bool((_HEAD.match(s) or _TUNIT.search(s)) and not _DOMAIN.search(s))


# ───────────────────────── stage 2: atoms ─────────────────────────
def _cid(raw: str) -> str:
    return PROGRAM[re.sub(r"\s+", " ", re.sub(r"^hệ\s+", "", raw.strip().lower()))]


def _resolve_program(h: str, tail: str):
    """Known programme -> its id. Programme followed by an unexpected word ('chính quy chất lượng cao') -> UNKNOWN."""
    if _AFTER_PROG.match(tail):
        return _cid(h), 0
    ext = _EXT.match(tail)
    if not ext:
        return _cid(h), 0
    name = re.sub(r"^hệ\s+", "", h.lower()) + " " + ext["w"].lower()
    return "UNKNOWN:" + re.sub(r"\s+", " ", name), ext.end()


def _scope_cue(p: str):
    """Leading programme cue of a fragment -> (condition, end index) or None."""
    if m := _CUE.match(p):
        cond, extra = _resolve_program(m["h"], p[m.end():])
        end = m.end() + extra
        end += len(re.match(r"\s*[,:]?\s*", p[end:])[0])
        return cond, end
    if m := _CANARY.match(p):
        return "UNKNOWN:" + re.sub(r"\s+", " ", m["x"].strip().lower()), m.end()
    return None


def _header_scope(line: str) -> str | None:
    s = line.strip()
    r = _scope_cue(s)
    return r[0] if r and not s[r[1]:].strip() else None


_NAMED_STOP = _NOT_A_NAME


def _named(p: str) -> Ent | None:
    """Capitalised token + achievement verb. Sentence-initial function words ('Được học…', 'Không đạt…') are not names."""
    m = _NAMED.match(p)
    if (m and m[1][0].isupper() and not (m[1].isupper() and len(m[1]) > 1)
            and m[1].lower() not in _NAMED_STOP):
        return Ent(m[1].lower(), True, frozenset({"SV"}))   # assumption: a named person here is a student
    return None


def _outcome(p: str):
    for name, rx in _OUTCOMES:
        if m := rx.search(p):
            return name, bool(_NEG.search(p[:m.start()]))
    return None


def _pieces(rx, s: str):
    out, last = [], 0
    for m in rx.finditer(s):
        out.append((last, m.start()))
        last = m.end()
    out.append((last, len(s)))
    return out


def _per_term(text: str) -> bool:
    return bool(_PER.search(text) or (_REG.search(text) and not _TOTAL.search(text)))


def _sentence_atoms(sent: str, s0: int, block, override) -> list[Atom]:
    """`s0` = offset of `sent` in the normalised text; `override` = fixed span (table rows)."""
    cond, src, sspan = (block[0], "HEADER", block[1]) if block else (None, None, (-1, -1))
    rows, last, per_carry = [], GENERIC_SV, False
    for a, b in _pieces(_COORD, sent):
        frag = sent[a:b]
        p = frag.strip()
        if not p:
            continue
        f0 = s0 + a + (len(frag) - len(frag.lstrip()))
        if r := _scope_cue(p):
            cond, end = r
            src, sspan = "INLINE", (f0, f0 + end)
            tail = p[end:]
            f0 += end + (len(tail) - len(tail.lstrip()))
            p = tail.strip()
            if not p:
                continue
        local, lsrc, lspan = cond, src, sspan
        if mm := _MID.search(p):
            local, _ = _resolve_program(mm["h"], p[mm.end():])
            lsrc, lspan = "INLINE", (f0 + mm.start("h"), f0 + mm.end("h"))
        ent = _named(p)
        last = ent or last
        per_here, has_num = _per_term(p), bool(_NUM.search(p))
        per = per_here or (per_carry and has_num)
        per_carry = per_here and not has_num if (has_num or per_here) else per_carry
        if override:
            lspan = override if lsrc == "INLINE" else lspan
        rows.append((p, local, ent or last, _outcome(p), override or (f0, f0 + len(p)), lsrc, lspan, per))
    outs = {r[3][0] for r in rows if r[3]}
    shared = next((r[3] for r in rows if r[3]), None) if len(outs) == 1 else None
    res = []
    for p, c, e, o, sp_, lsrc, lspan, per in rows:
        if not _NUM.search(p):
            continue
        oc = o or shared
        res.append(Atom(p, c, e, oc[0] if oc else None, oc[1] if oc else False,
                        sp_[0], sp_[1], lsrc, lspan[0], lspan[1], per))
    return res


def _line_atoms(line: str, lo: int, block, override, stats) -> list[Atom]:
    res = []
    for a, b in _pieces(_SENT, line):
        sent = line[a:b]
        if not sent.strip() or is_telemetry(sent):
            continue
        stats["sentences"] += 1
        if _NUM.search(sent):
            stats["numeric_sentences"] += 1
        res += _sentence_atoms(sent, lo + a, block, override)
    return res


def _cells(line: str):
    return [c.strip() for c in line.strip().strip("|").split("|")]


def _prog_text(cell: str):
    m = re.fullmatch(rf"(?:hệ\s+)?({_PROG_ALT})", cell.strip(), re.I)
    return m[1] if m else None


def _table_sentences(block):
    """Markdown table -> one synthetic sentence per numeric cell, each carrying its row span."""
    rows = [(pos, pos + len(line), _cells(line)) for pos, line in block]
    data = [r for r in rows if not all(re.fullmatch(r":?-{2,}:?", c.replace(" ", "")) or c == "" for c in r[2])]
    if len(data) < 2:
        return []
    header, out = data[0][2], []
    for rs, re_, cells in data[1:]:
        for j in range(1, min(len(cells), len(header))):
            if not _NUM.search(cells[j]):
                continue
            if p := _prog_text(header[j]):          # columns are programmes
                syn = f"Hệ {p}: {cells[0]} {cells[j]}"
            elif p := _prog_text(cells[0]):         # rows are programmes
                syn = f"Hệ {p}: {header[j]} {cells[j]}"
            else:
                syn = f"{cells[0]} {header[j]} {cells[j]}"
            out.append((syn, rs, re_))
    return out


def _walk(text: str):
    norm, sp = normalize_map(text)

    def orig(a: int, b: int):
        return (sp[a][0], sp[b - 1][1]) if 0 <= a < b <= len(sp) else (-1, -1)

    lines, pos = [], 0
    for ln in norm.split("\n"):
        lines.append((pos, ln))
        pos += len(ln) + 1
    stats = {"sentences": 0, "numeric_sentences": 0}
    out, block, in_list, i = [], None, False, 0
    while i < len(lines):
        pos, raw = lines[i]
        if not raw.strip():
            block, in_list, i = None, False, i + 1
            continue
        if raw.lstrip().startswith("|"):
            j = i
            while j < len(lines) and lines[j][1].lstrip().startswith("|"):
                j += 1
            for syn, rs, re_ in _table_sentences(lines[i:j]):
                out += _line_atoms(syn, 0, block, (rs, re_), stats)
            i = j
            continue
        mb = _BUL.match(raw)
        is_b, line = bool(mb), raw[mb.end():] if mb else raw
        lo = pos + (mb.end() if mb else 0)
        if block and in_list and not is_b:
            block = None                              # a non-bullet line after a list closes the header block
        if h := _header_scope(line):
            s = lo + (len(line) - len(line.lstrip()))
            block, in_list, i = (h, (s, lo + len(line.rstrip()))), False, i + 1
            continue
        in_list = in_list or is_b
        out += _line_atoms(line, lo, block, None, stats)
        i += 1
    mapped = []
    for a in out:
        s, e = orig(a.start, a.end)
        ss, se = orig(a.scope_start, a.scope_end)
        mapped.append(replace(a, start=s, end=e, scope_start=ss, scope_end=se))
    return mapped, stats


def atoms(text: str) -> list[Atom]:
    return _walk(text)[0]


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
    pre, post = a.text[:n.start()], a.text[n.end():]
    if metric == "credits" and (a.per_semester or _PER.match(post.lstrip())):
        unit = "credit/semester"                      # a per-semester load is not the programme total
    if _REMAIN.search(pre):
        unit += "/remaining"                          # \"còn tối đa 1 năm\" is time left, not the cap
    op = _find_op(pre, post)
    fact = op == "==" and (a.entity.instance or bool(_STRONG.search(a.text))
                           or bool(_WEAK.search(a.text) and _SUBJ.search(a.text)))
    return Tup(a.entity, metric, op, v, unit, role=Role.FACT if fact else Role.NORM, outcome=a.outcome,
               verdict=(not a.neg) if (fact and a.outcome) else None, condition=a.condition, text=a.text)


def _extract_atoms(text: str):
    pairs, stats = _walk(text)
    return [(a, extract(a)) for a in pairs], stats


def extract_all(text: str):
    tups, unparsed = [], []
    for a, r in _extract_atoms(text)[0]:
        if isinstance(r, str):
            unparsed.append((a.text, r))
        else:
            tups.append(r)
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
    if clm.op == "==":                                # \"thời gian là X năm\": lenient, X must lie inside the bound
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
    if query_condition is not None and query_condition in agg:   # None = \"no query context\", NOT the general bucket
        # query context may only TIGHTEN, never relax
        q = agg[query_condition]
        return Res(V.GROUNDING_CONFLICT, "query_scope_conflict") if q.verdict is V.GROUNDING_CONFLICT \
            else Res(V.SCOPE_ELIDED, query_condition)
    return Res(V.AMBIGUOUS_SCOPE, ",".join(f"{c}:{r.verdict.name}" for c, r in agg.items() if c))


def _evasion_pass(findings: list[Finding], kb: dict, query_condition: str | None) -> list[Finding]:
    """The query pinned a programme the KB knows, but the only claim about that metric uses a label the lexicon does
    not know ('hệ đại trà'). If its value violates the queried programme's rule, 'unverified' would let a wrong
    number reach the student: block. If the answer also addresses the queried programme (or is unscoped) for the
    same metric, the unknown label is extra information and stays unverified."""
    if query_condition is None:
        return findings
    out = list(findings)
    for i, f in enumerate(findings):
        t = f.tup
        if t is None or f.result.verdict is not V.OUT_OF_COVERAGE or not (t.condition or "").startswith("UNKNOWN:"):
            continue
        key = (t.metric, t.unit)
        if any(g.tup and (g.tup.metric, g.tup.unit) == key and g.tup.condition in (query_condition, None)
               for g in findings):
            continue
        kbk = kb.get(key, [])
        pool = [s for s in kbk if s.condition == query_condition] or [s for s in kbk if s.condition is None]
        if pool and _bucket([match(s, t) for s in pool]).verdict is V.GROUNDING_CONFLICT:
            out[i] = replace(f, result=Res(V.GROUNDING_CONFLICT, "query_scope_evasion"))
    return out


def _findings(answer: str, kb: dict, query_condition: str | None):
    pairs, stats = _extract_atoms(answer)
    fs = []
    for a, r in pairs:
        span, sspan = (a.start, a.end), (a.scope_start, a.scope_end)
        if isinstance(r, str):
            fs.append(Finding(a.text, None, Res(V.NOT_COMPARABLE, f"unparsed:{r}"), span, a.scope_src, sspan))
        else:
            fs.append(Finding(r.text, r, audit(r, kb, query_condition), span, a.scope_src, sspan))
    return _evasion_pass(fs, kb, query_condition), stats


def audit_text(answer: str, kb: dict, query_condition: str | None = None) -> list[Finding]:
    return _findings(answer, kb, query_condition)[0]


def gate(findings: list[Finding]) -> str:
    vs = {f.result.verdict for f in findings}
    if V.GROUNDING_CONFLICT in vs:
        return "BLOCK"
    if V.AMBIGUOUS_SCOPE in vs:
        return "REGENERATE"
    if vs & {V.OUT_OF_COVERAGE, V.SCOPE_ELIDED}:
        return "ANNOTATE"
    return "PASS"


# ───────────────────────── stage 6: report for the UI ─────────────────────────
_LABELLED = {V.GROUNDING_CONFLICT, V.AMBIGUOUS_SCOPE, V.OUT_OF_COVERAGE, V.SCOPE_ELIDED}
_HEADER_ANCHORED = {V.OUT_OF_COVERAGE, V.SCOPE_ELIDED}     # one label on the header covers every line under it


def audit_answer(answer: str, kb: dict, query_condition: str | None = None) -> AuditReport:
    """Span annotations + answer-level coverage. There is deliberately NO 'verified' state: only quantitative
    claims are checked, and sentences without a number are never looked at."""
    fs, stats = _findings(answer, kb, query_condition)
    ann, seen = [], set()
    for f in fs:
        v = f.result.verdict
        if v not in _LABELLED:
            continue
        if v in _HEADER_ANCHORED and f.scope_src == "HEADER" and f.scope_span[0] >= 0:
            if f.scope_span in seen:
                continue
            seen.add(f.scope_span)
            ann.append(Annotation(v.name, f.result.reason, f.scope_span[0], f.scope_span[1], "HEADER"))
        else:
            s0 = f.span[0]
            if f.scope_src == "INLINE" and 0 <= f.scope_span[0] < s0:
                s0 = f.scope_span[0]                      # label covers 'Hệ X: <clause>' so the reader sees the scope
            ann.append(Annotation(v.name, f.result.reason, s0, f.span[1], "CLAUSE"))
    n = lambda *vs: sum(1 for f in fs if f.result.verdict in vs)
    unparsed = sum(1 for f in fs if f.tup is None)
    summary = {
        "quantitative_checked": sum(1 for f in fs if f.tup is not None),
        "satisfied": n(V.SATISFIED_BOUND), "conflict": n(V.GROUNDING_CONFLICT), "ambiguous": n(V.AMBIGUOUS_SCOPE),
        "unverified": n(V.OUT_OF_COVERAGE, V.SCOPE_ELIDED),
        "not_comparable": n(V.NOT_COMPARABLE) - unparsed, "unparsed": unparsed,
        "sentences": stats["sentences"],
        "sentences_without_numbers": stats["sentences"] - stats["numeric_sentences"],
    }
    summary["note"] = (f"Đã đối chiếu {summary['quantitative_checked']} mệnh đề định lượng "
                       f"({summary['satisfied']} khớp, {summary['conflict']} mâu thuẫn, {summary['unverified']} chưa kiểm chứng); "
                       f"{summary['sentences_without_numbers']} câu không có số chưa được tự động kiểm chứng.")
    return AuditReport(fs, ann, summary, gate(fs))


def copy_footer(report: AuditReport) -> str:
    """Plain-text line to append when the answer is copied, so the warning survives pasting into Zalo etc."""
    if any(a.kind in ("OUT_OF_COVERAGE", "SCOPE_ELIDED") for a in report.annotations):
        return "[Lưu ý: một phần nội dung nằm ngoài phạm vi quy chế đã đối chiếu, chưa được kiểm chứng tự động.]"
    return ""


# ───────────────────────── stage 7: query side ─────────────────────────
# Questions are not predicate-shaped (\"hệ chính quy bao nhiêu năm?\"), so the terminator set is _PRED plus
# interrogatives and connectors. Anything ELSE after a programme name still means \"a longer name\" -> no pin.
_Q_STOP = (rf"(?:{_PRED}|bao|mấy|nào|sao|thế|ra|gì|hay|và|hoặc|so|với|khác|thì|còn|hơn|bằng|của|để|cho|nên|mà|vậy"
           r"|ở|tại|trong|bậc|ngành)")
_Q_ALIAS = re.compile(rf"\b(?P<a>{_PROG_ALT})\b", re.I)
_Q_HE = re.compile(r"\bhệ\s+", re.I)
_Q_NOT_A_PROGRAMME = re.compile(r"(?:thống|số|quả)\b", re.I)
_Q_SCALE = re.compile(r"\d+(?:[.,]\d+)?(?![.,]?\d)(?!\s*(?:năm|học\s+kỳ)\b)", re.I)
_Q_NEXT = re.compile(r"\s*(?P<w>[^\s,;:.?!()\[\]\"']+)?")


def _query_norm(q: str) -> str:
    q = unicodedata.normalize("NFC", q)
    q = _ODD_SPACE.sub(" ", _ZERO_WIDTH.sub("", q))
    return re.sub(r"\s+", " ", q).strip().lower()


def infer_query_condition(query: str | None) -> str | None:
    """The one programme the QUERY pins, else None. None is the safe answer: it only disables query tightening.
    A false pin is the dangerous error (it can turn an honest ANNOTATE into a BLOCK), so every doubt resolves to None:
    more than one programme, a `hệ <label>` that is not exactly a known programme (including digit names such as
    'hệ 5 năm'), or a known name followed by an unexpected word ('chính quy chất lượng cao').
    Known limit: an unknown label WITHOUT the word 'hệ' ('còn đại trà?') cannot be seen without a label lexicon."""
    if not query:
        return None
    q = _query_norm(query)
    for m in _Q_HE.finditer(q):                            # every `hệ <x>`: x must be a known programme, a scale or not a programme
        rest = q[m.end():]
        if _Q_NOT_A_PROGRAMME.match(rest) or _Q_SCALE.match(rest):
            continue                                       # hệ thống / hệ số / hệ 4 (grading scale)
        if not _Q_ALIAS.match(rest):
            return None                                    # unknown label, or digit name 'hệ 5 năm' / 'hệ 4,5 năm'
    ids: set[str] = set()
    for m in _Q_ALIAS.finditer(q):                         # every known name, with or without 'hệ'
        nxt = _Q_NEXT.match(q, m.end())["w"]
        if nxt and not re.fullmatch(_Q_STOP, nxt, re.I):
            return None                                    # extended name
        ids.add(PROGRAM[m["a"]])
    return next(iter(ids)) if len(ids) == 1 else None


# ───────────────────────── Backward Compatibility Adapter ─────────────────────────
class ContradictionType(Enum):
    GROUNDING_CONFLICT = auto()
    PREMISE_INVERSION = auto()
    NUMERIC_COLLISION = auto()
    AMBIGUOUS_SCOPE = auto()
    OUT_OF_COVERAGE = auto()
    SCOPE_ELIDED = auto()
    NOT_COMPARABLE = auto()
    DISJOINT_ENTITIES = auto()
    SATISFIED_BOUND = auto()


@dataclass
class AuditFinding:
    is_contradiction: bool
    conflict_type: ContradictionType
    step_index: int
    claim: str
    basis: str
    conflicting_source_id: Optional[str] = None
    conflicting_step_index: Optional[int] = None
    severity: str = "blocking"
    explanation: str = ""
    claim_origin: str = "step"  # "step" | "answer"

    def to_dict(self) -> Dict[str, Any]:
        return {
            "is_contradiction": self.is_contradiction,
            "conflict_type": self.conflict_type.name,
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
    findings: List[AuditFinding]
    monotonicity_score: float
    audited_steps_count: int
    source_evidences_count: int
    duration_ms: float = 0.0
    coverage_status: str = "checked"  # "checked" | "not_evaluated" | "no_evidences"
    claims_checked_count: int = 0
    operational_events_count: int = 0

    def to_dict(self) -> Dict[str, Any]:
        return {
            "passed": self.passed,
            "findings": [f.to_dict() for f in self.findings],
            "monotonicity_score": self.monotonicity_score,
            "audited_steps_count": self.audited_steps_count,
            "source_evidences_count": self.source_evidences_count,
            "duration_ms": self.duration_ms,
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
    """Distinguishes internal runner execution logs from domain propositions."""
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

is_operational_step = is_operational_event


class ContradictionAuditor:
    """
    Backward-compatible auditor facade integrating interval engine
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
                # Strip step numbering prefix like 'Bước 1:' or 'Step 1:'
                clean_step = re.sub(r"^\s*(?:Bước|Step)\s*\d+\s*[:.]?\s*", "", sc, flags=re.I).strip()
                claims_to_audit.append((s_idx, clean_step or sc, "step"))

        if answer:
            # We split answer by sentences while preserving order
            for a_idx, sent in enumerate(re.split(r"(?<=[.!?\n])\s+", answer)):
                sc = sent.strip()
                if sc and not is_operational_step(sc):
                    claims_to_audit.append((len(steps) + a_idx, sc, "answer"))

        claims_checked_count = len(claims_to_audit)

        # 3. Grounding audit via interval engine on answer & claims
        if kb:
            # Audit answer as a cohesive text
            if answer:
                ans_findings = audit_text(answer, kb, query_condition=query_cond)
                for f in ans_findings:
                    if f.result.verdict is V.GROUNDING_CONFLICT:
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
                            conflicting_source_id=matched_ev_id or (getattr(evidences[0], "source_id", None) if evidences and hasattr(evidences[0], 'source_id') else (evidences[0].get("source_id") if evidences and isinstance(evidences[0], dict) else None)),
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
