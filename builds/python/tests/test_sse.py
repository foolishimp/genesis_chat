# Validates: REQ-F-SSE-001
# Validates: REQ-F-SSE-002
# Validates: REQ-F-SSE-003
# Validates: REQ-F-SSE-004
"""Tests for SSE event stream server."""
import json
import tempfile
import time
import urllib.request
from pathlib import Path

import pytest

from genesis_chat.stream.sse_server import SSEServer


@pytest.fixture
def sse_env():
    """Create a temp workspace with events.jsonl and start SSE server."""
    with tempfile.TemporaryDirectory() as td:
        events_path = Path(td) / "events.jsonl"
        events_path.write_text("")
        # Use a high port to avoid conflicts
        server = SSEServer(events_path=events_path, port=0)  # port 0 = pick available
        # We'll use a fixed port for testing
        yield events_path, td


class TestSSEServer:
    def test_health_endpoint(self):
        with tempfile.TemporaryDirectory() as td:
            events_path = Path(td) / "events.jsonl"
            events_path.write_text("")
            server = SSEServer(events_path=events_path, port=18901)
            server.start()
            time.sleep(0.3)
            try:
                resp = urllib.request.urlopen("http://127.0.0.1:18901/health", timeout=2)
                data = json.loads(resp.read())
                assert data["status"] == "ok"
                assert data["seq"] == 0
            finally:
                server.stop()

    def test_health_reports_line_count(self):
        with tempfile.TemporaryDirectory() as td:
            events_path = Path(td) / "events.jsonl"
            events_path.write_text('{"event": "one"}\n{"event": "two"}\n')
            server = SSEServer(events_path=events_path, port=18902)
            server.start()
            time.sleep(0.3)
            try:
                resp = urllib.request.urlopen("http://127.0.0.1:18902/health", timeout=2)
                data = json.loads(resp.read())
                assert data["seq"] == 2
            finally:
                server.stop()

    def test_broadcast_increments_seq(self):
        with tempfile.TemporaryDirectory() as td:
            events_path = Path(td) / "events.jsonl"
            events_path.write_text("")
            server = SSEServer(events_path=events_path, port=18903)
            assert server._seq == 0
            server.broadcast("test", {"msg": "hello"})
            assert server._seq == 1
            server.broadcast("test", {"msg": "world"})
            assert server._seq == 2

    def test_404_on_unknown_path(self):
        with tempfile.TemporaryDirectory() as td:
            events_path = Path(td) / "events.jsonl"
            events_path.write_text("")
            server = SSEServer(events_path=events_path, port=18904)
            server.start()
            time.sleep(0.3)
            try:
                with pytest.raises(urllib.error.HTTPError) as exc_info:
                    urllib.request.urlopen("http://127.0.0.1:18904/nonexistent", timeout=2)
                assert exc_info.value.code == 404
            finally:
                server.stop()


class TestSSEEventTailing:
    def test_initial_line_count(self):
        with tempfile.TemporaryDirectory() as td:
            events_path = Path(td) / "events.jsonl"
            events_path.write_text('{"a":1}\n{"b":2}\n{"c":3}\n')
            server = SSEServer(events_path=events_path, port=18905)
            assert server._seq == 3

    def test_empty_file_seq_zero(self):
        with tempfile.TemporaryDirectory() as td:
            events_path = Path(td) / "events.jsonl"
            events_path.write_text("")
            server = SSEServer(events_path=events_path, port=18906)
            assert server._seq == 0


class TestSSEClientQueue:
    def test_client_push_and_wait(self):
        from genesis_chat.stream.sse_server import _SSEClient

        class FakeWfile:
            pass

        client = _SSEClient(FakeWfile())
        client.push("id: 1\nevent: test\ndata: {}\n\n")
        result = client.wait(timeout=0.1)
        assert result is not None
        assert "id: 1" in result

    def test_client_wait_timeout(self):
        from genesis_chat.stream.sse_server import _SSEClient

        class FakeWfile:
            pass

        client = _SSEClient(FakeWfile())
        result = client.wait(timeout=0.1)
        assert result is None

    def test_client_batches_multiple_events(self):
        from genesis_chat.stream.sse_server import _SSEClient

        class FakeWfile:
            pass

        client = _SSEClient(FakeWfile())
        client.push("event1\n\n")
        client.push("event2\n\n")
        result = client.wait(timeout=0.1)
        assert "event1" in result
        assert "event2" in result
