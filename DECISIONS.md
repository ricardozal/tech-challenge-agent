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
| 2026-10-04 | `actions_api` acepta `AS_OF_DATE` como "hoy" para la vigencia de documentos; el compose lo fija en `2026-10-04` | Los documentos sintéticos tienen fechas fijas; sin fecha fija los demos dejarían de pasar con el tiempo (SC-001) |
| 2026-10-04 | Domicilio: además de la similitud por tokens ordenados (R-18), se acepta la contención de tokens, ignorando palabras de relleno (`COLONIA`, `MÉX.`) | `AV. MORELOS 245, COL. CENTRO` contra `AV MORELOS 245, CENTRO` quedaba debajo de 0.90 sin ser otro domicilio |
| 2026-10-04 | Los prompts de extracción del gateway siguen el formato medido en la comparación de modelos (`eval/prompts_para_comparador.md`): rol, formato, lista de campos con tipos en el orden del esquema, reglas numeradas, pregunta y respuesta entre comillas; `num_predict` 512. `eval_gate.py` califica con la misma regla que esa comparación | El primer prompt del gateway (sin lista de campos) dio 68.4% en `make eval`; con el formato medido, 89.5% |
| 2026-10-04 | T097: los fixtures del LLM se quedan sembrados desde los guiones (`make seed-fixtures`); no se regraban con el modelo real | Con `LLM_MODE=ollama` en una Mac de 16 GB, el demo 2 pasó, pero el demo 1 excedió el límite de 330 s del guion en el tercer documento (Docker, `gemma4:12b` y `glm-ocr` cargados a la vez fuerzan swap; Ollama se trabó >300 s en una extracción y el reintento sí pasó). Regrabar en esta máquina daría fixtures incompletos, y los errores conocidos del modelo (p. ej. M16) romperían los guiones. La calidad del modelo la mide `make eval`; los demos y e2e prueban el flujo con respuestas fijas |
| 2026-10-04 | OCR con su propio límite (`num_predict` 1024) y el gateway se queda con la primera copia del texto | `glm-ocr` repite la página hasta el límite; con el límite de extracción (512) un documento largo se truncaría. La limpieza es la misma que `eval/` aplica a sus OCR grabados |

## Feature 002 · Web de demo

Detalle en [specs/002-demo-web/research.md](specs/002-demo-web/research.md). `web` (nginx con el
build de Vite) es el 6.º contenedor de la topología de referencia; se registra aquí antes de
agregarlo (Principio I).

| Id | Decisión | Motivo |
|---|---|---|
| W-01 | `web/` con React 19, Vite, TypeScript strict y Tailwind CSS 4; sin librería de componentes, router, estado global ni cliente HTTP | Dos vistas no justifican más dependencias |
| W-02 | Ruteo por `location.pathname` (`/chat`, `/asesor`); nginx responde `index.html` para cualquier ruta | Dos rutas sin transiciones |
| W-03 | Contenedor `web`: build con `node:24-alpine`, servido por `nginx:1.27-alpine` en 8080; el navegador llama directo a `agent` y `actions_api` | Estático y sin estado; sin proxy ni timeouts de proxy con el modelo real |
| W-04 | CORS en `agent` y `actions_api` solo para `WEB_ORIGINS` (por defecto `http://localhost:8080`) | El navegador llama desde otro origen; nada de `*` |
| W-05 | `scripts/export_web_scenarios.py` genera `web/public/scenarios.json` (versionado) desde `fixtures/scenarios/`; "documento fallido" une las ramas A y B del demo 3 | Las sugerencias son exactamente los textos con fixture; sin Python en el build de Node |
| W-06 | Sugerencias por `last_question` del agente; documentos por la pregunta de cada tipo | La llave del fixture incluye la pregunta (R-11); robusto ante texto libre |
| W-07 | Etapa, estado y resultado desde `GET /cases/{id}` de `actions_api`; sondeo cada 5 s solo mientras el caso está escalado | Una fuente de verdad, sin websockets |
| W-08 | Respuesta síncrona con "escribiendo…"; la `Idempotency-Key` se crea por intento y se reutiliza al reintentar | El canal de 001 ya es idempotente |
| W-09 | La sesión del chat vive en la URL (`?scenario=&case=`) | Recargable sin `localStorage` ni estado global |
| W-10 | La consola solo usa `actions_api`: lecturas existentes y `POST /tools/{name}` con `X-Actor: advisor` | Principio IV: el asesor escribe por la misma capa que el agente |
| W-11 | Lector `GET /policies/{policy_version}` en `actions_api` para el umbral de confianza | Principio VI: la web no tiene umbrales |
| W-12 | `web/src/labels.ts` traduce los códigos de los enums a español | Texto de presentación, sin tocar contratos |
| W-13 | Playwright (`web/e2e/demo.spec.ts`) contra el compose: los 4 escenarios del chat, reintento sin duplicar, tiempos (SC-012) y la resolución en `/asesor`; tags `@FR-xxx` leídos por `scripts/traceability.py` | FR-074/FR-075 piden los 4 escenarios desde el chat |
| W-14 | Fronteras de `web` verificadas: compose (sin base, sin LLM, sin volúmenes), fuentes de `web/src` y CORS | Principios III y IV con tests, como R-20 |

Desviaciones respecto a la entrada del plan: el header es `X-Actor: advisor` (valor del enum
`Actor`; `asesor` daría `422`), la consola vive en `/asesor` (no `/adviser`), Playwright cubre los
4 escenarios (no solo el happy path) y se agrega el lector `GET /policies/{version}`.

**Contrato implícito agente ↔ web**: las sugerencias del chat dependen de
`Conversation.state.last_question` y de los textos de `agent.questions.DOCUMENT_QUESTIONS`. Se
exportan a `web/public/scenarios.json` y `tests/web/test_scenarios_export.py` falla si se
desincronizan. Los contratos de `packages/contracts` de 001 no cambian.

### Ajustes durante la implementación

| Fecha | Decisión | Motivo |
|---|---|---|
| 2026-10-04 | El motivo de un rechazo en el chat sale de la última decisión con `result = rejected`, no de `kind = rejection` | El rechazo por auto se registra como `kind = eligibility`; `kind = rejection` solo lo usan perfil sin oferta y el asesor |
| 2026-10-04 | `.dockerignore` vuelve a incluir `fixtures/documents/*.png` (y excluye `web/node_modules`, `web/dist`) | La imagen `web` sirve los documentos de ejemplo; `fixtures/` estaba excluido para los servicios Python |
| 2026-10-04 | El healthcheck de `web` usa `http://127.0.0.1:8080/` | En la imagen alpine `localhost` resuelve a `::1` y nginx solo escucha IPv4 |
| 2026-10-04 | El chat expone `data-busy` (envío, lectura del caso o restauración desde la URL) y Playwright espera a que sea `false` | Sin esa señal, un test veía la página "lista" a mitad de la restauración y fallaba de forma intermitente |
| 2026-10-04 | El test del asesor genera la escalación enviando los documentos en el orden del guion del demo 3B (identificación, domicilio, factura y tres veces el recibo que no cuadra) | Siguiendo el orden en que pide el agente, el caso se escala sin domicilio ni factura y la verificación manual no puede llevarlo a OK |
| 2026-10-04 | Además de los 4 escenarios, Playwright cubre reintento sin duplicar (misma `Idempotency-Key`) y mide el p95 de respuesta por escenario (SC-012) | Hallazgos G1 y G3 de `/speckit-analyze` |
| 2026-10-04 | Los errores de API que ve el usuario se arman siempre en español (`web/src/api/errors.ts`): el mensaje del agente o un texto por código HTTP; nunca el `detail` de `actions_api` ni el texto de estado HTTP | Convergencia T054 (Principio X): un caso inexistente mostraba "case not found" |
| 2026-10-04 | La consola renueva la llave de idempotencia después de un rechazo; solo un reenvío tras error de red la reutiliza | Convergencia T055: `actions_api` guarda también los rechazos por llave, y reenviar tras un `version_conflict` daba `idempotency_mismatch` |
| 2026-10-04 | El test de conflicto de versión provoca el cambio con un mensaje del cliente mientras el caso está escalado (cambia la versión, no el estado), y verifica que reintentar el mismo formulario se acepta | Si otra pestaña devolvía el caso al agente, rechazar ya no estaba permitido y el reintento no se podía probar |

## Calidad del LLM (`make eval`, Principio VIII)

| Fecha | Modelo | Esquema | Casos | Campos correctos | JSON válido | Resultado |
|---|---|---|---|---|---|---|
| 2026-10-04 | `gemma4:12b` (temperature 0, seed 42, think false) | v3 | 37 (25 originales + 12 nuevos de v3) | 102/114 = **89.5%** (originales 88.2%, nuevos 95.2%) | 100% | Pasa (mínimo 85% y 100%) · `eval/resultados/gate-2026-10-04_104313.json` |
