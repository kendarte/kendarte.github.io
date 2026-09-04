"""Idempotent Darkhaven autonomy install patch.

This keeps the base academy seed focused on static tutorial content while the
bounded autonomy slice is applied explicitly by update/bootstrap.
"""

from services.faction_engine import upsert_faction, upsert_membership
from services.relationship_engine import create_fact_share_obligation
from world import darkhaven_academy_seed as seed

AUTONOMY_NPC_IDS = {
    "NPC-DH7-DINO",
    "NPC-DH7-SQUEEK",
    "NPC-DH7-BERTA",
    "NPC-DH7-ORLAN",
    "NPC-DH7-MAINE",
}

AUTONOMY = {
    "NPC-DH7-DINO": {
        "home_room_id": "DH7-ROOM-012",
        "work_room_id": "DH7-ROOM-001",
        "rest_room_id": "DH7-ROOM-012",
        "routine": [("DH7-ROOM-001", "vigilando el portón"), ("DH7-ROOM-002", "asistiendo ingresos"), ("DH7-ROOM-012", "descansando")],
        "needs": {"duty": 35, "rest": 20, "food": 15},
    },
    "NPC-DH7-SQUEEK": {
        "home_room_id": "DH7-ROOM-012",
        "work_room_id": "DH7-ROOM-009",
        "rest_room_id": "DH7-ROOM-012",
        "routine": [("DH7-ROOM-002", "recorriendo el patio"), ("DH7-ROOM-009", "preparando un briefing"), ("DH7-ROOM-012", "descansando")],
        "needs": {"duty": 30, "rest": 20, "food": 15},
    },
    "NPC-DH7-BERTA": {
        "home_room_id": "DH7-ROOM-012",
        "work_room_id": "DH7-ROOM-014",
        "rest_room_id": "DH7-ROOM-012",
        "routine": [("DH7-ROOM-014", "preparando la cocina"), ("DH7-ROOM-013", "sirviendo el comedor"), ("DH7-ROOM-012", "descansando")],
        "needs": {"duty": 40, "rest": 20, "food": 10},
    },
    "NPC-DH7-ORLAN": {
        "home_room_id": "DH7-ROOM-003",
        "work_room_id": "DH7-ROOM-010",
        "rest_room_id": "DH7-ROOM-003",
        "routine": [("DH7-ROOM-010", "supervisando entrenamiento"), ("DH7-ROOM-003", "tomando guardia"), ("DH7-ROOM-003", "descansando")],
        "needs": {"duty": 45, "rest": 20, "food": 10},
    },
    "NPC-DH7-MAINE": {
        "home_room_id": "DH7-ROOM-018",
        "work_room_id": "DH7-ROOM-017",
        "rest_room_id": "DH7-ROOM-018",
        "routine": [("DH7-ROOM-017", "reparando frames"), ("DH7-ROOM-018", "inspeccionando la bahía pesada"), ("DH7-ROOM-018", "descansando")],
        "needs": {"duty": 40, "rest": 20, "food": 10},
    },
}


def _find_room(room_id):
    return seed._find_room(room_id)


def _find_npc(npc_id):
    return seed._find_by_attr("npc_id", npc_id)


def _autonomy_task(task_id, job_id, activity, priority=55):
    return {
        "id": task_id,
        "job_id": job_id,
        "active": True,
        "status": "available",
        "priority": priority,
        "activity": activity,
        "work_required": 2,
        "work_done": 0,
        "work_per_action": 1,
        "one_shot": False,
        "canon_status": "vertical_slice",
    }


def _apply_npc_autonomy():
    rows = []
    for npc_id, config in AUTONOMY.items():
        npc = _find_npc(npc_id)
        if not npc:
            rows.append({"npc_id": npc_id, "patched": False, "reason": "NPC_NOT_FOUND"})
            continue
        npc.db.simulation_enabled = True
        npc.db.decision_enabled = True
        npc.db.home_room_id = config["home_room_id"]
        npc.db.work_room_id = config["work_room_id"]
        npc.db.rest_room_id = config["rest_room_id"]
        npc.db.routine = [
            {
                "id": "DH7-ROUTINE-%s-%02d" % (npc_id, index + 1),
                "room_id": room_id,
                "room_key": (_find_room(room_id).key if _find_room(room_id) else ""),
                "activity": activity,
                "activity_kind": "ROUTINE",
                "duration_ticks": 1,
            }
            for index, (room_id, activity) in enumerate(config["routine"])
        ]
        npc.db.needs = dict(config["needs"])
        npc.db.need_rules = [
            {"id": "DH7-NEED-REST", "need_key": "rest", "affordance": "rest", "op": "GTE", "value": 70, "priority": 75, "activity": "recuperando descanso", "enabled": True, "canon_status": "vertical_slice"},
            {"id": "DH7-NEED-FOOD", "need_key": "food", "affordance": "food", "op": "GTE", "value": 70, "priority": 72, "activity": "comiendo en el comedor", "enabled": True, "canon_status": "vertical_slice"},
        ]
        npc.db.need_dynamics = [
            {"id": "DH7-DYNAMIC-REST", "source": "CLOCK", "field": "rest", "op": "ADD", "value": 10, "every_ticks": 4, "min": 0, "max": 100, "enabled": True, "canon_status": "vertical_slice"},
            {"id": "DH7-DYNAMIC-FOOD", "source": "CLOCK", "field": "food", "op": "ADD", "value": 10, "every_ticks": 6, "min": 0, "max": 100, "enabled": True, "canon_status": "vertical_slice"},
        ]
        rows.append({"npc_id": npc_id, "patched": True})
    return rows


def _apply_sites_and_events():
    job_sites = {
        "DH7-ROOM-001": [_autonomy_task("DH7-JOB-GATE-WATCH", "ROLE-DH7-STUDENT-ASSISTANT", "vigilando el portón", 60)],
        "DH7-ROOM-002": [_autonomy_task("DH7-JOB-INTAKE-ASSISTANCE", "ROLE-DH7-STUDENT-ASSISTANT", "asistiendo ingresos", 58)],
        "DH7-ROOM-014": [_autonomy_task("DH7-JOB-KITCHEN-SERVICE", "JOB-DH7-BERTA", "atendiendo cocina", 62)],
        "DH7-ROOM-010": [_autonomy_task("DH7-JOB-TRAINING-SUPERVISION", "JOB-DH7-ORLAN", "supervisando entrenamiento", 62)],
        "DH7-ROOM-017": [_autonomy_task("DH7-JOB-FRAME-MAINTENANCE", "JOB-DH7-MAINE", "reparando un frame", 62)],
    }
    for room_id, tasks in job_sites.items():
        room = _find_room(room_id)
        if not room:
            continue
        room.tags.add("siza_job_site", category="siza_job")
        room.db.job_tasks = tasks
        room.db.job_rules = []
        room.db.work_state = {"autonomy_enabled": True}

    for room_id, affordances in {
        "DH7-ROOM-012": [{"id": "DH7-AFFORDANCE-REST", "kind": "rest", "need_key": "rest", "activity": "descansando", "completion_effects": [{"field": "rest", "op": "SUB", "value": 60}], "enabled": True, "canon_status": "vertical_slice"}],
        "DH7-ROOM-013": [{"id": "DH7-AFFORDANCE-FOOD", "kind": "food", "need_key": "food", "activity": "comiendo", "completion_effects": [{"field": "food", "op": "SUB", "value": 60}], "enabled": True, "canon_status": "vertical_slice"}],
    }.items():
        room = _find_room(room_id)
        if not room:
            continue
        room.tags.add("siza_need_site", category="siza_need")
        room.db.need_affordances = affordances

    observation = _find_room("DH7-ROOM-023")
    if observation:
        observation.tags.add("siza_event_site", category="siza_world_event")
        observation.db.world_event_state = {"minor_anomaly": True}
        observation.db.world_event_rules = [{
            "id": "DH7-EVENT-RULE-MINOR-ANOMALY",
            "event_id": "DH7-EVENT-MINOR-ANOMALY",
            "field": "minor_anomaly",
            "op": "EQ",
            "value": True,
            "goal_type": "EVENT",
            "priority": 45,
            "target_room_id": "DH7-ROOM-023",
            "target_room_key": observation.key,
            "npc_ids": ["NPC-DH7-SQUEEK"],
            "activity": "verificando una anomalía menor",
            "enabled": True,
            "canon_status": "vertical_slice",
        }]
    return {"job_sites": len(job_sites), "event_id": "DH7-EVENT-MINOR-ANOMALY"}


def _apply_faction_memberships():
    upsert_faction({
        "id": "FACTION-DH7-ACADEMY",
        "name": "Academia Darkhaven",
        "active": True,
        "ranks": {"STAFF": {"id": "STAFF", "authority_level": 20}, "GUARD": {"id": "GUARD", "authority_level": 40}},
        "canon_status": "vertical_slice",
    })
    for npc_id in AUTONOMY_NPC_IDS:
        npc = _find_npc(npc_id)
        if npc:
            upsert_membership(npc, {
                "faction_id": "FACTION-DH7-ACADEMY",
                "rank_id": "GUARD" if npc_id == "NPC-DH7-ORLAN" else "STAFF",
                "role": "darkhaven_autonomy",
                "active": True,
                "canon_status": "vertical_slice",
            })


def apply():
    npc_rows = _apply_npc_autonomy()
    autonomy = _apply_sites_and_events()
    _apply_faction_memberships()
    squeek = _find_npc("NPC-DH7-SQUEEK")
    dino = _find_npc("NPC-DH7-DINO")
    fact_share = (
        create_fact_share_obligation(squeek, dino, "DH7-FACT-TUT-ORIENTATION-001", priority=65)
        if squeek and dino else {"success": False, "reason": "MISSING_AUTONOMY_NPC"}
    )
    return {
        "status": "PATCHED",
        "selected_npcs": len([row for row in npc_rows if row.get("patched")]),
        "npc_rows": npc_rows,
        "autonomy": autonomy,
        "fact_share": fact_share,
    }
