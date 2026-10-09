"""
rat.engine.reranker — Multi-factor ranking, context snippet extraction, and explainable AI reasoning.
"""

from __future__ import annotations

import datetime
import json
import logging
import re
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from rat.engine.context_parser import ParsedContext, remove_accents
from rat.engine.llm_client import LLMClient

logger = logging.getLogger("rat.reranker")


def format_relative_time(timestamp: float) -> str:
    """Return friendly relative time string in Vietnamese (e.g. '2 giờ trước', 'Hôm qua')."""
    now = datetime.datetime.now()
    dt = datetime.datetime.fromtimestamp(timestamp)
    diff = now - dt

    if diff.total_seconds() < 60:
        return "Vừa xong"
    elif diff.total_seconds() < 3600:
        mins = int(diff.total_seconds() / 60)
        return f"{mins} phút trước"
    elif diff.total_seconds() < 86400:
        hours = int(diff.total_seconds() / 3600)
        return f"{hours} giờ trước"
    elif diff.days == 1:
        return f"Hôm qua, {dt.strftime('%H:%M')}"
    elif diff.days < 7:
        return f"{diff.days} ngày trước"
    elif diff.days < 30:
        weeks = int(diff.days / 7)
        return f"{weeks} tuần trước"
    elif diff.days < 365:
        months = int(diff.days / 30)
        return f"{months} tháng trước"
    else:
        return dt.strftime("%d/%m/%Y")


def format_file_size(size_bytes: int) -> str:
    """Format bytes into readable size."""
    if size_bytes < 1024:
        return f"{size_bytes} B"
    elif size_bytes < 1024 * 1024:
        return f"{size_bytes / 1024:.1f} KB"
    elif size_bytes < 1024 * 1024 * 1024:
        return f"{size_bytes / (1024 * 1024):.1f} MB"
    else:
        return f"{size_bytes / (1024 * 1024 * 1024):.1f} GB"


class SearchResultItem:
    """Structured search result with context explanation, VGC verification, and metadata."""

    def __init__(
        self,
        file_path: str,
        file_name: str,
        file_ext: str,
        file_size: int,
        modified_at: float,
        score: float,
        explanation: str,
        snippet: str,
        version_info: Optional[Dict[str, Any]] = None,
        raw_scores: Optional[Dict[str, Any]] = None,
        verified: bool = False,
        page_num: Optional[int] = None,
        vgc_certificate: Optional[Dict[str, Any]] = None,
    ) -> None:
        self.file_path = file_path
        self.file_name = file_name
        self.file_ext = file_ext
        self.file_size = file_size
        self.file_size_formatted = format_file_size(file_size)
        self.modified_at = modified_at
        self.modified_formatted = format_relative_time(modified_at)
        self.score = score
        self.explanation = explanation
        self.snippet = snippet
        self.version_info = version_info
        self.raw_scores = dict(raw_scores or {})
        self.verified = verified
        self.page_num = page_num
        self.vgc_certificate = vgc_certificate

    def to_citation(self) -> Dict[str, Any]:
        """Convert search result item into a grounded citation for Chat & QuickLook."""
        return {
            "file_path": self.file_path,
            "file_name": self.file_name,
            "page": self.page_num or 1,
            "snippet": self.snippet or self.explanation,
        }

    def to_dict(self) -> Dict[str, Any]:
        return {
            "file_path": self.file_path,
            "file_name": self.file_name,
            "file_ext": self.file_ext,
            "file_size": self.file_size,
            "file_size_formatted": self.file_size_formatted,
            "modified_at": self.modified_at,
            "modified_formatted": self.modified_formatted,
            "score": round(self.score, 2),
            "explanation": self.explanation,
            "snippet": self.snippet,
            "version_info": self.version_info,
            "raw_scores": self.raw_scores,
            "verified": self.verified,
            "page_num": self.page_num,
            "vgc_certificate": self.vgc_certificate,
        }


class Reranker:
    """Reranker with heuristic scoring and LLM reasoning."""

    def __init__(self, llm_client: Optional[LLMClient] = None) -> None:
        self.llm = llm_client or LLMClient()

    def extract_best_snippet(
        self,
        content: str,
        keywords: List[str],
        max_length: int = 240
    ) -> str:
        """Extract a representative text snippet containing query keywords."""
        if not content:
            return ""

        content_clean = re.sub(r"\s+", " ", content).strip()
        if not keywords:
            return content_clean[:max_length] + ("..." if len(content_clean) > max_length else "")

        # Find first occurrence of any keyword
        content_norm = remove_accents(content_clean)
        best_pos = -1
        for kw in keywords:
            kw_norm = remove_accents(kw)
            pos = content_norm.find(kw_norm)
            if pos != -1:
                if best_pos == -1 or pos < best_pos:
                    best_pos = pos

        if best_pos == -1:
            return content_clean[:max_length] + ("..." if len(content_clean) > max_length else "")

        start = max(0, best_pos - 60)
        end = min(len(content_clean), start + max_length)
        snippet = content_clean[start:end]

        prefix = "..." if start > 0 else ""
        suffix = "..." if end < len(content_clean) else ""
        return prefix + snippet.strip() + suffix

    def compute_heuristic_score(
        self,
        doc: Dict[str, Any],
        context: ParsedContext
    ) -> Tuple[float, List[str]]:
        """
        Compute multi-factor score and reasons why this document matches.
        Prioritizes exact filename matches, file extension alignment, and semantic chunks.
        """
        score = 5.0
        reasons = []
        feature_names = (
            "ext_hit", "ext_miss", "kw_stem", "kw_word", "kw_substr", "kw_content",
            "vec_sim", "sparse_only", "code_pen", "time_in", "time_near7",
            "time_near15", "time_far", "recent3", "recent14", "prov_app",
            "prov_dom", "visual", "facets3", "facets2",
            "study_doc", "sem_dir", "course_code_dir", "slide_lecture",
            "acronym_match",
        )
        features = dict.fromkeys(feature_names, 0.0)

        def add(name: str, points: float) -> None:
            nonlocal score
            score += points
            features[name] = features.get(name, 0.0) + points

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

        # 2. Filename keyword & stem matches (Top Priority)
        matched_kws_name = []
        matched_kws_content = []

        for kw in context.keywords:
            kw_norm = remove_accents(kw).lower()
            if not kw_norm:
                continue

            # Exact stem match (e.g. "vietnam" == "vietnam")
            if stem_norm == kw_norm:
                matched_kws_name.append(kw)
                add("kw_stem", 80.0)
            elif re.search(r"(?:^|[\s_\.\-])" + re.escape(kw_norm) + r"(?:$|[\s_\.\-])", name_norm):
                matched_kws_name.append(kw)
                add("kw_word", 55.0)
            elif len(kw_norm) >= 4 and kw_norm in name_norm:
                matched_kws_name.append(kw)
                add("kw_substr", 40.0)
            elif kw_norm in content_norm:
                matched_kws_content.append(kw)
                add("kw_content", 15.0)

        if matched_kws_name:
            reasons.append(f"Tên file có chứa '{', '.join(matched_kws_name)}'")
        if matched_kws_content:
            reasons.append(f"Nội dung nhắc đến '{', '.join(matched_kws_content)}'")

        # 3. Vector Dense Similarity match bonus
        vector_sim = doc.get("vector_similarity", 0.0)
        if vector_sim > 0.40:
            pct = int(vector_sim * 100)
            add("vec_sim", vector_sim * 35.0)
            reasons.append(f"Khớp ngữ nghĩa Vector {pct}%")

        if doc.get("matched_sparse") and not matched_kws_content and not matched_kws_name:
            add("sparse_only", 10.0)
            reasons.append("Khớp chỉ mục từ khóa FTS5")

        # 4. Penalty for incidental source code matches when user is searching for documents
        is_code_file = file_ext in [".py", ".js", ".ts", ".html", ".css", ".json", ".sh", ".sql"]
        user_wants_code = any(e in [".py", ".js", ".ts", ".html", ".css", ".json", ".sh", ".sql"] for e in context.extensions)
        if is_code_file and not user_wants_code and not matched_kws_name and len(context.keywords) > 0:
            add("code_pen", -25.0)

        # 5. Soft Temporal Scoring with decay (replaces hard in/out binary penalty)
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
                # Decay: closer to original range = smaller penalty
                distance_seconds = 0
                if orig_min is not None and modified_at < orig_min:
                    distance_seconds = orig_min - modified_at
                if orig_max is not None and modified_at > orig_max:
                    distance_seconds = max(distance_seconds, modified_at - orig_max)
                days_away = distance_seconds / 86400
                # 0-7 days away: small penalty, 7-15 days: moderate penalty
                if days_away <= 7:
                    add("time_near7", -5.0)
                    reasons.append(f"Gần mốc thời gian ({context.time_desc}, lệch {days_away:.0f} ngày)")
                elif days_away <= 15:
                    add("time_near15", -10.0)
                    reasons.append(f"Lân cận mốc thời gian ({context.time_desc}, lệch {days_away:.0f} ngày)")
                else:
                    add("time_far", -18.0)
        elif matched_kws_name or matched_kws_content or vector_sim > 0.5:
            # Subtle recency boost for relevant recently modified files
            now = datetime.datetime.now().timestamp()
            days_old = (now - modified_at) / 86400
            if days_old < 3:
                add("recent3", 8.0)
            elif days_old < 14:
                add("recent14", 4.0)

        # 6. Provenance match bonus
        source_app = getattr(context, "source_app", None)
        source_dom = getattr(context, "source_domain", None)
        if source_app or source_dom:
            content_lower = content_sample.lower()
            if source_app and source_app.lower() in content_lower:
                add("prov_app", 30.0)
                reasons.append(f"Nguồn gốc từ ứng dụng {source_app}")
            elif source_dom and source_dom.lower() in content_lower:
                add("prov_dom", 25.0)
                reasons.append(f"Nguồn tải từ {source_dom}")

        # 7. Visual Taxonomy & OCR match bonus
        visual_concepts = getattr(context, "visual_concepts", []) or []
        if visual_concepts:
            content_lower = content_sample.lower()
            matched_visual = [v for v in visual_concepts if v.lower() in content_lower]
            if matched_visual:
                add("visual", 25.0)
                reasons.append(f"Khớp nhãn thị giác [{', '.join(matched_visual)}]")

        # 8. Semester & Slide-Aware Ranking for Academic Course Bridge
        file_path = doc.get("file_path", "")
        path_norm = remove_accents(file_path).lower()

        # Detect academic course intent from keywords, course codes, or curriculum aliases
        course_codes = [kw for kw in context.keywords if re.fullmatch(r"\d{5,7}|[a-z]\d{5,6}", kw.lower())]
        course_aliases = getattr(context, "course_aliases", []) or []
        is_study_intent = bool(course_codes) or bool(course_aliases) or any(
            k in name_norm or any(k in kw.lower() for kw in context.keywords)
            for k in ["tai lieu", "tài liệu", "slide", "bai giang", "bài giảng", "lab", "assignment", "mon hoc", "môn học"]
        )

        if is_study_intent:
            # 8a. Study document format bonus (.pdf, .pptx, .docx, .ipynb, etc.)
            study_exts = {".pdf", ".pptx", ".ppt", ".docx", ".doc", ".ipynb", ".xlsx"}
            if file_ext in study_exts:
                add("study_doc", 25.0)
                reasons.append(f"Tài liệu học tập ({file_ext.upper()})")

            # 8b. Semester directory pattern bonus (e.g. HK241, 2024-2025, Hoc_Ky)
            sem_match = re.search(r"(?:^|[/\\])(?:hk\d{2,3}|(?:20)?2[3-6][-_](?:20)?2[4-7]|hoc[-_ ]?ky|semester|sem[-_ ]?\d|mon[-_ ]?hoc)(?:[/\\]|$)", path_norm)
            if sem_match:
                add("sem_dir", 35.0)
                reasons.append("Thư mục học kỳ (HK / Niên khóa)")

            # 8c. Course Code or Course Alias in directory path bonus
            matched_code = False
            if course_codes and any(code in path_norm for code in course_codes):
                matched_code = True
            elif course_aliases:
                clean_aliases = [remove_accents(a).lower().replace(" ", "") for a in course_aliases if len(a) >= 4]
                path_compact = path_norm.replace(" ", "")
                if any(ca in path_compact for ca in clean_aliases):
                    matched_code = True

            if matched_code:
                add("course_code_dir", 30.0)
                reasons.append("Thư mục đúng mã học phần / Tên môn tương đương")

            # 8d. Slide, lecture, lab, assignment naming bonus
            is_slide_or_lab = bool(re.search(r"(?:^|[\s_\.\-])(?:slide|lecture|chuong|ch\d*|bai[-_ ]?giang|bai[-_ ]?tap|lab\d*|assignment|gk|ck|de[-_ ]?thi)", name_norm))
            if is_slide_or_lab:
                add("slide_lecture", 30.0)
                reasons.append("Bài giảng / Slide / Lab học phần")

        # 8e. Initials-based Acronym Matching with Typo Tolerance (e.g. pttkht or pttkth)
        from rat.engine.curriculum_mapper import generate_acronym, damerau_levenshtein_le_1
        matched_acronyms = []
        for kw in context.keywords:
            kw_norm = remove_accents(kw).lower()
            if 2 <= len(kw_norm) <= 7 and kw_norm.isalpha():
                matched_for_kw = False
                for part in Path(file_path).parts:
                    part_acr = generate_acronym(part)
                    if part_acr:
                        if part_acr == kw_norm:
                            matched_acronyms.append(f"{kw} → {part}")
                            add("acronym_match", 60.0)
                            matched_for_kw = True
                            break
                        elif len(kw_norm) >= 4 and damerau_levenshtein_le_1(kw_norm, part_acr):
                            matched_acronyms.append(f"{kw} ~ {part_acr} ({part})")
                            add("acronym_match", 55.0)
                            matched_for_kw = True
                            break
                    part_tokens = [t.lower() for t in re.findall(r"[A-Za-z0-9]+", part)]
                    for pt in part_tokens:
                        if pt == kw_norm:
                            matched_acronyms.append(f"{kw} ∈ {part}")
                            add("acronym_match", 60.0)
                            matched_for_kw = True
                            break
                        elif len(kw_norm) >= 4 and damerau_levenshtein_le_1(kw_norm, pt):
                            matched_acronyms.append(f"{kw} ~ {pt} ({part})")
                            add("acronym_match", 55.0)
                            matched_for_kw = True
                            break
                    if matched_for_kw:
                        break
                if matched_for_kw:
                    break
        if matched_acronyms:
            reasons.append(f"Khớp viết tắt môn học ({', '.join(matched_acronyms)})")

        # 9. Multi-Facet Convergence Bonus
        matched_facets = doc.get("matched_facets", [])
        if len(matched_facets) >= 3:
            add("facets3", 15.0)
            reasons.append(f"Hội tụ đa tầng ({len(matched_facets)} chiều: {', '.join(matched_facets)})")
        elif len(matched_facets) == 2:
            add("facets2", 8.0)

        # Clamp score to 0..100
        doc["_raw_score"] = score
        doc["_feats"] = features
        final_score = max(5.0, min(100.0, score))
        return final_score, reasons

    def rerank(
        self,
        query: str,
        context: ParsedContext,
        candidates: List[Dict[str, Any]],
        top_k: int = 15,
        use_llm: bool = False,
        trace: Optional[Any] = None,
    ) -> List[SearchResultItem]:
        """
        Score, filter, and format candidate search results.
        """
        scored_items: List[Tuple[float, Dict[str, Any], List[str], str]] = []

        for doc in candidates:
            score, reasons = self.compute_heuristic_score(doc, context)

            # Prefer the exact matching semantic chunk snippet if available
            if doc.get("best_chunk_text"):
                raw_chunk = doc["best_chunk_text"]
                snippet = raw_chunk[:240] + ("..." if len(raw_chunk) > 240 else "")
            else:
                snippet = self.extract_best_snippet(doc.get("content_text", ""), context.keywords)

            # Generate natural language explanation
            if reasons:
                explanation = " • ".join(reasons)
            else:
                rel_time = format_relative_time(doc.get("modified_at", 0))
                explanation = f"Tệp sửa đổi {rel_time}"

            scored_items.append((score, doc, reasons, snippet))

        # Sort descending by score
        scored_items.sort(key=lambda x: x[0], reverse=True)
        top_items = scored_items[:top_k]

        results = []
        from rat.crawler.dedup import dedup_engine

        for score, doc, reasons, snippet in top_items:
            # Check version tree info for top items
            version_info = None
            try:
                version_info = dedup_engine.get_document_version_info(doc["file_path"])
                if version_info and version_info.get("total_versions", 0) > 1:
                    total_v = version_info["total_versions"]
                    if version_info.get("is_latest"):
                        reasons.insert(0, f"🎯 Bản mới nhất (Có {total_v} bản sửa đổi)")
                    else:
                        reasons.insert(0, f"⚠️ Bản cũ hơn (Bản mới: {version_info.get('latest_file_name')})")
            except Exception:
                pass

            # VGC Fail-Closed Verification on snippet
            verified = False
            cert_dict = None
            page_num = doc.get("page_number") or doc.get("chunk_page") or 1
            content_sample = doc.get("content_text") or doc.get("best_chunk_text") or ""
            if snippet and content_sample:
                try:
                    from rat.engine.vgc import VGCCertificate, VGCVerificationStatus, VGCVerifier
                    cert = VGCCertificate(
                        claim=snippet,
                        witness=snippet[:60],
                        source_file=doc["file_path"],
                        source_page=page_num,
                        source_snippet=snippet,
                    )
                    v_res = VGCVerifier.verify_document_fact(cert, content_sample)
                    if v_res.status == VGCVerificationStatus.VALID:
                        verified = True
                        cert_dict = {
                            "claim": cert.claim,
                            "witness": cert.witness,
                            "verification_ms": v_res.verification_ms,
                        }
                        reasons.append("✓ Xác thực VGC")
                except Exception as e:
                    logger.debug(f"VGC document verification error: {e}")

            # Build user friendly reason explanation
            reason_text = " • ".join(reasons) if reasons else f"Tệp phù hợp với ngữ cảnh ({doc['file_ext'].upper()})"
            item = SearchResultItem(
                file_path=doc["file_path"],
                file_name=doc["file_name"],
                file_ext=doc["file_ext"],
                file_size=doc["file_size"],
                modified_at=doc["modified_at"],
                score=score,
                explanation=reason_text,
                snippet=snippet,
                version_info=version_info,
                raw_scores={
                    "bm25": doc.get("bm25"),
                    "cosine": doc.get("vector_similarity"),
                    "mrrf": doc.get("rrf_score"),
                    "raw_score": doc.get("_raw_score", score),
                    "feats": doc.get("_feats", {}),
                    **({"prior_opens": doc["prior_opens"]} if "prior_opens" in doc else {}),
                },
                verified=verified,
                page_num=page_num,
                vgc_certificate=cert_dict,
            )
            results.append(item)

        return results


def natural_sort_key(text: str) -> List[Any]:
    """
    Split text into digit and non-digit chunks, lowercasing text.
    Ensures natural sort order (file1, file2, file10) and case-insensitivity ('in hoa or not').
    """
    return [int(c) if c.isdigit() else c.lower() for c in re.split(r"(\d+)", text or "")]


def sort_search_results(items: List[SearchResultItem], sort_mode: str = "abc") -> List[SearchResultItem]:
    """
    Sort search results according to user criteria:
    - 'abc': Natural alphabetical (A-Z, case-insensitive / in hoa or not), tie-breaker by most recent time (-modified_at)
    - 'recent': Most recent modified time first (modified_at DESC), tie-breaker by natural alphabetical (A-Z)
    - 'score': Relevance match score DESC, tie-breaker by most recent time (-modified_at)
    - 'size': File size DESC, tie-breaker by natural alphabetical (A-Z)
    """
    if sort_mode == "abc":
        return sorted(
            items,
            key=lambda x: (
                natural_sort_key(getattr(x, "file_name", "") or ""),
                -getattr(x, "modified_at", 0.0),
            )
        )
    elif sort_mode == "recent":
        return sorted(
            items,
            key=lambda x: (
                -getattr(x, "modified_at", 0.0),
                natural_sort_key(getattr(x, "file_name", "") or ""),
            )
        )
    elif sort_mode == "score":
        return sorted(
            items,
            key=lambda x: (
                -getattr(x, "score", 0.0),
                -getattr(x, "modified_at", 0.0),
                natural_sort_key(getattr(x, "file_name", "") or ""),
            )
        )
    elif sort_mode == "size":
        return sorted(
            items,
            key=lambda x: (
                -getattr(x, "file_size", 0),
                natural_sort_key(getattr(x, "file_name", "") or ""),
            )
        )
    return items
