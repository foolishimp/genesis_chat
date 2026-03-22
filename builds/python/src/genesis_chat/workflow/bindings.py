# Implements: REQ-F-WORK-001
# Implements: REQ-F-WORK-002
"""Workflow binding registry and executor."""
from __future__ import annotations

import os
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
class WorkflowBinding:
    name: str
    command_template: str
    args: dict
    description: str


class BindingRegistry:
    def __init__(self, bindings_path: Path):
        data = yaml.safe_load(bindings_path.read_text())
        self.bindings: dict[str, WorkflowBinding] = {}
        for name, entry in data.get("workflow_bindings", {}).items():
            self.bindings[name] = WorkflowBinding(
                name=name,
                command_template=entry["command"],
                args=entry.get("args", {}),
                description=entry.get("description", ""),
            )

    def get(self, name: str) -> WorkflowBinding | None:
        return self.bindings.get(name)


def execute_binding(binding: WorkflowBinding, workspace: str, params: dict, session_key: str = "") -> str:
    """Render the command template, execute in the target workspace, return output."""
    env = {**os.environ, "PYTHONPATH": str(Path(workspace) / ".genesis")}
    if session_key:
        env["GENESIS_SESSION_KEY"] = session_key
    cmd = binding.command_template
    for key, val in params.items():
        cmd = cmd.replace(f"{{{key}}}", str(val))
    cmd = cmd.replace("{workspace}", workspace)
    try:
        result = subprocess.run(
            cmd, shell=True, cwd=workspace,
            capture_output=True, text=True, env=env, timeout=300,
        )
        output = result.stdout.strip()
        if result.returncode != 0 and result.stderr.strip():
            output = (output + "\n" + result.stderr.strip()).strip()
        return output or "(no output)"
    except subprocess.TimeoutExpired:
        return "(workflow timed out after 300s)"
    except Exception as e:
        return f"(execution error: {e})"
