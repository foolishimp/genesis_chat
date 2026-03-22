# Validates: REQ-F-ENV-001
# Validates: REQ-F-ENV-002
# Validates: REQ-F-ENV-003
"""Tests for message envelope creation and rendering."""
from genesis_chat.adapter.base import MessageEnvelope, ChannelResponse, MessageAdapter
from genesis_chat.adapter.echo import EchoAdapter
from genesis_chat.adapter.irc import IRCAdapter, IRCConfig


class TestMessageEnvelope:
    def test_envelope_auto_timestamp(self):
        env = MessageEnvelope(sender="claude", platform="echo")
        assert env.timestamp  # auto-assigned

    def test_envelope_preserves_explicit_timestamp(self):
        env = MessageEnvelope(sender="claude", platform="echo", timestamp="2026-01-01T00:00:00Z")
        assert env.timestamp == "2026-01-01T00:00:00Z"

    def test_envelope_all_fields(self):
        env = MessageEnvelope(
            sender="claude",
            platform="irc",
            project="genesis_sdlc",
            feature="FT-AUTH-001",
            edge="design→code",
            elapsed_ms=2340,
            resolved_via="tier_2",
        )
        assert env.sender == "claude"
        assert env.project == "genesis_sdlc"
        assert env.feature == "FT-AUTH-001"
        assert env.edge == "design→code"
        assert env.elapsed_ms == 2340
        assert env.resolved_via == "tier_2"


class TestEnvelopeRendering:
    def test_base_format_minimal(self):
        adapter = EchoAdapter()
        env = MessageEnvelope(sender="genesis_chat", platform="echo")
        result = adapter.format_envelope(env)
        assert "genesis_chat" in result

    def test_echo_format_with_project(self):
        adapter = EchoAdapter()
        env = MessageEnvelope(sender="claude", platform="echo", project="genesis_sdlc")
        result = adapter.format_envelope(env)
        assert "claude" in result
        assert "on genesis_sdlc" in result
        assert "via" not in result  # echo doesn't show platform

    def test_echo_format_with_elapsed(self):
        adapter = EchoAdapter()
        env = MessageEnvelope(sender="claude", platform="echo", elapsed_ms=2340)
        result = adapter.format_envelope(env)
        assert "+2.3s" in result

    def test_echo_format_with_minutes(self):
        adapter = EchoAdapter()
        env = MessageEnvelope(sender="claude", platform="echo", elapsed_ms=154000)
        result = adapter.format_envelope(env)
        assert "+2m34s" in result

    def test_echo_format_with_feature_and_edge(self):
        adapter = EchoAdapter()
        env = MessageEnvelope(
            sender="claude", platform="echo",
            project="genesis_sdlc", feature="FT-AUTH-001", edge="design→code",
        )
        result = adapter.format_envelope(env)
        assert "FT-AUTH-001:design→code" in result

    def test_echo_format_with_command(self):
        adapter = EchoAdapter()
        env = MessageEnvelope(sender="genesis_chat", platform="echo", command="cmd_status")
        result = adapter.format_envelope(env)
        assert "cmd_status" in result

    def test_irc_format_shows_via_irc(self):
        cfg = IRCConfig()
        adapter = IRCAdapter(cfg)
        env = MessageEnvelope(sender="claude", platform="irc", project="genesis_sdlc")
        result = adapter.format_envelope(env)
        assert "via irc" in result
        assert "on genesis_sdlc" in result


class TestChannelResponseEnvelope:
    def test_response_with_envelope(self):
        env = MessageEnvelope(sender="claude", platform="echo")
        resp = ChannelResponse(text="hello", reply_to="MSG-0001", sender="claude", envelope=env)
        assert resp.envelope is env

    def test_response_without_envelope(self):
        resp = ChannelResponse(text="hello", reply_to="MSG-0001", sender="claude")
        assert resp.envelope is None
