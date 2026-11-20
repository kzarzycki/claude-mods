# CLI or TUI: VHS

[VHS](https://github.com/charmbracelet/vhs) types a `.tape` script into a real terminal
and renders it. It needs `ttyd` and `ffmpeg` on `PATH`; pin `vhs` and `ffmpeg` in the
project's tool manager so every machine renders the same video.

```tape
Set Shell bash
Set FontSize 18
Set Width 1280
Set Height 720
Set TypingSpeed 40ms

Hide
Type "cd examples/shop" Enter
Type "clear" Enter
Show

Type "mytool migrate --dry-run" Sleep 300ms Enter
Wait
Sleep 3s
```

- Put setup (directories, environment, fixtures, logins) between `Hide` and `Show`,
  then `clear`, so the video opens on the command.
- A bare `Wait` waits for VHS's own `>` prompt, so the video stays short on a fast machine
  and complete on a slow one. A pattern for another prompt never matches and fails the
  render; a command slower than 15 s needs `Wait@60s`.
- Pass the output on the command line, `vhs demo.tape -o "$tmp/demo.mp4"`, rather than
  an `Output` line, so the tape never writes into the repo.
