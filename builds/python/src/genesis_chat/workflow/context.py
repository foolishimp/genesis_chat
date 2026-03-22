# Implements: REQ-F-CTX-001
# Implements: REQ-F-TRACE-001
"""Context assembly from target project workspace."""
from __future__ import annotations

from pathlib import Path


def assemble_context(workspace: str, feature: str | None = None, max_events: int = 10) -> str:
    """
    Assemble a context pack from the target workspace.
    Events go to the TARGET project stream (REQ-F-TRACE-001) — this module reads, not writes.
    """
    ws = Path(workspace)
    sections: list[str] = []

    # Recent events from target project
    events_path = ws / ".ai-workspace" / "events" / "events.jsonl"
    if events_path.exists():
        lines = events_path.read_text().strip().splitlines()
        recent = lines[-max_events:]
        sections.append("## Recent events (target project)\n" + "\n".join(recent))

    # Active feature vector if specified
    if feature:
        feat_path = ws / ".ai-workspace" / "features" / "active" / f"{feature}.yml"
        if feat_path.exists():
            sections.append(f"## Feature: {feature}\n" + feat_path.read_text().strip())

    # Latest design post from target project
    comments_dir = ws / ".ai-workspace" / "comments" / "claude"
    if comments_dir.exists():
        posts = sorted(comments_dir.glob("*.md"), reverse=True)
        if posts:
            content = posts[0].read_text().strip()
            sections.append(f"## Latest design post ({posts[0].name})\n{content[:500]}")

    return "\n\n".join(sections) if sections else "(no context available for this workspace)"
