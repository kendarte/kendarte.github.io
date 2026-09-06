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
- Pokémon Creator
- importer/materializer de biomas

## Pokémon Creator

`pokemon-creator/` edita especies, nivel, experiencia, evolución, moves por nivel, compatibilidad TM/HM y un catálogo compartido de moves.

Los moves separan su efecto de su forma física: `CONTACT`, `PROJECTILE`, `BEAM`, `PARABOLA`, `ARC`, `RAIN`, `GROUND_BURST`, `CRAWL`, `WAVE`, `FIELD`, `MOVEMENT`, etc. También declaran `world_effects`, materiales compatibles y requisitos ambientales.

Preset inicial:

- `pokemon-creator/load-kanto-pallet-viridian.html`

## Física anime del mundo

`anime_world_physics_engine.py` resuelve consecuencias físicas consistentes sin intentar ser un simulador realista completo. Entre las reglas iniciales:

- fuego calienta y puede encender materiales inflamables;
- agua moja, enfría y apaga fuego;
- electricidad se propaga por un cuerpo de agua compartido y genera impactos para todos sus ocupantes registrados;
- agua/hielo pueden congelarse y crear superficie;
- calor fuerte seguido de enfriamiento brusco puede agrietar o romper materiales sensibles por choque térmico;
- viento dispersa humo y puede aumentar riesgo de propagación de fuego;
- corte, impacto y rotura dependen del material y estado del objeto.

`pokemon_world_move_resolution_engine.py` une autorización del move con esas reglas físicas.

## Primer bioma Kanto

El corredor inicial usa Kanto como referencia geográfica, pero amplía mucho la escala respecto al mapa de Game Boy. La topología base es:

Pueblo Paleta → Ruta 1 → Ciudad Verde → Ruta 2 → Bosque Verde.

El preset genera más de veinte localizaciones de aventura entre interiores, praderas, arroyos, calles, estanques y sectores del bosque. Cada Room puede cargar `biome_profile`, `pokemon_populations`, `environmental_state` y cuerpos de agua. Los props pueden cargar materiales y propiedades físicas.

Abrir directamente en Map Creator:

- `map-creator/load-kanto-pallet-viridian.html`

El materializador `world/pokemon_biome_materializer.py` puede CREAR Rooms, Exits y props nuevos desde un JSON exportado por el Map Creator sin borrar objetos existentes.

En Windows puede aplicarse con `APLICAR_BIOMA_POKEROL.bat` pasando el JSON exportado.

## Local

Ejecute primero `SETUP_POKEROL.bat` y después `INICIAR_POKEROL.bat`.
