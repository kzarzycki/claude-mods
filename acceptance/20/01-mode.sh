#!/usr/bin/env bash
# Story: the mod loads and its repl tool and /repl command answer (the kit's own fixtures, no model).
set -e
claude plugin validate plugins/code-mode
claude plugin test plugins/code-mode
