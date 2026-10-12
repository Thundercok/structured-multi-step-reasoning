"""
rat.crawler.warmup — Background Document Content Warmup for Semester Directories.
Discovers and extracts FTS5 text content for semester slides, lectures, and assignments
in the background using low priority (QoS Background), so search latency stays < 15ms.
"""

from __future__ import annotations

import logging
import os
import re
from pathlib import Path
from typing import List, Optional

from PyQt6.QtCore import QObject, pyqtSignal

from rat.config import config, set_thread_qos_background
from rat.crawler.db import Database
from rat.crawler.indexer import Indexer

logger = logging.getLogger("rat.crawler.warmup")

SEMESTER_DIR_PATTERN = re.compile(
    r"(?:^|[/\\])(?:hk\d{2,3}|(?:20)?2[3-6][-_](?:20)?2[4-7]|hoc[-_ ]?ky(?:[-_ ]?\d+)?|semester(?:[-_ ]?\d+)?|sem[-_ ]?\d+|mon[-_ ]?hoc)(?:[/\\]|$)",
    re.IGNORECASE,
)
ACADEMIC_EXTS = {".pptx", ".ppt", ".pdf", ".docx", ".doc", ".ipynb"}


class SemesterWarmupWorker(QObject):
    """Low-priority background worker for pre-indexing semester study materials."""

    finished = pyqtSignal(int)

    def __init__(self, db: Optional[Database] = None) -> None:
        super().__init__()
        self.db = db or Database(config.db_path)
        self.indexer = Indexer(self.db)
        self._stopped = False

    def stop(self) -> None:
        self._stopped = True
        self.indexer.cancel()

    def run(self) -> None:
        set_thread_qos_background()
        warmed = 0
        try:
            discovered_paths: List[str] = []
            for d in config.indexed_directories:
                d_path = Path(d).expanduser().resolve()
                if not d_path.exists() or not d_path.is_dir():
                    continue

                for root, dirs, files in os.walk(d_path):
                    if self._stopped:
                        break
                    # Filter out ignored directories
                    dirs[:] = [
                        d_name for d_name in dirs
                        if not d_name.startswith(".") and d_name not in ("node_modules", ".git", "Library")
                    ]

                    # Check if directory path matches semester or study keywords
                    is_sem = bool(SEMESTER_DIR_PATTERN.search(root))
                    if not is_sem:
                        is_sem = any(
                            re.search(r"\b(?:\d{5,7}|slide|lecture|bai[-_ ]?giang)\b", p, re.I)
                            for p in Path(root).parts
                        )

                    if not is_sem:
                        continue

                    for file_name in files:
                        if self._stopped:
                            break
                        file_path = Path(root) / file_name
                        if file_path.suffix.lower() in ACADEMIC_EXTS:
                            discovered_paths.append(str(file_path))

            logger.info(f"SemesterWarmupWorker discovered {len(discovered_paths)} academic files to verify.")
            for fp in discovered_paths:
                if self._stopped:
                    break
                # index_single_file skips if already indexed and up-to-date
                if self.indexer.index_single_file(fp):
                    warmed += 1

            if warmed > 0:
                logger.info(f"SemesterWarmupWorker successfully pre-warmed {warmed} new/updated academic files.")
            self.finished.emit(warmed)
        except Exception as e:
            logger.warning(f"SemesterWarmupWorker error: {e}")
            self.finished.emit(0)
