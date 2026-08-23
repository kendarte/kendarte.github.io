# 25. EJEMPLO COMPLETO: del pueblo a una interacción

Supongamos un pueblo costero de Caribia. El perfil de asentamiento genera un Distrito del Puerto con Plaza, Muelle, Pescadería I, almacén y Puesto de Guardia. La Pescadería instancia su blueprint y queda conectada a la calle principal y a un callejón de servicio.

```text
ZONE: PUERTO

PLAZA-01 ---- STREET-02 ---- MUELLE-01
                   |
               ENTER
                   v
           FISH-03-ENTRANCE
                   |
             FISH-03-COUNTER
              /          \
     FISH-03-CUT       FISH-03-OFFICE
          |
    FISH-03-COLD
          |
    FISH-03-YARD ---- SERVICE_EXIT ---- ALLEY-04
```

Nereida está en STREET-02. Escribe “entro a la pescadería”. El parser encuentra el Exit ENTER y la mueve a FISH-03-ENTRANCE. La descripción base muestra el mostrador, olor evidente, empleados presentes y Exits visibles. Si escribe “miro detrás del mostrador”, eso no cambia de Room; es una acción de percepción sobre objetos/espacio visible. Si escribe “paso detrás del mostrador”, el motor busca un Exit o relación de acceso entre COUNTER público y CUT de trabajo; puede existir pero estar restringido. El conflicto nace de una geometría ya definida.

Más tarde un incendio destruye la puerta al patio. El World State cambia el objeto puerta y el Exit; la pescadería continúa siendo la misma Structure Instance. Al regresar, el jugador encuentra el mismo grafo, modificado por consecuencias persistentes. Ésa es la diferencia entre un MUD espacial y una escena improvisada.

# 26. Relación con los otros documentos de Siza

| Documento | Responsabilidad |
| --- | --- |
| World Book | Define canon: geografía, cultura, estructuras posibles, instituciones, economía, historia. |
| Sistema de Espacio Físico y Mapas | Define dónde existen las cosas y cómo se conectan físicamente. |
| Sistema de Mundo Persistente | Define generación de asentamientos, edificios, facciones, economía y estados macro. |
| Sistema Player/NPC | Define qué puede, sabe, quiere y recuerda cada persona. |
| Tech Trees de facciones | Define qué estructuras puede producir/controlar cada facción y sus requisitos. |
| Master IA | Interpreta input, consulta los sistemas y narra resultados sin reemplazarlos. |

# 27. Orden de implementación recomendado

1. Definir los esquemas ROOM, EXIT, ZONE, DOOR y MAP_STATE.
2. Construir un automapper/debugger capaz de mostrar un grafo pequeño y current_room.
3. Hacer movimiento manual Room por Room sin IA.
4. Añadir puertas, bloqueos, one-way exits, pisos y pathfinding.
5. Añadir Player Discovery y mapa visible derivado.
6. Implementar un solo Structure Blueprint completo (Pescadería I) y conectarlo a un pequeño distrito.
7. Hacer que un NPC recorra el mismo grafo mediante rutina.
8. Conectar el parser de lenguaje natural a MOVE/INTERACT sin permitir mutación directa de posición por Qwen.
9. Añadir Spatial Context Window para narración.
10. Recién después escalar a generador de pueblos y catálogos completos de estructuras.

# 28. Criterios de aceptación del sistema espacial

- Es posible cerrar Qwen y seguir moviendo al jugador por el mapa mediante comandos estructurados.
- current_room siempre tiene un valor válido para jugador y NPC activos.
- “voy a mi recámara” sólo funciona si existe una recámara asociada y una ruta válida.
- Un NPC no aparece en una Room incompatible con su ruta/estado.
- Una puerta cerrada impide atravesar el Exit hasta que su estado cambie.
- Un Exit secreto puede existir sin aparecer en el mapa del jugador.
- Una estructura conserva las mismas Rooms al volver a visitarla salvo modificación persistente explícita.
- El mapa visible puede reconstruirse únicamente desde Player Discovery.
- El pathfinder responde a bloqueos persistentes y busca rutas alternativas.
- Qwen puede narrar con riqueza sin recibir permiso para inventar geometría.

# 29. Contratos de datos mínimos

## 29.1 ZONE

```text
ZONE {
  id
  parent_id
  type
  name
  settlement_id
  structure_id?
  level_range?
  room_ids[]
  context_tags[]
}
```

## 29.2 ROOM

```text
ROOM {
  id
  zone_id
  structure_id?
  name
  type
  level
  base_description
  geometry_tags[]
  exit_ids[]
  object_ids[]
  environment_defaults{}
  sensory_layers[]
  discovery_policy{}
}
```

## 29.3 EXIT

```text
EXIT {
  id
  from_room
  to_room
  direction
  bidirectional
  mode
  travel_cost
  door_id?
  requirements[]
  visibility
  hazard?
  capacity?
}
```

## 29.4 SPATIAL STATE

```text
SPATIAL_STATE {
  room_state{}
  exit_state{}
  door_state{}
  object_locations{}
  entity_locations{}
  temporary_blockers{}
}
```

## 29.5 PLAYER DISCOVERY

```text
PLAYER_MAP {
  visited_rooms[]
  known_rooms[]
  known_exits[]
  rumored_locations[]
  discovered_secret_exits[]
  mapped_zones[]
}
```

# 30. Regla final

> **Siza no pregunta a la IA “¿dónde estamos?”. El motor espacial ya lo sabe. La IA recibe esa respuesta y la convierte en experiencia.**

Una vez congelado este sistema, diseñar ciudades deja de significar escribir listas de lugares. Significa construir grafos persistentes a partir de estructuras funcionales. Esa base permite después integrar facciones, economía, Sims/NPC, percepción, quests, combate y eventos sin que cada sistema invente su propia versión del espacio.
