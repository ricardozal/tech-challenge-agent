// Pairs the agent's last question with the scenario script (W-06): the recorded LLM answers are
// keyed by (stage, question, text), so the suggestion is the script line for that exact question.
import type { DocumentSlot, Scenario, Stage, SuggestedMessage } from '../api/types'

export function suggestMessage(scenario: Scenario, stage: Stage, lastQuestion: string | null): SuggestedMessage | null {
  if (!lastQuestion) return null
  return scenario.messages.find((m) => m.question === lastQuestion && m.stage === stage) ?? null
}

export function requestedSlot(scenario: Scenario, lastQuestion: string | null): DocumentSlot | null {
  if (!lastQuestion) return null
  return scenario.documents.find((d) => d.question === lastQuestion) ?? null
}
