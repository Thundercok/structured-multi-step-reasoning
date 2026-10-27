"""Opt-in, bounded local semantic index. No model or file loads at import/startup."""
from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
import threading
import time
import gc


class LocalSemanticIndex:
    def __init__(self, model_root, database, scopes):
        self.root, self.database, self.scopes = Path(model_root), Path(database), scopes
        self.session = self.tokenizer = None
        self.lock = threading.RLock()
        self.last_used = 0.0

    def _connection(self):
        import apsw
        import sqlite_vec
        self.database.parent.mkdir(parents=True, exist_ok=True)
        connection = apsw.Connection(str(self.database))
        connection.enable_load_extension(True)
        try:
            connection.load_extension(sqlite_vec.loadable_path())
        finally:
            connection.enable_load_extension(False)
        connection.execute('create table if not exists chunks(id integer primary key, path text, identity text, text text)')
        connection.execute('create virtual table if not exists vectors using vec0(embedding float[384])')
        connection.execute('create table if not exists index_meta(key text primary key, value text)')
        return connection

    def count(self):
        if not self.database.exists():
            return 0
        with self.lock:
            c = self._connection()
            try:
                return c.execute('select count(*) from chunks').fetchone()[0]
            finally:
                c.close()

    def _load(self):
        if self.session is not None:
            return
        import onnxruntime as ort
        from tokenizers import Tokenizer
        manifest = json.loads((self.root / 'manifest.json').read_text())
        for item in manifest['files']:
            path = self.root / item['rfilename']
            payload = path.read_bytes()
            if len(payload) != item['size']:
                raise ValueError('model_size_mismatch')
            if 'lfs' in item and hashlib.sha256(payload).hexdigest() != item['lfs']['sha256']:
                raise ValueError('model_checksum_mismatch')
            if 'lfs' not in item and hashlib.sha1(f'blob {len(payload)}\0'.encode()+payload).hexdigest() != item['blobId']:
                raise ValueError('model_metadata_checksum_mismatch')
        options = ort.SessionOptions()
        options.intra_op_num_threads = 2
        options.inter_op_num_threads = 1
        self.tokenizer = Tokenizer.from_file(str(self.root / 'tokenizer.json'))
        self.tokenizer.no_truncation()
        self.tokenizer.enable_padding(pad_id=1, pad_token='<pad>')
        self.session = ort.InferenceSession(str(self.root / manifest['model_file']), sess_options=options,
                                           providers=['CPUExecutionProvider'])

    def embed(self, texts):
        import numpy as np
        self._load()
        self.last_used = time.monotonic()
        encoded = self.tokenizer.encode_batch(texts)
        if max(len(e.ids) for e in encoded) > 512:
            raise ValueError('embedding_chunk_too_long')
        arrays = {'input_ids': np.array([e.ids for e in encoded], dtype=np.int64),
                  'attention_mask': np.array([e.attention_mask for e in encoded], dtype=np.int64),
                  'token_type_ids': np.array([e.type_ids for e in encoded], dtype=np.int64)}
        output = self.session.run(None, {i.name: arrays[i.name] for i in self.session.get_inputs()})[0]
        mask = arrays['attention_mask'][..., None]
        vector = (output * mask).sum(axis=1) / mask.sum(axis=1)
        vector /= np.linalg.norm(vector, axis=1, keepdims=True)
        if not np.isfinite(vector).all():
            raise ValueError('embedding_not_finite')
        return vector.astype(np.float32)

    def pieces(self, text):
        # Special-token offsets are (0,0); including a trailing SEP would drop
        # the final real chunk. Chunk the raw text tokens, then add specials at embed.
        encoded = self.tokenizer.encode(text, add_special_tokens=False)
        for start in range(0, len(encoded.ids), 320):
            end = min(start+384, len(encoded.ids))
            left, right = encoded.offsets[start][0], encoded.offsets[end-1][1]
            piece = text[left:right]
            if piece.strip():
                yield piece

    def index(self, should_cancel, progress=lambda text: None):
        with self.lock:
            self._load()
            version, roots = self.scopes.version, self.scopes.roots
            c = self._connection()
            indexed, skipped, chunks, scanned, capped = 0, 0, 0, 0, 0
            try:
                c.execute('begin immediate')
                c.execute('delete from vectors')
                c.execute('delete from chunks')
                for root in roots:
                    for parent, dirs, files in os.walk(root, followlinks=False):
                        dirs[:] = [d for d in dirs if not d.startswith('.') and d not in
                                   ('node_modules', 'audit', 'work', 'build', 'dist', '__pycache__')]
                        for name in files:
                            if should_cancel() or version != self.scopes.version:
                                raise ValueError('cancelled:index')
                            scanned += 1
                            if scanned > 10_000 or chunks >= 100_000:
                                raise ValueError('index_limit_reached')
                            path = Path(parent) / name
                            if path.suffix.lower() not in ('.txt', '.md', '.pdf'):
                                continue
                            last_id = c.execute('select coalesce(max(id),0) from chunks').fetchone()[0]
                            previous_chunks = chunks
                            try:
                                path, info, identity = self.scopes.verify(path)
                                if info.st_size > 20_000_000:
                                    skipped += 1
                                    continue
                                if path.suffix.lower() == '.pdf':
                                    from document_intake.pdf import read_pdf
                                    result = read_pdf(str(path), max_pages=200, max_chars=100_000)
                                    text = result.get('full_text', '')
                                    capped += int(result.get('extraction_truncated', False))
                                else:
                                    original = path.read_text(encoding='utf-8')
                                    capped += int(len(original) > 100_000)
                                    text = original[:100_000]
                                if not text.strip():
                                    skipped += 1
                                    continue
                                self.scopes.verify(path, identity)
                                # Tokenizer-bound chunks preserve actual source text; 384 leaves prefix/special token room.
                                for piece in self.pieces(text):
                                    if should_cancel():
                                        raise ValueError('cancelled:index')
                                    vector = self.embed(['passage: ' + piece])[0]
                                    c.execute('insert into chunks(path,identity,text) values (?,?,?)',
                                              (str(path), json.dumps(identity), piece))
                                    chunk_id = c.last_insert_rowid()
                                    c.execute('insert into vectors(rowid,embedding) values (?,?)', (chunk_id, vector.tobytes()))
                                    chunks += 1
                                self.scopes.verify(path, identity)
                                indexed += 1
                                progress(f'Đã lập chỉ mục {indexed} file · {chunks} đoạn')
                            except (OSError, UnicodeError, ValueError) as exc:
                                if str(exc).startswith('cancelled:'):
                                    raise
                                c.execute('delete from vectors where rowid in (select id from chunks where id>?)', (last_id,))
                                c.execute('delete from chunks where id>?', (last_id,))
                                chunks = previous_chunks
                                skipped += 1
                if version != self.scopes.version or should_cancel():
                    raise ValueError('cancelled:index')
                fingerprint = hashlib.sha256((self.root / 'manifest.json').read_bytes()).hexdigest()
                c.execute('insert or replace into index_meta values (?,?)', ('model_manifest', fingerprint))
                c.execute('insert or replace into index_meta values (?,?)', ('scope_version', version))
                c.execute('commit')
                return {'status': 'partial' if skipped or capped else 'complete', 'indexed_files': indexed,
                        'chunks': chunks, 'skipped': skipped, 'capped': capped, 'update_mode': 'manual_rebuild'}
            except Exception:
                c.execute('rollback')
                raise
            finally:
                c.close()

    def search(self, query, should_cancel):
        with self.lock:
            if should_cancel():
                raise ValueError('cancelled:semantic')
            vector = self.embed(['query: ' + query])[0]
            c = self._connection()
            try:
                metadata = dict(c.execute('select key,value from index_meta'))
                fingerprint = hashlib.sha256((self.root / 'manifest.json').read_bytes()).hexdigest()
                if metadata.get('model_manifest') != fingerprint or metadata.get('scope_version') != self.scopes.version:
                    raise ValueError('index_incompatible_rebuild_required')
                result = []
                for rowid, distance in c.execute('select rowid,distance from vectors where embedding match ? and k=40 order by distance',
                                                (vector.tobytes(),)):
                    row = c.execute('select path,identity,text from chunks where id=?', (rowid,)).fetchone()
                    if row:
                        result.append({'file_path': row[0], 'identity': json.loads(row[1]),
                                       'chunk_text': row[2], 'similarity_score': 1-float(distance)**2/2})
                return result
            finally:
                c.close()

    def unload(self):
        with self.lock:
            self.session = self.tokenizer = None
        gc.collect()

    def release_if_idle(self, idle_seconds=90):
        if self.session is not None and time.monotonic()-self.last_used >= idle_seconds:
            self.unload()
            return True
        return False

    def invalidate_paths(self, paths):
        with self.lock:
            c = self._connection()
            try:
                with c:
                    for path in set(paths):
                        c.execute('delete from vectors where rowid in (select id from chunks where path=?)', (path,))
                        c.execute('delete from chunks where path=?', (path,))
            finally:
                c.close()

    def purge(self):
        """Delete only this regenerable application index on scope revocation."""
        with self.lock:
            for path in (self.database, Path(str(self.database)+'-wal'), Path(str(self.database)+'-shm')):
                path.unlink(missing_ok=True)
