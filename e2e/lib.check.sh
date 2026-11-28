#!/usr/bin/env bash
# Self-check of e2e/lib.sh, no model calls: a fake `claude` on PATH stands in for the real one.
cd "$(dirname "$0")/.."
T=$(mktemp -d); trap 'rm -rf "$T"' EXIT
mkdir "$T/bin"; export PATH="$T/bin:$PATH"
failed=0
check() { if [ "$2" = "$3" ]; then echo "ok   $1"; else echo "FAIL $1 (want '$3', got '$2')"; failed=$((failed + 1)); fi; }
# fake <body>: a `claude` that runs the body.
fake() { printf '#!/usr/bin/env bash\n%s\n' "$1" > "$T/bin/claude"; chmod +x "$T/bin/claude"; }
# count <env...>: FAILED after one claude_run of the current fake.
count() { env "$@" bash -c 'source e2e/lib.sh; claude_run "$0/out.jsonl" hi >/dev/null; echo $FAILED' "$T"; }

fake 'echo "{\"type\":\"result\"}"'
check "a session that exits 0 passes" "$(count E2E_TIMEOUT=5)" 0
fake 'echo "{\"type\":\"result\"}"; sleep 10'
check "a session that times out (exit 124) fails" "$(count E2E_TIMEOUT=1)" 1
fake 'echo "{\"type\":\"result\"}"; exit 3'
check "a session that exits non-zero fails" "$(count E2E_TIMEOUT=5)" 1
fake 'echo "{\"type\":\"result\"}"; sleep 10'
check "a timed-out check file exits non-zero" "$(E2E_TIMEOUT=1 bash -c 'source e2e/lib.sh; claude_run "$0/o.jsonl" hi >/dev/null; finish >/dev/null' "$T"; echo $?)" 1
# FAILED is lost in a subshell, so no check file wraps claude_run in one.
check "no check file runs claude_run in a subshell" "$(grep -nE '\(.*claude_run' e2e/*.sh | grep -v '^e2e/lib' | wc -l | tr -d ' ')" 0
echo "$failed failed"
exit $failed
