import { expect, test } from "claude-code/testing";

// A stand-in for decision-model. The kit runs a test plugin's register on its own, without its
// closure, so the answer is written into the noun's method, which a call on $.decision runs.
// `/decision-probe` calls that method the way a consumer does, for routesNouns.
const fakeDecision = {
  name: "decision-model",
  register: (on: any) => {
    on("command.run", { command: "decision-probe" }, async ($: any) => {
      try { await $.decision.ask({ state: "", questions: {} }); return { text: "routed" }; } catch (err) { return { text: String(err) }; }
    });
    on("engine.create", async ($: unknown, e: unknown, next: (e: unknown) => Promise<object>) => ({ ...(await next(e)), decision: { ask: async () => ({ backend: "claude", model: "fake", answers: { effort: { type: "choice", choice: "xhigh", probabilities: { xhigh: 1 }, confidence: 1 } } }) } }));
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

const stepResult = (turnId: string, index: number) => ({ turnId, index, answer: "ok", toolUses: [{ name: "Read", input: {} }], stopReason: "tool_use" as const, usage: null });

test("the decided level is the effort of every main-thread step of that turn", { plugins: [fakeDecision] }, async ($, on) => {
  const efforts: unknown[] = [];
  on("prompt.submit", ($, e) => ({ text: e.text }));
  on("ui.status", () => ({ value: undefined }));
  on("turn.step", async function* ($, e) {
    efforts.push(e.effort);
    return stepResult(e.turnId, e.index);
  });
  if (!(await routesNouns($))) return;
  await $.prompt.submit({ text: "why does the cache go stale under load?", wait: false, origin: { kind: "composer" } });
  for (const index of [0, 1]) for await (const _ of $.turn.step({ turnId: "t1", index, model: "opus", messageCount: 1 })) {}
  for await (const _ of $.turn.step({ turnId: "t2", index: 0, model: "opus", messageCount: 1 })) {}
  expect(efforts).toEqual(["xhigh", "xhigh", undefined]);
});
