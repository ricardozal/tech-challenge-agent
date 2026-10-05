# Demo 1 · Happy path

`make demo-happy-path` · guion `fixtures/scenarios/happy_path.yaml`

Laura tiene un auto a su nombre, sin adeudos y con las dos llaves. Pasa el perfilamiento, elige la primera opción y
envía los 4 documentos en orden. El sistema marca el caso **OK para financiera**. Los turnos abreviados siguen el
[patrón de un turno](README.md#patrón-de-un-turno-de-mensaje).

```mermaid
sequenceDiagram
    autonumber
    actor C as Cliente (Laura)
    participant A as agent
    participant L as llm_gateway
    participant API as actions_api
    participant D as doc_intel
    participant P as Proveedores simulados

    C->>A: POST /cases
    A->>API: create_case
    A->>L: /v1/reply (saludo)
    A-->>C: saludo + "¿Me compartes tu nombre completo?"

    rect rgb(231, 245, 255)
    Note over C,P: 0 · Elegibilidad del auto
    C->>A: "Hola, soy Laura Méndez Rojas"
    A->>L: /v1/extract (esquema eligibility)
    L-->>A: proporcionar_datos · nombre_completo
    A->>API: append_message + update_declared_data (nombre)
    A->>L: /v1/reply
    A-->>C: "¿Qué auto es? Dime marca, modelo y año."
    C->>A: "Tengo un Volkswagen Jetta 2019"
    A->>API: update_declared_data (marca, modelo, año)
    A-->>C: "¿El auto está a tu nombre?"
    C->>A: "Sí, está a mi nombre"
    A->>API: update_declared_data (a nombre propio)
    A-->>C: "¿El auto tiene algún adeudo, crédito o gravamen?"
    C->>A: "No, ya lo terminé de pagar"
    A->>API: update_declared_data (sin adeudos)
    A-->>C: "¿Tienes la segunda llave del auto?"
    C->>A: "Sí, tengo las dos llaves"
    A->>API: update_declared_data (segunda llave)
    A->>API: evaluate_eligibility
    API->>P: consulta vehicular (titular, gravamen, valor de referencia)
    P-->>API: a nombre de Laura · sin gravamen
    Note over API: regla de elegibilidad: elegible y con llave,<br/>no se cotiza · etapa → profiling
    API-->>A: accepted · stage profiling
    A-->>C: "¿Cuál es tu domicilio, con código postal?"
    end

    rect rgb(243, 240, 255)
    Note over C,P: 1 · Perfilamiento
    C->>A: "Av. Morelos 245, Col. Centro, Toluca, CP 50000"
    A->>API: update_declared_data (domicilio, CP)
    A-->>C: "¿Cuál es tu situación laboral y cuánto ganas?"
    C->>A: "Soy empleada y gano 20 mil al mes"
    A->>API: update_declared_data (empleada, 20,000 mensual)
    A-->>C: "¿Nos autorizas consultar tu historial en Buró de Crédito?"
    C->>A: "Sí, adelante"
    A->>API: record_bureau_consent
    A->>API: run_credit_check
    API->>P: Buró de Crédito (score)
    P-->>API: score
    Note over API: banda por score → monto máximo, tasa y plazo
    end

    rect rgb(235, 251, 238)
    Note over C,P: 2 · Simulación
    A->>API: simulate_options
    Note over API: 3 opciones (100/75/50% del máximo),<br/>cuota con IVA sobre interés
    API-->>A: opciones
    A-->>C: opciones + "¿Cuál opción prefieres?"
    C->>A: "La primera"
    A->>L: /v1/extract (esquema simulation)
    L-->>A: elegir_opcion · opcion_elegida 1
    A->>API: select_option · etapa → documents
    A-->>C: "Envíame una foto de tu identificación oficial (INE o pasaporte)."
    end

    rect rgb(255, 249, 219)
    Note over C,P: 3 · Datos y comprobantes
    C->>A: identificación
    A->>API: submit_document
    API->>D: /v1/documents/extract
    D->>L: /v1/ocr + /v1/extract
    D-->>API: identificación · campos con confianza
    Note over API: nombre ✓ · vigencia ✓ · gate: faltan documentos
    A-->>C: "Envíame tu comprobante de ingresos más reciente (recibo de nómina o estado de cuenta)."
    C->>A: recibo de nómina
    A->>API: submit_document (doc_intel lee el recibo)
    Note over API: ingreso vs declarado (±10%) ✓ · tipo de comprobante ✓<br/>nombre ✓ · vigencia ✓
    A-->>C: "¿Me envías tu comprobante de domicilio?"
    C->>A: comprobante de domicilio
    A->>API: submit_document
    Note over API: domicilio ✓ · vigencia ✓
    A-->>C: "Envíame la factura del auto."
    C->>A: factura del auto
    A->>API: submit_document
    Note over API: titularidad del vehículo ✓
    API->>API: evaluate_gate (actor system)
    Note over API: todas las validaciones passed, sin escalación abierta<br/>→ status ok_for_lender
    API-->>A: ok_for_lender
    A->>L: /v1/reply
    A-->>C: respuesta final · el chat muestra el resultado OK para financiera
    end
```

**Resultado:** status `ok_for_lender`. El "OK para financiera" lo marca el sistema (`evaluate_gate`, actor `system`),
no el agente.
