# Research: Modelos reales y observabilidad

Decisiones de diseño de la feature 003 (O-01…O-15). Continúan las de
[001/research.md](../001-credit-agent-core/research.md) (R-01…R-23) y
[002/research.md](../002-demo-web/research.md) (W-01…W-14), y se registran en `DECISIONS.md` al
implementar (Principio I).

Versiones verificadas el 2026-10-04 en un entorno aislado: `arize-phoenix-otel` 0.17.2,
`openinference-instrumentation-langchain` 0.1.78, `opentelemetry-instrumentation-httpx` y
`-fastapi` 0.66b0, `opentelemetry-sdk` 1.45.0, `arize-phoenix-client` 3.5.0, `langgraph` 1.2.12
(depende de `langchain-core`, que es lo que instrumenta OpenInference). Imagen
`arizephoenix/phoenix:version-20.19.0` (2026-10-01).

## Punto de partida (lo que ya existe)

- `llm_gateway` ya resuelve `LLM_MODE=fake|record|ollama` (R-11) y es el único que lo conoce
  (`test_only_the_gateway_knows_the_llm_mode_and_ollama`). `record` hoy escribe directo en
  `fixtures/llm/`, sin latencia, tokens ni origen.
- Los 56 fixtures de `fixtures/llm/` son **sembrados** por `scripts/seed_fixtures.py` desde los
  guiones (`extract`, `ocr`); `fixtures/llm/reply/` está vacío y `fake` responde con plantilla.
- `make eval` ya existe (R-13, `scripts/eval_gate.py`): llama a `/v1/extract` del gateway, aplica
  la regla de `puntaje` de `eval/esquemas.json`, guarda `eval/resultados/gate-*.json` y sale con 1
  si no cumple. Última corrida (2026-10-04, esquema v3): 102/114 = 89.5%, JSON válido 100%;
  desglose calculado del archivo: mensajes 69/75 = 92.0%, documentos 33/39 = **84.6%**; mediana
  por mensaje 12.8 s, por documento 17.9 s.
- No hay trazas: el gateway escribe logs JSON con PII redactada (R-22).

## O-01 · Contenedor `phoenix`

- **Decision**: servicio `phoenix` en `docker-compose.yml` con `arizephoenix/phoenix:version-20.19.0`
  (fijada, nunca `latest`), puerto 6006 (UI y OTLP/HTTP en `/v1/traces`), volumen `phoenix_data`
  con `PHOENIX_WORKING_DIR=/mnt/data` y healthcheck a `GET /healthz` con el intérprete de la
  imagen (si la imagen no trae con qué ejecutarlo, se omite: nadie depende de él). Ningún servicio
  declara `depends_on: phoenix`.
- **Rationale**: es el 7.º contenedor de la topología de referencia y la entrada del plan. Sin
  `depends_on`, el sistema arranca y atiende turnos con Phoenix apagado (FR-092, SC-022). El
  volumen conserva las trazas entre reinicios para revisarlas después de una demo.
- **Alternatives considered**: Langfuse, Grafana/Tempo, Prometheus (excluidos por el usuario y por
  el Principio XI); trazas solo en logs (no cumple FR-091: no hay consola).

## O-02 · Registro de telemetría por servicio

- **Decision**: un módulo `telemetry.py` en `agent`, `llm_gateway` y `doc_intel` con
  `setup(app=None)`: si `PHOENIX_COLLECTOR_ENDPOINT` está definido, llama
  `phoenix.otel.register(project_name="tech-challenge-agent", batch=True, auto_instrument=True)`
  (en `agent`, `auto_instrument=False` + instrumentación explícita, ver O-04), instrumenta `httpx`
  (`HTTPXClientInstrumentor().instrument()`) y, en `llm_gateway` y `doc_intel`, la app FastAPI
  (`FastAPIInstrumentor.instrument_app(app, excluded_urls="health")`). Sin la variable, no registra
  exportador (tests locales y unitarios no exportan). Compose define
  `PHOENIX_COLLECTOR_ENDPOINT=http://phoenix:6006` solo en esos tres servicios.
- **Rationale**: `register` resuelve proyecto, endpoint y exportador OTLP; `batch=True` exporta en
  segundo plano, de modo que un Phoenix caído no bloquea el turno (FR-092). Excluir `/health`
  evita una traza cada 5 s por healthcheck. Un módulo por servicio (≈20 líneas) respeta que ningún
  servicio importa código interno de otro (Principio III).
- **Alternatives considered**: paquete compartido `packages/telemetry` (otro paquete del workspace
  para 20 líneas; la frontera de `packages/` es para contratos); variables `OTEL_*` puras sin
  `phoenix.otel` (más configuración repetida por servicio).

## O-03 · Un turno = una traza

- **Decision**: el agente abre un span raíz `turn` (OpenInference `AGENT`) en `run_turn`, que
  envuelve `graph.ainvoke`. Atributos: `session.id` = id del caso, `metadata` con `message_id`,
  `kind` (`start|message|document`), etapa y estado antes y después, `input.value` (texto del
  cliente o tipo de documento, redactado) y `output.value` (respuesta, redactada). El agente
  **no** instrumenta su FastAPI de entrada: él inicia la traza. Todas sus llamadas salientes
  (`actions_api`, `llm_gateway`) van por `httpx` instrumentado, que inyecta `traceparent`; los
  servidores aguas abajo extraen el contexto con la instrumentación de FastAPI.
- **Rationale**: FR-085 pide exactamente una traza por turno; si el agente instrumentara su
  servidor, el span HTTP sería la raíz y además las lecturas (`GET /conversation`) abrirían trazas
  sueltas. `session.id` permite filtrar por caso en la vista de sesiones de Phoenix (FR-086,
  SC-021). Un reintento de la web con la misma `Idempotency-Key` que el candado resuelve sin
  ejecutar el grafo no abre `turn`.
- **Alternatives considered**: raíz en el span HTTP del agente (trazas extra por lecturas, nombre
  poco legible); baggage con el id del caso hacia los demás servicios (innecesario: el caso queda
  en la raíz y la traza agrupa todo).

## O-04 · LangGraph instrumentado con OpenInference, sin entrada/salida de nodos

- **Decision**: `agent` instala `openinference-instrumentation-langchain` y lo activa con
  `LangChainInstrumentor().instrument(tracer_provider=tp, config=TraceConfig(hide_inputs=True,
  hide_outputs=True))`. Cada nodo del grafo (`interpret`, `stage_*`, `intent_*`, `documents`,
  `respond`) aparece como span `CHAIN` con su nombre, orden, duración y error, sin el estado.
- **Rationale**: los nodos son las etapas del turno (FR-087). Su entrada y salida es el
  `TurnState` completo (historial, nombre, domicilio, campos extraídos); mostrarlo violaría la
  política de ocultamiento (FR-093) y duplicaría lo que ya muestran los spans de tool y de modelo,
  que sí llevan entrada y salida redactadas. `auto_instrument=True` instanciaría el mismo
  instrumentador sin poder pasarle `TraceConfig`, por eso en `agent` se instrumenta explícitamente
  (mismo instrumentador, misma librería; desviación menor de la entrada del plan).
- **Alternatives considered**: `auto_instrument=True` con entrada/salida visibles (expone PII);
  `OPENINFERENCE_HIDE_INPUTS` por variable de entorno (también ocultaría la entrada de los spans
  manuales del agente, que usan el mismo `TracerProvider` de OpenInference); redactar en un
  `SpanProcessor` (en el SDK 1.45 los atributos ya son inmutables al llegar a `_on_ending`/`on_end`).

## O-05 · Spans de tool en el agente

- **Decision**: `Deps.call_tool` abre un span `TOOL` por llamada: `tool.name`, `metadata` con
  actor, `idempotency_key` y versión esperada, `input.value` = entrada de la tool (JSON
  redactado), `output.value` = desenlace, código de rechazo y etapa/estado/versión resultantes.
  Un rechazo marca el span con estado `ERROR` y el código; el reintento por `version_conflict` es
  un segundo span hermano.
- **Rationale**: el agente es quien conoce la tool, su entrada y el desenlace (FR-088, FR-090), y
  todas las tools del turno pasan por ese método. Bajo cada span de tool cuelga la petición HTTP a
  `actions_api` y, para documentos, la cadena `doc_intel` → `llm_gateway` (O-06).
- **Alternatives considered**: spans de tool dentro de `actions_api` (O-06 explica por qué
  `actions_api` no exporta); atributos solo en el span HTTP (sin `tool.name` ni desenlace legible).

## O-06 · `actions_api` solo propaga contexto

- **Decision**: `actions_api` instala `opentelemetry-instrumentation-fastapi` e `-httpx` y los
  activa sin SDK ni exportador ni `PHOENIX_COLLECTOR_ENDPOINT`. Con el `TracerProvider` no-op de
  la API de OpenTelemetry, el span de entrada es no-grabante pero conserva el contexto recibido, y
  `httpx` lo reinyecta hacia `doc_intel`.
- **Rationale**: un turno de documento cruza `agent → actions_api → doc_intel → llm_gateway`
  (`DocumentReader` vive en `actions_api`); sin propagación en el salto intermedio la traza se
  partiría en dos (FR-085). Verificado el 2026-10-04 con dos servidores uvicorn reales: el
  `traceparent` que llega a `doc_intel` conserva el trace id recibido por el servicio intermedio.
  Que `actions_api` no exporte evita duplicar los spans de tool del agente y que las lecturas de la
  web (`GET /cases`, `/audit`, métricas) llenen Phoenix de trazas. Es una adición a la entrada del
  plan, que nombraba solo `agent`, `llm_gateway` y `doc_intel`.
- **Alternatives considered**: registrar `actions_api` en Phoenix (trazas de cada lectura de la
  web y del asesor; spans de tool duplicados); no tocar `actions_api` (traza partida en turnos de
  documento).

## O-07 · Spans de modelo en `llm_gateway`

- **Decision**: cada tarea abre un span `CHAIN` (`extract`, `ocr`, `reply`) y, dentro, un span
  `LLM` por llamada al modelo con atributos OpenInference: `llm.provider=ollama`,
  `llm.model_name`, `llm.invocation_parameters` (temperature, seed, num_predict, think),
  `llm.input_messages`/`input.value` y `llm.output_messages`/`output.value` (redactados),
  `llm.token_count.prompt|completion|total`, y `metadata` con `task`, `mode`, `schema_name`,
  `stage`, `schema_version`, `fixture_key`. Cada intento del reintento por salida inválida es un
  span `LLM` propio; el inválido lleva estado `ERROR` con el error de esquema. En `fake`, el span
  `LLM` lleva `metadata.replay=true`, `fixture_origin` (`recorded|seeded|missing`) y la latencia y
  tokens **originales** de la grabación como `metadata.recorded_latency_ms` y
  `llm.token_count.*`; la duración del span es la de la reproducción. En OCR, la entrada es el
  sha256 y el tipo MIME, nunca la imagen.
- **Rationale**: cubre FR-089 y FR-090 y deja claro en la consola qué fue reproducción (escenario
  7 de P2). La imagen en base64 inflaría cada traza sin aportar al diagnóstico.
- **Alternatives considered**: instrumentador OpenInference de la librería `ollama` (no aplica a
  `fake` ni marca reproducciones, y no conoce esquema ni etapa); un span por tarea sin hijos (el
  reintento quedaría invisible).

## O-08 · Spans en `doc_intel`

- **Decision**: `doc_intel` abre un span `CHAIN` `read_document` con `output.value` = tipo
  detectado y confianza por campo (valores redactados). Sus llamadas a `/v1/ocr` y `/v1/extract`
  van por `httpx` instrumentado, así que los spans del gateway cuelgan de él.
- **Rationale**: el escenario 2 de P2 pide ver lectura, extracción y confianza en orden.
- **Alternatives considered**: solo los spans HTTP automáticos (no muestran tipo ni confianza).

## O-09 · Política de ocultamiento compartida

- **Decision**: `redact()` pasa de `llm_gateway/redaction.py` a `contracts.redaction` (mismas
  reglas: CURP, RFC, teléfono y nombres conocidos). La usan los logs del gateway (R-22) y todos los
  spans manuales (`turn`, `TOOL`, `LLM`, `read_document`). Los nodos de LangGraph no llevan
  entrada ni salida (O-04).
- **Rationale**: FR-093 pide la misma política en trazas que en logs; tres servicios la necesitan
  y no pueden importarse entre sí. `contracts` ya aloja funciones puras compartidas que son parte
  del contrato (`fixture_key`, `to_domain`).
- **Alternatives considered**: copiar `redact` en cada servicio (tres copias de reglas de
  privacidad que pueden divergir); redactar en Phoenix (no existe ese punto).

## O-10 · Respuestas grabadas: origen, métricas y llave

- **Decision**: el fixture agrega `origin` (`seeded|recorded`), `latency_ms`, `prompt_tokens`,
  `completion_tokens`, `schema_version` y `prompt_version` a lo que ya guarda (`request`,
  `response`, `recorded_at`, `model`). `scripts/seed_fixtures.py` escribe `origin: seeded` sin
  métricas. La llave (`contracts.llm.fixture_key`) incorpora `schema_version` (de
  `eval/esquemas.json`) y `PROMPT_VERSION` (constante en `contracts.llm`, se sube al cambiar
  instrucciones), así que un cambio de esquema o de instrucciones convierte las grabaciones viejas
  en faltantes visibles en lugar de reproducir respuestas de otro prompt. Un fixture sin `origin`
  se lee como `seeded`.
- **Rationale**: FR-080, FR-083 y el borde "respuesta grabada faltante". Hoy la llave solo cubre
  `(tarea, esquema, entradas)`: con esquemas por etapa (O-13) una grabación vieja traería campos
  que el esquema reducido rechaza.
- **Alternatives considered**: hash del prompt completo en la llave (exacto, pero el script de
  siembra tendría que reconstruir el prompt del gateway); carpeta por versión (duplica fixtures).

## O-11 · `make record` con promoción por demo

- **Decision**: en `LLM_MODE=record` el gateway escribe en `fixtures/llm/_recording/<tarea>/`
  (ignorado por git; mismo volumen ya montado), nunca en `fixtures/llm/<tarea>/`.
  `scripts/record_fixtures.py` (objetivo `make record`) verifica que el gateway esté en `record`,
  y por cada guion de los 4 demos (5 archivos, ramas A y B del demo 3): vacía `_recording/`,
  corre el guion con la misma lógica de `scripts/run_demo.py`, y si el demo llega a su resultado
  esperado mueve lo grabado a `fixtures/llm/` (reemplaza por llave); si no, lo descarta y reporta
  el guion y el paso que falló. Termina con el resumen por demo y sale con 1 si alguno falló.
- **Rationale**: FR-081 (una grabación fallida no reemplaza las vigentes) sin que el gateway sepa
  de demos. Los guiones corren en secuencia, así que todo lo grabado entre dos vaciados pertenece
  a un solo demo. Los guiones ya verifican resultado, tools y eventos (`expected` en el YAML).
- **Alternatives considered**: grabar directo y revertir con git (deja el árbol sucio y mezcla
  demos); que el gateway reciba el nombre del demo por cabecera (el gateway no debe saber de demos).

## O-12 · Uso de respuestas grabadas y faltantes

- **Decision**: el gateway lleva, en memoria, el uso de fixtures desde el arranque o el último
  reinicio del contador: `GET /v1/fixtures/usage` devuelve conteos por origen
  (`recorded|seeded|missing`) y por tarea con las llaves; `DELETE /v1/fixtures/usage` lo reinicia.
  `make fixtures-status` (`scripts/fixtures_status.py`) reinicia el contador, corre los 4 demos en
  `fake` y reporta por demo cuántas llamadas usaron respuestas auténticas, sembradas o faltantes,
  y lista los fixtures del directorio que ningún demo usó (con `--prune` los borra).
- **Rationale**: FR-083 y SC-019 piden saber si los demos usan solo respuestas auténticas; las
  llaves de `reply` dependen de hechos calculados en tiempo de ejecución, así que no se pueden
  derivar offline de los guiones. El mismo endpoint lo usa el test e2e de SC-019.
- **Alternatives considered**: leer los logs del gateway (frágil, depende del formato de log);
  consultar Phoenix (haría que un test de reproducibilidad dependa de la consola).

## O-13 · Esquemas de mensaje por etapa

- **Decision**: `eval/esquemas.json` pasa a **v4** con un mapa `etapas` (llaves = valores de
  `Stage`) que lista los campos de mensaje que pide cada etapa; el gateway deriva el esquema
  reducido filtrando `properties` y `required` de `campos`, y el prompt (que se arma desde el
  esquema) lista solo esos campos. `intencion` conserva su enumeración completa en todas las
  etapas (pedir humano, cancelar y tema sensible valen siempre). Sin etapa (`stage=null`) se usa
  el esquema completo. El esquema de documentos no cambia. Campos por etapa:

  | Etapa | Campos |
  |---|---|
  | `eligibility` | `nombre_completo`, `auto_a_nombre_propio`, `adeudos_vehiculo`, `segunda_llave`, `auto_marca`, `auto_modelo`, `auto_anio` |
  | `profiling` | `domicilio`, `codigo_postal`, `ingreso_monto`, `ingreso_periodicidad`, `situacion_laboral`, `consentimiento_buro` |
  | `simulation` | `opcion_elegida`, `monto_solicitado`, `plazo_meses` |
  | `documents` | `nombre_completo`, `domicilio`, `codigo_postal`, `ingreso_monto`, `ingreso_periodicidad`, `situacion_laboral` |

- **Rationale**: entrada del plan: con salida restringida a esquema el modelo escribe todos los
  campos (16 hoy, con `null`), y los tokens de salida dominan la latencia de extracción. Con 3–7
  campos la salida baja a la mitad o menos. Verificado contra los datos: todas las extracciones de
  los 5 guiones y todos los casos de mensaje de `eval/` con etapa caben en el conjunto de su
  etapa (M17, corrección de ingreso en documentos, cabe en `documents`; M18–M20 son
  `transversal` y van sin etapa). La regla de puntaje no cambia: un campo fuera del esquema cuenta
  como ausente (`null`).
- **Consecuencia aceptada**: un dato que el cliente adelante fuera de su etapa (p. ej. el ingreso
  durante elegibilidad) ya no se extrae en ese turno; el agente lo pregunta en su etapa. Se
  registra en `DECISIONS.md`.
- **Gate obligatorio**: cambiar el esquema exige `make eval` en verde (Principio VIII). Se registra
  en la tabla "Calidad del LLM" de `DECISIONS.md` con la mediana de segundos por mensaje antes
  (12.8 s) y después.
- **Alternatives considered**: esquema completo (la latencia actual); esquemas acumulados (cada
  etapa más las anteriores: documentos volvería a pedir 16 campos); filtrar también las reglas
  por etapa (menos tokens de entrada, pero riesgo de perder exactitud medida; se deja para otra
  iteración con su propio `make eval`).

## O-14 · `make eval`: se extiende `scripts/eval_gate.py`

- **Decision**: `make eval` sigue corriendo `scripts/eval_gate.py` (R-13), que ya llama a
  `llm_gateway /v1/extract` con la etapa de cada caso (ahora selecciona el esquema por etapa),
  aplica la regla de puntaje y sale con 1 si no cumple. Se extiende con: desglose por mensajes y
  documentos, modelo en el resumen (lo expone `/health`), lista de casos fallidos, salida con 2 si
  el gateway no está en `ollama` (se quita `--allow-fake` del camino del umbral), y la lógica de
  puntaje se separa en funciones puras importables. `tests/eval/test_eval_gate.py` corre el gate
  completo con `@pytest.mark.ollama`; `pyproject.toml` registra el marcador y `addopts` agrega
  `-m "not ollama"`. Los tests de la regla de puntaje y del umbral (con resultados construidos) sí
  corren por defecto. `eval/correr_eval.py` queda como está.
- **Rationale**: la entrada del plan pide adaptar `eval/correr_eval.py`, pero ese script es el
  comparador de modelos (llama al backend `/comparar`, recorre 7 modelos y llena el Excel), y la
  comparación automática entre modelos está fuera de alcance de la spec. El gate que la entrada
  describe —llamar al gateway, puntuar con la misma regla y salir distinto de 0— ya vive en
  `scripts/eval_gate.py` desde la 001 (R-13); se extiende en lugar de duplicarlo.
- **Alternatives considered**: mover el gate a `eval/correr_eval.py` (mezcla comparador y gate,
  y obliga a cargar `openpyxl` en el gate); dos implementaciones de la regla de puntaje.

## O-15 · Modelos faltantes en modo real

- **Decision**: en `ollama` y `record`, el gateway consulta `GET /api/tags` de Ollama al arrancar y
  en `/health`; si falta `gemma4:12b` o `glm-ocr`, `/health` responde 503 con
  `{"status": "error", "mode", "missing_models": [...]}` y el log dice en español qué modelo falta
  y cómo instalarlo. El healthcheck de compose falla y `make up` lo reporta. Si Ollama no
  responde a mitad de una llamada, se mantiene el 502 `upstream_failure` existente; nunca se cae a
  fixtures.
- **Rationale**: FR-084: fallar visible, sin respuestas grabadas en silencio.
- **Alternatives considered**: verificar solo en la primera llamada (el error aparece a mitad de la
  demo).
