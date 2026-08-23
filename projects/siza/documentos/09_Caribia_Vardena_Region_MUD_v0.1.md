# SIZA — Caribia / Vardena: Mapa MUD v0.1

**Tipo:** atlas operativo regional  
**Estado:** canon extraído + propuestas topológicas marcadas

## 1. Identidad regional

- Superficie principal: **6.200 km²**.
- Población oficial: **305.000**.
- Población en asentamientos nombrados: **135.500**.
- Población abstracta: **169.500**.
- Carácter físico: **islas altas, suelos profundos, lagos y bosques húmedos**.
- Función: **agua, agricultura, madera y alimentos**.
- Quirks: `HIGH_ISLANDS`, `FRESHWATER_RICH`, `AGRICULTURAL`, `FORESTED`, `IRRIGATION_NETWORK`.

El mapa debe hacer visible que **agua, caminos y depósitos son poder**. Vardena es una red de cuencas, canales, terrazas, graneros y postas, no una colección de granjas aisladas.

## 2. Asentamientos

- **Vardena Alta** — ciudad, 86.000 — mercado agrícola mayorista, estación de carga, talleres de bombas, Casas de Remedio, escuelas y administración de riego.
- **Río Claro** — villa, 12.600 — canales, molinos, cooperativas, mercado semanal y Casa de Remedio.
- **Tres Puentes** — 7.800 — cruce de caminos, posadas, mercado de carga y reparación de transporte.
- **Ladera Norte** — 5.200 — terrazas agrícolas, cargadero comunal, escuela y altar/capilla advenida.
- **Santero de Agua** — 9.700 — reservorios, guardafuentes, taller de bombas, mercado de herramientas y Casa de Remedio.
- **Corte Verde** — 4.400 — viveros, aserraderos, depósitos y brigada de incendio rural.
- **Las Acequias** — 3.100 — distribución de riego, hortalizas, talleres pequeños y servicios locales.
- **Paso Largo** — 2.100 — posta de camino, relevo de transporte y albergue de tormenta.
- **Cauce Viejo** — 1.700 — canales antiguos, pesca de lago y reparación de compuertas.
- **Mesa Verde** — 2.900 — graneros elevados, mercado semanal y aeromuelle rural.

Líderes y porcentajes de WINDRAGO / ADVENIDOS / ECLESIA / LADRONES quedan **PENDIENTES DE DISEÑO**.

## 3. Conexiones troncales canónicas

- **Vardena Alta ↔ Kalnaj** — aerobarco y camino alto — **3,5 h**.
- **Vardena Alta ↔ Puerto Sereva** — camino de terraza y transporte de carga — **2,2 h**.

## 4. Red local propuesta v0.1

**PROPUESTA:** red mínima derivada de proximidad en el atlas; no fija todavía modo ni tiempo.

- Vardena Alta ↔ Ladera Norte.
- Ladera Norte ↔ Paso Largo.
- Paso Largo ↔ Corte Verde.
- Vardena Alta ↔ Mesa Verde.
- Mesa Verde ↔ Tres Puentes.
- Mesa Verde ↔ Las Acequias.
- Las Acequias ↔ Río Claro.
- Río Claro ↔ Cauce Viejo.
- Cauce Viejo ↔ Santero de Agua.

## 5. Vardena Alta — distritos canónicos

- **Mercado Alto** — cosecha mayorista, posadas y contratos rurales.
- **Canales** — reservorios, bombas, guardafuentes y política de agua.
- **Barrio de Oficios** — molinos, carpintería, herrería y conservación.
- **Camino de Sereva** — posta, aduana interior, carga y vivienda de viajeros.
- **Jardines de Lluvia** — viveros, clínicas, residencias y escuelas.

## 6. Seeds estructurales

Cada asentamiento debe generar infraestructura de agua y alimento antes de cualquier decoración. Los seeds principales son:

- Vardena Alta: Cabildo de Agua, mercado mayorista, administración de riego, talleres de bombas, gran posta, salud y escuelas.
- Río Claro: canales, molinos, cooperativas y Casa de Remedio.
- Santero de Agua: reservorios, guardafuentes, taller de bombas y audiencias de cuenca.
- Tres Puentes: cruce, posadas, mercado de carga y taller de transporte.
- Ladera Norte: terrazas, cargadero comunal, escuela y altar advenido.
- Corte Verde: viveros, madera tratada, depósitos y brigada de incendio.
- Las Acequias: riego, producción hortícola y talleres pequeños.
- Paso Largo: posta y refugio.
- Cauce Viejo: compuertas, canales y pesca lacustre.
- Mesa Verde: graneros, mercado y aeromuelle rural.

## 7. Próxima pasada

Aprobar conexiones locales, asignar líderes/facciones, dividir villas grandes en Zones, instanciar estructuras, y convertir sistemas de agua, molinos, caminos y mercados en Rooms/Exits persistentes.