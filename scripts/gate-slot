#!/usr/bin/env bash
# Run a heavy gate part (a test suite) holding one of this host's gate slots, which every worktree
# and project on the host shares, so agents working in parallel queue their gates instead of
# overloading the host together. `check:unit` calls it.
#
#   gate-slot COMMAND [ARG...]
#
# GATE_SLOTS (default 1) is how many gates run at once. A slot is a lock on a file, so it frees
# itself when the command exits, however it exits. GATE_JOBS, exported to the command, is the cores
# free when it starts (online cores minus the 1-minute load average, at least 1): a parallel runner
# reads it, e.g. `pytest -n "$GATE_JOBS"`, instead of adding a worker per core on a loaded host.
# LOOP_GATE_SLOT_HELD names the slot a run already holds: the loop's local-ci and land set it around each
# gate step, and gate-slot sets it for its command. Under a slot of its own directory gate-slot takes no
# lock, since it would wait on its own parent forever.
set -euo pipefail

[ $# -gt 0 ] || { echo "usage: gate-slot COMMAND [ARG...]" >&2; exit 2; }
slots="${GATE_SLOTS:-1}"
[[ "$slots" =~ ^[1-9][0-9]*$ ]] || { echo "gate-slot: GATE_SLOTS=$slots is no positive count" >&2; exit 2; }
dir="${XDG_CACHE_HOME:-$HOME/.cache}/engineering-loop"
mkdir -p "$dir"
# perl, since macOS ships no flock(1); the lock's descriptor stays open across exec, so the command holds it.
# GATE_JOBS is sampled once the slot is held, so a gate that waited sizes itself to the host as it is then.
exec perl -MFcntl=:flock -e '
  my ($dir, $slots, @command) = @ARGV;
  $^F = 1023;
  my ($said, $held);
  # Repeated slashes count as one on both sides: the loop builds the path with os.path.join, which writes no
  # "//" for an XDG_CACHE_HOME or HOME ending in a slash, as this script would.
  my ($want, $named) = map { (my $path = $_) =~ s{/+}{/}g; $path } $dir, $ENV{LOOP_GATE_SLOT_HELD} // "";
  $held = 1 if $named =~ m{\A\Q$want\E/gate\.[0-9]+\.lock\z};
  until ($held) {
    for my $i (1 .. $slots) {
      open(my $fh, ">>", "$dir/gate.$i.lock") or die "gate-slot: $dir/gate.$i.lock: $!\n";
      if (flock($fh, LOCK_EX | LOCK_NB)) {
        truncate($fh, 0); syswrite($fh, "$$\n"); $held = $fh; $ENV{LOOP_GATE_SLOT_HELD} = "$dir/gate.$i.lock"; last;
      }
    }
    next if $held;
    unless ($said++) {
      my $pid = do { local @ARGV = ("$dir/gate.1.lock"); my $line = <> // ""; chomp $line; $line };
      print STDERR "gate-slot: waiting for a host gate slot (held by pid ", ($pid || "unknown"), ")\n";
    }
    sleep 2;
  }
  my $cores = `getconf _NPROCESSORS_ONLN 2>/dev/null`;
  $cores = $cores =~ /^\s*(\d+)/ && $1 > 0 ? $1 : 1;
  my $load = do { local $ENV{LC_ALL} = "C"; `uptime` } =~ /load averages?: *([0-9.]+)/ ? $1 : 0;
  my $free = int($cores - $load);
  $ENV{GATE_JOBS} = $free < 1 ? 1 : $free > $cores ? $cores : $free;
  exec { $command[0] } @command or die "gate-slot: $command[0]: $!\n";
' "$dir" "$slots" "$@"
