# Data Model: Núcleo del agente de crédito con garantía vehicular

**Feature**: `001-credit-agent-core` · **Fecha**: 2026-10-03 · **Plan**: [plan.md](./plan.md)

Los modelos Pydantic de [packages/contracts](./contracts/README.md) son la fuente de verdad; este
documento describe su forma y sus reglas. Montos en `Decimal` serializados como string (R-17).
Fechas en ISO 8601; las reglas reciben la fecha de evaluación como parámetro.

## Glosario spec → código

| Spec (español) | Código | Tipo |
|---|---|---|
| Caso | `Case` / `CaseState` | modelo |
| Etapa: elegibilidad, perfilamiento, simulación, documentos (+ validación) | `Stage.eligibility`, `profiling`, `simulation`, `documents` | enum |
| Estado: en curso, escalado, OK para financiera, rechazado, cancelado | `Status.active`, `escalated`, `ok_for_lender`, `rejected`, `cancelled` | enum |
| Agente, asesor, sistema | `Actor.agent`, `advisor`, `system` | enum |
| Cliente (actúa vía agente) | `on_behalf_of = "client"` | campo de auditoría |
| Registro de acciones | `audit.audit_log` / `AuditEntry` | tabla / modelo |
| Ticket de escalación | `Escalation` | tabla / modelo |
| Gate "OK para financiera" | tool `evaluate_gate` | tool |
| Política | `Policy` (`policy/policy.yaml`) | modelo / archivo |
| Identificación, recibo de nómina, estado de cuenta, comprobante de domicilio, factura | `DocumentType.identification`, `payslip`, `bank_statement`, `proof_of_address`, `vehicle_invoice` | enum |
| Empleado, independiente, pensionado, desempleado | `Employment.employed`, `self_employed`, `retired`, `unemployed` | enum |

La etapa "validación" de la spec no es una etapa aparte: las validaciones corren dentro de
`documents` cada vez que llega un documento, y el gate se evalúa al cambiar cualquiera (R-08).

Los valores del LLM en español (`eval/esquemas.json`) se traducen a estos enums en una sola
función de `contracts` (`contracts.llm.to_domain`) (R-01).

## Enums

| Enum | Valores |
|---|---|
| `Stage` | `eligibility`, `profiling`, `simulation`, `documents` |
| `Status` | `active`, `escalated`, `ok_for_lender`, `rejected`, `cancelled` |
| `Actor` | `agent`, `advisor`, `system` |
| `DocumentType` | `identification`, `payslip`, `bank_statement`, `proof_of_address`, `vehicle_invoice`, `other` |
| `Employment` | `employed`, `self_employed`, `retired`, `unemployed` |
| `Periodicity` | `weekly`, `biweekly`, `monthly` |
| `ValidationType` | `income`, `name`, `address`, `validity`, `income_proof_type`, `vehicle_ownership` |
| `ValidationResult` | `passed`, `mismatch`, `low_confidence` |
| `ValidationOrigin` | `system`, `manual` |
| `RejectionReason` | `owner_mismatch`, `lien_or_debt`, `no_offer_for_profile`, `advisor_rejected` |
| `EscalationReason` | `mismatch_persisted`, `client_requested_human`, `sensitive_topic`, `provider_failure`, `no_reference_value`, `ok_revoked`, `policy_unavailable` |
| `Outcome` (auditoría) | `accepted`, `rejected` |

## Entidades

### Case (`cases.cases` + `state JSONB`)

| Campo | Tipo | Notas |
|---|---|---|
| `id` | UUID | también `thread_id` del grafo del agente |
| `stage` | `Stage` | columna de consulta |
| `status` | `Status` | columna de consulta |
| `version` | int | empieza en 1; `+1` en cada acción aceptada (FR-006) |
| `policy_version` | str | fijada al crear el caso (R-14) |
| `created_at`, `updated_at` | timestamptz | |
| `state` | `CaseState` (JSONB) | agregado validado por Pydantic (R-07) |

### CaseState (JSONB)

| Sección | Campos |
|---|---|
| `client` | `full_name`, `address` (texto libre), `postal_code`, cada uno con `source_message_id` — declarados en la conversación (R-16) |
| `declared` | `employment`, `income_amount`, `income_currency` (default `MXN`), `income_periodicity`, `bureau_consent` (bool), `bureau_consent_at`, `bureau_consent_message_id` |
| `vehicle` | `make`, `model`, `year`, `own_name` (bool\|null), `declared_debt` (bool\|null), `spare_key` (bool\|null), `registry` (`lien`, `reference_value`, `checked_at`) |
| `key_quote` | `amount`, `provider_quote_id`, `quoted_at` — solo si no hay segunda llave |
| `profile` | `bureau_score`, `band`, `max_amount_profile`, `annual_rate`, `standard_term_months`, `max_financeable` (= min(perfil, % valor del auto)) |
| `options` | lista de `CreditOption` |
| `selected_option_id` | str\|null |
| `documents` | lista de `DocumentRecord` |
| `validations` | dict `ValidationKey` → `Validation` (última por llave) |
| `attempts` | dict `ValidationType` → int (resultados ≠ `passed`) |
| `decisions` | lista de `Decision` |
| `messages` | lista de `MessageRef` (id, autor, texto, intención, fecha) |
| `open_escalation_id` | UUID\|null |

### CreditOption

| Campo | Tipo | Regla |
|---|---|---|
| `id` | str | `opt-<pct>` |
| `pct_of_max` | Decimal | de `policy.options.pcts_of_max` |
| `financed_amount` | Decimal | `pct × profile.max_financeable` |
| `key_cost` | Decimal | `key_quote.amount` o 0 |
| `client_amount` | Decimal | `financed_amount − key_cost`; si ≤ 0 la opción no se genera; si no queda ninguna, `no_offer_for_profile` (FR-020) |
| `term_months` | int | `profile.standard_term_months` |
| `annual_rate` | Decimal | `profile.annual_rate` |
| `monthly_payment` | Decimal | amortización francesa (R-17) |
| `policy_version` | str | |

### DocumentRecord

| Campo | Tipo | Notas |
|---|---|---|
| `id` | UUID | |
| `requested_type` | `DocumentType` | lo que pidió el agente |
| `detected_type` | `DocumentType` | lo que devolvió `doc_intel`; si difiere → tipo inesperado (FR-026) |
| `sha256` | str | nombre del archivo en el volumen `documents` |
| `is_test_specimen` | bool | el OCR contiene la marca de prueba (Principio X) |
| `fields` | dict `str` → `ExtractedField` (`value`, `confidence`) | (R-10) |
| `received_at` | timestamptz | |

### Validation

| Campo | Tipo | Notas |
|---|---|---|
| `key` | `ValidationKey` | `type` + `document_type` opcional, p. ej. `name@identification` |
| `type` | `ValidationType` | |
| `result` | `ValidationResult` | |
| `origin` | `ValidationOrigin` | `manual` solo vía `verify_validation_manually` (FR-045) |
| `detail` | dict | valores comparados, umbral aplicado, diferencia |
| `evidence` | list | ids de documento y campos usados |
| `justification` | str\|null | obligatoria si `origin = manual` |
| `attempt` | int | |
| `policy_version` | str | (FR-048) |

**Validaciones requeridas por el gate** (todas en `passed`):

| Llave | Documento | Regla (FR) |
|---|---|---|
| `income` | comprobante de ingresos | monto normalizado al periodo del declarado dentro de ± tolerancia y misma moneda (FR-027) |
| `income_proof_type` | comprobante de ingresos | tipo aceptado para `declared.employment` (FR-031) |
| `name@identification` | identificación | similitud ≥ umbral (FR-028, FR-029) |
| `name@income_proof` | comprobante de ingresos | similitud ≥ umbral (FR-028) |
| `address@proof_of_address` | comprobante de domicilio | CP idéntico y calle + número ≥ umbral (FR-028, FR-029) |
| `validity@identification` | identificación | `vigencia` ≥ fecha de evaluación (FR-030) |
| `validity@income_proof` | comprobante de ingresos | `fecha_emision`/`periodo_fin` ≤ N meses (FR-030) |
| `validity@proof_of_address` | comprobante de domicilio | `fecha_emision` ≤ N meses (FR-030) |
| `vehicle_ownership` | factura | titular ≈ cliente y marca, modelo, año = declarados (FR-032) |

Si un campo que usa la regla tiene `confidence < policy.documents.min_field_confidence`, el
resultado es `low_confidence` y el valor no se usa (FR-033).

### Decision

`kind` (`eligibility`, `profile`, `options`, `gate`, `rejection`, `ok_revocation`), `result`,
`reason`, `actor`, `inputs` (resumen), `policy_version`, `at`.

### Escalation (`cases.escalations`)

| Campo | Tipo | Notas |
|---|---|---|
| `id` | UUID | |
| `case_id` | UUID | |
| `reason` | `EscalationReason` | |
| `evidence` | JSONB | validaciones, documentos y mensajes relevantes |
| `summary` | text | plantilla en español con el estado del caso (R-09) |
| `suggested_action` | text | tabla motivo → acción (R-09) |
| `agent_note` | text\|null | solo si escaló el agente |
| `status` | `open` \| `resolved` | |
| `resolution` | JSONB\|null | tool usada, asesor, motivo |
| `created_at`, `resolved_at` | timestamptz | |

### AuditEntry (`audit.audit_log`, solo inserción)

| Campo | Tipo |
|---|---|
| `id` | bigserial |
| `case_id` | UUID |
| `at` | timestamptz |
| `actor` | `Actor` |
| `on_behalf_of` | `"client"` \| null |
| `tool` | str |
| `stage_before`, `status_before` | enums |
| `stage_after`, `status_after` | enums \| null |
| `idempotency_key` | str |
| `expected_version`, `case_version_after` | int |
| `outcome` | `Outcome` |
| `rejection_code` | str \| null (`forbidden`, `version_conflict`, `invalid_input`, `gate_not_met`, `case_closed`…) |
| `input` | JSONB (sin bytes de documentos; solo `sha256`) |
| `result` | JSONB |
| `events` | JSONB — lista de eventos de negocio que produjo la acción (ver abajo) |
| `policy_version` | str |

**Eventos de negocio** (en `events`, base del reporte de P5):
`vehicle_rejected{reason}`, `key_quoted{amount}`, `profile_assigned{band}`,
`validation_recorded{key, result}`, `escalated{reason}`, `gate_passed`, `gate_failed{missing}`,
`ok_revoked{reason}`, `case_cancelled`.

### Idempotency (`cases.idempotency_keys`)

`(case_id, idempotency_key)` PK, `tool`, `request_hash`, `response JSONB`, `created_at`. Si la
misma llave llega con otro `request_hash`, la respuesta es `409 idempotency_mismatch`.

## Transiciones de estado

### Etapa (solo con `status = active`)

```text
eligibility ──evaluate_eligibility: elegible──▶ profiling
profiling ──run_credit_check: perfil con oferta──▶ simulation
simulation ──simulate_options + select_option──▶ documents
documents ──(validaciones; gate automático)──▶ (status ok_for_lender)
```

`update_declared_data` con un ingreso corregido en `documents` invalida perfil y opciones y
regresa a `profiling` (edge case "corrección de datos declarados").

### Estado

```text
active ──evaluate_eligibility: owner/lien──▶ rejected
active ──run_credit_check o simulate_options: sin oferta──▶ rejected
active ──evaluate_gate: todo passed──▶ ok_for_lender
active ──escalate | auto (N intentos, proveedor, sin valor)──▶ escalated
active ──cancel_case──▶ cancelled
escalated ──return_to_agent──▶ active
escalated ──verify_validation_manually → evaluate_gate: todo passed──▶ ok_for_lender
escalated ──reject_case──▶ rejected
escalated ──cancel_case (agente en nombre del cliente o asesor)──▶ cancelled
escalated ──request_correction──▶ active (stage = documents)
ok_for_lender ──revoke_ok──▶ escalated
```

`rejected` y `cancelled` son finales: toda tool de negocio responde `case_closed` (FR-016,
FR-046). Con `status = escalated`, las tools de negocio con `actor = agent` responden
`forbidden` (FR-043); el agente solo puede `append_message` y `cancel_case` en nombre del
cliente, que además resuelve el ticket abierto.

## Política (`policy/policy.yaml`)

```yaml
policy_version: "2026.10-v1"
profile_bands:            # por score de Buró, de mayor a menor
  - {band: A, min_score: 700, max_amount: "150000", annual_rate: "0.24", standard_term_months: 24}
  - {band: B, min_score: 620, max_amount: "100000", annual_rate: "0.32", standard_term_months: 24}
  - {band: C, min_score: 550, max_amount: "60000",  annual_rate: "0.42", standard_term_months: 18}
vehicle:
  max_financeable_pct_of_value: "0.50"
options:
  pcts_of_max: ["1.00", "0.75", "0.50"]
pricing:
  apply_vat_on_interest: true
  vat_rate: "0.16"
income:
  tolerance_pct: "0.10"
  expected_currency: MXN
  accepted_proofs:
    employed: [payslip, bank_statement]
    self_employed: [bank_statement]
    retired: [bank_statement]
    unemployed: []
documents:
  min_field_confidence: "0.80"
  max_age_months: {payslip: 3, bank_statement: 3, proof_of_address: 3}
matching:
  name_similarity_threshold: "0.90"
  address_similarity_threshold: "0.90"
escalation:
  max_correction_attempts: 2       # escala al resultado fallido número N + 1
  provider_retries: 2
```

Un score bajo la banda más baja, o `employment = unemployed`, produce `no_offer_for_profile`
(FR-020).

## Reporte de observabilidad (`GET /metrics`)

Calculado solo desde `audit.audit_log` (FR-049, SC-008), sin leer `cases.cases`:

| Métrica | Fuente |
|---|---|
| Rechazos por auto, por motivo | eventos `vehicle_rejected{reason}` |
| Falsos OK, por motivo | eventos `ok_revoked{reason}` (FR-050) |
| Mismatches por tipo | eventos `validation_recorded` con `result ≠ passed`, agrupados por `key.type` |
| Casos con llave cotizada | `case_id` distintos con evento `key_quoted` |

Mismo registro → mismo reporte (consulta determinista y ordenada).
