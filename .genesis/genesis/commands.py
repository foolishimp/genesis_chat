# Implements: REQ-F-CMD-001
# Implements: REQ-F-CMD-002
# Implements: REQ-F-CMD-003
# Implements: REQ-F-CMD-004
# Implements: REQ-F-GRAPH-001
# Implements: REQ-F-GRAPH-002
# Implements: REQ-F-EVAL-002
# Implements: REQ-F-VIS-001
# Implements: REQ-F-PROV-001
# Implements: REQ-F-PROV-003
"""
commands — gen_start, gen_iterate, gen_gaps, Scope.

Three commands as named compositions of core functions. None introduce new
primitives. Phase 4 of the approved execution plan. See ADR-004 (Scope).

  /gen-gaps    = bind_fd over scope → delta_summary fields
  /gen-iterate = bind one Job → iterate exactly once
  /gen-start   = derive state → select job → bind → iterate
"""
from __future__ import annotations

import json
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Callable, Optional

from gtl.core import Job, Package, Worker

from .bind import bind_fd, bind_fp, bind_fh, job_evaluator_hash, req_hash
from .core import ContextResolver, EventStream, project
from .manifest import BoundJob
from .schedule import delta, iterate, schedule


# ── Workflow provenance helpers ───────────────────────────────────────────────

def _read_workflow_version(workspace: Path, active_workflow_path: str | None = None) -> str:
    """
    Read active-workflow.json and return "{workflow}@{version}".

    When *active_workflow_path* is provided (from genesis.yml runtime contract),
    it is resolved relative to workspace and used as the authoritative location.
    Otherwise reads .ai-workspace/runtime/active-workflow.json.

    .genesis/ is immutable installed runtime — no fallback to it. Mutable state
    must live under .ai-workspace/. The installer (gen-install.py) is responsible
    for creating the runtime directory and migrating legacy locations.

    Returns "unknown" on any failure: file absent, invalid JSON, missing keys,
    non-string values. The engine never fails to start due to this file's state.

    Pure read — no side effects. Called by Scope.__post_init__ at engine startup
    and by _emit_event_cmd at CLI call time (REQ-F-PROV-001/002).
    """
    if active_workflow_path:
        active_wf = (workspace / active_workflow_path).resolve()
    else:
        active_wf = workspace / ".ai-workspace" / "runtime" / "active-workflow.json"
    try:
        data = json.loads(active_wf.read_text(encoding="utf-8"))
        workflow = data["workflow"]
        version = data["version"]
        if not isinstance(workflow, str) or not isinstance(version, str):
            return "unknown"
        return f"{workflow}@{version}"
    except Exception:
        return "unknown"


def _read_carry_forward(scope: "Scope") -> list[dict]:
    """
    Read approved_carry_forward from the variant manifest.json.

    Path: {workflow_root}/{pkg}/{variant}/{version}/manifest.json
    where workflow "my_domain.standard@0.2.0" → pkg="my_domain",
    variant="standard", version="0.2.0".

    When scope.workflow_root is set (from genesis.yml runtime contract), it is
    used as the base directory. Otherwise falls back to .genesis/workflows/.

    Returns [] if workflow_version is "unknown", file absent, or key missing.
    """
    if scope.workflow_version == "unknown":
        return []
    workflow, version = scope.workflow_version.split("@", 1)
    parts = workflow.split(".", 1)
    pkg_name = parts[0]
    variant = parts[1] if len(parts) > 1 else "default"
    version_dir = "v" + version.replace(".", "_")
    if scope.workflow_root:
        wf_base = (scope.workspace_root / scope.workflow_root).resolve()
    else:
        wf_base = scope.workspace_root / ".genesis" / "workflows"
    manifest_path = (
        wf_base / pkg_name / variant / version_dir / "manifest.json"
    )
    try:
        data = json.loads(manifest_path.read_text(encoding="utf-8"))
        cf = data.get("approved_carry_forward", [])
        return cf if isinstance(cf, list) else []
    except Exception:
        return []


# ── Scope ─────────────────────────────────────────────────────────────────────

@dataclass
class Scope:
    """
    First-class scope object. Every command requires one. No ambient inference.

    Ambiguous scope fails closed — the command returns an error describing the
    available scopes rather than guessing. See ADR-004.

    worker: the Worker that executes jobs in this scope. When provided, the
        command layer is fully domain-blind — no spec import occurs. When None,
        _resolve_worker() falls back to the genesis self-hosting spec import
        (V1 CLI convenience; remove in V2 — callers should always supply worker).

    active_workflow_path: relative path to active-workflow.json, read from
        genesis.yml runtime contract. When set, used instead of the default
        .ai-workspace/runtime/active-workflow.json.

    workflow_root: relative path to workflow releases base directory, read from
        genesis.yml runtime contract. When set, used instead of .genesis/workflows/.

    workflow_version: derived at construction from active-workflow.json.
        "{workflow}@{version}" when file present and valid; "unknown" otherwise.
        When "unknown", provenance checks are bypassed.

    Build identifier is build-layer specific. This Claude Code build defaults to "claude_code".
    """
    package: Package
    workspace_root: Path
    feature: Optional[str] = None     # feature vector ID override (None = all)
    edge: Optional[str] = None        # edge name override (None = topological)
    build: str = "claude_code"
    worker: Optional[Worker] = None   # explicit worker; None = spec-import fallback
    active_workflow_path: Optional[str] = None  # runtime contract: path to active-workflow.json
    workflow_root: Optional[str] = None         # runtime contract: base dir for workflow releases
    workflow_version: str = field(init=False, default="unknown")

    def __post_init__(self) -> None:
        self.workflow_version = _read_workflow_version(
            self.workspace_root, self.active_workflow_path
        )


# ── gen_gaps — bind_fd over scope ─────────────────────────────────────────────

def gen_gaps(scope: Scope, stream: EventStream) -> dict:
    """
    /gen-gaps = bind_fd over selected jobs → return delta_summary fields.

    Requires explicit Scope — fails closed on ambiguity.
    Runs bind_fd only (no F_P dispatch).

    Returns: jobs considered, failing evaluators per job, total delta.
    """
    stream.workflow_version = scope.workflow_version
    resolver = ContextResolver(scope.workspace_root)
    worker = _resolve_worker(scope)
    jobs = _scoped_jobs(scope, worker)

    if not jobs:
        return {
            "status": "error",
            "reason": "no jobs in scope — check --feature and --edge flags",
        }

    # Pre-compute which (edge, feature) pairs already have a well-formed certificate.
    # REQ-F-CMD-004: deduplication must be keyed on (edge, feature) — not edge alone.
    # Edge-only deduplication means only the first feature gets a certificate per edge;
    # subsequent features on the same converged edge never emit their own certificate
    # and project(stream, target, feature_id) stays not_started.
    certified_edge_features: set[tuple] = {
        (e["data"]["edge"], e["data"].get("feature"))
        for e in stream.all_events()
        if e.get("event_type") == "edge_converged"
        and e.get("data", {}).get("target")
    }

    carry_forward = _read_carry_forward(scope)

    results = []
    for job in jobs:
        # Orphan tolerance: events referencing edges not in scope.jobs are
        # silently ignored. This is the mechanism that allows graph evolution
        # without event stream migration.
        if scope.workflow_version == "unknown":
            spec_hash = req_hash(scope.package.requirements)
        else:
            spec_hash = job_evaluator_hash(job)
        pre = bind_fd(
            job, stream, resolver, scope.workspace_root,
            spec_hash=spec_hash,
            current_workflow_version=scope.workflow_version,
            carry_forward=carry_forward,
        )
        results.append({
            "edge": job.edge.name,
            "delta": pre.delta,
            "failing": [ev.name for ev in pre.failing_evaluators],
            "passing": [ev.name for ev in pre.passing_evaluators],
            "delta_summary": pre.delta_summary,
        })
        # Emit edge_converged when freshly confirmed delta=0 and not yet certified.
        # Idempotent: once a well-formed certificate exists in the log (edge + target),
        # repeated gen_gaps calls over a converged workspace do not append duplicates.
        # feature is included so feature-scoped project() calls can match this event.
        if pre.delta == 0 and (job.edge.name, scope.feature) not in certified_edge_features:
            cert: dict = {
                "edge": job.edge.name,
                "target": job.edge.target.name,
                "feature": scope.feature,
                "delta": 0,
                "certified_by": "gen_gaps",
            }
            stream.append("edge_converged", cert)
            certified_edge_features.add((job.edge.name, scope.feature))

    total_delta = sum(r["delta"] for r in results)
    return {
        "scope": {
            "package": scope.package.name,
            "feature": scope.feature,
            "edge": scope.edge,
            "build": scope.build,
        },
        "jobs_considered": len(results),
        "total_delta": total_delta,
        "converged": total_delta == 0,
        "gaps": results,
    }


# ── gen_iterate — bind + iterate once ─────────────────────────────────────────

def gen_iterate(
    scope: Scope,
    stream: EventStream,
    on_fp_dispatch: Optional[Callable[[BoundJob], None]] = None,
) -> dict:
    """
    /gen-iterate = bind one Job → iterate exactly once.

    The most important command to keep pure.
    One Job. One Asset. One iterate call.
    """
    stream.workflow_version = scope.workflow_version
    resolver = ContextResolver(scope.workspace_root)
    worker = _resolve_worker(scope)
    jobs = _scoped_jobs(scope, worker)

    if not jobs:
        return {"status": "nothing_to_do", "reason": "no jobs in scope"}

    carry_forward = _read_carry_forward(scope)

    # Select the first unconverged job in topological order
    selected_job = None
    selected_pre = None
    for job in jobs:
        if scope.workflow_version == "unknown":
            spec_hash = req_hash(scope.package.requirements)
        else:
            spec_hash = job_evaluator_hash(job)
        pre = bind_fd(
            job, stream, resolver, scope.workspace_root,
            spec_hash=spec_hash,
            current_workflow_version=scope.workflow_version,
            carry_forward=carry_forward,
        )
        if pre.has_gap:
            selected_job = job
            selected_pre = pre
            break

    if selected_job is None:
        return {
            "status": "converged",
            "reason": "all jobs in scope have delta = 0",
        }

    # Determine result_path for F_P actor output (written before bind_fp)
    from gtl.core import F_D as _F_D, F_P as _F_P, F_H as _F_H
    fd_failing = [ev for ev in selected_pre.failing_evaluators if ev.category is _F_D]
    fp_failing = [ev for ev in selected_pre.failing_evaluators if ev.category is _F_P]
    fh_failing = [ev for ev in selected_pre.failing_evaluators if ev.category is _F_H]

    # REQ-F-GATE-002 (ADR-021): F_D findings escalate to F_P — no early return.
    # The fd_gap early return was removed. iterate() now emits both
    # found{kind: fd_findings} and fp_dispatched when F_D and F_P are both failing.

    ts = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S")
    edge_slug = selected_job.edge.name.replace("→", "_").replace("↔", "_")
    manifest_id = f"{edge_slug}_{ts}"

    # Check for pending F_P dispatch (fp_dispatched without matching assessed).
    # Prevents duplicate dispatch while a prior F_P invocation is still in flight.
    if fp_failing:
        pending_id = _find_pending_dispatch(stream, selected_job.edge.name)
        if pending_id is not None:
            return {
                "status": "pending",
                "reason": f"F_P dispatch already in flight for edge {selected_job.edge.name!r}",
                "pending_manifest_id": pending_id,
                "edge": selected_job.edge.name,
            }

    result_path = ""
    if fp_failing:
        fp_results_dir = scope.workspace_root / ".ai-workspace" / "fp_results"
        fp_results_dir.mkdir(parents=True, exist_ok=True)
        result_path = str(fp_results_dir / f"{manifest_id}.json")

    # Bind + iterate
    bound = bind_fp(selected_pre, selected_job, result_path=result_path)
    bound.manifest_id = manifest_id
    # REQ-F-CORE-001: include target so project() "current" projection can filter
    # edge_started to only the asset type being produced by this edge.
    stream.append("edge_started", {
        "edge": selected_job.edge.name,
        "build": scope.build,
        "target": selected_job.edge.target.name,
    })

    surface = iterate(bound, on_fp_dispatch=on_fp_dispatch)

    # Emit surface events
    for event in surface.events:
        stream.append(event["event_type"], event["data"])

    result: dict = {
        "status": "iterated",
        "edge": selected_job.edge.name,
        "delta_before": selected_pre.delta,
        "failing_evaluators": [ev.name for ev in selected_pre.failing_evaluators],
        "events_emitted": len(surface.events) + 1,  # +1 for edge_started
        "prompt_words": len(bound.prompt.split()),
        "surface_artifacts": surface.artifacts,
        "context_consumed": [c.name for c in surface.context_consumed],
    }

    # Write F_P manifest to disk when F_P dispatch is needed.
    # The manifest JSON is the authoritative F_P dispatch contract.
    # Any conforming transport (Claude Code, API, Codex) must be able to
    # execute from this JSON alone — CLAUDE.md is convenience, not authority.
    if fp_failing:
        manifests_dir = scope.workspace_root / ".ai-workspace" / "fp_manifests"
        manifests_dir.mkdir(parents=True, exist_ok=True)
        manifest_file = manifests_dir / f"{manifest_id}.json"

        # Source asset(s) — handle product arrows (A × B)
        src = selected_job.edge.source
        if isinstance(src, list):
            source_asset = [a.name for a in src]
            source_markov = {a.name: a.markov for a in src}
        else:
            source_asset = src.name
            source_markov = {src.name: src.markov}

        # Context references with locator + digest + resolved content
        contexts = []
        for ctx in selected_job.edge.context:
            ctx_entry: dict = {
                "name": ctx.name,
                "locator": ctx.locator,
                "digest": ctx.digest,
            }
            if ctx.name in selected_pre.relevant_contexts:
                ctx_entry["content"] = selected_pre.relevant_contexts[ctx.name]
            contexts.append(ctx_entry)

        manifest = {
            "manifest_id": manifest_id,
            "edge": selected_job.edge.name,
            "source_asset": source_asset,
            "target_asset": selected_job.edge.target.name,
            "source_markov": source_markov,
            "target_markov": selected_job.edge.target.markov,
            "failing_evaluators": [
                {"name": ev.name, "category": ev.category.__name__,
                 "description": ev.description}
                for ev in fp_failing
            ],
            "fd_results": selected_pre.fd_results,
            "delta": selected_pre.delta,
            "delta_summary": selected_pre.delta_summary,
            "contexts": contexts,
            "current_asset": selected_pre.current_asset,
            "prompt": bound.prompt,
            "result_path": result_path,
            "spec_hash": spec_hash,
            "requirements": scope.package.requirements,
        }
        manifest_file.write_text(json.dumps(manifest, indent=2), encoding="utf-8")
        result["fp_manifest_path"] = str(manifest_file)

    # Include F_H gate criteria so skill can evaluate without extra reads.
    if fh_failing:
        result["fh_gate"] = {
            "edge": selected_job.edge.name,
            "evaluators": [ev.name for ev in fh_failing],
            "criteria": [ev.description for ev in fh_failing],
        }

    return result


# ── gen_start — state machine ──────────────────────────────────────────────────

def gen_start(
    scope: Scope,
    stream: EventStream,
    auto: bool = False,
    on_fp_dispatch: Optional[Callable[[BoundJob], None]] = None,
) -> dict:
    """
    /gen-start = derive state → select job → bind → iterate.

    State machine: reads workspace, selects the next unconverged job,
    delegates to gen_iterate. In --auto mode, loops until converged or blocked.
    """
    state = _derive_state(scope, stream)

    if state["status"] == "converged":
        _close_completed_features(scope)
        return {
            "status": "converged",
            "message": "All jobs in scope have delta = 0. Run /gen-gaps for full report.",
        }

    if state["status"] == "nothing_to_do":
        return {
            "status": "nothing_to_do",
            "reason": state.get("reason", ""),
        }

    # IN_PROGRESS — dispatch to gen_iterate
    if not auto:
        return gen_iterate(scope, stream, on_fp_dispatch=on_fp_dispatch)

    # --auto: loop until converged, F_H gate, F_P dispatch, or max iterations.
    # Stop immediately on F_P dispatch (need actor response) or F_H gate (need human).
    MAX_AUTO = 50
    last_event_count = len(stream.all_events())
    result: dict = {}

    for _ in range(MAX_AUTO):
        result = gen_iterate(scope, stream, on_fp_dispatch=on_fp_dispatch)
        result["auto"] = True

        if result["status"] in ("converged", "nothing_to_do", "pending"):
            return result

        # Inspect events emitted by this iteration
        new_events = stream.all_events()[last_event_count:]
        last_event_count += len(new_events)

        # Stop on any condition that cannot auto-resolve without external input.
        new_types = {e["event_type"] for e in new_events}
        if "fp_dispatched" in new_types:
            result["stopped_by"] = "fp_dispatch"
            return result
        if "fh_gate_pending" in new_types:
            result["stopped_by"] = "fh_gate"
            return result
        # REQ-F-GATE-002 (ADR-021): only terminal fd_gap stops the loop.
        # fd_findings (escalation) accompanies fp_dispatched which stops above.
        if any(e["event_type"] == "found" and e.get("data", {}).get("kind") == "fd_gap"
               for e in new_events):
            result["stopped_by"] = "fd_gap"
            return result

    result["stopped_by"] = "max_iterations"
    return result


def _derive_state(scope: Scope, stream: EventStream) -> dict:
    """Derive project state from workspace. Never stored — always derived."""
    resolver = ContextResolver(scope.workspace_root)
    worker = _resolve_worker(scope)
    jobs = _scoped_jobs(scope, worker)

    if not jobs:
        return {"status": "nothing_to_do", "reason": "no jobs in scope"}

    carry_forward = _read_carry_forward(scope)

    total_delta = 0
    for job in jobs:
        if scope.workflow_version == "unknown":
            spec_hash = req_hash(scope.package.requirements)
        else:
            spec_hash = job_evaluator_hash(job)
        pre = bind_fd(
            job, stream, resolver, scope.workspace_root,
            spec_hash=spec_hash,
            current_workflow_version=scope.workflow_version,
            carry_forward=carry_forward,
        )
        total_delta += pre.delta

    if total_delta == 0:
        return {"status": "converged"}

    return {"status": "in_progress", "delta": total_delta}


# ── pending dispatch fluent ───────────────────────────────────────────────────

def _find_pending_dispatch(stream: EventStream, edge_name: str) -> Optional[str]:
    """
    Check for an outstanding F_P dispatch on this edge.

    Returns the manifest_id of the pending dispatch, or None if no dispatch
    is in flight. A dispatch is pending when an fp_dispatched event exists
    for this edge with a manifest_id that has no corresponding assessed event.

    Event Calculus:
      fp_dispatched{manifest_id: M}  initiates  pending(edge, M)
      assessed{manifest_id: M}       terminates pending(edge, M)
    """
    all_events = stream.all_events()

    # Collect all manifest_ids dispatched for this edge
    dispatched_ids: set[str] = set()
    for e in all_events:
        if (
            e.get("event_type") == "fp_dispatched"
            and e.get("data", {}).get("edge") == edge_name
            and e.get("data", {}).get("manifest_id")
        ):
            dispatched_ids.add(e["data"]["manifest_id"])

    if not dispatched_ids:
        return None

    # Remove any that have a matching assessed event
    for e in all_events:
        if (
            e.get("event_type") == "assessed"
            and e.get("data", {}).get("manifest_id") in dispatched_ids
        ):
            dispatched_ids.discard(e["data"]["manifest_id"])

    # Return the first remaining pending dispatch (if any)
    if dispatched_ids:
        return next(iter(dispatched_ids))
    return None


# ── internal helpers ──────────────────────────────────────────────────────────

def _resolve_worker(scope: Scope) -> Worker:
    """
    Resolve the worker for the given scope.

    Domain-blind: scope.worker must be explicitly supplied by the caller.
    The CLI resolves worker from --worker flag or .genesis/genesis.yml.
    """
    if scope.worker is None:
        raise RuntimeError(
            "scope.worker is None — supply worker via Scope(worker=...) "
            "or configure .genesis/genesis.yml (written by gen-install.py)"
        )
    return scope.worker


def _scoped_jobs(scope: Scope, worker: Worker) -> list[Job]:
    """
    Return jobs from worker.can_execute, filtered by scope overrides.

    edge override: exact match on job.edge.name — narrows which jobs run.

    feature override (V1 behaviour): existence validation only.
      V1 has a single trajectory — Jobs are not tagged by feature_id.
      --feature REQ-F-CORE validates that feature exists in the workspace;
      it does not narrow which jobs run (all 5 jobs cover the single trajectory).
      Unknown feature ID → empty list (fails closed; caller reports error).
      Per-job feature routing is a V2 concern when multiple packages coexist.
    """
    jobs = list(worker.can_execute)

    if scope.feature:
        known = _known_feature_ids(scope.workspace_root)
        if scope.feature not in known:
            return []  # fail closed — unknown feature

    if scope.edge:
        jobs = [j for j in jobs if j.edge.name == scope.edge]

    return jobs


def _close_completed_features(scope: Scope) -> None:
    """
    Move all active feature YAMLs to features/completed/ and update status field.

    Called by gen_start when it arrives and finds all edges have delta=0 — the
    worker came back, found the work done, closes the ticket.
    """
    active_dir = scope.workspace_root / ".ai-workspace" / "features" / "active"
    completed_dir = scope.workspace_root / ".ai-workspace" / "features" / "completed"
    completed_dir.mkdir(parents=True, exist_ok=True)

    if not active_dir.exists():
        return

    for yml in sorted(active_dir.glob("*.yml")):
        text = yml.read_text(encoding="utf-8")
        # Update status field regardless of current value
        for old_status in ("status: not_started", "status: active", "status: iterating"):
            if old_status in text:
                text = text.replace(old_status, "status: completed", 1)
                break
        (completed_dir / yml.name).write_text(text, encoding="utf-8")
        yml.unlink()


def _known_feature_ids(workspace_root: Path) -> set[str]:
    """Return feature IDs from YAML filenames in .ai-workspace/features/."""
    features_dir = workspace_root / ".ai-workspace" / "features"
    ids: set[str] = set()
    for subdir in ("active", "completed"):
        d = features_dir / subdir
        if d.exists():
            ids.update(f.stem for f in d.glob("*.yml"))
    return ids
