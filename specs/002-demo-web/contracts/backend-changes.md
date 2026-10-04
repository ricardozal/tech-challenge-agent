# Contrato: cambios en `agent`, `actions_api` y el compose

La feature 002 no agrega tools, no cambia permisos ni modelos de escritura. Solo agrega CORS, un
lector de política y el contenedor `web`.

## CORS (`agent` y `actions_api`, W-04)

| Variable | Valor por defecto | Compose |
|---|---|---|
| `WEB_ORIGINS` | `http://localhost:8080` | `${WEB_ORIGINS:-http://localhost:8080}` |

- `allow_origins` = lista de `WEB_ORIGINS` separada por comas; `allow_methods` = `GET`, `POST`;
  `allow_headers` = `Content-Type`, `Idempotency-Key` (agent), `X-Actor` (actions_api);
  `allow_credentials = false`.
- Preflight `OPTIONS` desde un origen permitido → `200` con `Access-Control-Allow-Origin` igual al
  origen. Desde otro origen → sin `Access-Control-Allow-Origin`.
- Llamadas sin `Origin` (guiones, agente → actions_api) no cambian.

## `GET /policies/{policy_version}` (`actions_api`, W-11)

Lector de solo lectura; no se audita (no es una acción).

→ `200` la política de esa versión tal como la carga `PolicyRegistry.get` (mismo modelo `Policy`
que usan las reglas):

```json
{"policy_version": "2026.10-v1", "documents": {"min_field_confidence": "0.80", "max_age_months": {"payslip": 3}}, "…": "…"}
```

→ `404 {"detail": "policy not found"}` si la versión no existe.

## Contenedor `web` (W-03)

```yaml
web:
  build:
    context: .
    dockerfile: web/Dockerfile
    args:
      VITE_AGENT_URL: ${VITE_AGENT_URL:-http://localhost:8001}
      VITE_ACTIONS_URL: ${VITE_ACTIONS_URL:-http://localhost:8000}
  ports:
    - "8080:8080"
  depends_on:
    agent: {condition: service_healthy}
    actions_api: {condition: service_healthy}
  healthcheck: wget -qO- http://localhost:8080/ (intervalo del ancla http-health)
```

Sin `environment` de base de datos ni del LLM, sin volúmenes (W-14).
