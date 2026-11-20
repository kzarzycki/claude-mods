---
description: Project-wide instructions for claude-mods
applyTo: "**"
---

# claude-mods

Claude Code mods: hooks, tools and panels that change how Claude Code works.

- Mods run in-process through Claude Code's `$` hook API, built on Claude Code 2.1.288; older versions won't load them. The README's Install section names the version they're tested on.
- Work in a worktree of your own, never in another session's: `docs/agents/loop.md` § Worktree has the command.
- The README's "What the spike found about the platform" and "Not done or not verified" sections hold what's known about the platform and the mods' limits. Update them when a change proves or breaks one.

Every change that lands as a PR runs the `engineering-loop` skill, unless your personal instructions say `Engineering loop: off` and `docs/agents/gatekeeper.md`'s policy sets `opt_out: true` under `loop`. Its project facts are in `docs/agents/`.
