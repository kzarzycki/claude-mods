# Agent briefs

An agent brief is the comment posted when an issue or PR moves to `ready-for-agent`. It is the contract an AFK agent works from; the original body and discussion are only context. For an issue it describes the change to build. For a PR it describes what is left to do to the existing diff (finish it, close gaps, address review points), and "Current behavior" is the state of the diff.

- **Durable.** The issue may wait weeks while the code moves. Name the interfaces, types, function signatures, config shapes and behavioural contracts to look for; leave out file paths, line numbers and assumptions about the current structure.
- **Behavioural, not procedural.** Say what the system should do, not how to build it; the agent explores fresh and makes its own implementation decisions.
- **Testable.** Every criterion is concrete and verifiable on its own.
- **Bounded.** Say what is out of scope, so the agent doesn't gold-plate adjacent features.

```markdown
## Agent Brief

**Category:** bug / enhancement
**Summary:** one line on what needs to happen

**Current behavior:**
What happens now: the broken behaviour for a bug, the status quo for an
enhancement, the state of the diff for a PR.

**Desired behavior:**
What should happen once the work is done, including edge cases and error
conditions.

**Key interfaces:**
- `TypeName`: what changes and why
- `functionName()` return type: what it returns now vs what it should return
- Config shape: any new options

**Acceptance criteria:**
- [ ] Specific, testable criterion 1
- [ ] Specific, testable criterion 2

**Out of scope:**
- What not to change, including adjacent features that look related
```
