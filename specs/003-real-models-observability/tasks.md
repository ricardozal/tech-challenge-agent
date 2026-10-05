---

description: "Task list for feature 003-real-models-observability"
---

# Tasks: Modelos reales y observabilidad

**Input**: Design documents from `specs/003-real-models-observability/`

**Prerequisites**: [plan.md](./plan.md), [spec.md](./spec.md), [research.md](./research.md),
[data-model.md](./data-model.md), [contracts/](./contracts/), [quickstart.md](./quickstart.md)

**Tests**: incluidos. La constitución exige al menos un test por FR (Principio VII) y tests de
fronteras y demos (Principio IX). Dentro de cada historia, los tests se escriben primero y deben
fallar antes de implementar. Los tests que necesitan Ollama llevan `@pytest.mark.ollama` y no
corren en el pytest por defecto.

**Organization**: tareas agrupadas por historia (US1 = P1 modo real y grabación, US2 = P2 trazas,
US3 = P3 calidad medida).

## Format: `[ID] [P?] [Story] Description`

- **[P]**: se puede hacer en paralelo (otro archivo, sin dependencias pendientes)
- **[Story]**: historia a la que pertenece (US1, US2, US3)

## Path Conventions

- `services/<servicio>/src/<paquete>/` y `services/<servicio>/tests/` — servicios Python del workspace `uv`
- `packages/contracts/src/contracts/` — contratos y funciones puras compartidas
- `scripts/`, `tests/architecture/`, `tests/e2e/`, `tests/eval/`, `tests/ollama/` en la raíz

## Convenciones para todas las tareas

- Código e identificadores en inglés; salidas de comandos, mensajes de error y logs para personas
  en español (Principio X).
- `LLM_MODE` solo se lee en `services/llm_gateway/src/llm_gateway/config.py` (Principio V); ningún
  otro servicio ni script de servicio lo conoce. Los scripts consultan el modo con
  `GET {LLM_URL}/health`.
- Ningún servicio importa código de otro (Principio III); lo compartido va en `packages/contracts`.
- Todo `input.value`, `output.value` y mensaje de modelo en spans manuales pasa por
  `contracts.redaction.redact` (O-09, FR-093).
- Tests que cubren un FR llevan `@pytest.mark.req("FR-xxx")`; los que necesitan el stack levantado
  usan la fixture `compose_up` de `tests/conftest.py`; los que necesitan Ollama llevan además
  `@pytest.mark.ollama`.
- Nombres y atributos de spans exactamente como en [contracts/tracing.md](./contracts/tracing.md);
  formato de fixture y endpoints como en [contracts/llm-gateway-changes.md](./contracts/llm-gateway-changes.md);
  salidas y códigos de salida de comandos como en [contracts/commands.md](./contracts/commands.md).

---

## Phase 1: Setup (Shared Infrastructure)

**Purpose**: decisiones registradas, dependencias, marcador de pytest y trazabilidad de la spec 003.

- [X] T001 Add section "Feature 003 · Modelos reales y observabilidad" to `DECISIONS.md` (after "Feature 002 · Web de demo", before "Calidad del LLM") with a link to `specs/003-real-models-observability/research.md`, a sentence stating that `phoenix` is the 7th container of the reference topology registered here before adding it (Principle I), and one table row per decision O-01…O-15 (Id · Decisión · Motivo) summarizing research.md, including the accepted consequence of O-13 (a datum given outside its stage is not extracted in that turn)
- [X] T002 [P] Add dependencies: `arize-phoenix-otel`, `opentelemetry-instrumentation-httpx`, `opentelemetry-instrumentation-fastapi`, `openinference-semantic-conventions` to `services/llm_gateway/pyproject.toml` and `services/doc_intel/pyproject.toml`; `arize-phoenix-otel`, `openinference-instrumentation-langchain`, `opentelemetry-instrumentation-httpx`, `openinference-semantic-conventions` to `services/agent/pyproject.toml`; only `opentelemetry-instrumentation-httpx` and `opentelemetry-instrumentation-fastapi` to `services/actions_api/pyproject.toml` (no SDK, no exporter, O-06); add `arize-phoenix-client` to the `dev` group of the root `pyproject.toml`; run `uv lock` and `uv sync` to update `uv.lock`
- [X] T003 [P] In root `pyproject.toml` `[tool.pytest.ini_options]`: add marker `"ollama: needs Ollama with gemma4:12b and glm-ocr (LLM_MODE=ollama)"` change `addopts` to `"--import-mode=importlib -m 'not ollama'"` and `testpaths` to `["services", "tests", "packages/contracts/tests"]`; add `test-ollama` target to `Makefile` (`uv run pytest -m ollama tests services`) with a `## Real-model tests (needs LLM_MODE=ollama make up)` comment and add it to `.PHONY`
- [X] T004 [P] Add `fixtures/llm/_recording/` to `.gitignore` (section "Datos locales de los servicios")
- [X] T005 [P] Add `ROOT / "specs" / "003-real-models-observability" / "spec.md"` to `SPECS` in `scripts/traceability.py` so FR-076…FR-098 are checked, and add `*sorted((ROOT / "packages").glob("*/tests"))` to `TEST_DIRS`
- [X] T006 [P] Create `services/llm_gateway/tests/conftest.py` with the shared fixture `stub_ollama` (the Ollama client is a dependency, not the unit under test): a factory returning an object with `chat_json`, `chat_text` and `ocr` that return `Completion(text, prompt_tokens=812, completion_tokens=64)` from a per-test queue of texts (so a test can make the first extraction attempt invalid), and `list_models()` returning a configurable list (default `["gemma4:12b", "glm-ocr"]`, or raising `ConnectionError`); used by the recording, health and tracing tests of US1 and US2

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: esquemas de mensaje por etapa (v4), llave de fixture versionada y `/health`
extendido, lectura del formato v2 de respuesta grabada y primera corrida de `make eval` con v4.
Bloquea US1 (las grabaciones deben hacerse con el esquema y la llave definitivos y ya validados),
US2 (los spans de reproducción leen el formato v2) y US3 (el gate mide el esquema v4).

**⚠️ CRITICAL**: no grabar fixtures (US1) antes de que `make eval` pase con el esquema v4 (Principio
VIII): si el gate obliga a cambiar los campos por etapa, cambia la llave y habría que grabar de nuevo.

- [X] T007 Write failing tests in `services/llm_gateway/tests/test_stage_schemas.py`: `Schemas.version == 4`; `Schemas.stage_fields("eligibility") == ["nombre_completo", "auto_a_nombre_propio", "adeudos_vehiculo", "segunda_llave", "auto_marca", "auto_modelo", "auto_anio"]` and the other three stages exactly as in the table of research.md O-13; `Schemas.schema("mensaje", stage="simulation")` has `campos.properties` and `campos.required` equal to `["opcion_elegida", "monto_solicitado", "plazo_meses"]` in full-schema order, `additionalProperties: false`, and `intencion` with the full enum (including `pedir_humano`, `cancelar`, `tema_sensible`); `schema("mensaje", stage=None)` is the full schema; `schema("documento", stage="profiling")` ignores the stage; loading an `esquemas.json` whose `etapas` lists an unknown field or a key that is not a `Stage` value raises `ValueError`; `LlmService.extract` in `fake` with `stage="simulation"` returns `data["campos"]` with only the three simulation keys; and the prompt from `prompts.extract_messages` for stage `eligibility` lists `auto_marca` but not `ingreso_monto`. Update `test_schema_is_version_3_with_sensitive_topic_and_personal_data` in `services/llm_gateway/tests/test_modes.py` to version 4
- [X] T008 Bump `eval/esquemas.json` to `"version": 4` and add the top-level `"etapas"` map with the four stage lists of research.md O-13 (keys `eligibility`, `profiling`, `simulation`, `documents`); `mensaje`, `documento` and `puntaje` unchanged
- [X] T009 Implement stage schemas in `services/llm_gateway/src/llm_gateway/schemas.py`: load and validate `etapas` (every field exists in `mensaje.schema.properties.campos.properties`, every key is a `contracts.common.Stage` value, else `ValueError`); `stage_fields(stage)`; `schema(name, stage=None)` returning the reduced schema (filter `campos.properties` and `campos.required` to the stage list in full-schema order) for `mensaje` with a stage and the full schema otherwise; per-(name, stage) cached `Draft202012Validator`; `field_names`, `errors`, `complete` and `fallback` take `stage=None` and use the reduced field list. Pass `req.stage` through in `services/llm_gateway/src/llm_gateway/modes.py` (`extract`, `_extract_with_model`) so the prompt in `prompts.extract_messages` and the Ollama `format` use the reduced schema
- [X] T010 Write failing tests in `packages/contracts/tests/test_fixture_key.py` (create the directory; it is collected by `testpaths` and `TEST_DIRS` from T003 and T005): `fixture_key("extract", "mensaje", inputs, schema_version=4)` differs from the same call with `schema_version=3`; it changes when `contracts.llm.PROMPT_VERSION` changes (monkeypatch); it ignores case and repeated spaces in `inputs` as today
- [X] T011 Add `PROMPT_VERSION = 2` to `packages/contracts/src/contracts/llm.py` (comment: bump when `llm_gateway/prompts.py` instructions change) and change `fixture_key(task, schema_name, inputs, schema_version)` to hash `{"task", "schema_name", "schema_version", "prompt_version", "inputs"}`; update every caller: `services/llm_gateway/src/llm_gateway/modes.py` (pass `self.schemas.version`), `scripts/seed_fixtures.py` (read `version` from `eval/esquemas.json`) and `services/llm_gateway/tests/test_modes.py` (`seed` helper). In the same change, make `_load` in `services/llm_gateway/src/llm_gateway/modes.py` return the whole fixture record (not only `response`) and read a missing `origin` as `seeded` (fixture v2 format of data-model.md, read side), with a test in `services/llm_gateway/tests/test_modes.py` that a fixture without `origin` is reported as `seeded` and one with `"origin": "recorded"` exposes its `latency_ms`, `prompt_tokens` and `completion_tokens`
- [X] T012 Extend `GET /health` in `services/llm_gateway/src/llm_gateway/main.py` to return `{"status": "ok", "mode", "schema_version", "prompt_version", "model", "ocr_model"}` per contracts/llm-gateway-changes.md, with a test in `services/llm_gateway/tests/test_modes.py`
- [X] T013 Regenerate the seeded fixtures with the new key: delete the files under `fixtures/llm/extract/` and `fixtures/llm/ocr/`, run `make seed-fixtures`, and confirm with `make up && make test-e2e` that the 4 demos still pass in `LLM_MODE=fake` (all scenario extractions fit their stage schema; verified in research.md O-13)
- [X] T014 Run the quality gate with schema v4 on the GPU machine before any recording: `make down && LLM_MODE=ollama make up && make eval` with the current `scripts/eval_gate.py` (it already sends each case's stage, so the gateway applies the stage schema); it must exit 0 (≥ 85% fields, 100% valid JSON). If it fails, stop: do not lower the threshold; adjust the O-13 field sets in `eval/esquemas.json` and `research.md` (bump `version` if the sets change), redo T013 and this task. Keep the resulting `eval/resultados/gate-*.json` path for the `DECISIONS.md` row of T053

**Checkpoint**: esquema v4 y llave versionada en uso y validados por `make eval`; los demos siguen
verdes en `fake`.

---

## Phase 3: User Story 1 - Modo real y grabación de respuestas auténticas (Priority: P1) 🎯 MVP

**Goal**: correr todo con `gemma4:12b` y `glm-ocr` cambiando solo `LLM_MODE`; grabar los 4 demos
con promoción por demo; reproducir sin GPU solo con respuestas auténticas.

**Independent Test**: `LLM_MODE=ollama make up && make demo-all` termina los 5 guiones;
`LLM_MODE=record make up && make record` sale con 0; `make up && make fixtures-status` sale con 0
y `make demo-all REPEAT=10` es idéntico (quickstart pasos 2–4).

### Tests for User Story 1 ⚠️

- [X] T015 [P] [US1] Add `@pytest.mark.req("FR-076")` to `test_only_the_gateway_knows_the_llm_mode_and_ollama` in `tests/architecture/test_compose.py` and add a test (also `FR-076`) asserting that no file under `services/*/src`, `scripts/` or `web/src` other than `services/llm_gateway/src/llm_gateway/config.py` reads the `LLM_MODE` environment variable (grep for `"LLM_MODE"` in `os.environ`/`getenv` calls)
- [X] T016 [P] [US1] Write failing tests in `services/llm_gateway/tests/test_recording.py` using the `stub_ollama` fixture of `services/llm_gateway/tests/conftest.py`: in `record`, `extract`, `ocr` and `reply` write to `<record_dir>/<task>/<key>.json` and never to `<fixtures_dir>/<task>/` (FR-080); the file has `origin: "recorded"`, `model`, `recorded_at`, `schema_version: 4`, `prompt_version`, `latency_ms` (number), `prompt_tokens: 812`, `completion_tokens: 64`; when the first attempt is invalid and the second valid, `latency_ms` and the token counts are those of the second (valid) attempt only; an extraction whose two attempts are invalid writes nothing; `fake` never reads `<fixtures_dir>/_recording/`. Mark with `@pytest.mark.req("FR-080")`
- [X] T017 [P] [US1] Write failing tests in `services/llm_gateway/tests/test_health_and_usage.py` with `TestClient(create_app(settings, service))` and the `stub_ollama` fixture: in `ollama`/`record` with `list_models()` returning `["gemma4:12b"]`, `GET /health` is 503 with `{"status": "error", "missing_models": ["glm-ocr"], "message": "Falta el modelo glm-ocr en Ollama. Instálalo con: ollama pull glm-ocr"}` and with `list_models()` raising `ConnectionError` it is 503 naming both models; with both installed it is 200; in `fake` `list_models` is never called; no request falls back to fixtures when Ollama fails (`/v1/extract` answers 502 `upstream_failure`) (`FR-084`). `GET /v1/fixtures/usage` after one `recorded`, one `seeded` and one missing extraction in `fake` returns `counts == {"recorded": 1, "seeded": 1, "missing": 1}` and the keys under `by_task.extract`; `DELETE /v1/fixtures/usage` answers 204 and resets to zero; in `ollama` counts stay zero (`FR-083`)
- [X] T018 [P] [US1] Write failing tests in `tests/scripts/test_record_fixtures.py` (create `tests/scripts/`) for the pure helpers of `scripts/record_fixtures.py` on `tmp_path`: `promote(recording_dir, fixtures_dir)` moves every `<task>/<key>.json` into `fixtures_dir/<task>/`, replacing a file with the same key, and returns the count; `discard(recording_dir)` empties it and leaves `fixtures_dir` byte-identical; `clear(recording_dir)` before each scenario; `run_all` with a fake `play` that raises `DemoFailure("paso 14: …")` for one scenario promotes the others, discards the failing one and returns exit code 1 with the step in the report (`FR-081`)
- [X] T019 [P] [US1] Write failing e2e test `tests/e2e/test_fixtures_status.py` (`compose_up`, gateway in `fake`): `DELETE {LLM_URL}/v1/fixtures/usage`, play the 5 scenarios with `scripts.run_demo.play`, then `GET /v1/fixtures/usage` has `counts.seeded == 0` and `counts.missing == 0` and `counts.recorded > 0` (`FR-082`, `FR-083`, SC-019); and `uv run python scripts/fixtures_status.py` exits 0. Skip with a clear reason if the gateway is not in `fake`. This test is expected to fail until T031 commits the recorded fixtures
- [X] T020 [P] [US1] Write `tests/ollama/test_real_mode.py` (`@pytest.mark.ollama`, `compose_up`, skip unless `/health` mode is `ollama`): `/health` reports `model == "gemma4:12b"` and `ocr_model == "glm-ocr"`, and `POST {LLM_URL}/v1/ocr` with `fixtures/documents/laura_identification.png` returns non-empty text with `model == "glm-ocr"` and `fixture_hit is False` (`FR-077`); each of the 5 scenarios in `fixtures/scenarios/` passes with `scripts.run_demo.play` (`FR-078`); on a new case in eligibility, after the agent asks for the car, the message "es un Nissan Versa 2020, lo compré de agencia" (not in any scenario, so there is no fixture for it) yields an extraction whose `intencion` is not `otro` and a turn whose `tool_calls` include `update_declared_data` accepted, and the case then has make `Nissan`, model `Versa` and year 2020 (`FR-079`)

### Implementation for User Story 1

- [X] T021 [US1] Add `record_dir: Path` to `Settings` in `services/llm_gateway/src/llm_gateway/config.py` from `FIXTURES_RECORD_DIR` (default `<fixtures_dir>/_recording`) and pass it to `LlmService`; add `FIXTURES_RECORD_DIR: /app/fixtures/llm/_recording` to `llm_gateway` in `docker-compose.yml`
- [X] T022 [US1] In `services/llm_gateway/src/llm_gateway/modes.py`: `_save` writes to `record_dir` with the fixture v2 fields of data-model.md ("`origin`: `recorded` | `seeded`", "`latency_ms` … solo `recorded`: duración de la llamada a Ollama", "`prompt_tokens`, `completion_tokens` … solo `recorded`: los que reporta Ollama", plus `schema_version`, `prompt_version`, `model`, `recorded_at`), measuring `latency_ms` around the Ollama call of the valid attempt only, with that attempt's token counts (data-model.md: the metrics describe the answer that is replayed) (the reading side of the format is already done in T011); save only validated outputs (already true for extraction; keep it for OCR and reply)
- [X] T023 [US1] Add fixture usage tracking to `LlmService` in `services/llm_gateway/src/llm_gateway/modes.py` (`usage()` and `reset_usage()`; in `fake`, every `extract`/`ocr`/`reply` records `recorded|seeded|missing` and its key per task, keys unique and in order of use; nothing is counted in other modes) and expose `GET /v1/fixtures/usage` and `DELETE /v1/fixtures/usage` (204) in `services/llm_gateway/src/llm_gateway/main.py` with the response of contracts/llm-gateway-changes.md
- [X] T024 [US1] Add `list_models()` to `services/llm_gateway/src/llm_gateway/ollama_client.py` (names from `Client.list()`, adding the bare name for `:latest` tags) and, in `services/llm_gateway/src/llm_gateway/main.py`, check `model` and `ocr_model` at startup and on every `/health` in `ollama`/`record`: 503 `{"status": "error", "mode", "missing_models", "message"}` with the Spanish message of the contract, and log the same message as JSON with `get_logger()`; `fake` never checks (O-15)
- [X] T025 [US1] Mark seeded fixtures in `scripts/seed_fixtures.py`: `write` adds `"origin": "seeded"`, `"schema_version"` and `"prompt_version"` (model stays `seeded-from-scenario`, no latency or tokens), and skips a key whose existing file has `"origin": "recorded"` (seeding never overwrites an authentic answer); re-run `make seed-fixtures`
- [X] T026 [US1] Make the demo runner reusable in `scripts/run_demo.py`: keep `play(path, quiet)` and `DemoFailure` importable as `scripts.run_demo` (same try/except import pattern as `scripts/seed_fixtures.py`) and make every `DemoFailure` message start with `paso N` and the step (`say` text or `upload` file) so callers can report it
- [X] T027 [US1] Create `scripts/record_fixtures.py` (docstring with usage `make record [ONLY="happy_path …"]`): helpers `clear`, `promote`, `discard`, `run_all(scenarios, play)`; `main()` checks `GET {LLM_URL}/health` mode is `record` (else Spanish message and exit 2), then for each of the 5 scenarios in `fixtures/scenarios/` (or `ONLY`) clears `fixtures/llm/_recording/`, plays it quietly, promotes on success or discards on `DemoFailure`, and prints the table of contracts/commands.md (`OK  N respuestas grabadas → fixtures/llm` / `FALLA  paso …` + `se descartan N respuestas; las vigentes no cambian`) and `K de 5 guiones grabados`; exit 0/1/2 as in the contract
- [X] T028 [US1] Create `scripts/fixtures_status.py`: check `/health` mode is `fake` (else exit 2); for each scenario `DELETE /v1/fixtures/usage`, play it quietly, read `GET /v1/fixtures/usage`; print the table `guion · auténticas · sembradas · faltantes` with a total row; list fixture files under `fixtures/llm/<task>/` whose key no scenario used ("fixtures sin uso en los demos: N") and delete them when `--prune` (Makefile `PRUNE=1`); exit 0 if no seeded or missing, else 1 listing scenario and task
- [X] T029 [US1] Add `record` (`$(PY) scripts/record_fixtures.py $(if $(ONLY),--scenarios $(ONLY))`, comment `## Record the 4 demos with real models (needs LLM_MODE=record make up)`) and `fixtures-status` (`$(PY) scripts/fixtures_status.py $(if $(PRUNE),--prune)`, comment `## Which recorded answers the demos use (LLM_MODE=fake)`) to `Makefile` and `.PHONY`; update the top comment of `Makefile` to mention `LLM_MODE=ollama|record`
- [X] T030 [US1] Run the real-model checks on the GPU machine: `make down && LLM_MODE=ollama make up && make demo-all REPEAT=3` (the 5 scenarios pass in 3 of 3 consecutive runs, SC-018) and `uv run pytest -m ollama tests/ollama` (T020 green); if a scenario does not reach its outcome with the real model, stop and record the finding in `DECISIONS.md` before changing prompts (any prompt change bumps `PROMPT_VERSION` and requires US3's `make eval`)
- [X] T031 [US1] Record the authentic answers: `make down && LLM_MODE=record make up && make record` (exit 0), then `make down && make up && make fixtures-status PRUNE=1` (exit 0: 0 seeded, 0 missing) and `make demo-all REPEAT=10`; review `git diff --stat fixtures/llm` and keep the promoted files with `origin: "recorded"`; T019 and `tests/e2e/test_reproducibility.py` must now pass

**Checkpoint**: modo real verificado; `fixtures/llm/` con respuestas auténticas; los 4 demos se
reproducen sin GPU con 0 sembradas y 0 faltantes.

---

## Phase 4: User Story 2 - Una traza por turno en la consola de observabilidad (Priority: P2)

**Goal**: contenedor `phoenix`; cada turno del agente es una traza con etapas, tools y llamadas al
modelo con entrada, salida, latencia y tokens; el turno no depende de la consola.

**Independent Test**: `make up && make demo-happy-path`, abrir `http://localhost:6006`, filtrar por
el id del caso y ver una traza por turno con `turn` → nodos → `TOOL` → `LLM` (quickstart pasos 1
y 5); `uv run pytest tests/e2e/test_tracing.py tests/e2e/test_tracing_console_down.py services/agent/tests/test_tool_spans.py` en verde.

### Tests for User Story 2 ⚠️

- [X] T032 [P] [US2] Update `tests/architecture/test_compose.py`: rename `test_topology_is_the_feature_002_subset` to `test_topology_is_the_reference_topology` asserting the 7 services `{"postgres", "actions_api", "agent", "llm_gateway", "doc_intel", "web", "phoenix"}`; add `@pytest.mark.req("FR-091")` tests: `phoenix` uses image `arizephoenix/phoenix:version-20.19.0` (not `latest`), publishes `6006:6006` and mounts `phoenix_data`; exactly `agent`, `llm_gateway` and `doc_intel` define `PHOENIX_COLLECTOR_ENDPOINT: http://phoenix:6006`; no service lists `phoenix` in `depends_on` (`FR-092`)
- [X] T033 [P] [US2] Write failing tests in `services/llm_gateway/tests/test_tracing.py` with an SDK `TracerProvider` + `SimpleSpanProcessor(InMemorySpanExporter())` set for the test (the exporter is OTel's, not a mock of the unit): in `record` with the `stub_ollama` fixture, `extract` produces a `CHAIN` span `extract` with `metadata.task`, `metadata.mode`, `metadata.schema_name`, `metadata.stage`, `metadata.schema_version`, `metadata.fixture_key` and a child `LLM` span with `llm.provider == "ollama"`, `llm.model_name == "gemma4:12b"`, `llm.invocation_parameters` containing `"temperature": 0` and `"seed": 42`, `input.value`, `output.value`, `llm.token_count.prompt == 812`, `.completion == 64`, `.total == 876`, `metadata.attempt == 1` (`FR-089`); a first invalid attempt yields two `LLM` children, the first with status `ERROR` and the schema error (`FR-090`); in `fake` with a fixture file written by the test in the v2 format (`"origin": "recorded"`, `latency_ms`, `prompt_tokens`, `completion_tokens`; read side from T011) the single `LLM` span has `metadata.replay == true`, `metadata.fixture_origin == "recorded"`, `metadata.recorded_latency_ms` and the recorded token counts (`FR-089`); an OCR span's input has the sha256 and never base64 image data; `input.value`/`output.value` of a text with a CURP, a phone and the client name contain `[REDACTED_CURP]`, `[REDACTED_PHONE]`, `[REDACTED_NAME]` (`FR-093`)
- [X] T034 [P] [US2] Write failing e2e test `tests/e2e/test_tracing.py` (`compose_up`, plus skip if `http://localhost:6006` does not answer) using `phoenix.client.Client(base_url="http://localhost:6006")` and the reading procedure of contracts/tracing.md (spans `turn` by `session.id`, then all spans by `trace_ids`, polling up to 10 s): parametrized over the 5 scenarios of `fixtures/scenarios/`, play each one and assert the number of `turn` spans of its case equals the number of agent turns (start + `say`/`upload` steps) and each has exactly one trace (`FR-085`, SC-020); the detailed checks below run on `happy_path`: each `turn` has `session.id == case_id` and `metadata.message_id`/`metadata.kind` (`FR-086`); each message trace contains the `CHAIN` node spans `interpret` and `respond` in start-time order (`FR-087`); `TOOL` spans have `tool.name`, `input.value` and `output.value` with `outcome` (`FR-088`); a document turn's trace contains `submit_document` → `read_document` → `ocr`/`extract` `LLM` spans, all with the same trace id (`FR-085`); `LLM` spans have model, `input.value`, `output.value` and token counts (`FR-089`); no `input.value` of any span contains the client's CURP from `fixtures/documents/specs.yaml` (`FR-093`); and a concurrency test that plays two scenarios at the same time in two threads (same approach as `tests/e2e/test_concurrency.py`) and asserts their traces are disjoint: every span of a trace belongs to the trace of its own case's `turn`, and no trace id appears under both cases' `turn` spans (edge case "Varios turnos simultáneos", `FR-085`)
- [X] T035 [P] [US2] Write failing test `services/agent/tests/test_tool_spans.py` (`stack` fixture of `services/agent/tests/conftest.py`, real `actions_api` in `LLM_MODE=fake`; SDK `TracerProvider` with `SimpleSpanProcessor(InMemorySpanExporter())` set for the test): create a case (it starts in `eligibility`), build `Deps` with the real `ActionsClient`/`LlmClient` and call `Deps.call_tool(state, "select_option", {"option_id": "opt-1"})`, which `actions_api` rejects with `forbidden` (permissions are checked before the handler, R-05) because `select_option` is only allowed in `simulation`; assert one `TOOL` span with `tool.name == "select_option"`, status `ERROR` with description `forbidden`, `output.value` containing `"outcome": "rejected"` and `"rejection_code": "forbidden"`, and `input.value` with the tool input (`FR-090`, `FR-088`); and that a call with a client message containing a CURP has `[REDACTED_CURP]` in `input.value` (`FR-093`); and a test of the `turn` span on failure: build the agent in-process with `TestClient(create_app(dataclasses.replace(Settings.from_env(), llm_url="http://127.0.0.1:9")))` (closed port, same pattern as `services/agent/tests/test_cors.py`), create a case and send a message; the response is 502 `upstream_failure` and the exporter has one `turn` span with status `ERROR` and `session.id` = case id (edge case "Modelo lento": an upstream failure or timeout ends the turn with a clear error recorded in the trace, `FR-090`)
- [X] T036 [P] [US2] Write failing e2e test `tests/e2e/test_tracing_console_down.py` (`compose_up`, `@pytest.mark.req("FR-092")`): run `docker compose stop phoenix` with `subprocess`, play the 5 scenarios with `scripts.run_demo.play` and assert they pass with the same final `status` as `expected`, then `docker compose start phoenix` in a `finally`

### Implementation for User Story 2

- [X] T037 [US2] Move `redact` and its regexes from `services/llm_gateway/src/llm_gateway/redaction.py` to `packages/contracts/src/contracts/redaction.py` (same rules: CURP, RFC, phone, known names); keep `get_logger`/`log_call` in the gateway and import `redact` from `contracts.redaction` in `services/llm_gateway/src/llm_gateway/modes.py`; move `test_redaction_removes_curp_rfc_phones_and_known_names` to `packages/contracts/tests/test_redaction.py`; `make test-arch` (import-linter) stays green
- [X] T038 [US2] Add the `phoenix` service to `docker-compose.yml` as in contracts/commands.md (image `arizephoenix/phoenix:version-20.19.0`, `PHOENIX_WORKING_DIR: /mnt/data`, volume `phoenix_data:/mnt/data`, port `6006:6006`, healthcheck to `http://localhost:6006/healthz` only if the image has an interpreter to run it — check with `docker run --rm --entrypoint python arizephoenix/phoenix:version-20.19.0 -c 1`; otherwise no healthcheck), declare volume `phoenix_data`, add `PHOENIX_COLLECTOR_ENDPOINT: http://phoenix:6006` to `agent`, `llm_gateway` and `doc_intel` without `depends_on: phoenix`, and change the header comment to "Feature 003: the 7 reference containers"
- [X] T039 [P] [US2] Create `services/llm_gateway/src/llm_gateway/telemetry.py` with `setup(app)`: if `PHOENIX_COLLECTOR_ENDPOINT` is unset, do nothing; else `phoenix.otel.register(project_name="tech-challenge-agent", batch=True, auto_instrument=True)`, `HTTPXClientInstrumentor().instrument()` and `FastAPIInstrumentor.instrument_app(app, excluded_urls="health")`; call it from `create_app` in `services/llm_gateway/src/llm_gateway/main.py`
- [X] T040 [P] [US2] Create `services/doc_intel/src/doc_intel/telemetry.py` (same as T039) and call it from `create_app` in `services/doc_intel/src/doc_intel/main.py`
- [X] T041 [P] [US2] Create `services/agent/src/agent/telemetry.py` with `setup()`: if `PHOENIX_COLLECTOR_ENDPOINT` is set, `tp = phoenix.otel.register(project_name="tech-challenge-agent", batch=True, auto_instrument=False)`, `LangChainInstrumentor().instrument(tracer_provider=tp, config=TraceConfig(hide_inputs=True, hide_outputs=True))` and `HTTPXClientInstrumentor().instrument()`; do NOT instrument the agent's FastAPI app (O-03); expose `tracer()` returning `trace.get_tracer("agent")`; call `setup()` from `create_app` in `services/agent/src/agent/main.py`
- [X] T042 [P] [US2] Instrument `services/actions_api/src/actions_api/main.py` for propagation only: `FastAPIInstrumentor.instrument_app(app, excluded_urls="health")` and `HTTPXClientInstrumentor().instrument()` with no tracer provider, no exporter and no `PHOENIX_COLLECTOR_ENDPOINT` (O-06); add a comment explaining that the no-op provider keeps the incoming `traceparent` for the `doc_intel` call
- [X] T043 [US2] Create `services/llm_gateway/src/llm_gateway/tracing.py` with helpers using `openinference.semconv.trace` constants: `task_span(task, mode, **metadata)` (context manager, `CHAIN`) and `llm_span(model, messages, invocation_parameters, attempt)` returning an object to set `output`, token counts, `replay`, `fixture_origin`, `recorded_latency_ms` and `ERROR` status; all text through `contracts.redaction.redact` with the known names of the call; wire them into `extract` (one `LLM` span per attempt in `_extract_with_model`), `ocr` (input = `{"sha256", "mime_type"}`) and `reply` in `services/llm_gateway/src/llm_gateway/modes.py`, and in `fake` one `LLM` span per task with the fixture's origin, recorded latency and tokens; set `ERROR` on the task span for `FixtureMissing`, `InvalidModelOutput` and upstream errors
- [X] T044 [US2] Add the `read_document` `CHAIN` span in `services/doc_intel/src/doc_intel/main.py` (input `{"requested_type", "mime_type", "sha256"}`, output `{"detected_type", "fields": {name: {"confidence"}}}` without values, `ERROR` on `UpstreamFailure`) around the OCR + extraction + confidence flow
- [X] T045 [US2] Add the root `turn` span (`AGENT`) in `run_turn` of `services/agent/src/agent/main.py` around `get_case` + `graph.ainvoke`, with `session.id` = case id (`openinference.instrumentation.using_session` plus the attribute on the span), `metadata` `case_id`, `message_id`, `kind`, `stage_before`, `status_before`, `stage_after`, `status_after`, `version_after`, `input.value` (redacted client text, or `documento: <requested_type>`) and `output.value` (redacted reply), `ERROR` status on exceptions; a replay resolved in `guarded_turn` by idempotency must not open a span
- [X] T046 [US2] Add a `TOOL` span in `Deps.call_tool` of `services/agent/src/agent/graph.py` per actions call (including the `version_conflict` retry as a sibling span): `tool.name`, `metadata` `actor` (`client` when `on_behalf_of`, else `agent`), `idempotency_key`, `expected_version`, `input.value` = redacted JSON of `tool_input`, `output.value` = `{"outcome", "rejection_code", "stage", "status", "version"}`, status `ERROR` with the rejection code when `outcome == "rejected"`
- [X] T047 [US2] Rebuild and verify: `make down && make up` (7 containers), `make test-arch`, `uv run pytest services/llm_gateway/tests/test_tracing.py`, `make test-e2e` (T034 and T036 green), then open `http://localhost:6006` after `make demo-happy-path` and check the tree of contracts/tracing.md by hand; confirm with `cd web && npx playwright test` that the response-time check of SC-012 still passes with tracing on

**Checkpoint**: trazas por turno visibles en Phoenix; los demos pasan con la consola apagada.

---

## Phase 5: User Story 3 - Calidad de extracción medida con un comando (Priority: P3)

**Goal**: `make eval` mide mensajes y documentos de `eval/` con el modelo real y el esquema por
etapa, reporta por caso, por tipo y en total, guarda la corrida y falla bajo el umbral o fuera de
modo real.

**Independent Test**: `LLM_MODE=ollama make up && make eval` sale con 0 y escribe
`eval/resultados/gate-*.json` con `by_type`; con el stack en `fake`, `make eval` sale con 2
(quickstart paso 6).

### Tests for User Story 3 ⚠️

- [X] T048 [P] [US3] Write failing tests in `tests/eval/test_eval_gate.py` (create `tests/eval/`) importing `scripts.eval_gate` pure functions: `score` follows the rule of `eval/esquemas.json` → `puntaje` (n = 1 + expected fields; `true` vs `"true"` is wrong; `9500` vs `"9500"` is right; `"Volkswagen"` vs `"VOLKSWAGEN."` is right; expected `null` only matches `null`; each extra non-null field subtracts 1, minimum 0; a field missing from the reduced schema counts as `null`) (`FR-095`); `summarize(rows, health)` gives `passed is True` at exactly 85.0% fields with 100% valid, `False` at 84.9% or with one invalid JSON (`FR-096`); the summary has `model`, `schema_version`, `prompt_version`, `mode`, `by_type` with `mensaje` and `documento` `{correct, fields, pct}`, `median_seconds` per type and `failed_cases` (`FR-097`); `request_for` sends the case's stage (`transversal` → `null`) for messages and the cleaned `eval/ocr_D0x.txt` text for documents (`FR-094`)
- [X] T049 [P] [US3] Add to `tests/eval/test_eval_gate.py` an e2e test (`compose_up`, `@pytest.mark.req("FR-098")`, skip unless gateway mode is `fake`) that runs `uv run python scripts/eval_gate.py` with `subprocess` and asserts exit code 2, the Spanish message that the measurement requires the real model, and that no new `eval/resultados/gate-*.json` was written
- [X] T050 [P] [US3] Add to `tests/eval/test_eval_gate.py` a test `@pytest.mark.ollama` with `@pytest.mark.req("FR-094")` and `@pytest.mark.req("FR-096")` (skip unless mode is `ollama`) that runs `scripts/eval_gate.py` over all 37 cases, asserts exit code 0, `summary.passed is True`, `fields_pct >= 85`, `valid_json_pct == 100`, `cases == 37` and `schema_version == 4` in the newest `eval/resultados/gate-*.json` (SC-023)

### Implementation for User Story 3

- [X] T051 [US3] Refactor `scripts/eval_gate.py` (keep it as `make eval`, R-13/O-14; do not touch `eval/correr_eval.py`): make it importable as `scripts.eval_gate`; extract pure `score`, `request_for` and `summarize(rows, health)`; read `model` and `prompt_version` from `/health`; add `by_type`, `median_seconds` and `failed_cases` to `summary` (data-model.md "Corrida de medición"); print the per-type line, the model/schema/mode/median line and the failed cases as in contracts/commands.md; exit 2 with "El gateway está en LLM_MODE=fake; la medición requiere el modelo real (LLM_MODE=ollama make up)." when mode is `fake` or the gateway does not answer, without writing a result file; remove `--allow-fake`; keep exit 1 when not passing
- [X] T052 [US3] Update the `eval` target comment in `Makefile` (`## LLM quality gate: ≥85% fields and 100% valid JSON (needs LLM_MODE=ollama make up)`) and the module docstring of `scripts/eval_gate.py` (stage schemas, exit codes 0/1/2)
- [X] T053 [US3] Run the refactored gate on the GPU machine (the first v4 run in T014 already proved the threshold; this one produces the final summary with `by_type`, `median_seconds` and `failed_cases`): `make down && LLM_MODE=ollama make up && make eval` (exit 0) and `uv run pytest -m ollama tests/eval`; add a row to "Calidad del LLM (`make eval`, Principio VIII)" in `DECISIONS.md` with date, `gemma4:12b` params, schema v4 (por etapa), 37 cases, fields correct/total and %, per-type %, valid JSON %, median seconds per message before (12.8 s) and after, result and the gate file path. If it does not pass, stop: do not lower the threshold; revisit O-13 (field sets or rules) with a new `make eval`

**Checkpoint**: gate verde con esquema v4 y registrado; las tres historias funcionan por separado.

---

## Phase 6: Polish & Cross-Cutting Concerns

- [X] T054 [P] Update `README.md`: modes (`LLM_MODE=fake|ollama|record`), Ollama prerequisites (`ollama pull gemma4:12b`, `ollama pull glm-ocr`), `make record`, `make fixtures-status`, `make eval`, `make test-ollama`, the Phoenix console at `http://localhost:6006` and how to find a case's traces (sessions view, `session.id`); 7 containers
- [X] T055 [P] Add the implementation adjustments found during US1–US3 (if any) to an "Ajustes durante la implementación" table under the Feature 003 section of `DECISIONS.md`, same format as features 001 and 002
- [X] T056 Run `make traceability` and confirm `TRACEABILITY.md` lists FR-076…FR-098 each with at least one test (no pending FR)
- [X] T057 Full regression in `LLM_MODE=fake`: `make up && make test && make test-arch && make test-e2e && cd web && npx playwright test`; then run `quickstart.md` steps 1, 4, 5 and 7 and, on the GPU machine, steps 2, 3 and 6

---

## Dependencies & Execution Order

### Phase Dependencies

- **Setup (Phase 1)**: sin dependencias.
- **Foundational (Phase 2)**: depende de Setup. Bloquea US1, US2 y US3. T014 (primer `make eval`
  con v4) requiere la máquina con GPU y va antes de cualquier grabación.
- **US1 (Phase 3)**: depende de Foundational. T030–T031 requieren la máquina con GPU.
- **US2 (Phase 4)**: depende de Setup (dependencias, `stub_ollama`) y de Foundational (formato v2
  de respuesta grabada, T011). No depende de US1: puede hacerse en paralelo. Hasta que US1 grabe,
  los spans `LLM` en `fake` muestran `fixture_origin=seeded`.
- **US3 (Phase 5)**: depende de Foundational (esquema v4 y `/health` con modelo). No depende de US1
  ni de US2. T053 requiere la máquina con GPU.
- **Polish (Phase 6)**: después de las historias que se quieran entregar.

### Within Each User Story

- Tests primero (deben fallar), luego implementación, luego la verificación con el stack.
- US1: T021 → T022 → T023; T024 independiente; T025, T026 → T027, T028 → T029 → T030 → T031.
- US2: T035 antes de T046; T037 antes de T043–T046 (usan `contracts.redaction`); T038 antes de T047; T039–T042 en
  paralelo; T043, T044, T045, T046 tocan archivos distintos.
- US3: T051 → T052 → T053.

### Parallel Opportunities

- Setup: T002–T006 en paralelo tras T001.
- Foundational: T007/T010 (tests) en paralelo; T008 → T009; T011 → T013 → T014.
- US1 tests T015–T020 en paralelo.
- US2 tests T032–T036 en paralelo; T039–T042 en paralelo.
- US3 tests T048–T050 en paralelo.
- Con dos personas: una hace Foundational + US1 + US3 (gateway, scripts, GPU) y otra US2 (telemetría).

---

## Parallel Example: User Story 1

```bash
Task: "FR-076 tests in tests/architecture/test_compose.py"
Task: "Recording tests in services/llm_gateway/tests/test_recording.py"
Task: "Health and usage tests in services/llm_gateway/tests/test_health_and_usage.py"
Task: "Promotion tests in tests/scripts/test_record_fixtures.py"
Task: "E2E fixtures status in tests/e2e/test_fixtures_status.py"
Task: "Real-mode tests in tests/ollama/test_real_mode.py"
```

## Parallel Example: User Story 2

```bash
Task: "Create services/llm_gateway/src/llm_gateway/telemetry.py"
Task: "Create services/doc_intel/src/doc_intel/telemetry.py"
Task: "Create services/agent/src/agent/telemetry.py"
Task: "Propagation-only instrumentation in services/actions_api/src/actions_api/main.py"
```

## Parallel Example: User Story 3

```bash
Task: "Scoring and threshold tests in tests/eval/test_eval_gate.py"
Task: "Fake-mode exit-2 e2e test in tests/eval/test_eval_gate.py"
```

---

## Implementation Strategy

### MVP First (User Story 1 Only)

1. Phase 1 + Phase 2: dependencias, esquema v4, llave versionada, demos verdes en `fake` y `make eval`
   en verde con v4.
2. Phase 3: modo real verificado, `make record`, fixtures auténticos.
3. **STOP and VALIDATE**: quickstart pasos 2–4; `make fixtures-status` en 0.
4. Ya se puede mostrar la demo con el modelo real y reproducirla sin GPU con sus respuestas.

Nota: el esquema v4 cambia la extracción, así que antes de dar por cerrada cualquier entrega que
lo incluya hay que correr `make eval` (T014, Principio VIII); por eso esa corrida está en Foundational,
antes de grabar.

### Incremental Delivery

1. Setup + Foundational → base lista.
2. US1 → modo real y respuestas auténticas (MVP).
3. US2 → trazas por turno en Phoenix.
4. US3 → gate extendido y registrado.
5. Polish → README, decisiones, trazabilidad, regresión.

---

## Notes

- [P] = otro archivo y sin dependencias pendientes.
- No se agregan tools, permisos ni tablas; si una tarea parece requerirlo, detenerse y registrar
  la decisión en `DECISIONS.md` antes (Principio I).
- Cambiar instrucciones del modelo ⇒ subir `PROMPT_VERSION`, volver a grabar (`make record`) y
  correr `make eval`.
- Commit por tarea o grupo lógico, solo cuando se pida (memoria del proyecto).

---

## Phase 7: Convergence

- [X] T058 CRITICAL: In `guarded_turn` of `services/agent/src/agent/main.py`, answer `UpstreamError` with a fixed Spanish client message (e.g. "No pude responderte en este momento porque un servicio tardó demasiado o no respondió. Intenta de nuevo en unos segundos.") instead of `str(exc)`, keeping the technical detail only in the `turn` span status (already set) and in the agent log; add a test in `services/agent/tests/test_tool_spans.py` (closed-port gateway, as in the existing turn-failure test) asserting the 502 body is `{"code": "upstream_failure", "message": <that Spanish text>}` with no class names or service URLs per Constitution X, spec edge case "Modelo lento" (contradicts)
- [X] T059 In `scripts/fixtures_status.py`, when a scenario uses seeded or missing answers, report the scenario step (`paso N (say …/upload …)`) that produced each one — e.g. by resetting `/v1/fixtures/usage` and reading it per step while playing, or by mapping the step's request to its fixture key — so the exit-1 listing matches contracts/commands.md ("se listan por guion y paso"); cover it with a test in `tests/scripts/` per contracts/commands.md `make fixtures-status` (partial)
