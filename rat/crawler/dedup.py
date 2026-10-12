"""
rat.crawler.dedup — Smart Deduplication & Semantic Document Version Tree Engine.
Detects exact binary duplicates (identical hashes) and semantic near-duplicate document revision trees
(e.g., 'report.docx', 'report_v2.docx', 'report_final(1).docx').
"""

from __future__ import annotations

import logging
import os
import re
from pathlib import Path
from typing import Any, Dict, List, Optional, Set, Tuple

from rat.config import config
from rat.crawler.db import Database
from rat.engine.reranker import format_file_size, format_relative_time

logger = logging.getLogger("rat.dedup")


def normalize_stem_for_versioning(file_name: str) -> str:
    """
    Strip versioning suffixes, dates, and copy indicators from filename stem.
    e.g. 'Bao_cao_final_v2(1).docx' -> 'bao cao'
         'Du_an_NAMI_edit2026.pptx' -> 'du an nami'
    """
    stem = Path(file_name).stem.lower()
    # Normalize separators
    stem = re.sub(r"[_\-\.\+]+", " ", stem)
    # Remove common versioning patterns
    stem = re.sub(r"\b(v\d+|\d+v|v|final|fixed|edit|sua|moi|new|copy|ban\s*sao|draft|nhap)\b", "", stem)
    # Remove parentheses with numbers e.g. (1), (2)
    stem = re.sub(r"\(\s*\d+\s*\)", "", stem)
    # Remove trailing digits
    stem = re.sub(r"\s+\d+\s*$", "", stem)
    # Collapse multiple spaces
    stem = re.sub(r"\s+", " ", stem).strip()
    return stem


def calculate_jaccard_token_similarity(text1: str, text2: str) -> float:
    """Calculate Jaccard similarity between two text samples using word tokens."""
    if not text1 or not text2:
        return 0.0
    tokens1 = set(text1.lower().split()[:500])
    tokens2 = set(text2.lower().split()[:500])
    if not tokens1 or not tokens2:
        return 0.0
    intersection = len(tokens1.intersection(tokens2))
    union = len(tokens1.union(tokens2))
    return float(intersection / union) if union > 0 else 0.0


class VersionGroup:
    """A cluster of related document versions or duplicate copies."""

    def __init__(self, canonical_name: str, file_ext: str) -> None:
        self.canonical_name = canonical_name
        self.file_ext = file_ext
        self.documents: List[Dict[str, Any]] = []

    def add_doc(self, doc: Dict[str, Any]) -> None:
        self.documents.append(doc)

    def finalize(self) -> None:
        """Sort documents by modified_at descending (latest first)."""
        self.documents.sort(key=lambda x: x.get("modified_at", 0), reverse=True)

    @property
    def latest_doc(self) -> Optional[Dict[str, Any]]:
        return self.documents[0] if self.documents else None

    @property
    def count(self) -> int:
        return len(self.documents)

    @property
    def total_size_bytes(self) -> int:
        return sum(d.get("file_size", 0) for d in self.documents)

    @property
    def wasted_size_bytes(self) -> int:
        """Potential wasted disk space from older/duplicate versions."""
        if len(self.documents) <= 1:
            return 0
        return sum(d.get("file_size", 0) for d in self.documents[1:])

    def to_dict(self) -> Dict[str, Any]:
        latest = self.latest_doc
        return {
            "canonical_name": self.canonical_name,
            "file_ext": self.file_ext,
            "total_versions": len(self.documents),
            "latest_file_name": latest["file_name"] if latest else "",
            "latest_file_path": latest["file_path"] if latest else "",
            "latest_modified": latest["modified_at"] if latest else 0,
            "latest_modified_formatted": format_relative_time(latest["modified_at"]) if latest else "",
            "wasted_space_formatted": format_file_size(self.wasted_size_bytes),
            "versions": [
                {
                    "file_name": d["file_name"],
                    "file_path": d["file_path"],
                    "file_size": d["file_size"],
                    "file_size_formatted": format_file_size(d["file_size"]),
                    "modified_at": d["modified_at"],
                    "modified_formatted": format_relative_time(d["modified_at"]),
                    "is_latest": (idx == 0),
                }
                for idx, d in enumerate(self.documents)
            ],
        }


class SmartDeduplicationEngine:
    """Engine for identifying duplicate files and semantic version trees."""

    def __init__(self, db: Optional[Database] = None) -> None:
        self.db = db or Database(config.db_path)

    def find_exact_duplicates(self) -> List[Dict[str, Any]]:
        """
        Find exact binary duplicates having identical MD5 hash across different paths.
        """
        conn = self.db.get_connection()
        cursor = conn.cursor()

        cursor.execute("""
            SELECT md5_hash, COUNT(*) as copy_count, SUM(file_size) as total_bytes
            FROM documents
            WHERE md5_hash IS NOT NULL AND md5_hash != '' AND file_size > 0
            GROUP BY md5_hash
            HAVING copy_count > 1
            ORDER BY total_bytes DESC
        """)
        rows = cursor.fetchall()
        if not rows:
            return []

        duplicate_groups = []
        for r in rows:
            h = r["md5_hash"]
            cursor.execute("SELECT * FROM documents WHERE md5_hash = ? ORDER BY modified_at DESC", (h,))
            doc_rows = [dict(d) for d in cursor.fetchall()]
            if len(doc_rows) > 1:
                single_size = doc_rows[0]["file_size"]
                wasted = single_size * (len(doc_rows) - 1)
                duplicate_groups.append({
                    "md5_hash": h,
                    "copy_count": len(doc_rows),
                    "file_size": single_size,
                    "wasted_space_bytes": wasted,
                    "wasted_space_formatted": format_file_size(wasted),
                    "files": [
                        {
                            "file_name": d["file_name"],
                            "file_path": d["file_path"],
                            "modified_at": d["modified_at"],
                            "modified_formatted": format_relative_time(d["modified_at"]),
                        }
                        for d in doc_rows
                    ]
                })

        return duplicate_groups

    def find_version_trees(self, min_versions: int = 2) -> List[VersionGroup]:
        """
        Cluster documents into version trees by normalized stem and extension similarity.
        """
        conn = self.db.get_connection()
        cursor = conn.cursor()

        # Only check document, slide, sheet and code extensions for versioning
        target_exts = (".pdf", ".docx", ".doc", ".pptx", ".ppt", ".xlsx", ".xls", ".py", ".txt", ".md")
        ext_placeholders = ",".join(["?"] * len(target_exts))

        cursor.execute(f"""
            SELECT id, file_path, file_name, file_ext, file_size, modified_at, created_at, content_text
            FROM documents
            WHERE file_ext IN ({ext_placeholders})
            ORDER BY modified_at DESC
        """, target_exts)

        all_docs = [dict(r) for r in cursor.fetchall()]
        if not all_docs:
            return []

        clusters: Dict[Tuple[str, str], VersionGroup] = {}

        for doc in all_docs:
            name = doc["file_name"]
            ext = doc["file_ext"].lower()
            clean_stem = normalize_stem_for_versioning(name)

            if len(clean_stem) < 3:
                continue

            key = (clean_stem, ext)
            if key not in clusters:
                clusters[key] = VersionGroup(canonical_name=clean_stem, file_ext=ext)
            clusters[key].add_doc(doc)

        # Finalize and filter groups with >= min_versions
        result_groups: List[VersionGroup] = []
        for group in clusters.values():
            group.finalize()
            if group.count >= min_versions:
                result_groups.append(group)

        # Sort groups by potential wasted space descending
        result_groups.sort(key=lambda g: g.wasted_size_bytes, reverse=True)
        return result_groups

    def get_document_version_info(self, file_path: str) -> Optional[Dict[str, Any]]:
        """
        Check if a given file belongs to a version cluster and return its version context.
        """
        doc = self.db.get_document_by_path(file_path)
        if not doc:
            return None

        clean_stem = normalize_stem_for_versioning(doc["file_name"])
        if len(clean_stem) < 3:
            return None

        ext = doc["file_ext"].lower()

        conn = self.db.get_connection()
        cursor = conn.cursor()
        cursor.execute("""
            SELECT id, file_path, file_name, file_ext, file_size, modified_at, created_at
            FROM documents
            WHERE file_ext = ?
        """, (ext,))

        candidates = [dict(r) for r in cursor.fetchall()]
        matched_docs = []
        for c in candidates:
            c_stem = normalize_stem_for_versioning(c["file_name"])
            if c_stem == clean_stem:
                matched_docs.append(c)

        if len(matched_docs) <= 1:
            return None

        # Sort by modified_at descending
        matched_docs.sort(key=lambda x: x["modified_at"], reverse=True)
        latest = matched_docs[0]
        is_latest = (latest["file_path"] == file_path)

        other_versions = [
            {
                "file_name": d["file_name"],
                "file_path": d["file_path"],
                "modified_formatted": format_relative_time(d["modified_at"]),
                "is_latest": (d["file_path"] == latest["file_path"]),
            }
            for d in matched_docs if d["file_path"] != file_path
        ]

        return {
            "canonical_name": clean_stem,
            "total_versions": len(matched_docs),
            "is_latest": is_latest,
            "latest_file_name": latest["file_name"],
            "latest_file_path": latest["file_path"],
            "latest_modified_formatted": format_relative_time(latest["modified_at"]),
            "other_versions": other_versions,
        }


# Global singleton instance
dedup_engine = SmartDeduplicationEngine()
