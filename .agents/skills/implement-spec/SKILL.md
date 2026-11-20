---
name: implement-spec
description: "Implement a spec and its tickets on one integration branch, working the ticket graph's frontier concurrently."
disable-model-invocation: true
---

# Implement Spec

Deliver the whole spec on one **integration branch**, with every ticket resolved the way the issue tracker closes work. `docs/agents/issue-tracker.md` names the tracker's realization file (for GitHub, the `engineering-loop` skill's `github.md`). If that file is missing, tell the user to create it: the project template writes one. The spec's tickets are a **task graph** of blocking edges, not a list of steps: every ticket whose blockers are done is on the **frontier** and can start.

1. Read the spec and enough of the tickets to see the graph.
2. Create the integration branch. If the tracker closes work through PRs, or the user asks for one, open a draft PR that closes the spec issue and every ticket after the first merge in step 4, because a branch with no commits ahead of its base cannot open one.
3. Work the frontier. Hand tickets that can run in parallel, or would flood your context, to background implementers, a fresh one per ticket started with a fresh context window rather than a fork of yours, each in its own worktree on its own branch; do a small ticket yourself when that is quicker. An implementer confirms its worktree is based on the integration branch and resets onto it if not, builds the ticket with the `tdd` skill, and merges the integration branch tip into its own branch before reporting done, so the merge back is a fast-forward. Exploration the tickets need (code or external docs) can go to a helper that writes markdown notes to a directory outside the repo, where every later implementer can read them.
4. Merge each finished branch into the integration branch, then start whatever the merge put on the frontier.
5. When every ticket is merged, run the `code-review` skill on the integration branch against its base and fix every finding, in one fresh implementer pass or yourself.
6. If a draft PR exists, mark it ready for review, with its body per the `pr` skill. Otherwise resolve each ticket the way the tracker closes work and report the integration branch. Remove the implementer worktrees.

Brief helpers with **context pointers** (the spec, the ticket, research notes, earlier commits) rather than copies of what those already say, and keep messages to and from them short.
