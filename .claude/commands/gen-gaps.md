# /gen-gaps — Show Convergence State

Runs the engine's gap analysis over the current workspace and reports which edges
are converged and which have failing evaluators.

## Usage

```
/gen-gaps [--feature REQ-F-*] [--edge "source→target"]
```

## Instructions

**Step 1 — Run the engine**

```bash
PYTHONPATH=.genesis python -m genesis gaps \
  [--feature {F}] [--edge {E}]
```

Parse stdout as JSON.

**Step 2 — Report**

The engine returns:

```json
{
  "converged": true|false,
  "total_delta": N,
  "jobs_considered": N,
  "gaps": [
    {
      "edge": "source→target",
      "delta": N,
      "failing": ["evaluator_name", ...],
      "passing": ["evaluator_name", ...],
      "delta_summary": "delta = N — N evaluator(s) failing: ..."
    }
  ]
}
```

Display:

```
CONVERGENCE STATE
  Jobs:     {jobs_considered}
  Delta:    {total_delta}
  Status:   {CONVERGED | IN PROGRESS}

EDGES:
  ✓ source→target          (all evaluators pass)
  ✗ source→target          delta={N}
      failing: evaluator_name — {detail}

NEXT: /gen-start [--auto] [--human-proxy]
```

If `converged: true`, all edges have delta=0. The workspace is ready for a new feature.

If `converged: false`, list the failing edges and their evaluator details so the user
can decide which edge to target with `/gen-iterate`.
