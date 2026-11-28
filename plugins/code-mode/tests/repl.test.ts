import type { On } from "claude-code";
import { expect, test } from "claude-code/testing";

// The kernel itself is checked by kernel/kernel.check.ts. Here a fake kernel answers http.fetch,
// so this covers the mod's half: the call/resume loop and how each host call is run.

type Ev = Record<string, unknown>;

/** Start the session against a fake kernel whose /run and /resume replies come from `script`. */
async function start($: any, on: On, script: (path: string, body: any) => Ev, registered: any[] = [], bunAt = "/usr/bin/bun") {
  const posts: { path: string; body: any }[] = [];
  on("session.id", () => ({ value: "session-one" }));
  on("tool.register", ($, e) => (registered.push(e), { value: { tool: `mcp__code-mode__${e.name}` } }));
  on("command.register", ($, e) => ({ value: { command: e.name } }));
  // hooks/find-bun.sh answers with bunAt ("" for none); any other spawn is the kernel, which ends at once.
  on("process.spawn", async function* (_$, e) {
    if (e.argv.some((a: string) => a.endsWith("find-bun.sh")) && bunAt) yield { stream: "stdout", text: `${bunAt}\n` } as never;
    return { value: { code: bunAt ? 0 : 1, signal: null } };
  });
  on("clock.sleep", () => ({ value: undefined }));
  on("session.cwd", () => ({ value: "/repo" }));
  on("http.fetch", ($, e) => {
    const path = new URL(e.url).pathname;
    const body = typeof e.init?.body === "string" ? JSON.parse(e.init.body) : undefined;
    if (path !== "/health") posts.push({ path, body });
    const reply = path === "/health" ? { ok: true } : script(path, body);
    return { value: { status: 200, ok: true, headers: {}, text: JSON.stringify(reply) } };
  });
  on("session.start", ($, e) => ({ cwd: e.cwd }));
  await $.session.start({ cwd: "/repo", surface: null, isInteractive: false });
  return posts;
}

test("a script's tool call runs through $.tool.call and its result resumes the script", async ($, on) => {
  on("tool.call", { tool: "Read" }, ($, e) => ({ result: `contents of ${e.file_path}` as never, text: `contents of ${e.file_path}` }));
  const posts = await start($, on, (path, body) =>
    path === "/run" ? { status: "call", callId: "c1", kind: "tool", payload: { tool: "Read", args: { file_path: "/repo/a.ts" } } } : { status: "done", output: "", value: JSON.stringify(body.value) },
  );
  const r = await $.tool.call({ tool: "mcp__code-mode__repl", code: "await tools.Read({ file_path: '/repo/a.ts' })" });
  expect(r.isError).toBeUndefined();
  expect(String(r.result)).toContain("contents of /repo/a.ts");
  expect(posts[0]).toEqual({ path: "/run", body: { code: "await tools.Read({ file_path: '/repo/a.ts' })", cwd: "/repo" } });
  expect(posts[1]!.body).toMatchObject({ callId: "c1", ok: true, value: { text: "contents of /repo/a.ts", isError: false } });
});

test("a script may not call repl itself, and the refusal reaches the script as an error", async ($, on) => {
  const posts = await start($, on, path =>
    path === "/run" ? { status: "call", callId: "c1", kind: "tool", payload: { tool: "mcp__code-mode__repl", args: { code: "1" } } } : { status: "error", output: "", error: "Error: a script can't call repl itself" },
  );
  const r = await $.tool.call({ tool: "mcp__code-mode__repl", code: "await tools.mcp__code-mode__repl({ code: '1' })" });
  expect(r.isError).toBe(true);
  expect(posts[1]!.body).toMatchObject({ callId: "c1", ok: false, error: "a script can't call repl itself" });
});

test("a wait event asks the kernel again until the script ends", async ($, on) => {
  let waits = 0;
  const posts = await start($, on, path =>
    path === "/run" || (path === "/next" && waits < 2) ? (waits++, { status: "wait" }) : { status: "done", output: "", value: "slept" },
  );
  const r = await $.tool.call({ tool: "mcp__code-mode__repl", code: "await sleep(60000)\n'slept'" });
  expect(String(r.result)).toBe("=> slept");
  expect(posts.map(p => p.path)).toEqual(["/run", "/next", "/next"]);
});

test("repl takes no free-text label: Claude Code would refuse later Bash calls that contain its words", async ($, on) => {
  const registered: any[] = [];
  await start($, on, () => ({ status: "done", output: "" }), registered);
  expect(Object.keys(registered[0].inputSchema.properties).sort()).toEqual(["code", "reset"]);
});

test("the Code Mode guide is the tool's description: preferred beside Bash, exclusive without it", async ($, on) => {
  let listed = ["mcp__code-mode__repl", "Bash", "Read", "Edit"];
  on("env.get", () => ({ value: undefined }));
  on("tool.describe", () => ({ description: "short" }));
  on("tool.list", () => ({ value: listed.map(name => ({ name, description: "", mcp: false })) }));
  await start($, on, () => ({ status: "done", output: "" }));
  const describe = () => $.tool.describe({ tool: "mcp__code-mode__repl", description: "short", provider: { plugin: "code-mode", tier: "user" } } as any);
  expect((await describe()).description).toContain("Prefer `repl`");
  listed = ["mcp__code-mode__repl", "Read", "Edit"]; // only Bash missing: still preferred
  expect((await describe()).description).toContain("Prefer `repl`");
  listed = ["mcp__code-mode__repl", "ToolSearch"];
  expect((await describe()).description).toContain("Work through `repl`");
});

test("the guide gives merge rules and one split rule for repl calls", async ($, on) => {
  on("env.get", () => ({ value: undefined }));
  on("tool.describe", () => ({ description: "short" }));
  on("tool.list", () => ({ value: [] }));
  await start($, on, () => ({ status: "done", output: "" }));
  const d = (await $.tool.describe({ tool: "mcp__code-mode__repl", description: "short", provider: { plugin: "code-mode", tier: "user" } } as any)).description;
  for (const t of ["Merge into one script", "Promise.all", "commit, push, open the PR, clone", "poll or wait loop", "the steps of one phase", "Split only where the next step needs a judgment"]) expect(d).toContain(t);
});

test("the guide says to keep going in the same script on the happy path and stop at the first failure", async ($, on) => {
  on("env.get", () => ({ value: undefined }));
  on("tool.describe", () => ({ description: "short" }));
  on("tool.list", () => ({ value: [] }));
  await start($, on, () => ({ status: "done", output: "" }));
  const d = (await $.tool.describe({ tool: "mcp__code-mode__repl", description: "short", provider: { plugin: "code-mode", tier: "user" } } as any)).description;
  expect(d).toContain("On the happy path keep going in the same script");
  expect(d).toContain("if the tests pass, commit, push and open the PR");
  expect(d).toContain("stop and return on the first failure with what failed");
});

test("with CODE_MODE_GUIDE=system the description points at the system prompt instead of repeating the guide", async ($, on) => {
  on("env.get", ($, e) => ({ value: e.name === "CODE_MODE_GUIDE" ? "system" : undefined }));
  on("tool.describe", () => ({ description: "short" }));
  on("tool.list", () => ({ value: [] }));
  await start($, on, () => ({ status: "done", output: "" }));
  const d = (await $.tool.describe({ tool: "mcp__code-mode__repl", description: "short", provider: { plugin: "code-mode", tier: "user" } } as any)).description;
  expect(d).toContain("the Code Mode section of your system prompt");
  expect(d).not.toContain("# Code Mode");
});

test("/next and /resume name the script's cell, so scripts running side by side don't take each other's events", async ($, on) => {
  on("tool.call", { tool: "Read" }, () => ({ result: "x" as never, text: "x" }));
  let n = 0;
  const posts = await start($, on, path =>
    path === "/run" ? { status: "wait", cell: "k7" } : n++ === 0 ? { status: "call", callId: "c1", kind: "tool", payload: { tool: "Read", args: {} }, cell: "k7" } : { status: "done", output: "", value: "ok", cell: "k7" },
  );
  await $.tool.call({ tool: "mcp__code-mode__repl", code: "await tools.Read({})" });
  expect(posts.map(p => [p.path, p.body.cell])).toEqual([["/run", undefined], ["/next", "k7"], ["/resume", "k7"]]);
});

// agent() isn't covered here: the agent id comes only from core (a test hook answering
// agent.spawn starts no subagent and gets none), so e2e/repl.sh covers it with a real one.

test("with no bun found, repl fails with one line naming the install command, and no kernel starts", async ($, on) => {
  const posts = await start($, on, () => ({ status: "done", output: "", value: "1" }), [], "");
  const r = await $.tool.call({ tool: "mcp__code-mode__repl", code: "1" });
  expect(r.isError).toBe(true);
  expect(String(r.result)).toContain("curl -fsSL https://bun.sh/install | bash");
  expect(String(r.result).trim().split("\n").length).toBe(1);
  expect(posts).toEqual([]);
});

// A kernel's stop is a POST /stop to its socket. The fake kernels are processes that run until stopped
// (so supervise would start a stopped one again, and the spawns show it), refuse connections once stopped
// or while still starting, and can hold a script open.
async function startWithSockets($: any, on: On, opts: { upAfter?: number } = {}) {
  const calls: { path: string; at: string }[] = [];
  const spawns: string[] = []; // the socket of each kernel started
  const ends = new Map<string, () => void>();
  const down = new Set<string>();
  const attempts = new Map<string, number>();
  const hold = { release: () => {}, gate: null as Promise<void> | null };
  on("session.id", () => ({ value: "session-one" }));
  on("tool.register", ($, e) => ({ value: { tool: `mcp__code-mode__${e.name}` } }));
  on("command.register", ($, e) => ({ value: { command: e.name } }));
  on("turn.complete", () => ({ text: "" }) as never);
  on("session.end", () => ({ sessionId: "session-one" }) as never);
  on("process.spawn", async function* (_$, e) {
    if (e.argv.some((a: string) => a.endsWith("find-bun.sh"))) yield { stream: "stdout", text: "/usr/bin/bun\n" } as never;
    else {
      const at = e.argv[e.argv.findIndex((a: string) => a.endsWith("kernel.ts")) + 1]!;
      spawns.push(at);
      await new Promise<void>(r => ends.set(at, r));
    }
    return { value: { code: 0, signal: null } };
  });
  on("clock.sleep", () => ({ value: undefined }));
  on("session.cwd", () => ({ value: "/repo" }));
  on("http.fetch", async ($, e) => {
    const path = new URL(e.url).pathname;
    const at = String((e.init as any)?.socketPath);
    const n = (attempts.get(at) ?? 0) + 1;
    attempts.set(at, n);
    if (down.has(at) || n <= (opts.upAfter ?? 0)) throw new Error("connect ECONNREFUSED " + at);
    calls.push({ path, at });
    if (path === "/stop") {
      down.add(at);
      ends.get(at)?.();
    }
    let reply: object = path === "/health" ? { ok: true } : { status: "done", output: "", value: "1" };
    if (hold.gate && path === "/run") reply = { status: "wait", cell: "c" };
    if (hold.gate && path === "/next") {
      await hold.gate;
      reply = { status: "done", output: "", value: "late", cell: "c" };
    }
    return { value: { status: 200, ok: true, headers: {}, text: JSON.stringify(reply) } };
  });
  on("session.start", ($, e) => ({ cwd: e.cwd }));
  await $.session.start({ cwd: "/repo", surface: null, isInteractive: false });
  const stops = () => calls.filter(c => c.path === "/stop").map(c => c.at);
  /** The socket a repl call's script ran in. */
  const ranIn = async (call: Promise<any>) => {
    const before = calls.length;
    const r = await call;
    return { r, at: calls.slice(before).find(c => c.path === "/run")?.at };
  };
  return { calls, stops, spawns, hold, ranIn };
}

const repl = (code: string, agentId?: string) => ({ tool: "mcp__code-mode__repl", code, ...(agentId ? { agentId } : {}) }) as any;
const end = ($: any, agentId: string) => $.turn.complete({ agentId, reason: "answer", answer: "done" } as any);

test("with own subagents, a subagent's kernel stops when its agent ends, the main one keeps serving, and a resumed agent gets a fresh one", { options: { subagents: "own" } }, async ($, on) => {
  const k = await startWithSockets($, on);
  const main = await k.ranIn($.tool.call(repl("1")));
  const agent = await k.ranIn($.tool.call(repl("1", "agent-a")));
  expect(agent.at).not.toBe(main.at);
  expect(k.spawns).toEqual([main.at!, agent.at!]);
  await end($, "agent-a");
  expect(k.stops()).toEqual([agent.at!]);
  // The main kernel still serves, and the stopped one isn't started again by supervise.
  const again = await k.ranIn($.tool.call(repl("2")));
  expect(again.r.isError).toBeUndefined();
  expect(again.at).toBe(main.at);
  expect(k.spawns).toEqual([main.at!, agent.at!]);
  // A resumed agent's next call starts a fresh kernel.
  const resumed = await k.ranIn($.tool.call(repl("3", "agent-a")));
  expect(resumed.r.isError).toBeUndefined();
  expect(resumed.at).not.toBe(agent.at);
  expect(k.spawns.length).toBe(3);
});

test("the shared kernel keeps running when a subagent that used it ends, and stops when the main session ends", async ($, on) => {
  const k = await startWithSockets($, on);
  const main = await k.ranIn($.tool.call(repl("1")));
  const agent = await k.ranIn($.tool.call(repl("1", "agent-a")));
  expect(agent.at).toBe(main.at);
  await end($, "agent-a");
  expect(k.stops()).toEqual([]);
  expect((await k.ranIn($.tool.call(repl("2")))).at).toBe(main.at);
  await $.session.end({} as any);
  expect(k.stops()).toEqual([main.at!]);
});

test("a kernel with a script still running stops when the script ends, not before", { options: { subagents: "own" } }, async ($, on) => {
  const k = await startWithSockets($, on);
  let release!: () => void;
  k.hold.gate = new Promise<void>(r => (release = r));
  const running = $.tool.call(repl("await slow()", "agent-a"));
  while (!k.spawns.length || !k.calls.some(c => c.path === "/next")) await new Promise(r => setTimeout(r, 1));
  await end($, "agent-a");
  expect(k.stops()).toEqual([]);
  release();
  expect((await running).isError).toBeUndefined();
  expect(k.stops()).toEqual([k.spawns[1]!]);
});

test("a kernel that is still starting when its agent ends is stopped once it answers", { options: { subagents: "own" } }, async ($, on) => {
  const k = await startWithSockets($, on, { upAfter: 3 });
  // Blank code fails at once, after asking for the kernel to start.
  expect((await $.tool.call(repl(" ", "agent-a"))).isError).toBe(true);
  expect(k.spawns.length).toBe(2);
  await end($, "agent-a");
  expect(k.stops()).toEqual([k.spawns[1]!]);
});
