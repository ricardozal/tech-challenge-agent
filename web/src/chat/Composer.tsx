import { useState, type FormEvent } from 'react'

interface Props {
  suggestion: string | null
  disabled: boolean
  onSend: (text: string) => void
}

export default function Composer({ suggestion, disabled, onSend }: Props) {
  const [text, setText] = useState('')

  function submit(event: FormEvent) {
    event.preventDefault()
    const value = text.trim()
    if (!value || disabled) return
    setText('')
    onSend(value)
  }

  return (
    <div className="border-t border-slate-200 bg-white p-3">
      {suggestion && (
        <div className="mb-2 flex items-center gap-2 text-sm">
          <span className="text-slate-500">Sugerencia:</span>
          <button
            type="button"
            data-testid="suggestion"
            disabled={disabled}
            onClick={() => onSend(suggestion)}
            className="rounded-full border border-indigo-300 bg-indigo-50 px-3 py-1 text-indigo-800 hover:bg-indigo-100 disabled:opacity-50"
          >
            {suggestion}
          </button>
        </div>
      )}
      <form onSubmit={submit} className="flex gap-2">
        <input
          data-testid="message-input"
          value={text}
          onChange={(e) => setText(e.target.value)}
          disabled={disabled}
          placeholder="Escribe un mensaje"
          className="flex-1 rounded-md border border-slate-300 px-3 py-2 disabled:bg-slate-100"
        />
        <button
          type="submit"
          data-testid="send"
          disabled={disabled || !text.trim()}
          className="rounded-md bg-indigo-600 px-4 py-2 text-white disabled:opacity-50"
        >
          Enviar
        </button>
      </form>
      <p className="mt-2 text-xs text-slate-500">Con respuestas grabadas del modelo, usa las sugerencias para avanzar.</p>
    </div>
  )
}
