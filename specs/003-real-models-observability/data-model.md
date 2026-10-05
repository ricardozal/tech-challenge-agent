# Data Model: Modelos reales y observabilidad

La feature no agrega tablas ni cambia el estado del caso. Sus datos viven en archivos versionados
(`fixtures/llm/`, `eval/`), en memoria del gateway (uso de fixtures) y en Phoenix (trazas).

## Respuesta grabada (`fixtures/llm/<task>/<key>.json`)

| Campo | Tipo | Regla |
|---|---|---|
| `request` | objeto | entrada de la tarea: `ExtractRequest`, `{"sha256"}` de OCR o `ReplyRequest` |
| `response` | objeto | salida validada: `data` de extracción, `{"text"}` de OCR o de respuesta |
| `origin` | `recorded` \| `seeded` | ausente se lee como `seeded` |
| `model` | texto | `gemma4:12b` o `glm-ocr` |
| `recorded_at` | fecha-hora ISO 8601 UTC | |
| `schema_version` | entero | versión de `eval/esquemas.json` al grabar |
| `prompt_version` | entero | `contracts.llm.PROMPT_VERSION` al grabar |
| `latency_ms` | número \| ausente | solo `recorded`: duración de la llamada a Ollama del intento válido (el que se reproduce); un intento inválido previo no se suma |
| `prompt_tokens`, `completion_tokens` | entero \| ausente | solo `recorded`: los que reporta Ollama para el intento válido |

- **Identidad**: `key = fixture_key(task, schema_name, inputs)` con `schema_version` y
  `prompt_version` dentro del hash (O-10). Mismo request + misma versión → misma llave.
- **Ciclo de vida**: `seeded` (siembra) → `recorded` en `_recording/` (grabación) → `recorded` en
  `fixtures/llm/` (promoción tras demo exitoso) → huérfano si ningún demo lo usa (se borra con
  `make fixtures-status PRUNE=1`). Una grabación nunca se edita a mano.
- **Validación**: `response` de extracción cumple el esquema (reducido si hay etapa) de su
  `schema_version`; en `fake`, un fixture que no lo cumple produce `invalid_model_output`.

## Esquema por etapa (`eval/esquemas.json` → `etapas`)

| Campo | Tipo | Regla |
|---|---|---|
| llave | valor de `Stage` | `eligibility`, `profiling`, `simulation`, `documents` |
| valor | lista de nombres de campo | subconjunto de `mensaje.schema.properties.campos.properties` |

El esquema efectivo de una extracción es función pura de `(schema_name, stage, esquemas.json)`.

## Uso de respuestas grabadas (memoria de `llm_gateway`)

| Campo | Tipo | Regla |
|---|---|---|
| `counts` | `{recorded, seeded, missing}` enteros | solo se incrementa en `fake` |
| `by_task` | `{task: {origin: [key]}}` | llaves en orden de uso, sin repetir |

Se reinicia con `DELETE /v1/fixtures/usage` o al reiniciar el contenedor. No se persiste.

## Traza de turno (Phoenix, proyecto `tech-challenge-agent`)

| Elemento | Origen | Contenido |
|---|---|---|
| Traza | span raíz `turn` | un turno = una traza; `session.id` = id del caso |
| Paso: etapa | nodo de LangGraph (`CHAIN`) | nombre, orden, duración, estado |
| Paso: tool | `Deps.call_tool` (`TOOL`) | nombre, actor, entrada, desenlace |
| Paso: tarea del modelo | gateway (`CHAIN`) | tarea, modo, esquema, etapa, llave |
| Paso: llamada al modelo | gateway (`LLM`) | modelo, entrada, salida, latencia, tokens, intento, reproducción |
| Paso: lectura de documento | doc_intel (`CHAIN`) | tipo detectado y confianza por campo |

Atributos exactos en [contracts/tracing.md](./contracts/tracing.md). Relación: un caso tiene
muchas trazas (una por turno); una traza tiene un árbol de pasos.

## Corrida de medición (`eval/resultados/gate-<fecha-hora>.json`)

| Campo | Tipo | Regla |
|---|---|---|
| `summary.at` | fecha-hora | |
| `summary.mode`, `summary.model`, `summary.schema_version`, `summary.prompt_version` | | de `/health` |
| `summary.cases`, `summary.correct_fields`, `summary.fields` | enteros | sobre todo el set |
| `summary.fields_pct`, `summary.valid_json_pct` | número (1 decimal) | |
| `summary.by_type` | `{mensaje, documento}` → `{correct, fields, pct}` | informativo |
| `summary.median_seconds` | `{mensaje, documento}` | latencia por caso |
| `summary.failed_cases` | lista de ids | JSON inválido o algún campo incorrecto |
| `summary.passed` | booleano | `fields_pct ≥ 85` y `valid_json_pct = 100` |
| `rows[]` | `{case, ok, n, seconds, data}` | igual que hoy |

- **Puntaje por caso** (sin cambios, regla de `eval/esquemas.json` → `puntaje`): n = 1 + campos
  esperados; números y booleanos exactos; texto normalizado; `null` solo para `null` esperado;
  cada campo extra no nulo resta 1 (mínimo 0). Un caso con error HTTP cuenta como JSON inválido y
  0 correctos.
- **Estado**: inmutable una vez escrito.
