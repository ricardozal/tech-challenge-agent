import AdvisorPage from './advisor/AdvisorPage'
import ChatPage from './chat/ChatPage'

export default function App() {
  const path = location.pathname.replace(/\/+$/, '') || '/'
  if (path === '/') {
    location.replace('/chat')
    return null
  }
  const page = path === '/chat' ? <ChatPage /> : path === '/asesor' ? <AdvisorPage /> : null

  return (
    <div className="min-h-screen bg-slate-50 text-slate-900">
      <header className="flex items-center gap-6 border-b border-slate-200 bg-white px-6 py-3">
        <span className="font-semibold">Agente de crédito · Demo</span>
        <nav className="flex gap-4 text-sm">
          <a className={linkClass(path === '/chat')} href="/chat">
            Chat del cliente
          </a>
          <a className={linkClass(path === '/asesor')} href="/asesor">
            Consola del asesor
          </a>
        </nav>
        <span className="ml-auto text-xs text-slate-500">Datos sintéticos de prueba</span>
      </header>
      {page ?? (
        <main className="p-6">
          <p>Página no encontrada. Abre el chat del cliente o la consola del asesor.</p>
        </main>
      )}
    </div>
  )
}

function linkClass(active: boolean): string {
  return active ? 'font-medium text-indigo-700' : 'text-slate-600 hover:text-slate-900'
}
