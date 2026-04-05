# Implements: REQ-F-CORE-001
"""
fp_dispatch — Subprocess transport for F_P actor invocations.

Architecture: F_D → subprocess → agent (ADR-020 superseded)
Transport: Direct subprocess invocation with environment sanitization.

The agent receives a workspace and a manifest prompt. It has full shell access,
file discovery, and tool use. The framework checks artifacts at expected paths
after the agent exits. The framework does not constrain agent internals.

Supported agents:
  - claude: Claude Code CLI (`claude -p`) — env sanitized to prevent nesting hang
  - codex: OpenAI Codex CLI (`codex -q --full-auto`)
  - gemini: Google Gemini CLI (`gemini -p`)

The agent is selected by the Worker declaration in the Package spec.
All agents share the same contract: prompt in, artifacts out, exit code.

History: ADR-020 mandated MCP as the sole transport because `claude -p` hung
when nested inside an active Claude Code session (nesting guard env vars:
CLAUDECODE, CLAUDE_CODE_SSE_PORT, CLAUDE_CODE_ENTRYPOINT). The fix is to
strip CLAUDE* env vars before subprocess launch. Validated 2026-03-23.
MCP had a pervasive ExceptionGroup race condition (SDK 1.17.x) causing 3/7
live tests to fail — subprocess with env sanitization eliminates that class
of failures entirely.
"""
from __future__ import annotations

import os
import shutil
import subprocess


# Wall-clock timeout for a single agent invocation (seconds).
# Agents typically complete within 2-3 minutes per artifact.
# 5 minutes is generous but prevents indefinite hangs.
AGENT_CALL_TIMEOUT = 300


class AgentTransportError(Exception):
    """Agent transport failure — process crash, timeout, not installed.

    Distinct from agent quality failures. Transport errors are retryable;
    quality failures need different prompts or escalation.
    """

    def __init__(self, message: str, failure_class: str = "transport_failure"):
        super().__init__(message)
        self.failure_class = failure_class


# Legacy alias — callers may reference the old name
McpTransportError = AgentTransportError


def has_agent(agent: str = "claude") -> bool:
    """Check if the named agent CLI is available on PATH."""
    return shutil.which(_agent_command(agent)) is not None


# Legacy alias
def has_mcp_transport() -> bool:
    return has_agent("claude")


def call_agent(
    prompt: str,
    work_folder: str,
    *,
    agent: str = "claude",
    timeout: int = AGENT_CALL_TIMEOUT,
) -> str:
    """Invoke an autonomous agent in a workspace via subprocess.

    The agent receives the prompt and full workspace access. It can read files,
    run commands, write artifacts — whatever it needs. The framework only checks
    the artifacts afterward.

    Environment sanitization: For Claude Code, all CLAUDE* env vars are stripped
    to prevent the nesting guard hang (CLAUDECODE, CLAUDE_CODE_SSE_PORT, etc.).
    Without this, `claude -p` detects it's inside an active session and hangs.

    Args:
        prompt: The manifest prompt (work order).
        work_folder: Workspace directory the agent operates in.
        agent: Agent identifier ("claude", "codex", "gemini").
        timeout: Wall-clock timeout in seconds.

    Returns:
        The agent's stdout (conversational response, not the artifact).

    Raises:
        AgentTransportError: if the agent times out, crashes, or is not installed.
    """
    cmd = _agent_command(agent)
    if not shutil.which(cmd):
        raise AgentTransportError(
            f"Agent '{agent}' not found (command: {cmd}). Install it or check PATH.",
            failure_class="transport_failure",
        )

    args = _build_args(agent, prompt)
    env = _sanitized_env(agent)

    try:
        result = subprocess.run(
            args,
            cwd=work_folder,
            capture_output=True,
            text=True,
            timeout=timeout,
            env=env,
        )
    except subprocess.TimeoutExpired as exc:
        raise AgentTransportError(
            f"Agent '{agent}' timed out after {timeout}s in {work_folder}.",
            failure_class="transport_failure",
        ) from exc

    if result.returncode != 0:
        # Agent exited with error — could be a crash or a legitimate failure.
        # Return what we have; let the caller inspect artifacts.
        pass

    return result.stdout


# Legacy alias — drop-in replacement for call_claude_code_mcp
def call_claude_code_mcp(
    prompt: str,
    work_folder: str,
    *,
    timeout: int = AGENT_CALL_TIMEOUT,
) -> str:
    return call_agent(prompt, work_folder, agent="claude", timeout=timeout)


def _agent_command(agent: str) -> str:
    """Map agent identifier to CLI command."""
    commands = {
        "claude": "claude",
        "codex": "codex",
        "gemini": "gemini",
    }
    if agent not in commands:
        raise ValueError(f"Unknown agent: {agent!r}. Supported: {sorted(commands)}")
    return commands[agent]


def _build_args(agent: str, prompt: str) -> list[str]:
    """Build the subprocess argument list for the given agent."""
    if agent == "claude":
        return ["claude", "-p", "--output-format", "text", prompt]
    elif agent == "codex":
        return ["codex", "-q", "--full-auto", prompt]
    elif agent == "gemini":
        return ["gemini", "-p", prompt]
    else:
        raise ValueError(f"Unknown agent: {agent!r}")


def _sanitized_env(agent: str) -> dict[str, str]:
    """Build a sanitized environment for subprocess launch.

    For Claude Code: strips all CLAUDE* env vars to prevent the nesting guard
    hang. When `claude -p` detects CLAUDECODE=1 or CLAUDE_CODE_SSE_PORT, it
    thinks it's inside an active session and hangs indefinitely.

    For other agents: passes the environment through unchanged.
    """
    env = os.environ.copy()
    if agent == "claude":
        for key in list(env):
            if key.startswith("CLAUDE"):
                del env[key]
    return env
