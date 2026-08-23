Los quirks se combinan. Un asentamiento COASTAL + HIGH_ALTITUDE + AEROSHIP_ROUTE no debe parecer simplemente “costero”; probablemente tenga muelle bajo, ascensores de acantilado, aeromuelle alto y un flujo vertical de carga. El generador debe resolver conflictos entre tags mediante prioridades físicas: una estructura sólo aparece si existe un lugar viable y una razón económica para sostenerla.


# 5. Control persistente de facciones

Cada asentamiento registra porcentajes de dominio o influencia. Estos valores no reemplazan la geografía ni la economía; modifican qué instituciones existen, quién puede construirlas, quién las controla, qué Jobs tienen acceso al poder y qué eventos son probables.

```text
FACTION_CONTROL
Windrago: 35
Advenidos: 45
Eclesia: 8
Ladrones: 12

dominant_faction: ADVENIDOS
local_leader_id: NPC-...
contested: true
```

Las cuatro alineaciones principales para esta capa son WINDRAGO, ADVENIDOS, ECLESIA y LADRONES. La infraestructura COMÚN no es una quinta facción: pescaderías, viviendas, mercados, cisternas, talleres o tabernas pueden ser civiles y posteriormente quedar financiadas, protegidas, infiltradas, tributadas o capturadas por una facción.


## 5.1 Qué debe cambiar el porcentaje de facción

- Probabilidad y cantidad de estructuras propias de la facción dentro de los límites del asentamiento.
- Capacidad de nombrar autoridad local, patrullar, cobrar, proteger, predicar, ocultar o arbitrar.
- Composición de Jobs institucionales disponibles.
- Seguridad efectiva y tiempos de respuesta.
- Rumores, leyes informales y prioridades de inversión.
- Eventos de conflicto cuando dos facciones compiten por la misma capacidad o recurso.


## 5.2 Líder local

Todo asentamiento debe tener una autoridad o liderazgo identificable. “Líder” no significa siempre alcalde: puede ser comandante, cabildo, figura religiosa, representante de Casa, coalición o poder clandestino. El generador registra quién ejerce autoridad formal y quién posee poder efectivo. Si ambos difieren, esa discrepancia se convierte en fuente de eventos.


# 6. Generación de edificios

El generador no selecciona edificios de una bolsa aleatoria. Los crea en seis pasadas, cada una con una causa distinta. El resultado final debe poder explicarse desde los parámetros del asentamiento.

| Pasada | Origen | Pregunta |
| --- | --- | --- |
| 1. Indispensables | Población y supervivencia | ¿Qué necesita esta cantidad de habitantes para seguir existiendo? |
| 2. Económicas | Recursos y especialización | ¿De qué vive el asentamiento y cómo transforma/almacena lo producido? |
| 3. Geográficas | Quirks y rutas | ¿Qué infraestructura exige el terreno y cómo se mueve la gente/carga? |
| 4. Faccionales | Control e influencia | ¿Qué instituciones pudieron construir/sostener las facciones presentes? |
| 5. Especiales | Canon/historia | ¿Qué estructuras únicas están fijadas y deben existir siempre? |
| 6. Clandestinas | Crimen, presión económica y huecos de control | ¿Qué redes ilegales pueden esconderse dentro de la infraestructura legítima? |


## 6.1 Requisitos y capacidad

Una estructura se construye o se mantiene sólo si cumple requisitos: población suficiente, recurso o cadena de suministro, conocimiento, cuota energética, ruta y una razón social/económica. Esto conserva la regla canónica de que los árboles no mejoran sólo porque “sube un nivel”.

```text
CAN_BUILD(structure) =
  population_ok
  AND geography_ok
  AND required_inputs_available
  AND route_or_local_supply_ok
  AND workforce_possible
  AND faction_or_civil_permission_ok
  AND special_requirements_ok
```


## 6.2 Base de ramas civiles ya existentes

El World Book ya contiene un árbol civil que sirve como vocabulario inicial. Esta especificación no congela todavía todos los blueprints internos, pero sí conserva las ramas como capacidades de sociedad.

| Rama | Grado I | Grado II | Grado III |
| --- | --- | --- | --- |
| Cívica | Plaza de Pulso | Cabildo de Isla | Casa Provincial |
| Energía y agua | Cargadero / Cisterna | Casa de Bombas | Reserva de Nexo |
| Pesca | Muelle de Pesca | Cámara Fría | Intercambio Abisal |
| Minería acuática | Muelle de Descenso | Casa de Campanas | Estación Béntica |
| Industria | Taller de Caldera y Escama | Astillero | Dársena Aeromarina |
| Salud civil | Botiquín / Consultorio | Clínica / Hospital | Instituto Médico |
| Defensa | Puesto de Guardia | Baluarte | Fortaleza |
| Entretenimiento | Taberna / Patio | Teatro / Restaurante | Barrio de Fiesta |
| Conocimiento | Escuela | Archivo / Academia | Observatorio de Niebla |
| Ruta | Embarcadero / Posta | Puerto de Enlace | Nodo Aeromarino |
| Reserva | Punto de Incidente | Puesto Darkhaven | Estación de Cuarentena |
| Clandestina | Escondrijo | Casa de Contraseña | Corte del Fondo |


# 7. Contrato de una STRUCTURE

Una Structure Template define qué clase de edificio existe en el vocabulario del generador. Una Structure Instance es una copia concreta colocada en un asentamiento. El template no tiene dueño individual; la instancia sí.

| Campo | Descripción |
| --- | --- |
| structure_type_id | Identificador estable del tipo de edificio. |
| alignment | COMÚN, WINDRAGO, ADVENIDOS, ECLESIA, LADRONES u otra rama canónica. |
| tier / grade | Nivel tecnológico o de capacidad. |
| requirements | Población, quirks, estructuras previas, recursos, Jobs y permisos necesarios. |
| capacity_tags | Subsistencia, industria, comercio, defensa, fe/cuidado, entretenimiento/conocimiento. |
| resource_inputs | Recursos que consume para operar. |
| resource_outputs | Recursos o servicios que produce. |
| job_slots | Puestos que habilita y rangos de cantidad. |
| room_blueprint | Rooms mínimas y conexiones internas. |
| security_profile | Permisos, barreras, guardia y respuesta. |
| event_repertoire | Servicio, rutina, conflicto, alarma, escasez, delito, facción y anomalía. |
| upgrade_paths | Qué puede mejorar y qué desbloquea. |


## 7.1 Datos de una instancia

```text
STRUCTURE_INSTANCE
  id
  template_id
  settlement_id
  district_id
  name
  owner_id
  controller_faction
  tier
  condition
  energy_quota
  inventory
  job_occupancy
  schedule
  security_state
  relationships
  current_events
  room_zone_id
```


## 7.2 Ejemplo de blueprint: Pescadería I

La Pescadería I ya existe como ejemplo canónico: mostrador, canal de lavado, cuchillos, mesa de corte, cubos de sal, cámara fría y puerta trasera. Para el MUD eso se formaliza como un blueprint de Rooms, no como una sola descripción.

```text
STRUCTURE_COMMON_FISHMONGER_I
Rooms mínimas:
  FISH-ENTRANCE / MOSTRADOR
  FISH-CUTTING / ÁREA DE CORTE
  FISH-COLD / CÁMARA FRÍA
  FISH-LOAD / PATIO O CALLEJÓN DE CARGA

Exits base:
  ENTRANCE <-> CUTTING
  CUTTING <-> COLD
  CUTTING <-> LOAD
  ENTRANCE <-> SETTLEMENT_ROOM
```

El template define la geometría mínima. La instancia puede añadir una habitación familiar, un altillo, una segunda cámara fría o una puerta bloqueada por historia local, pero no puede perder la función que justifica sus Jobs sin pasar a estado degradado.


# 8. ROOM: unidad mínima del MUD

Una Room es una localización atómica para movimiento e interacción. “Voy al bar” no mueve al jugador narrativamente; el motor debe resolver una ruta válida desde CURRENT_ROOM hasta una Room de destino o pedir una elección cuando la referencia sea ambigua.

| Campo | Función |
| --- | --- |
| room_id | Identificador inmutable. |
| zone_id | Zona o interior al que pertenece. |
| name | Nombre visible cuando se conoce. |
| base_description | Información obvia sin tirada. |
| exits | Conexiones válidas a otras Rooms. |
| objects | Objetos persistentes presentes. |
| npc_presence | NPC actualmente en la Room. |
| structures_visible | Estructuras o entradas observables desde la Room. |
| permissions | Pública, trabajo, privada, restringida u otra regla de acceso. |
| sensory_layers | Hechos revelables por vista, oído, olfato, tacto y gusto. |
| local_state | Luz, Niebla, daño, puertas, incendios, suciedad, etc. |
| event_hooks | Eventos o disparadores asociados al lugar. |


## 8.1 Exits

Un Exit es una arista del grafo. Debe poder representar dirección, destino, estado y condiciones. No todos los Exits tienen que ser cardinales.

```text
EXIT
  id: EXIT-00231
  from: ROOM-A
  to: ROOM-B
  command_tags: [norte, entrar, puerta_del_fondo]
  bidirectional: true
  state: closed
  lock_state: unlocked
  requirements: []
  travel_cost: 1
  visible_by_default: true
```

Los pasadizos secretos son Exits existentes con visible_by_default=false. Una tirada de Percepción puede revelar el Exit al jugador; no crea el pasadizo.


# 9. Descripción base y percepción por los cinco sentidos

Cada Room tiene una capa descriptiva obvia y capas sensoriales no reveladas. La percepción no es un chequeo pasivo automático al entrar. Se activa cuando la acción del jugador deriva de uno de los cinco sentidos y existe información relevante cuya obtención no sea trivial.


## 9.1 Regla de activación

```text
IF action.intent == PERCEIVE
AND action.sense IN [SIGHT, HEARING, SMELL, TOUCH, TASTE]
AND target_is_reachable
AND hidden_fact_exists
AND uncertainty_or_consequence_exists
THEN resolve PERCEPTION
ELSE describe obvious result without roll
```


## 9.2 Los cinco sentidos

| Sentido | Acciones típicas | Ejemplos de hechos revelables |
| --- | --- | --- |
| Vista | Mirar, observar, inspeccionar, buscar visualmente. | Sellos rotos, manchas, gestos, marcas, movimiento, salida oculta. |
| Oído | Escuchar, acercar el oído, distinguir voces. | Conversación detrás de puerta, mecanismo, pasos, objeto suelto. |
| Olfato | Oler, rastrear olor, identificar humo o sustancia. | Sangre, combustible, podredumbre, metal, contaminación. |
| Tacto | Palpar, tocar, medir temperatura, sentir vibración. | Calor anormal, pared hueca, humedad, vibración mecánica. |
| Gusto | Probar una sustancia accesible. | Salinidad, veneno, deterioro, composición aproximada cuando el Job lo permite. |


## 9.3 Capas de dificultad

Cada hecho sensorial posee una dificultad contextual y prerequisitos. La dificultad pertenece al hecho, no a una descripción entera. Una misma Room puede contener diez hechos de diferentes sentidos y dificultades.

```text
SENSORY_FACT
  fact_id: FACT-CARGO-019
  sense: SIGHT
  target_id: BOX-004
  difficulty: 8
  prerequisites: [line_of_sight]
  reveal: "el sello fue rehecho después de abrir la caja"
  persistent_discovery: true
  expires: false
```


## 9.4 Qué se narra al entrar
