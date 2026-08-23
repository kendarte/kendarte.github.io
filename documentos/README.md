# SIZA — Documentos de diseño

Esta carpeta separa la **documentación de sistema** del canon textual del World Book y del código ejecutable.

## Regla de organización

- `canon/` o el World Book: define **qué es verdad en Rivarica**.
- `data/`: define **estado y datos estructurados consumibles por el juego**.
- `documentos/`: define **cómo funcionan los sistemas de Siza**.
- código del juego: implementa esas reglas.

Los documentos de esta carpeta pueden proponer mecánicas sin convertir automáticamente esas propuestas en canon diegético.

## Documentos actuales

- `05_Catalogo_General_Conocimientos_v0.2.md` — taxonomía maestra de **240 Conocimientos** para Player/NPC, con descripción, parámetros frecuentes, bonus y efecto de gameplay.

## Convención

Cada documento debe indicar versión y alcance. Cuando una regla quede congelada para implementación, debe reflejarse después en los esquemas de `data/` o en el código correspondiente.
