# SIZA — Caribia: Mapa Maestro Provincial MUD v0.1

**Tipo:** atlas operativo / mapa maestro de juego  
**Base:** World Book de Rivarica + `data/geography/caribia/atlas.json`  
**Estado:** canon extraído + derivaciones + propuestas explícitamente marcadas

## 1. Función

Este documento convierte el atlas canónico de Caribia en la **primera capa operativa del grafo MUD**. No baja todavía a todas las calles y Rooms; fija la topología provincial que esas capas deben respetar.

## 2. Escala provincial

- Arco territorial: aproximadamente **540 km este-oeste × 360 km norte-sur**.
- Tierra aprovechable: aproximadamente **23.000 km²**.
- Medio: islas flotantes sobre un **océano físico de agua salada**, con Nieblamar superpuesta.
- Regiones físicas: **6**.
- Población regional oficial documentada: **1.080.000**.
- Población de los **49 asentamientos nombrados** en `atlas.json`: **739.300**.
- Población regional no individualizada en esos 49 nodos: **340.700**.

Esa diferencia no es un error. El atlas establece que parte de la población vive en aldeas menores, fincas, barcos habitados, estaciones y tejido rural que no necesita nombre canónico antes de una campaña.

## 3. Regiones

| Región | Área | Población oficial | En nodos nombrados | Población abstracta | Carácter físico | Función | Quirks base |
|---|---:|---:|---:|---:|---|---|---|
| Kalnaj | 4.900 km² | 230.000 | 175.800 | 54.200 | mesetas oscuras, escarpas y fondos mineralizados | gobierno, defensa, refinado y minería acuática | `HIGH_PLATEAU, ESCARPMENT, AQUATIC_MINING, INDUSTRIAL, MILITARY, VERTICAL_INFRASTRUCTURE` |
| Vardena | 6.200 km² | 305.000 | 135.500 | 169.500 | islas altas, suelos profundos, lagos y bosques húmedos | agua, agricultura, madera y alimentos | `HIGH_ISLANDS, FRESHWATER_RICH, AGRICULTURAL, FORESTED, IRRIGATION_NETWORK` |
| Sereva | 3.100 km² | 275.000 | 237.000 | 38.000 | canales centrales, bahías protegidas y alturas medias | comercio, correos, seguros y transbordo | `CENTRAL_CHANNELS, PROTECTED_BAYS, COMMERCIAL_HUB, TRANSIT_HUB, VERTICAL_PORT` |
| Orvena | 2.700 km² | 135.000 | 89.200 | 45.800 | archipiélagos bajos, esteros, arrecifes y aguas cálidas | pesca, conservación, acuicultura y cocina | `LOW_ARCHIPELAGO, WARM_WATERS, FISHING_GROUNDS, AQUACULTURE, FOOD_PRESERVATION` |
| Ragmar | 1.850 km² | 92.000 | 74.500 | 17.500 | islas ventosas, pasos estrechos y costas de tormenta | corso, pilotaje, reparación y frontera móvil | `WIND_EXPOSED, STORM_COAST, FRONTIER, CORSAIR_NETWORK, REPAIR_HUB` |
| Cadena de las Agujas | 1.250 km² | 43.000 | 27.300 | 15.700 | peñones occidentales y corredores de niebla | faros, vigilancia, refugio y acceso exterior | `ROCK_SPIRES, HEAVY_FOG, LIGHTHOUSE_NETWORK, EDGE_FRONTIER, ISOLATED_REFUGES` |

## 4. Accidentes físicos mayores canónicos

- **Macizo de Kalnaj** — montaña — atlas (38,32).
- **Cuencas de Vardena** — cuenca — atlas (60,31).
- **Escarpas de Sereva** — acantilado — atlas (70,52).
- **Bancos de Orvena** — mar/corriente — atlas (57,75).
- **Costa de Tormentas** — costa — atlas (24,62).
- **Borde de Nieblamar** — niebla — atlas (8,50).
- **Mar Interior** — mar — atlas (50,58).
- **Gran Océano de Niebla** — mar — atlas (1,58).

## 5. Red troncal canónica

- **Kalnaj ↔ Muelle Hondo** — elevador, funicular y canal bajo — **0,8 h**.
- **Kalnaj ↔ Vardena Alta** — aerobarco y camino alto — **3,5 h**.
- **Kalnaj ↔ Puerto Sereva** — aerobarco regional — **2,3 h**.
- **Vardena Alta ↔ Puerto Sereva** — camino de terraza y transporte de carga — **2,2 h**.
- **Puerto Sereva ↔ Bajorvena** — navío costero — **2,8 h**.
- **Puerto Sereva ↔ Ragmar del Este** — aerobarco — **3 h**.
- **Ragmar del Este ↔ Punta Ocaso** — camino costero protegido — **1,5 h**.
- **Punta Ocaso ↔ Primera Luz** — navío o aerobarco ligero — **1,2 h**.
- **Primera Luz ↔ Aguja Media** — barco de relevo — **1 h**.
- **Aguja Media ↔ Última Aguja** — barco de relevo — **2,5 h**.

Estas rutas son el esqueleto interregional. Los cierres por tormenta, Nieblamar, aduana, accidente o prioridad militar pertenecen a `WORLD_STATE`.

## 6. Asentamientos canónicos por región

### Kalnaj

**Población regional oficial:** 230.000. **En nodos nombrados:** 175.800. **Abstracta/no nombrada:** 54.200.

**Quirks regionales heredables:** `HIGH_PLATEAU, ESCARPMENT, AQUATIC_MINING, INDUSTRIAL, MILITARY, VERTICAL_INFRASTRUCTURE`.

| Asentamiento | Tipo | Población | Atlas | Funciones/estructuras canónicas | Quirks específicos derivados | Líder | Control faccional |
|---|---|---:|---|---|---|---|---|
| **Kalnaj** | ciudad | 121.000 | (37,47) | Fortaleza Kalnaj; mercado central; distrito de talleres; dársenas mineras; Casa de Remedio mayor; puestos Darkhaven; cargaderos industriales | `DARKHAVEN`, `PORT`, `INDUSTRIAL`, `HEALTHCARE` | PENDIENTE | PENDIENTE |
| **Escarpa Azul** | villa minera | 18.600 | (31,42) | elevadores de mina; barracones; talleres de núcleo; enfermería minera; mercado de turno | `MINING`, `VERTICAL`, `INDUSTRIAL`, `HEALTHCARE` | PENDIENTE | PENDIENTE |
| **Cuenca Roca** | pueblo | 9.200 | (42,40) | depósitos de agua; talleres; mercado de abastos; Casa de Remedio; escuela técnica básica | `WATER_INFRASTRUCTURE`, `INDUSTRIAL`, `EDUCATION`, `HEALTHCARE` | PENDIENTE | PENDIENTE |
| **Muelle Hondo** | puerto | 14.300 | (31,52) | muelles de mineral; aduana; grúas cristalinas; almacenes; cargadero naval | `MINING`, `PORT`, `CUSTOMS`, `INDUSTRIAL` | PENDIENTE | PENDIENTE |
| **Vigía Kal** | pueblo faro | 6.100 | (28,57) | faro secundario; puesto Darkhaven; muelle de rescate; tabernas de tripulación; depósito de emergencia | `LIGHTHOUSE`, `DARKHAVEN`, `PORT`, `EMERGENCY` | PENDIENTE | PENDIENTE |
| **Loma de Hierro** | aldea/pueblo menor | 2.600 | (39,54) | mercado o tienda local; agua y refugio; conexión con el centro regional | `WATER_INFRASTRUCTURE`, `EMERGENCY` | PENDIENTE | PENDIENTE |
| **Pozo Siete** | aldea/pueblo menor | 1.800 | (34,37) | mercado o tienda local; agua y refugio; conexión con el centro regional | `WATER_INFRASTRUCTURE`, `EMERGENCY` | PENDIENTE | PENDIENTE |
| **Cantera Sur** | aldea/pueblo menor | 2.200 | (45,52) | mercado o tienda local; agua y refugio; conexión con el centro regional | `MINING`, `WATER_INFRASTRUCTURE`, `EMERGENCY` | PENDIENTE | PENDIENTE |

### Vardena

**Población regional oficial:** 305.000. **En nodos nombrados:** 135.500. **Abstracta/no nombrada:** 169.500.

**Quirks regionales heredables:** `HIGH_ISLANDS, FRESHWATER_RICH, AGRICULTURAL, FORESTED, IRRIGATION_NETWORK`.

| Asentamiento | Tipo | Población | Atlas | Funciones/estructuras canónicas | Quirks específicos derivados | Líder | Control faccional |
|---|---|---:|---|---|---|---|---|
| **Vardena Alta** | ciudad | 86.000 | (57,33) | mercado agrícola mayorista; estación de carga; talleres de bombas; Casa de Remedio; escuelas; administración de riego | `WATER_INFRASTRUCTURE`, `AGRICULTURAL`, `INDUSTRIAL`, `EDUCATION`, `HEALTHCARE` | PENDIENTE | PENDIENTE |
| **Río Claro** | villa | 12.600 | (49,28) | canales de riego; molinos mecánicos; mercado semanal; Casa de Remedio | `WATER_INFRASTRUCTURE`, `INDUSTRIAL`, `HEALTHCARE` | PENDIENTE | PENDIENTE |
| **Tres Puentes** | pueblo | 7.800 | (63,29) | cruce de caminos; posadas; taller de carros; mercado ganadero pendiente de especies | `INDUSTRIAL` | PENDIENTE | PENDIENTE |
| **Ladera Norte** | pueblo | 5.200 | (61,39) | terrazas agrícolas; cargadero comunal; escuela; capilla Advenida | `AGRICULTURAL`, `INDUSTRIAL`, `RELIGIOUS`, `EDUCATION` | PENDIENTE | PENDIENTE |
| **Santero de Agua** | villa | 9.700 | (50,41) | reservorios; guardafuentes; mercado de herramientas; Casa de Remedio | `WATER_INFRASTRUCTURE`, `HEALTHCARE` | PENDIENTE | PENDIENTE |
| **Corte Verde** | pueblo | 4.400 | (68,36) | aserraderos; viveros; depósitos; brigada de incendio rural | `AGRICULTURAL`, `FORESTRY`, `EMERGENCY` | PENDIENTE | PENDIENTE |
| **Las Acequias** | aldea/pueblo menor | 3.100 | (54,25) | mercado o tienda local; agua y refugio; conexión con el centro regional | `WATER_INFRASTRUCTURE`, `EMERGENCY` | PENDIENTE | PENDIENTE |
| **Paso Largo** | aldea/pueblo menor | 2.100 | (66,43) | mercado o tienda local; agua y refugio; conexión con el centro regional | `WATER_INFRASTRUCTURE`, `EMERGENCY` | PENDIENTE | PENDIENTE |
| **Cauce Viejo** | aldea/pueblo menor | 1.700 | (47,35) | mercado o tienda local; agua y refugio; conexión con el centro regional | `WATER_INFRASTRUCTURE`, `EMERGENCY` | PENDIENTE | PENDIENTE |
| **Mesa Verde** | aldea/pueblo menor | 2.900 | (59,25) | mercado o tienda local; agua y refugio; conexión con el centro regional | `WATER_INFRASTRUCTURE`, `EMERGENCY` | PENDIENTE | PENDIENTE |

### Sereva

**Población regional oficial:** 275.000. **En nodos nombrados:** 237.000. **Abstracta/no nombrada:** 38.000.

**Quirks regionales heredables:** `CENTRAL_CHANNELS, PROTECTED_BAYS, COMMERCIAL_HUB, TRANSIT_HUB, VERTICAL_PORT`.

| Asentamiento | Tipo | Población | Atlas | Funciones/estructuras canónicas | Quirks específicos derivados | Líder | Control faccional |
|---|---|---:|---|---|---|---|---|
| **Puerto Sereva** | ciudad mayor | 178.000 | (60,60) | puerto mayor; casas de cambio; bancos manarales; astilleros; mercados refrigerados; Darkhaven; Casas de Remedio; barrios de talleres | `DARKHAVEN`, `PORT`, `COLD_CHAIN`, `INDUSTRIAL`, `FINANCIAL` | PENDIENTE | PENDIENTE |
| **Terrazas de Sereva** | ciudad satélite | 24.100 | (63,54) | vivienda obrera; ascensores; cargaderos de barrio; mercados; lavaderos mecánicos | `VERTICAL`, `INDUSTRIAL` | PENDIENTE | PENDIENTE |
| **Dársena Vieja** | pueblo portuario | 11.200 | (54,63) | muelles antiguos; mercado de usados; casas de empeño; talleres navales | `PORT`, `CLANDESTINE_TRADE`, `INDUSTRIAL` | PENDIENTE | PENDIENTE |
| **Paso del Viento** | villa | 8.300 | (68,61) | estación de aerobarcos; posadas; aduana interior; cargadero regional | `CUSTOMS`, `AIR_ROUTE`, `INDUSTRIAL` | PENDIENTE | PENDIENTE |
| **Las Gradas** | pueblo | 6.900 | (57,53) | ascensores de acantilado; mercado de tránsito; talleres de poleas; guardia | `VERTICAL`, `INDUSTRIAL` | PENDIENTE | PENDIENTE |
| **Muelle Chico** | aldea/pueblo menor | 2.800 | (53,58) | mercado o tienda local; agua y refugio; conexión con el centro regional | `PORT`, `WATER_INFRASTRUCTURE`, `EMERGENCY` | PENDIENTE | PENDIENTE |
| **Barranca** | aldea/pueblo menor | 3.300 | (65,66) | mercado o tienda local; agua y refugio; conexión con el centro regional | `WATER_INFRASTRUCTURE`, `EMERGENCY` | PENDIENTE | PENDIENTE |
| **Puerto Seco** | aldea/pueblo menor | 2.400 | (67,56) | mercado o tienda local; agua y refugio; conexión con el centro regional | `WATER_INFRASTRUCTURE`, `EMERGENCY` | PENDIENTE | PENDIENTE |

### Orvena

**Población regional oficial:** 135.000. **En nodos nombrados:** 89.200. **Abstracta/no nombrada:** 45.800.

**Quirks regionales heredables:** `LOW_ARCHIPELAGO, WARM_WATERS, FISHING_GROUNDS, AQUACULTURE, FOOD_PRESERVATION`.

| Asentamiento | Tipo | Población | Atlas | Funciones/estructuras canónicas | Quirks específicos derivados | Líder | Control faccional |
|---|---|---:|---|---|---|---|---|
| **Bajorvena** | ciudad | 52.000 | (46,73) | lonja de pescado; depósitos fríos; astilleros pequeños; Casa de Remedio; mercado de manafauna | `PORT`, `FISHING`, `COLD_CHAIN`, `INDUSTRIAL`, `HEALTHCARE` | PENDIENTE | PENDIENTE |
| **Punta Clara** | villa pesquera | 10.500 | (51,78) | muelles de pesca; secaderos; reparación de redes; cargadero pequeño | `PORT`, `FISHING`, `INDUSTRIAL` | PENDIENTE | PENDIENTE |
| **Las Redes** | pueblo | 6.400 | (40,77) | cooperativas pesqueras; mercado; Casa de Remedio; escuela de navegación | `FISHING`, `EDUCATION`, `HEALTHCARE` | PENDIENTE | PENDIENTE |
| **Marea Baja** | pueblo | 4.700 | (42,67) | marismas; salinas/producción de conservación pendiente; talleres de bombas; muelle | `PORT`, `WATER_INFRASTRUCTURE`, `INDUSTRIAL` | PENDIENTE | PENDIENTE |
| **Puerto Frío** | villa | 8.900 | (51,69) | cámaras frías; subastas; almacenes; transportistas | `PORT`, `COLD_CHAIN` | PENDIENTE | PENDIENTE |
| **Caleta Sur** | aldea/pueblo menor | 2.200 | (48,81) | mercado o tienda local; agua y refugio; conexión con el centro regional | `WATER_INFRASTRUCTURE`, `EMERGENCY` | PENDIENTE | PENDIENTE |
| **Piedra de Red** | aldea/pueblo menor | 1.900 | (37,73) | mercado o tienda local; agua y refugio; conexión con el centro regional | `FISHING`, `WATER_INFRASTRUCTURE`, `EMERGENCY` | PENDIENTE | PENDIENTE |
| **Las Boyas** | aldea/pueblo menor | 2.600 | (55,75) | mercado o tienda local; agua y refugio; conexión con el centro regional | `WATER_INFRASTRUCTURE`, `EMERGENCY` | PENDIENTE | PENDIENTE |

### Ragmar

**Población regional oficial:** 92.000. **En nodos nombrados:** 74.500. **Abstracta/no nombrada:** 17.500.

**Quirks regionales heredables:** `WIND_EXPOSED, STORM_COAST, FRONTIER, CORSAIR_NETWORK, REPAIR_HUB`.

| Asentamiento | Tipo | Población | Atlas | Funciones/estructuras canónicas | Quirks específicos derivados | Líder | Control faccional |
|---|---|---:|---|---|---|---|---|
| **Ragmar del Este** | ciudad | 38.000 | (27,68) | puerto de frontera; mercado corsario legal; aduana; astilleros; Darkhaven; Casa de Remedio | `DARKHAVEN`, `PORT`, `CUSTOMS`, `CLANDESTINE_TRADE`, `HEALTHCARE` | PENDIENTE | PENDIENTE |
| **Punta Ocaso** | villa | 17.500 | (19,63) | último gran puerto occidental; depósitos; faro mayor; puesto Darkhaven; cargadero naval | `LIGHTHOUSE`, `DARKHAVEN`, `PORT`, `INDUSTRIAL` | PENDIENTE | PENDIENTE |
| **Quebrada de Sal** | pueblo | 7.200 | (24,75) | pesca; talleres de casco; mercado negro disperso; Casa de Remedio | `FISHING`, `CLANDESTINE_TRADE`, `INDUSTRIAL`, `HEALTHCARE` | PENDIENTE | PENDIENTE |
| **Mástil Rojo** | pueblo | 5.600 | (32,75) | astilleros; tabernas; reclutamiento de tripulaciones; almacenes | `PORT`, `INDUSTRIAL` | PENDIENTE | PENDIENTE |
| **Risco Bajo** | aldea/pueblo menor | 2.400 | (22,70) | mercado o tienda local; agua y refugio; conexión con el centro regional | `WATER_INFRASTRUCTURE`, `EMERGENCY` | PENDIENTE | PENDIENTE |
| **Caleta Negra** | aldea/pueblo menor | 1.700 | (29,79) | mercado o tienda local; agua y refugio; conexión con el centro regional | `WATER_INFRASTRUCTURE`, `EMERGENCY` | PENDIENTE | PENDIENTE |
| **Paso Corsario** | aldea/pueblo menor | 2.100 | (18,69) | mercado o tienda local; agua y refugio; conexión con el centro regional | `CLANDESTINE_TRADE`, `WATER_INFRASTRUCTURE`, `EMERGENCY` | PENDIENTE | PENDIENTE |

### Cadena de las Agujas

**Población regional oficial:** 43.000. **En nodos nombrados:** 27.300. **Abstracta/no nombrada:** 15.700.

**Quirks regionales heredables:** `ROCK_SPIRES, HEAVY_FOG, LIGHTHOUSE_NETWORK, EDGE_FRONTIER, ISOLATED_REFUGES`.

| Asentamiento | Tipo | Población | Atlas | Funciones/estructuras canónicas | Quirks específicos derivados | Líder | Control faccional |
|---|---|---:|---|---|---|---|---|
| **Primera Luz** | pueblo faro | 7.800 | (16,59) | faro estratégico; puesto Darkhaven; Casa de Remedio; muelle de evacuación; depósito energético | `LIGHTHOUSE`, `DARKHAVEN`, `PORT`, `EMERGENCY`, `HEALTHCARE` | PENDIENTE | PENDIENTE |
| **Aguja Media** | pueblo faro | 5.100 | (12,55) | faro; mercado pequeño; taller técnico; refugios; puesto Darkhaven | `LIGHTHOUSE`, `DARKHAVEN`, `INDUSTRIAL`, `EMERGENCY` | PENDIENTE | PENDIENTE |
| **Puerto Niebla** | pueblo | 4.300 | (10,62) | muelle; rescate marítimo; Casa de Remedio; almacenes; taberna | `PORT`, `EMERGENCY`, `HEALTHCARE` | PENDIENTE | PENDIENTE |
| **Última Aguja** | pueblo faro | 2.600 | (4,53) | faro de borde; puesto Darkhaven reducido; depósito de emergencia; muelle estrecho; refugio | `LIGHTHOUSE`, `DARKHAVEN`, `PORT`, `EMERGENCY` | PENDIENTE | PENDIENTE |
| **Segunda Luz** | aldea/pueblo menor | 3.200 | (14,51) | mercado o tienda local; agua y refugio; conexión con el centro regional | `WATER_INFRASTRUCTURE`, `EMERGENCY` | PENDIENTE | PENDIENTE |
| **Aguja de Sal** | aldea/pueblo menor | 1.900 | (9,49) | mercado o tienda local; agua y refugio; conexión con el centro regional | `WATER_INFRASTRUCTURE`, `EMERGENCY` | PENDIENTE | PENDIENTE |
| **Punta Hueca** | aldea/pueblo menor | 1.500 | (5,60) | mercado o tienda local; agua y refugio; conexión con el centro regional | `WATER_INFRASTRUCTURE`, `EMERGENCY` | PENDIENTE | PENDIENTE |
| **Islas Tortus** | sector insular sagrado | 900 | (3,64) | pequeño conjunto de islas con silueta de tortuga; Basílica de Sait Voltaire; muelle/plataforma de aerobarcos; hospedería religiosa; refugio de peregrinos | `PORT`, `AIR_ROUTE`, `RELIGIOUS`, `EMERGENCY` | PENDIENTE | PENDIENTE |

## 7. Distritos canónicos ya disponibles

### Kalnaj

- **Meseta de la Corona** — gobierno, Fortaleza Windrago, Consejo y residencias de Casa.
- **Escarpa de Caldera** — talleres Caldamar, fundiciones, ascensores y vivienda de turno.
- **Dársenas de Campana** — Bajovento, Mutual, descenso, mineral húmedo y espera familiar.
- **Cuenca Oriental** — hogares, huertos, escuelas, cisternas y mercados de barrio.
- **Muelle de Mineral** — aduana acuática, grúas, depósitos y navíos de superficie.
- **Patio de Tres Aguas** — archivo Hidraazul, clínica, mediación y registros de sucesión.
- **Costa de Guardia** — hangares, torres, entrenamiento y refugio Windrago.

### Puerto Sereva

- **Dársena Mayor** — aduana, lonjas, grúas, almacenes y trabajo portuario.
- **Bajos del Puerto** — vivienda densa, talleres, tabernas y casas de contraseña.
- **Cinturón de Mercado** — puestos, canales, cargaderos y mezcla de clases.
- **Terrazas Altas** — bancos, seguros, residencias y Guante Azul.
- **Astilleros** — diques, Caldamar, carpintería naval y núcleos de barco.
- **Mercado Frío** — subastas, cámaras, cocinas y transporte alimentario.
- **Barrio de Postas** — Velacendra, aerobarcos, correo y hospedaje de tránsito.
- **Patio del Alba** — parroquia Soledeo, refectorio Carmesí y peregrinos urbanos.

### Vardena Alta

- **Mercado Alto** — cosecha mayorista, posadas y contratos rurales.
- **Canales** — reservorios, bombas, guardafuentes y política de agua.
- **Barrio de Oficios** — molinos, carpintería, herrería y conservación.
- **Camino de Sereva** — posta, aduana interior, carga y vivienda de viajeros.
- **Jardines de Lluvia** — viveros, clínicas, residencias y escuelas.

### Bajorvena

- **Lonja** — subasta, clasificación, pescaderías y gremios.
- **Frigoríficos** — hielo manaral, almacenes y riesgo de cuota.
- **Barrio de Redes** — hogares, reparación, tabernas y Casas de Remedio.
- **Muelle Sur** — flota, rescate, astilleros pequeños y mercado de amanecer.

### Ragmar del Este

- **Puerto de Frontera** — aduana, muelles, cargadero y depósitos.
- **Barrio de Tripulaciones** — pensiones, reclutamiento, memoria y vida nocturna.
- **Mercado de Presas** — subasta corsaria, tasadores, guardia y litigios.
- **Camino de Ocaso** — caravanas, aerobarcos y talleres de ruta.

Los demás asentamientos todavía no poseen distritos canónicos nombrados. Su división espacial debe generarse en la pasada regional y quedar marcada `PROPUESTA` hasta aprobación.

## 8. Red local provisional para que ningún nodo quede aislado

**Estado: PROPUESTA DE DISEÑO.** Estas conexiones se derivan de proximidad gráfica en las coordenadas del atlas. Sirven para construir el primer grafo navegable, pero **no fijan modo ni tiempo de viaje** y deben revisarse con la geografía regional antes de pasar a canon.

### Kalnaj

- `Kalnaj` ↔ `Loma de Hierro` — separación geométrica estimada en el marco del atlas: **27,4 km equivalentes**.
- `Loma de Hierro` ↔ `Cantera Sur` — **33,2 km equivalentes**.
- `Kalnaj` ↔ `Cuenca Roca` — **36,9 km equivalentes**.
- `Kalnaj` ↔ `Escarpa Azul` — **37,1 km equivalentes**.
- `Escarpa Azul` ↔ `Pozo Siete` — **24,2 km equivalentes**.
- `Escarpa Azul` ↔ `Muelle Hondo` — **36,0 km equivalentes**.
- `Muelle Hondo` ↔ `Vigía Kal` — **24,2 km equivalentes**.

### Vardena

- `Vardena Alta` ↔ `Ladera Norte` — **30,5 km equivalentes**.
- `Ladera Norte` ↔ `Paso Largo` — **30,6 km equivalentes**.
- `Paso Largo` ↔ `Corte Verde` — **27,4 km equivalentes**.
- `Vardena Alta` ↔ `Mesa Verde` — **30,8 km equivalentes**.
- `Mesa Verde` ↔ `Tres Puentes` — **26,0 km equivalentes**.
- `Mesa Verde` ↔ `Las Acequias` — **27,0 km equivalentes**.
- `Las Acequias` ↔ `Río Claro` — **29,1 km equivalentes**.
- `Río Claro` ↔ `Cauce Viejo` — **27,4 km equivalentes**.
- `Cauce Viejo` ↔ `Santero de Agua` — **27,0 km equivalentes**.

### Sereva

- `Puerto Sereva` ↔ `Terrazas de Sereva` — **27,0 km equivalentes**.
- `Terrazas de Sereva` ↔ `Puerto Seco` — **22,8 km equivalentes**.
- `Puerto Seco` ↔ `Paso del Viento` — **18,8 km equivalentes**.
- `Paso del Viento` ↔ `Barranca` — **24,2 km equivalentes**.
- `Puerto Sereva` ↔ `Las Gradas` — **30,0 km equivalentes**.
- `Las Gradas` ↔ `Muelle Chico` — **28,1 km equivalentes**.
- `Muelle Chico` ↔ `Dársena Vieja` — **18,8 km equivalentes**.

### Orvena

- `Bajorvena` ↔ `Marea Baja` — **30,5 km equivalentes**.
- `Bajorvena` ↔ `Puerto Frío` — **30,6 km equivalentes**.
- `Puerto Frío` ↔ `Las Boyas` — **30,5 km equivalentes**.
- `Las Boyas` ↔ `Punta Clara` — **24,1 km equivalentes**.
- `Punta Clara` ↔ `Caleta Sur` — **19,5 km equivalentes**.
- `Marea Baja` ↔ `Piedra de Red` — **34,6 km equivalentes**.
- `Piedra de Red` ↔ `Las Redes` — **21,7 km equivalentes**.

### Ragmar

- `Ragmar del Este` ↔ `Risco Bajo` — **27,9 km equivalentes**.
- `Risco Bajo` ↔ `Quebrada de Sal` — **21,0 km equivalentes**.
- `Risco Bajo` ↔ `Paso Corsario` — **21,9 km equivalentes**.
- `Paso Corsario` ↔ `Punta Ocaso` — **22,3 km equivalentes**.
- `Quebrada de Sal` ↔ `Caleta Negra` — **30,6 km equivalentes**.
- `Caleta Negra` ↔ `Mástil Rojo` — **21,7 km equivalentes**.

### Cadena de las Agujas

- `Primera Luz` ↔ `Aguja Media` — **26,0 km equivalentes**.
- `Aguja Media` ↔ `Segunda Luz` — **18,0 km equivalentes**.
- `Aguja Media` ↔ `Aguja de Sal` — **27,0 km equivalentes**.
- `Aguja Media` ↔ `Puerto Niebla` — **27,4 km equivalentes**.
- `Puerto Niebla` ↔ `Punta Hueca` — **27,9 km equivalentes**.
- `Punta Hueca` ↔ `Islas Tortus` — **18,0 km equivalentes**.
- `Punta Hueca` ↔ `Última Aguja` — **25,8 km equivalentes**.

## 9. Nodos que requieren tratamiento especial

- **Islas Tortus:** sector insular sagrado con Basílica de Sait Voltaire; no debe generarse como pueblo común.
- **Cadena de las Agujas:** cada faro forma parte de una red redundante; perder un nodo modifica rutas y reservas.
- **Kalnaj:** la ciudad no es la región; su mapa urbano debe respetar meseta, escarpa, cuenca y dársenas.
- **Puerto Sereva:** puerto oceánico y aéreo superpuesto; el coste espacial de la altura es parte de su diseño.
- **Orvena:** la cadena de frío y el movimiento de captura son infraestructura espacial, no sólo economía.
- **Ragmar:** frontera móvil y rutas de tormenta; refugios y depósitos pueden ser mayores de lo que justificaría la población diaria.

## 10. Campos todavía sin canon suficiente

Para completar el mapa de juego faltan, asentamiento por asentamiento:

- líder local concreto;
- porcentajes WINDRAGO / ADVENIDOS / ECLESIA / LADRONES;
- distritos de los asentamientos que aún no los tienen;
- número e instancia de estructuras comunes;
- estructuras faccionales por Tier;
- conexiones locales aprobadas y su modo;
- tiempos de viaje locales;
- mapa de Rooms de cada distrito/edificio;
- capas sensoriales y objetos persistentes.

Estos vacíos no deben ser rellenados por Qwen durante una partida. Hasta que existan, el sistema debe tratarlos como datos de diseño pendientes.

## 11. Próxima bajada de escala

Los documentos regionales convierten cada una de las seis regiones en un grafo intermedio. Después se baja a asentamientos, distritos, estructuras y Rooms.