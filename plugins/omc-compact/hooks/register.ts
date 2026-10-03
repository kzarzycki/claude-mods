import type { EngineInterface, Register, SessionCompactResult, SessionMessage } from "claude-code";
import { messageTokens, shake } from "./shake";

// omc-compact: oh-my-pi's shake and handoff as Claude Code compaction methods.
// `/compact shake` and `/compact handoff [focus]` pick one by name (the built-in /compact passes its
// text through as `instructions`); `autoMethod` picks what runs when the context fills. There are
// no /shake or /handoff commands: a command hook may not start a compaction.

// oh-my-pi's prompts (agent/src/compaction/prompts/handoff-document.md, handoff-summary-context.md).
const HANDOFF_PROMPT = `<critical>
Write a handoff document for another instance of yourself.
The handoff MUST be sufficient for seamless continuation without access to this conversation.
Output ONLY the handoff document. No preamble, no commentary, no wrapper text.
</critical>

<instruction>
Capture exact technical state, not abstractions.
- File paths, symbol names, commands run
- Test results, observed failures
- Decisions made
- Partial work affecting the next step
Register: address the successor directly in the imperative ("Fix X", "Run Y") — never first person ("I need to…", "my attempt…").
The handoff mechanism is invisible to the document: NEVER list writing, generating, or delivering a handoff/summary/context document as progress or a next step. Progress and Next Steps cover the user's task only.
</instruction>

<output>
Use exactly this structure:

## Goal
## Constraints & Preferences
## Progress
### Done
### In Progress
### Pending
## Key Decisions
## Critical Context
## Next Steps
</output>`;

const handoffContext = (doc: string) => `Context replaced. The <handoff> below is a handoff document a prior instance of you wrote from the full conversation. It is your own working memory, not user input.
- First person inside it refers to you (the prior instance).
- "Next Steps" is your own resumed plan; re-check it against the latest user message before acting.
- The handoff already exists and is complete: NEVER write another handoff document unless the user explicitly asks.
MUST build on prior work; NEVER duplicate prior work.

<handoff>
${doc}
</handoff>`;

const total = (ms: readonly SessionMessage[]) => ms.reduce((n, m) => n + messageTokens(m), 0);

async function stateDir($: EngineInterface): Promise<string> {
  return `${(await $.env.get("HOME")) ?? "/tmp"}/.claude/omc-compact/${await $.session.id()}`;
}

async function runShake($: EngineInterface, messages: readonly SessionMessage[], protectTokens: number): Promise<{ result: SessionCompactResult; saved: number }> {
  const r = shake(messages, protectTokens, await stateDir($));
  for (const o of r.offloads) await $.fs.write(o.path, o.text);
  return { result: { messages: r.messages, tokensBefore: total(messages), tokensAfter: total(r.messages) }, saved: r.saved };
}

/** The conversation as plain text, for a handoff written without the prompt cache. */
function transcript(messages: readonly SessionMessage[]): string {
  const cap = (t: string, n: number) => (t.length > n ? `${t.slice(0, n)} …[${t.length - n} more]` : t);
  return messages
    .map(m => [
      m.text && `${m.role}: ${m.text}`,
      ...m.toolUses.map(u => `${m.role} called ${u.tool}(${cap(JSON.stringify(u.input), 300)})${u.text ? ` -> ${cap(u.text, 1500)}` : ""}`),
    ].filter(Boolean).join("\n"))
    .filter(Boolean)
    .join("\n\n")
    .slice(-200_000);
}

async function runHandoff($: EngineInterface, messages: readonly SessionMessage[], focus: string): Promise<SessionCompactResult | undefined> {
  const ask = focus ? `${HANDOFF_PROMPT}\n\n<instruction>\nAdditional focus: ${focus}\n</instruction>` : HANDOFF_PROMPT;
  // Fork first: it asks over the main thread's last request, so the prompt cache serves the
  // prefix. With no request to fork (a session just resumed), write it from the messages.
  let r = await $.model.fork({ prompt: ask });
  if (!r.isAnswered) r = await $.model.complete({ model: await $.session.model(), system: ask, prompt: `<conversation>\n${transcript(messages)}\n</conversation>\n\nWrite the handoff document now.`, maxTokens: 8000 });
  if (!r.isAnswered || !r.text.trim()) return undefined;
  await $.fs.write(`${await stateDir($)}/handoff-${await $.clock.now()}.md`, r.text);
  return { messages: [{ role: "user", text: handoffContext(r.text.trim()), toolUses: [] }], usage: r.usage };
}

export const register: Register = (on, options) => {
  const autoMethod = String(options.autoMethod ?? "native");
  const protectTokens = Number(options.protectTokens ?? 16000);
  const minSavings = Number(options.minSavings ?? 4000);

  on("session.compact", async ($, e, next) => {
    if (e.trigger === "precompute" || e.agentId) return next(e);
    const named = /^\s*(shake|handoff)\b\s*([\s\S]*)$/.exec(e.instructions ?? "");
    const method = named ? named[1]! : e.trigger === "auto" ? autoMethod : "native";
    if (method === "shake") {
      // A shake the person asked for keeps only a small tail, as oh-my-pi's manual /shake does.
      const { result, saved } = await runShake($, e.messages, named ? Math.min(protectTokens, 4000) : protectTokens);
      if (!named && saved < minSavings) return next(e);
      $.ui.toast(`omc-compact: shake saved ~${saved} tokens`);
      return saved > 0 ? result : { skip: "nothing large enough to shake" };
    }
    if (method === "handoff") {
      const result = await runHandoff($, e.messages, named?.[2]?.trim() ?? "");
      if (result) return result;
      $.ui.toast("omc-compact: handoff failed; using native compaction");
      return next({ ...e, instructions: named?.[2]?.trim() || undefined });
    }
    return next(e);
  });
};
