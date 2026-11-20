// Interrupt cases for the repl hook, against a stub kernel: `bun plugins/code-mode/tests/interrupt.check.ts`.
// An abort at any point before the script's result is accepted must cancel the cell (once it has one)
// and report "interrupted", never the script's value. The kit's `claude plugin test` hands a hook no
// abort signal, so this drives register() directly.
import { register } from "../hooks/register";

// Bun runs this; the mod's tsconfig carries only Claude Code's types, so name the two globals used here.
declare const console: { log(...args: unknown[]): void }, process: { exit(code: number): never };

const hooks = new Map<string, Function>();
register(((name: string, match: object | Function, handler?: Function) => {
  if (typeof match !== "function" && handler && name === "tool.call") hooks.set("repl", handler);
}) as never, {} as never);

type Reply = (path: string, abort: () => void) => object;
const done = { status: "done", cell: "g.k1", output: "", value: "finished" };
const cases: [string, Reply, (requests: string[]) => boolean][] = [
  ["abort before /run: the script is never submitted", (p, abort) => (p === "/health" && abort(), p === "/health" ? { ok: true } : done), r => !r.includes("/run")],
  ["abort during /run, first answer wait: the cell is cancelled", (p, abort) => (p === "/run" ? (abort(), { status: "wait", cell: "g.k1" }) : p === "/next" ? done : { ok: true }), r => r.includes("/cancel")],
  ["abort during /run, the script already done: interrupted, not its value", (p, abort) => (p === "/run" ? (abort(), done) : { ok: true }), () => true],
  ["abort while waiting on /next, which answers done: interrupted, not its value", (p, abort) => (p === "/run" ? { status: "wait", cell: "g.k1" } : p === "/next" ? (abort(), done) : { ok: true }), () => true],
];

let failed = 0;
for (const [name, reply, sent] of cases) {
  const controller = new AbortController();
  const requests: string[] = [];
  const engine = {
    session: { cwd: async () => "/repo" },
    http: { fetch: async (url: string) => {
      const path = new URL(url).pathname;
      requests.push(path);
      return { ok: true, text: JSON.stringify(reply(path, () => controller.abort())) };
    } },
  };
  const result = await hooks.get("repl")!(engine, { code: "'finished'" }, { signal: controller.signal });
  const ok = result.isError === true && /interrupted/.test(String(result.result)) && sent(requests);
  console.log(`${ok ? "ok  " : "FAIL"} ${name}`);
  if (!ok) (failed++, console.log("     ", JSON.stringify({ requests, result })));
}
console.log(failed ? `${failed} failed` : "all passed");
process.exit(failed ? 1 : 0);
