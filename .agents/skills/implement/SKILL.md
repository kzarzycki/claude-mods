---
name: implement
description: "Implement a piece of work from a spec or tickets, test-first, then review and commit it."
disable-model-invocation: true
---

Implement the work the user points to in the spec or tickets. Given a ticket reference, fetch it from the issue tracker and state its title before starting; ask if the reference is ambiguous.

- Build test-first with the `tdd` skill wherever it fits, at the seams the spec agreed.
- Typecheck and run the affected test files as you go; run the full suite once, at the end.
- Review the result with the `code-review` skill against the commit you started from, and address its findings.
- Commit to the current branch.
