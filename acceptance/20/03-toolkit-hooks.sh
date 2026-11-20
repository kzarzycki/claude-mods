#!/usr/bin/env bash
# Story: the toolkit runs Claude Code's tools: a PreToolUse hook sees \$, file().text() and
# file().exists(), and a Read the hook blocks reaches the script as an error. No model call.
E2E_CASES="cmd toolkit" exec bash e2e/repl.sh
