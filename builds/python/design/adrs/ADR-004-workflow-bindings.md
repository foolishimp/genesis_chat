# ADR-004: Workflow Bindings, Context Assembly, and Event Tracing

**Status**: Accepted
**Implements**: REQ-F-WORK-001, REQ-F-WORK-002, REQ-F-CTX-001, REQ-F-TRACE-001
**Date**: 2026-03-17

## Decision

Workflow bindings map intent text → genesis CLI invocation on a target workspace.
Context assembly reads the target project's event stream and recent feature vectors
to give the agent orientation before dispatching. Event tracing emits events to the
TARGET project's event stream, not genesis_chat's.

## Workflow binding schema

```yaml
workflow_bindings:
  gen-start:
    command: "PYTHONPATH={workspace}/.genesis python -m genesis start --auto --human-proxy"
    args:
      workspace: required
      feature: optional
    description: "Run genesis start loop on a target project"

  gen-iterate:
    command: "PYTHONPATH={workspace}/.genesis python -m genesis start --feature {feature} --edge {edge}"
    args:
      workspace: required
      feature: required
      edge: optional
    description: "Run one iteration on a specific feature/edge"
```

Bindings are declared in `workflow_bindings.yml` at the workspace root. The work_intent
F_P evaluator resolves the text to a binding, fills args, and the dispatcher executes.

## Context assembly

Before dispatching a workflow to an agent, the channel assembles a context pack:
- Last 10 events from the target project's event stream
- Active feature vectors for the requested feature (if specified)
- Most recent design post from `.ai-workspace/comments/claude/` (if exists)

Context is passed as a string prepended to the workflow invocation prompt. This
gives a returning agent enough orientation without a full session recap.

## Event tracing

All events emitted during a workflow invocation go to the TARGET project's
`.ai-workspace/events/events.jsonl` — the standard genesis write path. genesis_chat
does not have its own canonical event log for workflow results.

genesis_chat's event stream records channel-level events only:
- `message_received` — human or agent message arrived
- `workflow_dispatched` — work intent routed to agent + binding
- `workflow_completed` — workflow returned a result
- `approval_requested` — F_H gate surfaced in channel
- `approval_resolved` — human responded to gate

## Consequences

- Workflow bindings are a YAML registry — extensible without code changes
- Target project events are authoritative — no duplication into genesis_chat stream
- Context assembly is cheap (read + format) — no LLM call before dispatch
- The channel acts as a thin coordination layer; the target project's engine does
  the heavy lifting
- V2 extensions: add gen-review, gen-gaps, gen-status as channel commands via bindings
