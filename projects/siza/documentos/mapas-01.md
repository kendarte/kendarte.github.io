El clásico norte/sur/este/oeste sigue siendo útil, pero Siza necesita Exits semánticos porque el mundo contiene interiores, verticalidad y tecnología. “entrar en La Escama Celeste”, “subir por la escalera de servicio”, “cruzar la pasarela”, “usar el elevador”, “bajar al muelle inferior” o “embarcar” son Exits válidos. Internamente todos terminan en un to_room.

## 5.2 Exits unidireccionales y especiales

No todas las conexiones deben ser simétricas. Saltar desde un balcón puede llevar a un patio sin permitir regresar por la misma arista. Una corriente de Niebla puede arrastrar hacia otra Room. Un descenso por cuerda puede requerir equipo para regresar. El Exit debe declarar direccionalidad y condiciones; nunca se deduce por prosa.

# 6. PUERTAS, BARRERAS Y OBJETOS DE PASO

Una puerta no es sólo una frase del Room. Es un objeto espacial ligado a uno o más Exits. Puede cambiar de estado sin modificar la existencia de las Rooms conectadas.

```text
ROOM-A -- EXIT-17 / DOOR-03 -- ROOM-B

DOOR-03 state:
  open: false
  locked: true
  broken: false
  barred_from: ROOM-B
  key: KEY-WG-04
  noise_on_force: high
```

| Estado | Efecto espacial |
| --- | --- |
| Abierta | El Exit puede recorrerse sin resolución si no hay otra restricción. |
| Cerrada sin llave | La interacción “abrir” cambia estado y permite pasar. |
| Cerrada con llave | Exige llave, permiso, manipulación o fuerza según método. |
| Barricada | Puede bloquear sólo desde un lado o requerir desmontaje. |
| Destruida | El Exit sigue existiendo, pero cambia ruido, seguridad, cobertura o acceso. |
| Sellada | Puede desactivar temporalmente el Exit. |
| Oculta | El Exit existe en World Definition pero no en Player Discovery hasta ser encontrado. |

# 7. MAP DEFINITION, WORLD STATE Y PLAYER DISCOVERY

Estas tres capas no deben mezclarse. Separarlas es lo que hace posible un mundo persistente que cambie sin perder su identidad y un mapa que el jugador pueda descubrir.

## 7.1 MAP DEFINITION: la verdad estructural

Contiene lo que existe por diseño: IDs, Rooms, Zones, Exits, relaciones de pertenencia, geometría base, estructura de pisos y objetos permanentes. Normalmente cambia sólo por generación inicial, edición de contenido o transformaciones mayores autorizadas como construcción/demolición.

## 7.2 WORLD STATE: la verdad actual

Contiene lo que le ocurrió a esa estructura: puerta cerrada, calle bloqueada, habitación incendiada, puente derrumbado, edificio capturado, ascensor sin energía, niebla grado 4, agua en el piso, objeto movido. El ID de la Room permanece; cambia su estado.

## 7.3 PLAYER DISCOVERY: lo que sabe el jugador

Registra Rooms visitadas, Exits conocidos, rutas secretas descubiertas, nombres aprendidos, peligros identificados y conocimiento cartográfico. El jugador puede conocer una entrada sin haberla atravesado o haber visitado una Room sin haber encontrado todos sus Exits.

```text
MAP DEFINITION
  ROOM-17 exists
  SECRET_EXIT-4 -> ROOM-92

WORLD STATE
  SECRET_EXIT-4 is usable
  DOOR-4 is closed

PLAYER DISCOVERY
  ROOM-17 discovered = true
  SECRET_EXIT-4 discovered = false

Resultado: el mundo sabe que existe; el jugador todavía no.
```

# 8. EL MAPA VISIBLE DEL JUGADOR

El automapper no debe mostrar automáticamente el grafo completo. Debe ser una proyección de Player Discovery. Cuando el jugador entra por primera vez a una Room, ésta se añade al mapa si la política lo permite. Exits obvios pueden aparecer inmediatamente; Exits ocultos sólo después de descubrirlos. Lugares conocidos por conversación o mapas comprados pueden aparecer como nodos no visitados, diferenciados visualmente de los recorridos.

La UI puede ofrecer capas: geografía, estructuras, facciones, rutas y riesgos, pero todas consultan datos persistentes. La capa gráfica es una vista del grafo, no la fuente del grafo.

## 8.1 Estados de descubrimiento recomendados

| Estado | Significado |
| --- | --- |
| UNKNOWN | No aparece al jugador. |
| RUMORED | Sabe que el lugar existe, pero no su posición exacta o ruta completa. |
| LOCATED | Conoce su posición o conexión, pero no lo ha visitado. |
| VISITED | Ha ocupado la Room al menos una vez. |
| MAPPED | Tiene Exits principales confirmados. |
| SURVEYED | Ha identificado características relevantes y conexiones ocultas conocidas. |

# 9. MOVIMIENTO DEL JUGADOR

Toda orden espacial se traduce primero a una intención de destino. El motor no permite que la narración mueva al personaje antes de validar el grafo.

```text
INPUT: “voy al bar”
   ↓
1. Resolver referencia “bar” dentro del conocimiento del jugador
   ↓
2. Obtener candidate destination rooms
   ↓
3. Si hay uno: calcular ruta
   Si hay varios: pedir/mostrar elección
   Si no hay ninguno conocido: acción de búsqueda, no teletransporte
   ↓
4. Validar Exits de la ruta contra WORLD STATE
   ↓
5. Mover Room por Room
   ↓
6. Procesar tiempo, encuentros, triggers y cambios en cada transición
   ↓
7. Narrar resultado autorizado
```

## 9.1 Movimiento de una sola Room

Comandos como “entro”, “salgo”, “subo”, “cruzo la puerta” o tocar un destino cercano normalmente recorren un solo Exit. Si el Exit está libre, el movimiento ocurre sin dado. Si existe un obstáculo significativo, el movimiento se detiene y aparece la interacción correspondiente.

## 9.2 Movimiento hacia destino lejano

Una orden como “voy a la plaza” puede convertirse en pathfinding sobre Rooms conocidas. La interfaz puede abreviar los pasos tranquilos, pero el motor debe procesarlos. Si durante la ruta aparece un evento, bloqueo, NPC relevante, peligro o cambio de estado, el viaje se interrumpe en la Room exacta donde ocurre.

> **La abreviación narrativa nunca equivale a teletransporte. Puede ocultar pasos al jugador cuando no pasa nada, pero el estado espacial debe avanzar Room por Room.**

## 9.3 Pathfinding y coste

Cada Exit tiene travel_cost. La ruta más corta no siempre es la más rápida o segura. El pathfinder puede usar perfiles: rápido, seguro, discreto, accesible, carga pesada. Un personaje con conocimiento local puede desbloquear rutas o reducir incertidumbre, pero el grafo base sigue siendo el mismo.

# 10. MOVIMIENTO DE NPC Y SIMULACIÓN ESPACIAL

Los NPC usan exactamente el mismo sistema. Cada NPC activo mantiene current_room, destination_room, route, current_action y movement_mode. Las rutinas no dicen simplemente “a las 8 está en el trabajo”; generan un viaje desde su hogar hasta el trabajo por Exits válidos.

```text
NPC-0481
current_room: HOUSE-081-BEDROOM
destination_room: FISHMONGER-03-COUNTER
route: [HOUSE-HALL, STREET-12, PLAZA-04, FISH-ENTRANCE, FISH-COUNTER]
current_action: commute_to_work
```

Para ahorrar computación, los NPC alejados del jugador pueden simularse de forma agregada, pero su posición debe poder materializarse coherentemente. Cuando entran en el radio activo del jugador, el sistema resuelve una Room válida compatible con la ruta y el horario, no una aparición arbitraria.

## 10.1 Radio de simulación

| Nivel | Comportamiento |
| --- | --- |
| Hot / misma Zone | Movimiento Room por Room, presencia exacta, objetos y triggers completos. |
| Warm / mismo asentamiento | Ruta y horarios persistentes; pasos pueden agruparse entre puntos relevantes. |
| Cold / otra región | Estado agregado: viaje, trabajo, hogar, evento; se materializa sólo al acercarse o cuando un evento lo requiere. |

# 11. INTERIORES COMO BLUEPRINTS FÍSICOS

El catálogo de estructuras no sólo declara qué produce un edificio: debe incluir un Room Blueprint mínimo. Cuando el generador coloca una Pescadería I, instancia una topología reconocible; luego aplica variaciones de tamaño, orientación, accesos y estado.

```text
PESCADERÍA I — BLUEPRINT

[CALLE]
   | ENTER
[ENTRADA / MOSTRADOR] -- [ÁREA DE CORTE] -- [CÁMARA FRÍA]
          |                     |
      [OFICINA?]          [PATIO DE CARGA] -- EXIT SERVICE -> [CALLEJÓN]

Rooms opcionales dependen de Tier, lote, riqueza y quirks.
```

## 11.1 Blueprint vs instancia

El Blueprint define identidad funcional: qué espacios necesita una pescadería para operar. La instancia define el edificio real: nombre, IDs, orientación, propietario, puertas, estado, dimensiones narrativas, objetos y conexiones con la ciudad. Dos pescaderías comparten lógica sin ser copias exactas.

## 11.2 Room slots obligatorios y opcionales

| Slot | Regla |
| --- | --- |
| PUBLIC | Debe ser accesible desde el exterior durante horario activo. |
| WORK | Zona operativa; puede exigir Job, invitación o permiso. |
| STORAGE | Inventario y recursos; seguridad superior a la zona pública. |
| SERVICE EXIT | Acceso logístico opcional pero frecuente. |
| PRIVATE | Oficina, vivienda o administración cuando corresponda. |
| RESTRICTED | Armería, bóveda, santuario interno, cámara técnica, etc.; sólo si el tipo/Tier lo exige. |
| VERTICAL | Escalera, torre, sótano, plataforma o ascensor cuando el blueprint tenga niveles. |

# 12. PISOS, ALTURA Y ESPACIO VERTICAL

Caribia necesita verticalidad real: islas altas, puentes, torres, aeromuelles, fortalezas y estructuras sobre niebla. Cada Room puede tener elevation/level, pero el movimiento vertical siempre ocurre por Exits. “Está arriba” no es una conexión.

```text
LEVEL +2   [TORRE DE SEÑALES]
              | STAIRS_DOWN
LEVEL +1   [PASARELA] -- [OFICINA]
              | STAIRS_DOWN
LEVEL  0   [GUARDIA] -- [ENTRADA] -- EXIT -> CALLE
              | STAIRS_DOWN
LEVEL -1   [DEPÓSITO] -- [CALABOZO]
```

Los niveles sirven también para line_of_sight, caída, ruido, rutas de evacuación y riesgo. Un ascensor sin energía no borra el piso superior: cambia el estado del Exit vertical y obliga a buscar otra ruta.

# 13. ESPACIOS ABIERTOS, CALLES Y DISTRITOS

El sistema no debe caer en el error de tratar cada calle como una sola Room infinita. Las calles se segmentan cuando cambian cruces, entradas relevantes, visibilidad, riesgo o función. El objetivo es producir topología jugable, no cartografía centimétrica.

## 13.1 Reglas de segmentación

- Crear una Room en cada intersección importante.
- Crear una Room frente a conjuntos de entradas relevantes cuando la elección de acceso importe.
- Dividir trayectos largos cuando puedan contener eventos, persecuciones o peligros diferenciados.
- Usar una sola Room para tramos pequeños y homogéneos sin decisiones significativas.
- Evitar convertir cada puerta residencial decorativa en una Room exterior distinta si no cambia el juego.
- Reservar granularidad alta para lugares donde el jugador realmente puede actuar.

# 14. OBJETOS Y ANCLAJE ESPACIAL
