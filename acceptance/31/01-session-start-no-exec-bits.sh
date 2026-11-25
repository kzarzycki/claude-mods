#!/usr/bin/env bash
# Story: a code-mode copy whose hooks lost their exec bits still finds bun at session start: no "bun was
# not found" line, and bun's folder is exported to CLAUDE_ENV_FILE.
exec bun plugins/code-mode/tests/session-start.check.ts
