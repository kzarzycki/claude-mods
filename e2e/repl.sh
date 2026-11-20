#!/usr/bin/env bash
# The code-mode e2e. E2E_CASES="toolkit shared" runs only those cases; acceptance/20/ uses that.
source "$(dirname "$0")/lib.sh"
T=$(mktemp -d)
# an installed eval-kernel (the old name) would offer a second kernel to the model
OFF='"enabledPlugins":{"eval-kernel@claude-mods":false}'
E=(--plugin-dir "$PLUGINS/code-mode" --settings "{$OFF}")
ED=("${E[@]}" --plugin-dir "$PLUGINS/decision-model")
# Exclusive mode hides these nine (spec #20, story 1); Agent, Skill, ToolSearch, Workflow and MCP tools stay.
HIDDEN=(Bash Read Edit Write Glob Grep NotebookEdit WebFetch WebSearch)

if want cmd; then
  claude_run "$T/cmd.jsonl" "/repl const xs = [1, 2, 3].map(n => n * n)
xs.reduce((a, b) => a + b)" "${E[@]}"
  expect "/repl runs a script and returns its value" "$T/cmd.jsonl" 'code-mode: => 14'
fi

# The toolkit runs Claude Code's tools: a PreToolUse hook sees every shell and file call, exists()
# included, and a Read the hook blocks reaches the script as an error.
if want toolkit; then
  mkdir -p "$T/hk"; echo alpha > "$T/hk/a.txt"; echo secret > "$T/hk/blocked.txt"
  cat > "$T/hook.sh" <<HOOK
#!/usr/bin/env bash
in=\$(cat)
echo "\$in" | jq -c '{tool: .tool_name, input: .tool_input}' >> "$T/hook.log"
if [ "\$(echo "\$in" | jq -r .tool_name)" = Read ] && echo "\$in" | jq -r .tool_input.file_path | grep -q blocked.txt; then echo "blocked by the e2e hook" >&2; exit 2; fi
exit 0
HOOK
  hooks='"hooks":{"PreToolUse":[{"matcher":"Bash|Read","hooks":[{"type":"command","command":"bash '"$T"'/hook.sh"}]}]}'
  claude_run "$T/tool.jsonl" "/repl const d = '$T/hk'
({ read: (await file(d + '/a.txt').text()).trim(), yes: await file(d + '/a.txt').exists(), no: await file(d + '/none.txt').exists(), shell: (await \$\`echo via-bash\`).stdout.trim(), grep: (await \$\`grep -c nothing-like-this /dev/null\`).note ? 'answer' : 'threw', blocked: await file(d + '/blocked.txt').text().then(() => 'read', () => 'refused') })" --plugin-dir "$PLUGINS/code-mode" --settings "{$OFF,$hooks}"
  expect "file() reads through the Read tool" "$T/tool.jsonl" 'code-mode: => .*read: alpha'
  expect "file().exists() answers true and false" "$T/tool.jsonl" 'yes: true.*no: false'
  expect "\$ runs through the Bash tool" "$T/tool.jsonl" 'shell: via-bash'
  expect "grep's exit 1 is an answer" "$T/tool.jsonl" 'grep: answer'
  expect "a Read the hook blocks reaches the script as an error" "$T/tool.jsonl" 'blocked: refused'
  touch "$T/hook.log"
  expect "the hook sees the script's Read" "$T/hook.log" '"tool":"Read".*hk/a.txt'
  expect "the hook sees exists() as a Bash call" "$T/hook.log" '"tool":"Bash".*test -e.*hk/none.txt'
  expect "the hook sees the script's shell command" "$T/hook.log" '"tool":"Bash".*echo via-bash'
  expect "the hook sees the blocked Read" "$T/hook.log" '"tool":"Read".*hk/blocked.txt'
fi

if want agent && model "agent()"; then
  claude_run "$T/agent.jsonl" "Use the repl tool for all of this, one repl call per script.
Script 1: const fruit = 'kiwi-' + (6 * 7)
Script 2: fruit
Script 3: await Promise.all([completion('Reply with only the word PONG', { model: 'haiku' }), agent('Reply with only the word AGENTOK. Do not use tools.', { description: 'echo', model: 'sonnet' })])
Then reply with the three script values." "${E[@]}" --allowedTools "mcp__code-mode__repl"
  expect "declarations persist across scripts" "$T/agent.jsonl" '=> kiwi-42'
  expect "completion() answers inside a script" "$T/agent.jsonl" 'PONG'
  expect "agent() returns the subagent's report" "$T/agent.jsonl" '=> \[\\n  \\"PONG\\",\\n  \\"AGENTOK'
fi

# Five subagents in a row, each adding one word: agent() with a schema returns parsed JSON, judge()
# asks decision-model, and the subagents' hand-backs start no turns of the parent.
if want chain && model "agent() chain"; then
  claude_run "$T/chain.jsonl" "/repl let s = 'The'
  const words = []
  for (let i = 0; i < 5; i++) { const r = await agent('Continue this sentence with exactly one more word so it stays sensible English: ' + JSON.stringify(s), { description: 'word ' + (i + 1), model: 'haiku', schema: { type: 'object', properties: { word: { type: 'string' } }, required: ['word'] } }); words.push(r.word); s += ' ' + r.word }
  const sensible = await judge({ type: 'noul', instructions: 'Is this a sensible start of an English sentence?' }, s)
  ({ s, oneWordEach: words.length === 5 && words.every(w => /^[A-Za-z'-]+$/.test(w)), judged: sensible.type })" "${ED[@]}"
  expect "agent() with a schema returns one parsed word each" "$T/chain.jsonl" 'oneWordEach: true'
  expect "judge() answers through decision-model" "$T/chain.jsonl" 'judged: noul'
  extra=$(grep '"type":"result"' "$T/chain.jsonl" | grep -v -c -e 'code-mode: =>' -e 'Prompt dropped by a hook: code-mode')
  if [ "$extra" = 0 ]; then pass "the hand-backs start no turns of the parent"; else fail "$extra extra turns in $T/chain.jsonl"; fi
fi

# Code does the mechanical work (100 Reads, exact means), one agent reads only the outlier, and code
# checks its answer against what it already knows.
if want synth && model "agent() synthesis"; then
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
fi

# Exclusive mode's inventory, before any model call: none of the hidden tools is offered, repl is.
if want inventory; then
  claude_run "$T/inv.jsonl" "/repl 1 + 1" "${E[@]}" --disallowedTools "${HIDDEN[@]}"
  offered=$(jq -r 'select(.type == "system" and .subtype == "init") | .tools[]' "$T/inv.jsonl" 2>/dev/null)
  if [ -z "$offered" ]; then fail "exclusive inventory: no init event in $T/inv.jsonl"
  else
    leaked=$(grep -xE "$(IFS='|'; echo "${HIDDEN[*]}")" <<< "$offered" | tr '\n' ' ')
    if [ -z "$leaked" ]; then pass "exclusive inventory: none of the nine hidden tools is offered"; else fail "exclusive inventory: offered $leaked"; fi
    if grep -qx mcp__code-mode__repl <<< "$offered"; then pass "exclusive inventory: repl is offered"; else fail "exclusive inventory: no repl in $T/inv.jsonl"; fi
  fi
fi

# Exclusive mode with a model: it works through repl alone, reaching repl without ToolSearch, and its
# scripts still reach the hidden tools (a deny rule stops only the model).
if want exclusive && model "exclusive mode"; then
  lines=$(wc -l < "$ROOT/.claude-plugin/marketplace.json" | tr -d ' ')
  claude_run "$T/excl.jsonl" "How many lines does $ROOT/.claude-plugin/marketplace.json have, and what does \`uname -s\` print? Reply as: LINES=<n> OS=<name>" "${E[@]}" \
    --disallowedTools "${HIDDEN[@]}" --allowedTools "mcp__code-mode__repl"
  called=$(jq -r 'select(.type == "assistant") | .message.content[]? | select(.type == "tool_use") | .name' "$T/excl.jsonl" 2>/dev/null)
  others=$(grep -vx 'mcp__code-mode__repl' <<< "$called" | sort -u | tr '\n' ' ')
  if [ -z "$called" ]; then fail "exclusive mode: the model made no tool call (see $T/excl.jsonl)"
  elif [ -n "$others" ]; then fail "exclusive mode: the model also called $others"
  else pass "exclusive mode: every model tool call is repl, ToolSearch never needed"; fi
  expect "exclusive mode: scripts still reach the hidden tools" "$T/excl.jsonl" "LINES=$lines OS=$(uname -s)"
  # The guide reaches the model: it reads files and runs commands through the globals, not Node's
  # child_process or fs, which go around Claude Code.
  expect_not "exclusive mode: the model uses the globals, not child_process or fs" "$T/excl.jsonl" "child_process|node:fs|readFileSync|execSync"
fi

# Shared kernel: a subagent started from a script runs its repl scripts in the same kernel, so it
# reads the parent's variable and the parent reads the one it makes.
if want shared && model "shared kernel"; then
  claude_run "$T/shared.jsonl" "/repl const handoffWord = 'mango-' + (Math.random() * 1e4 | 0)
const r = await agent('Call the repl tool with the code handoffWord and reply with only the value it returns. Then call the repl tool with the code: globalThis.madeBySub = 6 * 7', { description: 'shared', model: 'sonnet' })
({ subSaw: String(r).includes(handoffWord), parentSees: globalThis.madeBySub })" "${E[@]}" --allowedTools "mcp__code-mode__repl"
  expect "the subagent calls the repl tool" "$T/shared.jsonl" '"name":"mcp__code-mode__repl"'
  expect "a subagent's repl sees the parent's variables" "$T/shared.jsonl" 'code-mode: => .*subSaw: true'
  expect "the parent sees what the subagent's repl made" "$T/shared.jsonl" 'code-mode: => .*parentSees: 42'
fi

# Long scripts: a script past the host's ~30 s fetch limit still finishes.
if want long; then
  claude_run "$T/long.jsonl" "/repl await sleep(45000)
'slept-45s'" "${E[@]}"
  expect "a 45 s script finishes" "$T/long.jsonl" 'code-mode: => slept-45s'
fi
finish
