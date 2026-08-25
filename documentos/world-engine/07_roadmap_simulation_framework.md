# 07 — Roadmap opcional: SIZA Simulation Framework robusto

**Estado:** OPCIONAL.  
**No requerido para cerrar el World Engine de SIZA.**  
**Punto de partida:** Core Freeze Candidate v1.01.1.  
**Meta si se decide continuar:** `SIZA Simulation Framework 2.0 — feature complete` alrededor de v1.13.

## 1. Por qué existe este documento

Durante el desarrollo del World Engine apareció una tendencia natural: cada sistema cerrado revelaba otro caso teórico que podía volver la simulación más general, más segura o más expresiva.

Ese proceso es útil, pero sin una línea de meta puede continuar indefinidamente.

Este documento convierte aquella dirección implícita en un roadmap **finito y deliberado**. Si algún día se decide convertir SIZA World Engine en un framework reusable de simulación narrativa, estos son los bloques que faltan.

Mientras esa decisión no se tome, el core permanece frozen y estos bloques son backlog de producto/plataforma, no deuda obligatoria.

## 2. Estado aproximado del framework ambicioso

Como estimación de planificación, no como métrica formal, el core actual contiene alrededor de **70–75% de las primitivas** que imaginábamos para una versión extremadamente robusta:

Ya existen:

- mundo persistente y geometría real;
- Actions/requirements/resolution/consequences;
- world state;
- percepción y descubrimiento;
- Knowledge/Facts/provenance;
- lifecycle ACTIVE/RETRACTED/SUPERSEDED;
- NPC autonomy;
- reloj/rutinas/needs/jobs/events;
- relaciones;
- transferencia social física;
- facciones/rangos/authority/orders;
- policies institucionales por Fact/type/severity;
- jerarquía ascendente;
- holder acquisition;
- narration/dialogue grounded;
- trace básico y QA determinista.

Lo que falta para el objetivo "simulation framework extremadamente robusto" está concentrado en **epistemología avanzada, protocolos institucionales, auditoría, escala y tooling**, no en cien mecánicas fundamentales nuevas.

## 3. Regla de ejecución del roadmap

Si se activa este roadmap:

1. Se implementan únicamente los bloques aquí listados, salvo bug crítico o dependencia descubierta.
2. Una versión no abre otra feature fuera del roadmap sólo porque resulte interesante.
3. Cada bloque debe tener validator y criterio de salida antes de empezar el siguiente.
4. Al cerrar v1.13 se declara feature complete.
5. Ideas posteriores van a backlog de una versión futura, no desplazan la línea de meta.

## 4. v1.02 — Fact confidence y source reliability

### Problema

Hoy un Fact ACTIVE conocido tiene autoridad binaria para los sistemas que lo consumen: usable o no usable. El engine conserva provenance, pero no modela cuánta confianza tiene el holder en ese dato.

Un testigo directo, un rumor y un reporte oficial pueden tener la misma `known=True` aunque no deban pesar igual.

### Objetivo

Separar:

```text
Fact existe / está ACTIVE
```

de:

```text
qué confianza tiene este holder en ese Fact
```

### Modelo recomendado

Holder-local, porque dos NPCs pueden valorar de forma distinta la misma proposición.

Conceptualmente:

```python
confidence = 0..1000
confidence_source = "DIRECT" | "TRANSFER" | "CORROBORATED" | ...
```

No es necesario fijar nombres/rango hasta implementar.

### Integraciones

- decision effects pueden exigir confidence mínima;
- disclosure puede considerar confidence sin revelar que algo es verdad objetiva;
- institutional policies pueden exigir threshold;
- retrieval puede incluir confidence metadata internamente sin exponerla necesariamente al Player.

### No debe hacer

- convertir confidence alta en verdad mundial;
- permitir que el LLM asigne confidence arbitrariamente;
- modificar provenance original.

### Criterio de cierre

Un mismo Fact puede existir en dos holders con diferente confidence; decisiones/policies respetan thresholds; una transferencia no borra el origen ni inventa certeza.

## 5. v1.03 — Contradicciones entre Facts

### Problema

El engine puede almacenar simultáneamente:

```text
"Mara estaba en la dársena"
"Mara estaba en la plaza"
```

Hoy no existe un contrato general que declare que ambas proposiciones compiten por la misma cuestión.

### Objetivo

Representar contradicción sin borrar información.

### Modelo recomendado

Introducir identidad de cuestión/proposición incompatible, por ejemplo conceptualmente:

```text
claim_group / subject-predicate slot / contradiction_set
```

Dos Facts pueden estar ACTIVE y conocidos pero marcados como mutuamente incompatibles.

### Resultado esperado

El NPC puede estar en estado:

```text
CONFLICTED / UNRESOLVED
```

respecto de una cuestión, en vez de que el engine trate ambos textos como si fueran perfectamente compatibles.

### Criterio de cierre

- contradicción exacta se detecta por metadata authored, no por free-form LLM;
- ambos Facts se preservan;
- downstream systems pueden distinguir resolved vs conflicted;
- no se elige "ganador" implícito por orden de lista.

## 6. v1.04 — Corroboración y resolución epistemológica

### Problema

Con contradicciones modeladas, hace falta explicar cómo cambia el estado cuando aparece evidencia adicional.

### Objetivo

Permitir que nueva evidencia:

- corrobore un Fact;
- debilite otro;
- resuelva un conflict set;
- produzca un replacement/supersession cuando corresponda.

### Ejemplo

```text
Testigo A: vio a Mara en la dársena.
Testigo B: vio a Mara en la dársena.
Registro horario: confirma entrada.
→ aumenta soporte del claim A.

Otro Fact incompatible pierde fuerza o queda superseded según rule authored.
```

### Regla clave

El framework no debe "votar" por cantidad de Facts sin authoring. La corroboración necesita provenance/independencia/rules explícitas.

### Criterio de cierre

Una cadena de evidencia puede modificar confidence/resolution de manera determinista, conservando historial causal.

## 7. v1.05 — Clasificación y secreto institucional

### Problema

Disclosure actual cubre permisos sociales del holder, pero no existe una política institucional general de clasificación de información.

### Objetivo

Poder expresar categorías como:

```text
PUBLIC
INTERNAL
RESTRICTED
SECRET
```

sin asumir necesariamente esos nombres finales.

### Necesidades

- clasificación del Fact o de su copia institucional;
- clearance/permission del source y target;
- policies que no materialicen SHARE_FACT hacia recipients no autorizados;
- no filtrar información clasificada al contexto LLM del viewer incorrecto.

### Criterio de cierre

Un NPC puede conocer un Fact y aun así no tener permiso institucional para transmitirlo a cierto target; el bloqueo sucede antes del viaje/LLM.

## 8. v1.06 — Trust source → receiver

### Problema

Confidence del Fact y confianza interpersonal no son lo mismo.

Un receptor puede confiar mucho en una capitana y poco en un contrabandista aunque ambos transmitan el mismo texto.

### Objetivo

Modelar trust como relación source→receiver que influya en adquisición/valoración del Fact.

### Integración

```text
transfer
→ provenance del hop
→ trust del receiver hacia source
→ confidence holder-local resultante
```

### No debe hacer

- reescribir la truth del mundo;
- hacer que relación alta convierta automáticamente mentira en verdad;
- depender del LLM para calcular trust.

### Criterio de cierre

Dos sources distintos pueden transmitir el mismo Fact a un holder y producir distinta valoración según trust y rule authored.

## 9. v1.07 — Rumores y degradación controlada

### Problema

El sistema actual transfiere el Fact exacto, ideal para reportes oficiales, pero una simulación social general también necesita rumores que pierdan precisión.

### Objetivo

Permitir una **representación derivada** del Fact original sin mutar silenciosamente el original.

Ejemplo:

```text
DIRECTO:
"Vi a un hombre de abrigo rojo entrar al almacén a las 22:10."

DERIVADO:
"Alguien vio a un hombre entrar al almacén."

RUMOR:
"Dicen que hubo alguien sospechoso en el almacén."
```

### Principio

La degradación debe ser authored/determinista por plantilla/regla, no una cadena telefónica libre del LLM que termine alterando canon.

### Datos necesarios

- parent/source Fact ID;
- transformation rule;
- hop count;
- confidence impact;
- provenance de derivación.

### Criterio de cierre

Un rumor puede propagarse como nuevo Fact derivado, con lineage auditable al Fact original y sin reemplazarlo.

## 10. v1.08 — Frescura, expiración y staleness

### Problema

v1.01 permite retractar/superseder manualmente, pero un Fact temporal puede seguir ACTIVE indefinidamente.

Ejemplo:

```text
"La puerta está abierta a las 08:00"
```

no debería necesariamente justificar una decisión a las 18:00.

### Objetivo

Separar memoria histórica de actualidad temporal.

Conceptos posibles:

```text
observed_at
valid_until / ttl
freshness policy
STALE como estado derivado, no necesariamente lifecycle destructivo
```

### Integración con World Clock

Debe usar el reloj de simulación, no `datetime` real, para Facts diegéticos dependientes del tiempo.

### Criterio de cierre

Un Fact temporal deja de autorizar acciones dependientes de actualidad sin borrar que el holder lo supo en el pasado.

## 11. v1.09 — Jurisdicción y protocolos institucionales

### Problema

Una facción puede tener authority y policies, pero aún no existe una noción general de "esta institución tiene competencia sobre este lugar/tipo de incidente".

### Objetivo

Modelar jurisdicción/protocolo para que la misma información produzca respuestas distintas según:

- territorio;
- tipo de asunto;
- institución;
- horario/estado de emergencia;
- authority/rank.

### Ejemplo

```text
incidente de muelle
→ Guardia Portuaria tiene jurisdicción

mismo Fact fuera del puerto
→ otra institución o ninguna
```

### Criterio de cierre

Policies institucionales pueden activarse/desactivarse por una autoridad de jurisdicción determinista, sin hard-codear cada Room en Python.

## 12. v1.10 — Workflows institucionales multi-step

### Problema

Hoy la institución puede transmitir Facts y producir goals/orders, pero no existe un motor general de proceso institucional encadenado.

### Objetivo

Representar workflows como:

```text
incidente
→ reporte
→ triage
→ asignación
→ investigación
→ hallazgo
→ revisión
→ decisión
→ cierre
```

sin escribir una quest monolítica para cada organismo.

### Posible modelo

State machine/workflow authored con:

- workflow ID;
- stages;
- entry conditions;
- required Facts;
- responsible role/rank;
- generated Goals/Jobs/Orders;
- completion conditions;
- outputs.

### Reutilización

Debe reutilizar:

- Facts;
- Goals;
- Jobs;
- Orders;
- Factions;
- world state;
- existing decision engine.

No crear un segundo NPC AI.

### Criterio de cierre

Un proceso de tres o más pasos puede ejecutarse por distintos NPCs a lo largo del tiempo y sobrevivir restart, con estado inspectable.

## 13. v1.11 — Causal replay y auditoría fuerte

### Problema

Existe trace de World Tick e historiales parciales, pero responder "¿por qué Mara fue allí?" todavía requiere correlacionar manualmente varios records.

### Objetivo

Construir una cadena causal estructurada.

Ejemplo esperado:

```text
Mara se movió a Calle de Servicio
← Goal RELATIONSHIP
← SHARE_FACT obligation
← Policy SECURITY_HIGH
← Fact FACT-X
← transfer from Informant
← consequence of Action ACT-Y
← Player resolution SUCCESS
```

### Requisitos

- IDs causales estables;
- parent/cause references;
- correlation entre Action, consequence, Fact, policy, obligation, Goal y movement;
- consulta/debug read-only.

### Criterio de cierre

Una acción autónoma relevante puede explicarse por una cadena causal machine-readable sin inferirla desde logs de texto.

## 14. v1.12 — Escala y performance

### Problema

El piloto valida corrección con pocos NPCs/Facts. Un framework reusable necesita conocer sus límites.

### Objetivo

Stress test y optimización sin cambiar semántica.

Escenarios mínimos sugeridos:

```text
100 NPCs
1,000 Facts
múltiples memberships
cientos/miles de obligations
muchas policies
world ticks repetidos
```

Y después escalar según resultados.

### Áreas probables de optimización

- índices por npc_id/fact_id/faction;
- evitar `search_tag` repetido en hot paths;
- caches invalidables;
- batching de policy sync;
- scheduling parcial de NPCs;
- limitar retrieval/graph scans;
- profiling de World Tick.

### Regla

No optimizar prematuramente rompiendo identidad/corrección. Primero medir.

### Criterio de cierre

Se definen budgets de tick y dataset de referencia; el framework sostiene el target elegido sin cambio observable de reglas.

## 15. v1.13 — Authoring y debug tooling

### Problema

Un framework robusto no puede exigir leer Python/DB Attributes para entender cada comportamiento.

### Objetivo

Crear herramientas de inspección y authoring para diseñadores/devs.

Consultas objetivo:

```text
¿Por qué Mara sabe este Fact?
¿Quién más lo sabe?
¿Qué copia está retractada?
¿Qué policy gobierna este share?
¿Por qué este NPC eligió este Goal?
¿Qué blockers impiden esta Action?
¿Qué stage tiene este workflow?
```

### Visualizaciones/inspectors posibles

- Fact holder graph;
- transfer lineage;
- faction membership/authority;
- policy expansion preview;
- decision candidate inspector;
- world tick profiler;
- Action requirement debugger;
- causal replay viewer.

### Criterio de cierre

Un diseñador puede diagnosticar los principales sistemas sin abrir archivos internos ni modificar estado accidentalmente.

## 16. Orden y dependencias

Orden recomendado:

```text
v1.02 confidence
   ↓
v1.03 contradictions
   ↓
v1.04 corroboration
   ↓
v1.05 classification
   ↓
v1.06 trust
   ↓
v1.07 rumors
   ↓
v1.08 freshness
   ↓
v1.09 jurisdiction
   ↓
v1.10 workflows
   ↓
v1.11 causal replay
   ↓
v1.12 performance
   ↓
v1.13 tooling
```

Algunas features podrían implementarse en paralelo técnicamente, pero este orden reduce rework porque epistemología se estabiliza antes de workflows/tooling.

## 17. Qué no entra aunque parezca relacionado

Este roadmap **no** incluye automáticamente:

- economía completa;
- mercados dinámicos;
- enfermedades/epidemias;
- política electoral;
- crimen procedural general;
- leyes universales;
- ownership de propiedades completo;
- reputación pública global;
- ecosistemas;
- guerra estratégica;
- generación procedural de sociedades.

Esas ideas podrían usar el framework, pero agregarlas aquí volvería a mover la meta otra vez.

## 18. Combat Bridge tampoco entra aquí

El bridge con el TCG es una integración necesaria del juego y se documenta aparte en `06_tcg_combat_bridge.md`.

Puede implementarse con el core frozen y no obliga a activar v1.02–v1.13.

## 19. Regla de parada definitiva

Si se completa v1.13 y sus criterios de cierre:

```text
SIZA SIMULATION FRAMEWORK 2.0 — FEATURE COMPLETE
```

A partir de ahí:

- sólo bugs;
- performance demostrada;
- API/authoring requerido por productos reales;
- nuevas major versions con roadmap separado.

No se permite que "encontré otro edge case interesante" retrase indefinidamente la entrega.
