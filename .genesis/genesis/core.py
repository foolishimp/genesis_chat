# Implements: REQ-F-CORE-001
# Implements: REQ-F-CORE-002
# Implements: REQ-F-CORE-003
# Implements: REQ-F-CORE-005
# Implements: REQ-F-EVAL-005
# Implements: REQ-F-PROV-002
"""
core — substrate functions: emit, project, EventStream, ContextResolver,
       workspace_bootstrap.

These are the irreversible primitives. Phase 2 of the approved execution plan.

Rules (ADR-005):
  - emit() is the only write path to events.jsonl
  - event_time is system-assigned — no caller can pass it
  - Corrupted event log lines fail visibly — no silent skipping
  - project() is deterministic: project(S, T, I) = project(S, T, I) always
"""
from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional

from gtl.core import Context


# ── EventStream ──────────────────────────────────────────────────────────────

class EventStream:
    """
    Append-only event log. The foundational medium.

    Assets are projections of this stream — never stored objects.
    System assigns event_time at append — no caller can override it.
    """

    def __init__(self, path: Path) -> None:
        self.path = path
        self.workflow_version: str = "unknown"

    @classmethod
    def open(cls, workspace: Path) -> "EventStream":
        """Open (or create) the canonical event log for a workspace."""
        events_path = workspace / ".ai-workspace" / "events" / "events.jsonl"
        return cls(events_path)

    def append(self, event_type: str, data: dict) -> dict:
        """
        Write one event. Returns the written record.

        event_time is assigned from the system clock — not from the caller.
        Business times (effective_at, completed_at) live in data.
        """
        record_data = {**data}
        if self.workflow_version != "unknown":
            record_data.setdefault("workflow_version", self.workflow_version)
        record = {
            "event_time": datetime.now(timezone.utc).isoformat(),
            "event_type": event_type,
            "data": record_data,
        }
        with self.path.open("a", encoding="utf-8") as f:
            f.write(json.dumps(record) + "\n")
        return record

    def all_events(self) -> list[dict]:
        """
        Read all events from the log.

        Fails visibly on corrupted lines — corrupted event logs are not
        silently skipped. Replay integrity depends on every line being valid.
        """
        if not self.path.exists():
            return []

        events: list[dict] = []
        with self.path.open(encoding="utf-8") as f:
            for lineno, line in enumerate(f, 1):
                line = line.strip()
                if not line:
                    continue
                try:
                    events.append(json.loads(line))
                except json.JSONDecodeError as exc:
                    raise ValueError(
                        f"Corrupted event log at {self.path}:{lineno}: {exc}\n"
                        f"  line: {line!r}\n"
                        "Replay is not possible until the corrupted line is repaired."
                    ) from exc
        return events

    def replay(self, asset_type: str, instance_id: str) -> dict:
        """Reconstruct asset state from the event stream. Convenience wrapper."""
        return project(self, asset_type, instance_id)


# ── emit — the only write path ───────────────────────────────────────────────

# Module-level stream reference. Set by workspace_bootstrap() or init_stream().
_stream: Optional[EventStream] = None


def init_stream(stream: EventStream) -> None:
    """Bind the module-level stream. Called by workspace_bootstrap."""
    global _stream
    _stream = stream


def emit(event_type: str, data: dict) -> None:
    """
    F_D event logger. The ONLY admissible write to events.jsonl.

    event_time is assigned from the system clock — no caller can pass it.
    F_P constructs content; the F_D engine calls emit(). Never the reverse.

    REQ-F-EVAL-005: assessed{kind: fp} events must carry spec_hash. The contract
    is enforced at the write primitive — not only at the CLI layer — so in-process
    callers cannot write stale assessments that bypass bind_fd() snapshot validation.

    Prime event validation: approved and revoked must carry kind. This prevents
    malformed events that would be silently ignored by the projection layer.

    Raises RuntimeError if workspace_bootstrap() has not been called.
    Raises ValueError if a prime event payload fails validation.
    """
    if _stream is None:
        raise RuntimeError(
            "emit() called before workspace_bootstrap(). "
            "Call workspace_bootstrap(path) first to initialise the stream."
        )
    if event_type == "assessed" and data.get("kind") == "fp" and "spec_hash" not in data:
        raise ValueError(
            "assessed{kind: fp} events must include 'spec_hash'. "
            "Use bind.req_hash(package.requirements) to compute it."
        )
    if event_type in ("approved", "revoked") and "kind" not in data:
        raise ValueError(
            f"{event_type} events must include 'kind' field. "
            "Without kind, the event is silently ignored by the projection layer."
        )
    _stream.append(event_type, data)


# ── project — state derivation ───────────────────────────────────────────────

def project(
    stream: EventStream,
    asset_type: str,
    instance_id: str,
) -> dict:
    """
    Assets are projections, not stored objects.

    project(S, T, I) = project(S, T, I) always — deterministic.
    The current state of any asset is derived here, never from mutable state.

    V1: scans all events for the given instance_id and asset_type.
    Returns a state dict with status, edges_converged, and matched events.
    """
    events = stream.all_events()

    state: dict[str, Any] = {
        "asset_type": asset_type,
        "instance_id": instance_id,
        "status": "not_started",
        "edges_converged": [],
        "event_count": 0,
    }

    for event in events:
        data = event.get("data", {})
        etype = event.get("event_type", "")

        # Match events relevant to this instance.
        # REQ-F-CORE-001: edge_started events must be observed by the "current" projection
        # so that active iteration is visible; edge_started carries only edge+build, not
        # target/asset_type, so it needs an explicit relevance rule.
        relevant = (
            data.get("instance_id") == instance_id
            or data.get("feature") == instance_id
            or (instance_id == "current" and asset_type in (
                data.get("target", ""),
                data.get("asset_type", ""),
            ))
            or (instance_id == "current" and etype == "edge_started"
                and data.get("target") == asset_type)
        )

        if not relevant:
            continue

        state["event_count"] += 1

        if etype == "edge_started":
            if state["status"] == "not_started":
                state["status"] = "in_progress"

        elif etype == "edge_converged":
            edge_name = data.get("edge", "")
            if edge_name and edge_name not in state["edges_converged"]:
                state["edges_converged"].append(edge_name)
            # Mark as converged if this edge targets our asset type
            if data.get("target") == asset_type:
                state["status"] = "converged"

        elif etype == "project_initialized":
            state["initialized"] = True

    return state


# ── ContextResolver ──────────────────────────────────────────────────────────

class ContextResolver:
    """
    Loads Context content by locator scheme + verifies digest.

    Schemes (ADR-005, ADR-002):
      workspace:// — local file or directory relative to workspace root
      git://        — NOT IMPLEMENTED in V1
      event://      — NOT IMPLEMENTED in V1
      registry://   — NOT IMPLEMENTED in V1

    Digest verification: sha256 content hash. PENDING digests (all zeros) skip.
    """

    def __init__(self, workspace_root: Path) -> None:
        self.workspace_root = workspace_root

    def load(self, ctx: Context) -> str:
        """Load context content and verify digest."""
        scheme = ctx.locator.split("://")[0]
        dispatch = {
            "workspace": self._load_workspace,
            "git":       self._load_git,
            "event":     self._load_event,
            "registry":  self._load_registry,
        }
        loader = dispatch.get(scheme)
        if loader is None:
            raise ValueError(f"Unknown context scheme: {scheme!r} in {ctx.locator!r}")

        content = loader(ctx.locator)
        self._verify_digest(ctx, content)
        return content

    def _load_workspace(self, locator: str) -> str:
        path_str = locator[len("workspace://"):]
        path = self.workspace_root / path_str

        if path.is_dir():
            parts: list[str] = []
            for pattern in ("*.md", "*.py", "*.txt", "*.yml"):
                for f in sorted(path.rglob(pattern)):
                    parts.append(f"# {f.relative_to(self.workspace_root)}")
                    parts.append(f.read_text(encoding="utf-8"))
                    parts.append("")
            if not parts:
                raise FileNotFoundError(
                    f"Context directory exists but contains no readable files: {path}"
                )
            return "\n".join(parts)

        if path.is_file():
            return path.read_text(encoding="utf-8")

        raise FileNotFoundError(f"Required context not found: {path}")

    def _load_git(self, locator: str) -> str:
        raise NotImplementedError(
            f"git:// context loading is not implemented in V1: {locator!r}"
        )

    def _load_event(self, locator: str) -> str:
        raise NotImplementedError(
            f"event:// context loading is not implemented in V1: {locator!r}"
        )

    def _load_registry(self, locator: str) -> str:
        raise NotImplementedError(
            f"registry:// context loading is not implemented in V1: {locator!r}"
        )

    def _verify_digest(self, ctx: Context, content: str) -> None:
        """Verify sha256 digest. PENDING digests (all zeros) are skipped."""
        pending = "sha256:" + "0" * 64
        if ctx.digest == pending:
            return  # Not yet computed — skip verification

        actual = "sha256:" + hashlib.sha256(content.encode("utf-8")).hexdigest()
        if actual != ctx.digest:
            raise ValueError(
                f"Context digest mismatch for {ctx.name!r}:\n"
                f"  expected: {ctx.digest}\n"
                f"  actual:   {actual}\n"
                "Replay integrity violation — context content has changed."
            )


# ── workspace_bootstrap ──────────────────────────────────────────────────────

def workspace_bootstrap(path: Path) -> EventStream:
    """
    Scaffold the .ai-workspace/ directory structure and return a bound EventStream.

    Idempotent — safe to call on an existing workspace.
    Binds the module-level stream so emit() becomes available.
    """
    ai_ws = path / ".ai-workspace"
    directories = [
        ai_ws / "events",
        ai_ws / "features" / "active",
        ai_ws / "features" / "completed",
        ai_ws / "context",
        ai_ws / "reviews" / "pending",
        ai_ws / "reviews" / "proxy-log",
        ai_ws / "comments" / "claude",
        ai_ws / "agents",
    ]
    for d in directories:
        d.mkdir(parents=True, exist_ok=True)

    events_file = ai_ws / "events" / "events.jsonl"
    if not events_file.exists():
        events_file.touch()

    stream = EventStream(events_file)
    init_stream(stream)
    return stream
