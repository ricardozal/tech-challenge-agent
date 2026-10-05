# Demo 3 · Validación documental fallida

Laura declaró un ingreso de 20,000 al mes, pero el primer recibo de nómina muestra 14,000. La validación de ingreso
(±10%, mismo período y moneda) falla y el caso no puede llegar a OK. Las etapas 0 a 2 son iguales a las del
[happy path](1-happy-path.md) y aquí se resumen.

## 3A · Corrección: la clienta envía el recibo correcto

`make demo-document-correction` · guion `fixtures/scenarios/document_correction.yaml`

```mermaid
sequenceDiagram
    autonumber
    actor C as Cliente (Laura)
    participant A as agent
    participant L as llm_gateway
    participant API as actions_api
    participant D as doc_intel

    Note over C,D: etapas 0 a 2 como en el happy path:<br/>elegible, perfil asignado, opción 1 elegida
    A-->>C: "Envíame una foto de tu identificación oficial (INE o pasaporte)."
    C->>A: identificación
    A->>API: submit_document
    Note over API: nombre ✓ · vigencia ✓
    A-->>C: "Envíame tu comprobante de ingresos más reciente..."

    rect rgb(255, 227, 227)
    C->>A: recibo de nómina con 14,000 al mes
    A->>API: submit_document
    API->>D: /v1/documents/extract
    D->>L: /v1/ocr + /v1/extract
    D-->>API: ingreso neto, período y confianza por campo
    Note over API: ingreso: mismatch (14,000 vs 20,000 declarados)<br/>intento 1 de 2 · gate no pasa
    API-->>A: validación income: mismatch
    A->>L: /v1/reply (documento, campo y montos)
    A-->>C: "$14,000.00 al mes no coincide con los $20,000.00" + vuelve a pedir<br/>"Envíame tu comprobante de ingresos más reciente..."
    end

    rect rgb(235, 251, 238)
    C->>A: recibo de nómina correcto (20,000 al mes)
    A->>API: submit_document
    Note over API: ingreso ✓ · tipo de comprobante ✓ · nombre ✓ · vigencia ✓
    A-->>C: "¿Me envías tu comprobante de domicilio?"
    C->>A: comprobante de domicilio
    A->>API: submit_document
    Note over API: domicilio ✓ · vigencia ✓
    A-->>C: "Envíame la factura del auto."
    C->>A: factura
    A->>API: submit_document
    Note over API: titularidad del vehículo ✓
    API->>API: evaluate_gate (actor system) → ok_for_lender
    A-->>C: respuesta final · el chat muestra el resultado OK para financiera
    end
```

**Resultado:** status `ok_for_lender`. La validación de ingreso queda auditada dos veces: primero como mismatch y
después como aprobada con el documento nuevo.

## 3B · Escalación: el recibo no cuadra tres veces y un asesor resuelve

`make demo-document-escalation` · guion `fixtures/scenarios/document_escalation.yaml` · resolución:
`make advisor-verify CASE=<id> KEY=income JUSTIFICATION="..."` o la consola `/asesor`

```mermaid
sequenceDiagram
    autonumber
    actor C as Cliente (Laura)
    participant A as agent
    participant API as actions_api
    participant D as doc_intel
    actor S as Asesor (/asesor)

    Note over C,S: etapas 0 a 2 como en el happy path
    C->>A: identificación · comprobante de domicilio · factura
    A->>API: submit_document (×3)
    Note over API: nombre, domicilio, vigencias y titularidad ✓<br/>gate: falta el comprobante de ingresos

    rect rgb(255, 227, 227)
    loop intentos 1 y 2 (máximo de correcciones de la política: 2)
        C->>A: recibo de nómina con 14,000 al mes
        A->>API: submit_document
        API->>D: /v1/documents/extract
        Note over API: ingreso: mismatch · se pide corrección
        A-->>C: el ingreso no coincide · pide de nuevo el comprobante
    end
    C->>A: recibo de nómina con 14,000 al mes (tercer intento)
    A->>API: submit_document
    Note over API: ingreso: mismatch por tercera vez
    API->>API: escalate (actor system · motivo mismatch_persisted)
    Note over API: ticket con motivo, evidencia (documentos y campos con<br/>confianza), resumen y acción sugerida · status escalated
    API-->>A: status escalated
    A-->>C: avisa que su caso pasó a revisión de un asesor
    Note over A: el agente queda en pausa:<br/>los permisos no le dejan avanzar un caso escalado
    end

    rect rgb(255, 244, 230)
    S->>API: GET /escalations (bandeja) y detalle del ticket
    API-->>S: motivo, resumen, acción sugerida, evidencia y auditoría
    Note over S: confirma el ingreso por llamada con el empleador
    S->>API: verify_validation_manually (actor advisor · income · justificación)
    Note over API: validación income: passed con origen manual · auditada
    API->>API: evaluate_gate (actor system)
    Note over API: todas las validaciones passed → ok_for_lender
    API-->>S: ok_for_lender
    end
```

**Resultado:** status `escalated` y, después de la acción del asesor, `ok_for_lender`. El asesor actúa con las mismas
tools que el agente y el gate lo vuelve a evaluar el sistema. El asesor también podría pedir corrección
(`request_correction`), rechazar (`reject_case`) o regresar el caso al agente (`return_to_agent`).
