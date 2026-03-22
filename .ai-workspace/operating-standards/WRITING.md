# Writing Principles for Human-Facing Documents

**Governance**: Maintained by the methodology author. Read-only for agents.

**NOTE TO LLM**: These principles apply whenever you write any human-facing document — ADRs, user guides, README files, comment posts, release notes, intent documents, or any prose produced for a human reader. Apply them before finalising output.

**Original author**: Dimitar Popov. Adapted from ADR Writing Principles (2026-03-07) for general use.

---

## The Audience

Sophisticated, time-scarce readers — engineers, decision-makers, technical leads. They can reason. The document's job is to deliver the premises, not the conclusions.

---

## 1. Assume Intelligence

State facts. The reader draws the inference. Do not write the conclusion the reader is supposed to reach — write the information that produces it.

**Wrong**: *Better prompts do not close the governance gap. The issue is not instruction quality — it is whether a formal methodology governs what AI builds.*
**Right**: *The differentiator is what the AI is building against.*

---

## 2. Eliminate Contrast Steering

"Not X, it is Y" and "not X, but Y" structures double the cognitive load of a claim. State the positive directly.

**Wrong**: *Legacy code is not primarily a technology problem. It is a knowledge problem.*
**Right**: *Legacy code encodes decades of business rules in a form that is expensive to maintain and difficult to explain.*

---

## 3. No Rhetorical Flourishes

Remove dramatic em-dash endings that restate what was just said, speculative premises used to set up a claim, and qualifiers inserted for rhythm rather than meaning.

Cut on sight:
- `— not at delivery` — restatement
- `As construction becomes fully automated,` — speculative premise doing rhetorical work
- `when the moment of examination arrives` — dramatic; say *under examination*
- `— current or future —` — inserted for sweep

---

## 4. Use the Audience's Vocabulary

Calibrate terminology to the reader's domain. Use terms that carry precise meaning for that audience. Do not introduce them and then explain them.

---

## 5. Tool vs. Methodology

A specific implementation is one of several approaches to the same methodology. The methodology is the argument. Tools are replaceable and should be positioned as such.

**Wrong**: *Genesis addresses this problem.*
**Right**: *Genesis is one implementation of spec-driven development.*

---

## 6. No Setup Paragraphs

Open sections with substance. A paragraph that describes what the section is about before delivering its content can be deleted.

**Wrong**: *This section discusses how spec-driven development changes the relationship with legacy systems.* [followed by the actual content]
**Right**: Start with the content.

---

## 7. One Idea Per Sentence

Each sentence carries one claim. A sentence that requires the reader to hold a contrast while evaluating a new claim should be split or rewritten as a direct positive statement.

---

## Consequences

- Documents are shorter and more credible
- Weak claims are immediately visible — the argument stands on its facts
- AI-assisted drafting requires an additional pass against these principles; LLMs default to contrast framing and rhetorical padding
- Revision is clean: removing a sentence that states a positive fact does not break surrounding logic
