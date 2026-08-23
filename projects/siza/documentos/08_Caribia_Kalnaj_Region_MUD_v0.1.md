# SIZA — Caribia / Kalnaj: Mapa MUD v0.1

**Tipo:** atlas operativo regional  
**Estado:** canon extraído + propuestas topológicas marcadas  
**Región:** Kalnaj

## 1. Identidad regional

- Superficie principal: **4.900 km²**.
- Población oficial regional: **230.000**.
- Población en asentamientos nombrados: **175.800**.
- Población abstracta regional: **54.200**.
- Carácter físico: **mesetas oscuras, escarpas y fondos mineralizados**.
- Función territorial: **gobierno, defensa, refinado y minería acuática**.
- Isla principal: aproximadamente **118 km norte-sur × 72 km** en su parte más ancha.
- La azurita se extrae bajo el océano, alrededor de la raíz insular; no es minería terrestre convencional.

## 2. Quirks regionales

- `HIGH_PLATEAU`
- `ESCARPMENT`
- `AQUATIC_MINING`
- `INDUSTRIAL`
- `MILITARY`
- `VERTICAL_INFRASTRUCTURE`

La prioridad espacial es vertical: meseta de gobierno → escarpa industrial → dársenas de profundidad → océano/minería acuática.

## 3. Asentamientos canónicos

### Kalnaj
- Tipo: **ciudad**.
- Población: **121.000**.
- Posición de atlas: `(37,47)`.
- Canon funcional: Fortaleza Kalnaj, mercado central, distrito de talleres, dársenas mineras, Casa de Remedio mayor, puestos Darkhaven y cargaderos industriales.
- Quirks derivados: `DARKHAVEN, PORT, INDUSTRIAL, HEALTHCARE`.
- Líder local: **PENDIENTE DE DISEÑO**.
- Control faccional: **PENDIENTE DE DISEÑO**.

### Escarpa Azul
- Tipo: **villa minera**.
- Población: **18.600**.
- Posición: `(31,42)`.
- Canon funcional: elevadores de mina, barracones, talleres de núcleo, enfermería minera y mercado de turno.
- Quirks: `MINING, VERTICAL, INDUSTRIAL, HEALTHCARE`.
- Líder/control faccional: **PENDIENTE**.

### Cuenca Roca
- Tipo: **pueblo**.
- Población: **9.200**.
- Posición: `(42,40)`.
- Canon funcional: depósitos de agua, talleres, mercado de abastos, Casa de Remedio y escuela técnica básica.
- Quirks: `WATER_INFRASTRUCTURE, INDUSTRIAL, EDUCATION, HEALTHCARE`.
- Líder/control faccional: **PENDIENTE**.

### Muelle Hondo
- Tipo: **puerto**.
- Población: **14.300**.
- Posición: `(31,52)`.
- Canon funcional: muelles de mineral, aduana, grúas cristalinas, almacenes y cargadero naval.
- Quirks: `MINING, PORT, CUSTOMS, INDUSTRIAL`.
- Líder/control faccional: **PENDIENTE**.

### Vigía Kal
- Tipo: **pueblo faro**.
- Población: **6.100**.
- Posición: `(28,57)`.
- Canon funcional: faro secundario, puesto Darkhaven, muelle de rescate, tabernas de tripulación y depósito de emergencia.
- Quirks: `LIGHTHOUSE, DARKHAVEN, PORT, EMERGENCY`.
- Líder/control faccional: **PENDIENTE**.

### Loma de Hierro
- Población: **2.600**.
- Posición: `(39,54)`.
- Canon: canteras de material común, huertos de ladera y posta; agua/refugio y conexión regional.
- Líder/control faccional: **PENDIENTE**.

### Pozo Siete
- Población: **1.800**.
- Posición: `(34,37)`.
- Canon: cisternas profundas, guardafuentes y mantenimiento de bombas; agua/refugio y conexión regional.
- Líder/control faccional: **PENDIENTE**.

### Cantera Sur
- Población: **2.200**.
- Posición: `(45,52)`.
- Canon: extracción de piedra, remache y transporte hacia talleres; agua/refugio y conexión regional.
- Líder/control faccional: **PENDIENTE**.

## 4. Conexiones troncales canónicas

- **Kalnaj ↔ Muelle Hondo** — elevador, funicular y canal bajo — **0,8 h**.
- **Kalnaj ↔ Vardena Alta** — aerobarco y camino alto — **3,5 h**.
- **Kalnaj ↔ Puerto Sereva** — aerobarco regional — **2,3 h**.

## 5. Red local propuesta v0.1

**PROPUESTA:** enlaces mínimos por proximidad de atlas; no fijan aún medio ni tiempo real.

- `Kalnaj` ↔ `Loma de Hierro` — 27,4 km equivalentes de atlas.
- `Loma de Hierro` ↔ `Cantera Sur` — 33,2 km.
- `Kalnaj` ↔ `Cuenca Roca` — 36,9 km.
- `Kalnaj` ↔ `Escarpa Azul` — 37,1 km.
- `Escarpa Azul` ↔ `Pozo Siete` — 24,2 km.
- `Escarpa Azul` ↔ `Muelle Hondo` — 36,0 km.
- `Muelle Hondo` ↔ `Vigía Kal` — 24,2 km.

## 6. Ciudad de Kalnaj — distritos canónicos

- **Meseta de la Corona** — gobierno, Fortaleza Windrago, Consejo y residencias de Casa.
- **Escarpa de Caldera** — talleres Caldamar, fundiciones, ascensores y vivienda de turno.
- **Dársenas de Campana** — Bajovento, Mutual, descenso, mineral húmedo y espera familiar.
- **Cuenca Oriental** — hogares, huertos, escuelas, cisternas y mercados de barrio.
- **Muelle de Mineral** — aduana acuática, grúas, depósitos y navíos de superficie.
- **Patio de Tres Aguas** — archivo Hidraazul, clínica, mediación y registros de sucesión.
- **Costa de Guardia** — hangares, torres, entrenamiento y refugio Windrago.

### Topología urbana propuesta v0.1

```text
                    [Meseta de la Corona]
                         /          \
          [Patio de Tres Aguas]   [Costa de Guardia]
                    |                   |
             [Cuenca Oriental] -- [Escarpa de Caldera]
                                      |
                              [Dársenas de Campana]
                                      |
                              [Muelle de Mineral]
```

Esta topología es **PROPUESTA**. Traduce el gradiente vertical canónico a grafo jugable y debe contrastarse con los mapas visuales antes de fijarse.

## 7. Seeds estructurales

### Kalnaj
- Fortaleza Kalnaj / núcleo Windrago.
- Consejo provincial.
- Archivo Hidraazul.
- mercado central.
- talleres industriales.
- dársenas mineras.
- Casas de Remedio.
- Darkhaven.
- cargaderos industriales.
- cisternas.
- aduana acuática.

### Escarpa Azul
- Casa de Campanas.
- elevadores de mina.
- barracones.
- talleres de núcleo.
- enfermería de profundidad.
- mercado de turno.
- bombeo.
- almacenes húmedos.

### Cuenca Roca
- depósitos/cisternas.
- mercado de abastos.
- talleres.
- Casa de Remedio.
- escuela técnica.
- vivienda de servicio.

### Muelle Hondo
- muelles de mineral.
- aduana mineral.
- grúas.
- almacenes mojados.
- cargadero naval.
- taller de reparación.
- bombeo.

### Vigía Kal
- faro secundario.
- puesto Darkhaven.
- muelle de rescate.
- tabernas de tripulación.
- depósito de emergencia.
- refugio.

### Loma de Hierro
- canteras de material común.
- huertos de ladera.
- posta.
- mercado/tienda local.
- agua/refugio.

### Pozo Siete
- cisternas profundas.
- guardafuentes.
- mantenimiento de bombas.
- mercado/tienda local.
- refugio.

### Cantera Sur
- extracción de piedra.
- taller/remache.
- transporte hacia talleres.
- mercado/tienda local.
- agua/refugio.

## 8. Próxima pasada regional

1. aprobar o corregir la red local propuesta;
2. definir líder y porcentajes faccionales de los ocho asentamientos;
3. dividir Escarpa Azul, Cuenca Roca, Muelle Hondo y Vigía Kal en Zones;
4. instanciar estructuras comunes y faccionales;
5. crear rutas de profundidad para minería acuática;
6. bajar estructuras clave a Room Blueprints;
7. conectar Jobs/NPC a Rooms concretas.