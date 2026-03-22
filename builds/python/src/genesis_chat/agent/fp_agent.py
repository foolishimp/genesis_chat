# Implements: REQ-F-DISP-003
# Implements: REQ-F-MCP-001
"""F_P agent — Claude Code instance via MCP claude_code tool.

Per ADR-023: MCP is the primary agent transport. Each agent nick is backed
by a Claude Code instance invoked via the claude_code MCP tool. Claude Code
has its own F_D tools (filesystem, bash, tests) and can spawn further
MCP(F_P) instances for deeper work.

genesis_chat is just the IRC ↔ MCP bridge. All intelligence lives in Claude Code.
"""
from __future__ import annotations

from pathlib import Path

from genesis_chat.agent.mcp_bridge import MCPBridge


class FPAgent:
    """Agent backed by Claude Code via MCP claude_code tool."""

    def __init__(
        self,
        nick: str,
        workspace_root: str,
        mcp_config: Path | None = None,
    ):
        self.nick = nick
        self.workspace = Path(workspace_root)
        self.mcp = MCPBridge(mcp_config)
        self._history: list[tuple[str, str]] = []
        self._max_history = 30

    @property
    def available(self) -> bool:
        """True if the claude_code MCP tool is connected."""
        return "claude_code" in self.mcp._tool_map

    def respond(self, sender: str, text: str) -> str:
        """Forward message to Claude Code via MCP, return response."""
        self._history.append((sender, text))
        if len(self._history) > self._max_history:
            self._history = self._history[-self._max_history:]

        prompt = self._build_prompt(sender, text)

        result = self.mcp.call_tool("claude_code", {
            "prompt": prompt,
            "workFolder": str(self.workspace),
        })

        self._history.append((self.nick, result))
        return result

    def _build_prompt(self, sender: str, text: str) -> str:
        # Recent conversation context (exclude current message, already appended)
        history_lines = []
        for s, t in self._history[:-1]:
            history_lines.append(f"<{s}> {t}")

        history_block = "\n".join(history_lines[-40:]) if history_lines else "(start of conversation)"

        return f"""You are {self.nick}, an AI agent in the #genesis IRC channel.
You help developers work on Genesis SDLC projects. The projects workspace is {self.workspace}.

Recent conversation in #genesis:
{history_block}

New message:
<{sender}> {text}

Respond naturally and concisely — this is IRC, not a document.
Use your tools to check project state, read files, run commands. Don't guess — look things up.
If the user asks to start work on a project, use gen-start / gen-iterate on the project directory.
If addressed by another agent's name, stay quiet."""
