// Advisor console (P2). Reads only actions_api and writes only through its tools as `advisor`.
import { useCallback, useEffect, useState } from 'react'
import { getAudit, getCase, getEscalation, getPolicy } from '../api/actions'
import type { AuditEntry, CaseView, Escalation, Policy } from '../api/types'
import ActionPanel from './ActionPanel'
import CaseDetail from './CaseDetail'
import CaseList from './CaseList'
import Inbox from './Inbox'
import MetricsPanel from './MetricsPanel'
import Timeline from './Timeline'

interface Detail {
  caseView: CaseView
  escalation: Escalation | null
  audit: AuditEntry[]
  policy: Policy | null
}

function CasePage({ caseId }: { caseId: string }) {
  const [detail, setDetail] = useState<Detail | null>(null)
  const [error, setError] = useState<string | null>(null)

  const load = useCallback(async () => {
    try {
      const [caseView, audit] = await Promise.all([getCase(caseId), getAudit(caseId)])
      const [escalation, policy] = await Promise.all([
        caseView.state.open_escalation_id ? getEscalation(caseView.state.open_escalation_id) : Promise.resolve(null),
        getPolicy(caseView.policy_version).catch(() => null),
      ])
      setDetail({ caseView, escalation, audit, policy })
      setError(null)
    } catch {
      setError('No se pudo leer el caso.')
    }
  }, [caseId])

  useEffect(() => {
    void load()
  }, [load])

  return (
    <main className="mx-auto flex max-w-6xl flex-col gap-4 p-6">
      <a href="/asesor" className="text-sm text-indigo-700 hover:underline">
        ← Bandeja
      </a>
      {error && <p className="text-sm text-red-700">{error}</p>}
      {detail && (
        <div className="grid gap-4 lg:grid-cols-[2fr_1fr]">
          <CaseDetail caseView={detail.caseView} escalation={detail.escalation} policy={detail.policy} />
          <div className="flex flex-col gap-4">
            <ActionPanel caseView={detail.caseView} onChanged={load} />
            <Timeline entries={detail.audit} />
          </div>
        </div>
      )}
    </main>
  )
}

export default function AdvisorPage() {
  const caseId = new URLSearchParams(location.search).get('case')
  if (caseId) return <CasePage caseId={caseId} />
  return (
    <main className="mx-auto grid max-w-6xl gap-4 p-6 lg:grid-cols-2">
      <div className="flex flex-col gap-4">
        <Inbox />
        <CaseList />
      </div>
      <MetricsPanel />
    </main>
  )
}
