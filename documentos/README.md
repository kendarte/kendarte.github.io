# SIZA — Documentos de diseño

Esta carpeta separa la **documentación de sistema** del canon textual del World Book y del código ejecutable.

## Regla de organización

- `canon/` o el World Book: define **qué es verdad en Rivarica**.
- `data/`: define **estado y datos estructurados consumibles por el juego**.
- `documentos/`: define **cómo funcionan los sistemas de Siza**.
- código del juego: implementa esas reglas.

Los documentos de esta carpeta pueden proponer mecánicas sin convertir automáticamente esas propuestas en canon diegético.

## Secciones actuales

### Conocimientos Player/NPC — 240 entradas

- [Índice general de Conocimientos](conocimientos/)
- [Volumen 1 — Espacio a Energía](conocimientos/01_espacio_a_energia.md)
- [Volumen 2 — Ingeniería a Medicina](conocimientos/02_ingenieria_a_medicina.md)
- [Volumen 3 — Sociedad a Crimen](conocimientos/03_sociedad_a_crimen.md)
- [Volumen 4 — Social a Dinámico](conocimientos/04_social_a_dinamico.md)

Cada Knowledge incluye descripción, parámetros frecuentes, bonus y efecto sobre gameplay.

## Convención

Cada documento debe indicar versión y alcance. Cuando una regla quede congelada para implementación, debe reflejarse después en los esquemas de `data/` o en el código correspondiente.
