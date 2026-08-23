# SIZA — Catálogo General de Conocimientos

Catálogo maestro de **240 Knowledge IDs** para Player y NPC.

## Regla central

El **parámetro** resuelve el obstáculo; el **Knowledge** define qué entiende el personaje, qué información puede interpretar, qué acciones profesionales habilita y qué bonus pertinente recibe.

Los Knowledge no sustituyen FUE, AGI, COO, INT, PER o PSI.

## Escala

- 0 — Ignorante
- 1 — Familiar
- 2 — Entrenado: `-1` a dificultad pertinente
- 3 — Profesional: `-2`; rutina profesional sin tirada cuando no hay riesgo relevante
- 4 — Experto: `-3`; interacciones especializadas
- 5 — Maestro: `-4`; interpretación excepcional

## Volúmenes

1. [Espacio a energía](01_espacio_a_energia.md) — Geografía, navegación, Niebla, manarales y minería. **60 Knowledge.**
2. [Ingeniería a medicina](02_ingenieria_a_medicina.md) — Ingeniería, economía, pesca, ecología y salud. **60 Knowledge.**
3. [Sociedad a crimen](03_sociedad_a_crimen.md) — Sociedad, política, Casas, religión y clandestinidad. **60 Knowledge.**
4. [Social a dinámico](04_social_a_dinamico.md) — Psicología, investigación, supervivencia, artes y conocimientos locales/dinámicos. **60 Knowledge.**

**Total: 240 conocimientos.**

## Separación obligatoria de datos

- **Knowledge:** competencia general y reutilizable.
- **Fact:** hecho concreto que el personaje conoce.
- **Rumor:** información no confirmada.
- **Secret:** hecho verdadero restringido por acceso, facción o descubrimiento.
- **Memory:** experiencia personal que puede cambiar relaciones y decisiones.

Un NPC con `PESCA 4` no sabe automáticamente quién robó una red ayer. Un NPC sin `PESCA` sí puede saberlo si lo presenció.

## Integración con el Master IA

Cuando Qwen responde como un NPC, el contexto debe limitarse a los Knowledge, Facts, Rumors, Secrets y Memories que ese NPC posee. El RAG no debe convertir a cada NPC en una interfaz omnisciente del World Book.
