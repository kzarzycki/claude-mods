---
name: grilling
description: Interview the user in rounds of questions until every decision in a plan, design, or idea is settled. Use when the user wants to stress-test their thinking or uses a "grill" phrase such as "grill me".
---

Interview the user until you share one understanding of every decision the idea contains. Treat it as a design tree: each decision branches into the decisions that hang off it.

Work in rounds. Each round, ask the whole frontier (every question whose prerequisites are settled), numbered, each with your recommended answer:

```
❓ **Q1** - **<question title>**: <question body, possibly several paragraphs, with its options>

➡️ <your recommended answer>

---

❓ **Q2** - **<question title>**: <question body>

➡️ <your recommended answer>
```

Word each question so that "yes" accepts your recommended answer.

Then wait for the answers, recompute the frontier, and ask the next round. A question that depends on another one still open this round waits for a later round.

Facts are yours to find, never the user's; decisions are the user's. Look facts up in the code, docs and tools while you ask the rest of the frontier (hand a lookup to a background agent, started with a fresh context window rather than a fork of yours, when it would flood your context), and hold back only the questions that depend on it.

The session ends when the frontier is empty and nothing is silently assumed. Act on it only after the user confirms the shared understanding.
