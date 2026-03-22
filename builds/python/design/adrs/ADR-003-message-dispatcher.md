# ADR-003: Message Dispatcher — Runtime GTL Package

**Status**: Accepted
**Implements**: REQ-F-DISP-001, REQ-F-DISP-002, REQ-F-DISP-003
**Date**: 2026-03-17

## Decision

The dispatcher is a runtime GTL Package with two assets and one edge. An incoming
`ChatMessage` is the source asset; a `ChannelResponse` is the target. The resolve
edge uses selector semantics: first passing evaluator wins.

## Runtime graph

```
ChatMessage → ChannelResponse
    edge: resolve
    evaluators (in order):
      1. command_match  (F_D) — registered command pattern match
      2. work_intent    (F_P) — route to agent + workflow binding
      3. approval_gate  (F_H) — pending approval resolution
```

Selector semantics: `confirm="question"` on the edge — the edge converges when
any single evaluator passes. This differs from build-time all-must-pass semantics.

## Evaluator contracts

**command_match (F_D)**
- Input: message text, command registry (list of `{pattern, handler, description}`)
- Output: `(matched: bool, handler_fn, args)`
- Registered commands: `status`, `gaps`, `approve <id>`, `assign <agent> <task>`, `help`
- No LLM call. Pure string/regex matching. < 10ms.

**work_intent (F_P)**
- Input: message text, agent registry, workflow bindings, workspace context
- Output: `(agent_id, workflow, target_workspace, params)`
- Fires only when command_match fails
- Routes "iterate auth feature on genesis_sdlc" → `{agent: claude, workflow: gen-iterate,
  workspace: /path/to/genesis_sdlc, params: {feature: REQ-F-AUTH}}`

**approval_gate (F_H)**
- Input: message text, pending approvals table
- Output: `(resolved: bool, pending_op_id, decision: approved|rejected)`
- Fires when message is a reply to a pending approval prompt
- The adapter's `request_approval()` is the write path; this is the read path

## Command registry format

```yaml
commands:
  - pattern: "^status$"
    handler: cmd_status
    description: "Show workspace status"
  - pattern: "^gaps$"
    handler: cmd_gaps
    description: "Show convergence gaps"
  - pattern: "^approve (.+)$"
    handler: cmd_approve
    description: "Approve a pending operation"
  - pattern: "^assign (\\w+) (.+)$"
    handler: cmd_assign
    description: "Assign a task to an agent"
  - pattern: "^help$"
    handler: cmd_help
    description: "List available commands"
```

## Consequences

- F_D command handling is fast and deterministic — no LLM involved
- work_intent F_P fires only on genuine work requests, not accidental matches
- approval_gate ensures F_H gates from running workflows surface cleanly in channel
- Selector semantics mean one clear winning path per message — no ambiguous multi-match
