---
name: handoff
description: Write the current conversation into a handoff document for a fresh agent to pick up, in another session, harness or directory.
argument-hint: "What will the next session be used for?"
disable-model-invocation: true
---

Write a handoff document that lets a fresh agent continue the work, and save it in the OS temporary directory (`$TMPDIR`, else `/tmp`; `%TEMP%` on Windows), not the workspace.

- Treat any arguments as what the next session will focus on, and tailor the document to it.
- Include a "Suggested skills" section naming the skills the next agent should load.
- Point to specs, plans, ADRs, issues, commits and diffs by path or URL instead of copying them.
- Redact secrets and personal data.
