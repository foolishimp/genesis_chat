# Implements: REQ-F-CHAN-002
"""IRCAdapter — connects to an IRC server as a channel substrate.

Uses stdlib socket only — no external dependencies.

Protocol:
  NICK <nick>
  USER <nick> 0 * :<realname>
  JOIN <channel>
  PRIVMSG <channel> :<text>
  PING → PONG (keepalive)

Each agent connects as a separate nick. Messages from any nick are received
as ChatMessages. The human is any nick not in the agent registry.
"""
from __future__ import annotations

import socket
import time
from dataclasses import dataclass, field
from threading import Event, Thread
from queue import Queue, Empty

from genesis_chat.adapter.base import ChatMessage, ChannelResponse, MessageAdapter


@dataclass
class IRCConfig:
    host: str = "localhost"
    port: int = 6667
    nick: str = "genesis_chat"
    channel: str = "#genesis"
    realname: str = "genesis_chat agent"
    connect_timeout: float = 10.0
    recv_timeout: float = 0.5


class IRCAdapter(MessageAdapter):
    """
    IRC channel adapter. One instance per agent nick.
    receive() blocks on the message queue (populated by a background reader thread).

    agent_nicks: set of nicks to treat as agents — messages from these are ignored
                 to prevent dispatch loops between agent containers.
    """

    def __init__(self, config: IRCConfig, agent_nicks: set[str] | None = None):
        self.config = config
        self._agent_nicks: set[str] = agent_nicks or set()
        self._sock: socket.socket | None = None
        self._buf = ""
        self._seq = 0
        self._inbox: Queue[ChatMessage] = Queue()
        self._approvals: dict[str, str] = {}  # op_id → "approved" | "rejected"
        self._pending_approval_nicks: dict[str, str] = {}  # op_id → awaiting reply from
        self._reader: Thread | None = None
        self._stop = Event()
        self._connected = False

    # ── Connection ─────────────────────────────────────────────────────────────

    def connect(self, retries: int = 10, retry_delay: float = 3.0) -> None:
        last_err = None
        for attempt in range(retries):
            try:
                self._sock = socket.create_connection(
                    (self.config.host, self.config.port),
                    timeout=self.config.connect_timeout,
                )
                break
            except OSError as e:
                last_err = e
                print(f"IRC connect attempt {attempt + 1}/{retries} failed: {e} — retrying in {retry_delay}s")
                time.sleep(retry_delay)
        else:
            raise ConnectionError(f"Could not connect to IRC after {retries} attempts: {last_err}")
        self._sock.settimeout(self.config.recv_timeout)
        self._send_raw(f"NICK {self.config.nick}")
        self._send_raw(f"USER {self.config.nick} 0 * :{self.config.realname}")
        # Wait for server welcome (001) before joining
        self._wait_for_welcome()
        self._send_raw(f"JOIN {self.config.channel}")
        self._connected = True
        # Start background reader
        self._reader = Thread(target=self._read_loop, daemon=True)
        self._reader.start()

    def disconnect(self) -> None:
        self._stop.set()
        if self._sock:
            try:
                self._send_raw("QUIT :genesis_chat shutting down")
                self._sock.close()
            except Exception:
                pass

    # ── MessageAdapter interface ────────────────────────────────────────────────

    def receive(self) -> ChatMessage:
        """Block until a message arrives from the channel."""
        while not self._stop.is_set():
            try:
                return self._inbox.get(timeout=0.1)
            except Empty:
                continue
        raise SystemExit(0)

    def send(self, response: ChannelResponse) -> None:
        """Send a response to the channel."""
        if response.envelope:
            prefix = self.format_envelope(response.envelope)
        else:
            prefix = f"[{response.sender}]"
        # Multi-line responses: send each line as a separate PRIVMSG
        for line in response.text.splitlines():
            if line.strip():
                self._send_raw(f"PRIVMSG {self.config.channel} :{prefix} {line}")
                time.sleep(0.05)  # avoid flood kick

    def format_envelope(self, envelope) -> str:
        """IRC adapter: includes 'via irc' for cross-platform visibility."""
        parts = [f"{envelope.sender} via irc"]
        if envelope.elapsed_ms is not None:
            secs = envelope.elapsed_ms / 1000
            if secs >= 60:
                parts.append(f"+{int(secs // 60)}m{int(secs % 60):02d}s")
            else:
                parts.append(f"+{secs:.1f}s")
        if envelope.project:
            parts.append(f"on {envelope.project}")
        if envelope.feature:
            ctx = envelope.feature
            if envelope.edge:
                ctx += f":{envelope.edge}"
            parts.append(ctx)
        elif envelope.command:
            parts.append(envelope.command)
        return "[" + " ".join(parts) + "]"

    def request_approval(self, msg: ChatMessage, prompt: str) -> str:
        import uuid
        op_id = uuid.uuid4().hex[:8]
        self._send_raw(
            f"PRIVMSG {self.config.channel} :[approval:{op_id}] {prompt} — reply y/n"
        )
        self._pending_approval_nicks[op_id] = msg.sender_id
        # Block until we get a y/n reply
        deadline = time.time() + 300  # 5 min timeout
        while time.time() < deadline:
            status = self._approvals.get(op_id)
            if status:
                return op_id
            time.sleep(0.2)
        self._approvals[op_id] = "rejected"  # timeout → reject
        return op_id

    def get_approval_status(self, op_id: str) -> str | None:
        return self._approvals.get(op_id)

    # ── Internal ───────────────────────────────────────────────────────────────

    def _send_raw(self, line: str) -> None:
        if self._sock:
            self._sock.sendall(f"{line}\r\n".encode("utf-8", errors="replace"))

    def _wait_for_welcome(self, timeout: float = 15.0) -> None:
        deadline = time.time() + timeout
        buf = ""
        while time.time() < deadline:
            try:
                data = self._sock.recv(4096).decode("utf-8", errors="replace")
                buf += data
                for line in buf.splitlines():
                    if " 001 " in line:  # RPL_WELCOME
                        return
                    if line.startswith("PING"):
                        token = line.split(":", 1)[1] if ":" in line else line.split()[1]
                        self._send_raw(f"PONG :{token}")
            except socket.timeout:
                pass
        raise ConnectionError(f"IRC server did not send welcome within {timeout}s")

    def _read_loop(self) -> None:
        """Background thread: read IRC lines and populate inbox."""
        while not self._stop.is_set():
            try:
                data = self._sock.recv(4096).decode("utf-8", errors="replace")
                if not data:
                    break
                self._buf += data
                while "\r\n" in self._buf:
                    line, self._buf = self._buf.split("\r\n", 1)
                    self._handle_line(line)
            except socket.timeout:
                continue
            except Exception:
                break

    def _handle_line(self, line: str) -> None:
        # PING keepalive
        if line.startswith("PING"):
            token = line.split(":", 1)[1] if ":" in line else line.split()[1]
            self._send_raw(f"PONG :{token}")
            return

        # :nick!user@host PRIVMSG #channel :text
        if "PRIVMSG" not in line:
            return
        try:
            prefix, rest = line[1:].split(" ", 1) if line.startswith(":") else ("", line)
            sender_nick = prefix.split("!")[0] if "!" in prefix else prefix
            parts = rest.split(" ", 2)
            if parts[0] != "PRIVMSG":
                return
            target = parts[1]
            text = parts[2].lstrip(":") if len(parts) > 2 else ""

            # Ignore messages not in our channel
            if target != self.config.channel:
                return
            # Ignore our own messages and messages from other agent nicks (prevents loops)
            if sender_nick == self.config.nick or sender_nick in self._agent_nicks:
                return

            # Check if this is a y/n approval reply
            for op_id, waiting_nick in list(self._pending_approval_nicks.items()):
                if op_id not in self._approvals:
                    if text.strip().lower() in ("y", "yes"):
                        self._approvals[op_id] = "approved"
                        del self._pending_approval_nicks[op_id]
                        return
                    elif text.strip().lower() in ("n", "no"):
                        self._approvals[op_id] = "rejected"
                        del self._pending_approval_nicks[op_id]
                        return

            self._seq += 1
            self._inbox.put(ChatMessage(
                id=f"MSG-{self._seq:04d}",
                text=text,
                sender_id=sender_nick,
                channel_id=self.config.channel,
                platform="irc",
            ))
        except Exception:
            pass  # malformed line — skip
