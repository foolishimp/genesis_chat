# Implements: REQ-F-CORE-001
# Implements: REQ-F-CORE-005
# Implements: REQ-F-CORE-006
# Implements: REQ-F-WKSP-001
# Implements: REQ-F-GATE-001
# Implements: REQ-F-GATE-002
# Implements: REQ-F-EVAL-002
# Implements: REQ-F-PROV-004
"""
schedule — delta, iterate, schedule.

The asset-producing loop. Phase 4 of the approved execution plan.

  delta(job, stream, workspace_root) -> float
      0.0 = converged. > 0.0 = work needed.

  iterate(bound_job, on_fp_dispatch) -> WorkingSurface
      Universal HOF. Domain-blind. Job is the parameter.
      Does NOT call emit() — the engine calls emit() on the surface.

  schedule(workers) -> list[list[Worker]]
      Partitions workers into parallel-safe batches.
      V1: trivially [[single_worker]].
"""
from __future__ import annotations

from pathlib import Path
from typing import Callable, Optional

from gtl.core import Evaluator, F_D, F_H, F_P, Job, Worker, WorkingSurface

from .bind import bind_fd, bind_fh, req_hash, run_fd_evaluator
from .core import EventStream, project
from .manifest import BoundJob


# ── delta ─────────────────────────────────────────────────────────────────────

def delta(
    job: Job,
    stream: EventStream,
    workspace_root: Path,
    spec_hash: str | None = None,
    current_workflow_version: str = "unknown",
    carry_forward: list[dict] | None = None,
) -> float:
    """
    0.0 = converged. > 0.0 = work needed.

    F_D evaluators: run deterministic check. 0.0 if passes, 1.0 if fails.
    F_H evaluators: 0.0 if holdsAt(operative(edge, wv)), 1.0 otherwise.
    F_P evaluators: 1.0 unless all required F_D checks have passed (proxy signal).

    Returns: fraction of failing evaluators (0.0 to 1.0).
    """
    if not job.evaluators:
        return 0.0

    events = stream.all_events()

    source = job.source_type
    source_name = source[0].name if isinstance(source, list) else source.name
    current = project(stream, source_name, "current")

    failing = 0

    for ev in job.evaluators:
        if ev.category is F_D:
            passes, _ = run_fd_evaluator(ev, current, workspace_root)
            if not passes:
                failing += 1

        elif ev.category is F_H:
            # Orphan tolerance: events referencing edges not in scope.jobs are
            # silently ignored. This is the mechanism that allows graph evolution
            # without event stream migration.
            if not bind_fh(job, events, current_workflow_version, carry_forward):
                failing += 1

        elif ev.category is F_P:
            # EC: holdsAt(certified(edge, evaluator, spec_hash, wv), now)
            # spec_hash=None means caller opted out of snapshot check (tests, legacy).
            resolved = any(
                e.get("event_type") == "assessed"
                and e.get("data", {}).get("kind") == "fp"
                and e.get("data", {}).get("edge") == job.edge.name
                and e.get("data", {}).get("evaluator") == ev.name
                and e.get("data", {}).get("result") == "pass"
                and (
                    spec_hash is None
                    or e.get("data", {}).get("spec_hash") == spec_hash
                )
                for e in events
            )
            if not resolved:
                failing += 1

    return failing / len(job.evaluators)


# ── iterate ───────────────────────────────────────────────────────────────────

def iterate(
    bound_job: BoundJob,
    on_fp_dispatch: Optional[Callable[[BoundJob], None]] = None,
) -> WorkingSurface:
    """
    The universal HOF. Domain-blind. Job is the parameter.

    Processes a BoundJob (the pre-computed manifest) and produces a WorkingSurface.
    Does NOT call emit() — the caller (engine) emits from the surface.

    on_fp_dispatch: called when F_P evaluators are failing. Caller decides routing.
    F_H gates: recorded in surface.events as fh_gate_pending.
    """
    surface = WorkingSurface()
    pre = bound_job.precomputed
    job = bound_job.job

    # Record what contexts were consumed
    surface.context_consumed = list(job.edge.context)

    # REQ-F-GATE-002: F_D must pass before F_P is dispatched; F_D + F_P must
    # pass before F_H gate is emitted. Dispatching agent work against a broken
    # deterministic state wastes budget and can produce false convergence.
    fd_failing = [ev for ev in pre.failing_evaluators if ev.category is F_D]

    # Dispatch F_P evaluators — only when all F_D pass
    fp_failing = [ev for ev in pre.failing_evaluators if ev.category is F_P]
    if fp_failing and not fd_failing:
        surface.events.append({
            "event_type": "fp_dispatched",
            "data": {
                "edge": job.edge.name,
                "failing_evaluators": [ev.name for ev in fp_failing],
                "prompt_length": len(bound_job.prompt.split()),
            },
        })
        if on_fp_dispatch is not None:
            on_fp_dispatch(bound_job)

    # Record F_H gates — only when all F_D and all F_P pass
    fh_failing = [ev for ev in pre.failing_evaluators if ev.category is F_H]
    if fh_failing and not fd_failing and not fp_failing:
        surface.events.append({
            "event_type": "fh_gate_pending",
            "data": {
                "edge": job.edge.name,
                "evaluators": [ev.name for ev in fh_failing],
                "criteria": [ev.description for ev in fh_failing],
            },
        })

    # Record F_D failures as artifacts (for audit trail)
    fd_failing = [ev for ev in pre.failing_evaluators if ev.category is F_D]
    if fd_failing:
        surface.events.append({
            "event_type": "found",
            "data": {
                "kind": "fd_gap",
                "edge": job.edge.name,
                "failing": [ev.name for ev in fd_failing],
                "delta_summary": pre.delta_summary,
            },
        })

    return surface


# ── schedule ──────────────────────────────────────────────────────────────────

def schedule(workers: list[Worker]) -> list[list[Worker]]:
    """
    Partition workers into parallel-safe execution batches.

    Batch i runs concurrently. Batch i+1 starts only after batch i completes.
    Workers A and B are in the same batch iff not A.conflicts_with(B).

    Derived entirely from Worker.writable_types — no external config.
    V1: single worker → trivially [[worker]].
    """
    if not workers:
        return []

    batches: list[list[Worker]] = []
    remaining = list(workers)

    while remaining:
        # Start a new batch with the first unassigned worker
        batch = [remaining[0]]
        still_remaining = []

        for w in remaining[1:]:
            # Add to current batch if it conflicts with no existing batch member
            if not any(w.conflicts_with(b) for b in batch):
                batch.append(w)
            else:
                still_remaining.append(w)

        batches.append(batch)
        remaining = still_remaining

    return batches
