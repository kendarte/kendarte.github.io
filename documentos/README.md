# SIZA — Documentos de diseño

Esta carpeta separa la **documentación de sistema** del canon textual del World Book y del código ejecutable.

## Regla de organización

- `canon/` o el World Book: define **qué es verdad en Rivarica**.
- `data/`: define **estado y datos estructurados consumibles por el juego**.
- `documentos/`: define **cómo funcionan los sistemas de Siza**.
- código del juego: implementa esas reglas.

Los documentos de esta carpeta pueden proponer mecánicas sin convertir automáticamente esas propuestas en canon diegético.

## Secciones actuales

### SIZA World Engine — documentación maestra

Estado documentado: **Core Freeze Candidate v1.01.1**. El feature set del World Engine está terminado; el QA automático de v1.01 está cerrado y queda únicamente la aceptación manual player-facing de lifecycle antes del freeze formal.

- [Índice maestro del World Engine](world-engine/)
- [Arquitectura y principios](world-engine/01_arquitectura_y_principios.md)
- [Sistemas implementados](world-engine/02_sistemas_implementados.md)
- [Modelos de datos y contratos](world-engine/03_modelos_de_datos_y_contratos.md)
- [Input, IA y narración grounded](world-engine/04_input_ia_y_narracion.md)
- [QA, historial y operación](world-engine/05_qa_historial_y_operacion.md)
- [Combat Bridge World Engine ↔ TCG](world-engine/06_tcg_combat_bridge.md)
- [Roadmap opcional del Simulation Framework](world-engine/07_roadmap_simulation_framework.md)
- [Inventario técnico](world-engine/08_inventario_tecnico.md)

La documentación distingue explícitamente entre:

1. **World Engine core** — implementado y en proceso de freeze.
2. **Combat Bridge con el TCG** — integración futura del juego una vez el TCG esté suficientemente cerrado.
3. **Simulation Framework v1.02–v1.13** — roadmap opcional sólo si se decide deliberadamente convertir el engine en una plataforma reusable más general.

### Conocimientos Player/NPC — 240 entradas

- [Índice general de Conocimientos](conocimientos/)
- [Volumen 1 — Espacio a Energía](conocimientos/01_espacio_a_energia.md)
- [Volumen 2 — Ingeniería a Medicina](conocimientos/02_ingenieria_a_medicina.md)
- [Volumen 3 — Sociedad a Crimen](conocimientos/03_sociedad_a_crimen.md)
- [Volumen 4 — Social a Dinámico](conocimientos/04_social_a_dinamico.md)

Cada Knowledge incluye descripción, parámetros frecuentes, bonus y efecto sobre gameplay.

## Convención

Cada documento debe indicar versión y alcance. Cuando una regla quede congelada para implementación, debe reflejarse después en los esquemas de `data/` o en el código correspondiente.

Para sistemas implementados, el código ejecutable es la autoridad final sobre comportamiento. Si un documento contradice al runtime, se corrige el documento o se registra el bug; la prosa no sobreescribe silenciosamente el código.
