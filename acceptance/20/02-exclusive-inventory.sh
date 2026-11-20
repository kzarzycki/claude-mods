#!/usr/bin/env bash
# Story: exclusive mode offers none of the nine hidden tools and offers repl; with a model, every model
# tool call is repl (no ToolSearch first) and scripts still reach the hidden tools.
# The model-led part prints SKIP and fails without a logged-in Claude Code.
E2E_CASES="inventory exclusive" exec bash e2e/repl.sh
