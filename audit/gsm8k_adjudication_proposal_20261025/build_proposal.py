"""Prepare three reviewable wording edits; never write a runnable dataset."""
import copy
import hashlib
import json
from pathlib import Path
from fractions import Fraction
from collections import Counter
import sys

ROOT = Path(__file__).resolve().parents[2]
OUT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))
from experiments.research_study import validate_dataset
from experiments.gsm8k_routing_baseline import candidate_rules


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    path = ROOT / "data/gsm8k_development_validation_candidate_v1/dataset.json"
    manifest = json.loads((path.parent / "manifest.json").read_text())
    original_hash = sha(path)
    assert original_hash == manifest["dataset_sha256"]
    original = json.loads(path.read_text())
    draft = copy.deepcopy(original)
    edits = {
        "gsm8k-dev-02343": ("pays before the 25th", "pays on or before the 25th", "Payment on day25 now explicitly qualifies.", Fraction(50)*4*Fraction(95,100)),
        "gsm8k-dev-00484": ("an eighth of his weight every month", "a fixed one-eighth of his post-growth weight each month", "Use the same post-growth baseline each month, not compounded current weight.", Fraction(156)-(Fraction(156+36)-3*Fraction(156+36,8))),
        "gsm8k-dev-03823": ("only 5 have said they are thinking about voting for him", "5 more have said they will definitely vote for him", "The five additional supporters explicitly commit;25 opponents remain.", Fraction(60)*Fraction(3,4)-(30+5+Fraction(60-30-5,5))),
    }
    changes = []
    for item in draft["items"]:
        if item["id"] not in edits: continue
        old, new, rationale, expected = edits[item["id"]]
        before = item["query"]
        assert before.count(old) == 1
        after = before.replace(old, new)
        assert Fraction(item["answer"]) == expected
        item["query"] = after
        changed_rules = [rule.id for rule in candidate_rules() if rule.choose(before) != rule.choose(after)]
        changes.append({"id":item["id"], "group_id":item["group_id"], "split":item["split"],
                        "original_source_line":item["source_provenance"]["line_1based"],
                        "before":before, "proposed_after":after, "replace_from":old, "replace_to":new,
                        "retained_gold":item["answer"], "rationale":rationale,
                        "old_word_count":len(before.split()), "proposed_word_count":len(after.split()),
                        "changed_rule_actions":changed_rules,
                        "original_query_sha256":hashlib.sha256(before.encode()).hexdigest(),
                        "proposed_query_sha256":hashlib.sha256(after.encode()).hexdigest(),
                        "human_decision":"pending"})
    assert len(changes) == 3
    assert Counter(x["split"] for x in draft["items"]) == {"train":48,"calibration":48}
    assert all(a["group_id"] == b["group_id"] and a["answer"] == b["answer"]
               for a,b in zip(original["items"], draft["items"]))
    # In-memory validation checks shape only; this is not a released dataset.
    validate_dataset(draft, pilot=True)
    proposal = {"kind":"wording_adjudication_proposal_not_dataset", "status":"human_review_pending",
                "original_dataset_sha256":original_hash, "changes":changes,
                "draft_frame":{"items":96,"fitting":48,"development_validation":48},
                "source_labels_retained":True,"data_quality_edits_informed_by_gold":True,
                "generated_model_outcomes_used":False,"new_model_calls":0,
                "execution_authorized":False,"publication_ready":False,
                "validation_wording_priorities_still_pending":True}
    rejected = False
    try: validate_dataset(proposal, pilot=True)
    except ValueError: rejected = True
    assert rejected and sha(path) == original_hash
    proposal["proposal_rejected_as_runnable_dataset"] = rejected
    target = OUT / "proposal.json"
    if target.exists():
        assert json.loads(target.read_text()) == proposal, "Existing proposal differs; preserve it."
    else:
        target.write_text(json.dumps(proposal,ensure_ascii=False,indent=2)+"\n")
    print(json.dumps({"original_unchanged":True,"shape_valid_in_memory":True,
                      "proposal_is_not_runnable_dataset":rejected,
                      "changes":[{k:r[k] for k in ("id","old_word_count","proposed_word_count","retained_gold","changed_rule_actions")} for r in changes]},indent=2))


if __name__ == "__main__": main()
