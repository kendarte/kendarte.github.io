# SIZA World Engine — Documentación Maestra v1.01

**Estado:** núcleo funcional completo; QA automático de v1.01 cerrado; aceptación manual player-facing de lifecycle pendiente antes del freeze formal.  
**Repositorio de implementación:** `siza-world-engine/`  
**Área de documentación pública:** `projects/siza/documentos/`  
**Principio rector:** **Acción y Consecuencia**.

---

## 1. Qué es el SIZA World Engine

El SIZA World Engine es el motor de simulación persistente que convierte el canon de Rivarica en un mundo MUD jugable, consultable y modificable por acciones. Su función no es escribir una historia lineal ni delegar el mundo a una IA generativa. Su función es mantener una **realidad de juego determinista**, persistente y auditable sobre la cual pueden operar el jugador, los NPC, las facciones, los eventos y el Master IA.

La idea base puede resumirse así:

```text
WORLD STATE
    ↓
PLAYER / NPC ACTION
    ↓
REQUIREMENTS + RESOLUTION
    ↓
CONSEQUENCE
    ↓
PERSISTENT WORLD MUTATION
    ↓
FACTS / KNOWLEDGE
    ↓
NPC GOALS / SOCIAL PROPAGATION / INSTITUTIONAL REACTION
    ↓
NEW WORLD STATE
```

El motor existe para que una acción concreta pueda producir una cadena causal durable. Si el jugador abre una puerta, investiga un manifiesto, presiona a un informante, agrede a una persona o revela una información, el resultado no debe existir solo como texto: debe quedar representado en estado persistente y poder ser utilizado posteriormente por otros sistemas.

---

## 2. Qué NO es el World Engine

El World Engine no es:

- un chatbot que improvisa el estado del mundo;
- un generador de quests sin autoridad determinista;
- el sistema TCG;
- el cliente visual definitivo;
- el World Book de Rivarica;
- una base de datos de lore sin mecánicas;
- un sistema que permite que Ollama/Qwen modifique objetos, Facts, estados o NPC directamente.

El World Book define **qué es verdad en Rivarica**. El World Engine define **cómo esas verdades se vuelven espacio, entidades, reglas, acciones, conocimiento, decisiones y consecuencias persistentes**.

---

## 3. Regla de autoridad: el LLM nunca es el mundo

SIZA usa IA local para interpretación lingüística, narración y propuestas, pero la IA no posee autoridad para mutar el mundo.

La separación es deliberada:

```text
Jugador escribe lenguaje natural
        ↓
Parser / proposal / retrieval
        ↓
LLM puede interpretar o proponer
        ↓
Deterministic bridge valida
        ↓
World Engine decide si existe una acción legal
        ↓
World Engine muta estado
```

### 3.1 Ollama / Qwen

Configuración de desarrollo actual:

- Ollama local.
- Modelo: `qwen3:8b`.
- Endpoint: `http://127.0.0.1:11434/api/chat`.
- `stream=false`.
- `think=false`.
- temperatura baja / determinista para las rutas donde se utiliza.

### 3.2 Principios de seguridad epistemológica

El proveedor de IA solo recibe información autorizada por los engines de retrieval. Un Fact privado o desconocido no debe llegar al prompt para después “pedirle” al modelo que no lo mencione. La privacidad se resuelve **antes del prompt**.

La IA puede:

- reformular una respuesta;
- narrar contexto conocido;
- clasificar una intención;
- proponer un movimiento, conversación, observación o acción de objeto dentro de capacidades autorizadas.

La IA no puede:

- crear conocimiento persistente por afirmación propia;
- mover directamente un NPC;
- abrir una puerta;
- cambiar un requisito;
- decidir el resultado de una tirada;
- fabricar un Fact canónico;
- modificar estados persistentes.

---

# PARTE I — ESPACIO Y ESTADO DEL MUNDO

## 4. Modelo espacial MUD

SIZA usa una estructura espacial persistente inspirada en MUD/ZMUD. El mundo no es una lista abstracta de escenas. Está compuesto por Rooms conectados mediante Exits.

La escala conceptual es una matrioska:

```text
Rivarica
→ Provincia
→ Isla / región
→ Asentamiento
→ Distrito / zona
→ Estructura
→ Interior
→ Room
```

Cada Room puede contener:

- descripción;
- NPC;
- objetos;
- exits;
- estado local;
- información perceptible;
- acciones disponibles;
- referencias de facción, trabajo, evento u otros sistemas.

### 4.1 Rooms y Exits persistentes

El movimiento real ocurre Room por Room. Los Exits pueden depender del estado del mundo.

Ejemplo del piloto:

```text
Pescadería de Dársena
→ entrar a la trastienda
```

El exit puede existir físicamente pero estar bloqueado hasta que una acción persistente cambie la condición correspondiente.

### 4.2 Presentación derivada del estado

Desde v0.45 la presentación del Room puede variar por `world_state`. El texto visible no debe ser una ficción desconectada del backend: puede reflejar objetos abiertos, estados descubiertos, condiciones físicas y consecuencias previas.

### 4.3 Exits derivados del estado

Desde v0.46 los exits pueden aparecer, desaparecer, habilitarse o quedar bloqueados según estado persistente.

### 4.4 Objetos temporales persistentes

Desde v0.47 una consecuencia puede crear objetos temporales con identidad persistente. Estos objetos pueden participar posteriormente en acciones authored.

---

## 5. World State

`world_state` representa hechos físicos o lógicos que pertenecen al mundo y no a la narración.

Ejemplos conceptuales:

```text
puerta_trastienda_abierta = true
manifiesto_duplicado_detectado = true
cajon_abierto = true
nivel_busqueda = 3
incendio_activo = false
```

El estado puede:

- habilitar acciones;
- bloquear acciones;
- alterar presentación;
- alterar exits;
- crear consecuencias;
- alimentar eventos posteriores.

La regla es: **si una consecuencia debe importar después, no debe existir únicamente como prosa**.

---

# PARTE II — PLAYER, STATS Y RESOLUCIÓN

## 6. Parámetros base

El World Engine utiliza seis parámetros de aventura:

- **FUE** — Fuerza.
- **AGI** — Agilidad.
- **COO** — Coordinación.
- **INT** — Inteligencia.
- **PER** — Percepción.
- **PSI** — Psique.

SIZA mantiene separado el set de stats de aventura del set que utilizará el TCG.

---

## 7. Tipos de resolución

El motor cerró cuatro familias de resolución determinista.

### 7.1 DIRECT

```text
d6 + stat vs dificultad
```

Sirve para una acción puntual con resultado inmediato.

Ejemplo del piloto:

```text
analizar manifiesto
PER vs dificultad 7
```

### 7.2 ACCUMULATE

Usa la misma lógica básica de tirada, pero el progreso queda persistente y puede requerir varios éxitos o acumulación hasta alcanzar una meta.

Ejemplo:

```text
reconstruir secuencia del manifiesto
INT vs dificultad
objetivo acumulado = 2
```

### 7.3 CONFRONT

```text
d6 + stat actor
vs
d6 + stat target
```

Se utiliza para conflictos de atributo contra atributo: presión, resistencia, forcejeo, intimidación y otras confrontaciones narrativas deterministas.

**Importante:** este `CONFRONT` no es el TCG. Es una resolución rápida stat-vs-stat dentro del World Engine.

### 7.4 SYNCHRONIZE

Tirada basada en sincronía/paridad con un stat authored:

```text
(d6 + stat) → EVEN / ODD
```

Sirve para acciones donde importa coincidir con un patrón, ritmo, ventana o sincronización.

---

## 8. Action lifecycle

Desde v0.39 una acción no es una función opaca. Tiene un ciclo explícito:

```text
ACTION
→ requirements
→ attempt
→ resolution
→ outcome
→ consequence
→ persistent state
```

El lifecycle conserva información suficiente para depuración y auditoría.

### 8.1 Requirements

Una acción puede exigir:

- stat;
- Skill;
- Knowledge;
- objeto;
- estado;
- contexto espacial;
- otras precondiciones authored.

Desde v0.42 los requisitos Skill + Knowledge son gates reales. Tener un stat alto no permite saltarse conocimiento o habilidad authored.

### 8.2 Acciones bloqueadas siguen siendo inspeccionables

Una acción authored puede mantenerse visible para debug aunque sea inelegible, exponiendo blockers claros como:

```text
SKILL
KNOWLEDGE
STATE
```

### 8.3 Consequence authority

Desde v0.43 una resolución exitosa puede disparar consecuencias que mutan persistentemente `world_state`.

Desde v0.44 ese estado puede ser requisito de otras acciones, formando cadenas causales authored.

---

# PARTE III — OBJETOS E INPUT NATURAL

## 9. Object Actions

Desde v0.48 los objetos pueden poseer acciones authored propias.

Una acción de objeto puede contener:

- id estable;
- aliases / lenguaje aceptado;
- requirements;
- tipo de resolución;
- difficulty;
- stat;
- consequence;
- Knowledge producido;
- Facts producidos;
- estados modificados.

Desde v0.49 las consecuencias pueden dirigirse a objetos por identidad exacta.

Desde v0.50 el input authored de objetos tiene precedencia sobre el fallback genérico de puerta/no-match.

---

## 10. Natural input routing

El World Engine acepta frases naturales, pero las enruta hacia autoridades distintas.

Rutas importantes cerradas durante v0.68–v0.83:

```text
MOVEMENT
TALK / INTERACTION
PERCEPTION
OBJECT_ACTION
AI_INQUIRY
KNOWLEDGE_QUERY
```

### 10.1 Guarded natural input

No toda frase se envía a Ollama. El sistema intenta resolver primero rutas deterministas.

### 10.2 Proposal Engine

Cuando una frase requiere interpretación, la IA puede proponer una capacidad dentro de un conjunto autorizado:

- MOVE;
- TALK;
- OBSERVE;
- OBJECT_ACTION.

La propuesta no muta nada. El bridge determinista valida y ejecuta únicamente capacidades existentes.

### 10.3 Explicit TALK precedence

Una frase explícita de conversación tiene prioridad sobre una interpretación general de IA.

### 10.4 Player Knowledge Query

Desde v0.83 preguntas explícitas de primera persona como:

```text
¿Qué sé sobre la marca de arrastre verde?
```

usan retrieval determinista y **no llaman a Ollama**.

La respuesta pública expone únicamente el texto autorizado, no IDs internos, `knowledge_key`, provenance ni metadata privada.

---

# PARTE IV — PERCEPCIÓN Y DESCUBRIMIENTO

## 11. Perception

El World Engine distingue entre descripción pasiva y búsqueda/observación activa.

La percepción puede:

- consultar elementos visibles;
- realizar una acción authored;
- exigir PER u otro stat;
- descubrir información;
- generar Knowledge persistente.

### 11.1 Active Search

Desde v0.76 existe búsqueda activa como capacidad diferenciada.

### 11.2 Discovery → Knowledge

Desde v0.77 un descubrimiento puede elevar Knowledge real. Esto evita que una descripción narrativa quede desconectada de lo que el personaje mecánicamente sabe.

### 11.3 Deterministic parity

Desde v0.78 se validó paridad entre percepción activa y estado determinista del sistema.

---

# PARTE V — KNOWLEDGE Y FACTS

## 12. Diferencia entre Knowledge y Fact

### Knowledge

Es una capacidad, competencia o nivel de conocimiento representado normalmente mediante una clave y nivel:

```text
V057_DUPLICATE_SHIFT_LINK = 1
```

Sirve como requisito y como autoridad mecánica.

### Fact

Es una unidad semántica concreta de información persistente:

```text
FACT-PESCADERIA-DUPLICADO-RELEVO-001
```

Puede contener:

- `id`;
- `topic`;
- `text`;
- `aliases`;
- `knowledge_key`;
- `required_level`;
- source;
- learned_by;
- transfer_history;
- disclosure;
- decision_effects;
- fact_type;
- severity;
- lifecycle.

La combinación Knowledge + Fact permite responder tanto “¿tiene la capacidad de saber esto?” como “¿qué información concreta conoce?”.

---

## 13. Persistent Knowledge Facts

Desde v0.57 los Facts son persistentes y semánticos.

Ejemplo del piloto:

```text
FACT-PESCADERIA-DUPLICADO-RELEVO-001
```

Texto conceptual:

> La segunda anotación duplicada del manifiesto fue procesada durante el relevo de cierre de la dársena.

Un Fact conserva provenance y puede generar reglas posteriores.

---

## 14. Fact Retrieval

Desde v0.64.1 la recuperación de Facts conocidos es determinista.

Orden general:

```text
holder tiene Fact almacenado
→ fact_knowledge_state dice si está usable
→ query/topic determina relevancia
→ site puede actuar como bias de ranking
→ budget / max facts
→ contexto autorizado
```

La localización no vuelve relevante un Fact semánticamente ajeno. Solo puede influir en ranking entre Facts ya relevantes.

---

## 15. Grounded narration

El narrador recibe únicamente:

```text
WORLD STATE
KNOWN FACTS
```

No debe recibir private Facts desconocidos.

Esta arquitectura evita dos fallos clásicos:

1. que el modelo invente estado persistente;
2. que el modelo filtre información que nunca debió entrar al prompt.

---

## 16. Fact lifecycle — v1.01

Antes de v1.01, un Fact almacenado podía seguir siendo considerado vigente indefinidamente. v1.01 introduce lifecycle holder-local.

Estados:

```text
ACTIVE
RETRACTED
SUPERSEDED
```

### ACTIVE

El Fact está almacenado y usable.

### RETRACTED

El holder conserva memoria histórica y Knowledge level, pero el Fact deja de ser autoridad viva.

### SUPERSEDED

El Fact se conserva como registro histórico pero fue sustituido por otro Fact identificado mediante `superseded_by_fact_id`.

### 16.1 `level_known` vs `known`

v1.01 diferencia:

```text
level_known = True
```

El holder tiene el nivel de Knowledge asociado.

```text
known = True
```

El Knowledge level alcanza el requisito **y** el Fact está `ACTIVE`.

Un Fact retractado puede tener `level_known=True` y `known=False`.

### 16.2 Efecto transversal del lifecycle

Los siguientes sistemas consultan la autoridad común `fact_knowledge_state()`:

- retrieval;
- grounding para LLM;
- disclosure;
- decision effects;
- Fact-goals;
- SHARE_FACT;
- transfer.

Por eso un Fact retractado deja de alimentar estos sistemas sin ser borrado de la memoria histórica.

### 16.3 Lifecycle holder-local

Retraer la copia de un Fact en Mara no modifica mágicamente una copia que ya fue transferida a otro NPC.

Cada holder mantiene su propio estado epistemológico.

---

# PARTE VI — DIÁLOGO Y DISCLOSURE

## 17. Grounded Dialogue

Desde v0.81 las respuestas de conversación pueden utilizar Facts reales del NPC.

Un NPC no debe revelar información solo porque su texto de lore la mencione. La respuesta se deriva de lo que el NPC conoce de manera autorizada.

### 17.1 Style Renderer

v0.82 añadió contexto de estilo y v0.82.1 impuso un renderer de estilo para separar:

- contenido factual;
- forma de hablar.

El estilo no puede fabricar Facts nuevos.

---

## 18. Fact Disclosure

Desde v0.84 un Fact puede incluir política de disclosure basada en familiarity.

Ejemplo conceptual:

```python
"disclosure": {
    "min_familiarity": 3
}
```

El gate ocurre **antes** de que TALK pueda mutar o revelar el contenido.

### 18.1 Holder-local disclosure policy

v0.85 permitió restricciones locales del holder, de modo que dos NPC que poseen el mismo Fact pueden tener políticas de revelación distintas.

Las condiciones pueden utilizar estados ya demostrados por acciones anteriores, por ejemplo una confrontación específica.

---

# PARTE VII — FACT TRANSFER Y SOCIAL INFORMATION

## 19. Transferencia de Fact

Desde v0.58 un Fact puede transferirse entre Character/NPC.

Autoridad actual del transfer directo:

- source y target deben estar co-localizados;
- source debe conocer el Fact exacto y tenerlo `ACTIVE`;
- se conserva la provenance original;
- se agrega `transfer_history`;
- se eleva el Knowledge requerido en el receptor;
- se emite un evento `KNOWLEDGE_FACT_SHARED`.

Ejemplo de historial:

```text
Informante C
→ Mara
→ Trabajador B
```

Cada hop queda registrado con source, target, modo y timestamp.

---

## 20. Player → NPC INFORM

v0.79.1 cerró la transferencia semántica desde el jugador hacia un NPC.

## 21. NPC → Player acquisition

v0.80 cerró la adquisición exacta de Fact desde NPC hacia jugador.

La conversación y la transferencia no son simplemente texto: pueden producir estado epistemológico persistente.

---

# PARTE VIII — NPC AUTONOMY

## 22. NPC decision model

Los NPC pueden tener:

- goals;
- current goal;
- priority;
- actividad;
- destination;
- Knowledge;
- relationships;
- faction membership;
- job;
- traits/personality;
- needs;
- orders;
- social obligations.

El decision engine selecciona una actividad válida a partir de estado persistente.

---

## 23. Fact-driven goals

Desde v0.59 un Fact conocido puede materializar un goal authored una sola vez.

Ejemplo:

```text
NPC aprende FACT-X
→ rule FACT_GOAL-X
→ goal: ir a Cantina
```

### 23.1 One-shot semantics

Un goal completado normalmente no se reactiva automáticamente.

### 23.2 Lifecycle-aware goals

Desde v1.01, si un goal todavía está activo y su Fact fuente pasa a `RETRACTED` o `SUPERSEDED`, se cancela con:

```text
SOURCE_FACT_NO_LONGER_ACTIVE
```

Solo un goal cancelado específicamente por lifecycle puede reactivarse si el mismo Fact vuelve a `ACTIVE`. Un goal completado sigue siendo terminal.

---

## 24. Autonomous movement

Un goal puede hacer que un NPC busque un destino y se mueva por el grafo real de Rooms.

Desde v0.72 el bridge de propuestas soporta movimiento; desde las fases posteriores los social goals también usan pathfinding real.

El motor no “teletransporta” socialmente la información: cuando una obligación requiere contacto, el NPC debe llegar físicamente al target.

---

## 25. Relationships

El relationship engine mantiene relaciones y obligaciones sociales persistentes.

Tipos relevantes:

- INFORM;
- SHARE_FACT;
- familiarity y otras propiedades sociales existentes.

Una obligación social puede convertirse en candidate del decision engine siempre que:

- esté activa;
- el NPC tenga decisiones habilitadas;
- el target exista;
- la obligación continúe siendo epistemológicamente válida.

---

# PARTE IX — FACTIONS E INSTITUCIONES

## 26. Faction Engine

Las facciones poseen definición persistente y los NPC pueden tener memberships con metadata como:

- `faction_id`;
- active;
- role;
- rank_id;
- authority_level;
- loyalty_bias.

La autoridad permite construir cadenas institucionales sin hard-codear cada NPC.

---

## 27. Fact Share Rules — v0.89 a v0.95

Esta fase convirtió la información social en comportamiento persistente.

### v0.89 — Fact-driven social share

Un Fact conocido puede generar una obligación `SHARE_FACT` hacia un target. El NPC puede desplazarse, hacer contacto y transferir el Fact.

### v0.90 — Target awareness

Si el target ya conoce el Fact exacto, la obligación deja de ser útil y se retira.

### v0.91 — Source awareness

Si el source deja de conocer el Fact, la obligación pendiente se cancela.

### v0.92 — FACTION targets

Una rule puede dirigirse a miembros activos de una facción en vez de un NPC explícito.

### v0.93 — `min_authority`

Los targets pueden filtrarse por autoridad mínima.

### v0.94 — `selection=NEAREST`

El engine puede elegir un número limitado de destinatarios alcanzables usando pathfinding real.

Ranking:

1. menor path length;
2. mayor authority;
3. `npc_id` estable como tie-break.

### v0.95 — Need-aware limited selection

Antes de consumir `max_targets`, se eliminan:

- recipients que ya conocen el Fact;
- recipients cuyo one-shot ya está completado.

Esto evita gastar slots escasos en destinatarios inútiles.

---

## 28. Faction-level Fact Share Policies — v0.96

v0.96 resolvió el problema de authoring institucional. Ya no es necesario duplicar la misma rule en cada guardia o trabajador.

La faction definition puede contener:

```python
"fact_share_policies": [
    {
        "id": "REPORTAR_INCIDENTE",
        "fact_id": "FACT-X",
        "target_mode": "FACTION",
        "min_authority": 500,
        "selection": "NEAREST",
        "max_targets": 1
    }
]
```

La policy se proyecta en managed rules locales para miembros activos.

Propiedades importantes:

- rule IDs namespaced y estables;
- salir de la facción elimina la rule heredada;
- remover la policy cancela la intención pendiente;
- reentrar puede reutilizar la misma obligation identity;
- una rule NPC-local para el mismo Fact hace override;
- múltiples policies heredadas que compiten por el mismo Fact fallan cerrado.

---

## 29. Fact Type Policies — v0.97

Para evitar una policy por Fact individual, un Fact puede incluir:

```text
fact_type = SECURITY_INCIDENT
```

Una policy puede seleccionar por tipo:

```text
fact_type = SECURITY_INCIDENT
```

El engine expande la policy a una managed rule por `fact_id` concreto. La transferencia continúa siendo exacta; nunca se transfiere un “tipo abstracto”.

---

## 30. Severity — v0.98

Los Facts tipados pueden incluir una severidad authored no negativa.

Policies pueden usar:

```text
min_severity
max_severity
```

Ejemplo:

```text
SECURITY_INCIDENT severity 0–3
→ supervisor

SECURITY_INCIDENT severity 4+
→ mando
```

No existe precedencia implícita. Ranges que se solapan sobre el mismo Fact generan conflicto fail-closed.

Cambiar la severidad de un Fact puede hacer que la rule anterior desaparezca y una nueva política se vuelva aplicable.

---

## 31. Upchain Authority — v0.99

Campo opcional:

```text
authority_relation = HIGHER_THAN_SOURCE
```

En una rule FACTION, el target debe tener autoridad estrictamente superior a la del source dentro de la misma facción.

Esto permite:

```text
100 → 500 → 800
```

pero bloquea:

```text
500 → 500
800 → 500
```

El objetivo es impedir broadcast lateral y modelar una cadena de mando ascendente.

La relación se recalcula con memberships actuales, por lo que una promoción puede abrir un nuevo hop sin reauthoring.

---

## 32. Holder Acquisition — v1.00

Una policy institucional puede distinguir cómo llegó el Fact al holder actual.

Valores:

```text
ANY
NONTRANSFERRED
LOCAL_TRANSFER
```

### ANY

Comportamiento histórico.

### NONTRANSFERRED

El holder no tiene un `DIRECT_LOCAL` registrado hacia sí en `transfer_history`.

### LOCAL_TRANSFER

El holder recibió el Fact socialmente mediante un transfer local.

Esto permite protocolos como:

```text
quien presencia/genera el dato inicia reporte
→ NONTRANSFERRED

quien recibe el reporte debe elevarlo
→ LOCAL_TRANSFER
```

La provenance original no se reescribe para obtener esta clasificación.

---

# PARTE X — CONSEQUENCES, WITNESSES Y NUEVOS FACTS

## 33. Consequence Engine

Una consecuencia puede afectar:

- World State;
- objects;
- Knowledge;
- Facts;
- NPCs específicos;
- NPCs presentes en el sitio.

### SITE_NPCS — v0.88

Una consecuencia puede producir un Fact para NPCs físicamente presentes en el site.

Esto permite modelar testigos sin escribir cada receptor por nombre.

Ejemplo:

```text
jugador realiza acción pública
→ consequence SITE_NPCS
→ presentes aprenden FACT-X
→ sus policies sociales pueden reaccionar
```

---

## 34. Acción → Fact → Goal → Movimiento

Desde v0.87 está cerrado el loop completo:

```text
player world action
→ consequence
→ Fact en NPC
→ Fact-goal
→ autonomous movement
```

Este loop es una de las capacidades centrales de SIZA porque permite que las consecuencias del jugador entren en la simulación social sin una quest lineal manual para cada caso.

---

# PARTE XI — PILOTO DE PESCADERÍA

## 35. Propósito del piloto

La Pescadería de Dársena existe como laboratorio persistente para validar que varias capas del World Engine pueden encadenarse.

Rooms principales del piloto:

- Embarcadero de Campana — `CAR-KAL-DAR-001`.
- Patio de Mineral — `CAR-KAL-DAR-002`.
- Plaza de Recepción — `CAR-KAL-DAR-003`.
- Calle de Servicio — `CAR-KAL-DAR-004`.
- Casa de Remedio — `CAR-KAL-DAR-005`.
- Cantina de Turno — `CAR-KAL-DAR-006`.
- Pescadería de Dársena — `CAR-KAL-DAR-007`.
- Trastienda de Pescadería — `CAR-KAL-DAR-008`.

NPC de prueba relevantes:

- Mara Vensal — `NPC-KAL-DAR-MARA-001`.
- Trabajador de Prueba B — `TEST-NPC-KAL-DAR-WORKER-B`.
- Informante de Prueba C — `TEST-NPC-KAL-DAR-INFORMANT-C`.

Objetos:

- Cajón de reparto de prueba.
- Manifiesto de carga de prueba.

---

## 36. Cadena v0.51–v0.63 del piloto

El piloto demostró progresivamente:

```text
v0.51
Cajón sellado → abrir → manifiesto visible

v0.52
analizar manifiesto → DIRECT PER

v0.53
reconstruir secuencia → ACCUMULATE INT

v0.54
presionar informante → CONFRONT

v0.55
sincronizar sellos → SYNCHRONIZE COO

v0.56
acción exitosa → Knowledge

v0.57
Knowledge semántico → Fact

v0.58
Fact Character → NPC

v0.59
Fact conocido → one-shot NPC goal → movimiento

v0.60
NPC → NPC Fact share

v0.61
Fact propagado → comportamiento secundario

v0.62
object completion

v0.63
NPC obtiene Fact por evidencia directa propia
```

Esta secuencia estableció la base que después permitió social propagation, faction policies y lifecycle.

---

# PARTE XII — JOBS, NEEDS, PERSONALITY, ORDERS Y TIEMPO

## 37. Jobs

El World Engine contiene infraestructura de Jobs persistentes.

Conceptualmente un Job puede:

- asociar una persona a un oficio;
- definir worksite;
- exigir Skills/Knowledge;
- producir actividad autónoma;
- conectar población con estructuras y economía;
- desbloquear unidades/cartas/conocimientos authored en capas de juego superiores.

En el diseño general de SIZA los Jobs convierten población en agentes funcionales dentro de un asentamiento.

---

## 38. Needs

Los NPC pueden mantener necesidades que forman parte de la evaluación de comportamiento.

La intención del sistema es que necesidades persistentes compitan con goals, orders y obligaciones sociales, en vez de que cada NPC espere inmóvil una quest.

---

## 39. Personality / Traits

Existen sistemas para personality y traits persistentes. En el modelo de diseño de SIZA, la personalidad de un NPC surge de la combinación de:

- conocimientos;
- virtudes;
- defectos;
- job;
- relationships;
- estado actual.

La personalidad no sustituye reglas deterministas; modifica prioridades o presentación donde esté authored.

---

## 40. Orders

El World Engine incluye infraestructura de órdenes y autoridad. Esto permite que un NPC o estructura de mando produzca goals explícitos cuando la relación de autoridad lo permite.

---

## 41. Time

Existe un sistema de tiempo del World Engine con comandos de inspección, avance, rate y set. El tiempo sirve como infraestructura para rutinas, eventos y futuras políticas temporales.

El core v1.01 todavía no incluye una epistemología completa de `fresh/stale/expired` para Facts; eso pertenece al roadmap avanzado descrito en el Documento 16.

---

# PARTE XIII — EVENTS E INFORMATION

## 42. Events

El motor contiene un Event Engine independiente del sistema de Facts.

Los eventos pueden:

- existir como occurrence identificable;
- asociarse a un sitio;
- generar conocimiento mediante rutas explícitas;
- originar obligaciones de información (`INFORM`).

Facts y Events se relacionan pero no son lo mismo:

- Event = ocurrencia estructurada del mundo.
- Fact = información concreta que un holder conoce.

---

## 43. Information obligations

El relationship engine puede mantener una obligación `INFORM` sobre un event occurrence y `SHARE_FACT` sobre un Fact exacto.

Esta separación permite conservar compatibilidad con información basada en eventos y con la capa semántica de Facts construida después.

---

# PARTE XIV — QA Y CONTRATOS

## 44. Filosofía de QA

El World Engine usa validación por riesgo.

Regla general:

```text
implementación
→ validator específico
→ regresión selectiva
→ aceptación manual solo cuando queda riesgo concreto
```

No se exige prueba manual por rutina cuando un comportamiento determinista está completamente representado en el validator.

La aceptación manual se reserva para riesgos como:

- input real del jugador no representado;
- shared/core changes;
- persistence/reset;
- movimiento no cubierto;
- integración cross-system;
- UI/output real;
- LLM/external nondeterminism.

---

## 45. `siza-qa-latest`

Es el comando de una sola entrada para ejecutar la validación de mayor riesgo actualmente pendiente.

Cada nueva capability debe mantener explícitamente los builds históricos que no fueron reemplazados.

La política es evitar afirmar “no hay bugs”; el QA demuestra contratos concretos y limita el riesgo conocido.

---

## 46. QA de Ollama

Cuando una versión afecta IA, el testing relevante incluye:

- transport failure;
- respuesta inválida;
- roundtrip real;
- inspección de request;
- private Fact leakage;
- fabricación del modelo sin persistencia.

La regla más importante es que un error del modelo no puede convertirse en autoridad persistente.

---

# PARTE XV — VERSIONES CERRADAS

## 47. Timeline resumido

### v0.39
Action-resolution lifecycle.

### v0.42
Skill + Knowledge requirement gates.

### v0.43
Action → resolution → consequence → persistent world state.

### v0.44
State gates actions.

### v0.45
State-driven room presentation.

### v0.46
State-driven exits.

### v0.47
Persistent temporary objects.

### v0.48
Authored object actions.

### v0.49
Exact object-state effects.

### v0.50
Object input precedence.

### v0.51–v0.63
Pescadería pilot: cuatro resoluciones, Knowledge, Facts, transfer, Fact-goals, movement y object completion.

### v0.64.1
Deterministic known-Fact retrieval.

### v0.65–v0.67
Narration context / narrator integration.

### v0.68–v0.71
Guarded natural input, proposal engine, bridge y async proposal.

### v0.72
Movement capability.

### v0.73–v0.74.1
Semantic interaction, topic y TALK precedence.

### v0.75–v0.78
Perception, active search y discovery → Knowledge.

### v0.79.1
Player → NPC INFORM.

### v0.80
NPC → player Fact acquisition.

### v0.81
Grounded dialogue.

### v0.82–v0.82.1
Style context + enforced renderer.

### v0.83
Deterministic player self-Knowledge query.

### v0.84
Authored Fact disclosure by familiarity.

### v0.85
Holder-local disclosure requirements.

### v0.86
Fact → Knowledge → authored object action cross-system loop.

### v0.87
Player action → NPC Fact → Fact-goal → autonomous movement.

### v0.88
SITE_NPCS witness consequences.

### v0.89
Fact-driven social SHARE_FACT.

### v0.90
Target-aware pruning.

### v0.91
Source-aware cancellation.

### v0.92
Faction targeted share rules.

### v0.93
Authority filtering.

### v0.94
NEAREST / max_targets.

### v0.95
Need-aware limited selection.

### v0.96
Faction-level inherited Fact-share policies.

### v0.97
Fact-type policies.

### v0.98
Severity filtered policies.

### v0.99
Strict upchain authority relation.

### v1.00
Holder-acquisition-aware sharing.

### v1.01
Holder-local Fact lifecycle: ACTIVE / RETRACTED / SUPERSEDED.

### v1.01.1
QA-only correction del baseline `decision_enabled`; producción v1.01 sin cambios.

---

# PARTE XVI — FRONTERA CON EL TCG

## 48. Confrontation rápida vs TCG combat

El World Engine ya posee `CONFRONT` stat-vs-stat. Esa resolución permanece para conflictos rápidos.

Ejemplos:

```text
presionar a un informante
forcejear por un objeto
resistir intimidación
```

El combate TCG es otra capa.

La arquitectura prevista es:

```text
WORLD ENGINE
→ detecta COMBAT_CONFRONTATION
→ crea encounter
→ abre TCG
→ TCG resuelve
→ devuelve outcome estructurado
→ World Engine aplica consecuencias persistentes
```

### 48.1 Contrato futuro World Engine → TCG

Campos previstos:

- attacker;
- defenders;
- location;
- encounter reason;
- world state relevante;
- stats/modificadores;
- deck/loadout;
- condiciones especiales;
- stakes.

### 48.2 Contrato futuro TCG → World Engine

Campos previstos:

- winner;
- defeated entities;
- damage/status;
- resources spent;
- surrender/flee/capture/death;
- outcome tags;
- otros resultados mecánicos autorizados.

Después del retorno, el World Engine puede generar:

- heridas;
- captura;
- muerte;
- Facts;
- witness reactions;
- faction consequences;
- goals;
- cambios de world state.

**El Combat Bridge se implementa cuando el TCG tenga un contrato estable. No forma parte de extender infinitamente el World Engine.**

---

# PARTE XVII — ESTADO ACTUAL Y FREEZE

## 49. Qué consideramos completo en el core

El core actual incluye las primitivas necesarias para construir contenido real de SIZA:

- mundo MUD persistente;
- Rooms / Exits / state-driven presentation;
- objects y authored actions;
- requirements;
- cuatro tipos de resolución;
- consequences;
- perception / discovery;
- Knowledge;
- semantic Facts;
- Fact lifecycle;
- deterministic retrieval;
- grounded AI context;
- diálogo grounded;
- disclosure;
- transfer;
- NPC goals;
- autonomous movement;
- relationships;
- social obligations;
- factions y authority;
- institutional Fact policies;
- fact type + severity;
- nearest / need-aware routing;
- strictly-upchain reporting;
- holder acquisition classification;
- jobs / needs / traits / orders / time / events como infraestructura de simulación.

---

## 50. Qué queda antes del freeze formal

El QA automático de v1.01 quedó cerrado mediante el targeted v1.01.1.

Solo queda una aceptación manual player-facing del lifecycle:

```text
ACTIVE
→ pregunta normal “¿Qué sé sobre X?” devuelve Fact

RETRACTED
→ la misma pregunta no devuelve Fact

ACTIVE otra vez
→ la misma pregunta vuelve a devolverlo
```

Después de esa aceptación, el estado recomendado es:

> **SIZA WORLD ENGINE v1.01 — CORE FROZEN**

A partir del freeze, una modificación al engine necesita una de dos justificaciones:

1. bug reproducible;
2. necesidad concreta descubierta mientras se construye el juego.

No se continúa agregando sistemas por completitud teórica.

---

# PARTE XVIII — QUÉ SIGUE PARA SIZA

## 51. Trabajo posterior al freeze

El siguiente trabajo principal deja de ser “hacer World Engine” y pasa a ser usarlo:

1. poblar Rivarica con contenido real;
2. convertir World Book en Rooms, NPC, objetos, jobs, factions y policies;
3. construir quests/campañas emergentes usando Action & Consequence;
4. terminar el TCG por separado;
5. definir e implementar Combat Bridge;
6. mejorar presentación/cliente;
7. construir vertical slice;
8. preparar paquete para publisher.

---

## 52. Regla final de diseño

La promesa técnica del World Engine es:

> Una acción no termina cuando aparece una frase en pantalla. Termina cuando sus consecuencias están representadas en el mundo y pueden ser descubiertas, recordadas, transmitidas y utilizadas por otros sistemas.

Eso es **Acción y Consecuencia** convertido en arquitectura.

---

## 53. Documentos relacionados

Dentro de esta misma área de documentación:

- **01 — Mundo persistente MUD**: estructura general del mundo.
- **02 — Espacio físico y mapas**: Zones, Rooms y Exits.
- **03 — Player y NPC**: modelo general de actores.
- **04 — Windrago**: árbol tecnológico de facción.
- **05 — 240 Conocimientos**: catálogo Knowledge.
- **06–14**: proceso de mapeado de Caribia y detalle de regiones/Kalnaj.
- **16 — Roadmap Simulation Framework**: expansión deliberadamente acotada que faltaría si se decide convertir este core en un framework de simulación narrativa general extremadamente robusto.
