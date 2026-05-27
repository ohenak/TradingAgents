"""PROPERTIES tests — PROP-FALLBACK-13: sentinel import enforcement.

PROP-FALLBACK-13: STRUCTURED_OUTPUT_SENTINEL must be defined as a module-level
constant in tradingagents/agents/utils/structured.py. All four wheel agents must
import it from there — it must not be hardcoded as a string literal in any of
the four agent files.

Test method per PROPERTIES doc:
  Use ast.parse() + ast.walk() to scan each agent source file.
  Assert the sentinel string literal appears only in structured.py (definition).
  Assert the sentinel string literal does NOT appear as an ast.Constant node
  in any of the four agent source files.
  Also assert each agent file contains an import referencing STRUCTURED_OUTPUT_SENTINEL.
"""
from __future__ import annotations

import ast
import importlib
import inspect
import os
from pathlib import Path

import pytest

from tradingagents.agents.utils.structured import STRUCTURED_OUTPUT_SENTINEL


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _read_source(module_path: str) -> str:
    """Read source code for the given module dot-path."""
    import tradingagents
    pkg_root = Path(inspect.getfile(tradingagents)).parent
    # Convert e.g. "tradingagents.agents.utils.structured" → path
    rel = module_path.replace("tradingagents.", "").replace(".", os.sep)
    return (pkg_root / (rel + ".py")).read_text(encoding="utf-8")


def _collect_string_constants(source: str) -> list[str]:
    """Walk AST and collect all string literal constant values."""
    tree = ast.parse(source)
    constants = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Constant) and isinstance(node.value, str):
            constants.append(node.value)
    return constants


def _has_import_of(source: str, name: str) -> bool:
    """Return True if source imports `name` from any module."""
    tree = ast.parse(source)
    for node in ast.walk(tree):
        # from ... import STRUCTURED_OUTPUT_SENTINEL
        if isinstance(node, ast.ImportFrom):
            for alias in node.names:
                if alias.name == name or alias.asname == name:
                    return True
        # import ... as ...  (not typical for constants but be thorough)
        if isinstance(node, ast.Import):
            for alias in node.names:
                if name in (alias.name, alias.asname or ""):
                    return True
    return False


# ---------------------------------------------------------------------------
# PROP-FALLBACK-13: Sentinel constant import, not hardcode
# ---------------------------------------------------------------------------

WHEEL_AGENT_MODULES = [
    "tradingagents.agents.analysts.wheel_analyst",
    "tradingagents.agents.options.csp_agent",
    "tradingagents.agents.options.cc_agent",
    "tradingagents.agents.options.roll_agent",
]

STRUCTURED_MODULE = "tradingagents.agents.utils.structured"


class TestSentinelEnforcement:
    """PROP-FALLBACK-13: sentinel is defined once, imported everywhere."""

    def test_sentinel_constant_defined_in_structured_py(self):
        """PROP-FALLBACK-13: STRUCTURED_OUTPUT_SENTINEL is a non-empty string in structured.py."""
        assert isinstance(STRUCTURED_OUTPUT_SENTINEL, str)
        assert len(STRUCTURED_OUTPUT_SENTINEL) > 0, (
            "PROP-FALLBACK-13: STRUCTURED_OUTPUT_SENTINEL must be a non-empty string"
        )

    def test_sentinel_string_appears_in_structured_py_source(self):
        """PROP-FALLBACK-13: the sentinel literal is defined in structured.py."""
        source = _read_source(STRUCTURED_MODULE)
        constants = _collect_string_constants(source)
        assert STRUCTURED_OUTPUT_SENTINEL in constants, (
            f"PROP-FALLBACK-13: STRUCTURED_OUTPUT_SENTINEL literal '{STRUCTURED_OUTPUT_SENTINEL}' "
            f"must appear as a string constant in structured.py"
        )

    @pytest.mark.parametrize("module_path", WHEEL_AGENT_MODULES)
    def test_sentinel_not_hardcoded_in_agent_file(self, module_path: str):
        """PROP-FALLBACK-13: sentinel literal must NOT appear in wheel agent source files."""
        source = _read_source(module_path)
        constants = _collect_string_constants(source)
        assert STRUCTURED_OUTPUT_SENTINEL not in constants, (
            f"PROP-FALLBACK-13: sentinel string must not be hardcoded in {module_path}. "
            f"Import STRUCTURED_OUTPUT_SENTINEL from tradingagents.agents.utils.structured instead."
        )

    @pytest.mark.parametrize("module_path", WHEEL_AGENT_MODULES)
    def test_agent_imports_sentinel_from_structured(self, module_path: str):
        """PROP-FALLBACK-13: each wheel agent imports STRUCTURED_OUTPUT_SENTINEL."""
        source = _read_source(module_path)
        assert _has_import_of(source, "STRUCTURED_OUTPUT_SENTINEL"), (
            f"PROP-FALLBACK-13: {module_path} must import STRUCTURED_OUTPUT_SENTINEL "
            f"from tradingagents.agents.utils.structured"
        )
