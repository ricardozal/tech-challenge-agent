# Contrato: Document Intelligence (`doc_intel`)

Sin base de datos, sin volúmenes, sin estado entre llamadas (Principio III). Modelos en
`contracts.documents`.

## `POST /v1/documents/extract`

```json
{"expected_type": "identification", "mime_type": "image/png", "content_base64": "…"}
```

→ `200`:

```json
{
  "detected_type": "identification",
  "type_matches": true,
  "is_test_specimen": true,
  "fields": {
    "nombre_completo": {"value": "LAURA MÉNDEZ ROJAS", "confidence": 0.95},
    "curp": {"value": "MERL880412MMCNJR09", "confidence": 0.95},
    "vigencia": {"value": "2031-12-31", "confidence": 0.6},
    "banco": {"value": null, "confidence": 0.0}
  },
  "ocr_chars": 412
}
```

Flujo: `llm_gateway /v1/ocr` → `llm_gateway /v1/extract` (`schema_name = "documento"`, `text` =
OCR) → confianza determinista por campo (R-10) → respuesta.

- `fields` usa las llaves del esquema `documento` (`eval/esquemas.json`); `actions_api` las
  traduce con `contracts.llm.to_domain` (R-01).
- `is_test_specimen`: el OCR contiene la marca de documento de prueba ("ESPÉCIMEN DE PRUEBA",
  "DATOS FICTICIOS"…). `actions_api` registra el valor; no bloquea.
- Si el gateway falla: `502 upstream_failure`. `actions_api` reintenta según la política y, si
  sigue fallando, escala con `provider_failure` (FR-041).
