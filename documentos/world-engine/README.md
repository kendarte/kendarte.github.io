# SIZA World Engine — Documentación maestra

**Versión documentada:** Core Freeze Candidate `v1.01.1`  
**Fecha de corte:** 2026-08-25  
**Implementación:** `siza-world-engine/`  
**Estado:** feature set del World Engine terminado; QA automático de v1.01 cerrado; queda únicamente la aceptación manual player-facing de retract/reactivate antes de declarar `CORE FROZEN`.

Esta carpeta es la referencia de sistema del **SIZA World Engine**. Explica qué hace el motor, cómo se organizan sus autoridades, qué datos persiste, cómo circula la información entre personajes, cómo se integra la IA local y qué bloques quedan fuera del core actual.

No es World Book. No define lore de Rivarica. No canoniza lugares, religiones, facciones o personajes por sí mismo. Los ejemplos de Kalnaj/Dársenas existen como piloto de validación salvo que el World Book los confirme por separado.

## 1. Qué es el World Engine

El World Engine es la capa determinista y persistente de SIZA. Su responsabilidad es resolver y conservar el estado del mundo antes de cualquier redacción generativa.

En términos prácticos controla:

- Rooms, Exits, ubicación y navegación.
- Estado persistente de puertas, objetos, Rooms y entidades.
- Acciones authored y sus requisitos.
- Stats de aventura y resolución DIRECT / ACCUMULATE / CONFRONT / SYNCHRONIZE.
- Consecuencias y cambios persistentes de world state.
- Percepción, búsqueda activa y descubrimiento.
- Knowledge, Facts, provenance, transferencia social y lifecycle.
- NPCs persistentes, rutinas, tiempo, necesidades, trabajos, eventos y relaciones.
- Facciones, rangos, autoridad, órdenes y políticas institucionales.
- Goals derivados de Facts y comportamiento autónomo.
- Selección de intención natural y bridges de ejecución.
- Contextos grounded para narración y diálogo.
- QA determinista y trazabilidad operativa.

La regla fundamental es:

```text
EL ENGINE AUTORIZA EL MUNDO.
LA IA PUEDE PROPONER O REDACTAR, PERO NO AUTORIZA NI MUTA ESTADO POR SU CUENTA.
```

## 2. Qué NO es el World Engine

No es:

- El TCG de combate.
- El frontend móvil.
- El World Book de Rivarica.
- Un LLM que improvisa estado.
- Un sistema de combate de cartas embebido en Evennia.
- Un sustituto de contenido authored.

El TCG y el World Engine son subsistemas separados que se conectarán mediante un **Combat Bridge** cuando el TCG esté suficientemente cerrado. El `CONFRONT` estadístico que existe hoy sigue siendo una resolución rápida de oposición; no sustituye un combate TCG completo.

## 3. Estado de terminación

### Core implementado

El World Engine ya dispone de las primitivas necesarias para construir SIZA como juego:

```text
mundo persistente
→ input
→ intent autorizado
→ acción
→ requisitos
→ resolución
→ consecuencia
→ world state
→ percepción / Knowledge / Facts
→ goals
→ NPC decisions
→ movimiento / interacción
→ nueva consecuencia
```

También existe un circuito social/institucional de información:

```text
Fact exacto
→ holder actual
→ policy local o de facción
→ filtro por tipo/severidad
→ autoridad / jerarquía
→ necesidad del destinatario
→ distancia / NEAREST
→ SHARE_FACT
→ movimiento físico
→ contacto
→ transferencia exacta
→ transfer_history
```

Y desde v1.01 los Facts tienen lifecycle holder-local:

```text
ACTIVE      = memoria vigente y utilizable
RETRACTED   = permanece almacenada, pero no autoriza comportamiento vivo
SUPERSEDED  = permanece almacenada y apunta a un Fact reemplazo
```

### Gate final de freeze

El QA automático quedó cerrado con el targeted v1.01.1. El único gate restante antes del freeze formal es la aceptación manual player-facing:

1. Sembrar Fact temporal ACTIVE en el Player.
2. Preguntar por lenguaje natural `¿Qué sé sobre ...?` y verlo.
3. Retractarlo.
4. Repetir la consulta y comprobar que deja de aparecer.
5. Reactivarlo.
6. Repetir la consulta y comprobar que vuelve.
7. Restaurar el snapshot original del Player.

Al completar eso, el estado esperado es:

```text
SIZA WORLD ENGINE v1.01 — CORE FROZEN
```

Después del freeze, no se agregan features al core por especulación. Sólo se reabre por:

- bug demostrado;
- necesidad concreta surgida al construir/jugar SIZA;
- decisión explícita de convertirlo en un framework de simulación más general.

## 4. Documentos de esta sección

- [01 — Arquitectura y principios](01_arquitectura_y_principios.md)  
  Autoridades, capas, persistencia, World Tick, decisiones y flujo causal.

- [02 — Sistemas implementados](02_sistemas_implementados.md)  
  Referencia funcional de todos los bloques existentes: mundo, acciones, percepción, Knowledge, NPCs, facciones, instituciones e IA grounded.

- [03 — Modelos de datos y contratos](03_modelos_de_datos_y_contratos.md)  
  Campos persistentes y formas authored principales: Fact, Action, Goal, Membership, Policy, Relationship obligation, Need, Job y Event.

- [04 — Input, IA y narración grounded](04_input_ia_y_narracion.md)  
  Routing natural, precedencias, proposals, bridges, Ollama/Qwen, privacidad de Facts y fallback.

- [05 — QA, operación e historial](05_qa_historial_y_operacion.md)  
  Política de pruebas, comandos operativos, restauración de estado y ledger de versiones hasta v1.01.1.

- [06 — Combat Bridge World Engine ↔ TCG](06_tcg_combat_bridge.md)  
  Contrato futuro para abrir una confrontación TCG y devolver sus resultados al mundo persistente.

- [07 — Roadmap opcional: Simulation Framework robusto](07_roadmap_simulation_framework.md)  
  Los bloques v1.02–v1.13 que faltan sólo si deliberadamente se decide continuar más allá del core de SIZA.

- [08 — Inventario técnico](08_inventario_tecnico.md)  
  Mapa de carpetas, typeclasses, servicios y responsabilidades de los archivos principales.

## 5. Jerarquía de autoridad documental

Para evitar que una nota vieja contradiga al código:

1. **Código ejecutable actual** en `siza-world-engine/overlay/` es la autoridad sobre comportamiento implementado.
2. **Esta documentación** explica y organiza ese comportamiento.
3. `documentos/` puede contener propuestas futuras, siempre marcadas como propuestas.
4. El **World Book/canon** decide qué contenido diegético es verdad en Rivarica.

Si código y documentación difieren, se debe corregir la documentación o registrar un bug; no se asume que el texto puede sobreescribir el runtime.

## 6. Filosofía de diseño que debe preservarse

### Determinismo primero

La IA no puede conceder una acción imposible, crear un Exit, mover un NPC, transferir un Fact privado o resolver un check sin pasar por la autoridad correspondiente.

### Identidad exacta

Siempre que importa persistencia se usan identidades estables: `room_id`, `npc_id`, `fact_id`, `goal_id`, `obligation_id`, IDs de Action/Rule/Event/Task. El texto visible puede cambiar; la identidad sistémica no debe depender de coincidencias ambiguas de prosa.

### Fail closed

Metadata malformed no debe producir una interpretación “probable”. Ejemplos actuales:

- requirements inválidos bloquean la Action;
- policies con selector ambiguo fallan cerradas;
- severity filter inválido no elige un rango arbitrario;
- dos policies heredadas para el mismo Fact concreto producen conflicto;
- `authority_relation` inválido cancela la rama social pendiente;
- `holder_acquisition` inválido cancela la rama;
- Fact status inválido no muta lifecycle.

### Estado derivado reversible cuando corresponde

Obligaciones o goals derivados pueden retirarse cuando dejan de cumplir su fuente, y reactivarse con la **misma identidad** cuando vuelve a existir la condición. Los resultados terminales one-shot completados no se reviven sólo porque el contexto vuelva a coincidir.

### El mundo no depende del LLM

Ollama/Qwen puede estar apagado. La geometría, estado, acciones, Knowledge, NPC simulation y consecuencias deben seguir funcionando. El LLM mejora interpretación/narración dentro de límites, pero no es la base de persistencia.

## 7. Piloto de Dársenas de Campana

La implementación actual se prueba en una micro-zona persistente con ocho Rooms y entidades de prueba. Su función es validar navegación, objetos, Actions, Knowledge, NPC autonomy e información social en un entorno pequeño y reproducible.

El piloto no debe confundirse con el mapa final ni con una afirmación de canon. Al crear contenido final, se reutilizan las mismas primitivas del engine con IDs y datos aprobados.

## 8. Regla de expansión después del freeze

Antes de agregar un nuevo subsistema al World Engine deben responderse tres preguntas:

1. ¿Existe una situación jugable concreta que el core actual no puede representar?
2. ¿El problema pertenece realmente al World Engine y no al TCG, frontend, World Book o authoring de contenido?
3. ¿Puede resolverse extendiendo una autoridad existente en vez de crear otra paralela?

Si no se cumplen esas tres condiciones, la feature no entra al core.
