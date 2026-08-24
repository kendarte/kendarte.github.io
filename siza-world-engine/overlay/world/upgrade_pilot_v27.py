from services.consequence_engine import (
    CONSEQUENCE_BUILD,
    get_consequence_registry,
    upsert_consequence_rule,
)


RULE_ID = "TEST-CONSEQUENCE-RANKED-ORDER-MEMORY-001"
ORDER_ID = "TEST-RANKED-ORDER-REPORT-001"
WORKER_ID = "TEST-NPC-KAL-DAR-WORKER-B"
MEMORY_ID = "TEST-AUTO-MEMORY-B-ORDER-CONSEQUENCE-001"
EFFECT_ID = "TEST-AUTO-MEMORY-EFFECT-B-ORDER-001"


def build():
    registry = get_consequence_registry(create=True)
    existing = {
        str(item.get("id") or ""): item
        for item in list(registry.db.rules or [])
        if hasattr(item, "get")
    }
    already = RULE_ID in existing

    rule = {
        "id": RULE_ID,
        "enabled": bool(existing.get(RULE_ID, {}).get("enabled", False)) if already else False,
        "when": {
            "action_type": "ORDER_ISSUED",
            "order_id": ORDER_ID,
            "actor_npc_id": WORKER_ID,
        },
        "recipient_mode": "ACTION_RECIPIENTS",
        "memory": {
            "memory_id": MEMORY_ID,
            "type": "order_issued_consequence",
            "schema": 3,
            "summary": "Registro conductual de prueba: el Trabajador B emitió una orden formal dirigida a este personaje.",
            "decision_effect": {
                "id": EFFECT_ID,
                "enabled": True,
                "value": 20,
                "when": {
                    "type": "ORDER",
                    "issuer_id": "$actor_npc_id",
                },
                "kind": "CONTEXT_BIAS",
                "canon_status": "prototype",
            },
        },
        "canon_status": "prototype",
    }
    upsert_consequence_rule(rule)
    registry.db.build = CONSEQUENCE_BUILD

    caller.msg("Kalnaj Pilot v0.27 aplicado: Action -> Consequence Memory Rules.")
    caller.msg(f"Rule: {RULE_ID} | ORDER_ISSUED por B -> memory persistente en recipients | DISABLED.")
    caller.msg(f"Auto memory: {MEMORY_ID} | effect={EFFECT_ID} | futuras ORDER de B +20.")
    caller.msg("La regla usa acción estructurada; no interpreta prosa ni llama al narrador.")
    caller.msg("La memoria es UPSERT por regla/personaje: repetir occurrences actualiza el mismo recuerdo y no apila +20 indefinidamente.")
    caller.msg("No se modificó posición, hora, jobs, claims, fatigue, obligations, orders, factions, events ni dangers.")
    caller.msg("Prueba: siza-consequences")


build()
