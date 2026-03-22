# Backlog Item Conventions

**Governance**: Maintained by the methodology author. Read-only for agents.

**NOTE TO LLM**: If this file is referenced in a prompt, it is an active instruction to create or update a backlog item in the format specified here.

---

## What the Backlog Is

A pre-intent holding area. Items here are interesting but not ready to become intent vectors — they need more context, capacity, dependency resolution, or incubation before promotion.

The backlog is a sidecar to the SDLC graph. It has no evaluators, no convergence criteria, no gates. It is monitored by the sensory system, not driven by the engine.

---

## File Location and Naming

```
.ai-workspace/backlog/BL-{NNN}.yml
```

Sequence is monotonic. Check existing files for the highest current number and increment by one. Gaps in sequence are acceptable.

---

## Schema

```yaml
id: BL-001
title: Short imperative phrase describing the idea
status: idea | incubating | ready | promoted | abandoned
created: YYYY-MM-DD
updated: YYYY-MM-DD
notes: |
  Free-form prose. No length limit. This is the incubation space —
  write what you know, what's uncertain, and what would need to be
  true before this becomes an intent vector.
promoted_to: REQ-F-*        # set on promotion only
promotion_reason: text      # set on promotion only
```

**Required fields**: `id`, `title`, `status`, `created`

**Optional fields**: `notes`, `promoted_to`, `promotion_reason`

---

## Status Lifecycle

```
idea → incubating → ready → promoted
                  ↘ abandoned
```

| Status | Meaning |
|--------|---------|
| `idea` | Captured, not yet evaluated. Default on creation. |
| `incubating` | Under active consideration — notes being developed, dependencies being mapped. |
| `ready` | Sufficiently understood to become an intent vector. Surfaces as an attention signal in `gen backlog status`. |
| `promoted` | Converted to an intent vector via `gen backlog promote`. `promoted_to` and `promotion_reason` set. |
| `abandoned` | Will not be pursued. Reason recorded in `notes`. |

---

## Writing Good Notes

Notes are the incubation surface. A good notes field captures:

- **What problem this solves** — one sentence, no setup
- **What's uncertain** — dependencies, unknowns, open questions
- **What would need to be true** before this is ready to promote
- **Any related work** — backlog items, features, ADRs this touches

Avoid: describing what the feature would look like in detail (that belongs in the intent/requirements stage), or restating the title.

---

## Promotion

Promote when:
- The item is understood well enough to write an intent vector
- Dependencies are resolved or explicitly accepted as risks
- Capacity exists and strategic fit is clear

Promote via:
```bash
python -m genesis_sdlc.backlog promote BL-xxx \
  --reason "capacity freed after v0.1.4 release" \
  --feature REQ-F-NEW-001
```

This emits `intent_raised` and marks the item `promoted`. The item is not deleted — it remains as audit history.
