#!/usr/bin/env bash
source "$(dirname "$0")/lib.sh"
T=$(mktemp -d)
P=(--plugin-dir "$PLUGINS/omc-decision" --plugin-dir "$PLUGINS/omc-ttsr")
mkdir -p "$T/proj/.claude/ttsr" "$T/proj/src"
cat > "$T/proj/.claude/ttsr/no-any.md" <<'RULE'
---
description: No any in TypeScript
condition: ":\\s*any\\b"
scope: tool:edit,write(*.ts)
---
Never type a value as `any`. Use `unknown` and narrow it.
RULE
cat > "$T/proj/.claude/ttsr/no-banana.md" <<'RULE'
---
question: Does the message contain the word banana?
---
Never write the word banana; write "yellow fruit" instead.
RULE

cd "$T/proj"
claude_run "$T/list.jsonl" "/ttsr" "${P[@]}"
expect "/ttsr lists both rules" "$T/list.jsonl" 'no-any .*no-banana|no-banana.*no-any'

claude_run "$T/write.jsonl" "Create src/a.ts containing exactly: export const x: any = 1" "${P[@]}" --allowedTools "Write,Edit,Read" --disallowedTools "Bash"
expect "a matching Write is denied with the rule" "$T/write.jsonl" 'TTSR rule \\"no-any\\" stopped this Write call'
[ -f "$T/proj/src/a.ts" ] && expect_not "the file never holds the banned pattern" "$T/proj/src/a.ts" ':\s*any\b'

# Interactive: headless, the note written after the last turn is lost when the process exits.
SID=$(uuidgen | tr 'A-Z' 'a-z')
claude_tty "$T/q.log" 15 "Reply with the single word: banana" "Quote the text of the rule you were just given." -- "${P[@]}" --session-id "$SID"
expect "a question rule is appended for the next turn" "$(transcript "$SID")" 'ttsr-rule name=\\"no-banana\\"'
expect "the model reads it on its next turn" "$T/q.log" 'yellow ?fruit'
finish
