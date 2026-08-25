# 02 — Sistemas implementados del SIZA World Engine

**Versión:** Core Freeze Candidate v1.01.1  
**Propósito:** referencia funcional de lo que existe hoy en código.

Este documento describe sistemas implementados. Cuando una capacidad no existe todavía se marca como futura y no se presenta como parte del runtime actual.

## 1. Mundo persistente y geometría

### Rooms

El mundo espacial se representa con Rooms Evennia persistentes. Cada Room puede tener identidad estable (`room_id`), descripción, estado y presentation rules.

La ubicación de un Character/NPC es estado real: `object.location`.

### Exits

Las conexiones son Exits reales con destino real. El movimiento válido debe atravesar un Exit o un path derivado del grafo de Exits.

Existe gating por estado de Exit. Esto permite puertas/bloqueos persistentes sin delegar la geometría a la IA.

### Room presentation

`room_presentation_engine.py` permite que la presentación visible cambie según state flags persistentes. La presentación no es la autoridad del estado: sólo lo refleja.

### Object visibility

`object_visibility_engine.py` permite objetos visibles/ocultos según estado. El patrón usado en el piloto es que una acción puede revelar un objeto persistente que después entra en el resto del sistema de Actions/Knowledge.

## 2. Estado persistente y efectos

### State effects

`state_effect_engine.py` aplica cambios authored de estado sin permitir mutaciones arbitrarias del LLM.

### Context effects

`context_effect_engine.py` permite modificadores derivados de contexto authored, usados principalmente para afectar decisión/prioridad sin reemplazar la regla base.

### Consequences

`consequence_engine.py` conecta outcomes autorizados con cambios persistentes.

Puede producir efectos sobre:

- actor/player;
- NPC específico;
- NPCs presentes en un sitio (`SITE_NPCS`);
- Knowledge/Facts;
- world state;
- objetos/estado derivado según reglas authored.

La introducción de `SITE_NPCS` permite que testigos físicamente presentes aprendan Facts como consecuencia de un evento sin elegirlos por nombre uno por uno.

### Consequence registry

Existe typeclass de registry persistente para reglas globales/authoring relacionado con consecuencias.

## 3. Skills, Traits y Adventure Stats

### Skills

`skill_engine.py` mantiene Skills persistentes y niveles/valores authored.

Las Actions pueden exigir Skill mínimo antes de entrar a resolución.

### Traits

`trait_engine.py` mantiene traits persistentes que pueden influir en comportamiento/authoring según la regla que los consuma.

### Adventure Stats

Los seis stats de aventura actuales son:

```text
FUE — Fuerza
AGI — Agilidad
COO — Coordinación
INT — Inteligencia
PER — Percepción
PSI — Psique
```

Los stats sólo existen si fueron authored/persistidos; un stat faltante no se interpreta automáticamente como cero para checks que lo requieren.

## 4. Action system

### World Actions

`world_action_engine.py` representa acciones del mundo con identidad authored.

Una Action puede definir:

- ID;
- nombre/aliases;
- disponibilidad;
- requisitos;
- target;
- check opcional;
- consecuencias/effects.

### Action requirements

`action_requirement_engine.py` valida gates antes de intentar la Action.

Se ha probado explícitamente la combinación Skill + Knowledge:

```text
Skill insuficiente
→ bloquea

Knowledge faltante
→ bloquea

Skill suficiente + Knowledge suficiente
→ Action elegible
→ sólo entonces entra al stat check si existe
```

Un requisito no se bypass-ea porque otro requisito sí esté satisfecho.

### Action lifecycle

El lifecycle separa intento de resolución:

```text
Action input
→ match authored
→ requirements
→ si no requiere check: ejecución/consequence
→ si requiere check: PENDING_RESOLUTION
→ provider calcula
→ resolve action
→ consequences
```

El historial de resolución es persistente y limitado para inspección.

## 5. Object Actions

`object_action_engine.py` y `object_action_input_engine.py` permiten acciones authored directamente sobre objetos.

Capacidades probadas:

- matching de frases naturales authored/aliases;
- gating por requisitos;
- creación de pending resolution;
- outcomes;
- efectos de estado del objeto;
- efectos persistentes en el mundo;
- generación de Knowledge/Facts;
- completion de goals mediante interacción con objeto.

Desde v0.50, el input de objeto authored tiene precedencia sobre el fallback genérico de input. Esto evita que una frase válida de gameplay sea interceptada por el LLM/no-match antes de comprobar la Action real.

## 6. Resolution system

### DIRECT

Fórmula actual:

```text
d6 + actor_stat >= difficulty
```

Outcomes:

```text
SUCCESS
FAILURE
```

### ACCUMULATE

Modo de progreso persistente. Un intento puede sumar avance hacia un goal authored en vez de resolver todo en una tirada.

Outcomes soportados por contrato:

```text
PROGRESS
SETBACK
COMPLETE
FAILURE
```

El progreso pertenece al intento/acción persistente correspondiente; no es memoria informal del LLM.

### CONFRONT

Oposición rápida stat-vs-stat.

Conceptualmente:

```text
d6 + actor_stat
vs
d6 + target_stat
```

Outcomes:

```text
ACTOR_WIN
TARGET_WIN
TIE
```

Este modo sirve para interrogatorios, forcejeos narrativos, disputas o checks competitivos que no justifican abrir el TCG.

### SYNCHRONIZE

Check de sincronía/paridad authored.

Outcomes:

```text
SYNC
MISS
```

El piloto utiliza una expectativa EVEN/ODD en metadata para probar la mecánica.

### Combat no es CONFRONT

El combate TCG futuro será otra clase de confrontación (`COMBAT_CONFRONTATION` a nivel de integración). No debe reemplazar el CONFRONT rápido ni incrustar reglas de cartas en este resolver.

## 7. Percepción

### Perception engine

`perception_engine.py` maneja percepción de entidades/datos visibles autorizados.

### Active perception

Existe búsqueda/observación activa para intentar descubrir información no entregada pasivamente.

### Deterministic active perception

`deterministic_active_perception_engine.py` permite resolución determinista de búsqueda activa cuando el contexto authored ya define qué se puede hallar.

### Perception → Knowledge

`perception_knowledge_projection_engine.py` proyecta descubrimientos autorizados a Knowledge/Facts persistentes.

El flujo esperado es:

```text
Player observa/busca
→ target/perception intent
→ authority de percepción
→ hallazgo autorizado
→ Knowledge/Fact
```

No:

```text
Player pregunta al LLM
→ LLM inventa pista
```

## 8. Knowledge levels

`knowledge_context_engine.py` mantiene niveles numéricos por `knowledge_key`.

Se usan para:

- Action requirements;
- decidir si un Fact asociado está realmente conocido;
- decision modifiers authored;
- adquisición/proyección;
- retrieval privado/seguro.

Un Fact no queda “conocido” sólo por estar almacenado: necesita su `knowledge_key` al nivel requerido y, desde v1.01, lifecycle ACTIVE.

## 9. Knowledge Facts

### Fact persistente

`knowledge_fact_engine.py` persiste Facts estructurados e idempotentes por `fact_id`.

Un Fact puede contener:

- topic;
- text/response;
- aliases;
- knowledge_key;
- required_level;
- source;
- learned_by;
- transfer_history;
- decision_effects;
- disclosure;
- fact_type;
- severity;
- lifecycle.

### Provenance

`source` y `learned_by` conservan el origen del conocimiento. Una transferencia social no debe reemplazar ese origen.

### transfer_history

Cada transferencia local añade un registro de hop con source/target/timestamp. Esto permite reconstruir la cadena social sin falsificar el origen inicial.

### Retrieval

`knowledge_fact_retrieval_engine.py` recupera sólo Facts que el holder conoce de verdad. El provider/narrador no recibe Facts privados desconocidos para luego “decidir no usarlos”; se filtran antes.

### Player self-query

`player_knowledge_query_engine.py` reconoce preguntas explícitas de primera persona como:

```text
¿Qué sé sobre la marca de arrastre verde?
¿Qué conozco de X?
¿Qué información tengo sobre Y?
```

La respuesta es determinista, read-only y no llama al LLM.

## 10. Fact lifecycle v1.01

Cada copia holder-local de un Fact puede estar en:

### ACTIVE

El Fact puede:

- aparecer en retrieval;
- groundear narración/dialogue;
- activar decision effects;
- activar Fact-goals;
- originar SHARE_FACT;
- transferirse.

### RETRACTED

El holder conserva:

- Fact almacenado;
- Knowledge level;
- provenance;
- lifecycle history.

Pero `known=False` para autoridades vivas. No puede groundear ni propagarse.

### SUPERSEDED

Igual que RETRACTED en uso vivo, pero exige `superseded_by_fact_id` para identificar el replacement.

### Holder-local

Cambiar lifecycle en un NPC no modifica mágicamente copias ya transferidas a otros holders. La corrección debe llegar a otros personajes por un mecanismo de juego/propagación si se desea.

## 11. Facts → decision effects

Un Fact puede llevar `decision_effects` explícitos. Sólo se aplican si el Fact está actualmente conocido/ACTIVE.

Esto permite que conocimiento real cambie prioridades sin permitir al LLM modificar la personalidad o decisión arbitrariamente.

## 12. Facts → Goals

`fact_goal_engine.py` materializa goals authored cuando el NPC conoce un Fact requerido.

`fact_goal_completion_engine.py` conecta completion de esos goals con acciones/objetos/resultados según reglas authored.

Desde v1.01:

- un Fact inactivo cancela goals derivados aún activos;
- cancellation reason: `SOURCE_FACT_NO_LONGER_ACTIVE`;
- reactivar el mismo Fact puede reactivar el mismo goal si fue cancelado sólo por lifecycle;
- goals one-shot ya completados permanecen terminales.

## 13. Información y memoria social temprana

`information_engine.py` maneja información derivada de eventos/ocurrencias y rutas de conocimiento anteriores al sistema de Facts sociales.

El Relationship engine mantiene también obligaciones `INFORM` para contar eventos conocidos.

Este sistema coexiste con `SHARE_FACT`; no debe confundirse una occurrence/event con un Knowledge Fact exacto.

## 14. Relationships

`relationship_engine.py` mantiene relaciones persistentes por target y obligaciones sociales.

Una obligación puede producir un candidate `RELATIONSHIP` para el decision engine.

Tipos relevantes:

- `INFORM` — informar sobre occurrence/event;
- `SHARE_FACT` — compartir un Fact exacto.

El NPC debe estar habilitado para decision para que `collect_relationship_candidates()` exponga candidates.

## 15. Fact transfer

`knowledge_fact_transfer_engine.py` exige co-location para transferencia local.

Reglas centrales:

- source debe conocer el Fact exacto;
- target y source deben estar físicamente juntos;
- se conserva source/learned_by original;
- se añade transfer history;
- se eleva Knowledge del target según el Fact;
- se emite evento/packet de Fact shared.

Un Fact RETRACTED/SUPERSEDED falla source-awareness y no se transfiere.

## 16. SHARE_FACT — reglas locales

`fact_share_rule_engine.py` convierte rules en obligaciones sociales útiles.

Capacidades acumuladas:

### v0.89 — materialización social

Fact conocido + rule → obligación `SHARE_FACT` → viaje/contacto → transferencia.

### v0.90 — target awareness

Si el target ya conoce el Fact exacto, no se crea viaje inútil y una rama pendiente puede retirarse.

### v0.91 — source awareness

Si source deja de conocer el Fact, se cancelan ramas pendientes.

### v0.92 — target_mode FACTION

Una rule puede apuntar a miembros activos de una facción.

### v0.93 — min_authority

Filtro opcional de autoridad de recipient.

### v0.94 — selection NEAREST / max_targets

Se usa `find_path` real. Ranking:

```text
menor path_length
→ mayor authority
→ npc_id estable
```

Un target unreachable se excluye.

### v0.95 — need-aware scarce slots

Para NEAREST limitado se eliminan primero recipients que ya conocen el Fact o ya completaron la obligación one-shot. Así `max_targets` se gasta sólo en quien todavía necesita el dato.

### v0.99 — authority_relation

`HIGHER_THAN_SOURCE` exige que el recipient tenga autoridad estrictamente mayor que el source en la facción correspondiente.

Esto permite cadenas ascendentes y evita relay lateral entre pares.

Valor default histórico: `ANY`.

## 17. Facciones

`faction_engine.py` mantiene un registry global persistente.

Una faction definition puede contener:

- id/name;
- active;
- ranks;
- metadata authored;
- policies adicionales como `fact_share_policies`.

### Ranks

Cada rank puede tener `authority_level` 0–1000.

### Memberships

Cada NPC puede tener múltiples memberships persistentes.

Campos relevantes:

- faction_id;
- active;
- loyalty_bias -100..100;
- rank_id/rank;
- role;
- authority_level override opcional.

### Loyalty

`loyalty_bias` no tiene una fórmula universal. Afecta contexto/prioridad de orders de esa facción cuando el sistema correspondiente lo consume.

## 18. Orders y authority

`authority_order_engine.py` produce órdenes institucionales/autoritativas que pueden entrar como goals `ORDER`.

Una orden puede conservar:

- authority id/name;
- faction;
- issuer;
- target/location;
- occurrence;
- prioridad.

La decisión del NPC integra ORDER junto con otras necesidades y obligaciones; no se ejecuta por teleport ni por intervención del LLM.

## 19. Faction Fact-share policies

`faction_fact_share_policy_engine.py` resuelve el problema de authoring a escala institucional.

### v0.96 — inheritance

Una faction definition puede tener `fact_share_policies` y sus miembros activos heredan rules managed.

ID exacto legacy:

```text
FACTION_POLICY:<faction_id>:<policy_id>
```

NPC-local rule para el mismo `fact_id` tiene override sobre la heredada.

Dos policies heredadas activas sobre el mismo Fact concreto fallan con conflicto en vez de elegir una silenciosamente.

### v0.97 — fact_type

Una policy puede seleccionar un `fact_type` en lugar de un `fact_id` exacto.

Se materializa una managed rule por Fact almacenado coincidente:

```text
FACTION_POLICY:<faction>:<policy>:FACT:<fact_id>
```

La transferencia final sigue siendo exacta.

Una policy con `fact_id` y `fact_type` simultáneos falla `AMBIGUOUS_FACT_SELECTOR`.

### v0.98 — severity

Sólo policies por `fact_type` pueden filtrar:

```text
min_severity
max_severity
```

Severity es entero no negativo authored en el Fact.

Rangos disjuntos permiten escalamiento institucional. Rangos que terminan gobernando el mismo Fact concreto producen conflicto; no existe precedencia implícita.

### v1.00 — holder_acquisition

Antes del refresh social se puede exigir:

```text
ANY
NONTRANSFERRED
LOCAL_TRANSFER
```

`LOCAL_TRANSFER` se determina únicamente por `transfer_history` DIRECT_LOCAL que tenga al holder actual como target.

No reescribe provenance.

## 20. Dialogue e Interaction

### Interaction engine

`interaction_engine.py` resuelve TALK e interacción semántica grounded con NPCs visibles/locales.

### Topic extraction

El input de conversación obtiene topic authored/derivado sin convertir cualquier interrogativo en una transferencia de información.

### Player → NPC INFORM

`semantic_fact_inform_engine.py` permite que el Player comparta un Fact que realmente conoce con un NPC local.

### NPC → Player acquisition

`conversation_fact_acquisition_engine.py` permite adquirir un Fact del NPC cuando la conversación autorizada lo entrega.

### Ranked Fact authority

`ranked_fact_conversation_engine.py` corrige la selección cuando varios Facts podrían responder a un topic: la conversación elige una autoridad/ranking determinista, no concatena indiscriminadamente secretos.

## 21. Fact disclosure

### Familiarity gate v0.84

`npc_fact_disclosure_engine.py` puede exigir `min_familiarity` para revelar un Fact.

La disclosure se evalúa antes de mutar TALK o transferir el Fact.

### Holder-local policy v0.85

`npc_fact_disclosure_state_engine.py` permite que la política de disclosure sea local al holder para no confundir el Fact compartido con el permiso de cada personaje para contarlo.

Puede requerir world/NPC state real, incluyendo resultados como la confrontación del piloto.

## 22. Grounded dialogue

`grounded_dialogue_renderer.py` renderiza respuestas usando Fact autorizado y contexto estructurado.

`dialogue_style_context_engine.py` construye contexto de estilo.

`styled_grounded_dialogue_renderer.py` aplica el estilo como renderer, no como permiso para inventar lore/estado.

Esto separa:

```text
qué puede decir el NPC
```

de:

```text
cómo lo dice
```

## 23. Personality

`decision_personality.py` aplica modificadores a priorities/candidates según personalidad/contexto authored.

La personalidad no elige una acción fuera del candidate set. Modifica preferencia entre posibilidades ya autorizadas.

## 24. Routines y NPC simulation

`npc_simulation.py` mantiene NPCs simulados, rutas y rutinas.

Capabilities:

- lookup de NPCs simulados;
- schedule de routine entries;
- movimiento paso a paso;
- `find_path` sobre Rooms/Exits;
- fallback cuando decision mode no está habilitado.

## 25. Needs

`need_engine.py` convierte estado interno + rules del NPC + affordances authored del mundo en goals NEED.

Ejemplo abstracto:

```text
hambre >= threshold
+ Room con affordance EAT
→ candidate NEED hacia esa Room
```

Al completar, sólo se aplican `completion_effects` authored en el affordance.

`need_dynamics.py` cambia necesidades por paso del tiempo y por actividad realizada.

## 26. Jobs

`job_engine.py` maneja work tasks persistentes y progreso.

`job_claims.py` resuelve ownership/claim de trabajo para evitar que varios NPCs actúen como si fueran dueños exclusivos del mismo task.

Capacidades:

- job candidates;
- work required/work done;
- claim/release;
- arbitration global antes del tick;
- completion effects;
- schedules/turnos según datos authored.

`shift_handoff.py` libera claims fuera de turno para permitir relevo.

## 27. World Events

`world_event_engine.py` produce events/occurrences persistentes y candidates derivados.

Los NPC pueden reconocer/acknowledge eventos al llegar al sitio correspondiente.

Event y Order se integran al decision engine como candidates, pero preservan metadata específica para completion/audit.

## 28. Decision engine

`npc_decision.py` reúne todos los candidates y elige por:

```text
reachable
→ effective_priority
→ path_length como desempate contextual
```

Cada candidate conserva source y metadata para que completion vuelva al engine correcto.

Sources principales:

```text
AUTHORED_GOAL
WORLD_EVENT
NPC_NEED
WORLD_JOB
RELATIONSHIP
ROUTINE_FALLBACK
```

El selected goal se copia a `current_goal` para inspección.

## 29. Natural input y intent proposals

La cadena v0.68–v0.78 introdujo routing natural guardado:

- preguntas fuertes → AI inquiry grounded;
- proposals estructurados;
- async runtime;
- movement bridge;
- semantic interaction;
- topic routing;
- perception;
- active search;
- discovery → Knowledge;
- determinismo para búsqueda activa cuando aplica.

Las capabilities de proposal históricamente autorizadas incluyen:

```text
MOVE
TALK
OBSERVE
OBJECT_ACTION
```

El LLM recibe opciones/targets, propone un intent, y el bridge vuelve a validar.

## 30. Ollama/Qwen

`ollama_narration_provider.py` usa el endpoint local `/api/chat` con modelo configurado (actualmente qwen3:8b por defecto).

Uso:

- redacción grounded;
- inquiry/proposal cuando la ruta lo permite.

No uso:

- autoridad geométrica;
- mutación directa;
- inventar Facts privados;
- resolver checks fuera del provider determinista;
- autorizar targets inexistentes.

`narration_queue.py` serializa/coordina narración asíncrona para evitar carreras simples de salida.

## 31. Grounded narration

`grounded_narration_context_engine.py` construye contexto desde estado autorizado y Known Facts.

`perspective_narration_engine.py` añade perspectiva sin cambiar qué Facts están autorizados.

`ollama_narrator.py` consume el packet y produce texto.

Si Ollama falla, la acción/movimiento ya resueltos permanecen resueltos; se usa fallback determinista donde corresponda.

## 32. Pilot loop v0.51–v0.63

El piloto de Pescadería demuestra una cadena completa de sistemas:

```text
Cajón sellado
→ abrir
→ manifiesto visible
→ DIRECT PER detecta duplicado
→ ACCUMULATE INT reconstruye secuencia
→ CONFRONT PSI presiona Informante
→ SYNCHRONIZE COO cruza sellos
→ DIRECT INT deduce ciclo
→ Knowledge
→ Fact semántico
→ Fact transfer
→ Fact goal
→ NPC movement
→ NPC→NPC share
→ goal secundario
→ object completion
→ Fact descubierto por NPC
```

El valor del piloto no es su historia específica; es demostrar que las primitivas pueden encadenarse sin script narrativo monolítico.

## 33. Loop institucional v0.89–v1.01

La segunda gran cadena prueba simulación social:

```text
World consequence
→ NPC recibe Fact
→ rule/policy detecta obligación
→ selecciona target útil
→ NPC viaja
→ comparte
→ recipient adquiere
→ recipient puede recibir policy propia
→ Fact escala jerárquicamente
→ top authority se detiene
→ Fact puede retractarse/supersederse holder-localmente
→ obligaciones/goals stale se cancelan
```

## 34. QA actual

`siza-qa-latest` apunta al validator relevante más reciente y sigue política risk-based.

Los validators deben:

- usar engines reales;
- controlar estado necesario;
- usar forced rolls sólo para determinismo de prueba;
- probar identidad, no sólo texto;
- restaurar estado exactamente;
- evitar asumir que un NPC no puede tener otra actividad no relacionada.

El detalle está en `05_qa_historial_y_operacion.md`.

## 35. Sistemas deliberadamente fuera del core actual

No están implementados como sistema general del World Engine:

- confidence/reliability de Facts;
- contradicciones epistemológicas;
- corroboración;
- secreto/clasificación institucional general;
- trust source→receiver sobre Facts;
- rumor degradation;
- freshness/expiry automática;
- jurisdicción institucional;
- workflows institucionales genéricos multi-step;
- causal replay completo;
- optimización de escala masiva;
- authoring/debug UI avanzada;
- bridge de combate TCG.

Los primeros once pertenecen al roadmap opcional del simulation framework. El último pertenece a integración World Engine↔TCG del juego.
