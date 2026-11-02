"""
rat.crawler.indexer — Multi-threaded local file crawler & indexer.
"""

from __future__ import annotations

import concurrent.futures
import fnmatch
import hashlib
import logging
import os
import time
from pathlib import Path
from typing import Callable, Dict, List, Optional, Set, Tuple

import numpy as np

from rat.config import (
    IGNORE_DIRS,
    IGNORE_PATTERNS,
    MAX_FILE_SIZE_BYTES,
    SUPPORTED_EXTENSIONS,
    config,
)
from rat.crawler.chunker import chunker
from rat.crawler.db import Database
from rat.crawler.extractors import extract_document_content
from rat.engine.embedder import embedder

logger = logging.getLogger("rat.indexer")


def get_file_md5_fast(file_path: str, max_bytes: int = 1024 * 1024) -> str:
    """Compute quick MD5 hash of the initial chunk of a file."""
    try:
        hasher = hashlib.md5()
        with open(file_path, "rb") as f:
            chunk = f.read(max_bytes)
            hasher.update(chunk)
        return hasher.hexdigest()
    except Exception:
        return ""


class Indexer:
    """Crawler & Indexer for local files."""

    def __init__(self, db: Optional[Database] = None) -> None:
        self.db = db or Database(config.db_path)
        self.is_indexing = False
        self._cancel_flag = False

    def cancel(self) -> None:
        """Signal the indexer to cancel the current run."""
        self._cancel_flag = True

    def is_ignored(self, path: Path) -> bool:
        """Check if path should be ignored."""
        for part in path.parts:
            if part in IGNORE_DIRS or part.startswith("."):
                return True
            lower_part = part.lower()
            if (
                lower_part.endswith(".app")
                or lower_part.endswith(".framework")
                or lower_part.endswith(".bundle")
                or lower_part.endswith(".xcodeproj")
                or lower_part.endswith(".photoslibrary")
            ):
                return True
        for pattern in IGNORE_PATTERNS:
            if fnmatch.fnmatch(path.name, pattern):
                return True
        return False

    def discover_files(self, directories: List[str]) -> List[str]:
        """Traverse directories and gather eligible file paths."""
        found_files: List[str] = []
        for d in directories:
            d_path = Path(d).expanduser().resolve()
            if not d_path.exists() or not d_path.is_dir():
                continue

            for root, dirs, files in os.walk(d_path):
                # Filter out ignored directories in-place to prevent descending into them
                dirs[:] = [
                    d_name for d_name in dirs
                    if d_name not in IGNORE_DIRS and not d_name.startswith(".")
                ]

                for file_name in files:
                    if self._cancel_flag:
                        return found_files

                    file_path = Path(root) / file_name
                    ext = file_path.suffix.lower()

                    if ext not in SUPPORTED_EXTENSIONS:
                        continue

                    if self.is_ignored(file_path):
                        continue

                    found_files.append(str(file_path))
        return found_files

    def index_single_file(self, file_path_str: str, force: bool = False) -> bool:
        """Index or re-index a single file."""
        try:
            path = Path(file_path_str)
            if not path.exists() or not path.is_file():
                return False

            stat = path.stat()
            size = stat.st_size
            if size > MAX_FILE_SIZE_BYTES:
                return False

            modified_at = stat.st_mtime
            created_at = getattr(stat, "st_birthtime", stat.st_ctime)

            # Check if file has already been indexed and not modified
            if not force:
                existing = self.db.get_document_by_path(str(path))
                if existing and existing["modified_at"] == modified_at and existing["file_size"] == size:
                    return False  # Up to date

            # Extract deep text content
            content_text = extract_document_content(str(path))
            file_name = path.name
            ext = path.suffix.lower()
            md5_hash = get_file_md5_fast(str(path))

            # Extract provenance (source URLs, originating domain, download app)
            from rat.crawler.provenance import provenance_extractor
            provenance = provenance_extractor.get_provenance(str(path))
            if provenance.get("provenance_text"):
                if content_text:
                    content_text = f"{content_text}\n\n[File Provenance]: {provenance['provenance_text']}"
                else:
                    content_text = f"[File Provenance]: {provenance['provenance_text']}"

            doc = {
                "file_path": str(path),
                "file_name": file_name,
                "file_ext": ext,
                "file_size": size,
                "created_at": created_at,
                "modified_at": modified_at,
                "md5_hash": md5_hash,
                "content_text": content_text,
                "summary": "",
                "indexed_at": time.time(),
            }

            # Prepare vectors before publishing any metadata or FTS changes.
            chunks = []
            chunk_embeddings = np.empty((0, 384), dtype=np.float32)
            if content_text and len(content_text.strip()) > 30:
                chunks = chunker.chunk_text(content_text)
                if chunks:
                    chunk_texts = [c.text for c in chunks]
                    chunk_embeddings = embedder.embed_texts(chunk_texts)
            self.db.replace_document(doc, chunks, chunk_embeddings)
            return True
        except Exception as e:
            logger.error(f"Error indexing {file_path_str}: {e}")
            return False

    def run_full_index(
        self,
        directories: Optional[List[str]] = None,
        progress_callback: Optional[Callable[[int, int, str], None]] = None,
        max_workers: int = 4,
    ) -> Tuple[int, int]:
        """
        Run a full crawl & index across specified directories.
        Returns: (indexed_count, total_discovered)
        """
        self.is_indexing = True
        self._cancel_flag = False
        target_dirs = directories or config.indexed_directories

        logger.info(f"Starting indexer on dirs: {target_dirs}")
        files = self.discover_files(target_dirs)
        total = len(files)
        indexed_count = 0

        # Clean deleted files from DB
        # Energy & Battery Governance: Prioritize Efficiency Cores and conserve battery
        from rat.config import is_on_battery, set_thread_qos_background

        on_battery = is_on_battery()
        effective_workers = max(1, max_workers // 2) if on_battery else max_workers
        if on_battery:
            logger.info("⚡ MacBook is on battery: reducing indexer workers to conserve power.")

        with concurrent.futures.ThreadPoolExecutor(
            max_workers=effective_workers,
            initializer=set_thread_qos_background
        ) as executor:
            future_to_file = {
                executor.submit(self.index_single_file, f): f for f in files
            }

            completed = 0
            for future in concurrent.futures.as_completed(future_to_file):
                if self._cancel_flag:
                    break
                f_path = future_to_file[future]
                try:
                    was_indexed = future.result()
                    if was_indexed:
                        indexed_count += 1
                except Exception as e:
                    logger.error(f"Failed worker indexing {f_path}: {e}")

                completed += 1
                if progress_callback:
                    progress_callback(completed, total, Path(f_path).name)

        self.is_indexing = False
        logger.info(f"Indexing completed: {indexed_count}/{total} files updated.")
        return indexed_count, total
