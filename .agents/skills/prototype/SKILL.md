---
name: prototype
description: Build a throwaway prototype to answer a design question. Use when the user wants to sanity-check whether a state model or logic feels right, or explore what a UI should look like.
---

# Prototype

A prototype is throwaway code that answers one question, and the question decides its shape:

- **Does this logic or state model feel right?** → [LOGIC.md](LOGIC.md): one shareable HTML file a non-developer can drive, with free-play buttons and tabbed guided walkthroughs that push the model through cases hard to reason about on paper.
- **What should this look like?** → [UI.md](UI.md): several radically different variations on one route, switched by a `?variant=` URL param and a floating bottom bar.

The two artifacts share nothing, so settle which question it is from the prompt, the surrounding code, or the user. If it stays ambiguous and the user is not around, pick by the code it serves (a backend module → logic, a page or component → UI) and state that assumption at the top of the prototype.

## Rules for both

- **Marked as throwaway.** Put it next to the module or page it serves, named so a casual reader sees it is a prototype, within the project's existing routing and layout conventions.
- **Trivial to run.** A UI prototype starts with one command from the project's task runner; a logic prototype is a file you double-click.
- **In-memory state.** Persistence is something a prototype may be checking, not something it depends on. When the question is about storage, use a scratch database or local file with an obvious "PROTOTYPE, wipe me" name.
- **No polish.** No tests, no error handling beyond what keeps it runnable, no abstractions, nothing generalised past the one question.
- **Visible state.** Render the full relevant state after every action (logic) or on every variant switch (UI).
- **Capture it.** Once it has answered its question, fold the validated decision into the real code and record the verdict and the question it settled in the issue or a commit. Commit the prototype itself, as a primary source, to a throwaway `prototype/<name>` branch out of main, and link that branch from the implementation issue. Main keeps only the validated decision.
