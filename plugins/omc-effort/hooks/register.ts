import type { EngineInterface, Register } from "claude-code";

type Question = Parameters<EngineInterface["decision"]["ask"]>[0]["questions"][string];

// omc-effort: asks the decision model how open-ended each prompt is and runs the turn it starts at
// that effort. Levels and wording copied from oh-my-pi (auto-thinking/classifier.ts), measured there.

const LEVELS = {
  low: "One obvious solution, mechanically applied: target, mapping, or fix given.",
  medium: "A few candidates in a localized area, or one small trap: which line breaks a test, one boundary case.",
  high: "Several viable designs or candidate causes: API shape, policy choice, a known cause whose fix needs a design choice.",
  xhigh: "Open cause of flaky, concurrent, or stale behavior; solutions that are easy to get subtly wrong (races, invariants, cross-version compatibility).",
  max: "Meets xhigh and at least one of: no reproduction to work from, irreversible or data-loss operation, or a live cutover that must stay correct while running. xhigh is required; difficulty alone is insufficient.",
} as const;
type Effort = keyof typeof LEVELS;
const ORDER = Object.keys(LEVELS) as Effort[];

export function effortQuestion(ceiling: Effort): Question {
  const allowed = ORDER.slice(0, ORDER.indexOf(ceiling) + 1);
  return {
    type: "choice",
    instructions:
      "The state is a user's request to a coding agent. Judge how open-ended its problem is: whether the fix or design is given, or which causes or designs remain open. Choose the reasoning effort that needs, judging inherent difficulty rather than phrasing politeness or verbosity. Volume of work never raises it. If torn between levels, choose the lower one" +
      (allowed.includes("max") ? ", except between xhigh and max: a request meeting the max conditions takes max." : "."),
    criteria: Object.fromEntries(allowed.map(l => [l, LEVELS[l]])),
  };
}

export const register: Register = (on, options) => {
  const ceiling = (ORDER.includes(options.maxEffort as Effort) ? options.maxEffort : "xhigh") as Effort;
  let pending: Effort | undefined;
  let turn: string | undefined;
  let applied: Effort | undefined;

  on("prompt.submit", async ($, e, next) => {
    // A prompt a plugin queued (a resume, a continuation) keeps the effort already chosen.
    if (e.origin?.kind === "plugin" || !e.text.trim() || e.text.trimStart().startsWith("/")) return next(e);
    try {
      const r = await $.decision.ask({ purpose: "effort", state: e.text, questions: { effort: effortQuestion(ceiling) } });
      const a = r.answers.effort;
      if (a?.type === "choice") pending = a.choice as Effort;
    } catch {
      // The decision log (/decision) records the failure; the turn runs at the session's effort.
    }
    return next(e);
  });

  on("turn.step", async function* ($, e, next) {
    if (e.agentId) return yield* next(e);
    if (pending && e.index === 0) {
      [turn, applied, pending] = [e.turnId, pending, undefined];
      $.ui.status(`effort ${applied}`);
    }
    return yield* next(applied && e.turnId === turn ? { ...e, effort: applied } : e);
  });

  on("session.start", async ($, e, next) => {
    await $.command.register({ name: "effort-rate", description: "omc-effort: rate a prompt's effort without running it", argumentHint: "<prompt>" });
    return next(e);
  });

  on("command.run", { command: "effort-rate" }, async ($, e) => {
    if (!e.args.trim()) return { text: `usage: /effort-rate <prompt> (ceiling ${ceiling})` };
    const r = await $.decision.ask({ purpose: "effort", state: e.args.trim(), questions: { effort: effortQuestion(ceiling) } });
    return { text: `effort: ${JSON.stringify(r.answers.effort)} via ${r.backend}/${r.model}` };
  });
};
