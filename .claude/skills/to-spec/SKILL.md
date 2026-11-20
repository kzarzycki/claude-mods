---
name: to-spec
description: "Synthesize the current conversation into a spec and publish it to the project issue tracker, without interviewing the user."
disable-model-invocation: true
---

# To Spec

Turn what the conversation and the codebase already establish into a spec. Don't interview the user; the one thing you check with them is the test seams.

`docs/agents/issue-tracker.md` names the tracker's realization file (for GitHub, the `engineering-loop` skill's `github.md`), and the repo's agent instructions map the triage labels (default names otherwise). If that file is missing, tell the user to create it: the project template writes one.

1. Explore the code as far as the spec needs. Use the `GLOSSARY.md` vocabulary and respect the ADRs in the area.
2. Choose the test seams: existing before new, as high as possible, as few as possible (one is ideal). Confirm them with the user.
3. Write the spec in the template below and publish it to the tracker following its realization file, labelled `ready-for-agent`; it needs no further triage. When the conversation starts from an existing issue, the spec goes into that issue instead of a new one, so one piece of work stays one issue: its body becomes the spec under the original text quoted in full, unless a tool owns the issue's body, in which case post the spec as a comment. With no existing issue, file a new one.

Leave out file paths and code snippets; they go stale. The exception is a prototype snippet (state machine, reducer, schema, type shape) that states a decision more precisely than prose: inline only its decision-rich part, within that decision, and say it came from a prototype.

<spec-template>

## Problem Statement

The problem, from the user's perspective.

## Solution

The solution, from the user's perspective.

## User Stories

A long, numbered list covering every aspect of the feature, each in the form:

1. As an <actor>, I want a <feature>, so that <benefit>

## Implementation Decisions

The decisions made: modules built or modified and their changed interfaces, architectural decisions, schema changes, API contracts, specific interactions, technical clarifications from the developer.

## Testing Decisions

What makes a good test here (external behaviour, not implementation details), which modules get tested, and prior art for those tests in the codebase.

## Acceptance

### Before merge

The examples run on the change's branch before review, each a check with its expected result and the reference it checks against (a fixture, a spec, the output of a tool the change did not write).

### After merge

Only the checks that need the merged default branch or a deployed environment, each with its reference, or `none`.

## Out of Scope

What this spec does not cover.

## Further Notes

Anything else about the feature.

</spec-template>
