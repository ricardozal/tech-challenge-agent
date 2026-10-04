import { useCallback, useEffect, useState } from 'react'
import { getMetrics } from '../api/actions'
import type { MetricsReport } from '../api/types'
import { label, type LabelKind } from '../labels'

const GROUPS: { id: string; title: string; field: keyof MetricsReport; kind: LabelKind }[] = [
  { id: 'vehicle_rejections', title: 'Rechazos por auto, por motivo', field: 'vehicle_rejections_by_reason', kind: 'rejection' },
  { id: 'false_ok', title: 'Falsos OK, por motivo de revocación', field: 'false_ok_by_reason', kind: 'rejection' },
  { id: 'mismatches', title: 'Mismatches por tipo', field: 'mismatches_by_type', kind: 'validation_type' },
]

export default function MetricsPanel() {
  const [metrics, setMetrics] = useState<MetricsReport | null>(null)
  const [error, setError] = useState<string | null>(null)

  const load = useCallback(async () => {
    try {
      setMetrics(await getMetrics())
      setError(null)
    } catch {
      setError('No se pudo leer el reporte de métricas.')
    }
  }, [])

  useEffect(() => {
    void load()
  }, [load])

  return (
    <section data-testid="metrics" className="rounded-lg border border-slate-200 bg-white">
      <header className="flex items-center justify-between border-b border-slate-200 px-4 py-3">
        <h2 className="font-semibold">Métricas del proceso</h2>
        <button type="button" onClick={() => void load()} className="text-sm text-indigo-700 hover:underline">
          Actualizar
        </button>
      </header>
      {error && <p className="px-4 py-3 text-sm text-red-700">{error}</p>}
      {metrics && (
        <div className="grid gap-4 p-4 sm:grid-cols-2">
          {GROUPS.map((group) => {
            const values = Object.entries(metrics[group.field] as Record<string, number>)
            return (
              <div key={group.id}>
                <h3 className="text-sm font-medium text-slate-700">{group.title}</h3>
                {values.length === 0 ? (
                  <p className="text-sm text-slate-500">Sin datos</p>
                ) : (
                  <dl className="mt-1 text-sm">
                    {values.map(([code, count]) => (
                      <div key={code} className="flex justify-between border-b border-slate-100 py-1">
                        <dt>{label(group.kind, code)}</dt>
                        <dd data-testid={`metric-${group.id}-${code}`} className="font-mono">
                          {count}
                        </dd>
                      </div>
                    ))}
                  </dl>
                )}
              </div>
            )
          })}
          <div>
            <h3 className="text-sm font-medium text-slate-700">Casos con llave cotizada</h3>
            <p data-testid="metric-key-quote" className="font-mono text-2xl">
              {metrics.cases_with_key_quote}
            </p>
          </div>
          <p className="text-xs text-slate-500 sm:col-span-2">
            Calculado solo a partir del registro de acciones ({metrics.audit_entries} entradas).
          </p>
        </div>
      )}
    </section>
  )
}
