import { useCallback, useEffect, useState } from 'react'
import { getCase, listEscalations } from '../api/actions'
import type { CaseView, Escalation } from '../api/types'
import { formatDate, label } from '../labels'

interface Row {
  escalation: Escalation
  caseView: CaseView
}

export default function Inbox() {
  const [rows, setRows] = useState<Row[] | null>(null)
  const [error, setError] = useState<string | null>(null)

  const load = useCallback(async () => {
    try {
      const open = await listEscalations('open')
      const cases = await Promise.all(open.map((e) => getCase(e.case_id)))
      const loaded = open.map((escalation, i) => ({ escalation, caseView: cases[i] }))
      loaded.sort((a, b) => b.escalation.created_at.localeCompare(a.escalation.created_at))
      setRows(loaded)
      setError(null)
    } catch {
      setError('No se pudo leer la bandeja.')
    }
  }, [])

  useEffect(() => {
    void load()
  }, [load])

  return (
    <section className="rounded-lg border border-slate-200 bg-white">
      <header className="flex items-center justify-between border-b border-slate-200 px-4 py-3">
        <h2 className="font-semibold">Bandeja de escalaciones</h2>
        <button type="button" onClick={() => void load()} className="text-sm text-indigo-700 hover:underline">
          Actualizar
        </button>
      </header>
      {error && <p className="px-4 py-3 text-sm text-red-700">{error}</p>}
      {rows?.length === 0 && (
        <p className="px-4 py-6 text-sm text-slate-600">
          No hay escalaciones abiertas. Corre el escenario «Documento fallido» enviando el recibo que no cuadra para generar
          una.
        </p>
      )}
      <ul className="divide-y divide-slate-100">
        {rows?.map(({ escalation, caseView }) => (
          <li key={escalation.id}>
            <a
              href={`/asesor?case=${caseView.id}`}
              data-testid={`inbox-item-${caseView.id}`}
              className="grid grid-cols-4 gap-2 px-4 py-3 text-sm hover:bg-slate-50"
            >
              <span className="font-medium">{caseView.state.client.full_name ?? 'Sin nombre'}</span>
              <span className="text-amber-800">{label('escalation', escalation.reason)}</span>
              <span>{label('stage', caseView.stage)}</span>
              <span className="text-slate-500">{formatDate(escalation.created_at)}</span>
            </a>
          </li>
        ))}
      </ul>
    </section>
  )
}
