"""Local meaning-based file index for the finder; no network, no LLM.

Reads the first pages of documents in the user's chosen folders, embeds a few
chunks per file with the bundled multilingual model and answers "find the
paper about attention" without the user remembering the file name. Content
stays in the RAT state directory. Heavy imports (fastembed, PDF readers) load
only in the indexing thread or on the first query.
"""
from __future__ import annotations

import json
import logging
import os
from pathlib import Path
import re
import sqlite3
import sys
import threading
import time

import numpy as np

logger = logging.getLogger('rat.semantic_index')

MODEL_NAME = 'sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2'
DOCUMENT_EXTENSIONS = {'.pdf', '.docx', '.pptx'}
EXTENSIONS = DOCUMENT_EXTENSIONS | {'.txt', '.md'}
SKIP_DIRS = {'node_modules', 'Library', '__pycache__', 'venv', '.venv', 'site-packages'}
MAX_FILES = 5000
MAX_FILE_BYTES = 80_000_000
CHUNK_CHARS = 600
CHUNKS_PER_FILE = 3
KEYWORD_WEIGHT = 0.10
FILENAME_KEYWORD_WEIGHT = 0.10
# Vision OCR is slow, so scanned PDFs are read a few at a time, newest first.
OCR_FILES_PER_PASS = 30
OCR_PAUSE_S = 0.5
STOPWORDS = {'tim', 'file', 've', 'cai', 'cua', 'cho', 'toi', 'minh', 'mot', 'nhung', 'cac', 'va', 'la',
             'o', 'trong', 'bai', 'the', 'a', 'an', 'of', 'about', 'find'}


def word_set(text):
    from rat.engine.finder_intent import _fold_ascii
    return set(re.findall(r'\w+', _fold_ascii(text)))


def find_embedding_directory():
    """Bundled model cache, else None so fastembed uses its local cache (source runs)."""
    base = Path(getattr(sys, '_MEIPASS', Path(__file__).resolve().parents[2]))
    folder = base / 'rat/assets/embedding'
    return str(folder) if any(folder.glob('models--*')) else None


def file_identity(path):
    info = os.stat(path)
    return [info.st_dev, info.st_ino, info.st_size, info.st_mtime_ns]


def read_document_text(path, limit=CHUNK_CHARS * CHUNKS_PER_FILE, ocr=False):
    ext = Path(path).suffix.lower()
    if ext in ('.txt', '.md'):
        with open(path, 'rb') as handle:
            return handle.read(limit * 4).decode('utf-8', errors='ignore')[:limit]
    if ext == '.pdf':
        from document_intake.pdf import read_pdf_native
        return (read_pdf_native(path, max_pages=3, max_chars=limit, ocr=ocr) or '')[:limit]
    if ext in ('.docx', '.pptx'):
        return office_text(path, ext, limit)
    return ''


def office_text(path, ext, limit):
    # Body text straight from the OOXML parts: no python-docx/pptx dependency,
    # and core-properties metadata (author, generator) never reaches a preview.
    import xml.etree.ElementTree as ET
    import zipfile
    tag = '{http://schemas.openxmlformats.org/wordprocessingml/2006/main}t' if ext == '.docx' else \
          '{http://schemas.openxmlformats.org/drawingml/2006/main}t'
    with zipfile.ZipFile(path) as package:
        names = (['word/document.xml'] if ext == '.docx' else
                 sorted((n for n in package.namelist() if re.fullmatch(r'ppt/slides/slide\d+\.xml', n)),
                        key=lambda n: int(re.search(r'\d+', n).group())))
        texts = []
        for name in names:
            for node in ET.fromstring(package.read(name)).iter(tag):
                if node.text:
                    texts.append(node.text)
            if sum(map(len, texts)) >= limit:
                break
    return ' '.join(texts)[:limit]


def document_chunks(path, text):
    p = Path(path)
    # The name chunk lets "báo cáo nhóm 4" match a file whose body is empty or scanned.
    chunks = [f'{p.stem.replace("_", " ")} · {p.parent.name}']
    body = ' '.join(re.sub(r'---\s*Page \d+[^-\n]*---', ' ', text).split())
    for start in range(0, min(len(body), CHUNK_CHARS * CHUNKS_PER_FILE), CHUNK_CHARS):
        piece = body[start:start + CHUNK_CHARS].strip()
        if len(piece) >= 40:
            chunks.append(piece)
    return chunks


def candidate_files(roots, should_stop):
    found = []
    for root in roots:
        for folder, dirs, files in os.walk(root, onerror=lambda _exc: None):
            if should_stop():
                return []
            # A code repository inside a chosen folder would fill the index with text
            # files nobody looks for by meaning. A repository chosen as the root stays.
            if folder != os.fspath(root) and ('.git' in dirs or '.git' in files):
                dirs[:] = []
                continue
            dirs[:] = [d for d in dirs if not d.startswith('.') and d not in SKIP_DIRS
                       and not d.endswith(('.app', '.bundle', '.photoslibrary'))]
            for name in files:
                if not name.startswith('.') and Path(name).suffix.lower() in EXTENSIONS:
                    path = os.path.join(folder, name)
                    try:
                        info = os.stat(path)
                    except OSError:
                        continue
                    if info.st_size <= MAX_FILE_BYTES:
                        is_document = Path(name).suffix.lower() in DOCUMENT_EXTENSIONS
                        found.append((is_document, info.st_mtime, path))
    # Documents before plain text, then recent first: they are what a student looks for,
    # and this order decides what the first minute of indexing and MAX_FILES keep.
    found.sort(reverse=True)
    return [path for _is_document, _mtime, path in found[:MAX_FILES]]


class SemanticIndex:
    """Thread-safe store plus one background indexing pass at a time."""

    def __init__(self, database, *, embedder=None):
        self.database = Path(database)
        self.database.parent.mkdir(parents=True, exist_ok=True)
        self._embedder = embedder
        self._lock = threading.RLock()
        self._matrix = None
        self._rows = []
        self._words = []
        self._thread = None
        self._stop = threading.Event()
        self._active_queries = 0
        self._progress = {'state': 'idle', 'done': 0, 'total': 0}
        with self._connect() as db:
            db.executescript('''
                CREATE TABLE IF NOT EXISTS files (path TEXT PRIMARY KEY, identity TEXT NOT NULL,
                    modified_at REAL, indexed_at REAL);
                CREATE TABLE IF NOT EXISTS ocr_checked (path TEXT PRIMARY KEY, identity TEXT NOT NULL);
                CREATE TABLE IF NOT EXISTS chunks (path TEXT NOT NULL, chunk_index INTEGER NOT NULL,
                    chunk_text TEXT NOT NULL, vector BLOB NOT NULL, PRIMARY KEY (path, chunk_index));''')

    def _connect(self):
        return sqlite3.connect(self.database, timeout=10)

    @property
    def embedder(self):
        if self._embedder is None:
            from rat.engine.embedder import LocalEmbedder
            self._embedder = LocalEmbedder(MODEL_NAME, cache_dir=find_embedding_directory(),
                                           local_files_only=True, threads=2)
        return self._embedder

    def progress(self):
        with self._lock:
            return dict(self._progress)

    def count(self):
        with self._connect() as db:
            return db.execute('SELECT COUNT(*) FROM files').fetchone()[0]

    def contains(self, path):
        """True only while the file is unchanged since it was indexed."""
        with self._lock, self._connect() as db:
            row = db.execute('SELECT identity FROM files WHERE path = ?', (str(path),)).fetchone()
        if row is None:
            return False
        try:
            return json.loads(row[0]) == file_identity(path)
        except OSError:
            return False

    def invalidate_paths(self, paths):
        with self._lock, self._connect() as db:
            db.executemany('DELETE FROM files WHERE path = ?', [(p,) for p in paths])
            db.executemany('DELETE FROM chunks WHERE path = ?', [(p,) for p in paths])
            db.executemany('DELETE FROM ocr_checked WHERE path = ?', [(p,) for p in paths])
            self._matrix = None

    def _load_matrix(self):
        with self._lock:
            if self._matrix is None:
                with self._connect() as db:
                    rows = db.execute('''SELECT c.path, c.chunk_index, c.chunk_text, c.vector, f.identity, f.modified_at
                                         FROM chunks c JOIN files f ON f.path = c.path''').fetchall()
                self._rows = [dict(file_path=r[0], chunk_index=r[1], chunk_text=r[2],
                                   identity=json.loads(r[4]), modified_at=r[5]) for r in rows]
                # Words of each chunk plus its file name, accent-folded, for keyword agreement.
                self._words = [word_set(r[2] + ' ' + Path(r[0]).stem) for r in rows]
                self._fn_words = [word_set(Path(r[0]).stem) for r in rows]
                self._matrix = (np.vstack([np.frombuffer(r[3], dtype=np.float32) for r in rows])
                                if rows else np.empty((0, 384), dtype=np.float32))
            return self._matrix, self._rows

    def search(self, query, should_cancel=lambda: False, limit=40, floor=0.35, spread=0.18):
        with self._lock:
            self._active_queries += 1
        try:
            matrix, rows = self._load_matrix()
            if not len(rows):
                return []
            vector = self.embedder.embed_query(query)
            if should_cancel():
                raise ValueError('cancelled:semantic')
            # Meaning alone ranks near neighbours closely; words the user typed that
            # literally appear in the document break those ties.
            terms = word_set(query) - STOPWORDS
            raw_sim = matrix @ vector
            if terms:
                fn_agree = np.array([len(terms & words) / len(terms) for words in self._fn_words],
                                    dtype=np.float32)
                all_agree = np.array([len(terms & words) / len(terms) for words in self._words],
                                     dtype=np.float32)
                scores = raw_sim + FILENAME_KEYWORD_WEIGHT * fn_agree + KEYWORD_WEIGHT * all_agree
            else:
                scores = raw_sim

            order = np.argsort(-scores)[:limit]
            best_score = float(scores[order[0]])
            raw_best = float(np.max(raw_sim))
            # Keep a band near the best match, but ensure high semantic matches are not
            # starved out by keyword outliers on unrelated documents.
            score_cutoff = max(floor, best_score - spread)
            raw_cutoff = max(floor, raw_best - spread)
            results, seen = [], set()
            for i in order:
                if scores[i] < score_cutoff and raw_sim[i] < raw_cutoff:
                    continue
                row = rows[i]
                # One best chunk per file: rank fusion would otherwise reward long files.
                if row['file_path'] in seen:
                    continue
                seen.add(row['file_path'])
                results.append({**row, 'file_name': Path(row['file_path']).name,
                                'file_ext': Path(row['file_path']).suffix.lower(),
                                'similarity_score': float(scores[i])})
            return results
        finally:
            with self._lock:
                self._active_queries -= 1

    def __call__(self, request):
        query = getattr(request, 'query', '') if not isinstance(request, str) else request
        cancel = getattr(request, 'cancelled', None)
        should_cancel = cancel.is_set if hasattr(cancel, 'is_set') else (lambda: False)
        for row in self.search(query, should_cancel=should_cancel):
            yield row['file_path']

    def start(self, roots):
        """Index new or changed files under roots in a daemon thread; no-op while one runs or query active."""
        with self._lock:
            if self._active_queries > 0:
                return False
            if self._thread and self._thread.is_alive():
                return False
            self._stop.clear()
            self._thread = threading.Thread(target=self._run, args=(tuple(map(str, roots)),),
                                            name='rat-semantic-index', daemon=True)
            self._thread.start()
            return True

    def stop(self):
        self._stop.set()

    def _run(self, roots):
        try:
            self._index(roots)
            self._ocr_pass()
        except Exception as exc:
            logger.warning('semantic_index_failed: %s', type(exc).__name__)
            with self._lock:
                self._progress = {'state': 'unavailable', 'done': 0, 'total': 0}
        finally:
            if self._embedder is not None and hasattr(self._embedder, 'evict'):
                self._embedder.evict()

    def _index(self, roots):
        with self._lock:
            self._progress = {'state': 'scanning', 'done': 0, 'total': 0}
        paths = candidate_files(roots, self._stop.is_set)
        if self._stop.is_set():
            return
        with self._connect() as db:
            known = dict(db.execute('SELECT path, identity FROM files'))
        live = set(paths)
        gone = [p for p in known if p not in live and any(p.startswith(r.rstrip('/') + '/') for r in roots)]
        if gone:
            self.invalidate_paths(gone)
        todo = []
        for path in paths:
            if self._stop.is_set():
                return
            try:
                identity = file_identity(path)
            except OSError:
                continue
            if known.get(path) != json.dumps(identity):
                todo.append((path, identity))

        # Cheap identity check: if nothing changed, finish immediately without loading embedder
        if not todo:
            with self._lock:
                self._progress = {'state': 'ready', 'done': 0, 'total': 0}
            return

        with self._lock:
            self._progress = {'state': 'indexing', 'done': 0, 'total': len(todo)}
        for done, (path, identity) in enumerate(todo, 1):
            if self._stop.is_set():
                break
            # Never index while a query runs: pause background indexing if user is querying
            while self._active_queries > 0 and not self._stop.is_set():
                time.sleep(0.05)
            if self._stop.is_set():
                break
            try:
                chunks = document_chunks(path, read_document_text(path, ocr=False))
                vectors = self.embedder.embed_texts(chunks, batch_size=8)
            except Exception as exc:
                # Unreadable or encrypted documents still get their name indexed.
                logger.info('semantic_index_skip ext=%s code=%s', Path(path).suffix, type(exc).__name__)
                chunks = document_chunks(path, '')
                vectors = self.embedder.embed_texts(chunks)
            self._store(path, identity, chunks, vectors)
            with self._lock:
                self._progress = {'state': 'indexing', 'done': done, 'total': len(todo)}
            # Yield the CPU between files so typing and translation stay responsive.
            time.sleep(0.02)
        with self._lock:
            if not self._stop.is_set():
                self._progress = {'state': 'ready', 'done': len(todo), 'total': len(todo)}

    def _store(self, path, identity, chunks, vectors):
        with self._lock, self._connect() as db:
            db.execute('DELETE FROM chunks WHERE path = ?', (path,))
            db.executemany('INSERT INTO chunks VALUES (?, ?, ?, ?)',
                           [(path, i, text, vec.astype(np.float32).tobytes()) for i, (text, vec) in enumerate(zip(chunks, vectors))])
            db.execute('INSERT OR REPLACE INTO files VALUES (?, ?, ?, ?)',
                       (path, json.dumps(identity), os.stat(path).st_mtime, time.time()))
            self._matrix = None

    def _ocr_pass(self):
        """Read scanned PDFs that the fast pass could only index by name.

        Runs quietly after indexing (no progress line) and yields to queries. Each
        file version is tried once, so unreadable scans are not OCRed on every pass.
        """
        with self._connect() as db:
            rows = db.execute('''SELECT f.path, f.identity FROM files f
                LEFT JOIN ocr_checked o ON o.path = f.path AND o.identity = f.identity
                WHERE f.path LIKE '%.pdf' AND o.path IS NULL
                  AND (SELECT COUNT(*) FROM chunks c WHERE c.path = f.path) <= 1
                ORDER BY f.modified_at DESC LIMIT ?''', (OCR_FILES_PER_PASS,)).fetchall()
        for path, stored_identity in rows:
            while self._active_queries > 0 and not self._stop.is_set():
                time.sleep(0.05)
            if self._stop.is_set():
                return
            try:
                identity = file_identity(path)
                if json.dumps(identity) != stored_identity:
                    continue  # Changed since indexing; the next pass handles the new version.
                chunks = document_chunks(path, read_document_text(path, ocr=True))
                if len(chunks) > 1:
                    self._store(path, identity, chunks, self.embedder.embed_texts(chunks, batch_size=8))
            except Exception as exc:
                logger.info('semantic_index_ocr_skip code=%s', type(exc).__name__)
            with self._lock, self._connect() as db:
                db.execute('INSERT OR REPLACE INTO ocr_checked VALUES (?, ?)', (path, stored_identity))
            time.sleep(OCR_PAUSE_S)


_shared = {}
_shared_lock = threading.Lock()


def shared_index(database):
    """One index per database file, shared by every MiniSession the UI creates."""
    key = str(Path(database).resolve())
    with _shared_lock:
        if key not in _shared:
            _shared[key] = SemanticIndex(database)
        return _shared[key]
