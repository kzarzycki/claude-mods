#!/usr/bin/env bash
source "$(dirname "$0")/lib.sh"
T=$(mktemp -d)
# Plugin settings are /config rows only in an interactive session (headless $.config.list has the
# engine's rows alone), so this check types into a real terminal session.
cd "$ROOT"
P=(--plugin-dir "$PLUGINS/cm-panel" --plugin-dir "$PLUGINS/cm-compact")
claude_tty "$T/1.log" 6 "/cm list" "/cm set autoMethod shake" "/cm list" "/cm set autoMethod native" -- "${P[@]}"
expect "/cm lists cm-compact's settings" "$T/1.log" 'cm-compact\.protectTokens ?= ?16000'
expect "/cm shows a picker's options" "$T/1.log" 'cm-compact\.autoMethod ?= ?"native" ?\[native\|shake\|handoff\]'
expect "/cm set changes a setting" "$T/1.log" 'cm-compact\.autoMethod ?= ?"shake"'
finish
