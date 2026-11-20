# Loop facts

The `engineering-loop` skill reads this file at every step but the gate.

## Settings

`mise run loop:approvals` reads this block, the engineering loop's settings
(its SKILL.md § Settings has every key). It is YAML: `key: value` under a
section name, a list one item per line. Quote a value that starts with `*` or
reads as another type (`no`, `on`, `1.10`). A key or section the loop doesn't
know is refused, naming it. § Approvals says what the seed's settings do.

```yaml
spec:
  # specs approved by policy, with no owner record; any other waits for the owner
  auto:
    - bug
    - follow-up
    - sub-issue

# practice:
#   the skill that fills a stage this project changes, one key each, such as
#   spec: brainstorming; a stage left out runs its default

risk:
  verifier: true
  paths:
    - .github/**
    - CODEOWNERS
    - docs/agents/loop.md

# bot:
#   renovate:   # deps:renovate's routine group, run on your token: see § Approvals
#     branch: renovate/
#     paths:
#       - uv.lock
#       - package-lock.json
#       - pyproject.toml
#       - package.json
#       - mise.toml
#       - .github/workflows/*.yml
```

## Owner

kzarzycki


## Proof on a branch

A session with the changed mod loaded: `claude --plugin-dir plugins/<mod>`, or the
`e2e/run.sh <suite>` suite that covers it, whose output says what each check saw.
`mise run check` is the rest.

Keep this line: a demo goes on the PR through the `demo` skill's script; when it refuses, stop and report.


## Acceptance references

In order: what a real Claude Code session does (an e2e suite, or a session started with the
mod loaded), Claude Code's mod API docs and `claude plugin` output, then the owner's report of
what they saw.


## Approvals

Only people approve; the rest is the standing policy in § Settings, which
`mise run loop:approvals` evaluates. `spec.auto` with `bug`, `follow-up` and
`sub-issue` approves the spec of a bug, a `Found while #<n>` follow-up, or a writer's sub-issue of an epic the
owner approved; any other spec waits for the owner. A PR lands on its gates
unless it is high risk: `risk:high` on the PR or its issue, the `risk` rule
matches, or the verifier's cap was reached with a blocker or major open. A
high-risk merge waits for the owner's `approved:merge` label, added after the
head's push.

The seed's `risk` rule lets the verifier judge every change and keeps a few
paths the owner's whatever it says. `verifier: true` holds when the verifier's
newest pass on the head says anything but `Risk: low`, so the owner sees only
what no check can settle. The paths hold on their own: CI's workflows and
rulesets under `.github/`, `CODEOWNERS`, and this file, since each decides what
the gates require and who approves. `risk` also takes `labels` (such as
`size:XL` or `area:<name>`, one per line) and `always: true`, which holds every
merge for the owner. `cap: <n>` under `loop` changes the verifier's pass cap
from the skill's default, and a `plan` section with `labels` asks for the
owner's approval of a matching plan. Required reviews go in branch protection,
which the loop obeys. The template ships no `CODEOWNERS`: GitHub would ask its
owners to review every PR the loop opens. Keep paths to a team with a push
ruleset instead, and ask someone for a review by name when it needs one.

Three settings the seed leaves out change this. `auto: true` under `spec`, in place of
the list, approves every spec by policy, epics included, except
one the `risk` rule matches or one opened by an account without write access,
which waits for the owner; the rule then holds the spec instead of the merge,
so that merge needs no `approved:merge`, but for its `verifier` term, which the
gate still judges at the merge. A `signoff` section, read as `risk` is, has
the owner sign off a matching change in use after it lands: its spec says
`Sign-off: owner` or `Sign-off: none`, and its PR links the issue with
`Implements #<n>`, which leaves it open for the sign-off. `opt_out: true` under
`loop` lets a developer whose personal instructions say
`Engineering loop: off` keep their PRs out of the loop: a PR with no loop trail
passes `loop:approvals`, its author merges it, and no risk rule holds it.
Renovate (`mise run deps:renovate`) labels `verify` the updates an agent
reviews: the template, the agent packages and every major. Its routine group
runs on the developer's token, so its PRs are the developer's and a verifier
reviews them too. The commented `bot.renovate` entry above exempts them
instead: it names Renovate by its `renovate/` branch, and holds only when every
commit is the developer's (`deps:renovate` sets Renovate's git author to
your git identity) and every file matches its `paths`. The `risk` rule still holds a match on its own paths, so
a workflow update keeps waiting for the owner until `.github/**` narrows to
what it means to keep, such as `.github/rulesets/**`.

## Risk criteria

A change that widens what a model can make a mod do: the eval kernel's scripts, calls through
`$.tool.call` (Claude Code's deny rules don't bind them), or a mod reading or writing another
mod's state or settings.

## In use

The owner's own Claude Code sessions, the interactive ones and those Omnigent starts, with the
mods installed from this marketplace. The repo is public, so anyone may install them. A mod runs
inside Claude Code with the session's access, and model output, tool results and other mods'
calls reach it, so a finding is judged by what a session hits and by what such input could make
the mod do.


## Worktree

`git worktree add ../claude-mods--<branch> -b <branch> origin/main`, then `mise trust && mise run setup:dev`.
Before removing one, end any session started with `--plugin-dir` pointing into it.


## Ledger

README.md § Not done or not verified


## Verifier checklist

None
