"""One repo, two sides: keep research and RAT separable without creating a second repo."""
import ast
from pathlib import Path
import subprocess

ROOT = Path(__file__).resolve().parents[1]

RESEARCH = (
    "structured_llm/",
    "data/",
    "audit/",
    "docs/",
    "requirements.txt",
    "tests/test_analyze.py",
    "tests/test_counterfactual.py",
    "tests/test_math_check.py",
    "tests/test_math_data.py",
    "tests/test_structured_trace.py",
)
HARNESS = (
    "rat/",
    "reasoning/",
    "document_intake/",
    "tools/",
    "tests/",
    "main.py",
    "research_scoring.py",
    "requirements-rat.txt",
)
SHARED = {
    ".github/workflows/ci.yml",
    ".gitignore",
    "AGENTS.md",
    "README.md",
    "pytest.ini",
    "tests/__init__.py",
    "tests/test_repo_boundaries.py",
}
HARNESS_MODULES = {
    "document_intake",
    "main",
    "rat",
    "reasoning",
    "research_scoring",
}

# TODO(human): list the structured_llm modules RAT may import once the model is wired in.
HARNESS_MAY_IMPORT = set()


def owner(path):
    if path in SHARED:
        return "shared"
    if path.startswith(RESEARCH):
        return "research"
    if path.startswith(HARNESS):
        return "harness"
    return None


def tracked():
    output = subprocess.check_output(["git", "ls-files"], cwd=ROOT, text=True)
    return [path for path in output.splitlines() if (ROOT / path).is_file()]


def python_files(side):
    return [path for path in tracked() if path.endswith(".py") and owner(path) == side]


def imports(path):
    found = set()
    for node in ast.walk(ast.parse((ROOT / path).read_text(encoding="utf-8"))):
        if isinstance(node, ast.Import):
            found.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and not node.level and node.module:
            if node.module == "structured_llm":
                found.update(f"structured_llm.{alias.name}" for alias in node.names)
            else:
                found.add(node.module)
    return found


def test_every_tracked_file_has_an_owner():
    assert [path for path in tracked() if owner(path) is None] == []


def test_research_never_imports_the_harness():
    found = {
        path: names
        for path in python_files("research")
        if (names := {name for name in imports(path) if name.split(".")[0] in HARNESS_MODULES})
    }
    assert found == {}


def test_harness_imports_only_the_public_research_modules():
    found = {
        path: names
        for path in python_files("harness")
        if (names := {
            name for name in imports(path)
            if name.split(".")[0] == "structured_llm" and name not in HARNESS_MAY_IMPORT
        })
    }
    assert found == {}
