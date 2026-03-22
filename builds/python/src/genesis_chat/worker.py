# Implements: REQ-F-MCP-001
# Implements: REQ-F-DISP-003
"""Workers — project-scoped agent instances with IRC presence and MCP backend.

A worker:
  1. Joins IRC with its own nick (e.g., abiogenesis.worker.claude)
  2. Listens for messages addressed to it
  3. Forwards them to MCP(claude_code) scoped to the project's workFolder
  4. Sends responses back through its own IRC connection

Naming: {project}.worker.{agent_type}
"""
from __future__ import annotations

import threading
from pathlib import Path

from genesis_chat.adapter.irc import IRCAdapter, IRCConfig
from genesis_chat.adapter.base import MessageEnvelope
from genesis_chat.agent.mcp_bridge import MCPBridge


class Worker:
    """A project-scoped agent with IRC presence and MCP(claude_code) backend."""

    def __init__(self, name: str, project: str, agent_type: str,
                 workspace: Path, mcp_config: Path | None,
                 irc_host: str = "localhost", irc_port: int = 6667,
                 irc_channel: str = "#genesis",
                 all_worker_nicks: set[str] | None = None):
        self.name = name
        self.project = project
        self.agent_type = agent_type
        self.workspace = workspace
        self.mcp = MCPBridge(mcp_config)
        self._history: list[tuple[str, str]] = []
        self._max_history = 30
        self._stop = threading.Event()
        self._thread: threading.Thread | None = None

        # IRC connection for this worker
        ignore_nicks = (all_worker_nicks or set()) | {"genesis_chat"}
        self._irc = IRCAdapter(
            IRCConfig(
                host=irc_host,
                port=irc_port,
                nick=name,
                channel=irc_channel,
                realname=f"{name} — genesis worker on {project}",
            ),
            agent_nicks=ignore_nicks,
        )
        self._irc_channel = irc_channel

    @property
    def available(self) -> bool:
        return "claude_code" in self.mcp._tool_map

    def start(self) -> None:
        """Connect to IRC and start message loop in background."""
        self._irc.connect()
        self._thread = threading.Thread(target=self._message_loop, daemon=True)
        self._thread.start()

    def shutdown(self) -> None:
        """Disconnect from IRC and tear down MCP."""
        self._stop.set()
        self._irc.disconnect()
        self.mcp.shutdown()

    def _message_loop(self) -> None:
        """Background: receive IRC messages addressed to us, forward to MCP, reply."""
        while not self._stop.is_set():
            try:
                msg = self._irc.receive()
                if not msg.text:
                    continue

                # Only respond if addressed to us
                text = msg.text.strip()
                addressed = False
                for prefix in (f"@{self.name} ", f"@{self.name}: ", f"{self.name}: ", f"{self.name} "):
                    if text.lower().startswith(prefix.lower()):
                        text = text[len(prefix):].strip()
                        addressed = True
                        break
                if not addressed:
                    continue

                # Process the message
                reply_text = self._respond(msg.sender_id, text)

                # Send response through our own IRC connection
                from genesis_chat.adapter.base import ChannelResponse
                response = ChannelResponse(
                    text=reply_text,
                    reply_to=msg.id,
                    sender=self.name,
                    envelope=MessageEnvelope(
                        sender=self.name,
                        platform="irc",
                        project=self.project,
                    ),
                )
                self._irc.send(response)

            except SystemExit:
                break
            except Exception as e:
                if not self._stop.is_set():
                    # Send error to channel
                    try:
                        self._irc._send_raw(
                            f"PRIVMSG {self._irc_channel} :[{self.name}] error: {e}"
                        )
                    except Exception:
                        pass

    def _respond(self, sender: str, text: str) -> str:
        """Forward to MCP claude_code with project context."""
        self._history.append((sender, text))
        if len(self._history) > self._max_history * 2:
            self._history = self._history[-self._max_history * 2:]

        prompt = self._build_prompt(sender, text)

        result = self.mcp.call_tool("claude_code", {
            "prompt": prompt,
            "workFolder": str(self.workspace),
        })

        self._history.append((self.name, result))
        return result

    def _build_prompt(self, sender: str, text: str) -> str:
        history_lines = []
        for s, t in self._history[:-1]:
            history_lines.append(f"<{s}> {t}")
        history_block = "\n".join(history_lines[-40:]) if history_lines else "(start of conversation)"

        return f"""You are {self.name}, an AI agent working on the {self.project} project in #genesis IRC.
Your workspace is {self.workspace}. You have full access to the project files, tests, and genesis SDLC tools.

Follow the project's operating standards. Post durable artifacts to .ai-workspace/comments/{self.agent_type}/ per CONVENTIONS.md.
For IRC conversation, be concise and direct — this is a live channel, not a document.

Recent conversation:
{history_block}

New message:
<{sender}> {text}

Respond concisely. Use your tools to check state, read files, run commands. Don't guess."""


def _short_project(project: str) -> str:
    """Abbreviate project name: genesis_chat → gc, genesis-manager → gm."""
    parts = project.replace("-", "_").split("_")
    if len(parts) > 1:
        return "".join(p[0] for p in parts if p)
    return project[:3]


class WorkerManager:
    """Manages worker lifecycle — spawn, stop, list."""

    def __init__(self, workspace_root: Path, mcp_config: Path | None,
                 irc_host: str = "localhost", irc_port: int = 6667,
                 irc_channel: str = "#genesis"):
        self.workspace_root = workspace_root
        self.mcp_config = mcp_config
        self.irc_host = irc_host
        self.irc_port = irc_port
        self.irc_channel = irc_channel
        self.workers: dict[str, Worker] = {}
        self._name_to_project: dict[str, str] = {}  # short name → full project

    def list_projects(self) -> list[str]:
        return sorted(
            p.name for p in self.workspace_root.iterdir()
            if p.is_dir() and (p / ".genesis").exists()
        )

    def start(self, project: str, agent_type: str = "claude") -> Worker:
        short = _short_project(project)
        name = f"{short}.w.{agent_type}"
        if name in self.workers:
            raise ValueError(f"Already running: {name}")

        workspace = self.workspace_root / project
        if not workspace.is_dir():
            raise ValueError(f"Project not found: {project}")
        if not (workspace / ".genesis").exists():
            raise ValueError(f"Not a genesis project: {project}")

        # All existing worker nicks (so this worker ignores them)
        all_nicks = set(self.workers.keys()) | {name}

        worker = Worker(
            name=name,
            project=project,
            agent_type=agent_type,
            workspace=workspace,
            mcp_config=self.mcp_config,
            irc_host=self.irc_host,
            irc_port=self.irc_port,
            irc_channel=self.irc_channel,
            all_worker_nicks=all_nicks,
        )

        if not worker.available:
            worker.shutdown()
            raise RuntimeError(f"MCP claude_code not available for {name}")

        worker.start()
        self.workers[name] = worker
        self._name_to_project[name] = project
        return worker

    def stop(self, name: str) -> bool:
        worker = self.workers.pop(name, None)
        if worker:
            worker.shutdown()
            return True
        return False

    def active(self) -> list[str]:
        return list(self.workers.keys())

    def get(self, name: str) -> Worker | None:
        return self.workers.get(name)

    def shutdown_all(self) -> None:
        for worker in list(self.workers.values()):
            worker.shutdown()
        self.workers.clear()
