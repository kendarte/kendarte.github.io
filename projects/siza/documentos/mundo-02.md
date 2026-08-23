La entrada a una Room entrega sólo información obvia: forma, iluminación, ocupación evidente, obstáculos, salidas visibles y señales de actividad. El World Book ya pide firmas sensoriales para estructuras; en este sistema esa regla se usa para ambientación obvia sin convertir cada olor o sonido en pista automática. Los secretos quedan en sensory_layers.

# 10. Objetos persistentes

Los objetos interactuables siguen la misma separación: estado objetivo, affordances y capas sensoriales. Una caja existe aunque el jugador nunca la inspeccione. Su contenido no se transforma para acomodar la narración.

```text
OBJECT
  id
  template_id
  room_id
  visible_name
  base_description
  state
  movable
  mass
  interactions: [look, touch, open, force, move, break]
  sensory_layers
  contained_objects
  ownership
  evidence_tags
```

## 10.1 Acciones corrientes vs acciones con resolución

Se conserva la regla canónica: sentarse en una silla, cruzar una puerta abierta o comprar un producto disponible no requiere tirada. Abrir una caja cerrada, manipular una caldera, distinguir una mancha casi invisible o actuar bajo oposición sí puede activar una resolución. La tirada aparece porque el resultado importa, no porque exista un objeto interactuable.

# 11. De edificios a Jobs

Los NPC no se generan primero. Cada edificio declara job_slots. Cuando se instancia el edificio, esos puestos pasan a la demanda laboral del asentamiento. La población disponible los cubre según formación, necesidad, facción y rutas.

```text
PESCADERÍA I
  1 x Pescadero
  0..2 x Aprendiz
  0..1 x Cargador

BALUARTE II
  1 x mando local
  N x guardia
  N x logística / reserva / mantenimiento
  ... según árbol Windrago congelado en su documento específico
```

Una estructura sin Job cubierto puede seguir existiendo, pero cambia de estado: cerrada, degradada, en búsqueda de personal o en construcción. Si un NPC muere o migra, el puesto queda vacante y el mundo reacciona en lugar de reemplazarlo silenciosamente.

## 11.1 Contrato de Job

La plantilla de Jobs existente ya separa knowledge_domains, gossip_domains, routine_tags, economic_role y perks. Este sistema añade la relación explícita con estructuras y horarios.

```text
JOB
  id
  name
  allowed_structure_types
  knowledge_domains
  gossip_domains
  routine_tags
  economic_role
  qualification_requirements
  typical_schedule
  faction_restrictions
  equipment_access
```

# 12. De Jobs a NPC, hogares y población social

Un puesto ocupado materializa un NPC persistente. El NPC hereda contexto del Job y del asentamiento, pero mantiene personalidad, memoria, relaciones y afiliaciones propias. La plantilla canónica ya contiene origen, residencia, Job, clase social, edad, afiliaciones, postura, persistencia, memorias y relaciones.

```text
NPC_INSTANCE
  id
  job_id
  employer_structure_id
  residence_id
  family_id
  affiliations
  personality/posture
  knowledge
  gossip
  memories
  relationships
  routine
  current_room
  current_state
```

## 12.1 Hogares

Los trabajadores generan demanda residencial y vínculos familiares. Los hogares completan población social: pareja, hijos, dependientes, familiares o compañeros. No toda la población debe materializarse como NPC completo desde el inicio. El sistema puede mantener población abstracta por hogar/barrio y promover individuos a NPC persistentes cuando ocupan un Job relevante, interactúan con el jugador o entran en un evento.

## 12.2 Rutinas espaciales

Una rutina es una secuencia de destinos en el grafo, no una frase. El NPC cambia current_room siguiendo horario, accesibilidad y eventos. Si una ruta está cerrada, debe encontrar alternativa, retrasarse o cancelar la actividad según sus reglas.

```text
05:00  HOME-KITCHEN
05:30  ROUTE -> MARKET
06:00  FISHMONGER-CUTTING
13:30  FISHMONGER-CLOSE
14:00  MARKET / SUPPLY
15:00  HOME
18:00  ADVENIDO_NODE (ciertos días)
```

# 13. Eventos producidos por estructuras y estado

Cada estructura mantiene un repertorio de reacción ya establecido en el World Book: servicio, rutina, conflicto, alarma, escasez, delito, facción y anomalía. El generador no necesita cientos de quests prefabricadas; combina esos repertorios con el estado real de la estructura, sus trabajadores, recursos y facciones.

| Familia | Disparador típico | Consecuencia inicial |
| --- | --- | --- |
| Servicio | Jugador compra, vende, pregunta o solicita una función. | Interacción normal; precios, horarios, disponibilidad. |
| Rutina | Hora, cierre, llegada de carga, relevo. | NPC cambia Room/estado; inventario entra o sale. |
| Conflicto | Disputa laboral, deuda, rivalidad, provocación. | Relaciones y reputación cambian. |
| Alarma | Robo visto, agresión, incendio, intrusión. | Personal/seguridad responde según capacidad real. |
| Escasez | Falla de frío, agua, cuota, materia prima. | Servicio se degrada; precios y necesidades cambian. |
| Delito | Contrabando, robo, falsificación, protección. | Red clandestina usa huecos del sistema legítimo. |
| Facción | Activo, mandato o prestigio faccional afectado. | La facción moviliza estructuras y Jobs disponibles. |
| Anomalía | Niebla, contaminación o fenómeno no cotidiano. | Protocolos y estructuras especializadas reaccionan. |

## 13.1 Escalada por relaciones

Las consecuencias escalan desde los presentes hasta el territorio sólo cuando existen vínculos para hacerlo: pelea local → alarma de estructura → respuesta de barrio → nivel de búsqueda/ruta → crisis de facción → crisis territorial. El sistema consulta testigos, comunicaciones, personal disponible y rutas antes de escalar.

# 14. Economía local y cadenas de dependencia

Las estructuras no sólo decoran el mapa: consumen y producen recursos. Eso convierte la distribución de edificios en economía jugable. La destrucción o cierre de un nodo propaga consecuencias hacia los edificios que dependían de él.

```text
FUENTE / EXTRACCIÓN
   -> TRANSPORTE
      -> PROCESAMIENTO
         -> ALMACENAMIENTO
            -> COMERCIO / SERVICIO
               -> CONSUMO
```

Ejemplo abstracto: un asentamiento con MINING_NEARBY puede generar extracción/cargadero, almacenamiento, talleres y seguridad asociada. Si la ruta queda bloqueada, los talleres no reciben materia prima, ciertos Jobs pierden horas, el inventario cae y aparecen eventos de escasez, contrabando o protesta. La IA sólo narra las consecuencias calculadas.

# 15. Tres capas de persistencia

Para que el MUD sea consistente hay que separar tres verdades. Mezclarlas es la causa típica de que un LLM “olvide” habitaciones, puertas o pistas.

| Capa | Qué contiene | Quién puede modificarla |
| --- | --- | --- |
| MAP DEFINITION | Rooms, Exits, estructura física, templates y posiciones. | Generador/edición de mundo; cambios estructurales explícitos. |
| WORLD STATE | Puertas, daño, inventario, control, NPC vivos, horarios, precios, eventos. | Simulación y acciones del jugador/NPC. |
| PLAYER DISCOVERY | Rooms conocidas, Exits descubiertos, hechos percibidos, nombres reconocidos. | Experiencia del jugador; no altera la realidad objetiva. |

## 15.1 Conocimiento de NPC como cuarta capa informativa

Además del discovery del jugador, cada NPC posee knowledge y gossip propios. Un pescadero no puede revelar automáticamente secretos del gobierno porque Qwen los conoce en el contexto global. Cuando Qwen interpreta un NPC, sólo debe recibir o utilizar los hechos que ese personaje puede conocer, más rumores que pueda creer aunque sean falsos.

# 16. Flujo de una acción del jugador

Toda acción libre escrita por el jugador atraviesa una cadena determinista antes de llegar a la prosa final.

1. Parser de intención: extrae verbo, objetivo, sentido si aplica, destino y modificadores.
2. Validación espacial: comprueba que el objetivo o Exit exista y sea alcanzable desde CURRENT_ROOM.
3. Validación de estado: puertas, permisos, inventario, presencia de NPC, horario y condiciones.
4. Resolución mecánica: sólo si existe incertidumbre significativa, oposición, presión o coste.
5. Mutación de WORLD STATE: movimiento, objeto abierto, daño, gasto, alarma, descubrimiento, etc.
6. Selección de contexto narrable: facts autorizados, NPC presentes y consecuencias inmediatas.
7. Master IA: redacta la escena sin crear nueva geometría ni hechos no autorizados.
8. Persistencia: guarda cambios y actualiza discovery, memoria o eventos futuros.

## 16.1 Ejemplo: “escucho detrás de la puerta”

```text
PARSER
  intent = PERCEIVE
  sense = HEARING
  target = DOOR-WH-02

SPATIAL CHECK
  target exists in CURRENT_ROOM = true
  reachable = true

PERCEPTION
  relevant hidden fact difficulty = 6
  result = success

REVEAL
  FACT-WH-09 = "dos personas discuten dentro"

PLAYER_DISCOVERY
  FACT-WH-09 = known

MASTER IA
  narra el hecho revelado; no decide cuántas personas hay.
```

# 17. Algoritmo de generación de asentamientos

Este es el pipeline propuesto para construir persistentemente una ciudad o pueblo. Debe ser reproducible mediante seed: la misma seed + los mismos parámetros producen la misma base espacial.

1. Cargar contexto heredado: provincia, región, isla, leyes, arquitectura y economía base.
2. Leer perfil del asentamiento: identidad, población, quirks, recursos, rutas, peligros, facciones y estructuras especiales.
3. Calcular infraestructura indispensable por escala de población.
4. Añadir especializaciones económicas derivadas de recursos y riqueza.
5. Añadir infraestructura geográfica derivada de quirks y rutas.
6. Aplicar árboles tecnológicos de facciones según presencia, control, requisitos y liderazgo.
7. Insertar estructuras especiales canónicas sin aleatoriedad.
8. Calcular red clandestina según crimen, comercio y huecos de control.
9. Distribuir edificios por distritos/zonas y crear instancias persistentes.
10. Instanciar Room Blueprints de cada estructura y conectar Exits a la red urbana.
11. Crear Job Slots desde estructuras activas.
12. Asignar población a Jobs; generar NPC persistentes donde sea necesario.
13. Crear hogares/residencias y rutinas espaciales.
14. Inicializar inventarios, cuotas, seguridad, producción y consumo.
15. Sembrar eventos activos y tensiones a partir del estado, no de una quest aleatoria independiente.
16. Crear PLAYER_DISCOVERY inicial vacío o condicionado por el origen del personaje.

## 17.1 Regla de explicación

> **Todo edificio generado debe poder responder “¿por qué existe aquí?”. Si la respuesta no sale de población, geografía, recurso, ruta, facción, historia especial o red clandestina, el edificio es ruido y debe eliminarse.**

# 18. Ejemplo técnico NO CANÓNICO de generación

El siguiente ejemplo usa un asentamiento ficticio de prueba para demostrar el sistema. No añade lore a Rivarica y no debe incorporarse al World Book como localidad real.

```text
