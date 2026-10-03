// Self-check for the kernel, outside Claude Code: `bun plugins/eval-kernel/kernel/kernel.check.ts`.
// Plays the mod's part: runs cells over the socket and answers host calls with fakes.
import { tmpdir } from "node:os";
import { join } from "node:path";

const sock = join(tmpdir(), `eval-kernel-check-${process.pid}.sock`);
const child = Bun.spawn(["bun", join(import.meta.dir, "kernel.ts"), sock], { stdout: "pipe", stderr: "inherit" });
const reader = child.stdout.getReader();
await reader.read(); // ready line

const post = (path: string, body: unknown) =>
  fetch(`http://localhost${path}`, { method: "POST", body: JSON.stringify(body), unix: sock } as any).then(r => r.json() as Promise<any>);
const get = (path: string) => fetch(`http://localhost${path}`, { unix: sock } as any).then(r => r.json() as Promise<any>);

/** Run a cell to completion, answering host calls the way the mod would. */
async function run(code: string, answer: (kind: string, payload: any) => unknown = () => null) {
  let ev = await post("/run", { code });
  const calls: string[] = [];
  while (ev.status === "call") {
    calls.push(`${ev.kind}:${ev.payload?.tool ?? ""}`);
    try {
      ev = await post("/resume", { callId: ev.callId, ok: true, value: await answer(ev.kind, ev.payload) });
    } catch (e) {
      ev = await post("/resume", { callId: ev.callId, ok: false, error: String(e) });
    }
  }
  return { ...ev, calls };
}

let failed = 0;
function check(name: string, cond: boolean, detail?: unknown) {
  console.log(`${cond ? "ok  " : "FAIL"} ${name}`);
  if (!cond) {
    failed++;
    console.log("     ", JSON.stringify(detail));
  }
}

try {
  const a = await run("const x = 40\nfunction add(a, b) { return a + b }");
  check("declarations run", a.status === "done", a);

  const b = await run("add(x, 2)");
  check("state survives across cells, trailing expression is the value", b.value === "42", b);

  const c = await run("console.log('hi', { n: 1 })\ndisplay([1, 2])");
  check("console and display are captured", c.output.includes("hi") && c.output.includes("[\n  1,\n  2\n]"), c);

  const d = await run(
    "const files = await Promise.all(['a.ts', 'b.ts'].map(f => tool.Read({ file_path: f })))\nfiles.join('|')",
    (kind, p) => (kind === "tool" ? { text: `content of ${p.args.file_path}` } : null),
  );
  check("parallel tool calls go through the host", d.value === "content of a.ts|content of b.ts" && d.calls.length === 2, d);

  const e = await run("await tool.Bash({ command: 'false' })", () => ({ text: "exit 1", isError: true }));
  check("an errored tool throws in the cell", e.status === "error" && e.error.includes("Bash failed: exit 1"), e);

  const f = await run("const r = await completion('2+2?', { model: 'haiku' })\nr", (kind, p) => (kind === "complete" ? `4 (${p.model})` : null));
  check("completion() reaches the host", f.value === "4 (haiku)", f);

  const g = await run("throw new Error('boom')");
  check("a thrown error is reported with the cell's output", g.status === "error" && g.error.includes("boom"), g);

  const h = await run("import { join } from 'node:path'\njoin('a', 'b')");
  check("static imports work and persist", h.value === "a/b", h);

  const i = await run("join('c', 'd')");
  check("an imported name survives to the next cell", i.value === "c/d", i);

  // Out-of-band answers: two parallel agent calls, answered later via /answer while /next waits.
  let ev = await post("/run", { code: "const [p, q] = await Promise.all([agent('a'), agent('b')])\np + q" });
  const first = ev;
  ev = await post("/next", {});
  const second = ev;
  const waiting = post("/next", {});
  await post("/answer", { callId: second.callId, ok: true, value: "B" });
  await post("/answer", { callId: first.callId, ok: true, value: "A" });
  ev = await waiting;
  check("calls answered out of band via /answer + /next", first.kind === "agent" && second.kind === "agent" && ev.value === "AB", { first, second, ev });

  const vars = await get("/vars");
  check("/vars lists user globals", vars.vars.some((v: any) => v.name === "add") && !vars.vars.some((v: any) => v.name === "tool"), vars);
} finally {
  child.kill();
}
console.log(failed ? `${failed} failed` : "all passed");
process.exit(failed ? 1 : 0);
