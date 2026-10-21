"""Offline packaging preflight; does not import RAT, load models or scan files."""
from __future__ import annotations

import argparse
import ast
import importlib.metadata
import json
from pathlib import Path
import subprocess
import sys


ROOT = Path(__file__).resolve().parents[1]


def check_packaging(root=ROOT, *, check_environment=True, probe_qt=False):
    root = Path(root)
    errors, warnings = [], []
    tree = ast.parse((root / "rat.spec").read_text())
    literals = {node.targets[0].id: ast.literal_eval(node.value)
                for node in tree.body if isinstance(node, ast.Assign)
                and isinstance(node.targets[0], ast.Name)
                and node.targets[0].id in {"added_files", "hidden_imports"}}
    analysis = next(node.value for node in tree.body if isinstance(node, ast.Assign)
                    and isinstance(node.value, ast.Call)
                    and isinstance(node.value.func, ast.Name) and node.value.func.id == "Analysis")
    excludes = ast.literal_eval(next(kw.value for kw in analysis.keywords if kw.arg == "excludes"))
    for module in ("sklearn", "scipy", "gymnasium", "pypdf", "document_intake", "reasoning"):
        if any(module == name or module.startswith(name + ".") for name in excludes):
            errors.append(f"runtime dependency excluded: {module}")
    for source, target in literals["added_files"]:
        path = root / source
        if not path.exists():
            errors.append(f"missing bundled resource: {source}")
        elif path.is_dir() and any(path.rglob("*.py")):
            errors.append(f"Python source directory bundled as data: {source}")
    resources = {source for source, _ in literals["added_files"]}
    for resource in ("rat/assets", "rat/engine/snapshot.schema.json", "rat/astrology/ephemeris"):
        if resource not in resources:
            errors.append(f"runtime resource absent from spec: {resource}")
    for module in literals["hidden_imports"]:
        if module.split(".")[0] in {"rat", "reasoning", "document_intake"}:
            path = root / module.replace(".", "/")
            if not path.with_suffix(".py").is_file() and not (path / "__init__.py").is_file():
                errors.append(f"missing local hidden import: {module}")

    try:
        from packaging.requirements import Requirement
    except ImportError:
        return {"status": "failed", "errors": errors + [
            "packaging is unavailable; install the declared build dependencies from requirements.txt"],
            "warnings": warnings, "installed_versions": {},
            "environment_checked": check_environment,
            "evidence_type": "offline_packaging_preflight", "model_calls": 0}
    requirements = []
    for line in (root / "requirements.txt").read_text().splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        if line.startswith("./"):
            if not (root / line / "pyproject.toml").is_file():
                errors.append(f"missing local dependency: {line}")
            continue
        req = Requirement(line)
        if req.marker is None or req.marker.evaluate():
            requirements.append(req)
    declared = {req.name.lower().replace("_", "-") for req in requirements}
    for name in ("scikit-learn", "gymnasium", "scipy", "pypdf"):
        if name not in declared:
            errors.append(f"desktop dependency undeclared: {name}")
    versions = {}
    if check_environment:
        for req in requirements:
            try:
                version = importlib.metadata.version(req.name)
            except importlib.metadata.PackageNotFoundError:
                errors.append(f"not installed: {req}")
                continue
            versions[req.name] = version
            if not req.specifier.contains(version, prereleases=True):
                errors.append(f"installed {req.name}=={version} does not satisfy {req.specifier}")
        try:
            versions["PyInstaller"] = importlib.metadata.version("pyinstaller")
        except importlib.metadata.PackageNotFoundError:
            errors.append("PyInstaller is required for an app build")
    qt_probe = {"status": "not_run"}
    if probe_qt:
        code = ("from PyQt6.QtCore import QLibraryInfo; "
                "print(QLibraryInfo.path(QLibraryInfo.LibraryPath.PluginsPath))")
        try:
            completed = subprocess.run([sys.executable, "-c", code],
                                       capture_output=True, text=True, timeout=10)
            qt_probe = {"status": "passed" if completed.returncode == 0 else "failed",
                        "exit_code": completed.returncode, "stderr": completed.stderr.strip()}
            if completed.returncode:
                errors.append("QtCore import failed; check target architecture and CPU access (sandbox restrictions can affect detection)")
            else:
                plugin_dir = Path(completed.stdout.strip())
                qt_probe["plugins_path"] = str(plugin_dir)
                if not plugin_dir.is_dir() or (sys.platform == "darwin" and not (plugin_dir / "platforms/libqcocoa.dylib").is_file()):
                    qt_probe["status"] = "failed"
                    errors.append("Qt platform plugin directory is incomplete")
        except (OSError, subprocess.TimeoutExpired) as exc:
            qt_probe = {"status": "failed", "error_type": type(exc).__name__}
            errors.append("QtCore probe could not complete")
    warnings.append("Native MLX inference, Tesseract executable/language data and optional astrology are separate capabilities; preflight does not validate them.")
    return {"status": "failed" if errors else "passed", "errors": errors, "warnings": warnings,
            "installed_versions": versions, "environment_checked": check_environment, "qt_probe": qt_probe,
            "evidence_type": "offline_packaging_preflight", "model_calls": 0}


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--spec-only", action="store_true", help="check source/resources without installed dependency checks")
    parser.add_argument("--probe-qt", action="store_true", help="also import QtCore in a child process, without launching a GUI")
    args = parser.parse_args(argv)
    result = check_packaging(check_environment=not args.spec_only, probe_qt=args.probe_qt)
    print(json.dumps(result, indent=2))
    return int(bool(result["errors"]))


if __name__ == "__main__":
    raise SystemExit(main())
