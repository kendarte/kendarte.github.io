# SIZA — Sistema de Mundo Persistente MUD

**Especificación de asentamientos, estructuras, Rooms, percepción, Jobs, NPC, eventos y generación procedural**

Versión 0.1 · Documento de expansión mecánica separado del World Book

Estado: diseño base para congelar arquitectura antes de producir mapas persistentes.

> **Principio rector: el mundo decide qué existe; el Master IA interpreta acciones y narra resultados. Qwen no inventa la geometría del mundo.**


## Propósito

Este documento define la base espacial y sistémica de Siza como MUD persistente. El problema que resuelve es concreto: el prototipo actual puede narrar una ubicación, pero todavía no trata el espacio como una red física estable de Rooms. Para corregirlo, cada asentamiento se genera desde parámetros objetivos; sus edificios se convierten en instancias persistentes; cada edificio contiene Rooms conectados; los edificios generan Jobs; los Jobs generan NPC y rutinas; y el estado de esos elementos produce eventos y consecuencias que permanecen.

El documento no sustituye el World Book. El World Book continúa siendo la fuente canónica de Rivarica. Esta especificación toma reglas ya existentes del canon y las convierte en contratos utilizables por el generador, el mapa, el motor de juego y el Master IA.


## Fuentes de diseño utilizadas

Base canónica: Rivarica World Book, especialmente “Asentamientos, estructuras y vida persistente”, los árboles de estructuras/facciones, el atlas territorial y las plantillas de Jobs, NPC y world-state. Referencia de interacción espacial: la filosofía clásica de MUD/zMUD basada en Rooms, Exits, Zones y mapas persistentes. Las reglas nuevas incluidas aquí se identifican como especificación de sistema y no como historia canónica.


# 0. Resumen ejecutivo

Siza se modelará como un grafo persistente. La unidad mínima de espacio jugable es la ROOM. El jugador se mueve Room por Room; cada Room conoce sus Exits, objetos, NPC presentes, descripción base, estado y capas sensoriales. Las ciudades no se escriben como prosa libre: se generan a partir de población, geografía, recursos, rutas, peligros, dominio de facciones y estructuras especiales. Los edificios que resultan de esos parámetros instancian blueprints de Rooms y puestos de trabajo. Los puestos generan habitantes con rutinas, conocimiento y relaciones. Los eventos emergen del estado de estructuras, recursos, facciones y personas.

```text
SETTLEMENT
  -> GEOGRAPHY / RESOURCES / ROUTES / DANGERS
  -> FACTION CONTROL
  -> BUILDING REQUIREMENTS
  -> BUILDING INSTANCES
  -> ROOM GRAPH
  -> JOB SLOTS
  -> NPC / HOUSEHOLDS / ROUTINES
  -> EVENTS / ECONOMY / CONSEQUENCES
  -> PERSISTENT WORLD STATE
```

> **Una taberna no aparece porque la narración la necesitó. Existe porque el asentamiento generó una instancia de Taberna, esa instancia ocupa una posición del mapa, contiene Rooms, tiene propietario, Jobs, inventario, horario y estado.**


# 1. Reglas que se congelan como base del sistema

1. La unidad mínima de navegación es la ROOM. Toda acción espacial se resuelve desde la Room actual.

2. El mapa físico no pertenece al LLM. Es una base de datos persistente que el LLM sólo puede consultar y describir.

3. Un asentamiento se genera desde condiciones objetivas antes de generar NPC.

4. Los edificios generan puestos de trabajo; los puestos ocupados generan NPC y rutinas.

5. Los interiores se modelan como subgrafos de Rooms. Un edificio puede ser un nodo en el mapa urbano y, al entrar, abrir su propia Zone interior.

6. Los cinco sentidos son acciones de percepción. La tirada de Percepción aparece cuando el jugador intenta obtener información sensorial cuyo resultado es incierto o relevante.

7. La descripción base de una Room no revela automáticamente toda la información sensorial disponible.

8. El estado objetivo del mundo, el conocimiento del jugador y el conocimiento de cada NPC son capas diferentes.

9. Una estructura puede existir cerrada, dañada, capturada, sin personal o sin cuota; su presencia física no garantiza que funcione.

10. La IA narra resultados ya autorizados por los sistemas. No crea Exits, edificios, NPC, objetos o hechos ocultos por conveniencia narrativa.


# 2. Jerarquía espacial del mundo

El World Book ya define a Caribia como una matrioska de contexto: provincia, región, isla, asentamiento, estructura, interior y objeto. Para el MUD, esa jerarquía se formaliza y se añade ROOM como unidad de navegación explícita.

```text
WORLD: RIVARICA
└── PROVINCE
    └── REGION
        └── ISLAND / TERRITORIAL FEATURE
            └── SETTLEMENT
                └── DISTRICT / ZONE
                    └── STRUCTURE INSTANCE
                        └── INTERIOR ZONE
                            └── ROOM
                                ├── EXITS
                                ├── OBJECTS
                                ├── NPC PRESENCE
                                └── LOCAL STATE
```

Cada nivel hereda contexto. La provincia aporta leyes, moneda y física general; la región aporta recursos, arquitectura y cultura; la isla aporta rutas y peligros; el asentamiento aporta población, economía y equilibrio de facciones; la estructura aporta funciones, Jobs y seguridad; la Room aporta geometría local, acceso y percepción; el objeto aporta interacciones concretas.


## 2.1 Zones y subzonas

Una Zone agrupa Rooms que comparten contexto espacial. El mapa de una ciudad puede representar un edificio como un solo nodo de entrada; al cruzarlo se carga la Zone interior del edificio. Los pisos, sótanos, torres y cámaras restringidas siguen siendo Rooms normales conectadas mediante Exits verticales o especiales.

```text
[MAPA URBANO]
PLAZA -- PESCADERÍA -- MUELLE
             |
          ENTER
             v
[PESCADERÍA / ZONE INTERIOR]
MOSTRADOR -- CORTE -- CÁMARA FRÍA
    |                    |
CALLEJÓN <--- PATIO DE CARGA
```


# 3. Perfil estructural de un asentamiento

El asentamiento es el seed principal del generador. No almacena primero “lugares cool”; almacena condiciones que explican por qué esos lugares existen. Con ocho grupos de datos puede producirse la primera capa física del pueblo o ciudad.

| Campo | Función sistémica | Ejemplos de valores |
| --- | --- | --- |
| Identidad | ID, nombre canónico, región, tipo y coordenadas de atlas. | SET-ORV-014; región Orvena; pueblo. |
| Población | Determina escala mínima de infraestructura, densidad y demanda. | 3.240 habitantes. |
| Geografía / quirks | Modifica qué infraestructura es posible, necesaria o eficiente. | Costera; alta; minera; acantilado; canal; niebla fuerte. |
| Recursos | Determina cadenas económicas y especializaciones. | Pesca alta; azurita media; agua baja. |
| Rutas | Determina acceso, comercio, correo, migración y respuesta de facciones. | Aerobarco regional; puerto local; camino interno. |
| Peligros | Incrementa requisitos de defensa, refugio, salud o contención. | Niebla, tormenta, piratería, contaminación. |
| Control de facciones | Determina instituciones, seguridad, cultura operativa y conflictos. | Windrago 35%; Advenidos 45%; Eclesia 8%; Ladrones 12%. |
| Estructuras especiales | Fija lugares únicos que no pueden aparecer por azar. | Fortaleza, basílica, faro singular, ruina, mina histórica. |

## 3.1 Escala de población

Se conserva la escala ya establecida en el World Book. La población no es sólo decoración: fija una obligación mínima de infraestructura y complejidad social.

| Tipo | Población habitual | Mínimo estructural |
| --- | --- | --- |
| Estación | 20–150 | Refugio, reserva, señal y Job principal. |
| Aldea | 150–900 | Plaza, agua, alimento, taller y autoridad. |
| Pueblo | 900–5.000 | Cabildo, mercado, salud, seguridad, escuela y ruta. |
| Villa | 5.000–25.000 | Servicios especializados, gremios y nodos regionales. |
| Ciudad | 25.000–150.000 | Redes completas, distritos y estructuras avanzadas. |
| Metrópoli regional | >150.000 | Múltiples centros superpuestos y gobierno de escala provincial. |

# 4. Quirks geográficos como reglas, no como adjetivos

Los quirks se almacenan como tags funcionales. Cada tag aplica modificadores a la selección de estructuras, costes, rutas, producción, riesgos y posibles eventos. Una descripción narrativa puede derivarse después de esos tags, pero el generador necesita primero consecuencias mecánicas.

| Quirk | Efecto sobre el generador | Estructuras/Jobs favorecidos |
| --- | --- | --- |
| COASTAL | Prioriza acceso marítimo, pesca, almacenamiento de captura y exposición climática. | Muelle, pescadería, cámara fría, astillero; pescadores, cargadores. |
| DEEP_WATER_PORT | Permite naves mayores y comercio regional. | Puerto de enlace, aduana, almacenes, capitanía. |
| HIGH_ALTITUDE | Reduce acceso de superficie y aumenta transporte vertical/aéreo. | Ascensor, aeromuelle, puentes; operadores y mantenimiento. |
| CLIFFSIDE | Introduce niveles, escaleras, elevadores y riesgos de caída/cierre. | Pasarelas, torres, plataformas, rescate. |
| MINING_NEARBY | Añade flujo mineral, trabajadores especializados y seguridad de carga. | Cargadero, refinado, taller, almacén, puesto de control. |
| DEEP_MINE | Incrementa peligros, salud industrial y logística pesada. | Casa de Campanas, enfermería, rescate, depósitos. |
| FISHING_GROUNDS | Aumenta subsistencia, mercado de captura y procesamiento. | Muelle pesquero, pescaderías, salado, redes. |
| FRESH_WATER_RICH | Reduce presión sobre cisternas y favorece población/agricultura. | Fuentes, lavaderos, cultivos. |
| FRESH_WATER_POOR | Vuelve crítica la infraestructura hídrica. | Cisternas, Casa de Bombas, reservas, racionamiento. |
| HEAVY_FOG | Eleva necesidad de refugio, señal, protocolos y eventos de Niebla. | Faros, refugios, Darkhaven cuando corresponda, guías. |
| STORM_EXPOSED | Aumenta mantenimiento y redundancia de rutas/energía. | Refugios, anclajes, reparación, lectura de tormenta. |
| TRADE_ROUTE | Aumenta comercio, hospedaje, información y crimen oportunista. | Mercado, taberna, almacenes, posta, casas de cambio. |
| AEROSHIP_ROUTE | Introduce pasajeros, carga aérea y ventanas de salida. | Aeromuelle, capitanía, correo, estibadores. |
| ISOLATED | Reduce especialización disponible y aumenta autosuficiencia. | Reservas, taller generalista, refugio, multi-Job. |
| AGRICULTURAL | Crea cadena de alimento terrestre. | Almacenes, mercados, molinos/transformación local. |
| INDUSTRIAL | Aumenta cuota energética, talleres, contaminación y demanda laboral. | Talleres, astillero, reserva energética, seguridad industrial. |
| CANAL_CITY | Convierte agua/canales en Exits de transporte y condiciona barrios. | Muelles menores, puentes, barqueros, mantenimiento. |

## 4.1 Combinación de quirks
