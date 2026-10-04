import { useCallback, useEffect, useState } from 'react'
import { listCases } from '../api/actions'
import type { CaseSummary } from '../api/types'
import { formatDate, label } from '../labels'

export default function CaseList() {
  const [cases, setCases] = useState<CaseSummary[] | null>(null)
  const [error, setError] = useState<string | null>(null)

  const load = useCallback(async () => {
    try {
      const all = await listCases()
      setCases([...all].sort((a, b) => b.updated_at.localeCompare(a.updated_at)))
      setError(null)
    } catch {
      setError('No se pudo leer la lista de casos.')
    }
  }, [])

  useEffect(() => {
    void load()
  }, [load])

  return (
    <section className="rounded-lg border border-slate-200 bg-white">
      <header className="flex items-center justify-between border-b border-slate-200 px-4 py-3">
        <h2 className="font-semibold">Casos</h2>
        <button type="button" onClick={() => void load()} className="text-sm text-indigo-700 hover:underline">
          Actualizar
        </button>
      </header>
      {error && <p className="px-4 py-3 text-sm text-red-700">{error}</p>}
      <ul className="max-h-96 divide-y divide-slate-100 overflow-y-auto">
        {cases?.map((c) => (
          <li key={c.id}>
            <a
              href={`/asesor?case=${c.id}`}
              data-testid={`case-row-${c.id}`}
              className="grid grid-cols-4 gap-2 px-4 py-2 text-sm hover:bg-slate-50"
            >
              <span className="font-mono text-xs">{c.id.slice(0, 8)}</span>
              <span>{label('stage', c.stage)}</span>
              <span>{label('status', c.status)}</span>
              <span className="text-slate-500">{formatDate(c.updated_at)}</span>
            </a>
          </li>
        ))}
      </ul>
    </section>
  )
}
