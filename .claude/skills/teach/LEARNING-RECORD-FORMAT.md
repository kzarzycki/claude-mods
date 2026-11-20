# Learning Record Format

Learning records are the teaching equivalent of ADRs: decision-grade insights that steer future sessions and place the zone of proximal development. They live in `learning-records/` as `0001-<slug>.md`, `0002-<slug>.md`, and so on; create the directory with the first record.

```md
# {Short title of what was learned or established}

{1-3 sentences: what is now known, and why it changes what to teach next.}
```

A single paragraph is usually enough. Add these only when they carry weight:

- `Status: active | superseded by LR-NNNN`, when a later record replaces this one. Supersede rather than delete; how understanding evolved is signal.
- **Evidence**: how the user showed the understanding, when the claim may be revisited.
- **Implications**: what this unlocks or rules out, when not obvious.

Write one when:

- the user demonstrated real understanding of something non-trivial, which raises the floor for what to teach next;
- the user disclosed prior knowledge, with the depth claimed;
- a misconception was corrected, which predicts stumbles on related topics;
- the mission shifted; update `MISSION.md` too.

Not for material that was merely covered, terms already in `GLOSSARY.md`, or a session log.
