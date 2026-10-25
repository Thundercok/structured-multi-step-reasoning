"""Offline Semantic & Fuzzy Reranker for RAT Progressive Finder.

Provides offline topic concept expansion, typo-tolerant fuzzy matching,
and multi-factor heuristic reranking without requiring external model APIs
or heavy neural networks during keyboard interaction.
"""
from __future__ import annotations

import re
import sqlite3
import unicodedata
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Sequence, Set, Tuple


def fold_ascii(text: str) -> str:
    """Normalize Vietnamese accents and punctuation to lowercase ASCII."""
    if not text:
        return ""
    decomposed = unicodedata.normalize("NFD", text.lower())
    without_marks = "".join(ch for ch in decomposed if unicodedata.category(ch) != "Mn")
    cleaned = without_marks.replace("đ", "d").replace("Đ", "d")
    return re.sub(r"[^\w\s]", " ", cleaned).strip()


def char_trigrams(text: str) -> Set[str]:
    """Extract character trigrams for typo-tolerant fuzzy similarity."""
    folded = f"  {fold_ascii(text)}  "
    if len(folded) < 3:
        return set()
    return {folded[i:i + 3] for i in range(len(folded) - 2)}


def trigram_similarity(s1: str, s2: str) -> float:
    """Compute Dice coefficient over character trigrams."""
    t1 = char_trigrams(s1)
    t2 = char_trigrams(s2)
    if not t1 or not t2:
        return 0.0
    intersection = len(t1 & t2)
    return (2.0 * intersection) / (len(t1) + len(t2))


# Offline Domain Topic Clusters for semantic concept expansion
OFFLINE_TOPIC_CLUSTERS: Dict[str, Tuple[str, ...]] = {
    "vrptw_logistics": (
        "lo trinh", "giao hang", "van tai", "xe", "phuong tien",
        "vrptw", "routing", "vehicle", "logistics", "alns", "dieu phoi",
        "tiet kiem", "chi phi", "quang duong", "kho bai", "fleet", "depot"
    ),
    "reinforcement_learning": (
        "hoc tang cuong", "mang no ron", "hoc may", "may hoc",
        "reinforcement learning", "deep q", "double dqn", "dqn",
        "neural network", "toan tu", "operator", "policy", "q learning",
        "agent", "phan thuong", "reward"
    ),
    "optimization": (
        "toi uu hoa", "giai thuat", "thuat toan", "toi uu", "heuristic",
        "metaheuristic", "alns", "adaptive large neighborhood search",
        "local search", "tim kiem cuc bo", "bien doi"
    ),
    "academic_research": (
        "phan bien", "bai bao", "nghien cuu", "luan van", "de tai",
        "tieu luan", "bao cao", "paper", "conference", "thesis",
        "khong gian mau", "ket qua", "benchmark", "thuc nghiem"
    ),
    "mathematics": (
        "giai tich", "toan cao cap", "dai so", "xac suat", "thong ke",
        "calculus", "linear algebra", "statistics", "ma1521", "ma1522"
    ),
    "university_regulations": (
        "quy che", "tin chi", "hoc vu", "thoi khoa bieu", "diem ren luyen",
        "hoc phan", "chuong trinh dao tao", "tot nghiep"
    ),
    "natal_astrology": (
        "tu vi", "la so", "tarot", "chiem tinh", "natal", "horoscope",
        "ephemeris", "banh xe", "cung hoang dao", "cung moc"
    ),
}


class SemanticFuzzyReranker:
    """Offline semantic expansion and fuzzy reranker for progressive search."""

    def __init__(self, db_path: str | Path, *, max_candidates: int = 50):
        self.db_path = str(db_path)
        self.max_candidates = max_candidates

    def expand_query_topics(self, query: str) -> List[str]:
        """Find related domain keywords via offline topic cluster association."""
        folded_q = fold_ascii(query)
        padded_q = f" {folded_q} "
        q_tokens = [t for t in folded_q.split() if len(t) >= 2]

        # Score clusters by match intensity
        cluster_scores: List[Tuple[int, str]] = []
        for cluster_name, keywords in OFFLINE_TOPIC_CLUSTERS.items():
            matched_count = 0
            for kw in keywords:
                if f" {kw} " in padded_q or (len(kw) >= 4 and kw in folded_q):
                    matched_count += 2
                elif any(tok == kw for tok in q_tokens):
                    matched_count += 1
            if matched_count > 0:
                cluster_scores.append((matched_count, cluster_name))

        cluster_scores.sort(key=lambda x: x[0], reverse=True)

        expanded: List[str] = []
        for _, cname in cluster_scores:
            for kw in OFFLINE_TOPIC_CLUSTERS[cname]:
                if kw not in folded_q and kw not in expanded:
                    expanded.append(kw)
        return expanded[:15]

    def compute_fuzzy_score(
        self,
        query: str,
        file_name: str,
        summary: str,
        content_snippet: str = "",
        is_pdf: bool = False,
        file_ext: str = "",
        target_extensions: Sequence[str] = (),
    ) -> Tuple[float, List[str]]:
        """Compute multi-factor score and reasons why this document matches."""
        score = 0.0
        reasons: List[str] = []

        q_fold = fold_ascii(query)
        name_fold = fold_ascii(file_name)
        sum_fold = fold_ascii(summary)
        q_tokens = [t for t in q_fold.split() if len(t) >= 2]

        if not q_tokens:
            return 0.0, []

        # 1. Trigram similarity on file title (typo-tolerant matching)
        sim = trigram_similarity(q_fold, name_fold)
        if sim > 0.25:
            bonus = min(40.0, sim * 50.0)
            score += bonus
            reasons.append(f"Tên tệp tương tự ({int(sim * 100)}%)")

        # 2. Token overlap in filename
        matched_title_tokens = [tok for tok in q_tokens if tok in name_fold]
        if matched_title_tokens:
            overlap_ratio = len(matched_title_tokens) / len(q_tokens)
            score += overlap_ratio * 35.0
            reasons.append(f"Khớp từ khóa trong tên ({len(matched_title_tokens)}/{len(q_tokens)})")

        # 3. Topic cluster semantic resonance
        query_clusters: Set[str] = set()
        for cname, kws in OFFLINE_TOPIC_CLUSTERS.items():
            if any(kw in q_fold or any(t in kw for t in q_tokens if len(t) >= 4) for kw in kws):
                query_clusters.add(cname)

        doc_clusters: Set[str] = set()
        for cname in query_clusters:
            kws = OFFLINE_TOPIC_CLUSTERS[cname]
            if any(kw in name_fold or kw in sum_fold for kw in kws):
                doc_clusters.add(cname)

        if doc_clusters:
            score += 25.0 * len(doc_clusters)
            reasons.append("Khớp cụm chủ đề ngữ nghĩa chuyên môn")

        # 4. Summary & excerpt matches
        matched_sum_tokens = [tok for tok in q_tokens if tok in sum_fold]
        if matched_sum_tokens:
            score += min(20.0, len(matched_sum_tokens) * 6.0)
            reasons.append("Nội dung/tóm tắt có nhắc đến từ khóa")

        # 5. Extension alignment
        if target_extensions:
            ext_clean = file_ext.lower()
            if ext_clean in [e.lower() for e in target_extensions]:
                score += 25.0
                reasons.append(f"Đúng định dạng {ext_clean.upper()}")
            else:
                score -= 15.0

        return score, reasons

    def __call__(self, request: Any) -> Iterable[str]:
        """Execute semantic and fuzzy candidate retrieval, yielding ranked file paths."""
        query = getattr(request, "query", "") or ""
        intent = getattr(request, "intent", None)
        extensions = intent.extensions if intent and hasattr(intent, "extensions") else ()

        clean_query = query.strip()
        if not clean_query:
            return []

        expanded_terms = self.expand_query_topics(clean_query)
        if not expanded_terms:
            return []

        # Build FTS5 query using OR for broad semantic retrieval based on topic expansion
        fts_query = " OR ".join(f'"{t}"' for t in expanded_terms[:6] if len(t) >= 2)

        try:
            conn = sqlite3.connect(f"file:{self.db_path}?mode=ro", uri=True)
            conn.execute("PRAGMA busy_timeout=50")
            cursor = conn.cursor()

            sql = (
                "SELECT d.file_path, d.file_name, d.file_ext, d.file_size, d.modified_at, "
                "substr(coalesce(d.summary, ''), 1, 300) AS summary "
                "FROM documents_fts JOIN documents d ON d.id = documents_fts.rowid "
                "WHERE documents_fts MATCH ? "
                "ORDER BY rank "
                "LIMIT ?"
            )
            rows = cursor.execute(sql, (fts_query, self.max_candidates)).fetchall()
            conn.close()
        except Exception:
            return []

        scored_candidates: List[Tuple[float, str]] = []
        for row in rows:
            path, file_name, file_ext, file_size, modified_at, summary = row
            p = Path(path)
            if not p.is_file():
                continue
            try:
                if p.stat().st_size == 0:
                    continue
            except OSError:
                continue

            score, _ = self.compute_fuzzy_score(
                clean_query,
                file_name=file_name or p.name,
                summary=summary or "",
                file_ext=file_ext or p.suffix,
                target_extensions=extensions,
            )
            if score > 5.0:
                scored_candidates.append((score, str(path)))

        scored_candidates.sort(key=lambda item: item[0], reverse=True)
        return [path for _, path in scored_candidates]
