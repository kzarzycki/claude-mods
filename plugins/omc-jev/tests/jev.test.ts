import { expect, test } from "claude-code/testing";

const cmd = (command: string, args = "") => ({ command, args, origin: { kind: "composer" as const }, presentation: { isFullscreen: false, columns: 80 } });
const usage = { input_tokens: 1, output_tokens: 1, cache_read_input_tokens: 0, cache_creation_input_tokens: 0 };
const stepResult = (turnId: string, index: number, answer: string, toolUses: { name: string; input: unknown }[] = []) => ({
  turnId,
  index,
  answer,
  toolUses,
  stopReason: (toolUses.length ? "tool_use" : "end_turn") as "tool_use" | "end_turn",
  usage: null,
});

test("a consumer plugin gets typed answers from $.jev with the Claude text judge", {
  plugins: [
    {
      name: "consumer",
      register: on => {
        on("command.run", { command: "probe" }, async $ => {
          const r = await $.jev.judge({
            state: "rename foo to bar in one file",
            questions: {
              size: { type: "choice", instructions: "How big?", criteria: { small: null, large: null } },
              risky: { type: "noul", instructions: "Is it risky?" },
            },
          });
          return { text: JSON.stringify(r) };
        });
      },
    },
  ],
}, async ($, on) => {
  let system = "";
  on("env.get", () => ({ value: undefined }));
  on("model.complete", ($, e) => {
    system = e.system ?? "";
    return { value: { isAnswered: true, text: "size: small\nrisky: no", usage } };
  });
  const r = JSON.parse((await $.command.run(cmd("probe"))).text ?? "{}");
  expect(r.backend).toBe("claude");
  expect(r.answers.size).toEqual({ type: "choice", choice: "small", probabilities: { small: 1, large: 0 }, confidence: 1 });
  expect(r.answers.risky).toEqual({ type: "noul", noul: 0 });
  expect(system).toContain("Question `size`");
});

test("with a key, questions go to Jev verbatim", { options: { apiKey: "k", endpoint: "openrouter" } }, async ($, on) => {
  let sent: any;
  on("command.register", ($, e) => ({ value: { command: e.name } }));
  on("http.fetch", ($, e) => {
    sent = { url: e.url, auth: e.init?.headers?.Authorization, body: JSON.parse(e.init?.body ?? "{}") };
    return { value: { status: 200, ok: true, headers: {}, text: JSON.stringify({ model: "jev-1", answers: { effort: { type: "choice", choice: "high", probabilities: { high: 0.8 }, confidence: 0.7 } } }) } };
  });
  const out = await $.command.run(cmd("jev", "ask fix the flaky test"));
  expect(out.text).toContain('"choice":"high"');
  expect(sent.url).toBe("https://openrouter.ai/api/alpha/decisions");
  expect(sent.auth).toBe("Bearer k");
  expect(sent.body.model).toBe("~typesafe/jev-latest");
  expect(sent.body.questions.effort.type).toBe("choice");
});

test("auto effort: the judged level is the effort of every main-thread step of that turn", async ($, on) => {
  const efforts: unknown[] = [];
  on("env.get", () => ({ value: undefined }));
  on("model.complete", () => ({ value: { isAnswered: true, text: "xhigh", usage } }));
  on("prompt.submit", ($, e) => ({ text: e.text }));
  on("ui.status", () => ({ value: undefined }));
  on("turn.step", async function* ($, e) {
    efforts.push(e.effort);
    return stepResult(e.turnId, e.index, "ok", [{ name: "Read", input: {} }]);
  });
  await $.prompt.submit({ text: "why does the cache go stale under load?", wait: false, origin: { kind: "composer" } });
  for (const index of [0, 1]) for await (const _ of $.turn.step({ turnId: "t1", index, model: "opus", messageCount: 1 })) {}
  for await (const _ of $.turn.step({ turnId: "t2", index: 0, model: "opus", messageCount: 1 })) {}
  expect(efforts).toEqual(["xhigh", "xhigh", undefined]);
});

test("an unexpected stop gets one resume prompt", { options: { autoEffort: false } }, async ($, on) => {
  const submitted: string[] = [];
  on("env.get", () => ({ value: undefined }));
  on("model.complete", () => ({ value: { isAnswered: true, text: "YES", usage } }));
  on("ui.toast", () => ({ value: undefined }));
  on("prompt.submit", ($, e) => {
    submitted.push(e.text);
    return { text: e.text };
  });
  on("turn.step", async function* ($, e) {
    return stepResult(e.turnId, e.index, "Let me run the tests next.");
  });
  on("turn.complete", ($, e) => ({ text: e.answer }));
  const complete = (turnId: string) => $.turn.complete({ turnId, answer: "Let me run the tests next.", durationMs: 1, isAborted: false, reason: "answer" });
  for await (const _ of $.turn.step({ turnId: "t1", index: 0, model: "opus", messageCount: 1 })) {}
  await complete("t1");
  for await (const _ of $.turn.step({ turnId: "t2", index: 0, model: "opus", messageCount: 1 })) {}
  await complete("t2");
  expect(submitted).toHaveLength(1);
  expect(submitted[0]).toContain("Carry on");
});
