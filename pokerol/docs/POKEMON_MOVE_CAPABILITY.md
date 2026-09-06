# POKEROL — Pokémon Move Capability Model

## Goal

A move is not only a battle attack. It is an authored physical capability the World Engine may apply to creatures, objects, terrain and environmental state.

TM and HM are teaching sources. They do not own world logic. The move owns world logic.

## Pokémon profile

A Pokémon record contains:

- species identity, types, form and descriptive profile
- level and experience
- evolution rules
- Pokémon battle stats
- World Engine stats
- locomotion, senses, body tags and environment tags
- `level_up_moves`
- `tm_compatibility`
- `hm_compatibility`
- `known_moves`
- optional active battle move limit

The authoritative known-move library is separate from the combat loadout. This lets POKEROL decide later whether the anime campaign enforces a four-move limit without losing learned capability history.

## Move profile

Battle fields:
- `move_id`
- type
- category
- damage class
- power
- accuracy
- PP
- priority

Physical execution:
- `delivery`
- `defense_profile`
- range
- target mode
- requirements

World interaction:
- `world_enabled`
- `world_effects`
- `materials`
- `world_rules`
- tags

Teaching:
- `machine.kind = NONE | TM | HM | TUTOR`
- machine id
- reusable flag

## Delivery / trajectory

The initial generic vocabulary is:

- CONTACT
- PROJECTILE
- BEAM
- PARABOLA
- ARC
- RAIN
- FALL
- GROUND_BURST
- CRAWL
- WAVE
- CONE
- MINE
- FIELD
- SELF
- TARGETED
- MOVEMENT

These are geometry semantics, not animation labels.

Examples:

- A rock projectile can collide with an obstacle before the intended target.
- A PARABOLA can pass over low cover.
- RAIN comes from above and is blocked by overhead shelter.
- GROUND_BURST requires a valid ground path.
- CRAWL travels through or along the ground.
- BEAM requires a clear line.
- CONTACT requires reach.
- FIELD changes an area instead of only one target.

## Defense profile

- NONE
- BARRIER
- SHELTER
- REDIRECT
- REFLECT
- ABSORB
- BRUSH

A defensive move can therefore be reasoned about spatially by the same engine.

## World effects

World effects are verbs the World Engine can authorize. Initial examples include:

- CUT / CUT_VEGETATION
- BREAK / PIERCE / BLUNT
- PUSH / PULL / LIFT / KNOCKDOWN
- BURN / IGNITE / HEAT
- COOL / FREEZE / MELT
- WATER / SOAK
- ELECTRIFY / POWER_DEVICE / SHORT_CIRCUIT
- DIG / TUNNEL / ERODE
- CREATE_COVER / DESTROY_COVER
- CREATE_WIND / CLEAR_SMOKE / MOVE_AIR / MOVE_WATER
- SURF / SWIM / FLY / GLIDE / CLIMB / CROSS_GAP / CARRY
- LIGHT / DARKEN
- GROW_PLANTS
- sensory effects such as TRACK, SCENT, SONAR and SENSE_HEAT
- TELEKINESIS / TELEPORT
- HEAL / CLEANSE / SLEEP / WAKE / RESTRAIN / RELEASE

## Materials and targets

Moves declare the kinds of targets their effects may logically operate on, e.g.:

CREATURE, VEGETATION, WOOD, STONE, SOIL, SAND, METAL, GLASS, ICE, WATER,
FIRE, ELECTRICAL_DEVICE, ROPE, FABRIC, FRAGILE_STRUCTURE, HEAVY_OBJECT,
SMOKE and GAS.

This is only a generic material vocabulary. Rooms and objects may add more specific tags.

## Why TM/HM work outside combat

Cut:
- delivery: CONTACT
- world effects: CUT, CUT_VEGETATION
- materials: VEGETATION, ROPE, FABRIC

Water Gun:
- delivery: PROJECTILE
- world effects: WATER, SOAK, COOL
- materials: CREATURE, FIRE, FRAGILE_STRUCTURE

Rock Throw:
- delivery: PARABOLA
- world effects: BLUNT, BREAK
- materials: CREATURE, GLASS, FRAGILE_STRUCTURE

Dig:
- delivery: CRAWL / MOVEMENT depending on authored use
- world effects: DIG, TUNNEL
- materials: SOIL, SAND

Thunderbolt:
- delivery: BEAM or TARGETED depending on campaign interpretation
- world effects: ELECTRIFY, POWER_DEVICE, SHORT_CIRCUIT
- materials: CREATURE, ELECTRICAL_DEVICE, METAL

The DM does not invent those effects. It proposes an intent. The World Engine checks the Pokémon's known move, geometry, requirements, target tags, room state and authored effects, then returns authorized consequences.

## Runtime request

A future use packet should look conceptually like:

```json
{
  "action": "USE_MOVE",
  "actor_pokemon_id": "PKMN-025-INSTANCE-01",
  "move_id": "MOVE-THUNDERBOLT",
  "target": {"object_id": "GENERATOR-01"},
  "intent": "intento encender el generador",
  "room_id": "ROOM-POWER-STATION"
}
```

Resolution order:

1. Pokémon actually knows the move.
2. Move is world-enabled.
3. Actor satisfies physical/environment requirements.
4. Geometry can reach the target.
5. Target material/tags accept at least one authored effect.
6. World rules and target rules select allowed state changes.
7. Consequence engine mutates authoritative state.
8. Narrator describes only the authorized result.

This keeps anime-style creativity without turning the AI into the authority over physics or world state.
