#!/usr/bin/env bash
# Story: an interrupt before /run (the cwd lookup included), during it, during a host tool call, or
# before a terminal response reports "interrupted" and cancels the cell once it has one.
exec bun plugins/code-mode/tests/interrupt.check.ts
