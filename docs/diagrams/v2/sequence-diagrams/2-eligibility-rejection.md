# Demo 2 · Rechazo por elegibilidad

`make demo-eligibility-rejection` · guion `fixtures/scenarios/eligibility_rejection.yaml`

Jorge declara que el auto está a nombre de su esposa ("yo lo manejo diario" es un distractor: manejarlo no es ser
titular). La regla rechaza por lo declarado, sin consultar al proveedor vehicular ni al Buró, y el rechazo queda
auditado con su motivo.

```mermaid
sequenceDiagram
    autonumber
    actor C as Cliente (Jorge)
    participant A as agent
    participant L as llm_gateway
    participant API as actions_api
    participant P as Proveedores simulados

    C->>A: POST /cases
    A->>API: create_case
    A-->>C: saludo + "¿Me compartes tu nombre completo?"

    rect rgb(231, 245, 255)
    Note over C,P: 0 · Elegibilidad del auto
    C->>A: "Hola, soy Jorge Ramírez Luna"
    A->>L: /v1/extract (esquema eligibility)
    A->>API: append_message + update_declared_data (nombre)
    A-->>C: "¿Qué auto es? Dime marca, modelo y año."
    C->>A: "Es un Nissan Versa 2018"
    A->>API: update_declared_data (marca, modelo, año)
    A-->>C: "¿El auto está a tu nombre?"
    C->>A: "está a nombre de mi esposa pero yo lo manejo diario"
    A->>L: /v1/extract (esquema eligibility)
    L-->>A: proporcionar_datos · auto_a_nombre_propio false
    A->>API: update_declared_data (a nombre propio: no)
    A->>API: evaluate_eligibility
    Note over API: regla: titular ≠ cliente → rechazo<br/>origen: declarado · no consulta proveedores
    Note over API,P: sin consulta vehicular ni Buró
    API-->>A: accepted · status rejected · motivo owner_mismatch
    Note over API: decisión y evento vehicle_rejected en auditoría<br/>con policy_version
    A->>L: /v1/reply (status rejected + motivo)
    A-->>C: explica que no se puede continuar y el motivo:<br/>el auto no está a su nombre
    end
```

**Resultado:** status `rejected` en la etapa de elegibilidad. El agente no puede revertirlo: no hay tool que le
permita reabrir un caso rechazado.
