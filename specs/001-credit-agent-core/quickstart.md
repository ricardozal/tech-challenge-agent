# Quickstart: validar la feature 001 de punta a punta

**Feature**: `001-credit-agent-core` · **Plan**: [plan.md](./plan.md)

Guía para comprobar que la feature funciona. No contiene implementación; los contratos están en
[contracts/](./contracts/README.md) y el modelo en [data-model.md](./data-model.md).

## Requisitos

- Docker con Compose v2.
- `uv` (Python 3.12 lo instala `uv`).
- Solo para `LLM_MODE=ollama|record` y `make eval`: Ollama en el host con `gemma4:12b` y
  `glm-ocr` descargados (`ollama pull gemma4:12b && ollama pull glm-ocr`).

## 1. Levantar el stack sin GPU

```bash
uv sync
make up            # docker compose up -d --build; LLM_MODE=fake por defecto
make ps            # postgres, actions_api, agent, llm_gateway, doc_intel en estado healthy
```

**Esperado**: 5 contenedores sanos; `llm_gateway` reporta `mode=fake` en `GET /health`.

## 2. Correr los demos

| Comando | Guion | Resultado esperado |
|---|---|---|
| `make demo-happy-path` | Demo 1 | `status = ok_for_lender`; el registro muestra `gate_passed` con `actor = system` |
| `make demo-eligibility-rejection` | Demo 2 | `status = rejected`, `owner_mismatch`; ninguna llamada a `run_credit_check` |
| `make demo-document-correction` | Demo 3, rama A | primer comprobante con `income` en `mismatch`, el cliente corrige, `status = ok_for_lender` |
| `make demo-document-escalation` | Demo 3, rama B | `income` falla 3 veces (N = 2), `status = escalated`, ticket `mismatch_persisted` con resumen y acción sugerida |
| `make demo-no-spare-key` | Demo 4 | evento `key_quoted`; cada opción con `key_cost > 0` y `client_amount = financed_amount − key_cost`; `status = ok_for_lender` |

Cada demo imprime la conversación, el estado final del caso (`GET /cases/{id}`) y su registro de
acciones (`GET /cases/{id}/audit`). Cada uno termina en menos de 2 minutos (SC-002).

## 3. Resolver una escalación como asesor

Después de `make demo-document-escalation`:

```bash
make advisor-open-escalations           # GET /escalations?status=open
make advisor-verify CASE=<id> KEY=income JUSTIFICATION="Ingreso confirmado por llamada"
```

**Esperado**: la validación queda `passed` con `origin = manual`; el gate se evalúa solo y el caso
queda `ok_for_lender`. La entrada de auditoría tiene `actor = advisor` (FR-044, FR-045).

## 4. Tests

```bash
make test               # reglas, tools, gateway, doc_intel y agente (Postgres y, para el agente, el compose)
make test-arch          # import-linter + permisos de BD + registro inmutable + compose (R-20)
make test-e2e           # los 5 guiones, concurrencia, reproducibilidad y métricas contra el compose (LLM_MODE=fake)
make traceability       # regenera TRACEABILITY.md; falla si un FR no tiene test
```

**Esperado**: todo en verde; `TRACEABILITY.md` lista FR-001…FR-052 sin huecos.

Verificaciones puntuales que cubren los tests:

- **Concurrencia (SC-005)**: `tests/e2e/test_concurrency.py` envía 50 pares de mensajes
  simultáneos; cada uno termina procesado o con `409 case_busy`, sin pérdida de datos.
- **Registro inmutable (SC-009)**: un `UPDATE` o `DELETE` sobre `audit.audit_log` falla.
- **Reproducibilidad (SC-001, SC-002)**: `tests/e2e/test_reproducibility.py` corre cada guion 10 veces
  y exige el mismo estado final y la misma secuencia de acciones, cada corrida en menos de 2 minutos.
  `make demo-all REPEAT=10` hace lo mismo desde la terminal.

## 5. Reporte de observabilidad

```bash
make metrics            # GET /metrics después de correr los demos
```

**Esperado**: rechazos por auto por motivo, falsos OK, mismatches por tipo y casos con llave
cotizada; cada cifra coincide con contar los eventos en `audit.audit_log` (SC-008).

## 6. Calidad del LLM (requiere Ollama)

```bash
LLM_MODE=ollama make up
make eval               # ≥ 85% de campos correctos y 100% de JSON válido, o falla
```

## 7. Regrabar fixtures (requiere Ollama)

```bash
LLM_MODE=record make up
make demo-all           # graba fixtures/llm/** de cada llamada
LLM_MODE=fake make up && make test-e2e
```

**Esperado**: los e2e siguen en verde con los fixtures nuevos.
