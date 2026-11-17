import { expect, test } from "claude-code/testing";

// A stand-in for decision-model that always says yes. The kit runs a test plugin's register on its
// own, without its closure, so the answer is written into the noun's method, which a call on $.decision runs.
const fakeDecision = {
  name: "decision-model",
  register: (on: any) => {
    on("command.run", { command: "decision-probe" }, async ($: any) => {
      try { await $.decision.ask({ state: "", questions: {} }); return { text: "routed" }; } catch (err) { return { text: String(err) }; }
    });
    on("engine.create", async ($: unknown, e: unknown, next: (e: unknown) => Promise<object>) => ({ ...(await next(e)), decision: { ask: async () => ({ backend: "claude", model: "fake", answers: { stop: { type: "noul", noul: 0.9 } } }) } }));
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

test("an unexpected stop gets one resume prompt", { plugins: [fakeDecision] }, async ($, on) => {
  const submitted: string[] = [];
  on("ui.toast", () => ({ value: undefined }));
  on("prompt.submit", ($, e) => {
    submitted.push(e.text);
    return { text: e.text };
  });
  on("turn.step", async function* ($, e) {
    return { turnId: e.turnId, index: e.index, answer: "Let me run the tests next.", toolUses: [], stopReason: "end_turn" as const, usage: null };
  });
  on("turn.complete", ($, e) => ({ text: e.answer }));
  if (!(await routesNouns($))) return;
  const complete = (turnId: string) => $.turn.complete({ turnId, answer: "Let me run the tests next.", durationMs: 1, isAborted: false, reason: "answer" });
  for await (const _ of $.turn.step({ turnId: "t1", index: 0, model: "opus", messageCount: 1 })) {}
  await complete("t1");
  for await (const _ of $.turn.step({ turnId: "t2", index: 0, model: "opus", messageCount: 1 })) {}
  await complete("t2");
  expect(submitted).toHaveLength(1);
  expect(submitted[0]).toContain("Carry on");
});
