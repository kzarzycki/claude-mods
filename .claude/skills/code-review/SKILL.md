---
name: code-review
description: "Review the changes since a fixed point (commit, branch, tag, or merge-base) on two separate axes, the repo's coding standards and the originating spec, reported side by side. Use when the user wants to review a branch, a PR, work-in-progress changes, or asks to \"review since X\"."
---

# Code Review

Review the diff from a fixed point to the current work on two axes, each in its own fresh-context sub-agent so neither colours the other, run in parallel (a later pass's delta is the exception, step 4):

- **Standards**: does the code follow this repo's documented coding standards?
- **Spec**: does it do what the originating issue or spec asked?

A change can pass one and fail the other (the right thing built against convention, or the wrong thing built well), so the axes stay separate from review to report.

`docs/agents/issue-tracker.md` names the tracker's realization file (for GitHub, the `engineering-loop` skill's `github.md`). If it is missing, tell the user to create it: the project template writes one.

## 1. Pin the diff

The fixed point is whatever the user named (SHA, branch, tag, `main`, `HEAD~5`); ask if they named none. Check that it resolves (`git rev-parse <fixed-point>`) and that the diff is non-empty before starting either reviewer.

- Diff: `git diff $(git merge-base <fixed-point> HEAD)`, against the merge-base and including uncommitted work. Untracked files are not in it; add those listed by `git ls-files --others --exclude-standard`.
- Commits: `git log <fixed-point>..HEAD --oneline`.

## 2. Find the spec

In order: issue references in the commit messages (`#123`, `Closes #45`, GitLab `!67`), fetched per the tracker's realization file; a path the user passed; a spec file under `docs/`, `specs/` or `.scratch/` matching the branch or feature; otherwise ask the user. If there is none, skip the Spec axis and say so in the report.

## 3. Find the standards

Search the repo for every file that documents how code should be written; `CODING_STANDARDS.md` and `CONTRIBUTING.md` are always on the list when they exist. On top of that, the Standards axis always applies this baseline of Fowler smells (*Refactoring*, ch. 3):

> Mysterious Name, Duplicated Code, Feature Envy, Data Clumps, Primitive Obsession, Repeated Switches, Shotgun Surgery, Divergent Change, Speculative Generality (anything the spec doesn't need), Message Chains, Middle Man, Refused Bequest.

A documented repo standard overrides the baseline. A smell is always a labelled judgement call with its fix ("possible Feature Envy: move the method onto the data it uses"), never a hard violation. Skip anything tooling already enforces.

## 4. Run both reviewers in parallel

Each gets the diff command, any untracked files, the commit list and the path of this file, and reads its own axis here: step 3 and its bullet below for Standards, its bullet below for Spec; it reviews that axis only and starts no reviewers of its own. A paraphrased brief drops the smell baseline and the report rules, so point to the text rather than summarise it. Each also gets:

- **Standards**: the standards files. Brief: report per file or hunk (a) each breach of a documented standard, citing the file and rule, and (b) each baseline smell, named, with the hunk quoted. Mark documented-standard breaches as hard violations or judgement calls; smells are always judgement calls. Skip what tooling enforces. Under 400 words.
- **Spec**: the spec's path or fetched contents. Brief: report (a) requirements missing or partial, (b) behaviour nobody asked for, (c) requirements that look implemented but wrong, quoting the spec line for each. Under 400 words.

A delta that an earlier fresh-context review of the same change already covered (a later pass) is the exception: review both axes yourself, one after the other, finishing each section before reading for the next, since two sub-agents rereading the repo for a few hunks cost more than their separation buys.

## 5. Report

Show the two reports under `## Standards` and `## Spec`, verbatim or lightly cleaned, without merging or reranking findings. End with one line: the finding count per axis and the worst finding within each axis, never one winner across both.
