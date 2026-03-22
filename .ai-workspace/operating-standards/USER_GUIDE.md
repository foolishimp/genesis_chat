# User Guide Writing Conventions

**Governance**: Maintained by the methodology author. Read-only for agents.

**NOTE TO LLM**: If this file is referenced in a prompt, it is an active instruction to write or update a user guide in the format and style specified here. Apply WRITING.md principles throughout.

---

## Purpose of a User Guide

A user guide answers: *what do I run, and what does it do?* It is not a tutorial, a design document, or a reference manual. It is the minimal surface a practitioner needs to operate the tool correctly on day one and recover when something goes wrong.

---

## Structure

```markdown
# {Tool Name} — User Guide

## Quick Start
Three commands maximum. The reader should be operational in under two minutes.

## Commands
One section per command. Each section:
  - Signature line (usage)
  - What it does — one sentence
  - Key flags — table
  - Output — what to expect
  - Common errors — what goes wrong and why

## Operating Loop
The repeated workflow. Show the cycle a practitioner runs daily, not every possible combination.

## Concepts
Only concepts required to operate the tool correctly. Not background theory.
If a concept is in the bootloader or a spec, link — do not re-explain.

## Troubleshooting
Specific symptoms → specific causes → specific fixes. No generic advice.
```

---

## Style Rules

Apply all principles from `operating-standards/WRITING.md`. Additional rules for user guides:

**Commands before explanations.** Show the command first, explain after. Readers scan for what to type.

**Concrete over abstract.** Show real output, real paths, real flags. Avoid placeholder-heavy examples that require translation before use.

**Error messages verbatim.** When documenting errors, quote the actual error text. Do not paraphrase.

**No version numbers in body text.** Versions change; body text does not. Put the version in the document header only.

**No "simply" or "just".** These words signal the author thinks something is easy. If it were simple the reader would not be reading the guide.

---

## What Belongs in the Guide vs. Elsewhere

| Content | Where it goes |
|---------|--------------|
| How to run commands | User guide |
| Why the architecture works this way | ADR |
| What the spec requires | GTL spec / bootloader |
| What changed between versions | Release notes |
| Open design questions | Comment post (STRATEGY or GAP) |

---

## Versioning

The user guide carries a version header matching the tool version it documents:

```markdown
**Tool version**: 0.1.4
**Updated**: YYYY-MM-DD
```

Update the header when any command behaviour, flag, or output format changes.
