#!/usr/bin/env bash
# #21: the policy is read from gatekeeper.md § Policy, with the owner's standing approval.
set -euo pipefail
cd "$(git rev-parse --show-toplevel)"
scripts=.agents/skills/engineering-loop/scripts

! grep -q '^## Settings' docs/agents/loop.md || { echo "loop.md still has ## Settings" >&2; exit 1; }

out=$(GATEKEEPER_POLICY_FROM_WORKING_TREE=1 uv run -q --python '>=3.11' "$scripts/approvals.py" check setup 2>&1)
echo "$out"
! grep -q deprecated <<<"$out" || { echo "the policy still reads as deprecated" >&2; exit 1; }

uv run -q --python '>=3.11' --with pyyaml python - "$scripts" <<'PY'
import pathlib, sys
sys.path.insert(0, sys.argv[1])
import gatekeeper as g
s = g.settings(g.Policy(pathlib.Path("docs/agents/gatekeeper.md").read_text()))
assert s["spec"] == {"auto": True}, s["spec"]
assert s["levels"] == {"high": {"spec": "policy", "merge": "gates"}}, s["levels"]
assert set(s["risk"]["paths"]) == {".github/**", "CODEOWNERS", "docs/agents/loop.md", "docs/agents/gatekeeper.md"}, s["risk"]
assert s["risk"]["verifier"] is True, s["risk"]
assert "critical_paths" not in s["risk"], s["risk"]
print("policy: spec.auto true, high {policy, gates}, critical default, risk paths kept plus gatekeeper.md")
PY
