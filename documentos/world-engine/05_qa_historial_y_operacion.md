# 05 — QA, operación e historial del SIZA World Engine

**Versión:** Core Freeze Candidate v1.01.1  
**Objetivo:** registrar cómo se valida el motor, cómo se opera el piloto y qué cerró cada versión.

## 1. Política de QA

La política actual es **risk-based**.

No toda feature necesita una prueba manual después de un validator verde. El tipo de prueba depende del riesgo residual.

### Siempre

- validator automático específico;
- restauración exacta del estado de prueba;
- assertions sobre identidad/estado, no sólo texto visible;
- regresión selectiva si una autoridad compartida cambió.

### Manual sólo cuando queda riesgo concreto

Se exige aceptación manual cuando el automático no representa suficientemente:

- input natural real del Player;
- UI/output player-facing;
- persistencia/reset difícil de simular;
- movimiento/cross-system no cubierto;
- cambios shared/core de autoridad;
- comportamiento externo/nondeterminista;
- integración con LLM real cuando el contrato depende del transporte/modelo.

No se hace manual “por costumbre” si el validator ya prueba exactamente la propiedad relevante.

## 2. `siza-qa-latest`

Comando principal:

```text
siza-qa-latest
```

Debe apuntar al validator de riesgo vigente, no a una suite infinita de todos los validators históricos.

La filosofía es:

```text
feature nueva
→ validator específico
→ si pasa y no hay riesgo residual, se cierra
→ latest avanza
```

## 3. Aceptación manual final v1.01

Debido a que v1.01 cambió `fact_knowledge_state()` —autoridad compartida usada por retrieval, goals, disclosure, SHARE_FACT y transfer— se dejó una aceptación player-facing final.

Harness QA-only:

```text
siza-qa-latest acceptance setup
```

Después, como input normal:

```text
¿Qué sé sobre la señal de cierre del motor v101?
```

Expected ACTIVE:

```text
La señal de cierre del motor v101 confirma que el Fact de aceptación manual está vigente.
```

Luego:

```text
siza-qa-latest acceptance retract
```

Misma pregunta.

Expected RETRACTED:

```text
No tienes información conocida sobre la señal de cierre del motor v101.
```

Luego:

```text
siza-qa-latest acceptance reactivate
```

Misma pregunta.

Expected ACTIVE otra vez:

```text
La señal de cierre del motor v101 confirma que el Fact de aceptación manual está vigente.
```

Finalmente:

```text
siza-qa-latest acceptance cleanup
```

El harness guarda un snapshot de `knowledge` y `knowledge_facts` del Player antes de sembrar el Fact temporal y restaura ese snapshot al cleanup.

## 4. Regla de state restoration

Un validator debe dejar el mundo igual que lo encontró, excepto por cambios que explícitamente sean el objeto permanente de una migración/upgrade.

Campos que se han restaurado en validators recientes incluyen:

- locations;
- Knowledge levels;
- Facts;
- lifecycle metadata;
- relationships;
- share rules;
- obligation-source index;
- faction memberships;
- faction registry;
- decision_enabled;
- goals/current goal;
- destination/activity;
- object/action/resolution histories.

Un validator que da PASS pero contamina el piloto no está cerrado.

## 5. Forced rolls

Los engines d6 aceptan forced rolls sólo para validación determinista.

Eso permite probar:

```text
roll bajo → FAILURE
roll alto → SUCCESS
```

sin convertir la producción en un sistema de resultados scripted.

En gameplay real, el provider usa random seguro del sistema para d6.

## 6. QA de Ollama

Cuando una versión afecta la frontera LLM deben comprobarse según riesgo:

- transport failure;
- timeout;
- invalid JSON/response;
- live local roundtrip;
- request payload (`stream=false`, `think=false`, etc.);
- ausencia de Facts privados desconocidos;
- que fabricación del modelo no persista/mute estado;
- fallback cuando el provider no responde.

El estado del mundo no debe depender de un PASS del modelo.

## 7. Operación local

### Actualizar overlay/runtime

En Windows CMD:

```bat
"C:\Users\PC\Desktop\kendarte.github.io\siza-world-engine\update_world_engine.bat"
```

No hace falta `cd /d` para ejecutar el updater por ruta absoluta.

### Webclient

Normalmente:

```text
http://localhost:4001/webclient/
```

Fallback:

```text
http://localhost:4001/
```

### Ollama

Provider default actual:

```text
http://127.0.0.1:11434/api/chat
qwen3:8b
```

## 8. Piloto persistente

El seed original crea ocho Rooms de prueba en Dársenas de Campana:

```text
Embarcadero de Campana        CAR-KAL-DAR-001
Patio de Mineral              CAR-KAL-DAR-002
Plaza de Recepcion            CAR-KAL-DAR-003
Calle de Servicio             CAR-KAL-DAR-004
Casa de Remedio               CAR-KAL-DAR-005
Cantina de Turno              CAR-KAL-DAR-006
Pescaderia de Darsena         CAR-KAL-DAR-007
Trastienda Pescaderia         CAR-KAL-DAR-008
```

Entidades de validación importantes:

```text
Mara Vensal                   NPC-KAL-DAR-MARA-001
Trabajador de Prueba B        TEST-NPC-KAL-DAR-WORKER-B
Informante de Prueba C        TEST-NPC-KAL-DAR-INFORMANT-C
```

Objetos del loop:

```text
Cajon de reparto de prueba
OBJ-TEST-PESCADERIA-REPARTO-001

Manifiesto de carga de prueba
OBJ-TEST-PESCADERIA-MANIFIESTO-001
```

La micro-zona es fixture de integración; no debe usarse como sustituto del contenido final de Rivarica.

## 9. Historial funcional — foundation pre-v0.39

Antes del lifecycle moderno de Actions ya existía una base de simulación incremental.

Los builds actuales conservan evidencia de esa fase:

- mundo persistente con Rooms/Exits;
- NPC routines y pathfinding;
- World Tick;
- World Clock/schedules (`0.16.0-world-clock-schedules`);
- world events;
- needs + affordances;
- jobs + claims + handoffs;
- decision engine y priorities;
- personality/context effects;
- factions, memberships, loyalty y rank authority (`0.25.1`);
- Knowledge-aware decisions (`0.28`);
- relationships/social information (`0.35`);
- Skills/Traits/Adventure stats;
- consecuencias/eventos/órdenes.

Estas piezas no se reemplazaron por las features posteriores; siguen siendo la base que alimenta NPC autonomy.

## 10. Historial v0.39–v0.51

### v0.39 — Action resolution lifecycle

Se separa Action de outcome y provider:

```text
READY/PENDING
→ provider
→ RESOLVED
```

### v0.42 — Skill + Knowledge gates

Requisitos duros se validan antes de resolución.

### v0.43 — Action → resolution → consequence → persistent world state

Outcome autorizado empieza a tener consecuencias persistentes.

### v0.44 — State gates Actions

World state puede volver una Action elegible/no elegible.

### v0.45 — State-driven Room presentation

La Room cambia presentación según estado real.

### v0.46 — Persistent state-driven Exits

Estado persistente controla traversal/gating de Exit.

### v0.47 — Persistent temporary objects

Se prueba creación/visibilidad persistente de objeto derivado del estado.

### v0.48 — Authored Object Actions

Los objetos llevan Actions authored.

### v0.49 — Action-object state effects por identidad exacta

Los efectos sobre objeto se atan a identidad, no a texto ambiguo.

### v0.50 — Authored Object input antes del no-match

Precedencia determinista de gameplay sobre fallback AI.

### v0.51.1 — Pescadería object loop

Loop completo de Cajón/Manifiesto listo para checks de aventura.

## 11. Historial v0.52–v0.63 — resolución + Knowledge/Facts

### v0.52 — DIRECT

`d6 + stat >= difficulty`.

### v0.53 — ACCUMULATE

Progress persistente hasta goal authored.

### v0.54 — CONFRONT

Oposición d6+stat vs d6+target stat.

### v0.55 — SYNCHRONIZE

Paridad/synchrony check.

### v0.56 — Player Knowledge unlock

Una resolución puede desbloquear Knowledge.

### v0.57 — Semantic Knowledge Facts

Knowledge deja de ser sólo una llave/level; se introduce Fact estructurado.

### v0.58 — Fact transfer Character→NPC

Transferencia exacta de Fact local.

### v0.59 — Known Fact → one-shot NPC goal

Un NPC puede materializar Goal por conocimiento y moverse.

### v0.60 — NPC→NPC Fact share completion

La finalización de un Goal puede compartir Fact a otro NPC.

### v0.61 — Propagated Fact → secondary behavior

El recipient puede generar comportamiento nuevo por lo aprendido.

### v0.62 — Object completion

Un goal se completa por Object Action.

### v0.63 — NPC self-discovered Knowledge Fact

Una consecuencia de NPC puede crear Fact directo con provenance propio.

## 12. Historial v0.64–v0.67 — retrieval y narración grounded

### v0.64.1 — deterministic known Fact retrieval

Filtro Knowledge antes de relevancia/contexto.

### v0.65+

Se consolida context/narration boundary grounded.

### v0.66.1 — Ollama local grounded provider

Provider real qwen/Ollama con transport handling.

### v0.67 — narrator

Narración posterior a estado autorizado.

## 13. Historial v0.68–v0.78 — natural input y perception

### v0.68.1 — guarded natural input

Interrogativos/rutas fuertes se clasifican antes de fallback.

### v0.69 — proposal engine

El LLM propone capabilities/targets cerrados.

### v0.70 — proposal→engine bridge

La propuesta debe pasar por ejecución determinista.

### v0.71.1 — async proposal

Proposal runtime no bloqueante.

### v0.72 — movement

Natural movement bridge.

### v0.73 — semantic interaction

TALK/interaction semántica con NPC real.

### v0.74 — topic

Topic extraction para conversación.

### v0.74.1 — explicit TALK precedence

TALK directo no cae a inquiry/proposal genérico.

### v0.75 — semantic perception

Observación de target semántico.

### v0.76 — active search

Búsqueda activa.

### v0.77 — discovery→Knowledge

Perception puede proyectar Knowledge.

### v0.78 — deterministic active perception parity

Cuando el mundo authored ya define el hallazgo, se evita decisión probabilística innecesaria.

## 14. Historial v0.79–v0.86.1 — conversación/Fact authority

### v0.79.1 — Player→NPC INFORM

El Player comparte un Fact que realmente conoce.

### v0.80.3 — NPC→Player acquisition closed

Conversación autorizada transfiere Fact al Player.

### v0.81.1 — grounded dialogue closed

Respuesta se basa en Fact autorizado.

### v0.82 — style context

Se separa contenido de estilo.

### v0.82.1 — enforced styled renderer

Renderer estilizado mantiene grounding.

### v0.83 / v0.83.1 — deterministic Player self-Knowledge query

`¿Qué sé sobre X?` bypass-ea Ollama y es read-only.

### v0.84 — min familiarity disclosure

Un Fact puede exigir familiarity mínima antes de TALK disclosure.

### v0.85.2 — holder-local disclosure state closed

El permiso de contar un Fact puede depender de estado del holder.

### v0.86 — Fact→Knowledge→Action loop

Fact recibido desbloquea Knowledge requirement que habilita una Object Action.

### v0.86.1 — ranked single-Fact authority

Se corrige colisión de múltiples Facts candidatos y TALK se ata a un Fact concreto rankeado.

## 15. Historial v0.87–v0.88 — consecuencias sociales directas

### v0.87 — world action → Fact en NPC → autonomous behavior

Una acción del Player enseña Fact a Mara; Fact-goal mueve al NPC.

### v0.88 — SITE_NPCS recipients

NPCs físicamente presentes pueden aprender Fact como testigos sin listas manuales por ID.

## 16. Historial v0.89–v0.95 — SHARE_FACT social

### v0.89.1 — Fact-sharing social propagation closed

Rules crean obligaciones `SHARE_FACT` y usan movimiento/contacto/transfer reales.

### v0.90 — target-aware pruning

Si target ya conoce Fact, se evita share inútil.

### v0.91 — source-aware cancellation

Si source deja de conocer Fact, se cancela pending share.

### v0.92 — faction target mode

Una rule puede expandirse a miembros activos de una facción.

### v0.93 — min_authority

Filtro de recipient por authority.

### v0.94 — NEAREST + max_targets

Ranking por path real, authority y npc_id.

### v0.95 — need-aware limited NEAREST

Slots limitados sólo se asignan a recipients que aún necesitan el Fact.

## 17. Historial v0.96–v1.00 — instituciones

### v0.96 / v0.96.1 — faction-level Fact-share policy inheritance

Faction definition proyecta policies a managed NPC rules. El 6/9 inicial fue falso negativo del validator por helper hard-coded a otro Fact; targeted 3/3 cerró producción sin cambios.

### v0.97 — fact_type policies

Una policy por tipo se expande a rules exactas por Fact almacenado.

### v0.98 — severity ranges

Policies por tipo pueden separar incidentes por severidad y usar distintos thresholds/targets.

### v0.99 — HIGHER_THAN_SOURCE

Cadena de autoridad estrictamente ascendente; peers iguales no relayan y el top se detiene.

### v1.00 — holder_acquisition

Policy puede distinguir holder no transferido vs holder que recibió el Fact por `DIRECT_LOCAL`.

## 18. Historial v1.01 / v1.01.1 — Fact lifecycle

### v1.01

Se introduce lifecycle holder-local:

```text
ACTIVE
RETRACTED
SUPERSEDED
```

`fact_knowledge_state()` se vuelve autoridad compartida de vigencia.

La suite original produjo 9/10. El único FAIL mostraba Goal y SHARE_FACT obligation activos correctamente; falló porque el validator no había fijado `decision_enabled=True` antes de pedir Relationship candidates.

### v1.01.1 targeted

Se controla `decision_enabled`, se prueba:

- Fact-goal baseline;
- SHARE_FACT obligation exacta;
- relationship candidate exacto.

Resultado:

```text
3/3 PASS
```

Producción v1.01 no cambió.

## 19. Estado de cierre actual

Automático:

```text
CLOSED
```

Manual player-facing:

```text
PENDING FINAL ACCEPTANCE
```

Después de `acceptance setup → query → retract → query → reactivate → query → cleanup`, el estado documental debe actualizarse a:

```text
SIZA WORLD ENGINE v1.01 — CORE FROZEN
```

## 20. Qué significa CLOSED

`CLOSED` significa:

- assertions diseñadas para esa propiedad pasaron;
- no queda un riesgo concreto identificado que exija otra prueba antes de continuar;
- no se conocen fallos reproducibles dentro del alcance del validator.

No significa una afirmación absoluta de “cero bugs”.

## 21. Qué significa CORE FROZEN

Freeze no significa abandonado.

Significa:

- no agregar features por exploración teórica;
- no reescribir sistemas cerrados sin evidencia;
- priorizar contenido/gameplay;
- reabrir sólo por bug, integración o requisito real.

## 22. Regla para validators futuros

Antes de escribir un validator nuevo:

1. Identificar la autoridad real que se está probando.
2. Usar un Fact/Goal/ID de prueba único para evitar colisiones históricas.
3. Controlar todos los gates que el assertion depende (`decision_enabled`, location, membership, etc.).
4. No reutilizar helpers viejos con IDs hard-coded sin inspeccionarlos.
5. Separar state assertion de presentation assertion.
6. Restaurar snapshot en `finally`.
7. Si el log de detalle contradice el FAIL, inspeccionar el validator antes de tocar producción.

Los falsos negativos v0.96 y v1.01 son precedentes claros de esa regla.
