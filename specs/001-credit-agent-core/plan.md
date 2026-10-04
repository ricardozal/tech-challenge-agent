# Implementation Plan: Núcleo del agente de crédito con garantía vehicular

**Branch**: `001-credit-agent-core` | **Date**: 2026-10-03 | **Spec**: [spec.md](./spec.md)

**Input**: Feature specification from `specs/001-credit-agent-core/spec.md`

## Summary

Un agente conversacional opera el tramo pre-originación de un crédito con garantía de auto
(elegibilidad → perfilamiento → simulación → documentos → gate o escalación) a través de una API de
mensajes y documentos por caso. El agente (LangGraph) interpreta mensajes con el LLM y actúa solo
llamando tools de la Case Actions API; ahí, funciones puras con la política versionada deciden
elegibilidad, perfil, opciones, validaciones y el gate, y cada acción pasa por permisos,
idempotencia, versión esperada, candado por caso y un registro de acciones solo de inserción.
Document Intelligence lee documentos sin estado; el LLM Gateway es el único cliente de Ollama y
por defecto responde con fixtures grabados, así que los 4 demos corren sin GPU. Las decisiones de
diseño están en [research.md](./research.md) (R-01…R-23).

## Technical Context

**Language/Version**: Python 3.12

**Primary Dependencies**: FastAPI, Pydantic v2, LangGraph + `langgraph-checkpoint-postgres`
(PostgresSaver), `psycopg` 3, `httpx`, `ollama` (solo en `llm_gateway`), PyYAML

**Storage**: PostgreSQL 16 (schemas `cases`, `audit`, `agent`; R-02, R-03); volumen Docker
`documents` para los bytes de documentos, montado solo en `actions_api`

**Testing**: pytest (marcador `req("FR-xxx")`), import-linter, e2e contra docker compose en
`LLM_MODE=fake`

**Target Platform**: Linux containers con docker compose en una laptop (macOS o Linux); Ollama en
el host solo para `ollama`/`record`/`eval`

**Project Type**: monorepo de servicios web (uv workspace): 4 servicios FastAPI + 1 paquete de
contratos

**Performance Goals**: cada demo en menos de 2 minutos en `LLM_MODE=fake` (SC-002); sin metas de
throughput

**Constraints**: sin GPU por defecto (FR-051); resultados idénticos entre corridas en `fake`
(SC-001); un mensaje a la vez por caso (FR-009); el registro de acciones no se puede modificar
(FR-008)

**Scale/Scope**: demo; decenas de casos, 5 guiones, 17 tools, 52 FR

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

| Principio | Cómo lo cumple el plan | Pre | Post |
|---|---|---|---|
| I. Demo, no producto | 5 de los 7 contenedores de referencia; `web` y `phoenix` llegan en las features 002 y 003. Cada pieza sirve a un demo o a una decisión de research. Las librerías nuevas (LangGraph, import-linter) no son infraestructura; las decisiones R-xx se copian a `DECISIONS.md` | ✅ | ✅ |
| II. El LLM propone, el código decide | Reglas en `actions_api/rules/` sin I/O, verificado por import-linter (R-20). El grafo transiciona solo por resultados de tools (R-19). Gate solo vía `evaluate_gate` (R-08). Confianza y matching deterministas (R-10, R-18) | ✅ | ✅ |
| III. Fronteras entre servicios | El agente habla solo HTTP con `actions_api` y `llm_gateway`; su rol de BD no puede leer `cases`/`audit` (R-03). `ollama` solo en `llm_gateway`. `doc_intel` sin BD ni volúmenes. Contratos en `packages/contracts`. Tests de arquitectura (R-20) | ✅ | ✅ |
| IV. Una sola capa de acciones | Decorador `@tool` con permisos actor × etapa × tool, idempotencia, versión esperada, candado y auditoría (R-05); el asesor usa las mismas tools. Trigger solo de inserción (R-06) | ✅ | ✅ |
| V. Reproducible sin GPU | `LLM_MODE=fake` por defecto y solo visible en `llm_gateway`; parámetros de Ollama fijos; modo `record` (R-11) | ✅ | ✅ |
| VI. Política versionada | `policy/policy.yaml` + `policy/archive/`, versión fijada por caso, reglas reciben la política, cada decisión y entrada de auditoría guarda `policy_version` (R-14) | ✅ | ✅ |
| VII. Trazabilidad | `@pytest.mark.req("FR-xxx")` + `scripts/traceability.py` genera `TRACEABILITY.md` y falla si falta un FR (R-21) | ✅ | ✅ |
| VIII. Calidad del LLM medida | `make eval` con umbral (R-13). El esquema `mensaje` cambia (`tema_sensible`, `nombre_completo`, `domicilio`, `codigo_postal`; R-12): la tarea correspondiente no se cierra sin casos nuevos en eval y una corrida de `make eval` que cumpla el umbral | ⚠️ | ✅ con condición |
| IX. Tests reales y mínimos | Unitarios de reglas y tools, arquitectura y 5 guiones e2e; sin metas de cobertura; el LLM se sustituye con `LLM_MODE=fake`, no con mocks | ✅ | ✅ |
| X. Datos sintéticos, texto como dato, idioma | Documentos de `eval/documentos` marcados "ESPÉCIMEN DE PRUEBA"; texto de usuario solo como campo delimitado (R-11, R-19); redacción de PII en logs (R-22); identificadores en inglés (R-01) con una excepción justificada abajo | ⚠️ | ✅ justificado |
| XI. Fuera de alcance | Sin auth, colas, Redis, Kubernetes, CI/CD, LiteLLM, Langfuse, Grafana ni WhatsApp. Phoenix y web diferidos | ✅ | ✅ |

**Resultado**: pasa. Dos condiciones abiertas: la corrida de `make eval` tras cambiar el esquema
de mensaje (VIII) y la excepción de idioma de Complexity Tracking (X).

**Cambios respecto al input de `/speckit-plan`**, todos por la constitución o por correctitud:

| Input | Plan | Motivo |
|---|---|---|
| tool `evaluar_gate`, nodos `elegibilidad`, `perfilamiento`… | `evaluate_gate`, `eligibility`, `profiling`… | Principio X: identificadores en inglés (R-01) |
| schema de Postgres `case` | `cases` | palabra reservada de SQL (R-02) |
| llave de fixture `(tarea, texto normalizado)` | incluye la pregunta del agente y el esquema | "sí" colisiona entre etapas (R-11) |
| respaldo `{"intencion":"otro","campos":{}}` | `campos` con todas las llaves en `null` | el esquema exige todos los campos (R-11) |
| advisory lock por caso en `actions_api` | además, candado por turno en el agente con otro espacio de llaves | el turno hace varias tools y escribe el checkpoint (R-04) |
| `make eval` | runner nuevo `scripts/eval_gate.py` con umbral | `eval/correr_eval.py` compara modelos y no tiene umbral (R-13) |
| un nodo por etapa | más `interpret` y `respond` | interpretación y redacción comunes a todas las etapas (R-19) |

## Project Structure

### Documentation (this feature)

```text
specs/001-credit-agent-core/
├── plan.md              # Este archivo
├── research.md          # Phase 0: decisiones R-01…R-23
├── data-model.md        # Phase 1: entidades, enums, transiciones, política, reporte
├── quickstart.md        # Phase 1: guía de validación
├── contracts/           # Phase 1: interfaces HTTP por servicio
│   ├── README.md
│   ├── actions-api.md
│   ├── agent-channel.md
│   ├── llm-gateway.md
│   └── doc-intel.md
├── checklists/
│   └── requirements.md
└── tasks.md             # Phase 2 (/speckit-tasks)
```

### Source Code (repository root)

```text
pyproject.toml                 # uv workspace; dev deps (pytest, import-linter); marcador req
.importlinter                  # contratos de arquitectura (R-20)
docker-compose.yml             # postgres, actions_api, agent, llm_gateway, doc_intel
Makefile                       # up/down/test/test-arch/test-e2e/demo-*/eval/traceability/metrics
DECISIONS.md                   # decisiones del proyecto (incluye R-xx de esta feature)
TRACEABILITY.md                # generado por scripts/traceability.py

db/
└── init.sql                   # schemas, roles, tablas, trigger solo-inserción (R-02, R-03, R-06)

policy/
├── policy.yaml                # versión vigente (R-14)
└── archive/                   # versiones anteriores

packages/contracts/src/contracts/
├── common.py                  # enums, errores, Money
├── case.py                    # CaseState, CaseView, Validation, Escalation, AuditEntry
├── actions.py                 # ToolContext, ToolResult, entradas/salidas por tool
├── channel.py                 # CreateCase, TurnResponse
├── llm.py                     # Extract/OCR/Reply + to_domain (R-01)
└── documents.py               # ExtractRequest/Response, ExtractedField

services/actions_api/
├── src/actions_api/
│   ├── main.py                # FastAPI: POST /tools/{name} + lectura + /metrics
│   ├── toolkit.py             # decorador @tool (R-05)
│   ├── permissions.py         # matriz actor × etapa × tool
│   ├── db.py                  # conexión actions_rw, candado (2, hashtext)
│   ├── tools/                 # un módulo por grupo: case, eligibility, profiling, documents, gate, advisor
│   ├── rules/                 # puras: eligibility, profile, options, payment, income, matching, validity, gate
│   ├── providers/             # bureau, vehicle_registry, key_quote (leen fixtures/providers)
│   ├── escalation.py          # plantillas de resumen y acción sugerida (R-09)
│   ├── metrics.py             # reporte desde audit_log
│   └── policy.py              # carga y valida policy/*.yaml
└── tests/                     # unit: rules/, tools/, permissions

services/agent/
├── src/agent/
│   ├── main.py                # POST /cases, /messages, /documents, GET /conversation
│   ├── graph.py               # StateGraph + PostgresSaver (search_path=agent)
│   ├── nodes/                 # interpret, eligibility, profiling, simulation, documents, gate, escalation, respond
│   ├── questions.py           # preguntas fijas por campo faltante (es)
│   ├── clients.py             # httpx: actions_api, llm_gateway
│   └── turn_lock.py           # candado (1, hashtext) + processed_messages (R-04)
└── tests/

services/llm_gateway/
├── src/llm_gateway/
│   ├── main.py                # /v1/extract, /v1/ocr, /v1/reply, /health
│   ├── modes.py               # fake / record / ollama (R-11)
│   ├── ollama_client.py
│   ├── schemas.py             # carga eval/esquemas.json
│   ├── prompts.py             # plantillas con texto de usuario delimitado
│   └── redaction.py           # PII en logs (R-22)
└── tests/

services/doc_intel/
├── src/doc_intel/
│   ├── main.py                # /v1/documents/extract
│   ├── confidence.py          # R-10
│   └── gateway_client.py
└── tests/

fixtures/
├── providers/                 # Buró, consulta vehicular, cotizador de llave (R-15)
├── documents/                 # documentos sintéticos de los guiones (parten de eval/documentos)
├── llm/                       # respuestas grabadas: extract/, ocr/, reply/
└── scenarios/                 # happy_path, eligibility_rejection, document_correction,
                               # document_escalation, no_spare_key (R-23)

scripts/
├── run_demo.py                # make demo-<escenario>
├── traceability.py            # R-21
└── eval_gate.py               # make eval (R-13)

tests/
├── architecture/              # import-linter, permisos de BD, compose (R-20)
└── e2e/                       # guiones + concurrencia contra el compose

eval/                          # existente: casos, esquemas (v3 con tema_sensible), documentos
```

**Structure Decision**: uv workspace con un paquete compartido (`packages/contracts`) y cuatro
servicios independientes en `services/`, cada uno con su `pyproject.toml`, `Dockerfile` y tests
unitarios. Los tests que cruzan servicios (`architecture`, `e2e`) viven en la raíz. Los fixtures
son compartidos y se montan solo de lectura en el servicio que los usa (`providers` en
`actions_api`; `llm` en `llm_gateway`).

### Base de datos (resumen; detalle en [data-model.md](./data-model.md))

| Schema | Tablas | Rol con acceso |
|---|---|---|
| `cases` | `cases`, `escalations`, `idempotency_keys` | `actions_rw` |
| `audit` | `audit_log` (trigger solo inserción) | `actions_rw` (INSERT, SELECT) |
| `agent` | tablas de PostgresSaver, `processed_messages` | `agent_rw` |

### Mapa historia → componentes

| Historia | Tools | Reglas | Nodo del agente | Demo |
|---|---|---|---|---|
| P1 Elegibilidad | `update_declared_data`, `evaluate_eligibility` | `eligibility` | `eligibility` | 1, 2, 4 |
| P2 Perfil y simulación | `record_bureau_consent`, `run_credit_check`, `simulate_options`, `select_option` | `profile`, `options`, `payment` | `profiling`, `simulation` | 1, 4 |
| P3 Documentos | `submit_document` | `income`, `matching`, `validity` | `documents` | 1, 3 |
| P4 Gate y escalación | `evaluate_gate`, `escalate`, tools de asesor | `gate` | `gate`, `escalation` | 1, 3 |
| P5 Observabilidad | — (`GET /metrics`) | — | — | todos |

## Complexity Tracking

| Violation | Why Needed | Simpler Alternative Rejected Because |
|---|---|---|
| Llaves en español en los esquemas del LLM (`eval/esquemas.json`: `intencion`, `campos`, `auto_a_nombre_propio`…) pese al Principio X (identificadores en inglés) | Son el contrato con el modelo y lo que mide `make eval`; el prompt y los campos están en el idioma del dominio | Traducirlas invalida las corridas de eval existentes y obliga a re-evaluar sin ganar nada; la traducción a nombres en inglés se hace en un único punto (`contracts.llm.to_domain`) |

## Próximos pasos

1. `/speckit-tasks` para generar `tasks.md`. Los ajustes a la spec que surgieron del diseño
   (FR-001, FR-004, FR-010, FR-017, FR-040, FR-047) ya están aplicados.
