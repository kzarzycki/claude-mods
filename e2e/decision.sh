#!/usr/bin/env bash
# cm-decision and the two mods that use it for harness decisions, cm-effort and cm-resume.
source "$(dirname "$0")/lib.sh"
T=$(mktemp -d)
D=(--plugin-dir "$PLUGINS/cm-decision" --plugin-dir "$PLUGINS/cm-effort" --plugin-dir "$PLUGINS/cm-resume")

claude_run "$T/ask.jsonl" "/decision ask Is this operation irreversible? -- DROP TABLE users; in production" "${D[@]}"
expect "/decision ask answers a yes/no question" "$T/ask.jsonl" 'noul\\":(0\.[5-9]|1)'

claude_run "$T/easy.jsonl" "/effort-rate fix the typo 'teh' in README.md line 3" "${D[@]}"
expect "an obvious fix rates low" "$T/easy.jsonl" 'effort: .*\\"choice\\":\\"low\\"'

claude_run "$T/hard.jsonl" "/effort-rate our websocket reconnect sometimes delivers messages twice after a deploy, only in prod" "${D[@]}"
expect "an open concurrency bug rates high or above" "$T/hard.jsonl" 'effort: .*\\"choice\\":\\"(high|xhigh)\\"'

# A turn that ends on a promise is judged an unexpected stop and resumed with a second turn. Runs
# in an empty folder with tools off, so the resumed turn has nothing to act on.
mkdir -p "$T/empty"
(cd "$T/empty" && claude_run "$T/stop.jsonl" "Reply with exactly this sentence and nothing else: Let me run the tests next." "${D[@]}" --disallowedTools "Bash,Write,Edit,Read,Glob,Grep,Agent")
expect "an unexpected stop is detected" "$T/stop.jsonl" 'stopped mid-promise; resuming'
if [ "$(grep -c '"type":"result"' "$T/stop.jsonl")" -ge 2 ]; then pass "a second turn ran"; else fail "no second turn in $T/stop.jsonl"; fi
finish
