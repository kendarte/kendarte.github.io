# SIZA — Caribia / Orvena: Mapa MUD v0.1

**Tipo:** atlas operativo regional  
**Estado:** canon extraído + propuestas topológicas marcadas

## 1. Identidad regional

- Superficie principal: **2.700 km²**.
- Población oficial: **135.000**.
- Población en asentamientos nombrados: **89.200**.
- Población abstracta: **45.800**.
- Carácter físico: **archipiélagos bajos, esteros, arrecifes y aguas cálidas**.
- Función: **pesca, conservación, acuicultura y cocina**.
- Quirks: `LOW_ARCHIPELAGO`, `WARM_WATERS`, `FISHING_GROUNDS`, `AQUACULTURE`, `FOOD_PRESERVATION`.

La cadena física **captura → lonja → conservación → mercado → transporte** debe existir como recorrido real del MUD. Si una parte falla, el efecto económico sale de la topología y del estado, no de una ocurrencia del Master.

## 2. Asentamientos

- **Bajorvena** — ciudad, 52.000 — lonja, cámaras frías, mercado de manafauna, cocinas y astilleros ligeros.
- **Punta Clara** — villa, 10.500 — flota pesquera, secado, redes y cargadero de temporada.
- **Puerto Frío** — villa, 8.900 — conservación, subasta mayorista y convoyes refrigerados.
- **Las Redes** — 6.400 — cooperativas, escuela de navegación y Casa de Remedio.
- **Marea Baja** — 4.700 — salinas, encurtido, bombas de estero y muelle de fondo plano.
- **Las Boyas** — 2.600 — mantenimiento de señales, viveros y rescate costero.
- **Caleta Sur** — 2.200 — pesca familiar, mercado de amanecer y refugio de temporal.
- **Piedra de Red** — 1.900 — tejido de red, extracción de sal y cría de moluscos.

Líderes y porcentajes faccionales quedan **PENDIENTES**.

## 3. Conexión troncal canónica

- **Bajorvena ↔ Puerto Sereva** — navío costero — **2,8 h**.

## 4. Red local propuesta v0.1

- Bajorvena ↔ Marea Baja.
- Bajorvena ↔ Puerto Frío.
- Puerto Frío ↔ Las Boyas.
- Las Boyas ↔ Punta Clara.
- Punta Clara ↔ Caleta Sur.
- Marea Baja ↔ Piedra de Red.
- Piedra de Red ↔ Las Redes.

La red es **PROPUESTA** y debe convertirse después en canales, rutas de fondo plano, muelles, caminos de isla o cabotaje según cada tramo.

## 5. Bajorvena — distritos canónicos

- **Lonja** — subasta, clasificación, pescaderías y gremios.
- **Frigoríficos** — hielo manaral, almacenes y riesgo de cuota.
- **Barrio de Redes** — hogares, reparación, tabernas y Casas de Remedio.
- **Muelle Sur** — flota, rescate, astilleros pequeños y mercado de amanecer.

## 6. Seeds estructurales

- Bajorvena: lonja, frigoríficos, mercado de manafauna, cocinas, pescaderías, astilleros ligeros, salud y muelles.
- Punta Clara: flota, secaderos, talleres de red y cargadero estacional.
- Puerto Frío: cámaras frías, subasta, almacenes y convoyes.
- Las Redes: cooperativas, escuela de navegación y salud.
- Marea Baja: salinas, encurtido, bombas de estero y muelle bajo.
- Las Boyas: señalización, viveros y rescate.
- Caleta Sur: pesca familiar, mercado de amanecer y refugio.
- Piedra de Red: tejido de red, sal y moluscos.

## 7. Consecuencias espaciales obligatorias

- una avería en Frigoríficos degrada inventarios y crea eventos de pérdida;
- un muelle bloqueado debe cortar rutas de captura;
- una marea o fenómeno de estero puede cerrar Exits de fondo plano;
- una especie protegida cambia qué Rooms/zonas de pesca pueden explotarse.

## 8. Próxima pasada

Diseñar la topología interna de Bajorvena y después modelar una ruta completa desde embarcación pesquera hasta mercado urbano para validar economía, Jobs y Rooms.