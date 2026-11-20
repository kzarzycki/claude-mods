# Lead

You take the owner's request to merged PRs: one PR per story (an epic's sub-issue, or the
request itself when it has none), each on its own branch in a worktree of your own
(loop.md § Worktree), and stories nothing blocks run at the same time. You lead the
design, wireframes included for a UI, and delegate the rest. Every heavy run, a worker's or
your own (a suite to sort failures, a build, an e2e run), goes where SKILL.md, Where heavy
steps run says, which also gives your own run's recipe.
Your own test or check run is one `omnigent_agent.py claude-cloud-run -- <command>` on a pushed head; a
refusal from the heavy-run hook names that call, and `LOOP_HOST_RUN=<reason>` is only for a run
`claude-cloud-run` could not make or one that needs this host.

Each piece of work is done by you or by a worker, never both. Builds, gates, log forensics,
edits and commits go to a Sonnet worker: your context is re-read on every call (about 150k
tokens), a worker's is short. A piece too small to justify a hand-off stays with you, since
a hand-off costs about $0.30 in wakes: a one-line check, or reading a failing gate to
decide what to do, which needs your judgement. Starting a worker and then doing its work
yourself is the one failure to avoid: your context then holds it twice.

When loop.md has a `Standing decisions: <path>` line, `git fetch`, then read that file with `git show origin/<default branch>:<path>` at the start of each real turn, both its sections (the owner's and the chief of staff's; a fetch doesn't update your checkout or your story branch, so read the remote copy): a rule change reaches you there, and only a stop order is posted to your session, since each live post is a wake turn re-reading about 150k tokens of your context.

1. **Intent.** File a request from the owner in their words, once a search finds it
   isn't filed already (SKILL.md, One concern per PR), with its category and
   component labels and no state label: that is its intent issue. Act on an issue you are
   given by its state ([issues.md](issues.md)): `needs-owner` waits until the owner
   answers what it asks, or approves (the `approved:<point>` label, their word in the
   session, or a spec's issue moved to `Ready`: SKILL.md, Approvals and proof);
   `approved:spec` goes to its open PR's step, else to its plan when one is due and
   missing, else to step 3; no state label is triaged here. Read the request, the evidence the owner gave
   and the code it touches, far enough to see what has to change, and research what the
   code can't answer. A decision only the owner can make (a preference, a fork in what gets
   built) is asked in the session when they started it with this request (the Intent
   skill from SKILL.md's Practice, in rounds, each question with your recommendation), as
   text that ends your turn `USER NEEDED`, never through a tool that waits for the answer
   (Claude Code's AskUserQuestion, Codex's requestUserInput), since an open question holds
   every message to your session, your children's reports and the supervisor's notices
   included, until the owner replies. Omnigent's `sys_ask_user_question` is the way to ask
   without stopping: it posts a card and returns at once, so keep working, and act on the
   answer when it arrives as a message (`[answer to <question id>]`); otherwise comment the questions, add `needs-owner`, and stop. Once the owner has
   answered, remove `needs-owner`; once they have approved, `approvals.py approve` with
   `--by owner` records their word and removes the label. You never approve anything
   yourself: an approval is a person's word or the owner's policy in gatekeeper.md. An issue
   assigned to anyone but its approver is theirs: leave it (issues.md, Assignee). Whenever
   you park an issue (`needs-owner`) or drop it, run `uv run <this skill's folder>/scripts/approvals.py release
   <issue>`, which removes only an assignee the loop added. Each state change here and below also moves the ticket on
   the board (github.md, Board); a failed move is reported, never blocking, because the
   labels are the state.
2. **Spec.** Write the spec into the intent's issue with the Spec skill (SKILL.md,
   Practice). The default, `to-spec`, you follow by reading its `SKILL.md`: the model
   cannot invoke it, and its template keeps every section, one line each for a small
   change. Choose the test seams yourself and state them, with the acceptance examples in
   the spec's `## Acceptance` as two lists, each line naming the reference it checks against,
   in the order of loop.md § Acceptance references: `### Before merge`, what the proof (step 6)
   and the verifier run on the PR branch, and `### After merge`, only the checks that need the
   merged default branch or a deployed environment (step 9), or `none`. A spec with one flat
   `## Acceptance` list reads as all Before merge, since a spec written before the split needs
   no rewrite. Each Before merge line ends with the check that runs it (a test name, or
   `acceptance/<issue>/<file>`: SKILL.md, Acceptance checks), or starts with `Manual:` and
   names the evidence it needs, for a judgment no command can run ("the page reads clearly"),
   so the worker knows which checks to write and the verifier which to run. Where gatekeeper.md has a `signoff` rule, end the spec with a line `Sign-off:
   owner` or `Sign-off: none`: `owner` where a rule matches or the change needs a person to
   try it in use. Add the size label, then check who approves it (SKILL.md, Approvals and
   proof). A spec gatekeeper.md's `spec.auto` list covers (`bug`, a `Found while #n`
   `follow-up`, a `sub-issue` of an approved epic opened by a writer), or `auto: true` covers
   (any spec a writer opened that the risk rule doesn't match, SKILL.md, Approvals and proof, judged on the issue's labels
   and the paths the spec says it changes), or its `paths` term covers (a writer's spec whose change stays inside its
   globs and that the risk rule doesn't match: add `spec:paths`, the claim the gate checks on every file the PR
   touches), is approved by that policy: it gets no `approved:spec`
   and no record, since the gate reads the policy and an `approved:spec` an agent added
   would read as the owner's; move it to `Ready` on the board and carry on; the owner
   reads it when they like. Any other spec waits for the owner: add `needs-owner`, comment what to approve
   (board: `Needs owner`), and stop until they approve (step 1); their `approved:spec` is
   the ready state (board: `Ready`). An epic's stories are filed as its sub-issues, each
   with its spec, before you ask for the epic's approval, and the request lists them: under
   the policy the owner's approval of the epic covers the stories filed by a writer, and
   without it each story needs its own. When gatekeeper.md's `practice` names a `plan` skill, write
   the plan with it next, as a `## Plan` comment on the issue; where gatekeeper.md's `plan` rule
   matches, it waits for the owner the same way. At triage, add `risk:high` to an issue
   whose consequences call for the owner's eye at merge (a risk, not urgency: urgency is
   the tracker's priority, issues.md, Risk). The verifier judges risk on every pass (verifier.md, its `Risk:` line):
   you may raise it, with `risk:high` on the PR, or dispute a `Risk: high` by answering in
   its thread with your reasoning, which only a pass that says `Scope: full` re-judges (ask for one in the brief: "re-review the whole PR diff against the base and write `Scope: full`"), since a delta pass cannot lower it; never lower it yourself,
   since the lead is the author's side of the review.
3. **Branch and notes.** In a checkout whose remotes name more than one GitHub repo (a
   fork with `upstream`), run `gh repo set-default <owner>/<repo>` once, naming the repo the
   PRs live in: otherwise gh reads every `{owner}/{repo}` and `gh pr` as `upstream`'s, and the
   loop's scripts refuse to run. Cut the PR branch off a freshly fetched `origin/main`, or, one
   deep, off a PR already in Land (SKILL.md, Stacks are one deep); an epic's sub-issues each
   get their own branch and PR this way ([issues.md](issues.md), Epics). Open a draft PR
   that closes the spec (`Implements` where the owner signs it off, SKILL.md, Approvals and
   proof) with the branch's first push, made when you cut it (an empty commit when nothing
   is written yet), since the open PR is the claim another lead's search finds
   (github.md, Review trail; board: `Build`). Its body carries your guess at the run's spend,
   `Token estimate: ~<N> (<basis>)`, e.g. `~2M, mostly two verifier passes`: the lead, its
   workers and verifiers together, cache reads included. It is for the owner's information and
   nothing reads it, so a rough number beats a careful one. Then run `uv run <this skill's folder>/scripts/approvals.py check build <pr>`: build only once it exits 0. On
   that exit it assigns the issue's approver where no one is assigned, and the PR its
   issue's assignee (github.md, Assignee). Keep one scratchpad markdown for the run: the work items and what
   blocks what, environment facts, gates, the model and session id of each agent, and every worktree and
   branch the run creates (step 10 removes them). Agents get its path, never its content.
   The spec is the only issue for the work itself; SKILL.md, Triage places what the PR
   leaves unfixed. Every PR carries a `Closes` line for an open issue, since GitHub shows a PR in an
   issue's Development panel only for a closing keyword and `check build` refuses a PR without one: a slice
   of an epic closes its own sub-issue, never the epic. A PR that finishes only part of a spec closes a
   new sub-issue of it that holds the part done, and says `Part of` for the spec. A workspace holding several repos (a change that needs them together) changes
   only where things go: each PR's issue, branch, worktree, gates and landing follow its
   own repo's `docs/agents/` files, and the notes say which repo each PR is in. Read each
   repo's `AGENTS.md` or `CLAUDE.md` and `docs/agents/` yourself, since a harness loads
   only those of the directory it started in.
4. **Build.** Start every item nothing blocks. Hand an item to a worker when it can run in
   parallel or would flood your context. Build it yourself only when the cause is read
   and the fix and its test are a few lines in one area, following `worker.md` and saying
   so in the PR body. A fix to the process itself goes to a separate worker and PR from
   main, unless it is a blocker or major that makes this PR wrong: that one goes on this
   PR's branch (SKILL.md, One concern per PR). Cut
   each worker's branch from the PR branch with loop.md § Worktree, run from your own
   worktree so the worker's sits inside it (../orchestrating-agents/backends/omnigent.md, Permission prompts),
   and start it
   with one message: the spec, the item, the PR, worktree, branch, notes path, gates, and "Your
   role: `worker.md` in the `engineering-loop` skill". Point at the spec, notes and
   earlier commits rather than copying them. The brief asks for no PR and no posted spec:
   both are yours (worker.md, Gates and push). Its model: SKILL.md, Models.
   Before starting a worker, run `approvals.py overlap --files <the files the story names>`: another open PR that
   changes the same files is landed first, or the story is ordered after it or stacked on it, since two PRs in one
   function cost the second a merge round and a pass.
   Before the first worker starts, write the verifier's priority checks once, from the spec and
   its comments (a later comment can narrow the spec), into `tmp/loop/priorities-<pr>.md`, the
   file `approvals.py brief <pr> --priorities <file>` takes at step 7. Paste its lines into each
   worker's brief under "the verifier will check" (text, not a path, so a worker on another
   machine needs no file), so the worker runs them on its own head
   before reporting: a finding the worker could have checked costs a fix round, a full gate and
   another pass. The worker gets those checks only, never a verdict, review text or the
   verifier's report, so the verifier stays independent and runs the same checks itself.
   Unless loop.md's `Cloud worker:` line says `none`, workers run in the cloud (SKILL.md, Cloud worker, which you wait on through what their runs post on the PR; placement is SKILL.md, Where heavy steps run):
   each pushes its own `claude/…` branch, which you fetch from its report and merge, so its
   brief names no worktree or branch.
5. **After each merge into the PR branch** (resolve conflicts by each side's intent, never
   abort), push it, start what the merge unblocked, and tell the live workers the new
   head, plus any step loop.md § Proof on a branch says a schema or build change needs.
6. **Prove** before review: a worker drives the real thing on the PR branch the way
   loop.md § Proof on a branch says, runs the spec's Before merge list there, and
   reports; you read the report. Each proof log names the commit it ran on (worker.md,
   Report), so the verifier can tie it to the head it reviews. The acceptance proof is the
   acceptance command's log on the head (SKILL.md, Acceptance checks), plus the evidence each
   `Manual:` line names. Green gates are necessary, not sufficient.
7. **Verify** (board: `Verify`). A worker report or fix-round gate log naming a test that passed only on its
   retry is yours to record on its `Flaky:` issue, and at the third occurrence to start
   the skip PR from main (SKILL.md, Flaky tests). Commit and push; under `ci: false`, then post the pass with `approvals.py local-ci <pr> --head <the pushed sha>`, since GitHub can still show the previous head for a moment after a push and a bare `local-ci <pr>` would post on it: `--head` waits about 30 s for the push, refuses naming both heads, and its one output line names the head it posted on. Before a verifier starts,
   each deviation on the worker report's `Spec deviations:` line is fixed, or taken to the
   owner as a scope change (SKILL.md, Approvals and proof: rewrite the issue, then
   `needs-owner`), since a verifier pass on a narrowed spec only finds what the report
   already said. Then write the PR body's `Spec deviations:` line: `none`, or each deviation
   with a link to the owner's decision (an issue comment URL or `#n`). Before each pass, rerun on the head every
   proof the spec's acceptance needs whose log names another commit, since the verifier
   counts it as missing and the pass is spent on it:
   `for f in <proof logs>; do head -1 "$f" | grep -qx "$(git rev-parse HEAD)" || echo "stale: $f"; done`
   prints the ones to rerun. Where the verifier runs in the worker's VM (the default, SKILL.md, Where heavy steps run), the pass runs there
   instead of in a host worktree (SKILL.md, Verifier in the worker's VM), with the proof logs named in its
   brief and the priorities file already in that checkout (copied there like the logs). Where else it runs is SKILL.md, Where heavy steps run.
   A verifier on a host starts on that pushed
   head (SKILL.md, Independent verification) in a worktree of its own at that head,
   `git worktree add --detach <path> <head>`, listed in your notes, so you keep working in
   yours while it reviews and no commit of yours moves the head under review.
   **Shared worktree.** The verifier reviews in the worker's worktree instead, saving a
   checkout, a dependency install and a fixture clone, when all hold: its HEAD is the pushed
   head under review (`git rev-parse HEAD`); `git status --porcelain` is empty; an instance,
   if the spec needs one, was built from that head with its data reset by the project's seed
   step (loop.md § Proof on a branch); and the worker's session is stopped (no turn running),
   since a turn could move the tree under review. Otherwise it gets its own detached worktree
   as above. In a shared worktree a fix round's worker runs no gate beside the pass (worker.md,
   Gates and push), since the verifier's mutation patches edit that tree; `land` and CI gate
   the head. Copy into its
   `tmp/loop/` the priorities file from step 4 (it exists only in your checkout, and `brief
   --priorities` runs there), the proof logs and, on a later pass, the previous report (as the
   `tmp/loop/pr<pr>-v<n>.md` the brief names) and its repros, since a read outside its
   workspace is prompted. Give it the path of `verifier.md`, the base, the reviewed head, the
   spec number, the priorities (that copy, extended with any a later finding adds), and a report path under `tmp/loop/` in that
   worktree, which the project gitignores. `uv run <this skill's folder>/scripts/approvals.py brief
   <pr> --priorities <file> --proof <log>…`, run from that worktree through that worktree's
   own copy of the skill, since the role path it prints follows the script's copy and only
   that one stays inside the verifier's workspace, prints that brief with every fact but the
   priorities read from the PR, the previous report and its head from pass 2,
   and loop.md's `## Verifier brief` (the project's own lines, such as host load rules)
   appended; it refuses a proof log whose first line isn't the head. It first checks that the head merges cleanly into the PR's own base (`git merge-tree --write-tree origin/<base> <head>`, after fetching both): a head that conflicts exits 1 naming the conflicted files and writes no brief, since CI doesn't run and `land` skips it, so merge the base in first, and one pass covers the fix and the merge; `--allow-conflict` writes the brief anyway, for a pass meant to review the conflicting head. The report path matters:
   outside its workspace a Codex child's sandbox refuses the write and a Claude Code child is
   prompted for a read (denied in auto mode), which nobody answers. Its model: SKILL.md, Models, in the verifier's family, and the brief names that tier so the verdict's `Verifier:` line carries it. A lower-tier
   verdict that says `Risk: high`, even a satisfied one, calls for a default-tier pass on the head before landing,
   and `check merge` refuses the change until one is posted. Name the family that wrote the diff when the backend takes it
   (Omnigent: `--author`, plus `--same-family` when the verifier shares it), and keep the
   brief silent about it (SKILL.md, Independent verification). When the change has something to see, first
   bring your instance up on that head from the verifier's worktree (loop.md § Proof on a branch),
   so the verifier finds it and its log there and can drive it. A report without a `SATISFIED:` line is
   unfinished: never triage or land on it. A verifier's `<report>.question` asking for a
   proof run (verifier.md, A run the sandbox refuses) is answered by filling `proof-run.md` from it
   and sending the logs back: a question that lists several runs gets one proof brief with
   all of them, made in one heavy-slot hold where one host can make them all, since a hold
   per run waits on the slot each time. The next pass's brief carries the answer under a
   `## Answer to your question` heading (put it in the `--priorities` file), which is how
   the verifier script knows a question was answered: a later question without a
   `New in the answer:` line is refused (exit 1), so the verifier asks once. Post each finished report with
   `uv run <this skill's folder>/scripts/approvals.py verdict <pr> <report>`: one PR review on the commit the
   report's `Head:` line names (github.md, Review trail), one inline comment per finding,
   labelled `Verifier (<family>), pass <n>`, and a summary carrying its `VERDICT:`,
   `SATISFIED:` and `Risk:` lines. That review is what the merge gate reads. A mixed PR's second
   verifier, running at the same time, gets its own detached worktree the same way. A verifier
   may instead run on another host loop.md's `Placement: hosts:` line lists (SKILL.md, Where heavy steps run), so its tests and
   mutation runs load that host: a top-level session there (orchestrating-agents' Omnigent
   backend, Verifiers on another host) whose `--workspace` holds a clone of the repo, briefed by
   `approvals.py brief <pr> --far <that clone>`, which tells it to fetch the head and make its own
   worktree; the proof logs and the previous report go there with `start --file`, you make no
   worktree for it, `wait --verdict` copies its report to your `tmp/loop/`, and a check that
   host can't run comes back as a proof-run question as above.
   **Verifier route.** Codex is the default verifier whenever it has quota. When it refuses (the quota error
   text goes to the owner at once), `--verifier-route gemini|claude` on the same verifier start, or
   `$OMNIGENT_VERIFIER_ROUTE`, picks the fallback, with the same brief, report format and `verdict` post:
   `gemini` runs agy's Gemini (experimental) on a `--host` that has agy logged in, in bypass mode, with a model
   from that host's `agy models` (`gemini-4-hydrogen-medium`; verifier.md's `Verifier:` line names it as
   `agy/<model>/<effort>`), and the PR body's review line says "verifier ran on Gemini (experimental
   fallback)"; `claude`, only when Gemini fails or can't be driven, starts a fresh Claude session with no
   author context, `--model` other than the author's (`--author-model`), the report labelled `Verifier: claude,
   same-family, pass <n> (Codex out of quota)` and the PR body's review line "same-family verifier (Codex out
   of quota)". A satisfied fallback verdict lands a change of any risk the way a Codex one does: `check merge` reads
   its family as no tier, and refuses only a `mid` or `small` Codex tier on a high-risk change. agy on another host takes the brief
   as a file there (backends/omnigent.md, Antigravity). Triage every finding (SKILL.md) and hand the fixes to a worker,
   or make them yourself (`worker.md`, Trail), naming the last green head (the newest head whose
   gate passed) for the fix round's gate (worker.md, Gates and push). A correctness finding's fix
   covers its class: each sibling the verifier lists under it (verifier.md, Siblings), triaged like
   a finding, that the same change fixes in files the PR already touches; a sibling past that cap
   is filed as its own issue (SKILL.md, Triage), since one case a pass costs a round per case and
   a fix reaching further grows the PR past its spec. The fixer replies on each fixed thread with
   the SHA and resolves it `ADDRESSED`. Resolve each deferred finding's thread yourself,
   `WONT_FIX`, replying with its triage and the issue it waits in, and each rejected one
   `INVALID`, with the one-line why; then push. Each later pass gets a fresh verifier, started the same way in a
   worktree at the new head, plus the previous report's copy and head; reviving the old one re-reads its whole earlier
   review every turn. With loop.md's `Verifier session: reuse` (SKILL.md, What the project states), keep the
   verifier's session across passes instead: `send` it the next pass's brief (`approvals.py brief`, as above)
   rather than starting one, and close it once the PR lands. Start it as soon as the fixer reports the pushed head, with the fix's gate
   still running, and wait on that gate yourself (`wait-for --log <log> --pid <pid>`): `land`
   needs a satisfied verdict and a green gate on the same head, so neither check weakens, and a
   red gate's failure joins that verdict's findings in the next fix round. A finding that doesn't make the PR wrong or unmergeable, a note on a
   satisfied verdict included, waits for the merge and starts from main (SKILL.md, One
   concern per PR). Every fix after a verdict needs a verdict on its head, because `land`
   (step 8) merges only a head the newest verifier review covers. A fix that changes nothing an
   agent or tool reads (prose for people: a README, the changelog, a code comment), a note
   fixed after a satisfied verdict among them, gets a short delta pass: the verifier reviews
   only the change since the last verdict's head. Instructions are code: a skill, a role
   file or brief, `AGENTS.md` and `CLAUDE.md`, the project's `docs/agents/` files, a prompt,
   and anything a tool parses each need the full verifier pass (gates, proof and repros),
   still reviewing only the change since the last verdict's head.
8. **Land** once the last verdict is triaged with no core finding open; the merge itself
   waits for the landing rule (SKILL.md):
   - Merge `origin/main` into the PR only when `land` comments that it conflicts with main
     (`Conflicts in the landing batch`): both merge queues test each head on top of main (the
     local one on the host, GitHub's in its `merge_group` CI), so a PR behind main lands
     without a merge. When you do merge it in, rerun the
     gates and get a verifier pass on the merge (step 7), since `land` merges only a head with
     a verdict of its own. A head with an earlier head's tree (`git rev-parse <sha>^{tree}`), as
     after a reword of commit messages only, keeps that head's verdict (unsatisfied or with
     findings open, it stays so) and go with no new pass, since no file changed: `check merge`
     and `land` print `verdict on <old> carried: same tree <tree>`. When main's changes touch no file the PR changes and no merge check
     (a `check:` task, a tool it runs, or the lint, type or test configuration), that pass is
     the short delta pass. Where loop.md still has `carry_over_main` (deprecated), no pass is
     needed when `check merge` prints that the merge carries the head's verdict. When every
     commit since the last verdict's head is a merge of main and `land` named none of those
     heads in a conflict comment, `check merge` and the verifier brief print `unforced merge
     of <base>: land merges heads itself (lead.md step 8); this pass is avoidable`: a brief
     telling you to merge main after each landing is wrong, so leave the next one unmerged.
   - A landing is told to the lead that owns the PR, by `land`'s exit and its `Landed` comment, and to nobody else: don't relay it to other leads. Each wake re-reads that lead's whole context, and a lead that needs the new base reads it when it next fetches.
   - Write the PR body with the Land skill (SKILL.md, Practice), its proof under
     `## Evidence`, keeping the `Token estimate:` line and adding below it the `Tokens spent:` line
     that `python3 <orchestrating-agents' folder>/scripts/omnigent_agent.py usage <session>...`
     prints last, naming each top-level session your notes list (a verifier on another host, a
     worker started outside your tree), since your session's record totals only its own tree,
     children included. A
     session Omnigent has no usage for is named as uncounted rather than guessed, since a guess
     would read as a measurement. Information only, like the estimate; on another backend, write
     `Tokens spent: not counted (<backend>)`. Where the change is high risk, the merge approval is also the owner's
     go on the head that lands (SKILL.md, Approvals and proof): `approvals.py approve merge
     <pr> --head <sha> --by owner` naming the head you showed them, when they say it in your
     session; you never give it, and `approved:merge` into the default branch is none. Into a
     feature branch the label is a go too, and the delegated approver loop.md names may add it
     with `approvals.py delegate <pr>`. `land` adds `risk:high` to the PR when it infers the risk, and a failure
     to add it is reported, not fatal.
   - End the PR body with `Impl: <signature>` of the agent that did most of the work, instead of the harness's
     "Generated with" footer: the worker's from its report, or yours, what orchestrating-agents'
     `scripts/omnigent_agent.py signature` prints in your session, else the `AGENT_SIGNATURE=` line atop your brief
     (`?` for any part you can't know).
   - A project's own batching merge queue (`check queue`, `batch`) is deprecated: where the
     project's instructions still name one, enqueue there as they say until it adopts `land`.
   - Run `uv run <this skill's folder>/scripts/approvals.py land <pr> --wait` (the project's `mise run loop:land <pr>`
     with `--wait`) once no local objection is left: the gate of record passed on the head (the worker's `affected-tests`, or `mise run check` where loop.md has no `Affected tests:` line or has `Gate: full`; with `ci: false`, the worker's `local-ci --record`, a narrowed pass where loop.md has the line; `land`'s batch gate runs the `Affected tests:` command against the base tip it merges onto where loop.md has the line, else the project's `loop.gate`: SKILL.md, Adopting the loop), the PR's required check is green (it runs CI's selection of the affected tests, so where `ci` is not `false` and no `gate_steps` step runs on the host, the host runs no gate of its own before the go: no `check-fast`, no full suite), the
     newest verifier review, satisfied with no core finding open, covers it, and every review
     thread is resolved (SKILL.md, Review trail on the PR). Start it as a background
     command whose exit wakes you, one per PR, the way the backend runs one (Waiting), and work
     on other items meanwhile. It lands every landable PR into main through main's merge
     queue, the local one or GitHub's, not only yours (SKILL.md, Approvals and proof;
     `approvals.py`'s docstring has each step), and
     exit 0 means your PR merged in the local queue, with a `Landed` comment naming the base commit, the tree and
     the gate, and its kept `--pr` worker sessions finishing in the background (its log is named; `reap --merged
     --pr <n>` finishes them again). On a base with GitHub's merge queue exit 0 means the PR is enqueued
     (or already queued) and `land` has ended: it never polls the queue. The merge, or a removal for a red
     check, reaches you as an event from the project's watcher; the PR is not landed until then. A removal's next
     step is `land <pr>` again, which reads the PR once. Exit 1 names what stopped your PR, and the fix is yours:
     - a missing proof, with nothing on the PR changed: add the proof;
     - a conflict with main or the PRs merged before it: merge `origin/main` in, as the first
       bullet says;
     - an eviction, red alone twice in the local queue or red twice on one head in GitHub's:
       the PR is a draft again with the failing log's tail in a comment; fix it like a check
       red after ready, and `land <pr>` marks it ready again;
     - `main itself is red`: nobody is evicted, since the fault is on main; fix main first
       (Rules for every role, Revert first);
     - a merge GitHub refused: as the bullet below says.
     Exit 3 is what `--wait` doesn't clear: the owner's go, or 2 hours of another land's lock
     (one whose PR already merged is broken at once) or of pending required checks. On a GitHub-queue
     base `--wait` never waits on the queue, and exit 3 for a conflict GitHub is still working out, or for main's
     checks on the commit a red group was built on, ends the run: run `land` again later. With gatekeeper.md's `land` section it squashes, signs and pushes
     each PR from your checkout instead, so run it where the signing key is. GitHub deletes the
     head branch (the repository's `delete_branch_on_merge`, which `setup:github` sets). Never
     mark a PR ready or merge it by hand (`gh pr ready`, `gh pr merge`), because `land` is what
     refuses a PR whose proof is missing: `land` itself marks each draft it names ready, before it
     waits for the lock, so the batch ahead of you takes it, and several PRs named in one `land`
     land in one batch. A push after it needs `gh pr ready --undo` first; the
     owner's go carries over only merges of the base whose verdict says `Logic change: none`
     (SKILL.md, Approvals and proof), and after the verdict on the new head `land` runs again.
   - Land every approved PR at once: start `land --wait` on each as soon as its proofs hold,
     never after another PR's merge. In the local queue whichever runs first takes the lock and
     lands every landable PR in one batch; the others wait for the lock and find their PR merged
     (exit 0) or land what is left. In GitHub's each enqueues what is landable, and the queue
     groups the entries. Host load is no reason to serialize: one gate covers the batch.
   - A PR held for the owner carries `needs-owner` (or `risk:high` when it waits for a merge
     go on a head), which the owner's `approve merge --by owner` removes: a question card
     alone holds nothing, since `land` batches every PR that is ready.
   - A check red after ready: `gh pr ready --undo`, then start a worker in the same worktree
     with the failing log as its brief, rather than fixing it yourself. It fixes the check,
     runs the gate of worker.md step 2 and pushes; a fresh verifier (step 7) reviews only the change
     since its last verdict's head; then `land` runs again on the new head.
   - Where a high-risk change waits for the owner's go, `land` exits 3 with only that left
     once the base's required checks have passed the head, so the owner never approves a head
     CI could still reject: give them the PR link and the head, ask for their go, and run `land` again once it is on.
     The PR has landed only once `land` exits 0, or `gh pr view <pr> --json state,mergeCommit`
     shows `MERGED`. Then use the merge commit in the steps below.
   - When GitHub refuses `land`'s merge for a missing review or check (`land` prints why), request the reviewers
     (`gh pr edit <pr> --add-reviewer <login>`), add `needs-owner` to the issue, and
     stop. Never use `--admin`, which overrides the project's protection, and never push
     to main.
   - Human review findings: triage each review comment with One concern per PR (SKILL.md).
     A blocker, a major or a bug the PR introduced is fixed on the PR's own branch; anything
     else gets a reply on its thread linking the issue it waits in, and starts from main once
     the PR lands. The fixes follow the review trail (SKILL.md): `gh pr ready --undo` first,
     so CI skips the half-done fix, then each fix its own pushed commit, replied on its
     thread with the SHA and resolved (`worker.md`, Trail), and a verifier pass (step 7)
     before `land` runs again. Never cascade a fix down a stack or re-prove a merge
     order: `land` gates each batch on top of main, main's push run catches the rest (step 9), and a PR stacked on this one moves
     onto main when it lands (SKILL.md, Stacks are one deep). Dismiss a teammate's review
     requesting changes only as SKILL.md, Review trail on the PR allows (github.md, Review trail).
   - Closing keywords fire only on a PR merged into the default branch, and GitHub misses
     some even there. They stay on the PR that carries the work: a stacked PR keeps its own
     `Closes` and lands itself once retargeted onto main. Copy them to its base only when
     the base actually contains the stacked work (the stack was merged into it), since
     otherwise the base's merge closes issues whose work isn't on main. Once the work is on the default branch, close each issue a PR on the
     way names with `Closes` (never `Part of` or `Implements`) that is still open
     (`gh issue close <n> --comment "Landed in #<pr> (<merge sha>)."`) and move it to `Done`.
   Every status comment you post follows github.md, Comment shape: a short result in view, the rest under `<details>`.
     When that was an epic's last open sub-issue, close and move the epic the same way. Where
     gatekeeper.md has a `signoff` section, each issue it names with `Implements` stays open for the
     owner's sign-off: move it to
     `Sign-off` and comment `Landed in #<pr> (<merge sha>); waits for your sign-off in use:`
     followed by the spec's acceptance examples to try ([issues.md](issues.md), Sign-off).
   - A PR replaced by another: the replacement carries `Closes` for every issue the old
     one closed, so none is left pointing only at a closed PR; close the old one with
     `Replaced by #<n>`.
   - Fast-forward the main checkout (`git -C <main checkout> pull --ff-only`), and tell
     the live peers that main moved: the merge SHA, plus any setup step they must run.
   - A PR stacked on this one moves onto main now. When you own it,
     `gh pr edit <stacked> --base main`, then merge `origin/main` into its branch and push.
     Otherwise comment on it, naming the merge SHA, so its owner moves it
     (`gh pr comment <stacked> --body "Base #<pr> landed in <merge sha>: retarget onto main and merge it in."`):
     never push to another owner's PR (SKILL.md, One concern per PR).
9. **Accept.** First read main's push run on the merge SHA
   (`gh run list --branch main --event push --commit <merge sha> --json conclusion,status`;
   with `ci: false` there is none). When it ends red, revert before anything else
   (SKILL.md, Revert first): `git revert --no-edit <merge sha>` on a new branch off a
   freshly fetched `origin/main`, then a PR whose body says `Reverts #<pr>` and
   `Part of #<spec>`, so `approvals.py` finds the spec, through this loop; reopen every issue
   the PR closed with `gh issue reopen <n> --comment "Reverted in #<revert pr>: <why>."`. Then run only
   the spec's After merge list, since the proof and the verifier already ran the Before merge
   list on the head the merge carries: each line against the reference it names, in the order of loop.md §
   Acceptance references, through a worker whose report you read when a line needs an
   environment brought up (loop.md § Proof on a branch) or a long run, else yourself. An After
   merge list of `none`, or none at all, means no acceptance runs here, and your report says
   `After merge: none`. A failure is reverted the same way, and the fix
   forward is a new change through this loop, never a patch on main.
   With loop.md's `Verifier session: reuse`, send the spec's After merge list to the kept
   verifier right after the merge, before you finish its session, since that session already
   knows the change and a new agent would learn it again: it runs each line on the merged
   default branch and reports each result, and you read that report as a worker's.
   Otherwise, or once that verifier's session has ended, run the list as above.
   **Epic handoff note.** When the merge closed an epic's last open sub-issue (step 8), once the
   After merge list has run, comment on the epic: each story's PR and merge commit, each spec's
   acceptance checks (the acceptance command with its issue, SKILL.md, Acceptance checks), the
   After merge results, and what the next nightly must confirm (SKILL.md, Nightly), so the owner
   reads one note on what landed and what is still to be confirmed. The epic closes as step 8 says.
10. **Clean up** once acceptance has run, pass or fail. Close the agents, and stop only the
   processes you started, as worker.md, Report says, since a shared pattern kills other
   agents' runs too. For every
   worktree your notes list, children's before yours (each verifier's detached one
   included), since removing yours first leaves
   theirs as stale entries, run its teardown (loop.md § Worktree), then, from the main checkout,
   `git worktree remove --force <path>` and `git branch -D <branch>`, the local branch only
   (a detached verifier's worktree has none): GitHub deleted the merged head branch, and you
   delete no remote branch. Remove only what your notes list: the project's `.worktrees/`
   also holds other sessions' worktrees.
11. **Report** to the owner: the PR and merge SHA, gate exit codes, the acceptance
   examples as checked (with a screenshot when there is something to see), ledger lines
   added, findings rejected, issues filed, each issue waiting for their sign-off, each
   agent's model, `verifier: same family`
   when it was, each heavy run that did not go to the cloud with where it went and why
   (SKILL.md, Where heavy steps run), and the main instance's link. When your brief names a report path, write
   this report there once, at the end: whoever started you takes that file as your final
   report, so keep progress notes in another file.

**Waiting.** Results come to you: a subagent's result or a backend's reply arrives as a
new prompt. While a PR waits for CI, move other ready items forward (another PR's step, a
spec, triage) and come back to the PR when CI reports, because CI takes tens of minutes
and a lead that waits through it makes CI the loop's speed. With nothing else to
do, end your turn. Don't poll agent lists, logs or panes,
or sleep: every check re-reads your whole context. Read the report file a reply names,
not logs or scrollback. A child nothing waits on reaches you only through the untitled
inbox notice, so watch your children as your backend's file in orchestrating-agents says (Omnigent: `watch`,
and for a child that still owes its report a detached `supervise --registry` that `run` and
`send` arm). Supervise with a process the host runs, not an in-session background command or
session cron, which die with your session and lose every wake they owed.
A child under a background `run --notify`, `send --notify` or `wait --notify` wakes you once when
it ends its turn with its report in: by Omnigent's notice when the child is your own sub-agent or you
subscribe to it, else by the command's `--notify` line, which also reports every other ending (a
timeout, a failure) (orchestrating-agents' backends/omnigent.md, One wake per child). Don't poll or
`watch` it for the other. Without `--notify`, expect Omnigent's notice and the command's exit both.
Your own long runs (a gate, a land, a live check) start detached the same way (verifier.md, A long or locked run is detached)
with the log, pid and exit code in files, since Claude Code's low-memory reaper stops
in-session background shells. Start each with `LOOP_NOTIFY` naming your session (orchestrating-agents'
backends/omnigent.md, Waiting on a run or a PR), so its wrapper's `wait-for --notify` step tells you
how it ended and you end your turn meanwhile; to block on one instead, the only way is
`omnigent_agent.py wait-for --log <log> --pid <pid>`, or `wait-for --pr <n>` for a PR's checks,
which blocks close to the tool limit and prints only the outcome. Start each with `exec`, or in its own process group under
`trap 'kill 0' EXIT`, since stopping a wrapper shell leaves its command running, gating a target
you have moved past; count runs with a pattern anchored at the interpreter
(`pgrep -f '^python3 <script> run'`), since one the wrapper's own command line holds never drops.
A run started with `exec` leaves no exit file, since nothing runs after it: judge its end by its
log or report, or use the trap form where its exit code matters.
Wait on a child or a run by whether it is alive, never on its report file alone: your backend's
status (Omnigent: `omnigent_agent.py status <session>`) or the run's pid and exit code, since a
child that died, or a `run` killed mid-retry, writes nothing and a file wait polls on for good.
So one wait ends on every terminal state (success, failure, the process gone), which `wait-for
--log <log> --pid <pid>` does, keeping each run's pid (or its lock or heartbeat file), since a
watcher that fires only on an outcome reads a dead run as still working. Wait on the pid file, not the bare pid: a pid the
system reused for another process still passes `kill -0`, so `wait-for` reads a process younger
than its pid file as the run gone, as it does a pid file that is missing or empty, and exits 1
naming `ps` when it cannot read a live process's age, since an unchecked pid may be another's. On every wake, a session restart included, check that each run you say you wait on is
alive before saying so, since a restart kills your background runs. A child still `running` with
no turn item a few minutes after its start never got its brief: treat it as dead.
A child that ends its turn saying it waits (for a build, a gate, CI) rather than reporting
has left no report and will not wake itself: arm such a wait on its process or log, and when it
fires, ask the child for its report. A worker's gate or verifier run is waited on by what
it posts on the PR, `wait-for --pr <n> --until gate` or `--until verdict` (orchestrating-agents'
backends/omnigent.md, Waiting on a run or a PR), never by the worker's turn ending, since the run
can outlast the turn or die with its machine; one that settles on nothing by the run's usual
length is restarted, and the wait on the restart passes `--since <its start time>`, so the old
run's failure or question does not answer it. Where the failure status cannot be written (a proxy
that refuses status writes), a failed run reads as exit 6 until the budget; with
`gate_steps`, exit 0 is one step's pass, and `local-ci <pr>` says whether the whole gate has one.
Finish a worker or verifier as soon as its report is read or its verdict posted, since an
idle child keeps its agent process, MCP servers and runner alive. With Omnigent, `run` and
`wait` already finish the child whose report they return, except a `--pr` worker, which they keep
for its fix rounds and which `reap` finishes once its PR is merged or closed (a verdict does not release it), and `land` once it
merges the PR; a report you heard any other way
(`send`, `watch`, a `run` that died, a file you read) leaves the child idle, so `reap <id>` it. At each
wake and before each new start, finish any child whose report you have read and whose turn
ended over 15 min ago. Only you know a report is in: an idle child still owing one looks
finished to the backend.
A step only the owner can unblock is parked (SKILL.md, Owner steps park): a reported child's
process still hung on one is yours to stop and release, since its owner has ended its turn.
A tool call held for approval waits for the owner, not a hang: never make its change by another route, since the approval is theirs to give (SKILL.md, Owner steps park).
End every `STILL WORKING` with one last line from `python3 <orchestrating-agents' folder>/scripts/omnigent_agent.py wait-on
supervisor|session <id>|pr <n>|ci|run <Actions run URL>|until <UTC time>`, pasted as printed (`Waits: supervisor`, `Waits: session <id>`,
`Waits: #<pr>`, `Waits: CI`, `Waits: https://github.com/<owner>/<repo>/actions/runs/<n>`, `Waits: until 2026-10-21T23:17Z`): it refuses a malformed wait, and the supervisor reads
that line exactly, where prose such as "waiting on the CoS spec approval" or "cloud session <id>" is only a fallback it
can misread. `supervisor` is any wait on the chief of staff or project manager (a spec to approve, a decision), which
they act on at once; for a wait on a session, name its full id. The line may name a set (`Waits: #12, #13 and session <id>`): the supervisor wakes you on the first failure, or when
every member has ended, and records the successes between. A child you started that reaches a final state (`DONE`,
`USER NEEDED`, `PARKED`, failed, archived; or idle with a last message that is no `STILL WORKING`, as a verifier
of another harness or a cloud run that answers in its report does, which counts for a session your wait names, and for
any other only when it came after your own turn) reaches you as news within a minute of its end, named or not, and a PR your
wait names that merged, closed or finished its checks the same, read from GitHub; an intermediate `STILL WORKING` turn of a
child is no end, so the line only has to name what you wait on.
`wait-on` also writes your state as the `lead` event on your branch (events.md): `waiting`. End `DONE` and `USER NEEDED` the
same way, pasting the line printed: `omnigent_agent.py end-on done <result> --report <path>` (event `ok`) and
`end-on needs-owner --question <file> --report <path>` (event `needs-owner`, with the whole question in `question.md`
and its first line in the printed line). Write the question to a file, never into the line: the supervisor sends the owner
the file's whole text, where a summary cuts a long one short. Once your branch has an event, the supervisor reads
that and your parsed `Waits:` line and ignores a `CoS:` footer and prose waits; a `Waits:` line that does not parse
gets one notice naming the accepted forms. A lead with no branch yet writes no event (its `needs-owner` is the issue's
label), and a host whose push fails still prints the line: the event only reports the step.
A wait on a background task of your own may name its id, `STILL WORKING bz3jp5aod`, which a
supervisor reads as a named wait. A wait of your own that ends at a known time (a timer, a scheduled job) names it in UTC in your
`STILL WORKING` line, `until 2026-10-21T23:17Z`, so a supervisor raises no progress deadline
before then, and arms what wakes you then (a detached `sleep` to that time, or a scheduled
message), since a time named only in text wakes nobody.

A core finding still open at the cap goes to the owner and stops the landing: offer a fix
with one pass past the cap, scoped to the open items, or leaving the code untouched
(SKILL.md, The cap). Make no fix until they choose.
