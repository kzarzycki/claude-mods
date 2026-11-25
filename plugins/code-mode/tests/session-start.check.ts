// hooks/session-start.sh with no exec bits on hooks/ (a plugin copy can lose them): `bun plugins/code-mode/tests/session-start.check.ts`.
// With a fake HOME holding ~/.bun/bin/bun, the hook must not say bun is missing and must export bun's folder to CLAUDE_ENV_FILE.
import { chmodSync, cpSync, mkdirSync, mkdtempSync, readdirSync, readFileSync, symlinkSync, writeFileSync } from "node:fs";
import { tmpdir } from "node:os";
import { join } from "node:path";

const root = mkdtempSync(join(tmpdir(), "session-start-"));
const hooks = join(root, "hooks");
cpSync(join(import.meta.dir, "../hooks"), hooks, { recursive: true });
for (const f of readdirSync(hooks)) chmodSync(join(hooks, f), 0o644);

const home = join(root, "home"), binDir = join(home, ".bun/bin"), envFile = join(root, "env");
mkdirSync(binDir, { recursive: true });
writeFileSync(join(binDir, "bun"), "#!/bin/sh\n");
chmodSync(join(binDir, "bun"), 0o755);
writeFileSync(envFile, "");

// A PATH with the tools the hook uses and no bun, so a bun in /usr/bin on this machine can't win over ~/.bun/bin.
const tools = join(root, "tools");
mkdirSync(tools);
for (const t of ["sh", "dirname"]) symlinkSync(Bun.which(t) ?? `/usr/bin/${t}`, join(tools, t));

const r = Bun.spawnSync(["/bin/sh", join(hooks, "session-start.sh")], { env: { PATH: tools, HOME: home, CLAUDE_ENV_FILE: envFile } });
const out = r.stdout.toString(), env = readFileSync(envFile, "utf8");
const cases: [string, boolean][] = [
  ["exits 0", r.exitCode === 0],
  ["no 'bun was not found' line", !out.includes("bun was not found")],
  ["CLAUDE_ENV_FILE exports bun's folder on PATH", env.trim() === `export PATH="${binDir}:$PATH"`],
];
let failed = 0;
for (const [name, ok] of cases) {
  if (!ok) failed++;
  console.log(`${ok ? "ok  " : "FAIL"} ${name}${ok ? "" : ` (stdout ${JSON.stringify(out)}, env file ${JSON.stringify(env)})`}`);
}
process.exit(failed ? 1 : 0);
