#!/bin/sh
# SessionStart hook: puts bun's folder on the session PATH (through CLAUDE_ENV_FILE, which Claude Code sets for
# SessionStart command hooks and sources into every Bash call), or says at session start that bun is missing.
here=$(dirname "$0")
if bun=$(sh "$here/find-bun.sh"); then
  dir=$(dirname "$bun")
  case ":$PATH:" in
    *":$dir:"*) ;;
    *) [ -n "${CLAUDE_ENV_FILE:-}" ] && printf 'export PATH="%s:$PATH"\n' "$dir" >> "$CLAUDE_ENV_FILE" ;;
  esac
else
  echo "code-mode: bun was not found, so the repl tool can't run. Install it: curl -fsSL https://bun.sh/install | bash"
fi
exit 0
