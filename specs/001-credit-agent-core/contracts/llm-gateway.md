# Contrato: LLM Gateway (`llm_gateway`)

Único servicio que habla con Ollama (Principio III). Modelos en `contracts.llm`. El modo
(`fake`, `record`, `ollama`) lo conoce solo este servicio (R-11).

## `POST /v1/extract`

Mensaje o texto de documento → JSON con esquema.

```json
{
  "schema_name": "mensaje",
  "stage": "eligibility",
  "agent_question": "¿El auto está a tu nombre?",
  "text": "no, está a nombre de mi esposa pero yo lo manejo diario"
}
```

→ `200`:

```json
{
  "data": {"intencion": "proporcionar_datos", "campos": {"auto_a_nombre_propio": false, "…": null}},
  "schema_name": "mensaje",
  "schema_version": 3,
  "model": "gemma4:12b",
  "mode": "fake",
  "fixture_hit": true
}
```

- `schema_name`: `mensaje` o `documento`, cargados de `eval/esquemas.json` (R-12).
- La salida siempre valida contra el esquema: todos los campos presentes, `null` si no aplican.
  Si el modelo devuelve algo inválido, el gateway reintenta una vez y si no responde `502
  invalid_model_output`.
- `text` va en un bloque delimitado del prompt, marcado como dato (Principio X).

## `POST /v1/ocr`

```json
{"content_base64": "…", "mime_type": "image/png"}
```

→ `200` `{"text": "IDENTIFICACIÓN — ESPÉCIMEN DE PRUEBA …", "model": "glm-ocr", "mode": "fake", "fixture_hit": true}`

En `fake`, la llave del fixture es el `sha256` de los bytes; sin fixture → `404
fixture_missing`.

## `POST /v1/reply`

Redacta la respuesta al cliente a partir de hechos, no de texto crudo.

```json
{
  "stage": "profiling",
  "status": "active",
  "facts": {"tool_results": [{"tool": "evaluate_eligibility", "outcome": "accepted", "key_quoted": "1850.00"}]},
  "next_question": "¿Cuál es tu situación laboral?",
  "client_first_name": "Laura"
}
```

→ `200` `{"text": "…", "model": "gemma4:12b", "mode": "fake", "fixture_hit": false}`

Sin fixture en `fake`: texto de plantilla por etapa que incluye `next_question`.

## Parámetros fijos de Ollama

`gemma4:12b` con `format` = esquema JSON, `options = {"temperature": 0, "seed": 42}`,
`think = false`; `glm-ocr` para OCR. `OLLAMA_URL=http://host.docker.internal:11434`.

## Fixtures

`fixtures/llm/<task>/<sha256>.json` con `{"request": …, "response": …, "recorded_at": …,
"model": …}`. La llave es el `sha256` del JSON canónico de la solicitud con textos normalizados
(R-11).

## Logs

Una línea JSON por llamada: `task`, `model`, `mode`, `latency_ms`, `prompt_tokens`,
`completion_tokens`, `fixture_hit`, texto redactado (CURP, RFC, teléfonos y nombres →
`[REDACTED_*]`) (R-22).
