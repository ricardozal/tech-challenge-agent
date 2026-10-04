// Client chat (P1). Writes only through the agent channel; reads stage and status from actions_api
// (specs/002-demo-web data-model § Sesión de chat). The session lives in the URL (W-09).
import { useCallback, useEffect, useRef, useState } from 'react'
import { getCase, getEscalation } from '../api/actions'
import { createCase, getConversation, sendDocument, sendMessage } from '../api/agent'
import { errorText } from '../api/errors'
import { loadScenarios } from '../api/scenarios'
import { FINAL_STATUSES, type CaseView, type Escalation, type SampleDocument, type Scenario } from '../api/types'
import { label } from '../labels'
import CaseStatusBar from './CaseStatusBar'
import Composer from './Composer'
import DocumentTray from './DocumentTray'
import MessageList, { type ChatItem } from './MessageList'
import ScenarioPicker from './ScenarioPicker'
import { requestedSlot, suggestMessage } from './suggestions'

type Pending =
  | { kind: 'create'; scenario: Scenario; key: string }
  | { kind: 'message'; text: string; key: string }
  | { kind: 'document'; sample: SampleDocument; key: string }

const POLL_MS = 5000
const DOCUMENT_TAG = /^\[documento: (\w+)\]$/

function readUrl(): { scenarioId: string | null; caseId: string | null } {
  const params = new URLSearchParams(location.search)
  return { scenarioId: params.get('scenario'), caseId: params.get('case') }
}

function resultReason(caseView: CaseView, escalation: Escalation | null): string | null {
  if (caseView.status === 'rejected') {
    const decision = [...caseView.state.decisions].reverse().find((d) => d.result === 'rejected')
    return decision ? label('rejection', decision.reason) : null
  }
  if (caseView.status === 'escalated' && escalation) return label('escalation', escalation.reason)
  return null
}

export default function ChatPage() {
  const [scenarios, setScenarios] = useState<Scenario[] | null>(null)
  const [scenario, setScenario] = useState<Scenario | null>(null)
  const [caseId, setCaseId] = useState<string | null>(null)
  const [items, setItems] = useState<ChatItem[]>([])
  const [lastQuestion, setLastQuestion] = useState<string | null>(null)
  const [caseView, setCaseView] = useState<CaseView | null>(null)
  const [escalation, setEscalation] = useState<Escalation | null>(null)
  const [pending, setPending] = useState<Pending | null>(null)
  const [sending, setSending] = useState(false)
  const [refreshing, setRefreshing] = useState(false)
  const [error, setError] = useState<string | null>(null)
  // True until a ?case= session in the URL is restored, so the page is not idle with half a conversation.
  const [restoring, setRestoring] = useState(() => readUrl().caseId !== null)
  const inFlight = useRef(false)

  const refresh = useCallback(async (id: string) => {
    setRefreshing(true)
    try {
      const [conversation, view] = await Promise.all([getConversation(id), getCase(id)])
      setLastQuestion(conversation.state.last_question ?? null)
      setCaseView(view)
      setEscalation(view.state.open_escalation_id ? await getEscalation(view.state.open_escalation_id) : null)
    } catch (e) {
      setError(errorText(e))
    } finally {
      setRefreshing(false)
    }
  }, [])

  // Load the scenarios and, with ?case= in the URL, restore the conversation (FR-064).
  useEffect(() => {
    let cancelled = false
    ;(async () => {
      try {
        const file = await loadScenarios()
        if (cancelled) return
        setScenarios(file.scenarios)
        const { scenarioId, caseId: urlCase } = readUrl()
        const picked = file.scenarios.find((s) => s.id === scenarioId) ?? null
        if (!picked || !urlCase) {
          setRestoring(false)
          return
        }
        setScenario(picked)
        setCaseId(urlCase)
        const conversation = await getConversation(urlCase)
        if (cancelled) return
        setItems(
          conversation.messages.map((m): ChatItem => {
            const doc = DOCUMENT_TAG.exec(m.text)
            if (m.author === 'client' && doc) return { author: 'client', kind: 'document', text: label('document', doc[1]) }
            return { author: m.author === 'client' ? 'client' : 'agent', kind: 'text', text: m.text }
          }),
        )
        await refresh(urlCase)
      } catch (e) {
        if (!cancelled) setError(errorText(e))
      } finally {
        if (!cancelled) setRestoring(false)
      }
    })()
    return () => {
      cancelled = true
    }
  }, [refresh])

  const run = useCallback(
    async (job: Pending) => {
      if (inFlight.current) return
      inFlight.current = true
      setPending(job)
      setSending(true)
      setError(null)
      try {
        if (job.kind === 'create') {
          const created = await createCase(job.key)
          setScenario(job.scenario)
          setCaseId(created.case_id)
          setItems([{ author: 'agent', kind: 'text', text: created.reply }])
          history.replaceState(null, '', `/chat?scenario=${job.scenario.id}&case=${created.case_id}`)
          setPending(null)
          setSending(false)
          await refresh(created.case_id)
        } else {
          const turn =
            job.kind === 'message'
              ? await sendMessage(caseId!, job.text, job.key)
              : await sendDocument(caseId!, job.sample, job.key)
          setItems((prev) => [...prev, { author: 'agent', kind: 'text', text: turn.reply }])
          setPending(null)
          setSending(false)
          await refresh(caseId!)
        }
      } catch (e) {
        setError(errorText(e))
        setSending(false)
      } finally {
        inFlight.current = false
      }
    },
    [caseId, refresh],
  )

  // The client's bubble is added once, when the message is first sent; a retry reuses it and the key.
  function sendText(text: string) {
    setItems((prev) => [...prev, { author: 'client', kind: 'text', text }])
    void run({ kind: 'message', text, key: crypto.randomUUID() })
  }

  function sendSample(sample: SampleDocument) {
    setItems((prev) => [...prev, { author: 'client', kind: 'document', text: sample.label }])
    void run({ kind: 'document', sample, key: crypto.randomUUID() })
  }

  function retry() {
    if (pending) void run(pending)
    else if (caseId) void refresh(caseId)
  }

  function restart() {
    history.replaceState(null, '', '/chat')
    setScenario(null)
    setCaseId(null)
    setItems([])
    setLastQuestion(null)
    setCaseView(null)
    setEscalation(null)
    setPending(null)
    setError(null)
  }

  // While escalated, re-read the case so the advisor's resolution shows up (W-07).
  const status = caseView?.status
  const version = caseView?.version
  useEffect(() => {
    if (!caseId || status !== 'escalated') return
    const timer = setInterval(async () => {
      try {
        const view = await getCase(caseId)
        if (view.status !== status || view.version !== version) await refresh(caseId)
      } catch {
        // next tick tries again
      }
    }, POLL_MS)
    return () => clearInterval(timer)
  }, [caseId, status, version, refresh])

  const busy = scenarios === null || restoring || sending || refreshing

  if (!scenario || !caseId) {
    return (
      <main data-testid="chat" data-busy={busy ? 'true' : 'false'}>
        {scenarios && <ScenarioPicker scenarios={scenarios} disabled={sending} onPick={(s) => run({ kind: 'create', scenario: s, key: crypto.randomUUID() })} />}
        {error && (
          <div data-testid="chat-error" className="mx-auto max-w-3xl px-6 text-sm text-red-700">
            {error}{' '}
            <button type="button" data-testid="retry" onClick={retry} className="underline">
              Reintentar
            </button>
          </div>
        )}
      </main>
    )
  }

  const active = caseView?.status === 'active'
  const closed = caseView !== null && FINAL_STATUSES.includes(caseView.status)
  const suggestion = active && caseView ? suggestMessage(scenario, caseView.stage, lastQuestion) : null
  const slot = active ? requestedSlot(scenario, lastQuestion) : null
  const showTray = active && caseView?.stage === 'documents' && scenario.documents.length > 0
  const stuck = active && !busy && !suggestion && !slot && !showTray

  return (
    <main data-testid="chat" data-busy={busy ? 'true' : 'false'} className="mx-auto flex h-[calc(100vh-49px)] max-w-4xl flex-col bg-slate-50">
      {caseView ? (
        <CaseStatusBar stage={caseView.stage} status={caseView.status} reason={resultReason(caseView, escalation)} onRestart={restart} />
      ) : (
        !busy && (
          // The session in the URL could not be restored (unknown case or API down).
          <div className="flex items-center justify-between border-b border-slate-200 bg-white px-4 py-3 text-sm">
            <span className="text-slate-600">No se pudo recuperar el caso de esta dirección.</span>
            <button type="button" data-testid="restart" onClick={restart} className="rounded-md border border-slate-300 px-3 py-1 hover:bg-slate-50">
              Empezar de nuevo
            </button>
          </div>
        )
      )}
      <div className="px-4 pt-2 text-xs text-slate-500">
        {scenario.title} · Cliente de prueba: {scenario.client_name} · Caso {caseId.slice(0, 8)}
      </div>
      <MessageList items={items} waiting={sending} error={error} onRetry={retry} />
      {stuck && (
        <p className="px-4 pb-2 text-sm text-slate-500">No hay más pasos sugeridos; puedes escribir o empezar de nuevo.</p>
      )}
      {showTray && <DocumentTray slots={scenario.documents} requested={slot} disabled={busy || pending !== null} onSend={sendSample} />}
      <Composer suggestion={suggestion?.text ?? null} disabled={busy || closed || pending !== null} onSend={sendText} />
    </main>
  )
}
