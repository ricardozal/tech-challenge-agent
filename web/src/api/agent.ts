// Agent channel (specs/001-credit-agent-core/contracts/agent-channel.md). The chat writes only here.
import { AGENT_URL } from '../config'
import { request, toApiError } from './errors'
import type { Conversation, CreateCaseResponse, SampleDocument, TurnResponse } from './types'

async function json<T>(resp: Response): Promise<T> {
  if (!resp.ok) throw await toApiError(resp)
  return (await resp.json()) as T
}

export async function createCase(idempotencyKey: string): Promise<CreateCaseResponse> {
  return json(await request(`${AGENT_URL}/cases`, { method: 'POST', headers: { 'Idempotency-Key': idempotencyKey } }))
}

export async function sendMessage(caseId: string, text: string, idempotencyKey: string): Promise<TurnResponse> {
  return json(
    await request(`${AGENT_URL}/cases/${caseId}/messages`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json', 'Idempotency-Key': idempotencyKey },
      body: JSON.stringify({ text }),
    }),
  )
}

export async function sendDocument(
  caseId: string,
  sample: SampleDocument,
  idempotencyKey: string,
): Promise<TurnResponse> {
  const file = await request(`/${sample.file}`)
  if (!file.ok) throw await toApiError(file)
  const form = new FormData()
  form.append('file', await file.blob(), sample.file.split('/').pop())
  form.append('requested_type', sample.requested_type)
  return json(
    await request(`${AGENT_URL}/cases/${caseId}/documents`, {
      method: 'POST',
      headers: { 'Idempotency-Key': idempotencyKey },
      body: form,
    }),
  )
}

export async function getConversation(caseId: string): Promise<Conversation> {
  return json(await request(`${AGENT_URL}/cases/${caseId}/conversation`))
}
