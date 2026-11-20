---
name: retro
description: "Run a retrospective on a coding session and propose changes to the agent's environment (checks, coding standards, steering files, tooling, information access) that would improve future runs."
disable-model-invocation: true
---

Run a retrospective: propose improvements to the coding agent's **environment**, not to the agent, so future runs go better. Read the primary sources for the session the user names, searching this machine's session logs if needed; default to the current session. Present the candidates to the user, most severe first.

Before drafting recommendations, read and follow the `writing-for-agents` skill for agent-facing writing. If it is unavailable, state that and use the project's agent-writing conventions.

## Where to look

- **Navigation**: the session spent long finding something, or files have hidden dependencies. Would a **navigation pointer** have helped?
- **Automated checks**: the agent made a mistake a lint, type, test or filesystem check could catch. Read the repo's own check commands and CI first, so an existing check that sits unwired or silently broken is the finding, not a reinvention. A repo with no **guardrail** (no pre-commit hook and no CI job running lint, typecheck or tests) is itself a finding.
- **Coding standards**: the reviewer missed a mistake. A **mechanical** violation (a fixed syntactic pattern, a banned API, an import shape, a file-location rule) gets a deterministic check in whichever of the repo's linter, a pre-commit hook or a CI job is cheapest. Prefer building the check over merely proposing it or writing a prose rule, within the project's authorization rules. Only **judgement calls** (cross-file consistency, matching the surrounding style) go in `CODING_STANDARDS.md`. Also look for rules to remove or clarify.
- **Steering files**: a large `AGENTS.md`, in the repo or the user's global scope, holds instructions that belong in coding standards or a check, or instructions that change no behaviour at all.
- **Tool economy**: an expensive tool call, or custom tooling (CLIs, MCP servers) that spends tokens badly.
- **Information access**: a crucial fact the agent could not reach, such as teeing dev server output to a log the agent can read, or read-only access to a third-party service.

## Where fixes belong

- The implementer carries the most context pressure (exploration, code, debugging); the reviewer gets a diff and little else. So the reviewer enforces coding standards, not the implementer.
- `CLAUDE.md` / `AGENTS.md` load into every agent's context: keep them sparse, mostly navigation pointers.
- `CODING_STANDARDS.md` is read at review, not implementation. Past about 1,000 lines, move detail into docs and point to it.
- Docs are reference files that other files point to; look for an existing one before writing a new one.
- A skill fits reference material that should announce itself through its description, or a user-invoked command.
