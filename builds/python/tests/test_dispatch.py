# Validates: REQ-F-DISP-001
# Validates: REQ-F-DISP-002
# Validates: REQ-F-DISP-003
"""Tests for message dispatcher — command match, intent routing, F_H gate."""
from __future__ import annotations

import tempfile
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from genesis_chat.adapter.base import ChatMessage
from genesis_chat.dispatch.commands import Command, CommandRegistry
from genesis_chat.dispatch.intent import WorkIntent, route_intent
from genesis_chat.registry.agents import AgentConfig
from genesis_chat.workflow.bindings import WorkflowBinding

COMMANDS_YAML = """
commands:
  - pattern: "^status$"
    handler_name: cmd_status
    description: "status — show workspace genesis status"
  - pattern: "^gaps$"
    handler_name: cmd_gaps
    description: "gaps — show convergence gaps"
  - pattern: "^help$"
    handler_name: cmd_help
    description: "help — list available commands"
"""


@pytest.fixture
def commands_file(tmp_path):
    p = tmp_path / "commands.yml"
    p.write_text(COMMANDS_YAML)
    return p


def test_command_registry_loads(commands_file):
    reg = CommandRegistry(commands_file)
    assert len(reg.commands) == 3


def test_command_match_status(commands_file):
    reg = CommandRegistry(commands_file)
    cmd, m = reg.match("status")
    assert cmd is not None
    assert cmd.handler_name == "cmd_status"


def test_command_match_gaps(commands_file):
    reg = CommandRegistry(commands_file)
    cmd, m = reg.match("gaps")
    assert cmd is not None
    assert cmd.handler_name == "cmd_gaps"


def test_command_no_match(commands_file):
    reg = CommandRegistry(commands_file)
    cmd, m = reg.match("build the auth feature")
    assert cmd is None
    assert m is None


def test_command_case_insensitive(commands_file):
    reg = CommandRegistry(commands_file)
    cmd, m = reg.match("STATUS")
    assert cmd is not None


# ── Intent routing tests ───────────────────────────────────────────────────────

@pytest.fixture
def agents():
    return [
        AgentConfig(id="claude", display_name="Claude", write_territory="",
                    workflow_bindings=["gen-start", "gen-iterate"], role="primary"),
        AgentConfig(id="mock_agent", display_name="Mock", write_territory="",
                    workflow_bindings=["gen-start"], role="secondary"),
    ]


@pytest.fixture
def bindings():
    return {
        "gen-start": WorkflowBinding(
            name="gen-start",
            command_template="PYTHONPATH={workspace}/.genesis python -m genesis start --auto",
            args={"workspace": "required"},
            description="Run gen-start",
        ),
        "gen-iterate": WorkflowBinding(
            name="gen-iterate",
            command_template="PYTHONPATH={workspace}/.genesis python -m genesis start --feature {feature}",
            args={"workspace": "required", "feature": "required"},
            description="Run gen-iterate",
        ),
    }


def test_route_intent_start(agents, bindings):
    intent = route_intent("start genesis_sdlc", agents, bindings, "/apps")
    assert intent is not None
    assert intent.binding.name == "gen-start"
    assert intent.agent.id == "claude"
    assert "genesis_sdlc" in intent.workspace


def test_route_intent_iterate_with_feature(agents, bindings):
    intent = route_intent("iterate REQ-F-AUTH on genesis_sdlc", agents, bindings, "/apps")
    assert intent is not None
    assert intent.binding.name == "gen-iterate"
    assert intent.params.get("feature") == "REQ-F-AUTH"
    assert "genesis_sdlc" in intent.workspace


def test_route_intent_no_match(agents, bindings):
    intent = route_intent("what is the weather", agents, bindings, "/apps")
    assert intent is None


def test_route_intent_no_capable_agent(agents, bindings):
    # Remove gen-iterate from all agents
    for a in agents:
        a.workflow_bindings = ["gen-start"]
    intent = route_intent("iterate REQ-F-AUTH on genesis_sdlc", agents, bindings, "/apps")
    assert intent is None
