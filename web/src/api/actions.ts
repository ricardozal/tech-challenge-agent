// Case Actions API (specs/001-credit-agent-core/contracts/actions-api.md). The console writes only
// through callTool, as `advisor` (Principle IV); everything else is a read.
import { ACTIONS_URL } from '../config'
import { ApiError, request, toApiError } from './errors'
import type {
  AuditEntry,
  CaseSummary,
  CaseView,
  Escalation,
  MetricsReport,
  Policy,
  ToolResult,
} from './types'

async function get<T>(path: string): Promise<T> {
  const resp = await request(`${ACTIONS_URL}${path}`)
  if (!resp.ok) throw await toApiError(resp)
  return (await resp.json()) as T
}

export const getCase = (caseId: string) => get<CaseView>(`/cases/${caseId}`)
export const listCases = () => get<CaseSummary[]>('/cases')
export const getAudit = (caseId: string) => get<AuditEntry[]>(`/cases/${caseId}/audit`)
export const listEscalations = (status?: 'open' | 'resolved') =>
  get<Escalation[]>(status ? `/escalations?status=${status}` : '/escalations')
export const getEscalation = (id: string) => get<Escalation>(`/escalations/${id}`)
export const getPolicy = (version: string) => get<Policy>(`/policies/${encodeURIComponent(version)}`)
export const getMetrics = () => get<MetricsReport>('/metrics')

export async function callTool(
  name: string,
  caseId: string,
  expectedVersion: number,
  input: Record<string, unknown>,
  idempotencyKey: string,
): Promise<ToolResult> {
  const resp = await request(`${ACTIONS_URL}/tools/${name}`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json', 'X-Actor': 'advisor' },
    body: JSON.stringify({
      context: { case_id: caseId, idempotency_key: idempotencyKey, expected_version: expectedVersion },
      input,
    }),
  })
  const body = await resp.json().catch(() => null)
  if (body && typeof body === 'object' && 'outcome' in body) return body as ToolResult
  throw new ApiError(resp.status, `http_${resp.status}`, resp.statusText)
}

