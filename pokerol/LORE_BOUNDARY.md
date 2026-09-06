# POKEROL — frontera motor / contenido

## No copiado desde SIZA

- `overlay/world/upgrade_pilot_*`
- `faro_ahogado_*`
- Darkhaven
- Kalnaj
- Mara y NPCs de prueba
- campañas, beats y cartas `FA-*`
- presets de Map Creator y NPC Creator
- imágenes de pescadería / dársenas / dockside
- loaders de localizaciones
- validadores históricos que materializan contenido del piloto

## Conservado por compatibilidad técnica

Algunos módulos, comandos, eventos DOM y clases CSS/JS siguen usando el prefijo `siza_` o `siza-`. Esos identificadores son parte del contrato técnico del motor/webclient heredado y no contienen canon de SIZA. Renombrarlos en masa ahora rompería integraciones sin aportar separación de mundo.

La regla para POKEROL es: contenido nuevo nunca debe depender de `siza-world-engine/overlay/world/*` ni de IDs narrativos de SIZA. Las mecánicas compartidas viven dentro de la copia propia de `pokerol/overlay/`.
