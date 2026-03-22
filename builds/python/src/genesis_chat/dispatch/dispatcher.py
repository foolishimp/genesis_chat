# Implements: REQ-F-DISP-001
"""Dispatcher — F_D listener with worker lifecycle management.

Pure deterministic. No LLM. Handles commands (projects, start, stop, workers, help).
Workers manage their own IRC connections and message handling.
"""
from __future__ import annotations

import time
from pathlib import Path

from genesis_chat.adapter.base import ChatMessage, ChannelResponse, MessageEnvelope
from genesis_chat.worker import WorkerManager


class Dispatcher:
    def __init__(self, workspace_root: str, config_dir: Path, platform: str = "echo",
                 nick: str = "genesis_chat",
                 irc_host: str = "localhost", irc_port: int = 6667,
                 irc_channel: str = "#genesis"):
        self.workspace_root = workspace_root
        self.platform = platform
        self.nick = nick

        mcp_config = config_dir / "mcp_servers.yml"
        self.manager = WorkerManager(
            workspace_root=Path(workspace_root),
            mcp_config=mcp_config if mcp_config.exists() else None,
            irc_host=irc_host,
            irc_port=irc_port,
            irc_channel=irc_channel,
        )

    def dispatch(self, msg: ChatMessage, adapter) -> ChannelResponse:
        text = msg.text.strip()
        t0 = time.monotonic()
        lower = text.lower()

        if lower == "projects":
            return self._cmd_projects(msg, t0)
        if lower == "workers":
            return self._cmd_workers(msg, t0)
        if lower.startswith("start "):
            return self._cmd_start(text, msg, t0)
        if lower.startswith("stop "):
            return self._cmd_stop(text, msg, t0)
        if lower in ("help", "?"):
            return self._cmd_help(msg, t0)

        # Not a command — hint
        elapsed = int((time.monotonic() - t0) * 1000)
        active = self.manager.active()
        if active:
            hint = f"Workers active: {', '.join(active)}. Talk to them directly."
        else:
            hint = "No workers. 'start <agent> on <project>' or 'help'"
        return ChannelResponse(
            text=hint, reply_to=msg.id, sender=self.nick,
            envelope=MessageEnvelope(
                sender=self.nick, platform=self.platform, elapsed_ms=elapsed,
            ),
        )

    def _cmd_projects(self, msg, t0):
        projects = self.manager.list_projects()
        text = "Genesis projects:\n" + "\n".join(f"  {p}" for p in projects) if projects else "No genesis projects found."
        elapsed = int((time.monotonic() - t0) * 1000)
        return ChannelResponse(
            text=text, reply_to=msg.id, sender=self.nick,
            envelope=MessageEnvelope(sender=self.nick, platform=self.platform, command="projects", elapsed_ms=elapsed),
        )

    def _cmd_workers(self, msg, t0):
        active = self.manager.active()
        text = "Active workers:\n" + "\n".join(f"  {n}" for n in active) if active else "No active workers."
        elapsed = int((time.monotonic() - t0) * 1000)
        return ChannelResponse(
            text=text, reply_to=msg.id, sender=self.nick,
            envelope=MessageEnvelope(sender=self.nick, platform=self.platform, command="workers", elapsed_ms=elapsed),
        )

    def _cmd_start(self, text, msg, t0):
        parts = text.split()
        agent_type = "claude"
        project = None

        if len(parts) == 2:
            project = parts[1]
        elif len(parts) >= 4 and parts[2].lower() == "on":
            agent_type = parts[1].lower()
            project = parts[3]
        elif len(parts) == 3:
            agent_type = parts[1].lower()
            project = parts[2]

        if not project:
            elapsed = int((time.monotonic() - t0) * 1000)
            return ChannelResponse(
                text="Usage: start [agent] on <project>",
                reply_to=msg.id, sender=self.nick,
                envelope=MessageEnvelope(sender=self.nick, platform=self.platform, elapsed_ms=elapsed),
            )

        try:
            worker = self.manager.start(project, agent_type)
            elapsed = int((time.monotonic() - t0) * 1000)
            return ChannelResponse(
                text=f"Started {worker.name} on {worker.workspace}",
                reply_to=msg.id, sender=self.nick,
                envelope=MessageEnvelope(sender=self.nick, platform=self.platform, command="start", elapsed_ms=elapsed),
            )
        except Exception as e:
            elapsed = int((time.monotonic() - t0) * 1000)
            return ChannelResponse(
                text=f"Failed: {e}",
                reply_to=msg.id, sender=self.nick,
                envelope=MessageEnvelope(sender=self.nick, platform=self.platform, elapsed_ms=elapsed),
            )

    def _cmd_stop(self, text, msg, t0):
        name = text[5:].strip()
        reply = f"Stopped {name}" if self.manager.stop(name) else f"No worker: {name}"
        elapsed = int((time.monotonic() - t0) * 1000)
        return ChannelResponse(
            text=reply, reply_to=msg.id, sender=self.nick,
            envelope=MessageEnvelope(sender=self.nick, platform=self.platform, command="stop", elapsed_ms=elapsed),
        )

    def _cmd_help(self, msg, t0):
        text = (
            "Commands:\n"
            "  projects                    — list genesis projects\n"
            "  start [agent] on <project>  — spawn worker\n"
            "  workers                     — list active workers\n"
            "  stop <worker.name>          — tear down worker\n"
            "  help                        — this message"
        )
        elapsed = int((time.monotonic() - t0) * 1000)
        return ChannelResponse(
            text=text, reply_to=msg.id, sender=self.nick,
            envelope=MessageEnvelope(sender=self.nick, platform=self.platform, command="help", elapsed_ms=elapsed),
        )
