"""Read-only: split gate 3a misses into checker limits and limits of the data itself."""
import collections, json, re, sys
sys.path.insert(0, ".")
from pathlib import Path
from structured_llm.math_check import (HARD_LEVELS, TRUE, CONDITIONAL, FALSE, boxed_answer, check_text, compare, equations,
    is_covered, is_trivial, parse, to_expression, _REJECT, _DROP)
rows=[json.loads(l) for l in Path("data/math_source/train.jsonl").read_text().splitlines()]
rows=[r for r in rows if r["level"] in HARD_LEVELS]
def norm(s): return re.sub(r"\s|\\!|\\,|\\left|\\right|\\boxed|\$|\.$","",s or "").replace("dfrac","frac").replace("tfrac","frac").strip("{}")
n=len(rows); C=collections.Counter(); reasons=collections.Counter(); ans_kinds=collections.Counter(); bysub=collections.defaultdict(collections.Counter)
for r in rows:
    sol=r["solution"]; pairs=[p for p in equations(sol)]; nontriv=[p for p in pairs if not is_trivial(*p)]
    ans=norm(boxed_answer(sol)); rhs={norm(b) for _,b in pairs}
    res=check_text(sol)
    cov=is_covered(res); C["current_covered"]+=cov
    two=len(nontriv)>=2; hit=bool(ans) and ans in rhs
    C["ge2_nontrivial_eq"]+=two; C["answer_on_some_rhs"]+=hit; C["upper_bound_parser_free"]+=two and hit
    bysub[r["subject"]]["n"]+=1; bysub[r["subject"]]["ub"]+=two and hit; bysub[r["subject"]]["cov"]+=cov
    # generous: conditional equations also count, when checked by substituting the boxed number
    a=parse(to_expression(boxed_answer(sol) or "")); t=res["counts"][TRUE]; sub=0
    if a is not None and a.is_number if a is not None else False:
        for L,R in nontriv:
            l,rr=parse(to_expression(L)),parse(to_expression(R.replace("\\boxed","")))
            if l is None or rr is None: continue
            syms=l.free_symbols|rr.free_symbols
            if len(syms)==1:
                s=next(iter(syms))
                try:
                    if compare(l.subs(s,a),rr.subs(s,a))==TRUE: sub+=1
                except Exception:
                    pass
    C["with_answer_substitution"]+=(t+sub>=2) and res["reaches_answer"]
    a_txt=boxed_answer(sol) or ""
    ans_kinds["number" if re.fullmatch(r"-?[\d.,]+",a_txt.strip()) else "readable_expr" if a is not None else "unreadable"]+=1
    for L,R in nontriv:
        for side in (L,R):
            if to_expression(side) is None:
                m=_REJECT.search(_DROP.sub("",side)); reasons[m.group(0) if m else "other"]+=1
print(json.dumps({"n":n,**{k:round(v/n,4) for k,v in C.items()},"answer_kinds":{k:round(v/n,4) for k,v in ans_kinds.items()},
  "upper_bound_by_subject":{k:{"n":v["n"],"current":round(v["cov"]/v["n"],3),"bound":round(v["ub"]/v["n"],3)} for k,v in sorted(bysub.items())},
  "unreadable_reasons_top":reasons.most_common(12)},indent=0,ensure_ascii=False))
