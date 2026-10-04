export class ApiError extends Error {
  readonly status: number
  readonly code: string

  constructor(status: number, code: string, message: string) {
    super(message)
    this.status = status
    this.code = code
  }
}

// agent: {"error": {"code", "message"}}; actions_api reads: {"detail": "..."}; network: status 0.
export async function toApiError(resp: Response): Promise<ApiError> {
  let code = `http_${resp.status}`
  let message = resp.statusText
  try {
    const body = await resp.json()
    if (body?.error) {
      code = body.error.code ?? code
      message = body.error.message ?? message
    } else if (typeof body?.detail === 'string') {
      message = body.detail
    }
  } catch {
    // body without JSON: keep the status text
  }
  return new ApiError(resp.status, code, message)
}

export async function request(input: string, init?: RequestInit): Promise<Response> {
  try {
    return await fetch(input, init)
  } catch {
    throw new ApiError(0, 'network_error', 'No hubo respuesta del servidor.')
  }
}
