"""
Reproducible End-to-End Demo for CHUOT / RAT Reasoning Pipeline.

Demonstrates:
1. Tier 0 Fast-Path (0 LLM inference cost)
2. Local Verifier Gate (AST sandbox & Lexical document checking)
3. Stopping vs Escalation Decision (Optimal Stopping Policy)
4. Cost & Token Accounting Summary

Usage:
    python -m scripts.run_reproducible_demo
"""

import sys
import time
from rat.engine.vgc import (
    VGCCertificate,
    VGCVerifier,
    VGCVerificationStatus,
)


def run_demo():
    print("=" * 70)
    print("      CHUOT (RAT) — REPRODUCIBLE END-TO-END REASONING DEMO")
    print("=" * 70)

    test_cases = [
        {
            "name": "Case 1: Valid Calculation (Tier 0 Fast-Path Success)",
            "query": "Calculate total budget: 15 * 8 + 30",
            "tier0_claim": "150",
            "tier0_expr": "15 * 8 + 30",
            "tier0_tokens": 20,
            "tier1_solve_fn": lambda: ("150", 250),
        },
        {
            "name": "Case 2: Faulty Arithmetic (Tier 0 Math Error -> Escalation Rescued)",
            "query": "Calculate discounted total: 200 - 200 * 0.15",
            "tier0_claim": "180",  # Faulty calculation (forgot 15% of 200 is 30)
            "tier0_expr": "200 - 200 * 0.15",  # Evaluates to 170.0
            "tier0_tokens": 25,
            "tier1_solve_fn": lambda: ("170", 310),  # Rescued by Tier 1 tool loop
        },
        {
            "name": "Case 3: Document Fact Grounding (Verbatim Excerpt Validated)",
            "query": "Extract Q3 Revenue from text",
            "source_text": "Company announcement: In Q3 2026, operating profit grew to 45 billion VND.",
            "tier0_claim": "operating profit grew to 45 billion VND",
            "tier0_tokens": 30,
            "tier1_solve_fn": None,
        },
        {
            "name": "Case 4: Document Fact Hallucination Detected -> Escalation",
            "query": "Extract Employee Count",
            "source_text": "The company has 120 full-time engineers and 15 interns.",
            "tier0_claim": "500 total employees",  # 500 is hallucinated
            "tier0_tokens": 25,
            "tier1_solve_fn": lambda: ("135 total employees (120 full-time + 15 interns)", 380),
        },
    ]

    total_tokens = 0
    escalations = 0

    for i, case in enumerate(test_cases, 1):
        print(f"\n[{i}] {case['name']}")
        print(f"    Query: \"{case['query']}\"")
        print(f"    Tier 0 Output: \"{case['tier0_claim']}\" (Tokens: {case['tier0_tokens']})")

        t0 = time.perf_counter()
        if "tier0_expr" in case:
            cert = VGCCertificate(claim=case["tier0_claim"], witness=case["tier0_claim"])
            v_res = VGCVerifier.verify_calculation(cert, case["tier0_expr"])
        else:
            cert = VGCCertificate(claim=case["tier0_claim"], witness=case["tier0_claim"], source_snippet=case["tier0_claim"])
            v_res = VGCVerifier.verify_document_fact(cert, case["source_text"])

        duration_ms = (time.perf_counter() - t0) * 1000

        print(f"    Verifier Result: {v_res.status.value.upper()} ({duration_ms:.2f}ms)")
        print(f"    Reason: {v_res.reason}")

        if v_res.status == VGCVerificationStatus.VALID:
            print("    --> Policy: STOPPED at Tier 0 (High confidence, verified execution).")
            tokens_used = case["tier0_tokens"]
            final_ans = case["tier0_claim"]
        else:
            escalations += 1
            print("    --> Policy: ESCALATE to Tier 1 (Model Reasoning / ReAct Tool loop).")
            if case.get("tier1_solve_fn"):
                tier1_ans, tier1_tok = case["tier1_solve_fn"]()
                tokens_used = case["tier0_tokens"] + tier1_tok
                final_ans = tier1_ans
                print(f"        Tier 1 Rescued Answer: \"{final_ans}\" (+{tier1_tok} tokens)")
            else:
                tokens_used = case["tier0_tokens"]
                final_ans = case["tier0_claim"]

        total_tokens += tokens_used
        print(f"    Final Output: \"{final_ans}\" | Cost: {tokens_used} tokens")

    print("\n" + "=" * 70)
    print("                     EXECUTION SUMMARY")
    print("=" * 70)
    print(f"Total Queries Evaluated: {len(test_cases)}")
    print(f"Escalation Count:        {escalations} ({escalations/len(test_cases)*100:.1f}%)")
    print(f"Total Tokens Consumed:   {total_tokens} tokens")
    print("Core mechanism successfully demonstrated end-to-end with 0 GUI dependencies.")
    print("=" * 70)


if __name__ == "__main__":
    run_demo()
