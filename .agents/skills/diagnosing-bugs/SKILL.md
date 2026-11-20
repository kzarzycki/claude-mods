---
name: diagnosing-bugs
description: Diagnosis loop for hard bugs and performance regressions. Use when the user says "diagnose" or "debug this", or reports something broken, throwing, failing or slow.
---

# Diagnosing Bugs

Work the phases in order; skip one only with a stated reason. Read `GLOSSARY.md` and the ADRs for the area when they exist.

Redact every secret in the commands, outputs and artifacts you show: write `<REDACTED>` in its place, pass credentials through environment variables so they never appear in the loop, and quote only the lines of a captured artifact that carry the signal, since artifacts carry auth headers. If the redacted output is not enough to diagnose, say so and ask the user.

## 1. Build a feedback loop

This is the skill. With a pass/fail signal that goes red on this bug, bisection, hypotheses and instrumentation just consume it; without one, reading code will not find the cause. Form no theory until the loop exists.

Reach for whatever gets there: a failing test at any seam that reaches the bug, a curl script against a dev server, a CLI run diffed against a known-good snapshot, a headless browser script, a replayed captured trace, a throwaway harness around the code path, a property or fuzz loop, a `git bisect run` harness, a differential run of old against new. Only when a human must trigger the bug, copy `scripts/hitl-loop.template.sh` and drive them through it; their observations come back as `KEY=VALUE` lines.

For a non-deterministic bug, aim for a higher reproduction rate rather than a clean repro: loop the trigger, parallelise, add stress, narrow timing windows until it fails often enough to debug.

The phase is done when you can name one command you have already run, shown with its redacted output, that:

- drives the real bug path and asserts the user's exact symptom, so it is red now and will be green once fixed;
- gives the same verdict every run, or a pinned high failure rate for a flaky bug;
- runs in seconds;
- runs unattended, with a human only through the HITL script.

If you cannot build one, stop and say so. List what you tried and ask for access to an environment that reproduces it, a redacted captured artifact (HAR file, log dump, core dump, timestamped screen recording), or permission to add temporary production instrumentation.

## 2. Reproduce and minimise

Confirm the loop shows the failure the user described, not a nearby one, and record the exact symptom (message, wrong output, timing) to check the fix against. Then cut inputs, callers, config, data and steps one at a time, rerunning after each cut, until removing any remaining element turns the loop green. The minimal repro narrows the hypotheses and becomes the regression test.

## 3. Hypothesise

Write 3-5 ranked hypotheses before testing any, so the first plausible idea does not anchor you. Each states a falsifiable prediction: "If X is the cause, changing Y makes the bug disappear." Show the ranked list to the user, who may re-rank it or rule some out, and carry on if they do not answer.

## 4. Instrument

Each probe tests one prediction; change one variable at a time. Prefer a debugger or REPL, then targeted logs at the boundaries that separate hypotheses. Tag every debug log with one unique prefix such as `[DEBUG-a4f2]` so cleanup is one grep. For a performance regression, measure a baseline and bisect instead of logging.

## 5. Fix with a regression test

Write the regression test before the fix, at a seam where it exercises the bug as it happens at the real call site; a seam too shallow to replicate the triggering chain gives false confidence. If no such seam exists, that is a finding: report it and suggest `/improve-codebase-architecture`. Otherwise turn the minimised repro into a failing test there, watch it fail (if you forced the red by mutating code or a fixture, `diff` against a pristine copy to prove the mutation landed before you trust it), fix, watch it pass, then rerun the Phase 1 loop on the original, un-minimised scenario.

## 6. Clean up

Before declaring done:

- the Phase 1 loop no longer reproduces the bug;
- the regression test passes, or the missing seam is documented;
- no `[DEBUG-` prefix is left in the tree;
- throwaway harnesses and prototypes are deleted, or moved to a clearly marked debug location;
- the commit or PR message states the hypothesis that proved correct.
