# Contrato: comandos y compose

Comandos que ve la persona que hace o mantiene la demo. Todos en español en su salida; códigos de
salida estables para usarlos en pruebas. Decisiones O-01, O-11, O-12, O-14.

## Cambio de modo

```bash
make up                    # LLM_MODE=fake (por defecto): respuestas grabadas, sin GPU
LLM_MODE=ollama make up    # modelos reales: gemma4:12b y glm-ocr en Ollama del host
LLM_MODE=record make up    # modelos reales + grabación en fixtures/llm/_recording/
```

Ningún otro archivo cambia (FR-076, SC-017). En `ollama`/`record`, si falta un modelo, `make up`
falla porque el healthcheck de `llm_gateway` responde 503 con el modelo faltante (O-15).

## `make record`

Requiere el stack en `LLM_MODE=record`.

```text
$ make record
happy_path             OK      18 respuestas grabadas → fixtures/llm
eligibility_rejection  OK       7 respuestas grabadas → fixtures/llm
document_correction    OK      22 respuestas grabadas → fixtures/llm
document_escalation    FALLA   paso 14 (upload laura_payslip_bad.png): status esperado 'escalated', obtenido 'active'
                               se descartan 21 respuestas; las vigentes no cambian
no_spare_key           OK       9 respuestas grabadas → fixtures/llm
4 de 5 guiones grabados
```

| Código | Significado |
|---|---|
| 0 | todos los guiones llegaron a su resultado y se promovieron |
| 1 | al menos un guion falló; los demás sí se promovieron |
| 2 | el gateway no está en `LLM_MODE=record` o no responde |

Opciones: `make record ONLY="happy_path no_spare_key"` limita los guiones.

## `make fixtures-status`

Requiere el stack en `LLM_MODE=fake`. Reinicia el contador del gateway, corre los 5 guiones y
reporta el origen de cada respuesta usada.

```text
$ make fixtures-status
guion                  auténticas  sembradas  faltantes
happy_path                     18          0          0
…
total                          77          0          0
fixtures sin uso en los demos: 3 (make fixtures-status PRUNE=1 para borrarlos)
```

Con respuestas sembradas o faltantes, cada una se lista con su guion y paso:

```text
  · no_spare_key · paso 9 (say 'Me quedo con la opción 1'): 1 respuesta faltante en reply
```

| Código | Significado |
|---|---|
| 0 | ninguna respuesta sembrada ni faltante |
| 1 | hay sembradas o faltantes (se listan por guion y paso) |
| 2 | el gateway no está en `fake` o no responde |

## `make eval`

Requiere el stack en `LLM_MODE=ollama` (o `record`, que también llama al modelo real).

```text
$ make eval
M01   2/2     4.1s  Afirmación directa.
…
D05   6/7    15.2s  El propietario es el receptor, no el emisor; …
mensajes:   70/75 = 93.3%   documentos: 33/39 = 84.6%
campos correctos: 103/114 = 90.4% (mínimo 85%) · JSON válido: 100.0% (mínimo 100%)
modelo gemma4:12b · esquema v4 · modo ollama · mediana mensaje 6.2s
PASA · resultados en eval/resultados/gate-2026-10-05_101500.json
```

(Las cifras del ejemplo son ilustrativas.)

| Código | Significado |
|---|---|
| 0 | campos correctos ≥ 85% del total y JSON válido = 100% |
| 1 | no cumple; se listan los casos con JSON inválido o con campos fallidos |
| 2 | el gateway está en `fake` o no responde (no hay medición) |

El archivo `eval/resultados/gate-*.json` conserva el formato actual (`summary`, `rows`) y agrega a
`summary`: `model`, `prompt_version`, `by_type` (`{"mensaje": {"correct", "fields", "pct"},
"documento": {...}}`), `median_seconds` por tipo y `failed_cases`.

## Pruebas

```bash
make test        # pytest por defecto: excluye @pytest.mark.ollama
make test-e2e    # e2e contra compose en fake (incluye trazas y fixtures-status)
make test-ollama # solo @pytest.mark.ollama (modo real, demos y gate); requiere LLM_MODE=ollama
```

`pyproject.toml`: marcador `ollama: needs Ollama with gemma4:12b and glm-ocr (LLM_MODE=ollama)` y
`addopts = "--import-mode=importlib -m 'not ollama'"`.

## Compose

```yaml
  phoenix:
    image: arizephoenix/phoenix:version-20.19.0
    environment:
      PHOENIX_WORKING_DIR: /mnt/data
    volumes:
      - phoenix_data:/mnt/data
    ports:
      - "6006:6006"
    # healthcheck: GET http://localhost:6006/healthz con el intérprete de la imagen (O-01)
```

- `agent`, `llm_gateway` y `doc_intel` reciben `PHOENIX_COLLECTOR_ENDPOINT: http://phoenix:6006`;
  ninguno declara `depends_on: phoenix`.
- `actions_api` no recibe la variable (solo propaga contexto, O-06).
- `llm_gateway` recibe `FIXTURES_RECORD_DIR`.
- `make up` arranca 7 contenedores; la consola queda en `http://localhost:6006`.
- `tests/architecture/test_compose.py` pasa de "subconjunto de la 002" a la topología completa de
  la constitución y verifica qué servicios conocen `PHOENIX_COLLECTOR_ENDPOINT`.
