---
name: wizard
description: Generate an interactive bash wizard that walks a human through steps only they can perform, such as provisioning infrastructure, setting up credentials or CI secrets, clicking through an unfamiliar third-party dashboard, or running a one-off migration or cutover. Not for steps the agent can perform itself.
---

# Wizard

A wizard is a bash script that walks a human through a manual procedure only they can perform: it opens each URL, says exactly what to click and copy, captures the values, writes them where they belong (`.env`, GitHub secrets and variables), confirms before irreversible steps and shows how many stages are left. It saves re-explaining the procedure to an agent every time.

[template.sh](template.sh) already provides the UX: stage progress, confirmation gates, cross-platform URL opening including WSL, hidden secret entry, idempotent `.env` upserts, `gh secret` and `gh variable` writes, and a closing summary. Your job is to scope the procedure and author its stages. Never edit the library above the `STAGES` marker; it is identical in every wizard.

A wizard is built for one run by default: save it to a scratch path or `scripts/` and delete it when the job is done. Commit it only when the user wants a repeatable setup path, and then link it from the README so the next person runs the script instead of asking an agent.

## 1. Scope

Read the repo before asking: `.env`, `.env.example`, `.env.*`, the README, `docker-compose*`, framework config and `.github/workflows/*`, where every `secrets.*` or `vars.*` reference is a value the wizard must produce. For a migration, establish the current state, the target state and the irreversible actions between them.

For each captured value, know where the human gets it, where it is written (`.env`, a GitHub secret, both, or nowhere, since some stages are pure actions), and whether it is secret. Show the user the ordered stages and their values, and let them add, drop or reorder before you write the script.

## 2. Map each stage

Write the exact path a human follows, such as "Dashboard → Developers → API keys → Reveal test key → copy", concrete enough for a stranger. Where you do not know the current UI or command, check the docs or ask; never invent a step.

## 3. Author

Copy `template.sh` to the target path, replace the example stage with one `stage` per step in dependency order, and set `TOTAL_STAGES` and the `banner` title to match. Keep every stage inside `run_wizard` and leave the file's last line as is: bash then parses the whole script before the first prompt, so an edit made while it runs cannot break it. Build stages from the library helpers: `stage`, `say`, `step`, `note`, `warn`, `open_url`, `ask`, `ask_secret`, `write_env`, `set_secret`, `set_var`, `pause`, `confirm`.

Open the URL before asking for its value, use `ask_secret` for anything secret, `write_env` every persisted value, `set_secret` only the values CI needs, and `confirm` before any irreversible action. Each `stage` clears the screen, so keep a stage to one task the human can finish without scrolling back.

## 4. Check and hand off

Run `bash -n` on the script, `shellcheck` if available, then `chmod +x`. Do not run it yourself: it opens browsers and blocks on human input. Trace it statically instead: every value from the scope lands where planned, and every `set_secret` name matches a `secrets.*` reference in CI. Tell the user how to run it.
