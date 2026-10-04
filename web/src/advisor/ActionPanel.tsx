// Advisor actions: the same catalog as the agent, as `advisor` (FR-068, FR-069). Permissions are
// decided by actions_api; this panel only hides what makes no sense for the case status.
import { useRef, useState, type FormEvent } from 'react'
import { callTool } from '../api/actions'
import { errorText } from '../api/errors'
import type { CaseView, Status, Validation } from '../api/types'
import { label } from '../labels'

type Tool =
  | 'request_correction'
  | 'verify_validation_manually'
  | 'reject_case'
  | 'return_to_agent'
  | 'cancel_case'
  | 'revoke_ok'

const BY_STATUS: Record<Status, Tool[]> = {
  escalated: ['verify_validation_manually', 'request_correction', 'return_to_agent', 'reject_case', 'cancel_case'],
  active: ['cancel_case'],
  ok_for_lender: ['revoke_ok'],
  rejected: [],
  cancelled: [],
}

const FORM: Record<Tool, { validation: boolean; text: string; required: boolean; minLength: number }> = {
  request_correction: { validation: true, text: 'Mensaje para el cliente', required: true, minLength: 1 },
  verify_validation_manually: { validation: true, text: 'Justificación', required: true, minLength: 10 },
  reject_case: { validation: false, text: 'Motivo del rechazo', required: true, minLength: 3 },
  return_to_agent: { validation: false, text: 'Nota para el agente', required: false, minLength: 0 },
  cancel_case: { validation: false, text: 'Motivo de la cancelación', required: true, minLength: 3 },
  revoke_ok: { validation: false, text: 'Motivo de la revocación', required: true, minLength: 3 },
}

function input(tool: Tool, text: string, validation: Validation | undefined): Record<string, unknown> {
  switch (tool) {
    case 'request_correction':
      return { validation_key: validation!.key, message_to_client: text }
    case 'verify_validation_manually':
      return { validation_key: validation!.key, justification: text, evidence: [...validation!.evidence, 'consola_asesor'] }
    case 'return_to_agent':
      return { note: text }
    case 'reject_case':
    case 'cancel_case':
    case 'revoke_ok':
      return { reason: text }
  }
}

interface Props {
  caseView: CaseView
  onChanged: () => Promise<void>
}

export default function ActionPanel({ caseView, onChanged }: Props) {
  const [tool, setTool] = useState<Tool | null>(null)
  const [validationKey, setValidationKey] = useState('')
  const [text, setText] = useState('')
  const [key, setKey] = useState('')
  const [sending, setSending] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [done, setDone] = useState<string | null>(null)
  const inFlight = useRef(false) // a double click submits once

  const tools = BY_STATUS[caseView.status]
  const pending = Object.values(caseView.state.validations).filter((v) => v.result !== 'passed')

  // One idempotency key per attempt: new when the form opens or changes, and after a rejection (the
  // case is re-read, so the next submit is another attempt on another version). A resend after a
  // network error reuses it, so the action runs at most once (FR-069).
  function open(next: Tool) {
    setTool(next)
    setValidationKey(pending[0]?.key ?? '')
    setText('')
    setKey(crypto.randomUUID())
    setError(null)
    setDone(null)
  }

  function edit(update: () => void) {
    update()
    setKey(crypto.randomUUID())
  }

  async function submit(event: FormEvent) {
    event.preventDefault()
    if (!tool || inFlight.current) return
    const form = FORM[tool]
    const validation = pending.find((v) => v.key === validationKey)
    if (form.validation && !validation) return setError('Elige una validación.')
    if (form.required && text.trim().length < form.minLength)
      return setError(`${form.text}: escribe al menos ${form.minLength} caracteres.`)
    inFlight.current = true
    setSending(true)
    setError(null)
    try {
      const result = await callTool(tool, caseView.id, caseView.version, input(tool, text.trim(), validation), key)
      if (result.outcome === 'rejected') {
        const code = result.rejection?.code
        setError(`${label('rejection_code', code)}. ${result.rejection?.message ?? ''}`)
        setKey(crypto.randomUUID())
      } else {
        setDone(`${label('tool', tool)}: acción registrada.`)
        setTool(null)
      }
      await onChanged()
    } catch (e) {
      setError(errorText(e))
    } finally {
      inFlight.current = false
      setSending(false)
    }
  }

  return (
    <section className="rounded-lg border border-slate-200 bg-white p-4">
      <h2 className="font-semibold">Acciones del asesor</h2>
      {tools.length === 0 && <p className="mt-2 text-sm text-slate-500">El caso está cerrado; no hay acciones disponibles.</p>}
      <div className="mt-2 flex flex-wrap gap-2">
        {tools.map((t) => (
          <button
            key={t}
            type="button"
            data-testid={`action-${t}`}
            onClick={() => open(t)}
            className={`rounded-md border px-3 py-1 text-sm ${tool === t ? 'border-indigo-500 bg-indigo-50' : 'border-slate-300 hover:bg-slate-50'}`}
          >
            {label('tool', t)}
          </button>
        ))}
      </div>

      {tool && tools.includes(tool) && (
        <form onSubmit={submit} className="mt-3 flex flex-col gap-2 text-sm">
          {FORM[tool].validation && (
            <label className="flex flex-col gap-1">
              Validación
              <select
                data-testid="action-validation"
                value={validationKey}
                onChange={(e) => edit(() => setValidationKey(e.target.value))}
                className="rounded border border-slate-300 px-2 py-1"
              >
                {pending.map((v) => (
                  <option key={v.key} value={v.key}>
                    {label('validation_type', v.type)} ({v.key}) · {label('validation_result', v.result)}
                  </option>
                ))}
              </select>
            </label>
          )}
          <label className="flex flex-col gap-1">
            {FORM[tool].text}
            <textarea
              data-testid="action-text"
              value={text}
              onChange={(e) => edit(() => setText(e.target.value))}
              rows={3}
              className="rounded border border-slate-300 px-2 py-1"
            />
          </label>
          <button
            type="submit"
            data-testid="action-submit"
            disabled={sending}
            className="self-start rounded-md bg-indigo-600 px-4 py-1.5 text-white disabled:opacity-50"
          >
            {sending ? 'Enviando…' : `${label('tool', tool)} como asesor`}
          </button>
        </form>
      )}
      {error && (
        <p data-testid="action-error" className="mt-2 text-sm text-red-700">
          {error}
        </p>
      )}
      {done && <p className="mt-2 text-sm text-green-700">{done}</p>}
    </section>
  )
}
