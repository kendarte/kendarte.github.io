# SIZA
SISTEMA DE PLAYER, NPC Y SIMULACIÓN DE PERSONAS
# Stats de aventura, conocimientos, Jobs, virtudes, defectos, necesidades, relaciones, memoria, autonomía y reglas de interacción.

# Contenido
0. Resumen ejecutivo
1. Dos capas de ficha: aventura y persona
2. Stats de aventura: seis familias de tiradas
3. Cuándo existe una tirada
4. Modos de resolución
5. Knowledge: qué entiende una persona del mundo
6. Job: qué hace una persona dentro de la sociedad
7. Virtudes y defectos: cómo decide
8. Necesidades y estados temporales
9. Relaciones y memorias
10. Utility AI y autonomía tipo Sim
11. Movimiento persistente Room por Room
12. Interacción Player ↔ Mundo ↔ NPC
13. Control de información y RAG del Master
14. Generación de personas desde edificios y Jobs
15. Contratos de datos
16. Ejemplo completo de NPC
17. Ejemplo de resolución de interacción
18. Reglas de seguridad mecánica contra improvisación del LLM
19. Criterios de prueba
20. Orden de implementación

# 0. Resumen ejecutivo
Siza necesita que Player y NPC dejen de ser “personajes narrados por Qwen” y se conviertan en entidades persistentes de simulación. El espacio ya se modela como un MUD basado en Rooms, Exits, objetos y estado. Este documento define la otra mitad: la persona que ocupa ese espacio.
Una persona se modela con dos capas de datos. La primera contiene los seis Stats de aventura y responde si puede superar un obstáculo. La segunda contiene Knowledge, Job, Virtues, Flaws, Needs, Relationships, Memories y Temporary States; esta capa responde qué información posee, qué acciones conoce, cómo toma decisiones y qué está intentando hacer ahora.

# 1. Dos capas de ficha: aventura y persona
## 1.1 Capa A — Stats de aventura
Los Stats de aventura son FUE, AGI, COO, INT, PER y PSI. Se utilizan para resolver obstáculos. No describen personalidad, profesión ni conocimiento. Dos personas con los mismos seis valores pueden comportarse de forma completamente diferente.

## 1.2 Capa B — Perfil de persona / simulación
Esta capa determina cómo la entidad interactúa con el mundo entre tiradas. Es la base del comportamiento autónomo y del conocimiento contextual de los NPC.
- Knowledge — qué entiende, reconoce, puede explicar o interpretar.
- Job — qué hace profesionalmente, dónde trabaja, qué responsabilidades tiene y qué acciones rutinarias domina.
- Virtues — tendencias relativamente estables que empujan decisiones en una dirección.
- Flaws — tendencias relativamente estables que introducen sesgos, riesgos o prioridades conflictivas.
- Needs — presiones inmediatas como hambre, descanso, dinero, seguridad, deber o vínculo social.
- Relationships — cómo valora a personas concretas.
- Memories — eventos pasados que deben afectar decisiones y diálogo futuro.
- Temporary States — condiciones temporales que alteran prioridades sin reescribir personalidad.

# 2. Stats de aventura: seis familias de tiradas
La elección del parámetro no depende del verbo genérico ni del Job. Depende del obstáculo concreto. Un Job puede habilitar la acción, aportar contexto o reducir dificultad, pero no sustituye al atributo.
## FUE — Fuerza
Función: Vencer resistencia física mediante potencia corporal.
Se usa cuando: El obstáculo consiste en peso, empuje, agarre, tracción o fuerza sostenida.
No cubre: Precisión, equilibrio, diagnóstico o voluntad.
- Abrir una compuerta atascada.
- Sostener una puerta mientras otro personaje pasa.
- Arrastrar una carga o recoger peso durante una faena.
## AGI — Agilidad
Función: Mover correctamente el cuerpo completo en el espacio.
Se usa cuando: El obstáculo exige equilibrio, salto, esquiva, trepar, reacción corporal o tránsito por terreno inestable.
No cubre: Trabajo fino con manos/herramientas o fuerza bruta.
- Cruzar una cubierta durante tormenta.
- Atravesar una estructura rota.
- Esquivar un objeto que cae.
## COO — Coordinación
Función: Precisión motora, control fino y ejecución técnica.
Se usa cuando: La acción depende de mano-ojo, herramienta, mecanismo, nudo o procedimiento delicado.
No cubre: Comprender qué hacer o mover el cuerpo entero.
- Manipular una cerradura con herramienta.
- Operar un aparejo.
- Tallado o reparación delicada bajo presión.
## INT — Inteligencia
Función: Comprender, comparar, diagnosticar, deducir o planificar información.
Se usa cuando: El obstáculo es conceptual, técnico o deductivo.
No cubre: Detectar sensorialmente una pista que todavía no se ha percibido.
- Diagnosticar una bomba desconocida.
- Interpretar genealogías/documentos.
- Elegir una técnica adecuada a un problema.
## PER — Percepción
Función: Obtener información no trivial mediante los cinco sentidos.
Se usa cuando: El Player realiza una acción derivada de vista, oído, olfato, tacto o gusto y existe incertidumbre significativa.
No cubre: Interpretar técnicamente la pista; inventar información no existente.
- Examinar un sello para ver si fue manipulado.
- Escuchar detrás de una puerta.
- Oler un líquido o palpar una pared buscando un hueco.
## PSI — Psique
Función: Resistir o imponer voluntad, identidad, estabilidad mental y concentración frente a presión psíquica o anómala.
Se usa cuando: El obstáculo ataca voluntad, identidad, miedo, interferencia mental o fenómenos de Niebla/maná.
No cubre: Sustituir automáticamente todo el sistema social normal.
- Resistir una voz de Niebla.
- Mantener identidad bajo una presencia.
- Sostener concentración frente a interferencia sobrenatural.

# 3. Cuándo existe una tirada
Lo cotidiano sucede sin dado. El motor sólo crea una tirada cuando el resultado es incierto y esa incertidumbre tiene importancia mecánica.
- Existe oposición activa.
- Existe riesgo o consecuencia relevante.
- Existe presión de tiempo o recurso.
- Existe información oculta cuya detección no es automática.
- Existe una condición física, técnica, mental o contextual que puede impedir la acción.
Ejemplos sin tirada: atravesar una puerta abierta, sentarse, comprar un artículo disponible al precio anunciado, caminar entre Rooms conectadas y accesibles, preguntar el nombre de un NPC dispuesto a responder.
Ejemplos con tirada: forzar la puerta, ocultar una acción frente a un guardia, detectar una marca diminuta, reparar un mecanismo bajo presión, resistir una presencia o perseguir a alguien que huye.
# 4. Modos de resolución
## 4.1 Directa
Una acción importante, un obstáculo principal y una consecuencia inmediata. Se selecciona el stat que corresponde al obstáculo y se compara contra una dificultad contextual.

## 4.2 Acumular
Trabajo prolongado compuesto por avances reales. Cada etapa puede usar un stat distinto. Fallar consume tiempo, recursos, condición, oportunidad o aumenta riesgo; no significa simplemente “tirar otra vez”.

## 4.3 Confrontar
Existe una oposición activa. Cada parte resuelve el parámetro que corresponde a lo que está haciendo. No es obligatorio enfrentar el mismo atributo contra sí mismo.

## 4.4 Sincronizar
Se utiliza cuando la acción debe coincidir con un patrón temporal/contextual previamente existente. No reemplaza Percepción: primero puede ser necesario detectar el patrón con PER o comprenderlo con INT.

# 5. Knowledge: qué entiende una persona del mundo
Knowledge es una base de datos de competencias e información. Su función principal NO es sumar bonos. Determina qué hechos puede interpretar una persona, qué acciones entiende, qué vocabulario maneja, qué información puede recuperar el Master cuando habla como ese NPC y qué interacciones especiales aparecen para el Player.
## 5.1 Diferencia entre PER, INT y Knowledge

Un personaje con PER alta y Knowledge bajo puede observar muy bien sin saber qué está viendo. Un profesional con PER mediocre puede reconocer patrones técnicos que un lego no entiende, siempre que logre percibir los indicios necesarios.
## 5.2 Funciones obligatorias de un Knowledge
- Information Gate — autoriza hechos y fragmentos de World Book que un NPC puede utilizar.
- Interpretation — convierte observaciones en significado técnico/social/cultural.
- Interaction Unlock — habilita acciones o preguntas especializadas.
- Difficulty Context — puede reducir dificultad o eliminar la necesidad de una tirada cuando algo es rutina profesional.
- Vocabulary — permite al NPC hablar con terminología y precisión apropiadas.
- Recognition — reconoce símbolos, señales, objetos, profesiones, facciones o procedimientos.
## 5.3 Jerarquía de conocimientos
Los conocimientos deben organizarse por dominios y especializaciones para no crear miles de habilidades aisladas.

## 5.4 Niveles propuestos
- 0 — Sin conocimiento: sólo experiencia común.
- 1 — Familiaridad: reconoce términos y hechos básicos.
- 2 — Competencia básica: puede realizar tareas simples sin supervisión.
- 3 — Profesional: conocimiento suficiente para ejercer un Job normal.
- 4 — Experto: interpreta casos difíciles y detecta anomalías del oficio.
- 5 — Autoridad/Maestría: conocimiento raro; puede enseñar, innovar o diagnosticar situaciones excepcionales.
Estos niveles son una escala mecánica propuesta y pueden ajustarse durante balance. Lo importante es que cada nivel tenga permisos concretos, no sólo un modificador numérico.
# 6. Job: qué hace una persona dentro de la sociedad
Job sitúa a la persona dentro de la simulación económica y social. Define workplace, horario, responsabilidades, red profesional, acciones rutinarias, ingresos y conocimientos mínimos. No define personalidad ni sustituye Stats.

## 6.1 Job y edificio
Los edificios crean Job Slots. Un NPC existe profesionalmente porque ocupa uno de esos slots. Si el edificio cierra, pierde cuota, es destruido o capturado, los Jobs afectados cambian de estado; esto puede producir desempleo, migración, cambio de rutina o eventos.

## 6.2 Carreras y progresión
Un Job puede formar una carrera, especialmente en instituciones de facción. La promoción depende de Knowledge, experiencia, relaciones, reputación, vacantes y estructura disponible.

# 7. Virtudes y defectos: cómo decide
Virtues y Flaws son pesos de decisión relativamente permanentes. No son alineamientos absolutos ni simples bonificadores de tirada. Deben modificar qué opciones obtiene mayor prioridad cuando el NPC enfrenta alternativas.

Virtudes y defectos pueden coexistir y contradecirse. Esa contradicción es deseable porque produce personas. Un NPC puede ser leal 5, codicioso 4, cobarde 3 y compasivo 2. Puede aceptar sobornos normalmente y aun así negarse a vender a su hermana.
## 7.1 Regla de aplicación
- No modificar tiradas físicas por defecto.
- No escribir “actúa honorable” como instrucción libre. Debe existir una lista de decisiones afectadas.
