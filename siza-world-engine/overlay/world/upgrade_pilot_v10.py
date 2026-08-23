from evennia import search_tag


ENTITY_TAG = "kalnaj_pilot_v03_entities"
ENTITY_CATEGORY = "siza_entity"
UPGRADE_TAG = "kalnaj_pilot_v10_need_dynamics"
UPGRADE_CATEGORY = "siza_upgrade"
DYNAMIC_ID = "DYNAMIC-MARA-FATIGUE-001"


def _plain_list(value):
    try:
        return list(value or [])
    except Exception:
        return []


def find_mara():
    for obj in search_tag(ENTITY_TAG, category=ENTITY_CATEGORY):
        if obj.db.npc_id == "NPC-KAL-DAR-MARA-001":
            return obj
    return None


def build():
    mara = find_mara()
    if not mara:
        caller.msg("No puedo aplicar v0.10: Mara Vensal no existe.")
        return

    try:
        already = mara.tags.has(UPGRADE_TAG, category=UPGRADE_CATEGORY)
    except Exception:
        already = False

    if already:
        caller.msg("Kalnaj Pilot v0.10 ya estaba aplicado; no se reinició fatigue ni su reloj de dinámica.")
        caller.msg("Use siza-needs Mara para inspeccionarlo.")
        return

    dynamics = []
    found = False
    for raw in _plain_list(mara.db.need_dynamics):
        try:
            item = {str(key): value for key, value in raw.items()}
        except Exception:
            dynamics.append(raw)
            continue

        if str(item.get("id") or "") == DYNAMIC_ID:
            found = True
            item = {
                "id": DYNAMIC_ID,
                "enabled": True,
                "field": "fatigue",
                "op": "add",
                "value": 1,
                "every_ticks": 3,
                "min": 0,
                "max": 10,
                "canon_status": "prototype",
            }
        dynamics.append(item)

    if not found:
        dynamics.append(
            {
                "id": DYNAMIC_ID,
                "enabled": True,
                "field": "fatigue",
                "op": "add",
                "value": 1,
                "every_ticks": 3,
                "min": 0,
                "max": 10,
                "canon_status": "prototype",
            }
        )

    mara.db.need_dynamics = dynamics
    if mara.db.need_dynamics_clock is None:
        mara.db.need_dynamics_clock = 0
    mara.tags.add(UPGRADE_TAG, category=UPGRADE_CATEGORY)

    caller.msg("Kalnaj Pilot v0.10 aplicado: fatigue evoluciona automáticamente con el World Tick.")
    caller.msg("Regla prototype: fatigue +1 cada 3 ticks propios de Mara, rango 0..10.")
    caller.msg("La matemática NO es canon y puede cambiar; esta versión valida autonomía y persistencia.")
    caller.msg("No se modificó el valor actual de fatigue.")
    caller.msg("Prueba: siza-needs Mara | siza-sim-start 10")


build()
