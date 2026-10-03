#!/usr/bin/env bash
source "$(dirname "$0")/lib.sh"
T=$(mktemp -d)
E=(--plugin-dir "$PLUGINS/omc-eval")

claude_run "$T/cmd.jsonl" "/eval const xs = [1, 2, 3].map(n => n * n)
xs.reduce((a, b) => a + b)" "${E[@]}"
expect "/eval runs a cell and returns its value" "$T/cmd.jsonl" 'omc-eval: => 14'

claude_run "$T/tool.jsonl" "/eval (await tool.Read({ file_path: '$ROOT/.claude-plugin/marketplace.json' })).includes('omc-eval')" "${E[@]}"
expect "a cell calls a Claude Code tool" "$T/tool.jsonl" 'omc-eval: => true'

claude_run "$T/agent.jsonl" "Use the eval tool for all of this, one eval call per cell.
Cell 1: const secret = 'kiwi-' + (6 * 7)
Cell 2: secret
Cell 3: await Promise.all([completion('Reply with only the word PONG', { model: 'haiku' }), agent('Reply with only the word AGENTOK. Do not use tools.', { description: 'echo', model: 'sonnet' })])
Then reply with the three cell values." "${E[@]}" --allowedTools "mcp__omc-eval__eval"
expect "declarations persist across cells" "$T/agent.jsonl" '=> kiwi-42'
expect "completion() answers inside a cell" "$T/agent.jsonl" 'PONG'
expect "agent() returns the subagent's report" "$T/agent.jsonl" '=> \[\\n  \\"PONG\\",\\n  \\"AGENTOK'
finish
