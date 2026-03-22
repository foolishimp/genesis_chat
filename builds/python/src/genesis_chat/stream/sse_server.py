# Implements: REQ-F-SSE-001
# Implements: REQ-F-SSE-002
# Implements: REQ-F-SSE-003
# Implements: REQ-F-SSE-004
"""SSE event stream server — tails events.jsonl and broadcasts channel messages.

Minimal stdlib-only HTTP server running on a background thread. Observers
(genesis-manager, browsers) connect via GET /events/stream and receive
Server-Sent Events with replay support via Last-Event-ID.

Source reference: OpenClaw Studio SSE replay pattern.
Our adaptation is ~130 LOC — stdlib only, no dependencies.
"""
from __future__ import annotations

import json
import os
import time
import threading
from http.server import HTTPServer, BaseHTTPRequestHandler
from pathlib import Path
from typing import Any


class SSEServer:
    """Lightweight SSE server for event stream broadcast."""

    def __init__(self, events_path: Path, port: int = 8086, host: str = "0.0.0.0"):
        self.events_path = events_path
        self.port = port
        self.host = host
        self._clients: list[_SSEClient] = []
        self._lock = threading.Lock()
        self._seq = 0  # current sequence (line count in events.jsonl)
        self._stop = threading.Event()
        self._httpd: HTTPServer | None = None

        # Load current line count
        if events_path.exists():
            self._seq = sum(1 for _ in events_path.open())

    def start(self) -> None:
        """Start HTTP server and file tailer on background threads."""
        server = self

        class Handler(BaseHTTPRequestHandler):
            def do_GET(self):
                if self.path == "/events/stream":
                    self._handle_sse(server)
                elif self.path == "/health":
                    self.send_response(200)
                    self.send_header("Content-Type", "application/json")
                    self.end_headers()
                    self.wfile.write(json.dumps({"status": "ok", "seq": server._seq}).encode())
                else:
                    self.send_response(404)
                    self.end_headers()

            def _handle_sse(self, srv: SSEServer):
                self.send_response(200)
                self.send_header("Content-Type", "text/event-stream")
                self.send_header("Cache-Control", "no-cache")
                self.send_header("Connection", "keep-alive")
                self.send_header("Access-Control-Allow-Origin", "*")
                self.end_headers()

                # Replay from Last-Event-ID if provided
                last_id = self.headers.get("Last-Event-ID")
                replay_from = int(last_id) if last_id and last_id.isdigit() else 0

                if replay_from > 0 and srv.events_path.exists():
                    with srv.events_path.open() as f:
                        for i, line in enumerate(f, 1):
                            if i > replay_from:
                                try:
                                    self.wfile.write(f"id: {i}\nevent: project_event\ndata: {line.strip()}\n\n".encode())
                                    self.wfile.flush()
                                except (BrokenPipeError, ConnectionResetError):
                                    return

                client = _SSEClient(self.wfile)
                with srv._lock:
                    srv._clients.append(client)

                # Keep connection open until client disconnects
                try:
                    while not srv._stop.is_set():
                        event = client.wait(timeout=1.0)
                        if event:
                            try:
                                self.wfile.write(event.encode())
                                self.wfile.flush()
                            except (BrokenPipeError, ConnectionResetError):
                                break
                finally:
                    with srv._lock:
                        if client in srv._clients:
                            srv._clients.remove(client)

            def log_message(self, format, *args):
                pass  # suppress access logs

        self._httpd = HTTPServer((self.host, self.port), Handler)
        threading.Thread(target=self._httpd.serve_forever, daemon=True).start()
        threading.Thread(target=self._tail_events, daemon=True).start()

    def stop(self) -> None:
        self._stop.set()
        if self._httpd:
            self._httpd.shutdown()

    def broadcast(self, event_type: str, data: dict, seq: int | None = None) -> None:
        """Push event to all connected SSE clients."""
        if seq is None:
            self._seq += 1
            seq = self._seq
        payload = f"id: {seq}\nevent: {event_type}\ndata: {json.dumps(data)}\n\n"
        with self._lock:
            dead: list[_SSEClient] = []
            for client in self._clients:
                try:
                    client.push(payload)
                except Exception:
                    dead.append(client)
            for d in dead:
                self._clients.remove(d)

    def _tail_events(self) -> None:
        """Background: watch events.jsonl for appends and broadcast new lines."""
        last_size = self.events_path.stat().st_size if self.events_path.exists() else 0
        line_num = self._seq

        while not self._stop.is_set():
            time.sleep(0.2)
            if not self.events_path.exists():
                continue
            current_size = self.events_path.stat().st_size
            if current_size <= last_size:
                continue

            with self.events_path.open() as f:
                f.seek(last_size)
                for line in f:
                    line = line.strip()
                    if line:
                        line_num += 1
                        try:
                            data = json.loads(line)
                        except json.JSONDecodeError:
                            data = {"raw": line}
                        self.broadcast("project_event", data, seq=line_num)

            last_size = current_size
            self._seq = line_num


class _SSEClient:
    """Per-client event queue."""

    def __init__(self, wfile):
        self._wfile = wfile
        self._queue: list[str] = []
        self._event = threading.Event()

    def push(self, payload: str) -> None:
        self._queue.append(payload)
        self._event.set()

    def wait(self, timeout: float = 1.0) -> str | None:
        self._event.wait(timeout=timeout)
        self._event.clear()
        if self._queue:
            events = "".join(self._queue)
            self._queue.clear()
            return events
        return None
