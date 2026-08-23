from evennia import search_tag


ENTITY_TAG = "kalnaj_pilot_v03_entities"
ENTITY_CATEGORY = "siza_entity"
UPGRADE_TAG = "kalnaj_pilot_v11_activity_needs"
UPGRADE_CATEGORY = "siza_upgrade"

OLD_UNIFORM_ID = "DYNAMIC-MARA-FATIGUE-001"
MOVE_ID = "DYNAMIC-MARA-FATIGUE-MOVE-001"
WORK_ID = "DYNAMIC-MARA-FATIGUE-WORK-001"
IDLE_ID = "DYNAMIC-MARA-FATIGUE-IDLE-001"


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
        caller.msg("No puedo aplicar v0.11: Mara Vensal no existe.")
        return

    try:
        already = mara.tags.has(UPGRADE_TAG, category=UPGRADE_CATEGORY)
    except Exception:
        already = False

    if already:
        caller.msg("Kalnaj Pilot v0.11 ya estaba aplicado; no se reinició fatigue, rutina ni contadores.")
        caller.msg("Use siza-needs Mara y siza-sim-trace para inspeccionarlo.")
        return

    # Preserve unrelated dynamics. Disable the old uniform clock rule instead of
    # deleting it so the prototype history remains explicit and reversible.
    dynamics = []
    managed_ids = {MOVE_ID, WORK_ID, IDLE_ID}
    for raw in _plain_list(mara.db.need_dynamics):
        try:
            item = {str(key): value for key, value in raw.items()}
        except Exception:
            dynamics.append(raw)
            continue

        item_id = str(item.get("id") or "")
        if item_id == OLD_UNIFORM_ID:
            item["enabled"] = False
            item["source"] = "CLOCK"
            dynamics.append(item)
            continue
        if item_id in managed_ids:
            continue
        dynamics.append(item)

    dynamics.extend(
        [
            {
                "id": MOVE_ID,
                "enabled": True,
                "source": "ACTIVITY",
                "activity_kind": "MOVE",
                "field": "fatigue",
                "op": "add",
                "value": 1,
                "every_actions": 2,
                "min": 0,
                "max": 10,
                "canon_status": "prototype",
            },
            {
                "id": WORK_ID,
                "enabled": True,
                "source": "ACTIVITY",
                "activity_kind": "WORK",
                "field": "fatigue",
                "op": "add",
                "value": 1,
                "every_actions": 2,
                "min": 0,
                "max": 10,
                "canon_status": "prototype",
            },
            {
                "id": IDLE_ID,
                "enabled": True,
                "source": "ACTIVITY",
                "activity_kind": "IDLE",
                "field": "fatigue",
                "op": "add",
                "value": 1,
                "every_actions": 6,
                "min": 0,
                "max": 10,
                "canon_status": "prototype",
            },
        ]
    )
    mara.db.need_dynamics = dynamics

    # Counters are new state in v0.11. Initializing them does not alter the
    # existing fatigue value or the older clock used for audit/history.
    if mara.db.need_activity_counters is None:
        mara.db.need_activity_counters = {}

    activity_by_routine = {
        "ROUTINE-MARA-CANTINA": "IDLE",
        "ROUTINE-MARA-PLAZA": "IDLE",
        "ROUTINE-MARA-PESCADERIA": "WORK",
    }
    routine = []
    for raw in _plain_list(mara.db.routine):
        try:
            entry = {str(key): value for key, value in raw.items()}
        except Exception:
            routine.append(raw)
            continue
        routine_id = str(entry.get("id") or "")
        if routine_id in activity_by_routine:
            entry["activity_kind"] = activity_by_routine[routine_id]
        routine.append(entry)
    mara.db.routine = routine

    mara.tags.add(UPGRADE_TAG, category=UPGRADE_CATEGORY)

    caller.msg("Kalnaj Pilot v0.11 aplicado: fatigue depende de acciones ejecutadas.")
    caller.msg("La regla uniforme v0.10 quedó disabled, no eliminada.")
    caller.msg("Prototype: MOVE +1/2 acciones | WORK +1/2 | IDLE +1/6 | REST usa la affordance existente.")
    caller.msg("No se modificó fatigue, ubicación, routine_index ni historial del World Tick.")
    caller.msg("Prueba: siza-needs Mara | siza-needset Mara fatigue 5 | siza-sim-start 5")


build()
