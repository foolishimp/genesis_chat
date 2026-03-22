# Implements: REQ-GTL-001
# Implements: REQ-GTL-002
# Implements: REQ-GTL-003
# Implements: REQ-GTL-004
"""
GTL constitutional object model — v0.3.0

Python library as the authored surface. No custom DSL parser.
AI assembles packages from this library; humans audit via normalised projections.

v0.3.0 additions (2026-03-15):
  WorkingSurface, Evaluator, Job, Worker, IterateProtocol — the typed execution model.
  Job<A,B> is the missing primitive that gives the system worker typing.
  Worker role = can_execute set — structural, not declarative.
  IterateProtocol declares the constitutional contract; the engine implements it.

v0.2.1 (Codex findings addressed 2026-03-14):
  1. Context: multi-resolver (git, workspace, event, registry), context_snapshot_id contract
  2. PackageSnapshot: explicit binding surface added
  3. Operative: typed, not free string
  4. Audit surface: topology vs traversal distinction clarified in docstrings
  5. Mutable defaults: field(default_factory=list) throughout

No external dependencies. Dataclasses + stdlib only.
"""
from __future__ import annotations
from dataclasses import dataclass, field
from typing import Callable, Optional, Protocol


# ── Functor categories ─────────────────────────────────────────────────────

class F_D:  """Deterministic — zero ambiguity, pass/fail."""
class F_P:  """Probabilistic — agent/LLM, bounded ambiguity."""
class F_H:  """Human — persistent ambiguity, judgment required."""


# ── Approval vocabulary ────────────────────────────────────────────────────

@dataclass(frozen=True)
class Consensus:
    n: int
    m: int

    def __post_init__(self):
        if self.n < 1 or self.m < 1 or self.n > self.m:
            raise ValueError(f"consensus({self.n}/{self.m}): n must be 1..m")

    def __repr__(self):
        return f"consensus({self.n}/{self.m})"

def consensus(n: int, m: int) -> Consensus:
    return Consensus(n, m)


# ── Operative condition (Finding 3) ────────────────────────────────────────
# Typed prime-axis conditions. No free strings.

@dataclass(frozen=True)
class Operative:
    """
    Typed operability condition derived from prime axes.

    Prime axes: approved, superseded.
    Conditions compose from them — no ad hoc strings.

    Examples:
        Operative(approved=True)                        # operative when approved
        Operative(approved=True, not_superseded=True)   # operative when approved and not superseded
    """
    approved: bool = True
    not_superseded: bool = False

    def __repr__(self):
        parts = []
        if self.approved:
            parts.append("approved")
        if self.not_superseded:
            parts.append("not superseded")
        return " and ".join(parts) if parts else "always"

# Convenience constants
OPERATIVE_ON_APPROVED            = Operative(approved=True)
OPERATIVE_ON_APPROVED_NOT_SUPERSEDED = Operative(approved=True, not_superseded=True)


# ── Context resolver (Finding 1) ───────────────────────────────────────────
# Multi-resolver; digest is the constitutional binding; runtime derives context_snapshot_id.

_CONTEXT_SCHEMES = ("git://", "workspace://", "event://", "registry://")

@dataclass
class Context:
    """
    Externally-located, snapshot-bound constraint dimension.

    locator: URI using a known scheme — used for discovery and retrieval.
        git://      — versioned document in a git repository
        workspace:// — loaded from the local .ai-workspace/
        event://    — derived from a package-definition event stream
        registry:// — from a shared Genesis context registry

    digest: sha256 content hash — the constitutional binding for replay.
        The floating URI is not authoritative. The digest is.

    The runtime derives an immutable context_snapshot_id from (locator + digest).
    Replay binds to context_snapshot_id, not the live URI.
    """
    name: str
    locator: str    # e.g. "git://github.com/org/repo//ctx/file.yml@abc123"
    digest: str     # "sha256:..."

    def __post_init__(self):
        if not self.digest.startswith("sha256:"):
            raise ValueError(f"Context.digest must start with 'sha256:': {self.digest!r}")
        if not any(self.locator.startswith(s) for s in _CONTEXT_SCHEMES):
            raise ValueError(
                f"Context.locator must use a known scheme {_CONTEXT_SCHEMES}: {self.locator!r}"
            )


# ── Core constructs ────────────────────────────────────────────────────────

@dataclass
class Rule:
    name: str
    approve: Consensus
    dissent: str = "none"       # "required" | "recorded" | "none"
    provisional: bool = False

    def __post_init__(self):
        if self.dissent not in ("required", "recorded", "none"):
            raise ValueError(f"Rule.dissent must be required|recorded|none, got {self.dissent!r}")


_OPERATOR_SCHEMES = ("agent://", "exec://", "check://", "metric://", "fh://")

@dataclass
class Operator:
    name: str
    category: type              # F_D | F_P | F_H
    uri: str

    def __post_init__(self):
        if self.category not in (F_D, F_P, F_H):
            raise TypeError(f"Operator.category must be F_D, F_P, or F_H")
        if not any(self.uri.startswith(s) for s in _OPERATOR_SCHEMES):
            raise ValueError(
                f"Operator URI must use a known scheme {_OPERATOR_SCHEMES}: {self.uri!r}"
            )


@dataclass
class Asset:
    """
    Typed asset class. Instances are produced by traversing edges.

    governing_snapshots: populated at runtime on instances that cross package
        boundaries — carries the full provenance map of upstream constitutional
        surfaces. Declared here as a type-level annotation; runtime populates it.
    """
    name: str
    id_format: str
    lineage: list[Asset] = field(default_factory=list)
    markov: list[str] = field(default_factory=list)
    operative: Optional[Operative] = None


@dataclass
class Edge:
    name: str
    source: Asset | list[Asset]     # list[Asset] = product arrow A × B × ...
    target: Asset
    using: list[Operator] = field(default_factory=list)
    confirm: str = "markov"         # "question" | "markov" | "hypothesis"
    rule: Optional[Rule] = None
    context: list[Context] = field(default_factory=list)
    co_evolve: bool = False         # True = both assets mutable in same iterate() call

    def __post_init__(self):
        if self.confirm not in ("question", "markov", "hypothesis"):
            raise ValueError(
                f"Edge.confirm must be question|markov|hypothesis, got {self.confirm!r}"
            )
        if self.co_evolve and not isinstance(self.source, list):
            raise ValueError(
                f"Edge '{self.name}': co_evolve=True requires source to be a list [A, B]"
            )


# ── WorkingSurface ─────────────────────────────────────────────────────────

@dataclass
class WorkingSurface:
    """
    Structured side-effect product of every Job execution.

    Two-surface model:
        events:            control surface — appended to event log, immutable once
                           written, drives the scheduler.
        artifacts:         trace surface — evidence file paths. Answers "why did
                           this converge?" Primary input to Auditor (Scenario 3)
                           and arbitration comparator (Scenario 2).
        context_consumed:  provenance — Contexts read during execution.
                           Enables exact historical replay under the same law.

    is_auditable() invariant: a Job producing no artifacts has no convergence
    evidence. The richer the surface, the better the arbitration signal.
    """
    events: list[dict] = field(default_factory=list)
    artifacts: list[str] = field(default_factory=list)
    context_consumed: list[Context] = field(default_factory=list)

    def is_auditable(self) -> bool:
        return bool(self.artifacts or self.events)


# ── Evaluator ──────────────────────────────────────────────────────────────

@dataclass
class Evaluator:
    """
    Typed convergence predicate — the stopping condition for iterate().

    category determines the evaluation regime:
        F_D — deterministic: computable, pass/fail, no LLM required
        F_P — probabilistic: LLM/agent assessment, bounded ambiguity
        F_H — human: judgment gate, persistent ambiguity

    A Job with no Evaluators cannot converge (Bootloader §XVII: evaluators ≠ ∅).
    """
    name: str
    category: type   # F_D | F_P | F_H
    description: str
    command: str = ""  # F_D only: shell command the kernel runs; empty = F_P/F_H or misconfigured

    def __post_init__(self):
        if self.category not in (F_D, F_P, F_H):
            raise TypeError(
                f"Evaluator.category must be F_D, F_P, or F_H, got {self.category!r}"
            )


# ── Job ────────────────────────────────────────────────────────────────────

@dataclass
class Job:
    """
    Typed transform — the missing primitive that gives the system worker typing.

    Job<A,B> = execution contract for a graph edge:
        Asset<A> → (Asset<B>, WorkingSurface)

    The source/target Asset types from the wrapped Edge are the type parameters
    A and B. The Job type signature IS the worker capability discriminator —
    a Worker executes this Job iff its signature matches.

    Three scheduling cases derive structurally from Job types:
        Scenario 1 (multi-stack):  workers have different source/target types → disjoint
        Scenario 2 (tournament):   workers share the same type → candidate slots differ
        Scenario 3 (role split):   workers have disjoint target types → all concurrent

    Invariant: evaluators must not be empty (Bootloader §XVII).
    """
    edge: Edge
    evaluators: list[Evaluator] = field(default_factory=list)

    def __post_init__(self):
        if not self.evaluators:
            raise ValueError(
                f"Job '{self.edge.name}': evaluators must not be empty "
                f"(Bootloader §XVII invariant)"
            )

    @property
    def source_type(self) -> Asset | list[Asset]:
        """Input type A — what this Job reads."""
        return self.edge.source

    @property
    def target_type(self) -> Asset:
        """Output type B — what this Job writes. Uniquely identifies write territory."""
        return self.edge.target


# ── Worker ─────────────────────────────────────────────────────────────────

@dataclass
class Worker:
    """
    Actor defined structurally by its Job type signature.

    Role = can_execute set. No external actor registry or prose write-territory
    rules needed — the type system enforces capability.

    Scheduling rule:
        workers with disjoint writable_types run in parallel (safe)
        workers with overlapping writable_types must serialise (conflict)

    Covers all three scenarios:
        Scenario 1: different stacks → different target types → no conflict
        Scenario 2: same Job type → candidate slots separate target types → no conflict
        Scenario 3: specialised roles → disjoint write sets → all concurrent
    """
    id: str
    can_execute: list[Job] = field(default_factory=list)

    def __post_init__(self):
        if not self.can_execute:
            raise ValueError(f"Worker '{self.id}': can_execute must not be empty")

    @property
    def writable_types(self) -> set[str]:
        """Target asset type names — this worker's write territory."""
        return {j.target_type.name for j in self.can_execute}

    @property
    def readable_types(self) -> set[str]:
        """Source asset type names — what this worker consumes."""
        result: set[str] = set()
        for j in self.can_execute:
            src = j.source_type
            if isinstance(src, list):
                result.update(a.name for a in src)
            else:
                result.add(src.name)
        return result

    def conflicts_with(self, other: Worker) -> bool:
        """True if serialisation is required — overlapping write territory."""
        return bool(self.writable_types & other.writable_types)


# ── iterate() protocol ─────────────────────────────────────────────────────

class IterateProtocol(Protocol):
    """
    Constitutional contract for the universal iteration function.

    GTL declares the signature. The engine (.genesis/) implements it.
    Job is a parameter — the iterator is domain-blind.

        iterate(job, evaluator_fn, asset) → (Asset<B>, WorkingSurface)

    Loops until evaluator_fn(candidate) is True, accumulating WorkingSurface.
    The fixed-point combinator over Job × Evaluator.
    """
    def __call__(
        self,
        job: Job,
        evaluator_fn: Callable[[Asset], bool],
        asset: Asset,
    ) -> tuple[Asset, WorkingSurface]: ...


@dataclass
class Overlay:
    """
    Lawful package extension (add_*) or restriction (restrict_to).
    Both forms require approve — overlay activation is a governance act.

    Restriction overlays ARE profiles. No separate profile mechanism.
    """
    name: str
    on: "Package"
    restrict_to: Optional[list[str]] = None
    add_assets: list[Asset] = field(default_factory=list)
    add_edges: list[Edge] = field(default_factory=list)
    add_operators: list[Operator] = field(default_factory=list)
    add_rules: list[Rule] = field(default_factory=list)
    add_contexts: list[Context] = field(default_factory=list)
    max_iter: Optional[int] = None
    approve: Optional[Consensus] = None

    def __post_init__(self):
        if self.approve is None:
            raise ValueError(f"Overlay '{self.name}' must declare approve=consensus(n/m)")
        if self.restrict_to is not None and any([
            self.add_assets, self.add_edges, self.add_operators,
            self.add_rules, self.add_contexts,
        ]):
            raise ValueError(f"Overlay '{self.name}': restrict_to and add_* are mutually exclusive")


# ── PackageSnapshot (Finding 2) ────────────────────────────────────────────

@dataclass
class PackageSnapshot:
    """
    Runtime artifact — projection of package-definition events at a point in time.
    Never authored directly in GTL. Produced by the runtime when an overlay is activated
    through the governance pipeline.

    Constitutional binding contract:
        Every work event (edge_started, iteration_completed, edge_converged) must carry
        package_snapshot_id. This is non-optional. It is the mechanism by which exact
        historical replay under the correct law is possible.

    governing_snapshots[]:
        Artifacts crossing package boundaries carry this field — a list of all upstream
        snapshot IDs that materially shaped the artifact. Downstream work traces full
        provenance, not just the immediate parent snapshot.
    """
    snapshot_id: str        # e.g. "snap-genesis-obligations-v1.2.0"
    package_name: str
    version: str
    activated_at: str       # ISO 8601
    activated_by: str       # ID of the governance event that activated this snapshot

    def to_dict(self) -> dict:
        """Serialise to package_snapshot_activated event payload."""
        return {
            "event_type": "package_snapshot_activated",
            "snapshot_id": self.snapshot_id,
            "package_name": self.package_name,
            "version": self.version,
            "activated_at": self.activated_at,
            "activated_by": self.activated_by,
        }

    def work_binding(self) -> dict:
        """Minimal fields every work event must carry."""
        return {
            "package_name": self.package_name,
            "package_snapshot_id": self.snapshot_id,
        }


# ── Package ────────────────────────────────────────────────────────────────

@dataclass
class Package:
    """
    Bounded constitutional world.

    Validated at construction — all invariants enforced immediately.
    Runtime serialises Package + governance event → PackageSnapshot.

    Audit surfaces (Finding 4):
        to_mermaid() renders TOPOLOGY — static package structure, background context.
        The primary operational human surface is TRAVERSAL — where work is now relative
        to the topology. Traversal is generated by the runtime from PackageSnapshot × work_events.
        These are distinct: topology does not change during a work run; traversal does.

    requirements: canonical list of REQ-* keys this Package is responsible for.
        Used by check-req-coverage as the authoritative source — no grepping.
        Empty = grep fallback (legacy mode).
    """
    name: str
    assets: list[Asset] = field(default_factory=list)
    edges: list[Edge] = field(default_factory=list)
    operators: list[Operator] = field(default_factory=list)
    rules: list[Rule] = field(default_factory=list)
    contexts: list[Context] = field(default_factory=list)
    overlays: list[Overlay] = field(default_factory=list)
    requirements: list[str] = field(default_factory=list)

    def __post_init__(self):
        self._validate()

    def _validate(self):
        errors = []
        declared_ops = {op.name for op in self.operators}

        for edge in self.edges:
            # Closed operator surface
            for op in edge.using:
                if op.name not in declared_ops:
                    errors.append(
                        f"Edge '{edge.name}': operator '{op.name}' not declared in package"
                    )
            # co_evolve consistency
            if edge.co_evolve and not isinstance(edge.source, list):
                errors.append(
                    f"Edge '{edge.name}': co_evolve=True requires source to be a list [A, B]"
                )

        if errors:
            raise ValueError(
                "Package validation failed:\n" + "\n".join(f"  - {e}" for e in errors)
            )

    def describe(self) -> str:
        lines = [f"Package: {self.name}"]
        lines.append(f"  assets    ({len(self.assets)}): " + ", ".join(a.name for a in self.assets))
        lines.append(f"  operators ({len(self.operators)}): " + ", ".join(o.name for o in self.operators))
        lines.append(f"  rules     ({len(self.rules)}): " + ", ".join(r.name for r in self.rules))
        lines.append(f"  contexts  ({len(self.contexts)}): " + ", ".join(c.name for c in self.contexts))
        lines.append(f"  edges     ({len(self.edges)}):")
        for e in self.edges:
            src = (
                " × ".join(a.name for a in e.source)
                if isinstance(e.source, list)
                else e.source.name
            )
            arrow = "<->" if e.co_evolve else "->"
            gov = f"  [govern: {e.rule.name}]" if e.rule else ""
            ops = ", ".join(o.name for o in e.using)
            lines.append(f"    {e.name}: {src} {arrow} {e.target.name}  confirm={e.confirm}{gov}")
            lines.append(f"      using: {ops}")
        if self.overlays:
            lines.append(f"  overlays  ({len(self.overlays)}):")
            for ov in self.overlays:
                if ov.restrict_to:
                    lines.append(
                        f"    {ov.name}: restrict to [{', '.join(ov.restrict_to)}]"
                        + (f" max_iter={ov.max_iter}" if ov.max_iter else "")
                    )
                else:
                    lines.append(f"    {ov.name}: additive")
        return "\n".join(lines)

    def to_mermaid(self, overlay: Optional[Overlay] = None) -> str:
        """
        Render package TOPOLOGY as a Mermaid flowchart.

        This is TOPOLOGY — the static package structure. It is background context,
        not the primary operational human surface. The operational surface is TRAVERSAL:
        where work is now relative to this topology, generated from PackageSnapshot × work_events.

        If an overlay with restrict_to is supplied, only those assets/edges are shown.
        LLM-generated Mermaid from Package.describe() is acceptable for documentation.
        Deterministic to_mermaid() is warranted when review-grade projection is required.
        """
        active_asset_names: Optional[set[str]] = None
        if overlay and overlay.restrict_to:
            active_asset_names = set(overlay.restrict_to)

        def _node(a: Asset) -> str:
            label = a.name.replace("_", " ")
            if a.operative:
                return f'  {a.name}(["{label}\\noperative: {a.operative}"])'
            return f'  {a.name}["{label}"]'

        def _visible(a: Asset) -> bool:
            return active_asset_names is None or a.name in active_asset_names

        lines = ["```mermaid", "graph LR"]
        lines.append("  classDef governed fill:#ffeeba,stroke:#d4a017")
        lines.append("  classDef product  fill:#d4edda,stroke:#28a745")
        lines.append("  classDef coevolve fill:#cce5ff,stroke:#004085")

        for a in self.assets:
            if _visible(a):
                lines.append(_node(a))

        for e in self.edges:
            sources = e.source if isinstance(e.source, list) else [e.source]
            if not all(_visible(s) for s in sources) or not _visible(e.target):
                continue

            ops_label = ", ".join(o.name for o in e.using[:2])
            if len(e.using) > 2:
                ops_label += f" +{len(e.using)-2}"
            edge_label = f"|{ops_label} [{e.confirm}]|"

            if e.co_evolve:
                a, b = sources[0], sources[1]
                lines.append(f"  {a.name} <-->|co_evolve| {b.name}")
                lines.append(f"  {a.name}:::coevolve")
                lines.append(f"  {b.name}:::coevolve")
            elif len(sources) > 1:
                join = "join_" + "_".join(s.name for s in sources)
                join_label = " × ".join(s.name for s in sources)
                lines.append(f'  {join}(("{join_label}"))')
                for s in sources:
                    lines.append(f"  {s.name} --> {join}")
                lines.append(f"  {join} --{edge_label}--> {e.target.name}")
                lines.append(f"  {join}:::product")
            else:
                src = sources[0]
                lines.append(f"  {src.name} --{edge_label}--> {e.target.name}")
                if e.rule:
                    lines.append(f"  {e.target.name}:::governed")

        lines.append("```")
        return "\n".join(lines)
