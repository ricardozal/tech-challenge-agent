# Contrato: escenarios de la web (`web/public/scenarios.json`)

Generado por `scripts/export_web_scenarios.py` (`make web-scenarios`) a partir de
`fixtures/scenarios/*.yaml` y versionado en git (W-05). No se edita a mano;
`tests/web/test_scenarios_export.py` falla si está desactualizado. Modelo en
[data-model.md](../data-model.md#escenario-de-demo-webpublicscenariosjson).

## Mapeo de escenarios

| `id` | Título | Guiones de 001 | `expected_results` |
|---|---|---|---|
| `happy_path` | Happy path | `happy_path` | `ok_for_lender` |
| `eligibility_rejection` | Rechazo por auto | `eligibility_rejection` | `rejected` |
| `document_failed` | Documento fallido | `document_correction` + `document_escalation` | `ok_for_lender`, `escalated` |
| `no_spare_key` | Sin segunda llave | `no_spare_key` | `ok_for_lender` |

`document_failed`: los pasos `say` de ambos guiones deben ser idénticos (el export falla si no lo
son); la ranura `income_proof` ofrece `laura_payslip_low.png` (`mismatch`) y `laura_payslip.png`
(`ok`). Enviar el que no cuadra tres veces escala (N = 2 en la política); enviar el correcto
después del primero termina en OK.

## Formato

```json
{
  "generated_from": ["fixtures/scenarios/happy_path.yaml", "…"],
  "scenarios": [
    {
      "id": "happy_path",
      "title": "Happy path",
      "description": "Auto elegible con segunda llave y documentos en orden: termina en OK para financiera.",
      "client_name": "Laura Méndez Rojas",
      "expected_results": ["ok_for_lender"],
      "source_scripts": ["happy_path"],
      "messages": [
        {"stage": "eligibility", "question": "¿Me compartes tu nombre completo?", "text": "Hola, soy Laura Méndez Rojas"}
      ],
      "documents": [
        {
          "slot": "income_proof",
          "question": "Envíame tu comprobante de ingresos más reciente (recibo de nómina o estado de cuenta).",
          "options": [
            {"file": "documents/laura_payslip.png", "requested_type": "payslip", "label": "Recibo de nómina", "variant": "ok"}
          ]
        }
      ]
    }
  ]
}
```

## Reglas que verifica el test del export

- El archivo versionado es igual al que produce el script.
- Cada `messages[]` tiene `stage`, `question` y `text` tomados de un paso `say` de sus guiones.
- Cada `documents[].question` es el texto de `agent.questions.DOCUMENT_QUESTIONS` de su ranura.
- Cada `options[].file` existe en `fixtures/documents/`; cada `requested_type` es un `DocumentType`.
- Los cuatro `id` existen y solo `document_failed` tiene una ranura con más de una opción.

## Documentos servidos

El Dockerfile de `web` copia `fixtures/documents/*.png` a `/documents/` del sitio. En desarrollo,
`make web-dev` los copia a `web/public/documents/` (ignorado por git).
