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

test("a refused settings-file read tells the script to use file(path).text(), not $.settings.read", async ($, on) => {
  on("tool.call", { tool: "Bash" }, () => ({ deny: "a Claude Code settings file is not for plugins outside policy to write; read settings with $.settings.read" }));
  const posts = await start($, on, path =>
    path === "/run" ? { status: "call", callId: "c1", kind: "tool", payload: { tool: "Bash", args: { command: "jq . ~/.claude/settings.json" } } } : { status: "done", output: "", value: "ok" },
  );
  await $.tool.call({ tool: "mcp__code-mode__repl", code: "await $`jq . ~/.claude/settings.json`" });
  const text = String(posts[1]!.body.value.text);
  expect(text).toContain("file(path).text()");
  expect(text).not.toContain("$.settings.read");
});

test("a settings refusal returned as an error result is rewritten too", async ($, on) => {
  on("tool.call", { tool: "Bash" }, () => ({ result: "x" as never, isError: true, text: "a Claude Code settings file is not for plugins outside policy to write; read settings with $.settings.read" }));
  const posts = await start($, on, path =>
    path === "/run" ? { status: "call", callId: "c1", kind: "tool", payload: { tool: "Bash", args: { command: "jq . ~/.claude/settings.json" } } } : { status: "done", output: "", value: "ok" },
  );
  await $.tool.call({ tool: "mcp__code-mode__repl", code: "await $`jq . ~/.claude/settings.json`" });
  const text = String(posts[1]!.body.value.text);
  expect(text).toContain("file(path).text()");
  expect(text).not.toContain("$.settings.read");
});

test("a tool's own output that holds the settings phrase is not rewritten", async ($, on) => {
  const out = "Exit code 2\nread settings with $.settings.read";
  on("tool.call", { tool: "Bash" }, () => ({ result: "x" as never, isError: true, text: out }));
  const posts = await start($, on, path =>
    path === "/run" ? { status: "call", callId: "c1", kind: "tool", payload: { tool: "Bash", args: { command: "x" } } } : { status: "done", output: "", value: "ok" },
  );
  await $.tool.call({ tool: "mcp__code-mode__repl", code: "await $`x`" });
  expect(posts[1]!.body.value.text).toBe(out);
});
