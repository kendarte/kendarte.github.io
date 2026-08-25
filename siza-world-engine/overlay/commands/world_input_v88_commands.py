from evennia import Command, search_object

from commands.world_input_v74_commands import _clone
from services.consequence_engine import (
    SITE_NPC_RECIPIENT_BUILD,
    _npc_map,
    _recipient_ids,
    get_consequence_registry,
)
from services.knowledge_context_engine import knowledge_levels
from services.knowledge_fact_engine import find_knowledge_fact
from services.object_action_engine import object_action_history
from services.object_action_input_engine import route_object_action_input
from world.upgrade_pilot_v51 import MANIFEST_VISIBLE_FIELD
from world.upgrade_pilot_v60 import MARA_NPC_ID
from world.upgrade_pilot_v86 import (
    ACTION_FIELD,
    ACTION_ID,
    ACTION_INPUT,
    KNOWLEDGE_KEY as V086_PLAYER_KNOWLEDGE_KEY,
    WORLD_FIELD as V086_WORLD_FIELD,
)
from world.upgrade_pilot_v87 import TARGET_ROOM_ID, TARGET_ROOM_KEY
from world.upgrade_pilot_v88 import (
    FACT_ID,
    FACT_TEXT,
    KNOWLEDGE_KEY,
    PILOT_BUILD,
    RULE_ID,
    ensure_v88_pilot_content,
    v88_rule_count,
)


V088_VALIDATION_BUILD = "0.88.0-site-local-npc-witness-recipient-mode"


def _target_room():
    for obj in search_object(TARGET_ROOM_KEY):
        if str(getattr(obj.db, "room_id", "") or "") == TARGET_ROOM_ID:
            return obj
    return None


def _npc_id(npc):
    return str(getattr(npc.db, "npc_id", "") or "").strip() if npc else ""


def _remove_v88_knowledge(npc):
    levels = dict(getattr(npc.db, "knowledge", {}) or {})
    levels.pop(KNOWLEDGE_KEY, None)
    npc.db.knowledge = levels
    npc.db.knowledge_facts = [
        row
        for row in list(getattr(npc.db, "knowledge_facts", []) or [])
        if str((row or {}).get("id") or "") != FACT_ID
    ]


def _reset_v86_world(actor, site, manifest):
    actor_levels = dict(getattr(actor.db, "knowledge", {}) or {})
    actor_levels[V086_PLAYER_KNOWLEDGE_KEY] = max(
        int(actor_levels.get(V086_PLAYER_KNOWLEDGE_KEY, 0) or 0),
        1,
    )
    actor.db.knowledge = actor_levels

    state = _clone(getattr(manifest.db, "state", {}))
    if not isinstance(state, dict):
        state = {}
    state[ACTION_FIELD] = False
    manifest.db.state = state

    world_state = _clone(getattr(site.db, "world_state", {}))
    if not isinstance(world_state, dict):
        world_state = {}
    world_state[MANIFEST_VISIBLE_FIELD] = 1
    world_state.pop(V086_WORLD_FIELD, None)
    site.db.world_state = world_state


def _rule_result(executed):
    consequence = dict((executed.get("action_result") or {}).get("action_consequence") or {})
    row = next(
        (
            dict(item)
            for item in list(consequence.get("results") or [])
            if str((item or {}).get("rule_id") or "") == RULE_ID
        ),
        {},
    )
    return consequence, row


def _applied_fact_ids(rule_result):
    return {
        str((row or {}).get("npc_id") or "")
        for row in list((rule_result or {}).get("applied") or [])
        if bool((row or {}).get("knowledge_fact_applied"))
    }


class CmdSizaValidateV88(Command):
    key = "siza-validate-v88"
    aliases = ["validate-v88"]
    locks = "cmd:perm(Admin)"

    def func(self):
        install = ensure_v88_pilot_content()
        if not bool(install.get("success")):
            self.caller.msg(f"[V0.88 VALIDATION] FAIL | install={install}")
            return

        actor = self.caller
        site = install.get("site")
        manifest = install.get("manifest")
        informant = install.get("informant")
        mara = install.get("mara")
        away = _target_room()
        registry = get_consequence_registry(create=True)
        all_npcs = _npc_map()
        if not site or not manifest or not informant or not mara or not away or not registry:
            self.caller.msg("[V0.88 VALIDATION] FAIL | persistent context missing")
            return

        original_actor_location = actor.location
        original_actor_knowledge = _clone(getattr(actor.db, "knowledge", {}))
        original_actor_facts = _clone(getattr(actor.db, "knowledge_facts", []))
        original_actor_object_history = _clone(getattr(actor.db, "object_action_history", []))
        original_actor_resolution_history = _clone(getattr(actor.db, "action_resolution_history", []))
        original_manifest_state = _clone(getattr(manifest.db, "state", {}))
        had_world_state = bool(site.attributes.has("world_state"))
        original_world_state = _clone(getattr(site.db, "world_state", None))
        original_processed = _clone(getattr(registry.db, "processed_action_ids", []))
        original_log = _clone(getattr(registry.db, "action_log", []))
        original_npc_state = {
            npc_id: {
                "location": npc.location,
                "knowledge": _clone(getattr(npc.db, "knowledge", {})),
                "facts": _clone(getattr(npc.db, "knowledge_facts", [])),
            }
            for npc_id, npc in all_npcs.items()
        }
        results = []

        def check(label, passed, detail=""):
            results.append(bool(passed))
            self.caller.msg(f"{'PASS' if passed else 'FAIL'} {label}{' | ' + detail if detail else ''}")

        self.caller.msg(f"=== SIZA VALIDATION v0.88 | {V088_VALIDATION_BUILD} ===")
        self.caller.msg(
            "real action site -> SITE_NPCS resolves current physical witnesses -> existing consequence engine teaches only those NPCs -> swap positions -> recipient set follows location"
        )

        try:
            if actor.location != site:
                actor.move_to(site, quiet=True)
            actor.db.object_action_history = []
            actor.db.action_resolution_history = []

            for npc in all_npcs.values():
                _remove_v88_knowledge(npc)

            rule = next(
                (
                    row
                    for row in list(getattr(registry.db, "rules", []) or [])
                    if str((row or {}).get("id") or "") == RULE_ID
                ),
                None,
            )
            check(
                "v088-installs-exactly-one-site-npc-consequence-rule",
                v88_rule_count() == 1
                and rule is not None
                and str((rule or {}).get("recipient_mode") or "").upper() == "SITE_NPCS",
                f"rules={v88_rule_count()} mode={(rule or {}).get('recipient_mode')}",
            )

            informant_id = _npc_id(informant)
            mara_id = _npc_id(mara)
            legacy_action = {
                "actor_npc_id": informant_id,
                "target_npc_id": mara_id,
                "recipient_ids": [mara_id],
            }
            legacy_ok = (
                _recipient_ids({"recipient_mode": "EXPLICIT", "recipient_ids": [informant_id]}, legacy_action, npcs=all_npcs) == [informant_id]
                and _recipient_ids({"recipient_mode": "ACTOR"}, legacy_action, npcs=all_npcs) == [informant_id]
                and _recipient_ids({"recipient_mode": "TARGET"}, legacy_action, npcs=all_npcs) == [mara_id]
                and _recipient_ids({"recipient_mode": "ACTION_RECIPIENTS"}, legacy_action, npcs=all_npcs) == [mara_id]
            )
            check(
                "existing-explicit-actor-target-and-action-recipient-modes-remain-unchanged",
                legacy_ok,
                f"build={SITE_NPC_RECIPIENT_BUILD}",
            )

            missing_site = _recipient_ids({"recipient_mode": "SITE_NPCS"}, {}, npcs=all_npcs)
            room_only = set(
                _recipient_ids(
                    {"recipient_mode": "SITE_NPCS"},
                    {"site_room_id": str(getattr(site.db, "room_id", "") or "")},
                    npcs=all_npcs,
                )
            )
            dbref_only = set(
                _recipient_ids(
                    {"recipient_mode": "SITE_NPCS"},
                    {"site_dbref": int(site.id)},
                    npcs=all_npcs,
                )
            )
            check(
                "site-recipient-mode-fails-closed-without-site-and-supports-room-id-or-dbref",
                missing_site == [] and room_only == dbref_only,
                f"missing={missing_site} room={sorted(room_only)} dbref={sorted(dbref_only)}",
            )

            if informant.location != site:
                informant.move_to(site, quiet=True)
            if mara.location != away:
                mara.move_to(away, quiet=True)
            _reset_v86_world(actor, site, manifest)

            expected_first = set(
                _recipient_ids(
                    {"recipient_mode": "SITE_NPCS"},
                    {
                        "site_dbref": int(site.id),
                        "site_room_id": str(getattr(site.db, "room_id", "") or ""),
                    },
                    npcs=all_npcs,
                )
            )
            before_history = len(object_action_history(actor))
            first = route_object_action_input(actor, ACTION_INPUT)
            first_consequence, first_rule = _rule_result(first)
            first_applied = _applied_fact_ids(first_rule)
            check(
                "first-real-v086-action-completes-through-existing-consequence-engine",
                first.get("status") == "COMPLETED"
                and str(first.get("object_action_id") or "") == ACTION_ID
                and first_consequence.get("status") == "PROCESSED"
                and len(object_action_history(actor)) == before_history + 1,
                f"status={first.get('status')} consequence={first_consequence.get('status')}",
            )
            check(
                "first-site-broadcast-applies-exactly-to-current-npcs-at-action-site",
                first_rule.get("status") == "APPLIED"
                and first_applied == expected_first
                and informant_id in first_applied
                and mara_id not in first_applied,
                f"expected={sorted(expected_first)} applied={sorted(first_applied)}",
            )

            informant_fact = find_knowledge_fact(informant, FACT_ID)
            mara_fact = find_knowledge_fact(mara, FACT_ID)
            source = dict((informant_fact or {}).get("source") or {})
            learned_by = dict((informant_fact or {}).get("learned_by") or {})
            check(
                "present-witness-learns-grounded-fact-with-direct-site-provenance-while-absent-npc-does-not",
                informant_fact is not None
                and str(informant_fact.get("text") or "") == FACT_TEXT
                and int(knowledge_levels(informant).get(KNOWLEDGE_KEY, 0) or 0) >= 1
                and source.get("kind") == "DIRECT_SITE_WITNESS"
                and learned_by.get("mode") == "SITE_PRESENCE"
                and mara_fact is None
                and int(knowledge_levels(mara).get(KNOWLEDGE_KEY, 0) or 0) == 0,
                f"informant_fact={informant_fact is not None} mara_fact={mara_fact is not None}",
            )

            for npc in all_npcs.values():
                _remove_v88_knowledge(npc)
            if informant.location != away:
                informant.move_to(away, quiet=True)
            if mara.location != site:
                mara.move_to(site, quiet=True)
            _reset_v86_world(actor, site, manifest)

            expected_second = set(
                _recipient_ids(
                    {"recipient_mode": "SITE_NPCS"},
                    {
                        "site_dbref": int(site.id),
                        "site_room_id": str(getattr(site.db, "room_id", "") or ""),
                    },
                    npcs=all_npcs,
                )
            )
            second = route_object_action_input(actor, ACTION_INPUT)
            second_consequence, second_rule = _rule_result(second)
            second_applied = _applied_fact_ids(second_rule)
            check(
                "second-real-action-uses-a-new-attempt-and-is-not-deduped-by-first-consequence",
                second.get("status") == "COMPLETED"
                and second_consequence.get("status") == "PROCESSED"
                and first_consequence.get("action_id") != second_consequence.get("action_id"),
                f"first={first_consequence.get('action_id')} second={second_consequence.get('action_id')}",
            )
            check(
                "after-swapping-positions-site-recipient-set-follows-location-not-npc-identity",
                second_rule.get("status") == "APPLIED"
                and second_applied == expected_second
                and mara_id in second_applied
                and informant_id not in second_applied,
                f"expected={sorted(expected_second)} applied={sorted(second_applied)}",
            )

            mara_fact_second = find_knowledge_fact(mara, FACT_ID)
            informant_fact_second = find_knowledge_fact(informant, FACT_ID)
            check(
                "second-run-teaches-the-now-present-npc-and-does-not-magically-teach-the-away-npc",
                mara_fact_second is not None
                and str(mara_fact_second.get("text") or "") == FACT_TEXT
                and int(knowledge_levels(mara).get(KNOWLEDGE_KEY, 0) or 0) >= 1
                and informant_fact_second is None
                and int(knowledge_levels(informant).get(KNOWLEDGE_KEY, 0) or 0) == 0,
                f"mara_fact={mara_fact_second is not None} informant_fact={informant_fact_second is not None}",
            )

            second_install = ensure_v88_pilot_content()
            check(
                "v088-install-remains-idempotent-after-two-real-site-witness-actions",
                second_install.get("success") is True and v88_rule_count() == 1,
                f"rules={v88_rule_count()}",
            )

        except Exception as exc:
            check("validator-runtime", False, f"error={exc}")
        finally:
            try:
                if actor.location != original_actor_location:
                    actor.move_to(original_actor_location, quiet=True)
            except Exception:
                pass
            actor.db.knowledge = original_actor_knowledge
            actor.db.knowledge_facts = original_actor_facts
            actor.db.object_action_history = original_actor_object_history
            actor.db.action_resolution_history = original_actor_resolution_history

            for npc_id, snapshot in original_npc_state.items():
                npc = all_npcs.get(npc_id)
                if not npc:
                    continue
                try:
                    if npc.location != snapshot.get("location"):
                        npc.move_to(snapshot.get("location"), quiet=True)
                except Exception:
                    pass
                npc.db.knowledge = snapshot.get("knowledge")
                npc.db.knowledge_facts = snapshot.get("facts")

            manifest.db.state = original_manifest_state
            if had_world_state:
                site.db.world_state = original_world_state
            else:
                try:
                    site.attributes.remove("world_state")
                except Exception:
                    pass
            registry.db.processed_action_ids = original_processed
            registry.db.action_log = original_log

        passed = sum(1 for item in results if item)
        total = len(results)
        self.caller.msg(f"RESULT: {passed}/{total} PASS")
        self.caller.msg(
            "STATE RESTORED: actor state, every persistent NPC location/Knowledge/Facts, manifest/room state and consequence registry restored exactly"
        )
        self.caller.msg(
            "PERSISTENT SYSTEM RETAINED: SITE_NPCS is a deterministic consequence recipient mode; existing effect application remains owned by consequence_engine"
        )
        self.caller.msg("========================================================")
