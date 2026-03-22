# STRATEGY: V2 Acceleration Plan — Requirements, Design, Task Execution

**Author**: claude
**Date**: 2026-03-22T20:00:00Z
**Addresses**: V2 scope, openclaw selective extraction (ref: 20260322T193000_STRATEGY)
**For**: all

## Summary

Detailed execution plan for genesis_chat V2: six work packages derived from the OpenClaw selective extraction strategy, each with requirements, design decisions, and ordered tasks. Total estimated scope: ~1,100 LOC of new Python code across 8 new/modified modules. Build order respects dependencies — message envelope and session keys are foundational; SSE streaming and binding tiers depend on them.

---

## Build Order & Dependency Graph

```
                 WP-1: Message Envelope
                 WP-2: Session Keys
                    ↓          ↓
            WP-3: SSE Stream   WP-4: Binding Tiers
                    ↓
            WP-5: Adapter Registry
                    ↓
            WP-6: Patch Queuing (genesis-manager side)
```

WP-1 and WP-2 are independent of each other, can be built in parallel.
WP-3 depends on WP-1 (envelope format used in SSE payloads).
WP-4 depends on WP-2 (session keys used in binding resolution).
WP-5 depends on WP-4 (registry resolves adapter by binding tier config).
WP-6 is genesis-manager work, depends on WP-3 (consumes SSE stream).

---

## WP-1: Message Envelope

### Problem
Channel messages have no structured provenance. A message from claude about feature FT-AUTH-001 on edge design→code looks the same as a status command response. Context is lost in the flat text stream.

### Requirements

**REQ-F-ENV-001 — Structured message envelope**
Every outbound ChannelResponse carries structured metadata: sender identity, target project, elapsed time since dispatch, and work context (feature, edge) when available.
Acceptance: ChannelResponse includes an `envelope` field; `adapter.send()` renders it as a formatted prefix.

**REQ-F-ENV-002 — Envelope rendering per adapter**
Each adapter renders the envelope in its platform-native format. IRC: `[claude via irc +2m34s on genesis_sdlc]`. Echo: `[claude +2m34s]`. Future adapters define their own rendering.
Acceptance: EchoAdapter and IRCAdapter both render envelopes; format is adapter-specific.

**REQ-F-ENV-003 — Work context propagation**
When a dispatch originates from F_P (work intent), the envelope carries feature and edge context. F_D commands carry command name. Unrecognised input carries no work context.
Acceptance: Envelope metadata populated by dispatcher based on dispatch path (F_D/F_P/F_H).

### Design

Extend `ChannelResponse` in `adapter/base.py`:

```python
@dataclass
class MessageEnvelope:
    sender: str
    platform: str
    project: str | None = None
    feature: str | None = None
    edge: str | None = None
    command: str | None = None
    elapsed_ms: int | None = None
    timestamp: str = ""  # ISO 8601, assigned at creation

@dataclass
class ChannelResponse:
    text: str
    reply_to: str
    sender: str
    envelope: MessageEnvelope | None = None
```

Dispatcher creates envelope at dispatch time. Each adapter's `send()` renders `envelope` as prefix using a `format_envelope(envelope) -> str` method on the adapter base class (with default implementation, overridable per adapter).

**Source reference**: OpenClaw `src/auto-reply/envelope.ts` (~260 LOC). Our adaptation is ~80 LOC — simpler because we have fewer channels and no timezone negotiation.

### Tasks

| # | Task | File | Est LOC |
|---|------|------|---------|
| 1.1 | Add `MessageEnvelope` dataclass to `adapter/base.py` | `adapter/base.py` | +15 |
| 1.2 | Add `envelope` field to `ChannelResponse` | `adapter/base.py` | +2 |
| 1.3 | Add `format_envelope()` default method to `MessageAdapter` | `adapter/base.py` | +15 |
| 1.4 | Override `format_envelope()` in `EchoAdapter` | `adapter/echo.py` | +10 |
| 1.5 | Override `format_envelope()` in `IRCAdapter` | `adapter/irc.py` | +12 |
| 1.6 | Update `adapter.send()` in both adapters to prepend envelope | `adapter/echo.py`, `adapter/irc.py` | +8 |
| 1.7 | Update `Dispatcher.dispatch()` to create envelope on each path (F_D, F_P, F_H) | `dispatch/dispatcher.py` | +25 |
| 1.8 | Add timing: record dispatch start time, compute elapsed at response | `dispatch/dispatcher.py` | +8 |
| 1.9 | Tests: envelope creation, rendering per adapter, context propagation | `tests/test_envelope.py` (new) | +60 |

**Total: ~155 LOC**

---

## WP-2: Session Keys

### Problem
Agent work is not resumable. If an agent crashes mid-iteration or the channel restarts, there's no way to correlate the new session with the previous work context. Claims are soft and expire — they don't provide session identity.

### Requirements

**REQ-F-SESS-001 — Deterministic session key generation**
Every agent dispatch generates a deterministic session key from `agent_id + project + feature + edge`. Same inputs always produce the same key.
Acceptance: `session_key("claude", "genesis_sdlc", "FT-AUTH-001", "design→code")` returns the same string on every call.

**REQ-F-SESS-002 — Session key stored in claims**
Claims carry the session key. When an agent resumes work on the same feature+edge, it finds its prior claim by session key rather than scanning all claims.
Acceptance: `Claim` dataclass includes `session_key` field; `ClaimRegistry.find_by_session()` returns matching claim.

**REQ-F-SESS-003 — Session key in event metadata**
When workflow execution emits events to the target project, the session key is included in event data. This threads the channel session to the project event stream.
Acceptance: `execute_binding()` passes session key as env var; events emitted during execution carry `session_key` in their data payload.

### Design

New module: `session/keys.py`

```python
import hashlib

def session_key(agent_id: str, project: str, feature: str = "main", edge: str = "main") -> str:
    """Deterministic session key: agent:project:feature:edge."""
    raw = f"agent:{agent_id}:project:{project}:feature:{feature}:edge:{edge}"
    short_hash = hashlib.sha256(raw.encode()).hexdigest()[:8]
    return f"{agent_id}:{project}:{feature}:{edge}:{short_hash}"
```

The hash suffix prevents collision when feature/edge names contain special characters. The human-readable prefix keeps keys inspectable.

Extend `Claim` to carry `session_key`. Extend `execute_binding()` to pass `GENESIS_SESSION_KEY` env var to subprocess.

**Source reference**: OpenClaw `src/routing/session-key.ts` (~200 LOC). Our adaptation is ~40 LOC — simpler because we don't have multi-account/guild/peer dimensions.

### Tasks

| # | Task | File | Est LOC |
|---|------|------|---------|
| 2.1 | Create `session/keys.py` with `session_key()` function | `session/keys.py` (new) | +20 |
| 2.2 | Add `session_key` field to `Claim` dataclass | `registry/agents.py` | +3 |
| 2.3 | Update `ClaimRegistry.claim()` to compute and store session key | `registry/agents.py` | +8 |
| 2.4 | Add `ClaimRegistry.find_by_session(key) -> Claim | None` | `registry/agents.py` | +10 |
| 2.5 | Update `execute_binding()` to pass `GENESIS_SESSION_KEY` env var | `workflow/bindings.py` | +5 |
| 2.6 | Update `Dispatcher.dispatch()` F_P path to compute session key and pass to claim + binding | `dispatch/dispatcher.py` | +10 |
| 2.7 | Tests: key determinism, key uniqueness, claim lookup by session, env var propagation | `tests/test_session_keys.py` (new) | +50 |

**Total: ~106 LOC**

---

## WP-3: SSE Event Stream

### Problem
Genesis-manager polls the backend every 10 seconds. During `gen start --auto`, events fire rapidly and the observer misses intermediate state. There's no way for the channel to push real-time updates to external observers.

### Requirements

**REQ-F-SSE-001 — SSE endpoint tailing events.jsonl**
A lightweight HTTP server exposes an SSE endpoint that tails the target project's `events.jsonl`. New events are pushed to connected clients as they are appended.
Acceptance: `GET /events/stream` returns `text/event-stream`; new events appear within 1s of being appended.

**REQ-F-SSE-002 — Replay from Last-Event-ID**
When a client reconnects with `Last-Event-ID` header, the server replays all events after that sequence number before switching to live tail.
Acceptance: Client disconnects, reconnects with last seen ID, receives all missed events without gaps or duplicates.

**REQ-F-SSE-003 — Envelope-formatted event payloads**
SSE event data includes the message envelope (WP-1) when the event originated from a channel dispatch. Raw project events are forwarded as-is.
Acceptance: SSE events from channel dispatch include envelope metadata; project events include raw event JSON.

**REQ-F-SSE-004 — Channel message broadcast**
Channel messages (both inbound and outbound) are broadcast on the SSE stream in addition to project events. Observers see the full conversation.
Acceptance: All `adapter.send()` calls also emit an SSE event with envelope and response text.

### Design

New module: `stream/sse_server.py`

```python
# Minimal SSE server using stdlib http.server (no external deps)
# Runs on a separate thread, shares an event queue with the channel loop

class SSEServer:
    def __init__(self, events_path: Path, port: int = 8086):
        ...

    def start(self) -> None:
        """Start HTTP server on background thread."""

    def broadcast(self, event_type: str, data: dict, seq: int) -> None:
        """Push event to all connected SSE clients."""

    def _tail_events(self) -> None:
        """Background: watch events.jsonl for appends, broadcast new lines."""
```

The tail uses `os.stat()` polling (200ms) on the JSONL file — simpler than inotify/kqueue and cross-platform. Each event gets a sequence number (line number in JSONL). `Last-Event-ID` maps directly to this sequence.

Channel loop integration: after `adapter.send()`, also call `sse_server.broadcast("channel_message", {...})`.

**Source reference**: OpenClaw Studio SSE replay pattern. Our adaptation is ~180 LOC — stdlib only, no dependencies.

### Tasks

| # | Task | File | Est LOC |
|---|------|------|---------|
| 3.1 | Create `stream/sse_server.py` with `SSEServer` class | `stream/sse_server.py` (new) | +120 |
| 3.2 | Implement `_tail_events()` — file watcher on events.jsonl | `stream/sse_server.py` | (included above) |
| 3.3 | Implement `Last-Event-ID` replay on client connect | `stream/sse_server.py` | (included above) |
| 3.4 | Add `broadcast()` call after `adapter.send()` in `channel.py` | `channel.py` | +15 |
| 3.5 | Add `--sse-port` CLI flag to `__main__.py` | `__main__.py` | +8 |
| 3.6 | Start SSE server in `run()` when `--sse-port` provided | `channel.py` | +10 |
| 3.7 | Envelope integration: include envelope metadata in SSE event data | `channel.py` | +8 |
| 3.8 | Tests: SSE connection, event delivery, replay from Last-Event-ID, channel broadcast | `tests/test_sse.py` (new) | +80 |

**Total: ~241 LOC**

---

## WP-4: Binding Tier Routing

### Problem
Current dispatch uses "first evaluator wins" selector semantics. With 2 agents this works. With 3+ agents and multiple projects, there's no way to express routing priority — an explicit claim should override a capability match, which should override a project default.

### Requirements

**REQ-F-TIER-001 — Four-tier binding resolution**
Message routing evaluates bindings in priority order:
1. **Tier 1 — Active claim**: Agent has an active claim on this feature+edge (hard binding)
2. **Tier 2 — Capability match**: Agent's `workflow_bindings` includes the requested workflow
3. **Tier 3 — Project default**: Agent is configured as default for this project
4. **Tier 4 — Channel default**: Fallback agent for unmatched intents
Acceptance: Tier 1 match takes precedence over Tier 2; Tier 2 over Tier 3; etc. Resolution is deterministic.

**REQ-F-TIER-002 — Project-agent default mapping**
Configuration supports mapping projects to default agents. When no claim or capability match exists, the project's default agent handles the intent.
Acceptance: `agents.yml` supports `default_projects: [genesis_sdlc, c4h]` per agent.

**REQ-F-TIER-003 — Tier resolution audit trail**
Each dispatch logs which tier resolved the routing. This surfaces in the message envelope as `resolved_via: tier_1|tier_2|tier_3|tier_4`.
Acceptance: Envelope carries `resolved_via` field; observable in channel output and SSE stream.

### Design

New module: `dispatch/binding_resolver.py`

```python
@dataclass
class ResolvedBinding:
    agent: AgentConfig
    binding: WorkflowBinding
    tier: int  # 1-4
    reason: str  # human-readable: "active claim on FT-AUTH-001:design→code"

def resolve_binding(
    intent_text: str,
    agents: list[AgentConfig],
    bindings: dict[str, WorkflowBinding],
    claims: ClaimRegistry,
    workspace: str,
    params: dict,
) -> ResolvedBinding | None:
    ...
```

Replaces the current `route_intent()` in `dispatch/intent.py`. The existing intent pattern matching (regex extraction of project/feature) remains — it feeds into the resolver as parsed params.

Extend `agents.yml` schema:
```yaml
agents:
  - id: claude
    display_name: Claude (primary)
    write_territory: .ai-workspace/comments/claude/
    workflow_bindings: [gen-start, gen-iterate]
    default_projects: [genesis_sdlc, genesis_chat]
    role: primary
```

**Source reference**: OpenClaw `src/routing/resolve-route.ts` binding tier concept. Our adaptation is ~100 LOC — four tiers vs OpenClaw's seven, no guild/team/peer dimensions.

### Tasks

| # | Task | File | Est LOC |
|---|------|------|---------|
| 4.1 | Create `dispatch/binding_resolver.py` with `ResolvedBinding` and `resolve_binding()` | `dispatch/binding_resolver.py` (new) | +80 |
| 4.2 | Add `default_projects` field to `AgentConfig` | `registry/agents.py` | +3 |
| 4.3 | Update `AgentRegistry.__init__()` to parse `default_projects` (optional, defaults to []) | `registry/agents.py` | +2 |
| 4.4 | Update `Dispatcher.dispatch()` F_P path to use `resolve_binding()` instead of `route_intent()` | `dispatch/dispatcher.py` | +15 |
| 4.5 | Add `resolved_via` to `MessageEnvelope` (depends on WP-1) | `adapter/base.py` | +2 |
| 4.6 | Populate `resolved_via` in dispatcher envelope creation | `dispatch/dispatcher.py` | +5 |
| 4.7 | Update `agents.yml` with `default_projects` for existing agents | `agents.yml` | +4 |
| 4.8 | Tests: tier 1 precedence over tier 2, tier 2 over tier 3, fallback to tier 4, audit trail | `tests/test_binding_resolver.py` (new) | +70 |

**Total: ~181 LOC**

---

## WP-5: Adapter Registry

### Problem
Adding a new adapter (Matrix, Slack) requires code changes in `channel.py` and `__main__.py`. The adapter selection is hardcoded (`if args.adapter == "irc": ...`). V2 needs pluggable adapters without touching core.

### Requirements

**REQ-F-AREG-001 — Config-driven adapter resolution**
Adapters are registered in `adapters.yml` with module path, class name, and default config. The channel loop resolves the adapter by name from this registry.
Acceptance: Adding a new adapter requires only a new Python module + a YAML entry. No changes to `channel.py` or `__main__.py`.

**REQ-F-AREG-002 — Adapter discovery at startup**
At startup, the registry validates that all configured adapter modules are importable. Missing modules produce a clear error with install instructions.
Acceptance: `python -m genesis_chat --adapter matrix` with missing module prints "Adapter 'matrix' requires package X. Install with: pip install X".

**REQ-F-AREG-003 — Adapter config passthrough**
CLI flags for adapter-specific config (e.g., `--irc-host`, `--irc-port`) are passed through to the adapter constructor. The registry maps flag names to constructor kwargs.
Acceptance: `--adapter irc --irc-host example.com` resolves to `IRCAdapter(IRCConfig(host="example.com"))`.

### Design

New module: `adapter/registry.py`

```python
class AdapterRegistry:
    def __init__(self, registry_path: Path):
        ...

    def resolve(self, name: str, **kwargs) -> MessageAdapter:
        """Import module, instantiate class with kwargs, return adapter."""

    def validate_all(self) -> list[str]:
        """Return list of adapter names with import errors."""
```

Config file `adapters.yml`:
```yaml
adapters:
  echo:
    module: genesis_chat.adapter.echo
    class: EchoAdapter
    config_class: null  # no config needed
  irc:
    module: genesis_chat.adapter.irc
    class: IRCAdapter
    config_class: IRCConfig
    cli_prefix: irc  # maps --irc-* flags to IRCConfig fields
    requires: []  # no extra packages (stdlib socket)
  matrix:
    module: genesis_chat.adapter.matrix
    class: MatrixAdapter
    config_class: MatrixConfig
    cli_prefix: matrix
    requires: [matrix-nio]
```

**Source reference**: OpenClaw `src/channels/plugins/load.ts` registry pattern (~150 LOC). Our adaptation is ~90 LOC Python — importlib-based, no jiti/bundler complexity.

### Tasks

| # | Task | File | Est LOC |
|---|------|------|---------|
| 5.1 | Create `adapter/registry.py` with `AdapterRegistry` | `adapter/registry.py` (new) | +70 |
| 5.2 | Create `adapters.yml` with echo and irc entries | `adapters.yml` (new) | +20 |
| 5.3 | Update `__main__.py` to use `AdapterRegistry.resolve()` instead of hardcoded if/else | `__main__.py` | +15 (net ~0, replacing existing) |
| 5.4 | Update `channel.py` `run()` to accept adapter instance instead of constructing internally | `channel.py` | +5 |
| 5.5 | Add `validate_all()` call at startup with clear error messages | `__main__.py` | +8 |
| 5.6 | Tests: registry resolution, missing module error, config passthrough, validation | `tests/test_adapter_registry.py` (new) | +55 |

**Total: ~173 LOC**

---

## WP-6: Live Patch Queuing (Genesis-Manager Integration)

### Problem
When genesis-manager consumes the SSE stream (WP-3) during `gen start --auto`, rapid events can cause React to re-render on every event. The UI needs debounced state updates.

### Requirements

**REQ-F-PATCH-001 — Debounced state updates from SSE**
Genesis-manager's Zustand store accumulates SSE events and flushes state updates after 200ms of silence or when 50 events buffer — whichever comes first.
Acceptance: During a burst of 20 events in 100ms, the store updates once (not 20 times).

**REQ-F-PATCH-002 — Event type filtering**
SSE events are classified by type (project_event, channel_message, convergence_update). The store can subscribe to specific types.
Acceptance: GraphPage subscribes to convergence_update only; EventStreamPage subscribes to all.

### Design

This work is in **genesis-manager**, not genesis_chat. New module: `stores/ssePatchQueue.ts`

```typescript
class SSEPatchQueue {
  private buffer: SSEEvent[] = [];
  private flushTimer: number | null = null;
  private readonly SILENCE_MS = 200;
  private readonly MAX_BUFFER = 50;

  push(event: SSEEvent): void { ... }
  subscribe(types: string[], callback: (events: SSEEvent[]) => void): void { ... }
}
```

**Source reference**: OpenClaw Studio `livePatchQueue.ts` (~100 LOC). Our adaptation is ~80 LOC TypeScript.

### Tasks

| # | Task | File (genesis-manager) | Est LOC |
|---|------|------------------------|---------|
| 6.1 | Create `stores/ssePatchQueue.ts` | `stores/ssePatchQueue.ts` (new) | +80 |
| 6.2 | Add SSE EventSource connection in `stores/workspaceStore.ts` | `stores/workspaceStore.ts` | +30 |
| 6.3 | Wire patch queue into existing store refresh cycle (replace polling when SSE available) | `stores/workspaceStore.ts` | +20 |
| 6.4 | Add event type filter subscriptions per page | `pages/*.tsx` | +15 |
| 6.5 | Tests: debounce behavior, buffer flush, type filtering | `__tests__/ssePatchQueue.test.ts` (new) | +50 |

**Total: ~195 LOC (TypeScript, in genesis-manager)**

---

## Execution Summary

| WP | Name | New Files | Modified Files | Est LOC | Dependencies |
|----|------|-----------|---------------|---------|--------------|
| 1 | Message Envelope | `tests/test_envelope.py` | `adapter/base.py`, `adapter/echo.py`, `adapter/irc.py`, `dispatch/dispatcher.py` | 155 | None |
| 2 | Session Keys | `session/keys.py`, `tests/test_session_keys.py` | `registry/agents.py`, `workflow/bindings.py`, `dispatch/dispatcher.py` | 106 | None |
| 3 | SSE Event Stream | `stream/sse_server.py`, `tests/test_sse.py` | `channel.py`, `__main__.py` | 241 | WP-1 |
| 4 | Binding Tiers | `dispatch/binding_resolver.py`, `tests/test_binding_resolver.py` | `registry/agents.py`, `dispatch/dispatcher.py`, `adapter/base.py`, `agents.yml` | 181 | WP-1, WP-2 |
| 5 | Adapter Registry | `adapter/registry.py`, `adapters.yml`, `tests/test_adapter_registry.py` | `__main__.py`, `channel.py` | 173 | WP-4 |
| 6 | Patch Queuing | `stores/ssePatchQueue.ts`, `__tests__/ssePatchQueue.test.ts` | `stores/workspaceStore.ts`, `pages/*.tsx` | 195 | WP-3 |
| | **Total** | **10 new files** | **~14 modified files** | **~1,051** | |

### Suggested Build Sequence

**Phase A** (parallel, no dependencies):
- WP-1: Message Envelope
- WP-2: Session Keys

**Phase B** (after Phase A):
- WP-3: SSE Event Stream (needs WP-1 envelope format)
- WP-4: Binding Tiers (needs WP-1 envelope, WP-2 session keys)

**Phase C** (after Phase B):
- WP-5: Adapter Registry (needs WP-4 binding resolution)

**Phase D** (after WP-3, can parallel with WP-4/5):
- WP-6: Patch Queuing in genesis-manager (needs WP-3 SSE endpoint)

### What This Does NOT Include

- New adapter implementations (Matrix, Slack) — WP-5 makes them pluggable, but actual adapters are separate work
- Hard-lock claim semantics — V2 keeps soft claims; hard locks are V3 scope
- Vector cache / embedding-based context — out of scope per INTENT.md
- Changes to abiogenesis engine or genesis_sdlc — all work is in genesis_chat and genesis-manager

## Recommended Action

1. Create feature vectors for WP-1 and WP-2 (Phase A) — they can start immediately
2. Review whether `session_key` env var propagation (REQ-F-SESS-003) requires abiogenesis engine changes or if it's passthrough-only
3. Decide SSE port default (8086 proposed) and whether it should be mandatory or opt-in
4. Confirm genesis-manager is ready to consume SSE before starting WP-6
