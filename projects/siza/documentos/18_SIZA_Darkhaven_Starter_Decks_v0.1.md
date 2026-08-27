# SIZA — Darkhaven Starter Decks v0.1

**Estado:** PROPUESTO / diseño de vertical slice  
**Campaña objetivo:** Faro Ahogado  
**Alcance:** tres Spellbooks iniciales de Darkhaven + función de onboarding  
**No modifica todavía:** afinidades del Personaje, cristales, reglas TCG, World Engine ni runtime

## 1. Reglas que este diseño no puede romper

1. El Personaje posee sus afinidades, cristales, MF, PROW/EVA y stats Adventure. El deck no concede ni define cristales.
2. El Spellbook contiene Pages. Las Pages tienen sus propios requisitos de afinidad/pips.
3. Una invocación del Spellbook no es una persona física del mundo.
4. Una persona física puede aparecer como carta de Encounter cuando el TCG representa una confrontación autorizada por el World Engine.
5. Una Page adquirida después puede representar la memoria/eco pictomántico de una persona, pero no invoca a la persona real.
6. El starter de Darkhaven representa entrenamiento, catálogo y equipo institucional previo a Faro Ahogado. No contiene recuerdos de la campaña antes de vivirlos.
7. Formato actual: 60 cartas, máximo cuatro copias de cada no-Reserva.
8. Mano inicial aleatoria de siete. El tutorial no depende de una mano forzada.
9. Las tres listas deben compartir suficiente lenguaje mecánico para que el onboarding funcione con cualquiera de ellas.
10. Los pips/colores finales no se asignan en este documento hasta fijar el perfil de afinidad del protagonista del vertical slice. Asignarlos antes mezclaría otra vez Personaje y deck.

## 2. Estructura común de los tres starters

Cada starter usa:

- 20 Pages de núcleo Darkhaven compartido;
- 16 Pages de doctrina propia;
- 24 Reservas;
- total: 60.

La razón del núcleo común es de tutorial: cualquiera de los tres Spellbooks debe exponer al jugador a Invocación, Instant, Artifact, Equipment, Manafestation, Stack y Mana Burn sin requerir un tutorial distinto por deck.

## 3. Núcleo Darkhaven compartido — 20 cartas

### 4x Familiar de Práctica
**Tipo:** Creature — Familiar  
**Función:** invocación básica de bajo riesgo.  
**Perfil:** cuerpo simple, sin texto complejo.  
**Tutorial:** enseña manifestar una Invocación, entrada al Battlefield, ataque, bloqueo y agotamiento.

### 4x Lectura de Campo
**Tipo:** Instant  
**Efecto objetivo:** roba una carta.  
**Tutorial:** enseña Page reactiva/simple, Stack y ventaja de cartas.

### 4x Interrupción de Protocolo
**Tipo:** Instant  
**Efecto objetivo:** contrarresta el spell objetivo.  
**Tutorial:** enseña prioridad y respuesta. No requiere inventar una regla de tutorial; usa el Stack real.

### 4x Prisma de Servicio
**Tipo:** Artifact  
**Efecto objetivo:** agotarse para otorgar +1 a una tirada de Manafestation compatible.  
**Tutorial:** enseña permanentes no criatura, agotamiento y modificación de Manafestation.

### 4x Spellweapon de Servicio
**Tipo:** Artifact — Equipment  
**Efecto objetivo:** la Invocación equipada obtiene un bono ofensivo; Equipar {1}.  
**Tutorial:** enseña zona de Equipment, pago de Equipar y modificación de una Invocación ya presente.

> Los nombres anteriores describen Pages institucionales. El arte y la forma física pueden variar por Spellweapon/Familiar, pero ninguna representa a un agente humano invocable.

## 4. Starter A — VIGILANCIA

**Doctrina:** investigar, leer el campo, negar una amenaza y conservar opciones.  
**Rol de aprendizaje:** control / información.  
**No significa:** “deck azul” ni concede cristales azules.

### Módulo propio — 16 cartas

#### 4x Ojo de Baliza
**Tipo:** Creature — Familiar  
**Perfil:** pequeño, defensivo.  
**Efecto objetivo:** al entrar, observa la carta superior de la Library.

#### 4x Eco de Rastreo
**Tipo:** Creature — Echo  
**Perfil:** criatura media.  
**Efecto objetivo:** al entrar, roba una carta y luego descarta una, si la versión final del runtime lo soporta; mientras no esté cableado, usar sólo una variante de robo ya soportada.

#### 4x Ancla de Retorno
**Tipo:** Artifact  
**Efecto objetivo:** al entrar, devuelve otro permanente a la mano de su dueño.  
**Función:** control temporal, no destrucción.

#### 4x Corte de Señal
**Tipo:** Instant  
**Efecto objetivo:** descarte o interrupción secundaria según el efecto que esté cableado en el runtime al implementar.  
**Función:** quitar opciones al rival.

### Reservas — 24

12x Archivo de Guardia  
12x Plataforma de Relevo

### Identidad de partida

Vigilancia gana tiempo, ve más cartas y responde. Su starter debe hacer sentir que el agente preparado no necesariamente golpea primero: entiende primero qué está ocurriendo y decide qué merece resolverse.

## 5. Starter B — RUPTURA

**Doctrina:** convertir una ventana corta en ventaja decisiva.  
**Rol de aprendizaje:** presión / combate.  
**No significa:** “deck rojo” ni concede cristales rojos.

### Módulo propio — 16 cartas

#### 4x Ignimite de Ejercicio
**Tipo:** Creature — Elemental  
**Perfil:** pequeño y agresivo.  
**Efecto objetivo:** cuando hace daño de combate obtiene +1/+1.

#### 4x Mastín de Impacto
**Tipo:** Creature — Beast  
**Perfil:** ataque alto, defensa moderada.  
**Texto:** sencillo; su función es enseñar lectura de stats y combate limpio.

#### 4x Eco de Asalto
**Tipo:** Creature — Echo  
**Perfil:** atacante medio.  
**Efecto objetivo:** al declarar ataque, inflige daño adicional al Personaje defensor.

#### 4x Descarga de Ruptura
**Tipo:** Instant  
**Efecto objetivo:** daño directo al Personaje rival.  
**Función:** enseñar que una partida no se resuelve únicamente por combate de Invocaciones.

### Reservas — 24

12x Galería de Entrenamiento  
12x Hangar de Salida

### Identidad de partida

Ruptura obliga al jugador a comprender tempo, cuándo atacar, cuándo comprometer cristales y cuándo usar daño directo. Es el Spellbook más inmediato de los tres, no una clase de Personaje.

## 6. Starter C — CONTENCIÓN

**Doctrina:** permanecer, fijar la amenaza y negar espacio al rival.  
**Rol de aprendizaje:** defensa / permanencia.  
**No significa:** un perfil de cristales concreto.

### Módulo propio — 16 cartas

#### 4x Sabueso de Umbral
**Tipo:** Creature — Familiar  
**Perfil:** ataque bajo, defensa alta.  
**Función:** enseñar bloqueo eficiente.

#### 4x Custodio Lumex
**Tipo:** Creature — Construct  
**Perfil:** cuerpo medio de alta resistencia.  
**Texto:** simple para mantener legible el starter.

#### 4x Bastión Pictomántico
**Tipo:** Creature — Construct  
**Perfil:** Invocación grande y difícil de retirar.  
**Función:** objetivo de desarrollo del Battlefield.

#### 4x Contraimpulso
**Tipo:** Instant  
**Efecto objetivo:** devolver un permanente a la mano o negar una amenaza según el efecto final cableado.  
**Función:** transformar defensa en pérdida de tempo rival.

### Reservas — 24

12x Patio de Contención  
12x Cámara de Frames

### Identidad de partida

Contención enseña que sobrevivir un ataque también es una decisión ofensiva. Construye Battlefield, bloquea y obliga al rival a gastar más recursos para atravesarlo.

## 7. Por qué no hay humanos invocables en estos starters

Estos tres Spellbooks son institucionales y existen antes de Faro Ahogado. Por eso sus Creatures son Familiares, Constructos, Elementales, Bestias o Ecos estabilizados.

Una carta como:

- Pescador;
- Contrabandista;
- Guardia;
- Agente Darkhaven;
- trabajador del faro;

puede existir en dos contextos distintos:

### Encounter Card
Representa a la persona física que ya existe en el World Engine y participa en la confrontación. Master-controlled. No es una invocación.

### Page de tipo Memory/Echo adquirida
Representa la impresión pictomántica que la experiencia dejó en el Spellbook. Puede ser deck-legal si el sistema de recompensa la crea. No es el individuo físico original.

No es obligatorio que el nombre de la carta diga “Memoria de…”. La distinción debe vivir en el tipo/subtipo y en la procedencia de la Page.

## 8. Función de onboarding de los starters

Darkhaven permite enseñar el juego desde acciones reales del sistema, no mediante mecánicas ficticias de tutorial.

El recorrido pedagógico que los tres starters deben soportar es:

```text
EXPLORATION
-> MOVEMENT / PERCEPTION / INTERACTION / OBJECT_ACTION
-> FACT o Knowledge relevante
-> acción con requirement real
-> check Adventure sólo si la acción tiene check authored
-> COMBAT_CONFRONTATION autorizado por World Engine
-> Arena con el starter elegido
-> resultado vuelve al World Engine
-> consecuencia persistente
-> primera Page adquirida desde una experiencia real
```

No se añade “calibración de ManaDriver”, tirada especial de tutorial, mano forzada ni acción que el runtime no posea.

## 9. Distribución pedagógica

Los tres starters comparten veinte cartas para asegurar el mismo vocabulario base, pero sus dieciséis cartas propias cambian el énfasis:

- VIGILANCIA: observar, robar, negar, devolver.
- RUPTURA: atacar, crecer, presionar, daño directo.
- CONTENCIÓN: bloquear, resistir, desarrollar Battlefield, ganar tempo.

Así el tutorial no necesita saber qué starter eligió el jugador para enseñar las reglas fundamentales; sólo cambia la forma en que el jugador resuelve el encuentro.

## 10. Pendientes antes de implementación

### P0 — Perfil del protagonista
Fijar el perfil de afinidad/cristales del agente protagonista de Faro Ahogado. Sólo entonces se asignan pips y requisitos concretos a cada Page.

### P0 — Card effects
Al implementar, utilizar primero efectos ya cableados en el runtime actual. Cualquier efecto sólo presente como authoring debe marcarse y no venderse como ejecutable hasta cablearlo.

### P0 — Primera recompensa de campaña
Generalizar el desbloqueo Adventure -> Collection. El prototipo actual demuestra el concepto con una recompensa hardcodeada, pero Faro Ahogado necesita una autoridad general para crear/otorgar Pages desde hechos del mundo.

### P1 — Encounter humans
Definir schema/flag claro para distinguir `WORLD_ENTITY_CARD` de `SPELLBOOK_PAGE`, aunque ambos puedan compartir renderer.

### P1 — Memory/Echo provenance
Definir metadata de procedencia para una Page ganada por experiencia sin obligar a que el nombre visible use el prefijo “Memoria de”.

## 11. Criterio de cierre del diseño

Los tres starters estarán listos para entrar al runtime cuando:

1. el protagonista tenga afinidades/cristales fijados;
2. cada Page tenga pips, coste, dificultad y efecto ejecutable;
3. cada deck sume exactamente 60;
4. ninguna Creature institucional represente a una persona física;
5. el onboarding pueda usar cualquiera de los tres sin manos forzadas;
6. el primer Encounter pueda regresar una consecuencia al World Engine;
7. la primera Page adquirida por campaña entre a Collection mediante una autoridad general y no un ID hardcodeado.
