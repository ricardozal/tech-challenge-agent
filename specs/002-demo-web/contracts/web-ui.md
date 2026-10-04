# Contrato: interfaz web (`web`, puerto 8080)

Qué expone la web a quien hace la demo y qué llama de cada API. Las llamadas a las APIs siguen los
contratos de 001: [agent-channel.md](../../001-credit-agent-core/contracts/agent-channel.md) y
[actions-api.md](../../001-credit-agent-core/contracts/actions-api.md), más los cambios de
[backend-changes.md](./backend-changes.md).

## Rutas

| Ruta | Vista | FR |
|---|---|---|
| `/` | redirige a `/chat` | FR-053 |
| `/chat` | selector de escenarios | FR-056 |
| `/chat?scenario={id}&case={uuid}` | conversación del caso (recargable) | FR-057–FR-064 |
| `/asesor` | bandeja de escalaciones, buscador de casos y métricas | FR-065, FR-072, FR-073 |
| `/asesor?case={uuid}` | detalle del caso: ticket, evidencia, timeline y acciones | FR-066–FR-071 |

nginx responde `index.html` para cualquier ruta no estática; `/documents/*.png` y
`/scenarios.json` son estáticos.

## Llamadas por vista

**Chat** (escribe solo por el canal del agente, FR-054):

| Momento | Llamada |
|---|---|
| elegir escenario | `POST {AGENT}/cases` con `Idempotency-Key` |
| enviar texto o sugerencia | `POST {AGENT}/cases/{id}/messages` `{"text"}` con `Idempotency-Key` |
| enviar documento de ejemplo | `fetch('/documents/x.png')` → `POST {AGENT}/cases/{id}/documents` (`multipart`: `file`, `requested_type`) con `Idempotency-Key` |
| tras cada turno y al recargar | `GET {AGENT}/cases/{id}/conversation`, `GET {ACTIONS}/cases/{id}` |
| resultado escalado | `GET {ACTIONS}/escalations/{open_escalation_id}`; sondeo de `GET {ACTIONS}/cases/{id}` cada 5 s mientras `status = escalated` |

**Consola** (escribe solo con `POST {ACTIONS}/tools/{name}` y `X-Actor: advisor`, FR-054, FR-068):

| Momento | Llamada |
|---|---|
| bandeja | `GET {ACTIONS}/escalations?status=open` + `GET {ACTIONS}/cases/{case_id}` |
| casos | `GET {ACTIONS}/cases` |
| detalle | `GET {ACTIONS}/cases/{id}`, `GET {ACTIONS}/escalations/{id}`, `GET {ACTIONS}/cases/{id}/audit`, `GET {ACTIONS}/policies/{policy_version}` |
| acción | `POST {ACTIONS}/tools/{name}` con `{"context": {"case_id", "idempotency_key", "expected_version"}, "input": {…}}` |
| métricas | `GET {ACTIONS}/metrics` |

## Comportamiento garantizado

- Todo el texto visible está en español; los códigos se traducen con `labels.ts` (W-12).
- Ningún texto de cliente, documento, ticket o registro se inserta como HTML (FR-055).
- Un envío en curso deshabilita nuevos envíos; reintentar reutiliza la misma llave de
  idempotencia (FR-063, FR-069).
- La etapa visible y el estado son los de `GET {ACTIONS}/cases/{id}` después de cada turno
  (FR-061, SC-016).

## Selectores estables para pruebas

Los elementos que usa Playwright llevan `data-testid`: `scenario-{id}`, `stage`, `status`,
`result`, `result-reason`, `suggestion`, `message-input`, `send`, `typing`, `document-{file}`,
`restart`, `inbox-item-{case_id}`, `evidence`, `field-{doc}-{name}`, `timeline-entry`,
`action-{tool}`, `action-submit`, `action-error`, `metrics`.
