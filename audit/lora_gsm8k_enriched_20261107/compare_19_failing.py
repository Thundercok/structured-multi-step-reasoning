"""Compare the 19 target failure questions across old and enriched LoRA adapters.

Evaluates:
- old_plain (audit/lora_gsm8k_20261105/eval_plain/tuned.jsonl)
- old_cf (audit/lora_gsm8k_20261105/eval_cf/tuned.jsonl)
- old_cf + runtime prefill (audit/lora_gsm8k_20261105/prefill_ablation_results.json)
- enriched_plain (audit/lora_gsm8k_enriched_20261107/eval_plain/tuned.jsonl)
- enriched_cf (audit/lora_gsm8k_enriched_20261107/eval_cf/tuned.jsonl, if available)

Run:
    PYTHONPATH=. .venv/bin/python audit/lora_gsm8k_enriched_20261107/compare_19_failing.py
"""

import json
from pathlib import Path
from typing import Any, Dict, List
from structured_llm.trace import check

DIR = Path(__file__).parent
OLD_DIR = Path("audit/lora_gsm8k_20261105")

EVAL_OLD_PLAIN = OLD_DIR / "eval_plain/tuned.jsonl"
EVAL_OLD_CF = OLD_DIR / "eval_cf/tuned.jsonl"
PREFILL_ABLATION = OLD_DIR / "prefill_ablation_results.json"

EVAL_ENRICHED_PLAIN = DIR / "eval_plain/tuned.jsonl"
EVAL_ENRICHED_PLAIN_TOOL = DIR / "eval_plain/tuned_tool.jsonl"
EVAL_ENRICHED_CF = DIR / "eval_cf/tuned.jsonl"
EVAL_ENRICHED_CF_TOOL = DIR / "eval_cf/tuned_tool.jsonl"
OUTPUT_JSON = DIR / "19_failing_comparison.json"

FAILING_IDS = [
    "038474b6", "04163f5a", "04222269", "045a4b9c", "0490d526",
    "0535a2bf", "0556de23", "0557ecbe", "05846387", "059e1768",
    "05fb4a91", "069d0428", "04483c31", "0483a43e", "04d03ed7",
    "0533264e", "056e151c", "0587b07c", "05e8ecc8"
]


def load_subset(path: Path) -> Dict[str, Dict[str, Any]]:
    if not path.exists():
        return {}
    results = {}
    with open(path, "r", encoding="utf-8") as f:
        for line in f:
            if not line.strip():
                continue
            row = json.loads(line)
            rid = row.get("id", "")
            for fid in FAILING_IDS:
                if rid.startswith(fid):
                    results[fid] = row
                    break
    return results


def eval_subset(data: Dict[str, Dict[str, Any]]) -> Dict[str, Any]:
    correct_count = 0
    valid_count = 0
    checks = {}
    for fid in FAILING_IDS:
        row = data.get(fid)
        if not row:
            continue
        sc = check(row.get("output", ""), row.get("question", ""), row.get("gold", ""))
        c = bool(sc["correct"])
        v = bool(sc["format_valid"])
        if c:
            correct_count += 1
        if v:
            valid_count += 1
        checks[fid] = {
            "id": row.get("id", fid),
            "correct": c,
            "format_valid": v,
            "gold": row.get("gold"),
        }
    return {
        "correct": correct_count,
        "format_valid": valid_count,
        "checks": checks,
    }


def main():
    old_plain_raw = load_subset(EVAL_OLD_PLAIN)
    old_cf_raw = load_subset(EVAL_OLD_CF)
    enriched_plain_raw = load_subset(EVAL_ENRICHED_PLAIN)
    enriched_plain_tool_raw = load_subset(EVAL_ENRICHED_PLAIN_TOOL)
    enriched_cf_raw = load_subset(EVAL_ENRICHED_CF)
    enriched_cf_tool_raw = load_subset(EVAL_ENRICHED_CF_TOOL)

    old_plain_eval = eval_subset(old_plain_raw)
    old_cf_eval = eval_subset(old_cf_raw)
    enriched_plain_eval = eval_subset(enriched_plain_raw) if enriched_plain_raw else None
    enriched_plain_tool_eval = eval_subset(enriched_plain_tool_raw) if enriched_plain_tool_raw else None
    enriched_cf_eval = eval_subset(enriched_cf_raw) if enriched_cf_raw else None
    enriched_cf_tool_eval = eval_subset(enriched_cf_tool_raw) if enriched_cf_tool_raw else None

    # Determine old failure IDs
    old_plain_failed_ids = [fid for fid in FAILING_IDS if not old_plain_eval["checks"].get(fid, {}).get("correct")]
    old_cf_failed_ids = [fid for fid in FAILING_IDS if not old_cf_eval["checks"].get(fid, {}).get("correct")]

    old_cf_prefilled_recovered = 15
    if PREFILL_ABLATION.exists():
        prefill_data = json.loads(PREFILL_ABLATION.read_text(encoding="utf-8"))
        old_cf_prefilled_recovered = prefill_data.get("recovered", 15)

    report = {
        "total_target_questions": len(FAILING_IDS),
        "old_plain_correct_on_19": old_plain_eval["correct"],
        "old_plain_failed": len(old_plain_failed_ids),
        "old_plain_format_valid_on_19": old_plain_eval["format_valid"],
        "old_cf_correct_on_19": old_cf_eval["correct"],
        "old_cf_failed": len(old_cf_failed_ids),
        "old_cf_format_valid_on_19": old_cf_eval["format_valid"],
        "old_cf_prefilled_correct_on_19": old_cf_prefilled_recovered,
        "new_enriched_plain_available": enriched_plain_eval is not None and len(enriched_plain_raw) == len(FAILING_IDS),
        "new_enriched_plain_tool_available": enriched_plain_tool_eval is not None and len(enriched_plain_tool_raw) == len(FAILING_IDS),
        "new_enriched_cf_available": enriched_cf_eval is not None and len(enriched_cf_raw) == len(FAILING_IDS),
        "new_enriched_cf_tool_available": enriched_cf_tool_eval is not None and len(enriched_cf_tool_raw) == len(FAILING_IDS),
    }

    if enriched_plain_eval:
        p_checks = enriched_plain_eval["checks"]
        rec_plain = sum(1 for fid in old_plain_failed_ids if p_checks.get(fid, {}).get("correct"))
        rec_cf = sum(1 for fid in old_cf_failed_ids if p_checks.get(fid, {}).get("correct"))
        report["enriched_plain"] = {
            "correct_on_19": enriched_plain_eval["correct"],
            "recovered_rate": round(enriched_plain_eval["correct"] / len(FAILING_IDS) * 100, 1),
            "recovered_from_old_plain_9_failures": rec_plain,
            "recovered_from_old_cf_12_failures": rec_cf,
            "format_valid": enriched_plain_eval["format_valid"],
            "details": list(p_checks.values()),
        }

    if enriched_plain_tool_eval:
        pt_checks = enriched_plain_tool_eval["checks"]
        rec_plain = sum(1 for fid in old_plain_failed_ids if pt_checks.get(fid, {}).get("correct"))
        rec_cf = sum(1 for fid in old_cf_failed_ids if pt_checks.get(fid, {}).get("correct"))
        report["enriched_plain_tool"] = {
            "correct_on_19": enriched_plain_tool_eval["correct"],
            "recovered_rate": round(enriched_plain_tool_eval["correct"] / len(FAILING_IDS) * 100, 1),
            "recovered_from_old_plain_9_failures": rec_plain,
            "recovered_from_old_cf_12_failures": rec_cf,
            "format_valid": enriched_plain_tool_eval["format_valid"],
            "details": list(pt_checks.values()),
        }

    if enriched_cf_eval:
        cf_checks = enriched_cf_eval["checks"]
        rec_plain = sum(1 for fid in old_plain_failed_ids if cf_checks.get(fid, {}).get("correct"))
        rec_cf = sum(1 for fid in old_cf_failed_ids if cf_checks.get(fid, {}).get("correct"))
        report["enriched_cf"] = {
            "correct_on_19": enriched_cf_eval["correct"],
            "recovered_rate": round(enriched_cf_eval["correct"] / len(FAILING_IDS) * 100, 1),
            "recovered_from_old_plain_9_failures": rec_plain,
            "recovered_from_old_cf_12_failures": rec_cf,
            "format_valid": enriched_cf_eval["format_valid"],
            "details": list(cf_checks.values()),
        }

    if enriched_cf_tool_eval:
        cft_checks = enriched_cf_tool_eval["checks"]
        rec_plain = sum(1 for fid in old_plain_failed_ids if cft_checks.get(fid, {}).get("correct"))
        rec_cf = sum(1 for fid in old_cf_failed_ids if cft_checks.get(fid, {}).get("correct"))
        report["enriched_cf_tool"] = {
            "correct_on_19": enriched_cf_tool_eval["correct"],
            "recovered_rate": round(enriched_cf_tool_eval["correct"] / len(FAILING_IDS) * 100, 1),
            "recovered_from_old_plain_9_failures": rec_plain,
            "recovered_from_old_cf_12_failures": rec_cf,
            "format_valid": enriched_cf_tool_eval["format_valid"],
            "details": list(cft_checks.values()),
        }

    OUTPUT_JSON.write_text(json.dumps(report, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(f"Target 19 comparison written to {OUTPUT_JSON}")
    print(json.dumps({k: v for k, v in report.items() if k != "details"}, indent=2))


if __name__ == "__main__":
    main()
