import { useEffect, useRef } from 'react'

export interface ChatItem {
  author: 'client' | 'agent'
  kind: 'text' | 'document'
  text: string
}

interface Props {
  items: ChatItem[]
  waiting: boolean
  error: string | null
  onRetry: () => void
}

export default function MessageList({ items, waiting, error, onRetry }: Props) {
  const end = useRef<HTMLDivElement>(null)
  useEffect(() => {
    end.current?.scrollIntoView({ block: 'end' })
  }, [items.length, waiting, error])

  return (
    <div data-testid="conversation" className="flex flex-1 flex-col gap-3 overflow-y-auto p-4">
      {items.map((item, i) =>
        item.kind === 'document' ? (
          <div key={i} data-testid="bubble-document" className="self-end rounded-lg border border-dashed border-indigo-300 bg-indigo-50 px-3 py-2 text-sm text-indigo-900">
            📎 Documento enviado: {item.text}
          </div>
        ) : (
          <div
            key={i}
            data-testid={item.author === 'client' ? 'bubble-client' : 'bubble-agent'}
            className={
              item.author === 'client'
                ? 'max-w-[75%] self-end whitespace-pre-wrap rounded-2xl rounded-br-sm bg-indigo-600 px-4 py-2 text-white'
                : 'max-w-[75%] self-start whitespace-pre-wrap rounded-2xl rounded-bl-sm bg-white px-4 py-2 shadow-sm'
            }
          >
            {item.text}
          </div>
        ),
      )}
      {waiting && (
        <div data-testid="typing" className="self-start rounded-2xl bg-white px-4 py-2 text-sm text-slate-500 shadow-sm">
          escribiendo…
        </div>
      )}
      {error && (
        <div data-testid="chat-error" className="flex items-center gap-3 self-end text-sm text-red-700">
          <span>{error}</span>
          <button type="button" data-testid="retry" onClick={onRetry} className="rounded border border-red-300 px-2 py-0.5 hover:bg-red-50">
            Reintentar
          </button>
        </div>
      )}
      <div ref={end} />
    </div>
  )
}
