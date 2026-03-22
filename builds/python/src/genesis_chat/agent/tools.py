# Implements: REQ-F-DISP-001
"""F_D tools — deterministic operations exposed to the F_P agent via tool_use."""
from __future__ import annotations

import os
import subprocess
from pathlib import Path


TOOL_DEFINITIONS = [
    {
        "name": "list_projects",
        "description": "List all genesis SDLC projects available in the workspace.",
        "input_schema": {
            "type": "object",
            "properties": {},
        },
    },
    {
        "name": "project_status",
        "description": "Get genesis SDLC status for a project — feature vectors, edge states, convergence.",
        "input_schema": {
            "type": "object",
            "properties": {
                "project": {
                    "type": "string",
                    "description": "Project directory name (e.g. 'genesis_chat')",
                },
            },
            "required": ["project"],
        },
    },
    {
        "name": "project_gaps",
        "description": "Show convergence gaps — what edges need work, uncovered requirements.",
        "input_schema": {
            "type": "object",
            "properties": {
                "project": {
                    "type": "string",
                    "description": "Project directory name",
                },
            },
            "required": ["project"],
        },
    },
    {
        "name": "gen_start",
        "description": "Start the genesis SDLC auto-loop (gen-start --auto) on a project.",
        "input_schema": {
            "type": "object",
            "properties": {
                "project": {
                    "type": "string",
                    "description": "Project directory name",
                },
            },
            "required": ["project"],
        },
    },
    {
        "name": "gen_iterate",
        "description": "Run one iteration cycle on a specific feature/edge.",
        "input_schema": {
            "type": "object",
            "properties": {
                "project": {
                    "type": "string",
                    "description": "Project directory name",
                },
                "feature": {
                    "type": "string",
                    "description": "Feature name to iterate",
                },
                "edge": {
                    "type": "string",
                    "description": "Edge (e.g. 'design', 'code', 'unit_tests')",
                },
            },
            "required": ["project"],
        },
    },
    {
        "name": "read_file",
        "description": "Read a file from a project workspace.",
        "input_schema": {
            "type": "object",
            "properties": {
                "project": {
                    "type": "string",
                    "description": "Project directory name",
                },
                "path": {
                    "type": "string",
                    "description": "Relative path within the project",
                },
            },
            "required": ["project", "path"],
        },
    },
    {
        "name": "list_files",
        "description": "List files and directories in a project path.",
        "input_schema": {
            "type": "object",
            "properties": {
                "project": {
                    "type": "string",
                    "description": "Project directory name",
                },
                "path": {
                    "type": "string",
                    "description": "Relative path (default: root)",
                },
            },
            "required": ["project"],
        },
    },
]


def _genesis_run(project_path: Path, *args: str, timeout: int = 60) -> str:
    env = {**os.environ, "PYTHONPATH": str(project_path / ".genesis")}
    try:
        result = subprocess.run(
            ["python", "-m", "genesis", *args],
            cwd=project_path, capture_output=True, text=True, env=env, timeout=timeout,
        )
        return result.stdout.strip() or result.stderr.strip() or "(no output)"
    except subprocess.TimeoutExpired:
        return f"Command timed out after {timeout}s"
    except Exception as e:
        return f"Error: {e}"


def execute_tool(name: str, params: dict, workspace: Path) -> str | None:
    """Execute an F_D tool. Returns result string, or None if not an F_D tool."""

    if name == "list_projects":
        projects = sorted(
            p.name for p in workspace.iterdir()
            if p.is_dir() and (p / ".genesis").exists()
        )
        if not projects:
            return f"No genesis projects found under {workspace}"
        return "Genesis projects:\n" + "\n".join(f"  - {p}" for p in projects)

    if name == "project_status":
        pp = workspace / params.get("project", "")
        if not (pp / ".genesis").exists():
            return f"Project '{params.get('project')}' not found"
        return _genesis_run(pp, "status")

    if name == "project_gaps":
        pp = workspace / params.get("project", "")
        if not (pp / ".genesis").exists():
            return f"Project '{params.get('project')}' not found"
        return _genesis_run(pp, "gaps")

    if name == "gen_start":
        pp = workspace / params.get("project", "")
        if not (pp / ".genesis").exists():
            return f"Project '{params.get('project')}' not found"
        return _genesis_run(pp, "start", "--auto", timeout=120)

    if name == "gen_iterate":
        pp = workspace / params.get("project", "")
        if not (pp / ".genesis").exists():
            return f"Project '{params.get('project')}' not found"
        args = ["iterate"]
        if params.get("feature"):
            args.extend(["--feature", params["feature"]])
        if params.get("edge"):
            args.extend(["--edge", params["edge"]])
        return _genesis_run(pp, *args, timeout=120)

    if name == "read_file":
        fp = workspace / params.get("project", "") / params.get("path", "")
        if not fp.exists():
            return f"File not found: {params.get('project')}/{params.get('path')}"
        if fp.is_dir():
            return "Path is a directory, use list_files instead"
        try:
            content = fp.read_text()
            if len(content) > 10000:
                content = content[:10000] + f"\n... (truncated, {len(content)} total chars)"
            return content
        except Exception as e:
            return f"Error reading file: {e}"

    if name == "list_files":
        dp = workspace / params.get("project", "") / params.get("path", ".")
        if not dp.exists():
            return f"Path not found"
        if not dp.is_dir():
            return "Not a directory"
        entries = sorted(dp.iterdir())
        lines = []
        for e in entries[:100]:
            prefix = "d " if e.is_dir() else "f "
            lines.append(f"  {prefix}{e.name}")
        return "\n".join(lines) or "(empty directory)"

    return None
