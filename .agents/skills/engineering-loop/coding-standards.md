# Coding standards

The generic half, read at Build and Verify with the project's
`docs/agents/coding-standards.md` § Domain facts. Lint, types and tests
are the baseline and are not restated. A project adds a line to its own file on the
second occurrence of a mistake; a line that would not change behaviour goes.

## Tests and evidence

- Never edit or delete a test to make it pass. A failing test is a red light, never a
  caveat in the report.
- A bug fix ships a regression test named after its root cause. Test names are sentences.
- A performance fix's test counts work (queries, calls, rows, bytes), never time, which
  varies with the host.
- Evidence is by kind: a UI change gets one e2e test that fails if the feature breaks,
  plus a link to see it; a data change gets counts and timings from a real run in the
  commit and PR body; any other kind gets what `docs/agents/loop.md` § Proof on a branch names.

## Code

- Removing beats adding. A feature nobody has asked to use does not exist yet, and
  earlier decisions, including other models', are hypotheses.
- `ponytail:` marks a deliberate ceiling with its upgrade path
  (`# ponytail: global lock, per-account locks if throughput matters`), below the spec:
  it changes how an approved item is built, never whether. Triage's fail-fast guards carry
  one, and a reviewer reads it as known, not as a finding. A `ponytail:` that narrows an
  approved acceptance item or Implementation Decision is a spec deviation, and the reviewer
  reports it as a finding, since the owner approved the item, not the ceiling.
- A script is non-interactive and reproduces on another host: setup is code.

## Docs and git

- Docs hold only what code cannot say, written as current truth: rewrite, never amend,
  and delete a doc with the code it describes. A comment states the current rule; one
  that describes removed behaviour is fixed or deleted.
- A commit body says what and why, with measured evidence.
