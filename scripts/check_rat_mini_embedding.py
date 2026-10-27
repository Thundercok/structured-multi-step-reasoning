"""Explicit pinned local ONNX smoke on authored sentences, not a quality study.

Never downloads or loads remote Python code. Verify model bundle against metadata
before importing inference libraries. Not imported by RAT Mini at startup.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import platform
import resource
import time


def verify_bundle(root, manifest):
    root = Path(root).resolve(strict=True)
    total, observed = 0, []
    for entry in manifest["files"]:
        path = (root / entry["rfilename"]).resolve(strict=True)
        if not path.is_relative_to(root) or not path.is_file():
            raise ValueError("model asset outside bundle")
        payload = path.read_bytes()
        if len(payload) != entry["size"]:
            raise ValueError("model asset size mismatch")
        checksum = hashlib.sha256(payload).hexdigest()
        if "lfs" in entry:
            if checksum != entry["lfs"]["sha256"]:
                raise ValueError("model asset SHA256 mismatch")
        else:
            git_blob = hashlib.sha1(f"blob {len(payload)}\0".encode() + payload).hexdigest()
            if git_blob != entry["blobId"]:
                raise ValueError("model asset Git blob mismatch")
        total += len(payload)
        observed.append({"file": entry["rfilename"], "bytes": len(payload), "sha256": checksum})
    if total != manifest["selected_bytes"] or total >= 150_000_000:
        raise ValueError("model bundle exceeds byte budget or manifest size")
    return total, observed


def smoke(root, manifest):
    total, assets = verify_bundle(root, manifest)
    import numpy as np
    import onnxruntime as ort
    from tokenizers import Tokenizer

    texts = ["query: tài liệu về chăm sóc mèo",
             "passage: A guide to feeding and caring for cats.",
             "passage: Quarterly financial report on company revenue.",
             "passage: Hướng dẫn cho mèo ăn và chăm sóc sức khỏe của mèo."]
    tokenizer = Tokenizer.from_file(str(Path(root) / "tokenizer.json"))
    tokenizer.no_truncation()
    tokenizer.enable_padding(pad_id=1, pad_token="<pad>")
    encoded = tokenizer.encode_batch(texts)
    if max(len(item.ids) for item in encoded) > 512:
        raise ValueError("smoke input exceeds token limit")
    options = ort.SessionOptions()
    options.intra_op_num_threads = 2
    options.inter_op_num_threads = 1
    options.execution_mode = ort.ExecutionMode.ORT_SEQUENTIAL
    started = time.perf_counter()
    session = ort.InferenceSession(str(Path(root) / manifest["model_file"]),
                                   sess_options=options, providers=["CPUExecutionProvider"])
    initialization = time.perf_counter() - started
    arrays = {"input_ids": np.array([item.ids for item in encoded], dtype=np.int64),
              "attention_mask": np.array([item.attention_mask for item in encoded], dtype=np.int64),
              "token_type_ids": np.array([item.type_ids for item in encoded], dtype=np.int64)}
    inputs = {value.name: arrays[value.name] for value in session.get_inputs()}
    timings, pooled = [], None
    for _ in range(4):
        started = time.perf_counter()
        token_vectors = session.run(None, inputs)[0]
        mask = arrays["attention_mask"][..., None]
        pooled = (token_vectors * mask).sum(axis=1) / mask.sum(axis=1)
        pooled /= np.linalg.norm(pooled, axis=1, keepdims=True)
        timings.append((time.perf_counter() - started) * 1000)
    norms = np.linalg.norm(pooled, axis=1)
    if pooled.shape != (4, 384) or not np.isfinite(pooled).all() or not np.allclose(norms, 1):
        raise ValueError("invalid embedding output")
    scores = pooled[1:] @ pooled[0]
    return {"status": "passed", "kind": "development_inference_smoke_not_quality_acceptance",
            "repo_id": manifest["repo_id"], "revision": manifest["revision"],
            "environment": {"macos": platform.mac_ver()[0], "machine": platform.machine(),
                            "onnxruntime": ort.__version__, "providers": session.get_providers()},
            "bundle_bytes": total, "assets": assets, "shape": list(pooled.shape),
            "unit_norms": norms.tolist(), "initialization_seconds": initialization,
            "batch_inference_ms": timings, "batch_size": len(texts),
            "process_peak_rss_bytes": resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
                * (1 if platform.system() == "Darwin" else 1024),
            "rss_scope": "whole smoke Python process; not application idle or system unified memory",
            "authored_smoke_texts": texts, "cosine_scores": scores.tolist(),
            "ranked_passage_indices": (np.argsort(-scores) + 1).tolist(),
            "quality_acceptance": False, "target_m3_8gb_acceptance": False,
            "research_campaign": False, "model_downloaded_by_this_script": False}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--model-dir", type=Path, required=True)
    parser.add_argument("--manifest", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    manifest = json.loads(args.manifest.read_text())
    report = smoke(args.model_dir, manifest)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n")
    print(json.dumps({key: report[key] for key in ("status", "bundle_bytes", "shape",
                      "initialization_seconds", "batch_inference_ms", "process_peak_rss_bytes",
                      "quality_acceptance")}, indent=2))


if __name__ == "__main__":
    main()
