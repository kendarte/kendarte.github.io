from services.knowledge_fact_engine import set_knowledge_fact_status
from world.darkhaven_academy_seed import _find_by_attr


ORIENTATION_FACT_ID = "DH7-FACT-TUT-ORIENTATION-001"


def apply():
    removed = []
    # The authored training->briefing pair DH7-EXIT-012 already supplies the
    # correct route. Remove the older duplicate pair so the player cannot pick
    # an untagged parallel Exit and silently miss tutorial progression.
    for exit_id in ("DH7-EXIT-011A", "DH7-EXIT-011B"):
        obj = _find_by_attr("exit_id", exit_id)
        if obj:
            removed.append({"exit_id": exit_id, "dbref": int(obj.id)})
            obj.delete()

    briefing_exit = _find_by_attr("exit_id", "DH7-EXIT-012A")
    if briefing_exit:
        briefing_exit.db.campaign_tags = ["DH-TUT-BRIEFING"]

    # Dino receives the player at the gate, but Squeek is the intended
    # orientation source after the player has actually entered the academy.
    # Retraction preserves provenance without letting the first beat be
    # short-circuited by acquiring the next beat's fact too early.
    dino = _find_by_attr("npc_id", "NPC-DH7-DINO")
    dino_fact = None
    if dino:
        dino_fact = set_knowledge_fact_status(
            dino,
            ORIENTATION_FACT_ID,
            "RETRACTED",
            reason="DARKHAVEN_TUTORIAL_SOURCE_IS_SQUEEK",
        )

    squeek = _find_by_attr("npc_id", "NPC-DH7-SQUEEK")
    squeek_fact = None
    if squeek:
        squeek_fact = set_knowledge_fact_status(
            squeek,
            ORIENTATION_FACT_ID,
            "ACTIVE",
            reason="DARKHAVEN_TUTORIAL_ORIENTATION_SOURCE",
        )

    return {
        "status": "PATCHED",
        "removed_duplicate_exits": removed,
        "briefing_exit_dbref": int(briefing_exit.id) if briefing_exit else None,
        "dino_fact": dino_fact,
        "squeek_fact": squeek_fact,
    }
