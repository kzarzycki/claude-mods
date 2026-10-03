#!/usr/bin/env bash
source "$(dirname "$0")/lib.sh"
T=$(mktemp -d)
E=(--plugin-dir "$PLUGINS/eval-kernel")
ED=("${E[@]}" --plugin-dir "$PLUGINS/decision-model")

claude_run "$T/cmd.jsonl" "/eval const xs = [1, 2, 3].map(n => n * n)
xs.reduce((a, b) => a + b)" "${E[@]}"
expect "/eval runs a cell and returns its value" "$T/cmd.jsonl" 'eval-kernel: => 14'

claude_run "$T/tool.jsonl" "/eval (await tool.Read({ file_path: '$ROOT/.claude-plugin/marketplace.json' })).includes('eval-kernel')" "${E[@]}"
expect "a cell calls a Claude Code tool" "$T/tool.jsonl" 'eval-kernel: => true'

claude_run "$T/agent.jsonl" "Use the eval tool for all of this, one eval call per cell.
Cell 1: const secret = 'kiwi-' + (6 * 7)
Cell 2: secret
Cell 3: await Promise.all([completion('Reply with only the word PONG', { model: 'haiku' }), agent('Reply with only the word AGENTOK. Do not use tools.', { description: 'echo', model: 'sonnet' })])
Then reply with the three cell values." "${E[@]}" --allowedTools "mcp__eval-kernel__eval"
expect "declarations persist across cells" "$T/agent.jsonl" '=> kiwi-42'
expect "completion() answers inside a cell" "$T/agent.jsonl" 'PONG'
expect "agent() returns the subagent's report" "$T/agent.jsonl" '=> \[\\n  \\"PONG\\",\\n  \\"AGENTOK'

# Five subagents in a row, each adding one word: agent() with a schema returns parsed JSON, judge()
# asks decision-model, and the subagents' hand-backs start no turns of the parent.
claude_run "$T/chain.jsonl" "/eval let s = 'The'
const words = []
for (let i = 0; i < 5; i++) { const r = await agent('Continue this sentence with exactly one more word so it stays sensible English: ' + JSON.stringify(s), { description: 'word ' + (i + 1), model: 'haiku', schema: { type: 'object', properties: { word: { type: 'string' } }, required: ['word'] } }); words.push(r.word); s += ' ' + r.word }
const sensible = await judge({ type: 'noul', instructions: 'Is this a sensible start of an English sentence?' }, s)
({ s, oneWordEach: words.length === 5 && words.every(w => /^[A-Za-z'-]+$/.test(w)), judged: sensible.type })" "${ED[@]}"
expect "agent() with a schema returns one parsed word each" "$T/chain.jsonl" 'oneWordEach\\": true'
expect "judge() answers through decision-model" "$T/chain.jsonl" 'judged\\": \\"noul'
extra=$(grep '"type":"result"' "$T/chain.jsonl" | grep -v -c -e 'eval-kernel: =>' -e 'Prompt dropped by a hook: eval-kernel')
if [ "$extra" = 0 ]; then pass "the hand-backs start no turns of the parent"; else fail "$extra extra turns in $T/chain.jsonl"; fi

# Code does the mechanical work (100 Reads, exact means), one agent reads only the outlier, and code
# checks its answer against what it already knows.
mkdir -p "$T/synth"
claude_run "$T/synth.jsonl" "/eval const dir = '$T/synth'
const hot = Math.floor(Math.random() * 100), secret = 'zebra-' + Math.random().toString(36).slice(2, 6)
for (let i = 0; i < 100; i++) await Bun.write(dir + '/f' + i + '.txt', Array.from({ length: 50 }, () => i === hot ? 900 + Math.random() * 99 | 0 : Math.random() * 100 | 0).join('\n') + (i === hot ? '\nnote: ' + secret : ''))
const means = []
for (let i = 0; i < 100; i++) { const nums = (await tool.Read({ file_path: dir + '/f' + i + '.txt' })).split('\n').map(l => +l.split('\t')[1]).filter(n => !isNaN(n)); means.push(nums.reduce((a, b) => a + b) / nums.length) }
const outlier = means.indexOf(Math.max(...means))
const r = await agent('Read ' + dir + '/f' + outlier + '.txt and report the word after \"note:\".', { description: 'outlier', model: 'haiku', schema: { type: 'object', properties: { word: { type: 'string' } }, required: ['word'] } })
({ foundOutlier: outlier === hot, agentCorrect: r.word === secret })" "${E[@]}"
expect "code finds the outlier over 100 tool reads" "$T/synth.jsonl" 'foundOutlier\\": true'
expect "the one agent's typed answer checks out" "$T/synth.jsonl" 'agentCorrect\\": true'
finish
