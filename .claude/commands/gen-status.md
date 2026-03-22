# /gen-status — Workspace Status

Show current convergence state derived from the event stream. Read-only.

## Usage

```
/gen-status [--feature REQ-F-*]
```

## Instructions

**Step 1 — Run the engine**

```bash
PYTHONPATH=.genesis python -m genesis gaps \
  [--feature {F}]
```

Parse stdout as JSON.

**Step 2 — Show state**

```
WORKSPACE STATUS
  Package:   {scope.package}
  Workflow:  {active-workflow.json → workflow} v{active-workflow.json → version}
  Delta:     {total_delta}
  Status:    {CONVERGED | IN PROGRESS}

FEATURES:
  Active:    {list from .ai-workspace/features/active/}
  Completed: {list from .ai-workspace/features/completed/}

EDGES:
  ✓ source→target    (delta=0)
  ✗ source→target    delta={N} — failing: {evaluator names}

EVENTS: {count} total  (last: {most recent event_type})
```

All data is derived from `.ai-workspace/events/events.jsonl` and the workspace.
Never infer state — project from events.
