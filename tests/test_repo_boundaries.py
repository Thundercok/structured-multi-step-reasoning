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


def test_msra_never_imports_research():
    """MSRA engine must remain self-contained and never import research pipeline modules."""
    msra_dir = ROOT / "structured_llm" / "msra"
    paths = [p for p in msra_dir.glob("**/*.py") if p.is_file()]
    violations = {}
    research_modules = {
        "analyze", "counterfactual", "evaluate", "gsm8k", "intervene",
        "math_check", "math_convert", "math_data", "pal", "trace"
    }
    for path in paths:
        bad = set()
        for node in ast.walk(ast.parse(path.read_text(encoding="utf-8"))):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    parts = alias.name.split(".")
                    if parts[0] == "structured_llm" and len(parts) > 1 and parts[1] != "msra":
                        bad.add(alias.name)
            elif isinstance(node, ast.ImportFrom) and node.module:
                parts = node.module.split(".")
                if parts[0] == "structured_llm" and len(parts) > 1 and parts[1] != "msra":
                    bad.add(node.module)
                elif node.level == 2 and parts[0] in research_modules:
                    bad.add(node.module)
        if bad:
            violations[path.name] = sorted(bad)
    assert violations == {}
