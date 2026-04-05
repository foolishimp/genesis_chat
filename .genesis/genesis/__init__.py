# Implements: REQ-F-CORE-001
"""
genesis — GTL-first AI SDLC engine, V1.

Seven modules.

    core        — emit, project, EventStream, ContextResolver, workspace_bootstrap
    bind        — bind_fd, bind_fp, select_relevant_contexts, render_delta
    manifest    — PrecomputedManifest, BoundJob (dataclasses)
    schedule    — delta, iterate, schedule
    commands    — gen_start, gen_iterate, gen_gaps, Scope
    fp_dispatch — Subprocess transport for F_P actor invocations (ADR-022)
    __main__    — CLI entry point
"""
__version__ = "1.0.3"
