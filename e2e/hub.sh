#!/usr/bin/env bash
source "$(dirname "$0")/lib.sh"
T=$(mktemp -d)
# One interactive session: a resumed process starts with no subagents of its own. omc-eval spawns
# the subagent so the run doesn't depend on the model choosing to; the hub sees it like any other.
cd "$ROOT"
H=(--plugin-dir "$PLUGINS/omc-hub" --plugin-dir "$PLUGINS/omc-eval")
claude_tty "$T/1.log" 25 "/eval await agent('Reply with only the word HUBOK. Do not use tools.', { description: 'hub-probe', model: 'sonnet' })" "/hub list" -- "${H[@]}"
expect "the probe subagent ran" "$T/1.log" 'HUBOK'
# The captured terminal drops spaces and wraps long rows, so match loosely.
expect "/hub lists it with status, model, turns and tokens" "$T/1.log" 'omc-hub: ?[0-9a-f]+ *completed *claude-sonnet[^ ]* *1 *turns *[1-9][0-9]+'
expect "the row names the subagent" "$T/1.log" 'tok +general-purpose: ?hub-probe'
finish
