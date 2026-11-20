---
name: to-tickets
description: Break a plan, spec, or the current conversation into tracer-bullet tickets that declare their blocking edges, and publish them to the configured tracker.
disable-model-invocation: true
---

# To Tickets

Break a plan, spec, or conversation into **tickets**: tracer-bullet vertical slices, each naming the tickets that **block** it.

GitHub Issues is the default tracker; `docs/agents/issue-tracker.md` names its realization file (for GitHub, the `engineering-loop` skill's `github.md`), and the repo's agent instructions map the triage labels (default names otherwise). If that file is missing, tell the user to create it: the project template writes one.

## Draft

Work from the conversation. If the user passes a reference (spec path, issue number or URL), read its full body and comments. Explore the code as far as the slicing needs, use the `GLOSSARY.md` vocabulary, and respect the ADRs in the area. Look for prefactoring that makes the change easy; it goes first.

- Each slice cuts a narrow but complete path through every layer (schema, API, UI, tests), never one layer on its own.
- A finished slice is demoable or verifiable on its own.
- Each slice fits one fresh context window.
- A ticket's blockers are only the tickets that genuinely gate it; a ticket with none can start immediately.

A **wide refactor** is the exception: one mechanical change (rename a column, retype a shared symbol) whose blast radius breaks call sites across the codebase at once, so no vertical slice lands green. Sequence it expand–contract:

1. An expand ticket adds the new form beside the old.
2. Migrate tickets, each blocked by the expand and sized by blast radius (per package or directory), move the call sites over while the old form keeps CI green.
3. A contract ticket, blocked by every migrate ticket, deletes the old form.

If even the migrate batches can't stay green alone, they share an integration branch and all block a final integrate-and-verify ticket, the only one that promises green.

## Approve

Present the breakdown as a numbered list: title, blocked by, and the end-to-end behaviour each ticket delivers. Ask whether the granularity is right, whether each edge is a real gate, and what to merge or split. Iterate until the user approves.

## Publish

Render the approved tickets as one complete batch, every ticket's title, body, labels and blockers in dependency order (blockers first), and have the user review it before any issue is created. Publish it following the realization file's issue-batch protocol for approval, markers, resume, creation and relationship wiring rather than improvising tracker commands. Don't close or edit a parent issue; linking the tickets to it is the only change it gets.

- **Real tracker** (GitHub, Linear, …): one issue per ticket in the issue template, linked by the platform's native blocking relationship where it has one, otherwise by the "Blocked by" section. When the source was an existing issue, make each ticket its sub-issue (the realization file's operation). Label each `ready-for-agent` unless told otherwise; the tickets are agent-grabbable by construction.
- **Local files**, when the repo configures them instead: one file per ticket at `.scratch/<feature-slug>/issues/<NN>-<slug>.md`, numbered from `01` in dependency order, in the local template; never one combined file.

Leave file paths and code snippets out of tickets; they go stale. The exception is a prototype snippet (state machine, reducer, schema, type shape) that states a decision more precisely than prose: inline only its decision-rich part and say it came from a prototype.

<issue-template>

## Parent

A reference to the parent issue, when the source was one; otherwise omit this section.

## What to build

The end-to-end behaviour this ticket makes work, from the user's perspective, not a layer-by-layer implementation list.

## Acceptance criteria

- [ ] Criterion 1
- [ ] Criterion 2

## Blocked by

- A reference to each blocking ticket, or "None (can start immediately)". Omit this section when the blockers will be set as native edges (the tracker has a native blocking relationship).

</issue-template>

<local-ticket-template>

# <NN>: <Ticket title>

**What to build:** the end-to-end behaviour this ticket makes work, from the user's perspective.

**Blocked by:** the numbers and titles of the gating tickets, or "None (can start immediately)".

**Status:** ready-for-agent

- [ ] Acceptance criterion 1
- [ ] Acceptance criterion 2

</local-ticket-template>
