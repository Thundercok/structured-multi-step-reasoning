#!/usr/bin/env python3
"""
scripts/batch_embed_all.py — High-Throughput Safe Batch Embedding Worker for 'rat'.
Embeds all remaining documents into SQLite and keeps memory/thermal foot-print minimal on Apple Silicon.
Includes a hard deadline guard to cleanly finish well before user takes the laptop.
"""

import argparse
import ctypes
import datetime
import os
import signal
import sqlite3
import sys
import time
from pathlib import Path
from typing import List, Tuple

# Ensure project root in sys.path
PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from rat.config import config
from rat.crawler.chunker import chunker
from rat.crawler.db import Database
from rat.engine.embedder import embedder

# Global stop flag
STOP_REQUESTED = False


def set_macos_background_qos() -> bool:
    """Assign current process/thread to Apple Silicon Efficiency Cores (low power, 0dB fan)."""
    if sys.platform == "darwin":
        try:
            lib = ctypes.CDLL("libSystem.dylib")
            # 0x09 = QOS_CLASS_BACKGROUND in macOS pthread
            res = lib.pthread_set_qos_class_self_np(0x09, 0)
            os.nice(10)
            return res == 0
        except Exception:
            pass
    return False


def signal_handler(signum, frame):
    global STOP_REQUESTED
    print("\n🛑 Stop signal received. Finishing current batch and saving state...")
    STOP_REQUESTED = True


def get_unembedded_docs(db_path: str) -> List[Tuple[int, str, str, str]]:
    """
    Retrieve documents that have substantial content (> 50 chars) but no chunks yet.
    Prioritizes key document types: pdf, docx, pptx, md, py, txt.
    Returns: List of (id, file_path, file_name, content_text)
    """
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()

    # Prioritized order: documents/code first, then data/others
    sql = """
        SELECT d.id, d.file_path, d.file_name, d.file_ext, d.content_text
        FROM documents d
        LEFT JOIN document_chunks c ON d.id = c.doc_id
        WHERE c.doc_id IS NULL AND length(trim(d.content_text)) > 50
        ORDER BY 
            CASE 
                WHEN d.file_ext IN ('.pdf', '.docx', '.pptx', '.doc', '.ppt') THEN 1
                WHEN d.file_ext IN ('.md', '.py', '.txt', '.ipynb') THEN 2
                WHEN d.file_ext IN ('.xlsx', '.csv', '.json', '.html') THEN 3
                ELSE 4
            END,
            d.file_size ASC
    """
    cursor.execute(sql)
    rows = cursor.fetchall()
    results = [(r["id"], r["file_path"], r["file_name"], r["content_text"]) for r in rows]
    conn.close()
    return results


def run_batch_embedding(
    deadline_str: str = "06:15",
    batch_doc_count: int = 25,
    chunk_embed_batch_size: int = 64,
    limit: int = 0
) -> Tuple[int, int, float]:
    """
    Process unembedded documents in transactions of batch_doc_count.
    Embeds chunk texts in batches using FastEmbed ONNX Runtime.
    Returns: (total_docs_processed, total_chunks_saved, elapsed_sec)
    """
    global STOP_REQUESTED
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)

    set_macos_background_qos()
    db_path = config.db_path
    print(f"🐀 [rat-batch-embed] Database: {db_path}")

    unembedded = get_unembedded_docs(db_path)
    total_unembedded = len(unembedded)
    if limit > 0:
        unembedded = unembedded[:limit]
        total_unembedded = len(unembedded)

    print(f"📚 Found {total_unembedded} documents requiring vector embeddings.")
    if total_unembedded == 0:
        print("✅ All eligible documents already have chunk vector embeddings!")
        return 0, 0, 0.0

    # Parse deadline
    now = datetime.datetime.now()
    try:
        h, m = map(int, deadline_str.split(":"))
        deadline_dt = now.replace(hour=h, minute=m, second=0, microsecond=0)
        # If deadline is already past today, set it to tomorrow
        if deadline_dt <= now:
            deadline_dt += datetime.timedelta(days=1)
    except Exception:
        deadline_dt = now + datetime.timedelta(hours=4)

    deadline_ts = deadline_dt.timestamp()
    print(f"⏰ Hard Stop Deadline: {deadline_dt.strftime('%Y-%m-%d %H:%M:%S')} (will exit cleanly before then)")
    print(f"🚀 Starting batch embedding on Apple Silicon (Background QoS)...")

    # Warm up embedder
    embedder.embed_texts(["Warmup test embedding"])

    conn = sqlite3.connect(db_path, timeout=60.0)
    cursor = conn.cursor()
    cursor.execute("PRAGMA synchronous = NORMAL")
    cursor.execute("PRAGMA journal_mode = WAL")

    t_start = time.time()
    docs_processed = 0
    chunks_saved = 0

    try:
        for idx in range(0, len(unembedded), batch_doc_count):
            if STOP_REQUESTED:
                break

            # Check deadline before starting next batch
            if time.time() >= deadline_ts:
                print(f"\n⚠️ Reached hard deadline ({deadline_str})! Halting gracefully...")
                break

            batch_docs = unembedded[idx:idx + batch_doc_count]

            # 1. Chunk all docs in this batch
            batch_chunks_info = []  # (doc_id, file_path, chunk_index, chunk_text)
            for doc_id, file_path, file_name, content_text in batch_docs:
                chunks = chunker.chunk_text(content_text)
                if not chunks:
                    continue
                # Cap chunks per doc at 20 to avoid pathological infinite-text files
                capped_chunks = chunks[:20]
                for c in capped_chunks:
                    batch_chunks_info.append((doc_id, file_path, c.chunk_index, c.text))

            if not batch_chunks_info:
                docs_processed += len(batch_docs)
                continue

            # 2. Embed chunk texts in vectorized ONNX batch
            chunk_texts = [item[3] for item in batch_chunks_info]
            embeddings = embedder.embed_texts(chunk_texts, batch_size=chunk_embed_batch_size)

            # 3. Write rows to SQLite in a single transaction
            rows_to_insert = []
            for i, item in enumerate(batch_chunks_info):
                if i < len(embeddings):
                    emb_bytes = embeddings[i].tobytes()
                    rows_to_insert.append((item[0], item[1], item[2], item[3], emb_bytes))

            cursor.executemany("""
                INSERT INTO document_chunks (doc_id, file_path, chunk_index, chunk_text, embedding)
                VALUES (?, ?, ?, ?, ?)
            """, rows_to_insert)
            conn.commit()

            docs_processed += len(batch_docs)
            chunks_saved += len(rows_to_insert)

            # Logging metrics
            elapsed = time.time() - t_start
            rate_docs = docs_processed / max(elapsed, 0.001)
            rate_chunks = chunks_saved / max(elapsed, 0.001)
            pct = (docs_processed / total_unembedded) * 100
            remaining_docs = total_unembedded - docs_processed
            eta_sec = remaining_docs / max(rate_docs, 0.001)
            eta_min = eta_sec / 60.0

            last_name = batch_docs[-1][2]
            if len(last_name) > 30:
                last_name = last_name[:27] + "..."

            print(
                f"[{docs_processed:4d}/{total_unembedded:4d}] {pct:5.1f}% | "
                f"{rate_docs:4.1f} docs/s ({rate_chunks:4.1f} chk/s) | "
                f"ETA: {eta_min:4.1f}m | Chunks: {chunks_saved:5d} | "
                f"Latest: {last_name}"
            )

    except Exception as e:
        print(f"\n❌ Error during batch embedding: {e}")
        conn.commit()
    finally:
        # Checkpoint WAL
        try:
            cursor.execute("PRAGMA wal_checkpoint(PASSIVE)")
        except Exception:
            pass
        conn.close()

    elapsed = time.time() - t_start
    print(f"\n✨ Completed! Processed {docs_processed} docs ({chunks_saved} chunks) in {elapsed/60.0:.2f} mins.")
    return docs_processed, chunks_saved, elapsed


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="High-Throughput Safe Batch Embedding Worker")
    parser.add_argument("--deadline", type=str, default="06:15", help="HH:MM hard deadline (default 06:15)")
    parser.add_argument("--batch-docs", type=int, default=25, help="Number of documents per commit batch")
    parser.add_argument("--batch-size", type=int, default=64, help="FastEmbed chunk batch size")
    parser.add_argument("--limit", type=int, default=0, help="Optional max docs to process (0 = all)")
    args = parser.parse_args()

    run_batch_embedding(
        deadline_str=args.deadline,
        batch_doc_count=args.batch_docs,
        chunk_embed_batch_size=args.batch_size,
        limit=args.limit
    )
