# Implements: REQ-F-CHAN-002
# Implements: REQ-F-ENV-001
# Implements: REQ-F-ENV-002
"""MessageAdapter ABC — platform-agnostic channel interface."""
from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime, timezone


@dataclass
class ChatMessage:
    id: str
    text: str
    sender_id: str
    channel_id: str
    platform: str
    metadata: dict = field(default_factory=dict)


@dataclass
class MessageEnvelope:
    """Structured provenance metadata for every outbound message."""
    sender: str
    platform: str
    project: str | None = None
    feature: str | None = None
    edge: str | None = None
    command: str | None = None
    elapsed_ms: int | None = None
    resolved_via: str | None = None  # tier_1|tier_2|tier_3|tier_4
    timestamp: str = ""

    def __post_init__(self):
        if not self.timestamp:
            self.timestamp = datetime.now(timezone.utc).isoformat()


@dataclass
class ChannelResponse:
    text: str
    reply_to: str
    sender: str
    envelope: MessageEnvelope | None = None


class MessageAdapter(ABC):
    """Platform-agnostic messaging interface. Implementors: EchoAdapter (V1), SlackAdapter (V2+)."""

    @abstractmethod
    def receive(self) -> ChatMessage:
        """Block until the next message arrives."""

    @abstractmethod
    def send(self, response: ChannelResponse) -> None:
        """Send a response back to the originating channel."""

    @abstractmethod
    def request_approval(self, msg: ChatMessage, prompt: str) -> str:
        """Post a confirmation request and return a pending_op_id."""

    def format_envelope(self, envelope: MessageEnvelope) -> str:
        """Render envelope as a human-readable prefix. Override per adapter."""
        parts = [envelope.sender]
        if envelope.platform:
            parts[0] = f"{envelope.sender} via {envelope.platform}"
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
