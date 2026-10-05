# Implementation Plan: Modelos reales y observabilidad

**Branch**: `003-real-models-observability` | **Date**: 2026-10-04 | **Spec**: [spec.md](./spec.md)

**Input**: Feature specification from `specs/003-real-models-observability/spec.md`

## Summary

Tres piezas sobre lo que ya existe. **Modo real y grabación**: `LLM_MODE` ya resuelve
`fake|record|ollama` en `llm_gateway`; se completa con verificación de modelos instalados (503 en
`/health`), grabación a un directorio intermedio con latencia, tokens y origen, y `make record`,
que corre los 5 guiones de los 4 demos y promueve a `fixtures/llm/` solo lo de los demos que
llegaron a su resultado. `make fixtures-status` comprueba que `fake` usa solo respuestas
auténticas. Los mensajes se extraen con **esquemas por etapa** (`eval/esquemas.json` v4) para bajar
los tokens de salida y la latencia por turno. **Trazas**: contenedor `phoenix`
(`arizephoenix/phoenix:version-20.19.0`, puerto 6006); `agent`, `llm_gateway` y `doc_intel`
registran con `phoenix.otel.register`; el agente abre un span raíz `turn` por turno, LangGraph se
instrumenta con OpenInference (nodos sin entrada/salida) y cada tool es un span `TOOL`; el gateway
crea spans `LLM` a mano con modelo, entrada, salida, tokens y marca de reproducción; el contexto
viaja por `httpx`/FastAPI instrumentados, con `actions_api` solo propagando. **Calidad medida**:
`make eval` sigue en `scripts/eval_gate.py` (R-13), ahora con esquema por etapa, desglose por
tipo, salida 2 fuera de modo real y prueba `@pytest.mark.ollama`. Decisiones en
[research.md](./research.md) (O-01…O-15).

## Technical Context

**Language/Version**: Python 3.12 (servicios y scripts); sin cambios en la web

**Primary Dependencies**: nuevas — `arize-phoenix-otel` (agent, llm_gateway, doc_intel),
`openinference-instrumentation-langchain` (agent), `opentelemetry-instrumentation-httpx` (agent,
llm_gateway, doc_intel, actions_api), `opentelemetry-instrumentation-fastapi` (llm_gateway,
doc_intel, actions_api), `openinference-semantic-conventions` (atributos en spans manuales),
`arize-phoenix-client` (grupo dev, pruebas). Imagen `arizephoenix/phoenix:version-20.19.0`.
Existentes: FastAPI, LangGraph, `ollama`, `jsonschema`, httpx

**Storage**: archivos versionados (`fixtures/llm/`, `eval/esquemas.json`, `eval/resultados/`);
volumen `phoenix_data` para las trazas; contador de uso de fixtures en memoria del gateway. Sin
cambios en Postgres

**Testing**: pytest. Por defecto (fake): unitarias de esquema por etapa, llave y formato de
fixture, promoción de `make record`, spans del gateway con `InMemorySpanExporter`, regla de
puntaje y umbral; e2e contra compose que lee trazas de Phoenix con `arize-phoenix-client`,
`fixtures-status` y consola apagada; arquitectura de compose. Con `@pytest.mark.ollama`
(excluido por defecto): demos en modo real, texto libre y `make eval` completo

**Target Platform**: docker compose en laptop (Linux/macOS); Ollama en el host con
`gemma4:12b` y `glm-ocr` para modo real

**Project Type**: servicios web existentes + scripts de operación del demo

**Performance Goals**: con respuestas grabadas, SC-012 de la 002 se mantiene (< 3 s por respuesta)
con trazas activas; en modo real, mediana de extracción de mensaje por debajo de la línea base de
12.8 s (gate 2026-10-04; objetivo ≤ 9 s) sin bajar del umbral de calidad — objetivo informativo:
se mide y se registra en `DECISIONS.md` (T053), pero no es condición de aprobado porque la spec
no lo exige; exportar trazas no
agrega espera perceptible al turno (exportación por lotes en segundo plano)

**Constraints**: `LLM_MODE` solo en `llm_gateway`; ningún servicio depende de `phoenix` para
arrancar ni para completar un turno; misma redacción de PII en trazas que en logs; sin Langfuse,
Grafana, Prometheus ni alertas; esquema de extracción cambiado ⇒ `make eval` en verde

**Scale/Scope**: 1 persona haciendo la demo; 5 guiones, ~80 llamadas al modelo por corrida
completa; 37 casos de evaluación; ~15 spans por turno

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

| Principio | Cumplimiento | Estado |
|---|---|---|
| I · Demo, no producto | Sirve a los 4 demos (modo real y reproducción auténtica) y a dos preguntas de evaluación (qué hizo el modelo en cada turno; cómo se mide la extracción). `phoenix` es el 7.º contenedor de la topología de referencia; contenedor y dependencias nuevas se registran en `DECISIONS.md` antes de agregarlos (O-01, O-02) | ✅ |
| II · El LLM propone, el código decide | Nada de lo nuevo decide: las trazas observan, la grabación guarda salidas ya validadas, el esquema por etapa solo reduce lo que el modelo puede proponer. Reglas y gate sin cambios | ✅ |
| III · Fronteras | Solo el gateway llama a Ollama (también para verificar modelos). El agente sigue hablando solo con `actions_api` y el gateway; exportar a Phoenix no es acceso a caso ni a Ollama. `redact` pasa a `packages/contracts` (O-09) para no importar entre servicios; cada servicio tiene su `telemetry.py`. `test_compose.py` e import-linter se actualizan y siguen fallando ante violaciones | ✅ |
| IV · Una sola capa de acciones | Sin tools, permisos ni endpoints de escritura nuevos en `actions_api`; solo instrumentación de propagación | ✅ |
| V · Reproducible sin GPU | `fake` sigue por defecto; los 4 demos corren sin GPU y, tras `make record`, con respuestas auténticas. `record` y `ollama` usan los parámetros de la constitución. El modo sigue resolviéndose solo en el gateway; las trazas muestran el modo porque lo escribe el gateway | ✅ |
| VI · Política versionada | No toca `policy.yaml` ni umbrales de negocio. El 85%/100% de la medición es de la constitución (Principio VIII), no de negocio | ✅ |
| VII · Trazabilidad | FR-076…FR-098 con prueba marcada (`@pytest.mark.req`); las de modo real llevan además `@pytest.mark.ollama`; `TRACEABILITY.md` regenerado | ✅ |
| VIII · Calidad del LLM | El esquema de mensaje cambia (v4, por etapa) ⇒ `make eval` debe pasar antes de cerrar y la corrida se registra en `DECISIONS.md`. El gate se extiende, no se reemplaza | ✅ (gate obligatorio) |
| IX · Tests reales y mínimos | Pruebas contra el gateway real en `fake`, Phoenix real en compose y Ollama real con marcador; `InMemorySpanExporter` es un exportador de OTel, no un mock de la unidad bajo prueba. Sin tests de cobertura | ✅ |
| X · Sintéticos, texto como dato, idioma | Trazas con la misma redacción que logs; nodos de LangGraph sin estado. Prompts siguen delimitando texto del cliente y del documento. Salidas de comandos en español; código en inglés | ✅ |
| XI · Fuera de alcance | Sin Langfuse, Grafana, Prometheus, alertas, CI/CD ni colas. Phoenix está en la topología de referencia | ✅ |

**Gates de cierre** (constitución, "Flujo de desarrollo"): unitarias y e2e en `LLM_MODE=fake`
(incluidas trazas, consola apagada y `fixtures-status` en 0 tras grabar); `make test-arch` con 7
contenedores; `make traceability` sin FR pendientes; `make eval` en verde con esquema v4 y
registrado en `DECISIONS.md`; `make test-ollama` en verde en la máquina con GPU.

**Re-check post-diseño**: sin violaciones. Dos desviaciones menores respecto de la entrada del
plan, sin conflicto con la constitución: (1) `actions_api` también se instrumenta, solo para
propagar contexto (O-06), porque los turnos de documento pasan por él; (2) `make eval` extiende
`scripts/eval_gate.py` en lugar de `eval/correr_eval.py` (O-14), porque el gate ya vive ahí desde
la 001 y el otro script es el comparador de modelos, fuera de alcance. Además, en `agent` el
instrumentador de LangChain se activa explícitamente con `TraceConfig` en lugar de
`auto_instrument=True` (O-04) para ocultar el estado de los nodos.

## Project Structure

### Documentation (this feature)

```text
specs/003-real-models-observability/
├── plan.md
├── research.md                 # O-01…O-15
├── data-model.md
├── quickstart.md
├── contracts/
│   ├── tracing.md              # árbol de spans y atributos por servicio
│   ├── llm-gateway-changes.md  # esquemas por etapa, fixture v2, /health, /v1/fixtures/usage
│   └── commands.md             # make record, fixtures-status, eval, test-ollama; compose
├── checklists/requirements.md
└── tasks.md                    # /speckit-tasks
```

### Source Code (repository root)

```text
docker-compose.yml                    # + phoenix (6006, volumen phoenix_data); PHOENIX_COLLECTOR_ENDPOINT
                                      #   en agent/llm_gateway/doc_intel; FIXTURES_RECORD_DIR en llm_gateway
Makefile                              # + record, fixtures-status, test-ollama
pyproject.toml                        # marcador ollama; addopts -m "not ollama"; dev: arize-phoenix-client
.gitignore                            # + fixtures/llm/_recording/
DECISIONS.md                          # + sección Feature 003 (O-01…O-15) y corrida de make eval v4

eval/
└── esquemas.json                     # v4: + "etapas"

packages/contracts/src/contracts/
├── llm.py                            # PROMPT_VERSION; fixture_key con schema_version y prompt_version
└── redaction.py                      # redact() movido desde llm_gateway (O-09)

services/llm_gateway/
├── pyproject.toml                    # + arize-phoenix-otel, otel httpx/fastapi, openinference-semconv
└── src/llm_gateway/
    ├── telemetry.py                  # setup(app): register + FastAPI (sin /health) + httpx
    ├── tracing.py                    # spans CHAIN de tarea y LLM por intento (atributos OpenInference)
    ├── schemas.py                    # esquema reducido por etapa; validación de "etapas"
    ├── modes.py                      # record → _recording/; fixture v2 (origin, latencia, tokens); uso en fake
    ├── ollama_client.py              # list_models() para verificar gemma4:12b y glm-ocr
    ├── config.py                     # FIXTURES_RECORD_DIR
    ├── redaction.py                  # get_logger/log_call; redact desde contracts
    └── main.py                       # /health con 503 y modelos faltantes; GET/DELETE /v1/fixtures/usage

services/agent/
├── pyproject.toml                    # + arize-phoenix-otel, openinference-instrumentation-langchain, otel httpx
└── src/agent/
    ├── telemetry.py                  # register(auto_instrument=False) + LangChainInstrumentor(TraceConfig) + httpx
    ├── main.py                       # span raíz turn en run_turn (session.id = caso)
    └── graph.py                      # span TOOL en Deps.call_tool

services/doc_intel/
├── pyproject.toml                    # + arize-phoenix-otel, otel httpx/fastapi
└── src/doc_intel/
    ├── telemetry.py
    └── main.py                       # span read_document

services/actions_api/
├── pyproject.toml                    # + otel httpx/fastapi (sin SDK ni exportador)
└── src/actions_api/main.py           # instrumentación de propagación (O-06)

scripts/
├── record_fixtures.py                # make record: por guion vacía _recording, corre, promueve o descarta
├── fixtures_status.py                # make fixtures-status: uso por origen, huérfanos, PRUNE
├── run_demo.py                       # expone la ejecución de un guion como función reutilizable
├── seed_fixtures.py                  # origin: seeded; llave nueva
└── eval_gate.py                      # esquema por etapa, by_type, failed_cases, salida 2 fuera de modo real

tests/
├── architecture/test_compose.py      # 7 contenedores; quién conoce PHOENIX_COLLECTOR_ENDPOINT; sin depends_on phoenix
├── e2e/test_tracing.py               # una traza por turno, tools y LLM con atributos; consola apagada
├── e2e/test_fixtures_status.py       # 4 demos en fake usan 0 sembradas y 0 faltantes (SC-019)
├── eval/test_eval_gate.py            # regla de puntaje y umbral (por defecto) + gate completo (@ollama)
└── ollama/test_real_mode.py          # 4 demos y texto libre con modelos reales (@ollama)

services/llm_gateway/tests/           # esquema por etapa, fixture v2, record a _recording, /health 503,
                                      #   usage, spans con InMemorySpanExporter
fixtures/llm/                         # regenerado por make record (origin: recorded)
```

**Structure Decision**: se mantienen los cuatro servicios Python y `packages/contracts` de las
features 001 y 002; se agrega el contenedor `phoenix` sin código propio. La instrumentación vive en
un `telemetry.py` por servicio y los spans de dominio junto al código que conoce el dato (turno y
tools en el agente, modelo en el gateway, lectura en `doc_intel`). Los comandos nuevos son scripts
en `scripts/` con objetivo en el `Makefile`, como los existentes.

## Complexity Tracking

Sin violaciones de la constitución que justificar.
