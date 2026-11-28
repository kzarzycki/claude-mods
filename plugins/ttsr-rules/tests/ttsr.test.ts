import type { On } from "claude-code";
import { expect, test } from "claude-code/testing";
import { globToRegExp, matchToolRule, parseRule } from "../hooks/rules";

const NO_ANY = `---\ndescription: No any\ncondition: ":\\\\s*any\\\\b"\nscope: tool:edit(*.ts)\nglobs:\n  - "src/**"\n---\nUse unknown and narrow it.`;
const CLAIMS = `---\nquestion: Does the message claim tests pass without having run them?\n---\nRun the tests before saying they pass.`;

test("rule files parse the way oh-my-pi writes them", () => {
  const r = parseRule("no-any", "x", NO_ANY)!;
  expect(r.tools).toContain("Edit");
  expect(matchToolRule([r], "Edit", { file_path: "/p/src/a.ts", new_string: "let x: any = 1" }, "/p")?.match).toBe(": any");
  expect(matchToolRule([r], "Edit", { file_path: "/p/src/a.js", new_string: "let x: any" }, "/p")).toBeUndefined();
  expect(matchToolRule([r], "Edit", { file_path: "/p/lib/a.ts", new_string: "let x: any" }, "/p")).toBeUndefined();
  expect(matchToolRule([r], "Bash", { command: "x: any" }, "/p")).toBeUndefined();
  expect(globToRegExp("src/**/*.ts").test("src/c.ts")).toBe(true);
  expect(parseRule("q", "x", CLAIMS)?.question).toContain("claim tests pass");
  expect(parseRule("s", "x", `---\ncondition: foo\nscope: text\n---\nb`)).toBeUndefined();
});

test("a scope glob with braces keeps its commas and matches either extension", () => {
  const r = parseRule("b", "x", `---\ncondition: foo\nscope: tool:edit(*.{ts,tsx})\n---\nb`)!;
  const hit = (f: string) => matchToolRule([r], "Edit", { file_path: f, new_string: "foo" }, "/p")?.match;
  expect(hit("/p/a.ts")).toBe("foo");
  expect(hit("/p/a.tsx")).toBe("foo");
  expect(hit("/p/a.js")).toBeUndefined();
  const two = parseRule("c", "x", `---\ncondition: foo\nscope: tool:edit(*.{ts,tsx},src/**)\n---\nb`)!;
  expect(matchToolRule([two], "Edit", { file_path: "/p/src/a.md", new_string: "foo" }, "/p")?.match).toBe("foo");
});

test("an unclosed brace in a glob is a literal and the parse returns", () => {
  expect(globToRegExp("a{b").test("a{b")).toBe(true);
  expect(globToRegExp("a{b").test("ab")).toBe(false);
  const r = parseRule("u", "x", `---\ncondition: foo\nglobs:\n  - "src/{a"\n---\nb`)!;
  expect(r.globs.length).toBe(1);
});

test("a literal brace in a scope does not swallow the glob after it", () => {
  const r = parseRule("l", "x", `---\ncondition: foo\nscope: tool:edit(src/{draft,docs/**)\n---\nb`)!;
  const hit = (f: string) => matchToolRule([r], "Edit", { file_path: f, new_string: "foo" }, "/p")?.match;
  expect(hit("/p/src/{draft")).toBe("foo");
  expect(hit("/p/docs/a.md")).toBe("foo");
  expect(hit("/p/other/a.md")).toBeUndefined();
});

/** Answer the session's file reads from an in-memory rule folder. */
function ruleFolder(on: On, files: Record<string, string>) {
  const dir = "/repo/.claude/ttsr";
  on("env.get", () => ({ value: "/home" }));
  on("fs.exists", ($, e) => ({ value: e.path === dir }));
  on("fs.list", () => ({ value: Object.keys(files).map(name => ({ name, kind: "file" as const, size: 1, mtimeMs: 0, isLink: false })) }));
  on("fs.read", ($, e) => ({ value: files[e.path.slice(dir.length + 1)] ?? "" }));
  on("command.register", ($, e) => ({ value: { command: e.name } }));
  on("session.start", ($, e) => ({ cwd: e.cwd }));
}

// A stand-in for decision-model. The kit runs a test plugin's register on its own, without its closure,
// so it answers from the state alone: yes when the message mentions passing tests.
const fakeDecision = {
  name: "decision-model",
  register: (on: any) => {
    on("command.run", { command: "decision-probe" }, async ($: any) => {
      try { await $.decision.ask({ state: "", questions: {} }); return { text: "routed" }; } catch (err) { return { text: String(err) }; }
    });
    on("engine.create", async ($: unknown, e: unknown, next: (e: unknown) => Promise<object>) => ({
      ...(await next(e)),
      decision: {
        ask: async (e: { state: unknown; questions: Record<string, unknown> }) => {
          const noul = JSON.stringify(e.state).includes("tests pass") ? 0.9 : 0;
          return { backend: "claude", model: "fake", answers: Object.fromEntries(Object.keys(e.questions).map(id => [id, { type: "noul", noul }])) };
        },
      },
    }));
  },
};

// `claude plugin test` on CLI 2.1.321 to 2.1.326 can't route a call on a plugin's noun (the host op
// interface.call), and a test can't answer that op either. There a test that needs $.decision ends
// early; e2e/run.sh decision covers it in real sessions. The stand-in's `/decision-probe` makes the
// call, since a test's own `$` carries no plugin nouns.
declare const console: { log: (line: string) => void };
const routesNouns = async ($: any) => {
  const { text } = await $.command.run({ command: "decision-probe", args: "", origin: { kind: "composer" }, presentation: { isFullscreen: false, columns: 80 } });
  if (text === "routed") return true;
  if (!/no implementation for interface\.call/.test(text)) throw new Error(`decision-probe: ${text}`);
  console.log("skipped: this CLI's plugin test kit can't route $.decision (interface.call)");
  return false;
};

test("a matching tool call is denied with the rule as the reason", { plugins: [fakeDecision] }, async ($, on) => {
  ruleFolder(on, { "no-any.md": NO_ANY });
  on("ui.toast", () => ({ value: undefined }));
  let ran = 0;
  on("tool.call", () => (ran++, { result: "ok" }));
  await $.session.start({ cwd: "/repo", surface: null, isInteractive: false });
  const denied = await $.tool.call({ tool: "Edit", file_path: "/repo/src/a.ts", old_string: "x", new_string: "let v: any" });
  expect(denied.deny).toContain('TTSR rule "no-any"');
  expect(denied.deny).toContain("Use unknown and narrow it.");
  const allowed = await $.tool.call({ tool: "Edit", file_path: "/repo/src/a.ts", old_string: "x", new_string: "let v: unknown" });
  expect(allowed.deny).toBeUndefined();
  expect(ran).toBe(1);
});

// The test kit does not route $.session.append to a test's on("session.append") (checked with a
// one-hook repro), so this asserts the toast; e2e/ttsr.sh checks the appended rule in a real session.
test("a question rule the judge says yes to fires after the turn", { plugins: [fakeDecision] }, async ($, on) => {
  ruleFolder(on, { "claims.md": CLAIMS });
  const toasts: string[] = [];
  on("ui.toast", ($, e) => (toasts.push(e.text), { value: undefined }));
  on("ui.log", () => ({ value: undefined }));
  on("turn.complete", ($, e) => ({ text: e.answer }));
  if (!(await routesNouns($))) return;
  await $.session.start({ cwd: "/repo", surface: null, isInteractive: false });
  await $.turn.complete({ turnId: "t1", answer: "I refactored the parser.", durationMs: 1, isAborted: false, reason: "answer" });
  expect(toasts).toEqual([]);
  await $.turn.complete({ turnId: "t2", answer: "Done, all tests pass.", durationMs: 1, isAborted: false, reason: "answer" });
  expect(toasts).toEqual(["ttsr: claims"]);
});
