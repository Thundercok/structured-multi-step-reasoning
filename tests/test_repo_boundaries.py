"""Research must not depend on RAT, so results never change because the app changed."""
import ast
from pathlib import Path
import subprocess

ROOT = Path(__file__).resolve().parents[1]
RAT_MODULES = {"document_intake", "main", "rat", "reasoning", "research_scoring"}


def imported_modules(path):
    found = set()
    for node in ast.walk(ast.parse(path.read_text(encoding="utf-8"))):
        if isinstance(node, ast.Import):
            found.update(alias.name.split(".")[0] for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and not node.level and node.module:
            found.add(node.module.split(".")[0])
    return found


def test_research_never_imports_rat():
    output = subprocess.check_output(["git", "ls-files", "structured_llm", "audit"], cwd=ROOT, text=True)
    paths = [ROOT / name for name in output.splitlines() if name.endswith(".py")]
    found = {path.name: names for path in paths if path.exists() and (names := imported_modules(path) & RAT_MODULES)}
    assert found == {}
