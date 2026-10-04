import type { AuditEntry } from '../api/types'
import { formatDate, label } from '../labels'

export default function Timeline({ entries }: { entries: AuditEntry[] }) {
  const ordered = [...entries].sort((a, b) => a.id - b.id)
  return (
    <section className="rounded-lg border border-slate-200 bg-white">
      <h2 className="border-b border-slate-200 px-4 py-3 font-semibold">Registro de acciones</h2>
      <ol className="divide-y divide-slate-100 text-sm">
        {ordered.map((e) => (
          <li
            key={e.id}
            data-testid="timeline-entry"
            data-tool={e.tool}
            data-actor={e.actor}
            data-outcome={e.outcome}
            className={`grid grid-cols-[9rem_5rem_1fr_auto] gap-3 px-4 py-2 ${e.tool === 'append_message' ? 'text-slate-400' : ''}`}
          >
            <span className="text-xs text-slate-500">{formatDate(e.at)}</span>
            <span>{label('actor', e.actor)}</span>
            <span>
              {label('tool', e.tool)}
              {e.stage_before && (
                <span className="text-xs text-slate-500">
                  {' '}
                  · {label('stage', e.stage_before)} → {label('stage', e.stage_after)}
                </span>
              )}
              {e.events.length > 0 && (
                <span className="text-xs text-slate-500"> · {e.events.map((ev) => ev.type).join(', ')}</span>
              )}
            </span>
            <span className={e.outcome === 'accepted' ? 'text-green-700' : 'text-red-700'}>
              {e.outcome === 'accepted' ? 'aceptada' : `rechazada: ${label('rejection_code', e.rejection_code)}`}
            </span>
          </li>
        ))}
      </ol>
    </section>
  )
}
