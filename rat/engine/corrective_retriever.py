"""
rat.engine.corrective_retriever — Zero-Cloud Local Corrective Cascading Engine (Offline CRAG).
Diagnoses missing or low-confidence retrieval facets and executes targeted corrective recovery
without calling external commercial search engines.
"""

from __future__ import annotations

import logging
import time
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Optional, Tuple

from rat.config import config
from rat.crawler.db import Database
from rat.engine.embedder import LocalEmbedder, embedder as default_embedder
from rat.engine.hyde import HyDEEngine, hyde_engine as default_hyde
from rat.engine.multi_way_rrf import FacetResult, MultiWayRRF, multi_way_rrf as default_rrf
from rat.engine.query_decomposer import RetrievalPlan
from rat.engine.slm import SLMEngine, slm_engine as default_slm
from rat.engine.sufficiency_evaluator import SufficiencyReport
from rat.engine.vector_cache import VectorCache, vector_cache as default_vc

logger = logging.getLogger("rat.corrector")


@dataclass
class CorrectiveAction:
    """A single corrective strategy applied to recover from a retrieval gap."""
    facet: str
    action_type: str        # "widen_temporal" | "broaden_provenance" | "ocr_visual_fallback" | "relax_type" | "hyde_semantic" | "slm_reformulate"
    description: str
    new_candidates_count: int


@dataclass
class CorrectiveResult:
    """Outcome of the corrective retrieval pass."""
    actions: List[CorrectiveAction] = field(default_factory=list)
    recovered_candidates: List[Dict[str, Any]] = field(default_factory=list)
    corrected_plan: Optional[RetrievalPlan] = None
    iteration: int = 1
    latency_ms: float = 0.0


class CorrectiveRetriever:
    """
    Autonomous corrective retrieval engine that adapts search breadth and modalities
    based on sufficiency evaluation gaps.
    """

    def __init__(
        self,
        db: Optional[Database] = None,
        vector_cache: Optional[VectorCache] = None,
        embedder: Optional[LocalEmbedder] = None,
        hyde: Optional[HyDEEngine] = None,
        slm: Optional[SLMEngine] = None,
        rrf: Optional[MultiWayRRF] = None,
    ) -> None:
        self.db = db or Database(config.db_path)
        self.vector_cache = vector_cache or default_vc
        self.embedder = embedder or default_embedder
        self.hyde = hyde or default_hyde
        self.slm = slm or default_slm
        self.rrf = rrf or default_rrf

    def correct(
        self,
        plan: RetrievalPlan,
        report: SufficiencyReport,
        current_candidates: List[Dict[str, Any]],
        iteration: int = 1,
        allow_slm: bool = True,
    ) -> CorrectiveResult:
        """
        Execute targeted corrective recovery on missing or weak facets.
        """
        t0 = time.time()
        actions: List[CorrectiveAction] = []
        new_candidate_streams: List[FacetResult] = []

        # 1. Correct Temporal Gaps: Users often misremember time bounds
        if "temporal" in report.missing_facets and plan.date_min is not None:
            now = time.time()
            current_window = now - plan.date_min
            # Double window width (e.g. 7 days -> 14 days, or 30 days -> 60 days)
            widened_min = now - (current_window * 2.5)
            temporal_recs = self.db.search_candidates(
                keywords=plan.lexical_keywords[:3] if plan.lexical_keywords else [],
                extensions=plan.extensions or None,
                date_min=widened_min,
                date_max=None,
                limit=25
            )
            actions.append(CorrectiveAction(
                facet="temporal",
                action_type="widen_temporal",
                description=f"Mở rộng khung thời gian gấp 2.5x (từ {round(current_window/86400)} ngày lên {round(current_window*2.5/86400)} ngày)",
                new_candidates_count=len(temporal_recs),
            ))
            if temporal_recs:
                new_candidate_streams.append(FacetResult(
                    facet_name="temporal_widened",
                    candidates=temporal_recs,
                    weight=1.1,
                ))

        # 2. Correct Provenance Gaps: Search source keywords in FTS5
        if "provenance" in report.missing_facets and (plan.source_app or plan.source_domain):
            prov_term = plan.source_app or plan.source_domain or ""
            if prov_term:
                prov_recs = self.db.search_candidates(
                    keywords=[prov_term] + plan.lexical_keywords[:2],
                    extensions=plan.extensions or None,
                    limit=25
                )
                actions.append(CorrectiveAction(
                    facet="provenance",
                    action_type="broaden_provenance",
                    description=f"Chuyển sang quét FTS5 toàn diện với từ khóa nguồn gốc '{prov_term}'",
                    new_candidates_count=len(prov_recs),
                ))
                if prov_recs:
                    new_candidate_streams.append(FacetResult(
                        facet_name="provenance_broadened",
                        candidates=prov_recs,
                        weight=1.2,
                    ))

        # 3. Correct Visual Gaps: Fallback from visual tags to OCR text matching
        if "visual" in report.missing_facets and plan.visual_tags:
            ocr_recs = self.db.search_candidates(
                keywords=plan.visual_tags + plan.lexical_keywords[:2],
                extensions=[".png", ".jpg", ".jpeg", ".webp", ".pdf"],
                limit=25
            )
            actions.append(CorrectiveAction(
                facet="visual",
                action_type="ocr_visual_fallback",
                description=f"Quét xuyên thấu nội dung OCR/Scan với nhãn thị giác [{', '.join(plan.visual_tags)}]",
                new_candidates_count=len(ocr_recs),
            ))
            if ocr_recs:
                new_candidate_streams.append(FacetResult(
                    facet_name="visual_ocr_fallback",
                    candidates=ocr_recs,
                    weight=1.2,
                ))

        # 4. Correct Type Gaps: Relax strictly filtered extensions
        if "type" in report.missing_facets and plan.extensions:
            # Expand to kindred extensions (e.g. docx -> doc, pdf, txt)
            kindred_map = {
                ".docx": [".doc", ".pdf", ".txt", ".md"],
                ".xlsx": [".xls", ".csv"],
                ".pptx": [".ppt", ".pdf"],
                ".pdf": [".docx", ".txt"],
            }
            expanded_exts = list(plan.extensions)
            for e in plan.extensions:
                for ke in kindred_map.get(e, []):
                    if ke not in expanded_exts:
                        expanded_exts.append(ke)

            relaxed_recs = self.db.search_candidates(
                keywords=plan.lexical_keywords,
                extensions=expanded_exts,
                date_min=plan.date_min,
                date_max=plan.date_max,
                limit=25
            )
            actions.append(CorrectiveAction(
                facet="type",
                action_type="relax_type",
                description=f"Mở rộng định dạng tương đương: [{', '.join(expanded_exts)}]",
                new_candidates_count=len(relaxed_recs),
            ))
            if relaxed_recs:
                new_candidate_streams.append(FacetResult(
                    facet_name="type_relaxed",
                    candidates=relaxed_recs,
                    weight=1.0,
                ))

        # 5. Correct Semantic Gaps: Activate HyDE Speculative Expansion
        if allow_slm and len(plan.raw_query.strip()) >= 3 and ("semantic" in report.missing_facets or report.confidence < 0.45) and config.use_slm and self.slm.is_service_running():
            try:
                hyde_vec, hypo_doc, expanded_queries = self.hyde.get_hyde_query_vector(plan.raw_query)
                if hyde_vec is not None and hyde_vec.size > 0:
                    hyde_dense = self.vector_cache.search(
                        query_vector=hyde_vec,
                        extensions=plan.extensions or None,
                        limit=30
                    )
                    actions.append(CorrectiveAction(
                        facet="semantic",
                        action_type="hyde_semantic",
                        description="Kích hoạt HyDE tổng hợp tài liệu giả định và tính toán lại vector ngữ nghĩa",
                        new_candidates_count=len(hyde_dense),
                    ))
                    if hyde_dense:
                        new_candidate_streams.append(FacetResult(
                            facet_name="hyde_dense",
                            candidates=hyde_dense,
                            weight=1.3,
                            is_chunk_level=True,
                        ))
            except Exception as e:
                logger.debug(f"Corrective HyDE expansion note: {e}")

        # 6. Fuse Recovered Streams with Current Candidates
        if new_candidate_streams:
            # Create a stream from existing candidates
            current_stream = FacetResult(
                facet_name="prior_candidates",
                candidates=current_candidates,
                weight=1.0,
            )
            all_streams = [current_stream] + new_candidate_streams
            recovered_candidates = self.rrf.fuse(all_streams, top_k=max(25, len(current_candidates)))
        else:
            recovered_candidates = current_candidates

        latency_ms = round((time.time() - t0) * 1000.0, 2)

        return CorrectiveResult(
            actions=actions,
            recovered_candidates=recovered_candidates,
            iteration=iteration,
            latency_ms=latency_ms,
        )


# Global singleton instance
corrective_retriever = CorrectiveRetriever()
