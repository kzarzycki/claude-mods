import type { EngineInterface, Register } from "claude-code";
import { matchToolRule, parseRule, type Rule } from "./rules";

// omc-ttsr: oh-my-pi's time-traveling stream rules, at the seams Claude Code offers.
// - A rule with `condition:` is checked against what each tool call would write or run; a match
//   denies the call and hands the model the rule's body as the reason (omp aborts the stream
//   and retries; a denied call is the same lesson one step later).
// - A rule with `question:` is a yes/no question the judge ($.jev from omc-jev) answers about each
//   finished main-thread turn; a yes leaves the rule for the model's next turn.

const QUESTION_THRESHOLD = 0.5;

let rules: Rule[] = [];
let cwd = "";
const hits = new Map<string, number>();

/** Rule folders, lowest precedence first; a later file with the same name replaces an earlier one. */
async function ruleDirs($: EngineInterface, root: string): Promise<string[]> {
  const home = (await $.env.get("HOME")) ?? "";
  return [`${home}/.omp/agent/rules`, `${root}/.omp/rules`, `${home}/.claude/ttsr`, `${root}/.claude/ttsr`];
}

async function loadRules($: EngineInterface, root: string): Promise<Rule[]> {
  const byName = new Map<string, Rule>();
  for (const dir of await ruleDirs($, root)) {
    if (!(await $.fs.exists(dir))) continue;
    for (const entry of await $.fs.list(dir)) {
      if (entry.kind !== "file" || !entry.name.endsWith(".md")) continue;
      const path = `${dir}/${entry.name}`;
      const rule = parseRule(entry.name.replace(/\.md$/, ""), path, await $.fs.read(path));
      if (rule) byName.set(rule.name, rule);
    }
  }
  return [...byName.values()];
}

const tag = (rule: Rule) => `<ttsr-rule name="${rule.name}">\n${rule.body}\n</ttsr-rule>`;

export const register: Register = (on, options) => {
  const questionRules = options.questionRules !== false;
  const resume = options.questionAction === "resume";

  on("session.start", async ($, e, next) => {
    cwd = e.cwd;
    rules = await loadRules($, cwd);
    await $.command.register({ name: "ttsr", description: "omc-ttsr: list loaded rules and their hits; `/ttsr reload` rereads the rule folders", argumentHint: "[reload]" });
    return next(e);
  });

  on("tool.call", async ($, e, next) => {
    const hit = matchToolRule(rules, e.tool, e as unknown as Record<string, unknown>, cwd);
    if (!hit) return next(e);
    hits.set(hit.rule.name, (hits.get(hit.rule.name) ?? 0) + 1);
    $.ui.toast(`ttsr: ${hit.rule.name} blocked ${e.tool}`);
    return { deny: `TTSR rule "${hit.rule.name}" stopped this ${e.tool} call: it matched \`${hit.match.slice(0, 200)}\`. Follow the rule and try again.\n\n${tag(hit.rule)}` };
  });

  on("turn.complete", async ($, e, next) => {
    const done = await next(e);
    const asked = questionRules && !e.agentId && e.reason === "answer" && e.answer.trim() ? rules.filter(r => r.enabled && r.question) : [];
    if (asked.length === 0) return done;
    try {
      const ids = asked.map((r, i) => `r${i}`);
      const r = await $.jev.judge({
        state: { assistant_message: e.answer.slice(-4000) },
        questions: Object.fromEntries(asked.map((rule, i) => [ids[i]!, { type: "noul" as const, instructions: rule.question! }])),
      });
      const fired = asked.filter((_, i) => {
        const a = r.answers[ids[i]!];
        return a?.type === "noul" && a.noul >= QUESTION_THRESHOLD;
      });
      if (fired.length === 0) return done;
      for (const rule of fired) hits.set(rule.name, (hits.get(rule.name) ?? 0) + 1);
      const text = `The last answer broke ${fired.length === 1 ? "this rule" : "these rules"}. Apply ${fired.length === 1 ? "it" : "them"} from now on.\n\n${fired.map(tag).join("\n\n")}`;
      $.ui.toast(`ttsr: ${fired.map(f => f.name).join(", ")}`);
      if (resume) void $.prompt.submit({ text }).catch(() => {});
      else {
        const appended = await $.session.append({ message: { type: "user", content: [{ type: "text", text }] } });
        if (appended.deny !== undefined) $.ui.log(`omc-ttsr: rule note refused: ${appended.deny}`, { to: "debug" });
      }
    } catch (err) {
      $.ui.log(`omc-ttsr: question rules skipped: ${String(err)}`, { to: "debug" });
    }
    return done;
  });

  on("command.run", { command: "ttsr" }, async ($, e) => {
    if (e.args.trim() === "reload") rules = await loadRules($, cwd);
    if (rules.length === 0) return { text: `no TTSR rules in ${(await ruleDirs($, cwd)).join(", ")}` };
    return {
      text: rules
        .map(r => {
          const kind = [r.condition && `condition /${r.condition.source}/${r.tools.length ? ` on ${r.tools.join(",")}` : ""}`, r.question && `question "${r.question}"`].filter(Boolean).join("; ");
          return `${r.enabled ? "●" : "○"} ${r.name} (${hits.get(r.name) ?? 0} hits): ${kind}\n    ${r.source}`;
        })
        .join("\n"),
    };
  });
};
