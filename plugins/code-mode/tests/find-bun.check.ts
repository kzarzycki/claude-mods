// The order of hooks/find-bun.sh and its missing case: `bun plugins/code-mode/tests/find-bun.check.ts`.
// BUN_INSTALL/bin, then PATH, then ~/.bun/bin, then /opt/homebrew/bin (the last can't be faked, so only the first three are ordered).
import { chmodSync, mkdirSync, mkdtempSync, writeFileSync } from "node:fs";
import { tmpdir } from "node:os";
import { join } from "node:path";

const script = join(import.meta.dir, "../hooks/find-bun.sh");
const root = mkdtempSync(join(tmpdir(), "find-bun-"));
const fake = (dir: string) => (mkdirSync(dir, { recursive: true }), writeFileSync(join(dir, "bun"), "#!/bin/sh\n"), chmodSync(join(dir, "bun"), 0o755), join(dir, "bun"));
const find = (env: Record<string, string>) => {
  const r = Bun.spawnSync(["/bin/sh", script], { env: { PATH: "/usr/bin:/bin", ...env } });
  return { code: r.exitCode, out: r.stdout.toString().trim() };
};

const home = join(root, "home"), install = join(root, "install"), onPath = join(root, "path");
const dotBun = fake(join(home, ".bun/bin"));
const cases: [string, ReturnType<typeof find>, ReturnType<typeof find>][] = [];
const check = (name: string, got: ReturnType<typeof find>, want: ReturnType<typeof find>) => cases.push([name, got, want]);

// Nothing anywhere but a home without bun: missing (unless this machine has /opt/homebrew/bin/bun, which wins last).
const homebrew = Bun.file("/opt/homebrew/bin/bun").size > 0;
if (!homebrew) check("missing: exit 1 and no output", find({ HOME: join(root, "empty") }), { code: 1, out: "" });
check("~/.bun/bin when nothing earlier has it", find({ HOME: home }), { code: 0, out: dotBun });
const pathBun = fake(onPath);
check("PATH before ~/.bun/bin", find({ HOME: home, PATH: `${onPath}:/usr/bin:/bin` }), { code: 0, out: pathBun });
const installBun = fake(join(install, "bin"));
check("$BUN_INSTALL/bin before PATH", find({ HOME: home, BUN_INSTALL: install, PATH: `${onPath}:/usr/bin:/bin` }), { code: 0, out: installBun });

let failed = 0;
for (const [name, got, want] of cases) {
  const ok = got.code === want.code && got.out === want.out;
  if (!ok) failed++;
  console.log(`${ok ? "ok  " : "FAIL"} ${name}${ok ? "" : ` (got ${JSON.stringify(got)}, want ${JSON.stringify(want)})`}`);
}
process.exit(failed ? 1 : 0);
