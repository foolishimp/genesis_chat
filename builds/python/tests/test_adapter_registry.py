# Validates: REQ-F-AREG-001
# Validates: REQ-F-AREG-002
# Validates: REQ-F-AREG-003
"""Tests for config-driven adapter registry."""
import tempfile
from pathlib import Path

import pytest

from genesis_chat.adapter.registry import AdapterRegistry
from genesis_chat.adapter.base import MessageAdapter


@pytest.fixture
def registry_path():
    """Create a temporary adapters.yml."""
    content = """\
adapters:
  echo:
    module: genesis_chat.adapter.echo
    class: EchoAdapter
    config_class: null
    cli_prefix: null
    requires: []
  irc:
    module: genesis_chat.adapter.irc
    class: IRCAdapter
    config_class: IRCConfig
    cli_prefix: irc
    requires: []
"""
    with tempfile.NamedTemporaryFile(mode="w", suffix=".yml", delete=False) as f:
        f.write(content)
        return Path(f.name)


@pytest.fixture
def registry_with_missing():
    """Registry with a missing adapter module."""
    content = """\
adapters:
  echo:
    module: genesis_chat.adapter.echo
    class: EchoAdapter
    config_class: null
    requires: []
  matrix:
    module: genesis_chat.adapter.matrix
    class: MatrixAdapter
    config_class: MatrixConfig
    requires:
      - matrix-nio
"""
    with tempfile.NamedTemporaryFile(mode="w", suffix=".yml", delete=False) as f:
        f.write(content)
        return Path(f.name)


class TestAdapterResolution:
    def test_resolve_echo(self, registry_path):
        reg = AdapterRegistry(registry_path)
        adapter = reg.resolve("echo")
        assert isinstance(adapter, MessageAdapter)

    def test_resolve_unknown_raises(self, registry_path):
        reg = AdapterRegistry(registry_path)
        with pytest.raises(ValueError, match="Unknown adapter"):
            reg.resolve("slack")

    def test_resolve_irc_with_config(self, registry_path):
        reg = AdapterRegistry(registry_path)
        adapter = reg.resolve("irc", host="localhost", port=6667, nick="test", channel="#test")
        assert hasattr(adapter, "config")
        assert adapter.config.host == "localhost"
        assert adapter.config.nick == "test"


class TestAdapterValidation:
    def test_validate_all_available(self, registry_path):
        reg = AdapterRegistry(registry_path)
        results = reg.validate_all()
        assert results["echo"] is None  # no error
        assert results["irc"] is None

    def test_validate_missing_module(self, registry_with_missing):
        reg = AdapterRegistry(registry_with_missing)
        results = reg.validate_all()
        assert results["echo"] is None
        assert results["matrix"] is not None
        assert "matrix-nio" in results["matrix"]


class TestAdapterMissingModule:
    def test_resolve_missing_gives_clear_error(self, registry_with_missing):
        reg = AdapterRegistry(registry_with_missing)
        with pytest.raises(ImportError, match="matrix-nio"):
            reg.resolve("matrix")


class TestAdapterListing:
    def test_available_returns_sorted(self, registry_path):
        reg = AdapterRegistry(registry_path)
        available = reg.available()
        assert available == ["echo", "irc"]
