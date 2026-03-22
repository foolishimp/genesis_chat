# Implements: REQ-F-CHAN-003
# Implements: REQ-F-SSE-004
"""Main channel loop — receive, dispatch, respond, repeat.

V2: integrates SSE broadcast for real-time observer updates.
"""
from __future__ import annotations

import json
from pathlib import Path

from genesis_chat.adapter.base import MessageAdapter
from genesis_chat.adapter.echo import EchoAdapter
from genesis_chat.dispatch.dispatcher import Dispatcher
from genesis_chat.stream.sse_server import SSEServer


def run(
    workspace_root: str,
    config_dir: str | None = None,
    adapter: MessageAdapter | None = None,
    platform: str = "echo",
    sse_port: int | None = None,
    sse_host: str = "0.0.0.0",
    irc_host: str = "localhost",
    irc_port: int = 6667,
    irc_channel: str = "#genesis",
    nick: str = "genesis_chat",
) -> None:
    ws = Path(workspace_root)
    config = Path(config_dir) if config_dir else ws
    if adapter is None:
        adapter = EchoAdapter()
    dispatcher = Dispatcher(
        workspace_root=str(ws.resolve()),
        config_dir=config,
        platform=platform,
        nick=nick,
        irc_host=irc_host,
        irc_port=irc_port,
        irc_channel=irc_channel,
    )

    # Start SSE server if requested
    sse: SSEServer | None = None
    if sse_port:
        events_path = ws / ".ai-workspace" / "events" / "events.jsonl"
        events_path.parent.mkdir(parents=True, exist_ok=True)
        if not events_path.exists():
            events_path.touch()
        sse = SSEServer(events_path=events_path, port=sse_port, host=sse_host)
        sse.start()
        print(f"SSE stream available at http://{sse_host}:{sse_port}/events/stream")

    print(f"genesis_chat — {type(adapter).__name__} ready")
    print(f"Workspace: {ws.resolve()}")
    print("Type 'help' for commands. Ctrl+C or Ctrl+D to exit.\n")

    while True:
        try:
            msg = adapter.receive()
            if not msg.text:
                continue

            # Only respond if addressed to us: @genesis_chat or genesis_chat:
            text = msg.text.strip()
            addressed = False
            for prefix in (f"@{nick} ", f"@{nick}: ", f"{nick}: ", f"{nick} "):
                if text.lower().startswith(prefix.lower()):
                    text = text[len(prefix):].strip()
                    addressed = True
                    break
            if not addressed:
                continue

            # Rewrite message with prefix stripped
            from genesis_chat.adapter.base import ChatMessage
            msg = ChatMessage(
                id=msg.id, text=text, sender_id=msg.sender_id,
                channel_id=msg.channel_id, platform=msg.platform,
            )

            # Broadcast inbound message to SSE observers
            if sse:
                sse.broadcast("channel_inbound", {
                    "id": msg.id,
                    "sender": msg.sender_id,
                    "text": msg.text,
                    "platform": msg.platform,
                })

            response = dispatcher.dispatch(msg, adapter)
            adapter.send(response)

            # Broadcast outbound response to SSE observers
            if sse:
                envelope_data = None
                if response.envelope:
                    envelope_data = {
                        "sender": response.envelope.sender,
                        "platform": response.envelope.platform,
                        "project": response.envelope.project,
                        "feature": response.envelope.feature,
                        "edge": response.envelope.edge,
                        "command": response.envelope.command,
                        "elapsed_ms": response.envelope.elapsed_ms,
                        "resolved_via": response.envelope.resolved_via,
                    }
                sse.broadcast("channel_response", {
                    "sender": response.sender,
                    "text": response.text,
                    "reply_to": response.reply_to,
                    "envelope": envelope_data,
                })

            if platform == "echo":
                print()
        except KeyboardInterrupt:
            print("\nExiting.")
            if sse:
                sse.stop()
            break
        except SystemExit:
            if sse:
                sse.stop()
            break
