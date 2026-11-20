---
name: demo
description: Record a short video or take a screenshot of a change running and post it to its PR, so a reviewer judges a visible change without checking out the branch. Use when a PR changes what a user sees (a command and its output, a page, a screen, a speed-up), on "record a demo", or when the project's instructions or spec ask for one.
metadata:
  requires: "gh>=2.99.0 vhs ttyd ffmpeg"
---

# Demo

A demo is the change running, recorded at the PR's head and posted on the PR, so a
person can watch it work in a minute instead of checking out the branch. Whether a PR
gets one is the project's call: its agent instructions say when to suggest a demo and
when to record one (A project's task and rule). Without such a rule, record only when asked.

## Record and post

```sh
scripts/demo.sh [--pr <number>] [--caption "<what it shows>"] <recording>...
```

`scripts/` is relative to this skill's folder. One command records and posts: a `.tape` is
rendered with VHS, a `.webm` or `.mov` is converted to H.264 MP4 with ffmpeg, and an `.mp4`
is posted as it is, and a `.png` or `.jpg` screenshot is posted as it is. All of them go into one `## Demo` comment naming the head commit, each
attached with `gh pr comment --attach` (gh 2.99.0 or later), so it plays inline. Your
earlier `## Demo` comments are minimized as outdated, so only the current one is open;
other people's are left alone. The PR defaults to the current branch's, and without
`--caption` the comment names the recordings. Then name the demo in the PR body's Evidence.

Pick the form by the change. A screenshot when the change is a still result (a card that
renders differently, a new label, a layout fix): it is read at a glance, and a video of a
still page is only waiting. A video when the change is something happening (a flow, typing,
an animation, a speed-up). The author decides.

Every refusal comes before anything records: a missing file or an unknown type (not a tape, video, `.png` or `.jpg`) (exit 2),
gh older than 2.99.0 or `ttyd` missing for a tape (exit 1), and a checkout that is not
the PR's head or holds uncommitted or untracked files (exit 3), since the video must show
the head everyone else gets.

Pick the recorder for the surface and read its file to write the recording:

| Surface | Recorder | Read |
|---|---|---|
| CLI or TUI | VHS tape | [recorders/cli.md](recorders/cli.md) |
| Web page | Playwright video | [recorders/browser.md](recorders/browser.md) |
| iOS simulator | `simctl` | [recorders/ios.md](recorders/ios.md) |
| Android emulator or device | `screenrecord` | [recorders/android.md](recorders/android.md) |

A change that spans surfaces gets one short recording per surface, posted together.

- Record the real build at the PR's head, so the video proves the change rather than a
  mock.
- Drive it from a script (a tape, a test, a command list) next to the e2e scenario it
  shows, so a re-recording after a fix is one command and shows a path the tests check.
- Keep secrets off screen (tokens, passwords, `env` output, customer data): anyone who
  can read the PR can watch the video, and secret scanning does not read video.
- Write recordings to a temporary folder, never into the repo, since every recording
  would grow every clone. The script renders and converts into one of its own.

## A project's task and rule

A project wraps the command in a task and names it in its agent docs. mise passes a
variadic `arg` as one shell-quoted variable, `usage_<name>`, not as `$@`, so the task
unquotes it to keep a path with a space whole:

```toml
[tasks."pr:demo"]
usage = 'arg "<recording>" var=#true'
run = 'eval "set -- $usage_recording"; .agents/skills/demo/scripts/demo.sh "$@"'
```

Whether a PR needs a demo is the project's rule, and it goes in the project's agent
instructions, for example: record one for a PR that changes what a user sees, and accept a
`Demo: none, <why>` line in the PR body for one where nothing runs differently.
