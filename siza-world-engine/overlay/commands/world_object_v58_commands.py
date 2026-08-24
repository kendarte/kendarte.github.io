from evennia import Command

from services.consequence_engine import get_consequence_registry
from services.knowledge_context_engine import (
    fact_knowledge_state,
    knowledge_facts,
    knowledge_levels,
    set_knowledge_level,
)
from services.knowledge_fact_engine import find_knowledge_fact, upsert_knowledge_fact
from services.knowledge_fact_transfer_engine import FACT_TRANSFER_BUILD, transfer_knowledge_fact
from services.npc_simulation import find_npc
from world.upgrade_pilot_v51 import MANIFEST_ID
from world.upgrade_pilot_v57 import (
    ACTION_ID as V57_ACTION_ID,
    FACT_ID,
    FACT_TEXT,
    FACT_TOPIC,
    KNOWLEDGE_KEY,
)
from world.upgrade_pilot_v58 import (
    TARGET_NPC_ID,
    TARGET_QUERY,
    ensure_v58_pilot_context,
    reset_v58_target_fact,
)


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


def _plain_dict(value):
    try:
        return {str(key): item for key, item in (value or {}).items()}
    except Exception:
        return {}


def _plain_list(value):
    try:
        return list(value or [])
    except Exception:
        return []


def _fact_count(entity, fact_id):
    return sum(1 for row in knowledge_facts(entity) if str(row.get("id") or "") == str(fact_id or ""))


def _pilot_source_fact(site, manifest):
    return {
        "id": FACT_ID,
        "topic": FACT_TOPIC,
        "text": FACT_TEXT,
        "knowledge_key": KNOWLEDGE_KEY,
        "required_level": 1,
        "canon_status": "prototype",
        "source": {
            "object_id": MANIFEST_ID,
            "object_name": manifest.key,
            "site_room_id": str(getattr(site.db, "room_id", "") or ""),
            "site_name": site.key,
            "object_dbref": int(manifest.id),
            "site_dbref": int(site.id),
        },
        "learned_by": {
            "object_action_id": V57_ACTION_ID,
            "attempt_id": "V058-SOURCE-SEED",
            "provider": "SIZA_DIRECT_D6",
            "outcome": "SUCCESS",
            "action_id": "OBJECT_ACTION_RESOLVED:V058-SOURCE-SEED",
        },
    }


class CmdSizaShareFactV58(Command):
    """Share one persistent Fact known by the caller with a local Siza NPC."""

    key = "siza-share-fact"
    aliases = ["share-fact"]
    locks = "cmd:all()"

    def func(self):
        parts = [part.strip() for part in (self.args or "").split("|")]
        if len(parts) != 2 or not all(parts):
            self.caller.msg("Uso: siza-share-fact <NPC> | <FACT_ID>")
            return
        target = find_npc(parts[0])
        if not target:
            self.caller.msg("No identifico ese NPC de Siza.")
            return
        result = transfer_knowledge_fact(self.caller, target, parts[1])
        if not result.get("success"):
            reason = result.get("reason")
            if reason == "NOT_COLOCATED":
                self.caller.msg("Debes estar en el mismo lugar que ese NPC para compartir el hecho.")
            elif reason in {"SOURCE_FACT_NOT_FOUND", "SOURCE_DOES_NOT_KNOW_FACT"}:
                self.caller.msg("No conoces ese hecho de forma utilizable.")
            else:
                self.caller.msg(f"No se pudo compartir el hecho. reason={reason}")
            return
        if result.get("reason") == "ALREADY_TRANSFERRED":
            self.caller.msg(f"{target.key} ya recibió ese hecho de ti.")
            return
        self.caller.msg(
            f"[FACT SHARED] {self.caller.key} -> {target.key} | fact={result.get('fact_id')} | "
            f"knowledge={result.get('knowledge_key')} {result.get('knowledge_after')} | "
            f"history={result.get('transfer_history_count')}"
        )


class CmdSizaSharePilotFactV58(Command):
    """Player-facing pilot shortcut for sharing the v0.57 finding."""

    key = "compartir hallazgo"
    aliases = ["informar hallazgo"]
    locks = "cmd:all()"

    def func(self):
        query = (self.args or "").strip()
        query = query[4:].strip() if query.lower().startswith("con ") else query
        target = find_npc(query or TARGET_QUERY)
        if not target:
            self.caller.msg("No identifico con quién quieres compartir el hallazgo.")
            return
        result = transfer_knowledge_fact(self.caller, target, FACT_ID)
        if not result.get("success"):
            reason = result.get("reason")
            if reason == "NOT_COLOCATED":
                self.caller.msg("Debes estar junto a esa persona para contarle el hallazgo.")
            elif reason in {"SOURCE_FACT_NOT_FOUND", "SOURCE_DOES_NOT_KNOW_FACT"}:
                self.caller.msg("Todavía no conoces ese hallazgo con suficiente certeza para compartirlo.")
            else:
                self.caller.msg(f"No puedes compartir ese hallazgo ahora. reason={reason}")
            return
        if result.get("reason") == "ALREADY_TRANSFERRED":
            self.caller.msg(f"{target.key} ya conoce ese hallazgo porque se lo contaste.")
            return
        self.caller.msg(
            f"Compartes con {target.key} lo que descubriste en el manifiesto. "
            f"Ahora puede reconocer ese hecho como conocimiento propio."
        )


class CmdSizaNPCFactsV58(Command):
    """Inspect structured Facts known by one Siza NPC, including transfer provenance."""

    key = "siza-npc-facts"
    aliases = ["npc-facts"]
    locks = "cmd:all()"

    def func(self):
        target = find_npc((self.args or "").strip())
        if not target:
            self.caller.msg("Uso: siza-npc-facts <NPC>")
            return
        self.caller.msg(f"=== SIZA NPC FACTS | {FACT_TRANSFER_BUILD} ===")
        self.caller.msg(f"NPC: {target.key} | npc_id={str(getattr(target.db, 'npc_id', '') or '')}")
        facts = knowledge_facts(target)
        if not facts:
            self.caller.msg("Facts: NONE")
            self.caller.msg("========================================================")
            return
        self.caller.msg(f"Facts: {len(facts)}")
        for fact in facts:
            state = fact_knowledge_state(target, fact)
            source = _plain_dict(fact.get("source"))
            learned = _plain_dict(fact.get("learned_by"))
            transfers = _plain_list(fact.get("transfer_history"))
            self.caller.msg(
                f"  {fact.get('id')} | known={bool(state.get('known'))} | "
                f"knowledge={state.get('knowledge_key')} {state.get('level')}/{state.get('required_level')}"
            )
            self.caller.msg(f"    topic={fact.get('topic')}")
            self.caller.msg(f"    text={fact.get('text')}")
            self.caller.msg(
                f"    original_source={source.get('object_name')} | object_id={source.get('object_id')} | "
                f"site={source.get('site_name')} ({source.get('site_room_id')})"
            )
            self.caller.msg(
                f"    original_learned_by={learned.get('object_action_id')} | provider={learned.get('provider')} | "
                f"outcome={learned.get('outcome')}"
            )
            for transfer in transfers:
                row = _plain_dict(transfer)
                self.caller.msg(
                    f"    transferred_from={row.get('source_name')}#{row.get('source_dbref')} | "
                    f"mode={row.get('mode')} | transfer_id={row.get('id')}"
                )
        self.caller.msg("========================================================")


class CmdSizaResetV58(Command):
    """Reset only the v0.58 transferred Fact on the pilot target NPC."""

    key = "siza-reset-v58"
    aliases = ["reset-v58"]
    locks = "cmd:perm(Admin)"

    def func(self):
        result = reset_v58_target_fact()
        if not result.get("success"):
            self.caller.msg(f"[V0.58 RESET] FAIL | reason={result.get('reason')}")
            return
        target = result.get("target")
        self.caller.msg(f"=== SIZA v0.58 RESET | {FACT_TRANSFER_BUILD} ===")
        self.caller.msg(
            f"PASS target fact reset | target={target.key}#{target.id} | "
            f"{KNOWLEDGE_KEY}: {result.get('knowledge_before') if result.get('knowledge_before') is not None else 'UNSET'} -> UNSET | "
            f"fact_removed={result.get('fact_removed')}"
        )
        self.caller.msg("No se tocaron Facts/Knowledge del jugador ni estados v0.51-v0.57.")
        self.caller.msg("========================================================")


class CmdSizaValidateV58(Command):
    """Validate local persistent Fact transfer from a real Character to a persistent NPC."""

    key = "siza-validate-v58"
    aliases = ["validate-v58"]
    locks = "cmd:perm(Admin)"

    def func(self):
        source = self.caller
        context = ensure_v58_pilot_context()
        if not source or not bool(context.get("success")):
            self.caller.msg(f"[V0.58 VALIDATION] FAIL | context={context}")
            return
        site = context.get("site")
        manifest = context.get("manifest")
        target = context.get("target")
        registry = get_consequence_registry(create=True)

        original_source_location = source.location
        original_source_knowledge = _clone(getattr(source.db, "knowledge", {}))
        original_source_facts = _clone(getattr(source.db, "knowledge_facts", []))
        original_target_location = target.location
        original_target_knowledge = _clone(getattr(target.db, "knowledge", {}))
        original_target_facts = _clone(getattr(target.db, "knowledge_facts", []))
        original_processed = _clone(getattr(registry.db, "processed_action_ids", []))
        original_log = _clone(getattr(registry.db, "action_log", []))
        results = []

        def check(label, passed, detail=""):
            results.append(bool(passed))
            self.caller.msg(f"{'PASS' if passed else 'FAIL'} {label}{' | ' + detail if detail else ''}")

        self.caller.msg(f"=== SIZA VALIDATION v0.58 | {FACT_TRANSFER_BUILD} ===")
        self.caller.msg(
            f"Source Character: {source.key}#{source.id} | target={target.key}#{target.id} | fact={FACT_ID}"
        )

        try:
            if source.location != site:
                source.move_to(site, quiet=True)
            if target.location != site:
                target.move_to(site, quiet=True)

            source_levels = knowledge_levels(source)
            source_levels.pop(KNOWLEDGE_KEY, None)
            source.db.knowledge = source_levels
            source.db.knowledge_facts = [row for row in knowledge_facts(source) if str(row.get("id") or "") != FACT_ID]
            target_levels = knowledge_levels(target)
            target_levels.pop(KNOWLEDGE_KEY, None)
            target.db.knowledge = target_levels
            target.db.knowledge_facts = [row for row in knowledge_facts(target) if str(row.get("id") or "") != FACT_ID]

            check(
                "pilot-target-is-persistent-informant-and-colocated",
                str(getattr(target.db, "npc_id", "") or "") == TARGET_NPC_ID
                and source.location == target.location == site,
                f"npc_id={getattr(target.db, 'npc_id', None)} site={site.key}",
            )

            missing = transfer_knowledge_fact(source, target, FACT_ID)
            check(
                "transfer-is-blocked-when-source-does-not-have-fact",
                missing.get("success") is False and missing.get("reason") == "SOURCE_FACT_NOT_FOUND",
                f"reason={missing.get('reason')}",
            )

            seed = _pilot_source_fact(site, manifest)
            upsert_knowledge_fact(source, seed)
            still_unknown = transfer_knowledge_fact(source, target, FACT_ID)
            check(
                "fact-record-alone-does-not-substitute-for-source-knowledge-level",
                still_unknown.get("success") is False and still_unknown.get("reason") == "SOURCE_DOES_NOT_KNOW_FACT",
                f"reason={still_unknown.get('reason')}",
            )

            set_knowledge_level(source, KNOWLEDGE_KEY, 1)
            before_source = find_knowledge_fact(source, FACT_ID)
            transferred = transfer_knowledge_fact(source, target, FACT_ID)
            target_fact = find_knowledge_fact(target, FACT_ID)
            check(
                "known-fact-transfers-from-real-character-to-npc",
                transferred.get("success") is True
                and transferred.get("reason") == "FACT_TRANSFERRED"
                and transferred.get("target_known") is True
                and knowledge_levels(target).get(KNOWLEDGE_KEY) == 1
                and _fact_count(target, FACT_ID) == 1,
                f"reason={transferred.get('reason')} target_known={transferred.get('target_known')} knowledge={knowledge_levels(target).get(KNOWLEDGE_KEY)} facts={_fact_count(target, FACT_ID)}",
            )

            source_original = _plain_dict((before_source or {}).get("source"))
            target_original = _plain_dict((target_fact or {}).get("source"))
            source_learned = _plain_dict((before_source or {}).get("learned_by"))
            target_learned = _plain_dict((target_fact or {}).get("learned_by"))
            check(
                "transfer-preserves-original-source-and-learning-provenance",
                target_fact is not None
                and target_fact.get("text") == FACT_TEXT
                and target_original == source_original
                and target_learned == source_learned
                and target_original.get("object_id") == MANIFEST_ID
                and target_learned.get("object_action_id") == V57_ACTION_ID,
                f"source={target_original} learned_by={target_learned}",
            )

            transfers = _plain_list((target_fact or {}).get("transfer_history"))
            transfer_row = _plain_dict(transfers[0]) if transfers else {}
            check(
                "recipient-fact-adds-separate-transfer-provenance",
                len(transfers) == 1
                and transfer_row.get("source_dbref") == int(source.id)
                and transfer_row.get("source_name") == source.key
                and transfer_row.get("target_npc_id") == TARGET_NPC_ID
                and transfer_row.get("mode") == "DIRECT_LOCAL",
                f"transfer={transfer_row}",
            )

            check(
                "transferred-fact-is-known-through-normal-npc-knowledge-context",
                target_fact is not None and fact_knowledge_state(target, target_fact).get("known") is True,
                f"known={None if target_fact is None else fact_knowledge_state(target, target_fact).get('known')}",
            )

            consequence = transferred.get("action_consequence") or {}
            check(
                "fact-transfer-emits-structured-world-action",
                consequence.get("status") == "PROCESSED"
                and any(
                    str(row.get("action_type") or "") == "KNOWLEDGE_FACT_SHARED"
                    and str(row.get("fact_id") or "") == FACT_ID
                    for row in _plain_list(getattr(registry.db, "action_log", []))
                ),
                f"consequence={consequence.get('status')}",
            )

            repeated = transfer_knowledge_fact(source, target, FACT_ID)
            repeated_fact = find_knowledge_fact(target, FACT_ID)
            check(
                "same-source-target-fact-transfer-is-idempotent",
                repeated.get("success") is True
                and repeated.get("reason") == "ALREADY_TRANSFERRED"
                and knowledge_levels(target).get(KNOWLEDGE_KEY) == 1
                and _fact_count(target, FACT_ID) == 1
                and len(_plain_list((repeated_fact or {}).get("transfer_history"))) == 1,
                f"reason={repeated.get('reason')} facts={_fact_count(target, FACT_ID)} history={len(_plain_list((repeated_fact or {}).get('transfer_history')))}",
            )

            after_source = find_knowledge_fact(source, FACT_ID)
            check(
                "sharing-does-not-mutate-source-fact",
                after_source == before_source and knowledge_levels(source).get(KNOWLEDGE_KEY) == 1,
                f"source_fact_unchanged={after_source == before_source}",
            )

            reset = reset_v58_target_fact()
            check(
                "v058-reset-removes-only-target-copy",
                reset.get("success") is True
                and find_knowledge_fact(target, FACT_ID) is None
                and knowledge_levels(target).get(KNOWLEDGE_KEY, 0) == 0
                and find_knowledge_fact(source, FACT_ID) is not None
                and knowledge_levels(source).get(KNOWLEDGE_KEY) == 1,
                f"target_fact={find_knowledge_fact(target, FACT_ID) is not None} source_fact={find_knowledge_fact(source, FACT_ID) is not None}",
            )

        except Exception as exc:
            check("validator-runtime", False, f"error={exc}")
        finally:
            try:
                if source.location != original_source_location:
                    source.move_to(original_source_location, quiet=True)
            except Exception:
                pass
            try:
                if target.location != original_target_location:
                    target.move_to(original_target_location, quiet=True)
            except Exception:
                pass
            source.db.knowledge = original_source_knowledge
            source.db.knowledge_facts = original_source_facts
            target.db.knowledge = original_target_knowledge
            target.db.knowledge_facts = original_target_facts
            registry.db.processed_action_ids = original_processed
            registry.db.action_log = original_log

        passed = sum(1 for row in results if row)
        total = len(results)
        self.caller.msg(f"RESULT: {passed}/{total} PASS")
        self.caller.msg(
            "STATE RESTORED: source location/Knowledge/Facts, target location/Knowledge/Facts and consequence log restored"
        )
        self.caller.msg(
            "PERSISTENT SYSTEM RETAINED: generic Fact Transfer service + player share command + NPC Fact inspector"
        )
        self.caller.msg("========================================================")
