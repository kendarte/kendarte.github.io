# SIZA — Sistema de Espacio Físico y Mapas Persistentes MUD

**Especificación completa de la geometría jugable: World Graph, Zones, Rooms, Exits, interiores, pisos, puertas, rutas, descubrimiento y estado espacial**

Versión 0.1 · Documento mecánico separado del World Book y del sistema Player/NPC.

Objetivo: congelar cómo existe físicamente Rivarica dentro del juego antes de producir mapas de ciudades o continuar expandiendo contenido procedural.

> **Principio rector: en Siza el espacio existe antes de la narración. Qwen puede describirlo, pero nunca decidir que una habitación, puerta, calle, objeto o ruta existe porque le conviene a la escena.**

# 0. Problema que resuelve este documento

El prototipo actual puede conservar el nombre general de una ubicación, pero todavía trata el movimiento como una intención narrativa: el jugador escribe “voy al bar”, “voy a mi recámara” o “salgo al muelle” y el Master intenta imaginar qué significa. Ese enfoque es incompatible con un MUD. En un MUD el personaje ocupa exactamente una localización atómica, y moverse significa atravesar conexiones existentes entre localizaciones reales.

El objetivo de esta especificación es reemplazar la noción de “escena” por una base espacial persistente. Un pueblo será un grafo. Una calle será una secuencia o red de Rooms. Un edificio será una Zone interior conectada con el exterior. Una puerta será un Exit con estado. Un piso superior será otro conjunto de Rooms conectado por escaleras, rampas, ascensores o medios especiales. Los NPC usarán el mismo grafo que el jugador. Si una ruta no existe, nadie puede recorrerla; si una puerta está cerrada, el movimiento se detiene; si un puente se destruye, el grafo cambia y ese cambio permanece.

# 1. Las reglas espaciales que se congelan

1. La unidad mínima de presencia y navegación es la ROOM. Toda entidad espacial activa tiene un current_room.
2. El mundo físico se representa como un grafo persistente de Rooms conectadas por Exits.
3. Una Room no es necesariamente una habitación arquitectónica: puede ser una plaza, tramo de calle, cubierta, cornisa, muelle, cámara, pasillo, campo o espacio abierto suficientemente distinguible para interacción.
4. Una Zone agrupa Rooms que comparten contexto. Un asentamiento puede contener varias Zones y un edificio puede abrir una Zone interior propia.
5. Los Exits son datos de mundo. Qwen no puede crear, borrar o redirigir un Exit salvo que un sistema autorizado modifique el World State.
6. El mapa objetivo del mundo y el mapa descubierto por el jugador son capas distintas.
7. El estado de una Room o Exit puede cambiar sin que su identidad cambie: puerta cerrada, incendio, derrumbe, inundación de niebla, barricada, ocupación, reparación, etc.
8. Jugador y NPC se desplazan por el mismo grafo. La simulación no teletransporta NPC para acomodar una narración.
9. Una estructura especial o edificio generado se convierte en una instancia física con Zone, Rooms, Exits y objetos persistentes.
10. La IA recibe una ventana espacial autorizada y narra sólo lo que esa ventana permite.

# 2. Jerarquía física de Rivarica

La jerarquía canónica del World Book se formaliza para navegación. Los niveles superiores aportan contexto y escala; sólo las Rooms son posiciones atómicas de juego.

```text
WORLD: RIVARICA
└── PROVINCE
    └── REGION
        └── ISLAND / TERRITORIAL FEATURE
            └── SETTLEMENT
                ├── ZONE: DISTRITO / BARRIO / PUERTO / ACANTILADO
                │   └── ROOM EXTERIOR
                └── STRUCTURE INSTANCE
                    └── ZONE INTERIOR
                        ├── FLOOR / LEVEL
                        │   └── ROOM
                        └── SUBZONE RESTRINGIDA
                            └── ROOM
```

| Nivel | Qué significa | Qué NO significa |
| --- | --- | --- |
| World / Province | Marco político, leyes, moneda, física general y pertenencia territorial. | No es una Room ni una posición navegable. |
| Region / Island | Contexto geográfico, rutas mayores, quirks, peligros, recursos. | No sustituye el mapa local. |
| Settlement | Contenedor de población, facciones, estructuras y Zones locales. | No es una sola “escena”. |
| Zone | Agrupación de Rooms con contexto común y mapa local. | No tiene que equivaler a distrito administrativo. |
| Structure Instance | Edificio o instalación concreta situada en una Zone. | No es sólo un nombre en el lore. |
| Room | Posición atómica donde puede estar una entidad. | No tiene que tener cuatro paredes. |
| Exit | Conexión navegable o interactuable entre Rooms. | No es texto decorativo como “al norte hay una calle”. |

# 3. ROOM: átomo espacial del MUD

La Room es la respuesta exacta a la pregunta “¿dónde está este personaje ahora?”. Mientras una entidad esté activa dentro del mundo, debe poder resolverse a un room_id. El nombre narrativo de la ubicación es secundario; la identidad mecánica es el ID.

> **“Estoy en el puerto” es demasiado ambiguo para el motor. “Estoy en CAR-VAR-PORT-017” es una posición. El Master puede llamar a esa Room “pasarela oriental del cargadero”, pero la simulación trabaja con el ID.**

| Campo ROOM | Función |
| --- | --- |
| room_id | Identificador único e inmutable. |
| zone_id | Zone propietaria. |
| structure_id | Estructura propietaria si la Room es interior o pertenece a una instalación. |
| name | Nombre visible o funcional. |
| room_type | Calle, plaza, pasillo, salón, taller, muelle, escalera, cámara, exterior natural, etc. |
| elevation / level | Piso o nivel vertical relativo. |
| base_description | Descripción obvia al entrar; no contiene secretos. |
| geometry_tags | Amplia, estrecha, cubierta, exterior, vertical, inundable, etc. |
| capacity | Capacidad suave/dura de personas, monturas, carga o vehículos. |
| exits | Lista de conexiones autorizadas. |
| objects | Objetos persistentes presentes. |
| occupants | Entidades actualmente presentes o indexadas por la simulación. |
| environment | Luz, niebla, temperatura, ruido base, exposición, superficie. |
| sensory_layers | Hechos ocultos o no obvios ligados a sentidos y dificultades. |
| state_flags | Dañada, incendiada, bloqueada, inundada, ocupada, restringida, etc. |
| discovery_policy | Qué partes del Room/Exits son visibles automáticamente y cuáles requieren descubrimiento. |

## 3.1 Qué tamaño debe tener una Room

Una Room no se define por metros exactos sino por unidad de decisión. Debe dividirse el espacio cuando atravesarlo cambia interacciones, visibilidad, riesgo, acceso o destino. Una plaza pequeña puede ser una sola Room; una plaza enorme con mercado, monumento, callejones y entradas separadas puede requerir varias. Un pasillo de diez metros puede ser una sola Room; un puente largo expuesto a niebla puede dividirse en varios tramos porque cada tramo tiene consecuencias distintas.

La regla práctica es: si dos personajes pueden estar en el mismo lugar nominal pero enfrentan conjuntos distintos de Exits, objetos, NPC visibles o riesgos, probablemente necesitan Rooms diferentes.

## 3.2 Room exterior vs Room interior

El motor no trata “interior” como un tipo especial de física. Ambos son Rooms. La diferencia proviene de tags, permisos, visibilidad y Exits. Una calle tiene sky_exposure y varios accesos a estructuras; un almacén tiene roofed, puertas concretas, inventario y permisos. Esta uniformidad permite que las mismas reglas de movimiento, persecución, percepción, eventos y NPC funcionen en ambos contextos.

# 4. ZONES: mapas dentro del mapa

Una Zone es un subgrafo de Rooms. Su función es mantener manejable la escala y encapsular contexto. El mapa de una ciudad no necesita dibujar cada habitación de cada casa al mismo tiempo. Puede representar una estructura mediante su entrada; al cruzar el Exit ENTER se activa su Zone interior.

```text
[ZONE URBANA: PUERTO]

[PLAZA-01] -- [CALLE-02] -- [MUELLE-01]
     |              |
  ENTER          ENTER
     v              v
[PESCADERÍA]    [PUESTO WINDRAGO]

Cada caja inferior representa una Zone interior con su propio grafo.
```

## 4.1 Tipos de Zone

| Tipo | Uso |
| --- | --- |
| Settlement Zone | Mapa principal o sector de un asentamiento. |
| District Zone | Barrio, puerto, mercado, zona alta, industrial o religiosa. |
| Structure Zone | Interior de un edificio o instalación. |
| Floor Zone | Opcional para edificios complejos; agrupa Rooms por nivel. |
| Natural Zone | Cueva, bosque de islas, arrecife de niebla, cantera, mina. |
| Vehicle Zone | Aerobarco, nave, tren/plataforma móvil si se decide simularlo como espacio navegable. |
| Event Zone | Sólo cuando un evento altera temporalmente el grafo físico; no debe usarse para escenas que podrían existir como Rooms normales. |

## 4.2 Zonas anidadas

La anidación permite representar estructuras grandes sin contaminar el mapa urbano. Una Fortaleza Windrago puede ser un nodo en el mapa de la ciudad y contener una Zone con patio, torre, armería, oficinas y sótanos. Una Room de la fortaleza puede, a su vez, conducir a una subzone restringida. El motor nunca pierde la relación de retorno: todo salto de Zone debe estar respaldado por Exits explícitos.

# 5. EXITS: la geometría realmente jugable

Los Exits son aristas del grafo. Determinan qué movimientos son físicamente posibles. Una descripción puede sugerir que “al este se ve una torre”, pero eso no permite caminar a ella si no existe una ruta de Exits. Esta separación impide que el lenguaje natural destruya la topología del mundo.

| Campo EXIT | Función |
| --- | --- |
| exit_id | Identificador persistente de la conexión. |
| from_room / to_room | Origen y destino. |
| direction | N, S, E, O, arriba, abajo, entrar, salir o comando especial. |
| bidirectional | Si la conexión es reversible automáticamente. |
| travel_cost | Costo temporal o de movimiento. |
| mode | Caminar, trepar, nadar, aerobarco, ascensor, salto, puerta, etc. |
| door_id | Puerta/compuerta asociada si existe. |
| requirements | Llave, permiso, Knowledge, herramienta, tamaño, estado, acompañante, etc. |
| visibility | Visible, oculto, secreto, descubierto, sólo desde un lado. |
| hazard | Riesgos espaciales que pueden activar resolución. |
| capacity | Restricciones de personas/carga simultáneas. |
| state | Disponible, cerrado, bloqueado, destruido, en reparación, sellado. |

## 5.1 Direcciones no son suficientes
