# SIZA — Caribia / Cadena de las Agujas: Mapa MUD v0.1

**Tipo:** atlas operativo regional  
**Estado:** canon extraído + propuestas topológicas marcadas

## 1. Identidad regional

- Superficie principal: **1.250 km²**.
- Población oficial: **43.000**.
- Población en asentamientos nombrados: **27.300**.
- Población abstracta: **15.700**.
- Carácter físico: **peñones occidentales y corredores de niebla**.
- Función: **faros, vigilancia, refugio y acceso exterior**.
- Quirks: `ROCK_SPIRES`, `HEAVY_FOG`, `LIGHTHOUSE_NETWORK`, `EDGE_FRONTIER`, `ISOLATED_REFUGES`.

La red de faros es una infraestructura espacial distribuida. Cada nodo cubre un corredor; si uno falla, cambia la conectividad de sus vecinos y aumenta el gasto de reservas.

## 2. Asentamientos

- **Primera Luz** — 7.800 — faro estratégico, Casa de Relevo, Darkhaven, Casa de Remedio, muelle de evacuación y depósito energético.
- **Aguja Media** — 5.100 — faro, taller de baliza, refugios, mercado pequeño y Darkhaven.
- **Puerto Niebla** — 4.300 — rescate oceánico, almacenes, Casa de Remedio y taberna de relevo.
- **Segunda Luz** — 3.200 — baliza auxiliar, reserva y escuela de fareros.
- **Última Aguja** — 2.600 — faro de borde, Darkhaven reducido, depósito de emergencia, muelle estrecho y refugio.
- **Aguja de Sal** — 1.900 — cisterna mineral, señal de niebla y pesca difícil.
- **Punta Hueca** — 1.500 — observatorio acústico, refugio y acceso a cavernas.
- **Islas Tortus** — cerca de 900 — sector insular sagrado con Basílica de Sait Voltaire, hospedería y plataforma de peregrinos.

Líderes y porcentajes faccionales: **PENDIENTES**.

## 3. Conexiones troncales canónicas

- **Primera Luz ↔ Punta Ocaso** — navío o aerobarco ligero — **1,2 h**.
- **Primera Luz ↔ Aguja Media** — barco de relevo — **1 h**.
- **Aguja Media ↔ Última Aguja** — barco de relevo — **2,5 h**.

## 4. Red local propuesta v0.1

- Primera Luz ↔ Aguja Media.
- Aguja Media ↔ Segunda Luz.
- Aguja Media ↔ Aguja de Sal.
- Aguja Media ↔ Puerto Niebla.
- Puerto Niebla ↔ Punta Hueca.
- Punta Hueca ↔ Islas Tortus.
- Punta Hueca ↔ Última Aguja.

La red local es **PROPUESTA** hasta fijar corredores de niebla, rutas de relevo, navegación de superficie y aerobarcos.

## 5. Seeds estructurales

### Primera Luz
- faro estratégico.
- Casa de Relevo.
- Darkhaven.
- Casa de Remedio.
- muelle de evacuación.
- depósito energético.

### Aguja Media
- taller de baliza.
- refugios.
- mercado pequeño.
- puesto Darkhaven.

### Puerto Niebla
- rescate oceánico.
- almacenes.
- Casa de Remedio.
- taberna de relevo.

### Segunda Luz
- baliza auxiliar.
- reserva.
- escuela de fareros.

### Última Aguja
- faro de borde.
- Darkhaven reducido.
- depósito de emergencia.
- muelle estrecho.
- refugio.

### Aguja de Sal
- cisterna mineral.
- señal de niebla.
- pesca difícil.

### Punta Hueca
- observatorio acústico.
- refugio.
- acceso a cavernas.

### Islas Tortus
- Basílica de Sait Voltaire.
- hospedería religiosa.
- plataforma de peregrinos.
- refugio de peregrinos.

## 6. Regla especial de la red de faros

Un faro no ilumina toda la frontera. Abre un corredor y coordina señales. El `WORLD_STATE` debe registrar al menos:

```text
lighthouse_status
pulse_quality
reserve_level
covered_routes
neighbor_support
fog_grade
```

Cuando un faro cae, no desaparece el mapa: cambian disponibilidad y riesgo de los Exits/rutas asociados.

## 7. Próxima pasada

Fijar rutas de relevo entre todos los peñones, modelar el interior de Primera Luz como nodo de coordinación y definir el tratamiento especial de Islas Tortus sin convertirlo en un pueblo genérico.