# Validates: REQ-F-TIER-001
# Validates: REQ-F-TIER-002
# Validates: REQ-F-TIER-003
"""Tests for four-tier binding resolution."""
import tempfile
from pathlib import Path

from genesis_chat.dispatch.binding_resolver import resolve_binding, ResolvedBinding
from genesis_chat.registry.agents import AgentConfig, ClaimRegistry
from genesis_chat.workflow.bindings import WorkflowBinding


def _make_agents():
    return [
        AgentConfig(
            id="claude", display_name="Claude", write_territory="comments/claude/",
            workflow_bindings=["gen-start", "gen-iterate"], role="primary",
            default_projects=["genesis_sdlc"],
        ),
        AgentConfig(
            id="codex", display_name="Codex", write_territory="comments/codex/",
            workflow_bindings=["gen-start"], role="secondary",
            default_projects=["genesis_chat"],
        ),
    ]


def _make_bindings():
    return {
        "gen-start": WorkflowBinding(name="gen-start", command_template="echo start", args={}, description=""),
        "gen-iterate": WorkflowBinding(name="gen-iterate", command_template="echo iterate", args={}, description=""),
    }


class TestTier1ActiveClaim:
    def test_active_claim_wins(self):
        agents = _make_agents()
        bindings = _make_bindings()
        with tempfile.TemporaryDirectory() as td:
            claims = ClaimRegistry(Path(td))
            # Codex has an active claim on this feature+edge
            claims.claim("codex", "FT-AUTH", "gen-start")
            result = resolve_binding(
                "gen-start", agents, bindings, claims,
                project="genesis_sdlc", feature="FT-AUTH", edge="gen-start",
            )
            assert result is not None
            assert result.agent.id == "codex"
            assert result.tier == 1
            assert "active claim" in result.reason


class TestTier2CapabilityMatch:
    def test_capability_match(self):
        agents = _make_agents()
        bindings = _make_bindings()
        with tempfile.TemporaryDirectory() as td:
            claims = ClaimRegistry(Path(td))
            result = resolve_binding(
                "gen-iterate", agents, bindings, claims,
            )
            # Only claude has gen-iterate capability
            assert result is not None
            assert result.agent.id == "claude"
            assert result.tier == 2


class TestTier3ProjectDefault:
    def test_project_default_preferred(self):
        agents = _make_agents()
        bindings = _make_bindings()
        with tempfile.TemporaryDirectory() as td:
            claims = ClaimRegistry(Path(td))
            # Both agents have gen-start. genesis_chat's default is codex.
            result = resolve_binding(
                "gen-start", agents, bindings, claims,
                project="genesis_chat",
            )
            assert result is not None
            assert result.agent.id == "codex"
            assert result.tier == 3
            assert "default agent" in result.reason

    def test_project_default_genesis_sdlc(self):
        agents = _make_agents()
        bindings = _make_bindings()
        with tempfile.TemporaryDirectory() as td:
            claims = ClaimRegistry(Path(td))
            result = resolve_binding(
                "gen-start", agents, bindings, claims,
                project="genesis_sdlc",
            )
            assert result is not None
            assert result.agent.id == "claude"
            assert result.tier == 3


class TestTier4ChannelDefault:
    def test_channel_default_fallback(self):
        agents = _make_agents()
        # Binding exists but no agent has it
        bindings = {
            "gen-deploy": WorkflowBinding(name="gen-deploy", command_template="echo deploy", args={}, description=""),
        }
        with tempfile.TemporaryDirectory() as td:
            claims = ClaimRegistry(Path(td))
            result = resolve_binding("gen-deploy", agents, bindings, claims)
            assert result is not None
            assert result.tier == 4
            assert "channel default" in result.reason


class TestTierPrecedence:
    def test_tier_1_beats_tier_3(self):
        """Active claim overrides project default."""
        agents = _make_agents()
        bindings = _make_bindings()
        with tempfile.TemporaryDirectory() as td:
            claims = ClaimRegistry(Path(td))
            # Codex claims the feature even though claude is default for genesis_sdlc
            claims.claim("codex", "FT-AUTH", "gen-start")
            result = resolve_binding(
                "gen-start", agents, bindings, claims,
                project="genesis_sdlc", feature="FT-AUTH", edge="gen-start",
            )
            assert result.agent.id == "codex"
            assert result.tier == 1

    def test_no_binding_returns_none(self):
        agents = _make_agents()
        bindings = _make_bindings()
        with tempfile.TemporaryDirectory() as td:
            claims = ClaimRegistry(Path(td))
            result = resolve_binding("nonexistent", agents, bindings, claims)
            assert result is None


class TestResolvedBindingAudit:
    def test_resolved_binding_carries_tier_and_reason(self):
        agents = _make_agents()
        bindings = _make_bindings()
        with tempfile.TemporaryDirectory() as td:
            claims = ClaimRegistry(Path(td))
            result = resolve_binding("gen-start", agents, bindings, claims)
            assert isinstance(result, ResolvedBinding)
            assert isinstance(result.tier, int)
            assert isinstance(result.reason, str)
            assert len(result.reason) > 0
