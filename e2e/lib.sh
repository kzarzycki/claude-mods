# Shared helpers for the e2e checks. Each check runs real `claude -p` sessions with mods loaded
# from this repo and asserts on the stream-json output or on files the mods write.
set -u
# Sessions started from inside another Claude Code session inherit this marker and stop saving
# transcripts; the checks need transcripts.
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
PLUGINS="$ROOT/plugins"
MODEL_ARGS=()
[ -n "${E2E_MODEL:-}" ] && MODEL_ARGS=(--model "$E2E_MODEL")
FAILED=0

# claude_run <out.jsonl> <prompt> [claude args...]: one headless session; the prompt goes on stdin.
claude_run() {
  local out=$1 prompt=$2; shift 2
  printf '%s' "$prompt" | env -u CLAUDE_CODE_CHILD_SESSION timeout "${E2E_TIMEOUT:-300}" claude -p --output-format stream-json --verbose ${MODEL_ARGS[@]+"${MODEL_ARGS[@]}"} "$@" > "$out" 2> "$out.err"
  local code=$?
  [ $code -eq 0 ] || echo "  (claude exited $code; stderr: $(head -c 300 "$out.err"))"
  return 0
}

# claude_tty <log> <wait-seconds> <command>... -- <claude args>...: an interactive session through
# expect; the log is stripped of terminal escapes so it can be grepped.
claude_tty() {
  local log=$1; shift
  env -u CLAUDE_CODE_CHILD_SESSION expect "$ROOT/e2e/tty.exp" "$@" > "$log.raw" 2>&1
  sed 's/\x1b\[[0-9;?]*[a-zA-Z]//g' "$log.raw" | tr '\r' '\n' > "$log"
}

pass() { echo "ok   $1"; }
fail() { echo "FAIL $1"; FAILED=$((FAILED + 1)); }
# expect <name> <file> <extended regex>
expect() { if grep -Eq -- "$3" "$2"; then pass "$1"; else fail "$1 (no /$3/ in $2)"; fi; }
expect_not() { if grep -Eq -- "$3" "$2"; then fail "$1 (found /$3/ in $2)"; else pass "$1"; fi; }
finish() { [ $FAILED -eq 0 ] && echo "$(basename "$0"): passed" || echo "$(basename "$0"): $FAILED failed"; exit $FAILED; }
# The transcript file of a session id.
transcript() { find "$HOME/.claude/projects" -name "$1.jsonl" 2>/dev/null | head -1; }
