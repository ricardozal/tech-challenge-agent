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

## Feature 003 · Modelos reales y observabilidad

Detalle en [specs/003-real-models-observability/research.md](specs/003-real-models-observability/research.md).
`phoenix` (consola de trazas) es el 7.º contenedor de la topología de referencia; se registra aquí
antes de agregarlo (Principio I), junto con las dependencias de instrumentación.

| Id | Decisión | Motivo |
|---|---|---|
| O-01 | Contenedor `phoenix` (`arizephoenix/phoenix:version-20.19.0`, puerto 6006, volumen `phoenix_data`); ningún servicio depende de él para arrancar | Consola local de trazas (FR-091); el turno no depende de la consola (FR-092) |
| O-02 | `telemetry.py` por servicio con `phoenix.otel.register(project_name="tech-challenge-agent", batch=True)`, `httpx` y FastAPI instrumentados (sin `/health`); sin `PHOENIX_COLLECTOR_ENDPOINT` no exporta | Exportación en segundo plano; ningún servicio importa código de otro |
| O-03 | Un span raíz `turn` por ejecución del grafo, con `session.id` = caso; el agente no instrumenta su FastAPI de entrada | Una traza por turno (FR-085) y búsqueda por caso (FR-086) |
| O-04 | LangGraph instrumentado con OpenInference y `TraceConfig(hide_inputs, hide_outputs)` (instrumentación explícita en lugar de `auto_instrument`) | Los nodos muestran etapa, orden y duración sin exponer el estado del turno (FR-087, FR-093) |
| O-05 | Span `TOOL` por llamada en `Deps.call_tool`, `ERROR` si se rechaza | El agente conoce tool, entrada y desenlace (FR-088, FR-090) |
| O-06 | `actions_api` solo propaga contexto (instrumentación sin SDK ni exportador) | Los turnos de documento pasan por él; sin duplicar spans ni trazar las lecturas de la web |
| O-07 | Spans `CHAIN` por tarea y `LLM` por intento en el gateway, con modelo, entrada, salida, tokens y marca de reproducción | FR-089, FR-090 |
| O-08 | Span `read_document` en `doc_intel` con tipo detectado y confianza | La lectura de documentos se ve en orden en la traza |
| O-09 | `redact()` pasa a `contracts.redaction`; logs y spans manuales usan la misma política | FR-093 sin importar código entre servicios |
| O-10 | Fixture v2 (`origin`, latencia, tokens, versiones); la llave incluye `schema_version` y `PROMPT_VERSION` | Saber qué es auténtico (FR-083) y que un cambio de prompt o esquema no reproduzca respuestas viejas |
| O-11 | `LLM_MODE=record` graba en `fixtures/llm/_recording/`; `make record` promueve por guion solo si el demo llegó a su resultado | Una grabación fallida no reemplaza las vigentes (FR-081) |
| O-12 | `GET/DELETE /v1/fixtures/usage` en el gateway y `make fixtures-status` | Comprobar que los demos usan solo respuestas auténticas (FR-083, SC-019) |
| O-13 | `eval/esquemas.json` v4: cada etapa pide solo sus campos de mensaje; sin etapa, esquema completo | Menos tokens de salida y menos latencia por turno. Consecuencia aceptada: un dato que el cliente adelanta fuera de su etapa no se extrae en ese turno; el agente lo pregunta en su etapa |
| O-14 | `make eval` sigue en `scripts/eval_gate.py` (R-13), extendido con desglose por tipo y salida 2 fuera de modo real; `eval/correr_eval.py` no cambia | El gate ya existía; el otro script es el comparador de modelos (fuera de alcance) |
| O-15 | En `ollama`/`record` el gateway verifica `gemma4:12b` y `glm-ocr` y responde 503 en `/health` si falta alguno | Fallar visible, nunca caer a respuestas grabadas (FR-084) |

### Ajustes durante la implementación

| Fecha | Ajuste | Motivo |
|---|---|---|
| 2026-10-04 | Las listas de `etapas` en `eval/esquemas.json` siguen el orden del esquema completo (el gateway lo valida al cargar) | El esquema reducido conserva ese orden; una lista en otro orden confundía al leerla |
| 2026-10-04 | FastAPI 0.142 traza solo cuando hay un `TracerProvider` global: se desactiva su telemetría nativa (`FastAPI(telemetry={"tracing": False, ...})`) en los cuatro servicios | En el agente creaba una raíz HTTP por encima de `turn`; en los demás duplicaba los spans de la instrumentación de OpenTelemetry |
| 2026-10-04 | Al ejecutar cada nodo, el agente activa como contexto el span de LangGraph de ese nodo (`openinference.instrumentation.langchain.get_current_span`) | El instrumentador de LangChain no lo hace por diseño; sin esto las tools y las llamadas HTTP colgaban de `turn` y no de su etapa |
| 2026-10-04 | Exportación por OTLP/HTTP (`protocol="http/protobuf"`) al puerto 6006, sin `http receive/send` de ASGI | `register` elegía gRPC en 4317; el plan fija 6006. Los spans ASGI internos solo agregaban ruido |
| 2026-10-04 | La salida del span de OCR es `{"chars": n}`, como en los logs (R-22); el texto leído aparece redactado como entrada de la extracción | El OCR no conoce los nombres del documento; la extracción sí y los redacta |
| 2026-10-04 | La tool del turno de documento es `submit_document` (el contrato de trazas decía `register_document`) | Nombre real del catálogo de 001 |
| 2026-10-04 | Los clientes del agente envuelven errores de conexión y timeouts de httpx en `UpstreamError`: el canal responde 502 `upstream_failure` y el span `turn` queda en `ERROR` | Con el gateway caído el turno terminaba en 500 con traceback (edge case "Modelo lento") |
| 2026-10-04 | Los cuatro clientes HTTP entre servicios usan `keepalive_expiry=2` | Con modelos reales hay más de 5 s entre llamadas a `actions_api`; httpx reutilizaba una conexión que uvicorn estaba cerrando (keep-alive de 5 s) y el turno fallaba con `ReadError`. En `fake` nunca pasaba |
| 2026-10-04 | Las pruebas e2e de trazas esperan hasta 180 s a que Phoenix tenga los spans | Phoenix ingiere de forma asíncrona; tras la suite e2e se midió ≈ 1 min de atraso. No se pierden spans |
| 2026-10-04 | El gateway responde 502 `upstream_failure` ante timeouts o conexiones cortadas con Ollama (`httpx.HTTPError`) | En las pruebas con modelos reales Ollama no respondió una vez en 300 s y el gateway devolvía 500; el guion pasó al repetirlo |
| 2026-10-04 | El nodo `respond` garantiza que la respuesta termina con el texto exacto de la siguiente pregunta (`questions.end_with_question`): reemplaza una variante final con otra puntuación o mayúsculas, o la agrega | Con respuestas reales el modelo a veces escribe "¿el auto está a tu nombre?" o "¿Envíame…?"; la pregunta la decide el código (Principio II) |
| 2026-10-04 | Las pruebas del agente que buscaban frases de la plantilla verifican ahora los datos de la respuesta (montos, documento, desajuste) | Tras `make record` la redacción es la del modelo real; los datos siguen viniendo del código |
| 2026-10-04 | `make record ONLY="…"` filtra guiones (no `SCENARIOS`) | `SCENARIOS` ya es la lista de demos del Makefile |
| 2026-10-04 | Ante `upstream_failure` el agente responde al cliente un texto fijo en español; el detalle técnico queda en el span `turn` y en el log | Convergencia T058 (Principio X): el chat mostraba `llm_gateway reply: ReadTimeout: …` |
| 2026-10-04 | `make fixtures-status` lee el uso del gateway después de cada paso y reporta cada respuesta sembrada o faltante con su guion y paso | Convergencia T059: el contrato pide el paso, no solo la tarea |

## Calidad del LLM (`make eval`, Principio VIII)

| Fecha | Modelo | Esquema | Casos | Campos correctos | JSON válido | Resultado |
|---|---|---|---|---|---|---|
| 2026-10-04 | `gemma4:12b` (temperature 0, seed 42, think false) | v3 | 37 (25 originales + 12 nuevos de v3) | 102/114 = **89.5%** (originales 88.2%, nuevos 95.2%) | 100% | Pasa (mínimo 85% y 100%) · `eval/resultados/gate-2026-10-04_104313.json` |
| 2026-10-04 | `gemma4:12b` (temperature 0, seed 42, think false) | v4 (por etapa, O-13) | 37 | 102/114 = **89.5%** (mensajes 69/75 = 92.0%, documentos 33/39 = 84.6%; igual que v3) | 100% | Pasa · mediana por mensaje 12.8 s → **6.9 s** (documentos 15.8 s) · `eval/resultados/gate-2026-10-04_175615.json` (antes de grabar) y `eval/resultados/gate-2026-10-04_195001.json` (gate extendido) |
