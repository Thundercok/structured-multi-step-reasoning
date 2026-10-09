"""
rat.crawler.watcher — Real-time filesystem watcher using watchdog.
"""

from __future__ import annotations

import logging
import os
import threading
import time
from pathlib import Path
from typing import List, Optional

from watchdog.events import FileSystemEvent, FileSystemEventHandler
from watchdog.observers import Observer

from rat.config import SUPPORTED_EXTENSIONS, config, is_on_battery, set_thread_qos_background
from rat.crawler.indexer import Indexer

logger = logging.getLogger("rat.watcher")


class RatFileEventHandler(FileSystemEventHandler):
    """Event handler for filesystem changes with debouncing."""

    def __init__(
        self, indexer: Indexer, debounce_seconds: float = 2.0, *, autostart: bool = True
    ) -> None:
        super().__init__()
        self.indexer = indexer
        self.debounce_seconds = debounce_seconds
        self._pending_files: dict[str, float] = {}
        self._lock = threading.Lock()
        self._lifecycle_lock = threading.Lock()
        self._stopping_count = 0
        self._stop_event = threading.Event()
        self._stop_event.set()
        self._worker_thread: Optional[threading.Thread] = None
        self._poll_interval = 1.0
        if autostart:
            self.start()

    def start(self) -> None:
        """Start one queue worker, recreating it after a completed shutdown."""
        with self._lifecycle_lock:
            if self._stopping_count or (self._worker_thread and self._worker_thread.is_alive()):
                return
            self._stop_event.clear()
            self._worker_thread = threading.Thread(
                target=self._process_queue, daemon=True, name="rat-indexing-queue"
            )
            self._worker_thread.start()

    def _should_handle(self, path_str: str) -> bool:
        path = Path(path_str)
        if path.is_dir() or self.indexer.is_ignored(path):
            return False
        if path.suffix.lower() not in SUPPORTED_EXTENSIONS:
            return False
        return True

    def on_created(self, event: FileSystemEvent) -> None:
        if getattr(event, "is_directory", False):
            return
        if self._should_handle(event.src_path):
            self._queue_file(event.src_path)

    def on_modified(self, event: FileSystemEvent) -> None:
        if getattr(event, "is_directory", False):
            return
        if self._should_handle(event.src_path):
            self._queue_file(event.src_path)

    def on_deleted(self, event: FileSystemEvent) -> None:
        if self._stop_event.is_set():
            return
        if getattr(event, "is_directory", False):
            return
        if not self._should_handle(event.src_path):
            return
        try:
            self.indexer.db.delete_document(event.src_path)
            logger.info(f"File deleted from index: {event.src_path}")
        except Exception as e:
            logger.error(f"Error handling deleted file {event.src_path}: {e}")

    def on_moved(self, event: FileSystemEvent) -> None:
        if self._stop_event.is_set():
            return
        if getattr(event, "is_directory", False):
            return
        if self._should_handle(event.src_path):
            try:
                self.indexer.db.delete_document(event.src_path)
            except Exception:
                logger.exception("Error removing moved file from index: %s", event.src_path)
        if hasattr(event, "dest_path") and self._should_handle(event.dest_path):
            self._queue_file(event.dest_path)

    def _queue_file(self, file_path: str) -> None:
        with self._lock:
            if not self._stop_event.is_set():
                self._pending_files[file_path] = time.monotonic()

    def _process_queue(self) -> None:
        set_thread_qos_background()
        while not self._stop_event.wait(self._poll_interval):
            now = time.monotonic()
            to_process = []
            with self._lock:
                for file_path, added_time in list(self._pending_files.items()):
                    if now - added_time >= self.debounce_seconds:
                        to_process.append(file_path)
                        del self._pending_files[file_path]

            on_battery = is_on_battery()
            throttle_sleep = 0.2 if on_battery else 0.05

            for file_path in to_process:
                if self._stop_event.is_set():
                    break
                if os.path.exists(file_path):
                    try:
                        indexed = self.indexer.index_single_file(file_path, force=False)
                        if indexed:
                            logger.info(f"Auto-indexed updated file: {file_path}")
                    except Exception:
                        logger.exception("Error auto-indexing updated file: %s", file_path)
                    if self._stop_event.wait(throttle_sleep):
                        break

    def stop(self, timeout: float = 2.0) -> None:
        """Stop accepting work and wait for the queue worker within the timeout."""
        with self._lifecycle_lock:
            self._stopping_count += 1
            self._stop_event.set()
            worker = self._worker_thread
        try:
            with self._lock:
                self._pending_files.clear()
            if worker and worker.is_alive() and worker is not threading.current_thread():
                worker.join(timeout=max(0.0, timeout))
        finally:
            with self._lifecycle_lock:
                self._stopping_count -= 1


class FolderWatcher:
    """Manager for watching multiple folders."""

    def __init__(self, indexer: Optional[Indexer] = None) -> None:
        self.indexer = indexer or Indexer()
        self.observer = Observer()
        self.handler = RatFileEventHandler(self.indexer, autostart=False)
        self.is_running = False
        self._lifecycle_lock = threading.Lock()
        self._stop_event = threading.Event()
        self._startup_thread: Optional[threading.Thread] = None
        self._stopping_count = 0
        self._observer_used = False

    def start(self, directories: Optional[List[str]] = None) -> None:
        """Start watching directories asynchronously in background thread."""
        with self._lifecycle_lock:
            # An in-flight index operation cannot be interrupted safely. Do not
            # overlap it with a new watcher if a previous stop timed out.
            if self._stopping_count or self.is_running or self._background_threads_alive():
                return
            if self._observer_used:
                self.observer = Observer()  # watchdog observers are one-shot threads.
            self._observer_used = True
            self._stop_event.clear()
            target_dirs = list(config.indexed_directories if directories is None else directories)
            self._startup_thread = threading.Thread(
                target=self._start_internal,
                args=(target_dirs,),
                daemon=True,
                name="rat-filesystem-watcher",
            )
            self._startup_thread.start()

    def _background_threads_alive(self) -> bool:
        return any(
            thread is not None and thread.is_alive()
            for thread in (self._startup_thread, self.handler._worker_thread, self.observer)
        )

    def _stop_observer(self, timeout: float = 2.0) -> None:
        try:
            self.observer.stop()
        except Exception:
            logger.exception("Error stopping filesystem observer")
        try:
            if self.observer is not threading.current_thread():
                self.observer.join(timeout=max(0.0, timeout))
        except RuntimeError:
            # stop() is also valid before Observer.start() has run.
            pass
        except Exception:
            logger.exception("Error joining filesystem observer")

    def _start_internal(self, directories: Optional[List[str]] = None) -> None:
        started = False
        try:
            target_dirs = config.indexed_directories if directories is None else directories
            for d in target_dirs:
                if self._stop_event.is_set():
                    return
                try:
                    d_path = Path(d).expanduser().resolve()
                    if d_path.exists() and d_path.is_dir():
                        self.observer.schedule(self.handler, str(d_path), recursive=True)
                        logger.info(f"Watching directory: {d_path}")
                except Exception as e:
                    logger.warning(f"Failed to schedule directory {d}: {e}")

            with self._lifecycle_lock:
                if self._stop_event.is_set():
                    return
                self.handler.start()
            self.observer.start()
            with self._lifecycle_lock:
                if self._stop_event.is_set():
                    return
                self.is_running = True
                started = True
            logger.info("Realtime filesystem watcher started successfully.")
        except Exception as e:
            logger.warning(f"Error starting filesystem observer: {e}")
        finally:
            if not started:
                self._stop_observer()
                self.handler.stop()
                with self._lifecycle_lock:
                    self.is_running = False

    def stop(self) -> None:
        """Cancel startup and stop background services within a two-second wait."""
        deadline = time.monotonic() + 2.0
        with self._lifecycle_lock:
            self._stopping_count += 1
            self._stop_event.set()
            self.is_running = False
            # watchdog stop() permanently sets the observer's stopped event,
            # including when its thread has never been started.
            self._observer_used = True
            startup = self._startup_thread
        try:
            self.handler.stop(timeout=0.0)
            self._stop_observer(timeout=0.0)
            if startup and startup is not threading.current_thread():
                startup.join(timeout=max(0.0, deadline - time.monotonic()))
            # Startup may have finished Observer.start() after the initial stop.
            self._stop_observer(timeout=deadline - time.monotonic())
            self.handler.stop(timeout=deadline - time.monotonic())
        finally:
            with self._lifecycle_lock:
                self._stopping_count -= 1


# Alias for backward compatibility
Watcher = FolderWatcher
