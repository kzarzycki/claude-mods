#!/usr/bin/env bash
# self-compact: the model's own compact_after_turn call, and the nudge after a finished task.
# Thresholds are set to 1% through --settings so a short session counts as full.
source "$(dirname "$0")/lib.sh"
T=$(mktemp -d); mkdir -p "$T/empty"; cd "$T/empty"
OPTS='{"pluginConfigs":{"self-compact@inline":{"options":{"threshold":1,"toolFloor":1}}}}'
S=(--plugin-dir "$PLUGINS/self-compact" --settings "$OPTS" --allowedTools "mcp__self-compact__compact_after_turn" --disallowedTools "Bash,Write,Edit,Read,Glob,Grep,Agent")

claude_run "$T/tool.jsonl" "Call the compact_after_turn tool with focus 'the word banana', then reply with the single word done." "${S[@]}" --settings '{"pluginConfigs":{"self-compact@inline":{"options":{"threshold":1,"toolFloor":1,"nudge":false}}}}'
expect "the model's tool call compacts after its turn" "$T/tool.jsonl" '"subtype":"compact_boundary"'

claude_run "$T/nudge.jsonl" "Reply with exactly this and nothing else: The task is complete and nothing is left to do." "${S[@]}" --plugin-dir "$PLUGINS/decision-model"
expect "a finished task in a full context gets a nudge" "$T/nudge.jsonl" 'self-compact: asking the model whether to compact'
expect "the model answers the nudge by compacting" "$T/nudge.jsonl" '"subtype":"compact_boundary"'
n=$(grep -c '"subtype":"compact_boundary"' "$T/nudge.jsonl")
if [ "$n" = 1 ]; then pass "it compacts once"; else fail "$n compactions in $T/nudge.jsonl"; fi
# With resume-on-stop loaded too, the nudge's reply must not read as a stop to resume.
claude_run "$T/both.jsonl" "Reply with exactly this and nothing else: All done, the task is finished." "${S[@]}" --plugin-dir "$PLUGINS/decision-model" --plugin-dir "$PLUGINS/resume-on-stop"
expect_not "resume-on-stop leaves the nudge's reply alone" "$T/both.jsonl" 'stopped mid-promise'
n=$(grep -c '"subtype":"compact_boundary"' "$T/both.jsonl")
if [ "$n" = 1 ]; then pass "it compacts once alongside resume-on-stop"; else fail "$n compactions in $T/both.jsonl"; fi
finish
