---
name: teach
description: Teach the user a topic over several sessions, using the current directory as a stateful teaching workspace.
disable-model-invocation: true
argument-hint: "What would you like to learn about?"
---

Teach the user a topic over several sessions. The current directory is the teaching workspace and holds all the state; its paths (`./lessons/` and the rest) resolve from the directory the skill was run in, and only the `*-FORMAT.md` links resolve from this skill's folder:

- `MISSION.md`: why the user is learning this. Every lesson traces back to it. Format: [MISSION-FORMAT.md](./MISSION-FORMAT.md).
- `RESOURCES.md`: the high-trust sources and communities teaching draws on. Format: [RESOURCES-FORMAT.md](./RESOURCES-FORMAT.md).
- `GLOSSARY.md`: the workspace's canonical terms; every lesson and record uses them. Format: [GLOSSARY-FORMAT.md](./GLOSSARY-FORMAT.md).
- `learning-records/0001-<slug>.md`: what the user has demonstrably learned, read to place the next lesson. Format: [LEARNING-RECORD-FORMAT.md](./LEARNING-RECORD-FORMAT.md).
- `lessons/0001-<slug>.html`: one self-contained lesson per file, the main unit of teaching.
- `reference/*.html`: compressed quick-reference sheets distilled from lessons (cheat sheets, syntax, algorithms, sequences), designed to print well. The user returns to these, rarely to lessons.
- `assets/`: components shared across lessons: the shared stylesheet first, then quiz widgets, simulators, diagram helpers.
- `NOTES.md`: the user's teaching preferences and your working notes.

Numbered files take the highest existing number plus one.

## What to do next

- **No clear mission**: interview the user about why they want this before teaching anything. Missions shift as the user learns; confirm a change with them, update `MISSION.md`, and write a learning record.
- **Thin `RESOURCES.md`**: find high-trust sources first. Teach from them rather than from your own recall, and cite them in lessons.
- **Otherwise**: teach what the user asked for, or else the most mission-relevant step in their zone of proximal development, judged from the learning records.

## Lessons

- Short enough to finish quickly, with one tangible win the user can build on.
- Beautiful and readable, Tufte-style, since the user will come back to review.
- Built from `assets/`: read it first, link the shared stylesheet, and put anything a second lesson could reuse into a component instead of inlining it.
- Built around one skill: only the knowledge that skill needs, with citations, then practice with immediate feedback, automatic where possible (in-browser quizzes and tasks, or guided real-world steps).
- Aimed at long-term retention over in-the-moment fluency: retrieval practice, spacing, and interleaving for skills practice.
- Quiz answer options have the same word count, and character count where possible, and the correct one's position varies across questions, so neither formatting nor order gives a clue.
- Each lesson links related lessons and reference sheets, recommends the single best primary source to read or watch, and reminds the user to bring follow-up questions to you.
- Open the lesson for the user with a CLI command when you can.
- Distill each lesson into `reference/` as you go: the user rarely revisits a lesson, but keeps coming back to its reference sheet.

## Wisdom

Some questions need real-world practice, not knowledge. Answer what you can, then point the user to a high-reputation community (forum, subreddit, class, local group) from `RESOURCES.md`. Respect an opt-out.
