"""Reproducible retrieval-only benchmark on a consistent SQLite backup."""

from __future__ import annotations

import argparse
from contextlib import ExitStack
from datetime import datetime, timezone
import hashlib
from importlib.metadata import version
import json
import os
from pathlib import Path
import platform
import random
import re
import resource
import sqlite3
import subprocess
import sys
import tempfile
import time
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
DEFAULT_QUERIES = [
    "quy chế đào tạo", "lịch học", "báo cáo pdf", "machine learning",
    "python", "học phí", "đồ án", "tài liệu tháng 9",
    "file tải từ Telegram", "ảnh hóa đơn",
]


def file_hash(path):
    digest = hashlib.sha256()
    with Path(path).open("rb") as source:
        for block in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def command(*args):
    result = subprocess.run(args, cwd=ROOT, capture_output=True, text=True, check=True)
    return result.stdout.strip()


def summarize(samples):
    import numpy as np
    return {
        phase: {
            "n": len(values),
            **{f"p{percentile}": float(np.percentile(values, percentile))
               for percentile in (50, 90, 95, 99)},
            "stages": {
                stage: {f"p{percentile}": float(np.percentile(
                    [sample["stages"][stage] for sample in samples if sample["phase"] == phase], percentile))
                    for percentile in (50, 90, 95, 99)}
                for stage in samples[0]["stages"]
            },
        }
        for phase in ("cold", "warm")
        if (values := [sample["total_ms"] for sample in samples if sample["phase"] == phase])
    }


def paired_query_bootstrap(runs, replicates=2000, seed=0):
    """Compare warm latency by resampling query clusters, never individual iterations."""
    import numpy as np

    per_query = {}
    for run in runs:
        per_query[run["method"]] = {
            query_id: float(np.median([
                sample["total_ms"] for sample in run["samples"]
                if sample["phase"] == "warm" and sample["query_id"] == query_id
            ]))
            for query_id in sorted({
                sample["query_id"] for sample in run["samples"] if sample["phase"] == "warm"
            })
        }

    rng = random.Random(seed)
    comparisons = {}
    methods = list(per_query)
    for left_index, left in enumerate(methods):
        for right in methods[left_index + 1:]:
            query_ids = sorted(set(per_query[left]) & set(per_query[right]))
            if not query_ids:
                continue
            deltas = [per_query[left][query_id] - per_query[right][query_id]
                      for query_id in query_ids]
            bootstrapped = [
                float(np.median([deltas[rng.randrange(len(deltas))] for _ in deltas]))
                for _ in range(replicates)
            ]
            comparisons[f"{left}_minus_{right}_ms"] = {
                "query_clusters": len(query_ids),
                "replicates": replicates,
                "median_delta_ms": float(np.median(deltas)),
                "bootstrap_p05_ms": float(np.percentile(bootstrapped, 5)),
                "bootstrap_p95_ms": float(np.percentile(bootstrapped, 95)),
            }
    return {
        "unit": "per-query median warm latency; query IDs resampled as clusters",
        "iterations_within_query_are_not_independent_samples": True,
        "seed": seed,
        "comparisons": comparisons,
    }


def worker(args):
    from rat.config import config
    config.db_path = args.snapshot
    config.use_slm = False
    from rat.crawler.db import Database, remove_vietnamese_accents
    from rat.engine.context_parser import ContextParser
    from rat.engine.embedder import LocalEmbedder, DEFAULT_EMBED_MODEL
    from rat.engine.llm_client import LLMClient
    from rat.engine.slm import SLMEngine
    from rat.engine.multi_way_rrf import MultiWayRRF, FacetResult
    from rat.engine.query_decomposer import query_decomposer
    from rat.engine.reranker import Reranker
    from rat.engine.vector_cache import VectorCache
    from fastembed import TextEmbedding
    import numpy as np

    database = Database(args.snapshot)
    encoder = LocalEmbedder()
    vectors = VectorCache(database)
    fuser = MultiWayRRF()
    reranker = Reranker()
    queries = json.loads(Path(args.queries).read_text())
    llm_calls = 0

    def forbidden(*unused_args, **unused_kwargs):
        nonlocal llm_calls
        llm_calls += 1
        raise AssertionError("Stage 0 attempted an LLM call")

    def strict_embed(query):
        if encoder._model is None:
            encoder._model = TextEmbedding(model_name=DEFAULT_EMBED_MODEL, local_files_only=True)
        matrix = np.asarray(list(encoder._model.embed([query])), dtype=np.float32)
        if matrix.shape != (1, 384) or not np.isfinite(matrix).all():
            raise RuntimeError("Invalid query embedding; random fallback is forbidden")
        norm = np.linalg.norm(matrix[0])
        if norm <= 0:
            raise RuntimeError("Zero query embedding")
        return matrix[0] / norm

    def bm25_candidates(plan, filters):
        terms = []
        for keyword in plan.lexical_keywords:
            safe = re.sub(r"[^\w]+", "", keyword.strip())
            if safe:
                terms.append(f"{safe}*")
                unaccented = remove_vietnamese_accents(safe)
                if unaccented != safe.lower():
                    terms.append(f"{unaccented}*")
        if not terms:
            return []
        conditions = ["documents_fts MATCH ?"]
        parameters = [" OR ".join(terms)]
        for name, operator, values in (
            ("file_ext", "IN", plan.extensions),
            ("file_ext", "NOT IN", plan.excluded_extensions),
        ):
            if values:
                conditions.append(f"d.{name} {operator} ({','.join('?' for value in values)})")
                parameters.extend(value.lower() for value in values)
        for name, operator in (("date_min", ">="), ("date_max", "<=")):
            if filters[name] is not None:
                conditions.append(f"d.modified_at {operator} ?")
                parameters.append(filters[name])
        return database.get_connection().execute(
            "SELECT d.id, d.file_path, d.file_name, d.file_ext, d.file_size, "
            "d.created_at, d.modified_at, d.content_text, d.summary, "
            "bm25(documents_fts, 15.0, 1.0, 1.0) AS rank "
            "FROM documents_fts JOIN documents d ON documents_fts.rowid=d.id WHERE "
            + " AND ".join(conditions) + " ORDER BY rank ASC LIMIT 45", parameters,
        ).fetchall()

    def run(query, query_id, iteration, phase):
        timers = {name: 0.0 for name in (
            "decompose_ms", "embed_query_ms", "fts5_ms", "vector_ms",
            "provenance_ms", "visual_ms", "rrf_fuse_ms", "rerank_ms",
        )}

        def timed(name, callback):
            started = time.perf_counter()
            value = callback()
            timers[name] += (time.perf_counter() - started) * 1000
            return value

        started = time.perf_counter()
        plan = timed("decompose_ms", lambda: query_decomposer.decompose(query, allow_slm=False))
        context = ContextParser.parse_query(query)
        context.source_app = plan.source_app
        context.source_domain = plan.source_domain
        context.visual_concepts = plan.visual_tags
        filters = dict(extensions=plan.extensions or None,
                       date_min=plan.date_min - 15 * 86400 if plan.date_min is not None else None,
                       date_max=plan.date_max + 15 * 86400 if plan.date_max is not None else None)
        streams = []
        if args.method == "bm25":
            results = timed("fts5_ms", lambda: bm25_candidates(plan, filters))
        if args.method in ("lexical", "hybrid"):
            sparse = timed("fts5_ms", lambda: database.search_candidates(
                keywords=plan.lexical_keywords, excluded_extensions=plan.excluded_extensions or None,
                limit=45, **filters))
            streams.append(FacetResult("lexical", sparse, 1.0))
        if args.method in ("vector", "hybrid"):
            query_vector = timed("embed_query_ms", lambda: strict_embed(plan.semantic_text or query))
            dense = timed("vector_ms", lambda: vectors.search(
                query_vector, excluded_extensions=plan.excluded_extensions or None, limit=45, **filters))
            streams.append(FacetResult("semantic", dense, 1.2, True))
        if args.method == "hybrid" and "provenance" in plan.active_facets:
            provenance = timed("provenance_ms", lambda: database.search_by_provenance(
                source_app=plan.source_app, source_domain=plan.source_domain, limit=30, **filters))
            streams.append(FacetResult("provenance", provenance, 1.5))
        if args.method == "hybrid" and "visual" in plan.active_facets and plan.visual_tags:
            visual = timed("visual_ms", lambda: database.search_by_vision_tags(
                tags=plan.visual_tags, limit=30, **filters))
            streams.append(FacetResult("visual", visual, 1.4))
        if args.method != "bm25":
            candidates = timed("rrf_fuse_ms", lambda: fuser.fuse(streams, top_k=45))
            results = timed("rerank_ms", lambda: reranker.rerank(query, context, candidates, top_k=15, use_llm=False))
        elapsed = (time.perf_counter() - started) * 1000
        assert llm_calls == 0
        return dict(query_id=query_id, query=query, iteration=iteration, phase=phase,
                    total_ms=elapsed, stages=timers, results=len(results),
                    candidate_counts={stream.facet_name: len(stream.candidates) for stream in streams},
                    rss_mb=float(command("ps", "-o", "rss=", "-p", str(os.getpid()))) / 1024)

    with ExitStack() as stack:
        for cls, methods in ((LLMClient, ("generate", "call_llm", "query_gemini", "query_openai", "query_ollama")),
                             (SLMEngine, ("generate", "generate_stream", "deconstruct_query"))):
            for name in methods:
                stack.enter_context(patch.object(cls, name, forbidden))
        samples = [run(queries[0], 0, 0, "cold")]
        for query_id, query in enumerate(queries):
            run(query, query_id, -1, "warmup")
        for iteration in range(args.iterations):
            for query_id, query in enumerate(queries):
                samples.append(run(query, query_id, iteration, "warm"))
        assert llm_calls == 0
    peak = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
    Path(args.output).write_text(json.dumps(dict(
        method=args.method, samples=samples, summary=summarize(samples), llm_calls=llm_calls,
        peak_rss_mb=peak / (1024 * 1024 if sys.platform == "darwin" else 1024),
    ), indent=2, ensure_ascii=False))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--db", default=str(Path.home() / ".rat" / "rat_index.db"))
    parser.add_argument("--queries", help="JSON array of non-empty query strings")
    parser.add_argument("--iterations", type=int, default=3)
    parser.add_argument("--output")
    parser.add_argument("--snapshot", help=argparse.SUPPRESS)
    parser.add_argument("--method", choices=("bm25", "lexical", "vector", "hybrid"), help=argparse.SUPPRESS)
    args = parser.parse_args()
    if args.iterations < 1:
        parser.error("iterations must be positive")
    if args.method:
        worker(args)
        return
    queries = json.loads(Path(args.queries).read_text()) if args.queries else DEFAULT_QUERIES
    if not isinstance(queries, list) or not queries or not all(isinstance(query, str) and query.strip() for query in queries):
        parser.error("queries must be a non-empty JSON array of non-empty strings")
    timestamp = datetime.now(timezone.utc)
    output = Path(args.output) if args.output else ROOT / "scratch" / f"baseline_stage0_{timestamp:%Y%m%dT%H%M%S%fZ}.json"
    output.parent.mkdir(parents=True, exist_ok=True)
    source_hashes = {str(path.relative_to(ROOT)): file_hash(path)
                     for directory in (ROOT / "rat", ROOT / "scripts")
                     for path in sorted(directory.rglob("*.py"))}
    with tempfile.TemporaryDirectory(prefix="rat-stage0-") as temporary:
        snapshot = Path(temporary) / "snapshot.db"
        source = sqlite3.connect(Path(args.db).resolve().as_uri() + "?mode=ro", uri=True)
        destination = sqlite3.connect(snapshot)
        try:
            source.backup(destination)
            counts = {name: destination.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]
                      for name, table in (("n_files", "documents"), ("n_chunks", "document_chunks"))}
            counts["n_embeddings"] = destination.execute(
                "SELECT COUNT(*) FROM document_chunks WHERE embedding IS NOT NULL"
            ).fetchone()[0]
        finally:
            source.close()
            destination.close()
        query_file = Path(temporary) / "queries.json"
        query_file.write_text(json.dumps(queries, ensure_ascii=False))
        from rat.config import config
        config.db_path = str(snapshot)
        from rat.engine.embedder import DEFAULT_EMBED_MODEL
        payload = dict(manifest=dict(
            protocol="stage0-v1", date=timestamp.isoformat(), **counts,
            use_hyde=False, use_slm=False,
            model=DEFAULT_EMBED_MODEL, embedding_model_provenance="index does not persist model identity; assumed, not verified",
            git_sha=command("git", "rev-parse", "HEAD"), git_status=command("git", "status", "--porcelain"),
            source_sha256=source_hashes, snapshot_sha256=file_hash(snapshot),
            query_sha256=file_hash(query_file), queries=queries, iterations=args.iterations,
            power_source=command("pmset", "-g", "batt") if sys.platform == "darwin" else "unknown",
            platform=platform.platform(), python=sys.version,
            packages={package: version(package) for package in ("numpy", "fastembed", "onnxruntime")},
            cold_definition="first query per fresh worker; lazy model/vector load included; OS disk cache not flushed",
            warm_definition="all queries warmed once; query embedding computed each time, no query-result cache",
            scope="decompose + lexical/vector/4-way hybrid + fusion + heuristic rerank; no HyDE/correction/LLM",
            fts5_ms_scope="bm25 method: SQLite FTS5 only; lexical/hybrid: production FTS5 + filename/LIKE fallback",
            mrrf_scale="production rrf_score normalized 0..100",
        ), runs=[], status="running")
        try:
            for method in ("bm25", "lexical", "vector", "hybrid"):
                worker_output = Path(temporary) / f"{method}.json"
                subprocess.run([sys.executable, str(Path(__file__).resolve()), "--method", method,
                                "--snapshot", str(snapshot), "--queries", str(query_file),
                                "--iterations", str(args.iterations), "--output", str(worker_output)], check=True)
                payload["runs"].append(json.loads(worker_output.read_text()))
            expected_methods = ["bm25", "lexical", "vector", "hybrid"]
            actual_methods = [run.get("method") for run in payload["runs"]]
            if actual_methods != expected_methods:
                raise RuntimeError(f"Incomplete benchmark methods: {actual_methods}")
            if any(run.get("llm_calls") != 0 for run in payload["runs"]):
                raise RuntimeError("Stage 0 recorded an LLM/SLM call")
            payload["paired_query_bootstrap"] = paired_query_bootstrap(payload["runs"])
            payload["status"] = "complete"
        except Exception as error:
            payload["status"] = "failed"
            payload["error"] = str(error)
            raise
        finally:
            output.write_text(json.dumps(payload, indent=2, ensure_ascii=False))
            print(output)


if __name__ == "__main__":
    main()
