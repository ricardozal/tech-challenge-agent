import type { Stage, Status } from '../api/types'
import { label } from '../labels'

const STAGES: Stage[] = ['eligibility', 'profiling', 'simulation', 'documents']

const RESULT_STYLE: Record<Status, string> = {
  active: '',
  ok_for_lender: 'border-green-300 bg-green-50 text-green-900',
  rejected: 'border-red-300 bg-red-50 text-red-900',
  escalated: 'border-amber-300 bg-amber-50 text-amber-900',
  cancelled: 'border-slate-300 bg-slate-100 text-slate-700',
}

interface Props {
  stage: Stage
  status: Status
  reason: string | null
  onRestart: () => void
}

export default function CaseStatusBar({ stage, status, reason, onRestart }: Props) {
  const current = STAGES.indexOf(stage)
  return (
    <div className="border-b border-slate-200 bg-white px-4 py-3">
      <div className="flex items-center gap-4">
        <ol className="flex flex-1 items-center gap-2 text-sm">
          {STAGES.map((s, i) => (
            <li
              key={s}
              className={`rounded-full px-3 py-1 ${
                i === current ? 'bg-indigo-600 text-white' : i < current ? 'bg-indigo-100 text-indigo-800' : 'bg-slate-100 text-slate-500'
              }`}
            >
              {label('stage', s)}
            </li>
          ))}
        </ol>
        <span className="text-sm text-slate-600">
          Etapa: <strong data-testid="stage">{label('stage', stage)}</strong> · Estado:{' '}
          <strong data-testid="status">{label('status', status)}</strong>
        </span>
        <button type="button" data-testid="restart" onClick={onRestart} className="rounded-md border border-slate-300 px-3 py-1 text-sm hover:bg-slate-50">
          Empezar de nuevo
        </button>
      </div>
      {status !== 'active' && (
        <div className={`mt-3 rounded-md border px-4 py-3 ${RESULT_STYLE[status]}`}>
          <span data-testid="result" className="text-lg font-semibold">
            {label('status', status)}
          </span>
          {reason && (
            <span className="ml-2">
              · <span data-testid="result-reason">{reason}</span>
            </span>
          )}
        </div>
      )}
    </div>
  )
}
