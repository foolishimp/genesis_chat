# Implements: REQ-F-CORE-004
# Implements: REQ-F-EVAL-002
# Implements: REQ-F-BIND-001
# Implements: REQ-F-PROV-003
# Implements: REQ-F-PROV-004
# Implements: REQ-F-PROV-005
# Implements: REQ-F-EC-002
# Implements: REQ-F-EC-003
# Implements: REQ-F-EC-004
# Implements: REQ-F-EC-005
"""
bind — F_D pre-computation: bind_fd, bind_fp, select_relevant_contexts,
       render_delta.

The linker: turns a typed GTL skeleton into an F_P-executable manifest.
Phase 3 of the approved execution plan. See ADR-002, ADR-003.

bind_fd  — deterministic, no LLM required. Produces PrecomputedManifest.
bind_fp  — assembles F_P manifest from pre-computed material. Also F_D.
"""
from __future__ import annotations

import hashlib
import json as _json
import os
import re
import subprocess
import sys
from pathlib import Path
from typing import Any

from gtl.core import Context, Evaluator, F_D, F_H, F_P, Job

from .core import ContextResolver, EventStream, project
from .manifest import BoundJob, PrecomputedManifest


# ── spec_hash ─────────────────────────────────────────────────────────────────

def req_hash(requirements: list[str]) -> str:
    """
    Compute a stable hash of Package.requirements.

    Deprecated: used only when scope.workflow_version == "unknown" (no active-workflow.json).
    New code should use job_evaluator_hash(job) instead. Retained as fallback for
    workspaces without active-workflow.json.
    """
    return hashlib.sha256(
        _json.dumps(sorted(requirements)).encode()
    ).hexdigest()[:16]


def job_evaluator_hash(job: Job) -> str:
    """
    Hash of all evaluator definitions and bound context digests on this job.

    Covers F_D (command), F_P/F_H (description), name+category for all
    evaluators, plus every context digest on the edge. Changing any evaluator
    field or any context's content (detected via digest) changes this hash,
    automatically invalidating prior F_P certifications.

    Used as spec_hash when scope.workflow_version != "unknown". Replaces req_hash
    for workspaces with active-workflow.json present (REQ-F-PROV-003).
    """
    lines = sorted(
        f"{ev.name}:{ev.category.__name__}:{ev.command}:{ev.description}"
        for ev in job.evaluators
    )
    # Include context digests so that context content changes invalidate
    # prior assessed{fp, pass, spec_hash} certifications.
    ctx_lines = sorted(
        f"ctx:{ctx.name}:{ctx.digest}"
        for ctx in (job.edge.context or [])
    )
    raw = "\n".join(re.sub(r'\s+', ' ', line.strip()) for line in lines + ctx_lines)
    return hashlib.sha256(raw.encode()).hexdigest()[:16]


def bind_fh(
    job: Job,
    all_events: list[dict],
    current_workflow_version: str = "unknown",
    carry_forward: list[dict] | None = None,
) -> bool:
    """
    Evaluate holdsAt(operative(edge, wv), now) for the F_H gate.

    Event Calculus semantics:
      approved{kind: fh_review}  initiates  operative(edge, wv)
      approved{kind: fh_intent}  initiates  operative(edge, wv)
      revoked{kind: fh_approval} terminates operative(edge, wv)

    operative(edge, wv) holdsAt now iff:
      an approved event initiates it AND no later revoked event terminates it.

    When current_workflow_version == "unknown":
      Accept any approved matching edge name alone (no provenance file present).

    When current_workflow_version != "unknown":
      Accept only if:
        Condition A — event.data.workflow_version == current_workflow_version, OR
        Condition B — edge in carry_forward with event.data.workflow_version == from_version

    Default arguments preserve all existing call sites without modification.
    """
    if carry_forward is None:
        carry_forward = []

    # Find the latest approved event for this edge (last-writer-wins for timestamp)
    latest_approved_time = None
    found_approved = False

    for e in all_events:
        etype = e.get("event_type")
        edata = e.get("data", {})

        # Match: approved{kind: fh_review | fh_intent}
        is_approved = (
            etype == "approved" and edata.get("kind") in ("fh_review", "fh_intent")
        )

        if is_approved and edata.get("edge") == job.edge.name:
            if current_workflow_version == "unknown":
                found_approved = True
                latest_approved_time = e.get("event_time")
                continue

            ev_wv = edata.get("workflow_version")

            # Condition A: exact version match
            if ev_wv == current_workflow_version:
                found_approved = True
                latest_approved_time = e.get("event_time")
                continue

            # Condition B: carry-forward
            for cf in carry_forward:
                if cf.get("edge") == job.edge.name and cf.get("from_version") == ev_wv:
                    found_approved = True
                    latest_approved_time = e.get("event_time")
                    break

    if not found_approved:
        return False

    # Check for terminates: revoked{kind: fh_approval} postdating the approved event.
    # Revocation is scoped by workflow_version — a revocation from one lens cannot
    # cancel approvals from another. When current_workflow_version == "unknown",
    # revocations match by edge alone (same unversioned fallback as approvals).
    for e in all_events:
        etype = e.get("event_type")
        edata = e.get("data", {})
        if etype == "revoked" and edata.get("kind") == "fh_approval":
            revoked_edge = edata.get("edge")
            if revoked_edge == job.edge.name or revoked_edge == "*":
                # Workflow version scoping (symmetric with approval matching)
                if current_workflow_version != "unknown":
                    rev_wv = edata.get("workflow_version")
                    if rev_wv != current_workflow_version:
                        continue  # Different lens — does not terminate this fluent
                # Revocation must postdate the approval
                if latest_approved_time is None or e.get("event_time", "") > latest_approved_time:
                    return False

    return True


def bind_fp_certified(
    job: Job,
    ev: Evaluator,
    all_events: list[dict],
    spec_hash: str | None = None,
    current_workflow_version: str = "unknown",
) -> bool:
    """
    Evaluate holdsAt(certified(edge, evaluator, spec_hash, wv), now) for an F_P evaluator.

    Event Calculus semantics (symmetric with bind_fh):
      assessed{kind: fp, result: pass}  initiates  certified(edge, ev, spec_hash, wv)
      revoked{kind: fp_assessment}      terminates certified(edge, ev, spec_hash, wv)

    certified(edge, ev, spec_hash, wv) holdsAt now iff:
      an assessed{pass} event initiates it AND no later revoked{fp_assessment} terminates it,
      AND spec_hash matches (identity-based termination).
    """
    # Find the latest assessed{kind: fp, result: pass} for this edge+evaluator
    latest_assessed_time = None
    found_assessed = False

    for e in all_events:
        etype = e.get("event_type")
        edata = e.get("data", {})

        is_assessed = (
            etype == "assessed"
            and edata.get("kind") == "fp"
            and edata.get("edge") == job.edge.name
            and edata.get("evaluator") == ev.name
            and edata.get("result") == "pass"
        )

        if is_assessed:
            # spec_hash identity check
            if spec_hash is not None and edata.get("spec_hash") != spec_hash:
                continue  # Different fluent identity — does not initiate
            found_assessed = True
            latest_assessed_time = e.get("event_time")

    if not found_assessed:
        return False

    # Check for terminates: revoked{kind: fp_assessment} postdating the assessed event.
    # Symmetric with bind_fh revocation check.
    for e in all_events:
        etype = e.get("event_type")
        edata = e.get("data", {})
        if etype == "revoked" and edata.get("kind") == "fp_assessment":
            revoked_edge = edata.get("edge")
            if revoked_edge == job.edge.name or revoked_edge == "*":
                # Workflow version scoping (symmetric with bind_fh)
                if current_workflow_version != "unknown":
                    rev_wv = edata.get("workflow_version")
                    if rev_wv != current_workflow_version:
                        continue  # Different lens — does not terminate this fluent
                # Revocation must postdate the assessment
                if latest_assessed_time is None or e.get("event_time", "") > latest_assessed_time:
                    return False

    return True


# ── F_D evaluator runner ──────────────────────────────────────────────────────

# Wall-clock limit for F_D subprocess evaluators.
# Prevents unbounded hangs from misconfigured commands (e.g. cyclic genesis invocations).
# Override via FD_TIMEOUT_SECONDS env var for slow environments.
import os as _os
FD_TIMEOUT_SECONDS: int = int(_os.environ.get("FD_TIMEOUT_SECONDS", "120"))


def run_fd_evaluator(
    ev: Evaluator,
    current_asset: dict,
    workspace_root: Path,
) -> tuple[bool, Any]:
    """
    Run one F_D evaluator. Returns (passes: bool, detail: Any).

    Dispatches via ev.command — the Package specifies; the kernel runs.
    Fails closed: an F_D evaluator with no command is a misconfigured Package.
    PYTHONPATH is set so genesis and gtl packages resolve inside the subprocess.
    """
    if ev.category is not F_D:
        raise TypeError(
            f"run_fd_evaluator called on non-F_D evaluator: {ev.name!r} "
            f"(category={ev.category.__name__})"
        )
    if not ev.command:
        return False, {
            "status": "error",
            "reason": f"F_D evaluator {ev.name!r} has no command — misconfigured Package",
        }

    # Propagate sys.path as PYTHONPATH so genesis/gtl are importable in subprocesses.
    env = os.environ.copy()
    extra = os.pathsep.join(p for p in sys.path if p)
    existing = env.get("PYTHONPATH", "")
    env["PYTHONPATH"] = os.pathsep.join(filter(None, [extra, existing]))

    try:
        result = subprocess.run(
            ev.command, shell=True, cwd=workspace_root,
            capture_output=True, text=True, env=env,
            timeout=FD_TIMEOUT_SECONDS,
        )
    except subprocess.TimeoutExpired:
        return False, {
            "status": "timeout",
            "reason": (
                f"F_D evaluator {ev.name!r} exceeded {FD_TIMEOUT_SECONDS}s wall-clock limit. "
                "Check that the command does not re-enter orchestration (start/iterate/gaps/emit-event) "
                "and excludes long-running test suites."
            ),
        }
    return result.returncode == 0, {
        "returncode": result.returncode,
        "stdout": result.stdout[-3000:],
        "stderr": result.stderr[-500:],
    }


# ── bind_fd ───────────────────────────────────────────────────────────────────

def bind_fd(
    job: Job,
    stream: EventStream,
    resolver: ContextResolver,
    workspace_root: Path,
    spec_hash: str | None = None,
    current_workflow_version: str = "unknown",
    carry_forward: list[dict] | None = None,
) -> PrecomputedManifest:
    """
    F_D pre-computation phase. Everything computable without an LLM.

    Produces the residual gap — the minimal surface F_P must address.
    See ADR-002 for the split rationale.
    """
    # 1. Project current asset state
    source = job.source_type
    source_name = source[0].name if isinstance(source, list) else source.name
    current = project(stream, source_name, "current")

    # 2. Run all F_D evaluators — always, unconditionally.
    # edge_converged events are audit records (emitted by gen_gaps when delta=0),
    # not gates that bypass evaluation. F_D is deterministic; re-running is cheap
    # and necessary for live convergence detection.
    all_events = stream.all_events()
    fd_results: dict[str, Any] = {}
    for ev in job.evaluators:
        if ev.category is F_D:
            passes, detail = run_fd_evaluator(ev, current, workspace_root)
            fd_results[ev.name] = {"passes": passes, "detail": detail}

    def _passes(ev: Evaluator) -> bool:
        if ev.category is F_D:
            return fd_results.get(ev.name, {}).get("passes", False)
        if ev.category is F_H:
            return bind_fh(job, all_events, current_workflow_version, carry_forward)
        if ev.category is F_P:
            # EC: holdsAt(certified(edge, evaluator, spec_hash, wv), now)
            # Initiated by assessed{kind: fp, result: pass, spec_hash: H}.
            # Terminated by revoked{kind: fp_assessment} or spec_hash mismatch.
            return bind_fp_certified(
                job, ev, all_events, spec_hash, current_workflow_version
            )
        return False

    failing = [ev for ev in job.evaluators if not _passes(ev)]
    passing = [ev for ev in job.evaluators if _passes(ev)]

    # 4. Select relevant contexts (F_D filters to what the gap actually needs)
    relevant_ctxs = select_relevant_contexts(job.edge.context, failing)
    resolved: dict[str, str] = {}
    _missing_contexts: list[str] = []
    for ctx in relevant_ctxs:
        try:
            resolved[ctx.name] = resolver.load(ctx)
        except NotImplementedError as exc:
            # Unimplemented V1 scheme (git://, event://, registry://) — degrade gracefully
            resolved[ctx.name] = f"[context unavailable: {exc}]"
        except FileNotFoundError as exc:
            # Missing context — record for gap reporting but flag as unresolved.
            # bind_fp will refuse to dispatch F_P against incomplete context.
            resolved[ctx.name] = f"[context not found: {exc}]"
            _missing_contexts.append(ctx.name)
        # REQ-F-BIND-001: ValueError (digest mismatch, unknown scheme) propagates as fatal.
        # A digest mismatch is a replay-integrity violation — the constraint surface has
        # changed and the engine must not continue dispatching F_P against a corrupted context.

    # 5. Build structured delta summary
    summary = render_delta(fd_results, failing)

    return PrecomputedManifest(
        job=job,
        current_asset=current,
        failing_evaluators=failing,
        passing_evaluators=passing,
        fd_results=fd_results,
        relevant_contexts=resolved,
        missing_contexts=_missing_contexts,
        delta_summary=summary,
    )


# ── bind_fp ───────────────────────────────────────────────────────────────────

def bind_fp(
    pre: PrecomputedManifest,
    job: Job,
    result_path: str = "",
) -> BoundJob:
    """
    Assemble the minimal F_P manifest from pre-computed material.

    This function itself is F_D — template assembly only, no LLM.
    See ADR-003 for manifest structure.

    Raises FileNotFoundError if required context failed to resolve —
    F_P must not be dispatched against an incomplete constitutional surface.
    """
    if pre.missing_contexts:
        raise FileNotFoundError(
            f"Cannot dispatch F_P: required context(s) not found: "
            f"{', '.join(pre.missing_contexts)}. "
            f"Fix the context locators or provide the missing files before iterating."
        )
    prompt = _assemble_prompt(pre, job, result_path)
    return BoundJob(job=job, precomputed=pre, prompt=prompt, result_path=result_path)


def _assemble_prompt(pre: PrecomputedManifest, job: Job, result_path: str = "") -> str:
    """
    Assemble the F_P prompt.

    Structure: PRECONDITIONS → CURRENT STATE → GAP → CONTEXT → OUTPUT CONTRACT.

    The methodology comes from Context[] on the edge (bootloader, spec, ADRs) —
    not from hardcoded invariants. The engine is domain-blind; GSDLC (or any
    domain package) defines what the F_P actor sees via edge.context[].
    """
    sections: list[str] = []

    # [PRECONDITIONS] — what's guaranteed from upstream (source asset stability)
    src = job.edge.source
    if isinstance(src, list):
        src_name = " × ".join(a.name for a in src)
        src_markov = {a.name: a.markov for a in src}
    else:
        src_name = src.name
        src_markov = {src.name: src.markov}
    precond_lines = [
        "[PRECONDITIONS] — upstream asset stability (these hold):"
    ]
    for name, conditions in src_markov.items():
        if conditions:
            precond_lines.append(f"  {name}: {conditions}")
        else:
            precond_lines.append(f"  {name}: (no markov conditions)")
    sections.append("\n".join(precond_lines))

    # [CURRENT STATE]
    sections.append(
        f"[CURRENT STATE]\n"
        f"Edge: {job.edge.name}\n"
        f"Source asset: {src_name}\n"
        f"Target asset: {job.edge.target.name}\n"
        f"Status: {pre.current_asset.get('status', 'unknown')}\n"
        f"Edges converged: {pre.current_asset.get('edges_converged', [])}"
    )

    # [GAP]
    gap_lines = [f"[GAP] — {len(pre.failing_evaluators)} evaluator(s) failing:"]
    for ev in pre.failing_evaluators:
        detail = pre.fd_results.get(ev.name, {})
        gap_lines.append(f"  {ev.name} ({ev.category.__name__}): {ev.description}")
        if detail:
            gap_lines.append(f"    F_D result: {detail.get('detail', detail)}")
    if not pre.failing_evaluators:
        gap_lines.append("  (none — all evaluators pass)")
    sections.append("\n".join(gap_lines))

    # [CONTEXT] — full constraint surface from edge.context[], no truncation.
    # The methodology (bootloader), spec, design ADRs — whatever GSDLC declared
    # on this edge. The engine does not filter or summarize; the domain package
    # controls what the F_P actor sees by choosing edge.context[].
    if pre.relevant_contexts:
        ctx_lines = ["[CONTEXT] — constraint surface for this edge:"]
        for name, content in pre.relevant_contexts.items():
            ctx_lines.append(f"\n--- {name} ---\n{content}")
        sections.append("\n".join(ctx_lines))

    # [OUTPUT CONTRACT]
    # Constitutional constraint: F_P does NOT call the event logger.
    # The actor writes its assessment to result_path. The skill (F_D layer)
    # reads it and emits assessed{kind: fp} via emit-event CLI. See GTL Bootloader §V.
    target = job.edge.target
    fp_failing = [ev for ev in pre.failing_evaluators if ev.category is F_P]
    assessment_contract = ""
    if fp_failing and result_path:
        ev_assessments = [
            f'{{"evaluator": "{ev.name}", "result": "pass|fail", "evidence": "..."}}'
            for ev in fp_failing
        ]
        assessment_contract = (
            f"\n\nWrite assessment JSON to: {result_path}\n"
            f"Format: {{{{'edge': '{job.edge.name}', 'actor': '<your_agent_id>', 'assessments': [{', '.join(ev_assessments)}]}}}}\n"
            "The app reads this file and emits assessed events — do NOT call emit-event yourself."
        )

    sections.append(
        f"[OUTPUT CONTRACT]\n"
        f"Produce: {target.name} asset\n"
        f"Satisfying markov conditions: {target.markov}\n"
        f"Evaluators to pass: {[ev.name for ev in pre.failing_evaluators]}"
        + assessment_contract
    )

    return "\n\n".join(sections)


# ── select_relevant_contexts ──────────────────────────────────────────────────

def select_relevant_contexts(
    all_contexts: list[Context],
    failing: list[Evaluator],
) -> list[Context]:
    """
    F_D: filter contexts to those relevant to the failing evaluators.

    Domain-blind: contexts are only needed when F_P work is required.
    F_D and F_H failures do not need prompt context — F_D re-runs its command,
    F_H waits for an approved event. Only F_P dispatch consumes context.
    """
    if not failing:
        return []
    fp_failing = [ev for ev in failing if ev.category is F_P]
    if not fp_failing:
        return []
    return list(all_contexts)


# ── render_delta ─────────────────────────────────────────────────────────────

def render_delta(
    fd_results: dict[str, Any],
    failing: list[Evaluator],
) -> str:
    """Render a structured human-readable gap description."""
    if not failing:
        return "delta = 0 — all evaluators pass"

    lines = [f"delta = {len(failing)} — {len(failing)} evaluator(s) failing:"]
    for ev in failing:
        detail = fd_results.get(ev.name, {})
        det = detail.get("detail", detail) if isinstance(detail, dict) else detail
        lines.append(f"  {ev.name} ({ev.category.__name__}): {det}")

    return "\n".join(lines)
