#!/usr/bin/env bash
# Story: one kernel per machine, shared by sessions and subagents. The kernel self-check covers
# sessions and restarts; the e2e case covers a subagent's repl (model-led: SKIP and fail without a login).
set -e
bun plugins/code-mode/kernel/kernel.check.ts
E2E_CASES=shared bash e2e/repl.sh
