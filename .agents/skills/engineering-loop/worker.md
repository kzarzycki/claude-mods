# Worker

You implement one item of a spec, or a list of findings, on your own branch. The
lead's message gives the spec, the item, the PR, worktree, branch, notes path and gates.
Read the notes, the spec, [coding-standards.md](coding-standards.md) and the project's
`docs/agents/coding-standards.md` first. Run every command in your worktree, never in the
main checkout. A lead that builds an item itself follows this file on its own PR
branch: it pushes that branch, merges nothing, and writes the report into its notes.
A worker in a cloud session (loop.md's `Cloud worker:` line) follows SKILL.md, Cloud worker.

1. **Build**, with the Build skill when gatekeeper.md's `practice` names one, under these rules.
   On a branch with no PR yet, run `approvals.py check build --issue <n>` first (the
   project's `loop:approvals build` reads the issue from a branch named `<prefix>/<n>-…`)
   and build only once it exits 0, since without a PR nothing else checks that the spec
   was approved.
   A project's or owner's simplification rule (YAGNI, `ponytail:`) applies to how a spec
   item is built, never to whether: narrowing or dropping an acceptance item or an
   Implementation Decision is a question to the lead in `<report>.question`, and that item
   stops until it is answered, since only the owner changes an approved spec's scope.
   Read the spec's comments as well as its body, since a later comment can narrow
   the spec. A brief with "the verifier will check" lists the checks the verifier will run on
   your head: run each on your own head before you report, and list each one's result in the
   report, since a check left to the verifier costs a fix round, a full gate and another pass.
   Fixtures are synthetic: nothing in `docs/agents/issue-tracker.md` § Never on GitHub
   goes into code, tests or commits. A changed rule gets its line
   where the project records rules. Review angles you want run as native subagents.
2. **Gates and push.** Run `mise run test:changed` while iterating and `mise run check`
   before each push, or after it on a fix round (below) (with `ci: false`, `approvals.py local-ci --record` on the committed
   head, SKILL.md, Adopting the loop). A test that passed only on its retry, or failed in a
   file the change doesn't touch, follows SKILL.md, Flaky tests, and goes in the report with
   the run it came from (a CI run's id, else the time the gate started), since that run and
   the head are what make it one occurrence.
   When your brief opens with a `LOOP_HEAVY_LOCK=<path>` line, run each gate or full test run
   under that lock, around the host's heavy wrapper (SKILL.md, One heavy gate per host slot), since your lead may run another
   worker beside you and the host's slot counts every caller: `perl -MFcntl=:flock -e '$^F =
   1023; open(F, ">>", shift) or die "$!\n"; flock(F, LOCK_EX) or die "$!\n"; exec @ARGV'
   <path> uv run <this skill's folder>/scripts/approvals.py heavy mise run check` (perl, since macOS has no `flock`).
   Once it exits 0, commit and push with `git push -u origin <branch>` as
   its own command, since a pre-tool hook may scan the whole command text. Commit and push
   after each step whose gates are green, not only at the end, so a worker killed mid-task
   leaves its work on the branch. A fix round (a brief of a verdict's findings) pushes before
   its gate, since the lead starts the next verifier on that head while the gate runs: once
   `test:changed` and the mutation check (Report) pass, commit and push, start the gate
   detached on the pushed head (below), and report its log and pid in place of its exit code,
   never waiting on it. When the brief names the last green head (the newest head whose gate
   passed) and `git merge-base --is-ancestor <it> HEAD` exits 0, put `GATE_BASE=<it>` (or the
   variable loop.md's `Gate base:` line names) in front of `mise run check`, so a check that
   reads it selects only what changed since that head; with `ci: false` run the check that way,
   never `local-ci --record`, which clears the variable. The head that lands keeps the full selection, since `land`, CI
   and `local-ci` never set it. The lead merges your branch and opens the PR: a
   brief that asks for a PR means push the branch and report it. A spec or plan the brief
   asks for goes in a file under `tmp/loop/`, and you report its path: the lead
   posts it, since the spec lives on the issue. Your job ends at the push, and once the head is handed to the queue or for approval the branch is frozen: PR events (review comments, checks) are read-only to you, and a follow-up goes in a new PR. Don't wait for
   CI. A brief that is a failing CI log is a check red after the PR went ready: fix it in
   the worktree you are given, then `mise run check` and push the same way. A command that
   may outlast one tool call (a gate, a held lock, a queue) starts detached (verifier.md, A long or locked run is detached),
   with its log, pid and exit code in files, and is waited on with orchestrating-agents'
   `scripts/omnigent_agent.py wait-for --log <log> --pid <pid>` (a PR's checks: `wait-for --pr
   <n>`), which blocks close to the tool limit and prints only the outcome, since a foreground
   call times out and Claude Code's low-memory reaper stops in-session background shells; never
   end a turn saying you are waiting, since nothing wakes you and the lead reads silence as work.
   Any other pending condition (a queued run, a free device, an unlocked screen) is waited on the
   same way, in the foreground, with `scripts/omnigent_agent.py wait-until
   --every <s> --limit <s> -- <check>`, each call under the tool timeout: the
   turn goes on once it holds, and past the limit you state it ends with a report naming the
   condition, since a background command's exit does not wake an idle session.
3. **Trail.** Fixing findings from a PR review, make each fix its own commit. After the
   push, reply on each finding's thread with its commit SHA and resolve it, reason
   `ADDRESSED` (github.md, Review trail). Resolve only a thread you fixed: deferring or
   rejecting a finding is triage, the lead's.
4. **Report.** Every log or capture you hand over as proof (a gate run, a repro, a drive
   of the instance) starts with the output of `git rev-parse HEAD` and the command that
   produced it, since a proof of another commit says nothing about the one under review.
   That SHA is the whole provenance: a checksum manifest or digest exchange adds nothing a
   commit does not already pin. A fix that changes code a proof exercises reruns that proof
   before the report, which lists each proof log with the SHA it names.
   A change to a web UI gets a rendered check, since passing tests say nothing about what
   the page shows: the project's own browser e2e when it has one, else `uv run
   <this skill's folder>/scripts/browse.py <url> --out <png>` (`--do <file.py>` to click, hover or assert first,
   `--omnigent` to sign in to an Omnigent server; its docstring says what a sandbox needs).
   Every host with Playwright's Chromium in `~/.cache/ms-playwright` can render headless;
   hand over the PNG paths.
   Run browser tests and drives headless: a window that opens on the owner's machine takes
   focus from what they are doing. Start a headless browser of your own rather than attaching to one already open there
   (over CDP or a remote-debugging port), since that one is headed; attach only when the
   check needs that browser's logins, and say so in the report. Where a test can't run headless,
   open the browser in the background without taking focus and say in the report which
   test needed it and why. A project whose e2e opens a headed browser by default names the
   headless switch in its `docs/agents/` files.
   Before the report, mutation-check each production change you add: one patch per
   condition, branch or value, written as verifier.md, Mutation-check the new tests, says,
   committed with its tests first, since mutate.py refuses a tree with uncommitted changes, and
   run with `uv run <this skill's folder>/scripts/mutate.py --test '<tests>' --log <log>
   <patch>…`, which queues on the host gate slot itself (the short lane when the tests pass on the head within
   `short_seconds`: SKILL.md, One heavy gate per host slot), so the test command takes no lock of its own. A survivor
   gets a test before the report, which lists the log of the run with none left, since the
   verifier runs the same tool and a survivor there costs a pass.
   Clean up what you started (servers, temporary files), and only that: stop a process by
   the pid or process group you saved at its launch, or by a pattern holding your own
   worktree path once `lsof -a -p <pid> -d cwd` shows each match runs there, never with
   `pkill -f` or `killall` on a pattern other agents share, since on a shared host it kills
   their runs too. Then write your
   report to a file and send the lead its path: the branch and head SHA, the PR, the gate
   exit codes, your signature (what orchestrating-agents' `scripts/omnigent_agent.py signature` prints, else
   the `AGENT_SIGNATURE=` line atop your brief), the line `Spec deviations: none` or that line
   with one bullet per deviation quoting the spec line it narrows (each one already asked,
   above), anything else left out and why, and what you tried and dropped. The deviations
   line is fixed, so a narrowed item never sits among harmless choices where the lead skims
   past it. A follow-up starts fresh from this report, not your transcript. If you're
   blocked, report that and stop. Blocked on a step only the owner can unblock (SKILL.md, Owner
   steps park), first stop that step and release what it holds, then report the exact owner
   action, since the lead parks it and nothing else frees the slot. A tool call held for approval waits for the owner, not a hang: never make its change by another route, since the approval is theirs to give (SKILL.md, Owner steps park).
