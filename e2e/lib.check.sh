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
# decision.sh runs its last two sessions in an empty folder. A fake claude that logs its folder and call
# number, and hangs on call $HANG, stands in for the real one.
fake 'n=$(cat "$FAKE_DIR/n" 2>/dev/null || echo 0); n=$((n + 1)); echo $n > "$FAKE_DIR/n"
echo "$n $PWD" >> "$FAKE_DIR/calls"; echo "{\"type\":\"result\"}"
[ "$n" = "${HANG:-0}" ] && sleep 10; exit 0'
decision() { rm -rf "$T/fd"; mkdir "$T/fd"; env FAKE_DIR="$T/fd" E2E_TIMEOUT=1 "$@" bash e2e/decision.sh 2>&1; }
check "decision.sh: a hang in the 4th session fails the check" "$(decision HANG=4 | grep -c 'FAIL claude exited 124')" 1
check "decision.sh: a hang in the 5th session fails the check" "$(decision HANG=5 | grep -c 'FAIL claude exited 124')" 1
check "decision.sh: its last two sessions run in the empty folder" "$(decision HANG=0 >/dev/null; sed -n '4,5p' "$T/fd/calls" | grep -c '/empty$')" 2
# A mkdir that fails leaves no folder to enter: the check fails and starts neither session.
printf '#!/usr/bin/env bash\ncase "$*" in *empty*) exit 1;; esac\nexec /bin/mkdir "$@"\n' > "$T/bin/mkdir"; chmod +x "$T/bin/mkdir"
check "decision.sh: no empty folder fails the check" "$(decision HANG=0 | grep -c 'FAIL cannot enter')" 2
check "decision.sh: no empty folder starts no session in it" "$(wc -l < "$T/fd/calls" | tr -d ' ')" 3
rm "$T/bin/mkdir"
echo "$failed failed"
exit $failed
