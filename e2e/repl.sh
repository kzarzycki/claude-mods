#!/usr/bin/env bash
source "$(dirname "$0")/lib.sh"
T=$(mktemp -d)
# an installed eval-kernel (the old name) would offer a second kernel to the model
E=(--plugin-dir "$PLUGINS/code-mode" --settings '{"enabledPlugins":{"eval-kernel@claude-mods":false}}')
ED=("${E[@]}" --plugin-dir "$PLUGINS/decision-model")

claude_run "$T/cmd.jsonl" "/repl const xs = [1, 2, 3].map(n => n * n)
xs.reduce((a, b) => a + b)" "${E[@]}"
expect "/repl runs a script and returns its value" "$T/cmd.jsonl" 'code-mode: => 14'

claude_run "$T/tool.jsonl" "/repl ({ read: (await file('$ROOT/.claude-plugin/marketplace.json').text()).includes('code-mode'), shell: \$\`echo shell-ok\`, grep: (await \$\`grep -c nothing-like-this /dev/null\`).note ? 'answer' : 'threw' })" "${E[@]}"
expect "file() reads through the Read tool" "$T/tool.jsonl" 'read: true'
expect "\$ runs through the Bash tool" "$T/tool.jsonl" 'shell: shell-ok'
expect "grep's exit 1 is an answer" "$T/tool.jsonl" 'grep: answer'

claude_run "$T/agent.jsonl" "Use the repl tool for all of this, one repl call per script.
Script 1: const fruit = 'kiwi-' + (6 * 7)
Script 2: fruit
Script 3: await Promise.all([completion('Reply with only the word PONG', { model: 'haiku' }), agent('Reply with only the word AGENTOK. Do not use tools.', { description: 'echo', model: 'sonnet' })])
Then reply with the three script values." "${E[@]}" --allowedTools "mcp__code-mode__repl"
expect "declarations persist across scripts" "$T/agent.jsonl" '=> kiwi-42'
expect "completion() answers inside a script" "$T/agent.jsonl" 'PONG'
expect "agent() returns the subagent's report" "$T/agent.jsonl" '=> \[\\n  \\"PONG\\",\\n  \\"AGENTOK'

# Five subagents in a row, each adding one word: agent() with a schema returns parsed JSON, judge()
# asks decision-model, and the subagents' hand-backs start no turns of the parent.
claude_run "$T/chain.jsonl" "/repl let s = 'The'
const words = []
for (let i = 0; i < 5; i++) { const r = await agent('Continue this sentence with exactly one more word so it stays sensible English: ' + JSON.stringify(s), { description: 'word ' + (i + 1), model: 'haiku', schema: { type: 'object', properties: { word: { type: 'string' } }, required: ['word'] } }); words.push(r.word); s += ' ' + r.word }
const sensible = await judge({ type: 'noul', instructions: 'Is this a sensible start of an English sentence?' }, s)
({ s, oneWordEach: words.length === 5 && words.every(w => /^[A-Za-z'-]+$/.test(w)), judged: sensible.type })" "${ED[@]}"
expect "agent() with a schema returns one parsed word each" "$T/chain.jsonl" 'oneWordEach: true'
expect "judge() answers through decision-model" "$T/chain.jsonl" 'judged: noul'
extra=$(grep '"type":"result"' "$T/chain.jsonl" | grep -v -c -e 'code-mode: =>' -e 'Prompt dropped by a hook: code-mode')
if [ "$extra" = 0 ]; then pass "the hand-backs start no turns of the parent"; else fail "$extra extra turns in $T/chain.jsonl"; fi

# Code does the mechanical work (100 Reads, exact means), one agent reads only the outlier, and code
# checks its answer against what it already knows.
mkdir -p "$T/synth"
claude_run "$T/synth.jsonl" "/repl const dir = '$T/synth'
const hot = Math.floor(Math.random() * 100), hidden = 'zebra-' + Math.random().toString(36).slice(2, 6)
for (let i = 0; i < 100; i++) await Bun.write(dir + '/f' + i + '.txt', Array.from({ length: 50 }, () => i === hot ? 900 + Math.random() * 99 | 0 : Math.random() * 100 | 0).join('\n') + (i === hot ? '\nnote: ' + hidden : ''))
const means = []
for (let i = 0; i < 100; i++) { const nums = (await file(dir + '/f' + i + '.txt').lines()).map(Number).filter(n => !isNaN(n)); means.push(nums.reduce((a, b) => a + b) / nums.length) }
const outlier = means.indexOf(Math.max(...means))
const r = await agent('Read ' + dir + '/f' + outlier + '.txt and report the word after \"note:\".', { description: 'outlier', model: 'haiku', schema: { type: 'object', properties: { word: { type: 'string' } }, required: ['word'] } })
({ foundOutlier: outlier === hot, agentCorrect: r.word === hidden })" "${E[@]}"
expect "code finds the outlier over 100 tool reads" "$T/synth.jsonl" 'foundOutlier: true'
expect "the one agent's typed answer checks out" "$T/synth.jsonl" 'agentCorrect: true'

# Exclusive mode: the built-ins are denied, so repl is the model's way to work, and its scripts
# still reach Bash and Read (a deny rule stops only the model).
lines=$(wc -l < "$ROOT/.claude-plugin/marketplace.json" | tr -d ' ')
claude_run "$T/excl.jsonl" "How many lines does $ROOT/.claude-plugin/marketplace.json have, and what does \`uname -s\` print? Reply as: LINES=<n> OS=<name>" "${E[@]}" \
  --disallowedTools Bash Read Edit Write Glob Grep NotebookEdit WebFetch WebSearch --allowedTools "mcp__code-mode__repl"
expect "exclusive mode: the model works through repl" "$T/excl.jsonl" '"name":"mcp__code-mode__repl"'
# Task, Skill, ToolSearch and MCP tools stay offered by design (see the README's exclusive mode).
offered=$(jq -r 'select(.type == "system" and .subtype == "init") | .tools[]' "$T/excl.jsonl" | grep -xE 'Bash|Read|Edit|Write|Glob|Grep|NotebookEdit|WebFetch|WebSearch' | tr '\n' ' ')
if [ -z "$offered" ] && grep -q '"subtype":"init"' "$T/excl.jsonl"; then pass "exclusive mode: no denied tool is offered"; else fail "exclusive mode: offered $offered"; fi
others=$(jq -r 'select(.type == "assistant") | .message.content[]? | select(.type == "tool_use") | .name' "$T/excl.jsonl" | grep -vx 'mcp__code-mode__repl' | sort -u | tr '\n' ' ')
if [ -z "$others" ]; then pass "exclusive mode: every model tool call is repl"; else fail "exclusive mode: the model also called $others"; fi
expect "exclusive mode: scripts still reach the denied tools" "$T/excl.jsonl" "LINES=$lines OS=$(uname -s)"
# The guide reaches the model: it reads files and runs commands through the globals, not Node's
# child_process or fs, which go around Claude Code.
expect_not "exclusive mode: the model uses the globals, not child_process or fs" "$T/excl.jsonl" "child_process|node:fs|readFileSync|execSync"

# Shared kernel: a subagent started from a script runs its repl scripts in the same kernel, so it
# reads the parent's variable and the parent reads the one it makes.
claude_run "$T/shared.jsonl" "/repl const handoffWord = 'mango-' + (Math.random() * 1e4 | 0)
const r = await agent('Call the repl tool with the code handoffWord and reply with only the value it returns. Then call the repl tool with the code: globalThis.madeBySub = 6 * 7', { description: 'shared', model: 'sonnet' })
({ subSaw: String(r).includes(handoffWord), parentSees: globalThis.madeBySub })" "${E[@]}" --allowedTools "mcp__code-mode__repl"
expect "the subagent calls the repl tool" "$T/shared.jsonl" '"name":"mcp__code-mode__repl"'
expect "a subagent's repl sees the parent's variables" "$T/shared.jsonl" 'code-mode: => .*subSaw: true'
expect "the parent sees what the subagent's repl made" "$T/shared.jsonl" 'code-mode: => .*parentSees: 42'

# Long scripts: a script past the host's ~30 s fetch limit still finishes.
claude_run "$T/long.jsonl" "/repl await sleep(45000)
'slept-45s'" "${E[@]}"
expect "a 45 s script finishes" "$T/long.jsonl" 'code-mode: => slept-45s'
finish
