#!/usr/bin/env bash
source "$(dirname "$0")/lib.sh"
T=$(mktemp -d)
C=(--plugin-dir "$PLUGINS/compact-methods")
for i in $(seq 1 600); do echo "line $i: the quick brown fox jumps over the lazy dog, again and again and again"; done > "$T/big.log"

SID=$(uuidgen | tr 'A-Z' 'a-z')
claude_run "$T/1.jsonl" "Use the Read tool to read all of $T/big.log, then tell me what line 300 says." "${C[@]}" --session-id "$SID" --allowedTools Read --disallowedTools "Bash,Grep,Glob"
claude_run "$T/2.jsonl" "Reply with the word ok." "${C[@]}" --resume "$SID"
claude_run "$T/3.jsonl" "/compact shake" "${C[@]}" --resume "$SID"
expect "/compact shake compacts" "$T/3.jsonl" '"subtype":"compact_boundary"|Compacted'
if ls "$HOME/.claude/compact-methods/$SID/"*.txt >/dev/null 2>&1 && grep -q "line 600" "$HOME/.claude/compact-methods/$SID/"*.txt; then pass "the tool output was moved to a file"; else fail "no offloaded tool output in ~/.claude/compact-methods/$SID"; fi

claude_run "$T/4.jsonl" "/compact handoff" "${C[@]}" --resume "$SID"
expect "/compact handoff compacts" "$T/4.jsonl" '"subtype":"compact_boundary"|Compacted'
if ls "$HOME/.claude/compact-methods/$SID/"handoff-*.md >/dev/null 2>&1; then pass "the handoff document was saved"; else fail "no handoff document in ~/.claude/compact-methods/$SID"; fi
claude_run "$T/5.jsonl" "What file did you read earlier? Answer with just the path." "${C[@]}" --resume "$SID"
expect "the session continues from the handoff" "$T/5.jsonl" 'big\.log'
finish
