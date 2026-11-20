---
name: operating-omnigent
description: "Operate a local Omnigent install — crashes, blank UI, restarts, session attach/resume/dispose, process topology — and its raw sys_* MCP tools. Starting and collecting agents through a backend is orchestrating-agents'."
when_to_use: "Any omnigent operational question, or a sys_* call that orchestrating-agents' omnigent_agent.py does not make."
---

# Operating Omnigent

Omnigent is one server (the control plane) plus one runner per open session. Answer "is
it broken?" from the server's HTTP API and the `omnigent` CLI, not by killing processes
or reading source: the harness's permission layer (auto mode in Claude Code) may block
raw kills, and killing a runner orphans it rather than disposing its session.

## Topology

| Piece | Find it | Notes |
|---|---|---|
| Server (API + web UI) | `omnigent.cli server` on `127.0.0.1:6767` | One per machine. DB `~/.omnigent/chat.db`, artifacts `~/.omnigent/artifacts`. |
| Runner | `omnigent.runner._entry`, one PID per open session | Each spawns its own `tmux` and `claude`/`codex` terminal, so `ps` looks crowded. Idle-reaps after `runner.idle_timeout_s` (3600 s); the session then shows `runner_online: false` and is revived in place (§ Commands). |
| Logs | server `~/.omnigent/logs/server/local-server-*.log`; runner `~/.omnigent/logs/host-runner/runner-<id>.log`; CLI `~/.omnigent/logs/cli-*.log` | One file per session ever. Count live `omnigent.runner._entry` PIDs, never log files or numbers in old notes. |

`curl` is often missing from PATH in non-login shells; probe with `python3` urllib or
the CLI. Without `omnigent` on PATH, use
`~/.local/share/uv/tools/omnigent/bin/python3 -m omnigent.cli ...`.

## "Can't open omnigent"

```python
import urllib.request, json

g = lambda p: urllib.request.urlopen("http://127.0.0.1:6767" + p, timeout=5)
g("/health").read()  # {"status":"ok"}: the server is alive
```

- `/health` unreachable: the server is down; `omnigent server start`.
- `/health` ok but `/` returns `{"detail":"Not Found"}`: the web UI isn't mounted.
  `omnigent/server/app.py` mounts `server/static/web-ui` once at boot, and only if
  `index.html` exists then, so a UI built after boot (common with editable installs)
  404s every new tab until a restart; tabs already open keep working over their
  websocket. Confirm with the server start time (`ps -o lstart -p <pid>`) against the
  mtime of `web-ui/index.html`, then restart.

## Sessions API

- `GET /v1/sessions` returns `{object, data, has_more, first_id, last_id}`; each item
  has `id` (`conv_…`), `agent_name`, `status` (`running|idle|failed`), `title`,
  `runner_id`, `workspace`, `external_session_id`, `archived`.
- `GET /v1/sessions/conv_xxx` returns full detail: items, todos, `llm_model`,
  `parent_session_id`.
- Runner PID to session: `lsof -p <pid> | grep host-runner` gives its log;
  `grep -oE 'conv_[0-9a-f]{32}' <log>` gives the id to look up.

## Commands

| Action | How | Effect |
|---|---|---|
| Restart server | `omnigent stop && omnigent server start` (`omnigent server status` to check) | Drops every websocket and interrupts mid-turn work; sessions persist in SQLite. |
| Attach to a live session | `omnigent attach conv_xxx` | Interactive; needs a real terminal, not a headless shell. Starts nothing. |
| Reopen a stored session | `omnigent resume conv_xxx` | Interactive, like `attach`: fails headless. claude-native lands in `omnigent claude`. |
| Revive a reaped session | `POST /v1/sessions/conv_xxx/events` with `{"type": "retry_session", "data": {}}`, then poll `GET /v1/sessions/conv_xxx` until `runner_online` is true, then send as usual | Relaunches the runner on the same session and keeps its whole conversation; replies `{"queued": false, "recovered": true, "recovery": "runner_relaunched"}`; a native terminal already up gives `"recovered": true, "recovery": "native_terminal_ready"`, and a live runner `"recovered": false, "recovery": "already_connected"`, which is success too, so read `recovery`, not `recovered` alone. No runner to relaunch is an HTTP error. It is the web UI's "Resume session" button and works headless, unlike `omnigent resume`; the engineering-loop launcher's `send` does it by itself. Fallback: `PATCH /v1/sessions/conv_xxx` with `{"runner_id": ""}` (empty string clears, null leaves unchanged), then `POST /v1/hosts/<host_id>/runners` with `{"session_id", "workspace"}`; without the clear it fails 400 "session already has a runner bound". |
| Fork | `POST /v1/sessions/conv_xxx/fork` with optional `title`, `agent_id` (a built-in agent, switching the fork's harness) and `up_to_response_id` (copy only up to that response) | A new session holding a copy of the source's items, all of them by default. Every turn of the fork re-reads that copy, so it suits branching a short conversation, not a harness switch after a usage limit or a point diagnosis off a long session: start a fresh session briefed from the work's handover or notes file instead. |
| Archive (reversible) | `PATCH /v1/sessions/conv_xxx` with `{"archived": true}` | Hidden; transcript kept. About 8 s later (the Undo window) it stops the session and the runner bound to it. A sub-agent's archive releases only its own session on the runner it shares with its parent, which stays up, on a build with kzarzycki/omnigent 4dd0af32; an older build stops that runner and takes the parent offline. |
| Dispose (irreversible, owner-level) | `DELETE /v1/sessions/conv_xxx` | Removes tasks, terminals, files and the row. A running turn keeps running and the runner process is orphaned until the idle timeout; killing it sooner needs the user's approval for `kill <pid>`. |

If `OMNIGENT_RUNNER_ID` is set, you are running inside a runner and a server restart
kills your own session; ask the user to restart from a normal terminal.

`omnigent` may be an editable install from a local clone. It is a namespace package
(`omnigent.__file__` is `None`), so locate source with
`importlib.util.find_spec("omnigent.cli").origin`. Don't move, delete or switch branches
in that clone: the running install depends on it.

## Driving agents with `sys_*` tools

Available when an Omnigent turn advertises them. They launch and drive agents that are
already registered; authoring a new agent type (a `config.yaml` directory launched with
`config_path=`) is the `build-omnigent` skill's job when it is installed.

- `sys_agent_list`: `agent_id`s. Builtins: `claude-native-ui` (the Claude Code harness),
  `codex-native-ui`, `polly` (plans a goal, delegates to Claude, Codex or Pi sub-agents
  in parallel worktrees, and routes each diff to a different-vendor reviewer; launch it
  with the goal rather than hand-rolling that), `debby` (Claude and GPT brainstorm).
- `sys_session_create(agent_id, message?, title?)` spawns a child session (children
  only, never a sibling or top-level one) and returns its `conversation_id`. With
  `message`, it queues a turn that notifies you when done. Without it the session idles
  and nothing ever notifies; give it work with `sys_session_send`. `config_path=` in
  place of `agent_id` uploads and launches an agent from a local YAML, directory or
  `.tar.gz`.
- `sys_session_send(session_id, args)` posts a turn and returns a `launching` handle at
  once. Sent to a running child, it queues an override that takes over at the next turn
  boundary: a redirect, not a stop.
- `sys_session_get_info(session_id)`: metadata; `running` to `idle` means the turn
  finished. `failed` can still hold a complete result (codex-native flips to `failed`
  right after its final message), so read the history before concluding it produced
  nothing.
- `sys_session_get_history(conversation_id, tail_items)`: transcript tail, at most 50
  items, for any session you can access.
- `sys_call_async` and `sys_read_inbox`: background work whose completions land in the
  inbox.

All of it is asynchronous; no blocking variant exists. The loop: `sys_session_create`
with the task in `message`, wait for the runtime's `[System: sub-agent … finished …]`
notice in your next turn, then `sys_read_inbox` for the result; follow-ups go through
`sys_session_send` the same way. Fan out with several calls in one response. Poll
`get_info` or `get_history` only to debug a session that won't start. For a throwaway
helper on your own model, your harness's native subagent is synchronous and simpler;
use an Omnigent session for a different harness or a durable, independently visible
session.

Spawn briefs pass the same permission classifier as your own tool calls: a brief that
asks for an outward or unauthorized action (pushing to a default branch, reusing another
project's credential) is denied at spawn time. Gate such actions on the user inside the
brief ("commit to a local branch, do not push").

## Stopping a child

- `sys_cancel_task(child_conv_id)` cancels the in-flight turn immediately (for
  claude-native it kills the worker tmux pane via `stop_session`), but only for a
  non-terminal sub-agent registered under your session. `sys_session_send` and
  `sys_call_async` register one; a bare `sys_session_create` may not. `no in-flight task`
  means "not your tracked child, or already finished", not "unsupported".
- Fallback: `POST /v1/sessions/{id}/events` with `{"type":"interrupt"}` to cancel the
  turn, or `{"type":"stop_session"}` (owner-only) to kill the live session.
- codex-native cancellation is best-effort; the child may keep running.
- Not stops: `sys_session_close` only tombstones named sub-agents from
  `sys_session_send` in your spawn tree (it returns `session_not_a_sub_agent` for
  `sys_session_create` children, `session_out_of_tree` for independent chats and
  `sub_agent_busy` mid-turn); `sys_cancel_async` cancels only local `sys_call_async`
  tasks; `DELETE` frees resources while the turn runs on. For cleanup, let runners
  idle-reap, archive a session (a sub-agent's archive leaves its parent's runner up) or
  dispose over HTTP.

## Native-TUI child hangs at startup

A codex-native (or other `--remote` TUI) child that goes `running` then `failed` with
`model: null` in `get_info` (a healthy start shows the real model) is stuck on codex's
"Hooks need review" trust prompt, because a plugin or marketplace sync changed hooks.
Retrying won't help: the user runs `codex` once and picks "Trust all", or updates codex.
