# Contrato: cambios en `llm_gateway`

Cambios sobre el contrato de la feature 001 (`specs/001-credit-agent-core/contracts/`). Solo el
gateway conoce `LLM_MODE` (Principio V); nada de esto se expone a otros servicios salvo `/health`
y `/v1/fixtures/usage`, que usan los scripts y las pruebas. Decisiones O-10…O-15.

## `eval/esquemas.json` v4 · esquemas por etapa

Se agrega una llave de primer nivel `etapas` y `version` pasa a 4; `mensaje`, `documento` y
`puntaje` no cambian.

```json
{
  "version": 4,
  "etapas": {
    "eligibility": ["nombre_completo", "auto_a_nombre_propio", "adeudos_vehiculo", "segunda_llave",
                    "auto_marca", "auto_modelo", "auto_anio"],
    "profiling":   ["domicilio", "codigo_postal", "ingreso_monto", "ingreso_periodicidad",
                    "situacion_laboral", "consentimiento_buro"],
    "simulation":  ["opcion_elegida", "monto_solicitado", "plazo_meses"],
    "documents":   ["nombre_completo", "domicilio", "codigo_postal", "ingreso_monto",
                    "ingreso_periodicidad", "situacion_laboral"]
  },
  "mensaje": { "...": "sin cambios" },
  "documento": { "...": "sin cambios" },
  "puntaje": { "...": "sin cambios" }
}
```

Reglas:

- `POST /v1/extract` con `schema_name="mensaje"` y `stage` presente usa el esquema reducido:
  `campos.properties` y `campos.required` filtrados a la lista de la etapa, en el orden del
  esquema completo; `intencion` igual que en el completo. Con `stage=null`, esquema completo.
- `schema_name="documento"` ignora `stage`.
- Validación al cargar: cada campo listado en `etapas` existe en `mensaje.schema.campos` y la lista
  sigue el orden del esquema completo; cada
  llave de `etapas` es un valor de `Stage`. Si no, el gateway no arranca.
- La respuesta (`ExtractResponse.data`) trae solo los campos del esquema reducido. `to_domain` y
  la regla de puntaje tratan un campo ausente como `null` (sin cambios de código en el agente).

## Llave y formato de respuesta grabada

`contracts.llm.fixture_key(task, schema_name, inputs)` incorpora `schema_version` y
`PROMPT_VERSION`:

```text
sha256(canonical_json({"task", "schema_name", "schema_version", "prompt_version", "inputs"}))
```

`PROMPT_VERSION` es un entero en `contracts.llm`; se sube al cambiar instrucciones de
`llm_gateway/prompts.py`. `scripts/seed_fixtures.py` usa la misma función.

Archivo `fixtures/llm/<task>/<key>.json`:

```json
{
  "request": { "...": "entrada de la tarea" },
  "response": { "...": "salida validada" },
  "origin": "recorded",
  "model": "gemma4:12b",
  "recorded_at": "2026-10-05T10:00:00+00:00",
  "schema_version": 4,
  "prompt_version": 2,
  "latency_ms": 6123.4,
  "prompt_tokens": 812,
  "completion_tokens": 64
}
```

- `origin`: `recorded` (escrito en `record`) o `seeded` (escrito por `seed_fixtures.py`, sin
  `latency_ms` ni tokens). Ausente = `seeded` (compatibilidad con archivos existentes).
- Solo se graba una salida que pasó la validación del esquema; un intento inválido no se graba.
- `latency_ms`, `prompt_tokens` y `completion_tokens` son los del intento válido (el que se
  reproduce); el intento inválido previo, si lo hubo, solo queda en la traza.

## `LLM_MODE=record` · directorio de grabación

- Escribe en `${FIXTURES_DIR}/_recording/<task>/<key>.json` (`FIXTURES_RECORD_DIR`, por defecto
  `fixtures/llm/_recording`), nunca en `fixtures/llm/<task>/`. `_recording/` está en `.gitignore`.
- `fake` nunca lee `_recording/`. La promoción a `fixtures/llm/` la hace `make record` (ver
  [commands.md](./commands.md)).

## `GET /health`

```json
{"status": "ok", "mode": "ollama", "schema_version": 4, "prompt_version": 2,
 "model": "gemma4:12b", "ocr_model": "glm-ocr"}
```

En `ollama` o `record`, si a Ollama le falta un modelo o no responde:

```http
HTTP/1.1 503
{"status": "error", "mode": "record", "missing_models": ["glm-ocr"],
 "message": "Falta el modelo glm-ocr en Ollama. Instálalo con: ollama pull glm-ocr"}
```

En `fake` nunca consulta Ollama.

## `GET /v1/fixtures/usage` · `DELETE /v1/fixtures/usage`

Uso de respuestas grabadas desde el arranque o el último `DELETE` (en memoria; solo cuenta en
`fake`).

```json
{
  "mode": "fake",
  "counts": {"recorded": 41, "seeded": 0, "missing": 0},
  "by_task": {
    "extract": {"recorded": ["0037…", "…"], "seeded": [], "missing": []},
    "ocr":     {"recorded": ["…"], "seeded": [], "missing": []},
    "reply":   {"recorded": ["…"], "seeded": [], "missing": []}
  }
}
```

`DELETE` responde 204 y reinicia los conteos. En `ollama` y `record`, `counts` es siempre cero.

## Errores (sin cambios de códigos)

`fixture_missing` (404, OCR en `fake`), `invalid_model_output` (502), `upstream_failure` (502).
Cada uno marca con `ERROR` el span de la tarea ([tracing.md](./tracing.md)).

## Variables de entorno nuevas

| Variable | Servicio | Valor en compose |
|---|---|---|
| `PHOENIX_COLLECTOR_ENDPOINT` | `agent`, `llm_gateway`, `doc_intel` | `http://phoenix:6006` |
| `FIXTURES_RECORD_DIR` | `llm_gateway` | `/app/fixtures/llm/_recording` |
