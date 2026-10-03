# oh-my-claude

A spike: features of [oh-my-pi](https://github.com/can1357/oh-my-pi) (omp) rebuilt as Claude Code mods (plugins whose hooks run in-process through the `$` API, Claude Code 2.1.288). Each mod installs on its own. The one exception is `omc-ttsr`, which depends on `omc-jev` because its question rules need a judge.

| Mod | What it does |
| --- | --- |
| `omc-jev` | Adds `$.jev.judge` for every mod: typed questions (`choice`, `noul` = probability of yes, `score`) about a state, the shape of TypeSafe's System One API. Uses Jev when a key is set, else a small Claude model answers the same questions. Uses it for two harness decisions: **auto effort** (rate each prompt, set the turn's effort) and **unexpected stops** (a turn that ends on "Let me run the tests next." gets one resume turn). `/jev`, `/jev ask <prompt>`. |
| `omc-ttsr` | omp's TTSR rule files (`condition`, `scope`, `globs`, `question`) from `~/.omp/agent/rules`, `.omp/rules`, `~/.claude/ttsr`, `.claude/ttsr`. A `condition` rule denies the tool call that would break it and hands the model the rule as the reason. A `question` rule is judged after each turn; a yes leaves the rule for the model's next turn. `/ttsr`, `/ttsr reload`. |
| `omc-compact` | Two of omp's compaction methods. `/compact shake` moves old tool output to files under `~/.claude/omc-compact/<session>/` and leaves a pointer the model can Read (no model call). `/compact handoff [focus]` replaces the context with a handoff document written by a fork of the main thread. `autoMethod` picks what runs when the context fills. |
| `omc-hub` | `/hub` pane: this session's subagents with status, model, turns, tokens and their latest answer, plus a box that sends a message to a running one. `/hub list`, `/hub send <id> <message>`. |
| `omc-eval` | One `eval` tool backed by a long-lived Bun kernel. State persists between cells (top-level declarations, imports). Cells call Claude Code tools (`await tool.Read({ file_path })`), models (`completion()`) and subagents (`agent()`), in parallel with `Promise.all`. Every call goes back through Claude Code, so permissions and other mods' hooks still apply. `/eval <code>`, `/eval vars`, `/eval reset`. |
| `omc-panel` | `/omc`: every `omc-*` setting in one pane, or `/omc set <key> <value>`. Each mod's settings are also normal `/config` rows. |

## Install

```sh
claude plugin marketplace add ~/dev/agents/oh-my-claude
claude plugin install omc-eval@oh-my-claude      # any subset; omc-ttsr pulls in omc-jev
```

Or try without installing: `claude --plugin-dir plugins/omc-eval --plugin-dir plugins/omc-jev`.

`omc-eval` needs `bun` on the PATH (setting `omc-eval.bun` names another). To have `omc-jev` use Jev, set its API key in `/config`, or set `OPENROUTER_API_KEY` or `TYPESAFE_API_KEY`.

## Checks

- `scripts/check.sh`: validate, unit-test (`claude plugin test`) and type-check every mod, plus the kernel's self-check. No model calls, under ten seconds.
- `e2e/run.sh [jev eval ttsr compact hub panel]`: real `claude` sessions with the mods loaded, asserting on output and on files the mods write. They make real model calls; the whole run takes about four minutes. `panel`, `hub` and the question-rule check drive an interactive session through `expect`, because headless `claude -p` differs there (see below).

## How the pieces work

- **`$.jev` across mods.** A mod adds a noun to `$` in `engine.create`. The noun's methods are only placeholders: calling `$.jev.judge(x)` raises the event `jev.judge`, which omc-jev's hook answers with a `$` of its own. A `$` captured at `engine.create` can't be used later; the validator refuses it.
- **Eval kernel transport.** A mod can write to a child's stdin only once, so the kernel serves HTTP on a Unix socket instead (`$.http.fetch` with `socketPath`). A cell that needs the host parks the call and returns it as a `call` event; the mod runs it and answers with `/resume`.
- **Subagents from a cell.** `agent()` spawns the subagent and the eval hook waits on `/next`. The subagent's hand-back (`SubagentHandback`, or its final `turn.complete`) answers the call through `/answer`. Every wait happens inside `$.http.fetch`, which doesn't count against the hook's 10-second budget. Waiting on an ordinary promise would count.
- **Kernel lifetime.** The kernel is started from `session.start` and restarted when it exits (`/eval reset` simply exits it). It dies with the mod's module, and a parent-pid watchdog ends it if Claude Code dies.

## What the spike found about the platform

Each item was observed in a run, not read from docs.

- **Settings rows are interactive-only.** Plugin `userConfig` rows are in `$.config.list()` in an interactive session but not under `claude -p`, where only the engine's 40 rows come back.
- **Notes appended after the last turn are lost headless.** A `$.session.append` made after the last turn of a `claude -p` run never reaches the transcript, because the process exits. Interactively the model reads it on its next turn.
- **Compaction can't start from a command.** A `command.run` hook may not call `$.session.compact`; the engine refuses because the command holds the turn. Hence `/compact shake`, not `/shake`.
- **Fork can fail after a resume.** `$.model.fork` has nothing to fork right after a session is resumed headless. Handoff falls back to `$.model.complete` over the messages `session.compact` passes in.
- **A missing dependency blocks the load.** A mod whose `dependencies` aren't loaded doesn't load at all. A marketplace install pulls the dependency in (`+ 1 dependency: omc-jev`).
- **Child sessions don't save transcripts.** A session started from inside another Claude Code session inherits `CLAUDE_CODE_CHILD_SESSION` and stops saving transcripts; the e2e scripts unset it.
- **Haiku subagents can miss the task.** A Haiku subagent sometimes answers its injected system context ("System initialization acknowledged…") instead of the task. The e2e checks use Sonnet for subagents.
- **Test-kit gaps** (`claude plugin test`):
  - A test hook on `session.append` never sees `$.session.append`.
  - A test hook answering `agent.spawn` gets no agent id.
  - Test plugins run without their closures.

  Those paths are covered by e2e instead.

## Not done or not verified

- **Jev itself.** Untested against the real API: no key was available, so every live run used the Claude fallback (`claude/haiku`). The request shape matches omp's TypeSafe client, and a unit test checks it against a faked reply.
- **Steering a running subagent** (`/hub send`, the pane's input). No automated check: the kit can't intercept `$.session.append`, and an e2e needs a subagent that stays running long enough.
- **TTSR rules scoped to edit/write miss Bash.** A model that's refused a `Write` can write the same file with `printf … > file` (seen in an e2e run). Scope a rule to `tool:bash` too if that matters; matching shell redirections to file globs isn't done.
- **Eval cell timeouts.** A cell has no timeout. A synchronous infinite loop blocks the kernel until `/eval reset` (or `reset: true`). `judge()` in cells isn't wired: it would make `omc-eval` depend on `omc-jev`.
- **omp features left out of this MVP.** Snapcompact, omp's soft compaction, idle compaction, TTSR rules on streamed text (Claude Code can't take back text it has already shown), and multi-vendor models.
