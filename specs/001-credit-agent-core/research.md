# Research: Núcleo del agente de crédito con garantía vehicular

**Feature**: `001-credit-agent-core` · **Fecha**: 2026-10-03 · **Plan**: [plan.md](./plan.md)

El stack lo fijó el usuario en `/speckit-plan` (uv workspace, Python 3.12, FastAPI, Pydantic v2,
pytest, LangGraph, Postgres 16, Ollama en el host). Este documento no compara stacks: resuelve los
puntos que el input dejaba abiertos o que chocaban con la spec o la constitución. Cada decisión
tiene id `R-xx` para citarla desde el plan, las tareas y DECISIONS.md.

---

## R-01 · Identificadores en inglés, dominio en español

- **Decision**: todo identificador de código va en inglés: tools (`evaluate_gate`, no
  `evaluar_gate`), nodos del grafo (`eligibility`, `profiling`, `simulation`, `documents`,
  `gate`, `escalation`), enums de etapa y estado, schemas y tablas de Postgres. Los textos al
  cliente, los motivos legibles y los resúmenes de ticket van en español. El glosario de
  [data-model.md](./data-model.md#glosario-spec--código) mapea cada término de la spec a su
  identificador.
- **Excepción**: las llaves de los esquemas de extracción (`eval/esquemas.json`: `intencion`,
  `campos`, `auto_a_nombre_propio`…) se quedan en español. Son el contrato con el modelo, están
  medidas por `make eval` y traducirlas invalidaría el set de evaluación. `packages/contracts`
  las mapea a modelos con nombres en inglés en una sola función de traducción. Registrada en
  Complexity Tracking del plan.
- **Rationale**: la constitución (Principio X) prevalece sobre los nombres en español del input
  de plan.
- **Alternatives considered**: nombres en español en todo el código (viola el Principio X);
  traducir también los esquemas del LLM (rompe la comparabilidad con las corridas de eval).

## R-02 · Nombre del schema de Postgres: `cases`, no `case`

- **Decision**: schemas `cases`, `audit` y `agent`. Tablas `cases.cases`, `cases.escalations`,
  `cases.idempotency_keys`, `audit.audit_log`.
- **Rationale**: `CASE` es palabra reservada en SQL; un schema llamado `case` obliga a citarlo en
  cada consulta y es fuente segura de errores.
- **Alternatives considered**: `"case"` entre comillas en todo el código.

## R-03 · Frontera de base de datos del agente

- **Decision**: una sola base `app` con tres roles de login: `actions_rw` (dueño de `cases`, solo
  `INSERT`/`SELECT` en `audit.audit_log`), `agent_rw` (dueño de `agent`, sin `USAGE` en `cases`
  ni `audit`) y `app_admin` (solo para `init.sql`). El agente se conecta como `agent_rw` con
  `search_path=agent` para el checkpointer de LangGraph.
- **Rationale**: el Principio III dice que el agente nunca toca la base del caso. El checkpointer
  vive en el mismo Postgres, así que la frontera se hace cumplir con permisos, no solo con
  convención. Un test de arquitectura intenta `SELECT` sobre `cases.cases` con `agent_rw` y
  espera `permission denied`.
- **Alternatives considered**: un segundo contenedor de Postgres para el agente (agrega un
  contenedor fuera de la topología); confiar en que el agente no importe nada de `cases`
  (import-linter no ve SQL crudo).

## R-04 · Concurrencia: dos candados con espacios de llave distintos

- **Decision**:
  1. **Turno del agente**: al recibir un mensaje o documento, el agente toma
     `pg_try_advisory_lock(1, hashtext(case_id))` en su conexión `agent_rw`, reintentando
     hasta `CASE_LOCK_TIMEOUT_S` (10 s por defecto). Si no lo obtiene, responde `409
     case_busy` sin efectos (FR-009). Lo libera al terminar el turno.
  2. **Cada tool**: `actions_api` abre una transacción y toma
     `pg_advisory_xact_lock(2, hashtext(case_id))`, lee el caso, compara `expected_version`,
     ejecuta y hace commit. Si la versión no coincide responde `409 version_conflict`.
- **Rationale**: el spec pide un mensaje a la vez por caso. El candado de `actions_api` solo
  serializa tools sueltas; un turno del agente hace varias tools y escribe el checkpoint de
  LangGraph, que se corrompe si dos turnos usan el mismo `thread_id` a la vez. El primer
  argumento (`1` y `2`) separa los espacios de llave: con la misma llave en ambos servicios, el
  agente tendría el candado del caso mientras `actions_api` lo espera, y el turno se bloquearía
  solo.
- **Alternatives considered**: `asyncio.Lock` en memoria (falla con más de un worker); solo
  versión esperada (el segundo turno gastaría llamadas al LLM para luego chocar).

## R-05 · Transacción de una tool y qué se audita

- **Decision**: el decorador `@tool(name, stages=..., actors=...)` de `actions_api` ejecuta en
  una transacción: candado del caso → idempotencia (si la llave existe, devuelve la respuesta
  guardada) → carga del caso → versión esperada → permisos actor × etapa × tool → handler →
  `version + 1` → `INSERT` en `audit.audit_log` → `INSERT` en `cases.idempotency_keys` → commit.
  Si alguna verificación falla, igual se escriben la entrada de auditoría y la de idempotencia
  con `outcome = rejected` y el motivo, sin tocar el caso.
- **Rationale**: FR-005 a FR-008 y SC-004 (100% de acciones, aceptadas o rechazadas, en el
  registro). Guardar también la respuesta rechazada hace que un reintento con la misma llave dé
  el mismo resultado.
- **Alternatives considered**: auditar desde un middleware HTTP (no ve el resultado de negocio
  ni comparte la transacción).

## R-06 · Registro de acciones solo de inserción

- **Decision**: `audit.audit_log` con trigger `BEFORE UPDATE OR DELETE ... FOR EACH ROW` y
  trigger `BEFORE TRUNCATE ... FOR EACH STATEMENT` que lanzan excepción, más permisos (solo
  `INSERT`/`SELECT` para `actions_rw`). Cada fila guarda `policy_version` y `case_version`.
- **Rationale**: FR-008 y SC-009. El trigger cubre a quien tenga permisos de más; los permisos
  cubren el caso común.

## R-07 · Estado del caso como agregado JSONB versionado

- **Decision**: `cases.cases` tiene columnas de consulta (`id`, `stage`, `status`, `version`,
  `policy_version`, `client_id`, timestamps) y una columna `state JSONB` validada contra el
  modelo `CaseState` de `packages/contracts`. Escalaciones e idempotencia van en tablas propias.
  Los bytes de los documentos van en el volumen `documents` montado solo en `actions_api`,
  nombrados por `sha256`.
- **Rationale**: el caso se lee y escribe completo en cada tool, bajo un candado y una versión;
  un agregado evita una docena de tablas que nadie consulta por separado en un demo. El reporte
  de P5 sale del registro de acciones, no de estas columnas.
- **Alternatives considered**: tablas normalizadas por entidad (más migraciones y joins sin
  beneficio para los 4 demos).

## R-08 · Gate automático + `evaluate_gate`

- **Decision**: `evaluate_gate` es la única tool que puede poner `status = ok_for_lender`. Las
  tools que cambian validaciones (`submit_document`, `verify_validation_manually`) la invocan
  internamente al final de su transacción y la auditan como una entrada aparte con
  `actor = system`. El agente también puede llamarla; si falta algo, la respuesta es
  `rejected` con la lista de validaciones faltantes y queda auditada.
- **Rationale**: clarificación del 2026-10-03 (FR-036, FR-037). Se cumple el input de plan ("solo
  la tool evaluar_gate pone el OK") y nadie tiene que acordarse de pedirlo.

## R-09 · Escalaciones automáticas y el resumen del ticket

- **Decision**: `actions_api` escala sin intervención del agente cuando: un mismatch del mismo
  tipo llega a N intentos, un proveedor falla tras los reintentos, o el auto no tiene valor de
  referencia. El agente llama `escalate` cuando la intención es `pedir_humano` o
  `tema_sensible`. En todos los casos el resumen y la acción sugerida del ticket se generan con
  plantillas deterministas a partir del estado del caso (motivo → acción sugerida en una tabla
  de `actions_api`). Si escala el agente, agrega su nota.
- **Rationale**: `actions_api` no llama al LLM (el código decide); un resumen por plantilla es
  reproducible y suficiente para SC-007. Ver R-15.
- **Alternatives considered**: resumen redactado por el LLM (no reproducible y obliga a
  `actions_api` a hablar con el gateway).

## R-10 · Confianza por campo en Document Intelligence

- **Decision**: `doc_intel` pide OCR (`/v1/ocr`) y extracción (`/v1/extract` con el esquema
  `documento`) al gateway y calcula la confianza de cada campo de forma determinista:
  - `0.0` si el valor es `null`;
  - `0.3` si no pasa su validador de formato (CURP, fechas ISO, montos > 0, NIV de 17
    caracteres, código postal de 5 dígitos, moneda ISO);
  - `0.95` si pasa el formato y el valor aparece en el texto del OCR (comparación normalizada:
    mayúsculas, sin acentos ni puntuación; montos por dígitos);
  - `0.6` si pasa el formato pero no aparece literal en el OCR.
  Con el umbral inicial de la política (`0.8`), solo un valor respaldado por el OCR se usa en
  una validación.
- **Rationale**: los modelos no dan una confianza calibrada por campo y pedírsela en el JSON es
  poco confiable. Que el valor esté en el texto leído es una señal barata y determinista contra
  alucinaciones de la extracción.
- **Alternatives considered**: confianza autodeclarada por el modelo; logprobs de Ollama
  (dependen de la versión y no aplican al OCR).

## R-11 · LLM Gateway: modos, llave de fixture y respaldo

- **Decision**:
  - Solo el contenedor `llm_gateway` recibe `LLM_MODE` y `OLLAMA_URL` en el compose (Principio
    V: el resto no conoce el modo).
  - **Llave de fixture**: `sha256` del JSON canónico de `(task, schema_name, inputs)`, con textos
    normalizados (minúsculas, espacios colapsados). Para `extract` los inputs incluyen la
    pregunta que hizo el agente, no solo el texto del cliente; para `ocr`, el `sha256` de los
    bytes. Archivo: `fixtures/llm/<task>/<hash>.json` con la solicitud y la respuesta, legible.
  - **Sin fixture en `fake`**: `extract` devuelve `intencion = "otro"` y **todas** las llaves de
    `campos` en `null` (cumple el esquema); `reply` devuelve un texto de plantilla por etapa;
    `ocr` devuelve error `fixture_missing`. Cada respaldo se registra como `fixture_miss` en los
    logs para detectarlo en los tests.
  - `record` llama a Ollama y escribe el fixture; `ollama` solo llama.
  - Ollama: `gemma4:12b` con `format` = esquema JSON, `options = {temperature: 0, seed: 42}`,
    `think = false`; `glm-ocr` para OCR.
- **Rationale**: el input de plan decía llave `(tarea, texto normalizado)`, pero "sí" significa
  algo distinto según la pregunta ("¿está a tu nombre?" contra "¿tienes la segunda llave?").
  Sin la pregunta en la llave, el modo `fake` devolvería la misma extracción para ambas. El
  respaldo con todos los campos en `null` respeta el contrato de "todos los campos requeridos".
- **Alternatives considered**: llave solo por texto (colisiones entre etapas); fallar ante un
  fixture faltante en `extract` (haría frágiles los guiones al cambiar una coma).

## R-12 · Esquema de la etapa y el nuevo valor `tema_sensible`

- **Decision**: `/v1/extract` recibe `schema_name`. En esta feature todas las etapas usan el
  esquema `mensaje` evaluado (la etapa y la pregunta van como contexto) y los documentos usan
  `documento`. Se agrega `tema_sensible` al enum `intencion` (esquemas versión 3), con casos
  nuevos en `eval/casos_eval.jsonl` y una corrida de `make eval` antes de dar la tarea por
  terminada (Principio VIII).
- **Rationale**: FR-040 necesita clasificar temas sensibles. Hacerlo en la misma llamada evita
  una segunda inferencia por mensaje. Esquemas recortados por etapa quedan para cuando el set de
  eval los cubra.
- **Alternatives considered**: tarea separada `classify_sensitive` (doble latencia); esquemas
  por etapa sin eval (viola el Principio VIII).

## R-13 · `make eval` como gate

- **Decision**: nuevo `scripts/eval_gate.py` que corre `eval/casos_eval.jsonl` contra el
  `llm_gateway` en `LLM_MODE=ollama` (`/v1/extract`; los documentos usan el texto OCR guardado en
  `eval/ocr_D0x.txt`), aplica la regla `puntaje` de `eval/esquemas.json` y termina con código
  distinto de 0 si los campos correctos quedan por debajo de 85% o algún JSON no es válido.
  `eval/correr_eval.py` se queda como está: compara modelos y llena el Excel.
- **Rationale**: el runner actual compara modelos contra otro backend y no tiene umbral; el gate
  tiene que medir el gateway real con el modelo elegido.

## R-14 · Política versionada y fijada por caso

- **Decision**: `policy/policy.yaml` es la versión vigente (`policy_version: "2026.10-v1"`). Las
  versiones anteriores se guardan en `policy/archive/<policy_version>.yaml`. `actions_api` carga
  todas al arrancar, las valida con el modelo `Policy` y, al crear un caso, guarda la versión
  vigente en el caso. Cada tool resuelve la política del caso por su versión y la pasa a las
  reglas. Si un caso apunta a una versión que no está cargada, la tool responde
  `policy_unavailable` y escala.
- **Rationale**: la spec fija la versión al crear el caso (Assumptions) y el Principio VI exige
  que cada decisión registre la versión que la produjo.
- **Alternatives considered**: un solo archivo y aplicar siempre la versión vigente (rompe la
  suposición de la spec si la política cambia a mitad de un caso).

## R-15 · Qué es política y qué es proveedor

- **Decision**:
  - **Política** (`policy.yaml`): bandas de perfil por score (monto máximo, tasa, plazo
    estándar), porcentajes de las opciones, porcentaje máximo financiable del valor del auto,
    IVA sobre intereses, tolerancia de ingreso, umbral de confianza, umbral de similitud,
    antigüedad de comprobantes, comprobantes por situación laboral, N intentos, reintentos por
    proveedor.
  - **Proveedores simulados** (`providers/`, leen `fixtures/providers/`): Buró (score por
    cliente), consulta vehicular (gravamen y **valor de referencia** del auto) y cotizador de
    llave (precio por marca, modelo y año). Un fixture puede marcar `fail: true` para forzar la
    escalación por proveedor.
- **Rationale**: un precio de cerrajería o un valor de mercado son datos externos, no umbrales de
  negocio. Esto ajusta dos supuestos de la spec (ver "Ajustes a la spec" al final).

## R-16 · Datos del cliente de prueba y actor "cliente"

- **Decision**: `POST /cases` recibe `test_client_id`. El fixture del cliente trae nombre,
  domicilio, CURP, teléfono y la referencia de su vehículo; se guardan como datos declarados al
  crear el caso (simula un lead que ya trae sus datos). El agente pregunta el resto (auto,
  llave, situación laboral, ingreso, consentimiento). Las acciones que son decisión del cliente
  (consentimiento, elegir opción, cancelar) las ejecuta el agente con `actor = agent` y
  `on_behalf_of = client`, con el id del mensaje del cliente como evidencia.
- **Rationale**: sin autenticación (Principio XI) no hay forma de que el cliente llame a
  `actions_api` por sí mismo; el canal es el agente. El header `X-Actor` lo declara quien llama
  y no se verifica: es un supuesto explícito del demo.

## R-17 · Cálculo de la cuota

- **Decision**: amortización francesa con tasa mensual = tasa anual / 12, multiplicada por
  `(1 + IVA)` si `apply_vat_on_interest` es verdadero. Aritmética con `Decimal`, redondeo
  `ROUND_HALF_UP` a centavos, montos serializados como string. Monto financiado de cada opción =
  porcentaje × monto máximo financiable; monto para el cliente = monto financiado − costo de la
  llave (si lo hay).
- **Rationale**: FR-021 a FR-023 y la clarificación de opciones. `Decimal` evita diferencias de
  centavos entre corridas y entre tests.

## R-18 · Comparación de nombres y domicilios

- **Decision**: función pura `rules.matching` con normalización (mayúsculas, sin acentos,
  expansión de abreviaturas de una tabla fija: `AV.`→`AVENIDA`, `C.`→`CALLE`, `COL.`→`COLONIA`,
  `NO.`/`#`→`NUMERO`…; espacios colapsados) y similitud `difflib.SequenceMatcher` sobre tokens
  ordenados. Nombre: coincide si la similitud ≥ `name_similarity_threshold`. Domicilio: código
  postal idéntico y calle + número con similitud ≥ `address_similarity_threshold`.
- **Rationale**: clarificación del 2026-10-03. `difflib` está en la librería estándar: sin
  dependencias nuevas y determinista.
- **Alternatives considered**: `rapidfuzz` (más rápido, pero una dependencia más sin necesidad
  para 4 documentos por caso).

## R-19 · Grafo del agente

- **Decision**: `StateGraph` con `thread_id = case_id` y nodos `interpret` → router →
  {`eligibility`, `profiling`, `simulation`, `documents`, `gate`, `escalation`} → `respond`.
  - `interpret` llama `/v1/extract` y registra el mensaje con la tool `append_message`.
  - El router decide **solo** con la intención clasificada y la `stage`/`status` del caso que
    devolvió la última tool (`pedir_humano`/`tema_sensible` → `escalation`, `cancelar` →
    `cancel_case`).
  - Cada nodo de etapa traduce los campos extraídos a llamadas de tools y elige la siguiente
    pregunta de una tabla fija de preguntas por campo faltante (texto determinista, que además
    estabiliza las llaves de fixture de R-11).
  - `respond` llama `/v1/reply` con hechos estructurados (etapa, resultado de tools, siguiente
    pregunta) y nunca con el texto crudo de un documento.
  - Las llaves de idempotencia de las tools se derivan de `(message_id, step, tool)`, así que
    reprocesar un mismo mensaje no duplica acciones.
- **Rationale**: Principio II (las transiciones dependen del resultado de las tools) y
  Principio X (texto como dato). `interpret` y `respond` son nodos auxiliares además de los seis
  de etapa que pidió el input de plan.

## R-20 · Arquitectura verificada por tests

- **Decision**: `tests/architecture/` con:
  - **import-linter** (`.importlinter`): servicios independientes entre sí (solo comparten
    `contracts`); `ollama` prohibido fuera de `llm_gateway`; `psycopg`/`sqlalchemy` prohibidos en
    `doc_intel` y `llm_gateway`; `actions_api.rules` sin `httpx`, `psycopg`, `ollama`, `os`,
    `pathlib` ni `datetime.now` (las reglas reciben la fecha como parámetro).
  - **test de permisos de BD** (R-03): `agent_rw` no puede leer `cases` ni `audit`.
  - **test del compose**: `LLM_MODE`/`OLLAMA_URL` solo en `llm_gateway`; `doc_intel` sin
    variables de base de datos ni volúmenes; el volumen `documents` solo en `actions_api`.
- **Rationale**: Principio III exige que las fronteras fallen ante una violación, y
  import-linter solo ve imports de Python.

## R-21 · Trazabilidad FR → tests

- **Decision**: marcador `@pytest.mark.req("FR-xxx")` registrado en el `pyproject.toml` raíz.
  `scripts/traceability.py` recorre los tests por AST, cruza los ids con la lista de FR de
  `spec.md`, escribe `TRACEABILITY.md` y termina con error si algún FR no tiene test (`make
  traceability`).
- **Rationale**: Principio VII; leer el AST no requiere levantar servicios ni importar módulos.

## R-22 · Logs del gateway y redacción de PII

- **Decision**: logs JSON por línea a stdout con `task`, `model`, `mode`, `latency_ms`,
  `prompt_tokens`, `completion_tokens`, `fixture_hit`. Antes de registrar texto, una función de
  redacción reemplaza CURP, RFC, teléfonos (10 dígitos) y los nombres conocidos del caso que
  llegan en la solicitud por `[REDACTED_*]`. Phoenix queda para la feature 003.
- **Rationale**: input de plan y Principio X (sin datos personales en logs, aunque sean
  sintéticos).

## R-23 · Demos y e2e

- **Decision**: guiones YAML en `fixtures/scenarios/` (`happy_path`, `eligibility_rejection`,
  `document_correction`, `document_escalation`, `no_spare_key`). El demo 3 tiene dos guiones,
  uno por rama. `scripts/run_demo.py` los envía al agente por HTTP, imprime cada respuesta y al
  final muestra el estado del caso y su registro de acciones leídos de `actions_api`. `make
  demo-<escenario>` lo invoca. `tests/e2e/` corre los mismos guiones contra el compose en
  `LLM_MODE=fake` y verifica el estado final esperado. Los e2e verifican estado y auditoría, no
  el texto exacto de las respuestas.
- **Rationale**: FR-052 y SC-001; el texto redactado por el LLM puede variar entre modos y no es
  lo que el demo demuestra.

---

## Ajustes a la spec que surgen del diseño

Aplicados a `spec.md` el 2026-10-03:

1. **FR-017**: nombre y domicilio vienen del cliente de prueba al crear el caso (R-16); el agente
   no los pregunta.
2. **FR-047 y Assumptions**: el costo de la llave y el valor de referencia del auto vienen de
   proveedores simulados, no de tablas de la política (R-15).
3. **FR-004**: el actor "cliente" actúa a través del agente con `on_behalf_of = client` (R-16).
4. **FR-040**: la clasificación de tema sensible requiere el valor `tema_sensible` en el esquema
   de mensaje y casos nuevos en eval (R-12).
