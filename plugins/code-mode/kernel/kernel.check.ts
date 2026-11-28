// Self-check for the kernel, outside Claude Code: `bun plugins/code-mode/kernel/kernel.check.ts`.
// Plays the mod's part: runs scripts over the socket and answers host calls with a fake host whose
// Bash, Read, Edit and Write answer in the shapes Claude Code's tools give $.tool.call.
import { mkdirSync, mkdtempSync, readFileSync, writeFileSync } from "node:fs";
import { tmpdir } from "node:os";
import { dirname, join } from "node:path";

const WAIT_MS = 300;
const sock = join(tmpdir(), `code-mode-check-${process.pid}.sock`);
const child = Bun.spawn([process.execPath, join(import.meta.dir, "kernel.ts"), sock, String(WAIT_MS)], { stdout: "pipe", stderr: "inherit" });
await child.stdout.getReader().read(); // ready line
const dir = mkdtempSync(join(tmpdir(), "code-mode-check-"));

const post = (path: string, body: unknown, at = sock) =>
  fetch(`http://localhost${path}`, { method: "POST", body: JSON.stringify(body), unix: at } as any).then(r => r.json() as Promise<any>);
/** A kernel of its own, for checks that restart one. */
async function kernel(path: string, marker: string) {
  const k = Bun.spawn([process.execPath, join(import.meta.dir, "kernel.ts"), path, String(WAIT_MS), marker], { stdout: "pipe", stderr: "inherit" });
  await k.stdout.getReader().read();
  return k;
}
const get = (path: string) => fetch(`http://localhost${path}`, { unix: sock } as any).then(r => r.json() as Promise<any>);

/** Claude Code's tools, as $.tool.call answers them (probed shapes). */
function fakeTool(tool: string, a: any): unknown {
  if (tool === "Bash") {
    const r = Bun.spawnSync(["bash", "-c", `${a.command} 2>&1`]);
    const out = r.stdout.toString();
    // Claude Code saves a large output to a file and leaves stdout empty.
    if (a.command.includes("BIGOUT")) {
      const p = join(tmpdir(), "kernel-check-big.txt");
      writeFileSync(p, "line\n".repeat(3000));
      return { text: "<persisted-output>saved</persisted-output>", result: { stdout: "", stderr: "", persistedOutputPath: p }, isError: false };
    }
    if (a.command.includes("QUIETOK")) return { text: "(Bash completed with no output)", result: { stdout: "", stderr: "" }, isError: false };
    if (a.command.includes("UNREADABLE")) return { text: "preview of it", result: { stdout: "", stderr: "", persistedOutputPath: join(tmpdir(), "kernel-check-missing.txt") }, isError: false };
    if (a.command.includes("EMPTYSTDOUT")) return { text: "from text", result: { stdout: "", stderr: "" }, isError: false };
    return r.exitCode === 0
      ? { text: out, result: { stdout: out, stderr: "" }, isError: false }
      : { text: `Exit code ${r.exitCode}\n${out}`, isError: true };
  }
  if (tool === "Read") {
    let text: string;
    try { text = readFileSync(a.file_path, "utf8"); } catch { return { text: "<tool_use_error>File does not exist.</tool_use_error>", isError: true }; }
    const all = text.split("\n");
    const lines = all.slice(a.offset - 1, a.offset - 1 + a.limit);
    // Read refuses a page over its token budget; here, over 8000 characters.
    if (lines.join("\n").length > 8000) return { text: "File content (9999 tokens) exceeds maximum allowed tokens (2000). Use offset and limit.", isError: true };
    return { text: "numbered", result: { type: "text", file: { filePath: a.file_path, content: lines.join("\n"), numLines: lines.length, startLine: a.offset, totalLines: all.length } }, isError: false };
  }
  if (tool === "Edit") {
    const text = readFileSync(a.file_path, "utf8");
    if (!text.includes(a.old_string)) return { text: "String to replace not found in file.", isError: true };
    writeFileSync(a.file_path, a.replace_all ? text.split(a.old_string).join(a.new_string) : text.replace(a.old_string, () => a.new_string));
    return { text: "ok", isError: false };
  }
  if (tool === "Write") return (mkdirSync(dirname(a.file_path), { recursive: true }), writeFileSync(a.file_path, a.content), { text: "ok", isError: false });
  if (tool === "mcp__x__boom") return { text: "server said no", isError: true };
  return { text: `content of ${a.file_path}`, isError: false };
}
const TOOLS = [
  { name: "Bash", description: "Executes a bash command. More text." },
  { name: "mcp__linear__create_issue", description: "Create a Linear issue. Needs a team." },
];

/** Run a script to completion, answering host calls the way the mod would. */
async function run(code: string, answer: (kind: string, payload: any) => unknown = () => null, at = sock) {
  let ev = await post("/run", { code, cwd: dir }, at);
  const cell = ev.cell;
  const calls: string[] = [];
  let waits = 0;
  while (ev.status === "call" || ev.status === "wait") {
    if (ev.status === "wait") { waits++; ev = await post("/next", { cell }, at); continue; }
    calls.push(`${ev.kind}:${ev.payload?.tool ?? ""}`);
    try {
      const value = ev.kind === "tool" ? fakeTool(ev.payload.tool, ev.payload.args) : ev.kind === "tools" ? TOOLS : await answer(ev.kind, ev.payload);
      ev = await post("/resume", { callId: ev.callId, ok: true, value, cell }, at);
    } catch (e) {
      ev = await post("/resume", { callId: ev.callId, ok: false, error: String(e), cell }, at);
    }
  }
  return { ...ev, calls, waits };
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
  check("state survives across calls, trailing expression is the value", b.value === "42", b);

  const m = await run("const out = 3;\n({\n  total: out,\n})");
  check("a multi-line trailing object is the value", m.value === "total: 3", m);

  const mc = await run("[1, 2, 3]\n  .map(n => n * 2)\n  .join(',') // doubled");
  check("a multi-line method chain with a trailing comment is the value", mc.value === "2,4,6", mc);

  const blk = await run("if (true) {\n  1\n}");
  check("a script ending in a block has no value", blk.status === "done" && blk.value === undefined, blk);

  const c = await run("self.log('hi', { n: 1 })\nconsole.log('quiet')\nconsole.tail(1)");
  check("self.log reaches the output, console goes to the ring", c.output.includes("hi") && !c.output.includes("quiet") && c.value === "quiet", c);

  // $ through the Bash tool
  const s1 = await run("const name = \"it's here\"\nawait $`echo ${name} ${['a b', 'c']}`.text()");
  check("$ quotes each value as one argument, arrays one per item", s1.value === "it's here a b c\n" && s1.calls[0] === "tool:Bash", s1);

  const bigShell = await run("const r = await $`echo BIGOUT`\nJSON.stringify({ n: r.stdout.split('\\n').length, t: r.truncated, w: r.whole, note: r.note })");
  const bs = bigShell.status === "done" ? JSON.parse(bigShell.value) : {};
  check("a large $ output saved to a file is read back, one page of it", bs.n === 1000, bigShell);
  check("a large saved $ output is marked truncated and not whole, the note names the file", bs.t === true && bs.w === false && String(bs.note).includes("kernel-check-big.txt"), bigShell);

  const unread = await run("const r = await $`echo UNREADABLE`\nJSON.stringify({ out: r.stdout, t: r.truncated, w: r.whole, note: r.note })");
  const ur = unread.status === "done" ? JSON.parse(unread.value) : {};
  check("a saved $ output that can't be read back keeps the preview, truncated, not whole, with a note", ur.out === "preview of it" && ur.t === true && ur.w === false && String(ur.note).includes("could not be read back"), unread);

  const quiet = await run("JSON.stringify(await $`echo QUIETOK`.text())");
  check("a silent success stays an empty stdout, not Bash's status message", quiet.value === '""', quiet);

  const em = await run("await $`echo EMPTYSTDOUT`.text()");
  check("an empty stdout falls back to the result text", em.value === "from text", em);

  const s2 = await run("await $`exit 3`");
  check("a non-zero exit throws ShellError", s2.status === "error" && s2.error.includes("ShellError: exit 3"), s2);

  const s3 = await run("const r = await $`echo out; exit 3`.nothrow()\n[r.exitCode, r.stdout]");
  check("nothrow() gives the exit code and output", s3.value?.includes("3") && s3.value.includes("out"), s3);

  const s4 = await run("(await $`grep nope /dev/null`).note");
  check("exit 1 from grep is an answer with a note", s4.status === "done" && s4.value?.includes("answer"), s4);

  const s5 = await run("await $`pwd`.cwd('/tmp').env({ GREETING: 'hey there' }).text() + await $`echo $GREETING`.env({ GREETING: 'yo' }).text()");
  check("cwd() and env() apply to the command", /tmp\n/.test(s5.value) && s5.value.endsWith("yo\n"), s5);

  const s6 = await run("await $('echo \"a  b\" | tr a A', 5000).text()");
  check("$(cmd) runs a string as written", s6.value === "A  b\n", s6);

  const s7 = await run("({status: $`echo one`, other: $`echo two`.text()})");
  check("promises in a returned object are awaited, keys rendered one by one", s7.value === "status: one\nother:\ntwo\n" || s7.value === "status:\none\n\nother:\ntwo\n", s7);

  // files through Read, Edit and Write
  const f1 = await run("await write('sub/a.txt', 'alpha\\nbeta\\nalpha\\n')\nawait file('sub/a.txt').text()", () => null);
  check("write() then file().text() round-trips", f1.value === "alpha\nbeta\nalpha\n" && f1.calls.includes("tool:Write") && f1.calls.includes("tool:Read"), f1);

  const f2 = await run("await edit('sub/a.txt', 'alpha', 'x')");
  check("edit() refuses an ambiguous anchor", f2.status === "error" && f2.error.includes("2 matches"), f2);

  const f3 = await run("const e = await edit('sub/a.txt', [['beta', 'B'], ['B\\nalpha', 'C']])\n[e.replacements, await file('sub/a.txt').text()]");
  check("batch edit checks anchors in order and applies them", f3.value?.includes("2") && f3.value.includes("alpha\\nC\\n"), f3);

  const f4 = await run("await edit('sub/a.txt', 'zzz', 'y', { soft: true })");
  check("edit(..., {soft}) resolves ok: false", f4.value?.startsWith('ok: false'), f4);

  const f5 = await run("[await file('sub/a.txt').exists(), await file('nope.txt').exists()]");
  check("file().exists()", f5.value === "[\n  true,\n  false\n]", f5);

  // tools
  const t1 = await run("await tools.Read({ file_path: 'a.ts' })", () => null);
  check("tools.X calls a tool by name", t1.status === "done" && t1.calls[0] === "tool:Read", t1);

  const t2 = await run("await tools.mcp__x__boom({})");
  check("an MCP tool error throws", t2.status === "error" && t2.error.includes("server said no"), t2);

  const t3 = await run("({ found: await searchTools('linear issue'), d: await describeTool('Bash') })");
  check("searchTools and describeTool read the tool list", t3.value?.includes("mcp__linear__create_issue") && t3.value.includes("Executes a bash command"), t3);

  // long scripts: the kernel answers "wait" and the mod asks again
  const w = await run("await sleep(1000)\n'slept'");
  check("a long script sends wait events and still finishes", w.value === "slept" && w.waits >= 2, w);

  const big = await run("'x'.repeat(30000) + 'END'");
  check("a long value keeps head and tail", big.value.length < 21000 && big.value.endsWith("END") && big.value.includes("cut from the middle"), big.value.length);

  const f = await run("const r = await completion('2+2?', { model: 'haiku' })\nr", (kind, p) => (kind === "complete" ? `4 (${p.model})` : null));
  check("completion() reaches the host", f.value === "4 (haiku)", f);

  const g = await run("throw new Error('boom')");
  check("a thrown error is reported", g.status === "error" && g.error.includes("boom"), g);

  const h = await run("import { join } from 'node:path'\njoin('a', 'b')");
  check("static imports work and persist", h.value === "a/b", h);

  const i = await run("join('c', 'd')");
  check("an imported name survives to the next call", i.value === "c/d", i);

  // Out-of-band answers: two parallel agent calls, answered later via /answer while /next waits.
  let ev = await post("/run", { code: "const [p, q] = await Promise.all([agent('a'), agent('b')])\np + q", cwd: dir });
  const first = ev;
  ev = await post("/next", {});
  const second = ev;
  const waiting = post("/next", {});
  await post("/answer", { callId: second.callId, ok: true, value: "B" });
  await post("/answer", { callId: first.callId, ok: true, value: "A" });
  ev = await waiting;
  while (ev.status === "wait") ev = await post("/next", {});
  check("calls answered out of band via /answer + /next", first.kind === "agent" && second.kind === "agent" && ev.value === "AB", { first, second, ev });

  // An answer that lands after a "wait" and before the next /next: the event it causes must stay queued.
  ev = await post("/run", { code: "const late = await agent('x')\n'got ' + late", cwd: dir });
  const lateCall = ev;
  const parked = await post("/next", {});
  await post("/answer", { callId: lateCall.callId, ok: true, value: "it" });
  ev = await post("/next", {});
  for (let n = 0; ev.status === "wait" && n < 3; n++) ev = await post("/next", {});
  check("an event after a wait reaches the next /next", parked.status === "wait" && ev.value === "got it", { parked, ev });

  // what a model writes first: Node idioms (the trial session's failures)
  const r1 = await run("const { execSync } = require('child_process')\nexecSync('echo hi').toString()");
  check("require() works in a script", r1.value === "hi\n", r1);

  const r2 = await run("execSync('echo again').toString()");
  check("a destructured declaration survives to the next script", r2.value === "again\n", r2);

  const r3 = await run("const [one, { two: deux = 2 }] = [1, {}]\nconst xs = [1, 2].map(n => {\n  return n * 10;\n});\n({ one, deux, xs })");
  check("a trailing value after a function body with return", r3.value === "one: 1\ndeux: 2\nxs:\n[\n  10,\n  20\n]", r3);

  const r4 = await run("[one, deux]");
  check("array and nested destructuring persist too", r4.value === "[\n  1,\n  2\n]", r4);

  const tpl = await run("const tplText = `\nclass Nope {}\nconst nope = 1\nasync function nah() {}\nimport x from 'y'\nreturn 5\n`\nconst afterTpl = 'kept'\n// const notMe = 1\n/*\nconst notMeEither = 2\n*/\ntplText.split('\\n').length");
  const tpl2 = await run("[afterTpl, typeof Nope, typeof nope, typeof nah, typeof notMe, typeof notMeEither, tplText.includes('globalThis')]");
  check("declarations inside a template or comment stay text", tpl.value === "7" && tpl2.value === JSON.stringify(["kept", "undefined", "undefined", "undefined", "undefined", "undefined", false], null, 2), { tpl, tpl2 });

  // A script that throws while calls are still queued: its error is the next event, the queued calls never run.
  const q = await run("await Promise.all([tools.mcp__x__boom({}), tools.Bash({ command: 'echo a' }), tools.Bash({ command: 'echo b' })])");
  check("a script's error overtakes the calls it left queued", q.status === "error" && q.error.includes("server said no") && q.calls.length === 1, q);
  // An answer to a call the ended script handed out earlier is dropped, not refused.
  ev = await post("/run", { code: "await Promise.all([agent('a'), Promise.reject(new Error('early'))])", cwd: dir });
  const orphan = ev.status === "call" ? ev : null;
  while (ev.status === "call" || ev.status === "wait") ev = await post("/next", {});
  const late2 = orphan ? await post("/answer", { callId: orphan.callId, ok: true, value: "x" }) : null;
  check("a late answer to an ended script's call is dropped", ev.status === "error" && ev.error.includes("early") && late2?.ok === true, { orphan, ev, late2 });

  // A value after the last top-level ; of the last line is the script's value.
  const semi = await run("const semiR = 1 + 1; 'got ' + semiR");
  const semi2 = await run("const semiS = 'a;b'; [semiS, (1, 2)]; semiS.length");
  const semi3 = await run("for (let i = 0; i < 2; i++) {}");
  check("a value after ; on the last line is the value", semi.value === "got 2" && semi2.value === "3" && semi3.status === "done" && semi3.value === undefined, { semi, semi2, semi3 });

  // Two scripts at once share one scope, and each one's events reach only its own caller.
  const a1 = await post("/run", { code: "const sharedA = 'from-a'\nconst gotA = await agent('wait')\ngotA + ' ' + fromB", cwd: dir });
  const b1 = await run("const fromB = sharedA + '-seen-by-b'\nawait $`echo b-ran`.text() + fromB");
  const a2 = await post("/resume", { callId: a1.callId, ok: true, value: "a-done", cell: a1.cell });
  check("scripts run side by side in one shared scope", a1.kind === "agent" && b1.value === "b-ran\nfrom-a-seen-by-b" && b1.calls.join() === "tool:Bash" && a2.value === "a-done from-a-seen-by-b" && a1.cell !== b1.cell, { a1, b1, a2 });

  // /cancel stops one script and keeps the kernel and its variables.
  const c1 = await post("/run", { code: "const beforeCancel = 'kept'\nawait agent('never answered')\n'not reached'", cwd: dir });
  const c2 = await post("/cancel", { cell: c1.cell, why: "interrupted" });
  const c3 = await post("/answer", { callId: c1.callId, ok: true, value: "late" });
  const c4 = await run("beforeCancel");
  check("/cancel stops one script, the kernel and its variables stay", c2.ok && c3.ok && c4.value === "kept" && (await get("/health")).running === 0, { c1, c2, c3, c4 });

  // A call a script never awaited is rejected when the script ends; that must not end the kernel.
  const u1 = await run("tools.Bash({ command: 'echo never' })\n'left'");
  await Bun.sleep(50);
  const u2 = await run("beforeCancel + '-still'");
  check("an unawaited call doesn't crash the kernel", u1.value === "left" && u2.value === "kept-still", { u1, u2 });

  // A page Read refuses as too large is read again in smaller pages, still through Read.
  const bigFile = Array.from({ length: 3000 }, (_, i) => `line ${i}`).join("\n");
  writeFileSync(join(dir, "big.txt"), bigFile);
  writeFileSync(join(dir, "wide.txt"), "x".repeat(9000));
  const bigR = await run("(await file('big.txt').text()).length");
  const wideR = await run("await file('wide.txt').text()");
  // 3000 lines in one or two pages of 2000 would be 2 Reads; refused pages make it more
  check("a file too large for one Read is read in smaller pages through Read", bigR.value === String(bigFile.length) && bigR.calls.length > 2 && bigR.calls.every(c => c === "tool:Read"), bigR);
  check("a single line too large for Read is an error, not a direct read", wideR.status === "error" && /exceeds/.test(wideR.error), wideR);

  // A kernel that replaces an earlier one of the same session says so in its first script.
  const mk = join(dir, "ran.marker"), sock2 = sock + ".2";
  let k2 = await kernel(sock2, mk);
  const fresh1 = await run("1", () => null, sock2), fresh2 = await run("2", () => null, sock2);
  k2.kill();
  await k2.exited;
  k2 = await kernel(sock2, mk);
  const again = await run("3", () => null, sock2);
  k2.kill();
  // An answer to a call of the earlier kernel must not reach a script of the new one.
  await k2.exited;
  k2 = await kernel(sock2, mk);
  const oldRun = await post("/run", { code: "await tools.Bash({ command: 'old' })", cwd: dir }, sock2);
  const oldCall = oldRun.status === "call" ? oldRun : await post("/next", { cell: oldRun.cell }, sock2);
  k2.kill();
  await k2.exited;
  k2 = await kernel(sock2, mk);
  const newRun = await post("/run", { code: "await tools.Bash({ command: 'new' })", cwd: dir }, sock2);
  const newCall = newRun.status === "call" ? newRun : await post("/next", { cell: newRun.cell }, sock2);
  const stale = await post("/answer", { callId: oldCall.callId, ok: true, value: { text: "stale" } }, sock2);
  const fresh = await post("/resume", { callId: newCall.callId, ok: true, value: { text: "fresh" }, cell: newCall.cell }, sock2);
  k2.kill();
  check("an answer from before a restart is dropped, not given to a new script", oldCall.callId !== newCall.callId && !!stale.dropped && String(fresh.value).includes("fresh"), { oldCall, newCall, stale, fresh });
  check("a restarted kernel says its variables are gone, once", !fresh1.output.includes("[repl]") && !fresh2.output.includes("[repl]") && again.output.includes("started fresh"), { fresh1, again });

  const vars = await get("/vars");
  check("/vars lists user globals", vars.vars.some((v: any) => v.name === "add") && !vars.vars.some((v: any) => v.name === "file"), vars);
} finally {
  child.kill();
}
console.log(failed ? `${failed} failed` : "all passed");
process.exit(failed ? 1 : 0);
