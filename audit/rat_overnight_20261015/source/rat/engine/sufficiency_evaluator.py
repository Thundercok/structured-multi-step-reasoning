"""
rat.engine.sufficiency_evaluator — Deterministic Information Sufficiency Evaluator.
Assesses whether retrieved candidates adequately satisfy all active facets in < 2ms,
eliminating the need for expensive cloud reflection tokens (Self-RAG/CRAG).
"""

from __future__ import annotations

import logging
import time
from dataclasses import asdict, dataclass, field
from typing import Any, Dict, List, Optional, Set

from rat.engine.query_decomposer import RetrievalPlan

logger = logging.getLogger("rat.evaluator")


@dataclass
class SufficiencyReport:
    """Outcome of candidate sufficiency assessment across OS facets."""
    confidence: float                    # 0.0 to 1.0
    verdict: str                        # "SUFFICIENT" | "PARTIAL" | "INSUFFICIENT"
    facet_satisfactions: Dict[str, float] = field(default_factory=dict)
    missing_facets: List[str] = field(default_factory=list)
    best_candidate_path: Optional[str] = None
    best_candidate_name: Optional[str] = None
    best_candidate_score: float = 0.0
    candidate_count: int = 0
    explanation: str = ""
    latency_ms: float = 0.0

    @property
    def is_sufficient(self) -> bool:
        return self.verdict == "SUFFICIENT"

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


class SufficiencyEvaluator:
    """
    Zero-LLM deterministic evaluator that verifies candidate coverage across OS primitives.
    """

    def __init__(
        self,
        sufficient_threshold: float = 0.68,
        partial_threshold: float = 0.38,
    ) -> None:
        self.sufficient_threshold = sufficient_threshold
        self.partial_threshold = partial_threshold

    def evaluate(
        self,
        plan: RetrievalPlan,
        candidates: List[Dict[str, Any]],
    ) -> SufficiencyReport:
        """Evaluate candidate set against the retrieval plan blueprint."""
        t0 = time.time()
        if not candidates:
            latency_ms = round((time.time() - t0) * 1000.0, 2)
            return SufficiencyReport(
                confidence=0.0,
                verdict="INSUFFICIENT",
                missing_facets=list(plan.active_facets),
                candidate_count=0,
                explanation="Không tìm thấy tệp tin nào khớp với các tiêu chí tìm kiếm.",
                latency_ms=latency_ms,
            )

        facet_sats: Dict[str, float] = {}
        missing_facets: List[str] = []
        facet_weights: Dict[str, float] = {
            "lexical": 1.0,
            "semantic": 1.2,
            "temporal": 1.1,
            "provenance": 1.3,
            "visual": 1.2,
            "type": 0.9,
            "negation": 0.8,
        }

        top_candidates = candidates[:5]

        # 1. Evaluate Lexical Facet
        if "lexical" in plan.active_facets:
            kw_set = set(k.lower() for k in plan.lexical_keywords if len(k) > 1)
            if not kw_set:
                facet_sats["lexical"] = 1.0
            else:
                max_matched = 0
                for c in top_candidates:
                    text_corpus = f"{c.get('file_name', '')} {c.get('content_text', '')[:1000]}".lower()
                    matched = sum(1 for kw in kw_set if kw in text_corpus)
                    if matched > max_matched:
                        max_matched = matched
                sat = min(1.0, max_matched / max(1, min(len(kw_set), 3)))
                facet_sats["lexical"] = round(sat, 3)
                if sat < 0.4:
                    missing_facets.append("lexical")

        # 2. Evaluate Semantic Facet
        if "semantic" in plan.active_facets:
            max_sim = max((c.get("vector_similarity", 0.0) for c in top_candidates), default=0.0)
            if max_sim >= 0.60:
                sat = 1.0
            elif max_sim >= 0.40:
                sat = (max_sim - 0.30) / 0.30
            else:
                sat = max(0.1, max_sim / 0.40)
            facet_sats["semantic"] = round(sat, 3)
            if sat < 0.45:
                missing_facets.append("semantic")

        # 3. Evaluate Temporal Facet
        if "temporal" in plan.active_facets:
            has_temporal_match = False
            for c in top_candidates:
                mod = c.get("modified_at", 0.0)
                if plan.date_min is not None and mod < plan.date_min:
                    continue
                if plan.date_max is not None and mod > plan.date_max:
                    continue
                has_temporal_match = True
                break
            sat = 1.0 if has_temporal_match else 0.1
            facet_sats["temporal"] = sat
            if sat < 0.5:
                missing_facets.append("temporal")

        # 4. Evaluate Provenance Facet
        if "provenance" in plan.active_facets:
            has_prov_match = False
            target_app = (plan.source_app or "").lower()
            target_dom = (plan.source_domain or "").lower()
            for c in top_candidates:
                content = c.get("content_text", "").lower()
                facets_hit = c.get("matched_facets", [])
                if "provenance" in facets_hit:
                    has_prov_match = True
                    break
                if target_app and target_app in content:
                    has_prov_match = True
                    break
                if target_dom and target_dom in content:
                    has_prov_match = True
                    break
            sat = 1.0 if has_prov_match else 0.1
            facet_sats["provenance"] = sat
            if sat < 0.5:
                missing_facets.append("provenance")

        # 5. Evaluate Visual Facet
        if "visual" in plan.active_facets:
            has_vis_match = False
            target_tags = set(t.lower() for t in plan.visual_tags)
            for c in top_candidates:
                facets_hit = c.get("matched_facets", [])
                if "visual" in facets_hit:
                    has_vis_match = True
                    break
                content = c.get("content_text", "").lower()
                if any(tag in content for tag in target_tags):
                    has_vis_match = True
                    break
            sat = 1.0 if has_vis_match else 0.15
            facet_sats["visual"] = sat
            if sat < 0.5:
                missing_facets.append("visual")

        # 6. Evaluate Type Facet
        if "type" in plan.active_facets:
            target_ext_set = set(e.lower() for e in plan.extensions)
            has_type_match = any(c.get("file_ext", "").lower() in target_ext_set for c in top_candidates)
            sat = 1.0 if has_type_match else 0.2
            facet_sats["type"] = sat
            if sat < 0.5:
                missing_facets.append("type")

        # Weighted Overall Confidence
        active_list = [f for f in plan.active_facets if f in facet_sats]
        if not active_list:
            confidence = 0.5
        else:
            total_weight = sum(facet_weights.get(f, 1.0) for f in active_list)
            weighted_sum = sum(facet_weights.get(f, 1.0) * facet_sats[f] for f in active_list)
            confidence = weighted_sum / max(0.001, total_weight)

        # Scale bonus if multiple top candidates agree
        if len(candidates) >= 3 and confidence > 0.5:
            confidence = min(1.0, confidence + 0.05)

        # Determine Verdict
        if confidence >= self.sufficient_threshold and not missing_facets:
            verdict = "SUFFICIENT"
        elif confidence >= self.partial_threshold:
            verdict = "PARTIAL"
        else:
            verdict = "INSUFFICIENT"

        best_cand = candidates[0]
        best_path = best_cand.get("file_path")
        best_name = best_cand.get("file_name")
        best_score = best_cand.get("rrf_score", 0.0)

        # Explanation
        if verdict == "SUFFICIENT":
            explanation = f"Đạt độ tin cậy cao ({confidence*100:.0f}%). Khớp đầy đủ các chiều {', '.join(active_list)}."
        elif verdict == "PARTIAL":
            explanation = f"Đạt độ tin cậy mức trung bình ({confidence*100:.0f}%). Còn thiếu hoặc yếu ở chiều: {', '.join(missing_facets) or 'độ tương đồng ngữ nghĩa'}."
        else:
            explanation = f"Độ tin cậy thấp ({confidence*100:.0f}%). Chưa thỏa mãn các điều kiện: {', '.join(missing_facets)}."

        latency_ms = round((time.time() - t0) * 1000.0, 2)

        return SufficiencyReport(
            confidence=round(confidence, 3),
            verdict=verdict,
            facet_satisfactions=facet_sats,
            missing_facets=missing_facets,
            best_candidate_path=best_path,
            best_candidate_name=best_name,
            best_candidate_score=round(best_score, 1),
            candidate_count=len(candidates),
            explanation=explanation,
            latency_ms=latency_ms,
        )


# Global singleton instance
sufficiency_evaluator = SufficiencyEvaluator()
