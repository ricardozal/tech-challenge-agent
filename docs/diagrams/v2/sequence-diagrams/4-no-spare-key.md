# Demo 4 · Sin segunda llave

`make demo-no-spare-key` · guion `fixtures/scenarios/no_spare_key.yaml`

María Fernanda tiene una sola llave. No es un rechazo: `evaluate_eligibility` cotiza la reposición con el proveedor
de llaves ($2,400 para un Kia Rio 2021) y ese costo entra al plan de pagos de la simulación. Es independiente, así
que su comprobante de ingresos es un estado de cuenta.

```mermaid
sequenceDiagram
    autonumber
    actor C as Cliente (María Fernanda)
    participant A as agent
    participant L as llm_gateway
    participant API as actions_api
    participant D as doc_intel
    participant P as Proveedores simulados

    C->>A: POST /cases
    A->>API: create_case
    A-->>C: saludo + "¿Me compartes tu nombre completo?"

    rect rgb(231, 245, 255)
    Note over C,P: 0 · Elegibilidad del auto
    C->>A: "Buenas tardes, me llamo María Fernanda López García"
    A->>API: update_declared_data (nombre)
    C->>A: "Es un Kia Rio 2021" · "Sí, es mío" · "No tiene ningún adeudo"
    A->>API: update_declared_data (×3)
    A-->>C: "¿Tienes la segunda llave del auto?"
    C->>A: "No, solo tengo una llave"
    A->>L: /v1/extract (esquema eligibility)
    L-->>A: proporcionar_datos · segunda_llave false
    A->>API: update_declared_data (segunda llave: no)
    A->>API: evaluate_eligibility
    API->>P: consulta vehicular
    P-->>API: a nombre de María · sin gravamen
    Note over API: regla: elegible, sin segunda llave → cotizar, no rechazar
    API->>P: cotizador de llave (Kia Rio 2021)
    P-->>API: 2,400.00 · quote_id
    Note over API: key_quote guardado en el caso con policy_version<br/>evento key_quoted · etapa → profiling
    API-->>A: accepted · key_quote 2,400.00
    A-->>C: "¿Cuál es tu domicilio, con código postal?"
    end

    rect rgb(243, 240, 255)
    Note over C,P: 1 · Perfilamiento
    C->>A: "Calle Roble 18, Col. Jardines, Querétaro, CP 76020"
    A->>API: update_declared_data
    C->>A: "Trabajo por mi cuenta y me depositan unos 24 mil al mes"
    A->>API: update_declared_data (independiente, 24,000 mensual)
    C->>A: "Sí, los autorizo"
    A->>API: record_bureau_consent + run_credit_check
    API->>P: Buró de Crédito (score)
    Note over API: banda por score → monto máximo, tasa y plazo
    end

    rect rgb(235, 251, 238)
    Note over C,P: 2 · Simulación
    A->>API: simulate_options
    Note over API: el costo de la llave entra al monto financiado<br/>y a la cuota de cada opción
    A-->>C: opciones con la llave incluida en el plan + "¿Cuál opción prefieres?"
    C->>A: "Me quedo con la opción 1"
    A->>API: select_option · etapa → documents
    end

    rect rgb(255, 249, 219)
    Note over C,P: 3 · Datos y comprobantes
    C->>A: identificación
    A->>API: submit_document
    Note over API: nombre ✓ · vigencia ✓
    C->>A: estado de cuenta
    A->>API: submit_document
    API->>D: /v1/documents/extract
    Note over API: ingreso (depósitos del mes vs 24,000) ✓<br/>tipo: estado de cuenta aceptado para independiente ✓<br/>nombre ✓ · vigencia ✓
    C->>A: comprobante de domicilio
    A->>API: submit_document
    Note over API: domicilio ✓ · vigencia ✓
    C->>A: factura
    A->>API: submit_document
    Note over API: titularidad del vehículo ✓
    API->>API: evaluate_gate (actor system) → ok_for_lender
    A-->>C: respuesta final · el chat muestra el resultado OK para financiera
    end
```

**Resultado:** status `ok_for_lender`, con la cotización de la llave en el caso y en el plan de pagos. El caso cuenta
en la métrica "casos con llave cotizada".
