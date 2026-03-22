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

def _read_workflow_version(workspace: Path) -> str:
    """
    Read .genesis/active-workflow.json and return "{workflow}@{version}".

    Returns "unknown" on any failure: file absent, invalid JSON, missing keys,
    non-string values. The engine never fails to start due to this file's state.

    Pure function — no Scope dependency. Called by Scope.__post_init__ at
    engine startup and by _emit_event_cmd at CLI call time (REQ-F-PROV-001/002).
    """
    active_wf = workspace / ".genesis" / "active-workflow.json"
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

    Path: .genesis/workflows/{pkg}/{variant}/{version}/manifest.json
    where workflow "genesis_sdlc.standard@0.2.0" → pkg="genesis_sdlc",
    variant="standard", version="0.2.0".

    Returns [] if workflow_version is "unknown", file absent, or key missing.
    """
    if scope.workflow_version == "unknown":
        return []
    workflow, version = scope.workflow_version.split("@", 1)
    parts = workflow.split(".", 1)
    pkg_name = parts[0]
    variant = parts[1] if len(parts) > 1 else "default"
    version_dir = "v" + version.replace(".", "_")
    manifest_path = (
        scope.workspace_root / ".genesis" / "workflows"
        / pkg_name / variant / version_dir / "manifest.json"
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

    workflow_version: read from .genesis/active-workflow.json at construction.
        "{workflow}@{version}" when file present and valid; "unknown" otherwise.
        When "unknown", provenance checks are bypassed (no active-workflow.json present).

    Build identifier is build-layer specific. This Claude Code build defaults to "claude_code".
    """
    package: Package
    workspace_root: Path
    feature: Optional[str] = None     # feature vector ID override (None = all)
    edge: Optional[str] = None        # edge name override (None = topological)
    build: str = "claude_code"
    worker: Optional[Worker] = None   # explicit worker; None = spec-import fallback
    workflow_version: str = field(init=False, default="unknown")

    def __post_init__(self) -> None:
        self.workflow_version = _read_workflow_version(self.workspace_root)


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

    # REQ-F-GATE-002: do not produce an F_P manifest while F_D is red.
    # The gate is enforced in schedule.iterate() — this layer must not create
    # orphaned manifest files that imply a dispatch will happen when it won't.
    # Emit found{kind: fd_gap} so gen_start(auto=True) event-based detection at
    # commands.py#L314 fires correctly — without this event, the auto-loop
    # cannot distinguish "fd_gap" from "no progress" and loops to max_iterations.
    if fd_failing and fp_failing:
        stream.append("found", {
            "kind": "fd_gap",
            "edge": selected_job.edge.name,
            "failing": [ev.name for ev in fd_failing],
            "delta_summary": selected_pre.delta_summary,
        })
        return {
            "status": "iterated",
            "edge": selected_job.edge.name,
            "delta_before": selected_pre.delta,
            "failing_evaluators": [ev.name for ev in selected_pre.failing_evaluators],
            "events_emitted": 1,
            "stopped_by": "fd_gap",
        }

    ts = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S")
    edge_slug = selected_job.edge.name.replace("→", "_").replace("↔", "_")

    result_path = ""
    if fp_failing:
        fp_results_dir = scope.workspace_root / ".ai-workspace" / "fp_results"
        fp_results_dir.mkdir(parents=True, exist_ok=True)
        result_path = str(fp_results_dir / f"{edge_slug}_{ts}.json")

    # Bind + iterate
    bound = bind_fp(selected_pre, selected_job, result_path=result_path)
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
    }

    # Write F_P manifest to disk when F_P dispatch is needed.
    # gen-start.md reads fp_manifest_path to get the prompt for MCP dispatch.
    if fp_failing:
        manifests_dir = scope.workspace_root / ".ai-workspace" / "fp_manifests"
        manifests_dir.mkdir(parents=True, exist_ok=True)
        manifest_file = manifests_dir / f"{edge_slug}_{ts}.json"
        manifest = {
            "edge": selected_job.edge.name,
            "failing_evaluators": [
                {"name": ev.name, "description": ev.description}
                for ev in fp_failing
            ],
            "prompt": bound.prompt,
            "result_path": result_path,
            "spec_hash": spec_hash,
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

        if result["status"] in ("converged", "nothing_to_do"):
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
        if "found" in new_types:
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
