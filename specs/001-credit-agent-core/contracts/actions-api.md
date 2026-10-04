# Contrato: Case Actions API (`actions_api`)

Única capa de escritura sobre el caso, compartida por agente y asesor (Principio IV). Modelos en
`contracts.actions` y `contracts.case`.

## Llamar una tool

```http
POST /tools/{name}
X-Actor: agent | advisor | system
Content-Type: application/json

{
  "context": {
    "case_id": "6f1c…",
    "idempotency_key": "msg-0007:2:evaluate_eligibility",
    "expected_version": 4,
    "on_behalf_of": "client" | null,
    "evidence_message_id": "msg-0007" | null
  },
  "input": { … modelo de entrada de la tool … }
}
```

- `ToolContext` = `X-Actor` + `context`. `X-Actor` no se verifica (sin autenticación, R-16).
- `create_case` es la única tool sin `case_id` ni `expected_version`.

### Respuesta (`ToolResult`)

```json
{
  "outcome": "accepted",
  "case": {"id": "6f1c…", "stage": "profiling", "status": "active", "version": 5},
  "result": { … salida de la tool … },
  "events": [{"type": "key_quoted", "amount": "1850.00"}],
  "rejection": null,
  "policy_version": "2026.10-v1"
}
```

| HTTP | `outcome` | `rejection.code` |
|---|---|---|
| 200 | `accepted` | — |
| 403 | `rejected` | `forbidden` (actor × etapa × tool) |
| 409 | `rejected` | `version_conflict`, `idempotency_mismatch`, `case_closed`, `gate_not_met` |
| 422 | `rejected` | `invalid_input`, `consent_required`, `unconfirmed_data` |

Toda respuesta con `outcome` se audita, aceptada o rechazada (R-05). Repetir la misma
`idempotency_key` con el mismo cuerpo devuelve exactamente la respuesta guardada.

## Catálogo de tools

Columnas: actores permitidos y estado/etapa en que la tool es válida. Fuera de eso → `forbidden`.
`A` = agent, `D` = advisor, `S` = system.

| Tool | Actores | Válida en | Entrada | Efecto | FR |
|---|---|---|---|---|---|
| `create_case` | A | — | — | crea un caso vacío en `eligibility/active` y fija `policy_version` | FR-001, FR-002 |
| `append_message` | A | cualquiera | `message_id`, `author`, `text`, `intent` | guarda el mensaje como evidencia | FR-002 |
| `update_declared_data` | A (on_behalf_of client) | `active`, cualquier etapa no final | `full_name`, `address`, `postal_code`, campos del vehículo, `employment`, `income_*` (solo valores confirmados; `null` = sin cambio) | actualiza `client`/`vehicle`/`declared`; un ingreso corregido en `documents` regresa a `profiling`; un nombre o domicilio corregido vuelve a evaluar las validaciones afectadas | FR-010, FR-015, FR-017 |
| `evaluate_eligibility` | A | `eligibility/active` | — | consulta vehicular (reintentos) + `rules.eligibility`; rechaza (`owner_mismatch`, `lien_or_debt`), o cotiza llave y avanza a `profiling`; sin valor de referencia o falla de proveedor → escala | FR-011–FR-014 |
| `record_bureau_consent` | A (on_behalf_of client) | `profiling/active` | `consent: true`, `evidence_message_id` obligatorio | registra consentimiento con fecha y mensaje | FR-018 |
| `run_credit_check` | A | `profiling/active` | — | exige consentimiento; Buró (reintentos) + `rules.profile`; calcula `max_financeable`; sin oferta → rechaza; avanza a `simulation` | FR-018–FR-020, FR-023 |
| `simulate_options` | A | `simulation/active` | — | `rules.options` → opciones con cuota (y llave) | FR-021–FR-023 |
| `select_option` | A (on_behalf_of client) | `simulation/active` | `option_id` | registra la elección; avanza a `documents` | FR-024 |
| `submit_document` | A | `documents/active` | `requested_type`, `filename`, `content_base64` | guarda bytes, llama `doc_intel`, corre las validaciones del documento, cuenta intentos, escala al pasar N, evalúa el gate | FR-025–FR-036, FR-038 |
| `evaluate_gate` | A, D, S | `documents/active` o `escalated` | — | `rules.gate`: todo `passed` → `ok_for_lender`; si no → `409 gate_not_met` con `missing` | FR-036, FR-037 |
| `escalate` | A, D | `active` | `reason` (`client_requested_human`, `sensitive_topic`), `agent_note` | crea ticket y pasa a `escalated` | FR-039, FR-040, FR-042 |
| `cancel_case` | A (on_behalf_of client), D | `active`, `escalated` | `reason` | pasa a `cancelled` | FR-046 |
| `request_correction` | D | `escalated` | `validation_key`, `message_to_client` | resuelve el ticket, regresa a `active/documents` | FR-044 |
| `verify_validation_manually` | D | `escalated` | `validation_key`, `justification`, `evidence` | validación → `passed` con `origin = manual`; evalúa el gate | FR-044, FR-045 |
| `reject_case` | D | `escalated` | `reason` | pasa a `rejected` (`advisor_rejected`) | FR-044 |
| `return_to_agent` | D | `escalated` | `note` | resuelve el ticket, regresa a `active` | FR-044 |
| `revoke_ok` | D | `ok_for_lender` | `reason` | pasa a `escalated` con ticket `ok_revoked`; evento `ok_revoked` | FR-050 |

Escalaciones automáticas que hace `actions_api` dentro de otras tools (auditadas con
`actor = system`): `mismatch_persisted`, `provider_failure`, `no_reference_value`,
`policy_unavailable` (R-09, FR-038, FR-041).

La matriz de permisos vive en `actions_api/permissions.py` como tabla estática y tiene un test
por celda relevante (FR-004).

## Lectura (asesor y guiones de demo)

| Endpoint | Respuesta |
|---|---|
| `GET /cases?status=&stage=` | lista de `CaseSummary` |
| `GET /cases/{id}` | `CaseView` completo (`CaseState` + `stage`, `status`, `version`) |
| `GET /escalations?status=open` | lista de `Escalation` |
| `GET /escalations/{id}` | `Escalation` |
| `GET /cases/{id}/audit` | lista ordenada de `AuditEntry` |
| `GET /metrics` | `MetricsReport` (data-model § Reporte) |

`GET /cases/{id}` es también lo que usa el agente para leer `version`, `stage` y `status` al
inicio de cada turno.
