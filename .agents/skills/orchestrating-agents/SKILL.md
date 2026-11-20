---
name: orchestrating-agents
description: Start, message, wait on, watch, list and close agent sessions through one backend (native subagents, Omnigent or herdr-link), with reports as files and questions as files. Use when starting a child agent such as a worker, verifier or lead, waiting on or collecting the agents you started, or choosing which backend runs them. Running or repairing an Omnigent install itself is operating-omnigent's.
---

# Orchestrating agents

## Backend

Agents are started, messaged, listed and closed through one backend, the first that holds:
a pin in the project's instructions (under the engineering loop, loop.md's line
`Orchestration backend: <name>`); the same line in the developer's personal instructions;
the session you run in, read from its environment (`OMNIGENT=1` is omnigent,
`HERDR_ENV=1` is herdr); else native. Then read that backend's file:
[backends/native.md](backends/native.md), [backends/omnigent.md](backends/omnigent.md) or
[backends/herdr-link.md](backends/herdr-link.md). Only that line names a backend: an
instruction about which CLI or model to use is not one, and never turns a child into a
separate process outside the backend, since nothing then lists, watches or closes it.

Each file gives the backend's operations: **start** a child with its brief, **message**
it, **wait** for its report, **watch** children nothing waits on, **list** them and
**close** them; Omnigent's also **approves** a child's pending approval prompt
(`approve`), on whatever authority the project's instructions give, and **broadcasts** one
message to many sessions at once (`broadcast`); a long-lived supervisor runs as a user
service that restarts it and survives a reboot (`supervise --registry <file> --install --log <file>`). A `scripts/` path is relative to this skill's folder; run it with
`python3` (standard library only).

## Rules

- **Reports are files.** An agent writes its report to a file and sends only the path to
  whoever started it, through the backend's message operation, then stops. It writes the
  report path once, at the end: whoever waits takes that file as the final report, so
  progress notes go to another file. Text left in
  its own session reaches nobody. A report names each agent's model, and returns only
  what the next step needs; the agent cleans up what it created first, and only that: a
  process it stops by the pid or process group it saved at launch, or by a pattern holding its
  own worktree path once each match's working directory is checked, never by a `pkill -f` or
  `killall` pattern other agents share, since that kills their runs too.
- **Questions are files.** A child never asks the owner, who is not watching it: it
  writes its question to `<report>.question`, replies with that path and stops. Whoever
  started it answers from the brief, the spec and the owner's stated intent, asks the owner
  only when none of them settles it, and sends the answer to the same child.
- **Whoever starts a child collects it.** Keep a wait or a watch on each child you start,
  read its report before you report yourself, and close it once its report is in; never
  end your own work while one is still out, since its report then reaches nobody.
