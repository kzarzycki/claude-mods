---
name: loop-me
description: Grill the user into implementable specs for the recurring workflows they want to build or delegate, kept in this workspace.
disable-model-invocation: true
argument-hint: "A workflow to design, or nothing to go find one"
---

Run a stateful `/grilling` session whose only output is **workflow** specs. Create, edit and delete specs as the grilling settles things.

## The loop lens

A **loop** is a recurring pattern in the user's life: their career, their week, their morning, one repeated activity. Seeing a life as loops within loops shows how predictable its activities are, which is what makes them worth **delegating**. Use the lens to find loops worth specifying, including ones the user has not noticed.

A **workflow** is the spec of one loop; the loop is its running instance. Workflows live in `workflows/*.md` and are the source of truth.

## Vocabulary

Shared terms to use when a workflow calls for them, never a checklist. A workflow needs no AI, no checkpoint and no schedule unless the grilling shows it does.

- **Trigger**: what fires each run: an **event** (a new email, a new issue), usually the more efficient, or a **schedule** (every morning).
- **Checkpoint**: where the user verifies or decides. Some workflows have none.
- **Push right**: defer the checkpoint as late as it will go, so the user is asked once, with everything prepared.
- **Brief**: what a checkpoint presents: a tight, decision-ready summary of what was produced and why, linking to the asset, never the raw output. Review speed matters most.

## Done

A spec is done when an implementer agent could build it without asking a single question.

## The workspace

- `workflows/*.md`: one spec per workflow.
- `NOTES.md`: the user's world: tools, channels they process, and their own terms for both. While it is thin, interview them about that world before specifying anything. Record canonical terms here as fuzzy ones get sharpened.
