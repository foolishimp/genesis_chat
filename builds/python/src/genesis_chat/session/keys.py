# Implements: REQ-F-SESS-001
"""Deterministic session key generation.

Session keys uniquely identify an agent's work context: which agent, on which
project, on which feature and edge. Same inputs always produce the same key.

Source reference: OpenClaw src/routing/session-key.ts (~200 LOC).
Our adaptation is ~30 LOC — no multi-account/guild/peer dimensions.
"""
from __future__ import annotations

import hashlib


def session_key(
    agent_id: str,
    project: str,
    feature: str = "main",
    edge: str = "main",
) -> str:
    """Deterministic session key from agent + project + feature + edge.

    The hash suffix prevents collision when names contain special characters.
    The human-readable prefix keeps keys inspectable in logs and claims.
    """
    raw = f"agent:{agent_id}:project:{project}:feature:{feature}:edge:{edge}"
    short_hash = hashlib.sha256(raw.encode()).hexdigest()[:8]
    return f"{agent_id}:{project}:{feature}:{edge}:{short_hash}"
