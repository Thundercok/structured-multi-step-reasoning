"""
rat.engine.hybrid_search — FR-CoT (Faceted Retrieval Chain-of-Thought) Search Coordinator.
Coordinates multi-phase reasoning:
Phase 1: Faceted Query Decomposition
Phase 2: Parallel Multi-Engine Retrieval & Adaptive Multi-Way RRF
Phase 3: Deterministic Information Sufficiency Evaluation
Phase 4: Zero-Cloud Corrective Cascading Loop
Phase 5: Evidence-Grounded Reranking with Full Reasoning Trace
"""

from __future__ import annotations

import logging
import time
from typing import Any, Dict, List, Optional

from rat.config import config
from rat.crawler.db import Database
from rat.engine.context_engine import context_engine
from rat.engine.context_parser import ContextParser, ParsedContext
from rat.engine.corrective_retriever import CorrectiveRetriever, corrective_retriever
from rat.engine.embedder import embedder
from rat.engine.hyde import hyde_engine
from rat.engine.llm_client import LLMClient
from rat.engine.multi_way_rrf import FacetResult, MultiWayRRF, multi_way_rrf
from rat.engine.query_decomposer import QueryDecomposer, RetrievalPlan, query_decomposer
from rat.engine.reasoning_trace import ReasoningTrace
from rat.engine.reranker import Reranker, SearchResultItem
from rat.engine.rrf import rrf_fuser
from rat.engine.slm import slm_engine
from rat.engine.sufficiency_evaluator import SufficiencyEvaluator, SufficiencyReport, sufficiency_evaluator
from rat.engine.vector_cache import VectorCache, vector_cache

logger = logging.getLogger("rat.search")


class SearchEngine:
    """FR-CoT Multi-Modal Search Engine combining OS Facet Decomposition, M-RRF, and Corrective Reasoning."""

    def __init__(self, db: Optional[Database] = None) -> None:
        self.db = db or Database(config.db_path)
        self.llm = LLMClient()
        self.slm = slm_engine
        self.embedder = embedder
        self.hyde = hyde_engine
        self.rrf = rrf_fuser
        self.multi_way_rrf = multi_way_rrf
        self.reranker = Reranker(self.llm)
        self.vector_cache = vector_cache if db is None else VectorCache(self.db)
        self.context_engine = context_engine
        self.decomposer = query_decomposer
        self.evaluator = sufficiency_evaluator
        self.corrector = CorrectiveRetriever(
            db=self.db,
            vector_cache=self.vector_cache,
            embedder=self.embedder,
            hyde=self.hyde,
            slm=self.slm,
            rrf=self.multi_way_rrf,
        )

    def search(
        self,
        query: str,
        limit: int = 15,
        use_hyde: bool = True,
        use_vector: bool = True,
    ) -> Dict[str, Any]:
        """
        Execute end-to-end FR-CoT (Faceted Retrieval Chain-of-Thought) Search.
        """
        start_t = time.time()
        clean_q = query.strip()
        trace = ReasoningTrace(raw_query=query)

        # -----------------------------------------------------------------
        # Phase 1: Faceted Query Decomposition (< 3ms)
        # -----------------------------------------------------------------
        t_phase1 = time.time()
        plan = self.decomposer.decompose(clean_q, allow_slm=False)
        p1_latency = (time.time() - t_phase1) * 1000.0

        trace.add_step(
            phase="decompose",
            thought=f"Phân rã câu hỏi thành {len(plan.active_facets)} chiều OS trực giao: {', '.join(plan.active_facets)}",
            action=f"decompose(raw_query='{clean_q}')",
            observation=plan.plan_summary,
            evaluation=f"Chế độ: {plan.decomposition_mode} | Độ phức tạp: {'Cao (Multi-facet)' if plan.is_complex else 'Tiêu chuẩn'}",
            latency_ms=p1_latency,
        )

        context = ContextParser.parse_query(clean_q)
        # Copy provenance and visual tags to context
        context.source_app = plan.source_app
        context.source_domain = plan.source_domain
        context.visual_concepts = plan.visual_tags

        # Soft Temporal: Widen retrieval window by ±15 days to catch files edited
        # slightly outside the user's stated range (e.g. "tháng 8" file edited Sept 14).
        # The Reranker will apply fine-grained decay scoring to prefer in-range files.
        TEMPORAL_BUFFER_SECONDS = 15 * 86400  # 15 days
        if plan.date_min is not None:
            plan.date_min = plan.date_min - TEMPORAL_BUFFER_SECONDS
        if plan.date_max is not None:
            plan.date_max = plan.date_max + TEMPORAL_BUFFER_SECONDS

        # -----------------------------------------------------------------
        # Phase 2: Parallel Multi-Engine Retrieval & Adaptive M-RRF (< 40ms)
        # -----------------------------------------------------------------
        t_phase2 = time.time()
        facet_streams: List[FacetResult] = []

        # 2a. Sparse Lexical Search (FTS5 BM25)
        sparse_candidates = self.db.search_candidates(
            keywords=plan.lexical_keywords,
            extensions=plan.extensions or None,
            excluded_extensions=plan.excluded_extensions or None,
            date_min=plan.date_min,
            date_max=plan.date_max,
            limit=45
        )
        if sparse_candidates:
            facet_streams.append(FacetResult(
                facet_name="lexical",
                candidates=sparse_candidates,
                weight=1.0,
            ))

        # 2b. Dense Vector Search (VectorCache in-memory dot product)
        dense_chunk_candidates: List[Dict[str, Any]] = []
        hypo_text = None
        if use_vector and len(clean_q) >= 3:
            query_vector = None
            should_use_hyde = use_hyde and config.use_slm and len(clean_q.split()) >= 4
            if should_use_hyde and self.slm.is_service_running():
                query_vector, hypo_text, _ = self.hyde.get_hyde_query_vector(clean_q)

            if query_vector is None or query_vector.size == 0:
                query_vector = self.embedder.embed_query(plan.semantic_text or clean_q)

            if query_vector is not None and query_vector.size > 0:
                dense_chunk_candidates = self.vector_cache.search(
                    query_vector=query_vector,
                    extensions=plan.extensions or None,
                    excluded_extensions=plan.excluded_extensions or None,
                    date_min=plan.date_min,
                    date_max=plan.date_max,
                    limit=45
                )
                if dense_chunk_candidates:
                    facet_streams.append(FacetResult(
                        facet_name="semantic",
                        candidates=dense_chunk_candidates,
                        weight=1.2,
                        is_chunk_level=True,
                    ))

        # 2c. OS Provenance Retrieval (WhereFroms & Quarantine App)
        prov_candidates: List[Dict[str, Any]] = []
        if "provenance" in plan.active_facets:
            prov_candidates = self.db.search_by_provenance(
                source_app=plan.source_app,
                source_domain=plan.source_domain,
                extensions=plan.extensions or None,
                date_min=plan.date_min,
                date_max=plan.date_max,
                limit=30
            )
            if prov_candidates:
                facet_streams.append(FacetResult(
                    facet_name="provenance",
                    candidates=prov_candidates,
                    weight=1.5,
                ))

        # 2d. Multimodal Visual Retrieval (Apple Vision OCR & Taxonomy)
        vis_candidates: List[Dict[str, Any]] = []
        if "visual" in plan.active_facets and plan.visual_tags:
            vis_candidates = self.db.search_by_vision_tags(
                tags=plan.visual_tags,
                extensions=plan.extensions or None,
                date_min=plan.date_min,
                date_max=plan.date_max,
                limit=30
            )
            if vis_candidates:
                facet_streams.append(FacetResult(
                    facet_name="visual",
                    candidates=vis_candidates,
                    weight=1.4,
                ))

        # Fuse all streams with Multi-Way RRF
        if facet_streams:
            fused_candidates = self.multi_way_rrf.fuse(facet_streams, top_k=limit * 3)
        else:
            fused_candidates = []

        p2_latency = (time.time() - t_phase2) * 1000.0

        trace.add_step(
            phase="retrieve",
            thought=f"Khai thác {len(facet_streams)} luồng dữ liệu độc lập (Lexical: {len(sparse_candidates)}, Dense: {len(dense_chunk_candidates)}, Provenance: {len(prov_candidates)}, Visual: {len(vis_candidates)})",
            action=f"fuse_multi_way_rrf(streams={len(facet_streams)}, k=60)",
            observation=f"Hội tụ {len(fused_candidates)} ứng viên hợp nhất sau khử trùng lặp",
            evaluation=f"M-RRF dung hợp thành công. Điểm dẫn đầu: {fused_candidates[0].get('rrf_score', 0):.1f} pts" if fused_candidates else "Chưa tìm thấy ứng viên",
            latency_ms=p2_latency,
        )

        # -----------------------------------------------------------------
        # Phase 3: Deterministic Information Sufficiency Evaluation (< 2ms)
        # -----------------------------------------------------------------
        t_phase3 = time.time()
        report = self.evaluator.evaluate(plan, fused_candidates)
        p3_latency = (time.time() - t_phase3) * 1000.0

        trace.add_step(
            phase="evaluate",
            thought="Đánh giá mức độ bao phủ và thỏa mãn các điều kiện OS của tập ứng viên",
            action=f"evaluate_sufficiency(threshold={self.evaluator.sufficient_threshold})",
            observation=f"Verdict: {report.verdict} (Confidence: {report.confidence*100:.0f}%)",
            evaluation=report.explanation,
            latency_ms=p3_latency,
        )

        # -----------------------------------------------------------------
        # Phase 4: Zero-Cloud Corrective Cascading Loop (Conditional)
        # -----------------------------------------------------------------
        correction_count = 0
        if not report.is_sufficient and (report.missing_facets or report.confidence < 0.68) and len(clean_q) >= 3:
            t_phase4 = time.time()
            correct_res = self.corrector.correct(
                plan=plan,
                report=report,
                current_candidates=fused_candidates,
                iteration=1,
                allow_slm=use_hyde and len(clean_q) >= 3,
            )
            correction_count = len(correct_res.actions)
            fused_candidates = correct_res.recovered_candidates
            # Re-evaluate with recovered candidates
            report = self.evaluator.evaluate(plan, fused_candidates)
            p4_latency = (time.time() - t_phase4) * 1000.0

            action_descs = [f"{a.facet}: {a.description}" for a in correct_res.actions]
            trace.add_step(
                phase="correct",
                thought="Kích hoạt cascade tự phục hồi cục bộ cho các chiều còn thiếu",
                action=f"corrective_cascade(actions={len(correct_res.actions)})",
                observation=" | ".join(action_descs) if action_descs else "Không có hành động bổ sung",
                evaluation=f"Sau phục hồi: {report.verdict} (Confidence: {report.confidence*100:.0f}%, {len(fused_candidates)} ứng viên)",
                latency_ms=p4_latency,
            )

        # -----------------------------------------------------------------
        # Phase 5: Evidence-Grounded Reranking with CoT Synthesis (< 15ms)
        # -----------------------------------------------------------------
        t_phase5 = time.time()
        results = self.reranker.rerank(
            query=query,
            context=context,
            candidates=fused_candidates,
            top_k=limit,
            use_llm=False,
            trace=trace,
        )
        p5_latency = (time.time() - t_phase5) * 1000.0

        top_file_info = f"Top: '{results[0].file_name}' (Điểm: {results[0].score:.1f})" if results else "Không có kết quả"
        trace.add_step(
            phase="rerank",
            thought="Tái xếp hạng đa nhân tố kết hợp kiểm tra phả hệ phiên bản và tạo bằng chứng giải thích",
            action=f"rerank(top_k={limit}, candidates={len(fused_candidates)})",
            observation=f"Xuất xưởng {len(results)} kết quả chất lượng cao nhất. {top_file_info}",
            evaluation="Hoàn tất chuỗi suy luận FR-CoT, sẵn sàng trình bày",
            latency_ms=p5_latency,
        )

        trace.finalize(
            confidence=report.confidence,
            is_sufficient=report.is_sufficient,
            correction_count=correction_count,
        )

        latency_ms = round((time.time() - start_t) * 1000.0, 1)

        enriched = self.context_engine.enrich_query(clean_q)

        return {
            "query": query,
            "results": results,
            "latency_ms": latency_ms,
            "parsed_context": context.to_dict(),
            "ai_intent_summary": enriched.ai_intent_summary,
            "matched_concepts": plan.matched_concepts,
            "expanded_keywords": plan.lexical_keywords,
            "hyde_passage": hypo_text,
            "total_candidates": len(fused_candidates),
            "sparse_count": len(sparse_candidates),
            "dense_count": len(dense_chunk_candidates),
            # FR-CoT Enhanced Outputs
            "reasoning_trace": trace,
            "sufficiency_report": report.to_dict(),
            "plan": plan.to_dict(),
        }
