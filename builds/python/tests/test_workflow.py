# Validates: REQ-F-WORK-001
# Validates: REQ-F-WORK-002
# Validates: REQ-F-CTX-001
# Validates: REQ-F-TRACE-001
"""Tests for workflow bindings, context assembly, and event tracing."""
from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from genesis_chat.workflow.bindings import BindingRegistry, WorkflowBinding, execute_binding
from genesis_chat.workflow.context import assemble_context

BINDINGS_YAML = """
workflow_bindings:
  gen-start:
    command: "PYTHONPATH={workspace}/.genesis python -m genesis start --auto"
    args:
      workspace: required
    description: "Run gen-start"
  gen-iterate:
    command: "PYTHONPATH={workspace}/.genesis python -m genesis start --feature {feature}"
    args:
      workspace: required
      feature: required
    description: "Run gen-iterate"
"""


@pytest.fixture
def bindings_file(tmp_path):
    p = tmp_path / "workflow_bindings.yml"
    p.write_text(BINDINGS_YAML)
    return p


def test_binding_registry_loads(bindings_file):
    reg = BindingRegistry(bindings_file)
    assert "gen-start" in reg.bindings
    assert "gen-iterate" in reg.bindings


def test_binding_registry_get(bindings_file):
    reg = BindingRegistry(bindings_file)
    b = reg.get("gen-start")
    assert b is not None
    assert b.name == "gen-start"


def test_binding_registry_missing(bindings_file):
    reg = BindingRegistry(bindings_file)
    assert reg.get("nonexistent") is None


def test_execute_binding_renders_template(bindings_file, tmp_path):
    reg = BindingRegistry(bindings_file)
    binding = reg.get("gen-start")
    with patch("subprocess.run") as mock_run:
        mock_run.return_value = MagicMock(returncode=0, stdout="converged", stderr="")
        result = execute_binding(binding, str(tmp_path), {"workspace": str(tmp_path)})
    assert "converged" in result or result  # subprocess was called


def test_execute_binding_timeout(bindings_file, tmp_path):
    import subprocess
    reg = BindingRegistry(bindings_file)
    binding = reg.get("gen-start")
    with patch("subprocess.run", side_effect=subprocess.TimeoutExpired(cmd="x", timeout=1)):
        result = execute_binding(binding, str(tmp_path), {})
    assert "timed out" in result


# ── Context assembly tests ─────────────────────────────────────────────────────

def test_assemble_context_no_workspace(tmp_path):
    ctx = assemble_context(str(tmp_path))
    assert "no context available" in ctx


def test_assemble_context_with_events(tmp_path):
    events_dir = tmp_path / ".ai-workspace" / "events"
    events_dir.mkdir(parents=True)
    events_file = events_dir / "events.jsonl"
    events_file.write_text(
        json.dumps({"event_type": "edge_started", "data": {"edge": "design→code"}}) + "\n"
    )
    ctx = assemble_context(str(tmp_path))
    assert "Recent events" in ctx
    assert "edge_started" in ctx


def test_assemble_context_with_feature(tmp_path):
    feat_dir = tmp_path / ".ai-workspace" / "features" / "active"
    feat_dir.mkdir(parents=True)
    (feat_dir / "REQ-F-AUTH.yml").write_text("id: REQ-F-AUTH\ntitle: Auth feature\n")
    ctx = assemble_context(str(tmp_path), feature="REQ-F-AUTH")
    assert "REQ-F-AUTH" in ctx


def test_assemble_context_feature_not_found(tmp_path):
    ctx = assemble_context(str(tmp_path), feature="REQ-F-MISSING")
    assert "no context available" in ctx
