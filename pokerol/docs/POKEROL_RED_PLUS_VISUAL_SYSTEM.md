# POKEROL — Red Plus Visual System v0.1

POKEROL usa una interfaz inspirada en la legibilidad y economía visual de los RPG monocromos de Game Boy, especialmente la era de Pokémon Red/Blue, sin copiar marcos, tiles, logos ni tipografías propietarias 1:1.

## Principios

1. **Pixel-first, desktop-readable.** La interfaz simula una cuadrícula lógica pequeña, pero se escala para pantallas modernas.
2. **Cuatro tonos base + estados.** La pantalla principal usa una paleta limitada tipo LCD. Los acentos de peligro/selección son discretos y nunca sustituyen la legibilidad.
3. **Bordes duros.** No usar glassmorphism, blur, gradientes fotográficos ni esquinas grandes. Los paneles principales se leen como ventanas de RPG.
4. **Texto primero.** Descripción, diálogo y decisiones deben ser legibles antes que decorativas.
5. **Un cursor inequívoco.** La selección activa siempre usa un marcador triangular `▶` y/o inversión de fondo.
6. **Exploración y combate comparten lenguaje visual.** No deben parecer dos aplicaciones diferentes.
7. **Sprites pixelados sin suavizado.** `image-rendering: pixelated` para Pokémon, iconos y previews retro.
8. **El mundo puede ser ilustrado.** La UI es retro; las escenas/fondos pueden tener más detalle. Esto crea el estilo `Red Plus`.

## Paleta

Variables CSS autoritativas:

- `--pk-ink: #172016`
- `--pk-dark: #33412d`
- `--pk-mid: #71835f`
- `--pk-light: #d7e0bd`
- `--pk-paper: #eef3d5`
- `--pk-select: #263521`
- `--pk-select-text: #f2f6dc`
- `--pk-danger: #7f342f`
- `--pk-warning: #7a6430`

El fondo general puede ser más oscuro para separar la “pantalla” del navegador, pero los paneles jugables deben permanecer en la familia LCD.

## Tipografía

La UI intenta cargar `Silkscreen` como fuente pixel abierta desde Google Fonts. Fallback:

`ui-monospace, "Cascadia Mono", Consolas, monospace`

- Labels / menús: Silkscreen, 10–13 px.
- Diálogo / narrativa: monospace legible, 13–16 px.
- Nunca usar Georgia/serif en POKEROL.

## Escala

- Base visual conceptual: 160×144.
- Desktop: panel de juego máximo ~1152×864.
- Bordes: 2–4 px.
- Radio de esquinas: 0–4 px, nunca pill shapes para UI primaria.

## Componentes

### WindowFrame
- fondo `--pk-paper`
- borde exterior `--pk-ink`
- borde interior `--pk-mid`
- sombra dura 3–5 px

### DialogueBox
- texto oscuro sobre fondo claro
- altura suficiente para 2–4 líneas
- cursor `▼` para continuar si hay paginación

### ChoiceMenu
- una o dos columnas
- selección `▶`
- hover/focus = inversión de fondo

### StatusPanel
- nombre
- nivel
- estado
- HP con barra segmentada/recta
- sin tarjetas redondeadas modernas

### BattleHUD
- enemigo arriba-izquierda
- Pokémon jugador abajo-derecha
- caja de diálogo abajo-izquierda
- menú abajo-derecha
- FIGHT / POKÉMON / BAG / RUN

### MoveMenu
Cada move muestra:
- nombre
- tipo
- PP (cuando runtime lo exponga)
- power/accuracy como información secundaria, no dominante

### PartySlot
Posterior sprint:
- icono
- nombre
- nivel
- HP
- estado
- cursor de selección

## Estados de pantalla

Exploration:
`SCENE -> DIALOGUE/ACTIONS`

Travel Event:
`EVENT HEADER -> PREMISE -> CHOICES/FREE ACTION`

Battle:
`TEXT -> ACTION_MENU -> MOVE_MENU -> RESOLVE -> TEXT`

Posteriores:
`PARTY_MENU`, `BAG_MENU`, `TARGET_MENU`.

## Reglas de implementación

- POKEROL añade CSS/JS propios y conserva IDs técnicos `siza_*` mientras sean necesarios para compatibilidad.
- No editar el runtime TCG para imitar Pokémon.
- El battle client sólo presenta y manda intención; Evennia resuelve.
- Los sprites de especie pertenecen al Pokémon Creator/registry, no al CSS.
- Los fondos de batalla salen de `room.scene_image` o de un futuro `battle_scene_profile`.
