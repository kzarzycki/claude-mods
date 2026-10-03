# claude-mods

Claude Code mods: plugins whose hooks run inside Claude Code's engine through the in-process `$` API. Each one installs on its own from this repository's plugin marketplace. Mods that make decisions with a model (`auto-effort`, `resume-on-stop`, `ttsr-rules`) depend on `decision-model`, which provides that model.

## oh-my-pi features

The first set rebuilds features of [oh-my-pi](https://github.com/can1357/oh-my-pi) (omp), a coding-agent harness, as mods. The research behind it rates every omp feature by how naturally it fits Claude Code: [proposal](https://kzarzycki.github.io/claude-mods/proposal.html) (written before the build, where the project was called omc). The rest of this README covers that set: how to install it, how it works, and what building it found out about the platform.

| Mod | What it does |
| --- | --- |
| `decision-model` | The decision model, for other mods: `$.decision.ask({ state, questions })`, with typed questions (`choice`, `noul` = probability of yes, `score`) in the request and answer shape of TypeSafe's System One API. Any endpoint that speaks that protocol is a backend (presets `openrouter` and `typesafe`, or a URL; Jev is the default model). Without a key, a small Claude model answers the same questions as text. It does no deciding of its own. `/decision` shows the backend and every recent decision with the mod that asked; `/decision ask <question> -- <state>` tries one. |
| `auto-effort` | Auto effort: asks the decision model how open-ended each prompt is and runs that turn at the chosen effort, up to a ceiling. `/effort-rate <prompt>`. |
| `resume-on-stop` | Unexpected stops: a turn that ends on "Let me run the tests next." without acting is spotted by the decision model and gets one resume turn. |
| `ttsr-rules` | omp's TTSR rule files (`condition`, `scope`, `globs`, `question`) from `~/.omp/agent/rules`, `.omp/rules`, `~/.claude/ttsr`, `.claude/ttsr`. A `condition` rule denies the tool call that would break it and hands the model the rule as the reason. A `question` rule is put to the decision model after each turn; a yes leaves the rule for the model's next turn. `/ttsr`, `/ttsr reload`. |
| `compact-methods` | Two of omp's compaction methods. `/compact shake` moves old tool output to files under `~/.claude/compact-methods/<session>/` and leaves a pointer the model can Read (no model call). `/compact handoff [focus]` replaces the context with a handoff document written by a fork of the main thread. `autoMethod` picks what runs when the context fills. |
| `agent-hub` | `/hub` pane: this session's subagents with status, model, turns, tokens and their latest answer, plus a box that sends a message to a running one. `/hub list`, `/hub send <id> <message>`. |
| `eval-kernel` | One `eval` tool backed by a long-lived Bun kernel. State persists between cells (top-level declarations, imports). Cells call Claude Code tools (`await tool.Read({ file_path })`), models (`completion()`) and subagents (`agent()`), in parallel with `Promise.all`. Every call goes back through Claude Code, so permissions and other mods' hooks still apply. `/eval <code>`, `/eval vars`, `/eval reset`. |

## Install

Built and tested on Claude Code 2.1.288. The mods use the in-process `$` hook API, so older versions won't load them.

### From GitHub (to use them)

```sh
claude plugin marketplace add kzarzycki/claude-mods
claude plugin install auto-effort@claude-mods     # pulls in decision-model
claude plugin install resume-on-stop@claude-mods
claude plugin install ttsr-rules@claude-mods
claude plugin install compact-methods@claude-mods
claude plugin install agent-hub@claude-mods
claude plugin install eval-kernel@claude-mods
```

Pick any subset; each mod works alone, and the three that make decisions pull in `decision-model`. Inside a session, `/plugin` does the same from a menu. `claude plugin marketplace update claude-mods` fetches new versions.

### From a clone (to change them)

```sh
git clone https://github.com/kzarzycki/claude-mods && cd claude-mods
claude --plugin-dir plugins/decision-model --plugin-dir plugins/auto-effort   # one session
```

To load them in every session, including ones another tool starts (omnigent, an IDE), list the folders in `~/.claude/settings.json`; an interactive session reloads a mod when you save its files:

```json
{ "env": { "CLAUDE_CODE_PLUGIN_DIRS": "/path/to/claude-mods/plugins/decision-model:/path/to/claude-mods/plugins/auto-effort" } }
```

Options of mods loaded this way are under `<name>@inline` (in `/config`, or `claude plugin configure decision-model@inline`).

### Setup

- **Jev for decisions.** Without a key, `decision-model` asks Claude Haiku. To use Jev, give it an OpenRouter key without echoing it:
  ```sh
  read -rs K && printf '{"apiKey":"%s"}' "$K" | claude plugin configure decision-model@claude-mods --values-stdin; unset K
  ```
  (`decision-model@inline` for a clone), or set `OPENROUTER_API_KEY`. A TypeSafe key needs `"endpoint":"typesafe"` too; `endpoint` also takes the URL of any other System One server, with `model` naming its model. `/decision` shows which backend answers.
- **`eval-kernel`** needs [Bun](https://bun.sh) on the PATH (or its `bun` option set to one).
- **TTSR rules** are Markdown files in `.claude/ttsr/` (project) or `~/.claude/ttsr/`; existing omp rule folders are read too. See `e2e/ttsr.sh` for one of each kind.

## Checks

- `scripts/check.sh`: validate, unit-test (`claude plugin test`) and type-check every mod, plus the kernel's self-check. No model calls, under ten seconds.
- `e2e/run.sh [decision eval ttsr compact hub]`: real `claude` sessions with the mods loaded, asserting on output and on files the mods write. They make real model calls; the whole run takes about four minutes. `hub` and the question-rule check drive an interactive session through `expect`, because headless `claude -p` differs there (see below).

## How the pieces work

- **A decision model, and the places that use it.** `decision-model` owns the protocol and the backend; each place a decision is made (effort, stops, question rules) is its own mod that asks through `$.decision.ask` and names its `purpose` for the log. Swapping Jev for another model, or for Claude, changes no consumer.
- **`$.decision` across mods.** A mod adds a noun to `$` in `engine.create`. The noun's methods are only placeholders: calling `$.decision.ask(x)` raises the event `decision.ask`, which decision-model's hook answers with a `$` of its own. A `$` captured at `engine.create` can't be used later; the validator refuses it.
- **Eval kernel transport.** A mod can write to a child's stdin only once, so the kernel serves HTTP on a Unix socket instead (`$.http.fetch` with `socketPath`). A cell that needs the host parks the call and returns it as a `call` event; the mod runs it and answers with `/resume`.
- **Subagents from a cell.** `agent()` spawns the subagent and the eval hook waits on `/next`. The subagent's hand-back (`SubagentHandback`, or its final `turn.complete`) answers the call through `/answer`. Every wait happens inside `$.http.fetch`, which doesn't count against the hook's 10-second budget. Waiting on an ordinary promise would count.
- **Kernel lifetime.** The kernel is started from `session.start` and restarted when it exits (`/eval reset` simply exits it). It dies with the mod's module, and a parent-pid watchdog ends it if Claude Code dies.

## What the spike found about the platform

Each item was observed in a run, not read from docs.

- **Settings rows are interactive-only.** Plugin `userConfig` rows are in `$.config.list()` in an interactive session but not under `claude -p`, where only the engine's 40 rows come back.
- **Notes appended after the last turn are lost headless.** A `$.session.append` made after the last turn of a `claude -p` run never reaches the transcript, because the process exits. Interactively the model reads it on its next turn.
- **Compaction can't start from a command.** A `command.run` hook may not call `$.session.compact`; the engine refuses because the command holds the turn. Hence `/compact shake`, not `/shake`.
- **Fork can fail after a resume.** `$.model.fork` has nothing to fork right after a session is resumed headless. Handoff falls back to `$.model.complete` over the messages `session.compact` passes in.
- **A missing dependency blocks the load.** A mod whose `dependencies` aren't loaded doesn't load at all. A marketplace install pulls the dependency in (`+ 1 dependency`).
- **Jev returns real distributions; the Claude backend can't.** Jev's `choice` answers carry probabilities (`xhigh 0.99, high 0.01`, confidence 0.98); the Claude text judge answers one-hot. Jev's `noul` can sit near the middle where a reader would say yes: "Is `DROP TABLE users;` in production irreversible?" came back 0.51, so thresholds need tuning per question.
- **Child sessions don't save transcripts.** A session started from inside another Claude Code session inherits `CLAUDE_CODE_CHILD_SESSION` and stops saving transcripts; the e2e scripts unset it.
- **Haiku subagents can miss the task.** A Haiku subagent sometimes answers its injected system context ("System initialization acknowledged…") instead of the task. The e2e checks use Sonnet for subagents.
- **Test-kit gaps** (`claude plugin test`):
  - A test hook on `session.append` never sees `$.session.append`.
  - A test hook answering `agent.spawn` gets no agent id.
  - Test plugins run without their closures.

  Those paths are covered by e2e instead.

## Not done or not verified

- **Other System One servers.** Jev through the OpenRouter preset is checked live (the `decision` and `ttsr` e2e suites pass against it, answering as `typesafe/jev-1.13-20260917`). The TypeSafe preset and custom URLs are checked only against faked replies.
- **Steering a running subagent** (`/hub send`, the pane's input). No automated check: the kit can't intercept `$.session.append`, and an e2e needs a subagent that stays running long enough.
- **TTSR rules scoped to edit/write miss Bash.** A model that's refused a `Write` can write the same file with `printf … > file` (seen in an e2e run). Scope a rule to `tool:bash` too if that matters; matching shell redirections to file globs isn't done.
- **Eval cell timeouts.** A cell has no timeout. A synchronous infinite loop blocks the kernel until `/eval reset` (or `reset: true`). `judge()` in cells isn't wired: it would make `eval-kernel` depend on `decision-model`.
- **omp features left out of this MVP.** Snapcompact, omp's soft compaction, idle compaction, TTSR rules on streamed text (Claude Code can't take back text it has already shown), and multi-vendor models.
