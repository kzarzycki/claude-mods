# Proof run

A brief the lead fills in and sends to a cloud child (`run --pr <n>`, SKILL.md, Cloud worker)
when a verifier asks for its runs because the host's heavy slot was not free, or its sandbox refused a run (verifier.md,
A run the sandbox refuses). The child returns the logs; the verifier reads them as its own. The undo
and redo commands are the ones verifier.md, Mutation-check the new tests gives for its
patches, copied from the verifier's question, since the template would drift from that
paragraph if it named them itself. A verifier's question lists every run its pass needs, and the
brief takes them all: one list, answered together in one heavy-slot hold on one host that can make
each, not one brief per run.

```text
Check out PR #<n> at <head> (`git fetch origin pull/<n>/head && git checkout --detach <head>`)
and stop if `git rev-parse HEAD` is not <head>. Commit nothing and push nothing: these are a
review's runs, not a change.

Each log starts with the output of `git rev-parse HEAD` and the command, then its output,
then a line `exit <n>`, since a log of another commit proves nothing about this one.

Runs, in this order; drop a line the question did not ask for and add one per further run it
listed (an acceptance line, an instance or device proof, a gate step), each in its own log:

1. Green log: run <gate command>.
2. Mutation log: for each patch below, <the undo command>, run <tests>, then
   <the redo command>, one log section per patch.
   <each patch the verifier saved, verbatim in its own fenced block>
3. Restore: end with `git status --porcelain` and `git diff --stat` in the last log, both
   empty, since a run that leaves the tree changed taints the next one.

Write each log to `tmp/loop/<name>.log` and name each in your one report comment on PR
#<n>, so it comes back as a file block and one that would pass the comment's size limit is
cut to its last lines.
```
