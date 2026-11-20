---
name: omnigent-telemetry
description: Report Omnigent spend, tokens by model, session trees, scheduled-task health and Codex rate limits over the last N days, with one-line anomaly flags and an optional self-contained HTML page. Use for a retro across Omnigent sessions, or when asked where spend or a quota went.
---

# Omnigent telemetry

```sh
python3 scripts/omnigent_telemetry.py [--days N] [--server URL] [--json] [--html PATH] [--db-container NAME]
```

`scripts/omnigent_telemetry.py` is relative to this skill's folder. `scripts/__pycache__` is a file, not a folder, so running it leaves no bytecode in an installed copy. The window is the last
`N` UTC days, today included (default 7), counted as `GET /v1/usage` counts its 7 and 30; the request carries `?days=N`, so the server builds only that window, and waits up to 180 s for it.
Outside an Omnigent session on a machine with several logins,
`--server URL` names the server the API sections are read from; without it they are left out
with the reason. It exits 0 whenever it prints a report. `--json` prints the report as data; `--html PATH`
also writes one page from the same data, with no script and nothing fetched, so it opens
offline. The page holds the numbers; a retro's narrative stays the `retro` skill's.

## Sources

| Source | Where it answers | Gives |
|---|---|---|
| Omnigent API, `GET /v1/usage` | any host logged in to the server (`orchestrating-agents`' `scripts/omnigent_agent.py` does the login and token refresh) | spend today, over 7 and 30 days; each top-level session tree's cost by model |
| Server Postgres, `docker exec <container> psql` (default `omnigent-postgres-1`) | the server host only | daily cost, tokens by model, each tree's sub-agents, nested Codex sub-agents, compactions and forked items, live subscriptions, scheduled-task runs, all flags |
| Codex rollouts, `~/.omnigent/codex-native/*/codex-home/sessions/` | each host that ran Codex | the newest rate-limit snapshot, per window (5h, weekly) |

A source that does not answer leaves its sections out, and the report's `Left out` lists
each one with why. Run it on the server host for the full report, and on another host for
its own Codex limits. Tokens and per-model numbers are each session's lifetime totals for
the trees active in the window; Claude harnesses record cost but no tokens. A tree's cost
is the API's subtree sum, and its root cost the root session alone. The API lists only
unarchived top-level sessions, so an archived tree's cost is its sessions' sum from the
database, and without the database an archived tree is missing.

## Flags

Thresholds are constants at the top of the script; a flag fires at its threshold.

- `SUBAGENT_EXPLOSION`: a tree with 25 sub-agents, or 6 nested Codex ones (sessions
  Codex spawned itself, `sub_agent_name` `Codex`). Usually a reviewer that fans out per
  axis on every pass, or a lead that starts a session per small step.
- `VERIFIER_CHURN`: a verifier session titled pass 4 or later (`-p4`, `pass 4`), more
  passes than one change usually needs. Usually mechanical rejections (proof not at the reviewed head, a
  dirty worktree) or a spec the verifier reads differently each pass. It reads the title
  only, so verifiers named another way never fire it.
- `FORK_BLOAT`: a session started in the window with 500 items inherited from a fork.
  Usually a fork to switch harness after a quota wall, or to run one diagnosis, where a
  fresh session from a handover file costs a fraction.
- `SUBSCRIPTION_AMPLIFICATION`: one session wakes 2 or more subscribers each time it ends a
  turn. Usually a handover that left the old chief of staff subscribed.
- `CRON_FAIL_LOOP`: a scheduled task with 3 failed runs in the window (the run failed, or the
  session it started did); `last error` names the latest code, such as `host_offline`.
- `SIDEBAR_NOISE`: 10 or more unarchived top-level sessions that scheduled-task runs created,
  found by their run, not their title. Usually a task whose runs never archive themselves.
