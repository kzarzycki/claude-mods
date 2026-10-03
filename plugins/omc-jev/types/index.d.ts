// omc-jev's noun: typed judgments over a state, the shape of TypeSafe's System One API.

/** Pick one option; `criteria` maps option label to its rubric (`null` when the label says enough). */
export type JevChoiceQuestion = { type: "choice"; instructions: string; criteria: Record<string, string | null> };
/** Probability that a yes/no condition holds. */
export type JevNoulQuestion = { type: "noul"; instructions: string; criteria?: { true?: string; false?: string } };
/** Position on ordered levels, lowest first; at least two. */
export type JevScoreQuestion = { type: "score"; instructions: string; criteria: readonly string[] };
export type JevQuestion = JevChoiceQuestion | JevNoulQuestion | JevScoreQuestion;

export type JevChoiceAnswer = { type: "choice"; choice: string; probabilities: Record<string, number>; confidence: number };
export type JevNoulAnswer = { type: "noul"; noul: number };
export type JevScoreAnswer = { type: "score"; score: number; probabilities: Record<string, number>; confidence: number };
export type JevAnswer = JevChoiceAnswer | JevNoulAnswer | JevScoreAnswer;

export type JevRequest = {
  /** Text, or named fields rendered one per tag. */
  state: string | Record<string, unknown>;
  /** Questions under caller-chosen ids; answers come back under the same ids. */
  questions: Record<string, JevQuestion>;
};
export type JevResult = { backend: "jev" | "claude"; model: string; answers: Record<string, JevAnswer> };

export type Jev = {
  judge: (request: JevRequest) => Promise<JevResult>;
};

declare module "claude-code" {
  interface EngineInterface {
    jev: Jev;
  }
}
