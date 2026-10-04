# Contrato: canal del agente (`agent`)

API de mensajes y documentos por caso (FR-001). Es lo único que llaman los guiones de demo y
los e2e. Modelos en `contracts.channel`.

## `POST /cases`

```json
{"test_client_id": "laura-mendez"}
```

→ `201` `{"case_id": "6f1c…", "reply": "Hola Laura, …", "stage": "eligibility", "status": "active"}`

Crea el caso con la tool `create_case` y devuelve el saludo con la primera pregunta.

## `POST /cases/{case_id}/messages`

```http
Idempotency-Key: demo-happy-03
```
```json
{"text": "sí, está a mi nombre y no debo nada"}
```

→ `200` `TurnResponse`:

```json
{
  "message_id": "msg-0003",
  "reply": "Perfecto. ¿Tienes la segunda llave del auto?",
  "case": {"stage": "eligibility", "status": "active", "version": 4},
  "tool_calls": [{"tool": "update_declared_data", "outcome": "accepted"}]
}
```

- `Idempotency-Key` obligatorio. Un reenvío con la misma llave devuelve el mismo
  `TurnResponse` sin reprocesar (se guarda en `agent.processed_messages`).
- `tool_calls` es informativo, para los guiones de demo.
- `409 case_busy` si otro turno del mismo caso tiene el candado más de `CASE_LOCK_TIMEOUT_S`
  (R-04). El mensaje no se procesa y puede reenviarse.

## `POST /cases/{case_id}/documents`

`multipart/form-data` con `file` y `requested_type`, más `Idempotency-Key`. → `200`
`TurnResponse` (el agente llama `submit_document` y responde con el resultado de las
validaciones o la corrección que pide).

## `GET /cases/{case_id}/conversation`

Mensajes de la conversación (cliente y agente) leídos del checkpoint, para el guion de demo.

## Comportamiento garantizado

- Respuestas siempre en español (FR-001).
- Con `status = escalated`, el agente responde que un asesor tomará el caso y no ejecuta tools de
  negocio (FR-043).
- Con `status` final (`ok_for_lender`, `rejected`, `cancelled`), el agente informa el estado y no
  ejecuta tools de negocio.
