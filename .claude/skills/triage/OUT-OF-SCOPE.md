# Out-of-scope knowledge base

`.out-of-scope/` holds durable records of rejected enhancement requests, so the reasoning survives the closed issue and a repeat request surfaces the earlier decision instead of re-litigating it.

## Format

One file per concept, not per issue, named in short kebab-case that is recognisable without opening it (`dark-mode.md`). Write it as a short design note, with code or examples where they make the reasoning clear:

```markdown
# Dark Mode

This project does not support dark mode or user-facing theming.

## Why this is out of scope

<the substantive, durable reason: project scope, a technical constraint, or a strategic choice>

## Prior requests

- #42: "Add dark mode support"
- #87: "Night theme for accessibility"
```

A reason tied to temporary circumstances ("too busy right now") is a deferral, not a rejection, and doesn't belong here.

## Checking

During triage, read every file and match the request by concept, not keyword ("night theme" matches `dark-mode.md`). On a match, tell the maintainer what was rejected before and why, and ask whether that still holds:

- **Confirm**: add the issue to the file's Prior requests and close it.
- **Reconsider**: delete or update the file, and the issue proceeds through normal triage. Old issues stay closed as history.
- **Distinct**: related but different; proceed with normal triage.

## Writing

Only when an enhancement, issue or PR, is rejected as `wontfix`. Never for a bug, and never for something already implemented, which would poison the dedup check with false rejections.

1. Append the issue to a matching file's Prior requests, or create a file with the concept, decision, reason and first request.
2. Comment on the issue explaining the decision and linking the file.
3. Close it as `wontfix`.
