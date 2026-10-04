---

description: "Task list for feature 002-demo-web"
---

# Tasks: Web de demo

**Input**: Design documents from `specs/002-demo-web/`

**Prerequisites**: [plan.md](./plan.md), [spec.md](./spec.md), [research.md](./research.md),
[data-model.md](./data-model.md), [contracts/](./contracts/), [quickstart.md](./quickstart.md)

**Tests**: incluidos. La constitución exige al menos un test por FR (Principio VII) y tests de
fronteras y demos (Principio IX). Los FR de la web se cubren con un solo archivo de Playwright
(`web/e2e/demo.spec.ts`, tags `@FR-xxx`) más pytest para CORS, el lector de política, el export de
escenarios y las fronteras. Dentro de cada historia, los tests se escriben primero y deben fallar
antes de implementar.

**Organization**: tareas agrupadas por historia (US1 = P1 chat del cliente, US2 = P2 consola del
asesor).

## Format: `[ID] [P?] [Story] Description`

- **[P]**: se puede hacer en paralelo (otro archivo, sin dependencias pendientes)
- **[Story]**: historia a la que pertenece (US1, US2)

## Path Conventions

- `web/` — proyecto Node independiente (no es miembro del workspace `uv`)
- `services/agent/`, `services/actions_api/` — solo CORS y un lector nuevo
- `scripts/`, `tests/architecture/`, `tests/web/` en la raíz

## Convenciones para todas las tareas

- Código e identificadores en inglés; todo texto visible en español (Principio X, W-12).
- React sin `dangerouslySetInnerHTML`; todo texto de cliente, documento, ticket o registro se
  renderiza como texto (FR-055).
- Sin router, sin estado global, sin librería de componentes ni cliente HTTP: `fetch` directo
  (W-01, W-02).
- La web nunca tiene umbrales de negocio; el de confianza se lee de `GET /policies/{version}`
  (W-11).
- El actor de la consola es `advisor` (valor del enum `Actor`); la UI lo muestra como "asesor".
- Toda escritura del chat va por `agent` con `Idempotency-Key`; toda escritura de la consola va por
  `POST {ACTIONS}/tools/{name}` con `X-Actor: advisor`, `context.expected_version` y
  `context.idempotency_key`. La llave se crea por intento y se reutiliza al reintentar (W-08,
  W-10).
- Los elementos que usa Playwright llevan los `data-testid` de
  [contracts/web-ui.md](./contracts/web-ui.md#selectores-estables-para-pruebas).
- Tests Python que cubren un FR llevan `@pytest.mark.req("FR-xxx")`; tests de Playwright llevan
  `{ tag: ['@FR-xxx', …] }`.

---

## Phase 1: Setup (Shared Infrastructure)

**Purpose**: proyecto `web/`, contenedor y comandos.

- [X] T001 Create `web/package.json` (name `web`, `"type": "module"`, scripts `dev` = `vite`, `build` = `tsc -b && vite build`, `preview` = `vite preview --port 8080`, `test:e2e` = `playwright test`; dependencies `react@^19`, `react-dom@^19`; devDependencies `typescript@^5`, `vite`, `@vitejs/plugin-react`, `tailwindcss@^4`, `@tailwindcss/vite`, `@types/react`, `@types/react-dom`, `@playwright/test`) and run `npm install` in `web/` to produce `web/package-lock.json`
- [X] T002 [P] Create `web/tsconfig.json` (strict, `jsx: react-jsx`, `moduleResolution: bundler`, `types: ["vite/client"]`, include `src` and `e2e`) and `web/vite.config.ts` with plugins `react()` and `tailwindcss()` and `server.port = 5173`
- [X] T003 [P] Create `web/index.html` (`<html lang="es">`, title "Agente de crédito · Demo", `<div id="root">`, script `/src/main.tsx`), `web/src/main.tsx` (renders `<App />` in `StrictMode`) and `web/src/index.css` (`@import "tailwindcss";`)
- [X] T004 [P] Create `web/playwright.config.ts`: `testDir: 'e2e'`, `use.baseURL` = `process.env.WEB_URL ?? 'http://localhost:8080'`, single project `chromium`, `timeout: 120_000`, `expect.timeout: 15_000`, `workers: 1`, `reporter: 'list'`
- [X] T005 [P] Create `web/nginx.conf`: `listen 8080;`, `root /usr/share/nginx/html;`, `location / { try_files $uri /index.html; }`, `location /documents/ { try_files $uri =404; }`
- [X] T006 Add section "Feature 002 · Web de demo" to `DECISIONS.md` **before** creating the container or adding Node/nginx (Principio I: agregar un contenedor o dependencia de infraestructura va precedido de una decisión): a table W-01…W-14 (decision + motivo, one line each, linking to `specs/002-demo-web/research.md`), stating that `web` (nginx) is the 6.º contenedor of the reference topology, the deviations of plan.md § Complexity Tracking (`X-Actor: advisor`, ruta `/asesor`, Playwright de 4 escenarios, `GET /policies/{version}`) and, as its own row, the implicit agent↔web contract: the chat's suggestions depend on `Conversation.state.last_question` and on the texts of `agent.questions.DOCUMENT_QUESTIONS`, exported to `web/public/scenarios.json` and guarded by `tests/web/test_scenarios_export.py` (contracts of 001 unchanged)
- [X] T007 Create `web/Dockerfile` (build context = repo root): stage `build` from `node:24-alpine` with `ARG VITE_AGENT_URL=http://localhost:8001` and `ARG VITE_ACTIONS_URL=http://localhost:8000` exported as `ENV`, `COPY web/package.json web/package-lock.json` → `npm ci`, `COPY web/ .`, `COPY fixtures/documents/*.png public/documents/`, `npm run build`; stage from `nginx:1.27-alpine` copying `dist/` to `/usr/share/nginx/html` and `web/nginx.conf` to `/etc/nginx/conf.d/default.conf`, `EXPOSE 8080`
- [X] T008 [P] Append to `.gitignore`: `web/public/documents/`, `web/test-results/`, `web/playwright-report/`
- [X] T009 Add to `Makefile`: `web-scenarios` (`$(PY) scripts/export_web_scenarios.py`), `web-dev` (copies `fixtures/documents/*.png` to `web/public/documents/` and runs `cd web && npm run dev`), `test-web` (`cd web && npx playwright test`); add them to `.PHONY`; update the `up` comment to "Build and start the 6 services"

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: CORS, contenedor `web` en el compose, fronteras verificadas, trazabilidad ampliada y
la base de la SPA (config, clientes de API, etiquetas, ruteo). Bloquea ambas historias.

**⚠️ CRITICAL**: ninguna historia empieza antes de terminar esta fase.

### Tests for Foundational

- [X] T010 [P] Write `services/actions_api/tests/test_cors.py` using the existing `client` fixture: (a) `OPTIONS /tools/create_case` with `Origin: http://localhost:8080`, `Access-Control-Request-Method: POST`, `Access-Control-Request-Headers: content-type,x-actor` → 200 and `access-control-allow-origin == "http://localhost:8080"`; (b) same with `Origin: http://evil.example` → no `access-control-allow-origin` header; (c) `GET /health` without `Origin` still 200. Build the app with `create_app(make_settings(..., web_origins=("http://localhost:8080",)))`
- [X] T011 [P] Write `services/agent/tests/test_cors.py`: build the agent app with `create_app` and settings `web_origins=("http://localhost:8080",)` and check with `TestClient` (no lifespan needed for preflight) that `OPTIONS /cases/{uuid}/messages` with `Origin: http://localhost:8080` and `Access-Control-Request-Headers: content-type,idempotency-key` returns `access-control-allow-origin` equal to the origin, and that `Origin: http://evil.example` gets none. Build it as `TestClient(create_app(dataclasses.replace(Settings.from_env(), web_origins=(...))))` **without** the `with` block: the lifespan (database, checkpointer) does not run, so no database or compose is needed
- [X] T012 [P] Update `tests/architecture/test_compose.py`: rename `test_topology_is_the_feature_001_subset` to `test_topology_is_the_feature_002_subset` asserting `set(SERVICES) == {"postgres", "actions_api", "agent", "llm_gateway", "doc_intel", "web"}`; add `test_web_has_no_database_llm_or_volumes` (no env key containing `DATABASE`, no `LLM_MODE`/`OLLAMA_URL`, `volumes("web") == []`, `set(SERVICES["web"]["depends_on"]) == {"agent", "actions_api"}`) marked `@pytest.mark.req("FR-054")`; add `test_web_origins_on_agent_and_actions_api` asserting `env(s)["WEB_ORIGINS"] == "${WEB_ORIGINS:-http://localhost:8080}"` for `agent` and `actions_api`
- [X] T013 [P] Write `tests/architecture/test_web_boundaries.py` marked `@pytest.mark.req("FR-054")`, scanning every `web/src/**/*.ts(x)`: (a) only `web/src/config.ts` reads `import.meta.env` and only `VITE_AGENT_URL` / `VITE_ACTIONS_URL`; (b) no source contains `:5432`, `:55432`, `:8002`, `:8003`, `11434`, `llm_gateway`, `doc_intel` or `postgres`; (c) the only `method: 'POST'` calls to the actions API live in `web/src/api/actions.ts` and target `/tools/` with header `X-Actor: advisor`; (d) no file contains `dangerouslySetInnerHTML` (also mark `@pytest.mark.req("FR-055")`)

### Implementation for Foundational

- [X] T014 Add CORS to `services/agent`: field `web_origins: tuple[str, ...] = ("http://localhost:8080",)` in `services/agent/src/agent/config.py` read from `WEB_ORIGINS` (comma-separated, trimmed, empty items dropped); in `services/agent/src/agent/main.py` add `fastapi.middleware.cors.CORSMiddleware` with `allow_origins=list(settings.web_origins)`, `allow_methods=["GET", "POST"]`, `allow_headers=["Content-Type", "Idempotency-Key"]`, `allow_credentials=False` (makes T011 pass)
- [X] T015 Add CORS to `services/actions_api`: field `web_origins` in `services/actions_api/src/actions_api/config.py` from `WEB_ORIGINS` (same parsing and default as T014); in `create_app` of `services/actions_api/src/actions_api/main.py` add `CORSMiddleware` with `allow_methods=["GET", "POST"]`, `allow_headers=["Content-Type", "X-Actor"]`, `allow_credentials=False` (makes T010 pass)
- [X] T016 Add service `web` to `docker-compose.yml` per [contracts/backend-changes.md](./contracts/backend-changes.md#contenedor-web-w-03): build context `.`, dockerfile `web/Dockerfile`, build args `VITE_AGENT_URL: ${VITE_AGENT_URL:-http://localhost:8001}` and `VITE_ACTIONS_URL: ${VITE_ACTIONS_URL:-http://localhost:8000}`, ports `"8080:8080"`, `depends_on` agent and actions_api with `condition: service_healthy`, healthcheck `["CMD", "wget", "-qO-", "http://localhost:8080/"]` with `<<: *http-health`; add `WEB_ORIGINS: ${WEB_ORIGINS:-http://localhost:8080}` to `agent` and `actions_api`; update the header comment to "Feature 002: 6 of the 7 reference containers (phoenix: feature 003)" (makes T012 pass)
- [X] T017 Extend `scripts/traceability.py`: `SPECS = [specs/001-credit-agent-core/spec.md, specs/002-demo-web/spec.md]` (FR ids from both); besides `@pytest.mark.req`, collect Playwright tags by regex `@FR-\d{3}` inside `test(` / `test.describe(` declarations of `web/e2e/*.spec.ts`, recording `web/e2e/<file>::<test title>` (for parametrized titles, the template literal text); keep the output format and update the header line to mention both marker kinds; exit 1 if any FR of either spec has no test
- [X] T018 [P] Create `web/src/config.ts` exporting `AGENT_URL = import.meta.env.VITE_AGENT_URL ?? 'http://localhost:8001'` and `ACTIONS_URL = import.meta.env.VITE_ACTIONS_URL ?? 'http://localhost:8000'` (only file that reads `import.meta.env`)
- [X] T019 [P] Create `web/src/api/types.ts` mirroring the fields the web uses from `packages/contracts`: `Stage` (`eligibility|profiling|simulation|documents`), `Status` (`active|escalated|ok_for_lender|rejected|cancelled`), `CaseView` (`id, stage, status, version, policy_version, created_at, updated_at, state`), `CaseState` (`client, declared, vehicle, key_quote, profile, options, selected_option_id, documents, validations, attempts, decisions, messages, open_escalation_id`), `CreditOption`, `DocumentRecord` (`id, requested_type, detected_type, is_test_specimen, fields: Record<string, {value, confidence}>, received_at`), `Validation` (`key, type, result, origin, detail, evidence, justification, attempt, policy_version, at`), `Decision`, `MessageRef`, `CaseSummary`, `Escalation`, `AuditEntry` (incl. `events`), `MetricsReport`, `ToolResult` (`outcome, case, result, events, rejection: {code, message} | null, policy_version`), `TurnResponse` (`message_id, reply, case: {stage, status, version}, tool_calls`), `CreateCaseResponse`, `Conversation` (`case_id, messages: {author, text, ...}[], state: {last_question, case}`), and the scenario types of [data-model.md](./data-model.md#escenario-de-demo-webpublicscenariosjson) (`Scenario`, `SuggestedMessage`, `DocumentSlot` with `slot: 'identification'|'income_proof'|'proof_of_address'|'vehicle_invoice'`, `SampleDocument` with `variant: 'ok'|'mismatch'`). Check field names against `packages/contracts/src/contracts/{case,channel,actions}.py`
- [X] T020 [P] Create `web/src/api/agent.ts`: `createCase(key)` → `POST {AGENT_URL}/cases` with `Idempotency-Key`; `sendMessage(caseId, text, key)` → `POST /cases/{id}/messages` JSON `{text}`; `sendDocument(caseId, sample: SampleDocument, key)` → fetches `/${sample.file}` as a Blob and posts `multipart/form-data` with `file` (filename = basename) and `requested_type`; `getConversation(caseId)` → `GET /cases/{id}/conversation`. Non-2xx throws `ApiError {status, code, message}` reading the agent error body (`409 case_busy`, `502 upstream_failure`) or a network error with `status: 0`
- [X] T021 [P] Create `web/src/api/actions.ts`: `getCase`, `listCases(params?)`, `getAudit(caseId)`, `listEscalations(status?)`, `getEscalation(id)`, `getPolicy(version)` (`GET /policies/{version}`), `getMetrics`, and `callTool(name, caseId, expectedVersion, input, idempotencyKey)` → `POST {ACTIONS_URL}/tools/{name}` with header `X-Actor: advisor` and body `{"context": {"case_id", "idempotency_key", "expected_version"}, "input"}`, returning the `ToolResult` for any status that has an `outcome` (200/403/409/422) and throwing `ApiError` otherwise. This is the only POST to the actions API in `web/src`
- [X] T022 [P] Create `web/src/labels.ts` with Spanish labels and a `label(kind, code)` helper that falls back to the raw code: stages (`eligibility` "Elegibilidad", `profiling` "Perfilamiento", `simulation` "Simulación", `documents` "Documentos"); statuses (`active` "En curso", `escalated` "Escalado a asesor", `ok_for_lender` "OK para financiera", `rejected` "Rechazado", `cancelled` "Cancelado"); `RejectionReason` (`owner_mismatch` "Titular distinto al cliente", `lien_or_debt` "Gravamen o adeudo", `no_offer_for_profile` "Perfil sin oferta", `advisor_rejected` "Rechazado por asesor"); `EscalationReason` (`mismatch_persisted` "Mismatch persistente", `client_requested_human` "El cliente pidió hablar con una persona", `sensitive_topic` "Tema sensible", `provider_failure` "Falla de proveedor", `no_reference_value` "Auto sin valor de referencia", `ok_revoked` "OK revocado", `policy_unavailable` "Política no disponible"); `ValidationType`, `ValidationResult` (`passed` "Aprobada", `mismatch` "No coincide", `low_confidence` "Confianza baja"), `ValidationOrigin`, `DocumentType` (read the enum in `packages/contracts/src/contracts/common.py`), `Actor` (`agent` "agente", `advisor` "asesor", `system` "sistema"), tool names of the 001 catalog, and rejection codes (`forbidden`, `version_conflict`, `idempotency_mismatch`, `case_closed`, `gate_not_met`, `invalid_input`, `consent_required`, `unconfirmed_data`, `case_busy`, `upstream_failure`)
- [X] T023 Create `web/src/App.tsx`: route by `location.pathname` — `/` → `location.replace('/chat')`; `/chat` → `<ChatPage />`; `/asesor` → `<AdvisorPage />`; otherwise a page with links to both. A slim header with links "Chat del cliente" (`/chat`) and "Consola del asesor" (`/asesor`) using plain `<a href>`; create placeholder `web/src/chat/ChatPage.tsx` and `web/src/advisor/AdvisorPage.tsx` that render their title (replaced in US1/US2)
- [X] T024 Run `make up` and verify the 6 containers are healthy and `http://localhost:8080/chat` and `/asesor` load the placeholders; run `make test-arch` and the CORS tests (T010, T011) green

**Checkpoint**: la web arranca en 8080, las APIs aceptan su origen y las fronteras están
verificadas.

---

## Phase 3: User Story 1 - Chat del cliente (Priority: P1) 🎯 MVP

**Goal**: elegir un escenario, conversar con el agente con sugerencias del guion y documentos de
ejemplo, ver la etapa en todo momento y el resultado final (FR-056…FR-064, FR-074, FR-075).

**Independent Test**: `cd web && npx playwright test --grep chat` recorre los 4 escenarios solo con sugerencias y
documentos y verifica etapa y resultado; manualmente, la tabla 1 de
[quickstart.md](./quickstart.md#1--chat-los-cuatro-escenarios-p1).

### Tests for User Story 1 ⚠️

> Escribirlos primero; deben fallar antes de implementar.

- [X] T025 [P] [US1] Write `tests/web/test_scenarios_export.py` (import `scripts.export_web_scenarios.build` the same way tests import `scripts.seed_fixtures`), marked `@pytest.mark.req("FR-056")` and `@pytest.mark.req("FR-057")`: (a) `build()` equals the committed `web/public/scenarios.json`; (b) the four ids are `happy_path`, `eligibility_rejection`, `document_failed`, `no_spare_key`; (c) every `messages[]` item matches a `say` step (same `stage`, `question`, `text`) of one of its `source_scripts`; (d) every `documents[].question` equals `agent.questions.DOCUMENT_QUESTIONS[...]` text for its slot; (e) every `options[].file` exists under `fixtures/documents/` and every `requested_type` is a `contracts.common.DocumentType`; (f) only `document_failed` has a slot with more than one option, and that slot is `income_proof` with variants `mismatch` and `ok`. Create `tests/web/__init__.py` if the test layout needs it
- [X] T026 [US1] Write the chat part of `web/e2e/demo.spec.ts`: load `web/public/scenarios.json`; helper `playToEnd(page, scenario, {incomeVariant})` that clicks `scenario-{id}`, then loops: wait until `typing` is hidden; if `result` is visible stop; if `suggestion` is visible click it; else click the highlighted `document-{file}` (for `income_proof` pick the option with the requested variant); fail after 40 steps. Parametrized test `for (const s of scenarios)` titled `` `chat · ${s.id}` `` with tags `@FR-053 @FR-056 @FR-057 @FR-058 @FR-059 @FR-060 @FR-061 @FR-062 @FR-063 @FR-074 @FR-075`: asserts `stage` shows "Elegibilidad" first, that the stage text changes in order (record each distinct value; must be a prefix of Elegibilidad → Perfilamiento → Simulación → Documentos), and that `result` equals the label of `s.expected_results[0]` (for `document_failed` play the `ok` income variant after one `mismatch`); for `eligibility_rejection` also assert `result-reason` = "Titular distinto al cliente"; for `no_spare_key` assert the conversation shows the key cost of the options. Extra test `chat · happy_path · texto libre, recarga y reinicio` tagged `@FR-055 @FR-059 @FR-063 @FR-064`: after the first agent reply type `<b>hola</b>` in `message-input` and press `send`, assert the client bubble text is literally `<b>hola</b>` and no `b` element exists inside the conversation, `send` is disabled while `typing` is visible, and `suggestion` is still visible afterwards; then `page.reload()` and assert the conversation, `stage` and `suggestion` are restored from `?scenario=&case=`; then click `restart` and assert the scenario picker shows and the URL has no `case`. Retry test `chat · reintento sin duplicar` tagged `@FR-063`: start `happy_path`, use `page.route('**/cases/*/messages', …)` to abort the first POST only (`route.abort()` once, then `route.continue()`), click `suggestion`, assert the Spanish error and the "Reintentar" button, record the `Idempotency-Key` of the failed request, click "Reintentar" and assert the retried request carries the same `Idempotency-Key`, exactly one client bubble with that text exists and the stage advances normally. Timing (SC-012): in `playToEnd` measure for every step the milliseconds from the click until `typing` is hidden; each chat test asserts the 95th percentile of its steps is `< 3000` and attaches the list with `testInfo.attach('tiempos', …)`

### Implementation for User Story 1

- [X] T027 [US1] Create `scripts/export_web_scenarios.py` with `build() -> dict` and `main()` writing `web/public/scenarios.json` (UTF-8, `ensure_ascii=False`, indent 2, trailing newline). A constant manifest maps the 4 web ids to their 001 scripts, Spanish `title`/`description`, `expected_results` (`document_failed` → `["ok_for_lender", "escalated"]`) and document labels per file (e.g. `laura_payslip_low.png` → "Recibo de nómina — no cuadra", `variant: "mismatch"`). Messages: the `say` steps (`stage`, `question`, `text`) in script order; for `document_failed` assert the `say` steps of `document_correction` and `document_escalation` are identical and use them once. Documents: one slot per requested type in first-appearance order, `income_proof` for `payslip`/`bank_statement`, `question` from `agent.questions.DOCUMENT_QUESTIONS` (key `DocumentType.x` or `"income_proof"`), options deduplicated by file, `file` = `documents/<basename>`. `client_name` from the first `nombre_completo` extracted in the script. Write `generated_from` with the script paths (makes T025 pass after T028)
- [X] T028 [US1] Run `make web-scenarios` and commit the generated `web/public/scenarios.json`; check `document_failed` offers both payslips in `income_proof`
- [X] T029 [P] [US1] Create `web/src/chat/suggestions.ts`: `suggestMessage(scenario, stage, lastQuestion)` returns the first `messages[]` with `question === lastQuestion && stage === stage` or `null`; `requestedSlot(scenario, lastQuestion)` returns the `documents[]` slot whose `question === lastQuestion` or `null` (W-06)
- [X] T030 [P] [US1] Create `web/src/chat/ScenarioPicker.tsx`: fetches `/scenarios.json` once, renders one card button per scenario (`data-testid="scenario-{id}"`) with title, description and client name; `onPick(scenario)`
- [X] T031 [P] [US1] Create `web/src/chat/MessageList.tsx`: bubbles for `client` (right) and `agent` (left) and document items ("Documento enviado: {label}"), all rendered as text with `whitespace-pre-wrap`; a `typing` bubble "escribiendo…" (`data-testid="typing"`) when `waiting`; auto-scroll to the last item; error line in Spanish with a "Reintentar" button when `error` is set
- [X] T032 [P] [US1] Create `web/src/chat/Composer.tsx`: suggestion chip (`data-testid="suggestion"`) above a text input (`message-input`) and button `send`; Enter sends; everything disabled while `waiting` or when the case is closed; empty text cannot be sent
- [X] T033 [P] [US1] Create `web/src/chat/DocumentTray.tsx`: shown only in stage `documents` with status `active`; lists every option of every slot of the scenario as a thumbnail (`<img src="/{file}">`) with its label and a send button (`data-testid="document-{basename}"`); options of the slot returned by `requestedSlot` are highlighted and listed first; disabled while `waiting`
- [X] T034 [P] [US1] Create `web/src/chat/CaseStatusBar.tsx`: stage stepper with the 4 stages (`data-testid="stage"` holds the current stage label) and the status label (`status`); when status is not `active` shows a prominent result block (`result` = status label, `result-reason` = reason): `rejected` → `label('rejection', reason)` of the last `state.decisions` with `kind === 'rejection'`; `escalated` → `label('escalation', escalation.reason)`; `ok_for_lender` green, `rejected` red, `escalated` amber, `cancelled` gray; plus a "Empezar de nuevo" button (`restart`) always visible
- [X] T035 [US1] Implement `web/src/chat/ChatPage.tsx` per [data-model.md § Sesión de chat](./data-model.md#sesión-de-chat-estado-del-componente-chatpage): read `scenario` and `case` from `URLSearchParams`; without scenario show `ScenarioPicker`; on pick call `createCase(uuid)`, push agent greeting, `history.replaceState` to `/chat?scenario={id}&case={caseId}`; `send(kind, payload)` creates `{kind, payload, idempotencyKey: crypto.randomUUID()}` as `pending`, sets `waiting`, calls `sendMessage`/`sendDocument`, appends the reply, then `refresh()` = `getConversation` (→ `lastQuestion`) + `getCase` (→ `caseView`) and, if `status === 'escalated'` and `open_escalation_id`, `getEscalation`; on error keep `pending` and show the error; "Reintentar" re-sends with the same key; with `case` in the URL on load, rebuild `messages` from `conversation.messages` and call `refresh()`; while `status === 'escalated'` poll `getCase` every 5 s (clear on unmount or status change) and on change call `refresh()`; when the scenario has no suggestion and no requested slot while active, show "No hay más pasos sugeridos; puedes escribir o empezar de nuevo"; show a discreet note "Con respuestas grabadas, usa las sugerencias para avanzar" under the composer; restart clears state and URL (makes T026 pass)
- [X] T036 [US1] Rebuild and run `docker compose up -d --build web`, then `cd web && npx playwright test --grep chat`; fix until the 5 chat tests pass in `LLM_MODE=fake`

**Checkpoint**: los 4 escenarios se completan desde el navegador; MVP demostrable.

---

## Phase 4: User Story 2 - Consola del asesor (Priority: P2)

**Goal**: bandeja de escalaciones, detalle con evidencia y confianza, timeline, acciones del
catálogo con actor asesor, casos y métricas (FR-065…FR-073).

**Independent Test**: `cd web && npx playwright test --grep asesor` genera una escalación desde el chat
(`document_failed`, rama B), la resuelve en `/asesor` y verifica OK, timeline y métricas;
manualmente, la sección 2 de [quickstart.md](./quickstart.md#2--consola-del-asesor-p2).

### Tests for User Story 2 ⚠️

- [X] T037 [P] [US2] Write `services/actions_api/tests/test_policies_endpoint.py` marked `@pytest.mark.req("FR-066")`: `GET /policies/{current_version}` → 200 with `policy_version` equal and `documents.min_field_confidence == "0.80"` (as serialized); `GET /policies/does-not-exist` → 404 `{"detail": "policy not found"}`; the call adds no rows to the audit log
- [X] T038 [US2] Add to `web/e2e/demo.spec.ts` the test `asesor · resolver escalación` tagged `@FR-053 @FR-054 @FR-065 @FR-066 @FR-067 @FR-068 @FR-069 @FR-070 @FR-071 @FR-073`: play `document_failed` with the `mismatch` income variant three times (reuse `playToEnd`) until `result` = "Escalado a asesor", read `caseId` from the URL; open `/asesor` in a second page; assert `inbox-item-{caseId}` is visible with "Mismatch persistente"; click it; assert `evidence` lists the four documents, that at least one `field-*` shows a confidence value, and that `timeline-entry` count ≥ 10 with an entry by "sistema" for `escalate`; choose `action-verify_validation_manually`, pick the income validation, type a justification, double-click `action-submit`; assert the status shows "OK para financiera", exactly one `timeline-entry` for `verify_validation_manually` by "asesor", followed by an `evaluate_gate` entry by "sistema"; assert the action panel now offers only `action-revoke_ok` (escalation actions are hidden for an OK case); open `/asesor` (no `case`), fetch `${ACTIONS_URL}/metrics` with `page.request.get` and assert that every count in `metrics` equals the API value (each `vehicle_rejections_by_reason`, `false_ok_by_reason` and `mismatches_by_type` entry by its Spanish label, plus `cases_with_key_quote`), tagged also `@FR-073` (SC-015); finally assert the chat page of that case shows `result` "OK para financiera" within 10 s (polling). Second test `asesor · revocar OK y acción rechazada` tagged `@FR-070 @FR-072`: play `happy_path` to OK, open `/asesor`, find the case in the case list, open it, submit `action-revoke_ok` with a reason, assert it appears in the inbox as "OK revocado"; then open it in a second tab, act there first (`return_to_agent`), and submit `reject_case` from the stale first tab: assert `action-error` shows the Spanish label of `version_conflict`, the detail reloads to the new version, and the timeline contains the rejected attempt

### Implementation for User Story 2

- [X] T039 [US2] Add `GET /policies/{policy_version}` to `services/actions_api/src/actions_api/main.py`: `services.policies.get(version)`; `PolicyUnavailable`/`KeyError` → `HTTPException(404, "policy not found")`; return the `Policy` model (`response_model=Policy` from `actions_api.policy_model`); no audit, no DB access (makes T037 pass)
- [X] T040 [P] [US2] Create `web/src/advisor/Inbox.tsx`: `listEscalations('open')`, then `Promise.all(getCase(e.case_id))`; rows (`data-testid="inbox-item-{case_id}"`) with client `state.client.full_name ?? 'Sin nombre'`, `label('escalation', reason)`, stage label and `created_at` formatted `es-MX`, sorted by `created_at` desc; "Actualizar" button; empty state "No hay escalaciones abiertas. Corre el escenario «Documento fallido» enviando el recibo que no cuadra para generar una."
- [X] T041 [P] [US2] Create `web/src/advisor/CaseList.tsx`: `listCases()` sorted by `updated_at` desc, each row with short id, stage and status labels, linking to `/asesor?case={id}`; "Actualizar" button
- [X] T042 [P] [US2] Create `web/src/advisor/MetricsPanel.tsx` (`data-testid="metrics"`): `getMetrics()` on mount and on "Actualizar"; four blocks: rechazos por auto por motivo (labels of `RejectionReason`), falsos OK por motivo, mismatches por tipo (labels of `ValidationType`), casos con llave cotizada; plus `audit_entries` as a footnote; empty groups show "Sin datos"
- [X] T043 [P] [US2] Create `web/src/advisor/Timeline.tsx`: renders `AuditEntry[]` in `id` order (`timeline-entry`), each with `at` (es-MX), actor label, tool label, `stage_before → stage_after`, outcome ("aceptada"/"rechazada" with `rejection_code` label) and event types; hides nothing (includes `append_message`) but visually dims `append_message` entries
- [X] T044 [P] [US2] Create `web/src/advisor/CaseDetail.tsx` (`data-testid="evidence"` on the evidence section): header with client name, stage, status, version and policy version; ticket block when there is an `Escalation` (reason, `summary`, `suggested_action`, `agent_note`, status); documents: per `DocumentRecord` show `requested_type` vs `detected_type` labels, "Documento de prueba" badge when `is_test_specimen`, and a table of fields (`data-testid="field-{requested_type}-{name}"`) with value and confidence as a percentage, marked "Confianza baja" in red when `confidence < Number(policy.documents.min_field_confidence)` (policy from `getPolicy(case.policy_version)`, never a constant); validations table: key, type, result, origin, attempt, `detail` as key: value text; client messages from `state.messages`
- [X] T045 [US2] Create `web/src/advisor/ActionPanel.tsx` per [data-model.md § Acción del asesor](./data-model.md#consola-del-asesor-estado-de-advisorpage): offers only the actions valid for the current status (`escalated`: `request_correction`, `verify_validation_manually`, `reject_case`, `return_to_agent`, `cancel_case`; `active`: `cancel_case`; `ok_for_lender`: `revoke_ok`), each opened with `data-testid="action-{tool}"`; forms: validation select (only validations with `result !== 'passed'`) + `message_to_client` for `request_correction`; validation select + required `justification` for `verify_validation_manually` with `evidence = [...validation.evidence, 'consola_asesor']`; required `reason` for `reject_case`, `revoke_ok`, `cancel_case`; `note` for `return_to_agent`; submit (`action-submit`) keeps one `idempotencyKey` per form attempt (created when the form opens, renewed only after an accepted result or when the user edits the form), disables itself while sending, calls `callTool(tool, case.id, case.version, input, key)`; on `outcome === 'rejected'` shows `action-error` with `label('rejection_code', rejection.code)` and `rejection.message`, then calls `onChanged()`; on accepted calls `onChanged()`
- [X] T046 [US2] Implement `web/src/advisor/AdvisorPage.tsx`: without `?case` show `Inbox`, `CaseList` and `MetricsPanel`; with `?case={id}` load in parallel `getCase`, `getAudit`, `getPolicy(case.policy_version)` and, if `open_escalation_id`, `getEscalation`; render `CaseDetail`, `ActionPanel` (`onChanged` reloads all four) and `Timeline`, plus a "← Bandeja" link to `/asesor`; navigation by `<a href>` (makes T038 pass)
- [X] T047 [US2] Rebuild `web` and `actions_api` (`docker compose up -d --build web actions_api`), run `uv run pytest services/actions_api/tests/test_policies_endpoint.py` and `cd web && npx playwright test --grep asesor`; fix until green

**Checkpoint**: chat y consola funcionan juntos; el asesor resuelve con el mismo catálogo y queda
registrado como `advisor`.

---

## Phase 5: Polish & Cross-Cutting Concerns

- [X] T048 [P] Add to the "Ajustes durante la implementación" table of `DECISIONS.md` (dated rows) every decision taken during the implementation of 002 that differs from research.md W-01…W-14; if none, leave the Feature 002 section as written in Phase 1
- [X] T049 [P] Update `README.md`: services table with `web` (8080), how to open `/chat` and `/asesor`, `make test-web` (requires Node 24 and `npx playwright install chromium` once), `make web-scenarios` after changing a script in `fixtures/scenarios/`, and the dev flow with `WEB_ORIGINS=http://localhost:8080,http://localhost:5173`
- [X] T050 Run `make traceability` and commit the regenerated `TRACEABILITY.md`; it must list FR-001…FR-075 with tests (add tags to `web/e2e/demo.spec.ts` for any FR-053…FR-075 still uncovered)
- [X] T051 Regression of feature 001 with the new compose: `make up && make test-arch && make test-e2e && make demo-all REPEAT=3`; all green
- [X] T052 After a fresh `make down -v && make up`, run `cd web && npx playwright test --grep "chat ·" --repeat-each 10` (SC-011: the 4 scenarios end with the expected result in 10 of 10 runs) and check the attached `tiempos` (SC-012 p95 < 3 s) and that every scenario takes < 3 min (SC-010 sanity)
- [X] T053 Walk through [quickstart.md](./quickstart.md) manually end to end, including the "Documento fallido (rama B)" + consola flow and the metrics check against `make metrics`; fix any copy that is not in Spanish

---

## Dependencies & Execution Order

### Phase Dependencies

- **Setup (Phase 1)**: sin dependencias. T006 (decisiones en `DECISIONS.md`) va antes de T007 y de T016 (Principio I); T007 depende
  de T001 (lockfile); T009 depende de que
  existan los comandos que invoca (puede escribirse antes).
- **Foundational (Phase 2)**: depende de Setup. Tests T010–T013 antes de T014–T016. T018–T022 en
  paralelo; T023 después de T018. T024 cierra la fase.
- **US1 (Phase 3)**: depende de Foundational. T025–T026 primero; T027 → T028; T029–T034 en
  paralelo; T035 después de T029–T034; T036 al final.
- **US2 (Phase 4)**: depende de Foundational; su e2e (T038) reutiliza el helper `playToEnd` y el
  chat de US1 para generar la escalación, así que su validación (T047) requiere US1 terminada. La
  implementación T039–T046 puede avanzar en paralelo con US1.
- **Polish (Phase 5)**: después de US1 y US2.

### User Story Dependencies

- **US1 (P1)**: independiente; MVP.
- **US2 (P2)**: implementación independiente; prueba e2e depende de US1 para crear la escalación
  desde el navegador (alternativa manual: `make demo-document-escalation` y abrir `/asesor`).

### Within Each User Story

- Tests escritos y fallando antes de implementar.
- Tipos y clientes de API (Phase 2) antes de componentes; componentes antes de la página.
- Cada historia cierra con su corrida de Playwright en verde.

### Parallel Opportunities

- Setup: T002, T003, T004, T005, T008 en paralelo tras T001.
- Foundational: T010–T013 en paralelo; T018–T022 en paralelo; T014 y T015 en paralelo entre sí
  (servicios distintos).
- US1: T029–T034 (seis archivos distintos) en paralelo.
- US2: T040–T044 en paralelo; T039 (backend) en paralelo con cualquier tarea de la web.
- US1 y US2 en paralelo después de Phase 2 si hay dos personas.

---

## Parallel Example: User Story 1

```bash
Task: "Create web/src/chat/suggestions.ts (suggestMessage, requestedSlot)"
Task: "Create web/src/chat/ScenarioPicker.tsx"
Task: "Create web/src/chat/MessageList.tsx with typing bubble"
Task: "Create web/src/chat/Composer.tsx"
Task: "Create web/src/chat/DocumentTray.tsx"
Task: "Create web/src/chat/CaseStatusBar.tsx"
```

## Parallel Example: User Story 2

```bash
Task: "Add GET /policies/{policy_version} in services/actions_api/src/actions_api/main.py"
Task: "Create web/src/advisor/Inbox.tsx"
Task: "Create web/src/advisor/CaseList.tsx"
Task: "Create web/src/advisor/MetricsPanel.tsx"
Task: "Create web/src/advisor/Timeline.tsx"
Task: "Create web/src/advisor/CaseDetail.tsx"
```

---

## Implementation Strategy

### MVP First (User Story 1 Only)

1. Phase 1 + Phase 2: web en 8080, CORS, fronteras y trazabilidad.
2. Phase 3: chat con los 4 escenarios.
3. **STOP and VALIDATE**: `cd web && npx playwright test --grep chat` y la tabla 1 del quickstart.
4. Ya se pueden mostrar los 4 demos desde el navegador.

### Incremental Delivery

1. Setup + Foundational → base lista.
2. US1 → los 4 demos en el navegador (MVP).
3. US2 → resolución humana y métricas en la consola.
4. Polish → decisiones, README, trazabilidad, regresión de 001.

---

## Notes

- [P] = otro archivo y sin dependencias pendientes.
- No se agregan tools, permisos ni tablas; si una tarea parece requerirlo, detenerse y registrar
  la decisión en `DECISIONS.md` antes (Principio I).
- Commit por tarea o grupo lógico, solo cuando se pida (memoria del proyecto).

---

## Phase 6: Convergence

- [X] T054 CRITICAL: Show only Spanish text for API errors in `web/src/api/errors.ts` (and its callers `web/src/chat/ChatPage.tsx`, `web/src/advisor/ActionPanel.tsx`): map `http_404` → "No se encontró el caso o el recurso pedido", `http_5xx` → "El servicio no respondió correctamente", other `http_*` → "La solicitud no se pudo completar"; never show the actions_api `detail` or the HTTP `statusText` (English) to the user; keep the agent's Spanish `error.message` and the Spanish `rejection.message`; add the labels to `rejection_code` in `web/src/labels.ts` and extend `tests/architecture/test_web_boundaries.py` to fail if `errors.ts` uses `statusText` or `detail` as user text per Constitution X (contradicts)
- [X] T055 Renew the idempotency key in `web/src/advisor/ActionPanel.tsx` after a `rejected` outcome (the case is reloaded, so the next submit is a new attempt on another version; keep reusing it only for a resend of the same attempt after a network error), and extend `asesor · revocar OK y acción rechazada` in `web/e2e/demo.spec.ts` so that, after the `version_conflict`, submitting `reject_case` again from the same tab is accepted and the case shows "Rechazado" per FR-070, US2/AC8 (partial)
- [X] T056 In `web/src/advisor/CaseDetail.tsx`, list by name (with `label('field', …)`) the fields of each document that came back empty or with confidence below `policy.documents.min_field_confidence`, marked "Confianza baja", below the table of extracted fields, instead of only counting them; keep `data-testid="field-{requested_type}-{name}"` on the extracted rows per FR-066, US2/AC2 (partial)
- [X] T057 In `web/src/chat/ChatPage.tsx`, when restoring a `?case=` session fails (unknown case or API down), show the Spanish error together with an "Empezar de nuevo" button (`data-testid="restart"`) that clears the URL and returns to the scenario picker, and add a Playwright test `chat · recarga con caso inexistente` tagged `@FR-064` in `web/e2e/demo.spec.ts` per Edge case "Recargar la página" (partial)
- [X] T058 Remove the unused exports `formatMoney` from `web/src/labels.ts` and `FINAL_STATUSES` from `web/src/api/types.ts`, or use `FINAL_STATUSES` in `web/src/chat/ChatPage.tsx` instead of its inline list of final statuses per plan: estructura de `web/src` (unrequested)
