# ADR-002: Agent Registry Schema

**Status**: Accepted
**Implements**: REQ-F-AGENT-001, REQ-F-AGENT-002
**Date**: 2026-03-17

## Decision

Agent registry is a YAML file at `agents.yml` in the workspace root. It declares
agent identity, capability bindings, and write territory. An agent claim is a
runtime record written to `.ai-workspace/claims/` — a lightweight YAML file
marking that an agent has taken a work item.

## Registry schema

```yaml
agents:
  - id: claude
    display_name: Claude (primary)
    write_territory: .ai-workspace/comments/claude/
    workflow_bindings:
      - gen-start
      - gen-iterate
    role: primary

  - id: mock_agent
    display_name: Mock Agent (spike second slot)
    write_territory: .ai-workspace/comments/mock_agent/
    workflow_bindings:
      - gen-start
    role: secondary
```

## Claim schema

```
.ai-workspace/claims/{agent_id}_{feature}_{edge}_{ISO}.yml

agent: claude
feature: REQ-F-AUTH
edge: design→code
claimed_at: 2026-03-17T14:00:00Z
status: active | released | expired
```

Claims are soft — they are advisory coordination signals, not hard locks. If a
claim exists, other agents see the work is in progress. Claims expire after 30
minutes of inactivity (no events emitted by that agent for that feature).

## Consequences

- YAML registry is human-readable and editable; no service required
- Claim files live in .ai-workspace — they are trace surface, not control surface
- V2 hard-lock semantics can be layered on top without changing the schema
- mock_agent in spike is a stub that returns canned responses; the registry
  schema is identical to what a real second agent would use
