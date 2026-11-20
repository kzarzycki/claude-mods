# Design It Twice

The first interface idea is rarely the best (Ousterhout), so produce several radically different designs for the chosen candidate and compare them. Name things in the vocabulary of [SKILL.md](SKILL.md) and the project's `GLOSSARY.md`.

1. **Frame the problem** for the user: the constraints any new interface must meet, its dependencies and their category (SKILL.md, "Deepening a cluster"), and a rough code sketch that makes the constraints concrete, not a proposal. Show it and move straight on; the user reads while the designs are drafted.
2. **Draft at least three designs**, each under a different constraint:
   - minimise the interface: one to three entry points, maximum leverage per entry point;
   - maximise flexibility: many use cases and extension;
   - optimise for the most common caller: make the default case trivial;
   - when dependencies cross a seam, design around ports and adapters.

   Draft them in parallel sub-agents where your harness can, each started with a fresh context window rather than forked from yours, so no design anchors on another or on your own framing. Give each a technical brief (file paths, coupling, dependency category, what sits behind the seam, both vocabularies) rather than the user-facing framing. Each design covers: the interface (types, methods, parameters, invariants, ordering, error modes), a usage example, what the implementation hides, the dependency strategy and adapters, and where leverage is high or thin.
3. **Compare.** Present the designs one at a time, then contrast them in prose by depth, locality and seam placement. Recommend the strongest, or a hybrid when parts combine well; the user wants a strong read, not a menu.
