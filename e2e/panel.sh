#!/usr/bin/env bash
source "$(dirname "$0")/lib.sh"
T=$(mktemp -d)
# Plugin settings are /config rows only in an interactive session (headless $.config.list has the
# engine's rows alone), so this check types into a real terminal session.
cd "$ROOT"
P=(--plugin-dir "$PLUGINS/omc-panel" --plugin-dir "$PLUGINS/omc-compact")
claude_tty "$T/1.log" 6 "/omc list" "/omc set autoMethod shake" "/omc list" "/omc set autoMethod native" -- "${P[@]}"
expect "/omc lists omc-compact's settings" "$T/1.log" 'omc-compact\.protectTokens ?= ?16000'
expect "/omc shows a picker's options" "$T/1.log" 'omc-compact\.autoMethod ?= ?"native" ?\[native\|shake\|handoff\]'
expect "/omc set changes a setting" "$T/1.log" 'omc-compact\.autoMethod ?= ?"shake"'
finish
