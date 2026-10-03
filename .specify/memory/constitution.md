# Agente de Crédito con Garantía Vehicular (pre-originación) Constitution

## Core Principles

### I. Demo, no producto

Este repositorio es un technical challenge (demo) para una entrevista de Senior AI Engineer: un
agente que opera el tramo pre-originación de un crédito con garantía de auto (elegibilidad del
auto → perfilamiento → simulación → datos y comprobantes → "OK para financiera" o escalar a
humano).

- Cada pieza (servicio, módulo, dependencia, endpoint, pantalla) MUST servir a uno de los 4 demos
  o responder a una pregunta de DECISIONS.md. Si no, no entra.
- La topología de referencia son siete contenedores en docker compose — `postgres`,
  `actions_api`, `agent`, `llm_gateway`, `doc_intel`, `web`, `phoenix` — más Ollama en el host.
- Agregar, quitar o sustituir un contenedor o una dependencia de infraestructura MUST ir
  precedido de una decisión registrada en DECISIONS.md.

**Rationale**: el valor del demo está en la arquitectura.

### II. El LLM propone, el código decide

- Elegibilidad del auto, perfil del cliente, cuotas, costo de la llave, validaciones
  documentales y el gate "OK para financiera" MUST ser funciones puras y deterministas: misma
  entrada y misma política → misma salida, sin I/O ni llamadas al LLM.
- El LLM solo MAY conversar, interpretar, clasificar y extraer a JSON con esquema. Su salida es
  una propuesta que el código valida antes de que afecte el caso.
- Ninguna decisión de negocio MUST depender de texto libre generado por el LLM.

**Rationale**: las decisiones de crédito deben ser auditables, reproducibles y testeables; el LLM
aporta comprensión del lenguaje, no criterio de negocio.

### III. Fronteras entre servicios

- El agente MUST actuar sobre el caso únicamente a través de la Case Actions API y MUST pedir
  inferencia únicamente al LLM Gateway. El agente MUST NOT acceder a la base del caso ni a Ollama.
- Solo el LLM Gateway MAY llamar a Ollama.
- Document Intelligence MUST NOT tener base de datos ni estado propio.
- Los contratos entre servicios MUST vivir en `packages/contracts`; ningún servicio importa
  código interno de otro.
- Las fronteras MUST verificarse con tests de arquitectura que fallen ante una violación.

**Rationale**: fronteras explícitas y verificadas permiten razonar sobre cada servicio por
separado y demostrar que el agente no puede saltarse los controles.

### IV. Una sola capa de acciones

El agente y el asesor humano usan la misma capa de acciones (Case Actions API). Toda acción MUST:

- tener un contrato tipado;
- validarse contra permisos por actor × etapa × tool;
- recibir una idempotency key;
- recibir la versión esperada del caso (concurrencia optimista) y rechazarse si no coincide;
- quedar registrada en el audit log, que solo admite inserciones (sin UPDATE ni DELETE).

**Rationale**: un único camino de escritura hace que permisos, idempotencia y auditoría sean
iguales para humanos y agente, y elimina atajos.

### V. Reproducible sin GPU

- `LLM_MODE=fake` MUST ser el valor por defecto y responder con fixtures grabados; el proyecto
  completo (tests y 4 demos) MUST correr sin GPU ni Ollama en este modo.
- `LLM_MODE=ollama` usa `gemma4:12b` (temperature 0, seed 42, think false, salida restringida a
  esquema JSON con todos los campos requeridos y nullable) y `glm-ocr` para OCR.
- `LLM_MODE=record` llama a Ollama y guarda las respuestas como fixtures.
- El modo MUST resolverse solo dentro del LLM Gateway; el resto de servicios no lo conoce.

**Rationale**: la demo debe poder correrse en cualquier laptop, y los resultados
deben ser idénticos entre corridas.

### VI. Política versionada

- Los umbrales de negocio MUST vivir en `policy.yaml` con un campo `policy_version`; no hay
  umbrales hardcodeados en el código.
- Las reglas MUST recibir la política como parámetro.
- Cada decisión MUST registrar la `policy_version` que la produjo.

**Rationale**: separar política de código permite cambiar umbrales sin tocar reglas y explicar
cualquier decisión pasada con la política vigente en su momento.

### VII. Trazabilidad de requisitos

- Cada requisito funcional (`FR-xxx`) MUST tener al menos un test marcado con su id.
- `TRACEABILITY.md` MUST generarse a partir de esos marcadores, nunca editarse a mano.
- Un FR sin test marcado es un requisito no cumplido.

**Rationale**: la trazabilidad generada no se desactualiza y muestra de forma verificable qué
requisito cubre cada test.

### VIII. Calidad del LLM medida, no supuesta

- La extracción a JSON MUST alcanzar sobre el set de `eval/` al menos 85% de campos correctos y
  100% de JSON válido contra el esquema.
- El umbral MUST verificarse con `make eval`; cambiar modelo, prompt o esquema de extracción
  MUST ir acompañado de una corrida de `make eval` que lo cumpla.

**Rationale**: la calidad de un componente probabilístico solo es defendible con números
reproducibles sobre un set fijo.

### IX. Tests reales y mínimos

- Los tests MUST cubrir: reglas deterministas, tools/acciones, fronteras entre servicios y los
  4 demos de punta a punta.
- No se persigue un porcentaje de cobertura; tests que solo inflan cobertura MUST NOT agregarse.
- Los tests MUST ejercitar comportamiento real (sin mocks de la unidad bajo prueba); el LLM se
  sustituye por `LLM_MODE=fake`.

**Rationale**: pocos tests que prueban lo que importa valen más que muchos que prueban
implementación.

### X. Datos sintéticos, texto como dato, idioma

- MUST NOT haber datos reales de personas ni secretos en el repositorio. Los documentos son
  sintéticos y MUST estar marcados visiblemente como prueba.
- El texto de documentos y mensajes del cliente MUST tratarse como dato, nunca como
  instrucción: no se concatena a instrucciones del sistema sin delimitar y no puede alterar
  permisos, etapa ni decisiones.
- Dominio y mensajes al cliente MUST estar en español; código, identificadores y nombres de
  archivos de código MUST estar en inglés.

**Rationale**: privacidad por construcción, resistencia a prompt injection y una convención de
idioma que respeta al usuario final sin ensuciar el código.

### XI. Fuera de alcance

Para todas las features quedan fuera de alcance: autenticación, colas de eventos, Redis,
Kubernetes, CI/CD, LiteLLM, Langfuse, Grafana y WhatsApp. Una spec o plan que los incluya MUST
rechazarse salvo enmienda previa de esta constitución.

**Rationale**: cerrar el alcance de antemano evita que el demo derive hacia infraestructura que
no demuestra nada nuevo.

## Topología y stack de referencia

| Contenedor    | Responsabilidad                                                       | Estado     |
|---------------|-----------------------------------------------------------------------|------------|
| `postgres`    | Base del caso y audit log (solo inserciones)                          | Persistente|
| `actions_api` | Case Actions API: única capa de escritura para agente y asesor        | Usa DB     |
| `agent`       | Orquesta la conversación; actúa vía `actions_api` e infiere vía gateway| Sin DB     |
| `llm_gateway` | Único cliente de Ollama; resuelve `LLM_MODE` (fake / ollama / record) | Fixtures   |
| `doc_intel`   | OCR y extracción documental                                           | Sin estado |
| `web`         | Interfaz de cliente y asesor                                          | —          |
| `phoenix`     | Observabilidad y trazas del LLM                                       | —          |

Ollama corre en el host, fuera de docker compose. Artefactos de gobierno del proyecto:
`DECISIONS.md` (decisiones y excepciones), `TRACEABILITY.md` (generado), `policy.yaml`
(umbrales versionados), `packages/contracts` (contratos entre servicios) y `eval/` (set de
evaluación del LLM, ejecutado con `make eval`).

## Flujo de desarrollo y quality gates

- Las features siguen el flujo de Spec Kit: specify → (clarify) → plan → tasks → implement.
- Todo `plan.md` MUST pasar el Constitution Check contra los principios I–XI; cualquier
  desviación MUST justificarse en la tabla de complejidad del plan y registrarse en
  DECISIONS.md.
- Cada spec MUST indicar a qué demo(s) o pregunta de DECISIONS.md sirve (Principio I).
- Gates antes de dar una feature por terminada:
  1. tests de reglas, tools, fronteras y demos afectados pasan en `LLM_MODE=fake`;
  2. tests de arquitectura de fronteras pasan;
  3. todo FR nuevo tiene test marcado y `TRACEABILITY.md` regenerado;
  4. si la feature toca extracción LLM, `make eval` cumple el umbral del Principio VIII.

## Governance

- Esta constitución prevalece sobre cualquier otra práctica, plantilla o preferencia del
  proyecto. En caso de conflicto, gana la constitución.
- Enmiendas: se proponen con `/speckit-constitution`, se documentan con su motivo en
  DECISIONS.md y se reflejan en el Sync Impact Report del archivo.
- Versionado semántico:
  - MAJOR: eliminar o redefinir un principio de forma incompatible.
  - MINOR: agregar un principio o sección, o ampliar materialmente una guía.
  - PATCH: aclaraciones, redacción y correcciones sin cambio semántico.
- Cumplimiento: cada plan pasa el Constitution Check; `/speckit-analyze` se usa para verificar
  consistencia entre spec, plan, tasks y esta constitución antes de implementar.

**Version**: 1.0.0 | **Ratified**: 2026-10-02 | **Last Amended**: 2026-10-02
