from evennia import create_object, search_object, search_tag

from services.job_claims import release_job_claim


ENTITY_TAG = "kalnaj_pilot_v03_entities"
ENTITY_CATEGORY = "siza_entity"
UPGRADE_TAG = "kalnaj_pilot_v13_job_claims"
UPGRADE_CATEGORY = "siza_upgrade"
TEST_TAG = "kalnaj_pilot_v13_claim_worker"
TEST_CATEGORY = "siza_test"
WORKER_ID = "TEST-NPC-KAL-DAR-WORKER-B"
TASK_ID = "TEST-WORKORDER-PESCADERIA-001"
PLAZA_ID = "CAR-KAL-DAR-003"


def find_room(key, room_id):
    for obj in search_object(key):
        if obj.db.room_id == room_id:
            return obj
    return None


def find_worker():
    for obj in search_tag(ENTITY_TAG, category=ENTITY_CATEGORY):
        if str(obj.db.npc_id or "") == WORKER_ID:
            return obj
    return None


def ensure_worker(plaza):
    existing = find_worker()
    if existing:
        return existing, False

    npc = create_object(
        "typeclasses.npcs.NPC",
        key="Trabajador de Prueba B",
        aliases=["Trabajador B", "Worker B", "Prueba B"],
        location=plaza,
        tags=[
            (ENTITY_TAG, ENTITY_CATEGORY),
            (TEST_TAG, TEST_CATEGORY),
        ],
        attributes=[
            ("npc_id", WORKER_ID),
            ("desc", "NPC técnico de prueba para validar coordinación de trabajos; no pertenece al canon."),
            ("canon_status", "prototype"),
            ("test_harness", True),
            ("job", {"id": "JOB-DARSENA-TEST", "name": "trabajador de dársena (prueba)", "status": "prototype"}),
            ("knowledge", {}),
            ("knowledge_facts", []),
            ("memories", []),
            ("relationships", {}),
            ("needs", {}),
            ("need_rules", []),
            ("need_dynamics", []),
            ("need_activity_counters", {}),
            ("routine", [
                {
                    "id": "ROUTINE-WORKER-B-PLAZA",
                    "room_id": PLAZA_ID,
                    "room_key": "Plaza de Recepcion",
                    "activity": "esperando trabajo de prueba en la plaza",
                    "activity_kind": "IDLE",
                    "duration_ticks": 1,
                    "status": "prototype",
                }
            ]),
            ("routine_index", 0),
            ("routine_hold_remaining", 0),
            ("current_activity", "esperando trabajo de prueba en la plaza"),
            ("destination_id", PLAZA_ID),
            ("simulation_enabled", True),
            ("decision_enabled", True),
            ("decision_priorities", {
                "DANGER": 100,
                "EVENT": 80,
                "NEED": 70,
                "JOB": 60,
                "RELATIONSHIP": 50,
                "ROUTINE": 10,
            }),
            ("decision_goals", []),
            ("current_goal", None),
        ],
    )
    return npc, True


def build():
    plaza = find_room("Plaza de Recepcion", PLAZA_ID)
    if not plaza:
        caller.msg("No puedo aplicar v0.13: falta Plaza de Recepcion.")
        return

    existing = find_worker()
    if existing and existing.tags.has(UPGRADE_TAG, category=UPGRADE_CATEGORY):
        caller.msg("Kalnaj Pilot v0.13 ya estaba aplicado; no se movió ni reinició el worker de prueba.")
        caller.msg("Use siza-jobs Mara | siza-jobs Trabajador B.")
        return

    worker, created = ensure_worker(plaza)
    worker.tags.add(UPGRADE_TAG, category=UPGRADE_CATEGORY)

    # Start the claim test cleanly without changing task progress/world state.
    # A completed task normally has no claim; this only removes stale harness data.
    release_job_claim(TASK_ID, force=True)

    caller.msg("Kalnaj Pilot v0.13 aplicado: claim exclusivo para JOB multi-NPC.")
    caller.msg(
        f"Harness prototype: {worker.key} ({'creado' if created else 'ya existía'}) | "
        f"npc_id={WORKER_ID} | job_id=JOB-DARSENA-TEST."
    )
    caller.msg("El worker de prueba no es canon y no recibió lore, Knowledge ni necesidades inventadas.")
    caller.msg("Un JOB se reclama sólo cuando un NPC realmente lo selecciona para ejecutar.")
    caller.msg("El dueño conserva el claim durante interrupciones; al completar se libera automáticamente.")
    caller.msg("Admin/debug: siza-job-release TEST-WORKORDER-PESCADERIA-001")
    caller.msg("Prueba: siza-workset CAR-KAL-DAR-007 supplies 1")


build()
