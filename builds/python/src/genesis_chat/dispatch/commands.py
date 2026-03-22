# Implements: REQ-F-DISP-001
"""F_D command registry — pattern-matched deterministic handlers."""
from __future__ import annotations

import os
import re
import subprocess
from dataclasses import dataclass
from pathlib import Path

try:
    import yaml
except ImportError:
    import json as _json
    class _yaml_shim:
        @staticmethod
        def safe_load(text): return _json.loads(text)
    yaml = _yaml_shim()


@dataclass
class Command:
    pattern: str
    handler_name: str
    description: str

    def match(self, text: str) -> re.Match | None:
        return re.match(self.pattern, text.strip(), re.IGNORECASE)


class CommandRegistry:
    def __init__(self, config_path: Path):
        data = yaml.safe_load(config_path.read_text())
        self.commands = [Command(**c) for c in data.get("commands", [])]

    def match(self, text: str) -> tuple[Command, re.Match] | tuple[None, None]:
        for cmd in self.commands:
            m = cmd.match(text)
            if m:
                return cmd, m
        return None, None


# ── Handlers ──────────────────────────────────────────────────────────────────

def _genesis_run(workspace: Path, *args: str) -> str:
    env = {**os.environ, "PYTHONPATH": str(workspace / ".genesis")}
    result = subprocess.run(
        ["python", "-m", "genesis", *args],
        cwd=workspace, capture_output=True, text=True, env=env, timeout=30,
    )
    return result.stdout.strip() or result.stderr.strip() or "(no output)"


def _list_projects(workspace_root: Path) -> str:
    """List genesis projects available under workspace_root."""
    projects = sorted(
        p.name for p in workspace_root.iterdir()
        if p.is_dir() and (p / ".genesis").exists()
    )
    if not projects:
        return f"No genesis projects found under {workspace_root}"
    return "Available projects:\n" + "\n".join(f"  {p}" for p in projects)


def handle_status(workspace: Path, match: re.Match) -> str:
    # "status <project>" → run genesis status on that project
    # "status" alone → list available projects
    project = (match.group(1) or "").strip() if match.lastindex else ""
    if project:
        project_path = workspace / project
        if not (project_path / ".genesis").exists():
            return f"Project '{project}' not found or not a genesis project under {workspace}"
        return _genesis_run(project_path, "gaps")
    return _list_projects(workspace)


def handle_gaps(workspace: Path, match: re.Match) -> str:
    project = (match.group(1) or "").strip() if match.lastindex else ""
    if project:
        project_path = workspace / project
        if not (project_path / ".genesis").exists():
            return f"Project '{project}' not found under {workspace}"
        return _genesis_run(project_path, "gaps")
    return _list_projects(workspace)


def handle_projects(workspace: Path, match: re.Match) -> str:
    return _list_projects(workspace)


def handle_help(commands: list[Command], match: re.Match) -> str:
    lines = [
        "Commands:",
        "  projects               — list available genesis projects",
        "  status [project]       — genesis status for a project",
        "  gaps [project]         — convergence gaps for a project",
        "  help                   — this message",
        "",
        "Work intents (natural language):",
        "  start <project>        — run gen-start on a project",
        "  iterate <feat> on <project>  — run one iteration on a feature",
    ]
    return "\n".join(lines)


HANDLERS: dict = {
    "cmd_status": handle_status,
    "cmd_gaps": handle_gaps,
    "cmd_projects": handle_projects,
    "cmd_help": handle_help,
}
