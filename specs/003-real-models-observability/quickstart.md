# Quickstart: Modelos reales y observabilidad

Guía para validar la feature de punta a punta. Contratos en [contracts/](./contracts/); decisiones
en [research.md](./research.md).

## Requisitos

- Docker con compose; `uv` para los scripts.
- Para modo real, grabación y medición: Ollama en el host con los modelos instalados.

```bash
ollama pull gemma4:12b
ollama pull glm-ocr
```

## 1 · Modo por defecto con trazas (sin GPU)

```bash
make up                         # 7 contenedores, LLM_MODE=fake
make demo-happy-path
open http://localhost:6006      # consola de Phoenix, proyecto tech-challenge-agent
```

**Esperado**: en Phoenix, la vista de sesiones muestra el caso del demo; cada turno es una traza
con raíz `turn`, nodos del grafo en orden, tools con su desenlace y spans `LLM` marcados
`replay=true` con su origen (FR-085…FR-089). Antes de grabar, el origen es `seeded` y las
respuestas al cliente salen de plantilla (`missing`).

## 2 · Modo real

```bash
make down && LLM_MODE=ollama make up
make demo-all REPEAT=3
```

**Esperado**: los 5 guiones terminan con su resultado en las 3 corridas (FR-078, SC-018). En el chat
(`http://localhost:8080/chat`) un texto libre fuera del guion, p. ej. "es un Nissan Versa 2020, lo compré de agencia",
se interpreta (FR-079). En Phoenix, los spans `LLM` muestran tokens reales, latencia y
`replay=false`.

Modelo faltante: con `glm-ocr` desinstalado, `make up` falla y `curl -s localhost:8002/health`
responde 503 con `missing_models: ["glm-ocr"]` (FR-084).

## 3 · Grabar respuestas auténticas

```bash
make down && LLM_MODE=record make up
make record                     # exit 0 si los 5 guiones se promovieron
git status fixtures/llm         # cambios revisables; _recording/ queda ignorado
```

**Esperado**: el resumen por guion de [commands.md](./contracts/commands.md#make-record); los
archivos promovidos tienen `origin: "recorded"`, latencia y tokens (FR-080, FR-081).

## 4 · Reproducir sin GPU con respuestas auténticas

```bash
make down && make up            # vuelve a LLM_MODE=fake
make fixtures-status            # exit 0: 0 sembradas, 0 faltantes
make demo-all REPEAT=10
```

**Esperado**: los 5 guiones terminan igual en las 10 repeticiones y sus mensajes coinciden con la
grabación (FR-082, SC-019). En Phoenix, los spans `LLM` muestran `fixture_origin=recorded` con la
latencia y los tokens originales.

## 5 · Consola apagada

```bash
docker compose stop phoenix
make demo-all
docker compose start phoenix
```

**Esperado**: los 5 guiones terminan igual; los servicios solo registran que no pudieron exportar
(FR-092, SC-022).

## 6 · Medición de calidad

```bash
make down && LLM_MODE=ollama make up
make eval                       # exit 0 si ≥ 85% de campos y 100% JSON válido
```

**Esperado**: resultado por caso, desglose por mensajes y documentos, modelo, esquema v4 y modo, y
`eval/resultados/gate-*.json` nuevo (FR-094…FR-097). La corrida se registra en `DECISIONS.md`
("Calidad del LLM") con la mediana por mensaje antes (12.8 s) y después de los esquemas por etapa.

Con el stack en `fake`, `make eval` sale con 2 y no mide (FR-098).

## 7 · Pruebas

```bash
make test-arch                  # topología de 7 contenedores y variables por servicio
make test && make test-e2e      # fake: trazas en Phoenix, fixtures-status, consola apagada
LLM_MODE=ollama make up && make test-ollama   # modo real: demos, texto libre y gate
make traceability               # FR-076…FR-098 con prueba marcada
```
