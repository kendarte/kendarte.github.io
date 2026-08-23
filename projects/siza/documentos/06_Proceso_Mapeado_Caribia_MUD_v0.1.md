# SIZA — Proceso de Mapeado Persistente de Caribia MUD v0.1

**Tipo:** documento de sistema / proceso de producción  
**Alcance:** construcción espacial completa de la provincia de Caribia para el modo aventura MUD de Siza  
**Estado:** v0.1 — procedimiento de trabajo, no canon diegético por sí mismo

## 1. Objetivo

Este documento fija **cómo se convierte el World Book de Caribia en un espacio físico persistente jugable**. Su función es impedir dos fallos:

1. que el Master IA improvise lugares, conexiones o interiores;
2. que el equipo escriba ciudades como prosa sin convertirlas en geometría navegable.

La regla central es:

> **El espacio de Siza es un grafo persistente. La IA narra ese grafo; no lo inventa.**

El proceso parte del atlas y del canon territorial, baja por capas hasta `ROOM`, y separa siempre cuatro clases de información:

- **CANON:** existe explícitamente en el World Book o `atlas.json`.
- **DERIVADO:** cálculo o clasificación obtenida directamente de datos canónicos sin introducir ficción nueva.
- **PROPUESTO:** geometría, conexión o detalle creado para completar el juego; requiere aprobación antes de convertirse en canon de sistema.
- **RUNTIME:** cambios producidos durante una partida; nunca reescriben el mapa base.

## 2. Jerarquía espacial

```text
RIVARICA
└── PROVINCIA
    └── REGIÓN
        └── ISLA / MASA / SECTOR
            └── ASENTAMIENTO
                └── DISTRITO / ZONE
                    └── ESTRUCTURA
                        └── INTERIOR / ZONE
                            └── ROOM
                                ├── EXIT
                                ├── OBJECT
                                └── NPC_PRESENT
```

Una entidad sólo puede estar físicamente en **una Room actual**. Los desplazamientos largos se resuelven como secuencias de enlaces entre Zones/Rooms, aunque la interfaz pueda resumirlos cuando no ocurre nada relevante.

## 3. Capa 0 — congelar la fuente

Antes de diseñar una región se extraen:

- escala territorial;
- población oficial;
- asentamientos nombrados;
- coordenadas de atlas;
- rutas troncales;
- tiempos de viaje;
- accidentes físicos;
- distritos canónicos;
- estructuras especiales;
- funciones regionales;
- reglas de servicios por tamaño de asentamiento.

Nada que contradiga esta capa puede entrar al mapa de juego sin corregir antes la fuente maestra.

## 4. Capa 1 — provincia

La provincia fija:

- límites conceptuales;
- medio físico;
- regiones;
- red troncal;
- nodos de frontera;
- grandes accidentes;
- población total;
- reglas transversales de viaje.

Caribia no es una superficie plana. El mapa debe soportar **altura**, océano físico, Nieblamar, rutas de navío, rutas aéreas y descensos de profundidad.

## 5. Capa 2 — región

Cada región recibe:

- `region_id`;
- población oficial;
- superficie;
- función territorial;
- quirks geográficos;
- recursos;
- riesgos;
- asentamientos canónicos;
- población no asignada a nodos;
- enlaces externos;
- reglas de generación compatibles con la región.

Los quirks no son decoración. Modifican qué estructuras son probables u obligatorias.

Ejemplos:

`AQUATIC_MINING` favorece Casa de Campanas, dársenas de inmersión, enfermería de profundidad y talleres.

`FRESHWATER_RICH` favorece reservorios, guardafuentes, riego, molinos y agricultura.

`HEAVY_FOG` exige reservas, refugios, señales, faros o protocolos de relevo.

## 6. Capa 3 — seed de asentamiento

Todo asentamiento empieza con un registro mínimo:

```text
SETTLEMENT_ID
name
region
population
scale
atlas_position
geographic_quirks
economic_roles
canonical_features
special_structures
faction_control
local_leader
districts
connections
```

`faction_control` y `local_leader` no se inventan si el World Book no los define. Se marcan `PENDIENTE_DE_DISEÑO`.

La población determina capacidades mínimas. La geografía y economía determinan especialización. Las facciones deforman esa base. Las estructuras especiales se imponen desde canon.

## 7. Capa 4 — composición de estructuras

El generador de edificios recibe:

```text
population
geographic_quirks
resources
routes
risks
faction_control
special_structures
```

y produce cinco grupos:

1. **infraestructura obligatoria** por escala;
2. **infraestructura económica** por recursos;
3. **infraestructura geográfica** por quirks;
4. **infraestructura faccional** por control/presencia;
5. **estructuras especiales canónicas**.

Una estructura no es un nombre narrativo: es una instancia de un `STRUCTURE_BLUEPRINT`.

## 8. Capa 5 — distritos / Zones urbanas

Una ciudad o villa grande se divide en Zones cuando una sola Room-map ya no conserva escala.

Cada distrito debe definir:

- función;
- clase/uso;
- horarios;
- entradas/salidas;
- estructuras;
- riesgo;
- conexiones a otros distritos.

Los distritos canónicos se conservan. Los distritos generados deben explicarse por población, función y geografía.

## 9. Capa 6 — estructuras e interiores

Cada tipo de estructura posee un blueprint de Rooms.

Ejemplo:

```text
PESCADERÍA
├── entrada / mostrador
├── área de corte
├── almacén
└── patio de carga
```

Una instancia concreta hereda ese blueprint y añade nombre, propietario, condición, inventario, empleados, puertas y modificaciones locales.

## 10. Capa 7 — Room

La Room es la unidad atómica de presencia.

Debe contener:

```text
ROOM_ID
name
zone_id
base_description
exits
anchored_objects
dynamic_objects
npc_present
environment
sensory_facts
runtime_state
```

La descripción base sólo informa lo evidente. Los datos ocultos permanecen en `sensory_facts`.

## 11. Capa 8 — percepción y descubrimiento

La Room existe completa aunque el jugador no la conozca.

Se separan:

- `MAP_DEFINITION`: geometría verdadera;
- `WORLD_STATE`: estado actual de esa geometría;
- `PLAYER_DISCOVERY`: parte conocida por el personaje.

Las acciones derivadas de vista, oído, olfato, tacto o gusto pueden activar `PER` cuando existe incertidumbre significativa. Una tirada exitosa revela hechos ya almacenados; nunca crea una pista nueva.

## 12. Capa 9 — movimiento

El movimiento siempre valida:

1. `current_room`;
2. Exit solicitado;
3. puerta/barrera;
4. permisos/condiciones;
5. coste/tiempo;
6. cambio de Room;
7. eventos de entrada/salida;
8. actualización de discovery.

Qwen recibe el resultado después de la validación.

## 13. Capa 10 — NPC en el mismo grafo

Los NPC no se teletransportan narrativamente.

Cada uno mantiene:

```text
current_room
destination_room
route
current_action
```

Su rutina, Job, necesidades y eventos deciden destino. El pathfinder usa el mismo grafo del jugador.

## 14. Generación de población sin crear un millón de JSON

El atlas contiene nodos nombrados, pero la población provincial es mayor. Esa diferencia se conserva como **población abstracta regional**.

Sólo se materializan como NPC persistentes:

- titulares de Jobs;
- personas relacionadas con el player;
- autoridades;
- familias necesarias;
- actores de eventos;
- NPC visitados o recordados.

El resto puede permanecer agregado hasta que el juego necesite individualizarlo.

## 15. Rutas: canon y propuesta

Las rutas troncales del World Book son inmutables salvo revisión del canon.

Para conectar asentamientos menores se puede crear una red provisional derivada de coordenadas. Esa red se marca `PROPUESTA` y **no recibe tiempo ni medio canónico hasta una pasada regional**.

La distancia gráfica del atlas sólo sirve para priorizar vecinos plausibles. No equivale a distancia navegable ni a tiempo de viaje.

## 16. Gate de validación de una región

Una región no se considera mapeada hasta cumplir:

- [ ] todos los asentamientos canónicos tienen `SETTLEMENT_ID`;
- [ ] todos pertenecen a una Zone regional;
- [ ] todos tienen al menos una conexión válida;
- [ ] no hay nodos aislados salvo que el canon lo exija;
- [ ] sus quirks proceden del canon o están marcados como propuesta;
- [ ] sus estructuras especiales están registradas;
- [ ] población regional = población nombrada + población abstracta;
- [ ] las ciudades mayores tienen distritos;
- [ ] los edificios importantes tienen blueprint de Rooms;
- [ ] no existe una salida narrada sin `EXIT`;
- [ ] el Master no puede crear una estructura para resolver una petición del jugador.

## 17. Orden de producción para Caribia

1. Mapa Maestro Provincial.
2. Kalnaj regional.
3. Vardena regional.
4. Sereva regional.
5. Orvena regional.
6. Ragmar regional.
7. Cadena de las Agujas.
8. Catálogo de estructuras comunes.
9. Estructuras faccionales.
10. Distritos de cada asentamiento mayor.
11. Blueprints interiores.
12. Conversión final a `map_definition.json`.

## 18. Regla de cierre

La prueba final no es que el mapa “se vea completo”.

La prueba es:

> El jugador puede pedir una dirección, caminar Room por Room, volver después, encontrar la misma geometría, descubrir detalles mediante sus sentidos y comprobar que tanto NPC como eventos respetan esa misma topología.

Cuando eso ocurre, el espacio deja de ser contexto narrativo y se convierte en mundo.