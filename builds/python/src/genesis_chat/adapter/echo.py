# Implements: REQ-F-CHAN-001
# Implements: REQ-F-CHAN-003
"""EchoAdapter — local stdin/stdout channel for spike."""
from __future__ import annotations

import uuid

from genesis_chat.adapter.base import ChatMessage, ChannelResponse, MessageAdapter


class EchoAdapter(MessageAdapter):
    """Spike adapter: reads from stdin, writes to stdout. No networking, no credentials."""

    def __init__(self, channel_id: str = "echo-main"):
        self.channel_id = channel_id
        self._seq = 0
        self._approvals: dict[str, str] = {}  # op_id → "approved" | "rejected"

    def receive(self) -> ChatMessage:
        try:
            text = input("> ").strip()
        except EOFError:
            raise SystemExit(0)
        self._seq += 1
        return ChatMessage(
            id=f"MSG-{self._seq:04d}",
            text=text,
            sender_id="human",
            channel_id=self.channel_id,
            platform="echo",
        )

    def send(self, response: ChannelResponse) -> None:
        if response.envelope:
            prefix = self.format_envelope(response.envelope)
            print(f"{prefix} {response.text}")
        else:
            print(f"[{response.sender}] {response.text}")

    def format_envelope(self, envelope) -> str:
        """Echo adapter: compact format without platform (always local)."""
        parts = [envelope.sender]
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
        op_id = uuid.uuid4().hex[:8]
        print(f"[approval:{op_id}] {prompt} (y/n)")
        try:
            answer = input("> ").strip().lower()
        except EOFError:
            answer = "n"
        self._approvals[op_id] = "approved" if answer == "y" else "rejected"
        return op_id

    def get_approval_status(self, op_id: str) -> str | None:
        return self._approvals.get(op_id)
