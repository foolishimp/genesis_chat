# Implements: REQ-F-CORE-001
"""
genesis — GTL-first AI SDLC engine, V1.

Six modules. No more, no less.

    core      — emit, project, EventStream, ContextResolver, workspace_bootstrap
    bind      — bind_fd, bind_fp, select_relevant_contexts, render_delta
    manifest  — PrecomputedManifest, BoundJob (dataclasses)
    schedule  — delta, iterate, schedule
    commands  — gen_start, gen_iterate, gen_gaps, Scope
    __main__  — CLI entry point
"""
__version__ = "0.5.1"
