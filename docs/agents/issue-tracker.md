Tracker: GitHub (engineering-loop's github.md)

## Settings

The loop's label and board facts, a block `mise run loop:approvals`,
`mise run setup:github` (the labels) and the loop's board moves read; the
engineering loop's SKILL.md § Settings has every key. It is YAML, each section
`name: text` lines; a section or key the loop doesn't know is refused, naming
it. Uncomment an optional section to use it.

- `components`: where a change lands, each an `area:` label (`area:<name>`
  or the bare name) and what it covers. Every issue carries at least one. Edit
  the list to the project's parts; `mise run setup:github` creates each label.
- `categories`: optional, categories beyond the method's four (`kind:bug`,
  `kind:enhancement`, `kind:chore`, `kind:documentation`), each `kind:<name>`
  and what it means.
- `labels`: optional, labels this project adds beyond the pack's, each in
  full and what it means.
- `renames`: optional, labels to rename in place so every issue keeps them,
  the old name then the new, such as `frontend: area:web`. The pack's own
  renames (`bug`, `enhancement`, `chore` and `documentation` to their `kind:`
  names) need no line.
- `board`: the board column each loop column shows in. Rename the right side
  to the board's own column; several loop columns may share one, and a loop
  column left out keeps its own name.

```yaml
components:
  area:agent-hub: plugins/agent-hub, the subagent pane and /hub
  area:auto-effort: plugins/auto-effort, effort picked per turn
  area:compact-methods: plugins/compact-methods
  area:decision-model: plugins/decision-model, the $.decision backend the deciding mods share
  area:eval-kernel: plugins/eval-kernel, the eval tool and its Bun kernel
  area:resume-on-stop: plugins/resume-on-stop
  area:self-compact: plugins/self-compact, compaction at task boundaries
  area:ttsr-rules: plugins/ttsr-rules, rules matched against the model's stream
  area:e2e: e2e/, real sessions with the mods loaded
  area:tooling: mise tasks, scripts/, git hooks, CI workflows, the marketplace manifest and agent configuration
  area:docs: the README and the docs outside `docs/agents/`

# categories:
#   kind:ops: runbooks and alerts.

# labels:
#   customer-reported: filed from a support ticket.

# renames:
#   frontend: area:web

board:
  Intent: Intent
  Needs owner: Needs owner
  Ready: Ready
  Build: Build
  Verify: Verify
  Sign-off: Sign-off
  Done: Done
```

## Never on GitHub

The repo is public. Never: client or employer data, session transcripts or tool output from
work sessions, credentials or API keys (the decision-model keys included), or paths and hostnames
of private machines. Write a made-up example that shows the same behaviour instead.
