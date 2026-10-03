import { expect, test } from "claude-code/testing";

const cmd = (command: string, args = "") => ({ command, args, origin: { kind: "composer" as const }, presentation: { isFullscreen: false, columns: 80 } });
const usage = { input_tokens: 1, output_tokens: 1, cache_read_input_tokens: 0, cache_creation_input_tokens: 0 };

test("a consumer plugin gets typed answers from $.decision with the Claude text judge", {
  plugins: [
    {
      name: "consumer",
      register: on => {
        on("command.run", { command: "probe" }, async $ => {
          const r = await $.decision.ask({
            purpose: "probe",
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

test("with a key, questions go to the System One endpoint verbatim", { options: { apiKey: "k", endpoint: "openrouter" } }, async ($, on) => {
  let sent: any;
  on("command.register", ($, e) => ({ value: { command: e.name } }));
  on("http.fetch", ($, e) => {
    sent = { url: e.url, auth: e.init?.headers?.Authorization, body: JSON.parse(e.init?.body ?? "{}") };
    return { value: { status: 200, ok: true, headers: {}, text: JSON.stringify({ model: "jev-1", answers: { q: { type: "noul", noul: 0.8 } } }) } };
  });
  const out = await $.command.run(cmd("decision", "ask Is it flaky? -- the test fails one run in ten"));
  expect(out.text).toContain('"noul":0.8');
  expect(sent.url).toBe("https://openrouter.ai/api/alpha/decisions");
  expect(sent.auth).toBe("Bearer k");
  expect(sent.body.model).toBe("~typesafe/jev-latest");
  expect(sent.body.questions.q.type).toBe("noul");
  expect(sent.body.purpose).toBeUndefined();
});

test("any endpoint speaking the protocol can be the backend", { options: { backend: "system-one", endpoint: "https://decide.example/v1/systemone", model: "my-model", apiKey: "k" } }, async ($, on) => {
  let sent: any;
  on("command.register", ($, e) => ({ value: { command: e.name } }));
  on("http.fetch", ($, e) => {
    sent = { url: e.url, body: JSON.parse(e.init?.body ?? "{}") };
    return { value: { status: 200, ok: true, headers: {}, text: JSON.stringify({ model: "my-model", answers: { q: { type: "noul", noul: 0.1 } } }) } };
  });
  const out = await $.command.run(cmd("decision", "ask Is it risky? -- rename a variable"));
  expect(out.text).toContain("via system-one/my-model");
  expect(sent.url).toBe("https://decide.example/v1/systemone");
  expect(sent.body.model).toBe("my-model");
  expect((await $.command.run(cmd("decision"))).text).toContain("ask: q=0.10 (system-one/my-model)");
});
