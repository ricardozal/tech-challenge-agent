# Research: Web de demo

Decisiones de diseño de la feature 002 (W-01…W-14). Continúan las de
[001/research.md](../001-credit-agent-core/research.md) (R-01…R-23) y se registran en
`DECISIONS.md` al implementar (Principio I).

## W-01 · Stack de la web

- **Decision**: `web/` con React 19, Vite, TypeScript (strict) y Tailwind CSS 4 (plugin de Vite).
  Sin librería de componentes, sin router, sin estado global ni librería de datos: componentes con
  `useState`/`useEffect` y `fetch` directo a `agent` y `actions_api`. Versiones fijadas por
  `package-lock.json`.
- **Rationale**: es la entrada del plan. Dos vistas y unas diez pantallas parciales no justifican
  más; menos dependencias, menos que explicar en la entrevista.
- **Alternatives considered**: Next.js/SSR (excluido por el usuario; agrega un servidor sin
  necesidad), react-router (dos rutas se resuelven con `location.pathname`), TanStack Query/Redux
  (estado local suficiente), shadcn/MUI (excluido).

## W-02 · Ruteo sin librería

- **Decision**: `App` elige la vista por `location.pathname`: `/chat` → chat, `/asesor` → consola,
  `/` → redirige a `/chat`, otra ruta → enlace a ambas. Navegación entre vistas con `<a href>`
  (recarga completa). nginx sirve `index.html` para cualquier ruta (`try_files $uri /index.html`).
- **Rationale**: dos rutas, sin transiciones; cada vista arranca de cero leyendo de las APIs.
- **Alternatives considered**: react-router (dependencia sin valor aquí), hash routing (URLs
  feas en la demo).

## W-03 · Contenedor `web`: build de Vite servido con nginx en 8080

- **Decision**: `web/Dockerfile` multi-stage con contexto en la raíz del repo: etapa `node:24-alpine`
  (`npm ci`, `npm run build`, copia `fixtures/documents/*.png` a `public/documents/`), etapa
  `nginx:1.27-alpine` con `dist/` y `web/nginx.conf`. Puerto 8080 (`listen 8080`, publicado como
  `8080:8080`). Las URLs de las APIs entran como `VITE_AGENT_URL` y `VITE_ACTIONS_URL` en build
  (por defecto `http://localhost:8001` y `http://localhost:8000`).
- **Rationale**: `web` es el sexto contenedor de la topología de referencia (constitución); es
  estático, sin estado y sin acceso a la base. El navegador llama a las APIs directamente, así que
  no hay proxy ni timeouts de proxy cuando el modelo real tarda.
- **Alternatives considered**: nginx como reverse proxy de las APIs (evita CORS, pero la entrada
  del plan pide CORS y llamadas directas; además ocultaría que la consola usa la misma API que el
  agente), servir el build desde FastAPI (mezcla responsabilidades).

## W-04 · CORS solo para el origen de la web

- **Decision**: `CORSMiddleware` de FastAPI en `agent` y `actions_api`, con
  `allow_origins = WEB_ORIGINS` (lista separada por comas, por defecto
  `http://localhost:8080`; el compose la fija igual). Métodos `GET`, `POST`; encabezados
  `Content-Type`, `Idempotency-Key`, `X-Actor`; sin credenciales. Para `npm run dev` se agrega
  `http://localhost:5173` vía variable al levantar el compose.
- **Rationale**: entrada del plan; el navegador llama desde `:8080` a `:8000`/`:8001`. Un origen
  explícito evita `*` y deja documentado quién puede llamar desde un navegador.
- **Alternatives considered**: `allow_origins=["*"]` (innecesariamente abierto), proxy (W-03).

## W-05 · Escenarios del chat: exportados de los guiones de 001

- **Decision**: `scripts/export_web_scenarios.py` (`make web-scenarios`) lee
  `fixtures/scenarios/*.yaml` y escribe `web/public/scenarios.json` (versionado en git) con los 4
  escenarios de la web ([contracts/web-scenarios.md](./contracts/web-scenarios.md)). "Documento
  fallido" une `document_correction` y `document_escalation`: los mensajes son idénticos y el paso
  del comprobante de ingresos ofrece `laura_payslip_low.png` (no cuadra) y `laura_payslip.png`
  (correcto). Un test (`tests/web/test_scenarios_export.py`) regenera en memoria y falla si el
  archivo versionado está desactualizado.
- **Rationale**: los guiones de 001 ya están sembrados como fixtures del LLM (R-11, R-23); si la
  web sugiere exactamente esos textos, el modo `fake` los entiende y los 4 escenarios terminan
  igual que los demos (FR-074). Versionar el JSON evita Python en el build de Node.
- **Alternatives considered**: guiones a mano en TypeScript (se desincronizan de los fixtures),
  endpoint en `agent` que sirva escenarios (mete material de demo en un servicio), generar en el
  Dockerfile con una etapa Python (dos toolchains en el build).

## W-06 · Sugerencias guiadas por la última pregunta del agente

- **Decision**: después de cada turno el chat lee `GET {agent}/cases/{id}/conversation` y toma
  `state.last_question`. Sugerencia de mensaje = el mensaje del escenario cuya `question` es igual a
  `last_question` y cuya `stage` es la etapa actual. En etapa de documentos, la bandeja muestra los
  documentos de ejemplo del escenario y resalta el que corresponde a `last_question` (el export
  incluye la pregunta de cada tipo, tomada de `agent.questions.DOCUMENT_QUESTIONS`).
- **Rationale**: la llave del fixture incluye la pregunta (R-11); emparejar por pregunta es lo que
  hace que la sugerencia sea la respuesta correcta aunque el usuario haya escrito texto libre antes.
  El agente acepta los documentos en cualquier orden (los guiones de 001 usan órdenes distintos).
- **Alternatives considered**: avanzar un índice del guion (se rompe con texto libre o
  reintentos), pedir al agente el siguiente paso (el agente no conoce guiones).

## W-07 · Etapa, estado y resultado

- **Decision**: `TurnResponse.case` actualiza etapa y estado de inmediato; además, tras cada turno
  el chat lee `GET {actions}/cases/{id}` (fuente de verdad, entrada del plan). Resultado:
  `ok_for_lender` → "OK para financiera"; `rejected` → motivo de la última decisión
  `kind = rejection`; `escalated` → `GET {actions}/escalations/{open_escalation_id}` y su
  `reason`; `cancelled` → "Cancelado". Mientras el caso esté escalado, el chat vuelve a leer el
  caso cada 5 s para reflejar la resolución del asesor (FR-062, escenario 11 de P2).
- **Rationale**: un solo lector de verdad (actions_api) y sin websockets (excluidos). El sondeo
  solo ocurre en el estado escalado, que es el único que cambia sin acción del cliente.
- **Alternatives considered**: websockets/SSE (excluidos), botón manual solamente (menos claro en
  la demo).

## W-08 · Respuesta síncrona, "escribiendo…" y reintentos

- **Decision**: cada envío es un `fetch` que espera el `TurnResponse`. Mientras tanto se muestra la
  burbuja "escribiendo…" y se deshabilitan entrada, sugerencias y documentos. La
  `Idempotency-Key` (`crypto.randomUUID()`) se crea al intentar enviar y se reutiliza si el
  usuario pulsa "Reintentar" tras un error de red o `409 case_busy`; así un reintento nunca
  duplica (FR-063, contrato del canal de 001). Errores se muestran en español debajo del mensaje.
- **Rationale**: entrada del plan; el contrato del canal ya garantiza idempotencia y candado.
- **Alternatives considered**: cola de mensajes en el cliente (innecesaria con envío bloqueado).

## W-09 · Recuperar la conversación al recargar

- **Decision**: la URL guarda la sesión: `/chat?scenario=<id>&case=<uuid>`. Al cargar con `case`,
  el chat pide `GET {agent}/cases/{id}/conversation` (historial y última pregunta) y
  `GET {actions}/cases/{id}`. "Empezar de nuevo" limpia la query. El historial no muestra los
  documentos como imagen, solo el texto que el agente registró.
- **Rationale**: sin `localStorage` ni estado global; la URL se puede recargar o compartir.
- **Alternatives considered**: `localStorage` (estado invisible, se pierde entre navegadores).

## W-10 · Consola: lecturas y acciones

- **Decision**: la consola usa solo `actions_api`:
  - Bandeja: `GET /escalations?status=open`, y por cada una `GET /cases/{case_id}` en paralelo para
    nombre del cliente y etapa (decenas de casos en una demo).
  - Detalle: `GET /cases/{id}`, `GET /escalations/{id}`, `GET /cases/{id}/audit`.
  - Buscar caso: `GET /cases` (todos, más recientes primero) para abrir cualquiera (FR-072).
  - Métricas: `GET /metrics`.
  - Acciones: `POST /tools/{name}` con `X-Actor: advisor` (el valor del enum `Actor` de 001; la UI
    lo muestra como "asesor"), `context.expected_version` = versión del caso mostrado y una
    `context.idempotency_key` por intento, reutilizada en reintentos.
- **Rationale**: Principio IV: el asesor escribe por la misma capa de acciones que el agente. Sin
  endpoints de escritura nuevos.
- **Alternatives considered**: agregar `client_name` a `Escalation` o `CaseSummary` (cambia
  contratos de 001 solo por conveniencia; se puede hacer después si la bandeja crece).

## W-11 · Umbral de confianza desde la política

- **Decision**: nuevo endpoint de solo lectura `GET /policies/{policy_version}` en `actions_api`,
  que devuelve la política de esa versión (`PolicyRegistry.get`). La consola marca como baja la
  confianza de un campo cuando es menor que `documents.min_field_confidence` de la versión de
  política del caso.
- **Rationale**: Principio VI: no hay umbrales en el código, tampoco en la web. Es un lector, no
  una acción, así que no necesita auditoría.
- **Alternatives considered**: hardcodear `0.80` en la web (viola el Principio VI), marcar solo
  las validaciones `low_confidence` (no dice qué campo).

## W-12 · Textos en español para códigos

- **Decision**: `web/src/labels.ts` traduce los códigos de los enums de 001 (`Stage`, `Status`,
  `RejectionReason`, `EscalationReason`, `ValidationType`, `ValidationResult`, `DocumentType`,
  `Actor`, nombres de tools, campos extraídos) a texto en español. Un código sin traducción se
  muestra tal cual.
- **Rationale**: Principio X (mensajes al usuario en español) sin tocar contratos. Es texto de
  presentación, no reglas.
- **Alternatives considered**: devolver textos desde las APIs (mezcla presentación en servicios).

## W-13 · Pruebas: Playwright contra el compose

- **Decision**: `web/e2e/demo.spec.ts` con `@playwright/test` (Chromium) contra
  `http://localhost:8080` con el compose levantado en `LLM_MODE=fake` (`make test-web`):
  1. Chat, parametrizado por los 4 escenarios: elegir escenario, avanzar solo con sugerencias y
     documentos de ejemplo, verificar etapa visible y resultado. "Documento fallido" toma la rama
     de corrección. El happy path además envía un texto libre con marcado HTML para verificar que
     se muestra como texto y que la sugerencia sigue disponible.
  2. Asesor: genera una escalación con "documento fallido" rama B desde el chat, la abre en
     `/asesor`, revisa evidencia y timeline, marca la validación de ingreso como verificada
     manualmente y verifica que el caso queda en OK para financiera, que el timeline muestra
     `advisor` seguido de la evaluación del gate por `system`, que el panel de métricas carga y que
     el chat refleja el OK.
  Cada test lleva sus FR como tags de Playwright (`{ tag: ['@FR-056', …] }`).
  `scripts/traceability.py` se amplía: lee los FR de las specs 001 y 002 y, además de
  `@pytest.mark.req`, toma los tags `@FR-xxx` de `web/e2e/*.spec.ts`.
- **Rationale**: entrada del plan (happy path en `/chat` y resolución en `/asesor`). Parametrizar
  el test del chat por escenario cuesta unas líneas porque los escenarios son datos, y cubre
  FR-074/FR-075 y SC-011 (los 4 escenarios desde el chat), que el happy path solo no cubriría.
  Principio VII: cada FR nuevo con al menos un test marcado.
- **Alternatives considered**: solo happy path + asesor (deja FR-075 sin cumplir), Vitest para la
  lógica de sugerencias (otra herramienta; el e2e ya la ejercita), Cypress (más pesado).

## W-14 · Fronteras de la web

- **Decision**: `tests/architecture/test_compose.py` pasa a la topología de 6 contenedores
  (`web` incluido; `phoenix` sigue para la 003) y verifica que `web` no tiene `DATABASE_URL`,
  variables del LLM ni volúmenes, y que solo depende de `agent` y `actions_api`. Un test nuevo
  revisa que `web/src` solo usa `VITE_AGENT_URL` y `VITE_ACTIONS_URL` como destinos y que las
  escrituras a `actions_api` son solo `POST /tools/` con `X-Actor: advisor`. Tests de CORS en
  `agent` y `actions_api`: el origen de la web recibe `Access-Control-Allow-Origin`; otro origen
  no.
- **Rationale**: Principios III y IV verificados con tests, igual que las fronteras de 001 (R-20).
- **Alternatives considered**: confiar en revisión de código (no falla ante una violación).
