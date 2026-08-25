# 04 — Input, IA y narración grounded

**Versión:** Core Freeze Candidate v1.01.1  
**Alcance:** routing de input natural, proposals, bridges de ejecución, diálogo y Ollama/Qwen.

## 1. Objetivo

SIZA quiere aceptar lenguaje natural sin convertir al LLM en Game Master autoritativo.

La arquitectura resuelve eso separando:

```text
1. clasificación/routing
2. proposal opcional
3. bridge determinista
4. mutación autorizada
5. narración grounded
```

La IA nunca recibe “haz lo que te parezca con el mundo”. Recibe contexto limitado y debe producir una propuesta que otro engine valida.

## 2. Precedencia general

A lo largo de v0.68–v0.86.1 se consolidó una precedencia para evitar que rutas deterministas sean secuestradas por el fallback AI.

Conceptualmente:

```text
input del Player
→ ¿es Action de objeto authored?
→ ¿es movimiento reconocible?
→ ¿es TALK explícito?
→ ¿es self Knowledge query?
→ ¿es perception/observe/search?
→ ¿es semantic INFORM?
→ ¿es inquiry grounded?
→ si queda ambiguo: AI_ACTION_PROPOSAL
```

La implementación histórica está distribuida entre commands versionados, pero el principio es estable: **lo determinista y explícito gana antes de pedir una propuesta al modelo**.

## 3. Object Action precedence

Desde v0.50 el input de Object Actions se intenta antes del legacy no-match.

Razón:

```text
"analizar manifiesto"
```

si corresponde a una Action authored, no debe llegar primero a un modelo que “interprete” otra cosa.

## 4. TALK precedence

Desde v0.74.1 el TALK explícito conserva precedencia.

Ejemplo:

```text
hablo con Mara sobre el manifiesto
```

se procesa como interacción con NPC local, no como pregunta general al narrador.

La versión actual del no-match mantiene ese contrato y, para conversación normal, usa autoridad de Fact rankeada v0.86.1.

## 5. Self Knowledge query

Desde v0.83 se reconocen preguntas explícitas de primera persona:

```text
¿Qué sé sobre X?
¿Qué sé de X?
¿Qué conozco sobre X?
¿Qué información tengo de X?
¿Qué datos tengo sobre X?
```

El parser normaliza el topic y genera un retrieval query filtrado.

Esta ruta:

- no usa Ollama;
- no muta estado;
- sólo recupera Facts que el Player realmente conoce y están ACTIVE;
- sanitiza la respuesta pública.

Respuesta con un Fact:

```text
<texto authored del Fact>
```

Sin Facts conocidos:

```text
No tienes información conocida sobre <topic>.
```

Con varios Facts relevantes, los presenta sin inventar una síntesis que añada causalidad nueva.

## 6. AI inquiry

Una pregunta general sobre el mundo puede entrar a inquiry grounded.

Ejemplo conceptual:

```text
¿Por qué hay una marca verde aquí?
```

no equivale a:

```text
¿Qué sé sobre la marca verde?
```

La primera puede usar narración grounded; la segunda es inspección determinista de memoria propia.

El provider sólo debe ver world context/Facts autorizados para el viewer.

## 7. Action proposals

`action_intent_proposal_engine.py` permite que el modelo elija entre capabilities cerradas.

Capacidades históricas principales:

```text
MOVE
TALK
OBSERVE
OBJECT_ACTION
```

El proposal recibe opciones construidas desde el estado actual, como:

- labels;
- aliases;
- target identity necesaria para el bridge;
- capability permitida.

No se le entrega una API genérica para mutar `db.*`.

## 8. Async proposal runtime

`action_proposal_async_runtime.py` evita bloquear el input principal mientras Ollama procesa una propuesta.

El resultado vuelve por callback a un handler que:

- inspecciona el packet;
- rechaza failure/malformed;
- llama al bridge correspondiente;
- emite fallback seguro si el provider falla.

La asincronía no cambia quién tiene autoridad.

## 9. Active perception proposal runtime

`active_perception_proposal_runtime.py` extiende el proposal flow para observación/búsqueda activa.

La IA puede ayudar a mapear una frase a una capability/target de percepción, pero el hallazgo final se resuelve por perception authority.

## 10. Bridges de ejecución

Los bridges separan “intent propuesto” de “acción ejecutable”.

### Movement bridge

`movement_proposal_execution_bridge.py` valida que el target de movimiento corresponda a una opción real y ejecuta movimiento autorizado.

### Interaction bridge

`interaction_proposal_execution_bridge.py` lleva TALK/interaction a `interaction_engine.py` y sus capas de disclosure/acquisition.

### Perception bridge

`perception_proposal_execution_bridge.py` resuelve observación sobre target válido.

### Active perception bridge

`active_perception_proposal_execution_bridge.py` conecta búsqueda activa con la autoridad determinista/perception correspondiente.

### Generic action bridge

`action_proposal_execution_bridge.py` ejecuta proposals de capability autorizada sin convertir la salida del modelo en mutación directa.

## 11. Interaction parsing

`interaction_engine.py` mantiene parsing de TALK y topic.

La interacción requiere target local/visible válido. Esto evita conversaciones remotas accidentales con NPCs sólo porque el nombre exista en base de datos.

## 12. Player → NPC INFORM

`semantic_fact_inform_engine.py` distingue una intención de compartir información propia.

Principio:

```text
Player sólo puede INFORM un Fact que realmente conoce.
```

La selección es semántica pero la transferencia final sigue ligada a identidad exacta y target local.

## 13. NPC → Player acquisition

`conversation_fact_acquisition_engine.py` permite que una conversación autorizada transfiera Fact al Player.

Se respeta:

- holder Knowledge;
- topic;
- disclosure;
- Fact seleccionado;
- target/actor local.

## 14. Ranked Fact conversation v0.86.1

Problema resuelto:

Un NPC puede tener varios Facts que coinciden con un topic. Elegir “el primero que aparece” puede revelar el Fact equivocado o hacer que una conversation cambie de autoridad al variar el orden de persistencia.

`ranked_fact_conversation_engine.py` selecciona una autoridad de Fact concreta antes de disclosure/acquisition.

El no-match actual usa esa capa para TALK normal.

## 15. Disclosure

### Public por default

Si un Fact no authored disclosure, la capa histórica v0.84 lo trata como público desde el punto de vista de ese gate específico.

### min_familiarity

Forma:

```python
"disclosure": {
    "min_familiarity": 2,
}
```

El NPC debe alcanzar familiarity suficiente con el actor.

### Malformed disclosure

Falla cerrado; no revela el Fact.

### Holder-local disclosure state

Desde v0.85 el permiso de un holder para divulgar un Fact puede depender de estado local adicional. El hecho de transferir un Fact no significa transferir automáticamente la misma política social de revelación.

## 16. Grounded dialogue

El diálogo se divide en tres autoridades:

```text
Fact selection / disclosure
→ qué información puede salir

style context
→ cómo habla ese NPC

renderer
→ texto final
```

`grounded_dialogue_renderer.py` produce texto grounded.

`dialogue_style_context_engine.py` construye rasgos de estilo.

`styled_grounded_dialogue_renderer.py` aplica ese estilo sin autorizar nuevos Facts.

## 17. Narration context

`grounded_narration_context_engine.py` construye el packet de narración desde:

- world state autorizado;
- perspectiva/viewer;
- Known Facts permitidos.

No se debe enviar el World Book entero o todos los Facts privados al modelo esperando que “se porte bien”.

## 18. Fact retrieval antes del LLM

`knowledge_fact_retrieval_engine.py` hace el privacy/knowledge gate **antes** de construir el contexto del provider.

Flujo:

```text
knowledge_facts(holder)
→ fact_knowledge_state
→ known?
→ relevancia
→ budget/max facts
→ selected context
```

Un Fact unknown/retracted/superseded no entra como known Fact al contexto.

## 19. Relevance

El retrieval usa señales deterministas como:

- exact `fact_id`;
- exact `knowledge_key`;
- token overlap;
- current site como bias de ranking.

La ubicación por sí sola no vuelve relevante un Fact semánticamente no relacionado cuando existe query no vacía.

## 20. Perspective narration

`perspective_narration_engine.py` permite adaptar lo narrado al punto de vista sin cambiar el conjunto de hechos autorizados.

Perspectiva y verdad no son la misma capa.

## 21. Ollama provider

Configuración actual del provider:

```text
endpoint default  http://127.0.0.1:11434/api/chat
model default     qwen3:8b
stream            false
think             false
temperature       0 por default
num_predict       192 por default del provider
```

Variables de entorno actuales relevantes:

```text
SIZA_OLLAMA_ENDPOINT
SIZA_OLLAMA_MODEL
```

El README histórico también documentó variables anteriores; el código actual del provider es la autoridad sobre nombres efectivos.

## 22. Payload de Ollama

El provider traduce un boundary grounded a:

```python
{
    "model": "qwen3:8b",
    "messages": [
        {"role": "system", "content": "..."},
        {"role": "user", "content": "..."},
    ],
    "stream": False,
    "think": False,
    "options": {
        "temperature": 0,
        "num_predict": 192,
    },
}
```

## 23. Error handling del provider

Estados estructurados incluyen, entre otros:

```text
OK
INVALID_ENCODING
INVALID_JSON
INVALID_RESPONSE
EMPTY_CONTENT
HTTP_ERROR
TIMEOUT
TRANSPORT_ERROR
```

El provider devuelve packet de error en vez de lanzar transport errors que rompan la simulación.

## 24. Regla ante Ollama caído

Una mutación determinista nunca debe depender de que la narración termine bien.

Ejemplo:

```text
Exit traversal autorizado
→ Character.location cambia
→ estado persiste
→ se intenta narración
→ Ollama falla
→ fallback visible
→ location NO se revierte
```

Lo mismo aplica conceptualmente a otras acciones ya autorizadas.

## 25. Narration queue

`narration_queue.py` usa una exclusión/lock para serializar trabajo de narración que podría competir por salida compartida.

No es un scheduler de gameplay; sólo protege el flujo de narración.

## 26. Qué puede proponer la IA y qué no

### Puede

- mapear lenguaje ambiguo a capability entre opciones existentes;
- elegir target entre candidates entregados;
- redactar texto grounded;
- formular una respuesta sobre hechos ya autorizados.

### No puede

- crear Rooms/Exits;
- teleportar;
- inventar inventario;
- subir stats;
- desbloquear Knowledge;
- transferir un Fact desconocido;
- modificar faction membership;
- fabricar una consecuencia;
- cambiar fact lifecycle;
- resolver un check sin provider;
- declarar ganador de combate TCG futuro.

## 27. Boundary de seguridad contra fabricación

Para toda integración nueva con LLM se debe preguntar:

```text
¿el modelo está eligiendo/redactando dentro de un set autorizado?
```

Si la respuesta es no y la salida puede cambiar estado, la arquitectura está rota.

## 28. No-match actual

La versión actual de `CmdSizaNoMatchV861` mantiene la cadena histórica y agrega TALK rankeado.

Comportamiento relevante:

- TALK explícito → ranked talk + disclosure + acquisition;
- AI_ACTION_PROPOSAL → async active perception/proposal runtime;
- otras rutas → delegan al comportamiento anterior.

Esto evita reescribir todos los parsers cada vez: las versiones nuevas envuelven y preservan contracts anteriores.

## 29. Recomendación para contenido final

Para reducir dependencia del LLM en SIZA final:

- authorar aliases buenos para Actions/Objects/Exits;
- usar topics/aliases en Facts;
- usar IDs estables;
- preferir self-query determinista para memoria;
- usar proposal AI sólo para lenguaje realmente abierto;
- mantener fallback legible.

Cuanto mejor sea el authoring semántico, menos decisiones críticas dependen de inferencia probabilística.

## 30. Integración futura con frontend

El frontend no debería consumir texto del LLM como estado.

Debe consumir packets/estado estructurado para:

- ubicación;
- actions disponibles;
- pending resolution;
- combat encounter futuro;
- Knowledge UI;
- NPC state visible;
- world state.

La prosa puede acompañar la UI, pero no ser su única fuente de verdad.
