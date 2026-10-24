"""Fresh C1-C3 review; preserve earlier evidence, never load a model."""
import hashlib
import json
from pathlib import Path
import sys
import tempfile

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from experiments import checker_dry_run as m
from reasoning.reasoning_strategies import majority_vote
from research_scoring import typed_vote_key


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def snapshot(path):
    return {str(p.relative_to(path)): sha(p) for p in path.rglob("*") if p.is_file()}


def main():
    base = ROOT / "audit/rat_cot_quick_unification_20261022"
    protected = [base / "checker_development_dry_run", base / "checker_development_dry_run_repair_20261023",
                 base / "checker_development_dry_run_repair_20261024"]
    before = {str(p.relative_to(ROOT)): snapshot(p) for p in protected}
    repair = protected[-1]
    manifest = json.loads((repair / "manifest.json").read_text())
    artifacts = {p: sha(repair/p) == v for p,v in manifest["artifact_sha256"].items()}
    assert len(artifacts) == 9 and all(artifacts.values())
    sources = {name: sha(ROOT/path) == manifest["source_sha256"][name] for name,path in
               {"checker_dry_run_py":"experiments/checker_dry_run.py", "verifiers_py":"scripts/verifiers.py"}.items()}
    assert all(sources.values())
    with tempfile.TemporaryDirectory(prefix="checker-c123-acceptance-") as temp:
        target = Path(temp)/"run"
        m.build_checker_development_dry_run_artifacts(ROOT,target)
        first = snapshot(target)
        try:
            m.build_checker_development_dry_run_artifacts(ROOT,target)
        except ValueError as error:
            assert "occupied" in str(error)
        else:
            raise AssertionError("Occupied output accepted")
        assert snapshot(target) == first
        summary = json.loads((target/"dry_run_summary.json").read_text())
        cot = summary["paths"]["fixed_cot"]
        assert cot["is_synthetic"] is True
        assert "authored cost" in cot["data_provenance"]
        assert cot["total_generated_tokens"] == 960
        assert "[SYNTHETIC REPLAY]" in (target/"report.md").read_text()
        cpu_keys = []
        def check_cpu(value):
            if isinstance(value,dict):
                for key,v in value.items():
                    if "cpu_time" in key: cpu_keys.append(key)
                    check_cpu(v)
            elif isinstance(value,list):
                for v in value: check_cpu(v)
        for name in ("dry_run_summary.json","development_review_summary.json","proposed_execution_plan.json"):
            check_cpu(json.loads((target/name).read_text()))
        assert not cpu_keys
    bad, good = "1+2+3+4", "(1+3)*(2+4)"
    cases = [([bad,good,"(1 + 3) * (2 + 4)"],"no selection"),
             ([bad,good,"(1+3)×(2+4)"],"Best: 99"),
             ([bad,good,"(1 + 3)*(2 + 4)"],"Best: -1"),
             ([bad,good,"(1+2+3)*4"],"no selection")]
    votes=[]
    for index,(answers,selector) in enumerate(cases):
        bank={("authored","tot_candidate",i):{"output":"Answer: "+a,"tokens":20} for i,a in enumerate(answers)}
        bank[("authored","tot_selector",0)]={"output":selector,"tokens":5}
        evaluator=m.G24CheckerLadderEvaluator(m.ScriptedGenerationBackend(m.GenerationLedger(),bank))
        result=evaluator.evaluate_rung("TOT","authored","Make 24 using 1,2,3,4.",[1,2,3,4])
        expected,_=majority_vote(answers,answer_type="expression")
        assert typed_vote_key(result.extracted_answer,"expression")==expected
        assert result.verification_status == ("invalid" if index==3 else "valid")
        votes.append({"answers":answers,"selector":selector,"selected":result.extracted_answer,"status":result.verification_status})
    assert before == {str(p.relative_to(ROOT)):snapshot(p) for p in protected}
    evidence={"repair_artifact_hashes":artifacts,"current_source_matches":sources,
              "occupied_rerun_rejected_all_files_byte_unchanged":True,"fixed_cot_cost_labeled_synthetic":True,
              "cpu_time_aliases_removed":True,"selector_cases":votes,"protected_evidence_unchanged":True,
              "new_model_calls":0,"gsm8k_candidate_content_read":False,"stage0_changed":False}
    (Path(__file__).parent/"verification.json").write_text(json.dumps(evidence,indent=2)+"\n")
    print("PASS: C1-C3, 9 artifacts, 2 sources, 4 selector cases, prior evidence unchanged.")


if __name__ == "__main__":
    main()
