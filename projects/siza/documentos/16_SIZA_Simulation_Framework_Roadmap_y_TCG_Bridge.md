# SIZA Simulation Framework — Roadmap cerrado y frontera con TCG

**Base:** SIZA World Engine v1.01.  
**Objetivo de este documento:** fijar por adelantado qué faltaría para llevar el World Engine desde “core suficiente para construir SIZA” hasta un **simulation framework narrativo extremadamente robusto**, sin permitir que la línea de meta se mueva indefinidamente.

---

## 1. Punto de partida

El World Engine actual ya resuelve:

- mundo MUD persistente;
- actions + requirements + resolution + consequences;
- world state;
- objects;
- perception / discovery;
- Knowledge / Facts;
- grounded narration;
- diálogo y disclosure;
- Fact transfer;
- NPC goals y autonomous movement;
- relationships;
- factions / authority;
- institutional Fact-share policies;
- fact types;
- severity;
- nearest / max targets;
- need-aware routing;
- strictly-upchain chain of command;
- holder acquisition classification;
- Fact lifecycle ACTIVE / RETRACTED / SUPERSEDED;
- jobs / needs / personality / orders / events / time como infraestructura existente.

Para construir SIZA como juego, esto ya es suficiente para hacer freeze después de la aceptación final de v1.01.

El roadmap que sigue **no es requisito para terminar SIZA**. Es la expansión opcional que convertiría el engine en un framework reusable mucho más general.

---

# PARTE I — REGLA DE SCOPE

## 2. Límite deliberado

Si se decide perseguir la versión “extremadamente robusta”, el roadmap queda fijado a **11–12 bloques sustanciales** después de v1.01.

La meta recomendada sería aproximadamente:

```text
v1.01 actual
→ v1.02–v1.13 roadmap cerrado
→ SIZA Simulation Framework 2.0 — FEATURE COMPLETE
```

Después de ese punto no se agregan sistemas teóricos salvo:

1. bug reproducible;
2. requisito concreto de un producto/campaña;
3. limitación demostrada por stress test.

---

# PARTE II — BLOQUES FALTANTES

## 3. v1.02 — Confidence / Credibility de Facts

### Problema

Actualmente un Fact `ACTIVE` que un holder conoce es usable. El engine conserva provenance, pero no representa explícitamente cuánto confía el holder en ese dato.

No debería valer lo mismo:

- verlo directamente;
- leer un documento oficial;
- escucharlo de un amigo;
- escucharlo de un desconocido;
- recibir un rumor de tercer nivel.

### Capability

Añadir confidence holder-local, por ejemplo en una escala authored estable:

```text
0 = descartado / increíble
1 = rumor débil
2 = plausible
3 = confiable
4 = altamente confiable
5 = confirmado
```

La escala concreta debe fijarse antes de implementar; lo importante es que sea determinista y no inventada por el LLM.

### Uso

Rules/actions/goals podrían exigir:

```text
min_confidence
```

Ejemplo:

```text
Rumor: “hay contrabando en el almacén”
confidence 1
→ no autoriza una redada

Segundo testigo independiente
→ confidence sube

Documento de carga confiscado
→ confidence 5
→ autoriza acción institucional
```

### Compatibilidad

- Facts legacy sin confidence deben recibir default explícito.
- Confidence es holder-local.
- No se modifica la provenance original.
- El LLM no puede decidir arbitrariamente un confidence persistente.

---

## 4. v1.03 — Contradiction Sets

### Problema

El engine puede almacenar dos Facts incompatibles sin entender que compiten por la misma proposición.

Ejemplo:

```text
FACT-A: Mara estaba en la Pescadería a las 22:00
FACT-B: Mara estaba en la Plaza a las 22:00
```

Ambos pueden estar `ACTIVE` y known.

### Capability

Introducir una identidad de proposición o contradiction group:

```text
claim_group = MARA_LOCATION_2200
```

El holder puede tener múltiples candidates dentro del mismo group.

### Estado

Un contradiction group puede estar:

```text
UNCONTESTED
CONTESTED
RESOLVED
```

No se elimina automáticamente ninguna versión por existir contradicción.

### Uso

- dialogue puede admitir incertidumbre;
- goals pueden exigir un claim resuelto;
- institutional protocols pueden disparar investigación cuando aparece contradicción.

---

## 5. v1.04 — Corroboration / Evidence Resolution

### Problema

Contradictions sin un sistema de corroboración solo producen conflicto estático.

### Capability

Los Facts pueden aportar evidencia a una proposición.

Fuentes posibles:

- direct witness;
- object evidence;
- document;
- sensor;
- institutional report;
- social transfer.

El engine calcula deterministicamente cuándo una claim gana soporte, pierde soporte o queda resuelta.

### Regla importante

No debe implementarse como “la IA decide cuál parece verdadera”.

Debe usar authored rules / evidence classes / confidence / provenance.

### Resultado

```text
claim A confidence/evidence 2
claim B confidence/evidence 5
→ claim B RESOLVED
→ claim A puede pasar a RETRACTED o SUPERSEDED según regla authored
```

---

## 6. v1.05 — Classification / Secrecy / Information Permissions

### Problema

Actualmente disclosure y institutional routing controlan algunos accesos, pero no existe una clasificación general reusable.

### Capability

Facts podrían llevar una clasificación como:

```text
PUBLIC
INTERNAL
RESTRICTED
SECRET
```

Los nombres exactos deben quedar authored por la aplicación, pero la semántica de gate debe ser estable.

### Receptor authorization

Un target necesita autorización según:

- faction;
- role;
- rank;
- authority;
- clearance;
- relación especial.

### Consecuencia

Un NPC puede conocer un Fact y aun así no tener permiso para compartirlo con cualquier persona.

### Uso

- secretos militares;
- investigaciones;
- archivos inquisitoriales;
- información noble;
- rutas de contrabando;
- secretos de culto.

---

## 7. v1.06 — Trust graph entre source y receiver

### Problema

Dos fuentes distintas pueden transmitir el mismo Fact, pero el receptor debería valorar distinto sus testimonios.

### Capability

Trust como propiedad de relación, no del Fact global.

Ejemplo:

```text
Mara confía 80 en Oficial A
Mara confía 20 en Contrabandista B
```

Cuando ambos transmiten una claim, el trust afecta confidence/corroboration del holder receptor.

### Interacción con sistemas existentes

```text
relationship familiarity
+ trust
+ provenance
+ holder acquisition
→ confidence update
```

### Regla

Trust no es “simpatía”. Puede ser específico por dominio en una versión futura, pero v1.06 debería empezar con una métrica clara y limitada.

---

## 8. v1.07 — Rumor derivation / Information degradation

### Problema

El Fact exacto actualmente puede viajar preservando su contenido. Eso es correcto para evidencia formal, pero no modela rumor oral.

### Capability

Introducir **derived Facts** para canales que permitan degradación.

Ejemplo:

```text
Direct witness:
“Vi a un hombre de abrigo rojo entrar al Almacén 7 a las 02:10.”

Hop social 1:
“Un testigo vio a un hombre de abrigo rojo entrar al Almacén 7.”

Rumor derivado:
“Dicen que alguien sospechoso entró a un almacén durante la noche.”
```

### Regla crítica

No dejar que el LLM modifique arbitrariamente el estado.

La degradación debe ocurrir mediante transforms authored:

```text
remove exact time
remove identity detail
generalize place
lower confidence
change fact_type to RUMOR
```

El LLM puede renderizar lenguaje después de que el transform determinista decide qué información permanece.

### Provenance

El derived Fact debe conservar referencia a:

```text
origin_fact_id
parent_fact_id
transformation_id
```

---

## 9. v1.08 — Freshness / Temporal validity / Expiration

### Problema

v1.01 resolvió `ACTIVE/RETRACTED/SUPERSEDED`, pero un Fact puede ser verdadero históricamente y dejar de describir el presente sin ser “falso”.

Ejemplo:

```text
“La puerta está abierta.”
```

Puede ser correcto a las 08:00 y obsoleto a las 14:00.

### Capability

Metadata temporal:

```text
observed_at
valid_from
valid_until
freshness_class
```

Estados derivados posibles:

```text
CURRENT
STALE
EXPIRED
```

### Diferencia con lifecycle

- `RETRACTED`: holder declara que el Fact ya no debe usarse como verdad.
- `SUPERSEDED`: existe una versión reemplazante.
- `STALE`: el dato puede haber sido verdadero pero ya no es suficientemente reciente.

### Uso

- posiciones de NPC;
- puertas;
- rutas;
- precios;
- órdenes;
- disponibilidad;
- incidentes recientes.

---

## 10. v1.09 — Jurisdiction / Institutional Scope

### Problema

Una policy de facción puede saber a quién reportar, pero todavía falta una noción general de **dónde y sobre qué tiene autoridad una institución**.

### Capability

Definir jurisdiction por:

- region/zone/room;
- faction territory;
- incident type;
- object class;
- person class;
- legal domain.

### Ejemplo

```text
Guardia de Dársena
→ autoridad sobre muelles y carga

Eclesia
→ autoridad sobre herejía y ciertos territorios

Windrago
→ autoridad naval/aérea específica
```

### Routing

Un incidente puede generar:

```text
responsible institutions
→ jurisdiction match
→ protocol selection
```

No todo Fact debe ir a toda institución que esté presente.

---

## 11. v1.10 — Institutional Multi-Step Workflows

### Problema

Actualmente un Fact puede producir goals y subir por una cadena de mando. Falta convertir eso en un protocolo institucional de varios pasos.

### Capability

Workflow authored:

```text
INCIDENT RECEIVED
→ REVIEW
→ ASSIGN INVESTIGATOR
→ TRAVEL TO SITE
→ INSPECT
→ PRODUCE FINDINGS
→ REPORT UPCHAIN
→ DECISION
→ ENFORCEMENT / CLOSE
```

### Componentes

- workflow definition;
- workflow instance persistente;
- step IDs;
- requirements;
- assigned actors;
- timeouts;
- outputs;
- cancellation;
- escalation;
- audit trail.

### Ejemplo completo

```text
Trabajador presencia asesinato
→ Fact SECURITY_INCIDENT severity 5
→ supervisor recibe
→ policy crea INVESTIGATION workflow
→ guardia disponible recibe orden
→ guardia camina a la escena
→ percepción descubre arma
→ Fact EVIDENCE
→ workflow step completa
→ supervisor recibe findings
→ orden de captura
```

Esto convierte el engine en un simulador institucional real, no solo un propagador de información.

---

## 12. v1.11 — Causal Trace / Deterministic Replay

### Problema

El sistema ya conserva muchos IDs e historiales, pero un framework reusable necesita responder de forma uniforme:

```text
¿Por qué Mara está caminando a la Plaza?
```

### Capability

Un causal trace unificado:

```text
NPC movement
← selected goal
← SHARE_FACT obligation
← faction policy
← Fact known
← transfer from Informant
← Fact consequence
← player action
← object action
← resolution attempt
```

### Requisitos

Cada mutación importante debe registrar:

- cause id;
- parent cause id;
- subsystem;
- entity;
- timestamp;
- before/after summary;
- authored rule id;
- relevant Fact / action / event IDs.

### Beneficio

Debug, QA, player-facing explainability, herramientas de diseño y reproducción de bugs.

---

## 13. v1.12 — Scale / Scheduling / Performance

### Problema

El piloto demuestra corrección con pocos actores. Un framework serio debe probar carga real.

### Stress targets iniciales

Ejemplo de batería:

```text
100 NPC
1,000 Facts
50 factions
500 active social obligations
200 concurrent goals
large room graph
```

Después subir gradualmente.

### Qué medir

- decision step cost;
- faction policy projection cost;
- Fact retrieval cost;
- pathfinding cost;
- relationship refresh cost;
- social propagation storm risk;
- persistence write rate;
- Ollama queue contention.

### Posibles optimizaciones

Solo si los tests lo justifican:

- indexes por fact_type;
- holder index;
- faction membership cache;
- dirty flags;
- incremental refresh;
- scheduled simulation slices;
- distance cache;
- event-driven invalidation.

No optimizar antes de medir.

---

## 14. v1.13 — Authoring / Debug / Inspection Tooling

### Problema

Un framework puede ser correcto pero inutilizable si diseñar contenido exige leer atributos internos de Evennia.

### Capability

Herramientas de inspección legibles.

Ejemplos:

```text
siza-fact-trace FACT-X
```

Resultado:

```text
FACT-X
holders: 14
ACTIVE: 11
RETRACTED: 2
SUPERSEDED: 1
origin: Player action ACT-X
first holder: Mara
```

```text
siza-why Mara
```

Resultado:

```text
current activity: traveling to Plaza
selected goal: RELATIONSHIP:SHARE-FACT...
source rule: FACTION_POLICY...
source fact: FACT-X
priority: 900
reason target selected: nearest eligible authority
```

### Tooling mínimo esperado

- inspect Fact holders;
- inspect Fact lifecycle;
- inspect transfer graph;
- inspect faction policies;
- inspect active workflows;
- inspect goal competition;
- inspect why-action trace;
- validate authored definitions;
- detect dangling IDs;
- detect conflicting rules;
- export diagnostic snapshot.

---

# PARTE III — QUÉ NO ENTRA EN ESTE ROADMAP

## 15. Sistemas que NO deben aparecer como “una versión más” sin proyecto concreto

No forman parte automática del Simulation Framework 2.0:

- economía completa de oferta/demanda;
- sistemas legales universales;
- epidemias;
- política electoral;
- reproducción/población biológica;
- ecología completa;
- clima sistémico complejo;
- geopolítica autónoma infinita;
- mercados bursátiles;
- simulación física general;
- personalidad psicológica ilimitada;
- generación procedural total del mundo.

Si SIZA necesita alguno, se diseña como subsystem del juego sobre el framework, no como requisito para declarar el framework completo.

---

# PARTE IV — TCG: SISTEMA SEPARADO

## 16. Por qué el TCG se termina aparte

El World Engine y el TCG tienen responsabilidades distintas.

### World Engine

Autoridad sobre:

- quién está dónde;
- qué ocurrió;
- por qué ocurre un conflicto;
- qué participantes entran;
- condiciones previas;
- consecuencias persistentes después del combate.

### TCG

Autoridad sobre:

- reglas del encounter de combate;
- cartas;
- mana/resources;
- invocaciones;
- reacciones;
- daño de combate;
- victoria/derrota dentro del encounter.

El TCG no debe modificar directamente Rooms, faction policies, Facts o world state.

---

## 17. CONFRONT vs COMBAT_CONFRONTATION

El World Engine ya tiene `CONFRONT`:

```text
d6 + stat actor vs d6 + stat target
```

Se conserva para confrontaciones rápidas.

Ejemplos:

- intimidación;
- presión;
- arrebatar objeto;
- resistir empujón;
- competencia directa.

Un conflicto que deba convertirse en combate completo genera otro tipo conceptual:

```text
COMBAT_CONFRONTATION
```

Ese encounter abre el TCG.

---

## 18. Combat Bridge — contrato previsto

### World Engine → TCG

```text
encounter_id
attacker_ids
defender_ids
location_id
reason / trigger
world_context_tags
adventure status modifiers
deck/loadout references
initiative/context if applicable
special encounter rules
stakes
```

El bridge debe entregar IDs y datos autorizados, no referencias ambiguas de texto.

### TCG → World Engine

```text
encounter_id
winner / result
participant outcomes
remaining health/status
resources spent
cards/effects with world relevance
fled
surrendered
captured
defeated
dead (si la regla del juego lo permite)
outcome tags
```

El World Engine recibe el resultado y genera consecuencias persistentes.

---

## 19. Ejemplo Combat Bridge

```text
Jugador intenta arrestar contrabandista
→ action / interaction determina resistencia
→ COMBAT_CONFRONTATION
→ encounter creado

TCG inicia
→ combate completo
→ PLAYER_WIN
→ contrabandista DEFEATED
→ player resource spent = X

Bridge devuelve outcome

World Engine:
→ NPC status = wounded/captured
→ world state cambia
→ SITE_NPCS reciben Fact del combate
→ faction policy reacciona
→ supervisor puede recibir reporte
→ new goals
```

---

## 20. Regla de implementación del bridge

No implementar el bridge final hasta que el TCG tenga estables:

- identidad de combatientes;
- estructura de deck/loadout;
- estados de victoria;
- estados de derrota;
- damage/status contract;
- escape/surrender/capture;
- persistencia de resources relevante.

Antes de eso solo se documenta el contrato.

---

# PARTE V — ORDEN RECOMENDADO

## 21. Si el objetivo inmediato es terminar SIZA

```text
1. cerrar aceptación manual v1.01
2. freeze World Engine
3. terminar TCG
4. construir contenido real de Rivarica
5. Combat Bridge
6. vertical slice
7. publisher package
```

No construir v1.02–v1.13 antes de necesitarlo.

---

## 22. Si el objetivo cambia a vender/licenciar el Simulation Framework

Entonces sí:

```text
v1.02 Confidence
v1.03 Contradictions
v1.04 Corroboration
v1.05 Classification / Secrecy
v1.06 Trust
v1.07 Rumors / Degradation
v1.08 Freshness / Expiration
v1.09 Jurisdiction
v1.10 Institutional Workflows
v1.11 Causal Trace / Replay
v1.12 Scale / Performance
v1.13 Authoring / Debug Tooling
→ Framework 2.0 freeze
```

Este orden debe considerarse el roadmap cerrado. Si una feature nueva aparece, debe justificar por qué sustituye o entra dentro de uno de estos bloques; no se aumenta automáticamente la lista.

---

# PARTE VI — DEFINICIÓN DE “EXTREMADAMENTE ROBUSTO”

## 23. Estado objetivo

Al completar este roadmap, el sistema debería poder representar una cadena como:

```text
Player action
→ World consequence
→ direct witness Fact
→ confidence based on provenance
→ contradiction with existing claim
→ corroborating evidence
→ claim resolution
→ classified institutional report
→ receiver trust modifies confidence
→ jurisdiction selects responsible institution
→ workflow opens investigation
→ assigned NPC travels
→ evidence found
→ new Fact
→ upchain report
→ command decision
→ enforcement action
→ TCG combat if escalation reaches combat
→ TCG outcome
→ persistent world consequences
→ witnesses / rumors / institutional memory
→ causal trace explains every step
```

Todo sin entregar autoridad del mundo al LLM.

---

## 24. Arquitectura objetivo final

```text
                         WORLD BOOK
                             ↓
                       AUTHORED CANON
                             ↓
┌───────────────────────────────────────────────────────────┐
│                    SIZA SIMULATION FRAMEWORK              │
│                                                           │
│  SPACE / WORLD STATE                                      │
│        ↓                                                  │
│  ACTION / RESOLUTION / CONSEQUENCE                        │
│        ↓                                                  │
│  EVENTS / FACTS                                           │
│        ↓                                                  │
│  PROVENANCE / LIFECYCLE / CONFIDENCE / CONTRADICTION      │
│        ↓                                                  │
│  KNOWLEDGE / TRUST / RUMOR / TEMPORAL VALIDITY            │
│        ↓                                                  │
│  FACTIONS / AUTHORITY / JURISDICTION / POLICIES           │
│        ↓                                                  │
│  INSTITUTIONAL WORKFLOWS                                  │
│        ↓                                                  │
│  NPC GOALS / NEEDS / JOBS / ORDERS / RELATIONSHIPS        │
│        ↓                                                  │
│  MOVEMENT / INTERACTION / INVESTIGATION                   │
│        ↓                                                  │
│  NEW WORLD STATE                                          │
│                                                           │
│  CROSS-CUTTING: causal trace / QA / authoring / scaling   │
└───────────────────────────────────────────────────────────┘
                             ↓
             COMBAT ENCOUNTER WHEN REQUIRED
                             ↓
                            TCG
                             ↓
                   STRUCTURED OUTCOME
                             ↓
                    WORLD CONSEQUENCE
```

---

## 25. Criterio de terminación

El Simulation Framework se considera terminado cuando:

1. los 12 bloques descritos están implementados o deliberadamente descartados con razón documentada;
2. existe stress QA representativo;
3. un causal trace permite explicar decisiones importantes;
4. el authoring no exige editar internals a ciegas;
5. el LLM permanece sin autoridad de mutación;
6. el framework puede ejecutar al menos una cadena institucional multi-hop completa;
7. el Combat Bridge posee contrato estable con el TCG;
8. no existen capabilities abiertas sin un caso real de producto.

En ese punto:

> **SIZA Simulation Framework 2.0 — FEATURE COMPLETE / FROZEN**

---

## 26. Decisión vigente

La decisión recomendada para el proyecto SIZA actual es **NO perseguir automáticamente este roadmap**.

Primero se congela el core v1.01 y se utiliza para construir el juego. El roadmap queda documentado para que, si más adelante existe una razón comercial o técnica para desarrollar el framework general, la línea de meta ya esté definida y no vuelva a crecer de manera indefinida.
