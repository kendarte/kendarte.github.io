# 03 — Modelos de datos y contratos del SIZA World Engine

**Versión:** Core Freeze Candidate v1.01.1  
**Alcance:** formas persistentes y authored principales.  
**Nota:** los ejemplos muestran campos representativos/actualmente usados; no son una promesa de que cada diccionario acepte cualquier campo arbitrario.

## 1. Regla general de persistencia

SIZA utiliza Attributes persistentes de Evennia (`db.*`) y objetos/scripts persistentes.

El patrón común es:

```text
contenido authored
→ normalización
→ identidad estable
→ persistencia
→ service authority
→ packet estructurado
```

Nunca se debe depender de que el texto visible sea la única identidad de una entidad sistémica.

## 2. Identidades

Convenciones usadas en el proyecto:

```text
room_id        CAR-KAL-DAR-007
npc_id         NPC-KAL-DAR-MARA-001
fact_id        FACT-...
action id      ACT-...
goal id        GOAL-...
policy id      POLICY-...
rule id        RULE-... / FACT-SHARE-...
task id        TEST-WORKORDER-...
obligation id  SHARE-FACT-<target_npc_id>-<fact_id>
```

Los prefijos concretos son convenciones de authoring, no un parser universal. La propiedad importante es que el ID sea estable y único dentro del dominio correspondiente.

## 3. Character / NPC — campos persistentes relevantes

Según los sistemas activos, un Character/NPC puede usar varios Attributes.

### Identidad y simulación

```python
npc.db.npc_id
npc.db.is_npc
npc.db.decision_enabled
npc.db.current_goal
npc.db.destination_id
npc.db.current_activity
```

### Adventure

```python
npc.db.adventure_stats = {
    "FUE": 4,
    "AGI": 3,
    "COO": 5,
    "INT": 6,
    "PER": 4,
    "PSI": 2,
}
```

Stats faltantes se consideran no authored para checks que requieren el stat.

### Skills / Traits

Los engines correspondientes mantienen diccionarios/listas persistentes de Skills y Traits. Las Actions consumen esos datos mediante requirement checks.

### Knowledge levels

```python
npc.db.knowledge = {
    "TEST_DARSENA_WORK": 1,
    "V086_INFORMANT_AUDIT_SEAL": 1,
}
```

Los valores son niveles numéricos normalizados a entero cuando el engine los lee.

### Facts

```python
npc.db.knowledge_facts = [
    {...},
    {...},
]
```

Cada Fact tiene ID propio y se maneja idempotentemente por ese ID.

### Decisions

```python
npc.db.decision_priorities
npc.db.decision_goals
npc.db.current_goal
```

### Needs

```python
npc.db.needs
npc.db.need_rules
```

### Relationships

```python
npc.db.relationships = {
    "TARGET-NPC-ID": {
        "target_npc_id": "...",
        "target_dbref": 27,
        "target_name": "...",
        "obligations": [...],
        # otros campos sociales authored/históricos
    }
}
```

### Factions

```python
npc.db.faction_memberships = [
    {
        "faction_id": "FACTION-ID",
        "active": True,
        "rank_id": "RANK-ID",
        "rank": "Nombre",
        "role": "supervisor",
        "loyalty_bias": 0,
        # authority_level puede existir como override
    }
]
```

### Social Fact rules

```python
npc.db.fact_share_rules
npc.db.fact_share_obligation_sources
```

Las reglas heredadas de facción conviven con reglas locales, pero llevan metadata managed para poder sincronizarlas/retirarlas de forma determinista.

## 4. Room

Campos frecuentes en el piloto/sistemas:

```python
room.db.room_id
room.db.world_actions
room.db.need_affordances
room.db.world_state / state relacionado
```

Una Room puede además llevar metadata/tags usados por jobs, needs, events o percepción.

El nombre visible de Room no sustituye `room_id` cuando una regla necesita identidad estable.

## 5. Exit

Un Exit conserva el destination real de Evennia y puede tener estado/gates persistentes.

Conceptualmente:

```python
exit.destination
exit.db.exit_id
exit.db.state / gate fields
```

El engine de gating decide si traversal está permitido; el narrador no puede cambiar ese resultado.

## 6. Siza Object

Objetos interactuables pueden tener:

```python
obj.db.object_id
obj.db.object_actions
obj.db.state / visibility metadata
```

Object Actions permiten que un objeto sea actor de una secuencia de gameplay sin escribir un Command único por cada objeto.

## 7. World Action spec

Las acciones locales authored se almacenan en `site.db.world_actions`.

Forma representativa:

```python
{
    "id": "ACT-EXAMPLE-001",
    "enabled": True,
    "name": "analizar el manifiesto",
    "activity": "analizando el manifiesto",
    "canon_status": "prototype",
    "metadata": {},
    "skill_requirements": [
        {
            "skill": "ARCHIVO",
            "min": 1,
        }
    ],
    "knowledge_requirements": [
        {
            "knowledge_key": "SOME_KNOWLEDGE",
            "min": 1,
        }
    ],
    "check": {
        "trigger": "OBSTACLE",
        "mode": "DIRECT",
        "stat": "PER",
        "difficulty": 7,
    },
}
```

Los nombres exactos de campos internos de requirement rows deben seguir el engine de requirements correspondiente; el ejemplo expresa la semántica, no autoriza aliases nuevos.

### Action attempt record

Al comenzar una acción se crea un record histórico con datos como:

```python
{
    "attempt_id": "WACT-...",
    "world_action_id": "ACT-...",
    "world_action_name": "...",
    "activity": "...",
    "actor_npc_id": "...",
    "actor_name": "...",
    "site_room_id": "...",
    "site_dbref": 9,
    "site_name": "...",
    "created_at": "...",
    "requirement_check": {...},
    "status": "PENDING_RESOLUTION",
    "resolution_id": "...:RESOLUTION",
}
```

Si no hay check, puede completar de inmediato y emitir consequence.

## 8. Check spec

Stats válidos:

```text
FUE AGI COO INT PER PSI
```

Triggers válidos:

```text
OBSTACLE
OPPOSITION
SYNCHRONY
```

Modes válidos:

```text
DIRECT
ACCUMULATE
CONFRONT
SYNCHRONIZE
```

Forma:

```python
{
    "id": "CHECK-ID",           # opcional
    "trigger": "OBSTACLE",
    "mode": "DIRECT",
    "stat": "PER",
    "target_stat": None,
    "difficulty": 7,
    "metadata": {},
}
```

`target_stat` se usa cuando el mode/acción necesita target authored.

## 9. Resolution record

Un check preparado guarda identidad y snapshot de los stats necesarios antes de resolverse.

Campos representativos:

```python
{
    "resolution_id": "...",
    "mode": "DIRECT",
    "trigger": "OBSTACLE",
    "actor_stat": "PER",
    "actor_stat_value": 4,
    "target_stat": None,
    "target_stat_value": None,
    "difficulty": 7,
    "resolved": False,
    "outcome": None,
}
```

El provider que resuelve debe entregar un outcome permitido para el mode.

## 10. Fact

Forma extensa representativa:

```python
{
    "id": "FACT-SECURITY-001",
    "topic": "incidente en la dársena",
    "aliases": ["incidente", "reporte"],
    "text": "Se observó ...",
    "response": "Se observó ...",

    "knowledge_key": "SECURITY_INCIDENT_001",
    "required_level": 1,

    "fact_type": "SECURITY_INCIDENT",
    "severity": 4,

    "canon_status": "prototype",

    "source": {
        "kind": "DIRECT_SITE_WITNESS",
        "object_id": None,
        "site_room_id": "CAR-KAL-DAR-007",
        "site_dbref": 9,
        "site_name": "Pescaderia de Darsena",
    },

    "learned_by": {
        "mode": "SITE_PRESENCE",
        "provider": "...",
        "action_id": "...",
    },

    "transfer_history": [
        {
            "id": "FACT_TRANSFER:...",
            "fact_id": "FACT-SECURITY-001",
            "mode": "DIRECT_LOCAL",
            "source_npc_id": "NPC-A",
            "source_name": "A",
            "target_npc_id": "NPC-B",
            "target_name": "B",
            "shared_at": "...",
        }
    ],

    "decision_effects": [
        {
            "id": "EFFECT-...",
            "enabled": True,
            "value": 7,
            "when": {...},
        }
    ],

    "disclosure": {
        "min_familiarity": 2,
    },

    "fact_status": "ACTIVE",
    "fact_status_changed_at": None,
    "fact_status_reason": None,
    "superseded_by_fact_id": None,
    "fact_lifecycle_history": [],

    "learned_at": "...",
}
```

No todos los Facts necesitan todos los campos.

## 11. Fact lifecycle contract

Estados permitidos:

```text
ACTIVE
RETRACTED
SUPERSEDED
```

### ACTIVE

Es el default para backwards compatibility, incluso para Facts antiguos que no authored lifecycle inicialmente.

### RETRACTED

Conserva el record pero lo hace no utilizable para authorities vivas.

### SUPERSEDED

Requiere `superseded_by_fact_id` no vacío y distinto del propio Fact.

### Mutation packet

`set_knowledge_fact_status()` devuelve semántica explícita:

```python
{
    "success": True,
    "changed": True,
    "reason": "FACT_STATUS_CHANGED",
    "fact_id": "...",
    "before": "ACTIVE",
    "after": "RETRACTED",
    "fact": {...},
}
```

Valores de status desconocidos fallan `BAD_FACT_STATUS` y no mutan.

## 12. fact_knowledge_state

Contrato conceptual:

```python
{
    "knowledge_key": "...",
    "level": 1,
    "required_level": 1,
    "level_known": True,
    "known": True,
    "fact_status": "ACTIVE",
    "fact_status_valid": True,
    "fact_active": True,
    "fact_status_reason": None,
    "superseded_by_fact_id": None,
}
```

Distinción crucial:

```text
level_known
= el holder conserva nivel suficiente históricamente

known
= nivel suficiente Y Fact ACTIVE/válido
```

Los consumers deben usar `known` cuando necesitan autoridad viva.

## 13. Fact-goal rule

Forma representativa:

```python
{
    "id": "FACT-GOAL-SECURITY-001",
    "enabled": True,
    "fact_id": "FACT-SECURITY-001",
    "goal": {
        "id": "GOAL-INVESTIGATE-001",
        "type": "EVENT",
        "priority": 90,
        "active": True,
        "target_room_id": "...",
        "target_room_key": "...",
        "activity": "investigando el incidente",
        "one_shot": True,
    }
}
```

Al materializarse, el Goal recibe:

```python
fact_goal_rule_id
source_fact_id
```

El lifecycle engine puede marcar:

```python
status = "cancelled"
cancellation_reason = "SOURCE_FACT_NO_LONGER_ACTIVE"
```

## 14. Decision Goal

Forma general representativa:

```python
{
    "id": "GOAL-...",
    "type": "NEED" | "EVENT" | "ORDER" | "JOB" | "RELATIONSHIP" | "ROUTINE" | ...,
    "priority": 70,
    "active": True,
    "target_room_id": "...",
    "target_room_key": "...",
    "activity": "...",
    "one_shot": True,
    "source": "NPC_NEED" | "WORLD_EVENT" | "WORLD_JOB" | "RELATIONSHIP" | "AUTHORED_GOAL" | ...,
}
```

Durante evaluación se agregan datos derivados como:

```python
target_exists
at_target
reachable
path_length
base_priority
personality_modifier
effective_priority
priority_modifiers
```

## 15. current_goal

El selected goal se proyecta a `npc.db.current_goal` con metadata suficiente para inspección, incluyendo según source:

- id/type/priority;
- target;
- activity/source;
- event/order/faction/issuer;
- task/work/claim;
- relationship obligation/target;
- need/affordance;
- routine schedule.

No es una segunda autoridad del goal; es snapshot operativo del seleccionado.

## 16. Relationship record

Forma representativa:

```python
{
    "target_type": "NPC",
    "target_npc_id": "NPC-B",
    "target_dbref": 27,
    "target_name": "B",
    "obligations": [...],
}
```

Puede haber otros datos sociales, como familiarity, consumidos por disclosure.

## 17. SHARE_FACT obligation

Forma real utilizada:

```python
{
    "id": "SHARE-FACT-NPC-B-FACT-X",
    "kind": "SHARE_FACT",
    "active": True,
    "status": "pending",
    "priority": 945,
    "one_shot": True,
    "fact_id": "FACT-X",
    "activity": "buscando a B para compartir un dato conocido",
    "activated_at": "...",
    "created_at": "...",
    "canon_status": "prototype",
}
```

Estados terminales/cancelados conservan metadata como:

```python
cancelled_at
cancellation_reason
```

La identidad se conserva al reactivar para no duplicar historia.

## 18. Fact-share local rule

Forma representativa:

```python
{
    "id": "FACT-SHARE-X",
    "enabled": True,
    "fact_id": "FACT-X",

    "target_mode": "EXPLICIT" | "FACTION",
    "target_npc_id": "NPC-B",         # EXPLICIT
    "faction_id": "FACTION-X",       # FACTION

    "min_authority": 500,
    "authority_relation": "ANY" | "HIGHER_THAN_SOURCE",

    "selection": "ALL" | "NEAREST",
    "max_targets": 1,

    "holder_acquisition": "ANY" | "NONTRANSFERRED" | "LOCAL_TRANSFER",

    "priority": 900,
    "one_shot": True,
}
```

No todos los fields son válidos en todos los target modes. Valores malformed fallan cerrados según el engine.

## 19. Faction definition

Forma representativa:

```python
{
    "id": "FACTION-X",
    "name": "...",
    "active": True,
    "canon_status": "prototype",
    "ranks": {
        "RANK-1": {
            "id": "RANK-1",
            "name": "Supervisor",
            "authority_level": 500,
            "canon_status": "prototype",
        }
    },
    "fact_share_policies": [...],
}
```

El engine preserva metadata adicional authored siempre que no contradiga normalización requerida.

## 20. Faction membership

Forma representativa:

```python
{
    "faction_id": "FACTION-X",
    "active": True,
    "loyalty_bias": 0,
    "rank_id": "RANK-1",
    "rank": "Supervisor",
    "role": "supervisor",
    "authority_level": 500,  # opcional override
    "canon_status": "prototype",
}
```

Límites:

```text
loyalty_bias    -100..100
authority_level 0..1000
```

Si no hay authority override, se toma del rank.

## 21. Faction Fact-share policy

### Selector exacto v0.96

```python
{
    "id": "POLICY-REPORT-EXACT",
    "enabled": True,
    "fact_id": "FACT-X",
    "target_mode": "FACTION",
    "min_authority": 500,
    "selection": "NEAREST",
    "max_targets": 1,
    "priority": 900,
    "one_shot": True,
}
```

### Selector por tipo v0.97+

```python
{
    "id": "POLICY-REPORT-SECURITY",
    "enabled": True,
    "fact_type": "SECURITY_INCIDENT",
    "min_severity": 4,
    "max_severity": None,
    "target_mode": "FACTION",
    "min_authority": 800,
    "authority_relation": "HIGHER_THAN_SOURCE",
    "selection": "NEAREST",
    "max_targets": 1,
    "holder_acquisition": "LOCAL_TRANSFER",
    "priority": 950,
    "one_shot": True,
}
```

### Restricciones

```text
fact_id XOR fact_type
```

No se permiten ambos ni ninguno.

Severity filter requiere `fact_type`.

Si dos policies heredadas terminan coincidiendo sobre el mismo `fact_id` concreto para un holder, el conflicto falla cerrado.

## 22. Managed inherited rule

Una policy heredada se proyecta a rule local managed con metadata como:

```python
{
    "id": "FACTION_POLICY:FACTION-X:POLICY-X:FACT:FACT-Y",
    "fact_id": "FACT-Y",
    "authored_rule_id": "POLICY-X",
    "inherited_from_faction_id": "FACTION-X",
    "rule_scope": "FACTION_INHERITED",
    "fact_selector_mode": "TYPE",
    "authored_fact_type": "SECURITY_INCIDENT",
    "fact_severity": 5,
    "authored_min_severity": 4,
    "authored_max_severity": None,
    "managed_by": "0.96.0-inherited-faction-fact-share-policies",
    "source_membership_authority": 100,
    # más fields copiados de la policy
}
```

Estas rules se regeneran/sincronizan; no deben editarse manualmente como si fueran authoring local permanente.

## 23. Need rule

Forma conceptual:

```python
{
    "id": "NEED-HUNGER-HIGH",
    "enabled": True,
    "need_key": "hunger",
    "op": "gte",
    "value": 70,
    "affordance": "EAT",
    "priority": 70,
    "activity": "buscando comida",
}
```

Operators soportados por el need engine:

```text
lt lte gt gte eq ne
```

## 24. Need affordance

En un sitio tagged como need site:

```python
{
    "id": "AFFORDANCE-EAT-001",
    "enabled": True,
    "kind": "EAT",
    "need_key": "hunger",      # opcionalmente restringe
    "activity": "comiendo",
    "completion_effects": [
        {
            "field": "hunger",
            "op": "sub",
            "value": 50,
        }
    ],
}
```

Effects soportados por completion de need:

```text
set add sub min max
```

## 25. Job / Task

La implementación de jobs es más extensa que un único schema; los fields relevantes que circulan por decision/completion incluyen:

```text
task_id
work_done
work_required
work_per_action
claim_npc_id
claim_npc_name
status
site
completion_effects
claim policy/distance metadata
```

Los jobs son persistentes, pueden ser producidos/refrescados por rules y se arbitran globalmente antes de acciones de NPC.

## 26. World Event / Order

Los fields que llegan al decision engine incluyen según tipo:

```text
event_id
occurrence
target room/site
goal_type
priority
authority_id
authority_name
faction_id
issuer_id
issuer_name
order_id
order_kind
```

Event acknowledgement/completion vuelve al world event engine.

## 27. World Clock state

Forma:

```python
{
    "day": 0,
    "minute": 480,
    "time": "08:00",
    "minutes_per_tick": 10,
}
```

`minute` se normaliza 0–1439.

## 28. Schedule

Forma:

```python
{
    "enabled": True,
    "days": [0, 1, 2],
    "start_minute": 480,
    "end_minute": 1020,
}
```

Si start == end, el schedule se considera activo todo el día. Si start > end, la ventana cruza medianoche.

## 29. World Tick trace

Cada trace entry puede conservar:

```python
{
    "tick": 123,
    "timestamp": "...",
    "world_clock_result": {...},
    "producer_results": [...],
    "event_results": [...],
    "handoff_results": [...],
    "arbitration_results": [...],
    "need_results": [...],
    "activity_need_results": [...],
    "npc_results": [...],
}
```

La ventana actual se limita a los últimos ticks configurados por `TRACE_LIMIT`.

## 30. Public Knowledge query packet

La ruta Player self-query no expone IDs/provenance privados al texto público.

Packet conceptual:

```python
{
    "status": "KNOWN_FACTS_FOUND" | "NO_KNOWN_FACTS",
    "handled": True,
    "topic": "...",
    "retrieval_query": "...",
    "facts": [
        {
            "topic": "...",
            "text": "...",
        }
    ],
    "fact_count": 1,
    "response_text": "...",
}
```

No debe publicar `fact_id`, `knowledge_key`, `source` o `learned_by` como parte de esa interfaz de gameplay.

## 31. Packet vs authority

Muchos services devuelven packets ricos para inspección. Un packet no debe confundirse con estado persistente.

Ejemplo:

```text
Fact record persistido
= autoridad de Knowledge almacenado

retrieve_known_facts packet
= vista read-only autorizada en ese momento
```

Otro:

```text
relationship obligation persistida
= intención social pendiente

collect_relationship_candidates
= vista dinámica de qué obligations están actualmente ejecutables
```

## 32. Contrato de backwards compatibility

Cuando una feature nueva se agrega a un record viejo se prefiere:

- default que preserve comportamiento anterior;
- metadata aditiva;
- IDs históricos estables;
- no reescribir el engine viejo si puede componerse por wrapper/gate;
- fail closed sólo para authoring explícitamente inválido.

Ejemplos actuales:

```text
Fact sin fact_status            → ACTIVE
rule sin authority_relation     → ANY
rule sin holder_acquisition     → ANY
policy exacta v0.96             → conserva ID histórico
policy type sin severity filter → sigue siendo válida
```

## 33. Contrato de state restoration en QA

Un validator que toca datos persistentes debe snapshotear y restaurar sólo lo que modifica, incluyendo cuando aplique:

- location;
- Knowledge/Facts;
- relationships;
- rules/source index;
- memberships;
- goals/current goal;
- decision_enabled;
- world/faction registry;
- object/action/resolution history.

Un PASS que deja basura persistente no se considera un validator correcto.
