# 08 — Inventario técnico del SIZA World Engine

**Versión:** Core Freeze Candidate v1.01.1  
**Propósito:** mapa rápido de dónde vive cada responsabilidad en el repositorio.

## 1. Raíz del runtime

Directorio:

```text
siza-world-engine/
```

Archivos operativos principales:

### `README.md`

Entrada histórica de instalación/uso del piloto. La documentación maestra actual está en `documentos/world-engine/`.

### `requirements.txt`

Dependencias Python del runtime.

### `setup_windows.bat`

Setup inicial del entorno Windows/Evennia.

### `start_world_engine.bat`

Arranque del runtime.

### `stop_siza_world.bat`

Detención del runtime.

### `play_siza_world.bat`

Atajo de ejecución/entrada al entorno de juego.

### `qa_world_engine.bat`

Atajo histórico/operativo de QA.

### `update_world_engine.bat`

Actualiza el runtime local copiando/sincronizando el overlay actual del repositorio.

Comando recomendado por ruta absoluta:

```bat
"C:\Users\PC\Desktop\kendarte.github.io\siza-world-engine\update_world_engine.bat"
```

## 2. `overlay/`

Estructura:

```text
overlay/
├── commands/
├── services/
├── typeclasses/
└── world/
```

El overlay es la implementación que se copia al game dir/runtime de Evennia.

## 3. `overlay/typeclasses/`

### `characters.py`

Typeclass base de Character/Player para SIZA.

### `npcs.py`

Typeclass de NPC persistente y defaults relacionados con simulación.

### `rooms.py`

Room SIZA; presentation/state hooks del espacio.

### `exits.py`

Exit SIZA con validación/gating de traversal.

### `siza_objects.py`

Objeto interactuable base.

### `world_tick.py`

Script persistente global `SIZA_WORLD_TICK`. Orquesta reloj, jobs, events, needs, handoffs, arbitration, NPC actions y trace.

### `faction_registry.py`

Script/typeclass para registro persistente de facciones.

### `consequence_registry.py`

Registry persistente usado por authoring/consequences.

## 4. `overlay/services/` — Action y resolución

### `world_action_engine.py`

Autoridad de World Actions locales: authoring, eligibility, attempts, pending resolution, completion y emission de consequences.

### `action_requirement_engine.py`

Valida requirements duros de Actions, incluyendo Skills y Knowledge.

### `action_resolution_engine.py`

Contrato común de checks, Adventure Stats, modes/triggers, lifecycle e historial de resolución.

### `direct_d6_resolution_engine.py`

Provider DIRECT: `d6 + actor_stat >= difficulty`.

### `accumulate_d6_resolution_engine.py`

Provider ACCUMULATE con progreso persistente.

### `confront_d6_resolution_engine.py`

Provider CONFRONT stat-vs-stat.

### `synchronize_d6_resolution_engine.py`

Provider SYNCHRONIZE/paridad.

### `player_roll_resolution_engine.py`

Bridge/utilidades para resolución de rolls del Player.

## 5. `overlay/services/` — Objetos, estado y consecuencias

### `object_action_engine.py`

Lifecycle de Object Actions, historial, resolution y effects.

### `object_action_input_engine.py`

Matcher read-only/ejecutor de input contra Actions authored de objetos.

### `object_visibility_engine.py`

Visibilidad de objetos basada en estado.

### `state_effect_engine.py`

Aplicación determinista de state effects authored.

### `context_effect_engine.py`

Efectos/modificadores contextuales.

### `consequence_engine.py`

Consequences de Actions/eventos y recipients, incluyendo `SITE_NPCS`.

### `player_recipient_consequence_engine.py`

Consequences cuyo recipient es el Player.

### `exit_state_gate_engine.py`

Gating de Exits por estado persistente.

### `room_presentation_engine.py`

Presentación de Room derivada de world state.

## 6. `overlay/services/` — Skills, Traits y personality

### `skill_engine.py`

Skills persistentes y consulta/modificación.

### `trait_engine.py`

Traits persistentes.

### `decision_personality.py`

Aplica personality/context modifiers a decision candidates; no crea candidates nuevos por sí mismo.

## 7. `overlay/services/` — Percepción

### `perception_engine.py`

Autoridad base de percepción/observación.

### `deterministic_active_perception_engine.py`

Búsqueda activa determinista cuando el authoring define el hallazgo.

### `perception_knowledge_projection_engine.py`

Convierte discoveries autorizados en Knowledge/Facts.

### `perception_proposal_execution_bridge.py`

Bridge de proposal → perception.

### `active_perception_proposal_execution_bridge.py`

Bridge específico de búsqueda/percepción activa.

### `active_perception_proposal_runtime.py`

Runtime async para proposals de percepción activa.

## 8. `overlay/services/` — Knowledge y Facts

### `knowledge_context_engine.py`

Knowledge levels, `fact_knowledge_state()`, decision modifiers y lifecycle authority compartida desde v1.01.

### `knowledge_fact_engine.py`

Persistencia/upsert/remove/find de Facts y mutación de lifecycle ACTIVE/RETRACTED/SUPERSEDED.

### `knowledge_fact_retrieval_engine.py`

Retrieval determinista de Known Facts con relevance y budget; gate antes del LLM.

### `knowledge_fact_transfer_engine.py`

Transferencia local exacta de Fact entre holders, preservando provenance y agregando `transfer_history`.

### `player_knowledge_query_engine.py`

Consulta read-only de memoria del Player mediante lenguaje natural explícito.

## 9. `overlay/services/` — Facts → Goals/decisions

### `fact_goal_engine.py`

Materializa Fact-goals y desde v1.01 cancela/reactiva goals según lifecycle del Fact.

### `fact_goal_completion_engine.py`

Completion de Fact-goals mediante resultados/actions authored.

### `fact_driven_decision.py`

Wrapper que prepara Fact-goals y social/institutional Fact state antes de delegar a `npc_decision`.

## 10. `overlay/services/` — Relaciones e información social

### `relationship_engine.py`

Relationships, obligaciones `INFORM`/`SHARE_FACT`, candidates sociales y resolución por co-location.

### `information_engine.py`

Información basada en events/occurrences; sistema histórico de awareness/información.

### `semantic_fact_inform_engine.py`

Player→NPC INFORM semántico de Facts realmente conocidos.

### `conversation_fact_acquisition_engine.py`

NPC→Player Fact acquisition a través de TALK autorizado.

### `fact_share_rule_engine.py`

Autoridad v0.89–v0.99 de reglas sociales `SHARE_FACT`: source/target awareness, faction targets, authority, NEAREST, max targets, need-aware pruning y `HIGHER_THAN_SOURCE`.

### `fact_share_holder_acquisition_engine.py`

Gate v1.00 `ANY/NONTRANSFERRED/LOCAL_TRANSFER` antes del refresh social histórico.

## 11. `overlay/services/` — Facciones, autoridad e instituciones

### `faction_engine.py`

Faction registry, definitions, ranks, memberships, authority y loyalty context.

### `faction_fact_share_policy_engine.py`

Proyecta `fact_share_policies` institucionales en managed NPC rules. Incluye selector exact/type y severity filtering.

### `authority_order_engine.py`

Órdenes/authority institucional y metadata para goals ORDER.

### `shift_handoff.py`

Liberación/relevo de claims fuera de turno.

## 12. `overlay/services/` — NPC simulation y decisions

### `npc_simulation.py`

NPCs simulados, routines, movimiento paso a paso y `find_path` sobre la geometría real.

### `npc_decision.py`

Agregador/selector/ejecutor de decision candidates. Integra authored goals, events, needs, jobs, relationships y routine.

### `need_engine.py`

Genera NEED goals a partir de needs + rules + affordances de sitios.

### `need_dynamics.py`

Evolución de needs por tiempo y actividad.

### `job_engine.py`

Jobs/tasks, work progress, candidates y completion.

### `job_claims.py`

Claim, release y arbitration global de jobs.

### `world_event_engine.py`

World events/occurrences, candidates y acknowledgement.

### `world_clock.py`

Reloj persistente de simulación y schedules.

## 13. `overlay/services/` — Interaction, disclosure y dialogue

### `interaction_engine.py`

Parsing/ejecución de TALK e interacción semántica con NPC local.

### `ranked_fact_conversation_engine.py`

Selecciona un Fact concreto rankeado para TALK cuando múltiples Facts coinciden.

### `npc_fact_disclosure_engine.py`

Disclosure gate por familiarity.

### `npc_fact_disclosure_state_engine.py`

Disclosure holder-local condicionado por estado authored.

### `grounded_dialogue_renderer.py`

Render de diálogo basado en Fact/contexto autorizado.

### `dialogue_style_context_engine.py`

Contexto de estilo/persona para diálogo.

### `styled_grounded_dialogue_renderer.py`

Aplica estilo a diálogo grounded.

## 14. `overlay/services/` — Natural input y proposals

### `action_intent_proposal_engine.py`

Construye/valida proposals de capability cerrada.

### `action_proposal_async_runtime.py`

Runtime async para Ollama proposal.

### `action_proposal_execution_bridge.py`

Bridge proposal→authority ejecutable.

### `movement_proposal_execution_bridge.py`

Bridge de movimiento natural.

### `interaction_proposal_execution_bridge.py`

Bridge de interacción/TALK.

## 15. `overlay/services/` — Narración/Ollama

### `grounded_narration_context_engine.py`

Construye contexto de narración únicamente con estado/Facts autorizados.

### `perspective_narration_engine.py`

Aplica perspectiva sin cambiar truth set.

### `ollama_narration_provider.py`

Transport/provider local `/api/chat`; payload y error handling estructurado.

### `ollama_narrator.py`

Narrador que consume provider/contexto.

### `narration_queue.py`

Serialización/lock de trabajo de narración.

## 16. `overlay/commands/` — Familias funcionales

Los commands están versionados porque muchos fueron validators durante el crecimiento incremental. Para mantenimiento conviene pensar en familias, no memorizar cada archivo.

### Administración de sistemas

```text
action_resolution_commands.py
action_resolution_v39_commands.py
consequence_commands.py
context_effect_commands.py
decision_commands.py
event_commands.py
faction_commands.py
information_commands.py
job_commands.py
knowledge_commands.py
need_commands.py
order_commands.py
personality_commands.py
relationship_commands.py
skill_commands.py
time_commands.py
trace_commands.py
trait_commands.py
siza_commands.py
```

### Player rolls

```text
player_roll_v52_commands.py
player_roll_v53_commands.py
player_roll_v54_commands.py
player_roll_v55_commands.py
```

### World Actions

```text
world_action_commands.py
world_action_v42_commands.py
world_action_v43_commands.py
world_action_v44_commands.py
world_action_v46_commands.py
```

### Object/world validation chain

Familias:

```text
world_object_vXX_commands.py
world_presentation_vXX_commands.py
```

Contienen validators y herramientas del loop v0.47–v0.65+.

### Natural input chain

Familia:

```text
world_input_v68_commands.py
...
world_input_v101_commands.py
world_input_v1011_commands.py
```

Cada versión conserva/extiende contracts anteriores.

El `__nomatch__` actualmente registrado en `default_cmdsets.py` es:

```text
CmdSizaNoMatchV861
```

Ese command integra la cadena natural hasta ranked single-Fact TALK v0.86.1 y delega rutas previas según clasificación.

### QA

```text
qa_commands.py
```

Expone `CmdSizaQALatest` y el harness manual final de v1.01.

### `default_cmdsets.py`

Registra commands disponibles en Character/Account/etc. Es el punto para comprobar qué command versionado está efectivamente activo en gameplay.

## 17. `overlay/world/`

### `kalnaj_pilot.py`

Seed inicial de la micro-zona de Dársenas de Campana.

### `upgrade_pilot_vXX.py`

Cadena incremental de upgrades/fixtures del piloto.

Responsabilidad:

- crear/actualizar contenido de prueba;
- insertar Actions/Facts/Rules/Objects/NPC data necesarios para validators;
- mantener upgrades idempotentes cuando sea posible.

No responsabilidad:

- contener reglas globales de engine;
- sustituir services;
- definir el canon completo de Rivarica.

## 18. Directorio de documentación

```text
documentos/world-engine/
```

Archivos:

```text
README.md
01_arquitectura_y_principios.md
02_sistemas_implementados.md
03_modelos_de_datos_y_contratos.md
04_input_ia_y_narracion.md
05_qa_historial_y_operacion.md
06_tcg_combat_bridge.md
07_roadmap_simulation_framework.md
08_inventario_tecnico.md
```

Esta carpeta explica el sistema; `siza-world-engine/overlay/` sigue siendo la autoridad ejecutable.

## 19. Dónde buscar según el problema

### "Una acción no aparece / está bloqueada"

Mirar:

```text
world_action_engine.py
action_requirement_engine.py
object_action_engine.py / object_action_input_engine.py
```

### "Un check no resuelve bien"

```text
action_resolution_engine.py
<mode>_d6_resolution_engine.py
```

### "Una consecuencia no cambió el mundo"

```text
consequence_engine.py
state_effect_engine.py
player_recipient_consequence_engine.py
```

### "El Player/NPC no conoce o sigue conociendo algo"

```text
knowledge_context_engine.py
knowledge_fact_engine.py
knowledge_fact_retrieval_engine.py
```

### "Un NPC no fue a contar un Fact"

```text
fact_driven_decision.py
faction_fact_share_policy_engine.py
fact_share_holder_acquisition_engine.py
fact_share_rule_engine.py
relationship_engine.py
npc_decision.py
npc_simulation.py
```

### "El target de share es incorrecto"

```text
fact_share_rule_engine.py
faction_engine.py
npc_simulation.find_path
```

### "Una policy de facción no aparece"

```text
faction_engine.py
faction_fact_share_policy_engine.py
```

### "El NPC eligió otra cosa"

```text
npc_decision.py
decision_personality.py
trace_commands.py
world_tick.py
```

### "Un NPC está hambriento pero no va a resolverlo"

```text
need_engine.py
need_dynamics.py
npc_decision.py
```

### "Dos NPCs compiten por el mismo trabajo"

```text
job_engine.py
job_claims.py
shift_handoff.py
world_tick.py
```

### "El diálogo revela/no revela el Fact equivocado"

```text
ranked_fact_conversation_engine.py
npc_fact_disclosure_engine.py
npc_fact_disclosure_state_engine.py
conversation_fact_acquisition_engine.py
```

### "Qwen inventó/recibió información que no debía"

```text
knowledge_fact_retrieval_engine.py
grounded_narration_context_engine.py
ollama_narration_provider.py
```

Primero comprobar qué contexto recibió; no arreglar el prompt antes de verificar el privacy/authority boundary.

### "Input natural tomó una ruta equivocada"

```text
default_cmdsets.py
world_input_v861_commands.py
classify_v83_input y ancestors
proposal/bridge correspondiente
```

## 20. Regla para modificar un sistema cerrado

Antes de editar:

1. localizar authority file;
2. leer caller/wrapper que lo usa;
3. identificar validator cerrado más cercano;
4. hacer delta mínimo;
5. no mover lógica a otro service sólo por estética;
6. validar nueva propiedad;
7. correr regresión sólo donde cambió contrato;
8. actualizar esta documentación si el contrato cambió.

## 21. Regla especial para shared/core

Archivos de alto impacto actual:

```text
knowledge_context_engine.py
npc_decision.py
fact_share_rule_engine.py
relationship_engine.py
consequence_engine.py
npc_simulation.py
world_tick.py
```

Cambios allí requieren inspección de consumers y QA más ancho, porque muchas features convergen en esas autoridades.

## 22. Regla especial para wrappers

Cuando una feature nueva puede implementarse como gate/wrapper sin reescribir un core cerrado, esa opción suele ser preferible.

Ejemplos históricos:

```text
faction policy projection
→ managed local rules
→ reutiliza fact_share_rule_engine

holder acquisition
→ pre-social gate
→ reutiliza fact_share_rule_engine

fact-driven decision
→ prepara Facts/social
→ reutiliza npc_decision
```

Esto redujo regresiones y debe seguir siendo patrón cuando tenga sentido.
