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
| `self-compact` | Compaction at task boundaries rather than at overflow. The model can call `compact_after_turn` (with a `focus` for what to keep) and the compaction runs as `/compact` once its turn ends. Above `threshold` (60% of the auto-compact window, not the model's), a turn `decision-model` judges a finished task gets a short follow-up turn asking the model whether to compact; without `decision-model`, each prompt carries a hidden line with the fill level instead. A session left above the threshold compacts after `idleSeconds` (default 1800; 0 turns it off) with no prompt from a person, a declined nudge included. Claude Code's own idle compaction (the `idleCompaction` setting, read from 2.1.326) is narrower: attended sessions on the 1-hour prompt cache only, about 54 minutes after the last request, above 200k tokens (`CLAUDE_CODE_IDLE_COMPACT_MIN_TOKENS`, floor 100k). |
| `agent-hub` | `/hub` pane: this session's subagents with status, model, turns, tokens and their latest answer, plus a box that sends a message to a running one. `/hub list`, `/hub send <id> <message>`. |
| `code-mode` | Claude Code's Code Mode as a mod: one `repl` tool runs JavaScript in a long-lived Bun kernel, with Code Mode's globals (`$`, `file`, `edit`, `write`, `preview`, `tools`, `searchTools`, `describeTool`, `self.log`, `console.tail`) plus `completion()`, `agent()` (with a JSON Schema `schema` for a parsed answer) and `judge()` (when `decision-model` is loaded). `$` runs as the Bash tool and the file globals as Read, Edit and Write, so the person sees each call and permissions and other mods' hooks still apply. Code Mode's own prompt text, adapted, is the tool's description, in one of two modes (below). It goes there, not into the system prompt, because an organization's sec-default mod skips a person's prompt hooks. State persists between calls (top-level declarations, destructuring and imports included; `require` works too); a script may run as long as it needs, and scripts run side by side in one shared scope. Subagents share the kernel by default, so a script can hand a subagent data through a variable; the `subagents` option set to `own` gives each subagent a kernel of its own. `/repl <code>`, `/repl vars`, `/repl reset`. |

## Install

Built on Claude Code 2.1.288 and tested on 2.1.326. The mods use the in-process `$` hook API, so older versions won't load them. On 2.1.321 to 2.1.326, `claude plugin test` can't route one mod's call to another mod's noun, so the unit tests that need `$.decision` skip there and say so; `e2e/run.sh` runs them in real sessions.

### From GitHub (to use them)

```sh
claude plugin marketplace add kzarzycki/claude-mods
claude plugin install auto-effort@claude-mods     # pulls in decision-model
claude plugin install resume-on-stop@claude-mods
claude plugin install ttsr-rules@claude-mods
claude plugin install compact-methods@claude-mods
claude plugin install self-compact@claude-mods
claude plugin install agent-hub@claude-mods
claude plugin install code-mode@claude-mods      # replaces eval-kernel: uninstall that first
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
- **`code-mode`** needs [Bun](https://bun.sh) on the PATH (or its `bun` option set to one). It has two modes, picked per request from the tools the model is offered (`mode` option: `auto`, `preferred`, `exclusive`):
  - **Preferred** (a normal session): the other tools stay, and the guide says `repl` is the better way for shell, file and multi-step work, with a direct call still fine for one call whose whole output the model needs.
  - **Exclusive**: start the session with the built-ins denied, `claude --disallowedTools Bash Read Edit Write Glob Grep NotebookEdit`, and `repl` is the model's one way to work. Scripts still reach those tools, because a deny rule stops only the model, not a mod's `$.tool.call`.
  - **The guide in the system prompt**: the mod can only make the guide repl's tool description, because an organization's sec-default mod skips a person's prompt hooks. A launcher can put it in the system prompt instead: `bun plugins/code-mode/guide.ts [exclusive|preferred] > guide.md`, then `claude --append-system-prompt-file guide.md` with the env var `CODE_MODE_GUIDE=system` (in `--settings` `env`), so repl's description points there instead of repeating it. Under Omnigent use the file flag: it refuses a launch argument over 4,096 characters.
  - **As an Omnigent agent**: list the denied tools as patterns, `disallowed_tools: ["Bash(*)", "Read(*)", ...]`. A plain name there also becomes Omnigent's server deny policy, whose PreToolUse hook refuses the mod's calls too ("Tool 'Bash' is forbidden by the agent spec"); a pattern only reaches the harness flag, and still hides the tool from the model.
- **TTSR rules** are Markdown files in `.claude/ttsr/` (project) or `~/.claude/ttsr/`; existing omp rule folders are read too. See `e2e/ttsr.sh` for one of each kind.

## Checks

- `scripts/check.sh`: validate, unit-test (`claude plugin test`) and type-check every mod, plus the kernel's self-check. No model calls, under ten seconds.
- `e2e/run.sh [decision repl ttsr compact hub self-compact]`: real `claude` sessions with the mods loaded, asserting on output and on files the mods write. They make real model calls; the whole run takes about four minutes. `hub` and the question-rule check drive an interactive session through `expect`, because headless `claude -p` differs there (see below).

## How the pieces work

- **A decision model, and the places that use it.** `decision-model` owns the protocol and the backend; each place a decision is made (effort, stops, question rules) is its own mod that asks through `$.decision.ask` and names its `purpose` for the log. Swapping Jev for another model, or for Claude, changes no consumer.
- **`$.decision` across mods.** A mod adds a noun to `$` in `engine.create`, and the noun's methods do the work: Claude Code sends every mod's `$.decision.ask(x)` to decision-model's method (the host op `interface.call`). That method reaches the host only as `beneath.<noun>.<method>(...)` on the value of `next(e)`, with each environment variable's name written out, so it hands `decide` three small functions (key, fetch, model call) built that way. `/decision` builds the same three from its own `$`.
- **code-mode kernel transport.** A mod can write to a child's stdin only once, so the kernel serves HTTP on a Unix socket instead (`$.http.fetch` with `socketPath`). A script that needs the host parks the call and returns it as a `call` event; the mod runs it and answers with `/resume`.
- **Long scripts.** A request through `$.http.fetch` is cut after about 30 s, so the kernel answers `{status: "wait"}` after 20 s with nothing new and the mod asks `/next` again. A script can run for as long as it needs.
- **Scripts side by side.** Each `/run` starts a cell with its own id, and `/next`, `/resume` and `/cancel` name it, so a subagent's script and its parent's don't take each other's events. All cells share one `globalThis`; `AsyncLocalStorage` tells which cell a host call or log line belongs to. An interrupt or the host-call cap cancels only its own script, and the variables stay.
- **Subagents from a script.** `agent()` spawns the subagent and the repl hook waits on `/next`. The subagent's hand-back (`SubagentHandback`, or its final `turn.complete`) answers the call through `/answer`. Every wait happens inside `$.http.fetch`, which doesn't count against the hook's 10-second budget. Waiting on an ordinary promise would count.
- **Kernel lifetime.** The kernel is started from `session.start` and restarted when it exits (`/repl reset` simply exits it). It dies with the mod's module, and a parent-pid watchdog ends it if Claude Code dies. A kernel that starts where an earlier one ran (a marker file per session) puts a `[repl]` line at the top of its first result, so the model knows its variables are gone instead of finding out from a `ReferenceError`. A mod reload from editing a `--plugin-dir` (any session's edit) restarts it too. An unhandled rejection is logged to the console ring instead of ending the kernel.
- **`reset: true` in shared mode** restarts the one kernel, so it wipes the variables of every agent using it.

## What the spike found about the platform

Each item was observed in a run, not read from docs.

- **Settings rows are interactive-only.** Plugin `userConfig` rows are in `$.config.list()` in an interactive session but not under `claude -p`, where only the engine's 40 rows come back.
- **Notes appended after the last turn are lost headless.** A `$.session.append` made after the last turn of a `claude -p` run never reaches the transcript, because the process exits. Interactively the model reads it on its next turn.
- **Compaction can't start from a command.** A `command.run` hook may not call `$.session.compact`; the engine refuses because the command holds the turn. Hence `/compact shake`, not `/shake`.
- **Fork can fail after a resume.** `$.model.fork` has nothing to fork right after a session is resumed headless. Handoff falls back to `$.model.complete` over the messages `session.compact` passes in.
- **A missing dependency blocks the load.** A mod whose `dependencies` aren't loaded doesn't load at all. A marketplace install pulls the dependency in (`+ 1 dependency`).
- **Jev returns real distributions; the Claude backend can't.** Jev's `choice` answers carry probabilities (`xhigh 0.99, high 0.01`, confidence 0.98); the Claude text judge answers one-hot. Jev's `noul` can sit near the middle where a reader would say yes: "Is `DROP TABLE users;` in production irreversible?" came back 0.51, so thresholds need tuning per question.
- **A mod compacts only between turns.** `$.session.compact` and `$.command.run("compact")` are refused inside `tool.call` and `prompt.submit` hooks ("would compact under the turn this hook is holding"), so a model can't compact mid-turn and a mod can't compact just before a new prompt runs. From `turn.complete` both work interactively; headless (`-p`) only `$.command.run("compact")` does.
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
- **Script timeouts.** A script has no timeout. A synchronous infinite loop blocks the kernel until `/repl reset` (or `reset: true`). `agent()`'s `schema` is parsed, not validated: a wrong shape reaches the script as is.
- **What code-mode leaves out of Claude Code's Code Mode.**
  - Scripts don't detach: a `repl` call waits for its script to end, so there is no Poll tool and no background lane. Scripts started side by side (by subagents, or parallel `repl` calls) do run at once.
  - Subagents share the parent's variables by default; in Claude Code's Code Mode each agent has a context of its own (our `subagents: own`).
  - No tool schemas: `searchTools` and `describeTool` give names and descriptions only, because Claude Code hands mods no input schemas.
  - `$` output is what the Bash tool returns; there is no spill-file reading of large outputs.
  - Timers a script sets aren't cleared when it ends.
  - The context isn't sealed: `import`, Bun and `node:*` work, and that work goes around Claude Code's permissions. The prompt tells the model to use the globals.
  - Permissions: every `repl` call is one permission decision, and each Bash, Read, Edit or Write inside it is checked again. In a mode that asks, that is a prompt per tool call; bypass mode asks nothing.
- **omp features left out of this MVP.** Snapcompact, omp's soft compaction, idle compaction, TTSR rules on streamed text (Claude Code can't take back text it has already shown), and multi-vendor models.
