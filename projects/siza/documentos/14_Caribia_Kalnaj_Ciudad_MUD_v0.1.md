# SIZA — Caribia / Kalnaj Urbana: Mapa MUD Detallado v0.1

**Tipo:** mapa urbano operativo  
**Escala:** ciudad → distrito/Zone → nodo público → estructura/interior  
**Estado:** distritos canónicos + topología y nodos propuestos

## 1. Regla de diseño

Kalnaj urbana no es una escena. Es un conjunto de **Zones persistentes conectadas vertical y horizontalmente**.

Canon físico:

- la **Meseta de la Corona** ocupa el nivel alto de gobierno;
- la **Escarpa de Caldera** desciende mediante plataformas y ascensores;
- las **Dársenas de Campana** ocupan el nivel bajo asociado a minería de profundidad;
- la **Cuenca Oriental** sostiene vivienda, huertos, escuelas y agua;
- el **Muelle de Mineral** conecta carga minera y navíos de superficie;
- el **Patio de Tres Aguas** concentra archivo Hidraazul, clínica y mediación;
- la **Costa de Guardia** concentra hangares, torres, entrenamiento y refugio Windrago.

Los nombres de distritos son CANON. Los nodos internos de este documento son `PROPUESTA` hasta aprobación.

## 2. Grafo de distritos propuesto

```text
                         [MESETA DE LA CORONA]
                           /       |        \
                          /        |         \
       [PATIO DE TRES AGUAS] [COSTA DE GUARDIA] [ESCARPA DE CALDERA]
                 |                  |                  |
                 |                  |                  |
          [CUENCA ORIENTAL] --------+------------------+
                                                       |
                                               [DÁRSENAS DE CAMPANA]
                                                       |
                                               [MUELLE DE MINERAL]
```

No implica distancia métrica. Indica qué Zones deben poseer Exits directos o sistemas de transporte entre ellas.

## 3. Meseta de la Corona

### Descripción canónica base

Meseta de gobierno de piedra oscura y techos de escama resistentes al viento. Contiene Fortaleza Windrago, Consejo, archivos de alto nivel y residencias mayores. Los patios amplios también sirven como formación y refugio.

### Nodos públicos propuestos

`KAL-MES-001 — Acceso de la Meseta`  
Punto de llegada desde Cuenca/Escarpa. Control de tránsito según estado político.

`KAL-MES-002 — Patio de Formación`  
Espacio abierto frente a estructuras Windrago. Funciona como plaza cívica, formación y refugio.

`KAL-MES-003 — Puerta de Fortaleza Kalnaj`  
Entrada estructural; no es la Fortaleza completa.

`KAL-MES-004 — Acceso del Consejo`  
Nodo exterior del gobierno provincial.

`KAL-MES-005 — Paseo de Residencias`  
Conecta residencias mayores y recepciones políticas.

### Exits principales propuestos

- Acceso de Meseta → Escarpa de Caldera.
- Acceso de Meseta → Patio de Tres Aguas.
- Patio de Formación → Costa de Guardia.
- Puerta de Fortaleza → interior de Fortaleza Kalnaj.

### Capas sensoriales candidatas

Vista: estandartes activos, formación, tránsito de Casa.  
Oído: viento, órdenes, campanas de turno lejanas.  
Olfato: piedra húmeda, metal, cocina de patios/refugio.  
Tacto: viento fuerte y piedra fría.

## 4. Escarpa de Caldera

### Descripción canónica base

Distrito industrial vertical. Plataformas y ascensores descienden por la roca. Caldamar mantiene talleres, fundiciones y astilleros colgados. Conductos visibles y ruido continuo; un silencio brusco puede indicar paro, accidente o pérdida de cuota.

### Nodos públicos propuestos

`KAL-ESC-001 — Estación Alta de Ascensores`  
Intercambio con Meseta/Cuenca.

`KAL-ESC-002 — Calle de Talleres`  
Accesos a múltiples talleres e industrias.

`KAL-ESC-003 — Patio de Fundición`  
Nodo industrial exterior, carga y control de seguridad.

`KAL-ESC-004 — Plataforma Media`  
Distribuye tráfico entre talleres y vivienda de turno.

`KAL-ESC-005 — Estación Baja de Ascensores`  
Conecta con Dársenas de Campana.

### Estado persistente relevante

- ascensor operativo / averiado / cerrado;
- cuota energética;
- turno industrial;
- accidente;
- paro;
- contaminación/humo;
- acceso restringido.

Una avería de ascensor modifica el grafo: algunos Exits quedan bloqueados y aparecen rutas alternativas más lentas.

## 5. Dársenas de Campana

### Descripción canónica base

Nivel bajo asociado a Bajovento, compañías mineras y Mutual Campana Honda. Familias esperan listas de regreso junto a comida y Casas de Remedio. El mineral asciende húmedo desde los descensos.

### Nodos públicos propuestos

`KAL-DAR-001 — Llegada de Ascensores`  
Conecta con Escarpa de Caldera.

`KAL-DAR-002 — Patio de Turnos`  
Listas de ingreso/regreso, contratación y espera familiar.

`KAL-DAR-003 — Mutual Campana Honda`  
Entrada a estructura administrativa y de seguridad laboral.

`KAL-DAR-004 — Casa de Remedio de Dársena`  
Entrada sanitaria.

`KAL-DAR-005 — Patio de Mineral Húmedo`  
Clasificación temporal antes de transporte.

`KAL-DAR-006 — Muelles de Descenso`  
Acceso a campanas, armaduras y expediciones de profundidad.

`KAL-DAR-007 — Corredor a Muelle de Mineral`  
Transferencia hacia carga de superficie.

### Submapa futuro obligatorio

```text
DÁRSENA
  ↓
CAMPANA / ASCENSOR DE PROFUNDIDAD
  ↓
ESTACIÓN SUMERGIDA
  ↓
RUTA DE FONDO
  ↓
VETA / PECIO / TEMPLO / INCIDENTE
```

La minería acuática requiere su propio grafo tridimensional.

## 6. Cuenca Oriental

### Descripción canónica base

Zona residencial y de servicios con hogares, huertos, escuelas, depósitos de agua y mercados de barrio. Mezcla empleados de Casa, obreros, artesanos y soldados.

### Nodos públicos propuestos

`KAL-CUE-001 — Plaza de Cisterna`  
Agua comunal y política cotidiana.

`KAL-CUE-002 — Mercado de Barrio`  
Comida, herramientas y servicios.

`KAL-CUE-003 — Calle de Escuelas`  
Entradas a escuelas y aprendizaje técnico.

`KAL-CUE-004 — Huertos de Cuenca`  
Producción y ocio.

`KAL-CUE-005 — Cruce Residencial`  
Distribuye rutas hacia hogares persistentes.

`KAL-CUE-006 — Camino de Tres Aguas`  
Conecta con Patio de Tres Aguas.

`KAL-CUE-007 — Subida a la Meseta`  
Conexión política/administrativa.

### Estado persistente relevante

- nivel de cisterna;
- precio/escasez de agua;
- horario escolar;
- mercado abierto/cerrado;
- presión política;
- evacuación desde niveles inferiores.

## 7. Muelle de Mineral

### Función canónica

Aduana acuática, grúas, depósitos y navíos de superficie. Recibe mineral y mercancía pesada.

### Nodos públicos propuestos

`KAL-MIN-001 — Acceso de Aduana`  
`KAL-MIN-002 — Patio de Grúas`  
`KAL-MIN-003 — Depósitos Mojados`  
`KAL-MIN-004 — Muelle de Carga`  
`KAL-MIN-005 — Embarque de Superficie`  
`KAL-MIN-006 — Corredor de Dársenas`

### Estado persistente

aduana, huelga, grúa averiada, cuota de carga, depósito lleno, inspección, tormenta, contaminación de mineral.

## 8. Patio de Tres Aguas

### Función canónica

Archivo Hidraazul, clínica, mediación y registros de sucesión.

### Nodos públicos propuestos

`KAL-PTA-001 — Patio Central`  
`KAL-PTA-002 — Archivo Hidraazul`  
`KAL-PTA-003 — Clínica`  
`KAL-PTA-004 — Sala de Mediación`  
`KAL-PTA-005 — Registro de Sucesión`  
`KAL-PTA-006 — Camino de Cuenca`  
`KAL-PTA-007 — Subida a Meseta`

Este distrito será importante para Knowledge: genealogía, medicina, ley, archivos y Casas nobles deben desbloquear información distinta sobre los mismos objetos/documentos.

## 9. Costa de Guardia

### Función canónica

Hangares, torres, entrenamiento y refugio Windrago.

### Nodos públicos propuestos

`KAL-GUA-001 — Puerta de Guardia`  
`KAL-GUA-002 — Patio de Entrenamiento`  
`KAL-GUA-003 — Hangares`  
`KAL-GUA-004 — Torre de Vigilancia`  
`KAL-GUA-005 — Refugio Windrago`  
`KAL-GUA-006 — Conexión de Meseta`  
`KAL-GUA-007 — Ruta de Escarpa`

El acceso cambia por nivel de alerta, reputación, órdenes y crisis.

## 10. Principio de estructuras

Los nodos anteriores son **espacio público/intersticial**. Las estructuras se abren como Zones propias.

Ejemplo:

```text
KAL-DAR-004 Casa de Remedio
    ↓ ENTER
ZONE: CASA_REMEDIO_DARSENA
    ├── recepción
    ├── sala de espera
    ├── consulta
    ├── tratamiento
    ├── almacén médico
    └── zona de personal
```

De esta forma la ciudad conserva escala sin convertir cada edificio en una sola descripción.

## 11. IDs y persistencia

Formato inicial:

```text
CAR-KAL-CITY-[DISTRICT]-[NODE]
```

Ejemplo: `CAR-KAL-CITY-DAR-006`.

Estado separado:

```text
MAP_DEFINITION
WORLD_STATE
PLAYER_DISCOVERY
```

El nombre visible puede cambiar sin romper el ID persistente.

## 12. Próximo trabajo

1. aprobar grafo de distritos;
2. aprobar nodos públicos;
3. fijar números/instancias de estructuras comunes por distrito;
4. insertar estructuras WINDRAGO/CALDAMAR/BAJOVENTO/HIDRAAZUL;
5. construir blueprints interiores;
6. generar el primer recorrido jugable continuo: **Cuenca Oriental → Meseta → Escarpa → Dársenas → Muelle de Mineral**;
7. probar que Nereida pueda caminar ese recorrido Room por Room sin que Qwen invente una salida.