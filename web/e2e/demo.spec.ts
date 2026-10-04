// End-to-end demo of the web against the compose stack in LLM_MODE=fake (specs/002-demo-web, W-13).
// Tags @FR-xxx are read by scripts/traceability.py.
import { expect, test, type Page, type TestInfo } from '@playwright/test'
import { readFileSync } from 'node:fs'
import type { Scenario, ScenarioFile } from '../src/api/types'

const scenarios: Scenario[] = (
  JSON.parse(readFileSync(new URL('../public/scenarios.json', import.meta.url), 'utf-8')) as ScenarioFile
).scenarios

const byId = (id: Scenario['id']) => scenarios.find((s) => s.id === id)!
const ACTIONS_URL = process.env.ACTIONS_URL ?? 'http://localhost:8000'

const STAGES = ['Elegibilidad', 'Perfilamiento', 'Simulación', 'Documentos']
const RESULT: Record<string, string> = {
  ok_for_lender: 'OK para financiera',
  rejected: 'Rechazado',
  escalated: 'Escalado a asesor',
  cancelled: 'Cancelado',
}

type Variant = 'ok' | 'mismatch'

interface Played {
  caseId: string
  stages: string[]
  timings: number[]
}

/** Waits until the chat is idle: no request in flight and the case re-read after the last turn. */
async function idle(page: Page) {
  await expect(page.getByTestId('chat')).toHaveAttribute('data-busy', 'false')
}

/** Clicks and returns the milliseconds until the agent's reply is on screen (SC-012). */
async function timed(page: Page, click: () => Promise<void>): Promise<number> {
  const replies = page.getByTestId('bubble-agent')
  const before = await replies.count()
  const started = Date.now()
  await click()
  await expect(replies).toHaveCount(before + 1)
  const elapsed = Date.now() - started
  await idle(page)
  return elapsed
}

/**
 * Picks the scenario and advances only with suggestions and the requested sample documents until a
 * result shows. `incomeVariants` chooses, in order, which income proof to send when two are offered.
 * `documentOrder` (file basenames) sends the documents in that order instead of the requested one.
 */
async function playToEnd(
  page: Page,
  scenario: Scenario,
  incomeVariants: Variant[] = ['ok'],
  documentOrder: string[] = [],
): Promise<Played> {
  await page.goto('/chat')
  await page.getByTestId(`scenario-${scenario.id}`).click()
  await expect(page.getByTestId('bubble-agent')).toHaveCount(1)
  await idle(page)
  const caseId = new URL(page.url()).searchParams.get('case')!
  const stages: string[] = []
  const timings: number[] = []
  const variants = [...incomeVariants]

  for (let step = 0; step < 40; step++) {
    const stage = (await page.getByTestId('stage').textContent())!.trim()
    if (stages.at(-1) !== stage) stages.push(stage)
    if (await page.getByTestId('result').isVisible()) return { caseId, stages, timings }

    const suggestion = page.getByTestId('suggestion')
    const requested = page.locator('[data-testid^="document-"][data-requested="true"]')
    if (await suggestion.isVisible()) {
      timings.push(await timed(page, () => suggestion.click()))
    } else if (documentOrder.length > 0 && (await page.getByTestId(`document-${documentOrder[0]}`).isVisible())) {
      const name = documentOrder.shift()!
      timings.push(await timed(page, () => page.getByTestId(`document-${name}`).click()))
    } else if ((await requested.count()) > 0) {
      let doc = requested.first()
      if ((await requested.count()) > 1) {
        const variant = variants.length > 1 ? variants.shift()! : variants[0]
        doc = page.locator(`[data-testid^="document-"][data-requested="true"][data-variant="${variant}"]`)
      }
      timings.push(await timed(page, () => doc.click()))
    } else {
      throw new Error(`paso ${step}: no hay sugerencia ni documento pedido (etapa ${stage})`)
    }
  }
  throw new Error('el escenario no terminó en 40 pasos')
}

function p95(values: number[]): number {
  const sorted = [...values].sort((a, b) => a - b)
  return sorted[Math.max(0, Math.ceil(sorted.length * 0.95) - 1)] ?? 0
}

async function checkTimings(played: Played, testInfo: TestInfo) {
  await testInfo.attach('tiempos', { body: JSON.stringify(played.timings), contentType: 'application/json' })
  expect(p95(played.timings), `p95 de ${JSON.stringify(played.timings)}`).toBeLessThan(3000)
}

// --- P1 · Chat del cliente -------------------------------------------------------------------------

for (const scenario of scenarios) {
  test(
    `chat · ${scenario.id}`,
    {
      tag: [
        '@FR-053', '@FR-056', '@FR-057', '@FR-058', '@FR-059', '@FR-060',
        '@FR-061', '@FR-062', '@FR-063', '@FR-074', '@FR-075',
      ],
    },
    async ({ page }, testInfo) => {
      // document_failed takes the correction branch here (mismatch, then the right payslip).
      const variants: Variant[] = scenario.id === 'document_failed' ? ['mismatch', 'ok'] : ['ok']
      const played = await playToEnd(page, scenario, variants)

      expect(played.stages[0]).toBe('Elegibilidad')
      expect(STAGES.slice(0, played.stages.length)).toEqual(played.stages)
      await expect(page.getByTestId('result')).toHaveText(RESULT[scenario.expected_results[0]])
      await expect(page.getByTestId('suggestion')).toBeHidden()
      await expect(page.locator('[data-testid^="document-"]')).toHaveCount(0)

      if (scenario.id === 'eligibility_rejection') {
        await expect(page.getByTestId('result-reason')).toHaveText('Titular distinto al cliente')
        expect(played.stages).toEqual(['Elegibilidad'])
      }
      if (scenario.id === 'no_spare_key') {
        await expect(page.getByTestId('bubble-agent').filter({ hasText: 'de la segunda llave' })).toHaveCount(1)
      }
      await checkTimings(played, testInfo)
    },
  )
}

test(
  'chat · happy_path · texto libre, recarga y reinicio',
  { tag: ['@FR-055', '@FR-059', '@FR-063', '@FR-064'] },
  async ({ page }) => {
    await page.goto('/chat')
    await page.getByTestId('scenario-happy_path').click()
    await expect(page.getByTestId('bubble-agent')).toHaveCount(1)
    await idle(page)
    const suggestion = (await page.getByTestId('suggestion').textContent())!

    // Free text with markup is shown literally; with recorded answers the agent asks again.
    await page.getByTestId('message-input').fill('<b>hola</b>')
    await page.getByTestId('send').click()
    await expect(page.getByTestId('send')).toBeDisabled()
    await expect(page.getByTestId('bubble-client').last()).toHaveText('<b>hola</b>')
    await expect(page.getByTestId('bubble-agent')).toHaveCount(2)
    await idle(page)
    await expect(page.getByTestId('conversation').locator('b')).toHaveCount(0)
    await expect(page.getByTestId('suggestion')).toHaveText(suggestion)

    // One step forward, then reload: conversation, stage and suggestion come back from the URL.
    await timed(page, () => page.getByTestId('suggestion').click())
    const bubbles = await page.getByTestId('bubble-agent').count()
    const next = await page.getByTestId('suggestion').textContent()
    await page.reload()
    await idle(page)
    await expect(page.getByTestId('bubble-agent')).toHaveCount(bubbles)
    await expect(page.getByTestId('stage')).toHaveText('Elegibilidad')
    await expect(page.getByTestId('suggestion')).toHaveText(next!)

    await page.getByTestId('restart').click()
    await expect(page.getByTestId('scenario-happy_path')).toBeVisible()
    expect(new URL(page.url()).searchParams.get('case')).toBeNull()
  },
)

test('chat · reintento sin duplicar', { tag: ['@FR-063'] }, async ({ page }) => {
  await page.goto('/chat')
  await page.getByTestId('scenario-happy_path').click()
  await expect(page.getByTestId('bubble-agent')).toHaveCount(1)
  await idle(page)

  const keys: string[] = []
  let failed = false
  await page.route('**/cases/*/messages', async (route) => {
    if (route.request().method() !== 'POST') return route.continue()
    keys.push(route.request().headers()['idempotency-key'])
    if (!failed) {
      failed = true
      await route.abort()
    } else {
      await route.continue()
    }
  })

  const text = (await page.getByTestId('suggestion').textContent())!
  await page.getByTestId('suggestion').click()
  await expect(page.getByTestId('chat-error')).toBeVisible()
  await page.getByTestId('retry').click()
  await expect(page.getByTestId('bubble-agent')).toHaveCount(2)
  await idle(page)

  expect(keys).toHaveLength(2)
  expect(keys[1]).toBe(keys[0])
  await expect(page.getByTestId('bubble-client').filter({ hasText: text })).toHaveCount(1)
  await expect(page.getByTestId('chat-error')).toBeHidden()
})

// --- P2 · Consola del asesor -----------------------------------------------------------------------

// Demo 3, branch B: the other documents first, then the payslip that does not match three times.
const ESCALATION_ORDER = [
  'laura_identification.png',
  'laura_proof_of_address.png',
  'laura_invoice.png',
  'laura_payslip_low.png',
  'laura_payslip_low.png',
  'laura_payslip_low.png',
]

async function timelineTools(page: Page): Promise<{ tool: string; actor: string; outcome: string }[]> {
  return page.getByTestId('timeline-entry').evaluateAll((rows) =>
    rows.map((row) => ({
      tool: row.getAttribute('data-tool')!,
      actor: row.getAttribute('data-actor')!,
      outcome: row.getAttribute('data-outcome')!,
    })),
  )
}

test(
  'asesor · resolver escalación',
  {
    tag: [
      '@FR-053', '@FR-054', '@FR-065', '@FR-066', '@FR-067', '@FR-068',
      '@FR-069', '@FR-070', '@FR-071', '@FR-073',
    ],
  },
  async ({ page, context }) => {
    const played = await playToEnd(page, byId('document_failed'), ['mismatch'], [...ESCALATION_ORDER])
    await expect(page.getByTestId('result')).toHaveText('Escalado a asesor')
    await expect(page.getByTestId('result-reason')).toHaveText('Mismatch persistente')

    const advisor = await context.newPage()
    await advisor.goto('/asesor')
    const item = advisor.getByTestId(`inbox-item-${played.caseId}`)
    await expect(item).toContainText('Mismatch persistente')
    await expect(item).toContainText('Laura Méndez Rojas')
    await item.click()

    // Ticket, evidence with confidence per field, timeline of the audit log.
    await expect(advisor.getByTestId('ticket-summary')).not.toBeEmpty()
    await expect(advisor.getByTestId('ticket-suggested-action')).not.toBeEmpty()
    await expect(advisor.getByTestId('evidence').getByTestId('document-record')).toHaveCount(6)
    await expect(advisor.getByTestId('field-payslip-net_income').first()).toContainText('%')
    const before = await timelineTools(advisor)
    expect(before.length).toBeGreaterThanOrEqual(10)
    expect(before).toContainEqual({ tool: 'escalate', actor: 'system', outcome: 'accepted' })

    // Manual verification of the income validation; a double click must act once (FR-069).
    await advisor.getByTestId('action-verify_validation_manually').click()
    await advisor.getByTestId('action-validation').selectOption('income')
    await advisor.getByTestId('action-text').fill('Recibo revisado por el asesor contra el estado de cuenta.')
    await advisor.getByTestId('action-submit').dblclick()
    await expect(advisor.getByTestId('case-status')).toHaveText('OK para financiera')

    const after = await timelineTools(advisor)
    const verify = after.filter((e) => e.tool === 'verify_validation_manually')
    expect(verify).toEqual([{ tool: 'verify_validation_manually', actor: 'advisor', outcome: 'accepted' }])
    const at = after.findIndex((e) => e.tool === 'verify_validation_manually')
    expect(after.slice(at + 1)).toContainEqual({ tool: 'evaluate_gate', actor: 'system', outcome: 'accepted' })

    // An OK case only offers the revocation.
    await expect(advisor.getByTestId('action-revoke_ok')).toBeVisible()
    await expect(advisor.getByTestId('action-verify_validation_manually')).toHaveCount(0)

    // Metrics panel: same numbers as GET /metrics (SC-015).
    await advisor.goto('/asesor')
    const metrics = await (await advisor.request.get(`${ACTIONS_URL}/metrics`)).json()
    const panel = advisor.getByTestId('metrics')
    await expect(panel).toBeVisible()
    for (const [group, values] of [
      ['vehicle_rejections', metrics.vehicle_rejections_by_reason],
      ['false_ok', metrics.false_ok_by_reason],
      ['mismatches', metrics.mismatches_by_type],
    ] as [string, Record<string, number>][]) {
      for (const [code, count] of Object.entries(values)) {
        await expect(panel.getByTestId(`metric-${group}-${code}`)).toHaveText(String(count))
      }
    }
    await expect(panel.getByTestId('metric-key-quote')).toHaveText(String(metrics.cases_with_key_quote))

    // The client's chat picks up the resolution by itself (polling while escalated).
    await expect(page.getByTestId('result')).toHaveText('OK para financiera', { timeout: 12_000 })
  },
)

test('asesor · revocar OK y acción rechazada', { tag: ['@FR-070', '@FR-072'] }, async ({ page, context }) => {
  const played = await playToEnd(page, byId('happy_path'))
  await expect(page.getByTestId('result')).toHaveText('OK para financiera')

  // Any case can be opened from the case list; an OK case can be revoked.
  const tabA = await context.newPage()
  await tabA.goto('/asesor')
  await tabA.getByTestId(`case-row-${played.caseId}`).click()
  await expect(tabA.getByTestId('case-status')).toHaveText('OK para financiera')
  await tabA.getByTestId('action-revoke_ok').click()
  await tabA.getByTestId('action-text').fill('El comprobante de domicilio resultó alterado.')
  await tabA.getByTestId('action-submit').click()
  await expect(tabA.getByTestId('case-status')).toHaveText('Escalado a asesor')
  await tabA.goto('/asesor')
  await expect(tabA.getByTestId(`inbox-item-${played.caseId}`)).toContainText('OK revocado')

  // Two tabs on the same case: the stale one gets a version conflict, shown in Spanish.
  await tabA.goto(`/asesor?case=${played.caseId}`)
  await expect(tabA.getByTestId('case-status')).toHaveText('Escalado a asesor')
  const tabB = await context.newPage()
  await tabB.goto(`/asesor?case=${played.caseId}`)
  await tabB.getByTestId('action-return_to_agent').click()
  await tabB.getByTestId('action-submit').click()
  await expect(tabB.getByTestId('case-status')).toHaveText('En curso')

  await tabA.getByTestId('action-reject_case').click()
  await tabA.getByTestId('action-text').fill('Documentación alterada.')
  await tabA.getByTestId('action-submit').click()
  await expect(tabA.getByTestId('action-error')).toContainText('El caso cambió')
  await expect(tabA.getByTestId('case-status')).toHaveText('En curso')
  expect(await timelineTools(tabA)).toContainEqual({ tool: 'reject_case', actor: 'advisor', outcome: 'rejected' })
})
