import type { CaseView, Escalation, Policy } from '../api/types'
import { formatDate, label } from '../labels'

interface Props {
  caseView: CaseView
  escalation: Escalation | null
  policy: Policy | null
}

function show(value: unknown): string {
  if (value === null || value === undefined) return '—'
  if (typeof value === 'object') return JSON.stringify(value)
  return String(value)
}

export default function CaseDetail({ caseView, escalation, policy }: Props) {
  const { state } = caseView
  // The threshold comes from the case's policy version (W-11); never a constant in the web.
  const threshold = policy ? Number(policy.documents.min_field_confidence) : null
  const validations = Object.values(state.validations)

  return (
    <div className="flex flex-col gap-4">
      <section className="rounded-lg border border-slate-200 bg-white p-4">
        <h1 className="text-lg font-semibold">{state.client.full_name ?? 'Cliente sin nombre'}</h1>
        <p className="mt-1 text-sm text-slate-600">
          Caso <span className="font-mono">{caseView.id}</span> · Etapa {label('stage', caseView.stage)} · Estado{' '}
          <strong data-testid="case-status">{label('status', caseView.status)}</strong> · Versión {caseView.version} · Política{' '}
          {caseView.policy_version}
        </p>
      </section>

      {escalation && (
        <section className="rounded-lg border border-amber-300 bg-amber-50 p-4 text-sm">
          <h2 className="font-semibold text-amber-900">
            Ticket · {label('escalation', escalation.reason)} ·{' '}
            {escalation.status === 'open' ? 'abierto' : 'resuelto'}
          </h2>
          <p className="mt-2 whitespace-pre-wrap" data-testid="ticket-summary">
            {escalation.summary}
          </p>
          <p className="mt-2">
            <span className="font-medium">Acción sugerida: </span>
            <span data-testid="ticket-suggested-action">{escalation.suggested_action}</span>
          </p>
          {escalation.agent_note && <p className="mt-2 text-slate-700">Nota del agente: {escalation.agent_note}</p>}
          <p className="mt-2 text-xs text-slate-500">Creado {formatDate(escalation.created_at)}</p>
        </section>
      )}

      <section data-testid="evidence" className="rounded-lg border border-slate-200 bg-white p-4">
        <h2 className="font-semibold">Evidencia</h2>

        <h3 className="mt-3 text-sm font-medium text-slate-700">Documentos</h3>
        {state.documents.length === 0 && <p className="text-sm text-slate-500">Sin documentos.</p>}
        <div className="mt-2 flex flex-col gap-3">
          {state.documents.map((doc) => {
            // Fields of the schema the reader did not find come back as null: listed apart, not as rows.
            const found = Object.entries(doc.fields).filter(([, f]) => f.value !== null && f.value !== '')
            const empty = Object.keys(doc.fields).filter((name) => !found.some(([n]) => n === name))
            return (
            <div key={doc.id} data-testid="document-record" className="rounded-md border border-slate-200 p-3 text-sm">
              <p className="font-medium">
                {label('document', doc.requested_type)}
                {doc.detected_type !== doc.requested_type && (
                  <span className="text-red-700"> · detectado: {label('document', doc.detected_type)}</span>
                )}
                {doc.is_test_specimen && (
                  <span className="ml-2 rounded bg-slate-200 px-1.5 py-0.5 text-xs text-slate-700">Documento de prueba</span>
                )}
              </p>
              <p className="text-xs text-slate-500">Recibido {formatDate(doc.received_at)}</p>
              <table className="mt-2 w-full text-xs">
                <tbody>
                  {found.map(([name, field]) => {
                    const low = threshold !== null && field.confidence < threshold
                    return (
                      <tr key={name} data-testid={`field-${doc.requested_type}-${name}`} className={low ? 'text-red-700' : ''}>
                        <td className="w-40 py-0.5 pr-2 text-slate-600">{label('field', name)}</td>
                        <td className="py-0.5 pr-2">{show(field.value)}</td>
                        <td className="w-36 py-0.5 text-right font-mono whitespace-nowrap">
                          {Math.round(field.confidence * 100)}%{low && ' · Confianza baja'}
                        </td>
                      </tr>
                    )
                  })}
                </tbody>
              </table>
              {empty.length > 0 && (
                <p data-testid={`empty-fields-${doc.requested_type}`} className="mt-1 text-xs text-slate-500">
                  Sin valor (confianza 0%, por debajo del umbral): {empty.map((name) => label('field', name)).join(', ')}
                </p>
              )}
            </div>
            )
          })}
        </div>

        <h3 className="mt-4 text-sm font-medium text-slate-700">Validaciones</h3>
        <table className="mt-2 w-full text-sm">
          <thead className="text-left text-xs text-slate-500">
            <tr>
              <th>Validación</th>
              <th>Resultado</th>
              <th>Origen</th>
              <th>Intento</th>
              <th>Detalle</th>
            </tr>
          </thead>
          <tbody>
            {validations.map((v) => (
              <tr key={v.key} className={v.result === 'passed' ? '' : 'text-red-700'}>
                <td className="py-1 pr-2">
                  {label('validation_type', v.type)} <span className="text-xs text-slate-500">({v.key})</span>
                </td>
                <td className="pr-2">{label('validation_result', v.result)}</td>
                <td className="pr-2">{label('origin', v.origin)}</td>
                <td className="pr-2">{v.attempt}</td>
                <td className="text-xs">
                  {Object.entries(v.detail)
                    .map(([k, value]) => `${k}: ${show(value)}`)
                    .join(' · ')}
                  {v.justification && ` · Justificación: ${v.justification}`}
                </td>
              </tr>
            ))}
          </tbody>
        </table>

        <h3 className="mt-4 text-sm font-medium text-slate-700">Mensajes del caso</h3>
        <ol className="mt-2 max-h-64 space-y-1 overflow-y-auto text-sm">
          {state.messages.map((m) => (
            <li key={m.id} className="whitespace-pre-wrap">
              <span className="font-medium">{m.author === 'client' ? 'Cliente' : 'Agente'}:</span> {m.text}
            </li>
          ))}
        </ol>
      </section>
    </div>
  )
}
