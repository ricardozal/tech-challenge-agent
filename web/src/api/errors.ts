// Every message here reaches the user, so it is always Spanish (Constitution X). The agent's error
// body is Spanish by contract; actions_api `detail` and the HTTP status text are English and are
// never shown.
import { label } from '../labels'

export class ApiError extends Error {
  readonly status: number
  readonly code: string

  constructor(status: number, code: string, message: string) {
    super(message)
    this.status = status
    this.code = code
  }
}

export function errorForStatus(status: number): ApiError {
  const code = codeFor(status)
  return new ApiError(status, code, label('rejection_code', code))
}

function codeFor(status: number): string {
  if (status === 404) return 'not_found'
  if (status >= 500) return 'server_error'
  return 'request_failed'
}

// agent: {"error": {"code", "message"}} (Spanish); anything else: a Spanish text by status.
export async function toApiError(resp: Response): Promise<ApiError> {
  try {
    const body = await resp.json()
    if (body?.error?.code && body?.error?.message) {
      return new ApiError(resp.status, body.error.code, body.error.message)
    }
  } catch {
    // body without JSON
  }
  return errorForStatus(resp.status)
}

export async function request(input: string, init?: RequestInit): Promise<Response> {
  try {
    return await fetch(input, init)
  } catch {
    throw new ApiError(0, 'network_error', label('rejection_code', 'network_error'))
  }
}

/** Spanish text of any error, for the chat and the console. */
export function errorText(error: unknown): string {
  if (error instanceof ApiError) {
    const title = label('rejection_code', error.code)
    return title === error.message ? `${title}.` : `${title}. ${error.message}`
  }
  return 'Ocurrió un error inesperado.'
}
