# Feature Specification: Web de demo

**Feature Branch**: `002-demo-web`

**Created**: 2026-10-04

**Status**: Draft

**Input**: User description: "Feature 002 · Web de demo. Una web sencilla con dos vistas para mostrar el agente funcionando. P1 · Chat del cliente (/chat). Una conversación tipo mensajería con el agente sobre un caso. Al iniciar se elige un escenario (happy path, rechazo por auto, documento fallido, sin segunda llave), que crea el caso con los datos de ese cliente de prueba. El usuario escribe libremente o toca sugerencias con los mensajes del guion, y puede enviar el documento de ejemplo que corresponde al paso. Siempre se ve la etapa actual del caso y, al terminar, el resultado: OK para financiera, rechazo con motivo o escalación. P2 · Consola del asesor (/adviser). Bandeja de escalaciones con motivo, resumen, evidencia (documentos y campos extraídos con su confianza) y acción sugerida; timeline del registro de acciones del caso; el asesor resuelve con las mismas acciones del agente y su acción queda registrada con actor asesor. Un panel muestra el reporte de métricas. Fuera de alcance: login, roles, diseño responsivo fino e internacionalización."

## Contexto

La feature 001 dejó el agente operando de punta a punta, pero solo se ve corriendo guiones desde
la terminal. Esta feature agrega una web sencilla para que una persona que evalúa el demo vea el
agente funcionando: del lado del cliente, una conversación tipo mensajería; del lado del asesor,
una consola donde atiende escalaciones con las mismas acciones que usa el agente y ve las métricas
del proceso.

La web no agrega reglas de negocio ni decisiones: muestra lo que el agente y el sistema ya hacen,
y el asesor actúa a través de la misma capa de acciones, con los mismos permisos, idempotencia y
registro que el agente.

**Demos a los que sirve (Principio I)**: los 4 demos de la feature 001, ahora navegables desde el
navegador. El chat recorre los demos 1–4; la consola cubre la resolución humana del demo 3 rama B
y el reporte de observabilidad (P5 de 001). Corresponde al contenedor `web` de la topología de
referencia.

**Actores**

- **Persona que hace la demo**: en el chat juega el papel del cliente de prueba del escenario; en
  la consola juega el papel del asesor.
- **Agente** y **Sistema**: los mismos de la feature 001; la web no cambia su comportamiento.

## Clarifications

### Session 2026-10-04 (plan)

- Q: ¿La consola del asesor vive en `/adviser` o en `/asesor`? → A: `/asesor`, como pide la
  entrada del plan (ruta visible al usuario, en español).
- Q: ¿"Validación" es una etapa visible? → A: No. Las etapas del caso son cuatro (elegibilidad,
  perfilamiento, simulación, documentos); la validación ocurre dentro de documentos y su avance se
  ve en el estado y en el resultado.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Chat del cliente (Priority: P1)

En la vista de chat, la persona elige uno de los cuatro escenarios de prueba (happy path, rechazo
por auto, documento fallido, sin segunda llave). Se crea un caso nuevo asociado al cliente de
prueba de ese escenario y empieza una conversación tipo mensajería con el agente. La persona puede
escribir libremente o tocar una sugerencia con el siguiente mensaje del guion; cuando el caso pide
un documento, puede enviar el documento de ejemplo que corresponde a ese paso. En todo momento ve
la etapa actual del caso y, cuando el caso termina, ve el resultado: OK para financiera, rechazo
con su motivo o escalación a un asesor.

**Why this priority**: es lo mínimo para ver el agente funcionando sin terminal. Por sí sola
permite correr los 4 demos frente a alguien.

**Independent Test**: abrir el chat, elegir cada escenario y avanzar solo con sugerencias y
documentos de ejemplo hasta el final; verificar que la etapa visible cambia en el orden esperado y
que el resultado final coincide con el del demo correspondiente.

**Acceptance Scenarios**:

1. **Given** la vista de chat sin caso abierto, **When** la persona elige un escenario, **Then** se
   crea un caso nuevo, se muestra el saludo del agente, la etapa actual (elegibilidad) y la primera
   sugerencia del guion de ese escenario.
2. **Given** un caso en curso, **When** la persona toca una sugerencia, **Then** el mensaje se
   envía como si lo hubiera escrito el cliente, aparece en la conversación, se muestra que el
   agente está respondiendo y después su respuesta, y se actualiza la etapa visible.
3. **Given** un caso en curso, **When** la persona escribe un mensaje propio y lo envía, **Then**
   el mensaje llega al agente igual que una sugerencia y la conversación continúa con su
   respuesta.
4. **Given** un caso en etapa de documentos, **When** el paso del guion corresponde a un
   documento, **Then** la persona ve el documento de ejemplo de ese paso (nombre y vista previa) y
   puede enviarlo con una sola acción; el documento aparece en la conversación y el agente
   responde con el resultado de su lectura.
5. **Given** el escenario "documento fallido", **When** llega el paso del comprobante de ingresos,
   **Then** la persona puede elegir entre reenviar el comprobante que no cuadra o enviar el
   correcto, y así recorrer la rama de corrección (termina OK) o la de escalación (termina
   escalado).
6. **Given** el escenario "happy path" o "sin segunda llave", **When** se envía el último documento
   consistente, **Then** el chat muestra el resultado "OK para financiera" de forma destacada y ya
   no ofrece sugerencias ni documentos.
7. **Given** el escenario "rechazo por auto", **When** el cliente declara que el auto está a nombre
   de otra persona, **Then** el chat muestra el resultado "Rechazado" con el motivo que registró el
   sistema.
8. **Given** un caso escalado, **When** el agente informa que un asesor tomará el caso, **Then** el
   chat muestra el resultado "Escalado a asesor" con el motivo de la escalación.
9. **Given** el escenario "sin segunda llave", **When** el agente presenta las opciones de crédito,
   **Then** la conversación muestra cada opción con el costo de la llave desglosado tal como lo
   calculó el sistema.
10. **Given** un caso terminado o en curso, **When** la persona elige empezar de nuevo, **Then** se
    abre la selección de escenarios y el siguiente caso es independiente del anterior.

---

### User Story 2 - Consola del asesor (Priority: P2)

En la vista del asesor, la persona ve una bandeja con las escalaciones abiertas. Al abrir una, ve
el ticket completo: motivo, resumen en español, evidencia (documentos del caso con sus campos
extraídos y la confianza de cada uno, validaciones y mensajes relevantes) y acción sugerida;
además, el timeline del registro de acciones del caso. Resuelve con las mismas acciones del
catálogo que usa el agente (pedir corrección, marcar una validación como verificada manualmente,
rechazar con motivo, devolver el caso al agente) y su acción aparece en el timeline con actor
asesor. Un panel muestra el reporte de métricas del proceso.

**Why this priority**: completa la historia del demo 3: lo que el agente no resuelve lo resuelve un
humano con las mismas reglas. Depende de que existan casos escalados, que el chat (P1) o los
guiones de 001 generan.

**Independent Test**: correr el demo 3 rama B (desde el chat o desde el guion de 001), abrir la
consola, encontrar la escalación en la bandeja, revisar evidencia y timeline, marcar la validación
de ingreso como verificada manualmente con justificación y comprobar que el caso llega a OK para
financiera y que el timeline muestra la acción del asesor seguida de la evaluación del sistema.

**Acceptance Scenarios**:

1. **Given** al menos un caso escalado, **When** la persona abre la consola, **Then** la bandeja
   lista cada escalación abierta con su cliente, motivo, etapa del caso y fecha, la más reciente
   primero.
2. **Given** la bandeja, **When** la persona abre una escalación, **Then** ve motivo, resumen,
   acción sugerida y evidencia: cada documento del caso con su tipo y sus campos extraídos con
   valor y confianza, señalando los campos con confianza por debajo del umbral, y cada validación
   con su resultado.
3. **Given** una escalación abierta, **When** la persona consulta el timeline, **Then** ve todas
   las acciones registradas del caso en orden cronológico, con actor, acción, etapa, resultado
   (aceptada o rechazada) y motivo.
4. **Given** una escalación con una validación fallida, **When** el asesor la marca como verificada
   manualmente con justificación, **Then** la acción se registra con actor asesor, la validación
   queda aprobada con origen manual, el sistema vuelve a evaluar el gate y la consola muestra el
   nuevo estado del caso sin que el asesor lo marque OK.
5. **Given** una escalación abierta, **When** el asesor rechaza el caso con motivo, pide una
   corrección o devuelve el caso al agente, **Then** la acción se registra con actor asesor, el
   ticket queda resuelto y desaparece de la bandeja de abiertos.
6. **Given** que el asesor intenta una acción que el sistema no permite para ese caso, **When** la
   envía, **Then** la consola muestra el motivo del rechazo en español, el caso no cambia y el
   intento aparece en el timeline como rechazado.
7. **Given** que el asesor envía dos veces la misma acción (doble clic o reintento), **When** el
   sistema la recibe, **Then** se ejecuta una sola vez.
8. **Given** que otra acción modificó el caso después de que el asesor lo abrió, **When** el asesor
   envía su acción, **Then** la consola indica que el caso cambió, muestra la versión actual y le
   deja volver a intentarlo.
9. **Given** un caso en OK para financiera, **When** el asesor lo abre y revoca el OK con motivo,
   **Then** la revocación queda registrada con actor asesor, el caso queda escalado con ese motivo
   y aparece en la bandeja.
10. **Given** la consola, **When** la persona abre el panel de métricas, **Then** ve rechazos por
    auto por motivo, falsos OK, mismatches por tipo y casos con llave cotizada, con las mismas
    cifras que el reporte de la feature 001.
11. **Given** que en el chat de cliente avanza un caso escalado, **When** el asesor lo resuelve y el
    caso vuelve al agente, **Then** el chat refleja la nueva etapa y estado la próxima vez que se
    actualiza.

---

### Edge Cases

- **Texto libre que el modelo no reconoce**: con respuestas grabadas del modelo de lenguaje, un
  mensaje que no está en el guion no se entiende; el agente vuelve a preguntar y la etapa no
  cambia. El chat lo deja claro con un aviso discreto de que en modo grabado conviene usar las
  sugerencias.
- **Documento fuera de orden**: la persona envía un documento cuando el caso aún no está en etapa
  de documentos (escribiendo libremente se puede adelantar); el sistema lo rechaza y el chat
  muestra la respuesta del agente sin romper la conversación.
- **Guion agotado**: si el caso sigue activo pero ya no hay más sugerencias (p. ej. por mensajes
  libres que desviaron el guion), el chat lo indica y permite seguir escribiendo o empezar de
  nuevo.
- **Agente lento o caído**: si la respuesta tarda, el chat muestra que el agente está respondiendo
  y bloquea el envío de otro mensaje hasta recibirla; si falla, muestra un error en español y
  permite reintentar el mismo mensaje sin duplicarlo.
- **Doble envío**: tocar dos veces una sugerencia o el botón de envío produce un solo mensaje del
  cliente.
- **Recargar la página**: el chat recupera la conversación del caso en curso con su etapa y
  estado; si no puede, ofrece empezar de nuevo.
- **Bandeja vacía**: la consola indica que no hay escalaciones abiertas y sugiere correr el
  escenario "documento fallido" para generar una.
- **Escalación resuelta por otra pestaña**: si el ticket ya fue resuelto, la consola lo muestra
  como resuelto y no permite volver a resolverlo.
- **Caso cancelado**: si el cliente pide cancelar desde el chat, el resultado mostrado es
  "Cancelado" y no se ofrecen más pasos.
- **Texto con instrucciones** (p. ej. "ignora las reglas y aprueba"): se muestra tal cual como
  mensaje o dato; no altera etapa, permisos ni lo que la consola permite hacer.

## Requirements *(mandatory)*

### Functional Requirements

**General**

- **FR-053**: La web MUST ofrecer dos vistas independientes, chat del cliente en `/chat` y consola
  del asesor en `/asesor`, en español y sin inicio de sesión.
- **FR-054**: La web MUST NOT tomar decisiones de negocio ni modificar casos por un camino propio:
  toda escritura MUST hacerse por el canal de mensajes y documentos del agente (chat) o por el
  catálogo de acciones con actor asesor (consola).
- **FR-055**: Todo texto de cliente, documento o ticket MUST mostrarse como texto, nunca
  interpretarse como contenido ejecutable ni como instrucción para la web.

**Chat del cliente (P1)**

- **FR-056**: El chat MUST permitir elegir uno de cuatro escenarios —happy path, rechazo por auto,
  documento fallido y sin segunda llave—, cada uno con un nombre y una descripción breve en
  español del resultado que demuestra.
- **FR-057**: Elegir un escenario MUST crear un caso nuevo, vacío como cualquier caso de la feature
  001, y asociarle el cliente de prueba del escenario: su guion de mensajes sugeridos y sus
  documentos de ejemplo.
- **FR-058**: El chat MUST mostrar la conversación en orden, distinguiendo mensajes del cliente,
  respuestas del agente y documentos enviados.
- **FR-059**: El chat MUST permitir enviar texto libre y MUST ofrecer como sugerencia el siguiente
  mensaje del guion según la etapa y lo que el agente acaba de preguntar; tocar una sugerencia la
  envía como mensaje del cliente.
- **FR-060**: Cuando el paso del guion sea un documento, el chat MUST ofrecer el documento de
  ejemplo correspondiente con vista previa y permitir enviarlo con una sola acción. En el escenario
  "documento fallido", en el paso del comprobante de ingresos MUST ofrecer tanto el comprobante que
  no cuadra como el correcto.
- **FR-061**: El chat MUST mostrar en todo momento la etapa actual del caso (elegibilidad,
  perfilamiento, simulación, documentos) y su estado (en curso, escalado, OK para financiera,
  rechazado, cancelado), actualizados después de cada
  respuesta del agente.
- **FR-062**: Cuando el caso llegue a un estado final o se escale, el chat MUST mostrar el
  resultado de forma destacada: "OK para financiera", "Rechazado" con su motivo, "Escalado a
  asesor" con su motivo o "Cancelado", y MUST dejar de ofrecer sugerencias y documentos (salvo
  que el caso vuelva a estar activo tras la resolución del asesor).
- **FR-063**: El chat MUST mostrar que el agente está respondiendo mientras espera, impedir un
  segundo envío durante la espera y enviar cada mensaje o documento una sola vez aunque se toque
  dos veces o se reintente tras un error.
- **FR-064**: El chat MUST permitir empezar de nuevo con otro escenario en cualquier momento, y
  MUST recuperar la conversación del caso en curso al recargar la página.

**Consola del asesor (P2)**

- **FR-065**: La consola MUST mostrar una bandeja con las escalaciones abiertas (cliente, motivo,
  etapa y fecha), la más reciente primero, y permitir actualizarla.
- **FR-066**: Al abrir una escalación, la consola MUST mostrar motivo, resumen, acción sugerida y
  evidencia: documentos del caso con tipo solicitado y detectado, campos extraídos con valor y
  confianza (señalando los que están por debajo del umbral de la política), validaciones con su
  resultado y número de intento, y los mensajes relevantes.
- **FR-067**: La consola MUST mostrar el timeline completo del registro de acciones del caso en
  orden cronológico, con actor, acción, etapa, resultado (aceptada o rechazada), motivo y fecha.
- **FR-068**: La consola MUST permitir al asesor ejecutar, sobre el caso escalado, las acciones
  del catálogo de la feature 001 que el sistema le permite: pedir corrección, marcar una validación
  como verificada manualmente (con justificación obligatoria), rechazar con motivo (obligatorio),
  devolver el caso al agente y cancelar; y revocar el OK con motivo sobre un caso en OK para
  financiera.
- **FR-069**: Cada acción del asesor MUST ejecutarse con actor asesor, una clave de idempotencia
  por intento y la versión del caso que el asesor está viendo; un reintento del mismo intento
  MUST NOT ejecutarse dos veces.
- **FR-070**: Si el sistema rechaza una acción del asesor (permiso, versión del caso o validación
  de entrada), la consola MUST mostrar el motivo en español, recargar el caso y permitir
  reintentar; el intento rechazado MUST verse en el timeline.
- **FR-071**: Después de cada acción aceptada, la consola MUST mostrar el estado, la etapa, el
  ticket y el timeline actualizados, incluidas las acciones que el sistema ejecutó como
  consecuencia (p. ej. la evaluación del gate tras una verificación manual).
- **FR-072**: La consola MUST permitir abrir cualquier caso existente (no solo los escalados) para
  ver su detalle y timeline, de modo que el asesor pueda revocar el OK de un caso en OK para
  financiera.
- **FR-073**: La consola MUST incluir un panel con el reporte de métricas de la feature 001
  (rechazos por auto por motivo, falsos OK por motivo de revocación, mismatches por tipo y casos
  con llave cotizada), con las mismas cifras que ese reporte y actualizable a petición.

**Reproducibilidad**

- **FR-074**: Los 4 escenarios MUST poder completarse desde el chat, usando solo sugerencias y
  documentos de ejemplo, con respuestas grabadas del modelo de lenguaje y sin acelerador gráfico,
  terminando en el mismo resultado que el demo correspondiente de la feature 001.
- **FR-075**: Cada escenario del chat MUST tener una prueba de punta a punta que lo recorra como lo
  haría una persona y verifique el resultado mostrado; la resolución de una escalación desde la
  consola MUST tener una prueba equivalente.

### Key Entities *(include if feature involves data)*

- **Escenario de demo**: nombre, descripción, cliente de prueba, resultado esperado y guion de
  pasos. Corresponde a los guiones de la feature 001.
- **Paso del guion**: mensaje sugerido (con la etapa y la pregunta del agente a la que responde) o
  documento de ejemplo (con el tipo solicitado); en "documento fallido" un paso puede ofrecer más
  de un documento.
- **Documento de ejemplo**: documento sintético marcado como prueba, con su vista previa.
- **Sesión de chat**: caso en curso y escenario elegido; permite recuperar la conversación al
  recargar.
- Caso, mensaje, documento, campo extraído, validación, ticket de escalación, acción registrada y
  reporte de métricas: los mismos de la feature 001; la web solo los muestra o actúa sobre ellos
  mediante el catálogo de acciones.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-010**: Una persona que no conoce el proyecto completa cualquiera de los 4 escenarios desde
  el chat, solo con sugerencias y documentos de ejemplo, en menos de 3 minutos y sin instrucciones
  adicionales.
- **SC-011**: Los 4 escenarios terminan desde el chat con el resultado del demo correspondiente en
  10 de 10 corridas consecutivas con respuestas grabadas, en una laptop sin acelerador gráfico.
- **SC-012**: Con respuestas grabadas, cada respuesta del agente aparece en el chat en menos de 3
  segundos en el 95% de los mensajes.
- **SC-013**: Partiendo de una escalación del demo 3 rama B, una persona resuelve el caso desde la
  consola (encuentra la escalación, revisa la evidencia y marca la verificación manual) en menos de
  2 minutos, y el caso llega a OK para financiera.
- **SC-014**: El 100% de las acciones ejecutadas desde la consola aparecen en el registro de
  acciones con actor asesor, y 0 acciones se ejecutan dos veces por doble clic o reintento.
- **SC-015**: Cada cifra del panel de métricas coincide con el reporte de la feature 001 sobre el
  mismo registro de acciones.
- **SC-016**: En todo momento del chat, la etapa y el estado mostrados coinciden con los del caso
  en el sistema después de cada respuesta.

## Assumptions

- **Caso vacío y cliente de prueba**: "crear el caso con los datos del cliente de prueba" se
  interpreta como asociar el caso al guion y documentos de ese cliente; el caso nace vacío y los
  datos entran por la conversación, como fijó la feature 001 (sin datos pre-guardados). Así el
  chat ejercita exactamente el mismo flujo que los demos.
- **Escenarios = guiones de 001**: los cuatro escenarios reutilizan los guiones existentes de los
  demos. "Rechazo por auto" usa el guion de titular distinto; "documento fallido" combina las ramas
  A y B del demo 3 y la persona elige la rama al enviar el comprobante de ingresos.
- **Texto libre con respuestas grabadas**: con respuestas grabadas del modelo de lenguaje, solo los
  mensajes del guion se interpretan; el texto libre funciona plenamente con el modelo real. Esto es
  consecuencia de la reproducibilidad de la feature 001 y no se cambia en esta feature.
- **Actualización de la consola**: la bandeja, el detalle y las métricas se actualizan al abrirlos y
  a petición; no se requiere actualización en tiempo real.
- **Un solo asesor a la vez**: no hay asignación ni bloqueo de tickets por asesor; los conflictos
  entre pestañas los resuelve la versión del caso.
- **Acciones del asesor**: el catálogo y los permisos son los de la feature 001; la web no agrega
  acciones nuevas. Si una acción del catálogo requiere datos (motivo, justificación, validación a
  verificar), la consola los pide en un formulario simple.
- **Navegador**: escritorio, navegador moderno; el diseño debe ser usable en pantallas de laptop.
- **Fuera de alcance**: inicio de sesión, roles y permisos por usuario de la web, diseño responsivo
  fino para móvil, internacionalización (todo en español), carga de documentos propios del usuario
  distintos a los de ejemplo, notificaciones en tiempo real y edición del guion desde la web.
- **Dependencias**: la feature 001 implementada (canal de mensajes y documentos por caso, catálogo
  de acciones con actor asesor, registro de acciones, tickets y reporte de métricas), los guiones
  de `fixtures/scenarios/` y los documentos sintéticos de `fixtures/documents/`.
