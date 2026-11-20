---
name: claude-handoff
description: Hand the current conversation off to a fresh Claude Code background agent that picks up the work immediately.
argument-hint: "What will the next session be used for?"
disable-model-invocation: true
---

Write a handoff summary that lets a fresh agent continue the work, save it to a file in the OS temporary directory, and launch a background agent with it as the prompt:

```sh
claude --bg --name "<descriptive name>" -- "$(cat <summary file>)"
```

Pass the summary through the file, not inline, so the shell runs no backticks and expands no `$` in it.

It starts in the current directory and returns immediately. `--name` sets the display name in the job list, session picker and terminal title, so always pass one (`--name "Fix login bug"`). The user manages the agent with `claude agents`.

- Treat any arguments as what the next session will focus on, and tailor the summary to it.
- Include a "Suggested skills" section naming the skills the next agent should load.
- Point to specs, plans, ADRs, issues, commits and diffs by path or URL instead of copying them.
- Redact secrets and personal data; the summary becomes the agent's prompt.
