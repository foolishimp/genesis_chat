# Implements: REQ-F-DISP-002
"""F_P work intent router — maps message text to agent + workflow binding."""
from __future__ import annotations

import re
from dataclasses import dataclass

from genesis_chat.registry.agents import AgentConfig
from genesis_chat.workflow.bindings import WorkflowBinding


@dataclass
class WorkIntent:
    agent: AgentConfig
    binding: WorkflowBinding
    workspace: str
    params: dict


# Pattern: (regex, workflow_name)
# Groups are workspace [, feature]
_PATTERNS = [
    (re.compile(r"start\s+(\S+)", re.I),                             "gen-start"),
    (re.compile(r"run\s+gen-start\s+on\s+(\S+)", re.I),             "gen-start"),
    (re.compile(r"iterate\s+(\S+)\s+on\s+(\S+)", re.I),             "gen-iterate"),
    (re.compile(r"iterate\s+(\S+)", re.I),                           "gen-iterate"),
    (re.compile(r"run\s+gen-iterate\s+on\s+(\S+)", re.I),           "gen-iterate"),
]


def route_intent(
    text: str,
    agents: list[AgentConfig],
    bindings: dict[str, WorkflowBinding],
    workspace_root: str,
) -> WorkIntent | None:
    for pattern, workflow_name in _PATTERNS:
        m = pattern.search(text)
        if not m or workflow_name not in bindings:
            continue
        capable = [a for a in agents if workflow_name in a.workflow_bindings]
        if not capable:
            continue
        agent = capable[0]
        binding = bindings[workflow_name]
        groups = m.groups()
        params: dict = {}

        if workflow_name == "gen-iterate":
            if len(groups) == 2:
                # "iterate <feature> on <project>"
                params["feature"] = groups[0]
                params["workspace"] = f"{workspace_root}/{groups[1]}"
            else:
                # "iterate <project>" — no feature specified
                params["workspace"] = f"{workspace_root}/{groups[0]}"
        else:
            # gen-start: last group is project name
            params["workspace"] = f"{workspace_root}/{groups[-1]}"

        return WorkIntent(
            agent=agent,
            binding=binding,
            workspace=params["workspace"],
            params=params,
        )
    return None
