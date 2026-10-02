"""
rat.engine.adaptive_reranker — E2: Intent-Aware & Adaptive Heuristic Reranker.

Solves the topical hijacking pathology of static_heuristic_v1:
In static_heuristic_v1, generic format keywords (e.g. 'slides', 'báo cáo', 'tài liệu')
receive an unconditional +80.0 stem bonus when matching a file named 'slides.pptx',
causing off-topic files (e.g. a VRPTW deck named slides.pptx) to rank #1 for 'slides calculus'
over the actual Calculus lectures (MA1521Chap*.pdf).

E2 separates Query Intents into:
- Format / Type Indicators (e.g. 'slides', 'pptx', 'bao cao', 'pdf', 'do an')
- Topical Core Keywords (e.g. 'calculus', 'giai tich', 'vrptw', 'machine learning')

Invariant & Guardrails:
1. Invariant: raw_score = 5.0 + sum(feats.values())
2. Version tag: "adaptive_e2"
3. Per-query topic state is local, thread-safe, and never leaks across invocations.
"""

from __future__ import annotations

import datetime
import logging
import re
from pathlib import Path
from typing import Any, Dict, List, Optional, Set, Tuple

from rat.engine.context_parser import ParsedContext, remove_accents
from rat.engine.reranker import SearchResultItem, format_file_size, format_relative_time

logger = logging.getLogger("rat.adaptive_reranker")

FORMAT_KEYWORDS: Set[str] = {
    "slide", "slides", "presentation", "thuyet trinh", "bai giang",
    "bao cao", "report", "do an", "de tai", "khoa luan", "luan van",
    "tai lieu", "file", "tep", "sach", "giao trinh", "de thi", "bai tap",
}


class AdaptiveE2Reranker:
    """
    E2 Intent-Aware Reranker that prevents format keywords from hijacking the search ranking
    away from the user's actual topical subject.
    """

    RANKER_VERSION = "adaptive_e2"

    def partition_keywords(self, keywords: List[str]) -> Tuple[List[str], List[str]]:
        """Partition context keywords into (topical_keywords, format_keywords)."""
        topical = []
        format_kw = []
        for kw in keywords:
            kw_norm = remove_accents(kw).strip().lower()
            if kw_norm in FORMAT_KEYWORDS:
                format_kw.append(kw)
            else:
                topical.append(kw)
        return topical, format_kw

    def compute_heuristic_score(
        self,
        doc: Dict[str, Any],
        context: ParsedContext,
    ) -> Tuple[float, List[str]]:
        """
        Compute multi-factor score with adaptive topical and format weighting.
        Preserves the 20-feature invariant: raw_score = 5.0 + sum(feats.values()).
        """
        score = 5.0
        reasons: List[str] = []
        feature_names = (
            "ext_hit", "ext_miss", "kw_stem", "kw_word", "kw_substr", "kw_content",
            "vec_sim", "sparse_only", "code_pen", "time_in", "time_near7",
            "time_near15", "time_far", "recent3", "recent14", "prov_app",
            "prov_dom", "visual", "facets3", "facets2",
        )
        features: Dict[str, float] = dict.fromkeys(feature_names, 0.0)

        def add(name: str, points: float) -> None:
            nonlocal score
            score += points
            features[name] += points

        file_name = doc.get("file_name", "")
        file_ext = doc.get("file_ext", "").lower()
        content = doc.get("content_text", "") or ""
        modified_at = doc.get("modified_at", 0)

        name_norm = remove_accents(file_name).lower()
        content_sample = content[:4000] if len(content) > 4000 else content
        content_norm = remove_accents(content_sample).lower()
        stem_norm = Path(name_norm).stem.lower()

        # 1. Extension match bonus & penalty
        if context.extensions:
            if file_ext in context.extensions:
                add("ext_hit", 35.0)
                reasons.append(f"Đúng định dạng {file_ext.upper()}")
            else:
                add("ext_miss", -30.0)

        # 2. Partition Topical vs Format Keywords
        topical_kws, format_kws = self.partition_keywords(context.keywords)
        vector_sim = doc.get("vector_similarity", 0.0)

        # Check topical match in filename and content
        topical_matched_name = []
        topical_matched_content = []
        for kw in topical_kws:
            kw_norm = remove_accents(kw).lower()
            if not kw_norm:
                continue
            if stem_norm == kw_norm:
                topical_matched_name.append(kw)
                add("kw_stem", 80.0)
            elif re.search(r"(?:^|[\s_\.\-])" + re.escape(kw_norm) + r"(?:$|[\s_\.\-])", name_norm):
                topical_matched_name.append(kw)
                add("kw_word", 55.0)
            elif len(kw_norm) >= 4 and kw_norm in name_norm:
                topical_matched_name.append(kw)
                add("kw_substr", 40.0)
            elif kw_norm in content_norm:
                topical_matched_content.append(kw)
                add("kw_content", 20.0)

        # 3. Format Keywords Evaluation (Intent-Aware)
        # If there ARE topical keywords, format keywords should only get full bonus if the document
        # has some topical relevance (either by matching topical keywords or having solid vector similarity).
        has_topical_signal = bool(topical_matched_name or topical_matched_content or vector_sim >= 0.40)

        format_matched_name = []
        format_matched_content = []
        for kw in format_kws:
            kw_norm = remove_accents(kw).lower()
            if not kw_norm:
                continue
            if stem_norm == kw_norm:
                format_matched_name.append(kw)
                if not topical_kws or has_topical_signal:
                    add("kw_stem", 80.0)
                else:
                    # Hijacking prevention: file named 'slides.pptx' with zero topic relevance
                    # gets moderated format alignment, not 80 points
                    add("kw_stem", 15.0)
            elif re.search(r"(?:^|[\s_\.\-])" + re.escape(kw_norm) + r"(?:$|[\s_\.\-])", name_norm):
                format_matched_name.append(kw)
                if not topical_kws or has_topical_signal:
                    add("kw_word", 55.0)
                else:
                    add("kw_word", 12.0)
            elif len(kw_norm) >= 4 and kw_norm in name_norm:
                format_matched_name.append(kw)
                if not topical_kws or has_topical_signal:
                    add("kw_substr", 40.0)
                else:
                    add("kw_substr", 10.0)
            elif kw_norm in content_norm:
                format_matched_content.append(kw)
                add("kw_content", 10.0)

        matched_kws_name = topical_matched_name + format_matched_name
        matched_kws_content = topical_matched_content + format_matched_content

        if matched_kws_name:
            reasons.append(f"Tên file có chứa '{', '.join(matched_kws_name)}'")
        if matched_kws_content:
            reasons.append(f"Nội dung nhắc đến '{', '.join(matched_kws_content)}'")

        # 4. Vector Dense Similarity match bonus
        if vector_sim > 0.40:
            pct = int(vector_sim * 100)
            # E2: If document matches topical content, vector similarity provides substantial boost
            mult = 40.0 if (topical_matched_content or not topical_kws) else 30.0
            add("vec_sim", vector_sim * mult)
            reasons.append(f"Khớp ngữ nghĩa Vector {pct}%")

        if doc.get("matched_sparse") and not matched_kws_content and not matched_kws_name:
            add("sparse_only", 10.0)
            reasons.append("Khớp chỉ mục từ khóa FTS5")

        # 5. Penalty for incidental source code matches
        is_code_file = file_ext in [".py", ".js", ".ts", ".html", ".css", ".json", ".sh", ".sql"]
        user_wants_code = any(e in [".py", ".js", ".ts", ".html", ".css", ".json", ".sh", ".sql"] for e in context.extensions)
        if is_code_file and not user_wants_code and not matched_kws_name and len(context.keywords) > 0:
            add("code_pen", -25.0)

        # 6. Soft Temporal Scoring
        if context.date_min is not None or context.date_max is not None:
            orig_min = context.date_min
            orig_max = context.date_max
            in_original_range = True
            if orig_min is not None and modified_at < orig_min:
                in_original_range = False
            if orig_max is not None and modified_at > orig_max:
                in_original_range = False

            if in_original_range:
                add("time_in", 25.0)
                reasons.append(f"Khớp mốc thời gian ({context.time_desc})")
            else:
                distance_seconds = 0
                if orig_min is not None and modified_at < orig_min:
                    distance_seconds = orig_min - modified_at
                if orig_max is not None and modified_at > orig_max:
                    distance_seconds = max(distance_seconds, modified_at - orig_max)
                days_away = distance_seconds / 86400
                if days_away <= 7:
                    add("time_near7", -5.0)
                elif days_away <= 15:
                    add("time_near15", -10.0)
                else:
                    add("time_far", -18.0)
        elif matched_kws_name or matched_kws_content or vector_sim > 0.5:
            now = datetime.datetime.now().timestamp()
            days_old = (now - modified_at) / 86400
            if days_old < 3:
                add("recent3", 8.0)
            elif days_old < 14:
                add("recent14", 4.0)

        # 7. Provenance match bonus
        source_app = getattr(context, "source_app", None)
        source_dom = getattr(context, "source_domain", None)
        if source_app or source_dom:
            content_lower = content_sample.lower()
            if source_app and source_app.lower() in content_lower:
                add("prov_app", 30.0)
            if source_dom and source_dom.lower() in content_lower:
                add("prov_dom", 25.0)

        # 8. Visual Concept Matching
        visual_tags = getattr(context, "visual_concepts", []) or []
        doc_visual = doc.get("visual_tags", []) or []
        if visual_tags and doc_visual:
            overlap = set(visual_tags).intersection(set(doc_visual))
            if overlap:
                add("visual", 30.0)

        # 9. Multi-stream intersection bonus
        matched_facets = doc.get("matched_facets", [])
        if len(matched_facets) >= 3:
            add("facets3", 20.0)
        elif len(matched_facets) == 2:
            add("facets2", 13.0)

        # Enforce exact clamping and feature invariant
        raw_score = score
        clamped_score = max(5.0, min(100.0, raw_score))
        doc["_raw_score"] = raw_score
        doc["_feats"] = features
        doc["_ranker_version"] = self.RANKER_VERSION

        return clamped_score, reasons

    def rerank(
        self,
        query: str,
        context: ParsedContext,
        candidates: List[Dict[str, Any]],
        top_k: int = 15,
        use_llm: bool = False,
    ) -> List[SearchResultItem]:
        """Rerank candidates using E2 intent-aware heuristic scoring."""
        scored_items: List[Tuple[float, Dict[str, Any], List[str], str]] = []

        for doc in candidates:
            score, reasons = self.compute_heuristic_score(doc, context)
            if doc.get("best_chunk_text"):
                raw_chunk = doc["best_chunk_text"]
                snippet = raw_chunk[:240] + ("..." if len(raw_chunk) > 240 else "")
            else:
                snippet = (doc.get("content_text", "") or "")[:240]

            reason_text = " • ".join(reasons) if reasons else f"Tệp phù hợp với ngữ cảnh ({doc.get('file_ext', '').upper()})"
            scored_items.append((score, doc, reasons, snippet))

        scored_items.sort(key=lambda x: x[0], reverse=True)
        top_items = scored_items[:top_k]

        results = []
        for score, doc, reasons, snippet in top_items:
            reason_text = " • ".join(reasons) if reasons else f"Tệp phù hợp với ngữ cảnh ({doc.get('file_ext', '').upper()})"
            item = SearchResultItem(
                file_path=doc["file_path"],
                file_name=doc["file_name"],
                file_ext=doc.get("file_ext", ""),
                file_size=doc.get("file_size", 0),
                modified_at=doc.get("modified_at", 0),
                score=score,
                explanation=reason_text,
                snippet=snippet,
                version_info=None,
                raw_scores={
                    "bm25": doc.get("bm25"),
                    "cosine": doc.get("vector_similarity"),
                    "mrrf": doc.get("rrf_score"),
                    "raw_score": doc.get("_raw_score", score),
                    "feats": doc.get("_feats", {}),
                    "ranker_version": self.RANKER_VERSION,
                },
            )
            results.append(item)

        return results
