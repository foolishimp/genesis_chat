# /gen-review — Human Evaluator Gate

Explicitly surface a pending F_H gate for human review. Use when you want to
review a candidate without running the full gen-start loop.

## Usage

```
/gen-review --feature REQ-F-* [--edge "source→target"]
```

## Instructions

**Step 1 — Load the gate**

Read the feature vector: `.ai-workspace/features/active/{feature}.yml`

Identify the current edge (or use `--edge` override).

Run the engine to get the current candidate and gate criteria:

```bash
PYTHONPATH=.genesis python -m genesis gaps \
  --feature {F} --edge {E}
```

**Step 2 — Present candidate**

```
REVIEW REQUEST
==============
Feature:  {F}
Edge:     {source}→{target}

CANDIDATE:
{the current asset — read from workspace}

F_H CRITERIA:
{list evaluator descriptions for F_H evaluators on this edge}

F_D STATUS:
  {passing evaluator names} — pass
  {failing evaluator names} — fail
```

**Step 3 — Collect decision**

Ask the user: approve or reject?

On **approve**: emit `approved` via the engine and go to Step 1:
```bash
PYTHONPATH=.genesis python -m genesis emit-event \
  --type approved \
  --data '{"kind": "fh_review", "feature": "{F}", "edge": "{E}", "actor": "human"}'
```

On **reject**: emit `assessed` with rejection, stop. Report to user.
```bash
PYTHONPATH=.genesis python -m genesis emit-event \
  --type assessed \
  --data '{"kind": "fh_review", "result": "reject", "feature": "{F}", "edge": "{E}", "actor": "human", "reason": "{reason}"}'
```
