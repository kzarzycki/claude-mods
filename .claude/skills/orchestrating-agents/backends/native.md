# Orchestrating with native subagents

The default backend: every harness has one, and it needs no setup.

- **Start:** your harness's own subagent tool, in the background, working in the item's
  worktree. The first message is the role file's path plus the specifics (spec and item,
  worktree, branch, base, report path). Name agents by spec, item and role
  (`s120-parser-worker`, `s120-verifier-p1`: one verifier per pass).
- **Message:** the harness's send-to-agent operation while the agent is live; otherwise
  a fresh agent whose brief points at the earlier report.
- **Wait:** end your turn. The harness notifies you when a background agent finishes,
  with its final reply, the report path; read the report then.
- **Watch:** the same notification arrives for every background agent you started, so
  there is nothing to arm for one no wait is on.
- **List:** the harness's list of running agents and background tasks.
- **Close:** stop the agent once its final reply has arrived.

## A child of another model family

This backend starts only native subagents of your own harness. A child of another model
family (which role does is the caller's policy: under the engineering loop, its
SKILL.md, Independent verification) is the Omnigent backend's
([omnigent.md](omnigent.md)); never start it with a bare CLI (`claude -p`, `codex exec`,
`omp`, `gemini -p`, `agy -p`) from a tool call, since nothing then lists, watches or
closes it. Without Omnigent, a fresh native subagent of your own harness is the only
child to start.

## A heavy run in the Claude cloud, with no Omnigent

A native subagent's Bash has no terminal, so a bare `claude --cloud "<task>"` exits 1 at once with
`--cloud requires an interactive terminal`. `scripts/claude_cloud.py` (this skill's folder) is the route that needs
only the host's Claude Code login, `git` and `gh`:

- **`start <task file> [--branch <b>]`** pushes the branch, runs `claude --cloud` under a pseudo-terminal
  (`script`), prints `session <id>` and `url <url>` from the recorded output and exits with claude's exit
  code. The task text asks the session to push its commits and post one comment on the branch's PR holding
  each command's exit code and failures: wait on that with `gh api repos/<owner>/<repo>/issues/<n>/comments`
  or `gh pr checks`, since nothing here reads a cloud session's output. With no cloud environment for the
  project it prints one line, naming `mise run claude-cloud:setup` (the project's wrapper of `claude_cloud.py
  setup`), and exits 2; run the step locally then and say so in one line.
- **`setup [--secret-as-variable] [--no-proof]`** is what a colleague runs once, and again after the
  definition changes. It makes or updates their own cloud environment from the committed
  `.claude/claude-cloud-environment.json` (`name`, `setup_script`, `network`, `variables`, `registries`, `proof`) and
  setup script `.claude/claude-cloud-setup.sh` (`.claude/cloud-setup.sh` is still read), adds each registry's token as a
  network secret (replacing the host's), pins the checkout and proves the result with one cloud run. A registry's token
  is read from `fnox -P claude-cloud get <secret>`, else a hidden prompt, and never printed or written to disk. When
  the network-secret endpoint, which is undocumented, fails, setup stops and names `--secret-as-variable`, which
  stores the token as an environment variable instead, inside the VM. `variables` holds no secret: a value that looks
  like a token is refused before any request.

`omnigent_agent.py claude-cloud-env <checkout>` (alias `cloud-env`) is the same environment step without the
secrets and the proof; both go through `scripts/claude_environments.py`.
