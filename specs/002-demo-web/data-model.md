# Data Model: Web de demo

La web no tiene base de datos ni estado persistente propio. Lee los modelos de la feature 001
(`packages/contracts`, ver [001/data-model.md](../001-credit-agent-core/data-model.md)) y agrega
solo modelos de presentación en el navegador. Los tipos TypeScript de `web/src/api/types.ts`
reflejan a mano los campos de los contratos que la web usa; no se generan.

## Escenario de demo (`web/public/scenarios.json`)

Generado por `scripts/export_web_scenarios.py` desde `fixtures/scenarios/*.yaml`
([contracts/web-scenarios.md](./contracts/web-scenarios.md)).

| Campo | Tipo | Regla |
|---|---|---|
| `id` | `happy_path` \| `eligibility_rejection` \| `document_failed` \| `no_spare_key` | único |
| `title`, `description` | texto en español | se muestran en el selector (FR-056) |
| `client_name` | texto | cliente de prueba (sintético) |
| `expected_results` | lista de `Status` | `document_failed` admite `ok_for_lender` y `escalated` |
| `source_scripts` | lista de nombres de guion de 001 | trazabilidad del export |
| `messages` | lista de **Mensaje sugerido** | orden del guion |
| `documents` | lista de **Ranura de documento** | una por tipo pedido |

**Mensaje sugerido**: `stage` (`Stage`), `question` (pregunta exacta del agente a la que
responde), `text` (lo que envía el cliente). Se ofrece cuando `question == last_question` y
`stage == case.stage` (W-06).

**Ranura de documento**: `slot` (`identification` \| `income_proof` \| `proof_of_address` \|
`vehicle_invoice`), `question` (pregunta del agente para ese tipo, de
`agent.questions.DOCUMENT_QUESTIONS`) y `options`: lista de **Documento de ejemplo**.

**Documento de ejemplo**: `file` (ruta servida, `documents/<nombre>.png`), `requested_type`
(`DocumentType` que se envía en el formulario), `label` (p. ej. "Recibo de nómina — no cuadra"),
`variant` (`ok` \| `mismatch`).

Reglas:
- Todo `text` de un mensaje sugerido existe en un guion de 001 con su misma `stage` y `question`
  (así el LLM en modo `fake` lo entiende).
- Todo `file` existe en `fixtures/documents/` y lleva la marca visible de prueba.
- Solo `document_failed` tiene una ranura con dos opciones (`income_proof`).

## Sesión de chat (estado del componente `ChatPage`)

| Campo | Origen |
|---|---|
| `scenarioId`, `caseId` | query de la URL (`?scenario=&case=`), W-09 |
| `messages` | `POST /cases` (saludo), `TurnResponse.reply`, mensajes del cliente enviados; al recargar, `GET /cases/{id}/conversation` |
| `lastQuestion` | `conversation.state.last_question` |
| `caseView` | `GET {actions}/cases/{id}` tras cada turno |
| `pending` | envío en curso: `{kind, payload, idempotencyKey}`; se reutiliza al reintentar |
| `error` | último error en español, con opción de reintentar |

Transiciones de la vista:

```text
sin escenario ──elegir──▶ creando caso ──201──▶ conversando
conversando ──enviar──▶ esperando ("escribiendo…") ──200──▶ conversando | terminado | escalado
esperando ──error/409──▶ conversando con error (Reintentar usa la misma Idempotency-Key)
escalado ──sondeo 5 s: status = active──▶ conversando
escalado ──sondeo 5 s: status final──▶ terminado
cualquiera ──Empezar de nuevo──▶ sin escenario
```

`terminado` = `status` en `ok_for_lender`, `rejected`, `cancelled`: se muestra el resultado y se
ocultan sugerencias y documentos (FR-062).

## Resultado mostrado

| `status` | Texto | Motivo |
|---|---|---|
| `ok_for_lender` | OK para financiera | — |
| `rejected` | Rechazado | `reason` de la última `Decision` con `result = rejected` (el rechazo por auto es `kind = eligibility`) |
| `escalated` | Escalado a asesor | `reason` del ticket `open_escalation_id` |
| `cancelled` | Cancelado | — |
| `active` | (sin resultado) | se muestra la etapa |

## Consola del asesor (estado de `AdvisorPage`)

| Vista | Lecturas |
|---|---|
| Bandeja | `GET /escalations?status=open` + `GET /cases/{case_id}` por ticket; orden `created_at` descendente |
| Casos | `GET /cases`, orden `updated_at` descendente |
| Detalle | `CaseView`, `Escalation` abierta (si hay), `AuditEntry[]`, política de `case.policy_version` (W-11) |
| Métricas | `MetricsReport` |

**Evidencia mostrada** (FR-066): por cada `DocumentRecord`: `requested_type`, `detected_type`,
`is_test_specimen`, y cada `ExtractedField` (`value`, `confidence`, marca de baja confianza si
`confidence < policy.documents.min_field_confidence`); por cada `Validation`: `key`, `type`,
`result`, `origin`, `attempt`, `detail`; los mensajes del caso (`state.messages`).

**Acción del asesor** (formulario → `ToolCall`):

| Acción (UI) | Tool | Entrada que pide el formulario | Válida cuando |
|---|---|---|---|
| Pedir corrección | `request_correction` | validación (de las no aprobadas), mensaje al cliente | `escalated` |
| Verificar manualmente | `verify_validation_manually` | validación (de las no aprobadas), justificación (obligatoria); `evidence` = `validation.evidence` + `"consola_asesor"` | `escalated` |
| Rechazar | `reject_case` | motivo (obligatorio) | `escalated` |
| Devolver al agente | `return_to_agent` | nota | `escalated` |
| Cancelar | `cancel_case` | motivo | `active`, `escalated` |
| Revocar OK | `revoke_ok` | motivo (obligatorio) | `ok_for_lender` |

La consola solo muestra las acciones válidas para el estado del caso, pero el permiso lo decide
`actions_api`: un rechazo (`403`, `409`, `422`) se muestra con su `rejection.code` traducido y el
caso se vuelve a leer (FR-070). Cada envío lleva `X-Actor: advisor`,
`context.expected_version = caseView.version` y `context.idempotency_key` nueva por intento,
reutilizada al reintentar (FR-069).
