// The watchdog against a real kernel: `bun plugins/code-mode/tests/watchdog.check.ts` (about 25 s).
// The mod runs through register() with a small engine adapter that spawns the real kernel, so this
// covers the wiring the stub cases in interrupt.check.ts can't: the kernel naming its own pid, the
// supervisor starting a replacement, the restart notice, and a pid that no longer names the kernel.
// A wedged kernel can't run its own exit handler, so it is ended by pid.
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";
import * as reg from "../hooks/register";

declare const Bun: any, console: { log(...args: unknown[]): void }, process: { exit(code: number): never; kill(pid: number, sig: number): void };
declare const setTimeout: (f: () => void, ms: number) => unknown;
declare const AbortController: any;

const root = join(dirname(fileURLToPath(import.meta.url)), "..");
const handlers: { name: string; match?: any; fn: Function }[] = [];
reg.register(((name: string, a: any, b?: Function) => handlers.push(typeof a === "function" ? { name, fn: a } : { name, match: a, fn: b! })) as never, {} as never);

const children: { proc: any; argv: string[] }[] = [];

const sleep = (ms: number) => new Promise<void>(r => setTimeout(r, ms));
async function* lines(proc: any) {
  const reader = proc.stdout.getReader();
  for (;;) {
    const { value, done } = await reader.read();
    if (done) return;
    yield { stream: "stdout", text: new TextDecoder().decode(value) };
  }
}
const engine: any = {
  session: { id: async () => "watchdog-check", cwd: async () => root },
  plugin: { root },
  tool: { register: async () => {} },
  command: { register: async () => {} },
  clock: { sleep },
  ui: { log: () => {} },
  process: {
    spawn: ({ argv, cwd }: { argv: string[]; cwd?: string }) => {
      const proc = Bun.spawn(argv, { cwd, stdout: "pipe", stderr: "pipe" });
      if (argv[1]?.endsWith("kernel.ts")) children.push({ proc, argv });
      const it = lines(proc);
      return { [Symbol.asyncIterator]: () => it, return: async () => ({ done: true }) };
    },
    run: async (argv: string[]) => {
      const proc = Bun.spawn(argv, { stdout: "pipe", stderr: "pipe" });
      const stdout = await new Response(proc.stdout).text();
      return { exitCode: await proc.exited, stdout, stderr: "" };
    },
  },
  http: { fetch: async (url: string, init: any = {}) => {
    const res = await fetch(url, { method: init.method, body: init.body, headers: init.headers, unix: init.socketPath });
    return { ok: res.ok, status: res.status, text: await res.text() };
  } },
};
const call = (code: string, signal?: any) => handlers.find(h => h.name === "tool.call" && h.match)!.fn(engine, { code }, { signal }) as Promise<{ isError?: boolean; result: string }>;
const alive = (pid: number) => { try { process.kill(pid, 0); return true; } catch { return false; } };
const pidOf = async () => JSON.parse(((await call("typeof 1")), await engine.http.fetch("http://localhost/health", { socketPath: reg.kernels.keys().next().value })).text).pid as number;

let failed = 0;
const check = (name: string, ok: boolean, detail?: unknown) => (console.log(`${ok ? "ok  " : "FAIL"} ${name}`), ok || (failed++, console.log("     ", JSON.stringify(detail))));
const stuckFor = async (code: string, abortAfter = 500) => {
  const c = new AbortController();
  const run = call(code, c.signal);
  await sleep(abortAfter);
  c.abort();
  return Promise.race([run, sleep(15000).then(() => "hung" as const)]);
};

await handlers.find(h => h.name === "session.start")!.fn(engine, { cwd: root }, async (e: unknown) => e);
await call("let keep = 42\nkeep");
const first = await pidOf();

// Interrupt a short synchronous loop (finite, under the wait): the kernel is not killed.
const busy = await stuckFor("const t = Date.now(); while (Date.now() - t < 2000) {}", 300);
await sleep(1500);
check("a kernel busy for 2 s keeps its pid and its variables", busy !== "hung" && (await pidOf()) === first && (await call("keep")).result.includes("42"), { busy });

// Interrupt a script stuck in a synchronous loop: killed, replaced, the model told.
const stuck = await stuckFor("while (true) {}");
check("an interrupted endless loop returns instead of hanging", stuck !== "hung" && /interrupted/.test(String((stuck as any).result)), { stuck });
for (let i = 0; i < 60 && alive(first); i++) await sleep(250);
check("the stuck kernel is gone", !alive(first));
const after = await call("typeof keep");
check("the replacement kernel starts fresh and says so", /\[repl\].*variables from earlier scripts are gone/.test(after.result) && /undefined/.test(after.result), { after });
const second = await pidOf();
check("the replacement is a different process", second !== first && alive(second), { first, second });

// A call queued behind a wedged kernel, interrupted while it waits for the kernel to answer.
const wedger = call("while (true) {}").catch(e => `killed with its kernel: ${String(e).slice(0, 40)}`);
await sleep(500);
const queued = await stuckFor("1", 500);
check("an interrupt while waiting for a wedged kernel returns", queued !== "hung", { queued });
for (let i = 0; i < 60 && alive(second); i++) await sleep(250);
check("and that interrupt killed the wedged kernel", !alive(second));
await Promise.race([wedger, sleep(5000)]);
check("the kernel after that one runs scripts", (await call("1 + 1")).result.includes("2"));

// A pid that no longer names this kernel is not signalled.
const k = [...reg.kernels.entries()][0]!;
const decoy = Bun.spawn(["sleep", "30"]);
k[1].pid = decoy.pid;
await reg.watchdog({ ...engine, http: { fetch: () => new Promise(() => {}) }, clock: { sleep: (ms: number) => sleep(Math.min(ms, 50)) } }, k[0]);
check("a pid whose command line is not this kernel's is left alone", alive(decoy.pid));
decoy.kill();

for (const c of children) c.proc.kill();
console.log(failed ? `${failed} failed` : "all passed");
process.exit(failed ? 1 : 0);
