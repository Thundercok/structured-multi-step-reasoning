"""Compare stored vectors with strict, cached re-embedding on a closed snapshot."""

import argparse
from collections import defaultdict
from contextlib import closing
from datetime import datetime, timezone
import hashlib
from importlib.metadata import version
import json
import os
from pathlib import Path
import random
import sqlite3
import sys
import time

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))


def file_hash(path):
    digest = hashlib.sha256()
    with Path(path).open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def summarize(records, threshold):
    values = [row["cosine"] for row in records if row["status"] == "compared"]
    return dict(
        sampled=len(records), compared=len(values), invalid_stored=len(records) - len(values),
        below_threshold=sum(value < threshold for value in values),
        cosine_percentiles={str(percentile): float(np.percentile(values, percentile)) for percentile in (0, 5, 50, 95, 100)} if values else {},
    )


def compare_embeddings(connection, encode_texts, sample_size=300, seed=42, threshold=0.99):
    if sample_size < 1 or not -1 <= threshold <= 1:
        raise ValueError("Positive sample size and cosine threshold in [-1, 1] required")
    eligible = [row[0] for row in connection.execute("""
        SELECT chunk.id FROM document_chunks AS chunk
        JOIN documents AS parent ON parent.id=chunk.doc_id AND parent.file_path=chunk.file_path
        WHERE chunk.embedding IS NOT NULL ORDER BY chunk.id
    """)]
    if not eligible:
        raise ValueError("No validly linked stored embeddings to audit")
    selected = sorted(random.Random(seed).sample(eligible, min(sample_size, len(eligible))))
    samples = [connection.execute("""
        SELECT chunk.id, chunk.doc_id, chunk.chunk_text, chunk.embedding, parent.indexed_at
        FROM document_chunks AS chunk JOIN documents AS parent ON parent.id=chunk.doc_id
        WHERE chunk.id=?
    """, (chunk_id,)).fetchone() for chunk_id in selected]
    started = time.perf_counter()
    fresh = np.asarray(encode_texts([row[2] for row in samples]), dtype=np.float32)
    elapsed = time.perf_counter() - started
    if fresh.ndim != 2 or fresh.shape[0] != len(samples) or not np.isfinite(fresh).all():
        raise RuntimeError("Invalid fresh embedding matrix; fallback is forbidden")
    fresh_norms = np.linalg.norm(fresh.astype(np.float64), axis=1)
    if np.any(fresh_norms <= 0) or not np.isfinite(fresh_norms).all():
        raise RuntimeError("Invalid fresh embedding norms; fallback is forbidden")
    records, weeks = [], defaultdict(list)
    for index, (chunk_id, doc_id, chunk_text, blob, indexed_at) in enumerate(samples):
        calendar = datetime.fromtimestamp(indexed_at, timezone.utc).isocalendar()
        record = dict(
            chunk_id=chunk_id, doc_id=doc_id, indexed_week=f"{calendar.year}-W{calendar.week:02d}",
            chunk_text_sha256=hashlib.sha256(chunk_text.encode("utf-8")).hexdigest(),
            stored_vector_sha256=hashlib.sha256(blob).hexdigest(), status="invalid_stored_vector",
        )
        if len(blob) and len(blob) % np.dtype(np.float32).itemsize == 0:
            stored = np.frombuffer(blob, dtype=np.float32).astype(np.float64)
            norm = np.linalg.norm(stored)
            if stored.shape != (fresh.shape[1],):
                record["status"] = "dimension_mismatch"
            elif np.isfinite(stored).all() and np.isfinite(norm) and norm > 0:
                cosine = float(np.dot(stored / norm, fresh[index].astype(np.float64) / fresh_norms[index]))
                record.update(status="compared", cosine=float(np.clip(cosine, -1, 1)), stored_norm=float(norm), fresh_norm=float(fresh_norms[index]))
        records.append(record)
        weeks[record["indexed_week"]].append(record)
    return dict(
        eligible_chunks=len(eligible), sample_size=len(records), seed=seed, threshold=threshold,
        sampling="seeded sample of sorted chunk IDs, without replacement; valid ID/path links only",
        embedding_seconds=elapsed, summary=summarize(records, threshold),
        by_indexed_week={week: summarize(rows, threshold) for week, rows in sorted(weeks.items())},
        records=records,
        interpretation="Low cosine flags inconsistency, not proof of a particular old model. indexed_at is the document's latest index time, not a persisted vector creation time.",
    )


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--db", required=True, help="Closed snapshot, not the live index")
    parser.add_argument("--output", required=True, help="New JSON report, never overwritten")
    parser.add_argument("--sample-size", type=int, default=300)
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--threshold", type=float, default=0.99)
    args = parser.parse_args()
    output = Path(args.output)
    if output.exists():
        parser.error("Output already exists")
    source = Path(args.db).resolve()
    wal = Path(str(source) + "-wal")
    if wal.exists() and wal.stat().st_size:
        parser.error("Active WAL is not a closed snapshot; make a SQLite backup first")
    os.environ["HF_HUB_OFFLINE"] = "1"
    os.environ["TRANSFORMERS_OFFLINE"] = "1"
    report = dict(status="running", source=str(source), source_sha256=file_hash(source))
    try:
        from fastembed import TextEmbedding
        from rat.engine.embedder import DEFAULT_EMBED_MODEL, LocalEmbedder
        started = time.perf_counter()
        backend = TextEmbedding(model_name=DEFAULT_EMBED_MODEL, local_files_only=True, threads=1)
        encoder = LocalEmbedder(DEFAULT_EMBED_MODEL)
        encoder._model = backend
        probe = np.asarray(list(backend.embed(["test"])), dtype=np.float32)
        if probe.ndim != 2 or probe.shape[0] != 1 or probe.shape[1] == 0:
            raise RuntimeError("Invalid cached model output shape")
        encoder._dimension = probe.shape[1]
        report["load_seconds"] = time.perf_counter() - started
        model_dir = Path(backend.model._model_dir)
        report.update(
            model=DEFAULT_EMBED_MODEL, model_directory=str(model_dir),
            model_sha256={str(path.relative_to(model_dir)): file_hash(path) for path in sorted(model_dir.rglob("*")) if path.is_file()},
            source_code_sha256={str(path.relative_to(ROOT)): file_hash(path) for path in (Path(__file__).resolve(), ROOT / "rat/engine/embedder.py")},
            packages={name: version(name) for name in ("numpy", "fastembed", "onnxruntime")},
            preprocessing="stored chunk_text unchanged; current LocalEmbedder.embed_texts float32 L2 normalization",
            local_files_only=True, generation_calls=0, python=sys.version,
        )
        with closing(sqlite3.connect(source.as_uri() + "?mode=ro&immutable=1", uri=True)) as connection:
            report["audit"] = compare_embeddings(connection, encoder.embed_texts, args.sample_size, args.seed, args.threshold)
        report["source_sha256_after"] = file_hash(source)
        if report["source_sha256_after"] != report["source_sha256"] or (wal.exists() and wal.stat().st_size):
            raise RuntimeError("Snapshot changed during audit")
        report["status"] = "complete"
    except Exception as error:
        report.update(status="failed", error=str(error))
    with output.open("x", encoding="utf-8") as stream:
        json.dump(report, stream, indent=2, ensure_ascii=False, allow_nan=False)
    print(output)
    return 0 if report["status"] == "complete" else 1


if __name__ == "__main__":
    raise SystemExit(main())
