# SIZA World Engine — Evennia pilot

Este directorio es un prototipo aislado del World Engine de Siza. No sustituye ni modifica el TCG ni el frontend MUD actual.

## Objetivo de esta fase

Demostrar cuatro cosas antes de migrar nada grande:

1. La posición del personaje existe como estado real y persistente.
2. El movimiento sólo ocurre por Exits válidos.
3. Puertas/Exits pueden tener estado persistente.
4. Qwen narra DESPUÉS de que Evennia resolvió el mundo; Qwen no decide la geometría.

## Requisitos

- Windows 10/11
- Python 3.12 x64
- Ollama corriendo en `http://127.0.0.1:11434`
- Modelo por defecto: `qwen3:8b`

Evennia 6.1 requiere Python >=3.12.

## Instalación en Windows

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

La primera ejecución de `python -m evennia` en Windows registra el comando de Evennia. Si `python -m evennia --init runtime` no acepta el argumento en su instalación, use:

```bat
evennia --init runtime
```

Ahora copie el overlay dentro del game dir generado:

```bat
robocopy overlay runtime /E
```

Después:

```bat
cd runtime
evennia migrate
evennia start
```

Evennia abrirá el webclient normalmente en:

```text
http://localhost:4001
```

En el primer arranque cree el superusuario que Evennia solicite.

## Crear el mapa piloto

Entre al juego como superusuario y ejecute:

```text
batchcode kalnaj_pilot
```

Eso crea ocho Rooms persistentes en una micro-zona de prueba de Dársenas de Campana.

## Qué debe probar

El seed crea un grafo aproximado:

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

La Cantina y la Pescadería son NODOS DE PROTOTIPO para probar navegación e interiores. No quedan canonizados por este test.

Muévase usando el nombre de cada Exit. Evennia sólo cambia `Character.location` cuando existe un Exit real.

La conexión a Ollama se ejecuta después de un traversal exitoso. Si Ollama está apagado, el movimiento sigue funcionando y sólo cae a una frase determinista.

## Variables opcionales de Ollama

Puede cambiar la configuración sin editar código:

```bat
set SIZA_OLLAMA_URL=http://127.0.0.1:11434/api/chat
set SIZA_OLLAMA_MODEL=qwen3:8b
set SIZA_OLLAMA_NUM_CTX=8192
```

## Arquitectura de este piloto

```text
Player command
    -> Evennia Exit
    -> valida estado del Exit
    -> Character.move_to(destination)
    -> persiste nueva location
    -> construye Narrative Packet
    -> Ollama /api/chat (think=false)
    -> Qwen narra el resultado autorizado
```

## Regla de implementación

El World Engine es autoridad sobre:

- Rooms
- Exits
- ubicación
- puertas/bloqueos
- objetos
- estado físico
- NPC presentes

Qwen es autoridad únicamente sobre la redacción final. Si un dato no está en el Narrative Packet, no debe inventarlo.

## Siguiente fase después de validar el piloto

1. Intent parser para frases como `voy al bar`.
2. Sensory facts + Percepción.
3. Knowledge del Player/NPC.
4. NPC persistente con rutina.
5. Scene Compiler conectado a la documentación de Rivarica.
6. Sustituir los nodos de prueba por el mapa aprobado de Kalnaj.
