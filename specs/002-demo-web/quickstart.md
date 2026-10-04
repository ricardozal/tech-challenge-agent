# Quickstart: Web de demo

Guía para comprobar la feature 002 de punta a punta. Contratos en [contracts/](./contracts/) y
modelo en [data-model.md](./data-model.md).

## Prerrequisitos

- Docker con compose; Node 24 y `npm` en el host (solo para Playwright y desarrollo).
- Feature 001 funcionando: `make up && make demo-all` pasa.
- `LLM_MODE=fake` (por defecto). No hace falta GPU ni Ollama.

## Levantar

```bash
make up                 # ahora 6 contenedores: incluye web en http://localhost:8080
make ps                 # web en estado healthy
```

## Validación manual

### 1 · Chat: los cuatro escenarios (P1)

Abrir `http://localhost:8080/chat`.

| Escenario | Cómo avanzar | Resultado esperado |
|---|---|---|
| Happy path | solo sugerencias y documentos resaltados | etapas elegibilidad → perfilamiento → simulación → documentos; "OK para financiera" |
| Rechazo por auto | sugerencias | "Rechazado" · titular distinto al cliente; no llega a perfilamiento |
| Documento fallido (rama A) | en el comprobante de ingresos, primero "no cuadra", luego el correcto | "OK para financiera" |
| Documento fallido (rama B) | enviar "no cuadra" tres veces | "Escalado a asesor" · mismatch persistente |
| Sin segunda llave | sugerencias y documentos | opciones con costo de llave desglosado; "OK para financiera" |

Comprobar además:
- Mientras el agente responde aparece "escribiendo…" y no se puede enviar otro mensaje.
- Escribir `<b>hola</b>` aparece como texto literal; el agente vuelve a preguntar y la sugerencia
  sigue disponible.
- Recargar la página a mitad del caso recupera la conversación, la etapa y la sugerencia.
- "Empezar de nuevo" vuelve al selector y el siguiente caso es nuevo.

### 2 · Consola del asesor (P2)

Con un caso de "Documento fallido (rama B)" escalado, abrir `http://localhost:8080/asesor`.

1. La escalación aparece primero en la bandeja con cliente, motivo, etapa y fecha.
2. El detalle muestra resumen, acción sugerida, documentos con campos y confianza (los de baja
   confianza señalados), validaciones con su intento y el timeline completo.
3. "Verificar manualmente" la validación de ingreso con una justificación → el caso queda en
   "OK para financiera"; el timeline termina con `asesor · verify_validation_manually` y
   `sistema · evaluate_gate`.
4. Repetir el envío (doble clic) no crea una segunda acción en el timeline.
5. La pestaña del chat de ese caso pasa sola de "Escalado a asesor" a "OK para financiera"
   (sondeo cada 5 s).
6. Abrir ese caso desde "Casos", "Revocar OK" con motivo → vuelve a la bandeja como escalado.
7. Panel de métricas: las cifras coinciden con `make metrics`; el falso OK del paso 6 aparece.

## Validación automática

```bash
make web-scenarios      # regenera web/public/scenarios.json desde los guiones
make test-arch          # topología de 6 contenedores y fronteras de web (CORS: services/*/tests)
uv run pytest tests/web services/agent/tests services/actions_api/tests -k "cors or policies or scenarios_export"
make test-web           # Playwright contra http://localhost:8080 (4 escenarios + asesor)
make traceability       # FR-001…FR-075 con test; falla si falta alguno
```

Resultado esperado: todo en verde y `TRACEABILITY.md` con 75 FR con test.

## Desarrollo

```bash
WEB_ORIGINS=http://localhost:8080,http://localhost:5173 make up
make web-dev            # copia documentos de ejemplo y corre Vite en :5173
```
