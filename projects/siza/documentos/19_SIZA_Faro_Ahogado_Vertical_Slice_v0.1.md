# SIZA — Faro Ahogado Vertical Slice v0.1

**Estado:** contrato canónico de implementación
**Campaña:** Faro Ahogado
**Autoridad:** World Engine
**Principio:** Acción y Consecuencia
**Datos ejecutables:** `siza-world-engine/overlay/world/faro_ahogado_cards.py`

## 1. Premisa canónica

El Culto de las Arañas está sustituyendo en secreto a los habitantes de un pueblo por Alternos. Cada sustitución aumenta la penetración de la Niebla y acerca al culto a contaminar la reliquia del templo-faro. La degradación de PSI y PER hace que habitantes y visitantes pierdan estabilidad, memoria y capacidad de reconocer aquello que los reemplaza.

La misión de Darkhaven es descubrir lo que ocurre, conservar suficientes personas y rutas funcionales, asegurar la Linterna Etérica, llegar al Faro Ahogado y activarlo antes de que la contaminación vuelva irreversible la situación.

El conflicto no consiste solamente en derrotar un enemigo. El jugador decide a quién escucha, a quién protege, qué riesgo acepta, qué información persigue y qué daño deja detrás. Esas decisiones cambian el pueblo que encontrará después.

## 2. Fantasía del jugador

El jugador entra en un lugar que todavía parece cotidiano, pero cuyas personas, recuerdos y reflejos han empezado a contradecirse. Investiga mediante acciones contextuales o lenguaje libre, resuelve checks reales, utiliza su Spellbook cuando existe una confrontación autorizada y construye una versión única del desastre mediante sus consecuencias.

La promesa del vertical slice es:

> El mundo recuerda lo que hiciste, quién lo vio, quién fue abandonado y qué ocupó su lugar.

## 3. Autoridad del sistema

El DM IA puede:

- interpretar lenguaje libre;
- elegir entre capacidades y blancos presentes;
- ordenar cartas de campaña elegibles;
- pedir contexto autorizado;
- narrar el resultado ya resuelto.

El DM IA no puede:

- decidir una tirada;
- crear una salida, objeto, NPC o Fact;
- convertir una persona por iniciativa propia;
- declarar una carta resuelta;
- alterar Niebla, Karma, PSI, PER o estado del Faro;
- declarar victoria o derrota.

La secuencia obligatoria es:

```text
intención del jugador
→ interpretación limitada
→ capability/acción existente
→ requisitos
→ check del World Engine
→ rama de éxito o fallo de la carta
→ mutaciones persistentes
→ Facts, memoria, goals y reacción social
→ selección de nuevas cartas elegibles
→ narración grounded
```

## 4. Estado persistente mínimo

La campaña debe conservar como mínimo:

- `fog_level`;
- `karma`;
- `faro_face_up_turns`;
- `faro_activated`;
- `master_exiled`;
- hitos alcanzados;
- cartas llamadas;
- presagios preparados;
- recompensas;
- estado y ubicación de cada NPC especial;
- PSI/PER actual de personas afectables;
- tags y estado de cada Tierra revelada;
- cultistas y hostiles presentes;
- Facts conocidos por jugador y NPC;
- testigos y consecuencias sociales de acciones públicas.

Una consecuencia que sólo aparezca en prosa no cuenta como consecuencia implementada.

## 5. Vocabulario de parámetros

El World Engine conserva sus parámetros de aventura:

```text
FUE, AGI, COO, INT, PER, PSI
```

Las cartas impresas usan `POW` para decisiones físicas. En el vertical slice esas pruebas se authoran como `FUE` y conservan `printed_stat=POW` para presentación. `PSI` y `PER` se comparten sin traducción.

`DEF` pertenece a criatura/Encounter/TCG y no se convierte silenciosamente en un parámetro de aventura.

`DRIVER` es una competencia de equipo usada únicamente cuando una acción authorada lo permita, como la activación final del Faro.

## 6. Cartas canónicas incluidas

Las catorce cartas recibidas quedan representadas en datos ejecutables:

1. `Aldeanos Paranoicos` — Elección / Pueblo / Social.
2. `Visión del Agua` — Elección / Agua / Revelación.
3. `Niña de las Flores` — Criatura / Aldeano Especial.
4. `La Niña de las Flores` — Elección / Aldeano Especial.
5. `Portavoz de la Seda Negra` — Criatura Evento / Culto / Sacerdote.
6. `Capilla Hundida` — Land / Pueblo / Santo / Agua / Closed.
7. `Rostro de Nadie` — Criatura Evento / Alterno / Niebla.
8. `Alterno de las Rosas Marchitas` — Criatura Evento / Alterno / Niebla / Flor.
9. `La Procesión Sin Rostros` — Elección / Culto / Niebla / Pueblo.
10. `Voz en la Niebla` — Evento / Niebla / Mente.
11. `Vecino Reemplazado` — Criatura Evento / Alterno / Niebla.
12. `Faro Ahogado` — Land / Objetivo / Costa / Torre / Niebla / Closed.
13. `El Pescador que Olvidó el Mar` — Elección / Aldeano Especial.
14. `Rostro en el Vidrio` — Criatura Evento / Ánima / Niebla / Reflejo.

Cada definición contiene:

- ID estable;
- tipo y tags;
- parámetros impresos cuando existen;
- triggers;
- requisitos;
- check autoritativo;
- efectos de éxito;
- efectos de fallo;
- llamadas a otras cartas;
- hitos de campaña;
- mutaciones marcadas como persistentes y autoritativas del World Engine.

## 7. Cadenas reactivas obligatorias

### Niña de las Flores

```text
preguntarle qué vio
→ PSI 7
→ éxito: revela/prepara el Alterno como Presagio
→ fallo: Niña recibe -1 PSI
→ PSI negativa llama Rostro Prestado
→ Niña es reemplazada por Alterno de las Rosas Marchitas
→ una Tierra Pueblo gana Niebla
→ la Tierra bloquea recuperación de PSI
→ REPLACEMENT_PROOF
```

La sustitución debe cambiar la entidad presente. No puede resolverse mostrando únicamente otro retrato o párrafo.

### Procesión Sin Rostros

Seguir la procesión con éxito descubre una Tierra del Culto y marca una ruta real. Interrumpir puede salvar a los aldeanos o llamar `Rito de Hilos Negros`. Dispersar puede reducir Niebla o degradar la PER de los aldeanos.

### Pescador que Olvidó el Mar

Pedirle ruta puede colocar una Tierra Costa/Agua entre las siguientes opciones. Dejarlo atrás no hace daño inmediato, pero al final del tramo pierde PER. Si su PER queda negativa, Vorsha puede abrir la cadena `Fe Torcida`.

### Visión del Agua

Buscar reflejo puede mejorar el próximo recorrido o llamar `Rostro en el Vidrio`. Lavar una marca soluciona una amenaza individual pero aumenta la Niebla global.

### Capilla Hundida

La Capilla requiere la Llave de los Advenidos. Al abrirse llama un Evento Santo. Si después recibe Niebla, pierde el tag Santo y llama un Evento de Ánima.

### Faro Ahogado

La ambigüedad circular de la carta impresa queda resuelta en dos acciones:

1. `Abrir el acceso con la Linterna Etérica`: requiere Linterna y ausencia de hostiles; remueve `Closed`.
2. `Activar el Faro`: requiere acceso abierto, Linterna y ausencia de hostiles; tira PER 9 o Driver 9.

Mientras permanezca boca arriba, cada turno llama un Evento de Ánima y aumenta Niebla. El éxito final marca `FARO_RESOLVED`, exilia al Master y gana la campaña.

## 8. Hitos y beats autoritativos

Los nombres históricos de beats se conservan para no romper partidas guardadas, pero sus condiciones dejan de aceptar acciones genéricas.

### FA-BEAT-LEAD

Requiere `REPLACEMENT_PROOF`. Compartir cualquier Fact ya no completa este beat.

### FA-BEAT-ROUTE

Requiere `ROUTE_IDENTIFIED`. Caminar por cualquier Exit ya no completa este beat.

### FA-BEAT-MEANS

Requiere `EXPEDITION_MEANS_SECURED`: Linterna, acceso y medios confirmados. Usar cualquier objeto ya no completa este beat.

### FA-BEAT-CROSSING

Requiere `CLIMAX_THREAT_RESOLVED`, emitido por el retorno autoritativo de la confrontación que bloqueaba el Faro. Ganar cualquier combate no basta.

### FA-BEAT-CLIMAX

Requiere `FARO_RESOLVED`. Resolver cualquier acción del mundo ya no completa la campaña.

## 9. Master Deck y cartas de aventura

El Master Deck del Director no sustituye las cartas de aventura.

- El Director rankea presión y oportunidades según estado actual.
- Cada carta del Director señala qué cartas reales puede intentar presentar.
- La carta real sólo entra si sus requisitos de mundo se cumplen.
- Elegibilidad no equivale a ejecución.
- El Director nunca genera la consecuencia de la carta.

## 10. Lenguaje libre y botones

La interfaz debe ofrecer botones contextuales para las acciones legibles de cada carta y objeto. El campo libre permanece disponible para intentos no listados.

Una acción libre válida debe terminar en una de estas rutas:

- capability existente;
- affordance authorada;
- check limitado por el DM Judge;
- rechazo grounded porque el mundo no ofrece soporte.

Después de resolver, el mismo motor de consecuencias utilizado por los botones debe aplicar la rama. Botón y texto no pueden producir reglas diferentes.

## 11. Spellbooks iniciales

Los tres Spellbooks confirmados son:

- Vigilancia;
- Ruptura;
- Contención.

Los tres atraviesan la misma campaña y modifican la forma de resolver encuentros, no el canon del pueblo.

La documentación existente no define todavía tres personajes jugables definitivos. No se asignan nombres, afinidades o biografías por invención. Hasta que ese contenido se cierre, la implementación debe representar tres slots de personaje/deck sin convertirlos en canon falso.

## 12. Dependencias de contenido aún no entregadas

Las catorce cartas llaman nueve piezas no incluidas entre las imágenes recibidas:

- Cultista del Ángulo Negro;
- Evento de Ánima;
- Evento Santo;
- Fe Torcida;
- Grito en la Costa;
- Los Faroles se Apagan;
- Rito de Hilos Negros;
- Rostro Prestado;
- Turba Iracunda.

Los IDs están declarados como dependencias externas válidas. No se inventa su texto ni sus efectos. Antes de cerrar el primer recorrido jugable deben existir sus definiciones reales.

También faltan como contenido authorado:

- Linterna Etérica;
- Llave de los Advenidos;
- condición exacta de derrota del Master;
- identidad y ficha suficiente de Vorsha;
- tres personajes jugables, si la selección será personaje más deck y no solamente deck;
- regla exacta que convierte un personaje marcado por `Voz en la Niebla`.

## 13. Criterio de aceptación del slice

El vertical slice no se considera reactivo hasta que una prueba limpia demuestre:

1. una decisión sustituye persistentemente a un NPC;
2. la sustitución altera una Tierra y cambia las acciones posteriores;
3. una consecuencia aplazada se ejecuta después del cambio de escena;
4. una acción pública produce testigos, Facts y reacción social;
5. una acción libre y su botón equivalente producen la misma mutación;
6. un Encounter TCG devuelve un resultado estructurado al World Engine;
7. el clímax se compone usando Niebla, hostiles, NPC salvados, Karma y recursos acumulados;
8. activar el Faro emite `FARO_RESOLVED` y sólo entonces completa la campaña;
9. reiniciar el cliente no borra las consecuencias;
10. ninguna respuesta del LLM puede fabricar uno de estos estados.

## 14. Siguiente bloque de producción

Con el contrato y las catorce cartas estructuradas, el siguiente trabajo es contenido:

1. definir las nueve cartas dependientes;
2. crear las Rooms/Tierras del recorrido;
3. crear NPC y objetos con identidades estables;
4. conectar cada rule con consequences, Facts y witnesses;
5. conectar botones y lenguaje libre al mismo executor;
6. integrar el primer Encounter con el Combat Bridge;
7. validar persistencia y tres rutas de Spellbook.

No se agrega otro sistema general al World Engine salvo que una de estas cadenas revele un bloqueo concreto.
