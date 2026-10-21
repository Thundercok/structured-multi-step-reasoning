"""
rat.crawler.warmup — Background Document Content Warmup for Semester Directories.
Discovers and extracts text from semester documents in the background, processing
each eligible file as it is found without retaining a full path queue.
"""

from __future__ import annotations

import logging
import os
import re
from pathlib import Path
from typing import Optional

from PyQt6.QtCore import QObject, pyqtSignal

from rat.config import config, is_on_battery, set_thread_qos_background
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
        warmed = 0
        try:
            if self._stopped or not config.auto_watch or not config.indexed_directories or is_on_battery():
                self.finished.emit(0)
                return
            set_thread_qos_background()
            discovered = 0
            for d in config.indexed_directories:
                if self._stopped or not config.auto_watch:
                    break
                d_path = Path(d).expanduser().resolve()
                if not d_path.is_dir() or self.indexer.is_ignored(d_path):
                    continue

                for root, dirs, files in os.walk(d_path):
                    if self._stopped or not config.auto_watch:
                        break
                    # Use the same exclusions as normal indexing (including
                    # generated directories and macOS application bundles).
                    dirs[:] = [
                        d_name for d_name in dirs
                        if not self.indexer.is_ignored(Path(root) / d_name)
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
                        if self._stopped or not config.auto_watch:
                            break
                        file_path = Path(root) / file_name
                        if file_path.suffix.lower() not in ACADEMIC_EXTS or self.indexer.is_ignored(file_path):
                            continue
                        discovered += 1
                        # The indexer skips unchanged files. Process now rather
                        # than accumulating paths across the whole directory tree.
                        if self.indexer.index_single_file(str(file_path)):
                            warmed += 1

            logger.info(f"SemesterWarmupWorker checked {discovered} academic files.")
            if warmed > 0:
                logger.info(f"SemesterWarmupWorker successfully pre-warmed {warmed} new/updated academic files.")
            self.finished.emit(warmed)
        except Exception as e:
            logger.warning(f"SemesterWarmupWorker error: {e}")
            self.finished.emit(0)
