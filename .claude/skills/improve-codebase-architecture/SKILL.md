---
name: improve-codebase-architecture
description: Scan a codebase for deepening opportunities, present them as a visual HTML report, then grill through whichever one you pick.
disable-model-invocation: true
---

# Improve Codebase Architecture

Find architectural friction and propose deepening opportunities: refactors that turn shallow modules into deep ones, for testability and AI-navigability.

Speak two vocabularies exactly, in the report and in conversation:

- Architecture terms come from the `codebase-design` skill: module, interface, implementation, depth, deep, shallow, seam, adapter, leverage, locality, and its principles (the deletion test, the interface as test surface, one adapter versus two). Never substitute component, service or unit for module; API or signature for interface; boundary for seam; layer or wrapper for module.
- Domain names come from `GLOSSARY.md`: if it defines "Order", write "the Order intake module", not "the FooBarHandler" or "the Order service".

ADRs in `docs/adr/` record decisions not to re-litigate.

## 1. Explore

Deepening pays off in future changes, so weight the parts of the codebase that change. Take the user's direction (a module, subsystem or pain point) if they gave one; otherwise walk back a good stretch of `git log` for the hot spots and look there first, widening the net only if the changes are scattered. Read `GLOSSARY.md` and the area's ADRs before scanning. Hand the walk to a sub-agent, started with a fresh context window rather than a fork of yours, when it would flood your context.

Look for friction rather than following a checklist: one concept that needs bouncing between many small modules, interfaces nearly as complex as their implementations, pure functions extracted for testability while the bugs hide in how they are called, coupling that leaks across seams, code that is untested or hard to test through its interface. Apply the deletion test to every suspect; a candidate is one where deleting would concentrate complexity, not just move it.

A candidate that contradicts an ADR belongs in the report only when the friction is real enough to reopen the ADR; do not list every refactor an ADR forbids.

## 2. Report

Write one self-contained HTML file to `<tmpdir>/architecture-review-<timestamp>.html`, where `<tmpdir>` is `$TMPDIR`, else `/tmp` (`%TEMP%` on Windows), so nothing lands in the repo and each run gets a fresh file. Open it in the user's browser and give its absolute path. Then ask which candidate they want to explore; do not propose interfaces yet.

```html
<!doctype html>
<html lang="en">
  <head>
    <meta charset="utf-8" />
    <title>Architecture review for {{repo name}}</title>
    <script src="https://cdn.tailwindcss.com"></script>
    <script type="module">
      import mermaid from "https://cdn.jsdelivr.net/npm/mermaid@11/dist/mermaid.esm.min.mjs";
      mermaid.initialize({ startOnLoad: true, theme: "neutral", securityLevel: "loose" });
    </script>
    <style>
      /* small custom layer for things Tailwind doesn't cover cleanly */
      .seam { stroke-dasharray: 4 4; }
      .leak { stroke: #dc2626; }
      .deep { background: linear-gradient(135deg, #0f172a, #1e293b); }
    </style>
  </head>
  <body class="bg-stone-50 text-slate-900 font-sans">
    <main class="max-w-5xl mx-auto px-6 py-12 space-y-12">
      <header>...</header>
      <section id="candidates" class="space-y-10">...</section>
      <section id="top-recommendation">...</section>
    </main>
  </body>
</html>
```

These two scripts are the only ones; the report is otherwise static. The header holds the repo name, the date and a legend (solid box = module, dashed line = seam, red arrow = leakage, thick dark box = deep module), then goes straight into the candidates with no introduction.

Each candidate is one `<article>`. The diagrams carry the weight and the prose stays sparse; a diagram that needs a paragraph gets redrawn.

- **Title**: names the deepening ("Collapse the Order intake pipeline").
- **Badges**: recommendation strength (`Strong` emerald, `Worth exploring` amber, `Speculative` slate) and dependency category from `codebase-design` (`in-process`, `local-substitutable`, `ports & adapters`, `mock`).
- **Files**: a monospaced list (`font-mono text-sm`).
- **Before / after diagram**: the centrepiece, two columns side by side.
- **Problem**: one sentence on what hurts.
- **Solution**: one sentence on what changes.
- **Wins**: bullets of at most six words naming the gain in glossary terms ("locality: bugs concentrate in one module", "leverage: one interface, N call sites", "tests hit one interface"); never "easier to maintain" or "cleaner code".
- **ADR callout**, when a candidate contradicts an ADR: one line in an amber-tinted box ("contradicts ADR-0007, but worth reopening because...").

End with a **Top recommendation** card: the candidate to tackle first, one sentence on why, and an anchor link to its card.

Vary the diagram patterns across candidates so the report does not look generic:

- **Mermaid flowchart or sequence** for graph-shaped structure (call flow, dependencies, "six round-trips before, one after"), inside a Tailwind card, with `classDef` colouring leakage edges red and the deep module dark.
- **Hand-built boxes and arrows** (divs plus absolutely positioned inline SVG) when Mermaid's layout fights you, such as one thick-bordered deep module with faded internals.
- **Cross-section**: stacked bands (`h-12 border-l-4`) for the layers a call passes through; many thin bands before, one thick labelled band after.
- **Mass diagram**: an interface rectangle beside an implementation rectangle; nearly equal before, short beside tall after.
- **Call-graph collapse**: nested call boxes before, one box with the calls faded inside after.

Style it editorial rather than dashboard: generous whitespace, optional `font-serif` headings, one accent (emerald or indigo) plus red for leakage and amber for warnings, diagrams about 320px tall so before and after sit side by side, and module labels in `text-xs uppercase tracking-wider` so they read as schematic.

## 3. Grill the pick

Walk the chosen candidate's decision tree with the `grilling` skill: constraints, dependencies, the shape of the deepened module, what sits behind the seam, which tests survive. Keep the domain model current with the `domain-modeling` skill as decisions land:

- A deepened module named after a concept missing from `GLOSSARY.md`, or a fuzzy term sharpened in conversation: update `GLOSSARY.md` there and then, creating it if needed.
- The user rejects the candidate for a reason a future review would need: offer an ADR ("Want me to record this as an ADR so future architecture reviews don't re-suggest it?"). Skip ephemeral reasons ("not worth it right now") and self-evident ones.
- Alternative interfaces for the deepened module: use the design-it-twice process in `codebase-design`.
