# Contrato: trazas de un turno

Qué spans produce cada servicio, cómo se enlazan y qué atributos llevan. Convenciones
OpenInference (`openinference.span.kind`, `input.value`, `output.value`, `llm.*`, `tool.*`,
`session.id`, `metadata`). Proyecto de Phoenix: `tech-challenge-agent`. Decisiones en
[research.md](../research.md) O-02…O-09.

## Árbol de un turno

Turno de mensaje:

```text
turn                                   AGENT   agent        (raíz, una por turno)
├── LangGraph                          CHAIN   agent        (instrumentado, sin entrada/salida)
│   ├── interpret                      CHAIN   agent
│   │   ├── POST llm_gateway/v1/extract  CLIENT  agent (httpx)
│   │   │   └── POST /v1/extract       SERVER  llm_gateway (FastAPI)
│   │   │       └── extract            CHAIN   llm_gateway
│   │   │           ├── gemma4:12b     LLM     llm_gateway   (intento 1)
│   │   │           └── gemma4:12b     LLM     llm_gateway   (intento 2, solo si el 1 fue inválido)
│   │   └── append_message             TOOL    agent
│   │       └── POST actions_api/tools/append_message  CLIENT  agent (httpx)
│   ├── stage_eligibility              CHAIN   agent
│   │   └── update_declared_data       TOOL    agent
│   │       └── …
│   └── respond                        CHAIN   agent
│       └── … reply                    CHAIN   llm_gateway
│           └── gemma4:12b             LLM     llm_gateway
```

Turno de documento (la lectura cuelga de la tool que la dispara):

```text
turn                                   AGENT   agent
└── LangGraph / documents              CHAIN   agent
    ├── submit_document              TOOL    agent
    │   └── POST actions_api/tools/submit_document   CLIENT agent (httpx)
    │       └── (actions_api: solo propaga, no exporta)
    │           └── POST /v1/documents/extract  SERVER  doc_intel (FastAPI)
    │               └── read_document   CHAIN   doc_intel
    │                   ├── … ocr       CHAIN   llm_gateway
    │                   │   └── glm-ocr LLM     llm_gateway
    │                   └── … extract   CHAIN   llm_gateway
    │                       └── gemma4:12b LLM  llm_gateway
    └── respond                        CHAIN   agent
```

Reglas:

- Exactamente un span `turn` por ejecución del grafo; un reintento resuelto por idempotencia (el
  agente devuelve la respuesta guardada) no abre `turn`.
- El contexto viaja en `traceparent` (W3C) por `httpx` instrumentado; los servidores lo extraen con
  la instrumentación de FastAPI. `actions_api` propaga sin exportar (O-06).
- `GET /health` no se traza en ningún servicio.
- Las peticiones que no son turnos (lecturas de la web, acciones del asesor, `make eval`) no
  producen `turn`; si pasan por el gateway o `doc_intel` aparecen como trazas propias sin raíz
  `turn`.

## Atributos por span

### `turn` (agent, `AGENT`)

| Atributo | Valor |
|---|---|
| `session.id` | id del caso |
| `metadata.case_id`, `metadata.message_id`, `metadata.kind` | `start` · `message` · `document` |
| `metadata.stage_before`, `metadata.status_before` | etapa y estado al iniciar |
| `metadata.stage_after`, `metadata.status_after`, `metadata.version_after` | al terminar |
| `input.value` | texto del cliente (redactado) o `documento: <tipo pedido>` |
| `output.value` | respuesta al cliente (redactada) |
| estado | `ERROR` si el turno termina en `upstream_failure` o excepción |

### Nodo de LangGraph (agent, `CHAIN`)

Nombre del nodo (`interpret`, `stage_<etapa>`, `intent_<intención>`, `documents`, `respond`),
orden y duración. Sin `input.value` ni `output.value` (`TraceConfig(hide_inputs, hide_outputs)`).

### Tool (agent, `TOOL`)

| Atributo | Valor |
|---|---|
| `tool.name` | nombre de la tool del catálogo |
| `metadata.actor` | `agent` (o `client` con `on_behalf_of`) |
| `metadata.idempotency_key`, `metadata.expected_version` | del `ToolContext` |
| `input.value` | entrada de la tool, JSON redactado |
| `output.value` | `{"outcome", "rejection_code", "stage", "status", "version"}` |
| estado | `ERROR` con descripción = código de rechazo si `outcome=rejected` |

### Tarea del gateway (llm_gateway, `CHAIN`: `extract` · `ocr` · `reply`)

| Atributo | Valor |
|---|---|
| `metadata.task`, `metadata.mode` | `extract|ocr|reply`, `fake|record|ollama` |
| `metadata.schema_name`, `metadata.stage`, `metadata.schema_version` | solo `extract` |
| `metadata.fixture_key` | llave de la respuesta grabada |
| `input.value` / `output.value` | entrada y salida de la tarea (redactadas). OCR: entrada = sha256 y MIME, salida = `{"chars": n}` como en los logs (R-22); el texto leído aparece redactado como entrada de la extracción que sigue |
| estado | `ERROR` si termina en `invalid_model_output`, `fixture_missing` o `upstream_failure` |

### Llamada al modelo (llm_gateway, `LLM`)

| Atributo | Valor |
|---|---|
| `llm.provider` | `ollama` |
| `llm.model_name` | `gemma4:12b` o `glm-ocr` |
| `llm.invocation_parameters` | `{"temperature": 0, "seed": 42, "num_predict": …, "think": false}` |
| `llm.input_messages.*` / `input.value` | mensajes enviados (redactados; imagen omitida) |
| `llm.output_messages.*` / `output.value` | texto devuelto (redactado) |
| `llm.token_count.prompt`, `.completion`, `.total` | de Ollama; en `fake`, los de la grabación |
| `metadata.attempt` | 1 o 2 |
| `metadata.replay` | `true` en `fake` |
| `metadata.fixture_origin` | `recorded` · `seeded` · `missing` (solo `fake`) |
| `metadata.recorded_latency_ms` | latencia de la llamada original (solo `fake` con `recorded`) |
| estado | `ERROR` si la salida no es JSON válido contra el esquema |

En `fake` hay un único span `LLM` por tarea; sin fixture (`missing`) el span existe con estado
`ERROR` (OCR) o con la respuesta de respaldo (extracción, respuesta) y `fixture_origin=missing`.

### `read_document` (doc_intel, `CHAIN`)

| Atributo | Valor |
|---|---|
| `input.value` | `{"requested_type", "mime_type", "sha256"}` |
| `output.value` | `{"detected_type", "fields": {campo: {"confidence"}}}` (sin valores) |
| estado | `ERROR` en `upstream_failure` |

## Redacción

Todo `input.value`, `output.value` y mensaje de modelo de spans manuales pasa por
`contracts.redaction.redact` (CURP, RFC, teléfono y nombres conocidos del turno), la misma función
que usan los logs del gateway (R-22, O-09).

## Lectura en pruebas

Las pruebas leen las trazas con `arize-phoenix-client`: primero los spans `turn` del caso
(`Client(base_url="http://localhost:6006").spans.get_spans(project_identifier="tech-challenge-agent",
name="turn", attributes={"session.id": case_id})`) y luego todos los spans de esas trazas
(`get_spans(..., trace_ids=[...])`). Como la exportación es por lotes, la prueba espera con
reintentos acotados (≤ 180 s, Phoenix ingiere de forma asíncrona y tras una ráfaga de pruebas puede ir atrasado) a que lleguen.
