# GTL Bootloader: Universal Constraint Context for the Graph-Type-Language Formal System

**Version**: 1.0.0
**Purpose**: Minimal sufficient context to constrain an LLM to operate within the GTL formal system. This document defines the universal axioms — four primitives, one operation, event stream substrate. It is domain-agnostic: any GTL Package (SDLC, data pipeline, infrastructure, chatbot) operates within these constraints. Domain-specific instantiations extend this bootloader, they do not replace it.

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

These primitives are realised as GTL types in `gtl/core.py`:

| GTL Type | Primitive | What it represents |
|----------|-----------|-------------------|
| **Package** | Graph | A complete graph definition — assets, edges, operators, rules, contexts, requirements |
| **Asset** | Graph | A typed node with markov stability conditions |
| **Edge** | Graph | An admissible transition between assets |
| **Job** | Iterate | An Edge bound to its Evaluator list — the unit of iteration |
| **Worker** | Iterate | An execution agent that can process Jobs |
| **Evaluator** | Evaluators | A convergence test — F_D, F_P, or F_H |
| **Operator** | Iterate | A named execution capability (agent, human gate, CLI command) |
| **Rule** | Evaluators | A consensus/approval policy for an edge |
| **Context** | Spec + Context | A constraint document loaded into the agent prompt |

Everything else — stages, agents, TDD, BDD, commands, configurations, event schemas — is parameterisation of these four for specific graph edges. They are emergence, not the methodology.

**The graph is not universal.** Any particular graph is one domain-specific instantiation. The four primitives are universal; the graph is parameterised.

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

## Universal Invariants

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

*Foundation: [Constraint-Emergence Ontology](https://github.com/foolishimp/constraint_emergence_ontology)*
*Formal system: [AI SDLC Asset Graph Model v2.8](AI_SDLC_ASSET_GRAPH_MODEL.md) — four primitives, one operation, event stream substrate*
*Projections: [Projections and Invariants v1.2](PROJECTIONS_AND_INVARIANTS.md)*
