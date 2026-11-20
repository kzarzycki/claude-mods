# Logic Prototype

One self-contained HTML file that lets anyone drive a state model by clicking. It is for business logic, state transitions or data shape: things that look reasonable on paper and only feel wrong once pushed through real cases. It installs nothing, so it can go to a designer, PM or domain expert, and it speaks their language, not the code's.

## Build

- **The question first.** Open the page with a visible intro stating the state model and the question it explores, so whoever opens it later can check it answers the right one.
- **Logic as a portable module.** Put the logic in one `<script>` block as a pure module that could be lifted into the real codebase: a reducer `(state, action) => state`; an explicit state machine when which actions are legal is part of the question; pure functions over a plain data type; or a class when the logic genuinely owns ongoing state. Choose the shape that fits the question, not the one easiest to wire. It never touches the DOM: the page calls into it and nothing flows back.
- **One file.** Plain HTML, CSS and JS, all inline; no framework, bundler, server or install, so it opens by double-click and survives being emailed.
- **Domain language.** Every label, button and explanation reads like the business, not the reducer.
- **Layout**, top to bottom:
  1. Title and a one-line explanation of what the demo explores.
  2. Current state as a readable panel of labelled fields (not raw JSON), re-rendered after every click, calling out what just changed.
  3. Free-play buttons, one per action, always available.
  4. Guided walkthroughs, one scenario per tab: a plain-language description of the setup and what to watch for, then the ordered steps as real buttons that perform the action and advance. Starting a walkthrough resets to a known initial state. Cover the happy path, a tricky edge case, and an attempt at something that should be illegal.
- **Restrained styling.** Clean typography, generous spacing, one accent colour, no animations.

## Hand over

Send or open the file. The reactions that matter are "that shouldn't be possible" and "I assumed X would be different": those are bugs in the idea. Add actions or scenarios as they ask.

## Capture

As [SKILL.md](SKILL.md) describes: the validated module lifts into the real code; the whole file goes to the throwaway branch, where it stays runnable as one file. The HTML shell never reaches production.
