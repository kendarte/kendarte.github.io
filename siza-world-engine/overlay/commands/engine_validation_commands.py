import uuid

from evennia import Command

from services.action_resolution_engine import (
    ACTION_RESOLUTION_BUILD,
    action_resolution_history,
    begin_action_resolution,
    resolve_action_resolution,
    set_adventure_stat,
)
from services.consequence_engine import (
    emit_world_action,
    get_consequence_registry,
    inspect_consequence_state,
)
from services.faction_engine import membership_authority, membership_for
from services.information_engine import (
    event_information_records,
    event_knowledge_route,
    find_event_occurrence,
)
from services.job_engine import job_sites
from services.knowledge_context_engine import inspect_knowledge_context
from services.npc_decision import DEFAULT_PRIORITIES
from services.npc_simulation import find_npc, find_path, find_room
from services.relationship_engine import collect_relationship_candidates
from services.skill_engine import check_task_skills, set_skill_level, skill_level
from services.trait_engine import inspect_traits
from services.world_clock import parse_hhmm, schedule_is_active, world_clock_state


ENGINE_VALIDATION_BUILD = "0.40.0-regression-stability-checkpoint"
EVENT_ID = "TEST-WORLD-EVENT-PESCADERIA-LOCAL-001"
FACTION_ID = "TEST-FACTION-DARSENA"
MARA_ID = "NPC-KAL-DAR-MARA-001"
WORKER_B_ID = "TEST-NPC-KAL-DAR-WORKER-B"
INFORMANT_C_ID = "TEST-NPC-KAL-DAR-INFORMANT-C"


def _clone(value):
    if hasattr(value, "items"):
        try:
            return {str(key): _clone(item) for key, item in value.items()}
        except Exception:
            pass
    if isinstance(value, (list, tuple, set)):
        return [_clone(item) for item in value]
    if not isinstance(value, (str, bytes)) and hasattr(value, "__iter__"):
        try:
            return [_clone(item) for item in value]
        except Exception:
            pass
    return value


def _plain_list(value):
    try:
        return list(value or [])
    except Exception:
        return []


def _plain_dict(value):
    try:
        return {str(key): item for key, item in (value or {}).items()}
    except Exception:
        return {}


def _task_dict(value):
    try:
        return {str(key): item for key, item in value.items()}
    except Exception:
        return None


class CmdSizaValidateEngine(Command):
    """Run the v0.40 non-destructive cross-system regression checkpoint."""

    key = "siza-validate-engine"
    aliases = ["siza-validate-v40", "validate-engine"]
    locks = "cmd:perm(Admin)"

    def func(self):
        results = []

        def check(label, passed, detail=""):
            results.append(bool(passed))
            suffix = f" | {detail}" if detail else ""
            self.caller.msg(f"{'PASS' if passed else 'FAIL'} {label}{suffix}")

        self.caller.msg(f"=== SIZA ENGINE VALIDATION | {ENGINE_VALIDATION_BUILD} ===")

        mara = find_npc("Mara Vensal")
        worker_b = find_npc("Trabajador B")
        informant_c = find_npc("Informante C")

        try:
            # 1. Clock and normal/overnight schedule semantics.
            clock = world_clock_state()
            normal = {"enabled": True, "start_minute": 8 * 60, "end_minute": 17 * 60}
            overnight = {"enabled": True, "start_minute": 17 * 60, "end_minute": 8 * 60}
            clock_ok = (
                bool(clock.get("exists"))
                and parse_hhmm("08:00") == 480
                and parse_hhmm("23:59") == 1439
                and parse_hhmm("24:00") is None
                and schedule_is_active(normal, state={"day": 0, "minute": 480})
                and not schedule_is_active(normal, state={"day": 0, "minute": 1020})
                and schedule_is_active(overnight, state={"day": 0, "minute": 1380})
                and schedule_is_active(overnight, state={"day": 0, "minute": 420})
                and not schedule_is_active(overnight, state={"day": 0, "minute": 720})
            )
            check(
                "world-clock-and-shift-semantics",
                clock_ok,
                f"time=day {clock.get('day')} {clock.get('time')} rate={clock.get('minutes_per_tick')}",
            )

            # 2. Persistent pilot graph uses real exits and still has the expected two-hop route.
            plaza = find_room("Plaza de Recepcion", "CAR-KAL-DAR-003")
            pescaderia = find_room("Pescaderia de Darsena", "CAR-KAL-DAR-007")
            forward = find_path(plaza, pescaderia) if plaza and pescaderia else None
            backward = find_path(pescaderia, plaza) if plaza and pescaderia else None
            graph_ok = (
                plaza is not None
                and pescaderia is not None
                and forward is not None
                and backward is not None
                and len(forward) == 2
                and len(backward) == 2
                and all(getattr(exit_obj, "destination", None) for exit_obj in forward + backward)
            )
            check(
                "native-exit-pilot-graph",
                graph_ok,
                f"Plaza->Pescaderia={None if forward is None else len(forward)} Pescaderia->Plaza={None if backward is None else len(backward)}",
            )

            # 3. Stable NPC identity fixtures from the simulation/social harness.
            ids = [
                str(getattr(getattr(npc, "db", None), "npc_id", "") or "")
                for npc in (mara, worker_b, informant_c)
                if npc is not None
            ]
            identity_ok = (
                mara is not None
                and worker_b is not None
                and informant_c is not None
                and str(mara.db.npc_id or "") == MARA_ID
                and str(worker_b.db.npc_id or "") == WORKER_B_ID
                and str(informant_c.db.npc_id or "") == INFORMANT_C_ID
                and len(set(ids)) == 3
            )
            check("stable-npc-identities", identity_ok, f"ids={ids}")

            # 4. Decision baseline contract. Concrete authored ORDERs may override this fallback.
            baseline_ok = (
                DEFAULT_PRIORITIES.get("DANGER") == 100
                and DEFAULT_PRIORITIES.get("EVENT") == 80
                and DEFAULT_PRIORITIES.get("NEED") == 70
                and DEFAULT_PRIORITIES.get("JOB") == 60
                and DEFAULT_PRIORITIES.get("RELATIONSHIP") == 50
                and DEFAULT_PRIORITIES.get("ROUTINE") == 10
            )
            check(
                "decision-baseline-contract",
                baseline_ok,
                "DANGER100 EVENT80 NEED70 JOB60 REL50 ROUTINE10",
            )

            # 5. Faction/rank/authority persistence from v0.24/v0.25.
            mara_mem = membership_for(mara, FACTION_ID, active_only=True) if mara else None
            b_mem = membership_for(worker_b, FACTION_ID, active_only=True) if worker_b else None
            mara_auth = membership_authority(mara, FACTION_ID) if mara else None
            b_auth = membership_authority(worker_b, FACTION_ID) if worker_b else None
            faction_ok = (
                bool(mara_mem)
                and bool(b_mem)
                and str(mara_mem.get("rank_id") or "") == "TEST_MEMBER"
                and str(b_mem.get("rank_id") or "") == "TEST_SUPERVISOR"
                and int(mara_mem.get("loyalty_bias", 0) or 0) == -10
                and int(b_mem.get("loyalty_bias", 0) or 0) == 10
                and mara_auth == 10
                and b_auth == 30
            )
            check(
                "faction-rank-authority-persistence",
                faction_ok,
                f"Mara={mara_auth}/{None if not mara_mem else mara_mem.get('loyalty_bias')} B={b_auth}/{None if not b_mem else b_mem.get('loyalty_bias')}",
            )

            # 6. Knowledge-by-doing persisted and remains an explicit fact/effect, not a skill alias.
            kctx = inspect_knowledge_context(mara) if mara else {"levels": {}, "facts": []}
            workflow_level = int((kctx.get("levels") or {}).get("TEST_PESCADERIA_WORKFLOW", 0) or 0)
            exp_fact = next(
                (
                    row
                    for row in (kctx.get("facts") or [])
                    if str(row.get("fact_id") or "") == "TEST-KNOWLEDGE-PESCADERIA-EXPERIENCE-001"
                ),
                None,
            )
            knowledge_ok = workflow_level >= 1 and bool(exp_fact and exp_fact.get("known"))
            check(
                "knowledge-learning-persistence",
                knowledge_ok,
                f"workflow={workflow_level} fact_known={bool(exp_fact and exp_fact.get('known'))}",
            )

            # 7. Trait harness persists without silently enabling personality effects.
            trait_rows = (inspect_traits(worker_b).get("traits") or []) if worker_b else []
            trait_map = {str(row.get("id") or ""): row for row in trait_rows}
            diligence = trait_map.get("TEST-TRAIT-WORKER-B-DILIGENCE-001")
            aversion = trait_map.get("TEST-TRAIT-WORKER-B-ORDER-AVERSION-001")
            traits_ok = (
                diligence is not None
                and aversion is not None
                and not bool(diligence.get("enabled"))
                and not bool(aversion.get("enabled"))
            )
            check(
                "trait-harness-remains-explicit-and-disabled",
                traits_ok,
                f"diligence={None if diligence is None else diligence.get('enabled')} aversion={None if aversion is None else aversion.get('enabled')}",
            )

            # 8. Real pilot JOB task still carries the hard skill requirement and B still qualifies.
            pilot_task = None
            for site in job_sites():
                for raw in _plain_list(getattr(site.db, "job_tasks", [])):
                    task = _task_dict(raw)
                    if task and str(task.get("id") or "") == "TEST-WORKORDER-PESCADERIA-001":
                        pilot_task = task
                        break
                if pilot_task:
                    break
            pilot_skill_check = check_task_skills(worker_b, pilot_task) if worker_b and pilot_task else {"eligible": False}
            requirements = (pilot_skill_check.get("requirements") or [])
            real_job_skill_ok = (
                pilot_task is not None
                and any(
                    str(row.get("skill_id") or "") == "TEST_DARSENA_WORK"
                    and int(row.get("min_level", 0) or 0) == 1
                    for row in requirements
                )
                and bool(pilot_skill_check.get("eligible"))
                and skill_level(worker_b, "TEST_DARSENA_WORK") >= 1
            )
            check(
                "job-skill-hard-gate-persistence",
                real_job_skill_ok,
                f"B_skill={0 if not worker_b else skill_level(worker_b, 'TEST_DARSENA_WORK')} eligible={pilot_skill_check.get('eligible')}",
            )

            # 9. Synthetic skill gate: prove 0 blocks and 1 permits, then restore C exactly.
            if informant_c:
                original_skills = _clone(getattr(informant_c.db, "skills", {}))
                try:
                    synthetic_task = {
                        "id": "V040-SKILL-GATE",
                        "skill_requirements": [
                            {"skill_id": "V040_TEST_SKILL", "min_level": 1, "name": "V040 Test Skill"}
                        ],
                    }
                    set_skill_level(informant_c, "V040_TEST_SKILL", 0)
                    blocked = check_task_skills(informant_c, synthetic_task)
                    set_skill_level(informant_c, "V040_TEST_SKILL", 1)
                    allowed = check_task_skills(informant_c, synthetic_task)
                    check(
                        "skill-gate-negative-and-positive",
                        not bool(blocked.get("eligible")) and bool(allowed.get("eligible")),
                        f"level0={blocked.get('eligible')} level1={allowed.get('eligible')}",
                    )
                finally:
                    informant_c.db.skills = original_skills
            else:
                check("skill-gate-negative-and-positive", False, "Informante C missing")

            # 10. v0.33.1 archived occurrence remains addressable after restart.
            _site4, event4 = find_event_occurrence(EVENT_ID, occurrence=4)
            history_ok = bool(
                event4
                and int(event4.get("occurrence", 0) or 0) == 4
                and str(event4.get("status") or "").lower() == "historical"
            )
            check(
                "event-occurrence-history-persistence",
                history_ok,
                f"occ4_status={None if not event4 else event4.get('status')}",
            )

            # 11. v0.37 chain persisted: B witnessed 10, C heard hop1, Mara heard hop2 from C.
            _site10, event10 = find_event_occurrence(EVENT_ID, occurrence=10)
            b_route = event_knowledge_route(worker_b, event10) if worker_b and event10 else {"via": "NONE"}
            c_route = event_knowledge_route(informant_c, event10) if informant_c and event10 else {"via": "NONE"}
            mara_route = event_knowledge_route(mara, event10) if mara and event10 else {"via": "NONE"}
            c_record = (c_route.get("record") or {})
            mara_record = (mara_route.get("record") or {})
            provenance_ok = (
                event10 is not None
                and b_route.get("via") == "WITNESSED"
                and c_route.get("via") == "REPORTED"
                and int(c_record.get("hops", 0) or 0) == 1
                and str(c_record.get("origin_npc_id") or "") == WORKER_B_ID
                and mara_route.get("via") == "REPORTED"
                and int(mara_record.get("hops", 0) or 0) == 2
                and str(mara_record.get("origin_npc_id") or "") == WORKER_B_ID
                and str(mara_record.get("source_npc_id") or "") == INFORMANT_C_ID
            )
            check(
                "information-provenance-chain-persistence",
                provenance_ok,
                f"B={b_route.get('via')} C={c_route.get('via')}/{c_record.get('hops')} Mara={mara_route.get('via')}/{mara_record.get('hops')}",
            )

            # 12. Reports never rewrite the direct-witness snapshot.
            aware10 = {str(value) for value in _plain_list((event10 or {}).get("aware_npc_ids")) if value}
            awareness_ok = (
                WORKER_B_ID in aware10
                and INFORMANT_C_ID not in aware10
                and MARA_ID not in aware10
            )
            check(
                "witness-snapshot-separate-from-reported-information",
                awareness_ok,
                f"aware={sorted(aware10)}",
            )

            # 13. Completed social intent from C -> Mara survived restart and is no longer a candidate.
            c_relationships = _plain_dict(getattr(informant_c.db, "relationships", {})) if informant_c else {}
            c_to_mara = _plain_dict(c_relationships.get(MARA_ID))
            c_obligations = [_plain_dict(row) for row in _plain_list(c_to_mara.get("obligations"))]
            completed_inform = next(
                (
                    row
                    for row in c_obligations
                    if str(row.get("id") or "")
                    == f"INFORM-{MARA_ID}-{EVENT_ID}-10"
                ),
                None,
            )
            social_persist_ok = bool(
                completed_inform
                and not bool(completed_inform.get("active"))
                and str(completed_inform.get("status") or "").lower() == "completed"
            )
            check(
                "completed-social-intent-persistence",
                social_persist_ok,
                f"status={None if not completed_inform else completed_inform.get('status')} active={None if not completed_inform else completed_inform.get('active')}",
            )

            # 14. Dynamic relationship target resolution using a temporary generic obligation.
            if worker_b and informant_c and informant_c.location:
                original_relationships = _clone(getattr(worker_b.db, "relationships", {}))
                original_decision_enabled = bool(worker_b.db.decision_enabled)
                try:
                    relationships = _plain_dict(_clone(original_relationships))
                    relation = _plain_dict(relationships.get(INFORMANT_C_ID))
                    obligations = [_plain_dict(row) for row in _plain_list(relation.get("obligations"))]
                    obligations.append(
                        {
                            "id": "V040-DYNAMIC-RELATIONSHIP",
                            "kind": "CHECKPOINT",
                            "active": True,
                            "status": "pending",
                            "priority": 52,
                            "one_shot": True,
                            "canon_status": "prototype",
                        }
                    )
                    relation.update(
                        {
                            "target_type": "NPC",
                            "target_npc_id": INFORMANT_C_ID,
                            "target_dbref": int(informant_c.id),
                            "target_name": informant_c.key,
                            "obligations": obligations,
                        }
                    )
                    relationships[INFORMANT_C_ID] = relation
                    worker_b.db.relationships = relationships
                    worker_b.db.decision_enabled = True
                    candidates = collect_relationship_candidates(worker_b)
                    row = next(
                        (
                            item
                            for item in candidates
                            if str(item.get("relationship_obligation_id") or "")
                            == "V040-DYNAMIC-RELATIONSHIP"
                        ),
                        None,
                    )
                    expected_room_id = str(getattr(informant_c.location.db, "room_id", "") or "")
                    dynamic_ok = bool(
                        row
                        and str(row.get("relationship_target_npc_id") or "") == INFORMANT_C_ID
                        and str(row.get("target_room_id") or "") == expected_room_id
                        and int(row.get("priority", 0) or 0) == 52
                    )
                    check(
                        "relationship-target-is-dynamic-location",
                        dynamic_ok,
                        f"target_room={None if not row else row.get('target_room_id')} expected={expected_room_id}",
                    )
                finally:
                    worker_b.db.relationships = original_relationships
                    worker_b.db.decision_enabled = original_decision_enabled
            else:
                check("relationship-target-is-dynamic-location", False, "B/C/location missing")

            # 15. Consequence registry/rules and the v0.37 chain are still persisted.
            consequence = inspect_consequence_state()
            rule_ids = {str(row.get("id") or "") for row in (consequence.get("rules") or [])}
            log = consequence.get("action_log") or []
            logged_ids = {str(row.get("action_id") or "") for row in log}
            consequence_ok = (
                bool(consequence.get("registry_exists"))
                and "TEST-CONSEQUENCE-LOCAL-EVENT-INFORM-C-001" in rule_ids
                and "TEST-CONSEQUENCE-INFORMATION-FORWARD-MARA-001" in rule_ids
                and f"EVENT_ACKNOWLEDGED:{EVENT_ID}:10:{WORKER_B_ID}" in logged_ids
                and any(
                    action_id.startswith(
                        f"INFORMATION_SHARED:{EVENT_ID}:10:{WORKER_B_ID}:{INFORMANT_C_ID}:"
                    )
                    for action_id in logged_ids
                )
            )
            check(
                "consequence-chain-persistence",
                consequence_ok,
                f"rules={len(rule_ids)} actions={len(logged_ids)}",
            )

            # 16. Exactly-once action processing, with registry state restored after the test.
            registry = get_consequence_registry(create=False)
            if registry is not None:
                original_processed = _clone(getattr(registry.db, "processed_action_ids", []))
                original_log = _clone(getattr(registry.db, "action_log", []))
                try:
                    action_id = f"V040:NOOP:{uuid.uuid4().hex}"
                    first = emit_world_action(
                        {
                            "action_id": action_id,
                            "action_type": "V040_VALIDATOR_NOOP",
                            "actor_npc_id": INFORMANT_C_ID,
                            "actor_name": informant_c.key if informant_c else "Informante de Prueba C",
                            "recipient_ids": [],
                        }
                    )
                    second = emit_world_action(
                        {
                            "action_id": action_id,
                            "action_type": "V040_VALIDATOR_NOOP",
                            "actor_npc_id": INFORMANT_C_ID,
                            "actor_name": informant_c.key if informant_c else "Informante de Prueba C",
                            "recipient_ids": [],
                        }
                    )
                    check(
                        "consequence-actions-process-exactly-once",
                        first.get("status") == "PROCESSED" and second.get("status") == "ALREADY_PROCESSED",
                        f"first={first.get('status')} second={second.get('status')}",
                    )
                finally:
                    registry.db.processed_action_ids = original_processed
                    registry.db.action_log = original_log
            else:
                check("consequence-actions-process-exactly-once", False, "registry missing")

            # 17. Action-resolution lifecycle regression, fully restored after test.
            if informant_c:
                original_stats = _clone(getattr(informant_c.db, "adventure_stats", {}))
                original_history = _clone(getattr(informant_c.db, "action_resolution_history", []))
                try:
                    informant_c.db.adventure_stats = {}
                    informant_c.db.action_resolution_history = []
                    set_adventure_stat(informant_c, "PER", 4)
                    rid = f"V040-RES-{uuid.uuid4().hex}"
                    pending = begin_action_resolution(
                        informant_c,
                        {
                            "id": "V040-DIRECT-PER",
                            "trigger": "OBSTACLE",
                            "mode": "DIRECT",
                            "stat": "PER",
                            "difficulty": 7,
                        },
                        resolution_id=rid,
                    )
                    invalid = resolve_action_resolution(
                        informant_c,
                        rid,
                        "ACTOR_WIN",
                        "V040_VALIDATOR_PROVIDER",
                    )
                    resolved = resolve_action_resolution(
                        informant_c,
                        rid,
                        "SUCCESS",
                        "V040_VALIDATOR_PROVIDER",
                        resolution_data={"checkpoint": "v0.40"},
                    )
                    duplicate = resolve_action_resolution(
                        informant_c,
                        rid,
                        "FAILURE",
                        "V040_SECOND_PROVIDER",
                    )
                    history = action_resolution_history(informant_c)
                    resolution_ok = (
                        pending.get("status") == "PENDING_RESOLUTION"
                        and invalid.get("status") == "INVALID_OUTCOME"
                        and resolved.get("status") == "RESOLVED"
                        and resolved.get("outcome") == "SUCCESS"
                        and duplicate.get("status") == "ALREADY_RESOLVED"
                        and len(history) == 1
                        and str(history[0].get("resolution_id") or "") == rid
                    )
                    check(
                        "action-resolution-lifecycle-regression",
                        resolution_ok,
                        f"pending={pending.get('status')} invalid={invalid.get('status')} resolved={resolved.get('status')} duplicate={duplicate.get('status')}",
                    )
                finally:
                    informant_c.db.adventure_stats = original_stats
                    informant_c.db.action_resolution_history = original_history
            else:
                check("action-resolution-lifecycle-regression", False, "Informante C missing")

        except Exception as exc:
            check("validator-runtime", False, f"error={type(exc).__name__}: {exc}")

        passed = sum(1 for value in results if value)
        total = len(results)
        self.caller.msg(f"RESULT: {passed}/{total} PASS")
        self.caller.msg("TEMP STATE RESTORED: skills, relationships, consequence log and action-resolution harness")
        self.caller.msg("===============================================================")
