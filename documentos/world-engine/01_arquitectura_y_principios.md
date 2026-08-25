# 01 — Arquitectura y principios del SIZA World Engine

**Versión:** Core Freeze Candidate v1.01.1  
**Alcance:** arquitectura implementada del World Engine.  
**No incluye:** reglas internas del TCG ni canon del World Book.

## 1. Principio rector

SIZA separa **autoridad de mundo** de **interpretación/redacción**.

La autoridad está en código determinista y estado persistente. La IA local puede interpretar lenguaje dentro de capacidades autorizadas y puede redactar resultados grounded, pero no tiene permiso para crear realidad por sí misma.

```text
PLAYER / NPC INPUT
        ↓
parser / classifier / proposal
        ↓
capability autorizada
        ↓
engine determinista
        ↓
mutación persistente
        ↓
resultado estructurado
        ↓
contexto grounded
        ↓
redacción opcional del LLM
```

Este orden no debe invertirse.

## 2. Capas del sistema

### 2.1 Evennia como sustrato persistente

Evennia aporta:

- Characters y NPC Objects persistentes;
- Rooms;
- Exits;
- Scripts persistentes;
- Attributes `db.*`;
- comandos;
- webclient;
- búsqueda por objetos/tags/scripts;
- lifecycle del servidor.

El World Engine no mantiene un “mapa imaginado” en memoria del LLM. La ubicación real es `Character.location`, las conexiones son Exits reales y el estado vive en atributos persistentes.

### 2.2 Typeclasses

Las typeclasses representan las familias principales de objetos persistentes:

- `characters.py`: Player Character base de SIZA.
- `npcs.py`: NPC persistente y datos de simulación.
- `rooms.py`: Room con presentación/estado de SIZA.
- `exits.py`: Exit con gating persistente.
- `siza_objects.py`: objetos interactuables del mundo.
- `world_tick.py`: Script global de simulación.
- `faction_registry.py`: registro persistente de definiciones de facción.
- `consequence_registry.py`: registro persistente para reglas/consecuencias.

La lógica compleja se mantiene en `services/`; las typeclasses no deben convertirse en archivos monolíticos de gameplay.

### 2.3 Services

`overlay/services/` contiene autoridades de dominio pequeñas o medianas. Ejemplos:

- acción y requirements;
- resolución de checks;
- world state/consequences;
- percepción;
- Knowledge/Facts;
- NPC simulation/decision;
- necesidades/trabajos/eventos;
- facciones/órdenes;
- relaciones y transferencia social;
- políticas institucionales;
- propuesta de intents;
- narration/dialogue grounded;
- Ollama.

La intención es que cada servicio tenga un contrato suficientemente aislado para probarlo de forma determinista.

### 2.4 Commands

`overlay/commands/` expone:

- comandos de juego;
- herramientas Admin;
- validators versionados;
- natural-input `__nomatch__`;
- `siza-qa-latest`.

Los validators no son una segunda implementación del sistema: llaman la autoridad real y comprueban sus efectos sobre estado real, restaurando después el snapshot.

### 2.5 World seed/upgrades

`overlay/world/` contiene:

- seed inicial de Kalnaj/Dársenas;
- upgrades incrementales del piloto;
- contenido de validación authored.

Estos scripts preparan fixtures persistentes. No son el sitio donde debe vivir una regla global de gameplay.

## 3. Autoridades principales

### 3.1 Geometría

Autoridad:

```text
Room + Exit + destination + Character.location
```

La IA no puede inventar que existe una puerta o que una Room conecta con otra. Movimiento válido pasa por Exit real o por pathfinding sobre el grafo real.

### 3.2 Estado físico / world state

Estado persistente de Room, Exit, Object o entidades se modifica por engines deterministas de state effects/consequences.

Presentation engines leen ese estado para cambiar lo visible sin duplicar la autoridad.

### 3.3 Acciones

Una Action authored define qué puede intentarse, qué requisitos tiene y si requiere check. El Player/NPC no obtiene permiso porque el texto “suene plausible”.

### 3.4 Resolución

El lifecycle de resolución separa:

```text
acción elegible
→ check preparado
→ provider de resolución
→ outcome autorizado
→ consecuencia
```

Las fórmulas existentes se documentan en `02_sistemas_implementados.md`.

### 3.5 Knowledge

Knowledge tiene dos niveles relacionados pero distintos:

- `knowledge` — niveles numéricos por `knowledge_key`;
- `knowledge_facts` — Facts estructurados con identidad, texto, provenance, lifecycle y metadata.

`fact_knowledge_state()` es la autoridad compartida que decide si un Fact es actualmente utilizable.

Desde v1.01 un Fact puede permanecer almacenado y recordado históricamente aunque no esté vivo para decisiones:

```text
level_known = True
known       = False
fact_status = RETRACTED / SUPERSEDED
```

### 3.6 NPC decisions

El NPC no recibe una respuesta libre del LLM sobre “qué hacer”. El decision engine reúne candidates authored/derivados, comprueba reachability, aplica modificadores y elige el de mayor prioridad efectiva.

Las prioridades base actuales son:

```text
DANGER       100
EVENT         80
NEED          70
ORDER         60
JOB           60
RELATIONSHIP  50
ROUTINE       10
```

Estas prioridades son configurables por NPC mediante `decision_priorities` y pueden ser modificadas por personalidad/contexto.

### 3.7 Instituciones

Las facciones poseen definición persistente, rangos y authority. Una membership de NPC puede incluir:

- facción;
- active;
- rank/rank_id;
- role;
- loyalty_bias;
- authority_level explícito o derivado del rango.

Las políticas institucionales se proyectan en reglas managed de NPC y después reutilizan el pipeline social común. Esto evita duplicar un segundo motor de transferencia para facciones.

## 4. World Tick

`SizaWorldTick` es el scheduler global persistente.

Su orden actual es deliberado:

```text
1. advance_world_clock
2. refresh_world_job_rules
3. refresh_world_event_rules
4. collect simulated NPCs
5. advance_need_dynamics de cada NPC
6. release_offshift_claims
7. refresh/arbitrate job claims globalmente
8. ejecutar un tick de cada NPC
9. aplicar activity need dynamics según lo que hizo
10. persistir trace/estado del tick
```

Este orden importa. Por ejemplo, los jobs se producen y arbitran antes de que los NPC intenten reclamarlos; las necesidades cambian antes de elegir acción; y el resultado de la acción afecta después el consumo/recuperación de necesidades.

El trace global conserva una ventana corta de ticks con:

- reloj;
- producers;
- events;
- handoffs;
- arbitration;
- needs;
- activity dynamics;
- resultados de NPC.

## 5. Reloj y schedules

El World Clock persistente guarda:

```text
world_day
world_minute
world_minutes_per_tick
```

El tiempo de día es 0–1439 minutos. Los schedules permiten ventanas normales o que crucen medianoche.

El reloj sirve a:

- rutinas;
- turnos;
- jobs;
- eventos;
- handoff de trabajo;
- necesidades dependientes del paso del tiempo.

No equivale al tiempo real del servidor. Es tiempo de simulación.

## 6. NPC autonomy

El decision loop actual puede recoger candidates desde:

- goals authored persistentes;
- world events;
- necesidades;
- jobs;
- relaciones/obligaciones sociales;
- rutina fallback.

Después:

```text
candidate
→ target existe?
→ reachable por find_path?
→ path_length
→ personality/context modifiers
→ effective_priority
→ sort
→ selected
```

El NPC mueve físicamente su `location` por el grafo hasta el target. Al llegar, el engine específico resuelve la finalidad:

- Event → acknowledge;
- Need → completion effects de affordance;
- Job → work progress/claim release;
- Relationship → resolver obligación social;
- authored one-shot → desactivar/completar;
- Routine → continuar schedule.

## 7. Goals como estado derivado

Un Goal puede venir de muchas fuentes. Para evitar estado zombie, los systems que materializan goals deben responsabilizarse de retirar o cancelar derivados cuando su fuente deja de ser válida.

Ejemplo v1.01:

```text
Fact ACTIVE
→ materializa Fact-goal

Fact RETRACTED
→ goal existente se cancela
  cancellation_reason = SOURCE_FACT_NO_LONGER_ACTIVE

mismo Fact vuelve ACTIVE
→ sólo ese goal lifecycle-cancelled puede reactivarse

Goal one-shot ya COMPLETED
→ no revive
```

Esta distinción es un patrón que debe conservarse en extensiones futuras.

## 8. Fact-driven wrapper

La capa `fact_driven_decision.py` prepara estado social antes de delegar al decision engine histórico.

A nivel conceptual:

```text
refresh Fact-goals
→ sync faction Fact-share policies
→ aplicar holder acquisition gate
→ refresh SHARE_FACT obligations
→ choose/execute normal NPC decision
```

Así las features nuevas de información no reescriben `npc_decision.py`; alimentan candidates/obligations que el decision engine ya sabe manejar.

## 9. Flujo social de Facts

Una transferencia social completa no es una copia instantánea a distancia.

```text
source conoce Fact exacto
→ policy/rule activa
→ target elegible
→ create/reactivate SHARE_FACT obligation
→ Relationship candidate
→ NPC viaja hacia target
→ co-location
→ resolve relationship goal
→ transfer_knowledge_fact
→ target adquiere Fact
→ transfer_history se agrega
```

Esto permite que el mundo observe el viaje y que el comportamiento tenga costo espacial/temporal.

## 10. Pipeline institucional

Una `fact_share_policy` de facción puede seleccionar un Fact exacto o un tipo de Fact.

El orden conceptual es:

```text
membership activa
→ faction activa
→ policy enabled
→ selector EXACT o TYPE
→ severity filter opcional
→ managed rule exacta por fact_id
→ conflicto/local override
→ holder acquisition gate
→ source-awareness
→ target faction/authority
→ authority relation
→ need-aware pruning
→ NEAREST/max_targets
→ SHARE_FACT
```

Importante: aunque una policy se authorée por `fact_type`, la transferencia final siempre se hace por `fact_id` concreto.

## 11. IA como capa no autoritativa

Hay dos usos distintos del LLM:

### Interpretación/proposal

Cuando una frase no coincide con rutas deterministas fuertes, el modelo puede recibir una lista cerrada de capabilities/targets y proponer una intención estructurada. El bridge vuelve a validar antes de ejecutar.

### Narración/dialogue

El modelo recibe contexto grounded construido desde world state y Facts conocidos autorizados. No recibe Facts privados desconocidos “por si acaso”.

Si Ollama falla, el estado ya resuelto no se revierte.

## 12. Fail-closed como regla arquitectónica

La robustez del World Engine depende de no “adivinar” metadata authored.

Algunos ejemplos de errores que deben bloquear:

```text
BAD_STAT
BAD_TRIGGER
BAD_MODE
BAD_MIN_AUTHORITY
BAD_AUTHORITY_RELATION
BAD_SELECTION
BAD_MAX_TARGETS
AMBIGUOUS_FACT_SELECTOR
BAD_SEVERITY_FILTER
MULTIPLE_INHERITED_POLICIES_FOR_FACT
BAD_HOLDER_ACQUISITION
BAD_FACT_STATUS
```

Un sistema general de simulación se vuelve impredecible si los errores authored se convierten silenciosamente en otra regla.

## 13. Identidad vs presentación

No se debe usar texto visible como única identidad si existe persistencia.

Preferir:

```text
CAR-KAL-DAR-007           room_id
NPC-KAL-DAR-MARA-001      npc_id
FACT-...                   fact_id
GOAL-...                   goal_id
SHARE-FACT-...             obligation_id
POLICY-...                  policy id
ACT-...                     action id
```

Los nombres visibles son presentación y pueden editarse. Los IDs son contratos.

## 14. Separación con el TCG

El World Engine puede detectar una situación que deba convertirse en combate, pero no debe ejecutar las reglas internas del TCG.

Arquitectura futura:

```text
World Engine
→ crea Combat Encounter autorizado
→ pausa/cede resolución de esa confrontación
→ TCG recibe snapshot de participantes/contexto
→ TCG juega
→ devuelve outcome estructurado
→ World Engine valida/aplica outcome
→ consecuencias / Facts / reacciones institucionales
```

El `CONFRONT` d6 actual permanece para oposición rápida no-TCG.

## 15. Criterio de freeze

El World Engine no necesita modelar toda sociedad posible antes de producir SIZA. El core actual se considera suficiente cuando puede:

- representar el contenido requerido por el juego;
- resolver cambios de mundo sin LLM;
- producir NPC autonomy inspectable;
- conservar causalidad mínima;
- integrar el TCG por contrato;
- crecer mediante datos authored sin reescribir el motor por cada quest.

Una extensión posterior debe justificarse por gameplay o por la decisión explícita de continuar el roadmap de simulation framework.
