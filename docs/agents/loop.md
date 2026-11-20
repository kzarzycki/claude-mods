# Loop facts

The `engineering-loop` skill reads this file at every step but the gate.

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

Only people approve; the rest is the standing policy in gatekeeper.md §
Policy, which `mise run loop:approvals` evaluates. The owner has given standing
approval for every spec and every merge, so the loop doesn't stop for a label
on work the owner already approved:

- `spec.auto: true` approves every spec by policy, epics included. A spec
  opened by an account without write access still waits for the owner, since
  the pack keeps that rule.
- `levels.high` `{spec: policy, merge: gates}` lands a high-risk PR on its
  gates. A PR rates high when `risk:high` is on it or its issue, the `risk`
  rule matches, or the verifier's cap was reached unsatisfied (the
  engineering-loop skill's SKILL.md, Approvals and proof, has the full rule).
  The rating still shows as `risk:high`, and the pack still requires a
  default-tier verifier verdict for it, so standing approval doesn't skip review.
- `critical` keeps the pack's default, the owner's own go on the head. No
  `risk.critical_paths` are set, so nothing rates critical today.

Withdrawing the standing approval is one edit to gatekeeper.md's block, through
this loop.

The `risk` rule decides what shows as `risk:high`. `verifier: true` rates a
change high when a verifier pass said anything but `Risk: low`, until a later
`Scope: full` pass from the same verifier family (Claude or Codex) says
`Risk: low`; each family's history counts on its own, and a low pass on only a
delta since then leaves it high. The paths rate high on their own: CI's workflows and rulesets under
`.github/`, `CODEOWNERS`, this file and gatekeeper.md, since each decides what
the gates require and who approves. `risk` also takes `labels` (such as
`size:XL` or `area:<name>`, one per line) and `always: true`. `cap: <n>` under
`loop` changes the verifier's pass cap from the skill's default, and a `plan`
section with `labels` asks for the owner's approval of a matching plan.
Required reviews go in branch protection, which the loop obeys. The repo has no
`CODEOWNERS`: GitHub would ask its owners to review every PR the loop opens.

Renovate (`mise run deps:renovate`) labels `verify` the updates an agent
reviews: the template, the agent packages and every major. Its routine group
runs on the developer's token, so its PRs are the developer's and a verifier
reviews them too. The commented `bot.renovate` entry in gatekeeper.md exempts
them instead: it names Renovate by its `renovate/` branch, and holds only when
every commit is the developer's (`deps:renovate` sets Renovate's git author to
your git identity) and every file matches its `paths`.

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
