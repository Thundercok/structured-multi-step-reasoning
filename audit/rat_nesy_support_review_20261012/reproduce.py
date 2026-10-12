"""Offline counterexamples for existing checkers, not a model-quality benchmark.

Run from repository root:
    python3.12 audit/rat_nesy_support_review_20261012/reproduce.py

The only generated-program execution is the literal, fixed print(999) fixture.
No model, document index, Qt, DocAI or application state is used.
"""
import json

from rat.engine.vgc import VGCCertificate, VGCVerifier, vgc_engine
from scripts.verifiers import verify_arith_rationale


def main():
    source = "Alice scored 100 points. Bob scored 20 points."
    claim = "Bob scored 100 points."
    result = VGCVerifier.verify_document_fact(
        VGCCertificate(claim=claim, witness=claim, source_snippet=source), source
    )
    print(json.dumps({"case": "wrong_entity_number_relation", "source": source,
                      "claim": claim, "status": result.status.value,
                      "reason": result.reason}))

    result = VGCVerifier.verify_calculation(
        VGCCertificate(claim="999", witness="999", raw_code="print(999)"), "2 + 2"
    )
    print(json.dumps({"case": "program_not_bound_to_expression", "expression": "2 + 2",
                      "witness": "999", "status": result.status.value,
                      "reason": result.reason}))

    result = verify_arith_rationale("2 + 2 = 4\nAnswer: 999")
    print(json.dumps({"case": "valid_step_wrong_final_answer", "status": result.status.value,
                      "reason": result.reason}))

    result = vgc_engine.solve_quantitative("Compute two plus two.", "2 + 2")
    print(json.dumps({"case": "deterministic_cascade_metadata", "answer": result.answer,
                      "tokens": result.tokens, "confidence": result.confidence,
                      "strategy": result.strategy}))


if __name__ == "__main__":
    main()
