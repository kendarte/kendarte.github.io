# SIZA — Caribia / Sereva: Mapa MUD v0.1

**Tipo:** atlas operativo regional  
**Estado:** canon extraído + propuestas topológicas marcadas

## 1. Identidad regional

- Superficie principal: **3.100 km²**.
- Población oficial: **275.000**.
- Población en asentamientos nombrados: **237.000**.
- Población abstracta: **38.000**.
- Carácter físico: **canales centrales, bahías protegidas y alturas medias**.
- Función: **comercio, correos, seguros y transbordo**.
- Quirks: `CENTRAL_CHANNELS`, `PROTECTED_BAYS`, `COMMERCIAL_HUB`, `TRANSIT_HUB`, `VERTICAL_PORT`.

El mapa debe superponer **puerto oceánico abajo, plataformas aéreas arriba y ascensores entre ambos**. En Sereva la altura es coste logístico y también división social.

## 2. Asentamientos

- **Puerto Sereva** — metrópoli, 178.000 — puerto mayor, banca manaral, Velacendra, Guante Azul, aduana, Darkhaven, astilleros y mercados refrigerados.
- **Terrazas de Sereva** — ciudad satélite, 24.100 — vivienda obrera, ascensores, mercados y cargaderos de barrio.
- **Dársena Vieja** — 11.200 — muelles antiguos, talleres navales, usados, empeño y contrabando.
- **Paso del Viento** — 8.300 — estación aeromarina, seguro, aduana interior y posadas.
- **Las Gradas** — 6.900 — ascensores de acantilado, poleas, guardia y mercado de tránsito.
- **Barranca** — 3.300 — vivienda de borde, talleres de cable y huertos de terraza.
- **Muelle Chico** — 2.800 — cabotaje, pesca diaria y hospedaje familiar.
- **Puerto Seco** — 2.400 — depósito interior, reparación de carros y conexión por cable.

Líderes y porcentajes faccionales quedan **PENDIENTES**.

## 3. Conexiones troncales canónicas

- **Puerto Sereva ↔ Kalnaj** — aerobarco regional — **2,3 h**.
- **Puerto Sereva ↔ Vardena Alta** — camino de terraza y transporte de carga — **2,2 h**.
- **Puerto Sereva ↔ Bajorvena** — navío costero — **2,8 h**.
- **Puerto Sereva ↔ Ragmar del Este** — aerobarco — **3 h**.

## 4. Red local propuesta v0.1

- Puerto Sereva ↔ Terrazas de Sereva.
- Terrazas de Sereva ↔ Puerto Seco.
- Puerto Seco ↔ Paso del Viento.
- Paso del Viento ↔ Barranca.
- Puerto Sereva ↔ Las Gradas.
- Las Gradas ↔ Muelle Chico.
- Muelle Chico ↔ Dársena Vieja.

Estas conexiones son **PROPUESTA**, no rutas canónicas cerradas.

## 5. Puerto Sereva — distritos canónicos

- **Dársena Mayor** — aduana, lonjas, grúas, almacenes y trabajo portuario.
- **Bajos del Puerto** — vivienda densa, talleres, tabernas y casas de contraseña.
- **Cinturón de Mercado** — puestos, canales, cargaderos y mezcla de clases.
- **Terrazas Altas** — bancos, seguros, residencias y Guante Azul.
- **Astilleros** — diques, Caldamar, carpintería naval y núcleos de barco.
- **Mercado Frío** — subastas, cámaras, cocinas y transporte alimentario.
- **Barrio de Postas** — Velacendra, aerobarcos, correo y hospedaje de tránsito.
- **Patio del Alba** — parroquia Soledeo, refectorio Carmesí y peregrinos urbanos.

## 6. Seeds estructurales

- Puerto Sereva: puerto mayor, bancos, casas de cambio, aduana, astilleros, mercados fríos, Darkhaven, Casas de Remedio, correo y hospedaje.
- Terrazas: vivienda obrera, ascensores, cargaderos y mercados.
- Dársena Vieja: muelles antiguos, talleres navales, usados, empeño y red clandestina.
- Paso del Viento: aeromuelle, seguros, aduana interior y posadas.
- Las Gradas: ascensores, talleres de poleas, guardia y mercado de tránsito.
- Barranca: vivienda de borde, cables y huertos de terraza.
- Muelle Chico: cabotaje, pesca y hospedaje familiar.
- Puerto Seco: depósito interior, reparación de transporte y conexión por cable.

## 7. Consecuencias espaciales obligatorias

Una huelga de ascensores debe poder **separar físicamente** muelle y mercado. Una avería de cámara fría debe afectar Rooms de almacenamiento y rutas de alimento. Un cierre de aduana debe bloquear Exits/rutas, no ser sólo texto narrativo.

## 8. Próxima pasada

Definir topología vertical de Puerto Sereva, conexiones de ascensor/cable, líderes y facciones, y luego instanciar edificios y Rooms de Dársena Mayor como primer distrito jugable.