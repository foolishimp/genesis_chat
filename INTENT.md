# Intent: genesis_chat

**ID**: INT-001
**Status**: Draft
**Profile**: spike

---

## Problem

Genesis projects are built through single-agent CLI sessions. There is no coordination
layer for multiple AI agents and humans to work together on a genesis project through a
shared channel. When multiple agents are involved, they operate in separate sessions with
no shared communication surface — handoffs are manual, F_H gates are CLI prompts, and
there is no way for agents to observe each other's work in real time.

The GTL F_D→F_P→F_H escalation chain governs construction at build time but has no
runtime manifestation as a multi-participant interaction surface.

---

## Value Proposition

genesis_chat provides a channel where human and multiple AI agents coordinate software
construction using genesis workflows. An incoming message is an intent asset — it resolves
through the same F_D→F_P→F_H chain that governs the build:

- **F_D**: registered commands execute deterministically (status, gaps, approve)
- **F_P**: work intents are routed to an agent + workflow (gen-start, gen-iterate, spike)
- **F_H**: approval gates surface in the channel as prompts awaiting human response

Every agent action is traceable to the event stream. Write territory rules apply in the
channel exactly as they do in the filesystem. The channel is the construction UI;
the event stream and spec are the persistent substrate.

The same formal model that governs construction governs the channel. No new primitives.

---

## Scope (V1 spike)

- **EchoAdapter** — local CLI channel (stdin/stdout); no external platform dependency
- **Agent registry** — YAML-configured agent slots with identity and write territory
- **Workflow bindings** — gen-start and gen-iterate as dispatchable workflows
- **Message dispatcher** — F_D command match → F_P work intent → F_H gate
- **F_H gate in channel** — approval prompts surface as channel messages; human replies
- **Two agent slots** — claude (primary) + mock_agent (second slot for multi-agent proof)

**Out of scope for spike**: Slack/Discord adapters, vector cache, URI scanning, full
multi-agent concurrent iteration, tool registry integration.

**Done when**: human types a work intent in the channel, an agent picks it up, runs a
genesis workflow iteration on a target project, and posts the result back. F_H gate
surfaces as a channel prompt if triggered.
