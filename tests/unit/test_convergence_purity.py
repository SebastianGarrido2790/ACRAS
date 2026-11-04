"""Import-boundary proof for the convergence core (P4-03 / T3-FR-11).

The divergence, Tier 1 confidence, and escalation modules must stay pure:
no gateway, network, or LLM dependency may enter their import graph, and they
must not perform dynamic imports or file I/O. This is asserted structurally on
the source AST so a future edit cannot quietly reintroduce a dependency.
"""

from __future__ import annotations

import ast
from pathlib import Path

import pytest

MODULE_DIR = Path(__file__).parents[2] / "src" / "agents" / "orchestration"

CONVERGENCE_MODULES = (
    "divergence.py",
    "tier1_confidence.py",
    "escalation.py",
)

FORBIDDEN_IMPORT_PREFIXES = (
    "src.gateway",
    "httpx",
    "requests",
    "urllib",
    "socket",
    "http",
    "aiohttp",
    "openai",
    "groq",
    "google",
    "anthropic",
    "langgraph",
    "langchain",
    "pydantic_ai",
)

FORBIDDEN_CALLS = frozenset({"__import__", "open", "exec", "eval"})


def _imported_modules(path: Path) -> set[str]:
    """Return every module named by a static import in one source file."""
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    modules: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            modules.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            modules.add(node.module)
    return modules


@pytest.mark.parametrize("filename", CONVERGENCE_MODULES)
def test_no_gateway_network_or_llm_imports(filename: str) -> None:
    """T3-FR-11: the pure modules never import a transport or model client."""
    modules = _imported_modules(MODULE_DIR / filename)
    offending = sorted(
        module
        for module in modules
        if any(
            module == prefix or module.startswith(prefix + ".")
            for prefix in FORBIDDEN_IMPORT_PREFIXES
        )
    )
    assert offending == [], f"{filename} imports forbidden modules: {offending}"


@pytest.mark.parametrize("filename", CONVERGENCE_MODULES)
def test_no_dynamic_imports_or_file_io_calls(filename: str) -> None:
    """Purity: no dynamic import, eval, exec, or file open in these modules."""
    path = MODULE_DIR / filename
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    offending = sorted(
        {
            node.func.id
            for node in ast.walk(tree)
            if isinstance(node, ast.Call)
            and isinstance(node.func, ast.Name)
            and node.func.id in FORBIDDEN_CALLS
        }
    )
    assert offending == [], f"{filename} performs forbidden calls: {offending}"
