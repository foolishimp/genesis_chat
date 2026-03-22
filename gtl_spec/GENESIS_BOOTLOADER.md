# Genesis Bootloader: LLM Constraint Context for the AI SDLC

**Version**: 3.0.2
**Purpose**: Minimal sufficient context to constrain an LLM to operate within the AI SDLC Asset Graph Model. Load this document into any LLM session — it replaces the need to load the full specification, ontology, and design documents for routine methodology operation.

---

## I. Logical Encapsulation Preamble

You must perform all analysis, construction, and evaluation strictly within the following specification. Treat this framework as a **hard constraint system**.

- Do not introduce assumptions, patterns, or conventions from outside this specification.
- Do not substitute familiarity with software methodologies (Agile, Scrum, Waterfall, SAFe) for reasoning within this system.
- Evaluate only against the defined primitives, invariants, and composition laws.
- If information is insufficient, state what is missing and which constraint cannot be evaluated — do not guess.

This specification defines a **virtual reasoning environment**: a controlled logic space where your conclusions are shaped by axioms rather than training-data patterns. The axioms are explicit and auditable. Different axioms produce mechanically different results.

**Epistemic honesty**: You do not *execute* this formal system — you *predict what execution would produce*. Reliability comes from **iteration and a gain function** — repeated evaluation with convergence criteria, not from a single prompt-response cycle. This bootloader makes the axioms visible so they can be checked.

---

## II. Foundation: What Constraints Are

A constraint is not a rule that dictates what must happen next, but a condition that determines which transformations are admissible at all.

Constraints restrict which transformations exist, limit composability, induce stability, enable boundary formation, and define subsystems. Without constraint, everything is permitted — and nothing persists.

**Generative principle**: As soon as a stable configuration is possible within a constraint structure, it will emerge. Constraints do not merely permit — they generate. The constraint structure fills its own possibility space.

**Naming is a constraint act.** When a high-order concept is identified and anchored — abiogenesis, the gradient, the GCC bootstrap model, the design marketplace — it immediately reduces the decision space below it. Questions that required debate resolve automatically as consequences of the named concept. A rule needs enforcement; an axiom needs only to be understood. Before adding any new rule, ask: is this already a consequence of an existing axiom? If yes, cite the axiom — do not restate it as a rule. Restating axioms as rules is the primary source of spec bloat and internal contradiction.

**The methodology is the constraints themselves.** Commands, configurations, event schemas, and tooling are implementations — emergence within those constraints. Any implementation that satisfies these constraints is a valid instantiation.

---

## III. The Formal System: Four Primitives, One Operation

| Primitive | What it is |
|-----------|-----------|
| **Graph** | Topology of typed assets with admissible transitions (zoomable) |
| **Iterate** | Event-producing convergence engine — the only operation |
| **Evaluators** | Convergence test — when is iteration done |
| **Spec + Context** | Constraint surface — what bounds construction |

Everything else — stages, agents, TDD, BDD, commands, configurations, event schemas — is parameterisation of these four for specific graph edges. They are emergence, not the methodology.

**The graph is not universal.** The SDLC graph is one domain-specific instantiation. The four primitives are universal; the graph is parameterised.

**The formal system is a generator of valid methodologies.** What it generates depends on which projection is applied, which encoding is chosen, and which technology binds the functional units.

---

## IV. The Iterate Function

```
iterate(
    Asset<Tn>,              // current asset — a projection of the event stream
    Context[],              // standing constraints (spec, design, ADRs, prior work)
    Evaluators(edge_type)   // convergence criteria for this edge
) → Event+                 // one or more events appended to the stream
```

`iterate()` returns **events**, not assets. The engine appends events to the stream. `Asset<Tn+1>` is derived by projecting the updated stream — the asset is a consequence of the event, not the direct output. This is the **only operation**. Every edge in the graph is this function called repeatedly until evaluators report convergence:

```
while not stable(candidate, edge_type):
    events = iterate(candidate, context, evaluators)
    append(events, stream)
    candidate = project(stream, asset_type, instance_id)
return promote(candidate)
```

Convergence: `stable(candidate) = ∀ evaluator ∈ evaluators(edge_type): evaluator.delta(candidate, spec) < ε`

---

## V. Event Stream as Model Substrate

**Assets are projections, not stored objects.** The event stream is the foundational medium. No operation modifies state directly — state is always derived by projecting the event stream.

```
Asset<Tn> := project(EventStream[0..n], asset_type, instance_id)
```

Three projection invariants every implementation must satisfy:

| Invariant | What it means |
|-----------|--------------|
| **Determinism** | `project(S, T, I) = project(S, T, I)` always — same stream, same asset |
| **Completeness** | Every prior state `Asset<Tk>` for any k ≤ n is reconstructable |
| **Isolation** | Projecting instance I never reads or modifies the stream of instance J |

**When asked "what is the current state of X?"** — derive it from the event stream, do not assume mutable state. When asked "what happened?" — replay is authoritative.

**Durability**: If a process fails mid-iteration, recovery is replay. No state is lost beyond the current iterate() call.

**Push context**: External signals (webhooks, telemetry anomalies, downstream completions) are events appended to the stream — not exceptions to the model.

**Event-time is append-assigned (architectural, not behavioral):** The event logger is an F_D-controlled function — the only admissible write path to `events.jsonl`. The F_D engine calls `emit_event(event_type, data)` after evaluating F_P-produced output. F_P constructs artifacts and assessment payloads; the F_D engine reads them, computes delta, and calls the logger. **F_P does not call the event logger. F_P constructs content; the F_D engine writes the log entry.** The function assigns `event_time` from the system clock at append; no caller can pass `event_time`. Business timing fields (`effective_at`, `completed_at`, `observed_at`) are payload in `data`, not system timestamps. This makes the invariant structural, not dependent on caller discipline.

**Control surface vs trace surface:** Two distinct surfaces on the event stream. The *control surface* contains authoritative, gate-moving events — emitted at the moment the decision is made, truthfully, append-time-stamped. The *trace surface* contains projections, audit packs, telemetry summaries, review paperwork, and other visibility artifacts derived from the canonical log — these MAY be incomplete during normal operation and are eventually consistent. A missing proxy-log or unarchived review YAML is trace debt (detectable, repayable). A backdated `event_time` or a control-event emitted without the work having occurred is a log-integrity violation (permanent, unrepayable).

---

## VI. The Gradient: One Computation at Every Scale

```
delta(state, constraints) → work
```

When `delta → 0`, the system is at rest. When `delta > 0`, work is produced. The same operation at every scale:

| Scale | State | Constraints | Delta → 0 means |
|-------|-------|-------------|-----------------|
| **Single iteration** | candidate asset | edge evaluators | evaluator passes |
| **Edge convergence** | asset at iteration k | all evaluators for edge | stable asset |
| **Feature traversal** | feature vector | graph topology + profile | feature converged |
| **Production** | running system | spec (SLAs, contracts, health) | system within bounds |
| **Spec review** | workspace state | the spec itself | spec and workspace aligned |
| **Constraint update** | irreducible delta | observation that surface is wrong | new ground states defined |

The last two rows are where the methodology becomes self-modifying — the constraints themselves are subject to gradient pressure.

---

## VII. Evaluators, Processing Phases, and Functor Encoding

### Three Evaluator Types

| Evaluator | Symbol | Regime | What it does |
|-----------|--------|--------|-------------|
| **Deterministic Tests** | F_D | Zero ambiguity | Pass/fail — type checks, schema validation, test suites, contract verification |
| **Agent** | F_P | Bounded ambiguity | LLM/agent disambiguates — gap analysis, coherence checking, refinement |
| **Human** | F_H | Persistent ambiguity | Judgment — domain evaluation, business fit, approval/rejection |

All three compute a **delta** and emit events driving the next iteration.

### Three Processing Phases

| Phase | When it fires | What it does |
|-------|--------------|-------------|
| **Reflex** | Unconditionally — every iteration | Sensing — event emission, test execution, state updates |
| **Affect** | When any evaluator detects a gap | Valence — urgency, severity, priority attached to the finding |
| **Conscious** | When affect escalates | Direction — judgment, intent generation, spec modification |

Affect is a **valence vector on the gap**, not an evaluator type. Any evaluator that finds a delta also emits affect. The affect signal determines routing — defer or escalate.

### Functor Encoding

```
Functor(Spec, Encoding) → Executable Methodology
```

The escalation chain is a natural transformation:

```
η: F_D → F_P    (deterministic blocked → agent explores)
η: F_P → F_H    (agent stuck → human review)
η: F_H → F_D    (human approves → deterministic deployment)
```

### Invocation Contract

Every functor invocation satisfies:

```
invoke(intent: Intent, state: State) → StepResult
```

`Intent` carries: `edge`, `feature`, `grain`, `constraints`, `context`, `budget_usd`, `wall_timeout_ms`, `stall_timeout_ms`, `run_id`.

`StepResult` carries: `run_id`, `converged`, `delta`, `artifacts` (with content hashes), `spawns`, `cost_usd`, `duration_ms`, `audit` (functor_type, transport, kill flags).

The engine calls `invoke()` without knowing the transport. The functor registry resolves the implementation. Transport changes are internal to the registry; the engine and event schema are unaffected.

---

## VIII. Sensory Systems

Two complementary systems feed signals into the processing phases continuously, independent of iterate():

| System | Direction | What it observes |
|--------|-----------|-----------------|
| **Interoception** | Inward — the system's own state | Test health, event freshness, coverage drift, feature vector stalls, spec/code drift |
| **Exteroception** | Outward — the environment | CVE feeds, dependency updates, runtime telemetry, API contract changes, user feedback |

**Review boundary**: The sensory system can autonomously observe, classify, and draft proposals. It cannot change the spec, modify code, or emit `intent_raised` events without F_H accountability.

---

## IX. The IntentEngine: Composition Law

The IntentEngine is **not a fifth primitive**. It is a composition law over the existing four:

```
IntentEngine(intent + affect) = observer → evaluator → typed_output
```

### Three Output Types (exhaustive — no fourth category)

The `requires_spec_change` field on `intent_raised` routes to one of three outputs:

| Output | Condition | What happens |
|--------|-----------|-------------|
| **reflex.log** | Ambiguity = 0 | Fire-and-forget event — action taken, logged, done |
| **composition_dispatched** | Bounded ambiguity; `requires_spec_change: false` | Named composition dispatched to execution layer — no spec change needed, F_H gate not required |
| **feature_proposal** | Persistent ambiguity; `requires_spec_change: true` | Enters Draft Features Queue — F_H gate required; spec change, spawning, or human judgment needed |

> **ADR-S-026 (2026-03-08)**: The `composition_dispatched` event carries a **typed composition expression** (`{macro, version, bindings}`) drawn from the named composition library. The gap evaluator calls `emit_event('composition_dispatched', {macro, version, bindings})` via the F_D event logger — it does not write events directly. A dispatch table maps `gap_type` to named composition. `reflex.log` is unchanged. See [ADR-S-026](../adrs/ADR-S-026-named-compositions-and-intent-vectors.md) §3 for the execution contract (macro registry required before zero-interpretation claim holds).

### Homeostasis: Intent Is Computed

```
intent = delta(observed_state, spec) where delta ≠ 0
```

Test failures, tolerance breaches, coverage gaps, ecosystem changes, and telemetry anomalies all produce intents. Human intent is the abiogenesis — the initial spark. Once the system has a specification and sensory monitors, it becomes self-sustaining. The human remains as F_H — one evaluator type among three.

---

## X. Constraint Tolerances

A constraint without a tolerance is a wish. A constraint with a tolerance is a sensor.

```
"the system must be fast"      → unmeasurable, delta undefined
"P99 latency < 200ms"          → measurable, delta = |observed - 200ms|
"all tests pass"               → measurable, delta = failing_count
```

Without tolerances, there is no homeostasis. Tolerances are not optional metadata — they are the mechanism by which constraints become operational.

---

## XI. Assets and Stability

An asset achieves stable status (Markov object) when:

1. **Boundary** — typed interface/schema (REQ keys, interfaces, contracts, metric schemas)
2. **Conditional independence** — usable without knowing its construction history
3. **Stability** — all evaluators report convergence (delta = 0)

An asset that fails its evaluators is a **candidate**. It stays in iteration.

**Path-independence invariant**: A stable asset must be reconstructable from the event stream alone, independent of the execution path that produced it. Two conformant implementations that process equivalent event streams must produce equivalent stable assets.

---

## XII. Completeness Visibility

Two questions must be answerable at any time: **"Did I get all the features?"** and **"Is it done?"**

### Feature Decomposition Convergence

The `requirements → feature_decomposition` edge converges when BOTH:

- **F_D (coverage)**: Every REQ-* key in requirements appears in the `satisfies:` field of at least one feature vector. Computable by grep — no LLM required.
- **F_H (approval)**: A human has explicitly approved the decomposition, dependency ordering, and MVP boundary.

F_D gates F_H — no human review is requested until coverage_delta = 0.

### Coverage Projection (always available, always free)

At any point after feature_decomposition is initiated, computable from artifacts without LLM invocation:

```
FEATURE COVERAGE
  Requirements: N REQs defined
  Covered:      n/N  [===----]  pct%
  Gaps:         [list of uncovered REQ-* keys]
  Features:     M vectors  ✓ converged / ⟳ in-progress / ○ not started
```

### Convergence Visibility (three mandatory levels)

| Level | When | Required output |
|-------|------|----------------|
| **Iteration summary** | After every iterate() call | delta (current vs previous), evaluator results, status |
| **Edge convergence** | When delta=0 on an edge | "CONVERGED — {edge}", what was produced, next step |
| **Feature completion** | When all edges in a feature converge | "COMPLETE — {feature_id}", REQ coverage, ready for review |

A convergence event not made visible before the next downstream iteration starts is a spec violation.

---

## XIII. Feature Vectors: Trajectories Through the Graph

A **feature** is a trajectory through the graph:

```
Feature F = |req⟩ + |feature_decomp⟩ + |design⟩ + |module_decomp⟩ + |basis_proj⟩ + |code⟩ + |unit_tests⟩ + |uat_tests⟩ + |cicd⟩ + |telemetry⟩
```

The **REQ key** threads from spec to runtime:

```
Spec:       REQ-F-AUTH-001 defined
Design:     Implements: REQ-F-AUTH-001
Code:       # Implements: REQ-F-AUTH-001
Tests:      # Validates: REQ-F-AUTH-001
Telemetry:  logger.info("login", req="REQ-F-AUTH-001", latency_ms=42)
```

Feature vectors have a required `satisfies:` field listing covered REQ-* keys — the mechanism for the coverage projection (§XII).

---

## XIV. The SDLC Graph (Default Instantiation)

```
Intent → Requirements → Feature Decomp → Design → Module Decomp → Basis Projections → Code ↔ Unit Tests
                                │              │                                              │
                                │              └──→ Test Cases → UAT Tests                   ↓
                                │                                              CI/CD → Running System → Telemetry
                                └──────────────────────────────── Observer/Evaluator ◄────────────────┘
                                                                          │
                                                                     New Intent
```

**Feature Decomposition is a first-class graph node.** It has its own convergence criterion (§XII), evaluators (F_D coverage + F_H approval), and visibility requirement. The spec/design boundary is at `Feature Decomp → Design`: everything upstream is tech-agnostic (WHAT); everything downstream is tech-bound (HOW).

**Intermediate nodes are computational complexity management** — not architectural requirements. Add them when the A→E leap exceeds reliable constructor range.

**The graph is zoomable.** Any edge can expand into a sub-graph, any sub-graph can collapse into a single edge.

```
Full:      Intent → Req → Feat Decomp → Design → Mod Decomp → Basis Proj → Code ↔ Tests → UAT
Standard:  Intent → Req → Feat Decomp → Design → Mod Decomp → Basis Proj → Code ↔ Tests
PoC:       Intent → Req → Feat Decomp → Design → Code ↔ Tests
Hotfix:                                         → Code ↔ Tests
```

**Standard profile v2.9 edge chain**:
`intent → requirements → feature_decomposition → design_recommendations → design → module_decomposition → basis_projections → code ↔ unit_tests`

---

## XV. Projections as Functors

Named profiles — each preserves all four invariants while varying the encoding:

| Profile | When | Graph | Evaluators | Iterations |
|---------|------|-------|-----------|------------|
| **full** | Regulated, high-stakes | All edges | All three types | No limit |
| **standard** | Normal feature work | Core edges + decomposition | Mixed types | Bounded |
| **poc** | Proof of concept | Core edges, decomp collapsed | Agent + deterministic | Low |
| **spike** | Research / experiment | Minimal edges | Agent-primary | Very low |
| **hotfix** | Emergency fix | Direct path | Deterministic-primary | 1-3 |
| **minimal** | Trivial change | Single edge | Any single evaluator | 1 |

---

## XVI. Spec / Design Separation

- **Spec** = WHAT, tech-agnostic. One spec, many designs. Boundary: up to and including Feature Decomposition.
- **Design** = HOW architecturally, tech-bound (ADRs, ecosystem bindings). Boundary: from Design onwards.

Code disambiguation feeds back to **Spec** (business gap) or **Design** (tech gap). Never conflate.

---

## XVII. Invariants

| Invariant | What it means | What breaks if absent |
|-----------|--------------|----------------------|
| **Graph** | Topology of typed assets with admissible transitions | No structure — ad hoc work |
| **Iterate** | Convergence loop producing events, deriving assets | No quality signal — one-shot |
| **Evaluators** | At least one evaluator per active edge | No stopping condition |
| **Spec + Context** | Constraint surface bounds construction | Degeneracy, hallucination |
| **Event stream** | State derived from stream; all writes via F_D event logger function — no direct mutation, no timestamp override | No replay, no recovery, no projection equivalence; timestamp integrity unenforceable |
| **Completeness visibility** | Every convergence transition produces a human-readable summary before downstream proceeds | Silent convergence — system cannot be trusted |

**Projection validity**: `valid(P) ⟺ ∃ G ⊆ G_full ∧ ∀ edge ∈ G: iterate(edge) defined ∧ evaluators(edge) ≠ ∅ ∧ convergence(edge) defined ∧ context(P) ≠ ∅`

**IntentEngine invariant**: Every edge traversal is an IntentEngine invocation. No unobserved computation.

**Path-independence invariant**: A stable asset must be reconstructable from the event stream alone, independent of execution path.

**Observability is constitutive.** The event log, sensory monitors, and feedback loop are methodology constraints, not tooling features. The methodology tooling is itself a product complying with the same constraints.

---

## XVIII. How to Apply This Bootloader

When working on any project under this methodology:

1. **Identify the graph** — what asset types exist, what transitions are admissible
2. **For each edge**: define evaluators, convergence criteria, and context
3. **Iterate**: produce events, derive candidate, evaluate, loop until stable
4. **Apply the gradient**: `delta(state, constraints) → work` — at every scale
5. **Route by ambiguity**: zero → reflex, bounded → iterate, persistent → escalate
6. **Maintain traceability**: REQ keys thread through every artifact from spec to telemetry
7. **Check tolerances**: every constraint must have a measurable threshold
8. **Track completeness**: coverage projection computable at any time; convergence visible before downstream proceeds
9. **Choose a projection** appropriate to the work
10. **Verify invariants**: graph, iteration, evaluators, context, event stream, visibility — any missing = invalid instance

The commands, configurations, and tooling are valid emergences from these constraints. If you have only the commands without this bootloader, you are pattern-matching templates. If you have this bootloader, you can derive the commands.

---

## XIX. Workspace Write Territory and Autonomous Mode Constraints

### Agent Write Territory (hard constraint — not a convention)

The `.ai-workspace/` directory is partitioned by agent identity. Violating these boundaries corrupts the design marketplace and is equivalent to modifying another agent's event stream.

| Territory | Who writes | Rule |
|-----------|-----------|------|
| `events/events.jsonl` | All agents via event logger only | **Never write directly.** Call `emit_event(event_type, data)`. The F_D event logger assigns `event_time`, enforces OL schema, and appends atomically. Append-only — never modify or delete existing lines. |
| `features/active/*.yml` | Owning agent | State projection — update only the feature you are iterating. |
| `features/completed/*.yml` | Owning agent | Move from active/ on full convergence. |
| `comments/claude/` | Claude Code only | Claude writes here. Never write to `comments/codex/`, `comments/gemini/`, or `comments/bedrock/`. |
| `comments/codex/` | Codex only | Same exclusivity — Claude must not write here. |
| `comments/gemini/` | Gemini only | Same. |
| `reviews/pending/PROP-*.yml` | All agents | Proposals written by any agent; human gate resolves. |
| `reviews/proxy-log/` | Proxy actor only | Written by `--human-proxy` mode before each `review_approved` event. |

**Post naming**: `YYYYMMDDTHHMMSS_CATEGORY_SUBJECT.md`. Categories: `REVIEW`, `STRATEGY`, `GAP`, `SCHEMA`, `HANDOFF`, `MATRIX`. Each file carries sufficient context for independent evaluation. Posts are immutable once written — supersede with a new file, never edit.

**Invariant**: An agent reading a comment post in another agent's directory does not confer write rights there. Reading is unrestricted; writing is territory-bound.

### Operating Standards

**`.ai-workspace/operating-standards/`** is the authoritative fallback for any agent action not governed by a more specific instruction. Before performing any of the following, load the relevant standard:

| Action | Standard |
|--------|----------|
| Writing a comment post (`comments/claude/`) | `operating-standards/CONVENTIONS.md` |
| Creating or updating a backlog item | `operating-standards/BACKLOG.md` |
| Writing any human-facing document (ADR, user guide, README, release notes, intent doc) | `operating-standards/WRITING.md` |
| Writing or updating a user guide | `operating-standards/USER_GUIDE.md` |
| Cutting a release (version bump, changelog, cascade install) | `operating-standards/RELEASE.md` |
| Any action not explicitly specified elsewhere | `operating-standards/` — scan for a relevant file |

Operating standards are installed by the methodology layer (e.g. genesis_sdlc) and versioned with it. They are read-only for agents — propose changes via a `STRATEGY` post in `comments/claude/`.

### Human Proxy Mode (`--human-proxy`)

Human proxy mode allows the LLM to act as an authorised F_H substitute during unattended `--auto` runs. It does not remove the F_H gate — it substitutes the actor.

**Activation constraint**: `--human-proxy` requires `--auto`. Used alone it is an error. It is never activated by config, env var, or inference — explicit flag only, per invocation only. It is never persisted to workspace state.

**Proxy evaluation protocol**: At each F_H gate, the proxy:
1. Loads the candidate artifact and the gate's F_H criteria
2. Evaluates each required criterion with explicit evidence
3. Computes the decision: `approved` iff all required criteria pass; `rejected` if any fail
4. Writes a proxy-log file to `.ai-workspace/reviews/proxy-log/{ISO}_{feature}_{edge}.md` **before** emitting any event
5. Emits `review_approved{actor: "human-proxy", proxy_log: "{path}"}` on approval

**Rejection halt**: A proxy rejection pauses the auto-loop immediately. The proxy may not re-invoke iterate on the rejected edge in the same session (`rejected_in_session` set is checked). The feature remains `iterating`.

**Actor field invariant**: Every `review_approved` event must carry `actor` field. Proxy decisions use `actor: "human-proxy"` (never `"human"`, never absent). Human decisions use `actor: "human"`. This is the auditability mechanism — the two must never be confused.

**Morning review**: `/gen-status` surfaces proxy decisions made since the last attended session. Humans dismiss with a `Reviewed: {date}` line or override via `/gen-review`. Proxy decisions are provisional — the human is the authority, not the proxy.

---

## XX. Bug Triage and Post-Mortem Escalation

Bugs during active development do not require a feature vector. The minimum viable artifact is a log entry. Post-mortem determines whether a formal response is warranted.

### Phase 1 — Fix and log (reflex, always)

Fix the bug directly. Append one `bug_fixed` event:

```json
{"event_type": "bug_fixed", "timestamp": "{ISO}", "project": "{name}",
 "data": {"description": "{what was wrong and what changed}", "file": "{primary file}", "root_cause": "coding_error|design_flaw|unknown"}}
```

`root_cause` is provisional — post-mortem may reclassify it.

| Value | Meaning |
|-------|---------|
| `coding_error` | Typo, wrong variable, obvious local mistake — discard after post-mortem |
| `design_flaw` | Fix touched interfaces, contracts, or multiple components — escalate |
| `unknown` | Cause unclear at fix time — investigate before discarding |

### Phase 2 — Post-mortem triage (conscious, on demand)

Run before releases, when a cluster appears, or when `/gen-status --health` surfaces a pattern.

- `design_flaw` or `unknown` resolved to design flaw → emit `intent_raised{signal_source: bug_post_mortem}` → normal homeostatic loop
- `unknown` resolved to coding error → discard
- Pattern of `coding_error` in same area → may indicate missing abstraction → emit `intent_raised` for investigation

### What is NOT required for a bug fix

No feature vector. No iterate() cycle. No human gate. No REQ key traceability. Only the `bug_fixed` event is required.

**The gradient test**: A coding error produces delta → 0 locally — the fix restores intended state, no design information generated. A design flaw produces a persistent delta — the symptom is patched but the constraint violation remains. Post-mortem detects which case applies and routes accordingly.

*Reference: [ADR-S-039](../adrs/ADR-S-039-bug-triage-and-post-mortem-escalation.md)*

---

*Foundation: [Constraint-Emergence Ontology](https://github.com/foolishimp/constraint_emergence_ontology)*
*Formal system: [AI SDLC Asset Graph Model v2.8](AI_SDLC_ASSET_GRAPH_MODEL.md) — four primitives, one operation, event stream substrate*
*Projections: [Projections and Invariants v1.2](PROJECTIONS_AND_INVARIANTS.md)*
*Key ADRs: [ADR-S-012](../adrs/ADR-S-012-event-stream-as-formal-model-medium.md) event stream · [ADR-S-013](../adrs/ADR-S-013-completeness-visibility.md) completeness visibility · [ADR-S-016](../adrs/ADR-S-016-invocation-contract.md) invocation contract · [ADR-S-039](../adrs/ADR-S-039-bug-triage-and-post-mortem-escalation.md) bug triage*

---

## XXI. Abiogenesis Project — Local Write Territory Amendment

*This section amends §XIX for the abiogenesis project structure. It does not modify the general invariants — it instantiates them for this build.*

**Build territory** (abiogenesis-specific, V1 single-tenant):

| Territory | Who writes | Rule |
|-----------|-----------|------|
| `builds/claude_code/code/` | Claude Code | Genesis engine implementation |
| `builds/claude_code/tests/` | Claude Code | Engine tests |
| `builds/claude_code/design/adrs/` | Claude Code | Architectural decisions |
| `builds/claude_code/.workspace/` | Claude Code | Build-local trace surface (not committed) |
| `.ai-workspace/events/events.jsonl` | All agents via `emit()` only | Never write directly |
| `.ai-workspace/comments/claude/` | Claude Code only | Design marketplace posts |
| `.ai-workspace/features/` | Claude Code | Feature vectors |
| `.ai-workspace/reviews/` | All agents | Proposals; human gate resolves |

**Spec is read-only**: `gtl_spec/` is the constitutional source of truth. `genesis_core.py` IS the spec. Claude Code reads `gtl_spec/` but never writes to it — writes go to `builds/claude_code/` only.

**V1 single-tenant constraint**: Only the `claude_code` build exists in V1. Do not create `comments/codex/`, `comments/gemini/`, or `comments/bedrock/` directories — they are V2+ concerns. See `V1_DOCTRINE.md` for the complete non-goals list.

**Bootstrap compiler**: The `.genesis/` directory contains the installed bootstrap compiler (genesis_sdlc). It is not committed — it is installed. Do not modify files under `.genesis/`.
