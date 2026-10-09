import type { EngineInterface, Register } from "claude-code";

// self-compact: compaction at the end of a finished task rather than when the context overflows.
// The model decides whether and what to keep; this mod decides when to ask it. A mod can't compact
// inside a tool call or a prompt.submit (the host refuses), so everything happens at turn.complete:
// the compact_after_turn tool only records the request, and the compaction runs as `/compact`
// once the turn ends (`$.command.run` works headless too, unlike `$.session.compact`).

const TOOL = "compact_after_turn";
const TOOL_ID = "mcp__self-compact__compact_after_turn";
const DESCRIPTION =
  "Compact the conversation once this turn ends. Call it after finishing a task when the next task won't need this one's details. `focus` tells the summary what to keep for what comes next. Nothing changes until the turn ends, so finish your reply as usual.";

const FINISHED_TASK = {
  type: "noul",
  instructions:
    "Classify whether this assistant message ends a self-contained task: the work it was doing is done or reported, and it does not announce further steps it is about to take or ask the user to decide something.",
} as const;

// Without a decision model, re-nudge only after this much growth or this many turns since the last nudge.
const REARM_POINTS = 10;
const REARM_TURNS = 5;

type Ask = { decision: { ask: (r: object) => Promise<{ answers: Record<string, { type: string; noul?: number }> }> } };

/** Whether this turn looks like a finished task: the decision model when installed, else unknown. */
async function looksFinished($: EngineInterface, answer: string): Promise<boolean | undefined> {
  try {
    const r = await ($ as unknown as Ask).decision.ask({ purpose: "self-compact", state: answer.slice(-2000), questions: { done: FINISHED_TASK } });
    const a = r.answers.done;
    return a?.type === "noul" && (a.noul ?? 0) >= 0.5;
  } catch (err) {
    // decision-model is optional: without it $.decision is missing and the threshold rule decides.
    if (err instanceof TypeError && /decision/.test(err.message)) return undefined;
    return false;
  }
}

async function compact($: EngineInterface, method: string, focus: string) {
  const args = [method === "native" ? "" : method, focus].filter(Boolean).join(" ");
  $.ui.toast(`self-compact: compacting${focus ? ` (keep: ${focus.slice(0, 60)})` : ""}`);
  await $.command.run({ command: "compact", args }).catch(() => {});
}

export const register: Register = (on, options) => {
  const threshold = Number(options.threshold ?? 60);
  const toolFloor = Number(options.toolFloor ?? 20);
  const nudge = options.nudge !== false;
  const method = String(options.method || "native");
  const idleSeconds = Number(options.idleSeconds ?? 0);

  let requested: string | undefined; // the model's focus, once it called the tool this turn
  let nudgePending = false; // the next main turn answers our nudge
  let last: { percent: number; turn: number } | undefined; // the last nudge
  let turns = 0;
  let compactedAt = -2; // the turn the last compaction was queued at
  let generation = 0; // bumped by every prompt; an idle timer fires only if nothing came since

  on("session.start", async ($, e, next) => {
    await $.tool.register({
      name: TOOL,
      description: DESCRIPTION,
      inputSchema: { type: "object", properties: { focus: { type: "string", description: "What the summary must keep for the next task" } } },
    });
    return next(e);
  });

  // ponytail: matched by hand because the generated types list only MCP tools connected when the mod was saved.
  on("tool.call", async ($, e, next) => {
    if ((e.tool as string) !== TOOL_ID) return next(e);
    if (e.agentId) return { isError: true, result: "compact_after_turn is for the main conversation" };
    requested = String((e as unknown as { focus?: unknown }).focus ?? "").trim();
    return { result: "Compaction will run when this turn ends." };
  });

  on("prompt.submit", async ($, e, next) => {
    generation++;
    return next(e);
  });

  on("turn.complete", async ($, e, next) => {
    const done = await next(e);
    if (e.agentId || e.isAborted || e.reason !== "answer") return done;
    turns++;
    const answered = nudgePending;
    nudgePending = false;
    const percent = (await $.session.usage()).context.percent ?? 0;

    if (requested !== undefined) {
      const focus = requested;
      requested = undefined;
      // A second request right after one (say from a resumed turn) would compact twice.
      if (percent >= toolFloor && turns - compactedAt >= 2) {
        compactedAt = turns;
        void compact($, method, focus);
      }
      return done;
    }
    if (answered || percent < threshold) return done; // a declined nudge, or not full enough

    const idle = generation;
    if (idleSeconds > 0) {
      void (async () => {
        await $.clock.sleep(idleSeconds * 1000);
        if (generation !== idle || (await $.prompt.read()).text.trim()) return;
        if (((await $.session.usage()).context.percent ?? 0) >= threshold) await compact($, method, "");
      })().catch(() => {});
    }

    if (!nudge) return done;
    const finished = await looksFinished($, e.answer);
    // ponytail: without a decision model, a fill-only rule rearmed by growth or turns. Upgrade path: none needed if decision-model is installed.
    const rearmed = !last || percent >= last.percent + REARM_POINTS || turns - last.turn >= REARM_TURNS;
    if (finished === false || (finished === undefined && !rearmed) || (finished && last && turns - last.turn < 2)) return done;
    last = { percent, turn: turns };
    nudgePending = true;
    $.ui.toast("self-compact: asking the model whether to compact");
    void $.prompt
      .submit({
        text: `Context is ${Math.round(percent)}% full and this looks like the end of a task. If it is, call the ${TOOL} tool with a focus saying what the next task needs kept, then reply only "ok". If the work isn't finished, reply only "no".`,
      })
      .catch(() => {
        nudgePending = false;
      });
    return done;
  });
};
