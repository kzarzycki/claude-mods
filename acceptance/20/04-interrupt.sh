#!/usr/bin/env bash
# Story: an interrupt before /run (the cwd lookup included), during it, during a host tool call or an
# agent spawn (succeeding or failing), or before a terminal response reports "interrupted", cancels
# the cell once it has one, and sends the cell no further reply.
exec bun plugins/code-mode/tests/interrupt.check.ts
