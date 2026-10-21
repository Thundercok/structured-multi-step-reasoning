"""
rat.engine.query_decomposer — Orthogonal Multi-Faceted Query Decomposition (MFQD).
Decomposes unstructured natural language into orthogonal operating system retrieval facets:
Q -> <Q_lex, Q_sem, Q_temp, Q_prov, Q_vis, Q_type, Q_neg>
"""

from __future__ import annotations

import logging
import re
import time
from dataclasses import asdict, dataclass, field
from typing import Any, Dict, List, Optional, Set

from rat.config import config
from rat.engine.context_engine import ContextEngine, context_engine as default_context_engine
from rat.engine.context_parser import ContextParser, ParsedContext, remove_accents
from rat.engine.slm import SLMEngine, slm_engine as default_slm_engine

logger = logging.getLogger("rat.decomposer")


@dataclass
class RetrievalPlan:
    """Structured blueprint for parallel multi-engine retrieval across OS facets."""
    raw_query: str
    active_facets: List[str] = field(default_factory=list)
    lexical_keywords: List[str] = field(default_factory=list)
    semantic_text: str = ""
    extensions: List[str] = field(default_factory=list)
    excluded_extensions: List[str] = field(default_factory=list)
    excluded_keywords: List[str] = field(default_factory=list)
    date_min: Optional[float] = None
    date_max: Optional[float] = None
    time_desc: Optional[str] = None
    source_app: Optional[str] = None
    source_domain: Optional[str] = None
    visual_tags: List[str] = field(default_factory=list)
    visual_desc: Optional[str] = None
    matched_concepts: List[str] = field(default_factory=list)
    is_complex: bool = False
    decomposition_mode: str = "fast_heuristic"
    plan_summary: str = ""
    latency_ms: float = 0.0

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


class QueryDecomposer:
    """
    Deconstructs natural language queries into orthogonal system primitives in < 3ms,
    with conditional SLM assistance for ambiguous multi-condition queries.
    """

    def __init__(
        self,
        slm_engine: Optional[SLMEngine] = None,
        context_engine: Optional[ContextEngine] = None,
    ) -> None:
        self.slm = slm_engine or default_slm_engine
        self.context_engine = context_engine or default_context_engine

    def decompose(self, raw_query: str, allow_slm: bool = False) -> RetrievalPlan:
        """Deconstruct query into faceted retrieval plan in < 3ms (or SLM-augmented if requested)."""
        t0 = time.time()
        cleaned_raw = raw_query.strip()
        if not cleaned_raw:
            return RetrievalPlan(raw_query="", plan_summary="Truy vấn rỗng")

        # 1. Base Context Parsing (Temporal, Types, Exclusions, Provenance, Visual)
        base_ctx = ContextParser.parse_query(cleaned_raw)

        # 2. Concept Ontology Enrichment
        enriched = self.context_engine.enrich_query(cleaned_raw)

        # Combine keywords
        all_keywords = list(enriched.expanded_keywords)
        for kw in base_ctx.keywords:
            if kw not in all_keywords:
                all_keywords.append(kw)

        # File extensions: user explicit takes priority, otherwise concept recommendation
        target_exts = base_ctx.extensions if base_ctx.extensions else (
            enriched.recommended_extensions if enriched.matched_concepts else []
        )

        # 3. Identify Active Facets
        active_facets: List[str] = []
        if all_keywords:
            active_facets.append("lexical")

        if enriched.semantic_query_text and len(enriched.semantic_query_text.strip()) > 0:
            active_facets.append("semantic")

        if base_ctx.date_min is not None or base_ctx.date_max is not None:
            active_facets.append("temporal")

        if base_ctx.source_app or base_ctx.source_domain:
            active_facets.append("provenance")

        if base_ctx.visual_concepts or any(e in [".png", ".jpg", ".jpeg", ".webp"] for e in target_exts):
            active_facets.append("visual")

        if target_exts:
            active_facets.append("type")

        if base_ctx.excluded_extensions or base_ctx.excluded_keywords:
            active_facets.append("negation")

        # 4. Complexity Heuristic
        q_norm = remove_accents(cleaned_raw)
        relational_terms = [
            "so sanh", "kiem tra", "doi chieu", "khac nhau", "khop", "hop dong",
            "bien lai", "gui kem", "gui qua", "dinh kem", "va", "chua ca"
        ]
        has_relational = any(re.search(rf"\b{t}\b", q_norm) for t in relational_terms)
        is_complex = len(active_facets) >= 3 or (has_relational and len(cleaned_raw.split()) >= 6)

        decomposition_mode = "fast_heuristic"

        # 5. Conditional SLM Enrichment (Active only if explicitly requested, complex, and available)
        if allow_slm and is_complex and config.use_slm and self.slm.is_model_installed():
            try:
                slm_decomp = self.slm.deconstruct_query(cleaned_raw)
                if slm_decomp:
                    decomposition_mode = "slm_augmented"
                    # Augment synonyms if provided by SLM
                    slm_syns = slm_decomp.get("expanded_synonyms", [])
                    for s in slm_syns:
                        if s and s not in all_keywords:
                            all_keywords.append(s)

                    # Augment extensions if missing
                    slm_exts = slm_decomp.get("file_extensions", [])
                    for e in slm_exts:
                        e_fmt = f".{e.lstrip('.')}"
                        if e_fmt not in target_exts:
                            target_exts.append(e_fmt)
                            if "type" not in active_facets:
                                active_facets.append("type")
            except Exception as e:
                logger.debug(f"SLM deconstruction skipped: {e}")

        # 6. Synthesize Plan Summary for CoT Explainability
        summary_parts = []
        if "lexical" in active_facets:
            summary_parts.append(f"Lexical: {len(all_keywords)} từ khóa ({', '.join(all_keywords[:4])})")
        if "semantic" in active_facets:
            summary_parts.append(f"Semantic: Khái niệm [{', '.join(enriched.matched_concepts or ['chung'])}]")
        if "temporal" in active_facets:
            summary_parts.append(f"Thời gian: {base_ctx.time_desc or 'Khoảng ngày cụ thể'}")
        if "provenance" in active_facets:
            source_desc = base_ctx.source_app or base_ctx.source_domain or "Nguồn tải về"
            summary_parts.append(f"Nguồn gốc OS: {source_desc}")
        if "visual" in active_facets:
            summary_parts.append(f"Thị giác: {', '.join(base_ctx.visual_concepts or ['ảnh/scan'])}")
        if "type" in active_facets:
            summary_parts.append(f"Định dạng: {', '.join(target_exts)}")
        if "negation" in active_facets:
            summary_parts.append(f"Loại trừ: {', '.join(base_ctx.excluded_extensions + base_ctx.excluded_keywords)}")

        plan_summary = " | ".join(summary_parts) if summary_parts else "Truy vấn tổng quát"
        latency_ms = round((time.time() - t0) * 1000.0, 2)

        return RetrievalPlan(
            raw_query=cleaned_raw,
            active_facets=active_facets,
            lexical_keywords=all_keywords,
            semantic_text=enriched.semantic_query_text,
            extensions=target_exts,
            excluded_extensions=base_ctx.excluded_extensions,
            excluded_keywords=base_ctx.excluded_keywords,
            date_min=base_ctx.date_min,
            date_max=base_ctx.date_max,
            time_desc=base_ctx.time_desc,
            source_app=base_ctx.source_app,
            source_domain=base_ctx.source_domain,
            visual_tags=base_ctx.visual_concepts,
            matched_concepts=enriched.matched_concepts,
            is_complex=is_complex,
            decomposition_mode=decomposition_mode,
            plan_summary=plan_summary,
            latency_ms=latency_ms,
        )


# Global singleton instance
query_decomposer = QueryDecomposer()
