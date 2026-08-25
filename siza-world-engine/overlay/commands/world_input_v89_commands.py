from evennia import Command, search_object

from commands.world_input_v74_commands import _clone
from services.consequence_engine import _npc_map, get_consequence_registry
from services.fact_driven_decision import decision_step
from services.fact_share_rule_engine import fact_share_rules, refresh_fact_share_obligations
from services.knowledge_context_engine import knowledge_levels
from services.knowledge_fact_engine import find_knowledge_fact
from services.object_action_engine import object_action_history
from services.object_action_input_engine import route_object_action_input
from services.relationship_engine import collect_relationship_candidates, inspect_relationships
from world.upgrade_pilot_v51 import MANIFEST_VISIBLE_FIELD
from world.upgrade_pilot_v86 import (
    ACTION_FIELD,
    ACTION_ID,
    ACTION_INPUT,
    KNOWLEDGE_KEY as V086_PLAYER_KNOWLEDGE_KEY,
    WORLD_FIELD as V086_WORLD_FIELD,
)
from world.upgrade_pilot_v87 import TARGET_ROOM_ID, TARGET_ROOM_KEY
from world.upgrade_pilot_v88 import FACT_ID, FACT_TEXT, KNOWLEDGE_KEY
from world.upgrade_pilot_v89 import (
    PILOT_BUILD,
    PRIORITY,
    RULE_ID,
    ensure_v89_pilot_content,
    v89_rule_count,
)


V089_VALIDATION_BUILD = "0.89.0-site-witness-fact-social-propagation"


def _target_room():
    for obj in search_object(TARGET_ROOM_KEY):
        if str(getattr(obj.db, "room_id", "") or "") == TARGET_ROOM_ID:
            return obj
    return None


def _npc_id(npc):
    return str(getattr(npc.db, "npc_id", "") or "").strip() if npc else ""


def _remove_fact_knowledge(npc):
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


def _obligation_id(target_npc_id):
    return f"SHARE-FACT-{target_npc_id}-{FACT_ID}"


def _remove_test_obligation(source, target_npc_id):
    relationships = _clone(getattr(source.db, "relationships", {}))
    if not isinstance(relationships, dict):
        relationships = {}
    relation = relationships.get(str(target_npc_id))
    if relation is None:
        source.db.relationships = relationships
        return
    relation = _clone(relation)
    if not isinstance(relation, dict):
        relation = {}
    wanted = _obligation_id(target_npc_id)
    relation["obligations"] = [
        row
        for row in list(relation.get("obligations") or [])
        if str((row or {}).get("id") or "") != wanted
    ]
    relationships[str(target_npc_id)] = relation
    source.db.relationships = relationships


def _find_obligation(source, target_npc_id):
    wanted = _obligation_id(target_npc_id)
    for row in inspect_relationships(source):
        if str(row.get("target_npc_id") or "") != str(target_npc_id):
            continue
        for obligation in list(row.get("obligations") or []):
            if str((obligation or {}).get("id") or "") == wanted:
                return dict(obligation)
    return None


class CmdSizaValidateV89(Command):
    key = "siza-validate-v89"
    aliases = ["validate-v89"]
    locks = "cmd:perm(Admin)"

    def func(self):
        install = ensure_v89_pilot_content()
        if not bool(install.get("success")):
            self.caller.msg(f"[V0.89 VALIDATION] FAIL | install={install}")
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
            self.caller.msg("[V0.89 VALIDATION] FAIL | persistent context missing")
            return

        informant_id = _npc_id(informant)
        mara_id = _npc_id(mara)
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
                "relationships": _clone(getattr(npc.db, "relationships", {})),
                "decision_enabled": getattr(npc.db, "decision_enabled", None),
                "current_goal": _clone(getattr(npc.db, "current_goal", None)),
                "destination_id": getattr(npc.db, "destination_id", None),
                "current_activity": getattr(npc.db, "current_activity", None),
            }
            for npc_id, npc in all_npcs.items()
        }
        results = []

        def check(label, passed, detail=""):
            results.append(bool(passed))
            self.caller.msg(f"{'PASS' if passed else 'FAIL'} {label}{' | ' + detail if detail else ''}")

        self.caller.msg(f"=== SIZA VALIDATION v0.89 | {V089_VALIDATION_BUILD} ===")
        self.caller.msg(
            "local witness learns exact Fact -> authored Fact-share rule materializes social obligation -> relationship goal follows absent target -> local transfer occurs only after physical meeting"
        )

        try:
            if actor.location != site:
                actor.move_to(site, quiet=True)
            if informant.location != site:
                informant.move_to(site, quiet=True)
            if mara.location != away:
                mara.move_to(away, quiet=True)
            informant.db.decision_enabled = True
            informant.db.current_goal = None
            informant.db.destination_id = None
            informant.db.current_activity = None
            actor.db.object_action_history = []
            actor.db.action_resolution_history = []

            for npc in all_npcs.values():
                _remove_fact_knowledge(npc)
            _remove_test_obligation(informant, mara_id)
            _reset_v86_world(actor, site, manifest)
            registry.db.processed_action_ids = list(original_processed or [])
            registry.db.action_log = list(original_log or [])

            rule = next(
                (row for row in fact_share_rules(informant) if str(row.get("id") or "") == RULE_ID),
                None,
            )
            check(
                "v089-installs-one-authored-informant-to-mara-fact-share-rule",
                v89_rule_count(informant) == 1
                and rule is not None
                and str((rule or {}).get("fact_id") or "") == FACT_ID
                and str((rule or {}).get("target_npc_id") or "") == mara_id
                and int((rule or {}).get("priority", 0) or 0) == PRIORITY,
                f"rules={v89_rule_count(informant)} target={(rule or {}).get('target_npc_id')}",
            )

            before_known = refresh_fact_share_obligations(informant)
            check(
                "fact-share-rule-does-not-materialize-before-source-actually-knows-the-fact",
                not list(before_known.get("materialized") or [])
                and any(
                    str(row.get("rule_id") or "") == RULE_ID
                    and row.get("reason") == "SOURCE_DOES_NOT_KNOW_FACT"
                    for row in list(before_known.get("skipped") or [])
                )
                and _find_obligation(informant, mara_id) is None,
                f"status={before_known.get('status')} skipped={before_known.get('skipped')}",
            )

            before_history = len(object_action_history(actor))
            executed = route_object_action_input(actor, ACTION_INPUT)
            informant_fact = find_knowledge_fact(informant, FACT_ID)
            mara_fact_before_social = find_knowledge_fact(mara, FACT_ID)
            check(
                "real-v088-site-action-teaches-present-informant-but-not-absent-mara",
                executed.get("status") == "COMPLETED"
                and str(executed.get("object_action_id") or "") == ACTION_ID
                and len(object_action_history(actor)) == before_history + 1
                and informant_fact is not None
                and str(informant_fact.get("text") or "") == FACT_TEXT
                and int(knowledge_levels(informant).get(KNOWLEDGE_KEY, 0) or 0) >= 1
                and mara_fact_before_social is None
                and int(knowledge_levels(mara).get(KNOWLEDGE_KEY, 0) or 0) == 0,
                f"informant_fact={informant_fact is not None} mara_fact={mara_fact_before_social is not None}",
            )

            refresh = refresh_fact_share_obligations(informant)
            obligation = _find_obligation(informant, mara_id)
            check(
                "known-witness-fact-materializes-one-share-fact-obligation-without-teleporting-knowledge",
                any(
                    str(row.get("rule_id") or "") == RULE_ID
                    and str(row.get("obligation_id") or "") == _obligation_id(mara_id)
                    for row in list(refresh.get("materialized") or [])
                )
                and obligation is not None
                and obligation.get("active") is True
                and str(obligation.get("kind") or "") == "SHARE_FACT"
                and str(obligation.get("fact_id") or "") == FACT_ID
                and find_knowledge_fact(mara, FACT_ID) is None,
                f"materialized={refresh.get('materialized')} obligation={None if obligation is None else obligation.get('status')}",
            )

            candidates = collect_relationship_candidates(informant)
            candidate = next(
                (
                    row
                    for row in candidates
                    if str(row.get("relationship_obligation_id") or "") == _obligation_id(mara_id)
                ),
                None,
            )
            check(
                "share-fact-obligation-becomes-dynamic-relationship-goal-pointing-at-maras-current-room",
                candidate is not None
                and str(candidate.get("relationship_kind") or "") == "SHARE_FACT"
                and str(candidate.get("fact_id") or "") == FACT_ID
                and candidate.get("target_room_key") == mara.location.key
                and int(candidate.get("priority", 0) or 0) == PRIORITY,
                f"target={None if candidate is None else candidate.get('target_room_key')} priority={None if candidate is None else candidate.get('priority')}",
            )

            step = decision_step(informant, prepare_world_state=False)
            check(
                "existing-decision-engine-moves-informant-to-mara-and-resolves-share-fact-only-on-contact",
                step.get("status") == "GOAL_COMPLETED"
                and str(step.get("relationship_kind") or "") == "SHARE_FACT"
                and step.get("fact_shared") is True
                and str(step.get("relationship_target_npc_id") or "") == mara_id
                and informant.location == mara.location
                and informant.location == away,
                f"status={step.get('status')} kind={step.get('relationship_kind')} location={informant.location.key if informant.location else None}",
            )

            mara_fact = find_knowledge_fact(mara, FACT_ID)
            transfer_history = list((mara_fact or {}).get("transfer_history") or [])
            transfer = transfer_history[-1] if transfer_history else {}
            source = dict((mara_fact or {}).get("source") or {})
            learned_by = dict((mara_fact or {}).get("learned_by") or {})
            check(
                "mara-learns-the-exact-witness-fact-with-original-witness-provenance-plus-direct-local-transfer-history",
                mara_fact is not None
                and str(mara_fact.get("text") or "") == FACT_TEXT
                and int(knowledge_levels(mara).get(KNOWLEDGE_KEY, 0) or 0) >= 1
                and source.get("kind") == "DIRECT_SITE_WITNESS"
                and learned_by.get("mode") == "SITE_PRESENCE"
                and str(transfer.get("source_npc_id") or "") == informant_id
                and str(transfer.get("target_npc_id") or "") == mara_id
                and transfer.get("mode") == "DIRECT_LOCAL",
                f"history={len(transfer_history)} source={transfer.get('source_npc_id')} target={transfer.get('target_npc_id')}",
            )

            completed = _find_obligation(informant, mara_id)
            check(
                "resolved-share-fact-obligation-is-one-shot-and-completed",
                completed is not None
                and completed.get("active") is False
                and str(completed.get("status") or "") == "completed"
                and str(completed.get("completed_with_npc_id") or "") == mara_id,
                f"active={None if completed is None else completed.get('active')} status={None if completed is None else completed.get('status')}",
            )

            second_refresh = refresh_fact_share_obligations(informant)
            completed_after_refresh = _find_obligation(informant, mara_id)
            check(
                "completed-one-shot-share-rule-does-not-reactivate-on-later-decision-refresh",
                not list(second_refresh.get("materialized") or [])
                and any(
                    str(row.get("rule_id") or "") == RULE_ID
                    and row.get("reason") == "ALREADY_COMPLETED"
                    for row in list(second_refresh.get("skipped") or [])
                )
                and completed_after_refresh is not None
                and completed_after_refresh.get("active") is False,
                f"materialized={second_refresh.get('materialized')} skipped={second_refresh.get('skipped')}",
            )

            second_install = ensure_v89_pilot_content()
            check(
                "v089-install-is-idempotent-and-does-not-erase-completed-social-propagation-state",
                second_install.get("success") is True
                and v89_rule_count(informant) == 1
                and (_find_obligation(informant, mara_id) or {}).get("active") is False
                and find_knowledge_fact(mara, FACT_ID) is not None,
                f"rules={v89_rule_count(informant)}",
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
                npc.db.relationships = snapshot.get("relationships")
                npc.db.decision_enabled = snapshot.get("decision_enabled")
                npc.db.current_goal = snapshot.get("current_goal")
                npc.db.destination_id = snapshot.get("destination_id")
                npc.db.current_activity = snapshot.get("current_activity")

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
            "STATE RESTORED: actor state, all persistent NPC locations/Knowledge/Facts/relationships/decision state, manifest/room state and consequence registry restored exactly"
        )
        self.caller.msg(
            "PERSISTENT CONTENT RETAINED: v0.89 authored Fact-share rule remains installed; completed social obligations are one-shot and local transfer remains owned by transfer_knowledge_fact"
        )
        self.caller.msg("========================================================")
