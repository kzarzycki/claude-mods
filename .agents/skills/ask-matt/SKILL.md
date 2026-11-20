---
name: ask-matt
description: Router over this package's skills. Use when the user asks which skill or flow fits their situation, or what to do at a phase boundary.
disable-model-invocation: true
---

# Ask Matt

Answer from this map which skill or flow fits the user's situation. A **flow** is a path through the skills: most work runs along the main flow, on-ramps merge onto it, and the rest is standalone or vocabulary underneath.

The summaries here are for orientation: read a skill's `SKILL.md` before stating what it does or recommending that a step be skipped.

## Main flow: idea to ship

1. **`/grill-with-docs`** sharpens the idea by interview and records what it learns in `GLOSSARY.md` and ADRs. Use it whenever there is a repo to write into; without one, use `/grilling`.
2. **A question that needs a runnable answer** (state, business logic, a UI you have to see) detours through **`/prototype`**. The prototype lives in its own directory, so bridge with **`/handoff`** out to a fresh session and `/handoff` back, then reference what was learned from the idea thread.
3. **Multi-session build**: **`/to-spec`**, then **`/to-tickets`** for tracer-bullet tickets with blocking edges (one file per ticket under `.scratch/<feature>/issues/` on a local tracker, native blocking links on a real one). Then either **`/implement`** per ticket, clearing context between tickets since each is self-contained, or **`/implement-spec`** to run the whole ticket graph from one coordinator, with parallel implementers in worktrees landing on one integration branch. **Single-session build**: `/implement` in the same context.
4. **`/retro`** closes the loop after a build, especially one that went sideways: it reviews the session for changes to the agent's environment rather than the code (checks, coding standards, steering files, tooling). Run it in the session it looks back on, before clearing; afterwards, point it at that session's log.

`/implement` builds with **`/tdd`** at agreed seams and closes with **`/code-review`** (Standards and Spec axes); `/implement-spec`'s implementers each drive `/tdd`, and it runs one `/code-review` over the integration branch. Both stand alone too: `/tdd` for one behaviour test-first without a spec, `/code-review` for any branch or PR against a fixed point. **`/pr`** writes the PR body.

Keep steps 1 to 3 in one unbroken context window so the grilling, spec and tickets build on the same reasoning; each `/implement` then starts fresh from its ticket. If the session nears the edge of the [smart zone](https://www.aihero.dev/ai-coding-dictionary/smart-zone) (~150k tokens, where the model still reasons sharply) before `/to-tickets`, compact at the nearest phase boundary.

## On-ramps

- **Raw bugs and requests piling up** → **`/triage`** turns them into agent-ready issues for `/implement`. Only for issues that arrive from outside; `/to-tickets` output is already agent-ready.
- **A bug that resists a first look** (an intermittent flake, a regression between two known-good states) → **`/diagnosing-bugs`**. It builds one command that goes red on this bug before theorising, then fixes with a regression test. Once the fix is in, run `/retro` in the same session to ask what would have prevented the bug; when the finding is that no correct seam exists to lock it down, take it to `/improve-codebase-architecture`.
- **An effort too big and foggy for one session** (greenfield, a huge feature) → **`/wayfinder`** charts a map of decision tickets on the tracker and resolves them one at a time. It produces decisions, not deliverables, and is slow and dense, so never use it for a well-scoped feature. When the map clears, merge at `/to-spec`, which collapses the linked decisions into a buildable plan; go straight to `/implement` only if the effort turned out small.

## Codebase health

- **`/improve-codebase-architecture`** surveys for deepening opportunities when there is spare time. A picked candidate becomes an idea for `/grill-with-docs`, and is designed with `/codebase-design`.

## Vocabulary underneath

Model-invoked references that other skills pull in. Call one directly when the words, not the process, are the problem.

- **`/domain-modeling`**: the project's domain language: fuzzy or overloaded terms, `GLOSSARY.md`, ADRs for hard-to-reverse decisions.
- **`/codebase-design`**: the deep-module vocabulary (module, interface, depth, seam, adapter, leverage, locality) that `/tdd` and `/improve-codebase-architecture` speak.

## Standalone

- **`/grilling`**: the bare interview primitive, which saves nothing. Use it for a plan, design or piece of writing with no repo under it. `/grill-with-docs`, `/triage`, `/wayfinder` and `/improve-codebase-architecture` run it internally.
- **`/prototype`**: throwaway code that answers one design question. The validated decision folds into the real code; the prototype stays on a throwaway branch as a primary source.
- **`/research`**: a background agent reads primary sources and leaves a cited Markdown file in the repo. Feed it into `/grill-with-docs`.
- **`/wizard`**: an interactive bash script for steps only a human can take (credentials, CI secrets, an unfamiliar dashboard, a one-off cutover). Not for anything the agent can do itself.
- **`/wait-what`**: re-pitch a message that did not land. `/grill-with-docs` prevents the problem by agreeing a shared language early.
- **`/teach`**: learn a topic over several sessions in a stateful workspace.
- **`/loop-me`**: grill out specs for recurring workflows to delegate.
- **`/claude-handoff`**: hand the conversation to a fresh Claude Code background agent.
- **`/audit-third-party-software`**: audit third-party code before installing it.
- **`/demo`**: record a visible change running and post the video to its PR. `/pr` names it in the Evidence.
- **`/context-extractor`**: extract a project's conventions into a `CLAUDE.md`.
- **`/orchestrating-agents`**: start, message, watch and collect agents through one backend (native, Omnigent, herdr-link).
- **`/operating-omnigent`**: operate a local Omnigent install and its raw `sys_*` tools.

## Phase boundaries

A **phase** is a chunk of work that ends when you think "done with that": the grilling, the implementation, the QA. Choose how to move on only at a boundary; mid-phase, continue or hand the rest to subagents, because compacting mid-phase loses the thread. Take the first yes:

1. **Continue** if the next phase needs this one as a primary source (implementation wants the grilling's reasoning verbatim) or still fits in the smart zone. It costs nothing and loses nothing, so rule it out first.
2. **`/clear`** if nothing here matters to what comes next. Clearing relevant context loses the why behind what was built, and the diff will not give it back. The cleared session stays resumable.
3. **`/handoff`** only when the work travels: a new harness, a new directory or repo, a colleague, or a side task forked mid-phase.
4. **Subagent** when the task is scoped tightly enough to run unsteered, such as automated review; this session stays untouched.
5. **`/compact`** otherwise, with an instruction naming the next phase (`/compact we're going to QA this area`). It is the default but comes last: every move except Continue swaps the session for a lossy summary, and a session that starts from one can be confidently wrong about a decision the summary flattened.

These are judgement calls; the value is asking them in order.

## Precondition

**`docs/agents/issue-tracker.md`**: names the issue tracker's realization file the other skills follow (for GitHub, the `engineering-loop` skill's `github.md`), plus the project's components. The project template writes it. Custom trackers work too.
