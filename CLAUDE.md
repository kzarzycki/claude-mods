# claude-mods

Claude Code mods: hooks, tools and panels that change how Claude Code works.

## Conventions

- **Commits:** Conventional Commits (`feat:`, `fix:`, `docs:`, `refactor:`, `test:`, `chore:`). Optional scope: `feat(api):`.
- **Branches:** `feat/<kebab-case>`, `fix/<kebab-case>`.
- **Before committing:** show the diff and the message. Hooks run each `lint:` task on the staged files on commit; `mise run check` runs the lints and the unit tests, `mise run check:all` every check CI runs, and `mise tasks` lists the rest.
- **Secrets:** never commit `.env`. CI fails if `.env` is tracked. Add false positives to `.gitleaks.toml`.
- **Decisions:** record architecture decisions as ADRs in `docs/adr/` (start from `docs/adr/0001-record-architecture-decisions.md`).

## Tooling (Claude Code mods)

- Each mod is a folder under `plugins/`, listed in `.claude-plugin/marketplace.json`. Keep the `version` in its own `.claude-plugin/plugin.json` current.
- `mise run test` (`scripts/check.sh`) validates, unit-tests and type-checks every mod, plus the code-mode kernel's self-check. No model calls; CI runs the same.
- `e2e/run.sh [suite…]` runs real `claude` sessions with the mods loaded. It makes model calls, so it runs by hand, not in CI.
- Try a change in a session with `claude --plugin-dir plugins/<mod>`. The first load lays the mod's types into `.claude-plugin/types/`, which the type check needs.
