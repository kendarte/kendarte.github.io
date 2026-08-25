# 06 — Combat Bridge: World Engine ↔ TCG

**Estado:** contrato de integración futuro; no implementado todavía como bridge completo.  
**Dependencia:** se implementa cuando el TCG de SIZA esté suficientemente cerrado para fijar su interfaz real.

## 1. Por qué va separado

Desde el concepto inicial de SIZA, las confrontaciones importantes deben poder abrir el combate TCG.

Eso no significa que el TCG deba vivir dentro del World Engine.

La separación correcta es:

```text
WORLD ENGINE
→ detecta/autoriza una confrontación de combate
→ crea un Combat Encounter estructurado
→ entrega el encounter al TCG

TCG
→ resuelve cartas/reglas/recursos
→ devuelve un Combat Result estructurado

WORLD ENGINE
→ valida el result
→ aplica consecuencias persistentes
→ produce Facts/world state/NPC reactions
```

## 2. CONFRONT actual vs combate TCG

El mode `CONFRONT` que ya existe en el World Engine no se elimina.

Sirve para oposición rápida:

```text
interrogatorio
forcejeo breve
intimidación
competencia directa
oposición social/física que no amerita combate completo
```

Fórmula actual:

```text
d6 + actor_stat
vs
d6 + target_stat
```

El Combat Bridge debe representar otra clase de resolución.

Nombre conceptual recomendado:

```text
COMBAT_CONFRONTATION
```

No es necesario fijar ese nombre en código hasta implementar el bridge.

## 3. Cuándo debería abrirse el TCG

La decisión debe ser authored/determinista, no inferida libremente por el narrador.

Ejemplos:

```text
"le quito el manifiesto de las manos"
→ puede resolverse como CONFRONT

"ataco al guardia con intención de combatir"
→ COMBAT_CONFRONTATION
→ abre TCG
```

El mundo puede usar metadata de Action/encounter para decidir si una confrontación exige TCG.

## 4. Responsabilidad del World Engine antes del combate

Antes de abrir el TCG, el World Engine debe autorizar:

- que actor/target existen;
- que están en posición/contexto compatible;
- que la Action es posible;
- quién participa;
- qué estado previo tiene cada participante;
- qué location/contexto aplica;
- qué stakes authored existen;
- qué loadout/deck reference corresponde;
- qué modificadores de mundo deben exponerse.

No debe enviar datos “inventados por el LLM”.

## 5. Combat Encounter — contrato recomendado

Forma conceptual:

```python
{
    "encounter_id": "COMBAT-...",
    "encounter_type": "COMBAT_CONFRONTATION",

    "site": {
        "room_id": "CAR-...",
        "dbref": 9,
        "name": "...",
    },

    "initiator": {
        "entity_id": "PLAYER/CHARACTER ID",
        "name": "...",
        "deck_id": "...",
        "loadout": {...},
        "world_status": {...},
    },

    "opponents": [
        {
            "npc_id": "NPC-...",
            "name": "...",
            "deck_id": "...",
            "loadout": {...},
            "world_status": {...},
        }
    ],

    "allies": [],

    "stakes": {
        "on_player_win": [...],
        "on_player_loss": [...],
        "allow_flee": True,
        "allow_surrender": True,
    },

    "world_modifiers": [...],
    "source_action_id": "ACT-...",
    "created_at": "...",
}
```

El schema exacto debe cerrarse junto con el TCG, no antes.

## 6. Qué datos NO deberían enviarse al TCG

El TCG no necesita autoridad sobre:

- todo el World Book;
- todos los Facts de un NPC;
- faction policies completas;
- todos los goals;
- todos los Rooms;
- relationship graph completo.

Sólo se envía lo necesario para resolver el encuentro.

## 7. Responsabilidad del TCG

El TCG es autoridad sobre:

- reglas de cartas;
- turnos/acciones de combate;
- mana/recursos propios del TCG;
- cartas usadas/consumidas según su diseño;
- daño/estado interno de combate;
- victoria/derrota;
- flee/surrender/capture si son reglas del TCG;
- outcomes especiales propios del combate.

El World Engine no debe duplicar esas reglas.

## 8. Combat Result — contrato recomendado

Forma conceptual:

```python
{
    "encounter_id": "COMBAT-...",
    "status": "RESOLVED",

    "outcome": "PLAYER_WIN",
    "winner_ids": ["PLAYER-ID"],
    "defeated_ids": ["NPC-X"],

    "participants": [
        {
            "entity_id": "PLAYER-ID",
            "result_state": "ACTIVE",
            "damage": 3,
            "resources_spent": {...},
        },
        {
            "entity_id": "NPC-X",
            "result_state": "DEFEATED",
            "damage": 8,
        }
    ],

    "tags": ["CAPTURE_POSSIBLE"],
    "fled_ids": [],
    "surrendered_ids": [],
    "killed_ids": [],

    "tcg_build": "...",
    "resolved_at": "...",
}
```

El World Engine debe validar que `encounter_id` corresponde a un encounter pendiente y que los entity IDs estaban autorizados.

## 9. Qué hace el World Engine después

El resultado del TCG no debe quedarse como texto aislado.

Debe convertirse a world consequences.

Ejemplo:

```text
TCG devuelve PLAYER_WIN + NPC defeated
→ World Engine marca NPC defeated/herido/capturable según mapping authored
→ Action/combat encounter se cierra
→ world state cambia
→ consequence engine emite evento
→ SITE_NPCS pueden aprender Fact
→ factions pueden recibir/reportar Fact
→ goals pueden aparecer
→ NPC autonomy reacciona
```

## 10. Mapeo de outcome a consecuencias

No conviene hard-codear toda consecuencia en el TCG.

Ejemplo:

```text
TCG: NPC_X = DEFEATED
```

El significado diegético puede depender del encounter:

```text
encounter A
→ derrotado = huye

encounter B
→ derrotado = arrestable

encounter C
→ derrotado = inconsciente
```

Por eso el World Engine debe conservar stakes/mapping authored.

## 11. Facts derivados del combate

Un combate puede producir Facts estructurados:

```text
FACT: Player atacó a un guardia
FACT: Guard perdió la confrontación
FACT: Hubo disparos en la dársena
FACT: NPC X fue capturado
```

Recipients pueden ser:

- participantes;
- SITE_NPCS/testigos;
- instituciones después por SHARE_FACT;
- Player si corresponde.

La generación debe usar consequence authority, no una descripción inventada por el narrador.

## 12. Integración con instituciones

El loop social construido hasta v1.01 hace que el Combat Bridge tenga consecuencias sistémicas sin programar cada reacción a mano.

Ejemplo:

```text
Player pelea con guardia
→ Combat Result
→ Fact SECURITY_INCIDENT severity 5
→ guardia/testigo adquiere Fact
→ faction policy detecta severity 5
→ reporta hacia arriba
→ chain 100→500→800
→ autoridad recibe Fact
→ nuevo Fact-goal/order puede surgir
```

Esto es uno de los principales motivos para mantener Combat y World separados pero conectados por Facts/consequences.

## 13. Pause/resume del mundo

La implementación del bridge debe decidir explícitamente cómo se comporta el World Tick durante un combate del Player.

Opciones posibles:

- pausar todo World Tick;
- pausar sólo participantes;
- permitir mundo global mientras encounter queda locked.

No está decidido en el core actual y debe resolverse al integrar TCG según ritmo de juego final.

No se debe escoger una opción ahora sólo por completitud teórica.

## 14. Persistencia del encounter

Recomendación fuerte: el encounter pendiente debe ser persistente.

Razones:

- crash/reconnect;
- frontend móvil;
- no duplicar reward/outcome;
- reconciliar resultado TCG;
- audit/debug.

Estados conceptuales:

```text
PENDING
IN_PROGRESS
RESOLVED
CANCELLED
```

## 15. Idempotencia

Un mismo Combat Result no debe aplicar consecuencias dos veces.

Contrato futuro:

```text
encounter_id + result_id/outcome state
→ apply once
→ subsequent identical callback = ALREADY_RESOLVED
```

Esto debe seguir el patrón de Action resolution y Fact/obligation identity ya usado en el World Engine.

## 16. Fallos de integración

Casos que deben fallar cerrados:

- encounter desconocido;
- result de otro encounter;
- participant no autorizado;
- outcome desconocido;
- result duplicado con payload conflictivo;
- TCG build incompatible si el contrato versionado lo exige;
- world entity eliminada/cambiada de forma incompatible mientras encounter estaba activo.

## 17. Narración del combate

El LLM puede redactar un resumen del resultado **después** de que TCG y World Engine resuelvan.

No puede decidir quién ganó.

```text
Combat Result estructurado
→ World consequences
→ grounded narration packet
→ Qwen redacta
```

## 18. Cuándo implementar

No ahora por defecto.

Orden recomendado:

```text
1. freeze World Engine
2. terminar/cerrar suficiente del TCG
3. definir schema real de Encounter y Result
4. implementar bridge mínimo
5. validator con TCG stub determinista
6. integración real
7. manual gameplay acceptance
```

## 19. Qué NO forma parte del roadmap v1.02–v1.13

El Combat Bridge no debe confundirse con “seguir expandiendo el simulation framework”.

Es una integración necesaria del **juego SIZA** entre dos subsistemas ya planeados desde el comienzo.

Puede implementarse aunque el World Engine permanezca frozen.
