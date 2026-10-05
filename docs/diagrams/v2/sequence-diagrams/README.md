# Diagramas de secuencia de los 4 demos

Cada diagrama sigue lo que ejecuta el guion del demo (`fixtures/scenarios/*.yaml`) y las acciones que quedan en el
registro de auditoría al correrlo (`make demo-*`). Los textos entre comillas son los mensajes del guion.

| Demo | Diagrama | Comando |
|---|---|---|
| 1 · Happy path | [1-happy-path.md](1-happy-path.md) | `make demo-happy-path` |
| 2 · Rechazo por elegibilidad | [2-eligibility-rejection.md](2-eligibility-rejection.md) | `make demo-eligibility-rejection` |
| 3 · Validación documental fallida (A: corrección · B: escalación y asesor) | [3-document-validation.md](3-document-validation.md) | `make demo-document-correction` · `make demo-document-escalation` |
| 4 · Sin segunda llave | [4-no-spare-key.md](4-no-spare-key.md) | `make demo-no-spare-key` |

Participantes: el **cliente** (chat `/chat` o el guion), **agent**, **llm_gateway**, **actions_api** (Case Actions
API), **doc_intel** y los **proveedores simulados** con fixtures (consulta vehicular, cotizador de llave, Buró). Con
`LLM_MODE=fake` el gateway responde con respuestas grabadas del modelo real; con `LLM_MODE=ollama` llama a
`gemma4:12b` y `glm-ocr`. El flujo es el mismo en ambos modos.

Para que los demos se lean, cada diagrama detalla el primer turno y abrevia los siguientes. Todos siguen uno de
estos dos patrones.

## Patrón de un turno de mensaje

```mermaid
sequenceDiagram
    autonumber
    actor C as Cliente
    participant A as agent
    participant L as llm_gateway
    participant API as actions_api

    C->>A: POST /cases/{id}/messages (Idempotency-Key)
    Note over A: Turn Guard toma el candado del caso<br/>y abre el span raíz turn
    A->>API: GET /cases/{id} (etapa, estado, versión)
    A->>L: /v1/extract con el esquema de la etapa
    L-->>A: intención + campos (JSON validado contra el esquema)
    A->>API: append_message (el mensaje queda como evidencia)
    A->>API: tools de la etapa (p. ej. update_declared_data)
    Note over API: candado → idempotencia → versión esperada → permisos<br/>→ reglas puras con la política → auditoría
    API-->>A: outcome + etapa, estado y versión nuevos
    A->>L: /v1/reply con hechos estructurados + siguiente pregunta
    L-->>A: respuesta en español
    Note over A: la respuesta termina con la pregunta exacta<br/>que decidió el código (questions.py)
    A->>API: append_message (respuesta del agente)
    A-->>C: respuesta + etapa y estado del caso
```

## Patrón de un turno de documento

```mermaid
sequenceDiagram
    autonumber
    actor C as Cliente
    participant A as agent
    participant L as llm_gateway
    participant API as actions_api
    participant D as doc_intel

    C->>A: POST /cases/{id}/documents (archivo + tipo pedido)
    A->>API: append_message
    A->>API: submit_document
    API->>D: /v1/documents/extract
    D->>L: /v1/ocr (glm-ocr)
    L-->>D: texto del documento
    D->>L: /v1/extract con el esquema de documento
    L-->>D: tipo detectado + campos
    D-->>API: tipo detectado + campos con confianza
    Note over API: validaciones puras del tipo de documento<br/>(confianza < 0.80 → low_confidence, nunca OK)
    Note over API: si cambió una validación, el sistema evalúa el gate
    API-->>A: validaciones + etapa y estado
    A->>L: /v1/reply (siguiente documento o corrección)
    A-->>C: respuesta
```

Validaciones por tipo de documento: identificación → nombre y vigencia · comprobante de ingresos → ingreso vs
declarado (±10%, mismo período y moneda), tipo de comprobante aceptado según la situación laboral, nombre y vigencia
· comprobante de domicilio → domicilio y vigencia · factura → titularidad del vehículo.
