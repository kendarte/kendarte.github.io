# POKEROL

Fork técnico del `siza-world-engine` para construir un RPG de criaturas y aventuras estilo anime sobre la misma base de World Engine.

## Regla de separación

POKEROL reutiliza mecánicas e infraestructura, no el mundo de SIZA. No contiene Faro Ahogado, Darkhaven, Kalnaj, Mara, NPCs, mapas, campañas, beats, presets ni assets narrativos de SIZA.

Se conservan temporalmente identificadores internos `siza_*` / `siza-*` cuando forman parte del protocolo técnico heredado entre Evennia, servicios y webclient. Esos nombres no representan lore y se refactorizarán de forma gradual para no romper compatibilidad.

## Base incluida

- Evennia 6.1.0
- World Engine y persistencia
- acciones, percepción, consecuencias y tiradas
- NPC simulation, jobs, needs, knowledge, relationships, factions y events
- DM Director, registry y free-action pipeline
- combate / handoff al cliente
- webclient tipo libro
- Map Creator
- NPC Creator
- importer de contenido

## Mundo inicial

Vacío a propósito. POKEROL añadirá su propio mapa, criaturas, entrenadores, campaña, reglas y worldbook.

## Local

Ejecute primero `SETUP_POKEROL.bat` y después `INICIAR_POKEROL.bat`.
