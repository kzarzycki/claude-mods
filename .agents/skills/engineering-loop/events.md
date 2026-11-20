# Loop events: the contract

A step's state, written as a small git ref on `origin` where a reader finds it in a typed field instead of reading
prose. Every producer and the supervisor read this file; `scripts/events.py` is its writer and reader (`emit`,
`read`, `wait`, `clear`; its docstring has the flags). Read this when you write a producer, read an event, or add a kind.

## The ref

`refs/loop/<kind>/<branch>` points to a **parentless** commit whose tree holds `event.json` and, for a request to the
owner, `question.md` (the whole text, never cut). A beat is the same ref rewritten with a new parentless commit, so one
commit is reachable from it and history never grows. The branch is the one the work is on, so the ref exists before
a PR does and survives a push. The landing lock and waiter refs (`refs/heads/loop-landing/*`, `refs/heads/loop-waiting/*`)
are not events and stay as `land` writes them, and so are the gatekeeper's `refs/loop/records/*` (gate records) and
`refs/loop/landing`: `read` lists only the kinds below.

`event.json` fields (all present on every event):

| Field | Type | Meaning |
|---|---|---|
| `state` | string | `waiting`, `ok`, `failed` or `needs-owner` |
| `seq` | integer | 1 for a ref's first event in this clone, plus one on each rewrite |
| `at` | string | UTC time of the write, `YYYY-MM-DDTHH:MM:SSZ` |
| `beat_s` | number | seconds between this producer's beats: the kind's interval below unless the producer says otherwise |
| `url` | string | what the kind's row below says, or `""` |

States: `waiting` (the step runs and will beat again), `ok` (ended well), `failed` (ended badly: `url` says why),
`needs-owner` (the step needs the owner's answer: `question.md` holds it). A reader treats `ok`, `failed` and `needs-owner`
as ends and leaves a ref it cannot read or parse as `unknown`, never as ended; the deadline then applies.

## Kinds

| Kind | Writer | Beat interval | `url` points to |
|---|---|---|---|
| `lead` | the lead's own script, when it waits or needs the owner | 300 s | the PR or issue the lead's item is |
| `land` | `approvals.py land` | 300 s | the PR, and on `failed` the eviction comment, which holds the log's last lines |
| `gate` | the gate run, `local-ci` (slice #1379); the main-commit `gate` status that `land` writes (`publish(tip, landed_pass(...))`) stays | 120 s | the `local-ci` record; on `failed`, the detached run's log when there is one, else empty |
| `verifier` | the verifier run: `cloud_verifier.py`, or `events.py emit verifier <branch> <state>` by hand (verifier.md) | 300 s; a native pass sets `--beat` to its longest blocking call | the verifier's report or PR comment |
| `probe` | `events.py` tests and the one-off check below only | 60 s | nothing |

`land` writes its event for each PR it names: `waiting` only under `--wait`, once per round (about every 2 to 6 minutes)
and from the lock's heartbeat while a round gates, never over an end of the same round; `ok` once a PR merges (by `land`,
the merge queue or by hand); `failed` when it is evicted, or when `--wait` exits non-zero with the PR neither merged nor ended (main is red, say); `needs-owner` when the PR waits for the owner's go (a draft
too) and when `--wait` reaches its 2-hour ceiling.

`verifier` is on the branch the PR is from (`cloud_verifier.py`'s `verify` and `thread` routes both write it): `waiting` from the pass's start, beating while it reviews, then `ok` when
the report's `SATISFIED:` line is `yes`, `failed` when it is `no` or the pass wrote no verdict, `needs-owner` when it
writes a question (`question.md` holds it). `url` is the posted review, or the report's path where the pass posts none (the `thread` route, a native pass).

A wait is **live** while its ref changed within twice its `beat_s`. `wait` ends with exit 4 on a `waiting` event that
did not change for longer, counted from its `at` on the first sight and from the moment its sha moved after that.
The intervals are the kinds' starting values: the code that writes a kind may set `beat_s` per emit and fix its row here.

## Reading and waiting

- `read [<kind>]`: one `git ls-remote origin 'refs/loop/*'` (no API quota; a changed sha is a change), then a fetch of
  only the refs whose sha moved since the last read, into `refs/loop-remote/`, and the parsed events with `changed`,
  when this clone first saw the sha. The cache is `loop-events-seen.json` in the git dir.
- `wait <kind> <branch>`: exit 0 `ok`, 1 `failed`, 2 `needs-owner` (the question is printed), 3 timeout, 4 silent.
  Each poll reads the local ref, then origin's, and takes the later `at`.
- `clear <branch>`: removes the branch's refs of every kind here and on origin. `land` runs it in a detached process
  120 s after a PR merges, so a `wait` polling slower than that, or started later, finds no ref and runs to its timeout
  (exit 3). `omnigent_agent.py reap` runs it too for the head branch of each merged or closed PR whose worker it
  finishes, from that worker's checkout, so a PR closed unmerged leaves no ref behind.

## Degraded

Only `git` and an `origin` are needed. `emit` writes the local ref first; a push that fails prints one warning and
exits 0, so an event reports a step and is never part of it. A native lead in the same clone still sees the event with
`wait`; another host sees it when a later push goes through. `read` with origin down shows the local events (kinds below, nested branches included) and warns.

## Measured on GitHub

- **Rulesets:** `gh api repos/{owner}/{repo}/rulesets/<id>` lists two: `main` (target branch, includes only
  `refs/heads/main`: deletion, non_fast_forward, required_status_checks, pull_request) and `tags immutable` (target
  tag: deletion, update, non_fast_forward). Neither matches `refs/loop/*`, so no ruleset blocks it.
- **`git ls-remote origin 'refs/loop/*'`:** 0.51 s with no such ref (one call). The same call over `refs/heads/*`
  (325 refs) took 0.44 s and over every ref (1107) 0.37 s, so a listing of 20 refs costs well under a second; the call
  is bound by the round trip, not the count.
- **A push of `refs/loop/probe/<branch>`:** accepted by GitHub with a plain token from a host. One `events.py emit` took
  2.3 s end to end (process start, commit, push); `git ls-remote origin 'refs/loop/*'` with one such ref took 0.46 s;
  `events.py clear` removed it from `origin`. A cloud session's proxy refuses refs outside `refs/heads/` (`RPC failed;
  HTTP 403`), so **a cloud session's events stay local and warn once** (Degraded); only a host with push access
  writes events another host reads.
