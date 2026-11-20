# Issues and the board

The loop's issue conventions, the same in every project and on every tracker. How each
is done on a tracker is its realization file, read in place: [github.md](github.md) for
GitHub, with the issue-batch protocol `to-tickets` and `wayfinder` publish through. The
project's `docs/agents/issue-tracker.md` names that file in one line,
`Tracker: GitHub (engineering-loop's github.md)`, and adds only its own facts: its settings block
(SKILL.md, Settings: components, extra categories and labels, renames, board columns) and Never on GitHub.

## States

Two labels are an issue's state; the others classify it or record an approval. Every
issue starts as an intent, whoever raises it, so each phase can run in a different session
that acts on the state it finds.

- **No state label:** an intent that needs triage: the owner's loose idea, bug or
  feedback, an agent's first write for a request, or what a PR leaves unfixed.
- **`needs-owner`:** waiting for the owner: a decision research can't settle (the
  questions are a comment), a step only they can take, or their approval of a spec or
  plan gatekeeper.md's policy does not cover.
- **`approved:spec`:** ready: the spec is written into that same issue and approved
  (SKILL.md, Approvals and proof). Where a tool owns an issue's body, the spec is a comment
  headed `## Spec`. The spec step sets the size label; who approves, the owner or their
  policy in gatekeeper.md, and how, is SKILL.md, Approvals and proof.

The `triage` skill's categories map as bug = `kind:bug` and enhancement = `kind:enhancement`,
and its roles as needs-triage = no state label, needs-info =
`needs-owner`, ready-for-agent = `approved:spec`, which only the owner adds (a spec the
policy covers needs no label, since the gate reads the policy): a `ready-for-agent` label that
`to-spec` or `to-tickets` would set is not added, since a label without its approval would
read as approved.

## Labels

- **Category**, exactly one, set by whoever files the issue and corrected at triage:
  `kind:bug` (something a user or the pipeline hits is wrong), `kind:enhancement` (new or
  improved behaviour), `kind:chore` (tooling, CI or agent configuration only; no
  behaviour changes), `kind:documentation` (docs only), or `kind:<name>` for one of the project's extra categories.
- **Component**, at least one, set with the category: where the change lands,
  `area:<name>` for a name on the project's list.
- **Size**, exactly one, set by the spec step, once the code has been read. It is
  the size of the change, not a time estimate, and an intent has none: `size:XS` one line
  or one config value; `size:S` one module, the lead builds it; `size:M` several
  modules, one worker; `size:L` several workers or slices in one PR; `size:XL` too big
  for one spec: split it, or run it as a wayfinder map.

- **Approval**, `approved:spec` and `approved:plan` on the issue: added with the owner's
  approval (SKILL.md, Approvals and proof), so adding it is how they approve, or as the
  ready state of a spec gatekeeper.md's policy covers. `approved:merge` on a PR into a
  feature branch whose risk level asks a go is a go on its head, the owner's or the delegated approver's; into the default
  branch only `approvals.py approve merge` gives the go, and the label is none (elsewhere the gates
  are the approval and the label means nothing).
- **Risk**, `risk:high` on an issue or PR: the rating, saying its consequences are high (money,
  data, security, another team's contract); what a high change needs at merge, by default the
  owner's go, is gatekeeper.md's `levels` (SKILL.md, Approvals and proof). A person sets it, or the lead at
  triage, and `approvals.py` adds it to a PR when gatekeeper.md's `risk` rule matches, a path
  `risk.critical_paths` names is touched, or the cap was reached with a core finding open. It names consequences, not urgency: how soon a
  thing matters is the tracker's priority (its realization file says where it lives), which the
  gate never reads.
- **Queue**, `loop:queued` on a PR: `land` added it when it put the PR in GitHub's merge queue, and
  takes it off once the PR's `Landed` comment is written, or once it merged outside the queue, so a later `land` finds every PR the queue
  merged; nobody sets it by hand.

A wayfinder map or ticket carries its `wayfinder:` label instead of a category, and no
component or size: it resolves a decision, not a change.

Label names are the loop's fixed set here plus the project's `docs/agents/issue-tracker.md`
(its settings' `components`, `categories`, `labels`); the scripts read them from these two places only
(`scripts/approvals.py`, `label_names`). The tracker file names a component or category
bare (`billing`) or in full (`area:billing`); both mean the label. gatekeeper.md's policy name
a label in full, as GitHub shows it.

The repo's labels are synced from the same two places (github.md, Labels): every listed
label exists, an unlisted one goes once nothing carries it, and a renamed one is renamed in
place, so every issue keeps it. The tracker file's `renames` is the rename map, one
`old: new` line per label:

```yaml
renames:
  frontend: area:web
```

The loop's own renames need no line: `bug`, `enhancement`, `chore` and `documentation`
become their `kind:` names, and a listed component's or extra category's
bare name becomes its label. A line stays harmless once its old name is gone.

## Assignee

The assignee says whose issue it is; who is working on it shows in its board column.

- Assigning only claims an issue: the owner may assign themself to hold one for later. The
  go-ahead is still `approved:spec` or the owner's ask, never the assignment.
- Someone else's issue is theirs: the loop never builds an issue assigned to anyone but
  the person who approved its spec, and `approvals.py check build` refuses one.
- One build per issue: `check build` refuses a PR that closes an issue another open PR
  closes too, naming that PR and its branch, since each build runs its own verifier, gate
  and queue.
- When building starts and no one is assigned, the loop assigns the approver, and the PR
  gets its issue's assignee (`check build` does both, github.md, Assignee).
- Parked or dropped, the loop removes only an assignment it made; a claim the owner made
  stays.
- Agents are never assignees, since the column, not the assignee, says which agent is on it.

## Epics

An epic is an issue whose goal is an outcome the owner tracks; its work items are its
native sub-issues. It carries the `epic` label next to its category, so a board view can
filter for epics, and it closes when its outcome holds, that is when its sub-issues are
done. Prefer converting an existing issue whose spec already states the outcome over
filing a new one. Its stories are filed before its approval is asked for (lead.md,
Spec). An epic lands as its sub-issues' PRs, one per sub-issue, each off
main, with no epic or integration branch; a sub-issue whose work isn't usable yet lands
unexposed, and the sub-issue that exposes it comes last (SKILL.md, Land small and soon).
A slice's PR says `Closes #<its sub-issue>`: GitHub shows a PR in an issue's Development panel only for a closing
keyword, so `Part of #<epic>` alone leaves the epic and the PR unlinked, and `check build` refuses a PR with no
`Closes` of an open issue. The epic shows progress through its sub-issues and closes when the last one does. One issue is one PR: the merge closes the issue, and `check build` already refuses a second open PR for it, so more work gets its own sub-issue. A PR may close several issues, but one is the norm.
Two levels only: a sub-issue never has sub-issues of its own, since the
board's Parent issue field names only the direct parent and a grandchild would not show
under its epic.

## Board

The board shows every ticket in its loop stage with its assignee, and every epic with its progress; the
realization file says how a ticket moves. A project whose board has other names, or one column for
several of these, maps them in `docs/agents/issue-tracker.md`'s `board` settings ([github.md](github.md), Board). The labels stay the state: when a move fails,
report it and carry on.

| Column | The ticket is here when | Moved by |
|---|---|---|
| `Intent` | filed, no state label | whoever files it |
| `Needs owner` | it has `needs-owner` | whoever parks it |
| `Ready` | it has `approved:spec`, or gatekeeper.md's policy covers its spec | the spec step, or the owner approving |
| `Build` | its draft PR is open | the lead |
| `Verify` | the verifier has the PR | the lead |
| `Sign-off` | its PR merged with `Implements #<n>`, and it waits for the owner to check it in use | the lead, after landing |
| `Done` | closed | whoever closes it |

## Sign-off

Where gatekeeper.md has a `signoff` rule and it, or the spec's `Sign-off: owner` line, ask for
it, a person
checks the merged change in the running product before its issue counts as done, since
gates and the verifier prove the code, not how it feels in use. The PR links the issue with
`Implements #<n>` (SKILL.md, Approvals and proof), so the merge leaves it open; the
lead moves it to `Sign-off` with a comment naming the merge and the spec's
acceptance examples to try. Without a `signoff` section nothing waits for a sign-off, and
`Implements` is a link like `Part of`. The owner signs off by closing it (`Done`). What they find
wrong is a new intent with a `Found while #<n>` line, or a revert when the change itself is
wrong (SKILL.md, Revert first). An epic stays open while any sub-issue waits for its
sign-off.
