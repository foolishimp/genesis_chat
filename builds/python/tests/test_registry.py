# Validates: REQ-F-AGENT-001
# Validates: REQ-F-AGENT-002
"""Tests for agent registry and claim mechanism."""
from __future__ import annotations

import tempfile
from pathlib import Path

import pytest

from genesis_chat.registry.agents import AgentConfig, AgentRegistry, Claim, ClaimRegistry

REGISTRY_YAML = """
agents:
  - id: claude
    display_name: Claude (primary)
    write_territory: .ai-workspace/comments/claude/
    workflow_bindings:
      - gen-start
      - gen-iterate
    role: primary
  - id: mock_agent
    display_name: Mock Agent
    write_territory: .ai-workspace/comments/mock_agent/
    workflow_bindings:
      - gen-start
    role: secondary
"""


@pytest.fixture
def registry_file(tmp_path):
    p = tmp_path / "agents.yml"
    p.write_text(REGISTRY_YAML)
    return p


def test_agent_registry_loads(registry_file):
    reg = AgentRegistry(registry_file)
    assert len(reg.all()) == 2


def test_agent_registry_get(registry_file):
    reg = AgentRegistry(registry_file)
    claude = reg.get("claude")
    assert claude is not None
    assert claude.display_name == "Claude (primary)"
    assert claude.role == "primary"


def test_agent_registry_missing(registry_file):
    reg = AgentRegistry(registry_file)
    assert reg.get("nonexistent") is None


def test_agent_registry_capable_of(registry_file):
    reg = AgentRegistry(registry_file)
    capable = reg.capable_of("gen-iterate")
    assert len(capable) == 1
    assert capable[0].id == "claude"


def test_agent_registry_capable_of_gen_start(registry_file):
    reg = AgentRegistry(registry_file)
    capable = reg.capable_of("gen-start")
    assert len(capable) == 2


def test_claim_registry_creates_claim(tmp_path):
    claims_dir = tmp_path / "claims"
    reg = ClaimRegistry(claims_dir)
    claim = reg.claim("claude", "REQ-F-AUTH", "design→code")
    assert claim.agent == "claude"
    assert claim.status == "active"
    assert claims_dir.exists()


def test_claim_registry_lists_active(tmp_path):
    claims_dir = tmp_path / "claims"
    reg = ClaimRegistry(claims_dir)
    reg.claim("claude", "REQ-F-AUTH", "design→code")
    active = reg.active_claims()
    assert len(active) == 1
    assert active[0].agent == "claude"


def test_claim_registry_empty(tmp_path):
    reg = ClaimRegistry(tmp_path / "claims")
    assert reg.active_claims() == []
