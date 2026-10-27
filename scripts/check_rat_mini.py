"""Explicit, headless RAT Mini compatibility probes; never starts the application.

No network, model inference/download, clipboard/screen capture or permission prompt.
Spotlight runs only when an explicit scope and known filename are supplied.
Vector smoke uses two synthetic vectors in memory, not a retrieval quality test.
"""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import importlib.metadata
import json
from pathlib import Path
import platform
import shutil
import sqlite3
import subprocess
import sys


PACKAGE_NAMES = ("PyQt6", "certifi", "onnxruntime", "fastembed", "sqlite-vec", "apsw")


def _run(argv, *, timeout=10, input_text=None):
    try:
        result = subprocess.run(argv, input=input_text, capture_output=True,
                                text=True, timeout=timeout, check=False)
        return {"exit_code": result.returncode, "stdout": result.stdout,
                "stderr": result.stderr}
    except subprocess.TimeoutExpired:
        return {"error": "timeout"}
    except OSError as exc:
        return {"error": type(exc).__name__}


def spotlight_probe(scope: Path, known_name: str):
    """Check one known file in a caller-chosen scope; do not publish hit paths."""
    if not known_name or Path(known_name).name != known_name or "\x00" in known_name:
        raise ValueError("known_name must be a single filename")
    scope = scope.expanduser().resolve(strict=True)
    if not scope.is_dir():
        raise ValueError("scope must be a directory")
    if platform.system() != "Darwin" or not shutil.which("mdfind"):
        return {"status": "unavailable", "reason": "mdfind_unavailable"}
    escaped = known_name.replace("\\", "\\\\").replace('"', '\\"')
    response = _run(["/usr/bin/mdfind", "-0", "-onlyin", str(scope),
                     f'kMDItemFSName == "{escaped}"'])
    if "error" in response or response["exit_code"] != 0:
        return {"status": "failed", "reason": response.get("error", "mdfind_failed"),
                "exit_code": response.get("exit_code")}
    if len(response["stdout"]) > 1_000_000:
        return {"status": "inconclusive", "reason": "too_many_probe_hits"}
    hits = [Path(value) for value in response["stdout"].split("\0") if value]
    verified, out_of_scope, unreadable = 0, 0, 0
    for hit in hits:
        try:
            path = hit.resolve(strict=True)
            if not path.is_relative_to(scope):
                out_of_scope += 1
                continue
            if path.name != known_name or not path.is_file():
                continue
            with path.open("rb") as stream:
                stream.read(1)
            verified += 1
        except OSError:
            unreadable += 1
    return {"status": "passed" if verified else "inconclusive",
            "probe": "known_filename", "hit_count": len(hits),
            "verified_readable_hits": verified, "out_of_scope_hits": out_of_scope,
            "unreadable_or_stale_hits": unreadable,
            "exhaustive": False, "personal_paths_recorded": False}


VECTOR_PROBE = '''
import importlib.metadata as md, json, sys
{path_setup}
try:
    import apsw, sqlite_vec
except ImportError as exc:
    print(json.dumps({{"status":"unavailable","reason":"dependency_missing","module":exc.name}}))
    raise SystemExit(0)
connection = apsw.Connection(":memory:")
try:
    connection.enable_load_extension(True)
    try:
        connection.load_extension(sqlite_vec.loadable_path())
    finally:
        connection.enable_load_extension(False)
    version = connection.execute("select vec_version()").fetchone()[0]
    connection.execute("create virtual table spike using vec0(embedding float[3])")
    connection.executemany("insert into spike(rowid,embedding) values (?,?)",
                          [(1,"[1,0,0]"),(2,"[0,1,0]")])
    rows = list(connection.execute(
        "select rowid,distance from spike where embedding match ? and k=? order by distance",
        ("[1,0,0]",2)))
    okay = len(rows)==2 and rows[0][0]==1 and abs(rows[0][1])<1e-6
    print(json.dumps({{"status":"passed" if okay else "failed", "apsw":apsw.apswversion(),
        "sqlite":apsw.sqlitelibversion(), "sqlite_vec":version,
        "distribution_version":md.version("sqlite-vec"), "rows":rows,
        "synthetic_vectors":True, "quality_evidence":False}}))
finally:
    connection.close()
'''


def vector_probe(deps_dir: Path | None = None):
    setup = ""
    if deps_dir is not None:
        directory = deps_dir.expanduser().resolve(strict=True)
        if not directory.is_dir():
            raise ValueError("vector dependencies must be a directory")
        setup = f"sys.path.insert(0, {str(directory)!r})"
    if getattr(sys, "frozen", False):
        command = [sys.executable, "--vector-child"]
        if deps_dir is not None:
            command.extend(["--vector-deps", str(directory)])
    else:
        command = [sys.executable, "-c", VECTOR_PROBE.format(path_setup=setup)]
    result = _run(command, timeout=20)
    if "error" in result or result["exit_code"] != 0:
        return {"status": "failed", "reason": result.get("error", "native_probe_failed"),
                "exit_code": result.get("exit_code")}
    try:
        return json.loads(result["stdout"])
    except (ValueError, TypeError):
        return {"status": "failed", "reason": "invalid_probe_response"}


def native_translation_probe(helper: Path | None):
    if helper is None:
        return {"status": "not_run", "reason": "no_probe_helper_supplied"}
    path = helper.expanduser().resolve(strict=True)
    if not path.is_file():
        raise ValueError("helper must be a file")
    # This is a purpose-built capability probe, not the translation CLI: it must
    # query availability only and never download packs or request translation.
    result = _run([str(path)], timeout=10)
    if "error" in result or result["exit_code"] != 0:
        return {"status": "failed", "reason": result.get("error", "helper_failed"),
                "exit_code": result.get("exit_code")}
    try:
        return json.loads(result["stdout"])
    except ValueError:
        return {"status": "failed", "reason": "invalid_probe_response"}


def collect_report(*, scope=None, known_name=None, vector_deps=None, native_helper=None):
    if (scope is None) != (known_name is None):
        raise ValueError("supply scope and known filename together")
    packages = {}
    for name in PACKAGE_NAMES:
        try:
            packages[name] = importlib.metadata.version(name)
        except importlib.metadata.PackageNotFoundError:
            packages[name] = None
    connection = sqlite3.connect(":memory:")
    try:
        extensions = hasattr(connection, "enable_load_extension")
    finally:
        connection.close()
    return {
        "schema_version": 1,
        "recorded_at": datetime.now(timezone.utc).isoformat(),
        "kind": "local_compatibility_probe_not_target_acceptance",
        "environment": {"system": platform.system(), "macos": platform.mac_ver()[0],
                        "machine": platform.machine(), "python": platform.python_version()},
        "target": {"architecture": "arm64", "macos_minimum": "14.0", "ram_gib": 8,
                   "actual_target_tested": False},
        "packages": packages,
        "package_inventory_scope": "diagnostic process; null means metadata missing, not necessarily module missing",
        "stdlib_sqlite": {"version": sqlite3.sqlite_version,
                           "extension_api_present": extensions},
        "spotlight": (spotlight_probe(scope, known_name) if scope else
                      {"status": "not_run", "reason": "no_explicit_scope"}),
        "vector_storage": vector_probe(vector_deps),
        "native_translation": native_translation_probe(native_helper),
        "embedding": {"status": "not_run", "reason": "model_not_selected_or_loaded"},
        "limits": {"no_network": True, "no_models": True, "no_permission_prompts": True,
                   "no_ui_acceptance": True},
    }


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--scope", type=Path)
    parser.add_argument("--known-name")
    parser.add_argument("--vector-deps", type=Path, help="explicit trusted temporary dependency directory")
    parser.add_argument("--native-probe", type=Path, help="compiled apple_translation_probe.swift, not translation CLI")
    parser.add_argument("--output", type=Path)
    parser.add_argument("--vector-child", action="store_true", help=argparse.SUPPRESS)
    args = parser.parse_args(argv)
    if args.vector_child:
        setup = ""
        if args.vector_deps is not None:
            directory = args.vector_deps.expanduser().resolve(strict=True)
            if not directory.is_dir():
                parser.error("vector dependencies must be a directory")
            setup = f"sys.path.insert(0, {str(directory)!r})"
        exec(VECTOR_PROBE.format(path_setup=setup), {"__name__": "__main__"})
        return 0
    if args.native_probe is None and getattr(sys, "frozen", False):
        bundled_probe = Path(sys._MEIPASS) / "apple_translation_probe"
        if bundled_probe.is_file():
            args.native_probe = bundled_probe
    try:
        report = collect_report(scope=args.scope, known_name=args.known_name,
                                vector_deps=args.vector_deps, native_helper=args.native_probe)
    except (OSError, ValueError) as exc:
        parser.error(str(exc))
    content = json.dumps(report, ensure_ascii=False, indent=2) + "\n"
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(content, encoding="utf-8")
    print(content, end="")
    # Exit zero means a report was collected, not that release gates passed.
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
