# Implementation Plan: Web de demo

**Branch**: `002-demo-web` | **Date**: 2026-10-04 | **Spec**: [spec.md](./spec.md)

**Input**: Feature specification from `specs/002-demo-web/spec.md`

## Summary

Una web estática (React + Vite + TypeScript + Tailwind) servida por nginx en el contenedor `web`
(puerto 8080) con dos vistas. `/chat` crea un caso con el agente, sugiere los mensajes y documentos
de los guiones de 001 emparejándolos con la última pregunta del agente, muestra "escribiendo…"
mientras espera la respuesta síncrona y lee etapa, estado y resultado de `actions_api`. `/asesor`
lee escalaciones, casos, registro de acciones y métricas de `actions_api` y resuelve llamando las
tools del catálogo de 001 con `X-Actor: advisor`. El backend solo cambia en CORS para el origen de
la web y un lector `GET /policies/{version}` para el umbral de confianza. Playwright recorre los 4
escenarios en el chat y la resolución de una escalación en la consola. Decisiones en
[research.md](./research.md) (W-01…W-14).

## Technical Context

**Language/Version**: TypeScript 5 (strict) sobre Node 24 para build y pruebas; Python 3.12 en los
cambios de backend y scripts

**Primary Dependencies**: React 19, Vite, Tailwind CSS 4 (`@tailwindcss/vite`), `@playwright/test`
(dev); nginx 1.27 (imagen). Backend: `fastapi.middleware.cors` (ya incluido en FastAPI). Sin
librería de componentes, router, estado global ni cliente HTTP

**Storage**: ninguno en la web; la sesión del chat vive en la URL (W-09)

**Testing**: Playwright (Chromium) contra el compose con tags `@FR-xxx`; pytest para CORS, el
lector de política, el export de escenarios y las fronteras (`tests/architecture`)

**Target Platform**: navegador moderno de escritorio; contenedor Linux con nginx

**Project Type**: aplicación web (SPA estática) sobre los servicios existentes

**Performance Goals**: respuesta del agente visible en < 3 s en el 95% de los mensajes con
`LLM_MODE=fake` (SC-012); cualquier escenario completo en < 3 min (SC-010)

**Constraints**: sin autenticación, sin Next.js/SSR, sin websockets; respuestas síncronas; la web
solo habla con `agent` y `actions_api`; toda escritura por el canal del agente o por `/tools` con
actor `advisor`; textos en español; reproducible sin GPU

**Scale/Scope**: 1 persona haciendo la demo; decenas de casos; 2 vistas, ~10 componentes

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

| Principio | Cumplimiento | Estado |
|---|---|---|
| I · Demo, no producto | La web sirve a los 4 demos (chat) y a la resolución humana del demo 3 y el reporte (consola). `web` es el 6.º contenedor de la topología de referencia; el stack (React/Vite/Tailwind/nginx/Playwright) se registra en `DECISIONS.md` (W-01, W-03, W-13) | ✅ |
| II · El LLM propone, el código decide | La web no decide nada: muestra resultados de `actions_api`; el asesor no marca OK, el gate lo evalúa el sistema | ✅ |
| III · Fronteras | La web solo llama `agent` y `actions_api`; no toca base, gateway, doc_intel ni Ollama. El agente no cambia de fronteras. Verificado por `test_compose.py` y un test de fuentes de `web/src` (W-14) | ✅ |
| IV · Una sola capa de acciones | El asesor escribe solo con `POST /tools/{name}` (`X-Actor: advisor`, idempotencia, versión esperada, auditoría); el chat solo por el canal del agente. Sin endpoints de escritura nuevos | ✅ |
| V · Reproducible sin GPU | Las sugerencias son los textos de los guiones sembrados como fixtures; los 4 escenarios terminan igual en `LLM_MODE=fake`. La web no conoce el modo | ✅ |
| VI · Política versionada | El umbral de confianza se lee de `GET /policies/{version}` (W-11); la web no tiene umbrales | ✅ |
| VII · Trazabilidad | FR-053…FR-075 marcados en Playwright (tags) y pytest; `traceability.py` lee ambas specs y ambos tipos de marcador | ✅ |
| VIII · Calidad del LLM | No toca extracción, prompts ni esquemas; `make eval` no aplica | ✅ (N/A) |
| IX · Tests reales y mínimos | Un archivo de Playwright contra el stack real (4 escenarios + asesor), tests de CORS/lector/export/fronteras; sin mocks ni tests de componentes | ✅ |
| X · Sintéticos, texto como dato, idioma | Solo documentos sintéticos marcados; React escapa todo texto (sin `dangerouslySetInnerHTML`); UI en español, código en inglés; la ruta `/asesor` es texto visible al usuario | ✅ |
| XI · Fuera de alcance | Sin autenticación, colas, Redis, etc. Excluidos además Next.js/SSR y websockets | ✅ |

**Gates de cierre** (constitución, "Flujo de desarrollo"): e2e de 001 y Playwright en verde en
`LLM_MODE=fake`; `make test-arch` en verde con la topología nueva; `make traceability` sin FR
pendientes; `make eval` no aplica.

**Re-check post-diseño**: sin cambios. El diseño agrega un solo lector a `actions_api` y CORS; no
agrega tools, permisos, tablas ni dependencias de infraestructura fuera de la topología.

## Project Structure

### Documentation (this feature)

```text
specs/002-demo-web/
├── plan.md
├── research.md            # W-01…W-14
├── data-model.md
├── quickstart.md
├── contracts/
│   ├── web-ui.md          # rutas, llamadas por vista, data-testid
│   ├── web-scenarios.md   # formato de scenarios.json y reglas del export
│   └── backend-changes.md # CORS, GET /policies/{version}, servicio web en compose
├── checklists/requirements.md
└── tasks.md               # /speckit-tasks
```

### Source Code (repository root)

```text
web/
├── Dockerfile               # node:24-alpine build → nginx:1.27-alpine (contexto: raíz)
├── nginx.conf               # listen 8080; try_files $uri /index.html
├── package.json / package-lock.json
├── vite.config.ts           # react + @tailwindcss/vite
├── tsconfig.json
├── playwright.config.ts     # baseURL http://localhost:8080, chromium
├── index.html
├── public/
│   ├── scenarios.json       # generado por scripts/export_web_scenarios.py (versionado)
│   └── documents/           # copiado en build/dev desde fixtures/documents (ignorado por git)
├── src/
│   ├── main.tsx
│   ├── App.tsx              # ruteo por pathname (/chat, /asesor)
│   ├── index.css            # @import "tailwindcss"
│   ├── config.ts            # VITE_AGENT_URL, VITE_ACTIONS_URL
│   ├── labels.ts            # códigos → español (W-12)
│   ├── api/
│   │   ├── types.ts         # espejo de los campos de contracts que usa la web
│   │   ├── agent.ts         # createCase, sendMessage, sendDocument, getConversation
│   │   └── actions.ts       # getCase, listCases, getAudit, listEscalations, getEscalation,
│   │                        # getPolicy, getMetrics, callTool (X-Actor: advisor)
│   ├── chat/
│   │   ├── ChatPage.tsx     # sesión, envío, reintento, sondeo en escalado
│   │   ├── ScenarioPicker.tsx
│   │   ├── MessageList.tsx  # burbujas + "escribiendo…"
│   │   ├── Composer.tsx     # texto libre + sugerencia
│   │   ├── DocumentTray.tsx
│   │   ├── CaseStatusBar.tsx
│   │   └── suggestions.ts   # emparejamiento por last_question (W-06)
│   └── advisor/
│       ├── AdvisorPage.tsx
│       ├── Inbox.tsx
│       ├── CaseList.tsx
│       ├── CaseDetail.tsx   # ticket, evidencia, validaciones
│       ├── Timeline.tsx
│       ├── ActionPanel.tsx  # formularios por tool, idempotencia y reintento
│       └── MetricsPanel.tsx
└── e2e/
    └── demo.spec.ts         # 4 escenarios del chat + resolución en /asesor

services/agent/src/agent/main.py           # + CORSMiddleware (WEB_ORIGINS)
services/agent/src/agent/config.py         # + web_origins
services/agent/tests/test_cors.py
services/actions_api/src/actions_api/main.py    # + CORSMiddleware, + GET /policies/{version}
services/actions_api/src/actions_api/config.py  # + web_origins
services/actions_api/tests/test_cors.py
services/actions_api/tests/test_policies_endpoint.py

scripts/export_web_scenarios.py   # fixtures/scenarios → web/public/scenarios.json
scripts/traceability.py           # + spec 002, + tags @FR-xxx de web/e2e
tests/web/test_scenarios_export.py
tests/architecture/test_compose.py   # topología de 6, fronteras de web
tests/architecture/test_web_boundaries.py

docker-compose.yml   # + servicio web, + WEB_ORIGINS en agent y actions_api
Makefile             # + web-scenarios, web-dev, test-web; up incluye web
DECISIONS.md         # + sección Feature 002 (W-01…W-14)
README.md            # + cómo abrir /chat y /asesor
```

**Structure Decision**: un directorio `web/` en la raíz, hermano de `services/`, porque no es un
servicio Python del workspace `uv` sino un proyecto Node independiente. Los cambios de backend se
quedan en los servicios existentes y no tocan `packages/contracts`.

## Complexity Tracking

Sin violaciones de la constitución que justificar.

| Desviación de la entrada del plan | Por qué | Alternativa descartada |
|---|---|---|
| Header `X-Actor: advisor` (no `asesor`) | Es el valor del enum `Actor` de 001; `asesor` daría `422` | Agregar un alias en `actions_api` (dos nombres para el mismo actor en el registro) |
| Ruta `/asesor` en lugar de `/adviser` de la spec | La entrada del plan es posterior; se registró como clarificación en la spec | — |
| Playwright parametrizado por los 4 escenarios del chat (no solo happy path) | FR-074/FR-075 y SC-011 exigen los 4 desde el chat; los escenarios son datos, el costo es mínimo | Solo happy path (deja FR-075 sin test) |
| Lector `GET /policies/{version}` nuevo | Principio VI: la web no puede tener el umbral de confianza hardcodeado | Hardcodear 0.80 |
