---
name: engineering-loop
description: The engineering loop, run for every change that will land as a PR, however small - intent, a spec the owner reads, build, gates, proof, an independent verifier, triage, the pass cap and autonomous landing. Use from the owner's request onward, when working or verifying part of one, or when deciding whether a finding is worth fixing.
---

# Engineering loop

A project turns the loop on with one line in its `AGENTS.md`. From then on every change
that lands as a PR runs it, from the owner's request to the merge: tooling, agent
configuration and files under `~/` too, through the repo that owns them. Each step
prevents a failure, and leaves proof on GitHub that `approvals.py` checks. Size changes who
builds and how long the spec is, never which steps run: a step is skipped only when the
owner asks for that change, and the PR body says so. Where gatekeeper.md allows an opt-out, a
developer whose personal instructions hold the line `Engineering loop: off` works outside
it (Approvals and proof); no step runs for their changes.

| Step | Prevents |
|---|---|
| **Intent.** File the request as an issue; read it and the code it touches; ask the owner only at a fork, or park the issue for them. | building the wrong thing |
| **Spec.** Written into the intent's issue for the owner, then approved (`approved:spec`, the ready state); the PR closes it, or implements it where the owner signs it off. | a decision the owner never saw |
| **Build.** Workers, or the lead when delegating costs more than it saves, always under the worker's rules. | nothing: the one step that scales |
| **Gates.** On each head, the worker's loop.md `Affected tests:` selection (`approvals.py affected-tests`; lint ran in the commit hook), else `mise run check` (worker.md, Gates and push; who runs what: Adopting the loop); the test part behind a host gate slot that exports `GATE_JOBS` (Rules, One heavy gate per host slot); GitHub runs every `check:` part. | a broken change |
| **Proof.** The spec's Before merge list on the PR branch before review, then its After merge list (checks that need the merged default branch or a deployed environment) after landing: each new result against a reference the code did not produce. | works in tests, not in use |
| **Verify.** A fresh verifier, of the other model family where one is available, up to the cap (The cap). | the author's blind spots |
| **Land**, clean up everything the run created, then report. | a disk full of finished runs |

## What the project states

The loop never names a project's tools. Each step reads a section of one of these
(below, "loop.md § Worktree" means that file's `## Worktree`), and a missing fact is a
question for the owner, not a guess:

| Where | Sections | Read at |
|---|---|---|
| mise tasks (what each does is its `description`: `mise tasks ls`) | when the loop runs them: `test:changed` while iterating, `check` on each pushed head (`approvals.py affected-tests` where loop.md has an `Affected tests:` line, Adopting the loop), `loop:approvals <build\|merge> [pr]` before building and before merging, `loop:land <pr>` to merge, `setup:dev` on a fresh checkout | Build, Gates, Land |
| `docs/agents/gatekeeper.md` | Policy (the block `approvals.py` reads, below), which nothing else reads | Spec, Gates, Land |
| `docs/agents/loop.md` | Owner; Proof on a branch (bring an instance up, tell it is up, read its log, a step to rerun after a schema or build change); Acceptance references, in order; Approvals (the owner's reasons for the settings, short); Risk criteria (optional, the project's own, in words, which the verifier reads); In use (how to judge a finding); Worktree (create and tear down); Ledger (its path); Verifier checklist. Optional lines `Orchestration backend: <name>` (a pin), `OMP worker profile: <name>`, `Worker model: <tier> for <condition>` and `Verifier model: <tier> for <condition>` (Models), `Worker tools: <list>` and `Verifier tools: <list>` (the tools and MCP servers a role needs beyond the lean set, or `full`: orchestrating-agents' Omnigent backend, Lean children), `Lead autocompact: <size>` (the window a top-level Claude lead compacts at: the same file, Lead window), `Lead model: <tier> for <condition>` (the tier a top-level Claude lead starts on when the issues its brief names match the condition: Models), `Gate cost: <cores> cores, <GB> GB` (what one run of the heaviest gate costs, with optional `, reserve <GB> GB`, from which the host's gate slot count follows: Rules, One heavy gate per host slot), `Affected tests: <command>` (the command that selects and runs the tests a change affects, plus the project's cheap whole-repo lint and type checks, against the base it reads from the `Gate base:` variable, else `GATE_BASE`, and from no local state it doesn't select everything without: Adopting the loop; `approvals.py affected-tests` sets it to `git merge-base origin/<base> HEAD`, or to its `--base`; with it every gate is narrowed, `land`'s batch gate included: Adopting the loop; a project without a selector omits the line and runs the full check), `Gate: full` (the opt-out: every gate runs the full check, as without `Affected tests:`), `Gate base: <variable>` (the one its `check` and `Affected tests:` read as the commit to select changed tests from, when not `GATE_BASE`; a project whose `check` reads either names it in `local_ci_env` too, so `local-ci` never records a part run: worker.md, Gates and push) and `Cloud worker: <agent>, gate <task>` (with `, env <name>` for its cloud environment) where a project's cloud workers differ from the default `claude-cloud` with the policy's gate, or `Cloud worker: none` and its reason where its heavy runs stay on hosts (Cloud worker), with `Cloud verifier: worker session` beside it where the verifier runs in the worker's VM, `Verifier hosts: <name>, <name>` (the Omnigent hosts a verifier may run on: lead.md step 7), `Verifier session: reuse | fresh` (default `fresh`, a new verifier session each pass; `reuse` keeps one across passes: Independent verification), `Acceptance tests: <command>` (the command that runs one spec's checks) and `Acceptance budget: <spec minutes>, <nightly minutes>` (both: Acceptance checks), which agents read. | every step but Gates |
| `docs/agents/issue-tracker.md` | the line `Tracker: GitHub (engineering-loop's github.md)`; Settings (the block `approvals.py`, `labels.py` and `board.py` read, below); Never on GitHub | Intent, Spec, Land |
| `docs/agents/coding-standards.md` | Domain facts | Build, Verify |

loop.md's optional line `Standing decisions: <path>` names a file in the project where the chief of staff writes its rule changes (under `## Chief of staff decisions`); lead.md reads it at the start of each real turn, so a rule change needs no live broadcast.

Every agent reads loop.md on every step, like a system prompt, so it holds only what agents act
on, each with a short reason only where the reason changes a decision. History, undo steps,
evidence and anything this skill already states go in the PR or issue that set the line.

### Settings

gatekeeper.md holds the gatekeeper's policy, a fenced `yaml` block under `## Policy`, which
`approvals.py` reads, so a team that takes only the gatekeeper writes no loop file; loop.md
keeps the prose for people and agents: why a path is critical, how to judge a finding, the
risk criteria in words. A project without gatekeeper.md may keep the block under loop.md's
`## Settings` for now: `approvals.py` reads it there with a deprecation line, and refuses a
project with both, since two sources of the bar would drift. `uv run --python '>=3.11' approvals.py check setup` is a consumer's gate on a pack upgrade: it reads the policy this way and
scans the repo's mise config and workflows for a pack script run without `uv run` (README § Upgrading the pack). `approvals.py` reads these files,
and issue-tracker.md, from the base's copy on `origin/<base>`, never the checkout's: the base the
PR a command acts on merges onto, the ref `land` builds on (`check`, `land`, `local-ci <pr>`,
`approve merge`, `delegate`, `brief`), else the default branch. `land` fetches the base before
it reads the policy (where it may run, its key, which drafts to ready) and reads it again after
its fetch under the landing lock, so a policy another land changed meanwhile decides the batch:
it places the land again (refused, the lock released, where the base now excludes the place it
runs; signed with the key it now names), and a draft it readied that the new policy would not
ready goes back to draft. A failed fetch before the lock readies no draft. So a PR can't
loosen its own gate and a checkout behind its
base can't hold an old one: a working-tree copy that differs gets one line naming the file and
both commits, and only a checkout without that ref (no `origin`) reads its own, with a line
saying so. A PR that changes the gate is therefore gated, recorded and landed under the base's
gate, and its own applies from the next PR on. The block is YAML because a person
reads and edits it by hand as `key: value` under section names, a list one item per line,
and it is typed (a boolean, a number and a list are each their own kind, so none is a
string the reader guesses at). A string needs no quotes unless YAML would read it otherwise:
one that starts with `*`, `&`, `!` or `[`, holds `: ` or ` #`, or reads as another type.
YAML 1.1, which PyYAML follows, reads `yes`, `no`, `on` and `off` as booleans and `1.10` as
the number 1.1, so `approvals.py` matches each value's type exactly and refuses, naming the
key, a value or name YAML read as something else: quote it. A value names a thing (a label,
a glob, a skill, a branch, a kind of spec), never a rule in words: which specs the policy
approves is a list of kinds, not a phrase such as `auto unless risk` whose meaning lives in
the reader, so a person reads the policy off the block and may name any part of it.
`approvals.py` refuses, naming the key, a section or key it doesn't know and a value of the
wrong type, and refuses a policy file without the block, so a mistyped setting is never read as
a rule nobody wrote.

The scripts read the block with PyYAML, the one package they need beyond the standard
library. Each declares it inline (PEP 723), so `uv run <this skill's folder>/scripts/approvals.py` installs it
into uv's cache on first use and nothing is installed by hand; uv comes with the project's
mise. Run with a bare `python3` that lacks PyYAML, a script exits with one line saying to
run it with `uv run`. They need Python 3.9 or later, except `check setup`, which needs 3.11 (it reads mise's TOML). Every key is optional:

```yaml
spec:
  # specs approved by policy, with no owner record; any other waits for the owner.
  # `auto: true` approves every spec, and by default the risk rule then holds the spec, not the merge
  auto:
    - bug
    - follow-up
    - sub-issue
    - paths:   # a spec labelled spec:paths whose PR stays inside these globs
        - mise.toml
        - docs/agents/**

loop:
  cap: 3
  ci: false
  gate: GATE_TIER=full mise run check:all   # the merge check, and the variables it sets
  local_ci_env:
    - GATE_TIER
  opt_out: true
  batch_queue: true   # deprecated with ci and carry_over_main: land batches every landable PR
  owner: octocat   # whose own approved:spec label, added after the spec's last edit, is their approval
  machine_exit: 78   # the gate's exit for "this machine isn't ready": land runs it again, then stops
  short_seconds: 120   # a job expected to finish within this takes the host's short lane; 0 turns the lane off
  pre_land: python3 scripts/check_fork.py   # land's check of each PR against the base, before it batches them
  delegate: all   # the delegated approver's go on a head covers a PR into the default branch too; default feature
  pack_staleness: refuse   # approvals.py exits 1 at start when its checkout is behind its upstream and the script changed there (default warn; omnigent_agent.py only warns)
  head_proof:      # the status land requires on each head, and the names its recording takes from the caller
    status: gate-ui
    env:
      - GATE_UI_TESTS

practice:
  plan: writing-plans

risk:
  verifier: true
  labels:
    - size:L
    - size:XL
    - area:billing
  paths:
    - .github/**
    - CODEOWNERS
  critical_paths:   # the `critical` level, whatever the labels and the verifier say; was merge_paths
    - src/orders/**

levels:   # what each level asks; the values shown are the defaults
  low:
    spec: policy
    merge: gates
  high:   # under `spec.auto: true` {spec: owner, merge: gates}
    spec: policy
    merge: go
  critical:
    spec: policy
    merge: owner

plan:
  labels:
    - size:XL

signoff:
  labels:
    - area:ios

bot:
  dependabot[bot]:
    paths:
      - uv.lock
      - "**/package.json"   # quoted: a leading * is a YAML alias
  renovate:                 # an updater under a person's token: named by its branch
    branch: renovate/
    paths:
      - uv.lock

land:
  signed_squash_to: main
  allowed_signers: ~/.config/git/allowed_signers
  batch_wait_seconds: 600   # land waits up to this long before it gates, while another PR waits only on its required checks; default 0
  gate_on: cloud   # land's batch gate runs in a standing cloud session, the host as fallback; default host
  cloud_gate_timeout_seconds: 2400   # how long land waits for that session's record before gating on the host; default 2400

carry_over_main:
  # a clean merge of main keeps the head's verdict unless either side changed one of these
  except:
    - mise.toml
    - uv.lock
    - '**/uv.lock'
    - pyproject.toml
    - .github/**
```

| Section | Key | Value | Without it |
|---|---|---|---|
| `spec` | `auto` | a list of `bug`, `follow-up`, `sub-issue` and `paths` terms, or `true` for every spec (Approvals and proof) | every spec waits for the owner |
| `loop` | `cap` | a whole number (The cap) | the default |
| | `ci` | deprecated, goes in the next release (Approvals and proof); `false` for a project without CI, whose merge proof is then `uv run <this skill's folder>/scripts/approvals.py local-ci <pr>` (its docstring says what it records) | `true` |
| | `gate` | the merge check `local-ci` runs: a command, with any variables it sets in front (Adopting the loop) | `mise run check:all` |
| | `gate_steps` | the merge check as steps, in place of `gate`: a list of `name`, `command` (parsed as `gate` is), `where` (`any`; `host`: never run in a cloud session; or `linux`: only where `sys.platform` is Linux, a Linux host or a cloud session, never macOS) and optionally `paths`, globs of the files the step reads, matched on the full path as `paths` are, so its pass is reused on any tree whose files under them are the same; each step's pass recorded and reused by itself (Adopting the loop) | the one `gate` command; a step without `paths` reads the whole tree |
| | `local_ci_env` | the environment variables the check reads, cleared for its run unless `gate` sets them (Adopting the loop) | none |
| | `machine_exit` | the gate's exit that means the machine isn't ready (a locked screen, low disk), such as 78: `land` runs that gate once more on the same tree, and a second one stops the run landing, evicting and posting nothing, and `local-ci` refuses it as a machine fault (`approvals.py`'s docstring) | every non-zero exit is red |
| | `short_seconds` | a whole number of seconds: a job expected to finish within it takes the host's short lane instead of the heavy slot, and `0` turns the lane off (Rules, One heavy gate per host slot) | `120` |
| | `opt_out` | `true` where a person may work outside the loop (Approvals and proof) | `false` |
| | `pre_land` | a check `land` runs for each PR before batching it, parsed as `gate` is, from the base's tree with `LAND_HEAD` and `LAND_BASE` set, such as one refusing a branch forked before a restructuring; non-zero leaves that PR out of the batch with one comment per head holding its output, and it stays ready (`approvals.py`'s docstring says how) | no check |
| | `head_proof` | `status`, a commit status `land` requires on each head, and `env`, the variables `local-ci --record --head-proof` takes from the caller for that run, both required (Approvals and proof) | the batch gate is the only proof |
| `mutate` | `inconclusive_exit` | a whole number from 1 to 255: the exit a test command returns for "setup failed, no verdict", which `mutate.py` reports as an inconclusive patch (never killed) and exits 3 for; the project's test command exits with it when its device or build setup fails (verifier.md, Mutation-check the new tests) | `75` |
| `practice` | `intent`, `spec`, `plan`, `build`, `review`, `land` | the skill that fills that stage (Practice) | the stage's default |
| `risk`, `plan`, `signoff` | `always` (`true` or `false`), `labels`, `paths`, and in `risk` `verifier` | a rule (Approvals and proof); `plan` has no `paths`, since a plan comes before the change | no rule |
| `risk` | `critical_paths` | globs matched on the PR's files, as `paths` are: a PR touching one rates `critical` (Approvals and proof); `merge_paths` is its deprecated name, read with a `deprecated:` line, and both set is refused | nothing rates `critical` |
| `incubating` | `append_paths` (globs of existing files a feature may only append lines to), `waive` (any of `evidence`, `proof_run`, `verifier`, `full_gate`, `coverage`) | what an eligible `incubating` PR stops owing (Approvals and proof, Incubating) | the mode is off; with the section and no `waive`, all five |
| `levels` | `low`, `high`, `critical`, each with `spec` (`policy` or `owner`) and `merge` (`gates`, `go` or `owner`) | what a change rated at that level needs (Approvals and proof); a key left out keeps its default | `low` {policy, gates}; `high` {policy, go}, or under `spec.auto: true` {owner, gates}; `critical` {policy, owner} |
| `bot.<login>` | `paths`, and `branch` (a head-branch prefix) to name an updater by its branch instead | a bot whose PR needs no verifier review (Approvals and proof) | every PR needs one |
| `land` | `signed_squash_to` and `allowed_signers`, set together or not at all; `where` (`host`, `claude-cloud` or `both`; `cloud` still means `claude-cloud`), `signing_key_env`, `merge_queue`, `merge_commit_heads` (a list of fnmatch patterns over head branch names, such as `sync/*`), `batch_wait_seconds` (a whole number of seconds, 0 or more), `gate_on` (`host` or `cloud`) and `cloud_gate_timeout_seconds` (a whole number of seconds, 0 or more) | for a repo that trusts only commits its maintainers sign, the branch and the allowed signers file: `land` then squashes and signs the PR in the checkout instead of merging it on GitHub; `where` is where `land` may run (default `both`: a cloud session lands too, with no `land` section on a base whose ruleset requires GitHub's merge queue), and in a cloud session a repo with `signed_squash_to` signs with the key in the variable `signing_key_env` names, which must be in the allowed signers, never the session's own, and lands a PR there only with `merge_queue: false`, since REST can't say whether the base requires a merge queue (`approvals.py`'s docstring says how); a base whose ruleset requires GitHub's merge queue needs no key there, since GitHub merges and signs; `batch_wait_seconds` makes `land`, holding the lock, wait up to that long before it gates the batch while another open PR into the same base is held by nothing but its required checks still running (the proofs and any owner go already hold, and a PR whose required check no workflow will run, a conflicting one or a readied draft whose workflow lacks `ready_for_review`, never counts), and each such PR whose checks turn green in that time joins the batch and shares its one gate; its wait and who joined are printed and shown on the `Landed` comment's `Batch:` line, and `land` of named PRs only never waits; with `gate_on: cloud`, `land`, holding the lock, pushes the batch commit as the branch `loop-land/<tree>`, asks the repo's one standing cloud gate session (started on first use, its id kept in `.git/approvals/cloud-gate.json`) to run `local-ci --record` on it, waits for the record branch of exactly that tree (the same rule as any reused pass), deletes `loop-land/<tree>` and then gates as usual, which now reuses that pass and runs nothing on the host; a `where: host` step still runs there. No record within `cloud_gate_timeout_seconds` (default 2400 s: the measured cloud gate took 1,200 to 1,650 s, and the first batch also starts the session; the session's `launch-dir` and `start` take up to 600 s each on top), a session whose turn has ended with no record and no red line, a refused start or a session that is gone is one printed line, and the host gates as without the setting, so a cloud outage never blocks landing; a session whose turn ended (or that is archived, never one in a `failed` state, whose last message can be an earlier turn's) on `DONE: red <tree>` (a failed gate pushes no record) fails the tree at once with no host re-run, since a red suite stays red (a `machine_exit` exit is a machine fault, not red); the red path (each PR alone, then evict) takes the same route; it is optional, so it needs no signing keys | GitHub merges, on a host, or in a cloud session on a base whose ruleset requires the merge queue; no wait for `batch_wait_seconds`; a PR whose head matches `merge_commit_heads` lands with `gh pr merge --merge --match-head-commit`, keeping the head's ancestry (an upstream-sync PR needs it), and every other PR is squashed as before; `land` prints each PR's method, and a match with `signed_squash_to` set is refused, since a signed squash has no merge-commit form |
| `carry_over_main` | `except`, a list of globs, required | deprecated, goes in the next release (Approvals and proof); the project's merge-check configuration (lint, type, test and gate config, lockfiles): clean merges of main whose changes touch none of the PR's files, where neither the PR's changes nor main's touch one of these, keeps the head's verdict, never its `local-ci` record (Approvals and proof). A glob matches the full path, as `paths` does: a nested copy needs `**/<name>` beside `<name>` | every merge of main needs its own verifier pass |
| `adapters` | `tracker`, `forge`, `evidence` | the adapter each of the gatekeeper's ports runs on, by name: `github`, `gatekeeper.py`'s own (`github_adapter.py`), is the one it ships, and a name no adapter has is refused, naming it (`gatekeeper.py`'s docstring) | `github` |

issue-tracker.md holds its label and board facts in a block of the same form under its own
`## Settings`, read by `approvals.py` (`label_names`), `labels.py` and `board.py`, refused the
same way; its Never on GitHub stays prose. Each section's values are strings:

```yaml
components:
  # a component, bare or in full: its label's description
  billing: invoices and payment runs.

categories:
  ops: runbooks and alerts.

labels:
  customer-reported: filed from a support ticket.

renames:
  # old label: new label
  frontend: area:web

board:
  # loop column: the board's column
  Build: In progress
```

| Section | Key: value | Without it |
|---|---|---|
| `components` | a component (`billing` or `area:billing`): its description | no `area:` label |
| `categories` | an extra category (`ops` or `kind:ops`): its description | the loop's categories only |
| `labels` | any other label, in full: its description | none |
| `renames` | an old label name: its new one (issues.md, Labels) | the loop's own renames only |
| `board` | a loop column: the board's column (github.md, Board) | each column keeps its own name |

### Adopting the loop

kzarzycki/project-templates holds the repo files the loop runs on, so the pack keeps no
second copy. A new repo starts from it with Copier
(`copier copy --trust gh:kzarzycki/project-templates <dest>`); answering yes to mise, the
agent layer, the engineering pack and the engineering loop sets `loop_enabled`. An existing
repo takes these files from it. They are Jinja with includes, so render the template for the
repo's `project_type` into a scratch directory with `copier copy` and copy the rendered files:

- `mise.toml` tasks: the `check:`, `lint:`, `test:`, `ci:`, `loop:`, `setup:` and `agent:`
  groups, with the old names as aliases;
- `.pre-commit-config.yaml`: the git hooks, each one a caller of a mise task;
- `.github/workflows/`: CI, which runs every `check:` part, and the `loop:approvals`
  workflow, which turns `mise run loop:approvals merge`'s exit into the `loop:approvals`
  commit status on the head (0 success, 1 failure, 3 pending, since a job's own result can't
  hold a merge as pending), runs again when CI completes, and removes `approved:merge` on a
  push;
- `.github/check-paths.yml`: each part's path filter;
- the test runner's retry of a failed test, once (Rules for every role, Flaky tests);
- `.github/rulesets/main.json`: a ruleset on main allowing squash merges only, requiring
  exactly two checks, `check` and `loop:approvals`, and no up-to-date branch, since `land`
  gates every PR on top of main. The ruleset picks `land`'s merge queue. Without a
  `merge_queue` rule it is the local merge queue: `land` gates the batch on the host within
  one call and merges each PR directly. With one it is the GitHub merge queue: `land`
  enqueues each landable PR, and the queue's `merge_group` CI gates and merges it, so
  nothing heavy runs on a laptop and no CI job runs twice. It suits a project whose CI is
  long or that has code built around the queue. CI then needs `merge_group` triggers and
  `loop:approvals` success on the queue's commit, and PR-time CI may run only what changed,
  since the queue runs everything. A private repo on
  GitHub's free plan has no rulesets, branch protection or auto-merge, so the ruleset can't be
  applied: `land` reads no required checks there, merges directly once its proofs hold, and
  says GitHub enforces no rules there, since its proofs are the only gate. `mise run
  setup:github` applies it; GitHub layers it on top of the repo's own rulesets, which it
  leaves untouched, and reverting deletes only it. `setup:github` also syncs the repo's
  labels with `scripts/labels.py` (github.md, Labels). The files here are also what
  `scripts/rulesets.py check` compares the live rulesets against, one line per difference
  (`rulesets.py snapshot` writes them from a repo set up by hand): GitHub sends no alert when
  a ruleset is deleted, disabled, narrowed or given a bypass actor, so a project runs the check
  on a schedule, for example from its hygiene job.

**Which token the agents use.** What the token can do bounds what a misbehaving agent can undo.

- *In an organization:* a fine-grained token with the organization as resource owner. Repository
  permissions: Contents, Pull requests, Issues, Commit statuses and Workflows read and write;
  Metadata and Actions read. Organization permission: Projects read and write (`board.py`
  writes the board through GraphQL). It gets no Administration, so the rulesets bind the agents.
  Open question, unproved: `approvals.py check` reads each head's check runs
  (`commits/<sha>/check-runs` and `check-suites`, plus the `actions/runs` that name them and the
  commit statuses). GitHub's fine-grained permissions table lists the `actions/runs` and commit
  status routes (under Actions and Commit statuses, read), but it has no Checks permission and
  lists neither check-runs nor check-suites. If the token can't read check runs, `check` has no CI result to
  read and `check merge` can't tell a green head from a missing one, so it holds the merge
  (it has no fallback to the statuses alone); until someone runs
  `gh api repos/<owner>/<repo>/commits/<sha>/check-runs` with such a token and records the
  answer, treat the gap as real.
- *On a personal account:* a fine-grained token can't reach a repo the account only collaborates
  on, nor a user-owned Projects board, so the loop needs a classic `repo` token (plus the
  `project` scope for `board.py`). That token is admin, so rulesets don't bind it; the
  protection is detection: no-bypass rulesets plus a scheduled `rulesets.py check` (not yet shipped: issue #1041).
- *Renewal:* the `github-authentication-token-expiration` header of `gh api -i user` shows
  when a token runs out.

Hooks are git hooks, installed by `mise run setup:dev`; no check runs from a coding agent's
harness hook. A commit runs the `lint:` tasks on the staged files, and a push runs
`test:changed` and `check:secrets`. The proofs stay off the push, because a push is
reversible and a draft can't merge: `loop:approvals build` runs when the branch is cut, and
`loop:approvals merge` on ready PRs in CI.

A PR stays a draft until no core finding is open (Review trail on the PR), so CI skips its
jobs on draft PRs (`if: ${{ !github.event.pull_request.draft }}` on each job) and lists
`ready_for_review` in its `pull_request` types, so marking a PR ready starts them.
Merge-queue (`merge_group`) and push runs have no draft and run as before. A project with an `Affected tests:` line gets a narrowed batch gate on this version: add the push-to-main and nightly runs first, or set `Gate: full` until you do, and check that the `Affected tests:` command runs the project's lint and type checks too, since it becomes the whole batch gate (a line written for draft heads may run tests only). The project template ships those runs with a following release; until then the push and ready-PR runs call `approvals.py affected-tests --base <the PR's base SHA, or github.event.before on a push>`, and the nightly runs the full check and calls `nightly.py red` on red (Nightly, below). Narrowed mode is loop.md's `Affected tests: <command>` line without the opt-out line `Gate: full`. Its command is the whole narrowed check: the project's selector plus its cheap whole-repo lint and type checks, as one task (such as `mise run check-fast`), reading the base from the `Gate base:` variable, else `GATE_BASE`. It selects from the diff against that base and from nothing else the pack provides: every gate runs it on a clean checkout, often a fresh clone, a cloud VM or a CI runner, with only the base variable set. A stateful selector such as pytest-testmon, which keys on a local data file, says in the project's `docs/agents/` files how the project supplies that state (CI caching it keyed on the base commit, say), and without the state it selects every test, which is safe and as slow as the full check, since a selector that selects less without its state would pass a change it never tested. In narrowed mode every gate runs that command and none runs the full suite, which the nightly runs (Nightly): the check on each head the worker pushes, draft or ready, a fix round's too, is `uv run <this skill's folder>/scripts/approvals.py affected-tests`, against the merge base with the branch's base (the commit hook's `lint:` tasks ran at commit; it replaces a `GATE_BASE=<last green>` delta run); the project's CI on a ready PR and on a push to main runs `affected-tests --base <rev>` with the PR's base SHA or the push's previous main tip, and a `<rev>` git can't resolve (the all-zeros SHA of a new branch) runs the full `mise run check`, said in one line; and `land`'s batch gate runs the command with the variable set to the base tip the batch merges onto, so it selects over the batch's combined diff, under the same gate slot, `machine_exit`, records and cloud gate as the full gate. The `gate` line's variable assignments do not apply to the narrowed command: a project writes any variable its checks need on the `Affected tests:` line itself. A project with `gate_steps` keeps its steps in `land`, since each already narrows by its `paths`. No role reruns the full unit tier on a PR head, and, where `ci` is not `false` and no `gate_steps` step runs on the host, none reruns a gate on the host for a ready PR whose required check is green. Who runs what: a draft head, the worker's `affected-tests`; a ready PR, CI's selection; the verifier, on a draft head, reads the worker's report (its command and exit code) and runs the PR's own tests, the `gate` status and `loop-gate/` record being a ready head's. With `ci: false` the gate of record on the ready head is `approvals.py local-ci --record`, run by the worker once when the PR goes ready (again only if the head moves after that, or its merge base with the PR's base does: a stacked PR whose parent lands, a retarget, since a narrowed record is keyed by that merge base): in narrowed mode it runs the `Affected tests:` command against the merge base and records a narrowed pass, which `check merge` takes in place of a full one; otherwise it runs the full gate, and `check merge` takes only a full pass; this holds with or without a `head_proof`. A narrowed pass's command names its base and ends in ` (narrowed)`, which no gate command can hold, so its record and key never equal a full pass's; its `gate` status says `narrowed vs <base>` and `local-ci --status` says `narrowed against <base>`, and nothing that requires a full pass takes it. `local-ci` and `land` clear the `Gate base:` variable from the caller's environment, unless a head proof's `env` names it, and set it themselves only in narrowed mode, so a caller's base never narrows a recorded pass.

The risk of a narrowed batch gate is a main that breaks between nightlies: a test the selector misses (a data file, config, a script run as a subprocess), or two PRs each green alone that break together. Its guards: the push-to-main run tests the merged tree's affected tests (CI's `affected-tests --base <previous tip>`); the nightly runs the full suite, and on red `nightly.py red` opens one issue naming the merges since the last green (Nightly); and the line `Gate: full` in loop.md returns every gate to the full check, for a project whose selector is weak or while risky changes land. Without the `Affected tests:` line, or with `Gate: full`, every gate runs the full check as before, and `approvals.py check build` says in one line that the line is missing (not under `Gate: full`, which chose it). With `ci: false` in gatekeeper.md and no such line, the
check on a head you push for review is `uv run <this skill's folder>/scripts/approvals.py local-ci --record`
instead, and is the gate while iterating too: it runs the merge check, gatekeeper.md's `gate`
(default `mise run check:all`), and a clean, green run records itself by tree in the clone's git dir and pushes it
to the base repo as the branch `loop-gate/<tree>-<key>`, named by its tree and command, so `local-ci <pr>` at landing
posts that pass rather than running the check again (with no usable pass it refuses, naming the head, tree, record branch and what was wrong with a record found; `--run` runs the check on this host): in this clone for any commit with the same tree and gate
command (a rebase or reworded commit keeps its tree), in any other, host or cloud session, from that branch, at every
risk, through the same code. The branch is the one route a pass travels: the `gate` commit status the run and each
reader write on the head, where the token allows, only shows the pass on the PR, and no decision reads it, since
anyone who can write a status may type one. `land` deletes a record branch once its tree has landed, or once it is a
day old and its tree is no open PR's head. `gate` is one command with no shell operator, so a
chain of checks is one task, or the steps of `gate_steps`, each a command and where it runs (`any`, or `host` for one
a cloud VM can't run, such as an Apple build, or `linux` for one a Mac can't). Each step's pass is its own record and branch, named by the tree and
the step's command, so `local-ci`, `local-ci --record` and `land` run only the steps with no pass on the tree and print
where each reused one passed: a host runs only the `host` steps of a tree whose other steps a cloud session pushed,
and a cloud session runs the `any` steps and leaves the `host` ones, which `land` there refuses. A step may name
`paths`, globs of the files it reads (`paths: [ios/**, Package.swift]`); its pass is then keyed on its inputs, its command
and a digest of the `gate_steps` setting and the mode, object id and path of each file under its paths, so a tree
that changes none of them (a comment, the agent pack, another PR's files in a batch) reuses the pass from any tree with
the same inputs, from this clone's records or origin's branches, and the run says `<step>: reused, inputs unchanged
since <tree>`. A step without `paths` reads the whole tree, as do paths that match no file. A project whose docs no
step reads gives every step `paths` that leave `docs/**` out. Any change to `gate_steps`, a command or a step's
`paths`, changes every keyed step's key, so nothing is reused across it: `paths` skips work on purpose, and a wrong
glob passes a step that never ran on what it reads, so a change to it is high risk. A reused record counts only when
today's `paths` give its own tree the same key. Each step that runs
holds the host gate slot (Rules, One heavy gate per host slot) for its own run only, so a land whose host steps all
reuse never waits on it for them, and every record, a step's or the one gate's, carries the seconds it ran, the
seconds it waited for the slot, and the host's 1-minute load average and swap in use when it started. A run on a
checkout with changes records nothing. A project whose check reads environment variables (a
tier, a scope) names them in gatekeeper.md's `local_ci_env`, and they are cleared for the run, so a
host's own setting never changes what a pass proves; the tier the merge needs goes in
front of the command in `gate`. `local-ci` runs the check in a session of
its own and follows its log, so a harness that kills the caller's process group leaves the check to finish and record;
`local-ci --status <head>` then says whether it is running, passed or failed (its docstring names the files).

[coding-standards.md](coding-standards.md) is the generic half of the standards, read
with the project's. Issue states, categories, sizes and board columns are the method's,
in [issues.md](issues.md), so every project's board looks the same; [github.md](github.md)
does them on GitHub. A
`scripts/` path is relative to this skill's folder, not the repo root: in a project that
installs the skill it is under the install, such as
`.agents/skills/engineering-loop/scripts/board.py`. Run it from the worktree with `uv run`,
which installs what its inline header declares. `scripts/browse.py` renders a web UI headless, signed in to an Omnigent server when
asked, and screenshots it (worker.md, Report; its docstring has the flags). `scripts/mutate.py` applies
each mutation patch alone, runs the tests and restores the tree, writing a log stamped with the head: the worker
runs it before its report and the verifier in review (verifier.md, Mutation-check the new tests; its
docstring has the log format and exit codes). `scripts/events.py` writes and reads a step's state as a git ref (`emit`, `read`, `wait`, `clear`); the kinds, states, beat intervals and `event.json` fields are in [events.md](events.md), which a producer or a reader of an event reads first.

**Acceptance checks.** Each scriptable Before merge line of a spec becomes a check committed in
its PR, so a later change that breaks the example fails a run rather than a reader's memory.
The acceptance command runs one spec's checks: with loop.md's optional line `Acceptance tests:
<command>`, it is `<command> <issue>`, which the project wires however its suite selects tests
(a tag or marker, a name filter such as `#842` in the test name, a folder per spec), prints one
line per check and exits 0 when all pass; the loop names no runner. Without the line it is
`uv run <this skill's folder>/scripts/acceptance.py <issue>`, which runs every executable file in
`acceptance/<issue>/` at the repo root, in name order, from the repo root (a shell script, a SQL
client call, an HTTP call, any language), prints `PASS` or `FAIL` per file and the total, and
exits 0 when all pass, 1 when one fails and 2 when there is nothing to run, so "no checks" is
never read as "passed"; `--all` runs every `acceptance/*/` folder, for a nightly. The worker runs
it on the head before its report (worker.md, Report), and its docstring has the line formats.
One spec's checks finish within 10 min on the gate's machine and the `--all` run within 90, or
the minutes of loop.md's `Acceptance budget: <spec minutes>, <nightly minutes>`, since the
verifier reruns them on every pass: a longer check is split or moves to the nightly. Over the
budget the runner prints one line saying so and still exits on the checks' result, since the
budget is a signal, not a gate.

**Nightly.** After a merge nothing reruns a spec's checks but the project's nightly, and in
narrowed mode (Adopting the loop) nothing else runs the full suite at all, so the
nightly runs the project's full suite, which holds every spec's acceptance checks, plus
`uv run <this skill's folder>/scripts/acceptance.py --all` where the project uses the
`acceptance/<issue>/` folders; the workflow itself (its schedule, where it runs) is the
project's. When it ends red, it calls `uv run <this skill's folder>/scripts/nightly.py red
--last-green <sha> --red <sha> --run <url>`, with the newest default-branch commit a nightly
passed on, the one it failed on and the run's link, from a checkout holding the history
between them. It lists the PRs merged on the default branch since the last green (first-parent
merges and squash commits, each PR's linked issues and their epics) and opens one issue
`Nightly red since <short sha>` with that list and the link, or, while that issue is open,
comments the new run and the merges since the last red on it, so a person or a lead bisects
from a short list rather than the whole history. It needs only git and gh, checks each body
against `LOOP_DENY_LIST` before posting, and its docstring has the formats and exit codes. A
project's worker heads and `land`'s batch gate run narrowed from the pack once its loop.md names
its `Affected tests:` command; what it adds itself is that command (its selector plus its cheap
lint and type checks, one task), its CI's push and ready runs of `affected-tests --base`, and the
nightly workflow that runs the full suite and calls `nightly.py red`. The project template does not
ship those two workflows yet; they come with a following template release. Until a project has them,
`land`'s batch gate is guarded only by the selector, so it adds them or sets `Gate: full`.

**Fixing the gate itself.** `land` reads `gate_steps` from the default branch, so a PR that changes them lands under the old
policy, which still runs the step the PR moves (to `where: linux`, say) on a host where it can't pass. Run from a host where
the step runs, a clean checkout of the merge tree `land` will build (`git fetch origin pull/<n>/merge`, or the queue's
branch, then `git checkout --detach FETCH_HEAD`) and `approvals.py local-ci --record` there records and pushes the step's
pass, so `land` reuses it by tree and command and runs no step again. `local-ci` plans from `origin/<base>`'s policy, the
one `land` reads, never the checkout's own, so a PR cannot loosen its own gate: the plan holds the steps `land` will ask
for, including one the PR moves or drops, and each pass is keyed on the base's `gate_steps` setting. A PR that changes
`gate_steps` therefore gets passes under the old setting, and `land` finds them. To plan from the checkout's policy in a
test or preview, set `GATEKEEPER_POLICY_FROM_WORKING_TREE=1`; a real run never does.

### Practice

gatekeeper.md's `practice` names the skill that fills a stage, one key each, such as
`spec: brainstorming`; a stage it does not name runs its default. Either way the stage
produces what this table says:

| Stage | Must produce | Default skill |
|---|---|---|
| Intent | open questions settled, or asked in the issue | `grilling` |
| Spec | the spec in the issue, or linked from it, with acceptance examples as a Before merge and an After merge list and the reference each checks against | `to-spec` |
| Plan, only when gatekeeper.md's `practice` names a `plan` skill | ordered slices, each with its check, as a `## Plan` comment on the issue | none |
| Build | commits on the branch, with `check` green | the worker role |
| Review | findings with path, cost and repro, then the verdict lines | `code-review`, run by the verifier |
| Land | the PR body | `pr` |

Whatever the practice, the issue and the board hold the state, the gates run, the
verifier is a fresh session (Independent verification), and the loop merges. A practice skill's own
merging or state-keeping is overridden, because two writers of one state drift apart.

### Incubating

A feature merged to main early and not yet proven is incubating: its PR carries the label `incubating` and a body line
`Incubates: #<epic>`, naming the open epic (labelled `incubating`) that tracks the feature. Anyone who can write to the repo
may add both. The label is a claim, judged by `check merge` on every file the PR touches: it holds while every file is
added, or modified with no line deleted and matching `incubating.append_paths`, the epic is open and labelled, and the
change doesn't rate `high` or `critical`. A PR that fails owes the full loop, and `check merge` says why. While it holds,
`check merge` stops requiring what `incubating.waive` names: `evidence` (the `## Evidence` section and the `## Demo`
form), and `verifier` (the verifier's review on the head). Nothing here forbids them, and a review thread or a
`CHANGES_REQUESTED` review still blocks. The other three names (`proof_run`, `full_gate`, `coverage`) are for the project's gate:
`local-ci <pr>` (and the `ci: false` check in `check merge`) runs the gate with `GATE_INCUBATING=1` and
`GATE_INCUBATING_WAIVES` (the waived names, comma-joined) set for an eligible PR, and the gate command decides what each
skips (the pack can't know a project's e2e or coverage tasks). The pass is keyed by that env, so it never stands in for a
full one; a batch queue and a project's own CI read the label themselves. Without an `incubating` section the label means nothing.
An `incubating` issue stays open while the feature incubates: `check merge` refuses a PR that would close one unless its
body also says `Graduates #<n>`, and a PR that says it owes the full loop, labelled `incubating` or not. A slice closes its own
sub-issue (`Closes #<sub-issue>`), never the epic.
`approvals.py graduate <epic> --pr <n>` graduates an epic once PR <n> has merged with `Graduates #<epic>`: it comments,
removes the label and then closes. The graduating PR says `Part of #<epic>` beside `Graduates #<epic>` (and a `Closes` for the sub-issue it finishes), so GitHub leaves
the epic for that command. The workflow `.github/workflows/incubating-epic.yml` (an adopting project copies it) reopens
an `incubating` issue someone closed, and puts a dropped label back on an open `epic`, each with a comment; both leave
an issue alone once a `Graduated by` comment is on it. Anyone with write access can still graduate by hand: the
workflow keeps accidents out, not a person set on it.
A second workflow, `.github/workflows/incubating-nightly.yml` (also copied), runs nightly over the open `incubating` epics.
It lists each with its age in days, counted from the first time the label was put on, so a label put back does not restart it.
For an epic whose body names a `Flag:` (not `none`) and a `Nightly:` command, it runs that command with the flag set to 1
and comments a failure on the epic with the run link. It runs only a `Nightly:` line of the form `mise run <task>`,
since an issue body is editable text. It comments `Still incubating` on an epic whose label, or whose last such comment
by the bot, is `STALE_DAYS` (30) old. It blocks no PR: only its own run turns red. With no open epic it runs nothing.

### Approvals and proof

Only people approve: the owner, or a teammate where loop.md asks for one. No agent writes
an approval record, since an agent approving its own work is no approval; where nobody
was asked, the authority is the owner's standing policy in gatekeeper.md, which
`approvals.py` evaluates from the evidence on GitHub. A spec or plan approval is a comment
`uv run <this skill's folder>/scripts/approvals.py approve <spec|plan> <issue> --by owner` writes on the
owner's word, tied to the spec's or plan's text by its sha256, so any change to the text
needs approving again, plus the `approved:<point>` label. A re-approval says
what changed and minimizes the records it supersedes as outdated. The verifier only gives
the verdict, which `uv run <this skill's folder>/scripts/approvals.py verdict <pr> <report>` posts as a PR
review on the commit it reviewed.

gatekeeper.md's policy (Settings) holds:

- `spec.auto`, a list, approves by policy, with no record or label, the spec of each
  kind it names: `bug`, a `kind:bug`; `follow-up`, an issue whose body has a `Found while
  #<n>` line (a follow-up an agent raised, Triage); `sub-issue`, a native sub-issue of an
  epic the owner approved (their current record and `approved:spec`), opened by an account
  with write access to the repo. Any other spec, a new epic for one, needs the owner's
  approval; without `auto`, or with `false` or an empty list, every spec does.
- A `paths` term in the `spec.auto` list (`- paths: [mise.toml, docs/agents/**]`), globs
  matched as a rule's `paths` are, approves by policy the spec of an issue labelled
  `spec:paths`, which the lead adds when the spec's change stays inside them, such as the
  project's own tooling. The label is the claim, since the gate can't read where a change
  lands from the spec; `check build` and `check merge` judge it on every path the PR touches
  (before the PR, the branch's files so far). It approves only while every path matches a
  glob, a renamed or copied file's old name as well as its new one, so a move across the
  boundary either way voids it; GitHub gives every file and old name; neither the issue nor
  the PR carries `risk:high` and the `risk` rule doesn't hold, its `verifier` term included
  once a review is read; and the issue's author can write to the repo. Otherwise the spec
  waits for the owner's record and `approved:spec`, and `check` names why, the files outside
  the globs included. The label without the term approves nothing.
- `spec.auto: true` approves every spec by policy, epics included, so the owner reads only the
  critical ones: a spec the `risk` rule matches, or one opened by an account without write
  access, since anyone who can open an issue would otherwise approve their own, waits for
  the owner's record and `approved:spec`. The risk rule then holds the spec instead of the
  merge (the default `high` level there is `{spec: owner, merge: gates}`, below): the owner
  decides while the change is still cheap, and its merge is automatic like any other. `approvals.py` judges the rule on the labels of the issue and the PR
  and the PR's files, at `check build` the files pushed so far, so a file the spec didn't
  foresee still reaches the owner before the merge. `auto: true` moves the rule rather than
  a key of its own, since with every spec approved by policy the spec is the one point the
  owner sees a risky change before it is built, and holding the merge as well would ask
  them twice.
- The gates are the merge approval of a change whose level asks `gates` of the merge (by
  default a `low` one).
- `risk` is the rating: it says what rates `high` here, and any one of its terms matching holds: `labels`,
  matched exactly on the PR and its issues as GitHub names them (`size:L` and `size:XL`
  for large or larger, `area:billing`, `kind:bug`); `paths`, globs matched on the PR's
  files; `always: true`; and `verifier: true`. `approvals.py` reads the keys, never the
  words, so a path such as `docs/verifier.md` is only a path. A glob matches every path
  the PR touches on either side of the change, a renamed or copied file's old name too, since
  moving a file out of a listed directory changes it as much as editing it. Paths it can't
  judge, past the one page of files it reads, hold, since nothing else would enforce them.
  The `verifier` term holds when the verifier judges the change high: the newest
  highest `Risk:` of its passes since the last `Scope: full` one (its first counts as one), by a trusted account,
  is `high`, any word but `low`, or missing (verifier.md). Paths beside it hold whatever the verifier says, so
  `verifier: true` with `paths` `.github/**` and `CODEOWNERS` lets the verifier decide and
  keeps those files the owner's. The gate judges it at the merge, under `auto: true` too,
  since the verdict comes after the build, and quotes the verdict. A `risk:high` it added
  for that term comes off when a later `Scope: full` pass says `Risk: low`; one added again after it
  stays. loop.md § Risk criteria adds the project's own criteria in words, which the
  verifier reads.
- `risk.critical_paths`, globs matched on the PR's files as `paths` are, names the paths
  that rate `critical`, such as the code that places orders or moves money, whatever the
  PR's labels, `spec.auto` and the verifier's `Risk:` line say. By default only the owner's
  go on its head (`approve merge <pr> --head <sha> --by owner`) lets such a PR merge, into
  any branch: `check merge`, `check queue` and `land` wait for it, a new push needs a new
  go, `approve merge --by delegate` and `delegate` refuse it, and `approved:merge` is no go,
  since a rule that depends on someone remembering a label is no rule. It is a list of its
  own beside `paths`, so a project keeps a wide list holding the spec under `auto: true` and
  a short one holding every merge. Paths it can't judge hold. `merge_paths`, its old name,
  is deprecated for one release: read as `critical_paths` with one `deprecated:` line, and
  refused beside it, since two sources of one list would drift.
- `levels` says what each level of the rating needs, so a project changes the rule without
  changing the rating: `low` (everything the rating doesn't raise), `high` and `critical`,
  each with `spec`, `policy` (`spec.auto` decides) or `owner` (a spec rated at that level
  before the build waits for the owner's record and `approved:spec`, whatever `spec.auto`
  says), and `merge`, `gates` (the gates are the merge approval), `go` (a person's go on
  the head: the owner's, or the delegate's where `loop.delegate` and the feature-branch rule
  below allow) or `owner` (the owner's own go on the head, into any branch, as above). A key
  left out keeps its default, which reproduces the rule before `levels`: `low` `{spec:
  policy, merge: gates}`, `high` `{spec: policy, merge: go}`, or under `spec.auto: true`
  `{spec: owner, merge: gates}`, and `critical` `{spec: policy, merge: owner}`. A change
  rated by several terms takes the strictest `merge` any of them asks. A term the spec's
  hold never reads (`risk:high`, an exact revert of a high-risk change, the `verifier` term,
  the cap) rates the change only after its spec was approved: it takes its level's `merge`,
  or `go` where that level's `spec` is `owner` and its `merge` is `gates`, since the owner
  never saw that rating. `high: {merge: gates}` lands high risk on the gates in a low-stakes
  repo, and the rating still shows as `risk:high`; `low: {merge: go}` holds every merge for
  a go. The verifier's tier rule stays tied to the rating: a `high` or `critical` change
  needs a default-tier verdict whatever its `merge` says. `check merge` and `land` print the
  level and the action they applied on stderr (`PR #7: risk: high (it matches a risk rule
  (path `.github/**`)); merge: go`).
- `plan` asks for the owner's approval of a matching plan.
- `bot.<login>`, such as `bot.dependabot[bot]` with `paths` `uv.lock` and
  `pyproject.toml`: a PR that bot opens needs no verifier review when every commit is the
  bot's (its authors, and its committer unless that is no account) and every file it
  changes, none renamed or copied, matches one of its `paths`, since no verifier runs on a
  bot's PR; anything else needs the review as usual. A section with `branch`, such as
  `bot.renovate` with `branch` `renovate/`, names an updater that opens its PRs under a
  person's token instead: the PR's head is this repository's branch starting with the
  prefix (a fork's PR may name any branch), and every commit is that person's, so the
  updater commits as that person (Renovate's `gitAuthor`), not as its default author. A PR labelled
  `verify` (a major update) needs the review either way. Without the section, every PR needs
  one.
- `signoff`, such as `labels` `area:ios` and `area:watch`: the owner signs off a
  matching change in use after it lands, which no gate can do for them. The rule reads as
  `risk` does, on the labels of the PR and the issue and the PR's files. The spec records the outcome in a line
  `Sign-off: owner` or `Sign-off: none`, and `owner` there asks for it where no rule does.
  The PR links such an issue with `Implements #<n>`, which GitHub does not close, so the
  issue stays open for the sign-off, and every other issue with `Closes #<n>`; `Part of
  #<n>` suits both as a link, but the PR still needs a closing line for one open issue (`check build`). `check merge` refuses the wrong keyword, and so does `check build` on
  a PR, so it is fixed before the PR reaches `land`. Without a `signoff` section
  no keyword is checked, and `Implements` is a link like `Part of`.

A change rates `high` when `risk:high` is on the PR or an issue it closes, a risk rule
matches, or the cap was reached with a blocker or major open (The cap), and `critical`
when it touches `risk.critical_paths`. A high-risk spec covered by policy is still built
and PR'd; where its level asks a go (by default `high`, but for a rule that held its spec
under `spec.auto: true`, and `critical`), its merge waits for the owner's go on its head,
asked for once `check` is green there: `uv run <this skill's folder>/scripts/approvals.py
approve merge <pr> --head <sha> --by owner`, naming the head you showed them and run in
the session where the owner said it, posts a commit status `owner` on that one commit and a
record naming it, and refuses a head that moved since; the script writes every word, so
nobody's paraphrase of the change travels with it. `--withdraw` takes the go back, removing
the `approved:merge` label too. The owner's go relayed from another session is none: ask the
owner to say it where the landing runs, or record it as the delegate's. The delegated
approver's go may be relayed to the session where landing runs: `approve merge <pr> --head
<sha> --by delegate` records it, pinned to that head the same way, with a status and a record
that name it the delegate's, so the PR shows whose go landed it, and `check merge` and `land`
print whose go they used. Into the default branch it is refused unless the policy on
`origin/<base>` sets `delegate: all` under `loop` (a branch's own edit of it is not the owner's;
a base with no policy file leaves the default branch's), and there a delegate's go counts only while it does; without the
key (`feature`) the owner's go alone covers the default branch. A status covers one commit, so
it never covers code the approver did not see; it carries to a head that only takes the base in
(the catch-up rule below), else to one whose commits since are only merges of the base, once the verifier's pass there says `Logic change: none`. Into the default branch these are the only go:
anyone with triage rights can add a label, so `approved:merge` there is no go. On a change whose level asks no go
`approved:merge` means nothing. On a PR into a feature branch (any base but the default
branch) the label added after the head's push is a go too, and it may be the delegated
approver's, where loop.md names one: once the gate is green and a satisfied verdict from the
verifier's top model covers the head, it runs `approvals.py delegate <pr>`, which adds the
label and a record naming it the delegate's. So dependent work can go on landing behind a
high-risk change. `delegate` refuses a PR into the default branch, and the branch's own
merge to the default branch is high risk while any PR merged into the branch carries
`risk:high`: the stream gets one go, as a whole, the owner's or, with `loop.delegate: all`, the delegate's. When the gate rates a change `high` or `critical`, it adds `risk:high` to the PR, except
for a term the label, read back as a `high` rating after the spec, would ask more of: a
rule that held the spec at a level on `{spec: owner, merge: gates}` (the default under
`spec.auto: true`), or a level whose `merge` is lighter than that rating's, such as
`critical: {merge: gates}` beside the default `high`. Where the level asks `gates`,
the merge approval is the gates themselves: every verifier review on the newest pass's
commit satisfied with no blocker or major open, that commit covering the head that lands,
every review thread resolved, no review requesting changes, and the base's required checks
green. A pass counts whichever model family wrote it (Independent verification).

When a spec or plan needs the owner, add `needs-owner`, comment what to approve, and stop:
a person approves by adding `approved:<point>`, by saying so in the session, or, for a spec
on a repo with a board, by moving the issue to `Ready` while it has `needs-owner` (`uv run
<this skill's folder>/scripts/board.py column <issue>` prints `Ready`), and then you run `approve --by owner`,
which records their word, adds the label and removes `needs-owner`. With `owner: <login>`
under gatekeeper.md's `loop`, `check` and `land` do that themselves for a label that login added
after the spec's last edit, since nothing in it needs an agent's judgment. Changing an
approved spec's scope or acceptance is a decision the owner never saw: rewrite the issue
body, comment briefly what changed and why, remove `approved:spec`, add `needs-owner`, stop
until they approve. A spec the owner approved and then edited for wording needs their
`approve` again, since `approvals.py` can't tell wording from scope; one covered by policy
needs nothing. `mise run loop:approvals build` before building and `mise run
loop:approvals merge` before merging check every proof (`scripts/approvals.py` lists
them); `merge` exits 3 while it waits for `check` or the owner's go, and 1 when a proof
is missing. `scripts/approvals.py` is `scripts/gatekeeper.py`'s name before #614, kept for
one release line, so every command here runs under either; gatekeeper.py's docstring lists
the verbs. The gatekeeper's own names for `approve`, `verdict` and `local-ci` are `record
approval`, `record verdict` and `record checks`, and `report --json <report>` prints a
verifier report's facts as JSON, for a flow engine that should not parse the prose. It reaches
the tracker, the forge and the evidence only through its ports, each run by the adapter the
policy's `adapters` names (Settings); `scripts/github_adapter.py` is GitHub's, the default,
read when a GitHub call misbehaves. `scripts/folding.py` builds and reads the folded comments (github.md, Comment shape). Its own commit status counts under `loop:approvals` and,
for one release line, under `gatekeeper`: a ruleset may require either, and the gate waits
for neither. An agent merges only with `uv run <this skill's folder>/scripts/approvals.py land [<pr>...]` (the
project's `loop:land` task). It lands every landable PR through the base's merge queue, the
local one or GitHub's where the ruleset requires it (Adopting the loop), so a base that moved
costs one gate, not a merge, a gate and a verdict per PR, and no PR lands on a base it was
never gated on. The two take the same candidates and differ in where the gate runs (the host,
or GitHub's CI), when (within one `land` call, or continuously) and how a red group is
isolated (one PR at a time, or GitHub's per-entry groups). The local merge queue:
- It takes a lock any host sees, the branch `loop-landing/<base>` on `origin`, so two lands never
  run at once; it only moves forward, so a host that may only create and fast-forward branches
  (a cloud session) takes and releases it too. The lock names the last PR its land
  merges, so a lock whose PR is merged and in the base was left by a land that died after its
  merges and is broken at once; one older than 2 hours (a land that died before them) is broken too.
- `land --wait` takes a free lock in waiting order: each waiting land keeps a branch
  `loop-waiting/<base>/<id>` on `origin` (a new commit on it every poll, a `done` one when it stops),
  and a land that began waiting later leaves the lock to a live older one (stamped within 10 minutes),
  unless that one took the lock last round and landed nothing (its PR is not ready): it stamps `idle`.
  Those branches are this order's state: don't delete them while a land waits; a land that is gone
  leaves one that is ignored, and removed where the host may delete.
- The candidates are every ready PR into the base whose `check merge` proofs hold, but the CI
  wait, with the owner's go where the change's risk level asks one and the base's required checks
  green. `land <pr>...` marks each named draft ready, before it waits for the lock so the holder's next batch includes it, never on a missing proof, since ready starts CI.
  Several named PRs land in one batch; one that is no candidate is left out with its reason and the rest land, the exit being the worst of them (1 over 3 over 0).
- With gatekeeper.md's `head_proof`, a candidate's head also carries a green status of its `status`
  name for its own tree, since the batch gate runs one fixed tier and some changes need
  another (a UI test tier). The lead records it on a clean checkout of the head with the tier
  set in the caller's environment, `GATE_UI_TESTS=smoke uv run <this skill's folder>/scripts/approvals.py
  local-ci --record --head-proof`: the caller's value of each `env` name wins over the gate
  line's, and the status names the values, so the verifier sees the tier. Which tier a change
  needs is the project's rule, in its own docs; `land` checks only that the proof is there,
  and its refusal names the command.
- It merges their heads onto the base in a temporary worktree, oldest first, skipping a PR
  that conflicts with a comment saying so, and gates the result's tree once, or reuses the
  gate's pass on that tree, never GitHub's required checks in its place: a PR already up to
  date with the base, with a pass on its head, runs no gate.
- Run from a clone with no working tree (a `--no-checkout` launch dir a host keeps for cloud
  sessions), every `approvals.py` command reads the tracker file, loop.md and gatekeeper.md from
  origin's default branch, and `land` merges in objects (`git merge-tree --write-tree`): it reuses
  a recorded pass on the batch's tree and, with none, refuses naming the tree, so a session with
  the files checked out runs `local-ci --record` on a head with it. It never runs the gate or
  `pre_land` there, refusing a project with `pre_land` set.
- Green: it merges each PR through GitHub in the same order, pinned to its head, and right before each
  merge call, under the lock, posts the commit status `land` on that head (success, its description naming
  the lock commit's nonce), so a base can require `land` and refuse a merge made without it; a land that
  doesn't reach the merge call posts none, and a merge GitHub then refuses turns it to an error. Only this
  GitHub merge posts it: a signed squash (`signed_squash_to`) and a GitHub merge queue post none, so a base
  that lands either way must not require `land`. It then checks the
  base ended at the gated tree, publishes the pass on the new tip, and comments `Landed` on each.
- Red: it lands one PR at a time on the last green commit (a one-PR batch's red run is its first run alone). A PR red alone twice is evicted
  (back to draft, with its log's tail), and when the first PR is red twice the bare base is
  gated: red there stops the run and evicts nobody, since the fault is on the base.

The GitHub merge queue takes no lock and runs no local gate: `land` enqueues each candidate,
oldest first, pinned to the head its proofs judged, and GitHub orders, groups, gates and merges
them. An entry the queue removes for a red check gets a comment with that check's log tail and
goes in once more; a second red on the same head turns it back to draft. A red main counts
nothing and evicts nobody, nor does a red group built on a main commit where a required check
failed, a conflict gets the local queue's conflict comment while GitHub still reports one (and
waits while GitHub works it out), and a lost `merge_group`
event costs a dequeue and an enqueue after 10 minutes. It runs in a cloud session too, with no
landing key, over the REST routes the session's proxy serves: auto-merge on enqueues, and the PR
read again right after is the head pin. `approvals.py`'s docstring has each rule.

`land <pr>... --only` lands those PRs alone and leaves every other PR untouched, for a lead that must not land another lead's work.
With `--wait` it is one background command that ends when the PR landed or needs someone
(exit 3 while it waits on the lock or CI, 1 for a refusal or an eviction; on a base with GitHub's merge queue it ends once the PR is enqueued, exit 0, and polls nothing). A land that waits follows the base when another land changes the loop's scripts or policy, so no caller needs to pull and start it again: from a clean checkout of the base it fast-forwards that checkout, from any other (a linked worktree on a PR branch or a detached head, an edited tracked file) it leaves the checkout alone and runs again from a fresh detached worktree of the fetched base, removed when it ends. Never run `gh pr
ready` or `gh pr merge` by hand, because `land` is what refuses a PR whose proof is missing. A repo with
neither `docs/agents/gatekeeper.md` nor `docs/agents/loop.md` has no rules: `land` there needs each named issue to carry
`approved:spec` and not `needs-owner`, and the PR's own proofs. A post that names a private project, its repo or a host can't be taken back, since
GitHub's edit history keeps a comment's first text: every comment and review `approvals.py`
posts, and a cloud worker's report (`omnigent_agent.py` then has the worker reply with it
instead of posting, and checks it on the host before posting it), is first checked against a local deny list, the file the environment variable
`LOOP_DENY_LIST` names, one name, repo slug or hostname per line, and refused, naming the
term and the line, when it matches. The list and the variable live outside the repo (the
project's local, untracked instructions or the shell's environment name its path), since
listing a private name in a public repo would publish it. A rule GitHub can enforce,
such as a required review or a code owner, belongs in branch protection or `CODEOWNERS`,
which the loop obeys and never overrides.

A project's own batching merge queue (`check queue`, `batch`, `batch_queue`), `carry_over_main`
and `ci: false` still work for one release and print a `deprecated:` line each, so a project
keeps landing while it adopts the batch `land`: `land` gates the merged result itself, so a
queue of its own, a carried verdict and a `local-ci` pass on the head add nothing. Adopting
means deleting the project's queue and those keys from gatekeeper.md.

A verdict, and the owner's go, recorded on head H stay valid for a new head H' that only takes the base in with no hand edit,
so `land` and `check merge` ask for no new verifier pass and no new `Logic change: none`. The gate computes the proof
(`catch_up`, one function for the verdict and the go) and prints which one carried it and from which head: for a rebase,
`git range-diff` of `merge-base(H, base)..H` against `merge-base(H', base)..H'` marks every commit `=`, with none added or
dropped; for a merge of the base, every commit after H is a merge of the base whose first parent is the previous head and
whose `git show --remerge-diff` is empty. A resolved conflict, a changed or new commit, or a dropped one keeps the old
rule: no verdict on H' until a verifier reviews it, and the go carries only on `Logic change: none`. A clean catch-up
changes no line the PR wrote, so only what the old pass would have read for how main's new code meets the PR's is left
to the head's own gate; a project that sets `carry_over_main` keeps its own `except` rule for the verdict instead.

Deprecated: with gatekeeper.md's `carry_over_main` section, merging main into a PR head H keeps H's verdict
when git shows the merges changed nothing the PR's code reads: every commit from the new
head H' down its first parents to H is a merge with a commit on main as its second parent,
its tree is `git merge-tree`'s of its parents (no conflict resolved, nothing added), and
main's changes since the merge base touch none of the PR's files, and neither the PR's
changes nor main's touch an `except` glob, since a config change on either side was never
reviewed against the other side's code. H's verdict then covers H', over one merge of main
or several; `check merge`, `check queue` and `land` print one line per merge naming it, its
first parent and the predicate. Anything else (a PR commit after H, new, edited or rebased,
a conflict, an evil merge, an overlapping file, a touched except path, a git error) carries
nothing, and the check prints which condition failed: the head needs its own verifier pass. The gate never carries: H'
runs its own, as CI does, and under `ci: false` that is `local-ci <pr> --head <H'> --run` on H', since a
`local-ci` record stands in for CI on one exact tree. This skips a review on purpose, so a
project opts in by writing the section.

With `opt_out: true` in gatekeeper.md, a developer may keep their own PRs out of the
loop, by the line `Engineering loop: off` in their personal instructions and nothing on the
PR. `check merge` then reads a PR with no loop trail (no verifier review, no
`Approved: spec` record or `approved:spec` on an issue it links, no `Reverts #<n>` line,
not an exempt bot PR) as outside the loop: it prints one line saying so and exits 0, so the
`loop:approvals` status is green and the PR's author merges it their usual way, under the
repo's own rules. `land` leaves it out of every batch and, named, prints the same line and
exits 1, so no agent merges it. Risk rules and `risk:high` hold no PR outside the loop; the project
accepts that by setting it. A spec a policy covers is no trail, since under
`spec.auto: true` every issue is covered. Any trail puts the PR back under every proof. Without
it, a PR with no trail fails the gate.

## Roles

- **Lead** ([lead.md](lead.md)): takes a request to merged PRs, one per story, and
  runs every step above. A session whose brief names no role is the lead, since workers
  and verifiers are given theirs by the brief that starts them.
- **Worker** ([worker.md](worker.md)): implements a piece of the spec, or a list of
  findings, on its own branch. The lead follows it too when it builds itself.
- **Verifier** ([verifier.md](verifier.md)): reviews the PR, drives its instance, and
  leaves the tree as it found it.

Agents are started, messaged, watched and closed with the `orchestrating-agents` skill
(`../orchestrating-agents/SKILL.md`), which picks the backend and holds its rules, reports
and questions as files among them. Inside a worker or
verifier, review angles run as native subagents, never as full harness sessions.

## Where heavy steps run

One rule, for every project, every machine and every role, and the only place placement is stated: role files and briefs point here instead of restating it. A heavy run is any of these, whoever makes it: implementation, the gate, the verifier's test and mutation runs, proof runs, and a lead's own suite, build and e2e runs (rerunning a suite on a branch to sort its failures counts). The light work stays where the lead is: spec, triage, merges, posting, `land`. A heavy run goes, in this order:

1. To a Claude cloud session: the agent the project's `docs/agents/loop.md` names on its `Cloud worker:` line, else `claude-cloud` (Cloud worker), since a cloud session adds only a bridge process to the host. The gate and the verifier run on the same machine as the worker, which shares its checkout and build. The loop.md line `Placement:` sets where the verifier runs: `same machine` (the default when the line is absent), `hosts: <name>, <name>` or `CI`. It replaces the older `Cloud verifier:` and `Verifier hosts:` lines, which keep their meaning where a project still has one; the new line wins. For a host worker the same default means that worker's own host. A worker's machine that can't take the verifier (no Codex login, a PR that needs a Claude verifier) goes to a Codex Cloud thread, then a host.
2. Else to a host that offers the harness the step needs, under the start's capacity check; with `Cloud worker: none` every heavy run starts here. A `start` in a cloud session without `--host` follows `Placement:`: the first online host it names, and a refusal naming `--host` where it names none, never the host the bridge runs on.
3. A step that needs a particular machine (a production service, a device, an Apple build, a browser login) stays on that machine, and a run the VM is known not to make goes straight to a host.

On a host, the verifier reviews in the worker's own worktree when lead.md step 7's shared-worktree conditions hold, else in a detached worktree of its own; in the cloud and with `Placement: same machine` it already shares the worker's VM.

When a launch fails, for any reason, take the next option on this list: a cloud launch that is refused, whose setup fails twice, or that is out of quota goes to a host (option 2), and a host that refuses, has no capacity or is unreachable passes the run on to the next host. The lead's report says which run went where and why, since a run moved off the cloud loads a host the owner expects to stay free. Never fall back to running the step locally on the host that refused: what a machine accepts is its own configuration, so a refusal is the answer and not an obstacle. If no option is left, stop and report the refusal's text. Which machines may run a project's work is the host's own note (`~/.agents/host.md`), never this rule, which names no machine.

A brief that names a host worktree for a test run says where the code is, not where the run goes: the run still takes the first option above that can make it. A lead's own heavy run takes the cloud route in one call, with no worker or PR needed: commit and push the branch, then orchestrating-agents' `omnigent_agent.py claude-cloud-run [--checkout DIR] -- <command>` (its Omnigent backend has the details), which runs the command in a cloud session on that HEAD, prints the report path and exits with the command's own code; when the cloud route fails it exits 125 and prints why. The engineering pack's PreToolUse hook makes this the default in a Claude Code session on a host with an Omnigent server configured (`RUNNER_SERVER_URL`): in a repo whose loop.md has no `Cloud worker: none` line, it refuses a test or check command (a pytest suite, `mise run check*`/`test*`, `make test`, `npm test`, `cargo test`, `go test`, `local-ci --run`, and the like), naming the `claude-cloud-run` call for it; without a server, which the cloud route needs, it lets the run go ahead and says on one line that it stayed on this machine. The host fallback is the prefix `LOOP_HOST_RUN=<reason>`, which the hook lets through: use it only when `claude-cloud-run` failed, or when the run needs this host (a device, a `host` gate step), and say in the report which run went to the host and why. A child the launcher placed on a host is told to use it, since its placement already chose the host.

Where the orchestration backend is native (no Omnigent), a heavy run's cloud route is orchestrating-agents' `scripts/claude_cloud.py start <task file>`, which pushes the branch and starts the cloud session from any agent's Bash, since a bare `claude --cloud` needs a terminal a subagent lacks. The lead or subagent then waits on the session's results through the branch's PR (`gh pr view`, `gh pr checks`). Where the project's cloud environment is missing, `start` prints one line naming `claude-cloud:setup` and exits 2: the step then runs locally, and the report says so in one line that names `claude-cloud:setup`, since the colleague who has not run it is the one who can fix it.

With a cloud worker, a host makes no gate pass, since the worker's VM already holds the checkout and build and the host's cores run the sessions. When `local-ci <pr>` on a host finds no pass for the head, have the worker run `local-ci --record` on that head and push its record, then run `local-ci <pr>` again; never `--run` it, or `--record` it, on the host. Two steps stay on the host because no cloud pass can cover them: a `host` step of `gate_steps`, and `land`'s gate of a batch tree that no recorded pass covers.

## Cloud worker

With the loop.md line `Cloud worker: <agent>, gate <task>`, the lead runs on
the host and the workers run in the cloud, with the verifier in the worker's VM unless `Placement:` says otherwise (Where heavy steps run), as sessions of `<agent>`, a registered
Omnigent agent whose tools run in a cloud VM, which the lead starts. Without the line the
same holds with `claude-cloud` as the agent and the policy's `gate` as the gate, so a project
needs no setup before its heavy runs leave the host. The cloud worker's gate is one rule, which overrides that default where loop.md has an `Affected tests:` line: `affected-tests` when loop.md has an `Affected tests:` line, else the `Cloud worker:` line's gate task, else the policy's `gate`. A line that opens `Cloud worker: none`,
with the project's reason after it, keeps workers on hosts: nothing in this section applies
and every role file reads as written. A project that has the line keeps its meaning. `env <name>` on the
line (`Cloud worker: <agent>, gate <task>, env <name>`) names the project's cloud environment, the one
whose setup installs its tools: `start` and `launch-dir` resolve the name on the host's claude
login to that environment's id and pin it, so loop.md holds no id of one account; with no `env`,
the environment named after the repository is used, else the account's `Default`. orchestrating-agents'
`omnigent_agent.py cloud-env <checkout>` (also `claude-cloud-env`) creates the environment, or updates it,
from the checkout's committed `.claude/claude-cloud-setup.sh` (the older `.claude/cloud-setup.sh` is still read) and `.claude/claude-cloud-environment.json`, with no secrets; a colleague without Omnigent runs `claude_cloud.py setup` (a project's `mise run claude-cloud:setup`), which adds the private registries' network secrets and a proof run. The split takes coding,
compiling and unit tests off the host. What stays there is what the VM can't do: every
thread resolution, since GitHub's GraphQL API answers 403 in the VM (`approvals.py` reads REST
there, so its `check`, `local-ci`, `verdict` and `land` also run in the VM, `land` on a base that requires GitHub's merge queue with no key, and on a signed-squash repo only with its `signing_key_env`); the signed land without that key, since the VM holds none; a verifier of the other family, since Codex
has no cloud bridge, unless it runs in the worker's VM, the default (Verifier in the worker's VM, below); anything that needs a device, a simulator, an emulator, a browser login
or the owner's private network.

- **Who does what.** The lead runs intent, spec, the branch and draft PR, `check build`,
  triage, the fetch and merge (or fast-forward) of each worker's reported branch into the
  PR branch, the worker's gate where it runs (below), the instance, the verdict's post, thread
  resolution, `land` and acceptance. The worker's gate (the rule above, Adopting the loop; on a fix round started detached beside the
  next verifier, lead.md step 7) runs in the worker's VM, on its checkout and build; `Placement:` never moves it, since that line places the verifier only; a `local-ci --record` pass it makes (`ci: false`, on the ready head) is reused by the host's
  `local-ci <pr>`, `check merge` and `land`, while `affected-tests` records nothing. The worker codes and compiles, runs `mise run <task>`,
  the light gate (what the VM can run: compile, unit tests, headless web tests on its
  Chromium), before each push, and pushes to the `claude/…` branch its session was given,
  since a cloud session declines any other branch without its own user's permission and a
  peer's brief is not that; no brief names another push target. A worker's `local-ci --record`
  pass is pushed as its record branch as a host's is, and the host's `local-ci <pr>`,
  `check merge` and `land` reuse it from there, so nobody pastes or copies the record. Its brief names the role
  file by its path in the repo, since the host's worktrees and paths don't exist in the VM. The verifier runs in the worker's VM by default (Where heavy steps run), else on a host in a detached worktree at the head, or on another host loop.md's `Placement: hosts:` line lists, as lead.md step 7 says.
- **The PR is the interface for content.** The code is the worker's pushed branch. Its
  report is one comment on the PR: its branch and head SHA, each light-gate command with its
  exit code, what it left out and why. If the post fails, since the session's proxy-injected
  `GH_TOKEN` can expire 10 to 20 min in, its reply is `UNPOSTED REPORT` and then the body
  verbatim, and the backend's `wait --pr` posts it from the host. orchestrating-agents' `--pr` (its Omnigent backend, Cloud
  workers) has the worker post it and writes it to the report path on the host, so the lead
  reads a file as for any worker. The verdict is the review `approvals.py verdict` posts.
  The verifier names its evidence (screenshots, logs, result bundles) in its report, and the
  lead attaches its media to the verdict comment with `gh pr comment --attach` (gh 2.99.0 or
  later, as the `demo` skill does), giving alt text for an image only (`--attach
  './shot.png#The error state'`), since gh refuses it for a video and `approvals.py` refuses
  a screenshot posted as a release asset; logs and bundles too large for a comment stay
  named files in the report. So the worker fixes a failure from its diagnostics without the
  host.
- **Control flow is the lead's own.** It starts the worker with `run --pr` (from a
  host without the worker's harness, `start --top-level --host <host> --pr`, then
  `wait --pr`), which keeps the session, and `--no-keep` where it won't be sent to again, follows its turn end, and sends a fix list or a failing log, naming the
  review or comment to read, to that kept worker with `send --pr` while it is still there,
  since a fresh session is a fresh VM, clone and build and a kept one revives with its clone;
  else as a fresh `run --pr`. Nothing in
  the cloud calls the host, through MCP or otherwise, since such a tool can drop mid-run and
  stall the work, and nothing new watches the PR.
- **Wait on the signal, not the turn.** A cloud worker's gate and verifier post their own
  end on the PR, so wait on that rather than on the worker's turn, which may end before its run
  does: orchestrating-agents' `omnigent_agent.py wait-for --pr <n> --until gate` settles when
  the PR's current head has a pass (the record branch `local-ci --record` pushes, or a green
  `gate` status; exit 1 on the `gate` failure status a failed `--record` run writes), and
  `--until verdict` when a comment or review naming the head on its `Head:` line holds a
  `SATISFIED:` line (exit 1 for `no`, or for a `## Verifier question` posted after the head's
  commit), printing the URL it read. Both read REST only, so they run from a launch dir with no
  working tree. The newest gate signal wins, so a failure after a recorded pass is exit 1, and
  `--since <ISO time>` ignores signals older than a run restarted on the same head. Exit 6 is the
  budget: call it again. Where the failure status cannot be written (a cloud VM's proxy refuses
  status writes), a failed run reads as exit 6 until the budget; with `gate_steps`, exit 0 is one
  step's pass, and `local-ci <pr>` says whether the whole gate has one.
- **Proof.** The worker proves what the VM runs. The full gate's host-only parts (emulator,
  simulator and device tests), the instance, the acceptance examples and the evidence are
  the lead's and the verifier's, on the host. A failure there costs a round trip (relay,
  fix, push) instead of a local rerun, so it goes back with its diagnostics on the PR.
- **Host builds.** The host compiles at most once per verifier pass, the full gate and the
  instance build together, plus at most one compile for the verifier's mutation check, since
  taking builds off the host is the split's point; a worker's iterations compile only in the
  cloud.
- **Nothing on GitHub names a host, a path or a session**: not the report, the verdict, the
  evidence or a brief's text quoted there, since a public repo publishes them.
  The commits too: the cloud harness tells each session to end every commit with a
  `Claude-Session:` link, and neither a brief nor a committed `attribution.commit` in
  `.claude/settings.json` removes that instruction; a PR body it writes ends with a bare line
  holding the link even under an empty `attribution.pr`, and its proxy appends a `_Generated by
  [Claude Code](<link>)_` footer to every body and comment it writes. `land` drops each of these
  lines from the squash body and, before the merge, from the PR's body and comments on GitHub,
  so `main` and the PR page stay clean; `check merge` names any such text the account can't
  edit (a comment by another account), for a person to clear. The PR branch's commits keep it. A private repo may accept
  that. A public repo publishes its branch commits, so it strips the line at the source with
  `approvals.py commit-msg <file>`, which removes every such line and folds the
  blank lines as `land` does: its pre-commit config runs that command at the `commit-msg`
  stage (a local hook, `stages: [commit-msg]`), and the cloud environment's setup installs
  that hook type (`pre-commit install --hook-type commit-msg`), since a session's clone has
  only the hook types its setup installed.
- **Verifier in the worker's VM.** With `Placement: same machine` (or the old `Cloud verifier: worker session`), the verifier of a
  Claude-written PR is Codex run in the kept worker's VM, in its checkout, so a pass reuses the clone, the
  installed tools, the build and the running containers instead of paying for them again on a host; the sharing a
  host verifier gets from lead.md step 7's shared worktree.
  A Codex-written PR gets Claude there (`verify --harness claude`), as does a Claude-written one when Codex can't
  run (same-family, named so in the verdict); it runs on the session's own Claude login, so `seed` stays Codex-only.
  `scripts/cloud_verifier.py` does it, and its docstring has each command. On the host, `login` once, then
  `seed` before starting the worker: it stores a copy without the refresh token in the cloud environment,
  of the host's own Codex login when that has a day left, else of a login of its own that it keeps fresh, so no VM
  can break a login for the others. A host login with under `--host-refresh-days` left (default 3) is refreshed in
  place, the way the Codex CLI does it, in one atomic replace of the host's `auth.json`; a refused refresh exits 2
  and names `codex login`. `--env` repeats, to seed every environment in one run. To keep them fresh without the
  owner, run `seed` every 2 days as an Omnigent scheduled task on the host that holds the login, on a small model,
  keeping the run (`sys_session_keep`) when it exits non-zero. The script never prints a secret's value, in its own output, a
  traceback or the verifier's, and a refused seed is described by its length, hash and days left, which is how to check one. In the VM, `verify --pr <n> --brief <file>` refuses a tree with uncommitted changes outside the report's folder, checks out the
  PR's head, runs Codex on the brief and posts the report as a PR comment. The worker's session only carries
  the pass: the lead sends it the brief `approvals.py brief` prints, with `send --pr`, asking it to save the
  brief to a file, run that command detached, poll it and end its turn with the URL it prints, changing and
  reviewing nothing itself. `wait --pr` writes the comment to the report path, and the lead posts the verdict
  from it as for a host verifier. The VM has no Codex configuration, so the lead passes the model and effort
  the host's Codex is configured with as `--model` and `--effort` (or the `Verifier model:` tier's model);
  without them the CLI's own default runs. It also passes `--requested <unix seconds>`, the time the lead asked for
  the pass (`date +%s` when it sends the brief), so the comment's `Seconds:` footer and the run's JSON line can
  show how long the pass waited to start. Exit 3 means the verifier stopped on a question, posted as that
  comment: answer it and send the pass again. Exit 4 means the pass left the checkout changed, whatever else it did (the
  verifier's leftovers, or a checkout that failed part way): the script deletes and restores nothing, since git
  can't say which leftover hides an older file, so the checkout stays as it is, named in the output, and the
  worker puts it back before the next pass, which refuses a tree with changes. Exit 1 is a failed pass: Codex failed (a login that ran out shows here, in its output),
  wrote no report, or the comment could not be posted. Exit 2 names a missing precondition, such as a session
  without a login: seed again and start a fresh session, since a session gets the login when it starts. The project accepts
  three things with the line: the author's session starts its own verifier, though the script, not the
  session, picks the head and posts the report; the environment holds a ChatGPT login that every process in
  the VM can read, good for up to 10 days, so it suits PRs the owner's own agents wrote and not ones from
  forks; and the carrier spends its quota while it waits.
- **Verifier on a Codex Cloud thread.** With `Placement: same machine` (or the old `Cloud verifier: worker session, else codex thread`), a
  pass with no worker VM to carry it (the PR has no Claude cloud worker, or Claude tokens are short) runs on a Codex Cloud
  thread, driven from the host: `scripts/cloud_verifier.py thread --pr <n> --brief <file> --model M --effort E`. The
  host's own Codex login goes to OpenAI's endpoint only, never to a VM. It starts a thread (a VM that keeps its files and
  Docker images), checks out the PR's head there, sends the brief as a turn, reads the report back from the thread's
  checkout (else the final message) and writes it at the brief's `- Report:` path on the host; the lead posts the
  verdict from it as for a host verifier. It prints the weekly Codex quota before and after, the thread id and its
  environment id; a later pass passes `--thread` and `--env` to run on the same machine. Use the routes in this order:
  the worker's VM when a Claude cloud worker holds the build, the thread otherwise, a host verifier last. Never for a
  Codex-written PR: it needs a Claude verifier. The endpoint is undocumented and may change, so every surprise ends
  in exit 2 ("use route 2 or the host verifier"): take that exit as the cue to use the next route, never to skip the
  verifier. Exit 1 is a pass that wrote no report with a `SATISFIED:` line.
- **Auto-fix stays off on loop PRs** (a cloud session that subscribes to its own PR), since it
  pushes fixes and replies on threads by its own judgment, which is the lead's triage, and the
  lead already briefs the worker on each fix.

## Rules for every role

- **The owner is on the loop, not in it.** They read specs, never code: gates, tests and
  the verifier are the review. Ask them only at a fork that changes what gets built,
  before something hard to undo (deploy, publish, send, spend), for a credential only
  they hold, or at an approval gatekeeper.md's policy requires. A technical fork they can't judge is your call. Run commands yourself; when
  a guard blocks one, ask once for a scoped approval, then propose a narrow allow rule,
  never an interpreter-wide one. While they are away, make the reversible decisions, log
  each in one decision-log issue, wait out a usage limit and resume, and leave a handoff
  (`handoff` skill) when finished or stuck. Never idle: schedule a time-gated check and
  keep working.
- **Owner steps park, they don't block.** A step only the owner can unblock (a GUI
  dialog, a locked screen, a device, a permission prompt or classifier denial, a
  credential, an approval link that expires) is stopped at its first sign, so a hang
  becomes a failure, and whatever it holds (a gate slot, a lock, an instance) is released.
  A tool call held for approval is waiting for the owner, not hung: never make its change by
  another route (REST, another tool, a script), since the approval is the owner's control
  over what agents change and any agent holding a token could step around it. Carry on with
  other work, or, in a session the owner reads, end your turn `USER NEEDED` naming the prompt.
  Comment `Owner step: <the exact action>, unblocks <what>` on its issue or PR, unless an
  `Owner step:` for the same action is already there, since a second copy reads as a second
  ask; add
  `needs-owner`, add a checklist line to the decision-log issue so the owner clears every
  step in one sitting, and move to the next item; ask once, since a retry while they are
  away fails the same way. Before a long or unattended run, try once each owner-only
  prerequisite the queued items need (loop.md § Proof on a branch, the specs' acceptance)
  while the owner can still answer, and check such a precondition before a heavy step
  takes a slot.
- **One heavy gate per host slot.** Leads on one host share its cores, and gates run at
  once slow every one of them several times over and starve new sessions of the capacity
  to start. So the project's test part runs behind a host-wide slot that every worktree
  shares: the template's `scripts/gate-slot`, or, in a project without it, a lock on a file
  of the same set, `${XDG_CACHE_HOME:-~/.cache}/engineering-loop/gate.<n>.lock`, around its heavy check (a lock
  frees itself however the run exits). The host has `<N>` slots, `gate.1.lock` to `gate.<N>.lock`: `GATE_SLOTS`
  when it is a whole number from 1; else, where loop.md states what one run of its heaviest gate costs, `Gate cost:
  <cores> cores, <GB> GB` (optional `, reserve <GB> GB`, by default a quarter of the host's total memory, at least
  4 GB), the smaller of the cores ÷ the cost's cores and (total memory − reserve) ÷ the cost's GB, at least 1, since
  a gate that starts a database runs out of memory before cores; without the line, a third of the cores, at least 1.
  Total memory, never available memory, so the count never moves between runs and a waiter never waits on a slot
  that no longer exists. `approvals.py heavy --plan` (the template's `gate-slot --plan`) prints the count and the
  limit that set it, and a wait for a slot says the same line. A run takes the first
  free one and waits, saying so once, only when every one is held; `GATE_SLOTS=1` keeps one heavy gate on the host
  at a time, for a project whose gate needs the whole host, and `GATE_SLOTS=off`, for a person alone on a machine
  of their own, runs every command with no lock. A parallel runner takes the `GATE_JOBS` it exports (the
  cores free at start), never `-n auto` or a fixed count, and never more than the host's cores divided by `<N>`,
  since `<N>` gates load the host at once and a larger share each would oversubscribe it.
  A land's gate step holds the landing lock while it waits, which stops every other land, so it takes a freed slot
  ahead of a waiting PR gate: a waiting land holds a shared lock on `gate.land.lock`, and a PR gate that finds it
  takes no slot until no land waits. A project's own wrapper takes the same care: it skips its lock when
  `LOOP_GATE_SLOT_HELD` names any `gate.<n>.lock` of that directory, not only `gate.1.lock`, since a gate under slot 2
  would otherwise hold two; one that waits in a plain blocking `flock` is woken by the kernel ahead of a polling
  gate, so a project that wants a land to go first has its wrapper take its slot the way `approvals.take_slot` does
  (this repo's `tools/gate_slot.py`). With one slot a land blocks in the kernel too, so it competes evenly with a
  wrapper's `flock`.
  The cost of polling is that a gate waiting in a plain `flock` on the same file is woken by the kernel ahead of a
  `local-ci` or `mutate.py` run that polls, so on a host shared with a project whose wrapper blocks that way, its
  runs go first; a project that minds has its wrapper take its slot as `take_slot` does.
  `test:changed` while iterating and the lint parts stay outside the slot. `approvals.py`'s
  `local-ci` and `land` take a slot's lock around each gate step they run and set
  `LOOP_GATE_SLOT_HELD` to its path, as `mutate.py` does (both through one function, `approvals.take_slot`), so a wrapper under them that finds
  the variable naming its lock takes none, since it would wait on its own parent.
  Beside it runs a short lane, a lock on `${XDG_CACHE_HOME:-~/.cache}/engineering-loop/gate.short.lock`, which
  a job expected to finish within the policy's `short_seconds` (Settings, default 120) takes instead of the
  heavy one, so a two-minute job waits only for another short job, never behind a long gate: at most one heavy
  and one short job load a host at once. A short-lane run that goes past `short_seconds` prints one overrun
  line, so a job wrongly declared short shows in its log; `short_seconds: 0` turns the lane off and every job
  takes the heavy slot. `mutate.py` measures rather than declares: it runs the tests once on the unmutated head
  in the short lane and keeps the patches there only when that run passed within `short_seconds`.
  The slot limits how many heavy steps run at once; the heavy wrapper limits what each takes. A host turns it on with
  one line in `${XDG_CONFIG_HOME:-~/.config}/engineering-loop/host`, a `heavy_wrapper = <prefix>` line (`key = value` lines, so later host settings share the file), a command prefix (`systemd-run --user
  --scope --quiet --slice=loop-heavy.slice -p CPUQuota=400% -p MemoryMax=6G --`), and every heavy step then runs under
  it: each gate step of `local-ci` and `land`, the `pre_land` check, `mutate.py`'s test runs, and any command run as
  `uv run <this skill's folder>/scripts/approvals.py heavy <cmd>`. Without the file every step runs as before; a prefix
  that can't run (its command not on `PATH`, or `<prefix> true` failing) prints one line and runs the step unwrapped,
  so the gate never fails for it, and a wrapped step carries `LOOP_HEAVY_WRAPPED=1`, so a heavy call under it adds no
  scope of its own. Limits given on the scope cap each step alone; `systemctl --user set-property loop-heavy.slice
  CPUQuota=… MemoryMax=…` caps all of them together. A database server's backend runs in the server's own cgroup,
  so wrapping its client caps only the client.
- **Independent verification.** The verifier is a fresh session, never the author's. It
  is of the other model family when that family is installed, within quota and the
  backend can start it (native starts only its own harness's subagents; Omnigent starts
  either), since it misses different things; otherwise, as for a user with one family installed, a fresh
  session of the same family is the normal path. When Codex refuses, lead.md's Verifier route names the two fallbacks, Gemini through agy and then a same-family Claude, each labelled; a satisfied one lands a change of any risk like a Codex verdict. The PR body names which ran
  (`verifier: same family` for the latter). A PR with code from both families gets a
  verifier for each family's changes where both are available, integration edits
  included; each writes its own report, and the cap counts rounds they share. The family
  is a preference the lead follows and a record, not a gate: the verifier names it
  in its review's heading, and the merge gate checks only that the newest pass on the head
  is satisfied, whichever family wrote it, since the heading is the verifier's own word
  and proves nothing the gate could hold it to. loop.md's `Verifier session: reuse` keeps one
  verifier session across a PR's passes (lead.md step 7): it stays independent of the author but
  not fresh, so a project chooses it knowing its costs: the verifier anchors on its own earlier
  findings, the lead's triage replies can persuade it, and its context grows until it compacts. A brief never says who wrote the code or
  why the verifier shares its family: that biases the review. A verifier reviews a pushed
  PR head only, never an untracked helper script, a scratch wrapper or a mid-edit
  snapshot, since a review of what will not land proves nothing about what will: a helper
  worth reviewing is committed on a PR, and the cap counts PR passes only.
- **Reports are files**, sent as a path to whoever started the agent
  (orchestrating-agents, Reports are files).
- **Evidence, not claims.** Report each step's real exit code: a chain's status is its
  last command's. Prove a tooling or config change with a live round trip where it runs,
  and "can't" with a real call. Before saying done, check each item of the owner's
  feedback against what shipped, taking their example as one case of a class.
- **Stop on repeated failure.** Three tool calls in a row failing with the same error,
  even different calls, mean stop and report yourself blocked with the error line. That
  includes a permission classifier that fails closed because its provider is down: every
  retry is a full-context turn.
- **Flaky tests.** A project's `check` retries a failed test once, with its runner's own
  retry option, and prints each test that passed only on the retry; the gate is then green.
  Without one, rerun only the failed tests once, then only the parts of `check` the failure
  stopped, never the whole gate, whose minutes each flake would otherwise cost again; all
  green, the gate is green, and the report gives each command with its exit code. A
  `ci: false` project needs the retry option, since its `local-ci` record runs the whole
  `check`. Each test that passed on the retry has one open
  `kind:bug` issue titled `Flaky: <test id>`: search the open issues for the id before
  filing, and comment each occurrence on it (head SHA, PR, run, failure line), so two leads find
  the same issue and its comments count the occurrences. An occurrence is its head SHA plus
  the failing run (a CI run's id, else the time the local gate started): a report whose pair
  the issue already has is that occurrence again, not a new one, since two leads reading one
  run would otherwise count it twice toward the third. The third occurrence gets a PR
  from main that skips the test in the blocking gate, citing the issue, which stays open
  for the fix. A test red on both tries is a real failure: run it on main before blaming
  the PR.
- **Land small and soon.** Every PR branches off a freshly fetched `origin/main` and merges
  as soon as its gates pass, because a branch that lives as long as the work behind it goes
  stale against main, and a pile of them cascades on every rebase and breaks main when they
  land. An epic lands as one PR per sub-issue, each off main, with no epic or integration
  branch. A sub-issue whose work isn't usable yet lands unexposed, so main stays
  releasable while the epic is half done: wired into no entry point, or behind a flag the
  user docs don't name yet. The sub-issue that exposes it comes last, and documents the
  flag or removes it.
- **One concern per PR.** A change the spec's diff doesn't need (agent config, a skill,
  CI, tooling, an unrelated fix) gets its own PR from main, so it can be reviewed and
  reverted alone. A finding goes on the open PR's branch only when it makes that PR wrong
  or unmergeable: a review blocker or major, a bug the PR introduced, its CI failing, or a
  break on main the PR would cause. Anything else (a minor, an improvement, an adjacent bug
  found on the way) waits for that PR to land and starts from main, because on its branch
  it restarts the PR's review and CI and couples two concerns; chains of follow-up PRs come
  from PRs landing slower than they are produced, and fast landing makes the wait cheap.
  `approvals.py overlap <pr>` (or `overlap --files <path>...` for a story with no PR yet) lists the other open
  PRs into the same base that change a file this one does, with each side's hunk lines and whether the two heads
  merge cleanly (`brief` prints it on stderr), so the lead lands or orders the overlapping ones first.
  Never push to a PR someone else owns, since that rewrites work under its owner: comment
  on it, or wait for it to land and start from main. Before filing an issue or starting a
  fix, search the open issues and PRs of this repo, and of the repo that owns the cause,
  for the symptom (the test id, the error line, the file), since the board's `Build`
  column misses an issue filed an hour ago and agents sharing one account share an
  assignee: comment your evidence on what you find, use it, and don't pause other work
  waiting for it; whoever filed first owns it. An issue an open PR links is taken, so
  the lead opens its draft PR when it cuts the branch (lead.md step 3). A PR another lead
  opened is taken over only on the word of that lead or of whoever started the leads,
  recorded in the PR thread so other leads see the new owner, never because it looks
  idle, since an idle PR may be waiting on CI or on an answer its lead still owns.
- **Stacks are one deep.** Stacking on an unmerged branch is the exception for when
  waiting isn't possible, and only on a PR already in Land (verdict triaged, waiting for
  CI), because a base still in review changes under its stack and every change cascades.
  Its owner moves the stacked PR onto main the moment its base lands, and it lands itself
  with its own `Closes` or `Implements`. Anything else waits, or builds
  on main behind a seam.
- **Revert first.** When main goes red after a merge, or a merged change proves wrong in
  use, the first fix is a revert PR off main, because a revert returns main to a state
  that passed, while a fix forward holds every other merge back and ages every branch. The
  reverted PR's issues reopen with a comment naming the revert, and the fix forward is a
  new change through the loop.
- **Review trail on the PR.** The PR opens as a draft with the branch's first push, and
  every commit after it is pushed. Each verifier pass is posted as a PR review with
  `approvals.py verdict`: one inline comment per finding, labelled `Verifier (<family>),
  pass <n>`, and a summary carrying the verdict. The gate reads these reviews, so the
  review is the verdict. Resolution follows triage, and the verifier never triages: the
  worker resolves only a thread it fixed, reason `ADDRESSED`, replying with the fixing SHA;
  the lead resolves a deferred finding `WONT_FIX`, replying with its triage and the
  issue it waits in, and a rejected one `INVALID`, with the one-line why. The owner may
  override any resolution, and alone dismisses a teammate's `CHANGES_REQUESTED`; an agent
  dismisses one only when the owner asks for that review in the session, quoting the ask
  in the dismissal. A human review follows the same pattern. The PR is marked ready once no core finding (blocker or major)
  is open, and squashed on merge. The PR keeps a public trail of what was found, fixed and
  iterated, and the project's CI skips draft PRs, so it doesn't run on half-done work:
  the worker's `Affected tests:` selection (`approvals.py affected-tests`, else `mise run check`) on each pushed head is the check while a PR is a draft.
- **Remove, don't append.** Remove a thing as if it never existed. Edit and compress
  rather than append. A process failure or a costly manual step becomes a deterministic
  tool (a script, one call, no judgement). A routine that finds nothing to do succeeds
  silently.
- **Models.** Every start names a model fit for the job, never the harness default. The owner's named model wins; else loop.md's `Worker model:
  <tier> for <condition>` line names a tier for a worker whose issue matches the condition
  (on the issue's labels), so the choice sits in one file the owner can change; else the lead
  picks by design complexity times risk, for a worker and a verifier alike: `small` for mechanical work (a rename, a generated file, a docs fix); `mid` for the usual range and when unsure; `top` for high complexity or high risk; `frontier` only for very high complexity or very high risk, since "high" is common and `frontier` costs several times `top`. Effort high or below. A `Lead model: <tier> for <condition>` line does the same for a
  Claude lead: `start --top-level` reads it on the lead's host and starts the lead on the tier
  when the issues its brief names match the condition (`size:<S> or smaller`, size order XS < S < M < L < XL,
  or a bare label; a brief naming no issue, or issues with no size label, never matches),
  and `--model` outranks it. A line it can't parse fails the start. A `Verifier model:` line does the same for a verifier whose PR
  matches, judged as `check merge` judges risk: on the labels of the PR and its issues and
  on the PR's files, so a PR that `check merge` rates high never gets a lower tier. The
  verifier's own `Risk:` line comes after the launch: a lower-tier verdict that says
  `Risk: high` takes the PR out of the condition, so the PR needs a default-tier verdict on
  its head before it lands, even when the lower-tier verdict is satisfied; `check merge`
  reads the tier from the verdict's `Verifier:` line (verifier.md) and refuses until then. It applies within the verifier's own family: it lowers the tier, never the family, which
  stays the other one from the author's (Independent verification). The tier is `frontier`, `top`, `mid` or `small` (Claude's Fable, Opus, Sonnet, Haiku;
  Codex's Astra, Sol, Terra, Luna; each family names its own), so one line holds for every family
  and outlives a release. Resolve the tier
  at launch from the newest generation of the family's tier models only: its model of that
  tier, else its closest higher tier (its highest when none is higher), never an older
  generation's model, which the family has already superseded (`omnigent_agent.py start` refuses a Codex model when the host lists a newer generation). A lead that can't read the
  family's current lineup (the backend's Model section) names the tier's alias, and when the backend refuses a model it can't check (its Model section), waits for a host that lists them. A launch that fails on
  capacity takes the next placement option (Where heavy steps run); with none left it is retried
  later on the same model (the backend's Model section). When one
  family is out of quota, continue on the other in a fresh session briefed from the run's
  notes, the spec and the PR, never a fork of the old session, since every turn of a fork
  re-reads the whole transcript it copied; revive a stuck or interrupted agent rather than
  restart it.
- **Turns.** A turn the owner reads (not a child's path-only reply) ends with `DONE`,
  `STILL WORKING` or `USER NEEDED`; a `USER NEEDED` line wins over an earlier `DONE`, since an ask
  after it still needs its answer. A status reply opens with a tl;dr: the loop step with
  links to the spec, the PR and the instance, what is blocked, what the owner must do (or
  "nothing"), and each open question restated. Past about 150K tokens of context, at a
  natural break, offer the owner a ready compact command with the summary it should keep.
- **Landing.** Land starts once the last verdict is triaged with no core finding open and
  the ledger is updated; it writes the PR's evidence and runs `approvals.py land <pr> --wait`,
  which marks it ready and lands it with every other landable PR in one gated batch. The PR merges only when the newest
  verdict covers the head that lands, the required checks are green there, and, where the
  change's risk level asks a go (Approvals and proof), the owner's go is on that head.
  The verdict's commit is the head itself: any commit after it, a merge of main included,
  needs a verifier pass first, and a triage or comment is no verdict.

## Triage

Two axes per finding, judged by how the system is used (loop.md § In use), not by what a
hostile input could do. **Path**: core (the happy path a user or the pipeline hits every
run), edge (a real but rare input), theoretical (an input the system never produces, or
an interleaving nobody can trigger). **Cost**: silent (a wrong result, lost data or a leak
that nobody sees) or visible (crash, stale result, usability).

| Path | Silent | Visible |
|---|---|---|
| core | fix now | fix now |
| edge | fix if a one-liner, else fail-fast guard + ledger | ledger |
| theoretical | reject, one line why | reject |

A fail-fast guard is the cheapest thing that turns a silent wrong answer into a loud
refusal at the boundary (an assert on the assumption, a raise naming the ceiling) plus a
`ponytail:` comment. A rejection costs one line in the PR body. A fix that needs a new
mechanism (a lock, a trap, a baseline format) is a design change: one design note or ADR,
implemented once, not iterated against the verifier. A finding that contradicts the spec
may be resolved by correcting the spec.

The ledger (loop.md § Ledger) has one line per entry: what, where, the guard if
any, what would make it matter, and its issue. The lead writes it during triage,
in the fix commit; the verifier reads it first and does not re-report entries.

Everything real the PR leaves unfixed is placed before the report. The test: would
closing the spec's issue without it be dishonest?

- **Yes, it is within the issue's own acceptance:** the issue stays open, the PR says
  `Part of #n` and closes a new sub-issue of #n that holds the part done (`check build`
  refuses a PR with no `Closes`), and a comment on the issue names what remains (a
  comment, since an edit to the spec needs approving again).
- **No, it is outside it** (a ledger entry, or a bug, a flaky test or a problem only the
  owner can fix, `needs-owner`, found outside the spec's diff): a new issue stating
  problem, cause, fix, acceptance and a `Found while #n …` line. It is a native sub-issue
  of the originating issue's epic, or of the originating issue itself when that issue's
  own goal contains it and it has no parent, which makes it an epic
  ([issues.md](issues.md), Epics): the PR then says `Closes #<that issue>`, since an epic stays open
  until its sub-issues are done. Otherwise it stands alone. Attached, it counts toward
  the epic's progress instead of starting a chain of follow-ups the board shows as a flat
  list.
- **Its cause is in another repo** (a shared skill, a tool, a project template): two
  issues. In the repo that owns the cause, a generic one: problem, cause, fix and
  acceptance, the case described so it holds anywhere; when that repo is more public than
  this one, it names none of this project's names, products, customers, tickets or links.
  Here, one for this project's side: what happened, the plan (adopting the fix, a
  workaround meanwhile), and a link to the generic issue. Links point from the less
  public repo to the more public one, never back.

A rejected finding is not real, so it gets no issue.

## The cap

The cap is 3 passes, unless the project's gatekeeper.md sets its own with `cap` under `loop` in its policy.
Every other file says "the cap", so this is the one place to change it, and
`approvals.py` reads the same value. Pass 1 reviews the PR's full diff; each later pass
up to the cap reviews the diff since the previous report and reruns its repros. No fix
lands without review: every head that lands has a satisfied verdict on that exact head,
so any commit after the last verdict, a merge of main included, gets a verifier pass of
its own. The one exception is gatekeeper.md's `carry_over_main`: clean merges of main that touch
none of the PR's files keep the verdict (Approvals and proof).

- **The last pass under the cap leaves a blocker or major open:** stop and ask the owner,
  since the fix keeps regressing and only they decide what happens next. They have two
  options. One is a fix followed by one pass past the cap, scoped to the open items. The
  other is leaving the code untouched, and parking or closing the PR. You never fix and
  land on your own call: `land` holds such a PR for the owner's go on its head.
- **The last pass under the cap leaves only minor or edge findings open:** ledger them and
  file their issue (Triage), leave the code untouched, and land on the satisfied verdict.
  There is no owner stop.
