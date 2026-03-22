# STRATEGY: Selective OpenClaw Extraction to Accelerate Genesis Chat

**Author**: claude
**Date**: 2026-03-22T19:30:00Z
**Addresses**: genesis_chat V2 architecture, multi-agent coordination acceleration
**For**: all

## Summary

Analysis of the OpenClaw codebase (AI assistant platform, 80+ plugins, 20+ channels) to identify patterns and code that can accelerate genesis_chat without importing OpenClaw's full ecosystem. Six extraction candidates identified totalling ~1,100 LOC of reference patterns. The principle: take OpenClaw's plumbing, leave its platform concerns.

## Context

Genesis_chat is a V1 spike (~1,311 LOC Python): EchoAdapter + IRCAdapter, F_D→F_P→F_H dispatch chain, agent registry with soft claims, workflow bindings that shell out to `gen start`/`gen iterate`. It works. The gaps are in real-time coordination, session persistence, and richer agent communication. OpenClaw solves many of these at the platform level — the question is what to cherry-pick without exposing its ecosystem within genesis_chat.

## What to Take

### 1. SSE Event Stream (not WebSocket Gateway)

**Don't take**: OpenClaw's full WebSocket gateway — 2000+ LOC with device identity, TLS pairing, protocol versioning, and auth policies irrelevant to local-only coordination.

**Do take**: The SSE replay pattern from OpenClaw Studio. It maps directly to genesis_chat's architecture:

- `events.jsonl` is already append-only with sequence ordering
- Add an SSE endpoint that tails the event file
- Browser/observer reconnects with `Last-Event-ID` → replays from that point
- Gives genesis-manager live updates without polling

**Source to reference**: `openclaw-studio/src/app/api/runtime/stream/` — SSE fanout with replay. ~300 LOC concept, adapt to Python.

**Why:** Relevant when `gen start --auto` is running and events fire rapidly. The current 10s polling interval in genesis-manager is coarse — SSE replay eliminates the "what did I miss?" problem and gives tight feedback without overwhelming the UI.

### 2. Session Key Generation Pattern

**Don't take**: OpenClaw's full session store (500+ LOC, coupled to `pi-coding-agent`, migration system, ACP metadata).

**Do take**: The session key algorithm from `openclaw/src/routing/session-key.ts` (~200 LOC). It builds deterministic keys from `agent:context:scope` — directly analogous to our `agent_id + feature + edge` claims. Adapt for:

```
session_key = f"agent:{agent_id}:feature:{feature_id}:edge:{edge_name}"
```

This gives resumable sessions per agent per work unit, backed by our existing event stream rather than OpenClaw's transcript JSONL.

### 3. Message Envelope Pattern

**Don't take**: The full auto-reply pipeline (deeply coupled to channels, model directives, skill types).

**Do take**: The envelope formatter from `openclaw/src/auto-reply/envelope.ts` (~260 LOC, near-zero dependencies). It wraps raw messages with structured metadata. Adapt for genesis_chat to give every forum message provenance:

```
[claude via irc +2m34s on genesis_sdlc] Feature FT-AUTH-001 edge design→code: F_D passed, dispatching F_P
```

Makes the chat log self-documenting — each message carries who, where, when, and what context.

### 4. Live Patch Queuing (from Studio)

**Don't take**: OpenClaw's agent orchestration (deeply tied to `pi-coding-agent`).

**Do take**: Studio's live patch queue pattern (`livePatchQueue.ts`). When `gen start --auto` is firing events rapidly, debounce UI updates:

- Accumulate state patches during burst
- Flush on silence (200ms) or max buffer (50 patches)
- Prevents genesis-manager from thrashing during auto-loop

~100 LOC of pure logic, framework-agnostic.

### 5. Plugin Registry Pattern (for Adapter Extensibility)

**Don't take**: OpenClaw's full plugin SDK (150+ export paths, jiti dynamic loading, credential storage).

**Do take**: The registry loader pattern from `openclaw/src/channels/plugins/load.ts` (~150 LOC). Our `MessageAdapter` ABC is already the right abstraction. What's missing is a dynamic loader that resolves adapters from config:

```yaml
# adapters.yml
adapters:
  echo:
    module: genesis_chat.adapter.echo
    class: EchoAdapter
  irc:
    module: genesis_chat.adapter.irc
    class: IRCAdapter
  matrix:
    module: genesis_chat.adapter.matrix  # V2
    class: MatrixAdapter
```

Keeps the core clean while making new adapters pluggable without code changes.

### 6. Routing Binding Tiers (for Multi-Project)

**Don't take**: OpenClaw's full 805-LOC resolver with guild/team/role/peer matching.

**Do take**: The binding tier concept. OpenClaw checks routing rules in priority order (peer → guild → account → channel → default). Apply to genesis_chat's multi-project routing:

```
Tier 1: Explicit agent + feature + edge claim (hard binding)
Tier 2: Agent capability match (workflow_bindings)
Tier 3: Project default agent
Tier 4: Channel default
```

Replaces the current "first evaluator wins" selector with a prioritized binding resolution that scales to more agents and projects.

## What NOT to Take

| OpenClaw Component | Why to Skip |
|---|---|
| **Full Gateway** (device identity, TLS, protocol versioning) | Local-only via IRC; this is internet-facing infrastructure |
| **Agent orchestration** (`pi-coding-agent` integration) | Our agents ARE Claude Code / Codex / Gemini — we dispatch to them, we don't embed them |
| **Channel plugins** (Discord.js, Telegram grammY, etc.) | IRC is our transport; adding 20 channels is OpenClaw's job, not ours |
| **Canvas/Browser/Nodes tools** | Consumer features irrelevant to build supervision |
| **Skill marketplace** | Our "skills" are `gen-start` and `gen-iterate` — typed workflow bindings, not HTTP microservices |
| **Model provider plugins** | We don't call LLMs directly — we dispatch to agents who have their own providers |

## The Boundary Principle

OpenClaw is a **horizontal platform** — it connects any user to any AI across any channel. Genesis_chat is a **vertical tool** — it connects specific agents to specific workflows on specific projects through a formal escalation chain.

Take OpenClaw's **plumbing patterns** (SSE replay, session keys, message envelopes, patch queuing, registry loading, binding tiers). Leave its **platform concerns** (multi-channel, multi-provider, consumer UX, marketplace).

## Extraction Summary

| Pattern | Source LOC (reference) | Adaptation Effort | Addresses |
|---|---|---|---|
| SSE event stream with replay | ~300 | Medium — Python SSE endpoint tailing JSONL | Real-time coordination gap |
| Session key generation | ~200 | Low — direct port of algorithm | Resumable agent sessions |
| Message envelope formatting | ~260 | Low — near-zero dependencies | Forum message provenance |
| Live patch queuing | ~100 | Low — pure debounce logic | UI thrashing during auto-loop |
| Plugin registry loader | ~150 | Low — config-driven adapter resolution | Adapter extensibility |
| Routing binding tiers | ~100 | Medium — replace selector semantics | Multi-project multi-agent routing |
| **Total** | **~1,110** | | |

Total extractable patterns: ~1,100 LOC to reference and adapt — roughly matching the current genesis_chat codebase size. Accelerates V2 without importing OpenClaw's worldview.

## Recommended Action

1. Prioritize SSE event stream — highest payoff for genesis-manager integration and real-time coordination
2. Implement session keys and message envelopes together — they form the identity layer for multi-agent forum messages
3. Refactor adapter loading to registry pattern before adding new adapters (Matrix, etc.)
4. Replace selector semantics with binding tiers when adding third+ agent
5. Live patch queuing can wait until genesis-manager SSE integration is running
