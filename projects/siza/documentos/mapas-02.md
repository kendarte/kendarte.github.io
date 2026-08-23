Todo objeto persistente debe estar anclado a una Room, contenedor, personaje o estructura. “Una caja en el puerto” no es suficiente; el motor necesita saber exactamente dónde está. Mover un objeto significa cambiar su parent/location.

```text
OBJECT-BOX-004
location_type: room
location_id: WAREHOUSE-02-ROOM-STORAGE
movable: true

Tras moverla:
location_type: room
location_id: WAREHOUSE-02-ROOM-OFFICE
```

Los objetos grandes pueden alterar navegación. Una carreta volcada puede añadir un bloqueo parcial a un Exit; una barricada puede reducir capacidad; una caja pequeña normalmente no cambia el grafo.

# 15. DESCRIPCIÓN ESPACIAL DE UNA ROOM

La descripción base existe para orientar, no para sustituir el mapa. Al entrar, el Master recibe una ficha espacial que contiene nombre, forma general, iluminación, ocupación obvia, salidas visibles, estructuras/objetos evidentes y ambiente. Los secretos y detalles no obvios permanecen en sensory_layers y requieren acciones de percepción cuando corresponda.

| Capa | Se narra automáticamente | Ejemplo |
| --- | --- | --- |
| Orientación | Sí | “Un pasillo corto conecta la entrada con el salón.” |
| Exits visibles | Sí | “Una escalera sube al piso superior.” |
| Objetos dominantes | Sí | “Una mesa de corte ocupa el centro.” |
| NPC evidentes | Sí | “Dos cargadores trabajan junto a la puerta.” |
| Condición ambiental | Sí | “La niebla entra por las tablas abiertas.” |
| Pista no obvia | No | Sello manipulado, huella tenue, olor específico. |
| Exit oculto | No | Panel secreto, túnel, puerta camuflada. |

# 16. PERCEPCIÓN Y ESPACIO

La Percepción no crea geometría; revela propiedades existentes de esa geometría. Un Exit secreto puede estar en Map Definition con visibility=hidden. Una tirada de Vista o Tacto exitosa cambia Player Discovery. Un sonido puede revelar que existe actividad detrás de una puerta sin revelar todavía el Room exacto del otro lado.

```text
SENSORY_FACT
sense: HEARING
target: DOOR-03
difficulty: 6
reveal: “hay al menos dos voces detrás”
world_fact: occupants_in_adjacent_room >= 2
persistent_discovery: false
```

La información sensorial puede depender del estado. Si los NPC se marchan, el hecho audible deja de estar disponible. En cambio, descubrir físicamente una puerta secreta suele ser persistente.

# 17. VISIBILIDAD, ALCANCE Y ADYACENCIA

La Room simplifica el espacio, pero algunas interacciones necesitan relaciones más finas. Cada Room puede declarar tags de visibilidad y los Exits pueden transmitir o bloquear vista, sonido, olor o peligro. No necesitamos un motor 3D completo; necesitamos reglas discretas consistentes.

| Canal | Ejemplos de transmisión |
| --- | --- |
| Vista | Exit abierto, ventana, balcón, línea elevada; bloqueado por muro/puerta opaca. |
| Oído | Puede atravesar una puerta con penalización; muros gruesos reducen alcance. |
| Olfato | Puede viajar por Exits abiertos, ventilación o corriente. |
| Tacto | Normalmente requiere mismo Room y contacto con target. |
| Gusto | Requiere objeto consumible/accesible en inventario o Room. |
| Peligro | Fuego, niebla, humo o inundación pueden propagarse por reglas de Exit y ambiente. |

# 18. EVENTOS QUE MODIFICAN EL MAPA

Un evento espacial no debería reemplazar el mapa por una escena especial. Debe modificar World State o, en casos mayores, Map Definition. Esto permite que las consecuencias sobrevivan al evento.

| Evento | Cambio correcto |
| --- | --- |
| Incendio | Room state: burning; propagación por Exits; objetos dañados; posibles bloqueos. |
| Derrumbe | Exit state: blocked o destroyed; puede crear rubble object y ruta alternativa. |
| Construcción | Nueva Structure Instance y nuevos Rooms/Exits autorizados. |
| Demolición | Desactiva o archiva Rooms/Exits; conserva historial si hace falta. |
| Captura de facción | Cambia controller/permissions/security; geometría sólo cambia si realizan obras. |
| Tormenta/Niebla | Modifica hazards, visibilidad y travel_cost; no crea calles nuevas. |
| Barricada | Objeto espacial ligado a Exit; cambia capacidad/acceso. |
| Puente roto | Exit inutilizable; regiones siguen existiendo pero pathfinding debe rodear o detenerse. |

# 19. RUTAS ENTRE ASENTAMIENTOS

La misma lógica se extiende a escala regional. Una ruta de aerobarco, canal, puente entre islas o descenso minero es una conexión entre nodos territoriales que puede expandirse en Rooms sólo cuando sea jugable. El sistema puede trabajar con dos escalas: macro-edge para viajes lejanos y micro-Room graph cuando el jugador está dentro del trayecto.

```text
SETTLEMENT-A PORT --[REGIONAL ROUTE: 45 min]--> SETTLEMENT-B PORT

Si el viaje no tiene interacción: se procesa como edge macro.
Si ocurre un evento o el vehículo es explorable: se materializa VEHICLE/ROUTE ZONE con Rooms.
```

# 20. GENERACIÓN DE MAPAS DE ASENTAMIENTO

El generador recibe el perfil estructural del asentamiento y produce primero necesidades y estructuras; después les asigna posición/topología. No genera Rooms al azar sin función. La geografía y los quirks condicionan cómo se conectan los distritos y dónde pueden colocarse edificios.

```text
SETTLEMENT PROFILE
  population
  geography / quirks
  resources
  routes
  dangers
  faction control
  special structures
        ↓
DISTRICT LAYOUT
        ↓
STRUCTURE INSTANCES
        ↓
EXTERIOR ROOM GRAPH
        ↓
INTERIOR ROOM BLUEPRINTS
        ↓
EXITS / DOORS / LEVELS
        ↓
VALIDATION
        ↓
PERSISTENT MAP
```

## 20.1 Orden recomendado de generación

1. Fijar estructuras únicas canónicas y puntos de entrada/salida regional.
2. Determinar distritos o Zones funcionales según población, geografía y economía.
3. Colocar infraestructura crítica: agua, gobierno, seguridad, mercado, rutas, salud.
4. Colocar estructuras económicas según recursos y cadenas de suministro.
5. Colocar estructuras faccionales según dominio y Tech Tree.
6. Rellenar infraestructura común y vivienda hasta cubrir población/demanda.
7. Construir el grafo de Rooms exteriores y comprobar conectividad.
8. Instanciar Room Blueprints interiores para estructuras relevantes.
9. Asignar puertas, permisos, estados iniciales, objetos y Exits especiales.
10. Validar que toda estructura funcional sea alcanzable y que las rutas críticas no dependan de un único Exit salvo que sea intencional.

# 21. VALIDACIÓN DEL MAPA

Antes de aceptar un asentamiento generado, el motor debe ejecutar validaciones estructurales. El mapa no puede depender de Qwen para corregir errores topológicos durante la partida.

| Prueba | Condición de éxito |
| --- | --- |
| Reachability | Todo Room público requerido es alcanzable desde al menos una entrada válida. |
| Return path | Los interiores normales permiten salir; los one-way exits están marcados deliberadamente. |
| Critical services | Agua, gobierno, salud, mercado y rutas obligatorias tienen acceso físico. |
| Door consistency | Toda door enlaza Exits válidos y sus lados coinciden. |
| Vertical consistency | Pisos y niveles conectan por medios explícitos. |
| No orphan rooms | No existen Rooms aisladas salvo secretos intencionales. |
| Capacity sanity | Pasos críticos aceptan los tipos de entidad/carga que deben utilizarlos. |
| Faction access | Estructuras faccionales tienen permisos y rutas coherentes con su función. |
| Blueprint completeness | Cada Structure Instance cumple los slots obligatorios de su blueprint. |
| Discovery safety | Exits ocultos no son la única salida necesaria para un jugador sin conocimiento previo, salvo diseño deliberado. |

# 22. CONTRATO ENTRE EL MOTOR ESPACIAL Y QWEN

Qwen no recibe el mapa completo. Recibe una Spatial Context Window construida por el motor. Esta ventana contiene sólo la información que puede describir o utilizar para la acción actual.

```text
SPATIAL_CONTEXT
current_room:
  id: CAR-VAR-PORT-017
  name: Pasarela Oriental
  base_description: ...
  environment: ...

visible_exits:
  - north -> PORT-018
  - enter -> FISH-03-ENTRANCE
  - west -> PLAZA-04

visible_objects:
  - CRATE-04
  - NOTICEBOARD-01

present_npcs:
  - NPC-481
  - NPC-552

known_destinations:
  - La Plaza
  - La Escama Celeste

forbidden_for_narration:
  - undiscovered exits
  - contents of closed containers
  - NPC in non-visible rooms
  - rooms not reachable/known unless referenced as distant landmarks
```

> **El Master redacta; el motor autoriza. Si Qwen dice que Nereida cruzó una puerta que no existe, su respuesta debe rechazarse o repararse antes de mutar el estado.**

## 22.1 Resultado de una acción espacial

El parser debe producir una intención estructurada. El motor la valida y devuelve un resultado. Qwen narra ese resultado, pero no modifica current_room por su cuenta.

```text
PLAYER: “entro a la pescadería”

PARSER
  intent: MOVE
  target: STRUCTURE FISH-03

SPATIAL ENGINE
  current_room: PORT-017
  matching_exit: EXIT-88
  destination: FISH-03-ENTRANCE
  status: VALID

STATE MUTATION
  player.current_room = FISH-03-ENTRANCE

QWEN
  narra la transición y la descripción base de la nueva Room.
```

# 23. QUÉ PASA CON COMANDOS AMBIGUOS

El lenguaje natural introduce referencias incompletas. El sistema debe resolverlas utilizando Player Discovery, current Zone, nombres, alias y distancia. Nunca debe escoger un destino desconocido sólo porque semánticamente suene adecuado.

| Input | Resolución espacial |
| --- | --- |
| “voy al bar” | Buscar estructuras conocidas de tipo taberna/bar alcanzables; si hay varias, pedir elección o mostrar las más cercanas. |
| “voy a mi habitación” | Resolver player.home/private_room; si no existe o no está definida, no inventarla. |
| “salgo” | Buscar Exit semántico EXIT/OUT de la Room actual. |
| “subo” | Buscar Exits verticales ascendentes visibles/permitidos. |
| “voy al puerto” | Resolver Zone/destino conocido y calcular ruta; no mover a una descripción genérica. |
| “me alejo” | Puede requerir selección de Exit o aplicar heurística sólo entre Exits válidos, nunca crear dirección nueva. |

# 24. SAVEGAME Y PERSISTENCIA ESPACIAL

El savegame no necesita duplicar toda la definición del mundo si ésta pertenece a una versión de contenido estable. Debe almacenar referencia de versión y todos los deltas de estado/discovery necesarios para reconstruir la partida.

```text
SAVEGAME
world_definition_version: 0.1.12
player.current_room: CAR-VAR-PORT-017

world_state_deltas:
  DOOR-03.locked: false
  EXIT-BRIDGE-09.state: blocked
  ROOM-WH-02.state: burned
  OBJECT-BOX-04.location: PLAYER_INVENTORY

player_discovery:
  visited_rooms: [...]
  known_exits: [...]
  discovered_secrets: [...]
```

Los NPC persistentes guardan current_room o un estado de viaje materializable. Cargar una partida no debe recolocar personajes según lo que la narración “recuerde”.
