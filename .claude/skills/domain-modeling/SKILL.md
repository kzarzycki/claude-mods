---
name: domain-modeling
description: Build and sharpen a project's domain model, its GLOSSARY.md glossary and its ADRs. Use when discussing codebase terminology, writing or editing a GLOSSARY.md, or recording or editing an ADR.
---

# Domain Modeling

Sharpen the project's domain language while you design, and write it down as it settles. Reading `GLOSSARY.md` for vocabulary needs no skill; this one is for changing the model.

## Where it lives

A single-context repo keeps `GLOSSARY.md` at the root and ADRs in `docs/adr/`. A root `GLOSSARY-MAP.md` means several contexts: it points to each context's own `GLOSSARY.md`, which has a `docs/adr/` beside it for that context's decisions, while the root `docs/adr/` holds system-wide ones. Work in the context the topic belongs to, and ask when that is unclear. Create a file or directory only when you have its first entry to write.

## During the session

- Call out a term that conflicts with `GLOSSARY.md` as soon as it is used.
- Propose one canonical word for a vague or overloaded term ("account": the Customer or the User?).
- Probe the boundaries between concepts with concrete edge-case scenarios.
- Check claims about how the system works against the code, and surface contradictions.
- Write each resolved term into `GLOSSARY.md` when it settles rather than batching at the end, in the format of [GLOSSARY-FORMAT.md](./GLOSSARY-FORMAT.md). It is a glossary only: no implementation details, spec, or scratch notes.
- Offer an ADR only when the decision is hard to reverse, surprising without context, and the result of a real trade-off; if any of the three is missing, skip it. Format: [ADR-FORMAT.md](./ADR-FORMAT.md).
