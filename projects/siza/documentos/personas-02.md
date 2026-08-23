| PERSON =   ADVENTURE_STATS   + KNOWLEDGE   + JOB   + VIRTUES   + FLAWS   + NEEDS   + RELATIONSHIPS   + MEMORIES   + TEMPORARY_STATES   + CURRENT_GOAL / CURRENT_ACTION   + CURRENT_ROOM |
| --- |

| Regla de diseño: una variable que no cambie información, acciones, decisiones, relaciones, estado o resolución no debe existir. No queremos “flavor stats”. |
| --- |

| FUE 2 AGI 3 COO 4 INT 4 PER 3 PSI 2 |
| --- |

| Atajo conceptual: STATS = qué puede. KNOWLEDGE = qué sabe. JOB = qué hace. VIRTUES/FLAWS = qué tiende a querer. RELATIONSHIPS = por quién cambia sus decisiones. MEMORIES = por qué cambió. NEEDS/STATES = qué le urge ahora. |
| --- |

| Diferencia crítica: PER encuentra la pista; INT entiende lo que significa. AGI controla el cuerpo completo; COO controla precisión. El mismo objetivo puede usar stats distintos si cambia el método elegido por el jugador. |
| --- |

| ACTION: inspect_seal STAT: PER MODE: DIRECT TARGET: BOX-004 DIFFICULTY: 7 |
| --- |

| REPAIR_PUMP Stage 1: INT -> diagnosticar Stage 2: COO -> reparar Stage 3: FUE -> recolocar componente pesado |
| --- |

| perseguidor: AGI objetivo: AGI  forcejeo: FUE vs FUE  disparo preciso contra objetivo evasivo: COO vs AGI  resistencia mental: PSI vs PSI |
| --- |

| El modo de resolución y el stat son decisiones diferentes: primero se identifica el obstáculo; después se define cómo se resuelve. |
| --- |

| PER -> detecta: "el pescado tiene manchas oscuras y olor fuerte" KNOWLEDGE(PESCA) -> interpreta: "estuvo demasiado tiempo fuera de salmuera" INT -> puede deducir: "si toda la captura llegó así, falló la cadena de conservación" |
| --- |

| PESCA   pesca_costera   pesca_de_niebla   grandes_capturas   conservación   aparejos  MANARAL   identificación   extracción   refinado   valoración   seguridad  NAVEGACIÓN   aerobarcos   rutas   clima   cartas  RELIGIÓN   Advenidos   Soledeo   cultos_locales |
| --- |

| JOB: PESCADERO workplace_type: FISHMONGER required_knowledge:   PESCA: 2   CONSERVACION: 2 granted_context:   ECONOMIA_LOCAL: +familiaridad routine:   05:00 lonja   06:00 puesto   13:00 limpieza   14:00 cierre actions:   comprar_captura   evaluar_captura   limpiar_pescado   conservar_producto   vender_producto |
| --- |

| FISHMONGER_T1   1 owner/fishmonger   0-2 assistants   0-1 loader  WINDRAGO_POST_T1   1 leader   6 guards   1 logistics |
| --- |

| PESCADOR I -> PATRÓN DE BOTE II -> MAESTRE PESQUERO III  WINDRAGO AUXILIAR -> GUARDIA -> CABO -> OFICIAL -> COMANDANTE |
| --- |

| VIRTUE: FAMILY_LOYALTY intensity: 5 target: family effects:   protect_family: strong_positive   betray_family: severe_negative   accept_personal_risk_for_family: positive |
| --- |

| FLAW: GREED intensity: 4 effects:   accept_bribe: positive   exploit_scarcity: positive   hide_profitable_goods: positive |
| --- |

| state: ENDEUDADO intensity: 4 source: debt_contract_019 started_at: day_42 expires_when: debt <= 0 effects:   seek_money: +high   accept_bribe: +medium   luxury_spending: -high |
| --- |

| RELATIONSHIP NPC-108 -> NPC-221 role: jefe trust: 25 respect: 60 fear: 40 affection: 5 debt: 0 obligation: 35 |
| --- |

| MEMORY id: MEM-4401 subject: PLAYER fact: "Nereida salvó a mi hijo durante la tormenta" importance: 9 emotion: gratitude certainty: 100 created_at: day_27 effects:   trust_player: +35   help_player: +high |
| --- |

| La personalidad es relativamente permanente. El estado es temporal. La memoria es histórico. La relación es dinámica. La necesidad es inmediata. |
| --- |

| CANDIDATE GOALS work_shift              utility 72 buy_food                 utility 35 visit_sister             utility 48 accept_bribe             utility 40 report_theft             utility 30 protect_child            utility 20  EVENT: child_threatened  protect_child            utility 96 obey_threat              utility 71 report_theft             utility 8 work_shift               utility 12 |
| --- |

| NPC_00481 current_room: CAR-VAR-MARKET-014 destination: CAR-VAR-HOUSE-081 current_action: closing_shop reason: family_emergency route:   MARKET-014 -> STREET-009 -> PLAZA-002 -> STREET-017 -> HOUSE-081 |
| --- |

| El NPC no se teletransporta narrativamente. Si está “en casa”, existe una razón espacial y temporal para que haya llegado a esa Room. |
| --- |

| INPUT: "examino el pescado y le pregunto a la mujer si está bueno"  1. localizar target_object y target_npc en CURRENT_ROOM 2. ACTION_A = perceive / sight+smell 3. resolver PER sólo si existen facts no triviales 4. aplicar KNOWLEDGE(PESCA) para interpretar facts 5. ACTION_B = dialogue_question 6. comprobar knowledge y disposición del NPC 7. NPC responde sólo con información autorizada 8. Qwen redacta la escena |
| --- |

| Player sin PESCA:   hablar / comprar / preguntar  Player con PESCA 3:   evaluar captura   discutir corriente   negociar calidad   preguntar por banco pesquero  Player con CONTRABANDO 3:   reconocer señal clandestina   preguntar usando jerga apropiada |
| --- |

| NPC KNOWLEDGE PESCA_CARIBIANA: 4 ECONOMIA_LOCAL: 3 RUMORES_PUERTO: 2 RELIGION_ADVENIDA: 2 POLITICA_CARIBIA: 1 INGENIERIA_MANARAL: 0  QUESTION: "¿por qué vibra ese reactor?" AUTHORIZED DOMAIN: none NPC RESULT: "No lo sé; pregunte en el taller." |
| --- |

| SETTLEMENT   -> BUILDING INSTANCE     -> JOB SLOTS       -> WORKER NPC         -> HOUSEHOLD           -> PARTNER / CHILDREN / DEPENDENTS         -> RELATIONSHIPS         -> ROUTINE         -> KNOWLEDGE         -> VIRTUES / FLAWS         -> NEEDS         -> EVENTS |
| --- |

| PERSON {   id   name   age   adventure_stats { FUE, AGI, COO, INT, PER, PSI }   knowledge[]   job_id   virtues[]   flaws[]   needs{}   temporary_states[]   relationships[]   memories[]   faction_links[]   home_id   workplace_id   current_room_id   destination_room_id   current_goal   current_action   inventory[]   condition } |
| --- |

| KNOWLEDGE {   id   domain   parent_domain   level 0..5   authorized_facts[]   recognition_tags[]   interaction_unlocks[]   routine_actions[]   difficulty_modifiers[]   vocabulary_tags[] } |
| --- |

| TRAIT {   id   type: VIRTUE | FLAW   intensity 0..5   targets[]   decision_modifiers[]   risk_modifiers[]   social_modifiers[] } |
| --- |

| MEMORY {   id   subject_ids[]   location_id   fact_id / event_id   description_key   importance 0..10   emotion   certainty 0..100   created_at   decay_rule   effects[] } |
| --- |

| DECISION {   action_id   target_id   base_utility   need_weights[]   trait_weights[]   relationship_weights[]   memory_weights[]   job_weight   faction_weight   event_weight   feasibility   final_utility } |
| --- |

| NPC_00481 — Mara Vensal Edad: 42  ADVENTURE STATS FUE 2 | AGI 2 | COO 4 | INT 3 | PER 4 | PSI 3  JOB Pescadera · FISHMONGER-03  KNOWLEDGE Pesca caribiana 4 Conservación 3 Economía local 3 Advenidos 2 Windrago 1  VIRTUES Trabajadora 4 Lealtad familiar 5 Hospitalaria 2  FLAWS Desconfiada 3 Codiciosa 2 Supersticiosa 4  NEEDS Dinero 68 Familia 82 Descanso 33 Seguridad 47  RELATIONSHIPS NPC_00482: hermana / confianza 90 / afecto 85 PLAYER: confianza 15 / afecto 0 / miedo 0  HOME HOUSE-114  WORK FISHMONGER-03  CURRENT_ROOM MARKET-014 |
| --- |

| PLAYER INPUT: "huelo el pescado y le pregunto a Mara si me lo vendería"  A. MOTOR ESPACIAL - Player y objeto comparten Room: sí - objeto accesible: sí - Mara presente: sí  B. PARSER - perceive / smell / target fish_box - dialogue / negotiate / target Mara  C. PERCEPCIÓN - fact visible por olfato: olor anormal - dificultad: 5 - PER resuelve  D. KNOWLEDGE DEL PLAYER - PESCA 0: sólo conoce "huele mal" - PESCA 3: interpreta conservación deficiente  E. NPC INFORMATION - Mara conoce el problema por CONSERVACIÓN 3 - decide si admitirlo según Traits + Relationship + Need dinero  F. DECISIÓN NPC - honestidad/hospitalidad vs codicia/deuda - motor selecciona respuesta/intención  G. MASTER IA - narra la observación y redacta el diálogo autorizado |
| --- |

| Vertical slice recomendado: una estructura civil con 4–6 Rooms, 3 Jobs, 5–8 NPC persistentes y 10–15 Knowledge domains relevantes. Probar movimiento, trabajo, diálogo, Percepción, memoria y una decisión autónoma antes de escalar a toda una ciudad. |
| --- |
