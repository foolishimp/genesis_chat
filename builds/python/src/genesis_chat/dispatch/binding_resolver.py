# Implements: REQ-F-TIER-001
# Implements: REQ-F-TIER-002
# Implements: REQ-F-TIER-003
"""Four-tier binding resolution for multi-agent multi-project routing.

Tier 1 — Active claim: Agent has a live claim on this feature+edge
Tier 2 — Capability match: Agent's workflow_bindings includes the requested workflow
Tier 3 — Project default: Agent is configured as default for this project
Tier 4 — Channel default: Fallback to first capable agent

Source reference: OpenClaw src/routing/resolve-route.ts binding tier concept.
Our adaptation is ~80 LOC — four tiers vs seven, no guild/team/peer dimensions.
"""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from genesis_chat.registry.agents import AgentConfig, ClaimRegistry
from genesis_chat.workflow.bindings import WorkflowBinding


@dataclass
class ResolvedBinding:
    agent: AgentConfig
    binding: WorkflowBinding
    tier: int  # 1-4
    reason: str  # human-readable


def resolve_binding(
    workflow_name: str,
    agents: list[AgentConfig],
    bindings: dict[str, WorkflowBinding],
    claims: ClaimRegistry,
    project: str | None = None,
    feature: str | None = None,
    edge: str | None = None,
) -> ResolvedBinding | None:
    """Resolve agent + binding through four-tier priority matching."""
    binding = bindings.get(workflow_name)
    if not binding:
        return None

    # Tier 1: Active claim on this feature+edge
    if feature and edge:
        for claim in claims.active_claims():
            if claim.feature == feature and claim.edge == edge:
                agent = _find_agent(agents, claim.agent)
                if agent and workflow_name in agent.workflow_bindings:
                    return ResolvedBinding(
                        agent=agent,
                        binding=binding,
                        tier=1,
                        reason=f"active claim on {feature}:{edge}",
                    )

    # Tier 2: Capability match (agent has this workflow in bindings)
    capable = [a for a in agents if workflow_name in a.workflow_bindings]

    # Tier 3: Among capable agents, prefer project default
    if project and capable:
        for a in capable:
            if project in a.default_projects:
                return ResolvedBinding(
                    agent=a,
                    binding=binding,
                    tier=3,
                    reason=f"default agent for project {project}",
                )

    # Tier 2 (fallback): first capable agent
    if capable:
        return ResolvedBinding(
            agent=capable[0],
            binding=binding,
            tier=2,
            reason=f"capability match ({workflow_name})",
        )

    # Tier 4: Channel default — first agent regardless
    if agents:
        return ResolvedBinding(
            agent=agents[0],
            binding=binding,
            tier=4,
            reason="channel default (no capability match)",
        )

    return None


def _find_agent(agents: list[AgentConfig], agent_id: str) -> AgentConfig | None:
    for a in agents:
        if a.id == agent_id:
            return a
    return None
