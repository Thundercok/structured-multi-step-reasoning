"""Read-only: best case for a perfect reader. Unreadable equations count as true; equations with unknowns do not."""
import json, re, sys, collections
sys.path.insert(0, ".")
from pathlib import Path
from structured_llm.math_check import HARD_LEVELS, TRUE, CONDITIONAL, FALSE, boxed_answer, compare, equations, is_trivial, parse, to_expression
rows=[json.loads(l) for l in Path("data/math_source/train.jsonl").read_text().splitlines()]
rows=[r for r in rows if r["level"] in HARD_LEVELS]
def norm(s): return re.sub(r"\s|\\!|\\,|\\left|\\right|\\boxed|\$|\.$","",s or "").replace("dfrac","frac").replace("tfrac","frac").strip("{}")
C=collections.Counter(); by=collections.defaultdict(collections.Counter)
for r in rows:
    sol=r["solution"]; ans=norm(boxed_answer(sol)); ok=0; hit=False; conditional=0
    for L,R in equations(sol):
        if is_trivial(L,R): continue
        a,b=parse(to_expression(L)),parse(to_expression(R.replace("\\boxed","")))
        v=None if a is None or b is None else compare(a,b)
        if v==CONDITIONAL: conditional+=1
        if v in (TRUE,None):
            ok+=1; hit=hit or (bool(ans) and norm(R)==ans)
    good=ok>=2 and hit
    C["perfect_reader_bound"]+=good; C["two_checkable"]+=ok>=2; C["answer_reached"]+=hit
    C["has_conditional"]+=conditional>0
    by[r["subject"]]["n"]+=1; by[r["subject"]]["bound"]+=good
n=len(rows); print({k:round(v/n,4) for k,v in C.items()}); print({k:round(v["bound"]/v["n"],3) for k,v in sorted(by.items())})
