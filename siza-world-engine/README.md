# SIZA World Engine — Evennia runtime

Este directorio contiene la implementación ejecutable del **SIZA World Engine** sobre Evennia.

El World Engine es la capa determinista y persistente de SIZA. No sustituye el TCG ni el frontend; resuelve mundo, Actions, NPC simulation, Knowledge/Facts, consecuencias e instituciones, mientras Ollama/Qwen queda limitado a proposal/interpretación y redacción grounded.

## Estado actual

**Core Freeze Candidate v1.01.1 — 2026-08-25**

El feature set del World Engine está terminado para el core de SIZA. El QA automático de v1.01 está cerrado. Queda únicamente la aceptación manual player-facing `ACTIVE → RETRACTED → ACTIVE` antes de declarar:

```text
SIZA WORLD ENGINE v1.01 — CORE FROZEN
```

La documentación completa y mantenible está en:

```text
../documentos/world-engine/
```

Entrada principal:

[Documentación maestra del World Engine](../documentos/world-engine/README.md)

Ahí se documentan arquitectura, sistemas implementados, modelos de datos, input/IA, QA e historial, el futuro Combat Bridge con el TCG y el roadmap **opcional** v1.02–v1.13 para convertir el engine en un simulation framework más general.

## Principio de autoridad

```text
EL ENGINE AUTORIZA EL MUNDO.
LA IA PUEDE PROPONER O REDACTAR, PERO NO AUTORIZA NI MUTA ESTADO POR SU CUENTA.
```

El World Engine es autoridad sobre, entre otras cosas:

- Rooms, Exits y ubicación;
- puertas/bloqueos y world state;
- objetos y Object Actions;
- Actions, requirements y resolution lifecycle;
- stats FUE/AGI/COO/INT/PER/PSI;
- DIRECT / ACCUMULATE / CONFRONT / SYNCHRONIZE;
- consecuencias persistentes;
- percepción/búsqueda/descubrimiento;
- Knowledge y Facts;
- Fact lifecycle ACTIVE/RETRACTED/SUPERSEDED;
- NPC goals, movement y autonomous decisions;
- tiempo, rutinas, needs, jobs y events;
- relaciones e información social;
- facciones, ranks, authority, orders y policies institucionales.

Qwen/Ollama puede ayudar con input abierto y narración/dialogue grounded, pero no decide geometría, no crea Facts privados, no resuelve checks y no muta `db.*` directamente.

## Requisitos

- Windows 10/11
- Python 3.12 x64
- Ollama opcional para narración/proposal local
- Modelo por defecto actual: `qwen3:8b`

Evennia 6.1 requiere Python >=3.12.

El engine determinista debe seguir funcionando aunque Ollama esté apagado; sólo las capas que requieren provider caen a failure/fallback controlado.

## Instalación inicial en Windows

Desde la raíz del repositorio:

```bat
cd siza-world-engine
py -3.12 -m venv .venv
.venv\Scripts\activate
python -m pip install --upgrade pip
pip install -r requirements.txt
python -m evennia
python -m evennia --init runtime
```

Si `python -m evennia --init runtime` no acepta el argumento en su instalación:

```bat
evennia --init runtime
```

Copie el overlay al game dir generado:

```bat
robocopy overlay runtime /E
```

Después:

```bat
cd runtime
evennia migrate
evennia start
```

## Actualizar el runtime local durante desarrollo

Desde Windows CMD puede ejecutar directamente:

```bat
"C:\Users\PC\Desktop\kendarte.github.io\siza-world-engine\update_world_engine.bat"
```

No necesita hacer `cd /d` antes.

## Webclient

Normalmente:

```text
http://localhost:4001/webclient/
```

Fallback:

```text
http://localhost:4001/
```

## Ollama

El provider actual usa por defecto:

```text
http://127.0.0.1:11434/api/chat
qwen3:8b
```

Variables de entorno implementadas actualmente:

```bat
set SIZA_OLLAMA_ENDPOINT=http://127.0.0.1:11434/api/chat
set SIZA_OLLAMA_MODEL=qwen3:8b
```

El provider usa request no-streaming, `think=false`, y devuelve errores de transporte como packets estructurados en vez de mutar o revertir el mundo.

## Mapa piloto

El seed de Kalnaj crea ocho Rooms persistentes de validación:

```text
Embarcadero de Campana
        |
Patio de Mineral
        |
Plaza de Recepción
      /   |    \
Casa   Cantina  Calle de Servicio
Remedio          |
             Pescadería
                 |
             Trastienda
```

El piloto valida navegación, objetos, Actions, cuatro modos de resolución, Knowledge/Facts, NPC autonomy y propagación social/institucional.

Es un fixture de integración. No debe confundirse con una afirmación de que cada nodo o descripción del piloto sea canon final de Rivarica.

## Crear el piloto desde una instalación nueva

Como superusuario:

```text
batchcode kalnaj_pilot
```

Los upgrades versionados en `overlay/world/upgrade_pilot_vXX.py` agregan fixtures/datos usados por las etapas posteriores del engine.

## QA

Validator de riesgo vigente:

```text
siza-qa-latest
```

Estado automático actual: v1.01 cerrado mediante v1.01.1 targeted `3/3 PASS` después de identificar un falso negativo de setup del validator.

### Aceptación manual final antes del freeze

```text
siza-qa-latest acceptance setup
```

Luego, como input normal:

```text
¿Qué sé sobre la señal de cierre del motor v101?
```

Después:

```text
siza-qa-latest acceptance retract
```

Repita la misma pregunta y debe desaparecer del Knowledge vivo.

Después:

```text
siza-qa-latest acceptance reactivate
```

Repita la pregunta y debe volver.

Finalmente:

```text
siza-qa-latest acceptance cleanup
```

El harness restaura el snapshot original de Knowledge/Facts del Player.

Detalles y expected text exacto:

[QA, historial y operación](../documentos/world-engine/05_qa_historial_y_operacion.md)

## TCG

El TCG se desarrolla/resuelve por separado. Una confrontación completa de combate futura debe abrir el TCG mediante un **Combat Bridge**, mientras el `CONFRONT` d6 actual permanece como resolución rápida stat-vs-stat.

Contrato y límites:

[Combat Bridge World Engine ↔ TCG](../documentos/world-engine/06_tcg_combat_bridge.md)

## Después del freeze

No hay una “siguiente fase del World Engine” obligatoria.

Después del freeze, el trabajo normal pasa a:

- contenido real de Rivarica;
- quests/campaigns;
- NPCs/facciones reales;
- conexión del TCG cuando esté listo;
- frontend/presentación;
- bugs demostrados o necesidades concretas de gameplay.

Existe un roadmap opcional v1.02–v1.13 sólo si se decide explícitamente convertir el engine en un framework reusable más amplio:

[Roadmap del Simulation Framework](../documentos/world-engine/07_roadmap_simulation_framework.md)
