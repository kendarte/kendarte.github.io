SETTLEMENT_TEST_001
Population: 3,240
Type: Pueblo
Quirks: [COASTAL, FISHING_GROUNDS, HEAVY_FOG, AEROSHIP_ROUTE]
Resources:
  fishing = HIGH
  azurite = LOW
  fresh_water = MEDIUM
Faction control:
  WINDRAGO = 35
  ADVENIDOS = 45
  ECLESIA = 8
  LADRONES = 12
Special structures: []
```

La población obliga a generar gobierno, mercado, salud, seguridad, escuela, agua y ruta. COASTAL + FISHING_GROUNDS aumenta muelles, pescaderías, conservación y talleres de redes. HEAVY_FOG incrementa señal/refugio y eventos de cierre. AEROSHIP_ROUTE añade aeromuelle, correo y carga. El control advenido favorece sus nodos si cumplen requisitos; Windrago puede sostener seguridad proporcional; Ladrones utiliza huecos de almacenes, rutas y comercio. Finalmente, cada edificio crea sus Rooms y Jobs.

## 18.1 Resultado de primera capa

```text
COMMON / CIVIL
  viviendas: según densidad y household model
  mercado: 1
  cisternas: 2
  escuela: 1
  clínica/consultorio: 1..N según capacidad
  muelles: varios
  pescaderías: varias
  cámara fría: si capacidad/riqueza lo justifican
  talleres de redes: varios
  almacenes: varios
  aeromuelle/posta: 1

FACTIONS
  ADVENIDOS: nodos según árbol y requisitos
  WINDRAGO: defensa según árbol y control
  ECLESIA: presencia minoritaria si requisitos se cumplen
  LADRONES: red oculta dependiente de oportunidad

Luego: ROOM GRAPH -> JOBS -> NPC -> EVENTS
```

# 19. Esquemas de datos recomendados

## 19.1 Settlement

```text
SETTLEMENT {
  id, name, region_id, island_id, type, population,
  atlas_position,
  geography_quirks[],
  resources{},
  routes[],
  dangers{},
  faction_control{},
  formal_leader_id, effective_power_id,
  special_structure_ids[],
  district_ids[],
  building_instance_ids[],
  current_profile{},
  generation_seed,
  world_state_ref
}
```

## 19.2 Room

```text
ROOM {
  id, zone_id, settlement_id, structure_id?,
  name, base_description,
  exits[], objects[], npc_presence[],
  permissions, sensory_layers{},
  local_state{}, event_hooks[],
  tags[]
}
```

## 19.3 Sensory layers

```text
sensory_layers: {
  sight:   [SENSORY_FACT...],
  hearing: [SENSORY_FACT...],
  smell:   [SENSORY_FACT...],
  touch:   [SENSORY_FACT...],
  taste:   [SENSORY_FACT...]
}
```

## 19.4 Player discovery

```text
PLAYER_DISCOVERY {
  player_id,
  known_rooms[],
  known_exits[],
  known_facts[],
  known_npc_names[],
  mapped_structures[],
  last_seen_state{}
}
```

# 20. Integración con el Master IA

El Master IA opera encima del motor espacial. El contexto que recibe debe ser pequeño, verificable y específico de la Room actual. El RAG del World Book añade canon relevante, pero no sustituye MAP DEFINITION.

```text
MASTER_CONTEXT
  current_room
  valid_exits
  visible_objects
  npc_present
  current_local_state
  player_known_facts
  action_resolution_result
  relevant_worldbook_fragments
  npc_knowledge_scope (si habla un NPC)
```

## 20.1 Prohibiciones del Master

- No mover al personaje a una Room inexistente.
- No añadir un edificio para resolver una petición del jugador.
- No crear un NPC persistente sin que el sistema lo autorice.
- No revelar sensory_facts no descubiertos.
- No permitir que un NPC conozca información fuera de su knowledge/gossip.
- No ignorar puertas, permisos, horarios, daños o inventarios guardados.
- No cambiar el resultado de una resolución mecánica para mejorar la prosa.

# 21. Relación con el prototipo actual

La interfaz actual de Siza ya presenta ubicación, destinos cercanos, NPC presentes, atributos, resolución y World Book recuperado. La falla espacial observada —acciones como ir a una recámara o a un bar sin que la ubicación real cambie de forma consistente— se corrige cuando CURRENT_ROOM deja de ser un contexto narrativo y pasa a ser un identificador obligatorio del estado de partida.

La UI puede continuar mostrando una imagen y una descripción, pero ambas deben derivarse de CURRENT_ROOM/ZONE. Los botones de destinos cercanos deben ser Exits o rutas verificadas. Si el jugador escribe libremente un destino, el parser debe resolverlo contra el grafo antes de permitir que Qwen narre el movimiento.

# 22. Orden de implementación recomendado

1. Congelar el schema de Settlement, Structure Template, Structure Instance, Room, Exit y Sensory Fact.
2. Terminar el catálogo de estructuras COMUNES y sus Room Blueprints.
3. Terminar árboles tecnológicos y estructuras propias de WINDRAGO, ADVENIDOS, ECLESIA y LADRONES.
4. Definir Job Slots de todas las estructuras y completar el catálogo de Jobs.
5. Implementar generador reproducible de asentamientos a partir de seed.
6. Implementar grafo Room-to-Room y movimiento sin IA.
7. Implementar player discovery y mapa revelado.
8. Implementar percepción por sentidos y sensory facts.
9. Implementar NPC/rutinas basadas en Jobs y Rooms.
10. Implementar eventos y economía de estructuras.
11. Conectar Qwen como intérprete/narrador después de que el motor pueda resolver acciones básicas sin él.
12. Probar un asentamiento completo antes de expandir el atlas entero.

# 23. Criterios de aceptación del sistema espacial

El sistema puede considerarse funcional cuando supera pruebas donde la narración no puede “hacer trampa”.

- Volver a una Room horas después mantiene la misma geometría y refleja sólo los cambios reales de estado.
- Una puerta secreta existe antes de ser descubierta y aparece en el mapa del jugador sólo después de revelarse.
- “Ir al bar” encuentra una ruta real; si no existe bar conocido o accesible, el sistema no inventa uno.
- Un NPC que está trabajando no aparece simultáneamente en su casa.
- Cerrar o destruir una estructura elimina o degrada sus servicios y deja Jobs afectados.
- Matar o desplazar a un trabajador deja una vacante que puede producir consecuencias persistentes.
- Un evento de escasez puede rastrearse hasta un recurso, ruta o estructura concreta.
- Una tirada de Percepción sólo revela hechos almacenados en la Room/objeto/NPC objetivo.
- Un NPC no revela información que no conoce aunque el World Book la contenga.
- Guardar/cargar conserva CURRENT_ROOM, puertas, objetos, NPC, control faccional, eventos y discovery.

# 24. Glosario operativo

| Término | Definición |
| --- | --- |
| Settlement | Asentamiento persistente generado desde condiciones demográficas, geográficas, económicas y faccionales. |
| Structure Template | Definición reusable de un tipo de edificio. |
| Structure Instance | Edificio concreto colocado en un asentamiento. |
| Zone | Grupo espacial de Rooms con contexto compartido. |
| Room | Unidad atómica de navegación e interacción del MUD. |
| Exit | Conexión válida entre Rooms. |
| Sensory Fact | Hecho objetivo asociado a un sentido y una dificultad/requisito de percepción. |
| Job Slot | Puesto generado por una estructura y disponible para ser ocupado. |
| World State | Estado dinámico de objetos, estructuras, NPC, economía y eventos. |
| Player Discovery | Subconjunto del mundo que el jugador ha descubierto. |
| Faction Control | Influencia o dominio local que modifica instituciones, seguridad y comportamiento sistémico. |
| Master IA | Capa que interpreta lenguaje libre y narra hechos autorizados por el motor. |

# 25. Frontera con los documentos de facciones

Este documento define el contenedor y la interfaz que utilizarán los árboles tecnológicos. No intenta cerrar aquí cada árbol. WINDRAGO, ADVENIDOS, ECLESIA y LADRONES deben tener documentos separados con: Town Hall o centro equivalente, constructor/Job de expansión, tiers, requisitos, estructuras propias, Jobs producidos, mejoras, eventos, costes, condiciones de captura y relación con infraestructura COMÚN.

La salida de esos documentos alimentará directamente BUILDING REQUIREMENTS. Una vez congelados, el generador podrá saber no sólo que un pueblo tiene 35% de presencia Windrago, sino qué combinación específica de Puestos, Baluartes, Fortalezas, logística y Jobs es físicamente plausible allí.

# 26. Conclusión de diseño

> **Siza debe dejar de generar escenas y empezar a persistir lugares.**

La ciudad se vuelve estable cuando cada edificio tiene causa, cada edificio ocupa un lugar, cada interior está compuesto por Rooms, cada Room conoce sus Exits y contenido, cada Job nace de una estructura y cada evento puede rastrearse hasta un cambio en el estado. En ese punto Qwen deja de sostener el mundo con prosa y pasa a hacer el trabajo correcto: interpretar al jugador y convertir un sistema coherente en una experiencia narrativa.

# Apéndice A. Correspondencia con el World Book

Elementos tomados o formalizados desde el canon existente: jerarquía provincia/región/isla/asentamiento/estructura/interior/objeto; rangos de población; perfiles de capacidad; estructura activa con propietario, nivel, condición, cuota, inventario, Jobs, horario, seguridad, relaciones y eventos; Pescadería I como ejemplo; ramas civiles de estructuras; interiores por permisos; regla de que las acciones cotidianas no requieren tirada; repertorio de eventos; generación desde región, isla, población, recurso dominante, peligro y ruta; generación de puestos por edificio; persistencia de consecuencias. Las capas ROOM, EXITS, PLAYER_DISCOVERY, sensory facts por cinco sentidos y el pipeline detallado son la especificación mecánica añadida en este documento para convertir ese canon en un MUD persistente.

# Apéndice B. Plantilla mínima para diseñar una nueva estructura

```text
NOMBRE / ID
ALINEACIÓN
GRADO
FUNCIÓN SOCIAL
REQUIERE
DESBLOQUEA
RECURSOS DE ENTRADA
RECURSOS DE SALIDA
JOB SLOTS
HORARIO BASE
SEGURIDAD
ROOM BLUEPRINT
  Rooms
  Exits internos
  Exits al asentamiento
OBJETOS FIJOS
CAPAS SENSORIALES TÍPICAS
EVENT REPERTOIRE
UPGRADES
CONDICIONES DE DEGRADACIÓN
CONDICIONES DE CAPTURA / CAMBIO DE CONTROL
```

# Apéndice C. Plantilla mínima para diseñar un asentamiento

```text
IDENTIDAD
  id / nombre / región / tipo / atlas
POBLACIÓN
GEOGRAFÍA / QUIRKS
RECURSOS
RUTAS
PELIGROS
CONTROL DE FACCIONES
  Windrago / Advenidos / Eclesia / Ladrones
AUTORIDAD FORMAL / PODER EFECTIVO
ESTRUCTURAS ESPECIALES
SEED

SALIDA GENERADA
  distritos
  estructuras comunes
  estructuras faccionales
  estructuras clandestinas
  rooms / exits
  jobs
  npc / households
  economía
  eventos activos
  world state inicial
```