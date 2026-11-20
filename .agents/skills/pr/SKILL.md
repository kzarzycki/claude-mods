---
name: pr
description: "Write a PR body as a Summary visual of the change, before-and-after Evidence, and its Merge Danger. Use when writing a PR body."
metadata:
  credits:
    skill: show-me
    author: Dex Horthy
    organisation: Humanlayer
    url: "https://github.com/humanlayer/skills/blob/main/plugins/show-me/skills/show-me/SKILL.md"
---

Write the PR body in this template, with no preamble, brief prose, and the domain language of `GLOSSARY.md`. When the repo has a PR template, keep its headings and fit these sections under them, so the body has one shape:

```markdown
## Summary

<diagram, diff-sketch, or tree>

## Evidence

- **Before:** <screenshot/output/failing test run>
  **After:** <screenshot/output/passing test run>

## Merge Danger

**Door:** <one-way or two-way>

<optional: why>

**Blast Radius:** <one word>

<optional: potential ramifications of merge>
```

## Summary

Pick the smallest view that makes the key point: usually one, sometimes several, never all. Put each beside the short text it supports, and keep only the calls, files, props, states and boundaries that point needs.

- Pseudocode for logic or an algorithm.
- A call tree for runtime control flow.
- A component tree for UI structure, with the state and module boundaries that matter.
- A shallow file tree for file responsibilities or a broad refactor.
- Mermaid for component interaction, control flow or data flow.
- A `diff` block in one of those shapes when the point is what changes in a structure that already exists:

  ```diff
   submitForm
     createSession
       persistPrompt
  +    expandSkillMention
       launchAgent
  ```

- The whole block when most of it is new, when omitted context would hide ownership or order, or when the reader needs a copyable target shape.

## Evidence

Before and after. A screenshot is best for a visual change when the environment can take one. Otherwise use execution evidence, test results or console output, showing the test that failed before and passes now as pseudocode.

A video beats both when the change is something a user watches happen, such as a command's output, a flow across screens or a speed-up. The `demo` skill records one and posts it to the PR; name it here, or suggest one when the project's instructions call for it.

## Merge Danger

The door is two-way when the merge is cheap to walk back, one-way when it involves destructive or hard-to-reverse changes. The blast radius is everything the merge could affect, such as consumers, layout shift or mobile responsiveness. Name it in one word so it scans, and add the paragraph under it only when the ramifications need one.
