# Implements: REQ-F-AGENT-001
# Implements: REQ-F-AGENT-002
# Implements: REQ-F-SESS-002
# Implements: REQ-F-TIER-002
"""Agent registry and soft claim mechanism."""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path

try:
    import yaml
except ImportError:
    import json as _json  # fallback — yaml not available in all envs

    class _yaml_shim:
        @staticmethod
        def safe_load(text):
            return _json.loads(text)
    yaml = _yaml_shim()


@dataclass
class AgentConfig:
    id: str
    display_name: str
    write_territory: str
    workflow_bindings: list[str]
    role: str
    default_projects: list[str] = field(default_factory=list)


@dataclass
class Claim:
    agent: str
    feature: str
    edge: str
    claimed_at: str
    status: str  # active | released | expired
    session_key: str = ""


class AgentRegistry:
    def __init__(self, registry_path: Path):
        data = yaml.safe_load(registry_path.read_text())
        self._agents: dict[str, AgentConfig] = {}
        for entry in data.get("agents", []):
            a = AgentConfig(
                id=entry["id"],
                display_name=entry["display_name"],
                write_territory=entry["write_territory"],
                workflow_bindings=entry["workflow_bindings"],
                role=entry["role"],
                default_projects=entry.get("default_projects", []),
            )
            self._agents[a.id] = a

    def get(self, agent_id: str) -> AgentConfig | None:
        return self._agents.get(agent_id)

    def all(self) -> list[AgentConfig]:
        return list(self._agents.values())

    def capable_of(self, workflow: str) -> list[AgentConfig]:
        return [a for a in self._agents.values() if workflow in a.workflow_bindings]

    def default_for_project(self, project: str) -> AgentConfig | None:
        for a in self._agents.values():
            if project in a.default_projects:
                return a
        return None


class ClaimRegistry:
    def __init__(self, claims_dir: Path):
        self.claims_dir = claims_dir
        claims_dir.mkdir(parents=True, exist_ok=True)

    def claim(self, agent_id: str, feature: str, edge: str, session_key: str = "") -> Claim:
        c = Claim(
            agent=agent_id,
            feature=feature,
            edge=edge,
            claimed_at=datetime.now(timezone.utc).isoformat(),
            status="active",
            session_key=session_key,
        )
        slug = f"{agent_id}_{feature}_{edge.replace('→', '_').replace(' ', '_')}"
        path = self.claims_dir / f"{slug}.yml"
        path.write_text(
            f"agent: {c.agent}\nfeature: {c.feature}\nedge: {c.edge}\n"
            f"claimed_at: {c.claimed_at}\nstatus: {c.status}\n"
            f"session_key: {c.session_key}\n"
        )
        return c

    def find_by_session(self, key: str) -> Claim | None:
        for f in self.claims_dir.glob("*.yml"):
            data = yaml.safe_load(f.read_text())
            if data.get("session_key") == key:
                claim = Claim(**data)
                if claim.status == "active":
                    return claim
        return None

    def active_claims(self) -> list[Claim]:
        claims = []
        for f in self.claims_dir.glob("*.yml"):
            data = yaml.safe_load(f.read_text())
            claims.append(Claim(**data))
        return [c for c in claims if c.status == "active"]
