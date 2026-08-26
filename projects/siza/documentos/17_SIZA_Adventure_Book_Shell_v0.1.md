# SIZA — Adventure Book Shell v0.1

**Tipo:** especificación funcional de interfaz  
**Alcance:** frontend `siza-mobile-test` + futura presentación del World Engine  
**Estado:** implementación incremental; no modifica reglas TCG ni autoridad del World Engine

## 1. Objetivo

SIZA usa una sola pantalla de aventura que cambia de jerarquía según el estado del juego.

Modos de presentación:

```text
EXPLORATION
DIALOGUE
COMBAT
```

No son aplicaciones, escenas ni menús independientes. Son tres composiciones de la misma `Adventure Book Shell`.

La transición correcta es:

```text
EXPLORATION -> DIALOGUE -> EXPLORATION -> COMBAT -> EXPLORATION
```

El jugador debe percibir continuidad de lugar, personajes y estado.

## 2. Frontera de autoridad

La Shell no decide mundo ni combate.

- World Engine: autoriza Rooms, Exits, presencia, Facts, Knowledge, Actions y consecuencias.
- TCG runtime: autoriza reglas, mano, cristales, Manafestation, Stack, combate y resolución.
- Adventure Book Shell: presenta el estado autorizado y recoge intención del jugador.

Cambiar la interfaz no permite crear Facts, Exits, NPC, cartas o resultados.

## 3. Estado actual inspeccionado

El frontend actual ya contiene los tres componentes necesarios, pero no comparten todavía una carcasa visual única.

### Adventure

`renderAdventure()` usa:

```text
adventureGrid
scenePanel
sceneVisual
storyBlock
choices
objectiveBox
masterPulse
journalList
```

Actualmente exploración y diálogo viven juntos en esta ruta.

### Combat

`renderMatchV600()` usa:

```text
matchShell v05
matchHeader
matchBoardV5
arenaHalf
matchLog
resourceRailV610
handAreaV5
```

La clase `arenaShellV600` oculta la sidebar y el topbar para entrar en focus mode. Esa ruptura es la costura principal que debe eliminar la Book Shell.

### Estado existente reutilizable

No se reemplaza:

```text
state.adventure
state.match
state.player.mag
state.collection
state.deck
```

La Shell consume esos estados; no los redefine.

## 4. Regiones persistentes de la pantalla

La Shell mantiene cinco regiones conceptuales en los tres modos:

```text
BOOK_HEADER
SCENE_STAGE
CHARACTER_PRESENCE
NARRATIVE_PANEL
ACTION_RESOURCE_RAIL
```

### BOOK_HEADER

Siempre puede mostrar:

- capítulo;
- ubicación;
- región;
- hora/condición;
- identidad compacta del player;
- contraparte cuando exista;
- recursos globales relevantes.

### SCENE_STAGE

EXPLORATION: lugar y presencia física.  
DIALOGUE: mismo lugar, con prioridad a interlocutores.  
COMBAT: mismo espacio convertido en arena funcional.

### CHARACTER_PRESENCE

El player no desaparece entre modos. La contraparte cambia de función:

- NPC/interlocutor en diálogo;
- acompañante o presencia relevante en exploración;
- rival/enemigo en combate.

### NARRATIVE_PANEL

El área donde hoy vive texto de Adventure también debe ser el lugar conceptual del log de combate.

No se requiere que tenga idéntica altura, pero sí la misma función: explicar qué acaba de ocurrir y qué puede hacer el jugador.

### ACTION_RESOURCE_RAIL

EXPLORATION: Actions contextuales.  
DIALOGUE: respuestas/preguntas.  
COMBAT: mano, cristales, turno y comandos.

## 5. Jerarquía por modo

### EXPLORATION

Prioridad:

1. escena;
2. descripción/narración;
3. Actions;
4. personajes;
5. progreso/recursos.

La escena ocupa el área mayor.

### DIALOGUE

Prioridad:

1. interlocutores;
2. texto;
3. respuestas;
4. escena;
5. recursos.

La Room no desaparece. El diálogo es un estado dentro de la Room.

### COMBAT

Prioridad:

1. arena;
2. mano/cartas;
3. estados de combatientes;
4. turno/recursos;
5. log.

El combate no navega a una identidad visual ajena. La misma carcasa se comprime y reorganiza.

## 6. Contrato UI v0.1

Se crea `siza-mobile-test/adventure-book-shell-v01.js` como módulo de presentación sin side effects.

Modelo:

```text
version
mode
header
player
counterpart
scene
narrative
actions
resources
payload
```

### mode

```text
EXPLORATION
DIALOGUE
COMBAT
```

### header

```text
chapter
location
region
time
condition
```

### character

```text
id
name
title
portrait
life
mf
prow
eva
status[]
```

### scene

```text
title
subtitle
image
state
```

### narrative

```text
speaker
lead
text
prompt
log[]
```

### action

```text
id
label
hint
kind
enabled
payload
```

### resources

```text
crystals
hand[]
advance
advanceMax
turn
phase
```

El campo `payload` permite conservar una referencia al estado autorizado sin que la Shell lo interprete como autoridad.

## 7. Integración incremental

No se reescribe `index.html` de una sola vez.

Orden:

1. cargar el módulo `adventure-book-shell-v01.js`;
2. construir un adaptador desde `state.adventure` al modelo de Shell;
3. reemplazar únicamente el wrapper visual de `renderAdventure()`;
4. validar Adventure sin modificar Events/checks/flags;
5. construir adaptador desde `state.match`;
6. reemplazar únicamente el wrapper exterior de `renderMatchV600()`;
7. conservar intactas todas las funciones de reglas y resolución;
8. añadir estado `DIALOGUE` cuando un evento/NPC requiera presentación conversacional explícita.

## 8. Invariantes de regresión

Adventure Book Shell no puede cambiar:

- selección de Adventure Events;
- `advance`;
- `flags`;
- journal;
- desbloqueos;
- deck de 60 cartas;
- Manafestation;
- cristales;
- Mana Burn;
- Stack/prioridad;
- reglas de ataque/bloqueo;
- vida;
- resultado del match.

Si cualquiera cambia por una modificación de Shell, el cambio es inválido.

## 9. Primer recorrido objetivo

La primera validación seamless debe cubrir:

```text
EXPLORATION
Muelle / Dársenas
    ->
DIALOGUE
interacción con NPC
    ->
EXPLORATION
estado actualizado
    ->
COMBAT
encuentro TCG
    ->
EXPLORATION
consecuencia persistente
```

En una fase posterior el Muelle Viejo de prueba se sustituirá por contenido real de Rivarica sin cambiar el contrato de la Shell.

## 10. Regla de cierre v0.1

La Shell v0.1 se considera integrada cuando Adventure y Combat pueden cambiar de modo sin perder:

- identidad de ubicación;
- identidad del player;
- contraparte relevante;
- continuidad narrativa;
- estado autorizado;
- acceso al siguiente input válido.

La meta no es que las tres composiciones sean idénticas. La meta es que parezcan tres posiciones de la misma página viva.
