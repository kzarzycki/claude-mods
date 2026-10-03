import type { EngineInterface, Register } from "claude-code";

type Question = Parameters<EngineInterface["decision"]["ask"]>[0]["questions"][string];

// cm-resume: a main-thread turn whose last step was text only is asked about: did it say it would
// act and then stop? A yes starts one turn telling it to carry on, at most once per prompt.
// Question copied from oh-my-pi (session/unexpected-stop-classifier.ts).

export const UNEXPECTED_STOP: Question = {
  type: "noul",
  instructions: "Classify whether this assistant message is an unexpected stop: it says it will act, continue working, or call a tool, then ends without doing so.",
  criteria: {
    true: 'Unexpected stops:\n- "I should do the same for the JS eval worker. Doing that now."\n- "Let me run the tests next."\n- "I\'ll fix that now."\n- "Should I do that for you?"',
    false: 'Not an unexpected stop:\n- "I\'ve completed the task."\n- "Is there anything else I can help with?"\n- "The fix is done and tests pass."',
  },
};
const RESUME_TEXT = "You ended the turn right after saying you would act. Carry on with what you said you would do.";

export const register: Register = (on, options) => {
  const threshold = Number(options.threshold ?? 0.5);
  let last: { turnId: string; answer: string; isTextOnly: boolean } | undefined;
  let resumes = 0;

  on("prompt.submit", async ($, e, next) => {
    if (e.origin?.kind !== "plugin") resumes = 0;
    return next(e);
  });

  on("turn.step", async function* ($, e, next) {
    const r = yield* next(e);
    if (!e.agentId) last = { turnId: e.turnId, answer: r.answer, isTextOnly: r.toolUses.length === 0 && r.stopReason === "end_turn" };
    return r;
  });

  on("turn.complete", async ($, e, next) => {
    const done = await next(e);
    const step = last;
    if (e.agentId || e.reason !== "answer" || e.isAborted || !step || step.turnId !== e.turnId || !step.isTextOnly || !step.answer.trim() || resumes >= 1) return done;
    try {
      const r = await $.decision.ask({ purpose: "stop", state: step.answer.slice(-2000), questions: { stop: UNEXPECTED_STOP } });
      const a = r.answers.stop;
      if (a?.type === "noul" && a.noul >= threshold) {
        resumes++;
        $.ui.toast("cm-resume: the turn stopped mid-promise; resuming");
        void $.prompt.submit({ text: RESUME_TEXT }).catch(() => {});
      }
    } catch {
      // Recorded in /decision's log; the turn just ends.
    }
    return done;
  });
};
