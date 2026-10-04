# Decisiones

Registro de decisiones del proyecto (Principio I: nada fuera de la topología de referencia sin una
decisión aquí). Cada entrada enlaza al razonamiento completo.

## Feature 001 · Núcleo del agente

Detalle en [specs/001-credit-agent-core/research.md](specs/001-credit-agent-core/research.md).

| Id | Decisión | Motivo |
|---|---|---|
| R-01 | Identificadores en inglés; dominio y mensajes en español. Excepción: llaves de `eval/esquemas.json` en español, traducidas en `contracts.llm.to_domain` | Principio X; traducir los esquemas invalidaría la evaluación |
| R-02 | Schema de Postgres `cases`, no `case` | `CASE` es palabra reservada de SQL |
| R-03 | Roles `actions_rw` y `agent_rw`; el agente no tiene acceso a `cases` ni `audit` | La frontera del Principio III se hace cumplir con permisos |
| R-04 | Candado por turno en el agente `(1, hashtext)` y por tool en `actions_api` `(2, hashtext)` | Un turno hace varias tools y escribe el checkpoint; espacios de llave distintos evitan el autobloqueo |
| R-05 | Decorador `@tool`: candado → idempotencia → versión → permisos → handler → auditoría, en una transacción; los rechazos también se auditan | FR-003 a FR-008 |
| R-06 | `audit.audit_log` solo de inserción: triggers + permisos | FR-008 |
| R-07 | Estado del caso como agregado JSONB validado por `CaseState` | Se lee y escribe completo bajo un candado; menos tablas para un demo |
| R-08 | Solo `evaluate_gate` marca OK; se ejecuta solo al cambiar validaciones (auditado como `system`) y el agente puede pedirlo | Clarificación del gate |
| R-09 | Escalaciones automáticas en `actions_api`; resumen y acción sugerida por plantilla | `actions_api` no llama al LLM; reproducible |
| R-10 | Confianza por campo determinista (formato + respaldo en el OCR) | Los modelos no dan confianza calibrada |
| R-11 | Llave de fixture = sha256 de `(tarea, esquema, entradas)` incluida la pregunta del agente; respaldo con todos los campos en `null` | "sí" significa cosas distintas según la pregunta |
| R-12 | Esquema de mensaje v3: `tema_sensible`, `nombre_completo`, `domicilio`, `codigo_postal` | FR-040; el agente pregunta todo |
| R-13 | `make eval` con umbral en `scripts/eval_gate.py` | El runner existente compara modelos y no tiene umbral |
| R-14 | Política vigente + archivo de versiones; versión fijada por caso | Principio VI |
| R-15 | Umbrales en la política; costo de llave, valor del auto y score de Buró en proveedores simulados | Datos externos no son umbrales |
| R-16 | Caso vacío; el agente pregunta todo; decisiones del cliente con `on_behalf_of = client` | Sin datos pre-guardados ni autenticación |
| R-17 | Cuota con amortización francesa, `Decimal` y `ROUND_HALF_UP` | Resultados idénticos al centavo |
| R-18 | Coincidencia de nombre y domicilio con normalización + `difflib` | Determinista, sin dependencias |
| R-19 | Grafo: `interpret` → router → nodo de etapa → `respond`; transiciones solo por resultados de tools | Principio II |
| R-20 | Fronteras verificadas con import-linter, permisos de BD y el compose | Principio III |
| R-21 | `@pytest.mark.req("FR-xxx")` + `scripts/traceability.py` | Principio VII |
| R-22 | Logs JSON del gateway con PII redactada | Principio X |
| R-23 | Guiones YAML en `fixtures/scenarios/` para demos y e2e | FR-052 |

### Ajustes durante la implementación

| Fecha | Decisión | Motivo |
|---|---|---|
| 2026-10-04 | `cases.idempotency_keys` usa `scope` (`case_id` o `global`) en lugar de `case_id` en la llave primaria | `create_case` no tiene `case_id` y también es idempotente |
