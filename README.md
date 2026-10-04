# Agente de crédito con garantía vehicular

Technical challenge (demo) para una entrevista de Senior AI Engineer. Un agente conversacional opera el
tramo previo a la originación de un crédito personal con el auto como garantía, en el que el cliente
sigue usando su auto:

**elegibilidad del auto → perfilamiento → simulación → datos y comprobantes → "OK para financiera" o
escalación a un asesor**

El LLM conversa, interpreta y extrae; **el código decide**. Elegibilidad, perfil, cuotas, costo de la
llave, validaciones documentales y el gate son funciones puras con una política versionada, y cada
acción queda en un registro que solo admite inserciones.

## Arquitectura

Seis contenedores con docker compose y Ollama en el host:

| Servicio | Qué hace |
|---|---|
| `agent` | Canal de mensajes y documentos por caso; grafo de LangGraph que interpreta y responde. Solo actúa por la Case Actions API y solo pide inferencia al LLM Gateway |
| `actions_api` | Case Actions API: única capa de escritura para agente y asesor (permisos actor × etapa × tool, idempotencia, versión esperada, candado por caso, registro de acciones). Aquí viven las reglas |
| `llm_gateway` | Único cliente de Ollama. `LLM_MODE=fake` (por defecto, respuestas grabadas), `record` u `ollama` |
| `doc_intel` | OCR + extracción + confianza por campo. Sin base de datos ni estado |
| `web` | Web de demo en http://localhost:8080: chat del cliente (`/chat`) y consola del asesor (`/asesor`). Estática (nginx); el navegador llama directo a `agent` y `actions_api` |
| `postgres` | Esquemas `cases`, `audit` (solo inserción) y `agent` (checkpoints), con un rol por servicio |

Diagramas C4 en [docs/diagrams/](docs/diagrams/) (contexto, contenedores, componentes y vista dinámica).
Las decisiones están en [DECISIONS.md](DECISIONS.md) y la especificación completa en
[specs/001-credit-agent-core/](specs/001-credit-agent-core/) (spec, plan, research, modelo de datos,
contratos y tareas); la web de demo, en [specs/002-demo-web/](specs/002-demo-web/). La constitución del proyecto está en
[.specify/memory/constitution.md](.specify/memory/constitution.md).

## Requisitos

- Docker con Compose v2 y [uv](https://docs.astral.sh/uv/).
- Solo para las pruebas de la web (`make test-web`): Node 24 y, una vez, `cd web && npm ci && npx playwright install chromium`.
- Solo para `LLM_MODE=ollama|record` y `make eval`: Ollama en el host con `gemma4:12b` y `glm-ocr`.

No hace falta GPU: por defecto el gateway responde con fixtures grabados.

## Arrancar

```bash
uv sync
make up        # construye y levanta los 6 servicios (LLM_MODE=fake)
make ps
```

## Web de demo

Con `make up`, abre http://localhost:8080:

- **`/chat`**: eliges un escenario (happy path, rechazo por auto, documento fallido, sin segunda llave)
  y conversas con el agente como el cliente de prueba. Las sugerencias son los mensajes del guion y
  los documentos de ejemplo son los sintéticos de `fixtures/documents/`; siempre se ve la etapa y, al
  final, el resultado. En "documento fallido", enviar el recibo correcto lleva a OK; reenviar tres
  veces el que no cuadra escala el caso.
- **`/asesor`**: bandeja de escalaciones, detalle con evidencia (campos extraídos con su confianza),
  registro de acciones, las acciones del asesor (las mismas tools que usa el agente, como `advisor`) y
  el panel de métricas.

Con respuestas grabadas (`LLM_MODE=fake`) solo se entienden los mensajes del guion; el texto libre
funciona con `LLM_MODE=ollama`. Si cambias un guion de `fixtures/scenarios/`, corre
`make web-scenarios`. Para desarrollar la web con recarga en caliente:
`WEB_ORIGINS=http://localhost:8080,http://localhost:5173 make up && make web-dev`.

## Los 4 demos

| Demo | Comando | Qué muestra |
|---|---|---|
| 1 · Happy path | `make demo-happy-path` | Auto elegible, perfil, opciones, 4 documentos en orden; el sistema marca **OK para financiera** |
| 2 · Rechazo por elegibilidad | `make demo-eligibility-rejection` | "Está a nombre de mi esposa": rechazo con motivo, sin consultar Buró |
| 3 · Validación documental fallida | `make demo-document-correction` · `make demo-document-escalation` | El recibo no cuadra con el ingreso declarado: la clienta corrige y llega a OK, o falla 3 veces y se escala con ticket |
| 4 · Sin segunda llave | `make demo-no-spare-key` | Se cotiza la llave ($2,400), entra al plan de pagos y el caso llega a OK |

Cada demo imprime la conversación, el estado final del caso y su registro de acciones.
`make demo-all REPEAT=10` corre los cinco guiones diez veces.

Después del demo 3B, un asesor resuelve el ticket con las mismas acciones que el agente:

```bash
make advisor-open-escalations
make advisor-verify CASE=<id> KEY=income JUSTIFICATION="Ingreso confirmado por llamada con el empleador"
```

## Tests y calidad

```bash
make test           # reglas, tools, gateway, doc_intel y agente (necesita make up)
make test-arch      # fronteras: import-linter, permisos de BD, registro inmutable, compose
make test-web       # Playwright contra http://localhost:8080: los 4 escenarios del chat y la consola
make test-e2e       # demos, concurrencia (50 pares simultáneos), reproducibilidad (10 corridas), métricas
make traceability   # regenera TRACEABILITY.md; falla si algún FR no tiene test
make metrics        # reporte: rechazos por auto, falsos OK, mismatches por tipo, casos con llave cotizada
```

Cada test que cubre un requisito lleva `@pytest.mark.req("FR-xxx")` o, en Playwright, un tag `@FR-xxx`;
[TRACEABILITY.md](TRACEABILITY.md) se genera a partir de esos marcadores.

La calidad del LLM se mide, no se supone: `make eval` corre el set de [eval/](eval/) contra el gateway
con Ollama y falla si quedan menos de 85% de campos correctos o algún JSON inválido.

```bash
LLM_MODE=ollama make up
make eval
```

Para regrabar las respuestas del LLM: `LLM_MODE=record make up && make demo-all`.

## Datos

Todo es sintético: los documentos llevan la marca "ESPÉCIMEN DE PRUEBA — DATOS FICTICIOS"
([fixtures/documents/](fixtures/documents/), generados con `scripts/make_documents.py`) y los
proveedores (Buró, consulta vehicular, cotizador de llave) son simulados con fixtures. No hay datos
reales ni secretos; `.env.example` solo trae los valores locales del compose.
