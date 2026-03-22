# Spec Writing Standard

**Governance**: Maintained by the methodology author. Read-only for agents. Propose changes via `STRATEGY` post.

**Scope**: Applies whenever you write or review a requirements document, intent vector, feature YAML, or acceptance criteria. Applies to specs at every level — intent, requirements, feature decomp, design, ADR.

---

## The Premise

The entire purpose of this system is a **disambiguation pipeline**.

Human intent is ambiguous. Code is unambiguous. Every edge in the SDLC graph reduces ambiguity. The output of each step is the input constraint for the next. The pipeline terminates when the artifact is unambiguous enough to execute.

A spec is a step in that pipeline. Its job is to reduce ambiguity by exactly the amount the next edge requires. No more, no less.

---

## Spec Leads, Code Follows

The specification is the normative constraint surface. Code is downstream — an implementation of the spec, never a replacement for it.

- If implementation outpaces the spec, **stop and bring the spec current** before advancing.
- A codebase that cannot be regenerated from its specification is not under methodological control.
- The spec is aspirational — it describes what we want. Gap analysis (`gen-gaps`) measures the delta to reality. The gap is expected; the inversion is not.
- ADRs refine the spec. They do not replace it.
- Do not mix achieved-state language into the normative surface. The spec says what SHALL be true. Progress tracking belongs elsewhere.

---

## Staged Sufficiency

The sufficiency test is relative to position in the graph, not to implementation.

| Stage | Sufficient means |
|-------|-----------------|
| **Intent** | The `intent → requirements` iteration can begin. Enough context to produce candidate requirements; not required to specify them. |
| **Requirements** | Feature decomposition can converge against this document. Every REQ key is unambiguous enough for a feature vector's `satisfies:` field to be meaningful. |
| **Feature decomp / design** | The construction edge has unambiguous behavioral constraints. A builder reading only this document produces externally equivalent behavior to any other conformant builder. |
| **Implementation spec (feature YAML, ADR)** | Every evaluator criterion is deterministic. No behavioral question is left to the implementer. |

An intent document is not required to specify implementation. A requirements document is not required to specify design. Each artifact specifies exactly what its downstream edge needs to iterate against.

---

## The Sufficiency Test

Before finalising any spec, apply this test relative to its stage:

> **Given only this document, can the next edge begin iteration, and can its evaluators give a definitive pass/fail?**

If the answer is no, the spec has not finished its edge traversal. Identify the ambiguity the next evaluator would encounter and resolve it in the spec.

"Externally equivalent behavior" is the bar for implementation specs — not unique implementation. Module layout, naming, language idioms, and structurally equivalent data choices are builder decisions. Observable state transitions, error conditions, schema fields, algorithm choices where output differs — these are spec territory.

---

## Evaluators Define the Acceptance Criteria

Every spec carries evaluators appropriate to its stage. All three types are legitimate:

| Evaluator | What the spec must supply |
|-----------|--------------------------|
| **F_D** (deterministic) | Criteria precise enough to write as a passing/failing automated test without reading the description |
| **F_P** (agent assessment) | The assessment criteria the agent applies — what a "pass" means, what evidence is required |
| **F_H** (human approval) | The approval criteria the human evaluates against — what they are deciding, not just that they approve |

An F_H criterion that says only "human approves" is underspecified. The human needs to know what they are approving *against*. Name the criteria.

An F_D criterion that requires reading the description to interpret is a criterion that needs rewriting.

---

## Completeness Check

A spec at any stage is complete when:

1. Every evaluator has unambiguous criteria — F_D tests are derivable, F_P assessments are bounded, F_H gates name what is being decided
2. Every behavioral rule has a fully specified algorithm or decision procedure
3. Every schema field has a name, type, and source
4. Every boundary condition (null, empty, missing, conflict, first-run vs reinstall) has an explicit outcome
5. Two builders reading the spec produce implementations with identical externally observable behavior

If any of these fails, the spec has not finished its edge traversal. Return it to iteration.

---

## The Cost of an Incomplete Spec

An incomplete spec does not stall visibly. It produces an implementation. That implementation encodes the builder's resolution of the ambiguity — which may differ from the author's intent. The divergence surfaces later as a bug or rework, after the cost of construction has already been paid.

The disambiguation pipeline exists to make ambiguity bugs impossible at each edge. A spec that passes the sufficiency test for its stage eliminates that class of defect at that step.
