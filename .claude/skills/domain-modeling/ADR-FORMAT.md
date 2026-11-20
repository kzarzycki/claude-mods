# ADR Format

Files are `docs/adr/NNNN-slug.md` (`0001-event-sourced-orders.md`), numbered one past the highest existing number.

```md
# {Short title of the decision}

{1-3 sentences: the context, the decision, and why.}
```

A single paragraph is a complete ADR: the value is recording that the decision was made and why. Add a section only when it earns its place:

- `Status` frontmatter (`proposed | accepted | deprecated | superseded by ADR-NNNN`) when decisions get revisited.
- **Considered Options** when the rejected alternatives are worth remembering.
- **Consequences** when downstream effects are non-obvious.

Decisions that typically qualify: architectural shape, integration patterns between contexts, technology choices with real lock-in (not every library), ownership and scope boundaries (the explicit no's too), deliberate deviations from the obvious path (so nobody "fixes" them), constraints invisible in the code (compliance, a partner's latency contract), and rejections a future reader would otherwise re-propose.
