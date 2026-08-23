- Pueden modificar selección de objetivo, disposición social, riesgo tolerado, honestidad, cooperación, huida, denuncia, precio, secreto o lealtad.
- Las intensidades sirven como pesos para el Utility AI y como contexto para Qwen después de que el motor selecciona la intención.
# 8. Necesidades y estados temporales
Las Needs son presiones dinámicas. Los Temporary States son modificadores temporales. Juntos permiten autonomía tipo Sim sin alterar la personalidad base.
## 8.1 Necesidades recomendadas
- Hambre / alimentación.
- Descanso / fatiga.
- Seguridad.
- Dinero / solvencia.
- Deber / obligaciones de Job o facción.
- Vínculo social / familia.
- Salud / condición.
- Objetivo personal activo.
No todas necesitan mostrarse al jugador ni actualizarse cada segundo. Se evalúan en pulsos de simulación y sólo cuando pueden cambiar una decisión relevante.
## 8.2 Estados temporales
- HAMBRIENTO
- AGOTADO
- HERIDO
- ASUSTADO
- FURIOSO
- EBRIO
- ENDEUDADO
- EN_DUELO
- ENAMORADO
- INSPIRADO
- ENFERMO
- BAJO_ALERTA
Un estado temporal puede modificar utilidad de acciones, disponibilidad de interacciones, velocidad, disposición social o ciertos checks. Debe tener origen, intensidad y duración/condición de salida.

# 9. Relaciones y memorias
## 9.1 Relaciones
Una relación es específica entre dos personas. No se reduce a “amistad”. Puede almacenar varios ejes porque respeto, miedo y confianza pueden coexistir.

La relación con el Player utiliza el mismo esquema y por tanto no requiere un sistema especial de “reputación de diálogo”.
## 9.2 Memorias
Memory registra eventos suficientemente importantes para alterar conducta futura. Cada memoria tiene sujeto, hecho, importancia, carga emocional, certeza y fecha. Las memorias pueden degradarse, reinterpretarse o convertirse en rumor si el diseño lo requiere.

# 10. Utility AI y autonomía tipo Sim
Los NPC no necesitan guiones completos. En cada pulso relevante, el motor genera objetivos válidos desde sus Needs, Job, Relationships, Faction Orders, Events, Virtues/Flaws y Current State; después calcula una utilidad y selecciona una acción. Qwen puede narrar esa acción, pero no la elige libremente.

## 10.1 Fuentes de utilidad
- Need pressure — qué tan urgente es hambre, descanso, dinero, seguridad, deber o vínculo.
- Job duty — si existe turno, responsabilidad o consecuencia por abandonar el puesto.
- Virtues/Flaws — pesos de personalidad relevantes para esa decisión.
- Relationship — valor de las personas afectadas.
- Memory — experiencias previas asociadas a actor, lugar o situación.
- Faction order — órdenes institucionales y consecuencias de obedecer/desobedecer.
- World event — peligro, escasez, crimen, fiesta, alarma o crisis.
- Feasibility — la acción debe ser físicamente posible en el grafo MUD.
## 10.2 Frecuencia de simulación
No es necesario simular cada NPC a cada segundo. La autonomía puede evaluarse por ticks discretos y por eventos. NPC cercanos al Player reciben resolución fina Room por Room; NPC lejanos pueden usar desplazamiento abstracto entre checkpoints siempre que el resultado final respete ruta, tiempo y accesibilidad.
# 11. Movimiento persistente Room por Room
Todo NPC materializado comparte el mismo grafo espacial que el Player. Debe conocer current_room, destination, route, current_action y reason. El motor espacial, no el LLM, valida cada transición.

Esto permite cruzarse con NPC, seguirlos, encontrarlos ausentes del trabajo, interceptarlos o descubrir que una tienda está cerrada porque su propietario realmente se marchó.

# 12. Interacción Player ↔ Mundo ↔ NPC
El input continúa siendo lenguaje natural. El parser transforma la intención en una acción estructurada. La ficha del Player determina qué interacciones son posibles y qué información puede comprender.

## 12.1 Interacciones emergentes por Knowledge
El mismo NPC ofrece una profundidad distinta según los conocimientos del Player. No es necesario mostrar botones, pero el parser debe reconocer opciones habilitadas.

# 13. Control de información y RAG del Master
Cada NPC debe tener un filtro de conocimiento antes de consultar el World Book. El RAG no puede entregar al personaje información sólo porque está en el corpus. El motor construye una consulta limitada por Knowledge, Job, Memories, Location, Relationships y hechos públicos de la escena.

El Master puede conocer la respuesta objetiva para administrar el mundo y aun así hacer que el NPC diga que no sabe. Esta separación es obligatoria.
## 13.1 Tres niveles de verdad
- World Truth — lo que realmente existe o ocurrió.
- NPC Knowledge — lo que esa persona sabe, cree o recuerda.
- Player Discovery — lo que el personaje jugador ha descubierto.
Los rumores pueden ser falsos sin alterar World Truth. Una memoria puede ser incorrecta. Qwen debe recibir claramente qué capa está narrando.
# 14. Generación de personas desde edificios y Jobs
La población concreta se genera desde la infraestructura, no como una bolsa aleatoria de NPC. Los edificios crean Job Slots; los Jobs ocupados crean trabajadores; los trabajadores crean hogares y relaciones; el resto de la población puede permanecer abstracta hasta que necesite materializarse.

## 14.1 Qué viene del Job y qué se genera aparte
- Job aporta: workplace, horario, responsabilidades, conocimientos mínimos, acciones profesionales y red ocupacional.
- Generador de persona aporta: stats base, virtudes/defectos, relaciones familiares, necesidades, gustos/objetivos y variación individual.
- Mundo aporta: facción, cultura local, economía, riesgos, religión dominante, disponibilidad de vivienda y eventos.
- Historia aporta: memorias y relaciones acumuladas durante la partida.
# 15. Contratos de datos
Los siguientes contratos son deliberadamente legibles. No son todavía un schema de implementación definitivo, pero sí fijan qué información debe existir.
## 15.1 PERSON

## 15.2 KNOWLEDGE

## 15.3 VIRTUE / FLAW

## 15.4 MEMORY

## 15.5 DECISION CANDIDATE

# 16. Ejemplo completo de NPC
Ejemplo ilustrativo de cómo todas las capas producen una persona coherente sin depender de un prompt libre.

Si el Player pregunta por pesca, Mara puede utilizar información profesional. Si pregunta por ingeniería de un reactor, no. Si alguien amenaza a su familia, Lealtad familiar altera sus prioridades. Si está endeudada, la necesidad de dinero puede aumentar temporalmente su tolerancia al soborno. Si Nereida salvó a su hijo, una memoria puede modificar su relación y futuras decisiones.
# 17. Ejemplo de resolución de interacción
Escena: Nereida entra a una pescadería. Existe una caja con una captura en mal estado y Mara está presente.

La IA no decide que el pescado estaba malo, no decide qué sabe Mara y no inventa la razón por la que intenta venderlo. Sólo convierte la resolución sistémica en lenguaje natural.
# 18. Reglas contra improvisación del LLM
- Qwen no asigna nuevos Stats, Knowledge, Virtues, Flaws, Jobs o relaciones durante una conversación salvo que un sistema autorizado produzca ese cambio.
- Qwen no puede conceder conocimiento a un NPC porque “tendría sentido”. Debe existir en Knowledge, Job, Memory o hechos públicos.
- Qwen no decide current_room ni teletransporta NPC.
- Qwen no crea un nuevo objetivo persistente sin que el Utility AI/evento lo autorice.
- Qwen puede variar redacción, tono y gestos dentro de los límites de la intención y personalidad seleccionadas.
- Un NPC puede decir “no sé”, equivocarse o repetir un rumor si su capa de conocimiento lo exige.
- Knowledge no sustituye PER: saber de pesca no permite ver un detalle que físicamente no se percibió.
- PER no sustituye Knowledge: ver una anomalía no concede automáticamente su interpretación técnica.
- Job no sustituye Stats: saber cómo hacer una maniobra no garantiza ejecutarla bajo una dificultad física real.
# 19. Criterios de prueba
El sistema se considera funcional cuando supera pruebas donde el mismo mundo produce respuestas distintas por las diferencias reales entre personas.
- NPC sin Knowledge relevante responde “no sé” aunque el World Book contenga la respuesta.
- Dos NPC con el mismo Job pero distintos Virtues/Flaws toman decisiones diferentes ante un soborno.
- Un NPC abandona el trabajo por una emergencia y puede ser encontrado recorriendo Rooms hacia su destino.
- El Player con Knowledge especializado obtiene interpretación adicional de un mismo Sensory Fact.
- Una memoria importante modifica relación y decisión en encuentros posteriores.
- Un estado temporal cambia conducta y desaparece al resolverse su condición.
- Una estructura cerrada elimina temporalmente Jobs/rutinas asociados y produce consecuencias sociales.
- El Master narra una decisión seleccionada por sistema sin inventar una nueva intención incompatible.
# 20. Orden de implementación
Para no intentar simular una sociedad completa desde el primer build, la implementación debe hacerse por capas verificables.
1. 1. PERSON base — Stats + current_room + home/workplace + Job.
1. 2. Knowledge — Dominios, niveles, permisos de información y interaction unlocks.
1. 3. Parser de interacción — Mapear lenguaje natural a action / target / stat / mode / knowledge context.
1. 4. Relationships + Memory — Persistencia social mínima con Player y NPC cercanos.
1. 5. Virtues + Flaws — Utility modifiers de decisión.
1. 6. Needs + Temporary States — Presiones dinámicas y cambios temporales.
1. 7. Utility AI — Selección de objetivos y acciones autónomas.
1. 8. NPC locomotion — Rutas Room por Room sobre el mapa persistente.
1. 9. Job simulation — Turnos, ausencia, producción, salario y consecuencias.
1. 10. World feedback — Eventos personales que afecten edificios, facciones y economía.

# Conclusión
El Player y los NPC deben compartir una misma ontología de persona. La diferencia es control: el Player elige intención mediante lenguaje natural; los NPC la eligen mediante Utility AI. Ambos interactúan con el mismo mapa MUD, usan los mismos Stats de aventura, poseen Knowledge limitado, ocupan Jobs, mantienen relaciones y memorias y pueden ser afectados por estados temporales. Con esto, Siza deja de depender de personalidad improvisada por el LLM y obtiene individuos persistentes cuya conducta puede explicarse por datos del mundo.

| Principio rector: el mapa persistente define dónde existe una persona. Su ficha de simulación define qué puede hacer, qué sabe, qué hace, qué quiere, a quién le importa y qué recuerda. El Master IA sólo interpreta y narra esos datos. |
| --- |

| Versión | 0.1 |
| --- | --- |
| Tipo | Documento mecánico separado del World Book |
| Estado | Arquitectura base para congelar antes de implementar NPC autónomos |
| Dependencia | SIZA — Sistema de Mundo Persistente MUD v0.1 |
| Alcance | Player y NPC comparten el mismo modelo de persona |
