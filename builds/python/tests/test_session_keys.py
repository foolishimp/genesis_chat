# Validates: REQ-F-SESS-001
# Validates: REQ-F-SESS-002
# Validates: REQ-F-SESS-003
"""Tests for session key generation and claim integration."""
import tempfile
from pathlib import Path

from genesis_chat.session.keys import session_key
from genesis_chat.registry.agents import ClaimRegistry


class TestSessionKey:
    def test_deterministic(self):
        """Same inputs always produce the same key."""
        k1 = session_key("claude", "genesis_sdlc", "FT-AUTH-001", "design→code")
        k2 = session_key("claude", "genesis_sdlc", "FT-AUTH-001", "design→code")
        assert k1 == k2

    def test_different_agents_different_keys(self):
        k1 = session_key("claude", "genesis_sdlc", "FT-AUTH-001", "design→code")
        k2 = session_key("codex", "genesis_sdlc", "FT-AUTH-001", "design→code")
        assert k1 != k2

    def test_different_projects_different_keys(self):
        k1 = session_key("claude", "genesis_sdlc")
        k2 = session_key("claude", "genesis_chat")
        assert k1 != k2

    def test_different_features_different_keys(self):
        k1 = session_key("claude", "genesis_sdlc", "FT-AUTH-001")
        k2 = session_key("claude", "genesis_sdlc", "FT-DATA-001")
        assert k1 != k2

    def test_key_contains_human_readable_prefix(self):
        k = session_key("claude", "genesis_sdlc", "FT-AUTH-001", "design→code")
        assert k.startswith("claude:genesis_sdlc:FT-AUTH-001:design→code:")

    def test_key_has_hash_suffix(self):
        k = session_key("claude", "genesis_sdlc")
        parts = k.split(":")
        assert len(parts[-1]) == 8  # 8-char hash

    def test_defaults_to_main(self):
        k = session_key("claude", "genesis_sdlc")
        assert ":main:main:" in k


class TestClaimWithSessionKey:
    def test_claim_stores_session_key(self):
        with tempfile.TemporaryDirectory() as td:
            reg = ClaimRegistry(Path(td))
            sk = session_key("claude", "genesis_sdlc", "FT-AUTH", "design→code")
            claim = reg.claim("claude", "FT-AUTH", "design→code", session_key=sk)
            assert claim.session_key == sk

    def test_find_by_session_key(self):
        with tempfile.TemporaryDirectory() as td:
            reg = ClaimRegistry(Path(td))
            sk = session_key("claude", "genesis_sdlc", "FT-AUTH", "design→code")
            reg.claim("claude", "FT-AUTH", "design→code", session_key=sk)
            found = reg.find_by_session(sk)
            assert found is not None
            assert found.agent == "claude"
            assert found.feature == "FT-AUTH"

    def test_find_by_session_key_not_found(self):
        with tempfile.TemporaryDirectory() as td:
            reg = ClaimRegistry(Path(td))
            found = reg.find_by_session("nonexistent:key:here:abc12345")
            assert found is None

    def test_claim_backwards_compat_no_session_key(self):
        """Claims without session_key still work (V1 compat)."""
        with tempfile.TemporaryDirectory() as td:
            reg = ClaimRegistry(Path(td))
            claim = reg.claim("claude", "FT-AUTH", "gen-start")
            assert claim.session_key == ""
