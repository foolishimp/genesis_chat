# Implements: REQ-F-CORE-004
"""
manifest — PrecomputedManifest and BoundJob dataclasses.

The PrecomputedManifest is the output of bind_fd: everything F_D could
compute before F_P sees the problem. The BoundJob carries the assembled
F_P prompt.

No business logic here — pure typed containers.
See ADR-003 for the structure rationale.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from gtl.core import Evaluator, Job


@dataclass
class PrecomputedManifest:
    """
    F_D pre-computation output. The residual gap.

    passing_evaluators are NEVER included in the F_P prompt — they are
    provably outside the ambiguity bounds. Loading them wastes attention.
    See ADR-002, ADR-003.
    """
    job: Job
    current_asset: dict                    # project(stream, source_type) result
    failing_evaluators: list[Evaluator]    # delta > 0 — F_P must address these
    passing_evaluators: list[Evaluator]    # delta = 0 — excluded from F_P manifest
    fd_results: dict[str, Any]             # pytest output, check-tags counts, etc.
    relevant_contexts: dict[str, str]      # {context.name: resolved_text}
    missing_contexts: list[str] = field(default_factory=list)  # contexts that failed to resolve
    delta_summary: str = ""                # "3 tests fail, 2 files untagged"

    @property
    def has_gap(self) -> bool:
        """True if any evaluator is failing."""
        return bool(self.failing_evaluators)

    @property
    def delta(self) -> int:
        """Number of failing evaluators."""
        return len(self.failing_evaluators)


@dataclass
class BoundJob:
    """
    A Job with all Context references resolved.

    prompt carries: INVARIANTS + CURRENT STATE + GAP + RELEVANT CONTEXT
                    + OUTPUT CONTRACT.
    Everything the F_P actor needs. Nothing it doesn't.
    See ADR-003.
    """
    job: Job
    precomputed: PrecomputedManifest
    prompt: str                            # assembled F_P manifest text
    result_path: str = ""                  # where F_P writes its output
