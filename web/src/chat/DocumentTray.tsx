import type { DocumentSlot, SampleDocument } from '../api/types'

interface Props {
  slots: DocumentSlot[]
  requested: DocumentSlot | null
  disabled: boolean
  onSend: (sample: SampleDocument) => void
}

const basename = (file: string) => file.split('/').pop()!

export default function DocumentTray({ slots, requested, disabled, onSend }: Props) {
  const ordered = requested ? [requested, ...slots.filter((s) => s.slot !== requested.slot)] : slots
  return (
    <div className="border-t border-slate-200 bg-slate-100 p-3">
      <p className="mb-2 text-sm text-slate-600">Documentos de ejemplo (sintéticos, marcados como prueba)</p>
      <div className="flex gap-3 overflow-x-auto">
        {ordered.flatMap((slot) =>
          slot.options.map((sample) => {
            const isRequested = requested?.slot === slot.slot
            return (
              <button
                key={sample.file}
                type="button"
                data-testid={`document-${basename(sample.file)}`}
                data-requested={isRequested ? 'true' : 'false'}
                data-variant={sample.variant}
                disabled={disabled}
                onClick={() => onSend(sample)}
                className={`flex w-36 shrink-0 flex-col items-center gap-1 rounded-md border bg-white p-2 text-xs disabled:opacity-50 ${
                  isRequested ? 'border-indigo-500 ring-2 ring-indigo-300' : 'border-slate-200'
                } ${sample.variant === 'mismatch' ? 'text-amber-800' : ''}`}
              >
                <img src={`/${sample.file}`} alt={sample.label} className="h-20 w-full object-cover object-top" />
                <span>{sample.label}</span>
                {isRequested && <span className="text-indigo-700">Lo pide el agente</span>}
              </button>
            )
          }),
        )}
      </div>
    </div>
  )
}
