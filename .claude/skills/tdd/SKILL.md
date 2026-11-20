---
name: tdd
description: Test-driven development in red-green vertical slices at agreed seams. Use when the user wants to build features or fix bugs test-first, mentions "red-green-refactor", or wants integration tests.
---

# Test-Driven Development

Build in red-green cycles that leave tests worth keeping. Read `GLOSSARY.md`, when it exists, so test names use the project's domain language, and respect the ADRs for the area.

## Seams

A seam is where a module's interface lives, the place a test observes behaviour through. Before writing any test, list the seams under test, each with a one-line note on what it catches and what it misses, and confirm them with the user; seams already agreed in the spec count. Write no test at an unconfirmed seam: agreeing them up front puts the testing effort on critical paths and complex logic instead of every edge case.

When the shape of the interface is itself in question (how deep the module is, where the seam belongs, what it exposes), consult the `codebase-design` skill for its vocabulary; it is a reference, not a session to run.

## The loop

- One seam, one failing test, then only enough code to pass it. No speculative features or anticipated tests.
- Slice vertically: each test responds to what the last cycle taught you. Writing all the tests first verifies imagined behaviour and fixes the test structure before you understand the implementation.
- Refactoring is not part of the loop; it belongs to review (the `code-review` skill).

## Tests worth keeping

- Test behaviour through the public interface, so the test survives any refactor that keeps behaviour. A test that breaks on such a refactor is coupled to the implementation: it mocks internal collaborators, tests private methods, or verifies through a side channel, such as querying the database instead of reading back through the interface.
- Take expected values from an independent source (a known literal, a worked example, the spec), never by recomputing them the way the code does; `expect(add(a, b)).toBe(a + b)` passes by construction.
- Mock only at system boundaries: external APIs, time and randomness, and a database or filesystem only when no local stand-in exists. Never mock your own modules. At a boundary, inject the dependency, and prefer one function per external operation over a generic fetcher, so each mock returns one shape with no conditional logic.
