# Gatekeeper policy

`mise run loop:approvals` reads the block below, the engineering loop's policy
(its SKILL.md § Settings has every key), from `origin/main`'s copy, so a branch's
own edit takes effect only once it lands. It is YAML: `key: value` under a
section name, a list one item per line. Quote a value that starts with `*` or
reads as another type (`no`, `on`, `1.10`). A key or section the loop doesn't
know is refused, naming it. loop.md § Approvals says why the policy is what it is.

## Policy

```yaml
spec:
  # the owner's standing approval (loop.md § Approvals)
  auto: true

# practice:
#   the skill that fills a stage this project changes, one key each, such as
#   spec: brainstorming; a stage left out runs its default

risk:
  verifier: true
  paths:
    - .github/**
    - CODEOWNERS
    - docs/agents/loop.md
    - docs/agents/gatekeeper.md

levels:
  # the owner's standing approval covers merges (loop.md § Approvals)
  high:
    spec: policy
    merge: gates

# bot:
#   renovate:   # deps:renovate's routine group, run on your token: see loop.md § Approvals
#     branch: renovate/
#     paths:
#       - uv.lock
#       - package-lock.json
#       - pyproject.toml
#       - package.json
#       - mise.toml
#       - .github/workflows/*.yml
```
