# Feature Specification: Modelos reales y observabilidad

**Feature Branch**: `003-real-models-observability`

**Created**: 2026-10-04

**Status**: Implemented (2026-10-04)

**Input**: User description: "Feature 003 · Modelos reales y observabilidad. P1 · Modo real. El sistema corre con modelos locales reales (gemma4:12b para conversación y extracción, glm-ocr para OCR) cambiando una variable de entorno, sin cambiar código. Un modo de grabación guarda las respuestas reales como fixtures, para que el modo sin GPU use respuestas auténticas del modelo. P2 · Trazas. Cada turno del agente deja una sola traza con las etapas, las tools llamadas y las llamadas al modelo (entrada, salida, latencia y tokens), visible en una consola de observabilidad local. P3 · Calidad medida. La extracción de mensajes y documentos cumple un umbral sobre el set de evaluación existente (eval/): al menos 85% de campos correctos y 100% de respuestas JSON válidas, con la misma regla de puntaje de la comparación de modelos. Se corre con un comando que falla si no se cumple. Fuera de alcance: dashboards, alertas y comparación automática entre modelos."

## Contexto

Las features 001 y 002 dejaron el agente operando de punta a punta y navegable desde la web, pero
la demo sin acelerador gráfico responde con respuestas del modelo de lenguaje **sembradas** a
partir de los guiones: el texto de OCR, la extracción y la respuesta al cliente las escribió una
persona, no el modelo. Eso hace que la demo reproducible no muestre lo que el modelo realmente
hace, y que fuera de los mensajes del guion el chat no entienda texto libre.

Esta feature cierra esa brecha en tres partes: correr todo con los modelos locales reales con
solo cambiar la configuración, grabar sus respuestas auténticas para que la demo sin acelerador
gráfico las reproduzca, dejar una traza por turno que muestre qué hizo el agente y qué le pidió
al modelo, y medir la calidad de extracción con un comando que falla si no alcanza el umbral.

La feature no agrega reglas de negocio ni cambia decisiones: el modelo sigue proponiendo y el
código decidiendo (Principio II). Las trazas observan; no alteran el turno.

**Demos a los que sirve (Principio I)**: los 4 demos de la feature 001 (y su versión en la web de
la feature 002), ahora corridos con modelos reales y reproducidos con respuestas auténticas.
Responde además a dos preguntas de evaluación del demo: "¿qué hizo exactamente el agente y el
modelo en este turno?" (trazas) y "¿cómo sabes que la extracción es confiable?" (umbral medido).
Corresponde al contenedor `phoenix` de la topología de referencia y al gate del Principio VIII.

**Actores**

- **Persona que hace la demo**: corre los demos en modo real o en modo grabado y los muestra.
- **Persona que mantiene el demo**: graba respuestas, revisa trazas y corre la medición de
  calidad antes de cambiar modelo, instrucciones o esquema de extracción.
- **Agente**, **Sistema** y **Asesor**: los mismos de las features 001 y 002; esta feature no
  cambia su comportamiento.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Modo real y grabación de respuestas auténticas (Priority: P1)

La persona que hace la demo cambia una sola variable de entorno y reinicia el sistema: a partir de
ahí, la conversación y la extracción las resuelve el modelo local de lenguaje y el OCR de los
documentos lo resuelve el modelo local de OCR, sin modificar código ni otros archivos. Con el
sistema en modo real puede recorrer los 4 demos (por guion o desde el chat) y escribir texto libre
que el agente interpreta.

En modo de grabación, el sistema se comporta como en modo real y además guarda cada respuesta del
modelo como respuesta grabada. Después de grabar los 4 demos, el modo por defecto (sin acelerador
gráfico) reproduce esas respuestas auténticas en lugar de las sembradas, con resultados idénticos
entre corridas.

**Why this priority**: sin modelos reales el resto de la feature no tiene qué observar ni qué
medir, y sin grabación la demo reproducible sigue mostrando respuestas escritas a mano. Por sí
sola permite mostrar el agente con el modelo real y reproducir esa misma corrida en cualquier
laptop.

**Independent Test**: con los modelos locales disponibles, poner el sistema en modo real y correr
los 4 demos; verificar que terminan con el resultado esperado. Luego grabar los 4 demos, volver al
modo por defecto sin modelos disponibles, correrlos 10 veces y verificar que el resultado y cada
mensaje del agente son idénticos a la grabación.

**Acceptance Scenarios**:

1. **Given** el sistema en modo por defecto, **When** la persona cambia solo la variable de modo a
   real y reinicia, **Then** las llamadas de conversación y extracción las atiende el modelo local
   de lenguaje y las de OCR el modelo local de OCR, sin cambios en código ni en otros archivos.
2. **Given** el sistema en modo real, **When** se corre cada uno de los 4 demos, **Then** cada uno
   termina con el mismo resultado que su versión con respuestas grabadas (OK para financiera,
   rechazo por auto, corrección o escalación del documento, sin segunda llave).
3. **Given** el sistema en modo real, **When** la persona escribe en el chat un mensaje libre que
   no está en el guion (p. ej. "es un Nissan Versa 2020, lo compré de agencia"), **Then** el agente lo interpreta con el
   modelo real en lugar de tratarlo como mensaje no reconocido.
4. **Given** el sistema en modo de grabación, **When** se corren los 4 demos, **Then** cada
   respuesta del modelo (OCR, extracción y respuesta al cliente) queda guardada como respuesta
   grabada, marcada como auténtica, con el modelo que la produjo, la fecha, la latencia y los
   tokens de la llamada original.
5. **Given** respuestas grabadas de los 4 demos, **When** se corren en el modo por defecto sin
   modelos locales disponibles, **Then** cada demo termina con el resultado grabado y cada mensaje
   del agente es idéntico al de la grabación, en 10 de 10 corridas.
6. **Given** una grabación en la que un demo no llega a su resultado esperado, **When** termina la
   grabación, **Then** el sistema reporta qué demo falló y en qué paso, y las respuestas grabadas
   vigentes de ese demo no se reemplazan por las de esa corrida.
7. **Given** el modo real o de grabación y un modelo local no disponible o no instalado, **When**
   arranca el sistema o llega la primera llamada, **Then** el sistema lo reporta con un mensaje
   claro que nombra el modelo faltante y no cae en silencio a respuestas grabadas.

---

### User Story 2 - Una traza por turno en la consola de observabilidad (Priority: P2)

Cada vez que el agente atiende un turno —un mensaje o un documento del cliente— queda una sola
traza que agrupa todo lo que pasó en ese turno: las etapas que recorrió el agente, cada tool que
llamó (con su entrada, su resultado y si fue aceptada o rechazada) y cada llamada al modelo (con
la entrada, la salida, la latencia y los tokens de entrada y de salida). La persona que mantiene
el demo abre la consola de observabilidad local, busca el caso y ve la traza de cada turno en
orden.

**Why this priority**: es lo que permite explicar, turno por turno, qué propuso el modelo y qué
decidió el código; es la evidencia de que el agente no se salta controles. Depende de P1 para que
las llamadas al modelo sean reales, pero también funciona con respuestas grabadas.

**Independent Test**: correr el demo del happy path en cualquier modo, abrir la consola, buscar el
caso por su identificador y verificar que hay exactamente una traza por turno del cliente y que
cada traza muestra etapas, tools y llamadas al modelo con entrada, salida, latencia y tokens.

**Acceptance Scenarios**:

1. **Given** un caso en curso, **When** el cliente envía un mensaje y el agente responde, **Then**
   queda exactamente una traza para ese turno, asociada al caso y al mensaje, aunque el turno haya
   cruzado varios servicios.
2. **Given** un turno en el que el cliente envía un documento, **When** el agente lo procesa,
   **Then** la traza del turno incluye la lectura del documento (OCR), la extracción, las tools de
   registro y validación y la respuesta al cliente, en el orden en que ocurrieron.
3. **Given** una traza abierta en la consola, **When** la persona revisa una llamada al modelo,
   **Then** ve qué tarea era (OCR, extracción o respuesta), el modelo, el modo (real, grabación o
   respuesta grabada), la entrada, la salida, la latencia y los tokens de entrada y de salida.
4. **Given** una traza abierta en la consola, **When** la persona revisa una tool, **Then** ve su
   nombre, el actor, la entrada, el resultado y si fue aceptada o rechazada con su motivo.
5. **Given** un turno en el que el modelo devuelve una salida inválida, una tool se rechaza o un
   reintento ocurre, **When** se revisa la traza, **Then** el error y cada intento aparecen dentro
   de la misma traza, marcados como error.
6. **Given** la consola de observabilidad apagada o inaccesible, **When** el cliente envía un
   mensaje, **Then** el turno se completa igual, con el mismo resultado y sin demora perceptible.
7. **Given** un turno atendido con respuestas grabadas, **When** se revisa la traza, **Then** la
   llamada al modelo muestra los tokens y la latencia de la llamada original grabada, junto con la
   latencia real de la reproducción, y queda claro que fue una reproducción.

---

### User Story 3 - Calidad de extracción medida con un comando (Priority: P3)

La persona que mantiene el demo corre un comando que mide la extracción del sistema sobre el set
de evaluación existente (mensajes y documentos de `eval/`), usando el modelo real y la misma regla
de puntaje que se usó en la comparación de modelos. El comando muestra el resultado por caso y en
total, guarda la corrida y termina con falla si los campos correctos quedan por debajo del 85% o
si alguna respuesta no es JSON válido contra el esquema.

**Why this priority**: convierte "el modelo extrae bien" en un número reproducible y en una
barrera que impide cambiar modelo, instrucciones o esquema sin demostrar que se cumple el umbral.
Depende de P1 (modo real); no depende de P2.

**Independent Test**: con el sistema en modo real, correr el comando y verificar que reporta el
porcentaje de campos correctos y de JSON válido, guarda la corrida y termina con éxito; luego
correrlo contra una configuración degradada a propósito y verificar que termina con falla.

**Acceptance Scenarios**:

1. **Given** el sistema en modo real, **When** se corre el comando de medición, **Then** se
   evalúan todos los casos del set (mensajes y documentos) a través del mismo camino que usa el
   agente, y se reporta por caso: campos correctos, campos esperados, JSON válido y tiempo.
2. **Given** una corrida terminada, **When** el resumen se muestra, **Then** incluye el total de
   campos correctos sobre esperados, el porcentaje de JSON válido, el desglose por mensajes y por
   documentos, el modelo, la versión del esquema y el modo, y queda guardado con fecha y hora.
3. **Given** campos correctos ≥ 85% y JSON válido = 100%, **When** termina la corrida, **Then** el
   comando termina con éxito.
4. **Given** campos correctos < 85% o al menos una respuesta que no es JSON válido, **When**
   termina la corrida, **Then** el comando termina con falla y señala qué casos fallaron.
5. **Given** el sistema en el modo por defecto (respuestas grabadas), **When** se corre el
   comando, **Then** termina con falla indicando que la medición requiere el modelo real, sin
   reportar un resultado que parezca válido.
6. **Given** un caso esperado y una respuesta del modelo, **When** se puntúa, **Then** se aplica la
   regla de la comparación de modelos: n = 1 (intención o tipo de documento) + campos esperados;
   números y booleanos exactos; texto en mayúsculas, sin acentos, sin puntuación y con espacios
   simples; null solo coincide con null esperado; cada campo extra no nulo resta 1 (mínimo 0).

---

### Edge Cases

- **Modelo lento**: en modo real una llamada puede tardar decenas de segundos. El chat sigue
  mostrando que el agente está respondiendo y el turno no se duplica; si se excede el tiempo
  máximo configurado, el turno termina con un error claro y queda en la traza.
- **Respuesta grabada faltante**: si en el modo por defecto llega una llamada sin respuesta
  grabada (p. ej. porque cambiaron las instrucciones al modelo), se conserva el comportamiento de
  la feature 001 (mensaje no reconocido u OCR fallido), queda marcado en la traza como respuesta
  faltante y existe una forma de listar qué respuestas grabadas faltan para los 4 demos.
- **Respuestas grabadas sembradas y auténticas mezcladas**: cada respuesta grabada indica su
  origen; es posible saber si los 4 demos usan solo respuestas auténticas.
- **Salida del modelo inválida en modo real**: si el modelo devuelve algo que no cumple el
  esquema, el sistema aplica el mismo manejo de la feature 001 (no afecta el caso) y en grabación
  esa respuesta no se guarda como válida.
- **Variación del modelo real entre corridas**: aunque el modelo corre con parámetros
  deterministas, una corrida real puede diferir; la reproducibilidad estricta se garantiza solo en
  el modo por defecto, a partir de las respuestas grabadas.
- **Datos personales en trazas**: los datos de los demos son sintéticos, pero las trazas siguen la
  misma política de ocultamiento de identificadores que los registros del sistema.
- **Varios turnos simultáneos**: dos casos atendidos al mismo tiempo producen trazas separadas;
  ninguna llamada al modelo ni tool aparece en la traza de otro turno.
- **Caso del set de evaluación sin respuesta del modelo** (error o tiempo agotado): cuenta como
  JSON no válido y 0 campos correctos; la corrida continúa con el resto y el comando falla.

## Requirements *(mandatory)*

### Functional Requirements

**Modo real y grabación (P1)**

- **FR-076**: El modo del modelo de lenguaje (respuestas grabadas, real o grabación) MUST
  seleccionarse con una sola variable de entorno, con respuestas grabadas como valor por defecto;
  cambiarlo MUST NOT requerir cambios de código ni de otros archivos.
- **FR-077**: En modo real y de grabación, la conversación y la extracción MUST resolverse con el
  modelo local de lenguaje y el OCR con el modelo local de OCR, con los parámetros deterministas
  definidos en la constitución.
- **FR-078**: Con el modo real, los 4 demos MUST poder completarse por guion y desde el chat,
  terminando con el mismo resultado que con respuestas grabadas.
- **FR-079**: En modo real, el texto libre del cliente en el chat MUST interpretarse con el modelo
  real.
- **FR-080**: En modo de grabación, cada respuesta válida del modelo (OCR, extracción y respuesta
  al cliente) MUST guardarse como respuesta grabada junto con su origen (auténtica), el modelo, la
  fecha, la latencia y los tokens de la llamada original.
- **FR-081**: MUST existir un comando que grabe los 4 demos (5 guiones, con las ramas A y B del
  demo 3) de una vez y reporte, por demo, si
  llegó al resultado esperado; las respuestas de un demo que no llegó a su resultado MUST NOT
  reemplazar las respuestas grabadas vigentes de ese demo.
- **FR-082**: Una vez grabados, los 4 demos en el modo por defecto MUST usar solo respuestas
  auténticas y producir resultado y mensajes idénticos a la grabación en corridas repetidas, sin
  acelerador gráfico ni modelos locales.
- **FR-083**: Cada respuesta grabada MUST indicar si es sembrada o auténtica, y MUST existir una
  forma de listar las respuestas grabadas faltantes o sembradas que usan los 4 demos.
- **FR-084**: En modo real o de grabación, si un modelo local no está disponible o no está
  instalado, el sistema MUST reportarlo nombrando el modelo y MUST NOT responder en su lugar con
  respuestas grabadas.

**Trazas (P2)**

- **FR-085**: Cada turno del agente (mensaje o documento del cliente) MUST producir exactamente
  una traza que agrupe todo lo ocurrido en ese turno en los servicios que participan; la ejecución
  de cada tool se representa con su paso en la traza del agente.
- **FR-086**: La traza MUST identificar el caso, el turno y el mensaje o documento que lo originó,
  y MUST poder encontrarse en la consola por el identificador del caso.
- **FR-087**: La traza MUST incluir las etapas del turno del agente, en orden.
- **FR-088**: Cada tool llamada en el turno MUST aparecer en la traza con nombre, actor, entrada,
  resultado y desenlace (aceptada o rechazada con motivo).
- **FR-089**: Cada llamada al modelo MUST aparecer en la traza con tarea, modelo, modo, entrada,
  salida, latencia y tokens de entrada y de salida; con respuestas grabadas MUST mostrar además la
  latencia y los tokens de la llamada original y marcarse como reproducción.
- **FR-090**: Errores, salidas inválidas del modelo, rechazos y reintentos MUST aparecer dentro de
  la traza del turno, marcados como error.
- **FR-091**: Las trazas MUST verse en una consola de observabilidad local que forma parte del
  sistema y arranca con él, sin servicios externos.
- **FR-092**: Si la consola de observabilidad no está disponible, los turnos MUST completarse con
  el mismo resultado; la pérdida de trazas MUST NOT afectar el caso.
- **FR-093**: El contenido de las trazas MUST seguir la misma política de ocultamiento de
  identificadores personales que los registros del sistema.

**Calidad medida (P3)**

- **FR-094**: MUST existir un comando que mida la extracción del sistema sobre todos los casos del
  set de evaluación de `eval/` (mensajes y documentos), a través del mismo camino de extracción que
  usa el agente y con el modelo real.
- **FR-095**: El puntaje MUST seguir exactamente la regla de la comparación de modelos (n = 1 +
  campos esperados; números y booleanos exactos; texto normalizado; null solo para null esperado;
  cada campo extra no nulo resta 1, mínimo 0).
- **FR-096**: El comando MUST terminar con falla si los campos correctos son menos del 85% del
  total del set o si alguna respuesta no es JSON válido contra el esquema, y con éxito en otro
  caso.
- **FR-097**: El comando MUST reportar el resultado por caso y el resumen (total, desglose por
  mensajes y por documentos, modelo, versión del esquema y modo) y MUST guardar cada corrida con
  fecha y hora.
- **FR-098**: Si el sistema no está en modo real, el comando MUST terminar con falla indicando que
  la medición requiere el modelo real.

### Key Entities *(include if feature involves data)*

- **Respuesta grabada**: una respuesta del modelo guardada para reproducirse sin modelo. Atributos:
  tarea (OCR, extracción, respuesta), entrada que la identifica, salida, origen (sembrada o
  auténtica), modelo, fecha, latencia y tokens de la llamada original.
- **Traza de turno**: el registro de un turno del agente. Atributos: caso, turno, mensaje o
  documento que lo originó, inicio, duración, resultado, y sus pasos (etapas, tools y llamadas al
  modelo) en orden.
- **Paso de traza**: una etapa, tool o llamada al modelo dentro de una traza, con inicio, duración,
  entrada, salida, desenlace y, para llamadas al modelo, modelo, modo y tokens.
- **Corrida de medición**: una ejecución del comando de calidad. Atributos: fecha y hora, modelo,
  versión del esquema, modo, resultado por caso (campos correctos, esperados, JSON válido, tiempo)
  y resumen (porcentajes, desglose y si pasó el umbral).

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-017**: Pasar de respuestas grabadas a modelos reales requiere cambiar un solo valor de
  configuración y reiniciar; 0 archivos de código modificados.
- **SC-018**: Con modelos reales, los 4 demos terminan con su resultado esperado en 3 de 3 corridas
  consecutivas.
- **SC-019**: Tras grabar, los 4 demos sin acelerador gráfico usan 100% respuestas auténticas
  (0 sembradas) y producen resultado y mensajes idénticos a la grabación en 10 de 10 corridas.
- **SC-020**: El 100% de los turnos de los 4 demos produce exactamente una traza, y el 100% de las
  llamadas al modelo en esas trazas muestra entrada, salida, latencia y tokens.
- **SC-021**: Partiendo del identificador de un caso, una persona encuentra en la consola la traza
  de cualquiera de sus turnos y la llamada al modelo de ese turno en menos de 1 minuto.
- **SC-022**: Con la consola de observabilidad apagada, el 100% de los turnos de los 4 demos se
  completa con el mismo resultado.
- **SC-023**: La extracción sobre el set de evaluación alcanza al menos 85% de campos correctos y
  100% de JSON válido con el modelo real.
- **SC-024**: El comando de medición termina con falla en el 100% de las corridas que no cumplen el
  umbral o que no usan el modelo real.

## Assumptions

- **Modos existentes**: el modo por defecto con respuestas grabadas, el modo real y el modo de
  grabación ya están previstos en la constitución (Principio V) y el sistema los distingue en un
  solo lugar; esta feature los completa y los verifica de punta a punta, sin redefinirlos.
- **Qué se graba**: la grabación cubre los 4 demos (los 5 guiones, contando las ramas A y B del
  demo 3). Las respuestas sembradas actuales se conservan solo hasta ser reemplazadas por una
  grabación exitosa; el texto libre fuera del guion sigue requiriendo el modelo real.
- **Respuestas al cliente grabadas**: hoy, sin respuesta grabada, el agente responde con una
  plantilla en español; tras grabar, el modo por defecto reproduce el texto real del modelo.
- **Documentos en la medición**: los casos de documentos se miden sobre el texto de OCR ya
  registrado en `eval/` (como en la comparación de modelos), de modo que la medición aísla la
  calidad de extracción; el OCR con el modelo real se ejercita en los demos (P1), no en el umbral.
- **Umbral global**: el 85% se aplica al total del set, como fija el Principio VIII; el desglose por
  mensajes y documentos se reporta como información.
- **Set de evaluación**: es el existente en `eval/` (37 casos, esquema v3); esta feature no agrega
  casos. La última medición registrada en DECISIONS.md (89.5%, 100% JSON válido) es la referencia.
- **Hardware**: el modo real y la medición requieren una máquina con los modelos locales
  instalados; los tiempos de respuesta de la feature 002 (SC-012) aplican solo al modo con
  respuestas grabadas.
- **Ocultamiento en trazas**: se aplica la misma política de ocultamiento de identificadores
  (CURP, RFC, teléfono, nombre) que ya usan los registros; como los datos son sintéticos, esto no
  impide leer la entrada y salida de cada llamada.
- **Consola local**: la consola de observabilidad es el contenedor `phoenix` de la topología de
  referencia; no se configuran dashboards ni alertas sobre ella.
- **Fuera de alcance**: dashboards, alertas, comparación automática entre modelos, medición de la
  calidad del OCR por separado y todo lo listado en el Principio XI.
- **Dependencias**: las features 001 y 002 implementadas; el set de `eval/` y la regla de puntaje
  de `eval/esquemas.json`; los modelos locales `gemma4:12b` y `glm-ocr` instalados en el host para
  el modo real, la grabación y la medición.
