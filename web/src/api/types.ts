// Mirror of the fields the web uses from packages/contracts (case.py, channel.py, actions.py).
// Money travels as decimal strings (R-17).

export type Stage = 'eligibility' | 'profiling' | 'simulation' | 'documents'
export type Status = 'active' | 'escalated' | 'ok_for_lender' | 'rejected' | 'cancelled'
export type Actor = 'agent' | 'advisor' | 'system'
export type DocumentType =
  | 'identification'
  | 'payslip'
  | 'bank_statement'
  | 'proof_of_address'
  | 'vehicle_invoice'
  | 'other'

export const FINAL_STATUSES: Status[] = ['ok_for_lender', 'rejected', 'cancelled']

export interface ExtractedField {
  value: string | number | boolean | null
  confidence: number
}

export interface DocumentRecord {
  id: string
  requested_type: DocumentType
  detected_type: DocumentType
  sha256: string
  is_test_specimen: boolean
  fields: Record<string, ExtractedField>
  received_at: string
}

export interface Validation {
  key: string
  type: string
  result: 'passed' | 'mismatch' | 'low_confidence'
  origin: 'system' | 'manual'
  detail: Record<string, unknown>
  evidence: string[]
  justification: string | null
  attempt: number
  policy_version: string
  at: string
}

export interface Decision {
  kind: string
  result: string
  reason: string | null
  actor: Actor
  inputs: Record<string, unknown>
  policy_version: string
  at: string
}

export interface MessageRef {
  id: string
  author: 'client' | 'agent'
  text: string
  intent: string | null
  at: string
}

export interface CreditOption {
  id: string
  pct_of_max: string
  financed_amount: string
  key_cost: string
  client_amount: string
  term_months: number
  annual_rate: string
  monthly_payment: string
  policy_version: string
}

export interface CaseState {
  client: { full_name: string | null; address: string | null; postal_code: string | null }
  declared: Record<string, unknown>
  vehicle: { make: string | null; model: string | null; year: number | null; spare_key: boolean | null }
  key_quote: { amount: string } | null
  profile: Record<string, unknown> | null
  options: CreditOption[]
  selected_option_id: string | null
  documents: DocumentRecord[]
  validations: Record<string, Validation>
  attempts: Record<string, number>
  decisions: Decision[]
  messages: MessageRef[]
  open_escalation_id: string | null
}

export interface CaseView {
  id: string
  stage: Stage
  status: Status
  version: number
  policy_version: string
  created_at: string
  updated_at: string
  state: CaseState
}

export interface CaseSummary {
  id: string
  stage: Stage
  status: Status
  version: number
  updated_at: string
}

export interface Escalation {
  id: string
  case_id: string
  reason: string
  evidence: Record<string, unknown>
  summary: string
  suggested_action: string
  agent_note: string | null
  status: 'open' | 'resolved'
  resolution: Record<string, unknown> | null
  created_at: string
  resolved_at: string | null
}

export interface AuditEntry {
  id: number
  case_id: string | null
  at: string
  actor: Actor
  on_behalf_of: 'client' | null
  tool: string
  stage_before: Stage | null
  status_before: Status | null
  stage_after: Stage | null
  status_after: Status | null
  idempotency_key: string
  expected_version: number | null
  case_version_after: number | null
  outcome: 'accepted' | 'rejected'
  rejection_code: string | null
  events: { type: string }[]
}

export interface MetricsReport {
  vehicle_rejections_by_reason: Record<string, number>
  false_ok_by_reason: Record<string, number>
  mismatches_by_type: Record<string, number>
  cases_with_key_quote: number
  audit_entries: number
}

export interface Rejection {
  code: string
  message: string
  details: Record<string, unknown>
}

export interface ToolResult {
  outcome: 'accepted' | 'rejected'
  case: { id: string; stage: Stage; status: Status; version: number } | null
  result: Record<string, unknown>
  events: { type: string }[]
  rejection: Rejection | null
  policy_version: string | null
}

export interface Policy {
  policy_version: string
  documents: { min_field_confidence: string }
}

export interface TurnResponse {
  message_id: string
  reply: string
  case: { stage: Stage; status: Status; version: number }
  tool_calls: { tool: string; outcome: string; rejection_code: string | null }[]
}

export interface CreateCaseResponse {
  case_id: string
  reply: string
  stage: Stage
  status: Status
}

export interface Conversation {
  case_id: string
  messages: { author: string; text: string }[]
  state: { last_question?: string | null }
}

// web/public/scenarios.json (specs/002-demo-web/contracts/web-scenarios.md)
export type DocumentSlotId = 'identification' | 'income_proof' | 'proof_of_address' | 'vehicle_invoice'

export interface SampleDocument {
  file: string
  requested_type: DocumentType
  label: string
  variant: 'ok' | 'mismatch'
}

export interface DocumentSlot {
  slot: DocumentSlotId
  question: string
  options: SampleDocument[]
}

export interface SuggestedMessage {
  stage: Stage
  question: string | null
  text: string
}

export interface Scenario {
  id: 'happy_path' | 'eligibility_rejection' | 'document_failed' | 'no_spare_key'
  title: string
  description: string
  client_name: string
  expected_results: Status[]
  source_scripts: string[]
  messages: SuggestedMessage[]
  documents: DocumentSlot[]
}

export interface ScenarioFile {
  generated_from: string[]
  scenarios: Scenario[]
}
