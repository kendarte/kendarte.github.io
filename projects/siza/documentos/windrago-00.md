# SIZA — Sistema de Facciones Persistentes
## Documento 01: Casa Windrago — árbol tecnológico y control territorial

**Estado:** diseño mecánico separado del World Book  
**Versión:** 0.1  
**Base:** canon existente de Caribia; toda ampliación nueva se marca como **PROPUESTA** hasta aprobación.

---

## 1. Objetivo de esta capa

Este documento convierte la Casa Windrago en una facción persistente jugable y simulable, usando una lógica comparable a una raza de un RTS como Warcraft III.

La facción debe poder:

- poseer y perder estructuras;
- construir mediante un Job propio;
- mejorar su centro de mando por grados;
- desbloquear nuevos Jobs mediante edificios y requisitos;
- controlar un asentamiento sin borrar sus estructuras civiles;
- producir respuestas coherentes según su capacidad real;
- cambiar moral y políticamente con el tiempo;
- continuar existiendo aunque el jugador no esté presente;
- transmitir su estado al Master IA para decidir qué puede ocurrir en una escena.

La regla principal es que **la facción no recibe capacidades por “nivel abstracto”**. Las recibe porque existe una cadena material de estructuras, Jobs, reservas, permisos y rutas.

---

## 2. Lo que ya está fijado por el canon

### Identidad Windrago

Windrago ocupa la Corona de Tormenta y conserva el mandato provincial de **protección, refugio, defensa y respuesta de crisis**. Su legitimidad depende de llegar cuando una ruta colapsa, abrir refugios, evacuar y mantener continuidad durante una emergencia.

El canon también fija su riesgo político: una rama Windrago puede degradarse hasta usar la emergencia como excusa para prolongar el mando, cobrar por seguridad o transformar protección en dominio permanente.

Por tanto, Windrago no debe diseñarse simplemente como “la facción militar”. Su fantasía mecánica es:

**PROTEGER → RESISTIR → EVACUAR → CONSERVAR → TOMAR MANDO TEMPORALMENTE.**

Su corrupción natural es:

**PROTEGER → CONTROLAR → JUSTIFICAR EL CONTROL MEDIANTE LA CRISIS.**

### Árbol central canónico

El World Book ya establece esta progresión:

**Puesto de Guardia Windrago I → Baluarte Windrago II → Fortaleza Windrago III**

Y fija los Jobs principales asociados:

**Grado I**
- Guardia de puesto
- Vigía
- Auxiliar de refugio

**Grado II**
- Capitán
- Rescatista
- Ingeniero defensivo
- Escudero de tormenta

**Grado III**
- Comandante
- Caballero de escama
- Estratega
- Convoyes y mando regional de crisis

La patrulla es una **unidad enviada desde una estructura**, no un edificio.

### Recursos y obligaciones canónicas

Todo emblema Windrago colocado sobre una estructura implica una obligación real de mantener:

1. **Agua**
2. **Luz / energía**
3. **Refugio**

El canon también exige población formada, materiales, cuota energética, autoridad y conexión con el grado anterior para mejorar una estructura.

Una estructura puede estar físicamente presente pero no operar si carece de Jobs, reserva, permiso o entradas.

---

## 3. Regla nueva: Facción, control y alineación no son lo mismo

**PROPUESTA**

Para que el sistema no se vuelva rígido, cada estructura y asentamiento debe separar cuatro conceptos:

- **Tipo de estructura:** qué es físicamente.
- **Alineación estructural:** qué árbol la diseñó y qué Jobs puede producir naturalmente.
- **Controlador actual:** qué facción la posee o administra ahora.
- **Estado moral local:** cómo se está comportando esa rama concreta de la facción.

Ejemplo:

Una cisterna es una estructura **COMÚN**. Puede estar controlada por Windrago durante una emergencia sin convertirse mágicamente en una estructura Windrago.

Un Puesto de Guardia es una estructura **WINDRAGO**. Si Ladrones lo ocupan, sigue siendo un Puesto Windrago capturado; sus nuevos ocupantes no adquieren automáticamente formación Windrago ni capacidad de producir guardias legítimos.

Esto permite conquista, infiltración, corrupción y recuperación sin borrar la historia del edificio.

---

## 4. Las cuatro alineaciones de facción

**PROPUESTA DE MARCO — en este documento sólo se desarrolla WINDRAGO.**

Las alineaciones principales que pidió el sistema son:

- **WINDRAGO** — protección, defensa, refugio, crisis y mando.
- **ADVENIDOS** — vínculo, memoria, cuidado, pacto y lectura de tormenta.
- **ECLESIA** — reliquia, claridad, doctrina, cuidado soledeano e intervención religiosa.
- **LADRONES** — contrabando, ocultamiento, falsificación, receptación y coerción clandestina.

Las estructuras **COMUNES** no forman una quinta alineación. Son infraestructura civil neutral o disputable: pescaderías, mercados, cisternas, talleres, escuelas, muelles, viviendas, etc. Una facción puede poseerlas, protegerlas, infiltrarlas o convertirlas en requisito de su árbol sin cambiar su familia estructural.

Después podremos conservar Casas y organizaciones menores como subfacciones sin romper este nivel. Por ejemplo, una estructura Hidraazul puede seguir teniendo propietario y reglas Hidraazul aunque, para el sistema macro de control territorial que estamos construyendo ahora, no sea una de las cuatro alineaciones principales.

---

## 5. Ejes morales persistentes

**PROPUESTA**

La alineación dice **quién es la facción**. Los ejes dicen **en qué se está convirtiendo esa rama local**.

Cada núcleo de facción mantiene cuatro valores de -2 a +2.

### Eje A — Autoridad

- **-2:** autonomía extrema
- **0:** autoridad negociada
- **+2:** jerarquía y mando concentrado

### Eje B — Deber

- **-2:** explotación / beneficio propio
- **0:** intercambio pragmático
- **+2:** servicio / protección colectiva

### Eje C — Método

- **-2:** clandestino / extralegal
- **0:** informal / mixto
- **+2:** institucional / auditable

### Eje D — Dogma

- **-2:** adaptación pragmática
- **0:** tradición flexible
- **+2:** doctrina rígida

### Perfil base Windrago

**Autoridad +2 / Deber +2 / Método +2 / Dogma 0**

Esto expresa la Windrago ideal: jerárquica, protectora, institucional y relativamente pragmática.

La parte importante es que **el perfil puede desplazarse por asentamiento**.

Una guarnición Windrago que salva repetidamente a la población puede mantenerse en:

`A +2 / D +2 / M +2 / G 0`

Una guarnición que prolonga estados de emergencia para controlar comercio puede caer a:

`A +2 / D -1 / M +1 / G +1`

Sigue siendo WINDRAGO, pero ahora el Master sabe que esa rama es autoritaria y oportunista. No necesitamos inventar una facción nueva para representar corrupción local.

---

## 6. Estado mínimo de una facción dentro de un asentamiento

**PROPUESTA**

Cada **presencia de facción dentro de un asentamiento** guarda como mínimo:

```text
alignment: WINDRAGO
faction_presence: 0-5
faction_hq: NONE | PUESTO | BALUARTE | FORTALEZA
faction_leader: NPC_ID
legitimacy: 0-100
population_support: 0-100
reserve_status: 0-100
manpower: número
alert_state: NORMAL | VIGILIA | CERCO | HUNDIMIENTO
axis_authority: -2..+2
axis_duty: -2..+2
axis_method: -2..+2
axis_dogma: -2..+2
controlled_structures: [STRUCTURE_ID]
active_jobs: [NPC/JOB]
current_orders: [ORDER_ID]
```

Un mismo asentamiento puede tener simultáneamente nodos Windrago, Advenidos, Eclesia y Ladrones. Aparte se guarda `dominant_faction`, que indica cuál tiene mayor capacidad efectiva de convertir decisiones en acción.

No hace falta que el LLM calcule esto. El sistema guarda los valores y el Master los consulta.

---

## 7. El líder del asentamiento

**PROPUESTA**

Todo asentamiento debe tener un **líder efectivo** aunque legalmente exista un cabildo, consejo o varias autoridades.

El líder efectivo es la persona cuya decisión tiene mayor capacidad de convertirse en acción en ese momento.

Campos mínimos:

```text
leader_id
leader_name
leader_job
leader_faction
leader_legitimacy
leader_personal_axes
leader_relationships
leader_authority_basis
```

`leader_authority_basis` puede ser:

- elección / cabildo;
- nombramiento noble;
- mando de emergencia;
- autoridad religiosa;
- control económico;
- coerción criminal;
- ocupación;
- pacto local.

Esto permite que un pueblo posea instituciones civiles pero esté de facto dominado por una facción.

### Liderazgo Windrago por escala

El canon ya aporta una progresión de mando que podemos aprovechar:

- **Puesto I:** responsable o jefe de puesto — **PROPUESTA de título**, porque el canon aún no fija un nombre formal para quien dirige cada Puesto.
- **Baluarte II:** Capitán — **CANON**.
- **Fortaleza III:** Comandante — **CANON**.
- **Corona provincial:** Señor/Señora de la Tormenta — **CANON**.

La identidad de los líderes de cada ciudad todavía no está fijada en el World Book y no debe inventarse en esta capa. Se llenará después ciudad por ciudad.

---

# 8. Job constructor Windrago

## Constructor de Fortificación Windrago

**PROPUESTA**

Éste es el equivalente funcional al Peón/Peasant/Worker de una raza RTS.

No es un soldado genérico. Es un trabajador formado para levantar, reparar y mantener infraestructura de emergencia Windrago.

### Grado I — Constructor de Fortificación

Puede:

- levantar un Puesto de Guardia I;
- construir depósitos Windrago;
- preparar refugios y puertas de evacuación;
- reparar estructuras de grado I;
- colocar barricadas y señalización de emergencia;
- trabajar sobre estructuras comunes si existe permiso del propietario.

No puede:

- diseñar un Baluarte;
- certificar una armería;
- modificar un núcleo energético;
- construir infraestructura industrial especializada sin Jobs comunes o Caldamar.

### Grado II — Ingeniero Defensivo

**CANON como Job; ampliación de función propuesta.**

Puede construir y mantener la infraestructura necesaria para un Baluarte, organizar fortificación de sector y supervisar Constructores de Fortificación.

### Grado III — Ingeniero Mayor / Maestro de Fortaleza

**PROPUESTA.**

Especialización avanzada necesaria para proyectos de Fortaleza, grandes compuertas, refugios regionales y reconstrucción estratégica. No reemplaza a ingenieros Caldamar: coordina la arquitectura defensiva y contrata/integra Jobs técnicos externos cuando una obra exige maquinaria especializada.

Esta limitación es importante: Windrago puede tener el mejor plan defensivo de Caribia y aun necesitar a Caldamar para una bomba compleja o a Velacendra para una red logística.

---

# 9. Town Hall Windrago

El centro de la facción es exactamente la progresión ya canónica.

## TIER I — Puesto de Guardia Windrago

**Alineación:** WINDRAGO  
**Función RTS:** Town Hall I + cuartel defensivo básico + centro de alarma local.

### Produce / sostiene

- Constructor de Fortificación I — **PROPUESTA**
- Guardia de Puesto — **CANON**
- Vigía — **CANON**
- Auxiliar de Refugio — **CANON**

### Capacidades

- patrulla local;
- primera alarma;
- registro de incidentes;
- orientación de evacuación;
- botiquín básico;
