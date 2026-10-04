# Contratos entre servicios

Estos documentos describen las interfaces HTTP de la feature 001. La fuente de verdad son los
modelos Pydantic de `packages/contracts`; FastAPI genera el OpenAPI de cada servicio a partir de
ellos y no se escribe OpenAPI aparte (input de plan).

| Servicio | Quién lo llama | Documento | Módulo en `contracts` |
|---|---|---|---|
| `agent` (canal) | cliente / guiones de demo | [agent-channel.md](./agent-channel.md) | `contracts.channel` |
| `actions_api` | `agent`, asesor | [actions-api.md](./actions-api.md) | `contracts.actions`, `contracts.case` |
| `llm_gateway` | `agent`, `doc_intel` | [llm-gateway.md](./llm-gateway.md) | `contracts.llm` |
| `doc_intel` | `actions_api` | [doc-intel.md](./doc-intel.md) | `contracts.documents` |

```text
cliente/demo ──HTTP──▶ agent ──HTTP──▶ actions_api ──HTTP──▶ doc_intel ──HTTP──▶ llm_gateway ──▶ Ollama (host)
                         └──────────────HTTP──────────────────────────────────────▶ llm_gateway
```

## Convenciones comunes

- JSON UTF-8; montos como string decimal (`"12500.00"`); fechas ISO 8601.
- Errores con forma `{"error": {"code": "<snake_case>", "message": "<es>", "details": {...}}}`.
- `409` para `case_busy`, `version_conflict` e `idempotency_mismatch`; `403` para `forbidden`;
  `422` para entrada inválida; `502` para fallas de un servicio aguas abajo.
- Ningún servicio importa código de otro: solo `contracts` (Principio III, R-20).
- Los textos de documentos y mensajes viajan siempre como campos de datos, nunca concatenados a
  instrucciones (Principio X).
