# CLAUDE.md — genesis_chat

This project uses the **Genesis SDLC code builder** (abiogenesis + genesis_sdlc).

## Quick start

```bash
# Check project state and gaps
PYTHONPATH=.genesis python -m genesis gaps --workspace .

# Start the methodology engine (auto-loop)
/gen-start --auto
```

## Project structure

```
genesis_chat/
├── gtl_spec/packages/project_package.py   ← GTL spec — the construction contract
├── builds/python/
│   ├── src/                      ← implementation source
│   ├── tests/                    ← test suite
│   └── design/adrs/              ← architecture decision records
├── .genesis/                     ← abiogenesis engine (do not edit)
└── .ai-workspace/                ← runtime state (events, features, reviews)
```

## Invocation

```bash
PYTHONPATH=.genesis python -m genesis start --auto --workspace .
PYTHONPATH=.genesis python -m genesis gaps  --workspace .
```

## Slash commands

| Command | What it does |
|---------|-------------|
| `/gen-start [--auto] [--human-proxy]` | State machine — select next edge, iterate, loop |
| `/gen-iterate [--feature F] [--edge E]` | One F_D→F_P→F_H cycle on a specific edge |
| `/gen-gaps [--feature F]` | Convergence state — delta per edge |
| `/gen-review --feature F` | Explicit F_H gate — present candidate for human approval |
| `/gen-status [--feature F]` | Workspace status — events, features, edge state |

---

<!-- GTL_BOOTLOADER_START -->
# GTL Bootloader: Universal Constraint Context

**Version**: 1.0.1
**Domain-agnostic.** Domain packages (SDLC, data pipeline, etc.) extend this — they do not replace it.

---

## Primitives

| Primitive | What it is |
|-----------|-----------|
| **Graph** | Topology of typed assets with admissible transitions |
| **Iterate** | `iterate(job, evaluator_fn, asset) → (Asset, WorkingSurface)` — the only operation |
| **Evaluators** | Convergence tests: F_D (deterministic), F_P (agent), F_H (human) |
| **Spec + Context** | Constraint surface — what bounds construction |

GTL types: Package, Asset, Edge, Job, Worker, Evaluator, Operator, Rule, Context. Everything else is parameterisation.

## Evaluators and Escalation

| Evaluator | Regime | What it does |
|-----------|--------|-------------|
| **F_D** | Zero ambiguity | Pass/fail — tests, schema checks, tag verification |
| **F_P** | Bounded ambiguity | Agent disambiguates — gap analysis, code generation |
| **F_H** | Persistent ambiguity | Human judgment — approval, rejection |

Escalation: F_D → F_P (deterministic blocked). F_P → F_H (agent stuck). F_H → F_D (approved → deploy).

## Event Stream

- Assets are projections: `Asset<Tn> := project(EventStream[0..n], asset_type, instance_id)`
- **Determinism**: `project(S, T, I) = project(S, T, I)` always.
- **emit() is the only write path.** event_time is system-assigned at append.
- **F_P does NOT call the event logger.** F_P produces artifacts; F_D reads them and emits events.
- Recovery is replay. No state lost beyond current iterate() call.

## Gradient

`delta(state, constraints) → work`. When delta = 0, system is at rest. Same computation at every scale — single iteration, edge convergence, feature traversal, production.

## Territories

| Territory | What | Rule |
|-----------|------|------|
| `.genesis/` | ABG engine (installed) | **Never edit directly.** Updated only by ABG installer. |
| `<domain>/release/` | Domain package (installed) | **Never edit directly.** Updated only by domain installer. |
| `specification/` | Authored spec | Editable — intent, requirements, standards. |
| `builds/` | Authored source | Editable — implementation, tests, design. |
| `.ai-workspace/` | Runtime state | Events, features, comments — territory-partitioned by agent. |

## Cascade Chain

Source → installer → installed territory. Order: **ABG → domain package → dependents** (never ABG direct to dependents).

## F_P Dispatch Contract

The manifest JSON at `fp_manifest_path` is the authoritative dispatch contract. It carries structured fields (source/target assets, markov conditions, evaluators, contexts, delta). The prompt field is a human-readable render. CLAUDE.md is transport convenience — the manifest must be sufficient alone.

## Invariants

| Invariant | What breaks if absent |
|-----------|----------------------|
| Graph with typed transitions | No structure — ad hoc work |
| Iterate loop producing events | No quality signal — one-shot |
| At least one evaluator per edge | No stopping condition |
| Spec + Context bounds construction | Degeneracy, hallucination |
| Event stream — append-only, no timestamp override | No replay, no recovery |
| Completeness visibility before downstream | Silent convergence — untrusted |

<!-- GTL_BOOTLOADER_END -->

---

<!-- SDLC_BOOTLOADER_START -->
## Operating protocol

**Always route user intent through commands — never do work directly.**
When the user asks to build, fix, or iterate anything, that is `/gen-start` or
`/gen-iterate`. Direct edits bypass the F_D evaluation chain and nothing is traced.

| Intent | Command |
|--------|---------|
| "go" / "next" / "build X" / "fix Y" | `/gen-start --auto --human-proxy` |
| "one step" / "iterate edge E" | `/gen-iterate --feature F --edge E` |
| "what's broken" / "gaps" / "coverage" | `/gen-gaps` |
| "status" / "where am I" | `/gen-status` |
| "review" / "approve" | `/gen-review --feature F` |


# SDLC Bootloader: AI SDLC Instantiation of the GTL Formal System

**Version**: 1.1.1
**Requires**: GTL Bootloader (universal axioms)

---

## SDLC Graph

```
intent → requirements → feature_decomp → design → module_decomp → code ↔ unit_tests
                                                                        │
                                                                        ↓
                                                 uat_tests ← user_guide ← integration_tests
```

Spec/design boundary at `feature_decomp → design`. Upstream = WHAT (tech-agnostic). Downstream = HOW (tech-bound).

## Feature Vectors

A feature is a trajectory through the graph. REQ keys thread from spec to runtime:

```
Spec: REQ-F-AUTH-001 → Design: Implements: REQ-F-AUTH-001 → Code: # Implements: → Tests: # Validates:
```

Feature vectors have `satisfies:` listing covered REQ keys — the coverage projection mechanism.

## Completeness Visibility

Computable at any point without LLM:
- **Coverage**: every REQ-* in at least one feature's `satisfies:` field
- **Convergence visibility**: iteration summary (after each iterate), edge convergence (delta=0), feature completion (all edges converged)

A convergence event not made visible before downstream proceeds is a spec violation.

## Profiles

| Profile | When | Graph |
|---------|------|-------|
| **standard** | Normal feature work | Core edges + decomposition |
| **poc** | Proof of concept | Core edges, decomp collapsed |
| **hotfix** | Emergency fix | Direct → code ↔ tests |
| **minimal** | Trivial change | Single edge |

## Agent Write Territory (hard constraint)

| Territory | Who writes | Rule |
|-----------|-----------|------|
| `events/events.jsonl` | All agents via `emit_event()` only | **Never write directly.** Append-only. |
| `features/active/*.yml` | Owning agent | Update only your feature. |
| `comments/claude/` | Claude Code only | Never write to other agents' directories. |
| `comments/codex/` | Codex only | Same exclusivity. |
| `reviews/pending/` | All agents | Proposals; human gate resolves. |
| `reviews/proxy-log/` | Proxy actor only | Written before each `review_approved`. |

Post naming: `YYYYMMDDTHHMMSS_CATEGORY_SUBJECT.md`. Categories: `REVIEW`, `STRATEGY`, `GAP`, `SCHEMA`, `HANDOFF`, `MATRIX`. Immutable once written — supersede with new file.

## Operating Standards

Load from `.gsdlc/release/operating-standards/` before: writing posts (`CONVENTIONS.md`), backlog items (`BACKLOG.md`), human-facing docs (`WRITING.md`), user guides (`USER_GUIDE.md`), releases (`RELEASE.md`).

## Human Proxy Mode

- `--human-proxy` requires `--auto`. Explicit flag only, never persisted.
- Proxy writes proxy-log before emitting `review_approved{actor: "human-proxy"}`.
- Rejection halts auto-loop immediately. No retry in same session.
- `/gen-status` surfaces proxy decisions for morning review.

## Bug Triage

Fix directly. Emit `bug_fixed` event with `root_cause: coding_error|design_flaw|unknown`. No feature vector, no iterate cycle, no human gate required. Post-mortem determines escalation.

<!-- SDLC_BOOTLOADER_END -->
