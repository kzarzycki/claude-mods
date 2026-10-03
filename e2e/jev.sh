#!/usr/bin/env bash
source "$(dirname "$0")/lib.sh"
T=$(mktemp -d)
J=(--plugin-dir "$PLUGINS/omc-jev")

claude_run "$T/easy.jsonl" "/jev ask fix the typo 'teh' in README.md line 3" "${J[@]}"
expect "an obvious fix rates low" "$T/easy.jsonl" 'effort: .*\\"choice\\":\\"low\\"'

claude_run "$T/hard.jsonl" "/jev ask our websocket reconnect sometimes delivers messages twice after a deploy, only in prod" "${J[@]}"
expect "an open concurrency bug rates high or above" "$T/hard.jsonl" 'effort: .*\\"choice\\":\\"(high|xhigh)\\"'

# A turn that ends on a promise is judged an unexpected stop and resumed with a second turn. Runs
# in an empty folder with tools off, so the resumed turn has nothing to act on.
mkdir -p "$T/empty"
(cd "$T/empty" && claude_run "$T/stop.jsonl" "Reply with exactly this sentence and nothing else: Let me run the tests next." "${J[@]}" --disallowedTools "Bash,Write,Edit,Read,Glob,Grep,Agent")
expect "an unexpected stop is detected" "$T/stop.jsonl" 'stopped mid-promise; resuming'
if [ "$(grep -c '"type":"result"' "$T/stop.jsonl")" -ge 2 ]; then pass "a second turn ran"; else fail "no second turn in $T/stop.jsonl"; fi
finish
