---
name: context-extractor
description: Draft or extend a project's CLAUDE.md or AGENTS.md with the commands, conventions and gotchas an agent cannot infer, for any project type. Use on "extract conventions", "analyze project patterns", "generate CLAUDE.md", "what are the conventions", or /conventions.
---

# Context Extractor

Draft the project's agent instruction file: the one the repo already uses (`CLAUDE.md`
or `AGENTS.md`; when one symlinks to the other, edit the target), else `CLAUDE.md`. When
the repo compiles its agent files from sources, for example `.apm/instructions/` through
`mise run agent:sync`, propose the change to the source instead.

Survey whatever the project type offers (build, CI and lint config, sampled source and
tests, commit history, templates and branding, citation and frontmatter style, notebook
and data layout) and keep only what an agent would get wrong without being told.

## Content

- Imperative voice: "Run X before committing", not "The team prefers X".
- Commands (build, test, lint, run) come first and are mandatory for code projects.
- Conventions only where they differ from the language or framework default.
- Architecture only when the layout is not self-explanatory.
- Gotchas are the highest-value section: surprises, workarounds, things that look wrong
  but are intentional.
- 20–60 lines for most projects, up to 100 for complex ones.

Use these sections, dropping any that would be empty:

```markdown
## Project Overview
<!-- 1-2 sentences: what the project is and its primary purpose -->

## Commands

## Conventions

## Architecture

## Gotchas
```

## Approval

- No file yet: present the full draft.
- A file exists: propose additions only, each as its own diff the user can accept or
  reject. Never remove or rewrite existing content.
- Write nothing until the user approves.
