# Tracker: GitHub

How the loop's issue conventions ([issues.md](issues.md)) are done on GitHub. A project
whose `docs/agents/issue-tracker.md` says `Tracker: GitHub (engineering-loop's github.md)`
follows this file in place, never a copy, so a fix here reaches every project. Run `gh`
inside the repository: it infers the repo from the remote.

## Operations

- Create: `gh issue create --title "..." --body "..."`
- Read: `gh issue view <number> --comments`
- List: `gh issue list --state all --json number,title,body,labels,url`
- Comment: `gh issue comment <number> --body "..."`
- Label: `gh issue edit <number> --add-label "..."` or `--remove-label "..."`
- Close: `gh issue close <number> --comment "..."`
- Parent: an issue has at most one, and `addSubIssue` refuses a pair that already exists,
  so read the sub-issue's parent and both node ids first:
  `gh api graphql -F owner='{owner}' -F name='{repo}' -F n=<sub-issue> -F p=<parent> -f query='query($owner:String!,$name:String!,$n:Int!,$p:Int!){repository(owner:$owner,name:$name){issue(number:$n){id parent{number}} parent:issue(number:$p){id}}}'`.
  No parent yet:
  `gh api graphql -f p=<parent id> -f s=<sub-issue id> -f query='mutation($p:ID!,$s:ID!){addSubIssue(input:{issueId:$p,subIssueId:$s}){subIssue{parent{number}}}}'`.
  Already that parent: done. Another parent: it belongs to that epic; `replaceParent:true`
  moves it only when that one is wrong.
- Write access, which `spec.auto`'s `sub-issue` asks of a sub-issue's author: GitHub's
  collaborator permission, `gh api 'repos/{owner}/{repo}/collaborators/<login>/permission' --jq .permission`,
  is `admin`, `maintain` or `write`. It covers access through a team, which an issue's
  `author_association` does not.
- Risk, on an issue or a PR: `gh api 'repos/{owner}/{repo}/issues/<number>/labels' -f 'labels[]=risk:high'`,
  the call `approvals.py` makes, which creates the label where the repo has none.
- Epic: `gh issue edit <number> --add-label epic`, after
  `gh label create epic --color 8250DF --description "An outcome the owner tracks; its work items are sub-issues"`
  when the repo has no such label.

Pull requests are not a triage request surface.

## Posting under a person's account

Anything an agent writes under a person's GitHub account on a project that is not the
owner's own (an issue, a comment, a PR body, a reply) opens with the line `> 🤖 AI`, so
readers can tell the agent's words from the person's own; words the person dictated
verbatim go after the block, outside it. On the owner's own repo every word is an agent's,
so the line is dropped; `approvals.py` still skips it in old comments. The records
`approvals.py` posts (`Approved:`, `Assigned:`, `Local check passed`, the verifier's review)
keep their format, since their first lines already say who wrote them and the gate parses
them. A `## Spec` or `## Plan` comment may open with the marker: `approvals.py` skips that
leading line when it reads the heading.

## Labels

`uv run <this skill's folder>/scripts/labels.py` syncs the repo's labels with issues.md, Labels; `--dry-run`
prints the same plan and writes nothing. The project's `mise run setup:github` runs it; run
it by hand, `--dry-run` first, only to resync between setups. Its docstring says what it does, in order. The calls it makes:

- Rename in place, so every open and closed issue and PR keeps the label and its timeline
  shows no remove and add: `gh api -X PATCH 'repos/{owner}/{repo}/labels/<old>' -f new_name=<new>`
  (`gh label edit <old> --name <new>` is the same call). GitHub refuses a new name that
  exists, so a fold adds the new label to each carrier and removes the old, then deletes it.
- Who carries a label, open and closed, issues and PRs:
  `gh api --paginate -X GET 'repos/{owner}/{repo}/issues' -f labels=<name> -f state=all -f per_page=100 --jq '.[].number'`.
  A label any issue or PR carries is never deleted, since that loses who had it.

## Assignee

The calls behind issues.md, Assignee. `uv run <this skill's folder>/scripts/approvals.py check build <pr>` (a number no PR has is read as the issue, like `--issue`) reads
who added `approved:spec` (the approver) from the issue's timeline, refuses an issue
assigned to anyone else, and, once every build proof holds, assigns the approver where no
one is and the PR its issue's assignees. Before assigning it comments `Assigned: @<login>`
on the issue as the record that the loop made the assignment; when that comment is refused
it says so and leaves the issue unassigned. When you park an issue (`needs-owner`) or drop
it, run `uv run <this skill's folder>/scripts/approvals.py release <issue>`: it removes an assignee that record
names, unless someone assigned them again after the loop did, and keeps any other. Assign by hand
only a person: `gh issue edit <number> --add-assignee <login>`.

## Review trail

The calls behind SKILL.md, Review trail on the PR. `gh api` fills `{owner}` and `{repo}`
from the remote.

- Post a pass: `uv run <this skill's folder>/scripts/approvals.py verdict <pr> <report>`. It posts one review
  on the report's `Head:` commit, event `COMMENT`, because GitHub refuses
  `REQUEST_CHANGES` and `APPROVE` on your own PR. One comment whose path or line is outside
  the PR's diff at that commit refuses the whole review (422, `Path could not be resolved`
  or `Line could not be resolved`), so `verdict` moves a line to the nearest diff line and
  puts a finding whose file is outside the diff in the body.
- List the threads, each with the id to resolve it and its first comment's id to reply:
  `gh api graphql -F o='{owner}' -F r='{repo}' -F n=<pr> -f query='query($o:String!,$r:String!,$n:Int!){repository(owner:$o,name:$r){pullRequest(number:$n){reviewThreads(first:100){nodes{id isResolved path line comments(first:1){nodes{databaseId body}}}}}}}'`.
- Reply on a thread: `gh api 'repos/{owner}/{repo}/pulls/<pr>/comments/<first comment databaseId>/replies' -f body="Fixed in <sha>."`
- Resolve it with the triage's reason, `ADDRESSED`, `WONT_FIX` or `INVALID` (SKILL.md,
  Review trail on the PR): `gh api graphql -f t=<thread id> -f r=ADDRESSED -f query='mutation($t:ID!,$r:PullRequestReviewThreadResolutionReason){resolveReviewThread(input:{threadId:$t,resolutionReason:$r}){thread{isResolved}}}'`.
  GitHub keeps no readable reason, so the reply says why.
- Dismiss a review, only as SKILL.md, Review trail on the PR allows:
  `gh api -X PUT 'repos/{owner}/{repo}/pulls/<pr>/reviews/<id>/dismissals' -f message="<the owner's ask, quoted>" -f event=DISMISS`.
- `gh pr create --draft` needs a commit the base lacks: before anything is built, push an
  empty one (`git commit --allow-empty -m "<spec title>"`), which the squash drops.

## Board

A GitHub Projects board linked to the repo (the `github-project-board-setup` skill of the
`utilities` plugin creates one, with an Epics view and the Parent issue and Sub-issues
progress fields shown). `uv run <this skill's folder>/scripts/board.py <issue> <column>` adds the
issue when it is missing and sets its column, so the board's built-in workflows stay off, as
they are on a board created through the API, except "Item closed", which sets the column
`Done` shows in: GitHub closes an issue on a PR's `Closes` without the loop moving it, and a
closed issue is in no other loop column (one waiting for sign-off stays open). The
`github-project-board-setup` skill's `scripts/project_workflows.py` switches it on. That
column is named `Closed`, mapped from `Done` (below), since a closed issue may be completed,
not planned or a duplicate, and the card's icon says which. Its views show the Assignees field next to Status, so the board
shows whose each ticket is. Where the project ranks work, the board's `Priority` single-select
field holds it, since it takes one value per item, in its options' order, where an item can carry
several labels; the gate never reads it. `uv run <this skill's folder>/scripts/board.py column <issue>` prints the later of the
loop column the issue's board column shows and the one its labels give, so an issue with `approved:spec` reads
`Ready` even when its move failed or the repo has no board. Both take and print the loop's names.
The board's `Risk` single-select field (`Low`, `Medium`, `High`) holds a PR's risk beside its `risk:high`
label, one value where labels could show two. `check merge` sets it, adding the PR to the board: `High` beside
the label, else the verifier's `Risk:` word, so whoever makes the risk call sets it; a field already at `High`
adds the label, with a comment naming the field, and a lower one never takes the label off. The label stays the
merge check's only input, since a workflow's token can't read a board a personal account owns, so a board it
can't read or set (no board, no `project` scope) is a line in its output, never a failure.
`board.py field <issue or PR> <field> <option>` sets any single-select field by name the same way.

A board with other column names, or one column for several loop columns, maps them in the
project's `docs/agents/issue-tracker.md` settings under an optional `board`, one
`loop column: board column` line per mapping:

```yaml
board:
  Build: In progress
  Verify: In progress
  Done: Closed
```

A loop column the section does not name keeps its own name. `board.py <issue> <column>` sets
the mapped board column; a name that is no loop column goes as is. Where several loop columns
share a board column, `column` reads it as the earliest of them, since the board can't tell
them apart: the labels still say `Ready`, and an open PR says it is past it. A board status
nothing maps and the loop does not name prints as is. Without the section nothing changes.

## Publish an issue batch

Every set of issues an engineering skill produces is one publication batch. It is
fingerprinted and resumable so that an interrupted run neither duplicates nor loses an
issue.

### Canonical batch

- Titles are the issues' identities inside the batch. Stop on a duplicate title, an
  unknown blocker or a dependency cycle.
- Order: repeatedly take, among the tickets whose blockers are all already ordered, the
  one with the smallest exact UTF-8 title bytes; number them from 1 as `order`.
- Sort and deduplicate each issue's labels by exact UTF-8 bytes and its blockers by
  their `order`. Preserve titles and bodies byte-for-byte.
- Serialize the list of issues, in `order`, as UTF-8 JSON with only `title`, `body`,
  `labels`, `blockers` and `order`: object keys sorted, Unicode characters emitted
  directly, comma and colon separators without surrounding whitespace. The lowercase
  hexadecimal SHA-256 of those bytes is `batch_sha256`.
- Append each issue's marker to its body after a blank line:
  `<!-- agent-skills-batch:{batch_sha256}:ticket:{ordinal} -->`

### Durable state

Store the approved batch at
`.scratch/agent-skills/github-issue-batches/{batch_sha256}.json` with `version`,
`batch_sha256`, `approved`, the complete canonical issue list (each issue also holding
its marker, marked body, and resolved URL or `null`), and a `relationships` list
recording each edge's blocked order, blocker order, and `pending` or `confirmed` status.

Write state atomically after every transition: sibling temporary file, flush and
`fsync`, atomic replace, `fsync` of the parent directory. A partially written file is
never valid resume state. Stop when an existing state file is malformed, or its
fingerprint or canonical batch differs from the current batch.

### First publication

1. Search every marker across all issue states with
   `gh issue list --state all --search "<marker>" --json url,body`, and count only
   bodies that contain the exact marker. Record a single match's URL in the proposed
   state. When several issues contain one marker, stop before approval and report every
   matching URL.
2. Render one numbered review with every issue's order, title, complete marked body,
   labels and blockers, then the exact remaining write plan: each missing issue
   creation followed by each pending relationship edit.
3. When the plan contains external writes, ask exactly:
   “Create these GitHub Issues now?”
   Rejection, an edit request or no answer records no approval and writes nothing. A changed title, body, label, blocker or derived order is a new fingerprint
   and starts this flow over.
4. After approval, atomically persist the exact batch with `approved: true`, then run
   the first mutating `gh` command with no remote read in between.

### Create and resume

A run on an exact, already approved batch keeps its recorded approval. Before the next
external write, search every marker again, reconcile each unique match into state and
persist it; this recovers an issue GitHub created when the command response or the
following state write was lost.

- Create only issues whose URL is still `null`, in canonical order, passing the
  approved title, marked body and labels unchanged to `gh issue create`. Persist and
  print each returned URL immediately.
- On any command failure or interruption, stop with the current durable state; the next
  run reconciles again and does not ask for approval of the same fingerprint.
- Once every issue has a URL, add the native sub-issue and blocking relationships in
  canonical edge order with an idempotent add, so replaying a pending edge yields the
  same graph. Mark an edge `confirmed` only after its command succeeds. Where native
  relationships are unavailable, make an idempotent body update with the confirmed
  `Part of` and `Blocked by` URLs.

Approval covers only the displayed missing issue creations and relationship edits for
this fingerprint. Closing, commenting on, relabeling, assigning or editing unrelated
issues needs separate authority.

<!-- github-issue-batch-fixture-protocol
version: 2
canonical_fields:
  - title
  - body
  - labels
  - blockers
  - order
marker: "<!-- agent-skills-batch:{batch_sha256}:ticket:{ordinal} -->"
approval_prompt: "Create these GitHub Issues now?"
ordering:
  algorithm: stable_topological
  ticket_tiebreak: title_utf8_bytes
  blocker_order: final_ticket_order
  unique_titles: true
state:
  directory: .scratch/agent-skills/github-issue-batches
  filename: "{batch_sha256}.json"
  atomic_write: sibling_temp_fsync_replace_directory_fsync
  durable_fields:
    - batch_sha256
    - approved
    - canonical_marked_issues
    - resolved_urls
    - relationship_statuses
external_write_boundary:
  - gh
  - issue
  - create
first_run:
  reconcile_before_preview: true
  exact_remaining_write_plan: true
  approval_immediately_before_write: true
resume:
  reuse_exact_batch_approval: true
  reconcile_before_write: true
  recover_lost_create_response: true
search:
  state: all
  before_creation: all_markers
  exact_body_marker: true
matches:
  zero: create
  one: reuse_and_report_url
  multiple: stop
creation_order: dependency
relationships:
  phase: after_all_issue_urls
  replay: idempotent_pending_edges
-->
